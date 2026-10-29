import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.main import app
from app.repositories.user_repo import UserRepository
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


def test_students_crud_and_validation(client, db_session):
    """
    Test full lifecycle of students: create, read, search, filter, update, soft-delete,
    and validation of grade levels.
    """
    # 1. Setup teacher
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_stud", full_name="أ. فهد الكردي", phone="01011112222", password="StrongPassword1!"
    )
    headers = _login(client, "teacher_stud", "StrongPassword1!")

    # 2. Reject invalid grade
    invalid_payload = {
        "full_name": "طالب تجريبي",
        "grade_level": "4_sec",  # Invalid
        "phone": "01099998888"
    }
    resp = client.post("/api/students", json=invalid_payload, headers=headers)
    assert resp.status_code == 422

    # 3. Create valid student
    valid_payload = {
        "full_name": "عمر محمود حسن",
        "grade_level": "1_sec",
        "phone": "01012345678",
        "parent_name": "محمود حسن",
        "parent_phone": "01123456789",
        "address": "الجيزة، الدقي",
        "notes": "متفوق دراسياً"
    }
    resp = client.post("/api/students", json=valid_payload, headers=headers)
    assert resp.status_code == 201
    student_a = resp.json()
    assert student_a["full_name"] == "عمر محمود حسن"
    assert student_a["grade_level"] == "1_sec"
    assert student_a["grade_label"] == "الصف الأول الثانوي"
    assert student_a["phone"] == "01012345678"
    assert student_a["group_count"] == 0

    # 4. Support non-unique phones (e.g. brother with same student or parent phone)
    brother_payload = {
        "full_name": "يوسف محمود حسن",
        "grade_level": "2_sec",
        "phone": "01012345678",  # Same phone allowed
        "parent_name": "محمود حسن",
        "parent_phone": "01123456789"
    }
    resp_bro = client.post("/api/students", json=brother_payload, headers=headers)
    assert resp_bro.status_code == 201
    student_b = resp_bro.json()
    assert student_b["full_name"] == "يوسف محمود حسن"

    # 5. Search by name
    search_resp = client.get("/api/students?q=يوسف", headers=headers)
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) == 1
    assert results[0]["id"] == student_b["id"]

    # 6. Search by parent phone
    search_phone_resp = client.get("/api/students?q=01123456789", headers=headers)
    assert search_phone_resp.status_code == 200
    assert len(search_phone_resp.json()) == 2

    # 7. Filter by grade
    filter_grade_resp = client.get("/api/students?grade_level=1_sec", headers=headers)
    assert filter_grade_resp.status_code == 200
    assert len(filter_grade_resp.json()) == 1
    assert filter_grade_resp.json()[0]["id"] == student_a["id"]

    # 8. Update student
    update_payload = {
        "full_name": "عمر محمود حسن المعدل",
        "address": "القاهرة، المعادي"
    }
    update_resp = client.put(f"/api/students/{student_a['id']}", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["full_name"] == "عمر محمود حسن المعدل"
    assert update_resp.json()["address"] == "القاهرة، المعادي"

    # 9. Soft-delete student
    del_resp = client.delete(f"/api/students/{student_a['id']}", headers=headers)
    assert del_resp.status_code == 200

    # Verify deleted student is excluded from list
    list_after_del = client.get("/api/students", headers=headers)
    assert list_after_del.status_code == 200
    ids_after_del = [s["id"] for s in list_after_del.json()]
    assert student_a["id"] not in ids_after_del
    assert student_b["id"] in ids_after_del


def test_groups_crud_and_enrollment_lifecycle(client, db_session):
    """
    Test full lifecycle of groups: create, update, soft-delete, enrollment,
    duplicate rejection (409), grade mismatch rejection (400), and unenrollment.
    """
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_grp", full_name="أ. وائل شريف", phone="01033334444", password="StrongPassword1!"
    )
    headers = _login(client, "teacher_grp", "StrongPassword1!")

    # 1. Create students of different grades
    st1 = client.post("/api/students", json={
        "full_name": "طالب أولى", "grade_level": "1_sec", "phone": "01000000001"
    }, headers=headers).json()

    st2 = client.post("/api/students", json={
        "full_name": "طالب تانية", "grade_level": "2_sec", "phone": "01000000002"
    }, headers=headers).json()

    # 2. Create group for 1st secondary
    grp1 = client.post("/api/groups", json={
        "name": "مجموعة السبت والأربعاء 4 عصراً",
        "grade_level": "1_sec",
        "subject": "فيزياء",
        "schedule_details": "السبت والأربعاء من 4 إلى 6 م"
    }, headers=headers).json()

    assert grp1["name"] == "مجموعة السبت والأربعاء 4 عصراً"
    assert grp1["grade_level"] == "1_sec"
    assert grp1["grade_label"] == "الصف الأول الثانوي"
    assert grp1["student_count"] == 0

    # 3. Enroll compatible student
    enroll_resp = client.post(f"/api/groups/{grp1['id']}/students", json={"student_id": st1["id"]}, headers=headers)
    assert enroll_resp.status_code == 201

    # Verify group student count is now 1
    grp1_check = client.get(f"/api/groups/{grp1['id']}", headers=headers).json()
    assert grp1_check["student_count"] == 1

    # Verify student group list and count
    st1_check = client.get(f"/api/students/{st1['id']}", headers=headers).json()
    assert st1_check["group_count"] == 1
    assert len(st1_check["groups"]) == 1
    assert st1_check["groups"][0]["id"] == grp1["id"]

    # 4. Reject duplicate active enrollment -> 409 Conflict
    dup_resp = client.post(f"/api/groups/{grp1['id']}/students", json={"student_id": st1["id"]}, headers=headers)
    assert dup_resp.status_code == 409

    # 5. Reject grade mismatch (2_sec student into 1_sec group) -> 400 Bad Request
    mismatch_resp = client.post(f"/api/groups/{grp1['id']}/students", json={"student_id": st2["id"]}, headers=headers)
    assert mismatch_resp.status_code == 400
    assert "Grade level mismatch" in mismatch_resp.json()["detail"]

    # 6. List enrolled students in group
    enrolled_resp = client.get(f"/api/groups/{grp1['id']}/students", headers=headers)
    assert enrolled_resp.status_code == 200
    assert len(enrolled_resp.json()) == 1
    assert enrolled_resp.json()[0]["student_id"] == st1["id"]

    # 7. Unenroll student
    unenroll_resp = client.delete(f"/api/groups/{grp1['id']}/students/{st1['id']}", headers=headers)
    assert unenroll_resp.status_code == 200

    # Count drops to 0
    grp1_after_unenroll = client.get(f"/api/groups/{grp1['id']}", headers=headers).json()
    assert grp1_after_unenroll["student_count"] == 0

    # 8. Re-enrollment after unenrollment reactivates cleanly
    re_enroll = client.post(f"/api/groups/{grp1['id']}/students", json={"student_id": st1["id"]}, headers=headers)
    assert re_enroll.status_code == 201
    grp1_re_check = client.get(f"/api/groups/{grp1['id']}", headers=headers).json()
    assert grp1_re_check["student_count"] == 1

    # 9. Soft-delete group deactivates memberships
    del_grp = client.delete(f"/api/groups/{grp1['id']}", headers=headers)
    assert del_grp.status_code == 200

    # Student groups list now shows 0 active groups
    st1_after_grp_del = client.get(f"/api/students/{st1['id']}", headers=headers).json()
    assert st1_after_grp_del["group_count"] == 0


