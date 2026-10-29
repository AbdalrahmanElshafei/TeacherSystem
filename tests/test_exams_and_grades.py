import uuid
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
from app.models.user import Teacher
from app.models.academic import Student, Group, GroupStudent
from app.models.exam import Exam, ExamResult

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


def _create_teacher_and_login(client, username="mr_teacher_exam", password="StrongPassword2026!"):
    setup_payload = {
        "username": username,
        "full_name": f"Teacher {username}",
        "phone": "01011112222",
        "password": password
    }
    client.post("/api/auth/first-run-setup", json=setup_payload)
    return _login(client, username, password)


def _enroll_student(client, group_id, student_id, headers):
    resp = client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ==========================================
# --- Test 1: Exam CRUD & Validations ---
# ==========================================

def test_exam_crud_and_validations(client):
    headers = _create_teacher_and_login(client)

    # 1. Create a group
    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة الكيمياء 1ث",
        "grade_level": "1_sec",
        "subject": "كيمياء"
    }, headers=headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    # 2. Validation: invalid date format (must be YYYY-MM-DD)
    bad_date_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان شهر أكتوبر",
        "exam_date": "2026/10/28",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers)
    assert bad_date_resp.status_code == 422

    # 3. Validation: max_score <= 0
    bad_max_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان شهر أكتوبر",
        "exam_date": "2026-10-28",
        "max_score": 0,
        "passing_score": 0
    }, headers=headers)
    assert bad_max_resp.status_code == 422

    # 4. Validation: passing_score > max_score
    bad_passing_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان شهر أكتوبر",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 55
    }, headers=headers)
    assert bad_passing_resp.status_code == 422

    # 5. Validation: title too short
    bad_title_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "ا",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers)
    assert bad_title_resp.status_code == 422

    # 6. Success: Create exam
    create_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان شهر أكتوبر الشامل",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25,
        "description": "يشمل البابين الأول والثاني"
    }, headers=headers)
    assert create_resp.status_code == 201
    exam = create_resp.json()
    assert exam["title"] == "امتحان شهر أكتوبر الشامل"
    assert exam["max_score"] == 50.0
    assert exam["passing_score"] == 25.0
    assert exam["status"] == "scheduled"
    assert exam["status_label"] == "مجدول"
    assert exam["group_name"] == "مجموعة الكيمياء 1ث"
    exam_id = exam["id"]

    # 7. Get single exam
    get_resp = client.get(f"/api/exams/{exam_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == exam_id

    # 8. List exams with filters
    list_resp = client.get(f"/api/exams?group_id={group_id}&status=scheduled", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Date range filter error if start_date > end_date
    bad_range = client.get("/api/exams?start_date=2026-11-01&end_date=2026-10-01", headers=headers)
    assert bad_range.status_code == 400

    # 9. Update exam
    up_resp = client.put(f"/api/exams/{exam_id}", json={
        "title": "امتحان الكيمياء المعدل",
        "max_score": 60,
        "passing_score": 30
    }, headers=headers)
    assert up_resp.status_code == 200
    assert up_resp.json()["title"] == "امتحان الكيمياء المعدل"
    assert up_resp.json()["max_score"] == 60.0
    assert up_resp.json()["passing_score"] == 30.0

    # 10. Delete exam (soft delete)
    del_resp = client.delete(f"/api/exams/{exam_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # After delete, exam not found in get or list
    assert client.get(f"/api/exams/{exam_id}", headers=headers).status_code == 404
    assert len(client.get(f"/api/exams?group_id={group_id}", headers=headers).json()) == 0


# ==========================================
# --- Test 2: Single Grade Entry & Rules ---
# ==========================================

def test_single_grade_entry_and_rules(client):
    headers = _create_teacher_and_login(client)

    # Setup: Group, Students, Enrollment
    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة الفيزياء 2ث",
        "grade_level": "2_sec"
    }, headers=headers)
    group_id = grp_resp.json()["id"]

    st1 = client.post("/api/students", json={
        "full_name": "أحمد محمود سالم",
        "phone": "01000000001",
        "grade_level": "2_sec"
    }, headers=headers).json()["id"]

    st2 = client.post("/api/students", json={
        "full_name": "يوسف كمال الدين",
        "phone": "01000000002",
        "grade_level": "2_sec"
    }, headers=headers).json()["id"]

    # Enroll st1 in group, keep st2 UNENROLLED
    _enroll_student(client, group_id, st1, headers)

    # Create exam (max 50, passing 25)
    exam_id = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان فيزياء فصلي",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers).json()["id"]

    # 1. Unenrolled student grade rejected
    unenrolled_resp = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": st2,
        "status": "attended",
        "score": 30
    }, headers=headers)
    assert unenrolled_resp.status_code == 400
    assert "غير مسجل" in unenrolled_resp.json()["detail"]

    # 2. Score > max_score rejected
    too_high_resp = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": st1,
        "status": "attended",
        "score": 55
    }, headers=headers)
    assert too_high_resp.status_code == 400

    # 3. Missing score for attended rejected
    no_score_resp = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": st1,
        "status": "attended"
    }, headers=headers)
    assert no_score_resp.status_code == 422

    # 4. Valid score recording
    res1 = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": st1,
        "status": "attended",
        "score": 42.5,
        "notes": "إجابة ممتازة"
    }, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["score"] == 42.5
    assert res1.json()["status"] == "attended"

    # Check Results Sheet
    sheet = client.get(f"/api/exams/{exam_id}/results", headers=headers).json()
    assert len(sheet["students"]) == 1
    st_row = sheet["students"][0]
    assert st_row["student_id"] == st1
    assert st_row["score"] == 42.5
    assert st_row["percentage"] == 85.0
    assert st_row["is_passed"] is True

    # 5. Switch to absent -> score must be forced to None (do not fabricate score)
    res_absent = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": st1,
        "status": "absent"
    }, headers=headers)
    assert res_absent.status_code == 200
    assert res_absent.json()["status"] == "absent"
    assert res_absent.json()["score"] is None

    # Verify sheet reflects null score for absent
    sheet_absent = client.get(f"/api/exams/{exam_id}/results", headers=headers).json()
    assert sheet_absent["students"][0]["score"] is None
    assert sheet_absent["students"][0]["percentage"] is None
    assert sheet_absent["students"][0]["is_passed"] is None


