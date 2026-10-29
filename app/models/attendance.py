import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

VALID_SESSION_STATUSES = ("scheduled", "completed", "cancelled")
SESSION_STATUS_LABELS = {
    "scheduled": "مجدولة",
    "completed": "مكتملة",
    "cancelled": "ملغاة"
}

VALID_ATTENDANCE_STATUSES = ("present", "absent", "late", "excused")
ATTENDANCE_STATUS_LABELS = {
    "present": "حاضر",
    "absent": "غائب",
    "late": "متأخر",
    "excused": "غياب بعذر"
}


class ClassSession(BaseModel):
    """
    Class Session Model.
    Represents an actual scheduled lesson occurrence for a specific group,
    strictly owned by the teacher's workspace.
    """
    __tablename__ = "sessions"

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    start_time = Column(String(8), nullable=False)                 # HH:MM or HH:MM:SS
    end_time = Column(String(8), nullable=True)                    # HH:MM or HH:MM:SS
    location = Column(String(150), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default="scheduled", nullable=False, index=True)

    # Relationships
    teacher = relationship("Teacher")
    group = relationship("Group")
    attendance_records = relationship("Attendance", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ClassSession id={self.id} group={self.group_id} date={self.session_date} status={self.status}>"


class Attendance(BaseModel):
    """
    Attendance Record Model.
    Tracks attendance for an individual student in a specific session.
    Enforces uniqueness at DB level: strictly one attendance record per student per session.
    """
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student_attendance"),
        Index("ix_attendance_tenant", "teacher_id", "session_id", "student_id"),
        Index("ix_attendance_session_status", "session_id", "status"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # present, absent, late, excused
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(String(36), nullable=True)
    recorded_by_user_type = Column(String(20), nullable=True)  # "teacher" or "assistant"

    # Relationships
    session = relationship("ClassSession", back_populates="attendance_records")
    student = relationship("Student")
    teacher = relationship("Teacher")

    def __repr__(self):
        return f"<Attendance session={self.session_id} student={self.student_id} status={self.status}>"
