from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_permission, get_current_user, AuthenticatedUser
from app.models.academic import Group, GRADE_LABELS
from app.models.exam import (
    Exam,
    EXAM_STATUS_LABELS,
    RESULT_STATUS_LABELS,
)
from app.repositories.exam_repo import ExamRepository
from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    ExamStats,
    ExamResultsSheetResponse,
    ExamResultSingleRequest,
    ExamResultBulkRequest,
    StudentExamHistoryResponse,
    GroupExamsSummaryResponse,
)

router = APIRouter(prefix="/api/exams", tags=["Exams & Grades"])


def require_exam_read_permission(
    auth: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """Allow teachers, or assistants who have can_view_grades, can_manage_exams, or can_enter_grades."""
    if auth.is_teacher:
        return auth
    if (
        getattr(auth.user, "can_view_grades", False)
        or getattr(auth.user, "can_manage_exams", False)
        or getattr(auth.user, "can_enter_grades", False)
    ):
        return auth
    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail="Permission denied: Missing grade or exam viewing permissions."
    )


def _format_exam_response(db: Session, teacher_id: str, exam: Exam, group: Optional[Group] = None) -> ExamResponse:
    if not group:
        group = db.query(Group).filter(
            Group.id == exam.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()

    stats = ExamRepository.get_exam_stats(
        db, teacher_id, exam.id, exam.group_id, exam.passing_score, exam.max_score
    )

    return ExamResponse(
        id=exam.id,
        group_id=exam.group_id,
        group_name=group.name if group else "",
        grade_level=group.grade_level if group else "",
        grade_label=GRADE_LABELS.get(group.grade_level, "") if group else "",
        title=exam.title,
        exam_date=exam.exam_date,
        max_score=exam.max_score,
        passing_score=exam.passing_score,
        description=exam.description,
        status=exam.status,
        status_label=EXAM_STATUS_LABELS.get(exam.status, exam.status),
        stats=stats,
        created_at=exam.created_at,
    )


# ==========================================
# --- Exam CRUD & Actions ---
# ==========================================

@router.post("", response_model=ExamResponse, status_code=http_status.HTTP_201_CREATED, summary="Create a new exam")
def create_exam(
    payload: ExamCreate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_exams")),
    db: Session = Depends(get_db)
):
    """
    Create a new exam for an active group belonging to the teacher.
    """
    try:
        exam_obj = ExamRepository.create_exam(db, teacher_id=auth.teacher_id, data=payload)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _format_exam_response(db, auth.teacher_id, exam_obj)


@router.get("", response_model=List[ExamResponse], summary="List and filter exams")
def list_exams(
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    exam_date: Optional[str] = Query(None, description="Filter by exact date YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Filter from start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Filter to end date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="scheduled, completed, cancelled"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_exam_read_permission),
    db: Session = Depends(get_db)
):
    """
    List exams belonging strictly to the teacher workspace.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date"
        )

    exams, _ = ExamRepository.list_exams(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id,
        exam_date=exam_date,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
        offset=offset
    )

    group_ids = {e.group_id for e in exams}
    groups = {g.id: g for g in db.query(Group).filter(Group.id.in_(group_ids)).all()} if group_ids else {}

    results = []
    for ex in exams:
        results.append(_format_exam_response(db, auth.teacher_id, ex, groups.get(ex.group_id)))
    return results


# Notice: Put static /reports routes BEFORE parameterized /{exam_id} route
@router.get("/reports/student/{student_id}", response_model=StudentExamHistoryResponse, summary="Get student exam history")
def get_student_history(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_exam_read_permission),
    db: Session = Depends(get_db)
):
    """
    Retrieve exam history and overall pass rate for a specific student.
    """
    history_data = ExamRepository.get_student_exam_history(
        db=db,
        teacher_id=auth.teacher_id,
        student_id=student_id
    )
    if not history_data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الطالب غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return history_data


@router.get("/reports/group/{group_id}", response_model=GroupExamsSummaryResponse, summary="Get group exams summary")
def get_group_summary(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_exam_read_permission),
    db: Session = Depends(get_db)
):
    """
    Retrieve aggregate exams summary and recent exams for a group.
    """
    summary_data = ExamRepository.get_group_exams_summary(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id
    )
    if not summary_data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="المجموعة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return summary_data


@router.get("/{exam_id}", response_model=ExamResponse, summary="Get exam details")
def get_exam(
    exam_id: str,
    auth: AuthenticatedUser = Depends(require_exam_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get single exam details scoped strictly to teacher.
    """
    exam_obj = ExamRepository.get_exam_by_id(db, auth.teacher_id, exam_id)
    if not exam_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return _format_exam_response(db, auth.teacher_id, exam_obj)


@router.put("/{exam_id}", response_model=ExamResponse, summary="Update exam details")
def update_exam(
    exam_id: str,
    payload: ExamUpdate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_exams")),
    db: Session = Depends(get_db)
):
    """
    Update exam details (title, date, max_score, passing_score, description, status).
    Guards against reducing max_score below recorded scores and editing completed exams.
    """
    try:
        exam_obj = ExamRepository.update_exam(db, auth.teacher_id, exam_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not exam_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return _format_exam_response(db, auth.teacher_id, exam_obj)


@router.post("/{exam_id}/complete", response_model=ExamResponse, summary="Complete exam")
def complete_exam(
    exam_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_exams")),
    db: Session = Depends(get_db)
):
    """
    Mark an exam as completed.
    """
    exam_obj = ExamRepository.complete_exam(db, auth.teacher_id, exam_id)
    if not exam_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return _format_exam_response(db, auth.teacher_id, exam_obj)


@router.post("/{exam_id}/cancel", response_model=ExamResponse, summary="Cancel exam")
def cancel_exam(
    exam_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_exams")),
    db: Session = Depends(get_db)
):
    """
    Mark an exam as cancelled.
    """
    exam_obj = ExamRepository.cancel_exam(db, auth.teacher_id, exam_id)
    if not exam_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return _format_exam_response(db, auth.teacher_id, exam_obj)


@router.delete("/{exam_id}", summary="Delete exam")
def delete_exam(
    exam_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_exams")),
    db: Session = Depends(get_db)
):
    """
    Soft-delete an exam.
    """
    success = ExamRepository.delete_exam(db, auth.teacher_id, exam_id)
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return {"success": True, "message": "تم حذف الامتحان بنجاح"}


# ==========================================
# --- Exam Results Endpoints ---
# ==========================================

@router.get("/{exam_id}/results", response_model=ExamResultsSheetResponse, summary="Get exam results sheet")
def get_exam_results(
    exam_id: str,
    auth: AuthenticatedUser = Depends(require_exam_read_permission),
    db: Session = Depends(get_db)
):
    """
    Get full results sheet: all enrolled students in the exam's group,
    their scores, percentage, pass/fail status, and summary statistics.
    """
    sheet = ExamRepository.get_exam_results_sheet(db, auth.teacher_id, exam_id)
    if not sheet:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الامتحان غير موجود أو لا تملك صلاحية الوصول إليه"
        )
    return sheet


@router.post("/{exam_id}/results", summary="Record single student result")
def record_result(
    exam_id: str,
    payload: ExamResultSingleRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_enter_grades")),
    db: Session = Depends(get_db)
):
    """
    Record or update score/status for an individual student.
    """
    try:
        rec = ExamRepository.record_single_result(
            db=db,
            teacher_id=auth.teacher_id,
            exam_id=exam_id,
            student_id=payload.student_id,
            status=payload.status,
            score=payload.score,
            notes=payload.notes,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "id": rec.id,
        "exam_id": rec.exam_id,
        "student_id": rec.student_id,
        "status": rec.status,
        "status_label": RESULT_STATUS_LABELS.get(rec.status, rec.status),
        "score": rec.score,
        "notes": rec.notes,
        "updated_at": rec.updated_at
    }


@router.post("/{exam_id}/results/bulk", summary="Bulk record exam results")
def bulk_record_results(
    exam_id: str,
    payload: ExamResultBulkRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_enter_grades")),
    db: Session = Depends(get_db)
):
    """
    Bulk upsert exam results atomically in a transaction.
    Aborts if any student is not enrolled or if score exceeds max_score.
    """
    try:
        count = ExamRepository.bulk_record_results(
            db=db,
            teacher_id=auth.teacher_id,
            exam_id=exam_id,
            records=payload.records,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "count": count,
        "message": f"تم رصد درجات {count} طالب بنجاح"
    }