# ==========================================
# --- Test 3: Bulk Grade Entry & Atomicity ---
# ==========================================

def test_bulk_grade_entry_atomicity(client):
    headers = _create_teacher_and_login(client)

    grp = client.post("/api/groups", json={"name": "مجموعة الأحياء", "grade_level": "3_sec"}, headers=headers).json()
    group_id = grp["id"]

    s1 = client.post("/api/students", json={"full_name": "طالب 1", "phone": "01000000011", "grade_level": "3_sec"}, headers=headers).json()["id"]
    s2 = client.post("/api/students", json={"full_name": "طالب 2", "phone": "01000000012", "grade_level": "3_sec"}, headers=headers).json()["id"]
    s3 = client.post("/api/students", json={"full_name": "طالب 3", "phone": "01000000013", "grade_level": "3_sec"}, headers=headers).json()["id"]

    # Enroll s1 and s2 only
    _enroll_student(client, group_id, s1, headers)
    _enroll_student(client, group_id, s2, headers)

    exam_id = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان أحياء تجريبي",
        "exam_date": "2026-10-28",
        "max_score": 100,
        "passing_score": 50
    }, headers=headers).json()["id"]

    # 1. Bulk batch with duplicate student_id in payload -> rejected atomically
    dup_resp = client.post(f"/api/exams/{exam_id}/results/bulk", json={
        "records": [
            {"student_id": s1, "status": "attended", "score": 90},
            {"student_id": s1, "status": "attended", "score": 80}
        ]
    }, headers=headers)
    assert dup_resp.status_code == 400
    assert "تكرار" in dup_resp.json()["detail"]

    # 2. Bulk batch with unenrolled student (s3) -> rejected atomically, s1 is NOT saved
    invalid_batch = client.post(f"/api/exams/{exam_id}/results/bulk", json={
        "records": [
            {"student_id": s1, "status": "attended", "score": 90},
            {"student_id": s3, "status": "attended", "score": 75}
        ]
    }, headers=headers)
    assert invalid_batch.status_code == 400
    assert "غير مسجل" in invalid_batch.json()["detail"]

    # Verify atomic rollback: s1 has NO recorded result
    sheet = client.get(f"/api/exams/{exam_id}/results", headers=headers).json()
    assert sheet["stats"]["results_recorded"] == 0

    # 3. Valid bulk recording
    valid_batch = client.post(f"/api/exams/{exam_id}/results/bulk", json={
        "records": [
            {"student_id": s1, "status": "attended", "score": 85.5},
            {"student_id": s2, "status": "absent"}
        ]
    }, headers=headers)
    assert valid_batch.status_code == 200
    assert valid_batch.json()["count"] == 2

    # Verify sheet stats
    sheet = client.get(f"/api/exams/{exam_id}/results", headers=headers).json()
    assert sheet["stats"]["results_recorded"] == 2
    assert sheet["stats"]["attended_count"] == 1
    assert sheet["stats"]["absent_count"] == 1


