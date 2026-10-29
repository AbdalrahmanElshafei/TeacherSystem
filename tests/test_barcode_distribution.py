import io
import datetime
import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.main import app
from app.repositories.user_repo import UserRepository
from app.repositories.academic_repo import AcademicRepository
from app.services.barcode_service import BarcodeService
from app.schemas.academic import StudentCreate, GroupCreate
from app.config import CSRF_HEADER_NAME

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
    assert resp.status_code == 200
    data = resp.json()
    return {
        "Authorization": f"Bearer {data['session_token']}",
        CSRF_HEADER_NAME: data["csrf_token"]
    }


def _setup_teacher(db, username="teacher_dist", phone="01011112222"):
    return UserRepository.create_teacher(
        db,
        username=username,
        full_name=f"أستاذ {username}",
        phone=phone,
        password="StrongPassword123!"
    )


# --------------------------------------------------------------------------
# Test 1: Scanner compatibility — verify barcode payload matches Student.id
# and passes AttendanceRepository.scan_barcode
# --------------------------------------------------------------------------
def test_scanner_compatibility_student_id_matches_scan_barcode(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_scan")
    headers = _login(client, "teacher_scan", "StrongPassword123!")

    # Create group and student
    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة التفوق", grade_level="1_sec", subject="رياضيات")
    )
    student = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="زياد أحمد علي", grade_level="1_sec", phone="01099998888")
    )
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, student.id)

    # 1. Fetch barcode card data
    card_resp = client.get(f"/api/barcodes/students/{student.id}/card", headers=headers)
    assert card_resp.status_code == 200
    card_data = card_resp.json()

    # Barcode payload MUST be identical to student.id
    assert card_data["barcode_value"] == student.id
    assert card_data["student_id"] == student.id
    assert card_data["full_name"] == "زياد أحمد علي"
    assert "<svg" in card_data["barcode_svg"]

    # 2. Verify Attendance scan compatibility
    session_resp = client.post("/api/sessions", json={
        "group_id": group.id,
        "session_date": "2026-11-01",
        "start_time": "15:00",
        "end_time": "17:00",
        "status": "scheduled"
    }, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    scan_resp = client.post(f"/api/sessions/{session_id}/scan", json={
        "barcode": card_data["barcode_value"]
    }, headers=headers)
    assert scan_resp.status_code == 200
    scan_result = scan_resp.json()
    assert scan_result["success"] is True
    assert scan_result["status"] == "present"
    assert scan_result["student"]["full_name"] == "زياد أحمد علي"


# --------------------------------------------------------------------------
# Test 2: Barcode stability across repeated calls
# --------------------------------------------------------------------------
def test_barcode_stability_across_repeated_calls(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_stab")
    headers = _login(client, "teacher_stab", "StrongPassword123!")

    student = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="محمود سامي", grade_level="2_sec", phone="01122334455")
    )

    # Repeated calls must return exact same barcode
    resp1 = client.get(f"/api/barcodes/students/{student.id}/card", headers=headers)
    resp2 = client.get(f"/api/barcodes/students/{student.id}/card", headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["barcode_value"] == resp2.json()["barcode_value"] == student.id


# --------------------------------------------------------------------------
# Test 3: Single-student PDF export
# --------------------------------------------------------------------------
def test_single_student_pdf_export(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_pdf_single")
    headers = _login(client, "teacher_pdf_single", "StrongPassword123!")

    student = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="منى حسام", grade_level="3_sec", phone="01233445566")
    )

    # Export PDF
    pdf_resp = client.get(f"/api/barcodes/students/{student.id}/card.pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_resp.headers.get("content-disposition", "")
    assert pdf_resp.content.startswith(b"%PDF")

    # Check status advanced to 'generated'
    status_resp = client.get(f"/api/barcodes/students/{student.id}/card", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["distribution_status"] == "generated"


# --------------------------------------------------------------------------
# Test 4: Group PDF export — multi-card generation, cutting guidelines & logging
# --------------------------------------------------------------------------
def test_group_pdf_export_multicard_and_logging(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_pdf_grp")
    headers = _login(client, "teacher_pdf_grp", "StrongPassword123!")

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة الكيمياء", grade_level="1_sec", subject="كيمياء")
    )
    for i in range(3):
        s = AcademicRepository.create_student(
            db_session, teacher.id, StudentCreate(full_name=f"طالب رقم {i+1}", grade_level="1_sec", phone=f"010000000{i}")
        )
        AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s.id)

    # Export Group PDF
    export_resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=headers)
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/pdf"
    assert export_resp.content.startswith(b"%PDF")
    assert "attachment" in export_resp.headers.get("content-disposition", "")

    # Check distribution overview: all 3 students are now 'generated'
    overview_resp = client.get(f"/api/barcodes/distribution/groups/{group.id}", headers=headers)
    assert overview_resp.status_code == 200
    ov_data = overview_resp.json()
    assert ov_data["total_students"] == 3
    assert ov_data["pending_count"] == 3  # not confirmed_sent yet
    assert ov_data["last_exported_at"] is not None
    assert all(st["distribution_status"] == "generated" for st in ov_data["students"])


