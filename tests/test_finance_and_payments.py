import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.models
from app.main import app
from app.config import CSRF_HEADER_NAME
from app.core.security import hash_password
from app.models.user import Teacher, Assistant
from app.models.academic import Student, Group, GroupStudent
from app.models.attendance import ClassSession, Attendance
from app.models.finance import (
    GroupFeeConfig,
    StudentDue,
    CashPayment,
    PaymentAllocation,
    FinancialAuditLog
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return {
        CSRF_HEADER_NAME: data["csrf_token"],
        "Authorization": f"Bearer {data['session_token']}"
    }


def _create_teacher(db, username="mr_finance", password="Password123!"):
    teacher = Teacher(
        id=str(uuid.uuid4()),
        username=username,
        full_name="Mr. Finance Teacher",
        phone="01011112222",
        hashed_password=hash_password(password),
        is_active=True
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def _create_student(db, teacher_id, full_name="Ahmed Ali", phone="01099998888", grade="1_sec"):
    student = Student(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        full_name=full_name,
        phone=phone,
        grade_level=grade,
        parent_name="Ali Father",
        parent_phone="01088887777",
        is_active=True
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def _create_group(db, teacher_id, name="Group Sunday 1st Sec", grade="1_sec"):
    group = Group(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        name=name,
        grade_level=grade,
        is_active=True
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def _enroll_student(db, teacher_id, group_id, student_id, joined_at=None):
    gs = GroupStudent(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        group_id=group_id,
        student_id=student_id,
        joined_at=joined_at or datetime.now(timezone.utc),
        is_active=True
    )
    db.add(gs)
    db.commit()
    return gs


# ==============================================================================
# 1. Group Fee Config Tests
# ==============================================================================

def test_group_fee_config_crud_and_validation(client, db_session):
    teacher = _create_teacher(db_session, "fee_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Physics Group A")
    headers = _login(client, "fee_teacher", "Pass12345!")

    # 1. Create monthly fee config: 250.00 EGP
    resp = client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": 250.0,
        "effective_from": "2026-10-01",
        "notes": "First term monthly subscription"
    })
    assert resp.status_code == 201
    cfg_data = resp.json()
    assert cfg_data["group_id"] == group.id
    assert cfg_data["fee_model"] == "monthly"
    assert cfg_data["amount_piastres"] == 25000  # 250 EGP in piastres
    assert cfg_data["amount_egp"] == 250.0
    assert cfg_data["is_active"] is True
    config_id = cfg_data["id"]

    # 2. Get active fee for group
    resp_active = client.get(f"/api/finance/fees/group/{group.id}", headers=headers)
    assert resp_active.status_code == 200
    assert resp_active.json()["id"] == config_id
    assert resp_active.json()["amount_egp"] == 250.0

    # 3. Create a new fee config for the same group (per_session: 60 EGP) -> automatically deactivates previous
    resp2 = client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "per_session",
        "amount_egp": 60.0,
        "effective_from": "2026-11-01"
    })
    assert resp2.status_code == 201
    new_cfg = resp2.json()
    assert new_cfg["fee_model"] == "per_session"
    assert new_cfg["amount_piastres"] == 6000

    # Verify previous config was deactivated
    resp_active2 = client.get(f"/api/finance/fees/group/{group.id}", headers=headers)
    assert resp_active2.status_code == 200
    assert resp_active2.json()["id"] == new_cfg["id"]
    assert resp_active2.json()["fee_model"] == "per_session"

    # 4. List fee configs
    resp_list = client.get(f"/api/finance/fees?group_id={group.id}", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) == 2

    # 5. Validation: Negative or zero amount rejected
    resp_bad = client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": -50.0,
        "effective_from": "2026-10-01"
    })
    assert resp_bad.status_code in (400, 422)

    # Validation: Invalid fee model rejected
    resp_bad_model = client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "yearly_discount",
        "amount_egp": 100.0,
        "effective_from": "2026-10-01"
    })
    assert resp_bad_model.status_code in (400, 422)


# ==============================================================================
# 2. Monthly Dues Generation & Idempotency
# ==============================================================================

