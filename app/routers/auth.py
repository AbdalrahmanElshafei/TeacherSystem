from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import (
    SESSION_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    SESSION_EXPIRE_HOURS,
    logger
)
from app.models.user import Teacher, Assistant
from app.repositories.user_repo import UserRepository
from app.core.security import (
    verify_password,
    generate_session_token,
    generate_csrf_token,
    hash_token
)
from app.core.rate_limiter import login_rate_limiter
from app.core.dependencies import get_current_user, get_current_session, AuthenticatedUser
from app.schemas.auth import (
    FirstRunSetupRequest,
    LoginRequest,
    LoginResponse,
    SessionStatusResponse
)
from app.schemas.user import TeacherResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication & Setup"])

@router.get("/setup-status", summary="Check if first-run setup is required")
def check_setup_status(db: Session = Depends(get_db)):
    """Check whether the system has any existing teacher account."""
    count = UserRepository.count_teachers(db)
    return {
        "setup_required": count == 0,
        "message": "First-run setup required." if count == 0 else "System is initialized."
    }

@router.post("/first-run-setup", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED, summary="Initialize primary teacher account")
def first_run_setup(payload: FirstRunSetupRequest, db: Session = Depends(get_db)):
    """
    Creates the first primary teacher account.
    Permanently locked once the first teacher is created.
    Atomically guarantees only one initial teacher can ever be created, even under concurrent requests.
    """
    teacher = UserRepository.create_initial_teacher_atomic(
        db=db,
        username=payload.username,
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password
    )
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First-run setup is already complete. Please login."
        )

    logger.info(f"First-run setup completed successfully. Teacher account created: {teacher.username}")
    return teacher

@router.post("/login", response_model=LoginResponse, summary="Login with username and password")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticates Teacher or Assistant.
    Sets HttpOnly session cookie and accessible CSRF cookie for browser defense.
    Also returns session token in payload for Bearer header authentication (mobile clients).
    Protected against brute-force attacks via LoginRateLimiter.
    """
    # 0. Check rate limiter before expensive password hashing
    client_ip = request.client.host if request.client else "127.0.0.1"
    login_rate_limiter.check_rate_limit(ip=client_ip, username=payload.username)

    # 1. Attempt teacher login first
    teacher = UserRepository.get_teacher_by_username(db, payload.username)
    authenticated_user = None
    user_type = None
    teacher_id = None

    if teacher and teacher.is_active:
        if verify_password(payload.password, teacher.hashed_password):
            authenticated_user = teacher
            user_type = "teacher"
            teacher_id = teacher.id

    # 2. If not teacher, attempt assistant login
    if not authenticated_user:
        assistant = UserRepository.get_assistant_by_username(db, payload.username)
        if assistant and assistant.is_active:
            if verify_password(payload.password, assistant.hashed_password):
                authenticated_user = assistant
                user_type = "assistant"
                teacher_id = assistant.teacher_id

    if not authenticated_user:
        login_rate_limiter.record_failure(ip=client_ip, username=payload.username)
        logger.warning(f"Failed login attempt for username: {payload.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # Successful login resets failed attempts for this user/ip
    login_rate_limiter.record_success(ip=client_ip, username=payload.username)

    # 3. Create cryptographically secure session storing only the SHA-256 fingerprint
    raw_session_token = generate_session_token()
    token_hash = hash_token(raw_session_token)
    csrf_token = generate_csrf_token()

    UserRepository.create_session(
        db=db,
        session_token=token_hash,  # Store ONLY the SHA-256 fingerprint in database
        csrf_token=csrf_token,
        user_type=user_type,
        user_id=authenticated_user.id,
        teacher_id=teacher_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:250]
    )

    # 4. Set HttpOnly Cookie for session using the raw token
    max_age_seconds = SESSION_EXPIRE_HOURS * 3600
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=max_age_seconds,
        httponly=True,
        samesite="lax",
        path="/"
    )

    # 5. Set CSRF cookie (NOT HttpOnly so frontend JS can read and send in X-CSRF-Token header)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age_seconds,
        httponly=False,
        samesite="lax",
        path="/"
    )

    logger.info(f"User {authenticated_user.username} ({user_type}) logged in successfully.")
    return LoginResponse(
        success=True,
        message="Login successful.",
        user_type=user_type,
        user_id=authenticated_user.id,
        teacher_id=teacher_id,
        csrf_token=csrf_token,
        session_token=raw_session_token
    )

@router.post("/logout", summary="Logout and invalidate session")
def logout(
    response: Response,
    session = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """Revoke session immediately from database and clear browser cookies."""
    UserRepository.revoke_session(db, session.session_token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
    return {"success": True, "message": "Logged out successfully."}

@router.get("/me", response_model=SessionStatusResponse, summary="Get current session user details")
def get_me(auth: AuthenticatedUser = Depends(get_current_user)):
    """Retrieve details and permissions of the currently authenticated user."""
    permissions = None
    if auth.is_assistant:
        permissions = {
            "can_mark_attendance": auth.user.can_mark_attendance,
            "can_view_attendance": auth.user.can_view_attendance,
            "can_manage_students": auth.user.can_manage_students,
            "can_enter_grades": auth.user.can_enter_grades,
            "can_collect_cash": auth.user.can_collect_cash,
            "can_view_student_payment_history": auth.user.can_view_student_payment_history,
            "can_view_financial_analytics": auth.user.can_view_financial_analytics,
            "can_request_messages": auth.user.can_request_messages,
        }

    return SessionStatusResponse(
        is_authenticated=True,
        user_type="teacher" if auth.is_teacher else "assistant",
        user_id=auth.user_id,
        teacher_id=auth.teacher_id,
        username=auth.username,
        full_name=auth.user.full_name,
        csrf_token=auth.session.csrf_token,
        permissions=permissions
    )
