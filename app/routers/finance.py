from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_permission, require_teacher, get_current_user, AuthenticatedUser
from app.models.academic import Group, Student, GRADE_LABELS
from app.models.finance import (
    GroupFeeConfig,
    StudentDue,
    CashPayment,
    VALID_FEE_MODELS,
    FEE_MODEL_LABELS,
    VALID_DUE_STATUSES,
    DUE_STATUS_LABELS,
    VALID_CHARGE_TYPES,
    CHARGE_TYPE_LABELS,
)
from app.repositories.finance_repo import FinanceRepository
from app.schemas.finance import (
    to_piastres,
    to_egp,
    format_currency_egp,
    GroupFeeConfigCreate,
    GroupFeeConfigUpdate,
    GroupFeeConfigResponse,
    MonthlyDuesPreviewRequest,
    MonthlyDuesPreviewResponse,
    MonthlyDuesGenerateRequest,
    MonthlyDuesGenerateResponse,
    SessionDuesPreviewResponse,
    SessionDuesGenerateRequest,
    SessionDuesGenerateResponse,
    StudentDueResponse,
    DueVoidRequest,
    CashPaymentCreateRequest,
    CashPaymentResponse,
    PaymentAllocationResponse,
    PaymentReverseRequest,
    StudentFinancialProfileResponse,
    GroupCollectionSummaryResponse,
    MonthlyCollectionReportResponse,
    CashCollectionReportResponse,
    FinanceOverviewResponse,
)

router = APIRouter(prefix="/api/finance", tags=["Payments & Finance"])


def require_finance_read_permission(
    auth: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """Allow teacher or assistants with any finance read/write privilege."""
    if auth.is_teacher:
        return auth
    if (
        getattr(auth.user, "can_view_financial_analytics", False)
        or getattr(auth.user, "can_view_student_payment_history", False)
        or getattr(auth.user, "can_collect_cash", False)
        or getattr(auth.user, "can_manage_fees", False)
    ):
        return auth
    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail="Permission denied: Missing finance viewing permissions."
    )


# ==========================================
# --- Finance Overview ---
# ==========================================