# --------------------------------------------------------------------------
# Test 5: Empty group export — returns valid PDF without crashing
# --------------------------------------------------------------------------
def test_empty_group_pdf_export(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_empty")
    headers = _login(client, "teacher_empty", "StrongPassword123!")

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة فارغة", grade_level="2_sec", subject="فيزياء")
    )

    resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


# --------------------------------------------------------------------------
# Test 6: Large group export (multi-page pagination across > 8 cards)
# --------------------------------------------------------------------------
def test_large_group_pdf_pagination(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_large")
    headers = _login(client, "teacher_large", "StrongPassword123!")

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة كبيرة 10 طلاب", grade_level="3_sec", subject="أحياء")
    )
    for i in range(10):
        s = AcademicRepository.create_student(
            db_session, teacher.id, StudentCreate(full_name=f"طالب متفوق {i+1}", grade_level="3_sec", phone=f"015000000{i:02d}")
        )
        AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s.id)

    resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    # Verify PDF size is substantial enough for 2 pages
    assert len(resp.content) > 5000


# --------------------------------------------------------------------------
# Test 7: Identification of new students enrolled after latest export
# --------------------------------------------------------------------------
def test_identification_of_new_students_after_export(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_new_stud")
    headers = _login(client, "teacher_new_stud", "StrongPassword123!")

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة التعقب", grade_level="1_sec", subject="لغة عربية")
    )
    s1 = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب قديم 1", grade_level="1_sec", phone="01011110001")
    )
    s2 = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب قديم 2", grade_level="1_sec", phone="01011110002")
    )
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s1.id)
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s2.id)

    # Export group PDF
    export_resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=headers)
    assert export_resp.status_code == 200

    # Enroll a new student after export with a future joined_at timestamp to guarantee strictly newer
    s3 = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب حديث الانضمام", grade_level="1_sec", phone="01011110003")
    )
    enrollment, _ = AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s3.id)
    # Ensure joined_at is strictly in the future of exported_at
    enrollment.joined_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
    db_session.commit()

    # Check overview
    ov_resp = client.get(f"/api/barcodes/distribution/groups/{group.id}", headers=headers)
    assert ov_resp.status_code == 200
    data = ov_resp.json()

    assert data["total_students"] == 3
    # Check flags for each student
    students_map = {item["student_id"]: item for item in data["students"]}
    assert students_map[s1.id]["is_new_since_last_export"] is False
    assert students_map[s2.id]["is_new_since_last_export"] is False
    assert students_map[s3.id]["is_new_since_last_export"] is True
    assert data["new_since_export_count"] == 1


# --------------------------------------------------------------------------
# Test 8: Multi-group student has consistent barcode & group-specific tracking
# --------------------------------------------------------------------------
def test_multi_group_student_distribution(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_multigrp")
    headers = _login(client, "teacher_multigrp", "StrongPassword123!")

    grp1 = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة أ", grade_level="2_sec", subject="جبر")
    )
    grp2 = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة ب", grade_level="2_sec", subject="هندسة")
    )

    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب مشترك", grade_level="2_sec", phone="01055556666")
    )
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, grp1.id, s.id)
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, grp2.id, s.id)

    # Card barcode is identical
    card = client.get(f"/api/barcodes/students/{s.id}/card", headers=headers).json()
    assert card["barcode_value"] == s.id

    # Present in both group overviews
    ov1 = client.get(f"/api/barcodes/distribution/groups/{grp1.id}", headers=headers).json()
    ov2 = client.get(f"/api/barcodes/distribution/groups/{grp2.id}", headers=headers).json()
    assert any(item["student_id"] == s.id for item in ov1["students"])
    assert any(item["student_id"] == s.id for item in ov2["students"])


