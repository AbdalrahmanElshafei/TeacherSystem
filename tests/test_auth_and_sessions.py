import pytest
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.models.user import UserSession
from app.main import app
from app.config import SESSION_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

# Setup clean in-memory test SQLite database using StaticPool
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

def test_first_run_setup_and_lock(client):
    """
    Verify first-run setup creates the initial teacher account,
    and subsequent attempts are permanently locked and rejected.
    """
    # 1. Check initial setup status
    status_resp = client.get("/api/auth/setup-status")
    assert status_resp.status_code == 200
    assert status_resp.json()["setup_required"] is True

    # 2. Complete first-run setup
    setup_data = {
        "username": "mr_ahmed",
        "full_name": "أحمد محمود",
        "phone": "01012345678",
        "password": "StrongPassword2026!"
    }
    resp = client.post("/api/auth/first-run-setup", json=setup_data)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "mr_ahmed"
    assert "password" not in data
    assert "hashed_password" not in data

    # 3. Check setup status is now False
    status_resp = client.get("/api/auth/setup-status")
    assert status_resp.json()["setup_required"] is False

    # 4. Attempt second setup (must be rejected)
    resp_second = client.post("/api/auth/first-run-setup", json=setup_data)
    assert resp_second.status_code == 400
    assert "already complete" in resp_second.json()["detail"]

def test_login_and_cookie_attributes(client):
    """
    Verify login sets HttpOnly session cookie and accessible CSRF cookie
    with strict security attributes (SameSite=lax, Path=/, Max-Age).
    Also verify logout invalidates cookies with max-age=0.
    """
    # 1. Setup teacher
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_hassan",
        "full_name": "حسن علي",
        "phone": "01098765432",
        "password": "PasswordHassan123"
    })

    # 2. Login
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_hassan",
        "password": "PasswordHassan123"
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["success"] is True
    assert data["user_type"] == "teacher"
    assert "session_token" in data
    assert "csrf_token" in data

    # 3. Verify Cookie presence
    cookies = login_resp.cookies
    assert SESSION_COOKIE_NAME in cookies
    assert CSRF_COOKIE_NAME in cookies

    # 4. Verify Raw Set-Cookie Header Attributes
    set_cookie_headers = login_resp.headers.get_list("set-cookie")
    assert len(set_cookie_headers) >= 2

    session_header = next((h for h in set_cookie_headers if h.startswith(f"{SESSION_COOKIE_NAME}=")), None)
    assert session_header is not None, "Missing Set-Cookie header for session"
    header_session_lower = session_header.lower()
    assert "httponly" in header_session_lower, "Session cookie MUST have HttpOnly flag"
    assert "samesite=lax" in header_session_lower, "Session cookie MUST have SameSite=lax"
    assert "path=/" in header_session_lower, "Session cookie MUST have Path=/"
    assert "max-age=86400" in header_session_lower, "Session cookie MUST have Max-Age=86400"

    csrf_header = next((h for h in set_cookie_headers if h.startswith(f"{CSRF_COOKIE_NAME}=")), None)
    assert csrf_header is not None, "Missing Set-Cookie header for CSRF"
    header_csrf_lower = csrf_header.lower()
    assert "httponly" not in header_csrf_lower, "CSRF cookie MUST NOT have HttpOnly flag so client JS can read it"
    assert "samesite=lax" in header_csrf_lower, "CSRF cookie MUST have SameSite=lax"
    assert "path=/" in header_csrf_lower, "CSRF cookie MUST have Path=/"
    assert "max-age=86400" in header_csrf_lower, "CSRF cookie MUST have Max-Age=86400"

    # 5. Verify Logout clears both cookies with max-age=0
    logout_resp = client.post("/api/auth/logout", headers={CSRF_HEADER_NAME: data["csrf_token"]})
    assert logout_resp.status_code == 200
    logout_cookie_headers = logout_resp.headers.get_list("set-cookie")
    logout_session_header = next((h for h in logout_cookie_headers if h.startswith(f"{SESSION_COOKIE_NAME}=")), None)
    assert logout_session_header is not None
    assert "max-age=0" in logout_session_header.lower()

