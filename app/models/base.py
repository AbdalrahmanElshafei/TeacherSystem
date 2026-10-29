import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base

class BaseModel(Base):
    """
    Abstract base model providing:
    - UUIDv4 primary keys (for future distributed/offline synchronization)
    - Timestamp tracking (created_at, updated_at)
    - Soft-deletion support (is_deleted)
    """
    __abstract__ = True

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
