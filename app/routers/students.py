from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_permission, AuthenticatedUser
from app.repositories.academic_repo import AcademicRepository
from app.models.academic import GRADE_LABELS
from app.schemas.academic import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentGroupBrief
)

router = APIRouter(prefix="/api/students", tags=["Students Management"])


def _format_student_response(student, group_count: int = 0, groups: list = None) -> StudentResponse:
    return StudentResponse(
        id=student.id,
        full_name=student.full_name,
        grade_level=student.grade_level,
        grade_label=GRADE_LABELS.get(student.grade_level, student.grade_level),
        phone=student.phone,
        parent_name=student.parent_name,
        parent_phone=student.parent_phone,
        address=student.address,
        notes=student.notes,
        is_active=student.is_active,
        group_count=group_count,
        groups=[StudentGroupBrief(**g) for g in (groups or [])],
        created_at=student.created_at
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED, summary="Create a new student")
def create_student(
    payload: StudentCreate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Register a new student within the authenticated teacher workspace.
    Phone numbers are not unique to accommodate siblings.
    """
    student = AcademicRepository.create_student(db, teacher_id=auth.teacher_id, data=payload)
    return _format_student_response(student, group_count=0, groups=[])


@router.get("", response_model=List[StudentResponse], summary="List and search students")
def list_students(
    q: Optional[str] = Query(None, description="Search query across name, phone, parent phone"),
    grade_level: Optional[str] = Query(None, description="Filter by grade: 1_sec, 2_sec, 3_sec"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    group_id: Optional[str] = Query(None, description="Filter by enrolled group ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    List students belonging strictly to the authenticated teacher with search and filters.
    """
    students, _ = AcademicRepository.list_students(
        db=db,
        teacher_id=auth.teacher_id,
        q=q,
        grade_level=grade_level,
        is_active=is_active,
        group_id=group_id,
        limit=limit,
        offset=offset
    )

    output = []
    for s in students:
        cnt = AcademicRepository.get_student_group_count(db, auth.teacher_id, s.id)
        output.append(_format_student_response(s, group_count=cnt))
    return output


@router.get("/{student_id}", response_model=StudentResponse, summary="Get student details")
def get_student(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Retrieve single student details with current active group memberships.
    Enforces strict tenant isolation.
    """
    student = AcademicRepository.get_student_by_id(db, teacher_id=auth.teacher_id, student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or access denied."
        )

    groups = AcademicRepository.get_student_groups(db, teacher_id=auth.teacher_id, student_id=student_id)
    return _format_student_response(student, group_count=len(groups), groups=groups)


@router.put("/{student_id}", response_model=StudentResponse, summary="Update student details")
def update_student(
    student_id: str,
    payload: StudentUpdate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Update student information. Enforces teacher scope.
    """
    student = AcademicRepository.update_student(
        db=db,
        teacher_id=auth.teacher_id,
        student_id=student_id,
        data=payload
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or access denied."
        )

    groups = AcademicRepository.get_student_groups(db, teacher_id=auth.teacher_id, student_id=student_id)
    return _format_student_response(student, group_count=len(groups), groups=groups)


@router.delete("/{student_id}", status_code=status.HTTP_200_OK, summary="Soft-delete student")
def delete_student(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Soft-delete student and automatically deactivate all group enrollments.
    """
    success = AcademicRepository.soft_delete_student(db, teacher_id=auth.teacher_id, student_id=student_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or access denied."
        )
    return {"message": "Student soft-deleted successfully.", "student_id": student_id}


@router.get("/{student_id}/groups", response_model=List[StudentGroupBrief], summary="Get student enrolled groups")
def get_student_groups(
    student_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Retrieve all groups the student is actively enrolled in.
    """
    student = AcademicRepository.get_student_by_id(db, teacher_id=auth.teacher_id, student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or access denied."
        )

    groups = AcademicRepository.get_student_groups(db, teacher_id=auth.teacher_id, student_id=student_id)
    return [StudentGroupBrief(**g) for g in groups]