# --------------------------------------------------------------------------
# Test 9: Export does not falsely mark as confirmed sent
# --------------------------------------------------------------------------
def test_export_does_not_falsely_mark_confirmed_sent(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_not_false")
    headers = _login(client, "teacher_not_false", "StrongPassword123!")

    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="أنس كمال", grade_level="1_sec", phone="01077778888")
    )

    # Single export
    client.get(f"/api/barcodes/students/{s.id}/card.pdf", headers=headers)
    card = client.get(f"/api/barcodes/students/{s.id}/card", headers=headers).json()
    assert card["distribution_status"] == "generated"
    assert card["distribution_status"] != "confirmed_sent"

    # Share opened
    client.post(f"/api/barcodes/distribution/students/{s.id}/status", json={
        "status": "share_opened"
    }, headers=headers)
    card = client.get(f"/api/barcodes/students/{s.id}/card", headers=headers).json()
    assert card["distribution_status"] == "share_opened"
    assert card["distribution_status"] != "confirmed_sent"


# --------------------------------------------------------------------------
# Test 10: Status transition lifecycle (not_sent -> share_opened -> confirmed_sent -> not_sent)
# --------------------------------------------------------------------------
def test_status_transition_lifecycle(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_lifecycle")
    headers = _login(client, "teacher_lifecycle", "StrongPassword123!")

    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="كريم وليد", grade_level="1_sec", phone="01088889999")
    )

    # Initial: not_sent
    card = client.get(f"/api/barcodes/students/{s.id}/card", headers=headers).json()
    assert card["distribution_status"] == "not_sent"

    # Step 1: share_opened
    st1 = client.post(f"/api/barcodes/distribution/students/{s.id}/status", json={
        "status": "share_opened",
        "notes": "تم فتح مشاركة واتساب"
    }, headers=headers)
    assert st1.status_code == 200
    assert st1.json()["status"] == "share_opened"

    # Step 2: confirmed_sent
    st2 = client.post(f"/api/barcodes/distribution/students/{s.id}/status", json={
        "status": "confirmed_sent",
        "notes": "أكد ولي الأمر الاستلام"
    }, headers=headers)
    assert st2.status_code == 200
    assert st2.json()["status"] == "confirmed_sent"
    assert st2.json()["confirmed_by_name"] == teacher.full_name
    assert st2.json()["confirmed_sent_at"] is not None

    # Step 3: reset to not_sent
    st3 = client.post(f"/api/barcodes/distribution/students/{s.id}/status", json={
        "status": "not_sent"
    }, headers=headers)
    assert st3.status_code == 200
    assert st3.json()["status"] == "not_sent"
    assert st3.json()["confirmed_sent_at"] is None


# --------------------------------------------------------------------------
# Test 11: Teacher & Assistant RBAC permissions
# --------------------------------------------------------------------------
def test_rbac_permissions_teacher_and_assistant(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_rbac")

    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب الصلاحيات", grade_level="1_sec", phone="01011114444")
    )

    # 1. Unauthenticated request: 401
    client.cookies.clear()
    unauth_resp = client.get(f"/api/barcodes/students/{s.id}/card")
    assert unauth_resp.status_code == 401

    # 2. Assistant with can_manage_students: 200 OK
    asst_manage = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="asst_manage",
        full_name="مساعد إدارة الطلاب",
        phone="01011115555",
        password="StrongPassword123!",
        permissions={"can_manage_students": True, "can_view_attendance": False, "can_mark_attendance": False}
    )
    manage_headers = _login(client, "asst_manage", "StrongPassword123!")
    resp_m = client.get(f"/api/barcodes/students/{s.id}/card", headers=manage_headers)
    assert resp_m.status_code == 200

    # 3. Assistant with can_view_attendance: 200 OK
    client.cookies.clear()
    asst_att = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="asst_att",
        full_name="مساعد الحضور",
        phone="01011116666",
        password="StrongPassword123!",
        permissions={"can_manage_students": False, "can_view_attendance": True, "can_mark_attendance": False}
    )
    att_headers = _login(client, "asst_att", "StrongPassword123!")
    resp_a = client.get(f"/api/barcodes/students/{s.id}/card", headers=att_headers)
    assert resp_a.status_code == 200

    # 4. Assistant with ONLY finance permissions (NO student/attendance access): 403 Forbidden
    client.cookies.clear()
    asst_fin = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="asst_fin_only",
        full_name="مساعد الحسابات فقط",
        phone="01011117777",
        password="StrongPassword123!",
        permissions={
            "can_manage_students": False,
            "can_view_attendance": False,
            "can_mark_attendance": False,
            "can_collect_cash": True,
            "can_view_student_payment_history": True
        }
    )
    fin_headers = _login(client, "asst_fin_only", "StrongPassword123!")
    resp_f = client.get(f"/api/barcodes/students/{s.id}/card", headers=fin_headers)
    assert resp_f.status_code == 403
    assert "صلاحية مرفوضة" in resp_f.json()["detail"]


