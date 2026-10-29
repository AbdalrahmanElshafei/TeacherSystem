import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, distinct

from app.models.user import Teacher, Assistant
from app.models.academic import Student, Group, GroupStudent, GRADE_LABELS
from app.models.attendance import ClassSession, Attendance
from app.models.finance import (
    GroupFeeConfig,
    StudentDue,
    CashPayment,
    PaymentAllocation,
    FinancialAuditLog,
    VALID_FEE_MODELS,
    FEE_MODEL_LABELS,
    VALID_DUE_STATUSES,
    DUE_STATUS_LABELS,
    VALID_CHARGE_TYPES,
    CHARGE_TYPE_LABELS,
)
from app.schemas.finance import (
    to_piastres,
    to_egp,
    format_currency_egp,
    GroupFeeConfigCreate,
    GroupFeeConfigUpdate,
)


class FinanceRepository:
    """
    Repository for Payments, Fees, Student Balances, and Collection Reporting.
    Strictly enforces tenant isolation at query level for every read, write, count, and aggregate.
    """

    # ==========================================
    # --- Group Fee Configuration ---
    # ==========================================

    @staticmethod
    def create_or_update_fee_config(
        db: Session,
        teacher_id: str,
        data: GroupFeeConfigCreate,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> GroupFeeConfig:
        """
        Create or update fee configuration for a group.
        Deactivates any previous active config for this group so history is preserved.
        """
        group = db.query(Group).filter(
            Group.id == data.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            raise ValueError("المجموعة غير موجودة أو لا تتبع هذا المعلم")

        amount_piastres = to_piastres(data.amount_egp)
        if amount_piastres < 0:
            raise ValueError("لا يمكن أن تكون قيمة الرسوم سالبة")

        # Deactivate existing active configs for this group
        now = datetime.now(timezone.utc)
        existing_configs = db.query(GroupFeeConfig).filter(
            GroupFeeConfig.group_id == data.group_id,
            GroupFeeConfig.teacher_id == teacher_id,
            GroupFeeConfig.is_active == True,
            GroupFeeConfig.is_deleted == False
        ).all()
        for cfg in existing_configs:
            cfg.is_active = False
            if not cfg.effective_to:
                cfg.effective_to = data.effective_from
            cfg.updated_at = now

        new_config = GroupFeeConfig(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            group_id=data.group_id,
            fee_model=data.fee_model,
            amount=amount_piastres,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            is_active=True,
        )
        db.add(new_config)

        # Audit Log
        audit = FinancialAuditLog(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            action="fee_config_created",
            entity_type="group_fee_config",
            entity_id=new_config.id,
            actor_user_id=user_id,
            actor_user_type=user_type,
            details=json.dumps({
                "group_id": data.group_id,
                "fee_model": data.fee_model,
                "amount_piastres": amount_piastres,
                "effective_from": data.effective_from,
            })
        )
        db.add(audit)

        db.commit()
        db.refresh(new_config)
        return new_config

    @staticmethod
    def get_active_fee_config(db: Session, teacher_id: str, group_id: str) -> Optional[GroupFeeConfig]:
        """Fetch current active fee configuration for a group."""
        return db.query(GroupFeeConfig).filter(
            GroupFeeConfig.group_id == group_id,
            GroupFeeConfig.teacher_id == teacher_id,
            GroupFeeConfig.is_active == True,
            GroupFeeConfig.is_deleted == False
        ).order_by(GroupFeeConfig.created_at.desc()).first()

    @staticmethod
    def get_fee_config_for_date(
        db: Session,
        teacher_id: str,
        group_id: str,
        date_str: str
    ) -> Optional[GroupFeeConfig]:
        """Fetch applicable fee config for a specific date (YYYY-MM-DD)."""
        config = db.query(GroupFeeConfig).filter(
            GroupFeeConfig.group_id == group_id,
            GroupFeeConfig.teacher_id == teacher_id,
            GroupFeeConfig.effective_from <= date_str,
            or_(
                GroupFeeConfig.effective_to == None,
                GroupFeeConfig.effective_to >= date_str
            ),
            GroupFeeConfig.is_deleted == False
        ).order_by(GroupFeeConfig.effective_from.desc()).first()

        if not config:
            # Fallback to current active config
            config = FinanceRepository.get_active_fee_config(db, teacher_id, group_id)
        return config

    @staticmethod
    def list_fee_configs(
        db: Session,
        teacher_id: str,
        group_id: Optional[str] = None
    ) -> List[GroupFeeConfig]:
        """List fee configurations scoped to teacher."""
        query = db.query(GroupFeeConfig).filter(
            GroupFeeConfig.teacher_id == teacher_id,
            GroupFeeConfig.is_deleted == False
        )
        if group_id:
            query = query.filter(GroupFeeConfig.group_id == group_id)
        return query.order_by(GroupFeeConfig.created_at.desc()).all()

    # ==========================================
    # --- Monthly Dues Generation ---
    # ==========================================

    @staticmethod
    def preview_monthly_dues(
        db: Session,
        teacher_id: str,
        group_id: str,
        billing_month: str
    ) -> Dict[str, Any]:
        """
        Preview eligible students and expected dues for a billing month.
        Mid-month enrollment policy:
        Students enrolled on or before the last day of the billing month qualify.
        """
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            raise ValueError("المجموعة غير موجودة أو لا تتبع هذا المعلم")

        # Get fee config applicable to the 1st of the month
        month_start_date = f"{billing_month}-01"
        month_end_date = f"{billing_month}-31"
        fee_config = FinanceRepository.get_fee_config_for_date(db, teacher_id, group_id, month_start_date)

        if not fee_config or fee_config.fee_model != "monthly":
            raise ValueError(f"المجموعة '{group.name}' غير مهيأة لنظام الاشتراك الشهري")

        # Get all actively enrolled students in group
        enrollments = db.query(GroupStudent, Student).join(
            Student, GroupStudent.student_id == Student.id
        ).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        # Check existing dues for this group and billing month
        existing_dues = {
            d.student_id: d for d in db.query(StudentDue).filter(
                StudentDue.group_id == group_id,
                StudentDue.teacher_id == teacher_id,
                StudentDue.billing_month == billing_month,
                StudentDue.is_deleted == False
            ).all()
        }

        students_list = []
        newly_billable = 0
        already_billed = 0
        total_expected_piastres = 0

        for enroll, student in enrollments:
            # Mid-month policy: verify enrollment date is on or before month end
            joined_str = enroll.joined_at.strftime("%Y-%m-%d") if enroll.joined_at else month_start_date
            if joined_str > month_end_date:
                continue  # Joined in a later month

            existing = existing_dues.get(student.id)
            is_already_billed = existing is not None and existing.status != "void"

            if is_already_billed:
                already_billed += 1
                amount_p = existing.amount
            else:
                newly_billable += 1
                amount_p = fee_config.amount
                total_expected_piastres += amount_p

            students_list.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "student_phone": student.phone,
                "joined_at": joined_str,
                "amount_piastres": amount_p,
                "amount_egp": to_egp(amount_p),
                "already_billed": is_already_billed,
                "due_id": existing.id if existing else None
            })

        return {
            "group_id": group.id,
            "group_name": group.name,
            "billing_month": billing_month,
            "fee_model": fee_config.fee_model,
            "fee_model_label": FEE_MODEL_LABELS.get(fee_config.fee_model, fee_config.fee_model),
            "fee_amount_egp": to_egp(fee_config.amount),
            "total_enrolled_eligible": len(students_list),
            "newly_billable_count": newly_billable,
            "already_billed_count": already_billed,
            "total_expected_piastres": total_expected_piastres,
            "total_expected_egp": to_egp(total_expected_piastres),
            "students": students_list
        }

    @staticmethod
    def generate_monthly_dues(
        db: Session,
        teacher_id: str,
        group_id: str,
        billing_month: str,
        due_date: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> Tuple[int, int, int]:
        """
        Generate monthly dues for a group and billing month in an atomic transaction.
        Idempotent: skips already billed students without overwriting.
        Returns: (generated_count, skipped_count, total_amount_piastres).
        """
        preview = FinanceRepository.preview_monthly_dues(db, teacher_id, group_id, billing_month)
        group = db.query(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id).first()
        fee_config = FinanceRepository.get_fee_config_for_date(db, teacher_id, group_id, f"{billing_month}-01")

        target_due_date = due_date or f"{billing_month}-05"  # Standard default due date
        generated_count = 0
        total_amount_p = 0
        now = datetime.now(timezone.utc)

        for st in preview["students"]:
            if st["already_billed"]:
                continue

            due = StudentDue(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                student_id=st["student_id"],
                group_id=group_id,
                fee_config_id=fee_config.id if fee_config else None,
                charge_type="monthly_fee",
                billing_month=billing_month,
                amount=st["amount_piastres"],
                paid_amount=0,
                status="unpaid",
                due_date=target_due_date,
                description=f"اشتراك شهر {billing_month} — {group.name}",
            )
            db.add(due)
            generated_count += 1
            total_amount_p += st["amount_piastres"]

        if generated_count > 0:
            audit = FinancialAuditLog(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                action="monthly_dues_generated",
                entity_type="student_due",
                entity_id=None,
                actor_user_id=user_id,
                actor_user_type=user_type,
                details=json.dumps({
                    "group_id": group_id,
                    "billing_month": billing_month,
                    "generated_count": generated_count,
                    "total_amount_piastres": total_amount_p
                })
            )
            db.add(audit)

        db.commit()
        return generated_count, preview["already_billed_count"], total_amount_p

    # ==========================================
    # --- Per-Session Dues Generation ---
    # ==========================================

    @staticmethod
    def preview_session_dues(
        db: Session,
        teacher_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Preview eligible students and dues for a completed class session.
        Rule: Session must be completed. Only students with status 'present' or 'late' qualify.
        """
        sess = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not sess:
            raise ValueError("الحصة غير موجودة أو لا تتبع هذا المعلم")

        group = db.query(Group).filter(Group.id == sess.group_id, Group.teacher_id == teacher_id).first()
        fee_config = FinanceRepository.get_fee_config_for_date(db, teacher_id, sess.group_id, sess.session_date)

        is_eligible = True
        ineligibility_reason = None
        if sess.status != "completed":
            is_eligible = False
            ineligibility_reason = "الحصة لم تكتمل بعد (يجب اكتمال الحصة أولاً لرصد رسوم الحصص)"
        elif not fee_config or fee_config.fee_model != "per_session":
            is_eligible = False
            ineligibility_reason = f"المجموعة '{group.name}' غير مهيأة لنظام الحساب بالحصة"

        fee_amount_p = fee_config.amount if fee_config else 0

        # Query attendance records for present / late students
        attended_records = db.query(Attendance, Student).join(
            Student, Attendance.student_id == Student.id
        ).filter(
            Attendance.session_id == session_id,
            Attendance.teacher_id == teacher_id,
            Attendance.status.in_(["present", "late"]),
            Attendance.is_deleted == False,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        # Existing charges for this session
        existing_charges = {
            d.student_id: d for d in db.query(StudentDue).filter(
                StudentDue.session_id == session_id,
                StudentDue.teacher_id == teacher_id,
                StudentDue.is_deleted == False
            ).all()
        }

        students_list = []
        newly_billable = 0
        already_charged = 0
        total_expected_p = 0

        for att, student in attended_records:
            existing = existing_charges.get(student.id)
            is_already = existing is not None and existing.status != "void"

            if is_already:
                already_charged += 1
                amount_p = existing.amount
            else:
                newly_billable += 1
                amount_p = fee_amount_p
                if is_eligible:
                    total_expected_p += amount_p

            students_list.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "student_phone": student.phone,
                "joined_at": sess.session_date,
                "amount_piastres": amount_p,
                "amount_egp": to_egp(amount_p),
                "already_billed": is_already,
                "due_id": existing.id if existing else None
            })

        return {
            "session_id": sess.id,
            "group_id": sess.group_id,
            "group_name": group.name if group else "",
            "session_date": sess.session_date,
            "session_status": sess.status,
            "is_eligible_session": is_eligible,
            "ineligibility_reason": ineligibility_reason,
            "fee_amount_egp": to_egp(fee_amount_p),
            "attended_students_count": len(attended_records),
            "newly_billable_count": newly_billable,
            "already_charged_count": already_charged,
            "total_expected_piastres": total_expected_p,
            "total_expected_egp": to_egp(total_expected_p),
            "students": students_list
        }

    @staticmethod
    def generate_session_dues(
        db: Session,
        teacher_id: str,
        session_id: str,
        due_date: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> Tuple[int, int, int]:
        """
        Generate session dues for all qualifying attended students in a completed session.
        Idempotent: prevents duplicate charges via database constraints and pre-checks.
        """
        preview = FinanceRepository.preview_session_dues(db, teacher_id, session_id)
        if not preview["is_eligible_session"]:
            raise ValueError(preview["ineligibility_reason"] or "الحصة غير مؤهلة لإنشاء رسوم")

        sess = db.query(ClassSession).filter(ClassSession.id == session_id, ClassSession.teacher_id == teacher_id).first()
        group = db.query(Group).filter(Group.id == sess.group_id, Group.teacher_id == teacher_id).first()
        fee_config = FinanceRepository.get_fee_config_for_date(db, teacher_id, sess.group_id, sess.session_date)

        target_due_date = due_date or sess.session_date
        generated_count = 0
        total_amount_p = 0

        for st in preview["students"]:
            if st["already_billed"]:
                continue

            due = StudentDue(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                student_id=st["student_id"],
                group_id=sess.group_id,
                fee_config_id=fee_config.id if fee_config else None,
                charge_type="session_fee",
                session_id=session_id,
                amount=st["amount_piastres"],
                paid_amount=0,
                status="unpaid",
                due_date=target_due_date,
                description=f"رسوم حصة {sess.session_date} — {group.name if group else ''}",
            )
            db.add(due)
            generated_count += 1
            total_amount_p += st["amount_piastres"]

        if generated_count > 0:
            audit = FinancialAuditLog(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                action="session_dues_generated",
                entity_type="student_due",
                entity_id=session_id,
                actor_user_id=user_id,
                actor_user_type=user_type,
                details=json.dumps({
                    "session_id": session_id,
                    "generated_count": generated_count,
                    "total_amount_piastres": total_amount_p
                })
            )
            db.add(audit)

        db.commit()
        return generated_count, preview["already_charged_count"], total_amount_p

    # ==========================================
    # --- Cash Payments & Allocations ---
    # ==========================================

    @staticmethod
    def _generate_receipt_number(db: Session, teacher_id: str, payment_date: str) -> str:
        """Generate human-readable, unique receipt number: RCP-YYYYMM-XXXX."""
        prefix = f"RCP-{payment_date[:7].replace('-', '')}"
        count = db.query(CashPayment).filter(
            CashPayment.teacher_id == teacher_id,
            CashPayment.payment_date.startswith(payment_date[:7])
        ).count()
        return f"{prefix}-{(count + 1):04d}"

    @staticmethod
    def record_cash_payment(
        db: Session,
        teacher_id: str,
        student_id: str,
        amount_piastres: int,
        payment_date: str,
        allocations_data: List[Tuple[str, int]],  # List of (due_id, allocated_piastres)
        notes: Optional[str] = None,
        receipt_number: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> CashPayment:
        """
        Record a cash receipt and atomically allocate it to student dues.
        Validates:
        - Student belongs to teacher.
        - Payment amount > 0.
        - Total allocated <= Payment amount.
        - Each allocated due belongs to the same student and teacher.
        - Allocated amount <= outstanding balance of the due.
        """
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            raise ValueError("الطالب غير موجود أو لا تتبع هذا المعلم")

        if amount_piastres <= 0:
            raise ValueError("مبلغ السداد يجب أن يكون أكبر من الصفر")

        total_allocated_p = sum(alloc[1] for alloc in allocations_data)
        if total_allocated_p > amount_piastres:
            raise ValueError("إجمالي المبالغ المخصصة يتجاوز المبلغ المحصل")

        # Validate each due before mutating
        due_map = {}
        for due_id, alloc_p in allocations_data:
            if alloc_p <= 0:
                raise ValueError("لا يمكن تخصيص مبلغ صفر أو سالب لأي رسم")
            due = db.query(StudentDue).filter(
                StudentDue.id == due_id,
                StudentDue.teacher_id == teacher_id,
                StudentDue.student_id == student_id,
                StudentDue.is_deleted == False
            ).first()
            if not due:
                raise ValueError(f"الرسم برقم المعرف {due_id} غير موجود أو لا يخص هذا الطالب")
            if due.status == "void":
                raise ValueError(f"لا يمكن السداد على رسم ملغى ({due.description or due.id})")

            remaining = due.amount - due.paid_amount
            if alloc_p > remaining:
                raise ValueError(
                    f"المبلغ المخصص ({to_egp(alloc_p)} ج.م) يتجاوز الرصيد المتبقي للرسم ({to_egp(remaining)} ج.م)"
                )
            due_map[due_id] = due

        # Create Payment
        final_receipt_no = receipt_number or FinanceRepository._generate_receipt_number(db, teacher_id, payment_date)
        payment = CashPayment(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            student_id=student_id,
            amount=amount_piastres,
            allocated_amount=total_allocated_p,
            payment_date=payment_date,
            payment_method="cash",
            receipt_number=final_receipt_no,
            notes=notes.strip() if notes else None,
            recorded_by_user_id=user_id,
            recorded_by_user_type=user_type,
            is_reversed=False,
        )
        db.add(payment)

        now = datetime.now(timezone.utc)
        for due_id, alloc_p in allocations_data:
            due = due_map[due_id]
            allocation = PaymentAllocation(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                payment_id=payment.id,
                due_id=due_id,
                allocated_amount=alloc_p,
            )
            db.add(allocation)

            due.paid_amount += alloc_p
            if due.paid_amount >= due.amount:
                due.status = "paid"
            else:
                due.status = "partially_paid"
            due.updated_at = now

        # Audit Log
        audit = FinancialAuditLog(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            action="payment_recorded",
            entity_type="cash_payment",
            entity_id=payment.id,
            actor_user_id=user_id,
            actor_user_type=user_type,
            details=json.dumps({
                "student_id": student_id,
                "amount_piastres": amount_piastres,
                "allocated_piastres": total_allocated_p,
                "receipt_number": final_receipt_no,
                "allocations_count": len(allocations_data)
            })
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def reverse_payment(
        db: Session,
        teacher_id: str,
        payment_id: str,
        reason: str,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> CashPayment:
        """
        Reverse a cash payment and roll back its allocations atomically.
        Restores dues balances and maintains full auditability.
        """
        payment = db.query(CashPayment).filter(
            CashPayment.id == payment_id,
            CashPayment.teacher_id == teacher_id,
            CashPayment.is_deleted == False
        ).first()
        if not payment:
            raise ValueError("إيصال السداد غير موجود أو لا تملك صلاحية الوصول إليه")
        if payment.is_reversed:
            raise ValueError("تم إلغاء هذا الإيصال بالفعل مسبقاً")

        allocations = db.query(PaymentAllocation).filter(
            PaymentAllocation.payment_id == payment_id,
            PaymentAllocation.teacher_id == teacher_id,
            PaymentAllocation.is_deleted == False
        ).all()

        now = datetime.now(timezone.utc)
        for alloc in allocations:
            due = db.query(StudentDue).filter(
                StudentDue.id == alloc.due_id,
                StudentDue.teacher_id == teacher_id
            ).first()
            if due:
                due.paid_amount = max(0, due.paid_amount - alloc.allocated_amount)
                if due.status != "void":
                    if due.paid_amount == 0:
                        due.status = "unpaid"
                    elif due.paid_amount < due.amount:
                        due.status = "partially_paid"
                    else:
                        due.status = "paid"
                due.updated_at = now

            alloc.is_deleted = True
            alloc.updated_at = now

        payment.is_reversed = True
        payment.reversal_reason = reason.strip()
        payment.reversed_at = now
        payment.reversed_by_user_id = user_id
        payment.updated_at = now

        # Audit Log
        audit = FinancialAuditLog(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            action="payment_reversed",
            entity_type="cash_payment",
            entity_id=payment.id,
            actor_user_id=user_id,
            actor_user_type=user_type,
            details=json.dumps({
                "payment_id": payment_id,
                "receipt_number": payment.receipt_number,
                "amount_piastres": payment.amount,
                "reason": reason
            })
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def void_due(
        db: Session,
        teacher_id: str,
        due_id: str,
        reason: str,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> StudentDue:
        """
        Void an unpaid student due with an auditable reason.
        Rejects voiding if any payments are currently allocated to it.
        """
        due = db.query(StudentDue).filter(
            StudentDue.id == due_id,
            StudentDue.teacher_id == teacher_id,
            StudentDue.is_deleted == False
        ).first()
        if not due:
            raise ValueError("الرسم غير موجود أو لا تملك صلاحية الوصول إليه")
        if due.status == "void":
            raise ValueError("هذا الرسم ملغى بالفعل")
        if due.paid_amount > 0:
            raise ValueError("لا يمكن إلغاء رسم تم سداد جزء منه أو سداده بالكامل. يجب إلغاء إيصال السداد أولاً")

        now = datetime.now(timezone.utc)
        due.status = "void"
        due.void_reason = reason.strip()
        due.voided_at = now
        due.voided_by_user_id = user_id
        due.updated_at = now

        audit = FinancialAuditLog(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            action="due_voided",
            entity_type="student_due",
            entity_id=due.id,
            actor_user_id=user_id,
            actor_user_type=user_type,
            details=json.dumps({
                "due_id": due.id,
                "student_id": due.student_id,
                "amount_piastres": due.amount,
                "reason": reason
            })
        )
        db.add(audit)

        db.commit()
        db.refresh(due)
        return due

    # ==========================================
    # --- Financial Reports & Ledgers ---
    # ==========================================

    @staticmethod
    def get_student_financial_profile(
        db: Session,
        teacher_id: str,
        student_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete student financial ledger, dues, payments, and outstanding balance.
        """
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            return None

        # Fetch non-deleted dues
        dues = db.query(StudentDue, Group).outerjoin(
            Group, StudentDue.group_id == Group.id
        ).filter(
            StudentDue.student_id == student_id,
            StudentDue.teacher_id == teacher_id,
            StudentDue.is_deleted == False
        ).order_by(StudentDue.due_date.desc(), StudentDue.created_at.desc()).all()

        # Fetch non-deleted payments
        payments = db.query(CashPayment).filter(
            CashPayment.student_id == student_id,
            CashPayment.teacher_id == teacher_id,
            CashPayment.is_deleted == False
        ).order_by(CashPayment.payment_date.desc(), CashPayment.created_at.desc()).all()

        total_dues_p = sum(d.amount for d, _ in dues if d.status != "void")
        total_paid_p = sum(p.amount for p in payments if not p.is_reversed)
        total_allocated_p = sum(p.allocated_amount for p in payments if not p.is_reversed)
        outstanding_p = max(0, total_dues_p - total_allocated_p)
        unallocated_cash_p = max(0, total_paid_p - total_allocated_p)

        dues_list = []
        for d, grp in dues:
            rem_p = d.remaining_balance
            dues_list.append({
                "id": d.id,
                "student_id": d.student_id,
                "student_name": student.full_name,
                "group_id": d.group_id,
                "group_name": grp.name if grp else "مجموعة سابقة",
                "charge_type": d.charge_type,
                "charge_type_label": CHARGE_TYPE_LABELS.get(d.charge_type, d.charge_type),
                "billing_month": d.billing_month,
                "session_id": d.session_id,
                "amount_piastres": d.amount,
                "amount_egp": to_egp(d.amount),
                "paid_amount_piastres": d.paid_amount,
                "paid_amount_egp": to_egp(d.paid_amount),
                "remaining_balance_piastres": rem_p,
                "remaining_balance_egp": to_egp(rem_p),
                "status": d.status,
                "status_label": DUE_STATUS_LABELS.get(d.status, d.status),
                "due_date": d.due_date,
                "description": d.description,
                "void_reason": d.void_reason,
                "created_at": d.created_at
            })

        payments_list = []
        for p in payments:
            alloc_records = db.query(PaymentAllocation, StudentDue).join(
                StudentDue, PaymentAllocation.due_id == StudentDue.id
            ).filter(
                PaymentAllocation.payment_id == p.id,
                PaymentAllocation.is_deleted == False
            ).all()

            alloc_list = []
            for al, du in alloc_records:
                alloc_list.append({
                    "id": al.id,
                    "due_id": du.id,
                    "charge_type_label": CHARGE_TYPE_LABELS.get(du.charge_type, du.charge_type),
                    "description": du.description,
                    "allocated_amount_piastres": al.allocated_amount,
                    "allocated_amount_egp": to_egp(al.allocated_amount),
                    "formatted_amount": format_currency_egp(al.allocated_amount)
                })

            unalloc_p = p.unallocated_amount
            payments_list.append({
                "id": p.id,
                "student_id": p.student_id,
                "student_name": student.full_name,
                "student_phone": student.phone,
                "amount_piastres": p.amount,
                "amount_egp": to_egp(p.amount),
                "allocated_amount_piastres": p.allocated_amount,
                "allocated_amount_egp": to_egp(p.allocated_amount),
                "unallocated_amount_piastres": unalloc_p,
                "unallocated_amount_egp": to_egp(unalloc_p),
                "payment_date": p.payment_date,
                "payment_method": p.payment_method,
                "receipt_number": p.receipt_number or "—",
                "notes": p.notes,
                "recorded_by_user_id": p.recorded_by_user_id,
                "recorded_by_user_type": p.recorded_by_user_type,
                "is_reversed": p.is_reversed,
                "reversal_reason": p.reversal_reason,
                "reversed_at": p.reversed_at,
                "allocations": alloc_list,
                "created_at": p.created_at
            })

        return {
            "student_id": student.id,
            "student_name": student.full_name,
            "student_phone": student.phone,
            "parent_phone": student.parent_phone,
            "grade_level": student.grade_level,
            "grade_label": GRADE_LABELS.get(student.grade_level, ""),
            "total_dues_piastres": total_dues_p,
            "total_dues_egp": to_egp(total_dues_p),
            "total_paid_piastres": total_paid_p,
            "total_paid_egp": to_egp(total_paid_p),
            "total_allocated_piastres": total_allocated_p,
            "total_allocated_egp": to_egp(total_allocated_p),
            "outstanding_balance_piastres": outstanding_p,
            "outstanding_balance_egp": to_egp(outstanding_p),
            "unallocated_cash_piastres": unallocated_cash_p,
            "unallocated_cash_egp": to_egp(unallocated_cash_p),
            "dues": dues_list,
            "payments": payments_list
        }

    @staticmethod
    def get_group_collection_summary(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate collection summary and rate for a specific group.
        Collection rate denominator is strictly total charges generated.
        """
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            return None

        fee_cfg = FinanceRepository.get_active_fee_config(db, teacher_id, group_id)

        # Enrolled active students count
        total_students = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).count()

        # Dues for this group
        dues = db.query(StudentDue).filter(
            StudentDue.group_id == group_id,
            StudentDue.teacher_id == teacher_id,
            StudentDue.is_deleted == False,
            StudentDue.status != "void"
        ).all()

        total_charges_p = sum(d.amount for d in dues)
        total_collected_p = sum(d.paid_amount for d in dues)
        outstanding_p = max(0, total_charges_p - total_collected_p)
        collection_rate = round((total_collected_p / total_charges_p * 100), 1) if total_charges_p > 0 else 0.0

        students_with_bal = len({d.student_id for d in dues if d.status in ("unpaid", "partially_paid")})

        return {
            "group_id": group.id,
            "group_name": group.name,
            "grade_level": group.grade_level,
            "grade_label": GRADE_LABELS.get(group.grade_level, ""),
            "fee_model": fee_cfg.fee_model if fee_cfg else None,
            "fee_model_label": FEE_MODEL_LABELS.get(fee_cfg.fee_model) if fee_cfg else None,
            "active_fee_amount_egp": to_egp(fee_cfg.amount) if fee_cfg else None,
            "total_charges_piastres": total_charges_p,
            "total_charges_egp": to_egp(total_charges_p),
            "total_collected_piastres": total_collected_p,
            "total_collected_egp": to_egp(total_collected_p),
            "outstanding_balance_piastres": outstanding_p,
            "outstanding_balance_egp": to_egp(outstanding_p),
            "collection_rate": collection_rate,
            "students_with_balance_count": students_with_bal,
            "total_students_enrolled": total_students
        }

    @staticmethod
    def get_monthly_collection_report(
        db: Session,
        teacher_id: str,
        billing_month: str
    ) -> Dict[str, Any]:
        """
        Monthly collection report separating billing month dues from actual cash receipts.
        """
        # 1. Dimension: Charges generated for this billing month
        month_dues = db.query(StudentDue).filter(
            StudentDue.teacher_id == teacher_id,
            StudentDue.billing_month == billing_month,
            StudentDue.is_deleted == False,
            StudentDue.status != "void"
        ).all()

        charges_p = sum(d.amount for d in month_dues)
        allocated_to_month_p = sum(d.paid_amount for d in month_dues)
        outstanding_month_p = max(0, charges_p - allocated_to_month_p)
        month_rate = round((allocated_to_month_p / charges_p * 100), 1) if charges_p > 0 else 0.0

        # 2. Dimension: Cash received in this calendar month
        month_payments = db.query(CashPayment).filter(
            CashPayment.teacher_id == teacher_id,
            CashPayment.payment_date.startswith(billing_month),
            CashPayment.is_deleted == False,
            CashPayment.is_reversed == False
        ).all()

        cash_received_p = sum(p.amount for p in month_payments)
        distinct_students_paid = len({p.student_id for p in month_payments})

        return {
            "billing_month": billing_month,
            "charges_generated_piastres": charges_p,
            "charges_generated_egp": to_egp(charges_p),
            "charges_count": len(month_dues),
            "allocated_to_month_charges_piastres": allocated_to_month_p,
            "allocated_to_month_charges_egp": to_egp(allocated_to_month_p),
            "outstanding_month_dues_piastres": outstanding_month_p,
            "outstanding_month_dues_egp": to_egp(outstanding_month_p),
            "month_collection_rate": month_rate,
            "cash_received_in_month_piastres": cash_received_p,
            "cash_received_in_month_egp": to_egp(cash_received_p),
            "payments_count": len(month_payments),
            "distinct_students_paid": distinct_students_paid
        }

    @staticmethod
    def get_cash_collection_report(
        db: Session,
        teacher_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_id: Optional[str] = None,
        student_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cash receipts collection report filtered by date range, group, and student.
        """
        query = db.query(CashPayment, Student).join(
            Student, CashPayment.student_id == Student.id
        ).filter(
            CashPayment.teacher_id == teacher_id,
            CashPayment.is_deleted == False,
            CashPayment.is_reversed == False
        )

        if start_date:
            query = query.filter(CashPayment.payment_date >= start_date)
        if end_date:
            query = query.filter(CashPayment.payment_date <= end_date)
        if student_id:
            query = query.filter(CashPayment.student_id == student_id)
        if group_id:
            # Join through GroupStudent
            query = query.join(GroupStudent, GroupStudent.student_id == Student.id).filter(
                GroupStudent.group_id == group_id,
                GroupStudent.is_deleted == False
            )

        records = query.order_by(CashPayment.payment_date.desc(), CashPayment.created_at.desc()).all()

        total_cash_p = sum(p.amount for p, _ in records)
        total_alloc_p = sum(p.allocated_amount for p, _ in records)

        items = []
        for p, st in records:
            items.append({
                "payment_id": p.id,
                "receipt_number": p.receipt_number or "—",
                "student_id": st.id,
                "student_name": st.full_name,
                "student_phone": st.phone,
                "payment_date": p.payment_date,
                "amount_piastres": p.amount,
                "amount_egp": to_egp(p.amount),
                "allocated_amount_piastres": p.allocated_amount,
                "allocated_amount_egp": to_egp(p.allocated_amount),
                "notes": p.notes,
                "recorded_by": p.recorded_by_user_type
            })

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_cash_received_piastres": total_cash_p,
            "total_cash_received_egp": to_egp(total_cash_p),
            "total_payments_count": len(records),
            "total_allocated_piastres": total_alloc_p,
            "total_allocated_egp": to_egp(total_alloc_p),
            "payments": items
        }

    @staticmethod
    def get_finance_overview(db: Session, teacher_id: str) -> Dict[str, Any]:
        """
        Dashboard overview metrics and collection status across all teacher's groups.
        """
        all_dues = db.query(StudentDue).filter(
            StudentDue.teacher_id == teacher_id,
            StudentDue.is_deleted == False,
            StudentDue.status != "void"
        ).all()

        all_payments = db.query(CashPayment).filter(
            CashPayment.teacher_id == teacher_id,
            CashPayment.is_deleted == False,
            CashPayment.is_reversed == False
        ).order_by(CashPayment.payment_date.desc(), CashPayment.created_at.desc()).all()

        total_charges_p = sum(d.amount for d in all_dues)
        total_collected_p = sum(p.amount for p in all_payments)
        total_allocated_p = sum(d.paid_amount for d in all_dues)
        total_outstanding_p = max(0, total_charges_p - total_allocated_p)

        unpaid_students = {d.student_id for d in all_dues if d.status in ("unpaid", "partially_paid")}

        groups = db.query(Group).filter(
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).all()

        groups_summary = []
        for g in groups:
            summary = FinanceRepository.get_group_collection_summary(db, teacher_id, g.id)
            if summary:
                groups_summary.append(summary)

        # Recent payments formatting
        recent_payments = []
        for p in all_payments[:10]:
            st = db.query(Student).filter(Student.id == p.student_id).first()
            unalloc_p = p.unallocated_amount
            recent_payments.append({
                "id": p.id,
                "student_id": p.student_id,
                "student_name": st.full_name if st else "",
                "student_phone": st.phone if st else "",
                "amount_piastres": p.amount,
                "amount_egp": to_egp(p.amount),
                "allocated_amount_piastres": p.allocated_amount,
                "allocated_amount_egp": to_egp(p.allocated_amount),
                "unallocated_amount_piastres": unalloc_p,
                "unallocated_amount_egp": to_egp(unalloc_p),
                "payment_date": p.payment_date,
                "payment_method": p.payment_method,
                "receipt_number": p.receipt_number or "—",
                "notes": p.notes,
                "recorded_by_user_id": p.recorded_by_user_id,
                "recorded_by_user_type": p.recorded_by_user_type,
                "is_reversed": p.is_reversed,
                "reversal_reason": p.reversal_reason,
                "reversed_at": p.reversed_at,
                "allocations": [],
                "created_at": p.created_at
            })

        return {
            "total_cash_collected_piastres": total_collected_p,
            "total_cash_collected_egp": to_egp(total_collected_p),
            "total_outstanding_balance_piastres": total_outstanding_p,
            "total_outstanding_balance_egp": to_egp(total_outstanding_p),
            "total_charges_piastres": total_charges_p,
            "total_charges_egp": to_egp(total_charges_p),
            "students_with_outstanding_count": len(unpaid_students),
            "recent_payments": recent_payments,
            "groups_summary": groups_summary
        }