def test_csrf_protection_on_cookie_auth(client):
    """
    Verify CSRF protection blocks mutating requests (POST) when authenticated via cookie
    if X-CSRF-Token is missing or invalid.
    """
    # 1. Setup teacher and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_khaled",
        "full_name": "خالد عمر",
        "phone": "01123456789",
        "password": "KhaledPassword1!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_khaled",
        "password": "KhaledPassword1!"
    })
    csrf_token = login_resp.json()["csrf_token"]

    # 2. Attempt POST request with cookies but WITHOUT X-CSRF-Token header -> MUST FAIL 403
    fail_resp = client.post("/api/users/assistants", json={
        "username": "assistant1",
        "full_name": "مساعد تجريبي",
        "phone": "01234567890",
        "password": "AssistantPass1"
    })
    assert fail_resp.status_code == 403
    assert "CSRF" in fail_resp.json()["detail"]

    # 3. Attempt POST request with invalid CSRF token -> MUST FAIL 403
    fail_invalid = client.post(
        "/api/users/assistants",
        json={
            "username": "assistant1",
            "full_name": "مساعد تجريبي",
            "phone": "01234567890",
            "password": "AssistantPass1"
        },
        headers={CSRF_HEADER_NAME: "wrong_fake_token"}
    )
    assert fail_invalid.status_code == 403

    # 4. Attempt POST request with VALID X-CSRF-Token header -> MUST SUCCEED 201
    success_resp = client.post(
        "/api/users/assistants",
        json={
            "username": "assistant1",
            "full_name": "مساعد تجريبي",
            "phone": "01234567890",
            "password": "AssistantPass1"
        },
        headers={CSRF_HEADER_NAME: csrf_token}
    )
    assert success_resp.status_code == 201

def test_bearer_token_auth_bypasses_csrf(client):
    """
    Verify that mobile/API clients using Authorization: Bearer <token>
    can perform POST requests without CSRF token because Bearer tokens are immune to CSRF.
    """
    # Setup teacher and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_mobile",
        "full_name": "مدرس موبايل",
        "phone": "01512345678",
        "password": "MobilePassword1!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_mobile",
        "password": "MobilePassword1!"
    })
    session_token = login_resp.json()["session_token"]

    # Clear cookies to simulate pure API / Mobile client
    client.cookies.clear()

    # Make request with Authorization: Bearer
    resp = client.post(
        "/api/users/assistants",
        json={
            "username": "mobile_assistant",
            "full_name": "مساعد موبايل",
            "phone": "01598765432",
            "password": "PassMobileAss1!"
        },
        headers={"Authorization": f"Bearer {session_token}"}
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "mobile_assistant"

def test_logout_immediate_revocation(client):
    """Verify logout revokes the session in the database immediately."""
    # Setup and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_logout",
        "full_name": "مدرس خروج",
        "phone": "01000000001",
        "password": "LogoutPass123!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_logout",
        "password": "LogoutPass123!"
    })
    session_token = login_resp.json()["session_token"]
    csrf_token = login_resp.json()["csrf_token"]

    # Verify session is valid
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200

    # Logout
    logout_resp = client.post("/api/auth/logout", headers={CSRF_HEADER_NAME: csrf_token})
    assert logout_resp.status_code == 200

    # Next attempt with same session token must fail (401)
    revoked_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {session_token}"})
    assert revoked_resp.status_code == 401

def test_database_stores_only_sha256_token_hash(client, db_session):
    """
    Verify that the database stores strictly the SHA-256 fingerprint,
    and the raw session token is NEVER stored in plaintext in SQLite.
    """
    # 1. Setup teacher and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_hash_test",
        "full_name": "مدرس اختبار البصمة",
        "phone": "01099999999",
        "password": "HashPassword123!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_hash_test",
        "password": "HashPassword123!"
    })
    raw_token = login_resp.json()["session_token"]
    assert len(raw_token) >= 48

    # 2. Query user_sessions table directly in SQLite
    sessions_in_db = db_session.query(UserSession).all()
    assert len(sessions_in_db) == 1
    stored_session = sessions_in_db[0]

    # 3. Assert raw token is NOT in database
    assert stored_session.session_token != raw_token
    assert raw_token not in stored_session.session_token

    # 4. Assert stored value is exactly the SHA-256 hex digest
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert stored_session.session_token == expected_hash
    assert len(stored_session.session_token) == 64

    # 5. Verify authentication with raw token succeeds
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "mr_hash_test"