# --------------------------------------------------------------------------
# Test 12: Tenant isolation — Teacher B cannot export or view Teacher A's students
# --------------------------------------------------------------------------
def test_tenant_isolation_teacher_separation(client, db_session):
    teacher_a = _setup_teacher(db_session, "teacher_iso_a", phone="01011118888")
    teacher_b = _setup_teacher(db_session, "teacher_iso_b", phone="01011119999")

    headers_a = _login(client, "teacher_iso_a", "StrongPassword123!")
    headers_b = _login(client, "teacher_iso_b", "StrongPassword123!")

    # Teacher A creates group and student
    group_a = AcademicRepository.create_group(
        db_session, teacher_a.id, GroupCreate(name="مجموعة الأستاذ أ", grade_level="1_sec", subject="لغة")
    )
    student_a = AcademicRepository.create_student(
        db_session, teacher_a.id, StudentCreate(full_name="طالب الأستاذ أ", grade_level="1_sec", phone="01099991111")
    )
    AcademicRepository.enroll_student_in_group(db_session, teacher_a.id, group_a.id, student_a.id)

    # Teacher B attempts to access Teacher A's student card
    leak_card = client.get(f"/api/barcodes/students/{student_a.id}/card", headers=headers_b)
    assert leak_card.status_code == 404

    # Teacher B attempts to export Teacher A's student PDF
    leak_pdf = client.get(f"/api/barcodes/students/{student_a.id}/card.pdf", headers=headers_b)
    assert leak_pdf.status_code == 404

    # Teacher B attempts to export Teacher A's group PDF
    leak_grp_pdf = client.post(f"/api/barcodes/groups/{group_a.id}/export-pdf", headers=headers_b)
    assert leak_grp_pdf.status_code == 404

    # Teacher B attempts to view Teacher A's group distribution
    leak_overview = client.get(f"/api/barcodes/distribution/groups/{group_a.id}", headers=headers_b)
    assert leak_overview.status_code == 404


# --------------------------------------------------------------------------
# Test 13: XSS and Arabic name escaping
# --------------------------------------------------------------------------
def test_arabic_and_xss_name_escaping(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_xss")
    headers = _login(client, "teacher_xss", "StrongPassword123!")

    xss_name = "<script>alert('xss')</script> & 'مروان' \"المهندس\""
    student = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name=xss_name, grade_level="2_sec", phone="01033334444")
    )

    card_resp = client.get(f"/api/barcodes/students/{student.id}/card", headers=headers)
    assert card_resp.status_code == 200
    card_data = card_resp.json()
    assert card_data["full_name"] == xss_name
    assert card_data["barcode_value"] == student.id
    # Ensure SVG contains only the student ID and no unescaped script tag
    assert "<script>" not in card_data["barcode_svg"]
    assert student.id in card_data["barcode_svg"]

    # PDF export should compile cleanly without ReportLab XML parse errors
    pdf_resp = client.get(f"/api/barcodes/students/{student.id}/card.pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")


