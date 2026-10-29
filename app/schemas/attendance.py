import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from app.models.attendance import (
    VALID_SESSION_STATUSES,
    SESSION_STATUS_LABELS,
    VALID_ATTENDANCE_STATUSES,
    ATTENDANCE_STATUS_LABELS,
)

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_REGEX = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


def validate_session_date(v: str) -> str:
    if not DATE_REGEX.match(v):
        raise ValueError("session_date must be in YYYY-MM-DD format")
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("session_date is not a valid calendar date")
    return v


def validate_time(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not TIME_REGEX.match(v):
        raise ValueError("time must be in HH:MM or HH:MM:SS format")
    # Verify valid hour and minute
    parts = v.split(":")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Hour must be 00-23 and minute must be 00-59")
    if len(parts) == 3:
        sec = int(parts[2])
        if not (0 <= sec <= 59):
            raise ValueError("Second must be 00-59")
    return v


# --- Session Schemas ---

class SessionCreate(BaseModel):
    group_id: str = Field(..., min_length=1)
    session_date: str = Field(..., description="YYYY-MM-DD format")
    start_time: str = Field(..., description="HH:MM format")
    end_time: Optional[str] = None
    location: Optional[str] = Field(None, max_length=150)
    notes: Optional[str] = None
    status: Optional[str] = "scheduled"

    @field_validator("session_date")
    @classmethod
    def check_date(cls, v: str) -> str:
        return validate_session_date(v)

    @field_validator("start_time", "end_time")
    @classmethod
    def check_time_val(cls, v: Optional[str]) -> Optional[str]:
        return validate_time(v)

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_SESSION_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_SESSION_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_time_range(self):
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly after start_time")
        return self


class SessionUpdate(BaseModel):
    session_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = Field(None, max_length=150)
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("session_date")
    @classmethod
    def check_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_session_date(v)
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def check_time_val(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_time(v)
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SESSION_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_SESSION_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_time_range(self):
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly after start_time")
        return self


class SessionAttendanceStats(BaseModel):
    total_enrolled: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    unrecorded_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    id: str
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    session_date: str
    start_time: str
    end_time: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    status: str
    status_label: str
    stats: Optional[SessionAttendanceStats] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Attendance Taking Schemas ---

class AttendanceMarkSingleRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    status: str = Field(..., description="present, absent, late, excused")
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in VALID_ATTENDANCE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_ATTENDANCE_STATUSES)}")
        return v


class AttendanceMarkItem(BaseModel):
    student_id: str = Field(..., min_length=1)
    status: str = Field(..., description="present, absent, late, excused")
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in VALID_ATTENDANCE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_ATTENDANCE_STATUSES)}")
        return v


class AttendanceBulkRequest(BaseModel):
    records: List[AttendanceMarkItem] = Field(..., min_length=1)


class AttendanceScanRequest(BaseModel):
    barcode: str = Field(..., min_length=1, description="Opaque student ID or token")
    notes: Optional[str] = None


class AttendanceScanResponse(BaseModel):
    success: bool
    action: str  # recorded, already_present, status_changed
    message: str
    student: Dict[str, Any]
    status: str
    status_label: str
    timestamp: str


class SessionStudentAttendanceItem(BaseModel):
    student_id: str
    student_name: str
    student_phone: str
    parent_phone: Optional[str] = None
    attendance_id: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SessionAttendanceSheetResponse(BaseModel):
    session: SessionResponse
    students: List[SessionStudentAttendanceItem]
    stats: SessionAttendanceStats

    model_config = ConfigDict(from_attributes=True)


class StudentAttendanceHistoryItem(BaseModel):
    session_id: str
    session_date: str
    start_time: str
    group_id: str
    group_name: str
    status: str
    status_label: str
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StudentAttendanceHistoryResponse(BaseModel):
    student_id: str
    student_name: str
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_rate: float
    history: List[StudentAttendanceHistoryItem]

    model_config = ConfigDict(from_attributes=True)


class GroupAttendanceSummaryResponse(BaseModel):
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    total_sessions: int
    total_students: int
    average_attendance_rate: float
    recent_sessions: List[SessionResponse]

    model_config = ConfigDict(from_attributes=True)
