from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

STATUS_LABELS = {
    "not_sent": "بانتظار التسليم",
    "generated": "تم التصدير (PDF)",
    "share_opened": "تم فتح نافذة المشاركة",
    "confirmed_sent": "تم تأكيد التسليم"
}


class StudentGroupInfo(BaseModel):
    id: str
    name: str
    grade_level: str


class StudentCardResponse(BaseModel):
    student_id: str = Field(..., description="Unique student ID (scannable barcode value)")
    full_name: str = Field(..., description="Student full Arabic name")
    grade_level: str = Field(..., description="Grade code (e.g. 1_sec, 2_sec, 3_sec)")
    grade_label: str = Field(..., description="Grade name in Arabic")
    barcode_value: str = Field(..., description="Opaque barcode payload matching student.id")
    barcode_svg: str = Field(..., description="Inline SVG string for high-DPI display")
    primary_group_id: Optional[str] = None
    primary_group_name: Optional[str] = None
    enrolled_groups: List[StudentGroupInfo] = Field(default_factory=list)
    distribution_status: str = Field("not_sent", description="Current distribution status")
    status_label: str = Field("بانتظار التسليم", description="Arabic localized status label")
    card_generated_at: Optional[str] = None
    share_opened_at: Optional[str] = None
    confirmed_sent_at: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    is_new_since_last_export: bool = Field(False, description="Whether student joined after latest group export")

    model_config = ConfigDict(from_attributes=True)


class StudentDistributionItemResponse(BaseModel):
    student_id: str
    full_name: str
    phone: str
    grade_level: str
    grade_label: str
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    joined_at: Optional[str] = None
    barcode_value: str
    distribution_status: str
    status_label: str
    card_generated_at: Optional[str] = None
    share_opened_at: Optional[str] = None
    confirmed_sent_at: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    is_new_since_last_export: bool = False

    model_config = ConfigDict(from_attributes=True)


class GroupDistributionOverviewResponse(BaseModel):
    group_id: str
    group_name: str
    grade_level: str
    grade_label: str
    total_students: int
    confirmed_sent_count: int
    pending_count: int
    new_since_export_count: int
    last_exported_at: Optional[str] = None
    last_exported_by_name: Optional[str] = None
    students: List[StudentDistributionItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class StudentCardDistributionStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: 'share_opened', 'confirmed_sent', or 'not_sent'")
    group_id: Optional[str] = Field(None, description="Optional group context")
    notes: Optional[str] = Field(None, description="Optional audit notes")


class MultiStudentExportRequest(BaseModel):
    student_ids: List[str] = Field(..., min_length=1, description="List of student IDs to export")
    group_id: Optional[str] = Field(None, description="Optional group ID for context and header branding")
