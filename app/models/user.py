from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Teacher(BaseModel):
    """
    Teacher Model (Primary Workspace Owner).
    All academic, student, and financial records belong to a specific teacher.
    """
    __tablename__ = "teachers"

    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    assistants = relationship("Assistant", back_populates="teacher", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Teacher {self.username}>"


class Assistant(BaseModel):
    """
    Assistant Model.
    Each assistant is strictly scoped to one teacher and has fine-grained permissions.
    """
    __tablename__ = "assistants"

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Granular Permissions Matrix
    can_mark_attendance = Column(Boolean, default=True, nullable=False)
    can_view_attendance = Column(Boolean, default=True, nullable=False)
    can_manage_students = Column(Boolean, default=False, nullable=False)
    can_view_grades = Column(Boolean, default=False, nullable=False)
    can_manage_exams = Column(Boolean, default=False, nullable=False)
    can_enter_grades = Column(Boolean, default=False, nullable=False)
    can_collect_cash = Column(Boolean, default=False, nullable=False)
    can_view_student_payment_history = Column(Boolean, default=False, nullable=False)
    can_view_financial_analytics = Column(Boolean, default=False, nullable=False)  # Hidden by default
    can_manage_fees = Column(Boolean, default=False, nullable=False)
    can_request_messages = Column(Boolean, default=True, nullable=False)

    @property
    def can_view_finances(self) -> bool:
        return (
            self.can_view_financial_analytics
            or self.can_view_student_payment_history
            or self.can_collect_cash
            or self.can_manage_fees
        )

    @property
    def can_record_payments(self) -> bool:
        return self.can_collect_cash

    # Relationship
    teacher = relationship("Teacher", back_populates="assistants")

    def __repr__(self):
        return f"<Assistant {self.username} (Teacher: {self.teacher_id})>"


class UserSession(BaseModel):
    """
    Server-side database session table.
    Enables instant revocation on logout, password reset, or device disconnection.
    """
    __tablename__ = "user_sessions"

    session_token = Column(String(128), unique=True, index=True, nullable=False)
    user_type = Column(String(20), nullable=False)  # "teacher" or "assistant"
    user_id = Column(String(36), index=True, nullable=False)
    teacher_id = Column(String(36), index=True, nullable=False)  # Scoped tenant
    csrf_token = Column(String(64), nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<Session user_id={self.user_id} revoked={self.is_revoked}>"
