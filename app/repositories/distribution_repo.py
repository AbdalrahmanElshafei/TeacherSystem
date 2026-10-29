from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.academic import Student, Group, GroupStudent, GRADE_LABELS
from app.models.distribution import StudentCardDistribution, GroupCardExport
from app.schemas.distribution import STATUS_LABELS


class DistributionRepository:
    """
    Data repository managing student barcode distribution tracking,
    delivery confirmations, and group export auditing.
    """

    @staticmethod
    def get_or_create_distribution(
        db: Session,
        teacher_id: str,
        student_id: str,
        group_id: Optional[str] = None
    ) -> StudentCardDistribution:
        """
        Retrieves existing distribution record for a student or creates a clean 'not_sent' record.
        """
        query = db.query(StudentCardDistribution).filter(
            StudentCardDistribution.teacher_id == teacher_id,
            StudentCardDistribution.student_id == student_id,
            StudentCardDistribution.is_deleted == False
        )
        if group_id:
            specific = query.filter(StudentCardDistribution.group_id == group_id).first()
            if specific:
                return specific

        dist = query.first()
        if not dist:
            dist = StudentCardDistribution(
                teacher_id=teacher_id,
                student_id=student_id,
                group_id=group_id,
                status="not_sent"
            )
            db.add(dist)
            db.commit()
            db.refresh(dist)
        return dist

    @staticmethod
    def update_distribution_status(
        db: Session,
        teacher_id: str,
        student_id: str,
        new_status: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        group_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> StudentCardDistribution:
        """
        Updates student distribution status strictly differentiating between:
        - 'generated': PDF was compiled
        - 'share_opened': native share modal was triggered
        - 'confirmed_sent': teacher/assistant manually confirmed sending
        - 'not_sent': reset state
        """
        dist = DistributionRepository.get_or_create_distribution(
            db, teacher_id=teacher_id, student_id=student_id, group_id=group_id
        )
        now = datetime.now(timezone.utc)

        if new_status == "generated":
            dist.card_generated_at = now
            if dist.status == "not_sent":
                dist.status = "generated"

        elif new_status == "share_opened":
            dist.share_opened_at = now
            # Only promote if not already confirmed sent
            if dist.status in ("not_sent", "generated"):
                dist.status = "share_opened"

        elif new_status == "confirmed_sent":
            dist.status = "confirmed_sent"
            dist.confirmed_sent_at = now
            dist.confirmed_by_id = user_id
            dist.confirmed_by_name = user_name

        elif new_status == "not_sent":
            dist.status = "not_sent"
            dist.confirmed_sent_at = None
            dist.confirmed_by_id = None
            dist.confirmed_by_name = None

        if notes is not None:
            dist.notes = notes

        db.commit()
        db.refresh(dist)
        return dist

    @staticmethod
    def record_group_export(
        db: Session,
        teacher_id: str,
        group_id: str,
        user_id: str,
        user_name: Optional[str],
        student_count: int,
        export_type: str = "group_pdf"
    ) -> GroupCardExport:
        """
        Logs a group export batch and advances 'not_sent' students to 'generated'.
        Crucial: DOES NOT mark them as 'confirmed_sent'.
        """
        now = datetime.now(timezone.utc)
        export_log = GroupCardExport(
            teacher_id=teacher_id,
            group_id=group_id,
            exported_by_id=user_id,
            exported_by_name=user_name,
            student_count=student_count,
            export_type=export_type,
            exported_at=now
        )
        db.add(export_log)

        # Retrieve active students in this group
        active_enrollments = db.query(GroupStudent).filter(
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.group_id == group_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).all()

        for enr in active_enrollments:
            dist = DistributionRepository.get_or_create_distribution(
                db, teacher_id=teacher_id, student_id=enr.student_id, group_id=group_id
            )
            dist.card_generated_at = now
            if dist.status == "not_sent":
                dist.status = "generated"

        db.commit()
        db.refresh(export_log)
        return export_log

    @staticmethod
    def get_latest_group_export(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> Optional[GroupCardExport]:
        """Returns the most recent group export record if one exists."""
        return db.query(GroupCardExport).filter(
            GroupCardExport.teacher_id == teacher_id,
            GroupCardExport.group_id == group_id,
            GroupCardExport.is_deleted == False
        ).order_by(GroupCardExport.exported_at.desc()).first()

    @staticmethod
    def get_group_distribution_overview(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> Dict[str, Any]:
        """
        Compiles the complete distribution overview for a group:
        - All active students
        - Status of each student
        - Flags students who enrolled after the latest group export
        - Total, confirmed_sent, pending, and new-since-export counters
        """
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            raise LookupError("المجموعة المطلوبة غير موجودة")

        latest_export = DistributionRepository.get_latest_group_export(db, teacher_id, group_id)
        latest_export_time = latest_export.exported_at if latest_export else None

        # Query active enrolled students
        enrollments = db.query(GroupStudent, Student).join(
            Student, GroupStudent.student_id == Student.id
        ).filter(
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.group_id == group_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        student_items = []
        confirmed_count = 0
        new_since_export_count = 0

        # Preload distributions for this teacher and students
        dist_map = {}
        student_ids = [s.id for _, s in enrollments]
        if student_ids:
            dists = db.query(StudentCardDistribution).filter(
                StudentCardDistribution.teacher_id == teacher_id,
                StudentCardDistribution.student_id.in_(student_ids),
                StudentCardDistribution.is_deleted == False
            ).all()
            for d in dists:
                # Map by student_id; specific group match takes precedence
                if d.student_id not in dist_map or d.group_id == group_id:
                    dist_map[d.student_id] = d

        for enr, student in enrollments:
            dist = dist_map.get(student.id)
            current_status = dist.status if dist else "not_sent"

            # Check if enrolled after the last export
            is_new = False
            if latest_export_time and enr.joined_at:
                # Handle naive vs aware comparison if needed
                enr_time = enr.joined_at
                exp_time = latest_export_time
                if enr_time.tzinfo is None and exp_time.tzinfo is not None:
                    enr_time = enr_time.replace(tzinfo=timezone.utc)
                elif enr_time.tzinfo is not None and exp_time.tzinfo is None:
                    exp_time = exp_time.replace(tzinfo=timezone.utc)

                if enr_time > exp_time:
                    is_new = True
                    new_since_export_count += 1
            elif latest_export_time is None:
                # No export ever run, all are considered awaiting initial batch
                pass

            if current_status == "confirmed_sent":
                confirmed_count += 1

            student_items.append({
                "student_id": student.id,
                "full_name": student.full_name,
                "phone": student.phone,
                "grade_level": student.grade_level,
                "grade_label": GRADE_LABELS.get(student.grade_level, student.grade_level),
                "group_id": group.id,
                "group_name": group.name,
                "joined_at": enr.joined_at.isoformat() if enr.joined_at else None,
                "barcode_value": student.id,
                "distribution_status": current_status,
                "status_label": STATUS_LABELS.get(current_status, current_status),
                "card_generated_at": dist.card_generated_at.isoformat() if dist and dist.card_generated_at else None,
                "share_opened_at": dist.share_opened_at.isoformat() if dist and dist.share_opened_at else None,
                "confirmed_sent_at": dist.confirmed_sent_at.isoformat() if dist and dist.confirmed_sent_at else None,
                "confirmed_by_name": dist.confirmed_by_name if dist else None,
                "is_new_since_last_export": is_new,
            })

        total = len(student_items)
        pending = total - confirmed_count

        return {
            "group_id": group.id,
            "group_name": group.name,
            "grade_level": group.grade_level,
            "grade_label": GRADE_LABELS.get(group.grade_level, group.grade_level),
            "total_students": total,
            "confirmed_sent_count": confirmed_count,
            "pending_count": pending,
            "new_since_export_count": new_since_export_count,
            "last_exported_at": latest_export_time.isoformat() if latest_export_time else None,
            "last_exported_by_name": latest_export.exported_by_name if latest_export else None,
            "students": student_items
        }

    @staticmethod
    def get_student_card_data(
        db: Session,
        teacher_id: str,
        student_id: str,
        group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves full student metadata, group enrollments, and distribution status
        for single card rendering.
        """
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            raise LookupError("الطالب غير موجود أو غير مسجل في حساب المعلم")

        # Get all active enrollments for this student
        enrollments = db.query(GroupStudent, Group).join(
            Group, GroupStudent.group_id == Group.id
        ).filter(
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.student_id == student_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False,
            Group.is_deleted == False
        ).all()

        enrolled_groups = [
            {"id": g.id, "name": g.name, "grade_level": g.grade_level}
            for _, g in enrollments
        ]

        primary_group_id = None
        primary_group_name = None
        if group_id:
            match = next((g for g in enrolled_groups if g["id"] == group_id), None)
            if match:
                primary_group_id = match["id"]
                primary_group_name = match["name"]
        if not primary_group_id and enrolled_groups:
            primary_group_id = enrolled_groups[0]["id"]
            primary_group_name = enrolled_groups[0]["name"]

        dist = DistributionRepository.get_or_create_distribution(
            db, teacher_id=teacher_id, student_id=student_id, group_id=primary_group_id
        )

        return {
            "student_id": student.id,
            "full_name": student.full_name,
            "grade_level": student.grade_level,
            "grade_label": GRADE_LABELS.get(student.grade_level, student.grade_level),
            "barcode_value": student.id,
            "primary_group_id": primary_group_id,
            "primary_group_name": primary_group_name,
            "enrolled_groups": enrolled_groups,
            "distribution_status": dist.status,
            "status_label": STATUS_LABELS.get(dist.status, dist.status),
            "card_generated_at": dist.card_generated_at.isoformat() if dist.card_generated_at else None,
            "share_opened_at": dist.share_opened_at.isoformat() if dist.share_opened_at else None,
            "confirmed_sent_at": dist.confirmed_sent_at.isoformat() if dist.confirmed_sent_at else None,
            "confirmed_by_name": dist.confirmed_by_name,
            "is_new_since_last_export": False,
        }