# ==========================================
# --- Test 4: Completion & Cancellation Guards ---
# ==========================================

def test_completion_and_cancellation_guards(client):
    headers = _create_teacher_and_login(client)

    grp_id = client.post("/api/groups", json={"name": "مجموعة الجغرافيا", "grade_level": "1_sec"}, headers=headers).json()["id"]
    s_id = client.post("/api/students", json={"full_name": "سيف الدين", "phone": "01000000031", "grade_level": "1_sec"}, headers=headers).json()["id"]
    _enroll_student(client, grp_id, s_id, headers)

    exam_id = client.post("/api/exams", json={
        "group_id": grp_id,
        "title": "امتحان التضاريس",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers).json()["id"]

    # Record a score of 45 for student
    client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": s_id,
        "status": "attended",
        "score": 45
    }, headers=headers)

    # 1. Unsafe edit guard: lowering max_score below recorded score (45) is blocked
    low_max_resp = client.put(f"/api/exams/{exam_id}", json={
        "max_score": 40
    }, headers=headers)
    assert low_max_resp.status_code == 400
    assert "أعلى درجة: 45.0" in low_max_resp.json()["detail"]

    # 2. Mark exam as completed
    comp_resp = client.post(f"/api/exams/{exam_id}/complete", headers=headers)
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # Once completed: altering scores configuration is forbidden
    alter_completed = client.put(f"/api/exams/{exam_id}", json={
        "max_score": 60
    }, headers=headers)
    assert alter_completed.status_code == 400
    assert "امتحان مكتمل" in alter_completed.json()["detail"]

    # BUT authorized correction of student grade is STILL permitted
    grade_corr = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": s_id,
        "status": "attended",
        "score": 48
    }, headers=headers)
    assert grade_corr.status_code == 200
    assert grade_corr.json()["score"] == 48.0

    # 3. Create another exam to test cancellation
    exam_to_cancel = client.post("/api/exams", json={
        "group_id": grp_id,
        "title": "امتحان ملغى لاحقاً",
        "exam_date": "2026-10-29",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers).json()["id"]

    # Cancel the exam
    cancel_resp = client.post(f"/api/exams/{exam_to_cancel}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Recording grades on cancelled exam is STRICTLY forbidden
    cancel_record = client.post(f"/api/exams/{exam_to_cancel}/results", json={
        "student_id": s_id,
        "status": "attended",
        "score": 30
    }, headers=headers)
    assert cancel_record.status_code == 400
    assert "امتحان ملغى" in cancel_record.json()["detail"]


# ==========================================
# --- Test 5: Exact Statistics & Zero-Fabrication Protection ---
# ==========================================

def test_statistics_and_zero_fabrication(client):
    headers = _create_teacher_and_login(client)

    grp_id = client.post("/api/groups", json={"name": "مجموعة الإحصاء", "grade_level": "3_sec"}, headers=headers).json()["id"]

    # 5 Students
    s_ids = []
    for i in range(5):
        sid = client.post("/api/students", json={
            "full_name": f"طالب تجربة {i+1}",
            "phone": f"0105555555{i}",
            "grade_level": "3_sec"
        }, headers=headers).json()["id"]
        s_ids.append(sid)
        _enroll_student(client, grp_id, sid, headers)

    exam_id = client.post("/api/exams", json={
        "group_id": grp_id,
        "title": "امتحان الإحصاء والاحتمالات",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25
    }, headers=headers).json()["id"]

    # Student 1: 40 (Passed)
    # Student 2: 50 (Passed, Highest)
    # Student 3: 20 (Failed, Lowest)
    # Student 4: Absent (NO score!)
    # Student 5: Excused (NO score!)
    client.post(f"/api/exams/{exam_id}/results/bulk", json={
        "records": [
            {"student_id": s_ids[0], "status": "attended", "score": 40},
            {"student_id": s_ids[1], "status": "attended", "score": 50},
            {"student_id": s_ids[2], "status": "attended", "score": 20},
            {"student_id": s_ids[3], "status": "absent"},
            {"student_id": s_ids[4], "status": "excused"},
        ]
    }, headers=headers)

    sheet = client.get(f"/api/exams/{exam_id}/results", headers=headers).json()
    stats = sheet["stats"]

    assert stats["total_enrolled"] == 5
    assert stats["results_recorded"] == 5
    assert stats["results_pending"] == 0
    assert stats["attended_count"] == 3
    assert stats["absent_count"] == 1
    assert stats["excused_count"] == 1
    assert stats["pass_count"] == 2
    assert stats["fail_count"] == 1

    # Pass rate: 2 passed out of 3 attended = 66.7% (NOT 2 / 5!)
    assert stats["pass_rate"] == 66.7

    # Average score: (40 + 50 + 20) / 3 = 110 / 3 = 36.7 (absent/excused NEVER counted as 0.0!)
    assert stats["average_score"] == 36.7

    # Average percentage: (36.7 / 50) * 100 = 73.4%
    assert stats["average_percentage"] == 73.4

    assert stats["highest_score"] == 50.0
    assert stats["lowest_score"] == 20.0


# ==========================================
# --- Test 6: Assistant Permissions & RBAC ---
# ==========================================

def test_assistant_permissions_rbac(client):
    teacher_headers = _create_teacher_and_login(client, username="mr_owner_rbac")

    grp_id = client.post("/api/groups", json={"name": "مجموعة اللغات", "grade_level": "1_sec"}, headers=teacher_headers).json()["id"]
    s_id = client.post("/api/students", json={"full_name": "طالب أ", "phone": "01099999991", "grade_level": "1_sec"}, headers=teacher_headers).json()["id"]
    _enroll_student(client, grp_id, s_id, teacher_headers)

    exam_id = client.post("/api/exams", json={
        "group_id": grp_id,
        "title": "امتحان اللغة الإنجليزية",
        "exam_date": "2026-10-28",
        "max_score": 100,
        "passing_score": 50
    }, headers=teacher_headers).json()["id"]

    # 1. Create Assistant A: NO grade permissions
    client.post("/api/users/assistants", json={
        "username": "assistant_none",
        "full_name": "مساعد بدون صلاحيات درجات",
        "phone": "01099999992",
        "password": "AssistantPass123!",
        "permissions": {
            "can_view_grades": False,
            "can_enter_grades": False,
            "can_manage_exams": False
        }
    }, headers=teacher_headers)
    a_none_headers = _login(client, "assistant_none", "AssistantPass123!")

    # Assistant A cannot view exams
    assert client.get("/api/exams", headers=a_none_headers).status_code == 403
    assert client.get(f"/api/exams/{exam_id}", headers=a_none_headers).status_code == 403
    assert client.get(f"/api/exams/{exam_id}/results", headers=a_none_headers).status_code == 403
    assert client.post(f"/api/exams/{exam_id}/results", json={"student_id": s_id, "status": "attended", "score": 80}, headers=a_none_headers).status_code == 403

    # 2. Create Assistant B: can_view_grades ONLY
    client.post("/api/users/assistants", json={
        "username": "assistant_viewer",
        "full_name": "مساعد قارئ درجات فقط",
        "phone": "01099999993",
        "password": "AssistantPass123!",
        "permissions": {
            "can_view_grades": True,
            "can_enter_grades": False,
            "can_manage_exams": False
        }
    }, headers=teacher_headers)
    a_view_headers = _login(client, "assistant_viewer", "AssistantPass123!")

    # Assistant B CAN read exams and results
    assert client.get("/api/exams", headers=a_view_headers).status_code == 200
    assert client.get(f"/api/exams/{exam_id}/results", headers=a_view_headers).status_code == 200
    # Assistant B CANNOT create exam or enter grade
    assert client.post("/api/exams", json={"group_id": grp_id, "title": "اختبار", "exam_date": "2026-10-28", "max_score": 50, "passing_score": 25}, headers=a_view_headers).status_code == 403
    assert client.post(f"/api/exams/{exam_id}/results", json={"student_id": s_id, "status": "attended", "score": 80}, headers=a_view_headers).status_code == 403

    # 3. Create Assistant C: can_enter_grades ONLY
    client.post("/api/users/assistants", json={
        "username": "assistant_recorder",
        "full_name": "مساعد راصد درجات",
        "phone": "01099999994",
        "password": "AssistantPass123!",
        "permissions": {
            "can_view_grades": False,
            "can_enter_grades": True,
            "can_manage_exams": False
        }
    }, headers=teacher_headers)
    a_rec_headers = _login(client, "assistant_recorder", "AssistantPass123!")

    # Assistant C can view results sheet and record single/bulk results
    assert client.get(f"/api/exams/{exam_id}/results", headers=a_rec_headers).status_code == 200
    rec_resp = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": s_id,
        "status": "attended",
        "score": 92
    }, headers=a_rec_headers)
    assert rec_resp.status_code == 200
    # Assistant C CANNOT create/update/delete exam
    assert client.post("/api/exams", json={"group_id": grp_id, "title": "اختبار", "exam_date": "2026-10-28", "max_score": 50, "passing_score": 25}, headers=a_rec_headers).status_code == 403
    assert client.delete(f"/api/exams/{exam_id}", headers=a_rec_headers).status_code == 403

    # 4. Create Assistant D: can_manage_exams
    client.post("/api/users/assistants", json={
        "username": "assistant_manager",
        "full_name": "مساعد مدير امتحانات",
        "phone": "01099999995",
        "password": "AssistantPass123!",
        "permissions": {
            "can_view_grades": True,
            "can_enter_grades": True,
            "can_manage_exams": True
        }
    }, headers=teacher_headers)
    a_mgr_headers = _login(client, "assistant_manager", "AssistantPass123!")

    # Assistant D can create, complete, and delete exams
    new_ex = client.post("/api/exams", json={
        "group_id": grp_id,
        "title": "امتحان مديره المساعد",
        "exam_date": "2026-10-30",
        "max_score": 50,
        "passing_score": 25
    }, headers=a_mgr_headers)
    assert new_ex.status_code == 201


