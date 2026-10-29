import uuid
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from app.models.academic import Student, Group, GroupStudent, GRADE_LABELS
from app.schemas.academic import StudentCreate, StudentUpdate, GroupCreate, GroupUpdate


class AcademicRepository:
    """
    Repository handling Academic records (Students, Groups, and Group Enrollments).
    Strictly enforces tenant isolation at query-level for every read, write, and count.
    """

    # ==========================================
    # --- Student Operations ---
    # ==========================================

    @staticmethod
    def create_student(db: Session, teacher_id: str, data: StudentCreate) -> Student:
        student = Student(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            full_name=data.full_name.strip(),
            grade_level=data.grade_level,
            phone=data.phone.strip(),
            parent_name=data.parent_name.strip() if data.parent_name else None,
            parent_phone=data.parent_phone.strip() if data.parent_phone else None,
            address=data.address.strip() if data.address else None,
            notes=data.notes.strip() if data.notes else None,
            is_active=data.is_active,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return student

    @staticmethod
    def get_student_by_id(db: Session, teacher_id: str, student_id: str) -> Optional[Student]:
        """Fetch student strictly scoped to teacher_id."""
        return db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()

    @staticmethod
    def list_students(
        db: Session,
        teacher_id: str,
        q: Optional[str] = None,
        grade_level: Optional[str] = None,
        is_active: Optional[bool] = None,
        group_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Student], int]:
        """
        List students belonging strictly to teacher_id with optional search and filters.
        Returns (students, total_count).
        """
        query = db.query(Student).filter(
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        )

        if grade_level:
            query = query.filter(Student.grade_level == grade_level)

        if is_active is not None:
            query = query.filter(Student.is_active == is_active)

        if q:
            search = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Student.full_name.ilike(search),
                    Student.phone.ilike(search),
                    Student.parent_phone.ilike(search),
                    Student.parent_name.ilike(search),
                )
            )

        if group_id:
            # Join with active enrollments in the specified group
            query = query.join(
                GroupStudent,
                and_(
                    GroupStudent.student_id == Student.id,
                    GroupStudent.group_id == group_id,
                    GroupStudent.teacher_id == teacher_id,
                    GroupStudent.is_deleted == False,
                    GroupStudent.is_active == True,
                )
            )

        total = query.count()
        students = query.order_by(Student.full_name.asc()).offset(offset).limit(limit).all()
        return students, total

    @staticmethod
    def update_student(
        db: Session,
        teacher_id: str,
        student_id: str,
        data: StudentUpdate
    ) -> Optional[Student]:
        student = AcademicRepository.get_student_by_id(db, teacher_id, student_id)
        if not student:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            if isinstance(val, str):
                val = val.strip()
            setattr(student, key, val)

        student.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(student)
        return student

    @staticmethod
    def soft_delete_student(db: Session, teacher_id: str, student_id: str) -> bool:
        """
        Soft-delete student and automatically deactivate all their group enrollments
        in an atomic database transaction.
        """
        student = AcademicRepository.get_student_by_id(db, teacher_id, student_id)
        if not student:
            return False

        now = datetime.now(timezone.utc)
        student.is_deleted = True
        student.is_active = False
        student.updated_at = now

        # Deactivate all active group memberships
        enrollments = db.query(GroupStudent).filter(
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_deleted == False
        ).all()

        for en in enrollments:
            en.is_deleted = True
            en.is_active = False
            en.updated_at = now

        db.commit()
        return True

    @staticmethod
    def get_student_groups(db: Session, teacher_id: str, student_id: str) -> List[Dict[str, Any]]:
        """Get all active groups the student is enrolled in."""
        results = db.query(Group, GroupStudent.joined_at).join(
            GroupStudent,
            and_(
                GroupStudent.group_id == Group.id,
                GroupStudent.student_id == student_id,
                GroupStudent.teacher_id == teacher_id,
                GroupStudent.is_deleted == False,
                GroupStudent.is_active == True
            )
        ).filter(
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).all()

        groups = []
        for grp, joined_at in results:
            groups.append({
                "id": grp.id,
                "name": grp.name,
                "grade_level": grp.grade_level,
                "grade_label": GRADE_LABELS.get(grp.grade_level, grp.grade_level),
                "subject": grp.subject,
                "schedule_details": grp.schedule_details,
                "joined_at": joined_at
            })
        return groups

    @staticmethod
    def get_student_group_count(db: Session, teacher_id: str, student_id: str) -> int:
        """Count active group memberships for a student."""
        return db.query(func.count(GroupStudent.id)).filter(
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_deleted == False,
            GroupStudent.is_active == True
        ).scalar() or 0

    # ==========================================
    # --- Group Operations ---
    # ==========================================

    @staticmethod
    def create_group(db: Session, teacher_id: str, data: GroupCreate) -> Group:
        group = Group(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            name=data.name.strip(),
            grade_level=data.grade_level,
            subject=data.subject.strip() if data.subject else None,
            schedule_details=data.schedule_details.strip() if data.schedule_details else None,
            is_active=data.is_active
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        return group

    @staticmethod
    def get_group_by_id(db: Session, teacher_id: str, group_id: str) -> Optional[Group]:
        """Fetch group strictly scoped to teacher_id."""
        return db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()

    @staticmethod
    def list_groups(
        db: Session,
        teacher_id: str,
        grade_level: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Group], int]:
        """List groups belonging strictly to teacher_id."""
        query = db.query(Group).filter(
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        )

        if grade_level:
            query = query.filter(Group.grade_level == grade_level)

        if is_active is not None:
            query = query.filter(Group.is_active == is_active)

        total = query.count()
        groups = query.order_by(Group.name.asc()).offset(offset).limit(limit).all()
        return groups, total

    @staticmethod
    def update_group(
        db: Session,
        teacher_id: str,
        group_id: str,
        data: GroupUpdate
    ) -> Optional[Group]:
        group = AcademicRepository.get_group_by_id(db, teacher_id, group_id)
        if not group:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            if isinstance(val, str):
                val = val.strip()
            setattr(group, key, val)

        group.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(group)
        return group

    @staticmethod
    def soft_delete_group(db: Session, teacher_id: str, group_id: str) -> bool:
        """
        Soft-delete group and automatically deactivate all student memberships
        in an atomic database transaction.
        """
        group = AcademicRepository.get_group_by_id(db, teacher_id, group_id)
        if not group:
            return False

        now = datetime.now(timezone.utc)
        group.is_deleted = True
        group.is_active = False
        group.updated_at = now

        # Deactivate all active memberships in this group
        enrollments = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_deleted == False
        ).all()

        for en in enrollments:
            en.is_deleted = True
            en.is_active = False
            en.updated_at = now

        db.commit()
        return True

    @staticmethod
    def get_group_student_count(db: Session, teacher_id: str, group_id: str) -> int:
        """Count active students enrolled in a group."""
        return db.query(func.count(GroupStudent.id)).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_deleted == False,
            GroupStudent.is_active == True
        ).scalar() or 0

    @staticmethod
    def get_group_enrolled_students(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> List[Dict[str, Any]]:
        """List all active students currently enrolled in this group."""
        results = db.query(Student, GroupStudent.id, GroupStudent.joined_at, GroupStudent.is_active).join(
            GroupStudent,
            and_(
                GroupStudent.student_id == Student.id,
                GroupStudent.group_id == group_id,
                GroupStudent.teacher_id == teacher_id,
                GroupStudent.is_deleted == False,
                GroupStudent.is_active == True
            )
        ).filter(
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        enrolled = []
        for st, membership_id, joined_at, is_active in results:
            enrolled.append({
                "membership_id": membership_id,
                "student_id": st.id,
                "full_name": st.full_name,
                "phone": st.phone,
                "parent_name": st.parent_name,
                "parent_phone": st.parent_phone,
                "grade_level": st.grade_level,
                "grade_label": GRADE_LABELS.get(st.grade_level, st.grade_level),
                "joined_at": joined_at,
                "is_active": is_active
            })
        return enrolled

    # ==========================================
    # --- Enrollment Operations ---
    # ==========================================

    @staticmethod
    def enroll_student_in_group(
        db: Session,
        teacher_id: str,
        group_id: str,
        student_id: str
    ) -> Tuple[Optional[GroupStudent], Optional[str]]:
        """
        Enroll a student into a group with full tenant isolation and validation:
        1. Verifies group belongs to teacher_id.
        2. Verifies student belongs to teacher_id.
        3. Verifies grade_level compatibility.
        4. Detects duplicate active membership (returns error 'duplicate_enrollment').
        5. Reactivates previously soft-deleted/deactivated membership if exists, or inserts clean record.
        Returns (GroupStudent, error_code).
        """
        group = AcademicRepository.get_group_by_id(db, teacher_id, group_id)
        if not group:
            return None, "group_not_found"

        student = AcademicRepository.get_student_by_id(db, teacher_id, student_id)
        if not student:
            return None, "student_not_found"

        if student.grade_level != group.grade_level:
            return None, "grade_mismatch"

        # Check existing membership record
        existing = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id
        ).first()

        now = datetime.now(timezone.utc)
        if existing:
            if not existing.is_deleted and existing.is_active:
                return None, "duplicate_enrollment"

            # Reactivate soft-deleted or inactive membership
            existing.is_deleted = False
            existing.is_active = True
            existing.joined_at = now
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing, None

        # Insert new membership
        enrollment = GroupStudent(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            group_id=group_id,
            student_id=student_id,
            is_active=True,
            joined_at=now,
            created_at=now,
            updated_at=now,
            is_deleted=False
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment, None

    @staticmethod
    def unenroll_student_from_group(
        db: Session,
        teacher_id: str,
        group_id: str,
        student_id: str
    ) -> bool:
        """Unenroll / remove a student from a group."""
        enrollment = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_deleted == False
        ).first()

        if not enrollment:
            return False

        enrollment.is_deleted = True
        enrollment.is_active = False
        enrollment.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