def test_tenant_isolation_and_cross_teacher_security(client, db_session):
    """
    Verify strict isolation between distinct teachers:
    1. Teacher B cannot read, update, delete Teacher A's students or groups.
    2. Teacher B cannot enroll Teacher A's student into Teacher B's group.
    3. Teacher B cannot enroll Teacher B's student into Teacher A's group.
    """
    teacher_a = UserRepository.create_teacher(
        db_session, username="teacher_iso_a", full_name="أستاذ أ", phone="01011110001", password="StrongPassword1!"
    )
    teacher_b = UserRepository.create_teacher(
        db_session, username="teacher_iso_b", full_name="أستاذ ب", phone="01011110002", password="StrongPassword1!"
    )

    headers_a = _login(client, "teacher_iso_a", "StrongPassword1!")
    headers_b = _login(client, "teacher_iso_b", "StrongPassword1!")

    # Teacher A creates student and group
    st_a = client.post("/api/students", json={
        "full_name": "طالب المستأجر أ", "grade_level": "1_sec", "phone": "01000001111"
    }, headers=headers_a).json()

    grp_a = client.post("/api/groups", json={
        "name": "مجموعة المستأجر أ", "grade_level": "1_sec"
    }, headers=headers_a).json()

    # Teacher B creates student and group
    st_b = client.post("/api/students", json={
        "full_name": "طالب المستأجر ب", "grade_level": "1_sec", "phone": "01000002222"
    }, headers=headers_b).json()

    grp_b = client.post("/api/groups", json={
        "name": "مجموعة المستأجر ب", "grade_level": "1_sec"
    }, headers=headers_b).json()

    # 1. Teacher B cannot access Teacher A's student -> 404
    assert client.get(f"/api/students/{st_a['id']}", headers=headers_b).status_code == 404
    assert client.put(f"/api/students/{st_a['id']}", json={"full_name": "اختراق"}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/students/{st_a['id']}", headers=headers_b).status_code == 404

    # 2. Teacher B cannot access Teacher A's group -> 404
    assert client.get(f"/api/groups/{grp_a['id']}", headers=headers_b).status_code == 404
    assert client.put(f"/api/groups/{grp_a['id']}", json={"name": "اختراق"}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/groups/{grp_a['id']}", headers=headers_b).status_code == 404

    # 3. Cross-tenant enrollment: Teacher B attempts to add Teacher A's student into Teacher B's group -> 404
    cross_resp_1 = client.post(f"/api/groups/{grp_b['id']}/students", json={"student_id": st_a["id"]}, headers=headers_b)
    assert cross_resp_1.status_code == 404

    # 4. Cross-tenant enrollment: Teacher B attempts to add Teacher B's student into Teacher A's group -> 404
    cross_resp_2 = client.post(f"/api/groups/{grp_a['id']}/students", json={"student_id": st_b["id"]}, headers=headers_b)
    assert cross_resp_2.status_code == 404


def test_assistant_permissions_for_students_and_groups(client, db_session):
    """
    Verify fine-grained assistant permissions:
    - Assistant with can_manage_students=True can perform student & group operations.
    - Assistant with can_manage_students=False receives 403 Forbidden.
    """
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_perm", full_name="أ. صلاح فوزي", phone="01077778888", password="StrongPassword1!"
    )
    headers_teacher = _login(client, "teacher_perm", "StrongPassword1!")

    # 1. Create Assistant with can_manage_students = True
    client.post("/api/users/assistants", json={
        "username": "ass_authorized",
        "full_name": "مساعد مأذون له",
        "phone": "01099990001",
        "password": "AssistantPass1!",
        "permissions": {"can_manage_students": True}
    }, headers=headers_teacher)

    # 2. Create Assistant with can_manage_students = False
    client.post("/api/users/assistants", json={
        "username": "ass_unauthorized",
        "full_name": "مساعد محظور",
        "phone": "01099990002",
        "password": "AssistantPass1!",
        "permissions": {"can_manage_students": False}
    }, headers=headers_teacher)

    # Login both assistants
    headers_auth = _login(client, "ass_authorized", "AssistantPass1!")
    headers_unauth = _login(client, "ass_unauthorized", "AssistantPass1!")

    # 3. Unauthorized assistant receives 403 on students and groups endpoints
    unauth_st_post = client.post("/api/students", json={
        "full_name": "طالب غير مسموح", "grade_level": "1_sec", "phone": "01011119999"
    }, headers=headers_unauth)
    assert unauth_st_post.status_code == 403

    unauth_st_get = client.get("/api/students", headers=headers_unauth)
    assert unauth_st_get.status_code == 403

    unauth_grp_post = client.post("/api/groups", json={
        "name": "مجموعة غير مسموحة", "grade_level": "1_sec"
    }, headers=headers_unauth)
    assert unauth_grp_post.status_code == 403

    # 4. Authorized assistant succeeds on students and groups
    auth_st_post = client.post("/api/students", json={
        "full_name": "طالب مسموح بواسطة مساعد", "grade_level": "1_sec", "phone": "01011119999"
    }, headers=headers_auth)
    assert auth_st_post.status_code == 201
    created_st_id = auth_st_post.json()["id"]

    auth_grp_post = client.post("/api/groups", json={
        "name": "مجموعة بواسطة مساعد", "grade_level": "1_sec"
    }, headers=headers_auth)
    assert auth_grp_post.status_code == 201
    created_grp_id = auth_grp_post.json()["id"]

    # Authorized assistant enrolls student
    auth_enroll = client.post(
        f"/api/groups/{created_grp_id}/students",
        json={"student_id": created_st_id},
        headers=headers_auth
    )
    assert auth_enroll.status_code == 201
