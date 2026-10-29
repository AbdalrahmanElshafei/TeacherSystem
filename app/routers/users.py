from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import app.config as config
from app.database import get_db
from app.core.dependencies import (
    require_teacher,
    require_permission,
    get_current_user,
    AuthenticatedUser
)
from app.repositories.user_repo import UserRepository
from app.schemas.user import (
    AssistantCreate,
    AssistantUpdate,
    AssistantResponse
)

router = APIRouter(prefix="/api/users", tags=["User & Assistant Management"])

@router.post("/assistants", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED, summary="Create a new assistant")
def create_assistant(
    payload: AssistantCreate,
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """
    Teacher creates an assistant under their isolated workspace.
    Assistant has granular permissions with financial analytics disabled by default.
    """
    # Check if username already taken
    existing_teacher = UserRepository.get_teacher_by_username(db, payload.username)
    existing_assistant = UserRepository.get_assistant_by_username(db, payload.username)
    if existing_teacher or existing_assistant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already in use."
        )

    perms = payload.permissions.model_dump() if payload.permissions else {}
    assistant = UserRepository.create_assistant(
        db=db,
        teacher_id=auth.teacher_id,
        username=payload.username,
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password,
        permissions=perms
    )
    return assistant

@router.get("/assistants", response_model=List[AssistantResponse], summary="List all assistants for the current teacher")
def list_assistants(
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """List assistants belonging exclusively to the authenticated teacher."""
    return UserRepository.list_assistants_by_teacher(db, teacher_id=auth.teacher_id)

@router.get("/assistants/{assistant_id}", response_model=AssistantResponse, summary="Get assistant by ID")
def get_assistant(
    assistant_id: str,
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """
    Fetch single assistant.
    Enforces query-level isolation (returns 404 if assistant belongs to another teacher).
    """
    assistant = UserRepository.get_assistant_by_id(db, teacher_id=auth.teacher_id, assistant_id=assistant_id)
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found."
        )
    return assistant

@router.put("/assistants/{assistant_id}", response_model=AssistantResponse, summary="Update assistant details or permissions")
def update_assistant(
    assistant_id: str,
    payload: AssistantUpdate,
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Update assistant information or permissions."""
    perms = payload.permissions.model_dump(exclude_unset=True) if payload.permissions else None
    assistant = UserRepository.update_assistant(
        db=db,
        teacher_id=auth.teacher_id,
        assistant_id=assistant_id,
        full_name=payload.full_name,
        phone=payload.phone,
        is_active=payload.is_active,
        permissions=perms
    )
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found."
        )
    return assistant

@router.delete("/assistants/{assistant_id}", summary="Delete an assistant")
def delete_assistant(
    assistant_id: str,
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """Soft delete assistant and revoke all active sessions immediately."""
    deleted = UserRepository.delete_assistant(db, teacher_id=auth.teacher_id, assistant_id=assistant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found."
        )
    return {"success": True, "message": "Assistant deleted and sessions revoked successfully."}

# --- Granular Permissions Demonstration & Testing Endpoints ---
def verify_test_endpoints_enabled():
    """
    Ensures test-only permission endpoints cannot be accessed in production.
    Opt-in via ENABLE_TEST_ENDPOINTS configuration flag.
    """
    if not getattr(config, "ENABLE_TEST_ENDPOINTS", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found."
        )

@router.post(
    "/test-permissions/collect-cash",
    summary="Endpoint requiring can_collect_cash permission",
    dependencies=[Depends(verify_test_endpoints_enabled)]
)
def test_collect_cash_permission(
    auth: AuthenticatedUser = Depends(require_permission("can_collect_cash"))
):
    """Allowed for teacher or assistant with can_collect_cash permission."""
    return {"success": True, "message": f"Cash collection authorized for user {auth.username}."}

@router.get(
    "/test-permissions/financial-analytics",
    summary="Endpoint requiring can_view_financial_analytics permission",
    dependencies=[Depends(verify_test_endpoints_enabled)]
)
def test_financial_analytics_permission(
    auth: AuthenticatedUser = Depends(require_permission("can_view_financial_analytics"))
):
    """Allowed only for teacher or assistant explicitly granted can_view_financial_analytics."""
    return {"success": True, "message": f"Financial analytics authorized for user {auth.username}."}
