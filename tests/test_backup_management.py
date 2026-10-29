import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.database import Base, get_db
from app.repositories.user_repo import UserRepository
from app.services.backup_service import (
    BackupService,
    verify_sqlite_backup,
    resolve_backup_directory,
    format_bytes,
    is_directory_writable
)
import app.models  # Ensure all models are registered

# In-memory database for API auth/session testing
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

    main_app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_app) as test_client:
        yield test_client
    main_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def isolated_backup_env(tmp_path, monkeypatch):
    """
    Sets up an isolated file-based database and temporary backup directory
    so test runs do not alter production or real system backup folders.
    """
    backup_dir = tmp_path / "test_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))

    # Create a real file-based SQLite database with dummy application data
    src_db_file = tmp_path / "test_active.db"
    src_engine = create_engine(f"sqlite:///{src_db_file.as_posix()}")
    Base.metadata.create_all(bind=src_engine)

    # Insert a sample row to ensure tables exist
    conn = src_engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS test_students (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO test_students (name) VALUES ('أحمد علي');")
        conn.commit()
    finally:
        conn.close()

    yield {
        "backup_dir": backup_dir,
        "src_db_file": src_db_file,
        "src_engine": src_engine
    }

    src_engine.dispose()


def test_format_bytes():
    """Verify human-readable byte formatting across sizes."""
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 500) == "500.0 KB"
    assert format_bytes(1024 * 1024 * 2) == "2.00 MB"


def test_verify_sqlite_backup_valid_and_invalid(tmp_path):
    """Test the SQLite integrity verification helper on valid, corrupted, and empty files."""
    valid_db = tmp_path / "valid.db"
    conn = sqlite3.connect(str(valid_db))
    conn.execute("CREATE TABLE sample_t (id INTEGER PRIMARY KEY);")
    conn.commit()
    conn.close()

    is_valid, msg = verify_sqlite_backup(valid_db)
    assert is_valid is True
    assert msg == "verified_ok"

    # 1. Non-existent file
    is_valid, msg = verify_sqlite_backup(tmp_path / "missing.db")
    assert is_valid is False
    assert msg == "file_not_found"

    # 2. Too small file
    tiny = tmp_path / "tiny.db"
    tiny.write_bytes(b"short")
    is_valid, msg = verify_sqlite_backup(tiny)
    assert is_valid is False
    assert msg == "file_too_small"

    # 3. Invalid magic header
    fake_header = tmp_path / "fake.db"
    fake_header.write_bytes(b"NOT_SQLITE_HEADER" * 10)
    is_valid, msg = verify_sqlite_backup(fake_header)
    assert is_valid is False
    assert msg == "invalid_sqlite_magic_header"

    # 4. Database with valid header but no user tables
    empty_db = tmp_path / "empty.db"
    conn_e = sqlite3.connect(str(empty_db))
    conn_e.execute("CREATE TABLE temp_t (id INT);")
    conn_e.execute("DROP TABLE temp_t;")
    conn_e.commit()
    conn_e.close()
    is_valid, msg = verify_sqlite_backup(empty_db)
    assert is_valid is False
    assert msg == "database_has_no_tables"


def test_backup_service_create_and_list(isolated_backup_env):
    """Test BackupService creation and listing with an isolated SQLite engine."""
    engine = isolated_backup_env["src_engine"]
    backup_dir = isolated_backup_env["backup_dir"]

    # 1. Create first backup
    meta1 = BackupService.create_backup(target_engine=engine, custom_backup_dir=backup_dir)
    assert meta1.filename.startswith("teachersystem_backup_")
    assert meta1.filename.endswith(".db")
    assert meta1.size_bytes > 0
    assert meta1.is_verified is True
    assert (backup_dir / meta1.filename).is_file()

    # 2. Create second backup (different second or collision handled)
    meta2 = BackupService.create_backup(target_engine=engine, custom_backup_dir=backup_dir)
    assert meta2.filename != meta1.filename
    assert (backup_dir / meta2.filename).is_file()

    # 3. List backups
    res = BackupService.list_backups(custom_backup_dir=backup_dir)
    assert res.total_count == 2
    assert len(res.backups) == 2
    # Verify sorted newest first
    assert res.backups[0].filename >= res.backups[1].filename
    assert res.total_size_bytes == meta1.size_bytes + meta2.size_bytes


def test_backup_service_download_path_traversal_protection(isolated_backup_env):
    """Test strict rejection of directory traversal attempts."""
    backup_dir = isolated_backup_env["backup_dir"]
    engine = isolated_backup_env["src_engine"]

    meta = BackupService.create_backup(target_engine=engine, custom_backup_dir=backup_dir)

    # Valid download resolution
    resolved = BackupService.get_backup_path_for_download(meta.filename, custom_backup_dir=backup_dir)
    assert resolved == (backup_dir / meta.filename).resolve()

    # Reject traversal sequences
    traversal_attacks = [
        "../secret.txt",
        "..\\secret.txt",
        "teachersystem_backup_20261028_120000.db/../../../etc/passwd",
        "nested/teachersystem_backup_20261028_120000.db",
        "non_existent.db",
        "teachersystem_backup_20261028_999999.db"
    ]
    for attack in traversal_attacks:
        with pytest.raises(Exception):
            BackupService.get_backup_path_for_download(attack, custom_backup_dir=backup_dir)


