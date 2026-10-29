import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class StudentCardDistribution(BaseModel):
    """
    Tracks the lifecycle and delivery confirmation of student barcode ID cards.
    Differentiates between:
    - Card generated / exported
    - Native share dialog opened
    - Teacher / assistant manually confirmed delivery
    """
    __tablename__ = "student_card_distributions"
    __table_args__ = (
        Index("ix_student_card_dist_tenant", "teacher_id", "student_id"),
        Index("ix_student_card_dist_group", "teacher_id", "group_id"),
        Index("ix_student_card_dist_status", "teacher_id", "status"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True)

    # Status: 'not_sent', 'generated', 'share_opened', 'confirmed_sent'
    status = Column(String(20), nullable=False, default="not_sent", server_default="not_sent", index=True)

    card_generated_at = Column(DateTime, nullable=True)
    share_opened_at = Column(DateTime, nullable=True)
    confirmed_sent_at = Column(DateTime, nullable=True)

    confirmed_by_id = Column(String(36), nullable=True)
    confirmed_by_name = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    student = relationship("Student")
    group = relationship("Group")

    def __repr__(self):
        return f"<StudentCardDistribution student={self.student_id} status={self.status}>"


class GroupCardExport(BaseModel):
    """
    Audit log of group-level barcode card exports.
    Records when a group batch was exported, enabling precise identification of
    students newly enrolled after the latest relevant export.
    """
    __tablename__ = "group_card_exports"
    __table_args__ = (
        Index("ix_group_card_exports_lookup", "teacher_id", "group_id", "exported_at"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    exported_by_id = Column(String(36), nullable=False)
    exported_by_name = Column(String(120), nullable=True)
    student_count = Column(Integer, nullable=False, default=0)
    export_type = Column(String(30), nullable=False, default="group_pdf")  # 'group_pdf', 'multi_pdf'
    exported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    group = relationship("Group")

    def __repr__(self):
        return f"<GroupCardExport group={self.group_id} count={self.student_count} at={self.exported_at}>"