def test_monthly_dues_preview_and_generation(client, db_session):
    teacher = _create_teacher(db_session, "monthly_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Chemistry Group 1")
    s1 = _create_student(db_session, teacher.id, "Student One", "01011110001")
    s2 = _create_student(db_session, teacher.id, "Student Two", "01011110002")
    s3_future = _create_student(db_session, teacher.id, "Student NextMonth", "01011110003")

    # Enroll s1 and s2 in October 2026
    _enroll_student(db_session, teacher.id, group.id, s1.id, joined_at=datetime(2026, 10, 5, tzinfo=timezone.utc))
    _enroll_student(db_session, teacher.id, group.id, s2.id, joined_at=datetime(2026, 10, 20, tzinfo=timezone.utc))
    # Enroll s3 in November 2026 (should be excluded from October billing)
    _enroll_student(db_session, teacher.id, group.id, s3_future.id, joined_at=datetime(2026, 11, 2, tzinfo=timezone.utc))

    headers = _login(client, "monthly_teacher", "Pass12345!")

    # Set active monthly fee: 200.00 EGP
    client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": 200.0,
        "effective_from": "2026-10-01"
    })

    # 1. Preview October 2026 dues
    resp_prev = client.post("/api/finance/dues/monthly/preview", headers=headers, json={
        "group_id": group.id,
        "billing_month": "2026-10",
        "due_date": "2026-10-10"
    })
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert prev_data["eligible_students_count"] == 2
    assert prev_data["already_generated_count"] == 0
    assert prev_data["to_be_generated_count"] == 2
    assert prev_data["total_amount_piastres"] == 40000  # 400 EGP in piastres
    assert prev_data["total_amount_egp"] == 400.0

    # 2. Confirm and Generate October dues
    resp_gen = client.post("/api/finance/dues/monthly/generate", headers=headers, json={
        "group_id": group.id,
        "billing_month": "2026-10",
        "due_date": "2026-10-10"
    })
    assert resp_gen.status_code in (200, 201)
    gen_data = resp_gen.json()
    assert gen_data["generated_count"] == 2
    assert gen_data["total_amount_egp"] == 400.0

    # 3. IDEMPOTENCY TEST: Run generate again for the same month and group -> 0 generated
    resp_gen2 = client.post("/api/finance/dues/monthly/generate", headers=headers, json={
        "group_id": group.id,
        "billing_month": "2026-10",
        "due_date": "2026-10-10"
    })
    assert resp_gen2.status_code in (200, 201)
    gen_data2 = resp_gen2.json()
    assert gen_data2["generated_count"] == 0
    assert gen_data2["total_amount_egp"] == 0.0

    # Verify in DB: exactly 2 dues exist
    resp_dues = client.get(f"/api/finance/dues?group_id={group.id}&billing_month=2026-10", headers=headers)
    assert resp_dues.status_code == 200
    dues_list = resp_dues.json()
    assert len(dues_list) == 2
    for d in dues_list:
        assert d["amount_piastres"] == 20000
        assert d["paid_amount_piastres"] == 0
        assert d["status"] == "unpaid"
        assert d["charge_type"] == "monthly_fee"


# ==============================================================================
# 3. Session Dues Generation
# ==============================================================================