def test_backup_retention_pruning(isolated_backup_env):
    """Verify retention policy keeps max daily and weekly backups."""
    backup_dir = isolated_backup_env["backup_dir"]
    engine = isolated_backup_env["src_engine"]

    # Create 5 backups
    created = []
    for _ in range(5):
        m = BackupService.create_backup(target_engine=engine, custom_backup_dir=backup_dir)
        created.append(m.filename)

    # Prune with total keep of 3
    pruned = BackupService.prune_old_backups(custom_backup_dir=backup_dir, max_daily_keep=2, max_weekly_keep=1)
    assert len(pruned) == 2

    # Verify only 3 remaining
    listed = BackupService.list_backups(custom_backup_dir=backup_dir)
    assert listed.total_count == 3


def test_teacher_can_create_list_and_download_backup(client, db_session, isolated_backup_env, monkeypatch):
    """Test full API backup workflow for authenticated Teacher."""
    backup_dir = isolated_backup_env["backup_dir"]

    # Register teacher
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_main", full_name="الأستاذ المشرف", phone="01012345678", password="Password123!"
    )
    login_resp = client.post("/api/auth/login", json={"username": "teacher_main", "password": "Password123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create manual backup via POST /api/backups
    # Mock default_engine to isolated test engine so we don't hit production db
    monkeypatch.setattr("app.services.backup_service.default_engine", isolated_backup_env["src_engine"])

    create_resp = client.post("/api/backups", headers=headers)
    assert create_resp.status_code == 201, create_resp.text
    data = create_resp.json()
    assert "filename" in data
    assert data["is_verified"] is True
    filename = data["filename"]

    # 2. List backups via GET /api/backups
    list_resp = client.get("/api/backups", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total_count"] >= 1
    assert any(b["filename"] == filename for b in list_data["backups"])

    # 3. Download backup via GET /api/backups/{filename}/download
    download_resp = client.get(f"/api/backups/{filename}/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/x-sqlite3"
    assert download_resp.content.startswith(b"SQLite format 3\x00")


def test_assistant_denied_from_all_backup_endpoints(client, db_session, isolated_backup_env, monkeypatch):
    """Test that assistant accounts are strictly rejected with 403 Forbidden."""
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_t", full_name="المعلم", phone="01099999999", password="TeacherPassword123!"
    )
    assistant = UserRepository.create_assistant(
        db_session,
        teacher_id=teacher.id,
        username="assistant_sub",
        full_name="مساعد المعلم",
        phone="01188888888",
        password="AssistantPassword123!",
        permissions={
            "can_collect_cash": True,
            "can_view_student_payment_history": True,
            "can_view_financial_analytics": True
        }
    )

    login_resp = client.post("/api/auth/login", json={"username": "assistant_sub", "password": "AssistantPassword123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt POST /api/backups
    post_resp = client.post("/api/backups", headers=headers)
    assert post_resp.status_code == 403
    assert "restricted to the Teacher account only" in post_resp.json()["detail"]

    # Attempt GET /api/backups
    get_resp = client.get("/api/backups", headers=headers)
    assert get_resp.status_code == 403
    assert "restricted to the Teacher account only" in get_resp.json()["detail"]

    # Attempt GET /api/backups/any_file/download
    dl_resp = client.get("/api/backups/teachersystem_backup_20261028_120000.db/download", headers=headers)
    assert dl_resp.status_code == 403
    assert "restricted to the Teacher account only" in dl_resp.json()["detail"]


def test_unauthenticated_request_rejected(client):
    """Unauthenticated users must receive 401 Unauthorized."""
    resp = client.get("/api/backups")
    assert resp.status_code == 401

    post_resp = client.post("/api/backups")
    assert post_resp.status_code == 401


def test_api_download_path_traversal_rejection(client, db_session):
    """Path traversal attacks over the HTTP endpoint must fail with 400 or 404."""
    teacher = UserRepository.create_teacher(
        db_session, username="teacher_sec", full_name="المعلم الأمني", phone="01077777777", password="SecPassword123!"
    )
    login_resp = client.post("/api/auth/login", json={"username": "teacher_sec", "password": "SecPassword123!"})
    headers = {"Authorization": f"Bearer {login_resp.json()['session_token']}"}

    # Malicious filenames
    resp1 = client.get("/api/backups/..%2F..%2Fdata%2Fteachersystem.db/download", headers=headers)
    assert resp1.status_code in (400, 404)

    resp2 = client.get("/api/backups/invalid_name.txt/download", headers=headers)
    assert resp2.status_code == 400

    resp3 = client.get("/api/backups/teachersystem_backup_19990101_000000.db/download", headers=headers)
    assert resp3.status_code == 404


def test_production_database_remains_untouched():
    """Verify that the production database file has not been altered or replaced."""
    prod_db = Path("C:/TeacherSystem/data/teachersystem.db")
    assert prod_db.exists(), "Production database must exist"
    # Verify file is accessible and has tables
    conn = sqlite3.connect(f"file:{prod_db.as_posix()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchall()
        assert res[0][0] == "ok"
    finally:
        conn.close()
