import sqlite3
import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from app.config import DATABASE_URL, DEFAULT_DB_PATH, logger

# Create SQLAlchemy Engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enforce WAL mode, foreign keys, synchronous=NORMAL, and busy timeout for SQLite.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def backup_sqlite_database(target_path: Path) -> bool:
    """
    Safely backup the active SQLite database using the native SQLite backup API.
    This guarantees WAL compatibility, preventing corruption from uncommitted
    WAL journal entries even under active read/write load.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a raw sqlite3 connection to perform the online backup
    raw_src_conn = engine.raw_connection()
    try:
        dest_conn = sqlite3.connect(str(target_path))
        try:
            # Performs safe online backup using DBAPI driver connection
            dbapi_conn = raw_src_conn.driver_connection
            dbapi_conn.backup(dest_conn)
            logger.info(f"SQLite WAL safe backup created successfully at: {target_path}")
            return True
        finally:
            dest_conn.close()
    except Exception as e:
        logger.error(f"Failed to create SQLite safe backup: {e}")
        raise
    finally:
        raw_src_conn.close()