def test_session_dues_generation(client, db_session):
    teacher = _create_teacher(db_session, "session_fee_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Maths Group B")
    s1 = _create_student(db_session, teacher.id, "Student Present", "01022220001")
    s2 = _create_student(db_session, teacher.id, "Student Late", "01022220002")
    s3 = _create_student(db_session, teacher.id, "Student Absent", "01022220003")
    s4 = _create_student(db_session, teacher.id, "Student Excused", "01022220004")

    for s in (s1, s2, s3, s4):
        _enroll_student(db_session, teacher.id, group.id, s.id)

    headers = _login(client, "session_fee_teacher", "Pass12345!")

    # Set per-session fee: 75.00 EGP
    client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "per_session",
        "amount_egp": 75.0,
        "effective_from": "2026-10-01"
    })

    # Create completed session
    sess = ClassSession(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        group_id=group.id,
        session_date="2026-10-15",
        start_time="16:00",
        status="completed",
        notes="Calculus Introduction"
    )
    db_session.add(sess)
    db_session.commit()

    # Record attendance: s1 present, s2 late, s3 absent, s4 excused
    att_records = [
        Attendance(id=str(uuid.uuid4()), teacher_id=teacher.id, session_id=sess.id, student_id=s1.id, status="present"),
        Attendance(id=str(uuid.uuid4()), teacher_id=teacher.id, session_id=sess.id, student_id=s2.id, status="late"),
        Attendance(id=str(uuid.uuid4()), teacher_id=teacher.id, session_id=sess.id, student_id=s3.id, status="absent"),
        Attendance(id=str(uuid.uuid4()), teacher_id=teacher.id, session_id=sess.id, student_id=s4.id, status="excused"),
    ]
    db_session.add_all(att_records)
    db_session.commit()

    # 1. Preview session dues (GET)
    resp_prev = client.get(f"/api/finance/dues/session/{sess.id}/preview", headers=headers)
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert prev_data["attended_students_count"] == 2  # Only present and late
    assert prev_data["already_generated_count"] == 0
    assert prev_data["to_be_generated_count"] == 2
    assert prev_data["total_amount_egp"] == 150.0  # 2 * 75

    # 2. Generate session dues
    resp_gen = client.post("/api/finance/dues/session/generate", headers=headers, json={
        "session_id": sess.id,
        "due_date": "2026-10-15"
    })
    assert resp_gen.status_code in (200, 201)
    gen_data = resp_gen.json()
    assert gen_data["generated_count"] == 2
    assert gen_data["total_amount_egp"] == 150.0

    # 3. Idempotency test: Re-generate produces 0
    resp_gen2 = client.post("/api/finance/dues/session/generate", headers=headers, json={
        "session_id": sess.id,
        "due_date": "2026-10-15"
    })
    assert resp_gen2.status_code in (200, 201)
    assert resp_gen2.json()["generated_count"] == 0


# ==============================================================================
# 4. Cash Payments, Multi-Due Allocation & Overpayment Protection
# ==============================================================================

def test_cash_payment_multi_due_allocations_and_guards(client, db_session):
    teacher = _create_teacher(db_session, "pay_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Group Payment")
    student = _create_student(db_session, teacher.id, "Mahmoud Hassan", "01033330001")
    other_student = _create_student(db_session, teacher.id, "Other Student", "01033330002")

    _enroll_student(db_session, teacher.id, group.id, student.id)
    _enroll_student(db_session, teacher.id, group.id, other_student.id)

    headers = _login(client, "pay_teacher", "Pass12345!")

    # Create two dues for student: due1 = 200 EGP, due2 = 100 EGP
    due1 = StudentDue(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        student_id=student.id,
        group_id=group.id,
        charge_type="monthly_fee",
        billing_month="2026-09",
        amount=20000,
        paid_amount=0,
        status="unpaid",
        due_date="2026-09-10"
    )
    due2 = StudentDue(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        student_id=student.id,
        group_id=group.id,
        charge_type="monthly_fee",
        billing_month="2026-10",
        amount=10000,
        paid_amount=0,
        status="unpaid",
        due_date="2026-10-10"
    )
    # Due for other student: 150 EGP
    due_other = StudentDue(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        student_id=other_student.id,
        group_id=group.id,
        charge_type="monthly_fee",
        billing_month="2026-10",
        amount=15000,
        paid_amount=0,
        status="unpaid",
        due_date="2026-10-10"
    )
    db_session.add_all([due1, due2, due_other])
    db_session.commit()

    # Guard 1: Cross-student due allocation rejected
    resp_cross = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 300.0,
        "payment_date": "2026-10-20",
        "allocations": [
            {"due_id": due_other.id, "amount_egp": 150.0}
        ]
    })
    assert resp_cross.status_code in (400, 422)

    # Guard 2: Overpayment on a single due rejected (allocating 250 on a 200 due)
    resp_over = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 300.0,
        "payment_date": "2026-10-20",
        "allocations": [
            {"due_id": due1.id, "amount_egp": 250.0}
        ]
    })
    assert resp_over.status_code in (400, 422)

    # Guard 3: Total allocations exceed total payment amount rejected
    resp_exceed = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 200.0,
        "payment_date": "2026-10-20",
        "allocations": [
            {"due_id": due1.id, "amount_egp": 150.0},
            {"due_id": due2.id, "amount_egp": 100.0}  # total alloc = 250 > 200
        ]
    })
    assert resp_exceed.status_code in (400, 422)

    # Valid Payment: Pay 250 EGP, allocate 200 EGP to due1 (full payment) and 50 EGP to due2 (partial payment)
    resp_pay = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 250.0,
        "payment_date": "2026-10-20",
        "notes": "Paid at center reception",
        "allocations": [
            {"due_id": due1.id, "amount_egp": 200.0},
            {"due_id": due2.id, "amount_egp": 50.0}
        ]
    })
    assert resp_pay.status_code == 201
    pay_data = resp_pay.json()
    assert pay_data["amount_piastres"] == 25000
    assert pay_data["amount_egp"] == 250.0
    assert pay_data["allocated_amount_egp"] == 250.0
    assert pay_data["receipt_number"].startswith("RCP-")
    assert len(pay_data["allocations"]) == 2

    # Verify Dues Status in DB
    db_session.refresh(due1)
    db_session.refresh(due2)
    assert due1.paid_amount == 20000
    assert due1.status == "paid"
    assert due2.paid_amount == 5000
    assert due2.status == "partially_paid"
    assert due2.remaining_balance == 5000


