from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class BackupMetadataResponse(BaseModel):
    filename: str = Field(..., description="Secure filename of the backup")
    size_bytes: int = Field(..., description="File size in bytes")
    size_formatted: str = Field(..., description="Human-readable file size (e.g. 368.0 KB)")
    created_at: str = Field(..., description="Creation timestamp in ISO format")
    is_verified: bool = Field(True, description="Whether the backup passed SQLite integrity checks")
    integrity_status: str = Field("verified_ok", description="Status string from PRAGMA integrity_check")
    storage_location_hint: str = Field(..., description="General directory or drive hint without exposing full server paths")

    model_config = ConfigDict(from_attributes=True)

class BackupListResponse(BaseModel):
    backup_directory_hint: str = Field(..., description="Configured backup storage location hint")
    total_count: int = Field(..., description="Number of available backup files")
    total_size_bytes: int = Field(..., description="Total size of all backups in bytes")
    total_size_formatted: str = Field(..., description="Human-readable total backup size")
    backups: List[BackupMetadataResponse] = Field(default_factory=list, description="List of backups sorted newest first")

    model_config = ConfigDict(from_attributes=True)
