import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field
from app.models.exam import (
    VALID_EXAM_STATUSES,
    EXAM_STATUS_LABELS,
    VALID_RESULT_STATUSES,
    RESULT_STATUS_LABELS,
)

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_exam_date(v: str) -> str:
    if not DATE_REGEX.match(v):
        raise ValueError("exam_date must be in YYYY-MM-DD format")
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("exam_date is not a valid calendar date")
    return v


# --- Exam Schemas ---

class ExamCreate(BaseModel):
    group_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=2, max_length=150)
    exam_date: str = Field(..., description="YYYY-MM-DD format")
    max_score: float = Field(..., gt=0, description="Maximum score must be greater than 0")
    passing_score: float = Field(..., ge=0, description="Passing score must be non-negative and <= max_score")
    description: Optional[str] = None
    status: Optional[str] = "scheduled"

    @field_validator("exam_date")
    @classmethod
    def check_date(cls, v: str) -> str:
        return validate_exam_date(v)

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_EXAM_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_EXAM_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_passing_score(self):
        if self.passing_score > self.max_score:
            raise ValueError("درجة النجاح يجب ألا تزيد عن الدرجة العظمى للامتحان")
        return self


class ExamUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=150)
    exam_date: Optional[str] = None
    max_score: Optional[float] = Field(None, gt=0)
    passing_score: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("exam_date")
    @classmethod
    def check_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_exam_date(v)
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_EXAM_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_EXAM_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_scores_consistency(self):
        if self.max_score is not None and self.passing_score is not None:
            if self.passing_score > self.max_score:
                raise ValueError("درجة النجاح يجب ألا تزيد عن الدرجة العظمى للامتحان")
        return self


class ExamStats(BaseModel):
    total_enrolled: int = 0
    results_recorded: int = 0
    results_pending: int = 0
    attended_count: int = 0
    absent_count: int = 0
    excused_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0
    average_score: float = 0.0
    average_percentage: float = 0.0
    highest_score: Optional[float] = None
    lowest_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def total_students(self) -> int:
        return self.total_enrolled

    @computed_field
    def graded_count(self) -> int:
        return self.results_recorded

    @computed_field
    def pending_count(self) -> int:
        return self.results_pending

    @computed_field
    def pass_rate_percent(self) -> float:
        return self.pass_rate


class ExamResponse(BaseModel):
    id: str
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    title: str
    exam_date: str
    max_score: float
    passing_score: float
    description: Optional[str] = None
    status: str
    status_label: str
    stats: Optional[ExamStats] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Exam Results Schemas ---

class ExamResultSingleRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    status: str = Field("attended", description="attended, absent, excused")
    score: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in VALID_RESULT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_RESULT_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_score_rules(self):
        if self.status == "attended":
            if self.score is None:
                raise ValueError("الدرجة مطلوبة عند تسجيل حضور الطالب في الامتحان")
            if self.score < 0:
                raise ValueError("لا يمكن أن تكون الدرجة سالبة")
        else:
            # If absent or excused, score must be null (do not fabricate scores)
            self.score = None
        return self


class ExamResultItem(BaseModel):
    student_id: str = Field(..., min_length=1)
    status: str = Field("attended", description="attended, absent, excused")
    score: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in VALID_RESULT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_RESULT_STATUSES)}")
        return v

    @model_validator(mode="after")
    def check_score_rules(self):
        if self.status == "attended":
            if self.score is None:
                raise ValueError(f"الدرجة مطلوبة للطالب {self.student_id}")
            if self.score < 0:
                raise ValueError("لا يمكن أن تكون الدرجة سالبة")
        else:
            self.score = None
        return self


class ExamResultBulkRequest(BaseModel):
    records: List[ExamResultItem] = Field(..., min_length=1)


class StudentExamResultRow(BaseModel):
    student_id: str
    student_name: str
    student_phone: str
    parent_phone: Optional[str] = None
    result_id: Optional[str] = None
    score: Optional[float] = None
    percentage: Optional[float] = None
    is_passed: Optional[bool] = None
    status: Optional[str] = None  # None if pending/unrecorded
    status_label: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExamResultsSheetResponse(BaseModel):
    exam: ExamResponse
    students: List[StudentExamResultRow]
    stats: ExamStats

    model_config = ConfigDict(from_attributes=True)


class StudentExamHistoryItem(BaseModel):
    exam_id: str
    exam_title: str
    exam_date: str
    group_id: str
    group_name: str
    max_score: float
    passing_score: float
    score: Optional[float] = None
    percentage: Optional[float] = None
    is_passed: Optional[bool] = None
    status: str
    status_label: str
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StudentExamHistoryResponse(BaseModel):
    student_id: str
    student_name: str
    total_exams: int
    attended_count: int
    absent_count: int
    excused_count: int
    passed_count: int
    failed_count: int
    average_percentage: float
    overall_pass_rate: float
    history: List[StudentExamHistoryItem]

    model_config = ConfigDict(from_attributes=True)


class GroupExamsSummaryResponse(BaseModel):
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    total_exams: int
    total_students: int
    average_pass_rate: float
    average_group_score_percentage: float
    recent_exams: List[ExamResponse]

    model_config = ConfigDict(from_attributes=True)