# --------------------------------------------------------------------------
# Test 14: Multi-student custom selection export
# --------------------------------------------------------------------------
def test_multi_student_custom_selection_export(client, db_session):
    teacher = _setup_teacher(db_session, "teacher_multiselect")
    headers = _login(client, "teacher_multiselect", "StrongPassword123!")

    s1 = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب مختار 1", grade_level="1_sec", phone="01044441111")
    )
    s2 = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="طالب مختار 2", grade_level="1_sec", phone="01044442222")
    )

    resp = client.post("/api/barcodes/multi/export-pdf", json={
        "student_ids": [s1.id, s2.id]
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


# --------------------------------------------------------------------------
# Test 15: Regression — Group PDF Parser Validity and Binary Integrity
# --------------------------------------------------------------------------
def test_group_pdf_export_parser_validity_and_binary_integrity(client, db_session):
    """
    Verify that exported group PDF:
    1. Returns status 200 with application/pdf Content-Type.
    2. Sets Content-Length header equal to actual byte size.
    3. Sets nosniff and Cache-Control headers.
    4. Has valid %PDF- header and %%EOF trailer.
    5. Can be completely parsed and opened by pypdf without errors.
    """
    teacher = _setup_teacher(db_session, "teacher_pdf_val")
    headers = _login(client, "teacher_pdf_val", "StrongPassword123!")

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة التحقق من الصلاحية", grade_level="1_sec", subject="رياضيات")
    )
    for i in range(5):
        s = AcademicRepository.create_student(
            db_session, teacher.id, StudentCreate(full_name=f"طالب تدقيق {i+1}", grade_level="1_sec", phone=f"010998877{i:02d}")
        )
        AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s.id)

    resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "Content-Length" in resp.headers
    assert int(resp.headers["Content-Length"]) == len(resp.content)
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "no-store" in resp.headers.get("Cache-Control", "")

    # Validate binary signatures
    assert resp.content.startswith(b"%PDF-")
    assert b"%%EOF" in resp.content[-200:]

    # Parse with pypdf
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 1
    page = reader.pages[0]
    assert page.mediabox.width > 0
    assert page.mediabox.height > 0


# --------------------------------------------------------------------------
# Test 16: Regression — Individual Student Card PDF Parser Validity
# --------------------------------------------------------------------------
def test_individual_student_pdf_parser_validity_and_binary_integrity(client, db_session):
    """
    Verify individual student card PDF:
    1. Returns valid application/pdf with matching Content-Length.
    2. Contains valid %PDF- header and %%EOF trailer.
    3. Can be parsed by pypdf without errors.
    """
    teacher = _setup_teacher(db_session, "teacher_ind_val")
    headers = _login(client, "teacher_ind_val", "StrongPassword123!")

    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="زياد نادر فريد", grade_level="2_sec", phone="01155667788")
    )

    resp = client.get(f"/api/barcodes/students/{s.id}/card.pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "Content-Length" in resp.headers
    assert int(resp.headers["Content-Length"]) == len(resp.content)
    assert resp.content.startswith(b"%PDF-")
    assert b"%%EOF" in resp.content[-200:]

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert page.mediabox.width == 350
    assert page.mediabox.height == 230


# --------------------------------------------------------------------------
# Test 17: Regression — Unauthorized PDF Export returns JSON Error, NOT Fake PDF
# --------------------------------------------------------------------------
def test_unauthorized_pdf_export_returns_json_error_not_fake_pdf(client, db_session):
    """
    Ensure unauthenticated or unauthorized requests return HTTP 401/403 with
    JSON content-type and detail, never disguising an error as a PDF.
    """
    teacher = _setup_teacher(db_session, "teacher_auth_guard")
    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة الحماية", grade_level="1_sec", subject="فيزياء")
    )

    # 1. Unauthenticated request: 401 JSON
    client.cookies.clear()
    unauth_resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf")
    assert unauth_resp.status_code == 401
    assert "application/json" in unauth_resp.headers["content-type"]
    assert not unauth_resp.content.startswith(b"%PDF")
    assert "detail" in unauth_resp.json()

    # 2. Assistant with finance only (no attendance/student permission): 403 JSON
    asst = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="fin_guard_asst",
        full_name="مساعد حماية المالية",
        phone="01011119999",
        password="StrongPassword123!",
        permissions={"can_collect_cash": True, "can_manage_students": False, "can_view_attendance": False, "can_mark_attendance": False}
    )
    fin_headers = _login(client, "fin_guard_asst", "StrongPassword123!")

    forbid_resp = client.post(f"/api/barcodes/groups/{group.id}/export-pdf", headers=fin_headers)
    assert forbid_resp.status_code == 403
    assert "application/json" in forbid_resp.headers["content-type"]
    assert not forbid_resp.content.startswith(b"%PDF")
    assert "detail" in forbid_resp.json()


