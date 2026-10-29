import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.main import app
from app.repositories.user_repo import UserRepository
from app.schemas.user import AssistantPermissions

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

def test_query_level_teacher_isolation(client, db_session):
    """
    Verify strict tenant data isolation at the query/repository level.
    Teacher B must NEVER be able to read, update, or delete Teacher A's assistant,
    even when providing the exact target ID.
    """
    # 1. Create two distinct teachers directly in database
    teacher_a = UserRepository.create_teacher(
        db_session, username="teacher_a", full_name="الأستاذ أ", phone="01011111111", password="PasswordA123!"
    )
    teacher_b = UserRepository.create_teacher(
        db_session, username="teacher_b", full_name="الأستاذ ب", phone="01022222222", password="PasswordB123!"
    )

    # 2. Teacher A creates an assistant
    assistant_a = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher_a.id,
        username="assistant_a",
        full_name="مساعد أ",
        phone="01111111111",
        password="PassAssistantA1!",
        permissions={}
    )

    # 3. Test Repository Query-Level Isolation directly
    # Teacher A querying their own assistant -> Success
    res_a = UserRepository.get_assistant_by_id(db_session, teacher_id=teacher_a.id, assistant_id=assistant_a.id)
    assert res_a is not None
    assert res_a.id == assistant_a.id

    # Teacher B querying Teacher A's assistant -> Must return None
    res_b = UserRepository.get_assistant_by_id(db_session, teacher_id=teacher_b.id, assistant_id=assistant_a.id)
    assert res_b is None

    # Teacher B attempting update on Teacher A's assistant -> Must return None
    update_res = UserRepository.update_assistant(
        db_session, teacher_id=teacher_b.id, assistant_id=assistant_a.id, full_name="مخترق"
    )
    assert update_res is None

    # Teacher B attempting delete on Teacher A's assistant -> Must return False
    del_res = UserRepository.delete_assistant(
        db_session, teacher_id=teacher_b.id, assistant_id=assistant_a.id
    )
    assert del_res is False

    # 4. Test API-Level Isolation via HTTP Client
    # Login as Teacher B
    login_b = client.post("/api/auth/login", json={"username": "teacher_b", "password": "PasswordB123!"})
    token_b = login_b.json()["session_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Teacher B attempts GET /api/users/assistants/{assistant_a.id} -> Must return 404
    api_get_resp = client.get(f"/api/users/assistants/{assistant_a.id}", headers=headers_b)
    assert api_get_resp.status_code == 404

    # Teacher B attempts PUT /api/users/assistants/{assistant_a.id} -> Must return 404
    api_put_resp = client.put(
        f"/api/users/assistants/{assistant_a.id}",
        json={"full_name": "مخترق"},
        headers=headers_b
    )
    assert api_put_resp.status_code == 404

    # Teacher B attempts DELETE /api/users/assistants/{assistant_a.id} -> Must return 404
    api_del_resp = client.delete(f"/api/users/assistants/{assistant_a.id}", headers=headers_b)
    assert api_del_resp.status_code == 404

    # Verify Assistant A was NOT deleted and is still active
    check_a = UserRepository.get_assistant_by_id(db_session, teacher_id=teacher_a.id, assistant_id=assistant_a.id)
    assert check_a is not None
    assert check_a.is_deleted is False

def test_granular_permissions_enforcement(client, db_session, monkeypatch):
    """
    Verify fine-grained permission enforcement:
    - Default assistant has financial analytics and cash collection disabled.
    - Granting cash collection allows collection while still blocking financial analytics.
    - Assistant cannot access Teacher-only administrative routes.
    """
    monkeypatch.setattr("app.config.ENABLE_TEST_ENDPOINTS", True)

    # 1. Setup teacher and an assistant with default permissions
    teacher = UserRepository.create_teacher(
        db_session, username="mr_perm", full_name="أستاذ الصلاحيات", phone="01033333333", password="TeacherPerm1!"
    )
    assistant = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="ass_perm",
        full_name="مساعد صلاحيات",
        phone="01233333333",
        password="AssPermPass1!",
        permissions={
            "can_collect_cash": False,
            "can_view_financial_analytics": False
        }
    )

    # 2. Login as Assistant
    login_ass = client.post("/api/auth/login", json={"username": "ass_perm", "password": "AssPermPass1!"})
    ass_token = login_ass.json()["session_token"]
    ass_headers = {"Authorization": f"Bearer {ass_token}"}

    # 3. Assistant attempts Cash Collection -> 403 Forbidden (missing permission)
    resp_cash = client.post("/api/users/test-permissions/collect-cash", headers=ass_headers)
    assert resp_cash.status_code == 403
    assert "can_collect_cash" in resp_cash.json()["detail"]

    # 4. Assistant attempts Financial Analytics -> 403 Forbidden
    resp_fin = client.get("/api/users/test-permissions/financial-analytics", headers=ass_headers)
    assert resp_fin.status_code == 403
    assert "can_view_financial_analytics" in resp_fin.json()["detail"]

    # 5. Assistant attempts to create another assistant (Teacher-only) -> 403 Forbidden
    resp_admin = client.post("/api/users/assistants", json={
        "username": "sub_assistant",
        "full_name": "مساعد فرعي",
        "phone": "01044444444",
        "password": "SubPassword1!"
    }, headers=ass_headers)
    assert resp_admin.status_code == 403
    assert "Teacher account only" in resp_admin.json()["detail"]

    # 6. Teacher grants Assistant the 'can_collect_cash' permission only
    login_teacher = client.post("/api/auth/login", json={"username": "mr_perm", "password": "TeacherPerm1!"})
    teacher_token = login_teacher.json()["session_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    update_resp = client.put(
        f"/api/users/assistants/{assistant.id}",
        json={
            "permissions": {
                "can_collect_cash": True,
                "can_view_financial_analytics": False
            }
        },
        headers=teacher_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["can_collect_cash"] is True
    assert update_resp.json()["can_view_financial_analytics"] is False

    # 7. Assistant now retries Cash Collection -> MUST SUCCEED (200)
    retry_cash = client.post("/api/users/test-permissions/collect-cash", headers=ass_headers)
    assert retry_cash.status_code == 200
    assert retry_cash.json()["success"] is True

    # 8. Assistant STILL blocked from Financial Analytics -> 403 Forbidden
    retry_fin = client.get("/api/users/test-permissions/financial-analytics", headers=ass_headers)
    assert retry_fin.status_code == 403

    # 9. Teacher accesses both successfully without restriction
    t_cash = client.post("/api/users/test-permissions/collect-cash", headers=teacher_headers)
    assert t_cash.status_code == 200
    t_fin = client.get("/api/users/test-permissions/financial-analytics", headers=teacher_headers)
    assert t_fin.status_code == 200

def test_test_endpoints_disabled_by_default(client, db_session):
    """
    Verify test-only permission endpoints return 404 Not Found when ENABLE_TEST_ENDPOINTS is False.
    This guarantees zero exposure of test routes in default production environments.
    """
    # 1. Unauthenticated attempts must return 404, not 401
    resp_cash = client.post("/api/users/test-permissions/collect-cash")
    assert resp_cash.status_code == 404
    assert resp_cash.json()["detail"] == "Endpoint not found."

    resp_fin = client.get("/api/users/test-permissions/financial-analytics")
    assert resp_fin.status_code == 404
    assert resp_fin.json()["detail"] == "Endpoint not found."

    # 2. Authenticated attempts (even as Teacher) must also return 404
    teacher = UserRepository.create_teacher(
        db_session, username="mr_disabled_test", full_name="معلم معطل", phone="01099991111", password="Password123!"
    )
    login_resp = client.post("/api/auth/login", json={"username": "mr_disabled_test", "password": "Password123!"})
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_cash_auth = client.post("/api/users/test-permissions/collect-cash", headers=headers)
    assert resp_cash_auth.status_code == 404
    assert resp_cash_auth.json()["detail"] == "Endpoint not found."

    resp_fin_auth = client.get("/api/users/test-permissions/financial-analytics", headers=headers)
    assert resp_fin_auth.status_code == 404
    assert resp_fin_auth.json()["detail"] == "Endpoint not found."

def test_test_endpoints_enabled_via_config(client, db_session, monkeypatch):
    """
    Verify test-only endpoints become reachable when ENABLE_TEST_ENDPOINTS is explicitly enabled,
    while still enforcing full authentication and granular permissions.
    """
    monkeypatch.setattr("app.config.ENABLE_TEST_ENDPOINTS", True)

    # 1. Unauthenticated access -> 401 Unauthorized
    resp_unauth = client.post("/api/users/test-permissions/collect-cash")
    assert resp_unauth.status_code == 401

    # 2. Setup teacher and login
    teacher = UserRepository.create_teacher(
        db_session, username="mr_enabled_test", full_name="معلم مفعّل", phone="01088882222", password="Password123!"
    )
    login_teacher = client.post("/api/auth/login", json={"username": "mr_enabled_test", "password": "Password123!"})
    teacher_token = login_teacher.json()["session_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # 3. Teacher can access both endpoints -> 200 OK
    resp_cash_t = client.post("/api/users/test-permissions/collect-cash", headers=teacher_headers)
    assert resp_cash_t.status_code == 200
    assert resp_cash_t.json()["success"] is True

    resp_fin_t = client.get("/api/users/test-permissions/financial-analytics", headers=teacher_headers)
    assert resp_fin_t.status_code == 200
    assert resp_fin_t.json()["success"] is True

def test_tenant_isolation_put_update_assistant(client, db_session):
    """
    Verify API-level tenant isolation on PUT /api/users/assistants/{id}:
    Teacher B cannot modify Teacher A's assistant using a known assistant ID,
    and Assistant A's fields remain strictly unaltered in the database.
    """
    # 1. Setup Teacher A with an assistant
    teacher_a = UserRepository.create_teacher(
        db_session, username="teacher_put_a", full_name="أستاذ أ", phone="01011110001", password="PasswordA123!"
    )
    assistant_a = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher_a.id,
        username="assistant_put_a",
        full_name="الاسم الأصلي",
        phone="01111110001",
        password="PassAssistantA1!",
        permissions={"can_mark_attendance": True, "can_collect_cash": False}
    )

    # 2. Setup Teacher B
    teacher_b = UserRepository.create_teacher(
        db_session, username="teacher_put_b", full_name="أستاذ ب", phone="01022220002", password="PasswordB123!"
    )
    login_b = client.post("/api/auth/login", json={"username": "teacher_put_b", "password": "PasswordB123!"})
    token_b = login_b.json()["session_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Teacher B attempts PUT request targeting Assistant A's ID
    put_resp = client.put(
        f"/api/users/assistants/{assistant_a.id}",
        json={
            "full_name": "الاسم المخترق",
            "phone": "01999999999",
            "permissions": {"can_collect_cash": True}
        },
        headers=headers_b
    )
    assert put_resp.status_code == 404
    assert put_resp.json()["detail"] == "Assistant not found."

    # 4. Verify in DB that Assistant A remains completely unchanged
    db_session.expire_all()
    reloaded_a = UserRepository.get_assistant_by_id(db_session, teacher_id=teacher_a.id, assistant_id=assistant_a.id)
    assert reloaded_a.full_name == "الاسم الأصلي"
    assert reloaded_a.phone == "01111110001"
    assert reloaded_a.can_collect_cash is False

def test_tenant_isolation_get_list_assistants(client, db_session):
    """
    Verify API-level tenant isolation on GET /api/users/assistants:
    Listing assistants returns ONLY assistants belonging to the authenticated teacher.
    Assistants of other teachers are completely filtered out.
    """
    # 1. Setup Teacher 1 with 2 assistants
    t1 = UserRepository.create_teacher(
        db_session, username="teacher_list_1", full_name="معلم 1", phone="01012340001", password="Password123!"
    )
    ass_1a = UserRepository.create_assistant(
        db_session, teacher_id=t1.id, username="ass_1a", full_name="مساعد 1أ", phone="01111110011",
        password="PassAssistant1!", permissions={}
    )
    ass_1b = UserRepository.create_assistant(
        db_session, teacher_id=t1.id, username="ass_1b", full_name="مساعد 1ب", phone="01111110012",
        password="PassAssistant2!", permissions={}
    )

    # 2. Setup Teacher 2 with 1 assistant
    t2 = UserRepository.create_teacher(
        db_session, username="teacher_list_2", full_name="معلم 2", phone="01012340002", password="Password123!"
    )
    ass_2a = UserRepository.create_assistant(
        db_session, teacher_id=t2.id, username="ass_2a", full_name="مساعد 2أ", phone="01111110021",
        password="PassAssistant3!", permissions={}
    )

    # 3. Login as Teacher 1 and GET /api/users/assistants
    login_1 = client.post("/api/auth/login", json={"username": "teacher_list_1", "password": "Password123!"})
    token_1 = login_1.json()["session_token"]
    list_1_resp = client.get("/api/users/assistants", headers={"Authorization": f"Bearer {token_1}"})
    assert list_1_resp.status_code == 200
    list_1_data = list_1_resp.json()
    t1_ids = [item["id"] for item in list_1_data]

    assert len(list_1_data) == 2
    assert ass_1a.id in t1_ids
    assert ass_1b.id in t1_ids
    assert ass_2a.id not in t1_ids

    # 4. Login as Teacher 2 and GET /api/users/assistants
    login_2 = client.post("/api/auth/login", json={"username": "teacher_list_2", "password": "Password123!"})
    token_2 = login_2.json()["session_token"]
    list_2_resp = client.get("/api/users/assistants", headers={"Authorization": f"Bearer {token_2}"})
    assert list_2_resp.status_code == 200
    list_2_data = list_2_resp.json()
    t2_ids = [item["id"] for item in list_2_data]

    assert len(list_2_data) == 1
    assert ass_2a.id in t2_ids
    assert ass_1a.id not in t2_ids
    assert ass_1b.id not in t2_ids