# ==========================================
# --- Test 7: Tenant Isolation for Exams ---
# ==========================================

def test_tenant_isolation_exams(client, db_session):
    # Teacher 1
    t1_headers = _create_teacher_and_login(client, username="teacher_one_exam")
    g1_id = client.post("/api/groups", json={"name": "مجموعة أستاذ 1", "grade_level": "1_sec"}, headers=t1_headers).json()["id"]
    s1_id = client.post("/api/students", json={"full_name": "طالب أستاذ 1", "phone": "01011111111", "grade_level": "1_sec"}, headers=t1_headers).json()["id"]
    _enroll_student(client, g1_id, s1_id, t1_headers)
    e1_id = client.post("/api/exams", json={
        "group_id": g1_id,
        "title": "امتحان أستاذ 1 الخاص",
        "exam_date": "2026-10-28",
        "max_score": 50,
        "passing_score": 25
    }, headers=t1_headers).json()["id"]

    # Teacher 2 (Directly inserted into DB to have 2 isolated teachers)
    t2_id = str(uuid.uuid4())
    t2 = Teacher(
        id=t2_id,
        username="teacher_two_exam",
        full_name="Teacher Two",
        phone="01022222222",
        hashed_password=hash_password("TeacherPass2026!")
    )
    db_session.add(t2)
    db_session.commit()

    t2_headers = _login(client, "teacher_two_exam", "TeacherPass2026!")

    # 1. Teacher 2 cannot view Teacher 1's exams in list
    t2_list = client.get("/api/exams", headers=t2_headers).json()
    assert len(t2_list) == 0

    # 2. Teacher 2 cannot get Teacher 1's exam
    assert client.get(f"/api/exams/{e1_id}", headers=t2_headers).status_code == 404

    # 3. Teacher 2 cannot update or delete Teacher 1's exam
    assert client.put(f"/api/exams/{e1_id}", json={"title": "محاولة اختراق"}, headers=t2_headers).status_code == 404
    assert client.delete(f"/api/exams/{e1_id}", headers=t2_headers).status_code == 404

    # 4. Teacher 2 cannot view results sheet or record results
    assert client.get(f"/api/exams/{e1_id}/results", headers=t2_headers).status_code == 404
    assert client.post(f"/api/exams/{e1_id}/results", json={"student_id": s1_id, "status": "attended", "score": 40}, headers=t2_headers).status_code == 400

    # 5. Teacher 2 cannot view reports of Teacher 1's student or group
    assert client.get(f"/api/exams/reports/student/{s1_id}", headers=t2_headers).status_code == 404
    assert client.get(f"/api/exams/reports/group/{g1_id}", headers=t2_headers).status_code == 404