@router.get("/overview", response_model=FinanceOverviewResponse, summary="Get dashboard finance overview")
def get_overview(
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Retrieve high-level financial overview metrics: total cash collected,
    total outstanding balance, total charges, students with outstanding dues,
    recent payments, and group-by-group summary.
    """
    return FinanceRepository.get_finance_overview(db, auth.teacher_id)


# ==========================================
# --- Group Fee Configuration Endpoints ---
# ==========================================

@router.post("/fees", response_model=GroupFeeConfigResponse, status_code=http_status.HTTP_201_CREATED, summary="Create or update group fee configuration")
def set_group_fee_config(
    payload: GroupFeeConfigCreate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Configure monthly or per-session fees for a specific group.
    Preserves historical configs by deactivating previous settings.
    """
    try:
        config = FinanceRepository.create_or_update_fee_config(
            db=db,
            teacher_id=auth.teacher_id,
            data=payload,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    grp = db.query(Group).filter(Group.id == config.group_id).first()
    return GroupFeeConfigResponse(
        id=config.id,
        group_id=config.group_id,
        group_name=grp.name if grp else "",
        grade_level=grp.grade_level if grp else "",
        grade_label=GRADE_LABELS.get(grp.grade_level, "") if grp else "",
        fee_model=config.fee_model,
        fee_model_label=FEE_MODEL_LABELS.get(config.fee_model, config.fee_model),
        amount_piastres=config.amount,
        amount_egp=to_egp(config.amount),
        formatted_amount=format_currency_egp(config.amount),
        effective_from=config.effective_from,
        effective_to=config.effective_to,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.get("/fees", response_model=List[GroupFeeConfigResponse], summary="List fee configurations")
def list_fee_configs(
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    List fee configurations belonging to the teacher.
    """
    configs = FinanceRepository.list_fee_configs(db, auth.teacher_id, group_id)
    group_ids = {c.group_id for c in configs}
    groups = {g.id: g for g in db.query(Group).filter(Group.id.in_(group_ids)).all()} if group_ids else {}

    results = []
    for c in configs:
        grp = groups.get(c.group_id)
        results.append(GroupFeeConfigResponse(
            id=c.id,
            group_id=c.group_id,
            group_name=grp.name if grp else "",
            grade_level=grp.grade_level if grp else "",
            grade_label=GRADE_LABELS.get(grp.grade_level, "") if grp else "",
            fee_model=c.fee_model,
            fee_model_label=FEE_MODEL_LABELS.get(c.fee_model, c.fee_model),
            amount_piastres=c.amount,
            amount_egp=to_egp(c.amount),
            formatted_amount=format_currency_egp(c.amount),
            effective_from=c.effective_from,
            effective_to=c.effective_to,
            is_active=c.is_active,
            created_at=c.created_at,
        ))
    return results


@router.get("/fees/group/{group_id}", response_model=Optional[GroupFeeConfigResponse], summary="Get active fee config for group")
def get_group_active_fee(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get the currently active fee config for a group.
    """
    config = FinanceRepository.get_active_fee_config(db, auth.teacher_id, group_id)
    if not config:
        return None

    grp = db.query(Group).filter(Group.id == group_id, Group.teacher_id == auth.teacher_id).first()
    return GroupFeeConfigResponse(
        id=config.id,
        group_id=config.group_id,
        group_name=grp.name if grp else "",
        grade_level=grp.grade_level if grp else "",
        grade_label=GRADE_LABELS.get(grp.grade_level, "") if grp else "",
        fee_model=config.fee_model,
        fee_model_label=FEE_MODEL_LABELS.get(config.fee_model, config.fee_model),
        amount_piastres=config.amount,
        amount_egp=to_egp(config.amount),
        formatted_amount=format_currency_egp(config.amount),
        effective_from=config.effective_from,
        effective_to=config.effective_to,
        is_active=config.is_active,
        created_at=config.created_at,
    )


# ==========================================
# --- Dues Generation Endpoints ---
# ==========================================

@router.post("/dues/monthly/preview", response_model=MonthlyDuesPreviewResponse, summary="Preview monthly dues batch")
def preview_monthly_dues(
    payload: MonthlyDuesPreviewRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Preview eligible students, expected amounts, and already generated dues
    for a billing month before confirmation.
    """
    try:
        return FinanceRepository.preview_monthly_dues(
            db=db,
            teacher_id=auth.teacher_id,
            group_id=payload.group_id,
            billing_month=payload.billing_month
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/dues/monthly/generate", response_model=MonthlyDuesGenerateResponse, summary="Confirm & generate monthly dues")
def generate_monthly_dues(
    payload: MonthlyDuesGenerateRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Idempotent batch generation of monthly dues inside an atomic transaction.
    """
    try:
        gen_count, skip_count, total_p = FinanceRepository.generate_monthly_dues(
            db=db,
            teacher_id=auth.teacher_id,
            group_id=payload.group_id,
            billing_month=payload.billing_month,
            due_date=payload.due_date,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return MonthlyDuesGenerateResponse(
        success=True,
        group_id=payload.group_id,
        billing_month=payload.billing_month,
        generated_count=gen_count,
        skipped_existing_count=skip_count,
        total_amount_piastres=total_p,
        total_amount_egp=to_egp(total_p),
        message=f"تم إنشاء {gen_count} اشتراك شهري جديد بإجمالي {to_egp(total_p)} ج.م (وتم تخطي {skip_count} اشتراك موجود مسبقاً)."
    )


@router.get("/dues/session/{session_id}/preview", response_model=SessionDuesPreviewResponse, summary="Preview session dues batch")
def preview_session_dues(
    session_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Preview eligible students and expected dues for a completed class session.
    """
    try:
        return FinanceRepository.preview_session_dues(db, auth.teacher_id, session_id)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/dues/session/generate", response_model=SessionDuesGenerateResponse, summary="Confirm & generate session dues")
def generate_session_dues(
    payload: SessionDuesGenerateRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Generate dues for eligible attended students in a completed session atomically.
    """
    try:
        gen_count, skip_count, total_p = FinanceRepository.generate_session_dues(
            db=db,
            teacher_id=auth.teacher_id,
            session_id=payload.session_id,
            due_date=payload.due_date,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return SessionDuesGenerateResponse(
        success=True,
        session_id=payload.session_id,
        generated_count=gen_count,
        skipped_existing_count=skip_count,
        total_amount_piastres=total_p,
        total_amount_egp=to_egp(total_p),
        message=f"تم إنشاء {gen_count} رسم حصة جديد بإجمالي {to_egp(total_p)} ج.م (وتم تخطي {skip_count} رسم مسجل مسبقاً)."
    )


# ==========================================
# --- Student Dues Management ---
# ==========================================

@router.get("/dues", response_model=List[StudentDueResponse], summary="List and filter student dues")
def list_dues(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    billing_month: Optional[str] = Query(None, description="Filter by YYYY-MM"),
    status: Optional[str] = Query(None, description="unpaid, partially_paid, paid, void"),
    charge_type: Optional[str] = Query(None, description="monthly_fee, session_fee"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    List student dues with filtering, scoped strictly to the teacher workspace.
    """
    query = db.query(StudentDue, Student, Group).join(
        Student, StudentDue.student_id == Student.id
    ).outerjoin(
        Group, StudentDue.group_id == Group.id
    ).filter(
        StudentDue.teacher_id == auth.teacher_id,
        StudentDue.is_deleted == False
    )

    if student_id:
        query = query.filter(StudentDue.student_id == student_id)
    if group_id:
        query = query.filter(StudentDue.group_id == group_id)
    if billing_month:
        query = query.filter(StudentDue.billing_month == billing_month)
    if status:
        query = query.filter(StudentDue.status == status)
    if charge_type:
        query = query.filter(StudentDue.charge_type == charge_type)

    dues_rows = query.order_by(StudentDue.due_date.desc(), StudentDue.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for d, st, grp in dues_rows:
        rem_p = d.remaining_balance
        results.append(StudentDueResponse(
            id=d.id,
            student_id=d.student_id,
            student_name=st.full_name,
            group_id=d.group_id,
            group_name=grp.name if grp else "مجموعة سابقة",
            charge_type=d.charge_type,
            charge_type_label=CHARGE_TYPE_LABELS.get(d.charge_type, d.charge_type),
            billing_month=d.billing_month,
            session_id=d.session_id,
            amount_piastres=d.amount,
            amount_egp=to_egp(d.amount),
            paid_amount_piastres=d.paid_amount,
            paid_amount_egp=to_egp(d.paid_amount),
            remaining_balance_piastres=rem_p,
            remaining_balance_egp=to_egp(rem_p),
            status=d.status,
            status_label=DUE_STATUS_LABELS.get(d.status, d.status),
            due_date=d.due_date,
            description=d.description,
            void_reason=d.void_reason,
            created_at=d.created_at,
        ))
    return results


@router.post("/dues/{due_id}/void", response_model=StudentDueResponse, summary="Void an unpaid student due")
def void_due(
    due_id: str,
    payload: DueVoidRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_fees")),
    db: Session = Depends(get_db)
):
    """
    Void an unpaid due with an auditable reason.
    """
    existing = db.query(StudentDue).filter(
        StudentDue.id == due_id,
        StudentDue.teacher_id == auth.teacher_id,
        StudentDue.is_deleted == False
    ).first()
    if not existing:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="المطالبة المالية غير موجودة أو لا تملك صلاحية الوصول إليها")

    try:
        due = FinanceRepository.void_due(
            db=db,
            teacher_id=auth.teacher_id,
            due_id=due_id,
            reason=payload.reason,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    st = db.query(Student).filter(Student.id == due.student_id).first()
    grp = db.query(Group).filter(Group.id == due.group_id).first()
    return StudentDueResponse(
        id=due.id,
        student_id=due.student_id,
        student_name=st.full_name if st else "",
        group_id=due.group_id,
        group_name=grp.name if grp else "",
        charge_type=due.charge_type,
        charge_type_label=CHARGE_TYPE_LABELS.get(due.charge_type, due.charge_type),
        billing_month=due.billing_month,
        session_id=due.session_id,
        amount_piastres=due.amount,
        amount_egp=to_egp(due.amount),
        paid_amount_piastres=due.paid_amount,
        paid_amount_egp=to_egp(due.paid_amount),
        remaining_balance_piastres=0,
        remaining_balance_egp=0.0,
        status=due.status,
        status_label=DUE_STATUS_LABELS.get(due.status, due.status),
        due_date=due.due_date,
        description=due.description,
        void_reason=due.void_reason,
        created_at=due.created_at,
    )


# ==========================================
# --- Cash Payments & Allocations Endpoints ---
# ==========================================

@router.post("/payments", response_model=CashPaymentResponse, status_code=http_status.HTTP_201_CREATED, summary="Record a cash payment receipt")
def record_payment(
    payload: CashPaymentCreateRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_collect_cash")),
    db: Session = Depends(get_db)
):
    """
    Record an actual cash collection and allocate it to one or more selected dues.
    Validates amounts, bounds, and tenant/student ownership atomically.
    """
    amount_p = to_piastres(payload.amount_egp)
    allocations_data = [(a.due_id, to_piastres(a.allocated_amount_egp)) for a in payload.allocations]

    try:
        payment = FinanceRepository.record_cash_payment(
            db=db,
            teacher_id=auth.teacher_id,
            student_id=payload.student_id,
            amount_piastres=amount_p,
            payment_date=payload.payment_date,
            allocations_data=allocations_data,
            notes=payload.notes,
            receipt_number=payload.receipt_number,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    st = db.query(Student).filter(Student.id == payment.student_id).first()
    alloc_responses = []
    for al in payment.allocations:
        du = db.query(StudentDue).filter(StudentDue.id == al.due_id).first()
        alloc_responses.append(PaymentAllocationResponse(
            id=al.id,
            due_id=al.due_id,
            charge_type_label=CHARGE_TYPE_LABELS.get(du.charge_type, du.charge_type) if du else "",
            description=du.description if du else None,
            allocated_amount_piastres=al.allocated_amount,
            allocated_amount_egp=to_egp(al.allocated_amount),
            formatted_amount=format_currency_egp(al.allocated_amount),
        ))

    unalloc_p = payment.unallocated_amount
    return CashPaymentResponse(
        id=payment.id,
        student_id=payment.student_id,
        student_name=st.full_name if st else "",
        student_phone=st.phone if st else "",
        amount_piastres=payment.amount,
        amount_egp=to_egp(payment.amount),
        allocated_amount_piastres=payment.allocated_amount,
        allocated_amount_egp=to_egp(payment.allocated_amount),
        unallocated_amount_piastres=unalloc_p,
        unallocated_amount_egp=to_egp(unalloc_p),
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        receipt_number=payment.receipt_number or "—",
        notes=payment.notes,
        recorded_by_user_id=payment.recorded_by_user_id,
        recorded_by_user_type=payment.recorded_by_user_type,
        is_reversed=payment.is_reversed,
        reversal_reason=payment.reversal_reason,
        reversed_at=payment.reversed_at,
        allocations=alloc_responses,
        created_at=payment.created_at,
    )


@router.get("/payments", response_model=List[CashPaymentResponse], summary="List cash payments")
def list_payments(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    is_reversed: Optional[bool] = Query(None, description="Filter reversed payments"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    List cash payment receipts strictly scoped to teacher workspace.
    """
    query = db.query(CashPayment, Student).join(
        Student, CashPayment.student_id == Student.id
    ).filter(
        CashPayment.teacher_id == auth.teacher_id,
        CashPayment.is_deleted == False
    )

    if student_id:
        query = query.filter(CashPayment.student_id == student_id)
    if start_date:
        query = query.filter(CashPayment.payment_date >= start_date)
    if end_date:
        query = query.filter(CashPayment.payment_date <= end_date)
    if is_reversed is not None:
        query = query.filter(CashPayment.is_reversed == is_reversed)

    records = query.order_by(CashPayment.payment_date.desc(), CashPayment.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for p, st in records:
        unalloc_p = p.unallocated_amount
        results.append(CashPaymentResponse(
            id=p.id,
            student_id=p.student_id,
            student_name=st.full_name,
            student_phone=st.phone,
            amount_piastres=p.amount,
            amount_egp=to_egp(p.amount),
            allocated_amount_piastres=p.allocated_amount,
            allocated_amount_egp=to_egp(p.allocated_amount),
            unallocated_amount_piastres=unalloc_p,
            unallocated_amount_egp=to_egp(unalloc_p),
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            receipt_number=p.receipt_number or "—",
            notes=p.notes,
            recorded_by_user_id=p.recorded_by_user_id,
            recorded_by_user_type=p.recorded_by_user_type,
            is_reversed=p.is_reversed,
            reversal_reason=p.reversal_reason,
            reversed_at=p.reversed_at,
            allocations=[],
            created_at=p.created_at,
        ))
    return results


@router.get("/payments/{payment_id}", response_model=CashPaymentResponse, summary="Get payment details")
def get_payment(
    payment_id: str,
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get detailed payment receipt and its allocations.
    """
    p = db.query(CashPayment).filter(
        CashPayment.id == payment_id,
        CashPayment.teacher_id == auth.teacher_id,
        CashPayment.is_deleted == False
    ).first()
    if not p:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="إيصال السداد غير موجود")

    st = db.query(Student).filter(Student.id == p.student_id).first()
    alloc_records = db.query(PaymentAllocation, StudentDue).join(
        StudentDue, PaymentAllocation.due_id == StudentDue.id
    ).filter(
        PaymentAllocation.payment_id == p.id,
        PaymentAllocation.is_deleted == False
    ).all()

    alloc_responses = []
    for al, du in alloc_records:
        alloc_responses.append(PaymentAllocationResponse(
            id=al.id,
            due_id=du.id,
            charge_type_label=CHARGE_TYPE_LABELS.get(du.charge_type, du.charge_type),
            description=du.description,
            allocated_amount_piastres=al.allocated_amount,
            allocated_amount_egp=to_egp(al.allocated_amount),
            formatted_amount=format_currency_egp(al.allocated_amount),
        ))

    unalloc_p = p.unallocated_amount
    return CashPaymentResponse(
        id=p.id,
        student_id=p.student_id,
        student_name=st.full_name if st else "",
        student_phone=st.phone if st else "",
        amount_piastres=p.amount,
        amount_egp=to_egp(p.amount),
        allocated_amount_piastres=p.allocated_amount,
        allocated_amount_egp=to_egp(p.allocated_amount),
        unallocated_amount_piastres=unalloc_p,
        unallocated_amount_egp=to_egp(unalloc_p),
        payment_date=p.payment_date,
        payment_method=p.payment_method,
        receipt_number=p.receipt_number or "—",
        notes=p.notes,
        recorded_by_user_id=p.recorded_by_user_id,
        recorded_by_user_type=p.recorded_by_user_type,
        is_reversed=p.is_reversed,
        reversal_reason=p.reversal_reason,
        reversed_at=p.reversed_at,
        allocations=alloc_responses,
        created_at=p.created_at,
    )


@router.post("/payments/{payment_id}/reverse", response_model=CashPaymentResponse, summary="Reverse a payment receipt")
def reverse_payment(
    payment_id: str,
    payload: PaymentReverseRequest,
    auth: AuthenticatedUser = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """
    Reverse a payment and roll back its allocations atomically with an audit trail.
    """
    existing = db.query(CashPayment).filter(
        CashPayment.id == payment_id,
        CashPayment.teacher_id == auth.teacher_id,
        CashPayment.is_deleted == False
    ).first()
    if not existing:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="إيصال السداد غير موجود أو لا تملك صلاحية الوصول إليه")

    try:
        payment = FinanceRepository.reverse_payment(
            db=db,
            teacher_id=auth.teacher_id,
            payment_id=payment_id,
            reason=payload.reason,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    st = db.query(Student).filter(Student.id == payment.student_id).first()
    return CashPaymentResponse(
        id=payment.id,
        student_id=payment.student_id,
        student_name=st.full_name if st else "",
        student_phone=st.phone if st else "",
        amount_piastres=payment.amount,
        amount_egp=to_egp(payment.amount),
        allocated_amount_piastres=payment.allocated_amount,
        allocated_amount_egp=to_egp(payment.allocated_amount),
        unallocated_amount_piastres=0,
        unallocated_amount_egp=0.0,
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        receipt_number=payment.receipt_number or "—",
        notes=payment.notes,
        recorded_by_user_id=payment.recorded_by_user_id,
        recorded_by_user_type=payment.recorded_by_user_type,
        is_reversed=payment.is_reversed,
        reversal_reason=payment.reversal_reason,
        reversed_at=payment.reversed_at,
        allocations=[],
        created_at=payment.created_at,
    )


# ==========================================
# --- Reports & Ledgers Endpoints ---
# ==========================================

@router.get("/reports/student/{student_id}", response_model=StudentFinancialProfileResponse, summary="Get student financial profile & ledger")
def get_student_profile(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get student complete financial ledger: dues, payments, allocations, outstanding balance.
    """
    profile = FinanceRepository.get_student_financial_profile(db, auth.teacher_id, student_id)
    if not profile:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الطالب غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return profile


@router.get("/reports/group/{group_id}", response_model=GroupCollectionSummaryResponse, summary="Get group collection summary")
def get_group_summary(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get group aggregate collection rate, total charges, cash collected, and outstanding balance.
    """
    summary = FinanceRepository.get_group_collection_summary(db, auth.teacher_id, group_id)
    if not summary:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="المجموعة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return summary


@router.get("/reports/monthly/{billing_month}", response_model=MonthlyCollectionReportResponse, summary="Get monthly collection report")
def get_monthly_report(
    billing_month: str,
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get monthly collection report separating billing month dues from actual cash received.
    """
    return FinanceRepository.get_monthly_collection_report(db, auth.teacher_id, billing_month)


@router.get("/reports/cash", response_model=CashCollectionReportResponse, summary="Get cash collection report")
def get_cash_report(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    auth: AuthenticatedUser = Depends(require_finance_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get cash receipts collection report filtered by date range, group, or student.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date"
        )
    return FinanceRepository.get_cash_collection_report(
        db, auth.teacher_id, start_date, end_date, group_id, student_id
    )
