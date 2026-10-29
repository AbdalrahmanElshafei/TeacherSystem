from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.academic import VALID_GRADE_LEVELS, GRADE_LABELS

def validate_grade(v: str) -> str:
    if v not in VALID_GRADE_LEVELS:
        raise ValueError(f"Invalid grade_level '{v}'. Must be one of: {', '.join(VALID_GRADE_LEVELS)}")
    return v


# --- Student Schemas ---

class StudentBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    grade_level: str = Field(..., description="One of: 1_sec, 2_sec, 3_sec")
    phone: str = Field(..., min_length=7, max_length=20)
    parent_name: Optional[str] = Field(None, max_length=120)
    parent_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True

    @field_validator("grade_level")
    @classmethod
    def check_grade(cls, v: str) -> str:
        return validate_grade(v)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    grade_level: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    parent_name: Optional[str] = Field(None, max_length=120)
    parent_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("grade_level")
    @classmethod
    def check_grade(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_grade(v)
        return v


class StudentGroupBrief(BaseModel):
    id: str
    name: str
    grade_level: str
    grade_label: str
    subject: Optional[str] = None
    schedule_details: Optional[str] = None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentResponse(BaseModel):
    id: str
    full_name: str
    grade_level: str
    grade_label: str
    phone: str
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    group_count: int = 0
    groups: List[StudentGroupBrief] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Group Schemas ---

class GroupBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    grade_level: str = Field(..., description="One of: 1_sec, 2_sec, 3_sec")
    subject: Optional[str] = Field(None, max_length=100)
    schedule_details: Optional[str] = None
    is_active: bool = True

    @field_validator("grade_level")
    @classmethod
    def check_grade(cls, v: str) -> str:
        return validate_grade(v)


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    grade_level: Optional[str] = None
    subject: Optional[str] = Field(None, max_length=100)
    schedule_details: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("grade_level")
    @classmethod
    def check_grade(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_grade(v)
        return v


class GroupResponse(BaseModel):
    id: str
    name: str
    grade_level: str
    grade_label: str
    subject: Optional[str] = None
    schedule_details: Optional[str] = None
    is_active: bool
    student_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Membership / Enrollment Schemas ---

class EnrollStudentRequest(BaseModel):
    student_id: str = Field(..., min_length=1)


class GroupEnrolledStudentResponse(BaseModel):
    membership_id: str
    student_id: str
    full_name: str
    phone: str
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    grade_level: str
    grade_label: str
    joined_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
