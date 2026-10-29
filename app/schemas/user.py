from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.security import validate_password_strength

class TeacherBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_\-\.]+$')
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)

class TeacherCreate(TeacherBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class TeacherResponse(TeacherBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssistantPermissions(BaseModel):
    can_mark_attendance: bool = True
    can_view_attendance: bool = True
    can_manage_students: bool = False
    can_view_grades: bool = False
    can_manage_exams: bool = False
    can_enter_grades: bool = False
    can_collect_cash: bool = False
    can_view_student_payment_history: bool = False
    can_view_financial_analytics: bool = False  # Always False by default
    can_manage_fees: bool = False
    can_request_messages: bool = True

class AssistantCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_\-\.]+$')
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    permissions: Optional[AssistantPermissions] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class AssistantUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    is_active: Optional[bool] = None
    permissions: Optional[AssistantPermissions] = None

class AssistantResponse(BaseModel):
    id: str
    teacher_id: str
    username: str
    full_name: str
    phone: str
    is_active: bool
    can_mark_attendance: bool
    can_view_attendance: bool
    can_manage_students: bool
    can_view_grades: bool = False
    can_manage_exams: bool = False
    can_enter_grades: bool
    can_collect_cash: bool
    can_view_student_payment_history: bool
    can_view_financial_analytics: bool
    can_manage_fees: bool = False
    can_request_messages: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