def test_tampered_and_invalid_token_rejected(client):
    """Verify that random, malformed, or tampered tokens are rejected with 401."""
    # Setup and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_tamper",
        "full_name": "مدرس اختبار التلاعب",
        "phone": "01088888888",
        "password": "TamperPassword1!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_tamper",
        "password": "TamperPassword1!"
    })
    valid_token = login_resp.json()["session_token"]

    # Tamper with the last character
    tampered_token = valid_token[:-1] + ("A" if valid_token[-1] != "A" else "B")

    # Attempt with tampered token
    resp_tampered = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp_tampered.status_code == 401
    assert "Authentication required" in resp_tampered.json()["detail"] or "expired" in resp_tampered.json()["detail"]

    # Attempt with completely random token
    resp_random = client.get("/api/auth/me", headers={"Authorization": "Bearer completely_fake_token_value_xyz"})
    assert resp_random.status_code == 401

def test_session_expiration_rejection(client, db_session):
    """Verify that expired sessions are automatically rejected with 401."""
    # Setup and login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_expire",
        "full_name": "مدرس اختبار الانتهاء",
        "phone": "01077777777",
        "password": "ExpirePassword1!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_expire",
        "password": "ExpirePassword1!"
    })
    raw_token = login_resp.json()["session_token"]

    # Verify session is initially valid
    resp_valid = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert resp_valid.status_code == 200

    # Fast-forward session expiration to 1 hour in the past
    session_row = db_session.query(UserSession).first()
    assert session_row is not None
    session_row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    # Attempt request with expired session -> MUST FAIL 401
    resp_expired = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw_token}"})
    assert resp_expired.status_code == 401
    assert "expired" in resp_expired.json()["detail"]

