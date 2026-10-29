import uuid
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models.academic import Student, Group, GroupStudent, GRADE_LABELS
from app.models.exam import (
    Exam,
    ExamResult,
    VALID_EXAM_STATUSES,
    EXAM_STATUS_LABELS,
    VALID_RESULT_STATUSES,
    RESULT_STATUS_LABELS,
)
from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamResultItem,
    ExamStats,
)


class ExamRepository:
    """
    Repository for Exams & Grades operations.
    Strictly enforces tenant isolation at query level for every read, write, and count.
    """

    # ==========================================
    # --- Exam Management ---
    # ==========================================

    @staticmethod
    def create_exam(db: Session, teacher_id: str, data: ExamCreate) -> Exam:
        """Create a new exam after verifying group ownership."""
        group = db.query(Group).filter(
            Group.id == data.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            raise ValueError("المجموعة غير موجودة أو لا تتبع هذا المعلم")

        if data.max_score <= 0:
            raise ValueError("الدرجة العظمى للامتحان يجب أن تكون أكبر من الصفر")
        if data.passing_score < 0 or data.passing_score > data.max_score:
            raise ValueError("درجة النجاح يجب أن تكون بين الصفر والدرجة العظمى")

        exam = Exam(
            id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            group_id=data.group_id,
            title=data.title.strip(),
            exam_date=data.exam_date,
            max_score=data.max_score,
            passing_score=data.passing_score,
            description=data.description.strip() if data.description else None,
            status=data.status or "scheduled",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return exam

    @staticmethod
    def get_exam_by_id(db: Session, teacher_id: str, exam_id: str) -> Optional[Exam]:
        """Fetch single exam strictly scoped to teacher."""
        return db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()

    @staticmethod
    def list_exams(
        db: Session,
        teacher_id: str,
        group_id: Optional[str] = None,
        exam_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Exam], int]:
        """List exams with filtering, strictly scoped to teacher."""
        query = db.query(Exam).filter(
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        )

        if group_id:
            query = query.filter(Exam.group_id == group_id)

        if exam_date:
            query = query.filter(Exam.exam_date == exam_date)
        else:
            if start_date:
                query = query.filter(Exam.exam_date >= start_date)
            if end_date:
                query = query.filter(Exam.exam_date <= end_date)

        if status:
            query = query.filter(Exam.status == status)

        total = query.count()
        exams = query.order_by(
            Exam.exam_date.desc(),
            Exam.created_at.desc()
        ).offset(offset).limit(limit).all()

        return exams, total

    @staticmethod
    def update_exam(db: Session, teacher_id: str, exam_id: str, data: ExamUpdate) -> Optional[Exam]:
        """
        Update exam details.
        Safely enforces that max_score cannot be reduced below any already-recorded score.
        If exam is completed, changing max_score, passing_score, or group_id is forbidden.
        """
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            return None

        update_dict = data.model_dump(exclude_unset=True)

        # Check if exam is completed
        if exam.status == "completed":
            protected_fields = {"max_score", "passing_score", "group_id"}
            if any(f in update_dict for f in protected_fields):
                raise ValueError("لا يمكن تعديل درجات النجاح أو الدرجة العظمى لامتحان مكتمل بالفعل")

        # Check max_score safety against already recorded results
        new_max = update_dict.get("max_score", exam.max_score)
        new_passing = update_dict.get("passing_score", exam.passing_score)

        if new_max <= 0:
            raise ValueError("الدرجة العظمى يجب أن تكون أكبر من الصفر")
        if new_passing < 0 or new_passing > new_max:
            raise ValueError("درجة النجاح يجب أن تكون بين الصفر والدرجة العظمى")

        if "max_score" in update_dict and update_dict["max_score"] < exam.max_score:
            highest_score = db.query(func.max(ExamResult.score)).filter(
                ExamResult.exam_id == exam_id,
                ExamResult.teacher_id == teacher_id,
                ExamResult.status == "attended",
                ExamResult.is_deleted == False
            ).scalar()
            if highest_score is not None and update_dict["max_score"] < highest_score:
                raise ValueError(
                    f"لا يمكن تقليل الدرجة العظمى إلى {update_dict['max_score']} لوجود نتائج مسجلة بدرجة أعلى (أعلى درجة: {highest_score})"
                )

        for key, value in update_dict.items():
            if hasattr(exam, key):
                if isinstance(value, str):
                    value = value.strip()
                setattr(exam, key, value)

        exam.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exam)
        return exam

    @staticmethod
    def complete_exam(db: Session, teacher_id: str, exam_id: str) -> Optional[Exam]:
        """Mark an exam as completed."""
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            return None

        exam.status = "completed"
        exam.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exam)
        return exam

    @staticmethod
    def cancel_exam(db: Session, teacher_id: str, exam_id: str) -> Optional[Exam]:
        """Mark an exam as cancelled."""
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            return None

        exam.status = "cancelled"
        exam.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exam)
        return exam

    @staticmethod
    def delete_exam(db: Session, teacher_id: str, exam_id: str) -> bool:
        """Soft-delete an exam."""
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            return False

        exam.is_deleted = True
        exam.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    # ==========================================
    # --- Exam Statistics & Sheet ---
    # ==========================================

    @staticmethod
    def get_exam_stats(
        db: Session,
        teacher_id: str,
        exam_id: str,
        group_id: str,
        passing_score: float,
        max_score: float
    ) -> ExamStats:
        """
        Compute statistics for an exam with explicit, non-zero-fabricating rules:
        - absent, excused, and unrecorded students are NEVER averaged in as zero.
        - pass_rate denominator is strictly attended_count.
        """
        total_enrolled = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).count()

        results = db.query(ExamResult).filter(
            ExamResult.exam_id == exam_id,
            ExamResult.teacher_id == teacher_id,
            ExamResult.is_deleted == False
        ).all()

        results_recorded = len(results)
        results_pending = max(0, total_enrolled - results_recorded)

        attended_count = 0
        absent_count = 0
        excused_count = 0
        scores = []
        pass_count = 0
        fail_count = 0

        for r in results:
            if r.status == "attended":
                attended_count += 1
                if r.score is not None:
                    scores.append(r.score)
                    if r.score >= passing_score:
                        pass_count += 1
                    else:
                        fail_count += 1
            elif r.status == "absent":
                absent_count += 1
            elif r.status == "excused":
                excused_count += 1

        pass_rate = round((pass_count / attended_count * 100), 1) if attended_count > 0 else 0.0
        average_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        average_percentage = round((average_score / max_score * 100), 1) if (scores and max_score > 0) else 0.0
        highest_score = max(scores) if scores else None
        lowest_score = min(scores) if scores else None

        return ExamStats(
            total_enrolled=total_enrolled,
            results_recorded=results_recorded,
            results_pending=results_pending,
            attended_count=attended_count,
            absent_count=absent_count,
            excused_count=excused_count,
            pass_count=pass_count,
            fail_count=fail_count,
            pass_rate=pass_rate,
            average_score=average_score,
            average_percentage=average_percentage,
            highest_score=highest_score,
            lowest_score=lowest_score
        )

    @staticmethod
    def get_exam_results_sheet(db: Session, teacher_id: str, exam_id: str) -> Optional[Dict[str, Any]]:
        """
        Build complete exam results sheet:
        Lists all actively enrolled students in the exam's group,
        their scores and percentage (if attended), status, and summary statistics.
        """
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            return None

        group = db.query(Group).filter(
            Group.id == exam.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()

        # Enrolled active students
        enrollments = db.query(GroupStudent, Student).join(
            Student, GroupStudent.student_id == Student.id
        ).filter(
            GroupStudent.group_id == exam.group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        # Existing results
        results = db.query(ExamResult).filter(
            ExamResult.exam_id == exam_id,
            ExamResult.teacher_id == teacher_id,
            ExamResult.is_deleted == False
        ).all()
        res_map = {r.student_id: r for r in results}

        students_list = []
        for enroll, student in enrollments:
            rec = res_map.get(student.id)
            score = rec.score if (rec and rec.status == "attended") else None
            percentage = round((score / exam.max_score * 100), 1) if (score is not None and exam.max_score > 0) else None
            is_passed = (score >= exam.passing_score) if score is not None else None

            students_list.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "student_phone": student.phone,
                "parent_phone": student.parent_phone,
                "result_id": rec.id if rec else None,
                "score": score,
                "percentage": percentage,
                "is_passed": is_passed,
                "status": rec.status if rec else None,
                "status_label": RESULT_STATUS_LABELS.get(rec.status) if rec else "قيد الانتظار",
                "notes": rec.notes if rec else None,
                "updated_at": rec.updated_at if rec else None,
            })

        stats = ExamRepository.get_exam_stats(
            db, teacher_id, exam.id, exam.group_id, exam.passing_score, exam.max_score
        )

        exam_dict = {
            "id": exam.id,
            "group_id": exam.group_id,
            "group_name": group.name if group else "",
            "grade_level": group.grade_level if group else "",
            "grade_label": GRADE_LABELS.get(group.grade_level, "") if group else "",
            "title": exam.title,
            "exam_date": exam.exam_date,
            "max_score": exam.max_score,
            "passing_score": exam.passing_score,
            "description": exam.description,
            "status": exam.status,
            "status_label": EXAM_STATUS_LABELS.get(exam.status, exam.status),
            "stats": stats,
            "created_at": exam.created_at,
        }

        return {
            "exam": exam_dict,
            "students": students_list,
            "stats": stats
        }

    # ==========================================
    # --- Recording & Bulk Results ---
    # ==========================================

    @staticmethod
    def record_single_result(
        db: Session,
        teacher_id: str,
        exam_id: str,
        student_id: str,
        status: str,
        score: Optional[float] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> ExamResult:
        """
        Record or update exam result for a single student.
        Validates enrollment and score constraints.
        """
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            raise ValueError("الامتحان غير موجود أو لا تتبع هذا المعلم")
        if exam.status == "cancelled":
            raise ValueError("لا يمكن رصد أو تعديل درجات امتحان ملغى")

        # Verify active enrollment
        enrollment = db.query(GroupStudent).filter(
            GroupStudent.group_id == exam.group_id,
            GroupStudent.student_id == student_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).first()
        if not enrollment:
            raise ValueError("الطالب غير مسجل في هذه المجموعة")

        # Score validation
        if status == "attended":
            if score is None:
                raise ValueError("الدرجة مطلوبة عند تسجيل حضور الطالب في الامتحان")
            if score < 0:
                raise ValueError("لا يمكن أن تكون الدرجة سالبة")
            if score > exam.max_score:
                raise ValueError(f"الدرجة ({score}) أكبر من الدرجة العظمى للامتحان ({exam.max_score})")
        else:
            score = None  # No fabricated score for absent/excused

        # Check existing result
        rec = db.query(ExamResult).filter(
            ExamResult.exam_id == exam_id,
            ExamResult.student_id == student_id,
            ExamResult.teacher_id == teacher_id,
            ExamResult.is_deleted == False
        ).first()

        now = datetime.now(timezone.utc)
        if rec:
            rec.status = status
            rec.score = score
            if notes is not None:
                rec.notes = notes.strip() if notes else None
            rec.recorded_by_user_id = user_id
            rec.recorded_by_user_type = user_type
            rec.updated_at = now
        else:
            rec = ExamResult(
                id=str(uuid.uuid4()),
                teacher_id=teacher_id,
                exam_id=exam_id,
                student_id=student_id,
                status=status,
                score=score,
                notes=notes.strip() if notes else None,
                recorded_by_user_id=user_id,
                recorded_by_user_type=user_type,
            )
            db.add(rec)

        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def bulk_record_results(
        db: Session,
        teacher_id: str,
        exam_id: str,
        records: List[ExamResultItem],
        user_id: Optional[str] = None,
        user_type: Optional[str] = None
    ) -> int:
        """
        Bulk upsert exam results atomically in a transaction.
        Aborts if any student is not enrolled, if score exceeds max, or duplicate student in batch.
        """
        exam = db.query(Exam).filter(
            Exam.id == exam_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).first()
        if not exam:
            raise ValueError("الامتحان غير موجود أو لا تتبع هذا المعلم")
        if exam.status == "cancelled":
            raise ValueError("لا يمكن رصد أو تعديل درجات امتحان ملغى")

        # Distinct check in batch
        student_ids = [item.student_id for item in records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError("لا يمكن تكرار نفس الطالب أكثر من مرة في كشف الدرجات المجمع")

        # Get all valid enrolled active student IDs
        enrolled_student_ids = {
            s_id for (s_id,) in db.query(GroupStudent.student_id).filter(
                GroupStudent.group_id == exam.group_id,
                GroupStudent.teacher_id == teacher_id,
                GroupStudent.is_active == True,
                GroupStudent.is_deleted == False
            ).all()
        }

        # Full validation before any write
        for item in records:
            if item.student_id not in enrolled_student_ids:
                raise ValueError(f"الطالب برقم المعرف {item.student_id} غير مسجل في هذه المجموعة")
            if item.status == "attended":
                if item.score is None:
                    raise ValueError(f"الدرجة مطلوبة للطالب {item.student_id}")
                if item.score < 0:
                    raise ValueError(f"لا يمكن أن تكون الدرجة سالبة للطالب {item.student_id}")
                if item.score > exam.max_score:
                    raise ValueError(f"درجة الطالب ({item.score}) تتجاوز الدرجة العظمى للامتحان ({exam.max_score})")

        # Fetch existing records
        existing_records = {
            r.student_id: r for r in db.query(ExamResult).filter(
                ExamResult.exam_id == exam_id,
                ExamResult.teacher_id == teacher_id,
                ExamResult.is_deleted == False
            ).all()
        }

        now = datetime.now(timezone.utc)
        count = 0
        for item in records:
            actual_score = item.score if item.status == "attended" else None
            rec = existing_records.get(item.student_id)
            if rec:
                rec.status = item.status
                rec.score = actual_score
                if item.notes is not None:
                    rec.notes = item.notes.strip() if item.notes else None
                rec.recorded_by_user_id = user_id
                rec.recorded_by_user_type = user_type
                rec.updated_at = now
            else:
                new_rec = ExamResult(
                    id=str(uuid.uuid4()),
                    teacher_id=teacher_id,
                    exam_id=exam_id,
                    student_id=item.student_id,
                    status=item.status,
                    score=actual_score,
                    notes=item.notes.strip() if item.notes else None,
                    recorded_by_user_id=user_id,
                    recorded_by_user_type=user_type,
                )
                db.add(new_rec)
            count += 1

        db.commit()
        return count

    # ==========================================
    # --- Reports & History ---
    # ==========================================

    @staticmethod
    def get_student_exam_history(
        db: Session,
        teacher_id: str,
        student_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get complete exam history and pass rate for a student."""
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.teacher_id == teacher_id,
            Student.is_deleted == False
        ).first()
        if not student:
            return None

        records = db.query(ExamResult, Exam, Group).join(
            Exam, ExamResult.exam_id == Exam.id
        ).outerjoin(
            Group, Exam.group_id == Group.id
        ).filter(
            ExamResult.student_id == student_id,
            ExamResult.teacher_id == teacher_id,
            ExamResult.is_deleted == False,
            Exam.is_deleted == False
        ).order_by(Exam.exam_date.desc(), Exam.created_at.desc()).all()

        history = []
        attended_count = 0
        absent_count = 0
        excused_count = 0
        passed_count = 0
        failed_count = 0
        percentages = []

        for res, ex, grp in records:
            if ex.status == "cancelled":
                history.append({
                    "exam_id": ex.id,
                    "exam_title": ex.title,
                    "exam_date": ex.exam_date,
                    "group_id": grp.id if grp else ex.group_id,
                    "group_name": grp.name if grp else "مجموعة سابقة",
                    "max_score": ex.max_score,
                    "passing_score": ex.passing_score,
                    "score": None,
                    "percentage": None,
                    "is_passed": None,
                    "status": "cancelled",
                    "status_label": "امتحان ملغى",
                    "notes": ex.description or res.notes,
                    "recorded_at": res.updated_at
                })
                continue

            pct = None
            is_passed = None

            if res.status == "attended":
                attended_count += 1
                if res.score is not None:
                    pct = round((res.score / ex.max_score * 100), 1) if ex.max_score > 0 else 0.0
                    percentages.append(pct)
                    if res.score >= ex.passing_score:
                        passed_count += 1
                        is_passed = True
                    else:
                        failed_count += 1
                        is_passed = False
            elif res.status == "absent":
                absent_count += 1
            elif res.status == "excused":
                excused_count += 1

            history.append({
                "exam_id": ex.id,
                "exam_title": ex.title,
                "exam_date": ex.exam_date,
                "group_id": grp.id if grp else ex.group_id,
                "group_name": grp.name if grp else "مجموعة سابقة",
                "max_score": ex.max_score,
                "passing_score": ex.passing_score,
                "score": res.score if res.status == "attended" else None,
                "percentage": pct,
                "is_passed": is_passed,
                "status": res.status,
                "status_label": RESULT_STATUS_LABELS.get(res.status, res.status),
                "notes": res.notes,
                "recorded_at": res.updated_at
            })

        total_exams = attended_count + absent_count + excused_count
        average_percentage = round(sum(percentages) / len(percentages), 1) if percentages else 0.0
        overall_pass_rate = round((passed_count / attended_count * 100), 1) if attended_count > 0 else 0.0

        return {
            "student_id": student.id,
            "student_name": student.full_name,
            "total_exams": total_exams,
            "attended_count": attended_count,
            "absent_count": absent_count,
            "excused_count": excused_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "average_percentage": average_percentage,
            "overall_pass_rate": overall_pass_rate,
            "history": history
        }

    @staticmethod
    def get_group_exams_summary(
        db: Session,
        teacher_id: str,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get aggregate exams summary for a group."""
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()
        if not group:
            return None

        total_students = db.query(GroupStudent).filter(
            GroupStudent.group_id == group_id,
            GroupStudent.teacher_id == teacher_id,
            GroupStudent.is_active == True,
            GroupStudent.is_deleted == False
        ).count()

        exams = db.query(Exam).filter(
            Exam.group_id == group_id,
            Exam.teacher_id == teacher_id,
            Exam.is_deleted == False
        ).order_by(Exam.exam_date.desc(), Exam.created_at.desc()).all()

        active_exams = [e for e in exams if e.status != "cancelled"]
        total_exams = len(active_exams)

        pass_rates = []
        score_percentages = []
        recent_exams_data = []

        for ex in exams[:10]:
            stats = ExamRepository.get_exam_stats(
                db, teacher_id, ex.id, group_id, ex.passing_score, ex.max_score
            )
            if ex.status != "cancelled" and stats.attended_count > 0:
                pass_rates.append(stats.pass_rate)
                score_percentages.append(stats.average_percentage)

            recent_exams_data.append({
                "id": ex.id,
                "group_id": ex.group_id,
                "group_name": group.name,
                "grade_level": group.grade_level,
                "grade_label": GRADE_LABELS.get(group.grade_level, ""),
                "title": ex.title,
                "exam_date": ex.exam_date,
                "max_score": ex.max_score,
                "passing_score": ex.passing_score,
                "description": ex.description,
                "status": ex.status,
                "status_label": EXAM_STATUS_LABELS.get(ex.status, ex.status),
                "stats": stats,
                "created_at": ex.created_at
            })

        avg_pass_rate = round(sum(pass_rates) / len(pass_rates), 1) if pass_rates else 0.0
        avg_score_pct = round(sum(score_percentages) / len(score_percentages), 1) if score_percentages else 0.0

        return {
            "group_id": group.id,
            "group_name": group.name,
            "grade_level": group.grade_level,
            "grade_label": GRADE_LABELS.get(group.grade_level, ""),
            "total_exams": total_exams,
            "total_students": total_students,
            "average_pass_rate": avg_pass_rate,
            "average_group_score_percentage": avg_score_pct,
            "recent_exams": recent_exams_data
        }
