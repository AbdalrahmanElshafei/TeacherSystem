import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.main import app
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
        CSRF_HEADER_NAME: data["csrf_token"],
        "Authorization": f"Bearer {data['session_token']}"
    }


def _create_teacher_and_login(client, username="mr_teacher_att", password="StrongPassword2026!"):
    setup_payload = {
        "username": username,
        "full_name": f"Teacher {username}",
        "phone": "01011112222",
        "password": password
    }
    client.post("/api/auth/first-run-setup", json=setup_payload)
    return _login(client, username, password)


# ==========================================
# --- Test 1: Sessions CRUD & Validation ---
# ==========================================

def test_session_crud_and_validation(client):
    headers = _create_teacher_and_login(client)

    # 1. Create a group
    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة الأحد 5م",
        "grade_level": "1_sec",
        "subject": "رياضيات"
    }, headers=headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    # 2. Validation: invalid date format (must be YYYY-MM-DD)
    bad_date_resp = client.post("/api/sessions", json={
        "group_id": group_id,
        "session_date": "2026/10/28",
        "start_time": "17:00"
    }, headers=headers)
    assert bad_date_resp.status_code == 422

    # 3. Validation: invalid time format
    bad_time_resp = client.post("/api/sessions", json={
        "group_id": group_id,
        "session_date": "2026-10-28",
        "start_time": "5:00 PM"
    }, headers=headers)
    assert bad_time_resp.status_code == 422

    # 4. Validation: nonexistent group
    bad_grp_resp = client.post("/api/sessions", json={
        "group_id": "nonexistent-group-id",
        "session_date": "2026-10-28",
        "start_time": "17:00"
    }, headers=headers)
    assert bad_grp_resp.status_code == 400

    # 5. Create valid session
    valid_payload = {
        "group_id": group_id,
        "session_date": "2026-11-05",
        "start_time": "17:00",
        "end_time": "19:00",
        "location": "قاعة الأوائل 1",
        "notes": "شرح درس المصفوفات",
        "status": "scheduled"
    }
    create_resp = client.post("/api/sessions", json=valid_payload, headers=headers)
    assert create_resp.status_code == 201
    session_data = create_resp.json()
    session_id = session_data["id"]
    assert session_data["group_id"] == group_id
    assert session_data["group_name"] == "مجموعة الأحد 5م"
    assert session_data["status"] == "scheduled"
    assert session_data["status_label"] == "مجدولة"

    # 6. Get single session
    get_resp = client.get(f"/api/sessions/{session_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id

    # 7. List sessions with filters
    list_all = client.get("/api/sessions", headers=headers)
    assert list_all.status_code == 200
    assert len(list_all.json()) == 1

    list_by_grp = client.get(f"/api/sessions?group_id={group_id}", headers=headers)
    assert list_by_grp.status_code == 200
    assert len(list_by_grp.json()) == 1

    list_by_wrong_date = client.get("/api/sessions?session_date=2020-01-01", headers=headers)
    assert list_by_wrong_date.status_code == 200
    assert len(list_by_wrong_date.json()) == 0

    # 8. Update session
    update_resp = client.put(f"/api/sessions/{session_id}", json={
        "start_time": "17:30",
        "location": "قاعة الأوائل 2",
        "notes": "تم تأخير الحصة نصف ساعة"
    }, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["start_time"] == "17:30"
    assert update_resp.json()["location"] == "قاعة الأوائل 2"

    # 9. Cancel session
    cancel_resp = client.post(f"/api/sessions/{session_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
    assert cancel_resp.json()["status_label"] == "ملغاة"


# ==========================================
# --- Test 2: Attendance Taking & Upsert ---
# ==========================================

def test_attendance_taking_and_upsert(client):
    headers = _create_teacher_and_login(client)

    # 1. Create students and group
    st1 = client.post("/api/students", json={
        "full_name": "طالب 1", "grade_level": "2_sec", "phone": "01000000001"
    }, headers=headers).json()
    st2 = client.post("/api/students", json={
        "full_name": "طالب 2 (غير مقيد)", "grade_level": "2_sec", "phone": "01000000002"
    }, headers=headers).json()

    grp = client.post("/api/groups", json={
        "name": "مجموعة 2ث", "grade_level": "2_sec"
    }, headers=headers).json()

    # Enroll st1 only
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st1["id"]}, headers=headers)

    # Create session
    sess = client.post("/api/sessions", json={
        "group_id": grp["id"], "session_date": "2026-11-10", "start_time": "14:00"
    }, headers=headers).json()

    # 2. Attempt to mark attendance for unenrolled student st2 -> 400
    unenrolled_resp = client.post(f"/api/sessions/{sess['id']}/attendance", json={
        "student_id": st2["id"], "status": "present"
    }, headers=headers)
    assert unenrolled_resp.status_code == 400

    # 3. Mark attendance for enrolled student st1
    mark_resp = client.post(f"/api/sessions/{sess['id']}/attendance", json={
        "student_id": st1["id"], "status": "present", "notes": "حضر في الموعد"
    }, headers=headers)
    assert mark_resp.status_code == 200
    assert mark_resp.json()["status"] == "present"
    att_id = mark_resp.json()["id"]

    # 4. Upsert check: change status to 'late' with new notes
    update_att_resp = client.post(f"/api/sessions/{sess['id']}/attendance", json={
        "student_id": st1["id"], "status": "late", "notes": "تأخر 20 دقيقة"
    }, headers=headers)
    assert update_att_resp.status_code == 200
    assert update_att_resp.json()["id"] == att_id  # Same record ID, no duplicate created
    assert update_att_resp.json()["status"] == "late"

    # 5. Check attendance sheet
    sheet_resp = client.get(f"/api/sessions/{sess['id']}/attendance", headers=headers)
    assert sheet_resp.status_code == 200
    sheet = sheet_resp.json()
    assert sheet["stats"]["total_enrolled"] == 1
    assert sheet["stats"]["late_count"] == 1
    assert sheet["stats"]["present_count"] == 0
    assert sheet["stats"]["unrecorded_count"] == 0


# ==========================================
# --- Test 3: Bulk Attendance & Transaction ---
# ==========================================

def test_bulk_attendance_atomic_transaction(client):
    headers = _create_teacher_and_login(client)

    # Create 3 students
    s1 = client.post("/api/students", json={"full_name": "طالب أ", "grade_level": "1_sec", "phone": "01011111111"}, headers=headers).json()
    s2 = client.post("/api/students", json={"full_name": "طالب ب", "grade_level": "1_sec", "phone": "01022222222"}, headers=headers).json()
    s3_unenrolled = client.post("/api/students", json={"full_name": "طالب ج", "grade_level": "1_sec", "phone": "01033333333"}, headers=headers).json()

    grp = client.post("/api/groups", json={"name": "مجموعة 1ث", "grade_level": "1_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": s1["id"]}, headers=headers)
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": s2["id"]}, headers=headers)

    sess = client.post("/api/sessions", json={
        "group_id": grp["id"], "session_date": "2026-11-12", "start_time": "10:00"
    }, headers=headers).json()

    # 1. Bulk mark valid enrolled students s1 and s2
    bulk_valid = client.post(f"/api/sessions/{sess['id']}/attendance/bulk", json={
        "records": [
            {"student_id": s1["id"], "status": "present"},
            {"student_id": s2["id"], "status": "absent", "notes": "غياب بدون عذر"}
        ]
    }, headers=headers)
    assert bulk_valid.status_code == 200
    assert bulk_valid.json()["count"] == 2

    # 2. Transaction Atomicity: If one student is not enrolled, entire operation aborts
    bulk_invalid = client.post(f"/api/sessions/{sess['id']}/attendance/bulk", json={
        "records": [
            {"student_id": s1["id"], "status": "late"},  # would update s1
            {"student_id": s3_unenrolled["id"], "status": "present"}  # invalid!
        ]
    }, headers=headers)
    assert bulk_invalid.status_code == 400

    # Verify s1 was NOT modified to 'late' due to transaction rollback
    sheet = client.get(f"/api/sessions/{sess['id']}/attendance", headers=headers).json()
    s1_record = [r for r in sheet["students"] if r["student_id"] == s1["id"]][0]
    assert s1_record["status"] == "present"  # Intact!


# ==========================================
# --- Test 4: USB Barcode Scanner Workflow ---
# ==========================================

def test_usb_barcode_scanner_workflow(client):
    headers = _create_teacher_and_login(client)

    st1 = client.post("/api/students", json={"full_name": "زياد طارق", "grade_level": "3_sec", "phone": "01044445555"}, headers=headers).json()
    st2_other = client.post("/api/students", json={"full_name": "محمد طارق", "grade_level": "3_sec", "phone": "01066667777"}, headers=headers).json()

    grp = client.post("/api/groups", json={"name": "مجموعة 3ث لغات", "grade_level": "3_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st1["id"]}, headers=headers)

    sess = client.post("/api/sessions", json={
        "group_id": grp["id"], "session_date": "2026-11-15", "start_time": "18:00"
    }, headers=headers).json()

    # 1. Normal Scan (Barcode = student.id)
    scan_resp = client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": st1["id"]}, headers=headers)
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["success"] is True
    assert scan_data["action"] == "recorded"
    assert scan_data["status"] == "present"
    assert scan_data["student"]["full_name"] == "زياد طارق"
    assert "timestamp" in scan_data

    # 2. Duplicate Scan -> Handled gracefully without error
    dup_resp = client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": st1["id"]}, headers=headers)
    assert dup_resp.status_code == 200
    dup_data = dup_resp.json()
    assert dup_data["success"] is True
    assert dup_data["action"] == "already_present"
    assert "بالفعل" in dup_data["message"]

    # 3. Unknown barcode -> 404
    unknown_resp = client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": "UNKNOWN_BARCODE_123"}, headers=headers)
    assert unknown_resp.status_code == 404

    # 4. Student not enrolled in session's group -> 400
    not_enrolled_resp = client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": st2_other["id"]}, headers=headers)
    assert not_enrolled_resp.status_code == 400


# ==========================================
# --- Test 5: Tenant Isolation ---
# ==========================================

def test_tenant_isolation_sessions_and_attendance(client, db_session):
    # Teacher 1
    t1_headers = _create_teacher_and_login(client, username="t1_att", password="PasswordT1_2026!")

    t1_grp = client.post("/api/groups", json={"name": "مجموعة المعلم 1", "grade_level": "1_sec"}, headers=t1_headers).json()
    t1_st = client.post("/api/students", json={"full_name": "طالب المعلم 1", "grade_level": "1_sec", "phone": "01011110000"}, headers=t1_headers).json()
    client.post(f"/api/groups/{t1_grp['id']}/students", json={"student_id": t1_st["id"]}, headers=t1_headers)
    t1_sess = client.post("/api/sessions", json={
        "group_id": t1_grp["id"], "session_date": "2026-11-20", "start_time": "12:00"
    }, headers=t1_headers).json()

    # Teacher 2
    from app.repositories.user_repo import UserRepository
    t2 = UserRepository.create_teacher(
        db_session,
        username="t2_att",
        full_name="Teacher 2",
        phone="01022220000",
        password="PasswordT2_2026!"
    )
    t2_headers = _login(client, "t2_att", "PasswordT2_2026!")

    # 1. Teacher 2 cannot view Teacher 1's session (404)
    t2_view_sess = client.get(f"/api/sessions/{t1_sess['id']}", headers=t2_headers)
    assert t2_view_sess.status_code == 404

    # 2. Teacher 2 cannot list Teacher 1's session
    t2_list_sess = client.get("/api/sessions", headers=t2_headers)
    assert t2_list_sess.status_code == 200
    assert len(t2_list_sess.json()) == 0

    # 3. Teacher 2 cannot update or cancel Teacher 1's session
    t2_update = client.put(f"/api/sessions/{t1_sess['id']}", json={"location": "هاكر"}, headers=t2_headers)
    assert t2_update.status_code == 404

    t2_cancel = client.post(f"/api/sessions/{t1_sess['id']}/cancel", headers=t2_headers)
    assert t2_cancel.status_code == 404

    # 4. Teacher 2 cannot access Teacher 1's attendance sheet
    t2_sheet = client.get(f"/api/sessions/{t1_sess['id']}/attendance", headers=t2_headers)
    assert t2_sheet.status_code == 404

    # 5. Teacher 2 cannot mark attendance on Teacher 1's session
    t2_mark = client.post(f"/api/sessions/{t1_sess['id']}/attendance", json={
        "student_id": t1_st["id"], "status": "present"
    }, headers=t2_headers)
    assert t2_mark.status_code in (400, 404)

    # 6. Teacher 2 cannot scan Teacher 1's student barcode
    t2_scan = client.post(f"/api/sessions/{t1_sess['id']}/scan", json={"barcode": t1_st["id"]}, headers=t2_headers)
    assert t2_scan.status_code in (400, 404)

    # 7. Teacher 2 cannot view reports of Teacher 1's students or groups
    t2_st_rep = client.get(f"/api/sessions/reports/student/{t1_st['id']}", headers=t2_headers)
    assert t2_st_rep.status_code == 404

    t2_grp_rep = client.get(f"/api/sessions/reports/group/{t1_grp['id']}", headers=t2_headers)
    assert t2_grp_rep.status_code == 404


# ==========================================
# --- Test 6: Assistant Permissions ---
# ==========================================

def test_assistant_permissions_attendance(client):
    teacher_headers = _create_teacher_and_login(client)

    # Setup Group & Session by Teacher
    grp = client.post("/api/groups", json={"name": "مجموعة الصلاحيات", "grade_level": "1_sec"}, headers=teacher_headers).json()
    st = client.post("/api/students", json={"full_name": "طالب تجربة", "grade_level": "1_sec", "phone": "01088889999"}, headers=teacher_headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=teacher_headers)
    sess = client.post("/api/sessions", json={
        "group_id": grp["id"], "session_date": "2026-11-25", "start_time": "15:00"
    }, headers=teacher_headers).json()

    # Create Assistant 1: can_view_attendance=True, can_mark_attendance=False
    client.post("/api/users/assistants", json={
        "username": "ass_viewer",
        "full_name": "مساعد مشاهد فقط",
        "phone": "01011113333",
        "password": "AssistantPass1!",
        "permissions": {
            "can_view_attendance": True,
            "can_mark_attendance": False
        }
    }, headers=teacher_headers)
    viewer_headers = _login(client, "ass_viewer", "AssistantPass1!")

    # Assistant 1 can view sessions and sheet
    assert client.get("/api/sessions", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/sessions/{sess['id']}", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/sessions/{sess['id']}/attendance", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/sessions/reports/student/{st['id']}", headers=viewer_headers).status_code == 200

    # Assistant 1 CANNOT mutate sessions or take attendance (403 Forbidden)
    assert client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-26", "start_time": "10:00"}, headers=viewer_headers).status_code == 403
    assert client.put(f"/api/sessions/{sess['id']}", json={"location": "قاعة جديدة"}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/sessions/{sess['id']}/cancel", headers=viewer_headers).status_code == 403
    assert client.post(f"/api/sessions/{sess['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/sessions/{sess['id']}/attendance/bulk", json={"records": [{"student_id": st["id"], "status": "present"}]}, headers=viewer_headers).status_code == 403
    assert client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": st["id"]}, headers=viewer_headers).status_code == 403

    # Create Assistant 2: can_view_attendance=True, can_mark_attendance=True
    client.post("/api/users/assistants", json={
        "username": "ass_marker",
        "full_name": "مساعد رصد كامل",
        "phone": "01011114444",
        "password": "AssistantPass2!",
        "permissions": {
            "can_view_attendance": True,
            "can_mark_attendance": True
        }
    }, headers=teacher_headers)
    marker_headers = _login(client, "ass_marker", "AssistantPass2!")

    # Assistant 2 can mark attendance and scan barcode
    scan_res = client.post(f"/api/sessions/{sess['id']}/scan", json={"barcode": st["id"]}, headers=marker_headers)
    assert scan_res.status_code == 200
    assert scan_res.json()["action"] == "recorded"


# ==========================================
# --- Test 7: Reports & Rate Calculations ---
# ==========================================

def test_reports_calculations(client):
    headers = _create_teacher_and_login(client)

    st = client.post("/api/students", json={"full_name": "أحمد ممتاز", "grade_level": "3_sec", "phone": "01099990000"}, headers=headers).json()
    grp = client.post("/api/groups", json={"name": "مجموعة التقارير", "grade_level": "3_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)

    # Create 4 sessions
    s1 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-01", "start_time": "10:00"}, headers=headers).json()
    s2 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-08", "start_time": "10:00"}, headers=headers).json()
    s3 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-15", "start_time": "10:00"}, headers=headers).json()
    s4 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-22", "start_time": "10:00"}, headers=headers).json()

    # Record attendance: 2 present, 1 late, 1 absent
    client.post(f"/api/sessions/{s1['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)
    client.post(f"/api/sessions/{s2['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)
    client.post(f"/api/sessions/{s3['id']}/attendance", json={"student_id": st["id"], "status": "late"}, headers=headers)
    client.post(f"/api/sessions/{s4['id']}/attendance", json={"student_id": st["id"], "status": "absent"}, headers=headers)

    # Check Student History: 3 attended (2 present + 1 late) out of 4 sessions -> 75.0%
    hist_resp = client.get(f"/api/sessions/reports/student/{st['id']}", headers=headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["total_sessions"] == 4
    assert hist["present_count"] == 2
    assert hist["late_count"] == 1
    assert hist["absent_count"] == 1
    assert hist["attendance_rate"] == 75.0

    # Check Group Summary:
    summary_resp = client.get(f"/api/sessions/reports/group/{grp['id']}", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_sessions"] == 4
    assert summary["total_students"] == 1
    # Average rate across the 4 sessions: (100 + 100 + 100 + 0) / 4 = 75.0%
    assert summary["average_attendance_rate"] == 75.0


# =======================================================
# --- Test 8: Engineering Review Edge Cases & Integrity -
# =======================================================

def test_cancelled_session_blocks_attendance_and_updates_reports(client):
    headers = _create_teacher_and_login(client)

    st = client.post("/api/students", json={"full_name": "سامح خليل", "grade_level": "2_sec", "phone": "01033334444"}, headers=headers).json()
    grp = client.post("/api/groups", json={"name": "مجموعة 2ث ملغاة", "grade_level": "2_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)

    # Session 1: completed with 100% attendance
    s1 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-01", "start_time": "14:00", "status": "completed"}, headers=headers).json()
    client.post(f"/api/sessions/{s1['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)

    # Session 2: cancelled
    s2 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-08", "start_time": "14:00"}, headers=headers).json()
    client.post(f"/api/sessions/{s2['id']}/cancel", headers=headers)

    # 1. Single attendance on cancelled session -> rejected with 400
    res_single = client.post(f"/api/sessions/{s2['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)
    assert res_single.status_code == 400
    assert "ملغاة" in res_single.json()["detail"]

    # 2. Bulk attendance on cancelled session -> rejected with 400
    res_bulk = client.post(f"/api/sessions/{s2['id']}/attendance/bulk", json={"records": [{"student_id": st["id"], "status": "present"}]}, headers=headers)
    assert res_bulk.status_code == 400
    assert "ملغاة" in res_bulk.json()["detail"]

    # 3. Barcode scan on cancelled session -> rejected with 400
    res_scan = client.post(f"/api/sessions/{s2['id']}/scan", json={"barcode": st["id"]}, headers=headers)
    assert res_scan.status_code == 400
    assert "ملغاة" in res_scan.json()["detail"]

    # 4. Group attendance summary: cancelled session does NOT pull down the average attendance rate to 50%
    summary_resp = client.get(f"/api/sessions/reports/group/{grp['id']}", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_sessions"] == 1  # Only 1 active session
    assert summary["average_attendance_rate"] == 100.0  # Still 100.0%, not dragged down by cancelled session!


def test_bulk_attendance_rejects_duplicate_students_in_single_payload(client):
    headers = _create_teacher_and_login(client)

    st = client.post("/api/students", json={"full_name": "وائل كمال", "grade_level": "1_sec", "phone": "01077771111"}, headers=headers).json()
    grp = client.post("/api/groups", json={"name": "مجموعة تكرار البلك", "grade_level": "1_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)
    sess = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-05", "start_time": "15:00"}, headers=headers).json()

    # Duplicate student in records list
    dup_bulk = client.post(f"/api/sessions/{sess['id']}/attendance/bulk", json={
        "records": [
            {"student_id": st["id"], "status": "present"},
            {"student_id": st["id"], "status": "absent"}
        ]
    }, headers=headers)
    assert dup_bulk.status_code == 400
    assert "تكرار" in dup_bulk.json()["detail"]


def test_time_and_date_range_validation(client):
    headers = _create_teacher_and_login(client)
    grp = client.post("/api/groups", json={"name": "مجموعة التحقق الزمني", "grade_level": "1_sec"}, headers=headers).json()

    # 1. SessionCreate: end_time before start_time -> 422
    res_bad_range = client.post("/api/sessions", json={
        "group_id": grp["id"],
        "session_date": "2026-11-05",
        "start_time": "18:00",
        "end_time": "16:00"
    }, headers=headers)
    assert res_bad_range.status_code == 422

    # 2. SessionCreate: end_time equal to start_time -> 422
    res_equal_time = client.post("/api/sessions", json={
        "group_id": grp["id"],
        "session_date": "2026-11-05",
        "start_time": "18:00",
        "end_time": "18:00"
    }, headers=headers)
    assert res_equal_time.status_code == 422

    # 3. Create valid session
    sess = client.post("/api/sessions", json={
        "group_id": grp["id"],
        "session_date": "2026-11-05",
        "start_time": "16:00",
        "end_time": "18:00"
    }, headers=headers).json()

    # 4. SessionUpdate: update start_time to after end_time -> 400
    res_bad_update = client.put(f"/api/sessions/{sess['id']}", json={
        "start_time": "19:00"
    }, headers=headers)
    assert res_bad_update.status_code == 400

    # 5. list_sessions: start_date > end_date -> 400
    res_bad_dates = client.get("/api/sessions?start_date=2026-12-01&end_date=2026-11-01", headers=headers)
    assert res_bad_dates.status_code == 400
    assert "start_date" in res_bad_dates.json()["detail"]


def test_reenrollment_historical_integrity(client):
    headers = _create_teacher_and_login(client)

    st = client.post("/api/students", json={"full_name": "مازن سامي", "grade_level": "1_sec", "phone": "01099992222"}, headers=headers).json()
    grp = client.post("/api/groups", json={"name": "مجموعة السلامة التاريخية", "grade_level": "1_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)

    sess = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-01", "start_time": "14:00"}, headers=headers).json()

    # Mark attendance: present
    client.post(f"/api/sessions/{sess['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)

    # Unenroll student
    client.delete(f"/api/groups/{grp['id']}/students/{st['id']}", headers=headers)

    # Re-enroll student
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)

    # Check attendance sheet: student still has 1 record, status present, no duplicates
    sheet = client.get(f"/api/sessions/{sess['id']}/attendance", headers=headers).json()
    st_records = [r for r in sheet["students"] if r["student_id"] == st["id"]]
    assert len(st_records) == 1
    assert st_records[0]["status"] == "present"


def test_excused_absence_rate_calculation(client):
    headers = _create_teacher_and_login(client)

    st = client.post("/api/students", json={"full_name": "فهد طارق", "grade_level": "3_sec", "phone": "01099993333"}, headers=headers).json()
    grp = client.post("/api/groups", json={"name": "مجموعة العذر", "grade_level": "3_sec"}, headers=headers).json()
    client.post(f"/api/groups/{grp['id']}/students", json={"student_id": st["id"]}, headers=headers)

    s1 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-01", "start_time": "10:00"}, headers=headers).json()
    s2 = client.post("/api/sessions", json={"group_id": grp["id"], "session_date": "2026-11-08", "start_time": "10:00"}, headers=headers).json()

    # 1 present, 1 excused absence
    client.post(f"/api/sessions/{s1['id']}/attendance", json={"student_id": st["id"], "status": "present"}, headers=headers)
    client.post(f"/api/sessions/{s2['id']}/attendance", json={"student_id": st["id"], "status": "excused", "notes": "عذر مرضي"}, headers=headers)

    hist = client.get(f"/api/sessions/reports/student/{st['id']}", headers=headers).json()
    assert hist["total_sessions"] == 2
    assert hist["present_count"] == 1
    assert hist["excused_count"] == 1
    assert hist["absent_count"] == 0
    # Excused absence does not penalize attendance rate -> 100.0%
    assert hist["attendance_rate"] == 100.0

