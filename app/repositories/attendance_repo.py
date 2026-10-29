import uuid
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models.academic import Student, Group, GroupStudent, GRADE_LABELS
from app.models.attendance import (
    ClassSession,
    Attendance,
    VALID_SESSION_STATUSES,
    SESSION_STATUS_LABELS,
    VALID_ATTENDANCE_STATUSES,
    ATTENDANCE_STATUS_LABELS,
)
from app.schemas.attendance import (
    SessionCreate,
    SessionUpdate,
    AttendanceMarkItem,
    SessionAttendanceStats,
)


class AttendanceRepository:
    """
    Repository for Sessions & Attendance operations.
    Enforces strict tenant isolation at query level for every read, write, and count.
    """

    # ==========================================
    # --- Session Management ---
    # ==========================================

    @staticmethod
    def create_session(db: Session, teacher_id: str, data: SessionCreate) -> ClassSession:
        """Create a new class session after verifying group ownership."""
        group = db.query(Group).filter(
            Group.id == data.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            raise ValueError("المجموعة غير موجودة أو لا تتبع هذا المعلم")

        session_obj = ClassSession(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            group_id=data.group_id,
            session_date=data.session_date,
            start_time=data.start_time,
            end_time=data.end_time,
            location=data.location.strip() if data.location else None,
            notes=data.notes.strip() if data.notes else None,
            status=data.status or "scheduled",
        )
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
        return session_obj

    @staticmethod
    def get_session_by_id(db: Session, teacher_id: str, session_id: str) -> Optional[ClassSession]:
        """Fetch a single session strictly scoped to teacher."""
        return db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()

    @staticmethod
    def list_sessions(
        db: Session,
        teacher_id: str,
        group_id: Optional[str] = None,
        session_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[ClassSession], int]:
        """List sessions with filtering, strictly scoped to teacher."""
        query = db.query(ClassSession).filter(
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        )

        if group_id:
            query = query.filter(ClassSession.group_id == group_id)

        if session_date:
            query = query.filter(ClassSession.session_date == session_date)
        else:
            if start_date:
                query = query.filter(ClassSession.session_date >= start_date)
            if end_date:
                query = query.filter(ClassSession.session_date <= end_date)

        if status:
            query = query.filter(ClassSession.status == status)

        total = query.count()
        sessions = query.order_by(
            ClassSession.session_date.desc(),
            ClassSession.start_time.desc()
        ).offset(offset).limit(limit).all()

        return sessions, total

    @staticmethod
    def update_session(db: Session, teacher_id: str, session_id: str, data: SessionUpdate) -> Optional[ClassSession]:
        """Update session details."""
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(session_obj, key):
                if isinstance(value, str):
                    value = value.strip()
                setattr(session_obj, key, value)

        if session_obj.start_time and session_obj.end_time:
            if session_obj.end_time <= session_obj.start_time:
                raise ValueError("وقت الانتهاء يجب أن يكون بعد وقت بدء الحصة")

        session_obj.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session_obj)
        return session_obj

    @staticmethod
    def cancel_session(db: Session, teacher_id: str, session_id: str) -> Optional[ClassSession]:
        """Cancel a session."""
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            return None

        session_obj.status = "cancelled"
        session_obj.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session_obj)
        return session_obj

    # ==========================================
    # --- Attendance Taking Operations ---
    # ==========================================

    @staticmethod
    def get_session_stats(db: Session, teacher_id: str, session_id: str, group_id: str) -> SessionAttendanceStats:
        """Calculate attendance summary statistics for a session."""
        # Total enrolled active students in group
        enrolled_count = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).count()

        # Count attendance records by status
        counts = db.query(
            Attendance.status,
            func.count(Attendance.id)
        ).filter(
            Attendance.session_id == session_id,
            Attendance.teacher_id == teacher_id,
            Attendance.is_deleted == False
        ).group_by(Attendance.status).all()

        status_map = {status: count for status, count in counts}
        present_count = status_map.get("present", 0)
        absent_count = status_map.get("absent", 0)
        late_count = status_map.get("late", 0)
        excused_count = status_map.get("excused", 0)

        recorded_total = present_count + absent_count + late_count + excused_count
        unrecorded_count = max(0, enrolled_count - recorded_total)

        return SessionAttendanceStats(
            total_enrolled=enrolled_count,
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            excused_count=excused_count,
            unrecorded_count=unrecorded_count
        )

    @staticmethod
    def get_session_attendance_sheet(db: Session, teacher_id: str, session_id: str) -> Dict[str, Any]:
        """
        Build the full attendance sheet for a session:
        Returns the session details, all actively enrolled students in the session's group,
        their current attendance status (if recorded), and attendance summary stats.
        """
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            return None

        # Fetch group
        group = db.query(Group).filter(
            Group.id == session_obj.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()

        # Fetch active enrolled students
        enrollments = db.query(GroupStudent, Student).join(
            Student, GroupStudent.student_id == Student.id
        ).filter(
            GroupStudent.group_id == session_obj.group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        # Fetch existing attendance records for this session
        attendance_records = db.query(Attendance).filter(
            Attendance.session_id == session_id,
            Attendance.teacher_id == teacher_id,
            Attendance.is_deleted == False
        ).all()
        att_map = {rec.student_id: rec for rec in attendance_records}

        students_list = []
        for enroll, student in enrollments:
            rec = att_map.get(student.id)
            students_list.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "student_phone": student.phone,
                "parent_phone": student.parent_phone,
                "attendance_id": rec.id if rec else None,
                "status": rec.status if rec else None,
                "status_label": ATTENDANCE_STATUS_LABELS.get(rec.status) if rec else "غير مسجل",
                "notes": rec.notes if rec else None,
                "updated_at": rec.updated_at if rec else None,
            })

        stats = AttendanceRepository.get_session_stats(db, teacher_id, session_id, session_obj.group_id)

        session_dict = {
            "id": session_obj.id,
            "group_id": session_obj.group_id,
            "group_name": group.name if group else "",
            "grade_level": group.grade_level if group else "",
            "grade_label": GRADE_LABELS.get(group.grade_level, "") if group else "",
            "session_date": session_obj.session_date,
            "start_time": session_obj.start_time,
            "end_time": session_obj.end_time,
            "location": session_obj.location,
            "notes": session_obj.notes,
            "status": session_obj.status,
            "status_label": SESSION_STATUS_LABELS.get(session_obj.status, session_obj.status),
            "stats": stats,
            "created_at": session_obj.created_at,
        }

        return {
            "session": session_dict,
            "students": students_list,
            "stats": stats
        }

    @staticmethod
    def mark_single_attendance(
        db: Session,
        teacher_id: str,
        session_id: str,
        student_id: str,
        status: str,
        notes: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> Attendance:
        """
        Record or update attendance for an individual student.
        Verifies that student is actively enrolled in session's group.
        """
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            raise ValueError("الحصة غير موجودة أو لا تتبع هذا المعلم")
        if session_obj.status == "cancelled":
            raise ValueError("لا يمكن رصد أو تعديل الحضور لحصة ملغاة")

        # Verify enrollment
        enrollment = db.query(GroupStudent).filter(
            GroupStudent.group_id == session_obj.group_id,
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).first()
        if not enrollment:
            raise ValueError("الطالب غير مسجل في هذه المجموعة")

        # Check existing attendance
        rec = db.query(Attendance).filter(
            Attendance.session_id == session_id,
            Attendance.student_id == student_id,
            Attendance.teacher_id == teacher_id,
            Attendance.is_deleted == False
        ).first()

        now = datetime.now(timezone.utc)
        if rec:
            rec.status = status
            if notes is not None:
                rec.notes = notes.strip() if notes else None
            rec.recorded_by_user_id = user_id
            rec.recorded_by_user_type = user_type
            rec.updated_at = now
        else:
            rec = Attendance(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                session_id=session_id,
                student_id=student_id,
                status=status,
                notes=notes.strip() if notes else None,
                recorded_by_user_id=user_id,
                recorded_by_user_type=user_type,
            )
            db.add(rec)

        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def bulk_mark_attendance(
        db: Session,
        teacher_id: str,
        session_id: str,
        records: List[AttendanceMarkItem],
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> int:
        """
        Bulk upsert attendance records atomically in a transaction.
        If ANY student is not enrolled in the session's group, transaction aborts.
        """
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            raise ValueError("الحصة غير موجودة أو لا تتبع هذا المعلم")
        if session_obj.status == "cancelled":
            raise ValueError("لا يمكن رصد أو تعديل الحضور لحصة ملغاة")

        # Get all valid enrolled active student IDs
        enrolled_student_ids = {
            s_id for (s_id,) in db.query(GroupStudent.student_id).filter(
                GroupStudent.group_id == session_obj.group_id,
                GroupStudent.teacher_id == teacher_id,
                GroupStudent.is_active == True,
                GroupStudent.is_deleted == False
            ).all()
        }

        # Validate that all requested student IDs are enrolled and distinct
        student_ids = [item.student_id for item in records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError("لا يمكن تكرار نفس الطالب أكثر من مرة في كشف الحضور المجمع")

        for item in records:
            if item.student_id not in enrolled_student_ids:
                raise ValueError(f"الطالب برقم المعرف {item.student_id} غير مسجل في هذه المجموعة")

        # Fetch existing records for this session to upsert
        existing_records = {
            r.student_id: r for r in db.query(Attendance).filter(
                Attendance.session_id == session_id,
                Attendance.teacher_id == teacher_id,
                Attendance.is_deleted == False
            ).all()
        }

        now = datetime.now(timezone.utc)
        count = 0
        for item in records:
            rec = existing_records.get(item.student_id)
            if rec:
                rec.status = item.status
                if item.notes is not None:
                    rec.notes = item.notes.strip() if item.notes else None
                rec.recorded_by_user_id = user_id
                rec.recorded_by_user_type = user_type
                rec.updated_at = now
            else:
                new_rec = Attendance(
                    id=str(uuid.uuid4()),
                    teacher_id=teacher_id,
                    session_id=session_id,
                    student_id=item.student_id,
                    status=item.status,
                    notes=item.notes.strip() if item.notes else None,
                    recorded_by_user_id=user_id,
                    recorded_by_user_type=user_type,
                )
                db.add(new_rec)
            count += 1

        db.commit()
        return count

    @staticmethod
    def scan_barcode(
        db: Session,
        teacher_id: str,
        session_id: str,
        barcode: str,
        notes: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle barcode scan input for a session.
        Matches barcode as student ID (opaque identifier).
        Verifies enrollment, updates or marks present, detects duplicate scans gracefully.
        """
        barcode_clean = barcode.strip()
        session_obj = db.query(ClassSession).filter(
            ClassSession.id == session_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).first()
        if not session_obj:
            raise ValueError("الحصة غير موجودة أو لا تتبع هذا المعلم")
        if session_obj.status == "cancelled":
            raise ValueError("لا يمكن رصد أو تعديل الحضور لحصة ملغاة")

        # Find student by ID strictly scoped to teacher
        student = db.query(Student).filter(
            Student.id == barcode_clean,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            raise LookupError("لم يتم العثور على طالب بهذا الرمز أو المعرف")

        # Check if student is actively enrolled in the session's group
        enrollment = db.query(GroupStudent).filter(
            GroupStudent.group_id == session_obj.group_id,
            GroupStudent.student_id == student.id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).first()
        if not enrollment:
            raise PermissionError(f"الطالب '{student.full_name}' ليس مسجلاً في مجموعة هذه الحصة")

        # Check existing attendance record
        rec = db.query(Attendance).filter(
            Attendance.session_id == session_id,
            Attendance.student_id == student.id,
            Attendance.teacher_id == teacher_id,
            Attendance.is_deleted == False
        ).first()

        student_info = {
            "id": student.id,
            "full_name": student.full_name,
            "phone": student.phone,
            "grade_level": student.grade_level,
            "grade_label": GRADE_LABELS.get(student.grade_level, "")
        }

        now = datetime.now(timezone.utc)
        if rec and rec.status == "present":
            return {
                "success": True,
                "action": "already_present",
                "message": f"الطالب '{student.full_name}' مسجل حاضر بالفعل مسبقاً",
                "student": student_info,
                "status": "present",
                "status_label": ATTENDANCE_STATUS_LABELS["present"],
                "timestamp": now.strftime("%H:%M:%S")
            }

        if rec:
            rec.status = "present"
            if notes:
                rec.notes = notes.strip()
            rec.recorded_by_user_id = user_id
            rec.recorded_by_user_type = user_type
            rec.updated_at = now
            action = "status_changed"
            msg = f"تم تعديل حالة الطالب '{student.full_name}' إلى حاضر بنجاح"
        else:
            rec = Attendance(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                session_id=session_id,
                student_id=student.id,
                status="present",
                notes=notes.strip() if notes else None,
                recorded_by_user_id=user_id,
                recorded_by_user_type=user_type,
            )
            db.add(rec)
            action = "recorded"
            msg = f"تم تسجيل حضور الطالب '{student.full_name}' بنجاح"

        db.commit()
        db.refresh(rec)

        return {
            "success": True,
            "action": action,
            "message": msg,
            "student": student_info,
            "status": "present",
            "status_label": ATTENDANCE_STATUS_LABELS["present"],
            "timestamp": now.strftime("%H:%M:%S")
        }

    # ==========================================
    # --- Reports & History ---
    # ==========================================

    @staticmethod
    def get_student_attendance_history(
        db: Session,
        teacher_id: str,
        student_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get complete attendance history and rate for a student."""
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            return None

        records = db.query(Attendance, ClassSession, Group).join(
            ClassSession, Attendance.session_id == ClassSession.id
        ).outerjoin(
            Group, ClassSession.group_id == Group.id
        ).filter(
            Attendance.student_id == student_id,
            Attendance.teacher_id == teacher_id,
            Attendance.is_deleted == False,
            ClassSession.is_deleted == False
        ).order_by(ClassSession.session_date.desc(), ClassSession.start_time.desc()).all()

        history = []
        present_count = 0
        absent_count = 0
        late_count = 0
        excused_count = 0

        for att, sess, grp in records:
            if sess.status == "cancelled":
                history.append({
                    "session_id": sess.id,
                    "session_date": sess.session_date,
                    "start_time": sess.start_time,
                    "group_id": grp.id if grp else sess.group_id,
                    "group_name": grp.name if grp else "مجموعة سابقة",
                    "status": "cancelled",
                    "status_label": "حصة ملغاة",
                    "notes": sess.notes or att.notes,
                    "recorded_at": att.updated_at
                })
                continue

            if att.status == "present":
                present_count += 1
            elif att.status == "absent":
                absent_count += 1
            elif att.status == "late":
                late_count += 1
            elif att.status == "excused":
                excused_count += 1

            history.append({
                "session_id": sess.id,
                "session_date": sess.session_date,
                "start_time": sess.start_time,
                "group_id": grp.id if grp else sess.group_id,
                "group_name": grp.name if grp else "مجموعة سابقة",
                "status": att.status,
                "status_label": ATTENDANCE_STATUS_LABELS.get(att.status, att.status),
                "notes": att.notes,
                "recorded_at": att.updated_at
            })

        total = present_count + absent_count + late_count + excused_count
        applicable = present_count + late_count + absent_count
        attendance_rate = round(((present_count + late_count) / applicable * 100), 1) if applicable > 0 else (100.0 if excused_count > 0 else 0.0)

        return {
            "student_id": student.id,
            "student_name": student.full_name,
            "total_sessions": total,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "excused_count": excused_count,
            "attendance_rate": attendance_rate,
            "history": history
        }

    @staticmethod
    def get_group_attendance_summary(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get aggregate attendance summary for a group."""
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            return None

        # Total enrolled active students
        total_students = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).count()

        # Sessions for this group
        sessions = db.query(ClassSession).filter(
            ClassSession.group_id == group_id,
            ClassSession.teacher_id == teacher_id,
            ClassSession.is_deleted == False
        ).order_by(ClassSession.session_date.desc()).all()

        active_sessions = [s for s in sessions if s.status != "cancelled"]
        total_sessions = len(active_sessions)
        recent_sessions_data = []
        overall_rates = []

        for sess in sessions[:10]:
            stats = AttendanceRepository.get_session_stats(db, teacher_id, sess.id, group_id)
            if sess.status != "cancelled" and stats.total_enrolled > 0:
                rate = round(((stats.present_count + stats.late_count) / stats.total_enrolled) * 100, 1)
                overall_rates.append(rate)

            recent_sessions_data.append({
                "id": sess.id,
                "group_id": sess.group_id,
                "group_name": group.name,
                "grade_level": group.grade_level,
                "grade_label": GRADE_LABELS.get(group.grade_level, ""),
                "session_date": sess.session_date,
                "start_time": sess.start_time,
                "end_time": sess.end_time,
                "location": sess.location,
                "notes": sess.notes,
                "status": sess.status,
                "status_label": SESSION_STATUS_LABELS.get(sess.status, sess.status),
                "stats": stats,
                "created_at": sess.created_at
            })

        avg_rate = round(sum(overall_rates) / len(overall_rates), 1) if overall_rates else 0.0

        return {
            "group_id": group.id,
            "group_name": group.name,
            "grade_level": group.grade_level,
            "grade_label": GRADE_LABELS.get(group.grade_level, ""),
            "total_sessions": total_sessions,
            "total_students": total_students,
            "average_attendance_rate": avg_rate,
            "recent_sessions": recent_sessions_data
        }
