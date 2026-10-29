import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field
from app.models.finance import (
    VALID_FEE_MODELS,
    FEE_MODEL_LABELS,
    VALID_DUE_STATUSES,
    DUE_STATUS_LABELS,
    VALID_CHARGE_TYPES,
    CHARGE_TYPE_LABELS,
)

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_REGEX = re.compile(r"^\d{4}-\d{2}$")


def to_piastres(amount_egp: float) -> int:
    """Lossless conversion of EGP decimal to integer piastres."""
    return int(round(amount_egp * 100))


def to_egp(piastres: int) -> float:
    """Convert integer piastres to float EGP."""
    return round(piastres / 100.0, 2)


def format_currency_egp(piastres: int) -> str:
    """Format piastres as localized Arabic EGP string."""
    egp = to_egp(piastres)
    return f"{egp:,.2f} ج.م"


# ==========================================
# --- Fee Config Schemas ---
# ==========================================

class GroupFeeConfigCreate(BaseModel):
    group_id: str = Field(..., min_length=1)
    fee_model: str = Field("monthly", description="monthly or per_session")
    amount_egp: float = Field(..., ge=0, description="Fee amount in EGP (non-negative)")
    effective_from: str = Field(..., description="YYYY-MM-DD")
    effective_to: Optional[str] = Field(None, description="YYYY-MM-DD")

    @field_validator("fee_model")
    @classmethod
    def validate_fee_model(cls, v: str) -> str:
        if v not in VALID_FEE_MODELS:
            raise ValueError(f"fee_model must be one of: {', '.join(VALID_FEE_MODELS)}")
        return v

    @field_validator("effective_from")
    @classmethod
    def validate_from_date(cls, v: str) -> str:
        if not DATE_REGEX.match(v):
            raise ValueError("effective_from must be in YYYY-MM-DD format")
        return v

    @field_validator("effective_to")
    @classmethod
    def validate_to_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not DATE_REGEX.match(v):
            raise ValueError("effective_to must be in YYYY-MM-DD format")
        return v

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from cannot be after effective_to")
        return self


class GroupFeeConfigUpdate(BaseModel):
    fee_model: Optional[str] = None
    amount_egp: Optional[float] = Field(None, ge=0)
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("fee_model")
    @classmethod
    def validate_fee_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_FEE_MODELS:
            raise ValueError(f"fee_model must be one of: {', '.join(VALID_FEE_MODELS)}")
        return v

    @field_validator("effective_from")
    @classmethod
    def validate_from_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not DATE_REGEX.match(v):
            raise ValueError("effective_from must be in YYYY-MM-DD format")
        return v

    @field_validator("effective_to")
    @classmethod
    def validate_to_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not DATE_REGEX.match(v):
            raise ValueError("effective_to must be in YYYY-MM-DD format")
        return v


class GroupFeeConfigResponse(BaseModel):
    id: str
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    fee_model: str
    fee_model_label: str
    amount_piastres: int
    amount_egp: float
    formatted_amount: str
    effective_from: str
    effective_to: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# --- Dues Generation Schemas ---
# ==========================================

