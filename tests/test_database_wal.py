import sqlite3
import logging
from pathlib import Path
from sqlalchemy import text
from app.database import engine, backup_sqlite_database
from app.config import SensitiveDataFilter

def test_sqlite_wal_mode_and_pragmas():
    """Verify that SQLite engine initializes with WAL mode, foreign keys, and pragmas."""
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert journal_mode.lower() == "wal", f"Expected 'wal', got '{journal_mode}'"
        
        foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1, f"Expected foreign_keys=1, got '{foreign_keys}'"
        
        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        assert busy_timeout >= 5000, f"Expected busy_timeout >= 5000, got '{busy_timeout}'"

def test_sqlite_wal_safe_backup_compatibility(tmp_path):
    """
    Verify that backup_sqlite_database safely duplicates the live WAL database
    to a destination file, and the resulting file is a valid, readable SQLite database.
    """
    # 1. Create a temporary table and insert sample rows in the primary DB
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS _test_wal (id INTEGER PRIMARY KEY, name TEXT);"))
        conn.execute(text("INSERT INTO _test_wal (name) VALUES ('wal_test_record');"))

    backup_file = tmp_path / "test_backup.db"
    assert not backup_file.exists()

    # 2. Perform safe backup
    success = backup_sqlite_database(backup_file)
    assert success is True
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    # 3. Open the backup file independently and verify integrity
    dest_conn = sqlite3.connect(str(backup_file))
    try:
        cursor = dest_conn.cursor()
        # Verify integrity
        integrity = cursor.execute("PRAGMA integrity_check;").fetchone()
        assert integrity[0] == "ok", f"Integrity check failed: {integrity}"

        # Verify data was copied
        row = cursor.execute("SELECT name FROM _test_wal LIMIT 1;").fetchone()
        assert row is not None
        assert row[0] == "wal_test_record"
    finally:
        dest_conn.close()

    # Cleanup test table in source
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS _test_wal;"))

def test_sensitive_data_logger_filter():
    """Verify that passwords, tokens, and hashes are redacted from logging records."""
    log_filter = SensitiveDataFilter()
    
    # Test case 1: password in plain text string
    record1 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="User login attempt with password=SecretPassword123 and token=abc123xyz",
        args=(), exc_info=None
    )
    log_filter.filter(record1)
    assert "SecretPassword123" not in record1.msg
    assert "abc123xyz" not in record1.msg
    assert "***REDACTED***" in record1.msg

    # Test case 2: JSON-like structure
    record2 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg='Received body {"username": "teacher1", "password": "SuperSecretPassword!"}',
        args=(), exc_info=None
    )
    log_filter.filter(record2)
    assert "SuperSecretPassword!" not in record2.msg
    assert "***REDACTED***" in record2.msg

    # Test case 3: Authorization Bearer header
    record3 = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6",
        args=(), exc_info=None
    )
    log_filter.filter(record3)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6" not in record3.msg
    assert "***REDACTED***" in record3.msg
