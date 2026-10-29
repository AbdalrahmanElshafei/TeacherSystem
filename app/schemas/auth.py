from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.core.security import validate_password_strength

class FirstRunSetupRequest(BaseModel):
    """Used strictly when creating the first primary teacher account on an uninitialized system."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_\-\.]+$')
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_type: str  # "teacher" or "assistant"
    user_id: str
    teacher_id: str
    csrf_token: str
    session_token: Optional[str] = None  # Returned for Bearer token authorization (mobile)

class SessionStatusResponse(BaseModel):
    is_authenticated: bool
    user_type: Optional[str] = None
    user_id: Optional[str] = None
    teacher_id: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    csrf_token: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None
