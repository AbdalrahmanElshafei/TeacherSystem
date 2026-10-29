import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

VALID_EXAM_STATUSES = ("scheduled", "completed", "cancelled")
EXAM_STATUS_LABELS = {
    "scheduled": "مجدول",
    "completed": "مكتمل",
    "cancelled": "ملغى"
}

VALID_RESULT_STATUSES = ("attended", "absent", "excused")
RESULT_STATUS_LABELS = {
    "attended": "حضر",
    "absent": "غائب",
    "excused": "معتذر"
}


class Exam(BaseModel):
    """
    Exam Model.
    Represents an exam or quiz scheduled for a specific group,
    strictly scoped to the teacher's workspace.
    """
    __tablename__ = "exams"

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False, index=True)
    exam_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    max_score = Column(Float, nullable=False)
    passing_score = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="scheduled", nullable=False, index=True)

    # Relationships
    teacher = relationship("Teacher")
    group = relationship("Group")
    results = relationship("ExamResult", back_populates="exam", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Exam id={self.id} title={self.title} max_score={self.max_score} status={self.status}>"


class ExamResult(BaseModel):
    """
    Exam Result Model.
    Stores the score and status of a single student in an exam.
    Enforces uniqueness: strictly one result per student per exam.
    Absent or excused students do not store fabricated scores (score is None).
    """
    __tablename__ = "exam_results"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_exam_student_result"),
        Index("ix_exam_result_tenant", "teacher_id", "exam_id", "student_id"),
        Index("ix_exam_result_status", "exam_id", "status"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=True)  # Numeric score when attended; None when absent/excused
    status = Column(String(20), nullable=False, default="attended", index=True)  # attended, absent, excused
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(String(36), nullable=True)
    recorded_by_user_type = Column(String(20), nullable=True)  # "teacher" or "assistant"

    # Relationships
    exam = relationship("Exam", back_populates="results")
    student = relationship("Student")
    teacher = relationship("Teacher")

    def __repr__(self):
        return f"<ExamResult exam={self.exam_id} student={self.student_id} score={self.score} status={self.status}>"