# ==========================================
# --- Test 8: Student and Group Reports ---
# ==========================================

def test_student_and_group_reports(client):
    headers = _create_teacher_and_login(client)

    grp_id = client.post("/api/groups", json={"name": "مجموعة التقارير", "grade_level": "2_sec"}, headers=headers).json()["id"]
    st_id = client.post("/api/students", json={"full_name": "مريم أحمد", "phone": "01077777771", "grade_level": "2_sec"}, headers=headers).json()["id"]
    _enroll_student(client, grp_id, st_id, headers)

    # Exam 1: Scored 40/50 -> Pass
    e1_id = client.post("/api/exams", json={"group_id": grp_id, "title": "امتحان 1", "exam_date": "2026-10-10", "max_score": 50, "passing_score": 25}, headers=headers).json()["id"]
    client.post(f"/api/exams/{e1_id}/results", json={"student_id": st_id, "status": "attended", "score": 40}, headers=headers)

    # Exam 2: Scored 15/50 -> Fail
    e2_id = client.post("/api/exams", json={"group_id": grp_id, "title": "امتحان 2", "exam_date": "2026-10-17", "max_score": 50, "passing_score": 25}, headers=headers).json()["id"]
    client.post(f"/api/exams/{e2_id}/results", json={"student_id": st_id, "status": "attended", "score": 15}, headers=headers)

    # Exam 3: Cancelled
    e3_id = client.post("/api/exams", json={"group_id": grp_id, "title": "امتحان 3 ملغى", "exam_date": "2026-10-24", "max_score": 50, "passing_score": 25}, headers=headers).json()["id"]
    client.post(f"/api/exams/{e3_id}/cancel", headers=headers)

    # 1. Student Report
    st_rep = client.get(f"/api/exams/reports/student/{st_id}", headers=headers).json()
    assert st_rep["student_id"] == st_id
    assert st_rep["total_exams"] == 2  # Cancelled exam excluded from totals
    assert st_rep["attended_count"] == 2
    assert st_rep["passed_count"] == 1
    assert st_rep["failed_count"] == 1
    assert st_rep["overall_pass_rate"] == 50.0
    # Average percentage: (80% + 30%) / 2 = 55.0%
    assert st_rep["average_percentage"] == 55.0

    # 2. Group Summary
    grp_rep = client.get(f"/api/exams/reports/group/{grp_id}", headers=headers).json()
    assert grp_rep["group_id"] == grp_id
    assert grp_rep["total_exams"] == 2  # Active exams count
    assert grp_rep["total_students"] == 1
    assert grp_rep["average_pass_rate"] == 50.0
    assert grp_rep["average_group_score_percentage"] == 55.0