class MonthlyDuesPreviewRequest(BaseModel):
    group_id: str = Field(..., min_length=1)
    billing_month: str = Field(..., description="YYYY-MM format, e.g. 2026-10")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD format")

    @field_validator("billing_month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not MONTH_REGEX.match(v):
            raise ValueError("billing_month must be in YYYY-MM format")
        return v


class EligibleStudentItem(BaseModel):
    student_id: str
    student_name: str
    student_phone: str
    joined_at: str
    amount_piastres: int
    amount_egp: float
    already_billed: bool
    due_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MonthlyDuesPreviewResponse(BaseModel):
    group_id: str
    group_name: str
    billing_month: str
    fee_model: str
    fee_model_label: str
    fee_amount_egp: float
    total_enrolled_eligible: int
    newly_billable_count: int
    already_billed_count: int
    total_expected_piastres: int
    total_expected_egp: float
    students: List[EligibleStudentItem]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def eligible_students_count(self) -> int:
        return self.total_enrolled_eligible

    @computed_field
    def to_be_generated_count(self) -> int:
        return self.newly_billable_count

    @computed_field
    def already_generated_count(self) -> int:
        return self.already_billed_count

    @computed_field
    def total_amount_piastres(self) -> int:
        return self.total_expected_piastres

    @computed_field
    def total_amount_egp(self) -> float:
        return self.total_expected_egp


class MonthlyDuesGenerateRequest(BaseModel):
    group_id: str = Field(..., min_length=1)
    billing_month: str = Field(..., description="YYYY-MM format")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD format")

    @field_validator("billing_month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not MONTH_REGEX.match(v):
            raise ValueError("billing_month must be in YYYY-MM format")
        return v


class MonthlyDuesGenerateResponse(BaseModel):
    success: bool
    group_id: str
    billing_month: str
    generated_count: int
    skipped_existing_count: int
    total_amount_piastres: int
    total_amount_egp: float
    message: str


class SessionDuesPreviewResponse(BaseModel):
    session_id: str
    group_id: str
    group_name: str
    session_date: str
    session_status: str
    is_eligible_session: bool
    ineligibility_reason: Optional[str] = None
    fee_amount_egp: float
    attended_students_count: int
    newly_billable_count: int
    already_charged_count: int
    total_expected_piastres: int
    total_expected_egp: float
    students: List[EligibleStudentItem]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def to_be_generated_count(self) -> int:
        return self.newly_billable_count

    @computed_field
    def already_generated_count(self) -> int:
        return self.already_charged_count

    @computed_field
    def total_amount_piastres(self) -> int:
        return self.total_expected_piastres

    @computed_field
    def total_amount_egp(self) -> float:
        return self.total_expected_egp


class SessionDuesGenerateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD format")


class SessionDuesGenerateResponse(BaseModel):
    success: bool
    session_id: str
    generated_count: int
    skipped_existing_count: int
    total_amount_piastres: int
    total_amount_egp: float
    message: str


# ==========================================
# --- Student Dues Schemas ---
# ==========================================

class StudentDueResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    group_id: str
    group_name: str
    charge_type: str
    charge_type_label: str
    billing_month: Optional[str] = None
    session_id: Optional[str] = None
    amount_piastres: int
    amount_egp: float
    paid_amount_piastres: int
    paid_amount_egp: float
    remaining_balance_piastres: int
    remaining_balance_egp: float
    status: str
    status_label: str
    due_date: str
    description: Optional[str] = None
    void_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DueVoidRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255, description="Reason for voiding this charge")


# ==========================================
# --- Cash Payments & Allocations Schemas ---
# ==========================================

class PaymentAllocationItem(BaseModel):
    due_id: str = Field(..., min_length=1)
    allocated_amount_egp: float = Field(..., gt=0, description="Amount allocated to this due in EGP")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def handle_amount_alias(cls, data):
        if isinstance(data, dict):
            if "amount_egp" in data and "allocated_amount_egp" not in data:
                data["allocated_amount_egp"] = data["amount_egp"]
        return data


class CashPaymentCreateRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    amount_egp: float = Field(..., gt=0, description="Total cash received in EGP (> 0)")
    payment_date: str = Field(..., description="YYYY-MM-DD")
    notes: Optional[str] = None
    receipt_number: Optional[str] = None
    allocations: List[PaymentAllocationItem] = Field(default_factory=list)

    @field_validator("payment_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not DATE_REGEX.match(v):
            raise ValueError("payment_date must be in YYYY-MM-DD format")
        return v

    @model_validator(mode="after")
    def validate_allocations_sum(self):
        alloc_sum_piastres = sum(to_piastres(a.allocated_amount_egp) for a in self.allocations)
        total_paid_piastres = to_piastres(self.amount_egp)
        if alloc_sum_piastres > total_paid_piastres:
            raise ValueError("مجموع المبالغ الموزعة على الرسوم يتجاوز إجمالي المبلغ المحصل")
        return self


class PaymentAllocationResponse(BaseModel):
    id: str
    due_id: str
    charge_type_label: str
    description: Optional[str] = None
    allocated_amount_piastres: int
    allocated_amount_egp: float
    formatted_amount: str

    model_config = ConfigDict(from_attributes=True)


class CashPaymentResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    student_phone: str
    amount_piastres: int
    amount_egp: float
    allocated_amount_piastres: int
    allocated_amount_egp: float
    unallocated_amount_piastres: int
    unallocated_amount_egp: float
    payment_date: str
    payment_method: str
    receipt_number: str
    notes: Optional[str] = None
    recorded_by_user_id: Optional[str] = None
    recorded_by_user_type: Optional[str] = None
    is_reversed: bool
    reversal_reason: Optional[str] = None
    reversed_at: Optional[datetime] = None
    allocations: List[PaymentAllocationResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def formatted_amount(self) -> str:
        return format_currency_egp(self.amount_piastres)

    @computed_field
    def created_by_name(self) -> str:
        if self.recorded_by_user_type == "teacher":
            return "المعلم"
        elif self.recorded_by_user_type == "assistant":
            return "المساعد"
        return "المسؤول"


class PaymentReverseRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255, description="Reason for reversing this receipt")


# ==========================================
# --- Reports & Summaries Schemas ---
# ==========================================

class StudentFinancialProfileResponse(BaseModel):
    student_id: str
    student_name: str
    student_phone: str
    parent_phone: Optional[str] = None
    grade_level: str
    grade_label: str
    total_dues_piastres: int
    total_dues_egp: float
    total_paid_piastres: int
    total_paid_egp: float
    total_allocated_piastres: int
    total_allocated_egp: float
    outstanding_balance_piastres: int
    outstanding_balance_egp: float
    unallocated_cash_piastres: int
    unallocated_cash_egp: float
    dues: List[StudentDueResponse]
    payments: List[CashPaymentResponse]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def current_balance_egp(self) -> float:
        return self.outstanding_balance_egp


class GroupCollectionSummaryResponse(BaseModel):
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    fee_model: Optional[str] = None
    fee_model_label: Optional[str] = None
    active_fee_amount_egp: Optional[float] = None
    total_charges_piastres: int
    total_charges_egp: float
    total_collected_piastres: int
    total_collected_egp: float
    outstanding_balance_piastres: int
    outstanding_balance_egp: float
    collection_rate: float
    students_with_balance_count: int
    total_students_enrolled: int

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def total_billed_egp(self) -> float:
        return self.total_charges_egp

    @computed_field
    def total_outstanding_egp(self) -> float:
        return self.outstanding_balance_egp

    @computed_field
    def collection_rate_percent(self) -> float:
        return self.collection_rate

    @computed_field
    def enrolled_students_count(self) -> int:
        return self.total_students_enrolled


class MonthlyCollectionReportResponse(BaseModel):
    billing_month: str
    charges_generated_piastres: int
    charges_generated_egp: float
    charges_count: int
    allocated_to_month_charges_piastres: int
    allocated_to_month_charges_egp: float
    outstanding_month_dues_piastres: int
    outstanding_month_dues_egp: float
    month_collection_rate: float
    cash_received_in_month_piastres: int
    cash_received_in_month_egp: float
    payments_count: int
    distinct_students_paid: int

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def total_monthly_dues_egp(self) -> float:
        return self.charges_generated_egp

    @computed_field
    def total_collected_egp(self) -> float:
        return self.allocated_to_month_charges_egp

    @computed_field
    def total_outstanding_egp(self) -> float:
        return self.outstanding_month_dues_egp

    @computed_field
    def collection_rate_percent(self) -> float:
        return self.month_collection_rate

    @computed_field
    def outstanding_balance_egp(self) -> float:
        return self.outstanding_month_dues_egp


class CashCollectionReportItem(BaseModel):
    payment_id: str
    receipt_number: str
    student_id: str
    student_name: str
    student_phone: str
    payment_date: str
    amount_piastres: int
    amount_egp: float
    allocated_amount_piastres: int
    allocated_amount_egp: float
    notes: Optional[str] = None
    recorded_by: Optional[str] = None


class CashCollectionReportResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_cash_received_piastres: int
    total_cash_received_egp: float
    total_payments_count: int
    total_allocated_piastres: int
    total_allocated_egp: float
    payments: List[CashCollectionReportItem]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def total_collected_egp(self) -> float:
        return self.total_cash_received_egp

    @computed_field
    def payments_count(self) -> int:
        return self.total_payments_count

    @computed_field
    def net_collected_egp(self) -> float:
        return self.total_cash_received_egp

    @computed_field
    def total_reversed_egp(self) -> float:
        return 0.0


class FinanceOverviewResponse(BaseModel):
    total_cash_collected_piastres: int
    total_cash_collected_egp: float
    total_outstanding_balance_piastres: int
    total_outstanding_balance_egp: float
    total_charges_piastres: int
    total_charges_egp: float
    students_with_outstanding_count: int
    recent_payments: List[CashPaymentResponse]
    groups_summary: List[GroupCollectionSummaryResponse]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def total_dues_piastres(self) -> int:
        return self.total_charges_piastres

    @computed_field
    def total_collected_piastres(self) -> int:
        return self.total_cash_collected_piastres

    @computed_field
    def total_outstanding_piastres(self) -> int:
        return self.total_outstanding_balance_piastres

    @computed_field
    def collection_rate_percent(self) -> float:
        if self.total_charges_piastres > 0:
            return round(self.total_cash_collected_piastres / self.total_charges_piastres * 100.0, 1)
        return 0.0
