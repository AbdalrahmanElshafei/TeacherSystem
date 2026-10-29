import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

VALID_GRADE_LEVELS = ("1_sec", "2_sec", "3_sec")

GRADE_LABELS = {
    "1_sec": "الصف الأول الثانوي",
    "2_sec": "الصف الثاني الثانوي",
    "3_sec": "الصف الثالث الثانوي"
}

class Student(BaseModel):
    """
    Student Model.
    Represents an enrolled high-school student owned strictly by a Teacher workspace.
    """
    __tablename__ = "students"

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(120), nullable=False, index=True)
    grade_level = Column(String(20), nullable=False, index=True)  # "1_sec", "2_sec", "3_sec"
    phone = Column(String(20), nullable=False, index=True)
    parent_name = Column(String(120), nullable=True)
    parent_phone = Column(String(20), nullable=True, index=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    teacher = relationship("Teacher")
    enrollments = relationship("GroupStudent", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student {self.full_name} ({self.grade_level})>"


class Group(BaseModel):
    """
    Academic Group / Class Model.
    Represents a specific teaching group (e.g., center group, day/time slot) owned strictly by a Teacher.
    """
    __tablename__ = "groups"

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    grade_level = Column(String(20), nullable=False, index=True)  # "1_sec", "2_sec", "3_sec"
    subject = Column(String(100), nullable=True)
    schedule_details = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    teacher = relationship("Teacher")
    enrollments = relationship("GroupStudent", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Group {self.name} ({self.grade_level})>"


class GroupStudent(BaseModel):
    """
    Association table linking Students to Groups.
    Enforces tenant isolation and guarantees a student cannot be duplicated in the same group.
    """
    __tablename__ = "group_students"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", name="uq_group_student_membership"),
        Index("ix_group_students_tenant", "teacher_id", "group_id", "student_id"),
    )

    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    group = relationship("Group", back_populates="enrollments")
    student = relationship("Student", back_populates="enrollments")

    def __repr__(self):
        return f"<GroupStudent group={self.group_id} student={self.student_id}>"
