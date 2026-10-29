import os
import re
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from app.config import BASE_DIR, logger
from app.database import engine as default_engine
from app.schemas.backup import BackupMetadataResponse, BackupListResponse

# Filename pattern: teachersystem_backup_YYYYMMDD_HHMMSS.db or with collision suffix _1.db
BACKUP_FILENAME_REGEX = re.compile(r"^teachersystem_backup_\d{8}_\d{6}(?:_\d+)?\.db$")
SQLITE_HEADER = b"SQLite format 3\x00"

# Preferred storage drive/directory: D:\TeacherSystem_Backups
PREFERRED_BACKUP_DIR = Path(os.getenv("BACKUP_DIR", os.getenv("TEACHERSYSTEM_BACKUP_DIR", "D:/TeacherSystem_Backups")))
FALLBACK_BACKUP_DIR = BASE_DIR / "backups"


def format_bytes(bytes_count: int) -> str:
    """Formats raw byte counts into human-readable Arabic-friendly units."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    else:
        return f"{bytes_count / (1024 * 1024):.2f} MB"


def is_directory_writable(directory: Path) -> bool:
    """
    Validates whether the specified directory exists (or can be created)
    and has full write/delete permissions.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        canary = directory / f".write_test_{os.getpid()}_{int(time.time() * 1000)}.tmp"
        canary.write_text("teachersystem_write_test", encoding="utf-8")
        canary.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.warning(f"Directory write check failed for '{directory}': {e}")
        return False


def resolve_backup_directory(custom_dir: Optional[Path] = None) -> Path:
    """
    Resolves the active backup directory with automatic fallback:
    1. Custom directory (if provided by tests or caller).
    2. Dynamic environment variable (BACKUP_DIR / TEACHERSYSTEM_BACKUP_DIR).
    3. Preferred directory (D:\\TeacherSystem_Backups).
    4. Fallback directory (C:\\TeacherSystem\\backups).
    """
    if custom_dir is not None:
        c_path = Path(custom_dir).resolve()
        if is_directory_writable(c_path):
            return c_path
        raise RuntimeError(f"Specified custom backup directory '{c_path}' is not writable.")

    # 1. Dynamic environment variable check (allows test isolation)
    env_dir = os.getenv("BACKUP_DIR") or os.getenv("TEACHERSYSTEM_BACKUP_DIR")
    if env_dir:
        env_path = Path(env_dir).resolve()
        if is_directory_writable(env_path):
            return env_path
        logger.warning(f"Configured env BACKUP_DIR '{env_path}' is not writable, falling back.")

    # 2. Try preferred directory (D:\TeacherSystem_Backups)
    pref_path = PREFERRED_BACKUP_DIR.resolve()
    if is_directory_writable(pref_path):
        return pref_path

    # 3. Fall back to local C: drive within project
    fb_path = FALLBACK_BACKUP_DIR.resolve()
    if is_directory_writable(fb_path):
        logger.info(f"Using fallback backup directory: {fb_path}")
        return fb_path

    raise RuntimeError("No writable backup storage directory available on the server.")


def get_storage_location_hint(backup_dir: Path) -> str:
    """Provides a sanitized, human-readable description of the backup storage location."""
    path_str = str(backup_dir)
    drive = backup_dir.drive.upper() if backup_dir.drive else ""
    if drive.startswith("D"):
        return f"{path_str} (قرص تخزين منفصل D:)"
    elif drive.startswith("C"):
        return f"{path_str} (مجلد النظام المحلي C:)"
    return path_str


def verify_sqlite_backup(file_path: Path) -> Tuple[bool, str]:
    """
    Verifies SQLite database backup integrity:
    1. File existence and non-zero size.
    2. 16-byte SQLite magic header.
    3. Executes PRAGMA integrity_check.
    4. Validates table count > 0 to prevent empty backups.
    """
    if not file_path.is_file():
        return False, "file_not_found"

    if file_path.stat().st_size < 100:
        return False, "file_too_small"

    # Check 16-byte SQLite header
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        if not header.startswith(SQLITE_HEADER):
            return False, "invalid_sqlite_magic_header"
    except Exception as e:
        return False, f"header_read_error: {str(e)}"

    # Run PRAGMA integrity_check in read-only mode
    try:
        uri_path = file_path.resolve().as_posix()
        conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            rows = cursor.fetchall()
            if not rows or rows[0][0] != "ok":
                return False, f"integrity_failed: {rows}"

            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            table_count = cursor.fetchone()[0]
            if table_count == 0:
                return False, "database_has_no_tables"

            return True, "verified_ok"
        finally:
            conn.close()
    except Exception as e:
        return False, f"sqlite_verification_error: {str(e)}"


