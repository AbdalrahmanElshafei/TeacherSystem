from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, AuthenticatedUser
from app.models.academic import Student, Group, GroupStudent
from app.models.user import Teacher
from app.schemas.distribution import (
    StudentCardResponse,
    StudentCardDistributionStatusUpdate,
    GroupDistributionOverviewResponse,
    MultiStudentExportRequest
)
from app.repositories.distribution_repo import DistributionRepository
from app.services.barcode_service import BarcodeService
from app.config import logger

router = APIRouter(prefix="/api/barcodes", tags=["Student Barcode Distribution"])


def require_distribution_access(auth: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Enforce teacher role or assistant with student/attendance management permissions."""
    if auth.is_teacher:
        return auth
    if getattr(auth.user, "can_manage_students", False) or \
       getattr(auth.user, "can_view_attendance", False) or \
       getattr(auth.user, "can_mark_attendance", False) or \
       getattr(auth.user, "can_take_attendance", False):
        return auth
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="صلاحية مرفوضة: تتطلب إدارة الطلاب أو الحضور لعرض وتوزيع بطاقات الباركود."
    )


@router.get("/students/{student_id}/card", response_model=StudentCardResponse, summary="Get student barcode card metadata and SVG")
def get_student_card(
    student_id: str,
    group_id: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Returns student details, group enrollments, scannable barcode string,
    inline SVG representation, and current distribution status.
    """
    try:
        data = DistributionRepository.get_student_card_data(
            db, teacher_id=auth.teacher_id, student_id=student_id, group_id=group_id
        )
        data["barcode_svg"] = BarcodeService.generate_barcode_svg(data["barcode_value"])
        return data
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating card metadata for {student_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="حدث خطأ أثناء إعداد بيانات البطاقة.")


@router.get("/students/{student_id}/card.pdf", summary="Download single student barcode card as PDF")
def download_student_card_pdf(
    student_id: str,
    group_id: Optional[str] = None,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Compiles and downloads a single high-resolution, wallet-sized student barcode ID card PDF.
    Advances status to 'generated' if currently 'not_sent'.
    """
    try:
        card_data = DistributionRepository.get_student_card_data(
            db, teacher_id=auth.teacher_id, student_id=student_id, group_id=group_id
        )
        teacher = db.query(Teacher).filter(Teacher.id == auth.teacher_id).first()
        t_name = teacher.full_name if teacher else "المعلم"

        pdf_bytes = BarcodeService.generate_student_card_pdf(
            student=card_data,
            teacher_name=t_name,
            group_name=card_data.get("primary_group_name")
        )

        # Mark as generated
        DistributionRepository.update_distribution_status(
            db, teacher_id=auth.teacher_id, student_id=student_id, new_status="generated", group_id=group_id
        )

        safe_filename = f"card_{student_id[:8]}.pdf"
        logger.info(f"Generated single student card PDF: student={student_id[:8]}, size={len(pdf_bytes)} bytes")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error compiling student card PDF for {student_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="تعذر إنشاء ملف PDF للبطاقة.")


@router.get("/distribution/groups/{group_id}", response_model=GroupDistributionOverviewResponse, summary="Get group distribution status overview")
def get_group_distribution_status(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Retrieves full distribution overview for a group, including newly enrolled
    students since the last export, confirmed vs pending delivery counts.
    """
    try:
        return DistributionRepository.get_group_distribution_overview(
            db, teacher_id=auth.teacher_id, group_id=group_id
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching group distribution overview {group_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="تعذر جلب حالة توزيع البطاقات.")


@router.get("/groups/{group_id}/export-pdf", summary="Export group barcode cards as printable A4 PDF (GET)")
@router.get("/groups/{group_id}/cards.pdf", summary="Export group barcode cards as printable A4 PDF (alias)")
@router.post("/groups/{group_id}/export-pdf", summary="Export group barcode cards as printable A4 PDF (POST)")
def export_group_cards_pdf(
    group_id: str,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Generates a printable A4 PDF (8 cards per page) for all active students in the group.
    Logs the export batch to track newly enrolled students in subsequent runs.
    Supports both GET and POST requests.
    """
    try:
        overview = DistributionRepository.get_group_distribution_overview(
            db, teacher_id=auth.teacher_id, group_id=group_id
        )
        group_meta = {
            "name": overview["group_name"],
            "grade_level": overview["grade_level"],
            "grade_label": overview["grade_label"]
        }
        teacher = db.query(Teacher).filter(Teacher.id == auth.teacher_id).first()
        t_name = teacher.full_name if teacher else "المعلم"

        pdf_bytes = BarcodeService.generate_group_cards_pdf(
            group=group_meta,
            students=overview["students"],
            teacher_name=t_name
        )

        # Log group export batch
        DistributionRepository.record_group_export(
            db=db,
            teacher_id=auth.teacher_id,
            group_id=group_id,
            user_id=auth.user_id,
            user_name=getattr(auth.user, "full_name", None) or auth.username,
            student_count=overview["total_students"],
            export_type="group_pdf"
        )

        safe_filename = f"group_{group_id[:8]}_barcode_cards.pdf"
        logger.info(f"Generated group cards PDF: group={group_id[:8]}, size={len(pdf_bytes)} bytes, students={overview['total_students']}")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting group cards PDF {group_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="تعذر تصدير بطاقات المجموعة.")


@router.post("/multi/export-pdf", summary="Export selected student barcode cards as printable A4 PDF")
def export_multi_student_cards_pdf(
    payload: MultiStudentExportRequest,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Generates a printable A4 PDF for an arbitrary list of student IDs strictly
    scoped to the teacher tenant.
    """
    try:
        students = db.query(Student).filter(
            Student.id.in_(payload.student_ids),
            Student.teacher_id == auth.teacher_id,
            Student.is_deleted == False
        ).order_by(Student.full_name.asc()).all()

        if not students:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="لم يتم العثور على أي طلاب مطابقين.")

        group_meta = {"name": "بطاقات مخصصة", "grade_label": "متعدد"}
        if payload.group_id:
            grp = db.query(Group).filter(Group.id == payload.group_id, Group.teacher_id == auth.teacher_id).first()
            if grp:
                group_meta["name"] = grp.name
                group_meta["grade_label"] = grp.grade_level

        st_dicts = [
            {
                "student_id": s.id,
                "full_name": s.full_name,
                "grade_level": s.grade_level,
                "grade_label": s.grade_level
            }
            for s in students
        ]
        teacher = db.query(Teacher).filter(Teacher.id == auth.teacher_id).first()
        t_name = teacher.full_name if teacher else "المعلم"

        pdf_bytes = BarcodeService.generate_group_cards_pdf(
            group=group_meta,
            students=st_dicts,
            teacher_name=t_name
        )

        # Mark all selected students as generated
        for s in students:
            DistributionRepository.update_distribution_status(
                db, teacher_id=auth.teacher_id, student_id=s.id, new_status="generated", group_id=payload.group_id
            )

        safe_filename = f"selected_barcode_cards_{len(students)}.pdf"
        logger.info(f"Generated multi-student cards PDF: count={len(students)}, size={len(pdf_bytes)} bytes")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting multi-student cards PDF: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="تعذر تصدير البطاقات المحددة.")


@router.post("/distribution/students/{student_id}/status", summary="Update student card distribution status")
def update_student_distribution_status(
    student_id: str,
    payload: StudentCardDistributionStatusUpdate,
    auth: AuthenticatedUser = Depends(require_distribution_access),
    db: Session = Depends(get_db)
):
    """
    Updates the distribution status of a student's card (e.g. 'share_opened', 'confirmed_sent', 'not_sent').
    """
    valid_statuses = ("not_sent", "generated", "share_opened", "confirmed_sent")
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="حالة التوزيع غير صالحة.")

    try:
        updated = DistributionRepository.update_distribution_status(
            db=db,
            teacher_id=auth.teacher_id,
            student_id=student_id,
            new_status=payload.status,
            user_id=auth.user_id,
            user_name=getattr(auth.user, "full_name", None) or auth.username,
            group_id=payload.group_id,
            notes=payload.notes
        )
        return {
            "success": True,
            "student_id": student_id,
            "status": updated.status,
            "confirmed_sent_at": updated.confirmed_sent_at.isoformat() if updated.confirmed_sent_at else None,
            "confirmed_by_name": updated.confirmed_by_name
        }
    except Exception as e:
        logger.error(f"Error updating distribution status for student {student_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="تعذر تحديث حالة التوزيع.")
