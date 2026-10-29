from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_permission, AuthenticatedUser
from app.models.academic import Group, GRADE_LABELS
from app.models.attendance import (
    ClassSession,
    SESSION_STATUS_LABELS,
    ATTENDANCE_STATUS_LABELS,
)
from app.repositories.attendance_repo import AttendanceRepository
from app.schemas.attendance import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionAttendanceStats,
    SessionAttendanceSheetResponse,
    AttendanceMarkSingleRequest,
    AttendanceBulkRequest,
    AttendanceScanRequest,
    AttendanceScanResponse,
    StudentAttendanceHistoryResponse,
    GroupAttendanceSummaryResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["Sessions & Attendance"])


def _format_session_response(db: Session, teacher_id: str, sess: ClassSession, group: Optional[Group] = None) -> SessionResponse:
    if not group:
        group = db.query(Group).filter(
            Group.id == sess.group_id,
            Group.teacher_id == teacher_id,
            Group.is_deleted == False
        ).first()

    stats = AttendanceRepository.get_session_stats(db, teacher_id, sess.id, sess.group_id)

    return SessionResponse(
        id=sess.id,
        group_id=sess.group_id,
        group_name=group.name if group else "",
        grade_level=group.grade_level if group else "",
        grade_label=GRADE_LABELS.get(group.grade_level, "") if group else "",
        session_date=sess.session_date,
        start_time=sess.start_time,
        end_time=sess.end_time,
        location=sess.location,
        notes=sess.notes,
        status=sess.status,
        status_label=SESSION_STATUS_LABELS.get(sess.status, sess.status),
        stats=stats,
        created_at=sess.created_at,
    )


# ==========================================
# --- Session Endpoints ---
# ==========================================

@router.post("", response_model=SessionResponse, status_code=http_status.HTTP_201_CREATED, summary="Schedule a new class session")
def create_session(
    payload: SessionCreate,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Create a new class session for an active group belonging to the teacher.
    """
    try:
        session_obj = AttendanceRepository.create_session(db, teacher_id=auth.teacher_id, data=payload)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _format_session_response(db, auth.teacher_id, session_obj)


@router.get("", response_model=List[SessionResponse], summary="List and filter class sessions")
def list_sessions(
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    session_date: Optional[str] = Query(None, description="Filter by exact date YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Filter from start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Filter to end date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="scheduled, completed, cancelled"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_permission("can_view_attendance")),
    db: Session = Depends(get_db)
):
    """
    List class sessions belonging strictly to the teacher workspace.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date"
        )

    sessions, _ = AttendanceRepository.list_sessions(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id,
        session_date=session_date,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
        offset=offset
    )

    # Pre-fetch groups for performance
    group_ids = {s.group_id for s in sessions}
    groups = {g.id: g for g in db.query(Group).filter(Group.id.in_(group_ids)).all()} if group_ids else {}

    results = []
    for s in sessions:
        results.append(_format_session_response(db, auth.teacher_id, s, groups.get(s.group_id)))
    return results


# Notice: Put static /reports routes BEFORE parameterized /{session_id} route to avoid router conflicts
@router.get("/reports/student/{student_id}", response_model=StudentAttendanceHistoryResponse, summary="Get student attendance history")
def get_student_history(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_view_attendance")),
    db: Session = Depends(get_db)
):
    """
    Retrieve attendance history and attendance rate for a specific student.
    """
    history_data = AttendanceRepository.get_student_attendance_history(
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


@router.get("/reports/group/{group_id}", response_model=GroupAttendanceSummaryResponse, summary="Get group attendance summary")
def get_group_summary(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_view_attendance")),
    db: Session = Depends(get_db)
):
    """
    Retrieve aggregate attendance summary and recent sessions for a group.
    """
    summary_data = AttendanceRepository.get_group_attendance_summary(
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


@router.get("/{session_id}", response_model=SessionResponse, summary="Get session details")
def get_session(
    session_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_view_attendance")),
    db: Session = Depends(get_db)
):
    """
    Get single session details scoped strictly to teacher.
    """
    session_obj = AttendanceRepository.get_session_by_id(db, auth.teacher_id, session_id)
    if not session_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الحصة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return _format_session_response(db, auth.teacher_id, session_obj)


@router.put("/{session_id}", response_model=SessionResponse, summary="Update session details")
def update_session(
    session_id: str,
    payload: SessionUpdate,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Update session details (date, times, location, status, notes).
    """
    try:
        session_obj = AttendanceRepository.update_session(db, auth.teacher_id, session_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not session_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الحصة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return _format_session_response(db, auth.teacher_id, session_obj)


@router.post("/{session_id}/cancel", response_model=SessionResponse, summary="Cancel session")
def cancel_session(
    session_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Mark a session as cancelled.
    """
    session_obj = AttendanceRepository.cancel_session(db, auth.teacher_id, session_id)
    if not session_obj:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الحصة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return _format_session_response(db, auth.teacher_id, session_obj)


# ==========================================
# --- Attendance Taking Endpoints ---
# ==========================================

@router.get("/{session_id}/attendance", response_model=SessionAttendanceSheetResponse, summary="Get session attendance sheet")
def get_session_attendance(
    session_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_view_attendance")),
    db: Session = Depends(get_db)
):
    """
    Get full attendance sheet: all enrolled students in the session's group,
    their recorded statuses, and summary counters.
    """
    sheet = AttendanceRepository.get_session_attendance_sheet(db, auth.teacher_id, session_id)
    if not sheet:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="الحصة غير موجودة أو لا تملك صلاحية الوصول إليها"
        )
    return sheet


@router.post("/{session_id}/attendance", summary="Record single student attendance")
def mark_attendance(
    session_id: str,
    payload: AttendanceMarkSingleRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Record or update attendance for an individual student.
    """
    try:
        rec = AttendanceRepository.mark_single_attendance(
            db=db,
            teacher_id=auth.teacher_id,
            session_id=session_id,
            student_id=payload.student_id,
            status=payload.status,
            notes=payload.notes,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "id": rec.id,
        "session_id": rec.session_id,
        "student_id": rec.student_id,
        "status": rec.status,
        "status_label": ATTENDANCE_STATUS_LABELS.get(rec.status, rec.status),
        "notes": rec.notes,
        "updated_at": rec.updated_at
    }


@router.post("/{session_id}/attendance/bulk", summary="Bulk record attendance")
def bulk_mark_attendance(
    session_id: str,
    payload: AttendanceBulkRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Bulk upsert attendance records atomically in a transaction.
    Aborts if any student is not enrolled.
    """
    try:
        count = AttendanceRepository.bulk_mark_attendance(
            db=db,
            teacher_id=auth.teacher_id,
            session_id=session_id,
            records=payload.records,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "count": count,
        "message": f"تم تسجيل الحضور لـ {count} طالب بنجاح"
    }


@router.post("/{session_id}/scan", response_model=AttendanceScanResponse, summary="Scan student barcode")
def scan_attendance(
    session_id: str,
    payload: AttendanceScanRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_mark_attendance")),
    db: Session = Depends(get_db)
):
    """
    Process a hardware USB barcode scanner event.
    Accepts opaque student ID, verifies group membership, and records attendance.
    Handles duplicate scans gracefully.
    """
    try:
        result = AttendanceRepository.scan_barcode(
            db=db,
            teacher_id=auth.teacher_id,
            session_id=session_id,
            barcode=payload.barcode,
            notes=payload.notes,
            user_id=auth.user_id,
            user_type="teacher" if auth.is_teacher else "assistant"
        )
    except LookupError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))

    return result