# ==============================================================================
# 5. Payment Reversals and Due Voiding
# ==============================================================================

def test_payment_reversal_and_void_due(client, db_session):
    teacher = _create_teacher(db_session, "rev_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Group Rev")
    student = _create_student(db_session, teacher.id, "Tarek Ziad", "01044440001")
    _enroll_student(db_session, teacher.id, group.id, student.id)
    headers = _login(client, "rev_teacher", "Pass12345!")

    # Create due: 300 EGP
    due = StudentDue(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        student_id=student.id,
        group_id=group.id,
        charge_type="monthly_fee",
        billing_month="2026-10",
        amount=30000,
        paid_amount=0,
        status="unpaid",
        due_date="2026-10-10"
    )
    db_session.add(due)
    db_session.commit()

    # Pay 300 EGP allocating full due
    resp_pay = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 300.0,
        "payment_date": "2026-10-12",
        "allocations": [{"due_id": due.id, "amount_egp": 300.0}]
    })
    assert resp_pay.status_code == 201
    payment_id = resp_pay.json()["id"]

    db_session.refresh(due)
    assert due.status == "paid"
    assert due.paid_amount == 30000

    # Voiding a paid due must fail
    resp_void_fail = client.post(f"/api/finance/dues/{due.id}/void", headers=headers, json={
        "reason": "Trying to void paid due"
    })
    assert resp_void_fail.status_code == 400

    # Reverse the payment
    resp_rev = client.post(f"/api/finance/payments/{payment_id}/reverse", headers=headers, json={
        "reason": "Refund requested by parent"
    })
    assert resp_rev.status_code == 200
    rev_data = resp_rev.json()
    assert rev_data["is_reversed"] is True
    assert rev_data["reversal_reason"] == "Refund requested by parent"

    # Verify due returned back to unpaid with paid_amount = 0
    db_session.refresh(due)
    assert due.status == "unpaid"
    assert due.paid_amount == 0

    # Reversing an already reversed payment must fail
    resp_rev_again = client.post(f"/api/finance/payments/{payment_id}/reverse", headers=headers, json={
        "reason": "Reversing twice"
    })
    assert resp_rev_again.status_code == 400

    # Now void the due since it is unpaid
    resp_void = client.post(f"/api/finance/dues/{due.id}/void", headers=headers, json={
        "reason": "Student transferred to another center"
    })
    assert resp_void.status_code == 200
    assert resp_void.json()["status"] == "void"
    assert resp_void.json()["void_reason"] == "Student transferred to another center"

    # Verify financial audit log recorded both events
    logs = db_session.query(FinancialAuditLog).filter_by(teacher_id=teacher.id).all()
    actions = [log.action for log in logs]
    assert "payment_reversed" in actions
    assert "due_voided" in actions


# ==============================================================================
# 6. Student Financial Profile, Group Summary & Reports
# ==============================================================================

