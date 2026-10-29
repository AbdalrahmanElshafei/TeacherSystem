from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from app.core.dependencies import require_teacher, AuthenticatedUser
from app.schemas.backup import BackupMetadataResponse, BackupListResponse
from app.services.backup_service import BackupService
from app.config import logger

router = APIRouter(prefix="/api/backups", tags=["Backup Management"])


@router.post(
    "",
    response_model=BackupMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual SQLite database backup"
)
def create_backup(
    auth: AuthenticatedUser = Depends(require_teacher)
):
    """
    Creates a verified, WAL-consistent SQLite database backup using SQLite's
    online backup API. Restricted strictly to the primary Teacher account.
    """
    logger.info(f"Manual backup initiated by teacher: {auth.username} (ID: {auth.user_id})")
    try:
        metadata = BackupService.create_backup()
        return metadata
    except Exception as e:
        logger.error(f"Failed to create manual backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في إنشاء النسخة الاحتياطية لقاعدة البيانات: {str(e)}"
        )


@router.get(
    "",
    response_model=BackupListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available database backups"
)
def list_backups(
    auth: AuthenticatedUser = Depends(require_teacher)
):
    """
    Returns a list of all verified database backups sorted newest first,
    including file size, creation timestamp, and integrity status.
    Restricted strictly to the primary Teacher account.
    """
    try:
        return BackupService.list_backups()
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في جلب قائمة النسخ الاحتياطية: {str(e)}"
        )


@router.get(
    "/{filename}/download",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Download a specific database backup"
)
def download_backup(
    filename: str,
    auth: AuthenticatedUser = Depends(require_teacher)
):
    """
    Downloads a selected database backup file with strict path traversal
    protections. Restricted strictly to the primary Teacher account.
    """
    logger.info(f"Backup download requested: '{filename}' by teacher: {auth.username}")
    file_path = BackupService.get_backup_path_for_download(filename)

    return FileResponse(
        path=str(file_path),
        media_type="application/x-sqlite3",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