# --------------------------------------------------------------------------
# Test 18: Regression — Nonexistent Resource returns 404 JSON, NOT Fake PDF
# --------------------------------------------------------------------------
def test_nonexistent_group_or_student_pdf_returns_404_json_not_pdf(client, db_session):
    """
    Ensure nonexistent group/student ID returns 404 JSON, never an empty or corrupt PDF.
    """
    teacher = _setup_teacher(db_session, "teacher_404_guard")
    headers = _login(client, "teacher_404_guard", "StrongPassword123!")

    resp_grp = client.post("/api/barcodes/groups/nonexistent-uuid-group/export-pdf", headers=headers)
    assert resp_grp.status_code == 404
    assert "application/json" in resp_grp.headers["content-type"]
    assert not resp_grp.content.startswith(b"%PDF")
    assert "detail" in resp_grp.json()

    resp_stu = client.get("/api/barcodes/students/nonexistent-uuid-student/card.pdf", headers=headers)
    assert resp_stu.status_code == 404
    assert "application/json" in resp_stu.headers["content-type"]
    assert not resp_stu.content.startswith(b"%PDF")
    assert "detail" in resp_stu.json()


# --------------------------------------------------------------------------
# Test 19: Regression — BarcodeService Finalizes and Flushes Buffer
# --------------------------------------------------------------------------
def test_barcode_service_finalizes_and_validates_buffer():
    """
    Direct service-level test verifying that BarcodeService properly flushes,
    validates headers/trailers, closes internal BytesIO, and returns pypdf-compliant bytes.
    """
    group = {"name": "مجموعة الاختبار الفوري", "grade_level": "2_sec", "grade_label": "الصف الثاني الثانوي"}
    students = [
        {"student_id": f"uuid-000-{i}", "full_name": f"طالب رقم {i}", "grade_label": "الصف الثاني الثانوي"}
        for i in range(8)
    ]

    pdf_bytes = BarcodeService.generate_group_cards_pdf(group, students, "أ. تجريبي")
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"%%EOF" in pdf_bytes[-200:]

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1

    # Empty group check
    empty_pdf = BarcodeService.generate_group_cards_pdf(group, [], "أ. تجريبي")
    assert empty_pdf.startswith(b"%PDF-")
    empty_reader = pypdf.PdfReader(io.BytesIO(empty_pdf))
    assert len(empty_reader.pages) == 1


# --------------------------------------------------------------------------
# Test 20: Regression — Group PDF Export supports GET and Aliases without CSRF friction
# --------------------------------------------------------------------------
def test_group_pdf_export_get_and_alias_support(client, db_session):
    """
    Verify GET /api/barcodes/groups/{group_id}/export-pdf and
    alias /api/barcodes/groups/{group_id}/cards.pdf succeed with 200,
    valid application/pdf content type, proper headers, and parseable PDF bytes.
    """
    teacher = _setup_teacher(db_session, "teacher_dual_method")
    # Login and obtain cookie-based auth
    login_resp = client.post("/api/auth/login", json={"username": "teacher_dual_method", "password": "StrongPassword123!"})
    assert login_resp.status_code == 200
    data = login_resp.json()

    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة مزدوجة", grade_level="1_sec", subject="فيزياء")
    )
    s = AcademicRepository.create_student(
        db_session, teacher.id, StudentCreate(full_name="حمزة طارق", grade_level="1_sec", phone="01088887777")
    )
    AcademicRepository.enroll_student_in_group(db_session, teacher.id, group.id, s.id)

    # Set browser cookie auth (NO CSRF header sent)
    from app.config import SESSION_COOKIE_NAME, CSRF_COOKIE_NAME
    client.cookies.set(SESSION_COOKIE_NAME, data["session_token"])
    client.cookies.set(CSRF_COOKIE_NAME, data["csrf_token"])

    # 1. GET export-pdf
    res_get = client.get(f"/api/barcodes/groups/{group.id}/export-pdf")
    assert res_get.status_code == 200
    assert "application/pdf" in res_get.headers["content-type"]
    assert res_get.headers.get("x-content-type-options") == "nosniff"
    assert "attachment" in res_get.headers.get("content-disposition", "")
    assert res_get.content.startswith(b"%PDF-")
    assert b"%%EOF" in res_get.content[-200:]
    reader_get = pypdf.PdfReader(io.BytesIO(res_get.content))
    assert len(reader_get.pages) >= 1

    # 2. GET cards.pdf alias
    res_alias = client.get(f"/api/barcodes/groups/{group.id}/cards.pdf")
    assert res_alias.status_code == 200
    assert "application/pdf" in res_alias.headers["content-type"]
    assert res_alias.content.startswith(b"%PDF-")