def test_student_financial_profile_and_collection_reports(client, db_session):
    teacher = _create_teacher(db_session, "rep_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Reports Group")
    s1 = _create_student(db_session, teacher.id, "Student Alpha", "01055550001")
    s2 = _create_student(db_session, teacher.id, "Student Beta", "01055550002")

    _enroll_student(db_session, teacher.id, group.id, s1.id)
    _enroll_student(db_session, teacher.id, group.id, s2.id)

    headers = _login(client, "rep_teacher", "Pass12345!")

    # Student 1 has 300 EGP due, pays 200 EGP -> balance 100 EGP
    due_s1 = StudentDue(
        id=str(uuid.uuid4()), teacher_id=teacher.id, student_id=s1.id, group_id=group.id,
        charge_type="monthly_fee", billing_month="2026-10", amount=30000, paid_amount=0,
        status="unpaid", due_date="2026-10-10"
    )
    # Student 2 has 300 EGP due, pays 300 EGP -> balance 0 EGP
    due_s2 = StudentDue(
        id=str(uuid.uuid4()), teacher_id=teacher.id, student_id=s2.id, group_id=group.id,
        charge_type="monthly_fee", billing_month="2026-10", amount=30000, paid_amount=0,
        status="unpaid", due_date="2026-10-10"
    )
    db_session.add_all([due_s1, due_s2])
    db_session.commit()

    # Record payments
    client.post("/api/finance/payments", headers=headers, json={
        "student_id": s1.id,
        "amount_egp": 200.0,
        "payment_date": "2026-10-12",
        "allocations": [{"due_id": due_s1.id, "amount_egp": 200.0}]
    })
    client.post("/api/finance/payments", headers=headers, json={
        "student_id": s2.id,
        "amount_egp": 300.0,
        "payment_date": "2026-10-12",
        "allocations": [{"due_id": due_s2.id, "amount_egp": 300.0}]
    })

    # 1. Student 1 Ledger
    resp_prof = client.get(f"/api/finance/reports/student/{s1.id}", headers=headers)
    assert resp_prof.status_code == 200
    prof1 = resp_prof.json()
    assert prof1["total_dues_egp"] == 300.0
    assert prof1["total_paid_egp"] == 200.0
    assert prof1["current_balance_egp"] == 100.0
    assert len(prof1["dues"]) == 1
    assert len(prof1["payments"]) == 1

    # 2. Group Summary: total billed = 600, collected = 500, outstanding = 100, rate = 83.3%
    resp_grp = client.get(f"/api/finance/reports/group/{group.id}", headers=headers)
    assert resp_grp.status_code == 200
    grp_data = resp_grp.json()
    assert grp_data["total_billed_egp"] == 600.0
    assert grp_data["total_collected_egp"] == 500.0
    assert grp_data["total_outstanding_egp"] == 100.0
    assert round(grp_data["collection_rate_percent"], 1) == 83.3
    assert grp_data["total_students_enrolled"] == 2

    # 3. Monthly Collection Report
    resp_month = client.get("/api/finance/reports/monthly/2026-10", headers=headers)
    assert resp_month.status_code == 200
    m_data = resp_month.json()
    assert m_data["total_monthly_dues_egp"] == 600.0
    assert m_data["total_collected_egp"] == 500.0
    assert m_data["total_outstanding_egp"] == 100.0

    # 4. Cash Collection Report
    resp_cash = client.get("/api/finance/reports/cash?start_date=2026-10-01&end_date=2026-10-31", headers=headers)
    assert resp_cash.status_code == 200
    c_data = resp_cash.json()
    assert c_data["total_collected_egp"] == 500.0
    assert c_data["total_reversed_egp"] == 0.0
    assert c_data["net_collected_egp"] == 500.0
    assert c_data["payments_count"] == 2


# ==============================================================================
# 7. Assistant Permissions & RBAC
# ==============================================================================

