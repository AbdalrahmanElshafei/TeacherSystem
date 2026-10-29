from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_permission, AuthenticatedUser
from app.repositories.academic_repo import AcademicRepository
from app.models.academic import GRADE_LABELS
from app.schemas.academic import (
    GroupCreate,
    GroupUpdate,
    GroupResponse,
    EnrollStudentRequest,
    GroupEnrolledStudentResponse
)

router = APIRouter(prefix="/api/groups", tags=["Groups Management"])


def _format_group_response(group, student_count: int = 0) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        grade_level=group.grade_level,
        grade_label=GRADE_LABELS.get(group.grade_level, group.grade_level),
        subject=group.subject,
        schedule_details=group.schedule_details,
        is_active=group.is_active,
        student_count=student_count,
        created_at=group.created_at
    )


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED, summary="Create a new group")
def create_group(
    payload: GroupCreate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Create a new teaching group / class owned by the authenticated teacher.
    """
    group = AcademicRepository.create_group(db, teacher_id=auth.teacher_id, data=payload)
    return _format_group_response(group, student_count=0)


@router.get("", response_model=List[GroupResponse], summary="List groups")
def list_groups(
    grade_level: Optional[str] = Query(None, description="Filter by grade: 1_sec, 2_sec, 3_sec"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    List all groups belonging to the authenticated teacher with student counts.
    """
    groups, _ = AcademicRepository.list_groups(
        db=db,
        teacher_id=auth.teacher_id,
        grade_level=grade_level,
        is_active=is_active,
        limit=limit,
        offset=offset
    )

    output = []
    for g in groups:
        cnt = AcademicRepository.get_group_student_count(db, auth.teacher_id, g.id)
        output.append(_format_group_response(g, student_count=cnt))
    return output


@router.get("/{group_id}", response_model=GroupResponse, summary="Get group details")
def get_group(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Get details of a single group. Enforces tenant scope.
    """
    group = AcademicRepository.get_group_by_id(db, teacher_id=auth.teacher_id, group_id=group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found or access denied."
        )

    cnt = AcademicRepository.get_group_student_count(db, auth.teacher_id, group.id)
    return _format_group_response(group, student_count=cnt)


@router.put("/{group_id}", response_model=GroupResponse, summary="Update group details")
def update_group(
    group_id: str,
    payload: GroupUpdate,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Update group information. Enforces teacher scope.
    """
    group = AcademicRepository.update_group(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id,
        data=payload
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found or access denied."
        )

    cnt = AcademicRepository.get_group_student_count(db, auth.teacher_id, group.id)
    return _format_group_response(group, student_count=cnt)


@router.delete("/{group_id}", status_code=status.HTTP_200_OK, summary="Soft-delete group")
def delete_group(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Soft-delete group and automatically deactivate all student memberships.
    """
    success = AcademicRepository.soft_delete_group(db, teacher_id=auth.teacher_id, group_id=group_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found or access denied."
        )
    return {"message": "Group soft-deleted successfully.", "group_id": group_id}


@router.get("/{group_id}/students", response_model=List[GroupEnrolledStudentResponse], summary="List enrolled students")
def get_group_students(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    List all students actively enrolled in this group.
    """
    group = AcademicRepository.get_group_by_id(db, teacher_id=auth.teacher_id, group_id=group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found or access denied."
        )

    students = AcademicRepository.get_group_enrolled_students(db, teacher_id=auth.teacher_id, group_id=group_id)
    return [GroupEnrolledStudentResponse(**s) for s in students]


@router.post("/{group_id}/students", status_code=status.HTTP_201_CREATED, summary="Enroll student into group")
def enroll_student(
    group_id: str,
    payload: EnrollStudentRequest,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Enroll a student into a group:
    - Rejects cross-tenant enrollments (404).
    - Rejects grade level mismatches (400).
    - Rejects duplicate active enrollments (409 Conflict).
    """
    enrollment, error = AcademicRepository.enroll_student_in_group(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id,
        student_id=payload.student_id
    )

    if error == "group_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found or access denied.")
    if error == "student_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found or access denied.")
    if error == "grade_mismatch":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grade level mismatch: Student and Group must belong to the exact same academic grade."
        )
    if error == "duplicate_enrollment":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already actively enrolled in this group."
        )

    return {
        "message": "Student enrolled in group successfully.",
        "membership_id": enrollment.id,
        "group_id": group_id,
        "student_id": payload.student_id
    }


@router.delete("/{group_id}/students/{student_id}", status_code=status.HTTP_200_OK, summary="Remove student from group")
def unenroll_student(
    group_id: str,
    student_id: str,
    auth: AuthenticatedUser = Depends(require_permission("can_manage_students")),
    db: Session = Depends(get_db)
):
    """
    Unenroll / remove a student from a group.
    """
    group = AcademicRepository.get_group_by_id(db, teacher_id=auth.teacher_id, group_id=group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found or access denied.")

    success = AcademicRepository.unenroll_student_from_group(
        db=db,
        teacher_id=auth.teacher_id,
        group_id=group_id,
        student_id=student_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not enrolled in this group or was already removed."
        )

    return {
        "message": "Student removed from group successfully.",
        "group_id": group_id,
        "student_id": student_id
    }