# --------------------------------------------------------------------------
# Test 21: Assistant with can_mark_attendance permission access
# --------------------------------------------------------------------------
def test_assistant_with_mark_attendance_can_export_group_pdf(client, db_session):
    """
    Verify assistant with can_mark_attendance=True can access distribution
    endpoints without 403 Forbidden.
    """
    teacher = _setup_teacher(db_session, "teacher_asst_perm")
    asst = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="attendance_asst_ok",
        full_name="مساعد الحضور الرسمي",
        phone="01044443333",
        password="StrongPassword123!",
        permissions={"can_mark_attendance": True, "can_view_attendance": False, "can_manage_students": False}
    )
    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة الحضور للمساعد", grade_level="2_sec", subject="أحياء")
    )

    asst_headers = _login(client, "attendance_asst_ok", "StrongPassword123!")

    # Assistant exports group PDF via GET
    res_asst = client.get(f"/api/barcodes/groups/{group.id}/export-pdf", headers=asst_headers)
    assert res_asst.status_code == 200
    assert "application/pdf" in res_asst.headers["content-type"]
    assert res_asst.content.startswith(b"%PDF-")


# --------------------------------------------------------------------------
# Test 22: Error response isolation — Errors are strictly JSON, never PDF
# --------------------------------------------------------------------------
def test_error_responses_never_contain_pdf_content(client, db_session):
    """
    Verify that 401, 403, and 404 responses are strictly application/json,
    never begin with %PDF, and contain an intelligible detail message.
    """
    # Clear all cookies
    client.cookies.clear()

    # 1. 401 Unauthorized
    r401 = client.get("/api/barcodes/groups/any-group/export-pdf")
    assert r401.status_code == 401
    assert "application/json" in r401.headers["content-type"]
    assert not r401.content.startswith(b"%PDF")
    assert "detail" in r401.json()

    # Login as teacher
    teacher = _setup_teacher(db_session, "teacher_err_isolation")
    t_headers = _login(client, "teacher_err_isolation", "StrongPassword123!")

    # 2. 404 Not Found
    r404 = client.get("/api/barcodes/groups/00000000-0000-0000-0000-000000000000/export-pdf", headers=t_headers)
    assert r404.status_code == 404
    assert "application/json" in r404.headers["content-type"]
    assert not r404.content.startswith(b"%PDF")
    assert "detail" in r404.json()

    # 3. 403 Forbidden for assistant with only exam permissions
    asst_no_dist = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="exam_only_asst",
        full_name="مساعد الامتحانات فقط",
        phone="01099991111",
        password="StrongPassword123!",
        permissions={"can_manage_exams": True, "can_enter_grades": True, "can_mark_attendance": False, "can_view_attendance": False, "can_manage_students": False}
    )
    no_dist_headers = _login(client, "exam_only_asst", "StrongPassword123!")
    group = AcademicRepository.create_group(
        db_session, teacher.id, GroupCreate(name="مجموعة الحظر", grade_level="1_sec", subject="كيمياء")
    )
    r403 = client.get(f"/api/barcodes/groups/{group.id}/export-pdf", headers=no_dist_headers)
    assert r403.status_code == 403
    assert "application/json" in r403.headers["content-type"]
    assert not r403.content.startswith(b"%PDF")
    assert "detail" in r403.json()


