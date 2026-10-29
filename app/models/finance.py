import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

VALID_FEE_MODELS = ("monthly", "per_session")
FEE_MODEL_LABELS = {
    "monthly": "اشتراك شهري",
    "per_session": "حساب بالحصة",
}

VALID_DUE_STATUSES = ("unpaid", "partially_paid", "paid", "void")
DUE_STATUS_LABELS = {
    "unpaid": "غير مسدد",
    "partially_paid": "مسدد جزئياً",
    "paid": "مسدد بالكامل",
    "void": "ملغى",
}

VALID_CHARGE_TYPES = ("monthly_fee", "session_fee")
CHARGE_TYPE_LABELS = {
    "monthly_fee": "اشتراك شهري",
    "session_fee": "رسوم حصة",
}


class GroupFeeConfig(BaseModel):
    """
    Fee Configuration per Academic Group.
    Defines whether the group charges a monthly subscription or a per-session fee,
    storing the fee amount in integer minor units (piastres, 1 EGP = 100 piastres).
    """
    __tablename__ = "group_fee_configs"
    __table_args__ = (
        Index("ix_group_fee_configs_tenant", "teacher_id", "group_id", "is_active"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_model = Column(String(20), nullable=False, default="monthly", index=True)  # "monthly", "per_session"
    amount = Column(Integer, nullable=False)  # Integer piastres (>= 0)
    effective_from = Column(String(10), nullable=False)  # YYYY-MM-DD
    effective_to = Column(String(10), nullable=True)     # YYYY-MM-DD
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    teacher = relationship("Teacher")
    group = relationship("Group")
    dues = relationship("StudentDue", back_populates="fee_config")

    def __repr__(self):
        return f"<GroupFeeConfig group={self.group_id} model={self.fee_model} amount={self.amount}>"


class StudentDue(BaseModel):
    """
    Student Due / Charge Model.
    Represents an immutable financial obligation (monthly fee or session fee).
    Guarantees idempotency via database uniqueness constraints:
    - At most one monthly charge per student per group per billing month.
    - At most one session charge per student per completed session.
    """
    __tablename__ = "student_dues"
    __table_args__ = (
        UniqueConstraint("student_id", "group_id", "billing_month", name="uq_student_group_monthly_due"),
        UniqueConstraint("student_id", "session_id", name="uq_student_session_charge"),
        Index("ix_student_dues_tenant_student", "teacher_id", "student_id", "status"),
        Index("ix_student_dues_tenant_group_month", "teacher_id", "group_id", "billing_month"),
        Index("ix_student_dues_tenant_status", "teacher_id", "status"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_config_id = Column(String(36), ForeignKey("group_fee_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    charge_type = Column(String(20), nullable=False, index=True)  # "monthly_fee", "session_fee"
    billing_month = Column(String(7), nullable=True, index=True)   # "YYYY-MM" for monthly
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)  # for session
    amount = Column(Integer, nullable=False)                       # Total due in piastres (> 0)
    paid_amount = Column(Integer, default=0, nullable=False)       # Total allocated in piastres
    status = Column(String(20), default="unpaid", nullable=False, index=True)  # unpaid, partially_paid, paid, void
    due_date = Column(String(10), nullable=False)                  # YYYY-MM-DD
    description = Column(Text, nullable=True)
    void_reason = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_user_id = Column(String(36), nullable=True)

    # Relationships
    teacher = relationship("Teacher")
    student = relationship("Student")
    group = relationship("Group")
    session = relationship("ClassSession")
    fee_config = relationship("GroupFeeConfig", back_populates="dues")
    allocations = relationship("PaymentAllocation", back_populates="due", cascade="all, delete-orphan")

    @property
    def remaining_balance(self) -> int:
        if self.status == "void":
            return 0
        return max(0, self.amount - self.paid_amount)

    def __repr__(self):
        return f"<StudentDue id={self.id} student={self.student_id} amount={self.amount} paid={self.paid_amount} status={self.status}>"


class CashPayment(BaseModel):
    """
    Cash Payment Model.
    Represents actual physical cash collected from a student.
    Can be allocated across one or multiple dues of that student.
    Corrections preserve original records via is_reversed flag and audit trail.
    """
    __tablename__ = "cash_payments"
    __table_args__ = (
        Index("ix_cash_payments_tenant_date", "teacher_id", "payment_date"),
        Index("ix_cash_payments_tenant_student", "teacher_id", "student_id", "payment_date"),
        Index("ix_cash_payments_receipt", "teacher_id", "receipt_number"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)                  # Total cash received in piastres (> 0)
    allocated_amount = Column(Integer, default=0, nullable=False)  # Total allocated in piastres
    payment_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    payment_method = Column(String(20), default="cash", nullable=False)
    receipt_number = Column(String(50), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(String(36), nullable=True)
    recorded_by_user_type = Column(String(20), nullable=True)  # "teacher" or "assistant"
    is_reversed = Column(Boolean, default=False, nullable=False, index=True)
    reversal_reason = Column(Text, nullable=True)
    reversed_at = Column(DateTime, nullable=True)
    reversed_by_user_id = Column(String(36), nullable=True)

    # Relationships
    teacher = relationship("Teacher")
    student = relationship("Student")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")

    @property
    def unallocated_amount(self) -> int:
        if self.is_reversed:
            return 0
        return max(0, self.amount - self.allocated_amount)

    def __repr__(self):
        return f"<CashPayment id={self.id} student={self.student_id} amount={self.amount} allocated={self.allocated_amount} reversed={self.is_reversed}>"


class PaymentAllocation(BaseModel):
    """
    Payment Allocation Model.
    Links a portion of a cash payment to a specific student due.
    Ensures payment and due belong to the same student and teacher.
    """
    __tablename__ = "payment_allocations"
    __table_args__ = (
        Index("ix_allocations_tenant_due", "teacher_id", "due_id"),
        Index("ix_allocations_tenant_payment", "teacher_id", "payment_id"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(String(36), ForeignKey("cash_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    due_id = Column(String(36), ForeignKey("student_dues.id", ondelete="CASCADE"), nullable=False, index=True)
    allocated_amount = Column(Integer, nullable=False)  # In piastres (> 0)

    # Relationships
    payment = relationship("CashPayment", back_populates="allocations")
    due = relationship("StudentDue", back_populates="allocations")

    def __repr__(self):
        return f"<PaymentAllocation payment={self.payment_id} due={self.due_id} amount={self.allocated_amount}>"


class FinancialAuditLog(BaseModel):
    """
    Financial Audit Log.
    Provides immutable audit records for sensitive financial actions:
    fee configuration changes, dues generation batches, cash receipt creation,
    allocations, payment reversals, and due voiding.
    """
    __tablename__ = "financial_audit_logs"
    __table_args__ = (
        Index("ix_financial_audit_tenant_action", "teacher_id", "action", "created_at"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=True)
    actor_user_id = Column(String(36), nullable=True)
    actor_user_type = Column(String(20), nullable=True)
    details = Column(Text, nullable=True)  # JSON formatted metadata

    def __repr__(self):
        return f"<FinancialAuditLog action={self.action} entity={self.entity_type}:{self.entity_id}>"