def test_assistant_finance_permissions(client, db_session):
    teacher = _create_teacher(db_session, "rbac_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "RBAC Group")
    student = _create_student(db_session, teacher.id, "RBAC Student", "01066660001")
    _enroll_student(db_session, teacher.id, group.id, student.id)

    # Assistant 1: can_collect_cash ONLY
    ass_cash = Assistant(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        username="ass_cashier",
        full_name="Cashier Assistant",
        phone="01077770001",
        hashed_password=hash_password("Pass12345!"),
        can_collect_cash=True,
        can_manage_fees=False,
        is_active=True
    )
    # Assistant 2: can_manage_fees ONLY
    ass_mgr = Assistant(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        username="ass_manager",
        full_name="Fee Manager Assistant",
        phone="01077770002",
        hashed_password=hash_password("Pass12345!"),
        can_collect_cash=False,
        can_manage_fees=True,
        is_active=True
    )
    # Assistant 3: NO finance permissions (attendance only)
    ass_none = Assistant(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        username="ass_attendance",
        full_name="Attendance Assistant",
        phone="01077770003",
        hashed_password=hash_password("Pass12345!"),
        can_mark_attendance=True,
        can_collect_cash=False,
        can_manage_fees=False,
        is_active=True
    )
    db_session.add_all([ass_cash, ass_mgr, ass_none])
    db_session.commit()

    headers_cash = _login(client, "ass_cashier", "Pass12345!")
    headers_mgr = _login(client, "ass_manager", "Pass12345!")
    headers_none = _login(client, "ass_attendance", "Pass12345!")

    # Test 1: ass_none gets 403 on overview and dues
    resp_denied = client.get("/api/finance/overview", headers=headers_none)
    assert resp_denied.status_code == 403

    resp_denied_dues = client.get("/api/finance/dues", headers=headers_none)
    assert resp_denied_dues.status_code == 403

    # Test 2: ass_mgr CAN set fee configs, but ass_cash CANNOT
    resp_cfg_mgr = client.post("/api/finance/fees", headers=headers_mgr, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": 300.0,
        "effective_from": "2026-10-01"
    })
    assert resp_cfg_mgr.status_code == 201

    resp_cfg_cash = client.post("/api/finance/fees", headers=headers_cash, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": 350.0,
        "effective_from": "2026-10-01"
    })
    assert resp_cfg_cash.status_code == 403

    # Test 3: ass_cash CAN record payments, but ass_mgr CANNOT
    resp_pay_cash = client.post("/api/finance/payments", headers=headers_cash, json={
        "student_id": student.id,
        "amount_egp": 150.0,
        "payment_date": "2026-10-20"
    })
    assert resp_pay_cash.status_code == 201

    resp_pay_mgr = client.post("/api/finance/payments", headers=headers_mgr, json={
        "student_id": student.id,
        "amount_egp": 150.0,
        "payment_date": "2026-10-20"
    })
    assert resp_pay_mgr.status_code == 403


# ==============================================================================
# 8. Tenant Isolation
# ==============================================================================

def test_finance_tenant_isolation(client, db_session):
    teacher1 = _create_teacher(db_session, "tenant_t1", "Pass12345!")
    teacher2 = _create_teacher(db_session, "tenant_t2", "Pass12345!")

    group1 = _create_group(db_session, teacher1.id, "T1 Group")
    student1 = _create_student(db_session, teacher1.id, "T1 Student", "01099991111")
    _enroll_student(db_session, teacher1.id, group1.id, student1.id)

    headers1 = _login(client, "tenant_t1", "Pass12345!")
    headers2 = _login(client, "tenant_t2", "Pass12345!")

    # T1 creates a fee config and a due
    resp_cfg = client.post("/api/finance/fees", headers=headers1, json={
        "group_id": group1.id,
        "fee_model": "monthly",
        "amount_egp": 200.0,
        "effective_from": "2026-10-01"
    })
    assert resp_cfg.status_code == 201

    due1 = StudentDue(
        id=str(uuid.uuid4()), teacher_id=teacher1.id, student_id=student1.id, group_id=group1.id,
        charge_type="monthly_fee", billing_month="2026-10", amount=20000, paid_amount=0,
        status="unpaid", due_date="2026-10-10"
    )
    db_session.add(due1)
    db_session.commit()

    # T1 records a payment
    resp_pay = client.post("/api/finance/payments", headers=headers1, json={
        "student_id": student1.id,
        "amount_egp": 200.0,
        "payment_date": "2026-10-15",
        "allocations": [{"due_id": due1.id, "amount_egp": 200.0}]
    })
    payment_id = resp_pay.json()["id"]

    # Teacher 2 attempts:
    # 1. Create fee config for T1's group -> 400/404 (group not in T2's workspace)
    resp_t2_cfg = client.post("/api/finance/fees", headers=headers2, json={
        "group_id": group1.id,
        "fee_model": "monthly",
        "amount_egp": 500.0,
        "effective_from": "2026-10-01"
    })
    assert resp_t2_cfg.status_code in (400, 404)

    # 2. Void T1's due -> 404
    resp_t2_void = client.post(f"/api/finance/dues/{due1.id}/void", headers=headers2, json={
        "reason": "Malicious attempt"
    })
    assert resp_t2_void.status_code == 404

    # 3. View T1's payment details -> 404
    resp_t2_pay = client.get(f"/api/finance/payments/{payment_id}", headers=headers2)
    assert resp_t2_pay.status_code == 404

    # 4. Reverse T1's payment -> 404
    resp_t2_rev = client.post(f"/api/finance/payments/{payment_id}/reverse", headers=headers2, json={
        "reason": "Malicious reverse"
    })
    assert resp_t2_rev.status_code == 404

    # 5. View T1's student financial profile -> 404
    resp_t2_prof = client.get(f"/api/finance/reports/student/{student1.id}", headers=headers2)
    assert resp_t2_prof.status_code == 404


