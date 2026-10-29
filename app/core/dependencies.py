from typing import Optional, Union, Callable
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import SESSION_COOKIE_NAME, CSRF_HEADER_NAME, CSRF_COOKIE_NAME, logger
from app.models.user import Teacher, Assistant, UserSession
from app.repositories.user_repo import UserRepository

class AuthenticatedUser:
    """Wrapper holding authenticated context."""
    def __init__(self, user: Union[Teacher, Assistant], session: UserSession):
        self.user = user
        self.session = session
        self.is_teacher = isinstance(user, Teacher)
        self.is_assistant = isinstance(user, Assistant)
        self.teacher_id = user.id if self.is_teacher else user.teacher_id
        self.user_id = user.id
        self.username = user.username

async def get_current_session(
    request: Request,
    db: Session = Depends(get_db)
) -> UserSession:
    """
    Extracts and validates session token from:
    1. Authorization: Bearer <token> (API / Mobile Clients) -> Immune to CSRF
    2. HttpOnly Cookie ts_session (Browser Clients) -> Requires strict CSRF verification on POST/PUT/DELETE
    """
    auth_header = request.headers.get("Authorization")
    session_token = None
    is_cookie_auth = False

    if auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header.split(" ", 1)[1].strip()
    else:
        # Fallback to browser Cookie
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token:
            is_cookie_auth = True

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    session = UserRepository.get_valid_session(db, session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or was revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # CSRF Protection for Cookie-based mutating requests
    if is_cookie_auth and request.method in ("POST", "PUT", "DELETE", "PATCH"):
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        # Double-submit verification: Header must match session's CSRF token
        if not csrf_header or csrf_header != session.csrf_token:
            logger.warning(f"CSRF validation failed for user_id={session.user_id} path={request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF verification failed. Missing or invalid X-CSRF-Token."
            )

    return session

async def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db)
) -> AuthenticatedUser:
    """Resolve the session to an active Teacher or Assistant user instance."""
    if session.user_type == "teacher":
        user = UserRepository.get_teacher_by_id(db, session.user_id)
    elif session.user_type == "assistant":
        user = UserRepository.get_assistant_by_id(db, teacher_id=session.teacher_id, assistant_id=session.user_id)
    else:
        user = None

    if not user or not user.is_active or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or no longer exists."
        )

    return AuthenticatedUser(user=user, session=session)

def require_teacher(
    auth: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """Enforce that the authenticated user is the primary Teacher, not an assistant."""
    if not auth.is_teacher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation is restricted to the Teacher account only."
        )
    return auth

def require_permission(permission_name: str) -> Callable:
    """
    Factory dependency for fine-grained permissions:
    - If user is Teacher: Always granted.
    - If user is Assistant: Checks the specific permission flag.
    """
    async def permission_checker(
        auth: AuthenticatedUser = Depends(get_current_user)
    ) -> AuthenticatedUser:
        if auth.is_teacher:
            return auth

        # Assistant: verify specific attribute
        has_perm = getattr(auth.user, permission_name, False)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Missing '{permission_name}'."
            )
        return auth

    return permission_checker