class BackupService:
    """
    Core service managing database backups, online streaming,
    verification, and download security.
    """

    @staticmethod
    def create_backup(
        target_engine=None,
        custom_backup_dir: Optional[Path] = None
    ) -> BackupMetadataResponse:
        """
        Creates a manual online backup of the SQLite database using SQLite's
        online backup API. Validates WAL integrity before finalizing.
        """
        backup_dir = resolve_backup_directory(custom_backup_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"teachersystem_backup_{timestamp}.db"

        # Check for filename collisions within the same second
        collision_counter = 1
        while (backup_dir / filename).exists():
            filename = f"teachersystem_backup_{timestamp}_{collision_counter}.db"
            collision_counter += 1

        temp_target = backup_dir / f"{filename}.tmp"
        engine_to_use = target_engine or default_engine

        logger.info(f"Starting SQLite online backup to temporary file: {temp_target}")

        raw_src_conn = engine_to_use.raw_connection()
        try:
            dest_conn = sqlite3.connect(str(temp_target))
            try:
                # Use DBAPI driver connection to execute safe online backup
                dbapi_conn = raw_src_conn.driver_connection
                dbapi_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        except Exception as e:
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
            logger.error(f"SQLite online backup failed during copy: {e}")
            raise RuntimeError(f"Failed to perform online database backup: {e}") from e
        finally:
            raw_src_conn.close()

        # Verify integrity of the backup file BEFORE moving into final place
        is_verified, integrity_status = verify_sqlite_backup(temp_target)
        if not is_verified:
            temp_target.unlink(missing_ok=True)
            logger.error(f"Integrity check failed for new backup: {integrity_status}")
            raise RuntimeError(f"Database backup failed integrity check: {integrity_status}")

        # Atomically rename to final target file
        final_target = backup_dir / filename
        os.replace(temp_target, final_target)

        stat = final_target.stat()
        created_at_iso = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        size_bytes = stat.st_size
        size_formatted = format_bytes(size_bytes)
        location_hint = get_storage_location_hint(backup_dir)

        logger.info(f"Database backup created successfully: {filename} ({size_formatted}) at {backup_dir}")

        return BackupMetadataResponse(
            filename=filename,
            size_bytes=size_bytes,
            size_formatted=size_formatted,
            created_at=created_at_iso,
            is_verified=True,
            integrity_status=integrity_status,
            storage_location_hint=location_hint
        )

    @staticmethod
    def list_backups(custom_backup_dir: Optional[Path] = None) -> BackupListResponse:
        """
        Lists all valid backup files in the backup directory,
        sorted newest first with metadata and verification status.
        """
        backup_dir = resolve_backup_directory(custom_backup_dir)
        backups: List[BackupMetadataResponse] = []
        total_size = 0

        if backup_dir.exists():
            for item in backup_dir.iterdir():
                if item.is_file() and BACKUP_FILENAME_REGEX.match(item.name):
                    try:
                        stat = item.stat()
                        size_bytes = stat.st_size
                        total_size += size_bytes
                        created_at_iso = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()

                        is_verified, integrity_status = verify_sqlite_backup(item)

                        backups.append(BackupMetadataResponse(
                            filename=item.name,
                            size_bytes=size_bytes,
                            size_formatted=format_bytes(size_bytes),
                            created_at=created_at_iso,
                            is_verified=is_verified,
                            integrity_status=integrity_status,
                            storage_location_hint=get_storage_location_hint(backup_dir)
                        ))
                    except Exception as e:
                        logger.warning(f"Error reading backup file '{item.name}': {e}")

        # Sort newest first based on filename descending (timestamp-encoded)
        backups.sort(key=lambda b: b.filename, reverse=True)

        return BackupListResponse(
            backup_directory_hint=get_storage_location_hint(backup_dir),
            total_count=len(backups),
            total_size_bytes=total_size,
            total_size_formatted=format_bytes(total_size),
            backups=backups
        )

    @staticmethod
    def get_backup_path_for_download(
        filename: str,
        custom_backup_dir: Optional[Path] = None
    ) -> Path:
        """
        Validates backup filename and resolves its path with strict
        path traversal protection.
        """
        # 1. Reject any characters outside allowed safe pattern
        if not BACKUP_FILENAME_REGEX.match(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="اسم ملف النسخة الاحتياطية غير صالح أو يحتوي على رموز غير مسموحة."
            )

        # 2. Strict guard against directory traversal sequences
        if any(seq in filename for seq in ("/", "\\", "..", "\x00")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تم رفض المسار لاحتوائه على تسلسلات غير آمنة."
            )

        backup_dir = resolve_backup_directory(custom_backup_dir).resolve()
        candidate = (backup_dir / filename).resolve()

        # 3. Path containment check
        if candidate.parent != backup_dir or not candidate.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ملف النسخة الاحتياطية المطلوب غير موجود."
            )

        return candidate

    @staticmethod
    def prune_old_backups(
        custom_backup_dir: Optional[Path] = None,
        max_daily_keep: int = 7,
        max_weekly_keep: int = 4
    ) -> List[str]:
        """
        Optional retention manager: preserves 7 daily backups and 4 weekly backups.
        Returns the list of pruned filenames.
        """
        backup_dir = resolve_backup_directory(custom_backup_dir)
        if not backup_dir.exists():
            return []

        all_backups = []
        for item in backup_dir.iterdir():
            if item.is_file() and BACKUP_FILENAME_REGEX.match(item.name):
                all_backups.append(item)

        # Sort newest first
        all_backups.sort(key=lambda p: p.name, reverse=True)

        # If total files within total allowed retention limit (7 + 4 = 11), retain all
        total_keep = max_daily_keep + max_weekly_keep
        if len(all_backups) <= total_keep:
            return []

        pruned = []
        # Keep the newest `total_keep` files, prune older ones
        for to_delete in all_backups[total_keep:]:
            try:
                to_delete.unlink(missing_ok=True)
                pruned.append(to_delete.name)
                logger.info(f"Retention policy pruned old backup: {to_delete.name}")
            except Exception as e:
                logger.warning(f"Failed to prune old backup {to_delete.name}: {e}")

        return pruned