def test_concurrent_first_run_setup_race_condition(client, db_session):
    """
    Test genuine concurrency on first-run setup:
    Multiple simultaneous setup requests must result in exactly ONE successful creation (201)
    and all others rejected (400), with exactly ONE Teacher in the database.
    """
    import concurrent.futures
    from app.models.user import Teacher

    num_concurrent = 5
    results = []

    def attempt_setup(i):
        payload = {
            "username": f"concurrent_teacher_{i}",
            "full_name": f"معلم متزامن {i}",
            "phone": f"0100000000{i}",
            "password": f"ConcurrentPass{i}!"
        }
        return client.post("/api/auth/first-run-setup", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [executor.submit(attempt_setup, i) for i in range(num_concurrent)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    status_codes = [r.status_code for r in results]
    assert status_codes.count(201) == 1, f"Expected exactly one 201, got: {status_codes}"
    assert status_codes.count(400) == num_concurrent - 1, f"Expected {num_concurrent - 1} 400s, got: {status_codes}"

    for r in results:
        if r.status_code == 400:
            assert "already complete" in r.json()["detail"]

    # Verify at database level
    teacher_count = db_session.query(Teacher).count()
    assert teacher_count == 1

def test_password_policy_enforcement_on_setup_and_assistant(client):
    """
    Verify uniform password strength policy on both First-Run Setup and Assistant creation:
    - Min 8 chars, max 128 chars.
    - Must contain at least one letter and at least one number.
    - Must reject blacklisted common passwords.
    """
    # 1. Setup rejects weak passwords (422 Unprocessable Entity)
    weak_cases = [
        ("short1", "too short"),
        ("NoNumbersAtAll", "no numbers"),
        ("1234567890", "no letters"),
        ("password123", "trivial common password"),
    ]
    for weak_pwd, reason in weak_cases:
        resp = client.post("/api/auth/first-run-setup", json={
            "username": "mr_policy",
            "full_name": "معلم السياسة",
            "phone": "01011112222",
            "password": weak_pwd
        })
        assert resp.status_code == 422, f"Expected 422 for {reason} password '{weak_pwd}', got {resp.status_code}"

    # 2. Setup accepts valid password complying with policy (201)
    setup_resp = client.post("/api/auth/first-run-setup", json={
        "username": "mr_policy",
        "full_name": "معلم السياسة",
        "phone": "01011112222",
        "password": "StrongPassword2026!"
    })
    assert setup_resp.status_code == 201

    # 3. Login as Teacher
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_policy",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Assistant creation rejects weak passwords (422)
    for weak_pwd, reason in weak_cases:
        ass_resp = client.post("/api/users/assistants", json={
            "username": f"ass_{reason.replace(' ', '_')}",
            "full_name": "مساعد تجريبي",
            "phone": "01033334444",
            "password": weak_pwd
        }, headers=headers)
        assert ass_resp.status_code == 422, f"Expected 422 for assistant {reason} password '{weak_pwd}', got {ass_resp.status_code}"

    # 5. Assistant creation accepts valid compliant password (201)
    valid_ass_resp = client.post("/api/users/assistants", json={
        "username": "valid_assistant",
        "full_name": "مساعد صالح",
        "phone": "01033334444",
        "password": "ValidAssPassword2026!"
    }, headers=headers)
    assert valid_ass_resp.status_code == 201

def test_login_rate_limiting_activation_and_recovery(client):
    """
    Verify login brute-force rate limiting:
    - 5 consecutive failed attempts trigger lockout (HTTP 429 Too Many Requests).
    - Retry-After header is returned.
    - Lockout blocks further attempts even with correct password.
    - Advances time deterministically to verify recovery without real-time sleep.
    """
    from app.core.rate_limiter import login_rate_limiter

    # 1. Setup teacher account
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_ratelimit",
        "full_name": "معلم الحماية",
        "phone": "01055556666",
        "password": "CorrectPassword123!"
    })

    # 2. Perform 5 consecutive failed login attempts (401 Unauthorized)
    for attempt in range(1, 6):
        fail_resp = client.post("/api/auth/login", json={
            "username": "mr_ratelimit",
            "password": f"WrongPassword_{attempt}!"
        })
        assert fail_resp.status_code == 401, f"Attempt {attempt} should return 401"

    # 3. 6th attempt must be rejected by Rate Limiter with 429 Too Many Requests
    rate_limited_resp = client.post("/api/auth/login", json={
        "username": "mr_ratelimit",
        "password": "WrongPassword_6!"
    })
    assert rate_limited_resp.status_code == 429
    assert "Retry-After" in rate_limited_resp.headers
    retry_after = int(rate_limited_resp.headers["Retry-After"])
    assert retry_after > 0
    assert "Too many failed login attempts" in rate_limited_resp.json()["detail"]

    # 4. Attempt with CORRECT password while lockout is active -> STILL 429
    blocked_correct = client.post("/api/auth/login", json={
        "username": "mr_ratelimit",
        "password": "CorrectPassword123!"
    })
    assert blocked_correct.status_code == 429

    # 5. Fast-forward time deterministically beyond lockout window (e.g. +305s)
    current_time = login_rate_limiter._time_provider()
    login_rate_limiter._time_provider = lambda: current_time + 305

    # 6. Attempt with correct password after lockout expired -> MUST SUCCEED (200 OK)
    recovered_resp = client.post("/api/auth/login", json={
        "username": "mr_ratelimit",
        "password": "CorrectPassword123!"
    })
    assert recovered_resp.status_code == 200
    assert recovered_resp.json()["success"] is True

    # 7. Restore time provider and verify lockout history was cleared on success
    login_rate_limiter._time_provider = current_time.__class__
    import time
    login_rate_limiter._time_provider = time.time

def test_login_rate_limiting_isolation_per_account(client):
    """
    Verify that triggering rate limiting on one user does not lock out other users
    even from the same client IP.
    """
    # 1. Setup teacher
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_victim",
        "full_name": "المعلم الأول",
        "phone": "01077778888",
        "password": "PasswordVictim1!"
    })
    login_teacher = client.post("/api/auth/login", json={
        "username": "mr_victim",
        "password": "PasswordVictim1!"
    })
    token = login_teacher.json()["session_token"]

    # 2. Create second user (assistant)
    client.post("/api/users/assistants", json={
        "username": "innocent_user",
        "full_name": "المساعد البريء",
        "phone": "01099990000",
        "password": "InnocentPass123!"
    }, headers={"Authorization": f"Bearer {token}"})

    # 3. Lock out mr_victim with 5 failed attempts
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "mr_victim", "password": "WrongPassword!"})

    # Check mr_victim is locked out (429)
    victim_resp = client.post("/api/auth/login", json={"username": "mr_victim", "password": "PasswordVictim1!"})
    assert victim_resp.status_code == 429

    # 4. Innocent user can still log in normally (200 OK)
    innocent_resp = client.post("/api/auth/login", json={"username": "innocent_user", "password": "InnocentPass123!"})
    assert innocent_resp.status_code == 200
    assert innocent_resp.json()["success"] is True