# ==============================================================================
# 9. Additional Focused Financial Edge Cases
# ==============================================================================

def test_sequential_partial_payments_accumulating_on_same_due(client, db_session):
    """Verify that multiple partial payments incrementally pay off the same due."""
    teacher = _create_teacher(db_session, "multi_pay_t", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Multi Pay Group")
    student = _create_student(db_session, teacher.id, "Incremental Student", "01011112222")
    _enroll_student(db_session, teacher.id, group.id, student.id)
    headers = _login(client, "multi_pay_t", "Pass12345!")

    due = StudentDue(
        id=str(uuid.uuid4()), teacher_id=teacher.id, student_id=student.id, group_id=group.id,
        charge_type="monthly_fee", billing_month="2026-10", amount=30000, paid_amount=0,
        status="unpaid", due_date="2026-10-10"
    )
    db_session.add(due)
    db_session.commit()

    # Payment 1: 100 EGP
    resp_pay1 = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 100.0,
        "payment_date": "2026-10-12",
        "allocations": [{"due_id": due.id, "amount_egp": 100.0}]
    })
    assert resp_pay1.status_code == 201
    pay1_data = resp_pay1.json()
    assert pay1_data["formatted_amount"] == "100.00 ج.م"
    assert pay1_data["created_by_name"] == "المعلم"

    # Verify due is now partially_paid with 100 EGP paid, 200 EGP remaining
    due_check1 = client.get(f"/api/finance/dues?student_id={student.id}", headers=headers).json()[0]
    assert due_check1["status"] == "partially_paid"
    assert due_check1["paid_amount_egp"] == 100.0
    assert due_check1["remaining_balance_egp"] == 200.0

    # Payment 2: 200 EGP (completing the due)
    resp_pay2 = client.post("/api/finance/payments", headers=headers, json={
        "student_id": student.id,
        "amount_egp": 200.0,
        "payment_date": "2026-10-15",
        "allocations": [{"due_id": due.id, "amount_egp": 200.0}]
    })
    assert resp_pay2.status_code == 201
    pay2_data = resp_pay2.json()
    assert pay2_data["formatted_amount"] == "200.00 ج.م"
    assert pay2_data["created_by_name"] == "المعلم"

    # Verify due is now fully paid with 300 EGP paid, 0 EGP remaining
    due_check2 = client.get(f"/api/finance/dues?student_id={student.id}", headers=headers).json()[0]
    assert due_check2["status"] == "paid"
    assert due_check2["paid_amount_egp"] == 300.0
    assert due_check2["remaining_balance_egp"] == 0.0


def test_subsequent_month_enrollment_excluded_from_prior_month_dues(client, db_session):
    """Students enrolling in Month M+1 must be excluded from Month M dues preview and generation."""
    teacher = _create_teacher(db_session, "mid_month_t", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Mid-Month Group")
    st_oct = _create_student(db_session, teacher.id, "October Student", "01033331111")
    st_nov = _create_student(db_session, teacher.id, "November Student", "01033332222")

    # Enroll October student with joined_at in October
    enr_oct = GroupStudent(
        id=str(uuid.uuid4()), teacher_id=teacher.id, group_id=group.id, student_id=st_oct.id,
        is_active=True, joined_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    )
    # Enroll November student with joined_at in November
    enr_nov = GroupStudent(
        id=str(uuid.uuid4()), teacher_id=teacher.id, group_id=group.id, student_id=st_nov.id,
        is_active=True, joined_at=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    )
    db_session.add_all([enr_oct, enr_nov])
    db_session.commit()

    headers = _login(client, "mid_month_t", "Pass12345!")

    # Set monthly fee
    client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "monthly",
        "amount_egp": 250.0,
        "effective_from": "2026-10-01"
    })

    # Preview October (2026-10)
    prev_resp = client.post("/api/finance/dues/monthly/preview", headers=headers, json={
        "group_id": group.id,
        "billing_month": "2026-10"
    })
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert prev_data["total_enrolled_eligible"] == 1
    assert prev_data["students"][0]["student_id"] == st_oct.id
    assert prev_data["newly_billable_count"] == 1

    # Generate October dues
    gen_resp = client.post("/api/finance/dues/monthly/generate", headers=headers, json={
        "group_id": group.id,
        "billing_month": "2026-10"
    })
    assert gen_resp.status_code == 200
    assert gen_resp.json()["generated_count"] == 1

    # Verify only October student has a due
    oct_dues = client.get(f"/api/finance/dues?group_id={group.id}&billing_month=2026-10", headers=headers).json()
    assert len(oct_dues) == 1
    assert oct_dues[0]["student_id"] == st_oct.id


def test_cancelled_session_cannot_generate_charges(client, db_session):
    """Verify that cancelled sessions cannot generate session fees."""
    teacher = _create_teacher(db_session, "cancel_sess_t", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Cancel Sess Group")
    student = _create_student(db_session, teacher.id, "Attending Student", "01044445555")
    _enroll_student(db_session, teacher.id, group.id, student.id)
    headers = _login(client, "cancel_sess_t", "Pass12345!")

    # Configure per-session fee
    client.post("/api/finance/fees", headers=headers, json={
        "group_id": group.id,
        "fee_model": "per_session",
        "amount_egp": 80.0,
        "effective_from": "2026-10-01"
    })

    # Create a session and mark it cancelled
    session = ClassSession(
        id=str(uuid.uuid4()), teacher_id=teacher.id, group_id=group.id,
        session_date="2026-10-18", start_time="14:00", end_time="16:00",
        status="cancelled"
    )
    db_session.add(session)
    db_session.commit()

    # Preview must indicate session is not eligible
    prev_resp = client.get(f"/api/finance/dues/session/{session.id}/preview", headers=headers)
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert prev_data["is_eligible_session"] is False
    assert "لم تكتمل" in prev_data["ineligibility_reason"]

    # Generate must fail with 400 Bad Request
    gen_resp = client.post("/api/finance/dues/session/generate", headers=headers, json={
        "session_id": session.id
    })
    assert gen_resp.status_code == 400


def test_assistant_reversal_permission_denial(client, db_session):
    """Assistants (even with can_collect_cash) must be blocked from reversing payments."""
    teacher = _create_teacher(db_session, "rev_perm_teacher", "Pass12345!")
    group = _create_group(db_session, teacher.id, "Rev Perm Group")
    student = _create_student(db_session, teacher.id, "Rev Student", "01088889999")
    _enroll_student(db_session, teacher.id, group.id, student.id)

    # Assistant with can_collect_cash = True
    assistant = Assistant(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        username="ass_cashier_rev",
        full_name="Cashier Assistant",
        phone="01088880001",
        hashed_password=hash_password("Pass12345!"),
        can_collect_cash=True,
        can_manage_fees=False,
        is_active=True
    )
    db_session.add(assistant)
    db_session.commit()

    headers_teacher = _login(client, "rev_perm_teacher", "Pass12345!")
    headers_assistant = _login(client, "ass_cashier_rev", "Pass12345!")

    # Assistant records a payment
    resp_pay = client.post("/api/finance/payments", headers=headers_assistant, json={
        "student_id": student.id,
        "amount_egp": 120.0,
        "payment_date": "2026-10-22"
    })
    assert resp_pay.status_code == 201
    payment_id = resp_pay.json()["id"]
    assert resp_pay.json()["created_by_name"] == "المساعد"
    assert resp_pay.json()["formatted_amount"] == "120.00 ج.م"

    # Assistant attempts to reverse the payment -> 403 Forbidden
    resp_ass_rev = client.post(f"/api/finance/payments/{payment_id}/reverse", headers=headers_assistant, json={
        "reason": "Assistant attempting reversal"
    })
    assert resp_ass_rev.status_code == 403

    # Teacher reverses the payment -> 200 OK
    resp_t_rev = client.post(f"/api/finance/payments/{payment_id}/reverse", headers=headers_teacher, json={
        "reason": "Teacher authorized reversal"
    })
    assert resp_t_rev.status_code == 200
    assert resp_t_rev.json()["is_reversed"] is True


