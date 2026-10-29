import io
import os
import re
from typing import List, Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib import pagesizes
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderSVG
import arabic_reshaper
from bidi.algorithm import get_display

from app.config import logger

# Primary Brand Colors (Deep Nile Teal & Dark Slate)
TEAL_PRIMARY = colors.HexColor("#0f766e")
TEAL_LIGHT = colors.HexColor("#f0fdfa")
SLATE_BORDER = colors.HexColor("#cbd5e1")
SLATE_TEXT = colors.HexColor("#1e293b")
SLATE_MUTED = colors.HexColor("#64748b")
WHITE = colors.HexColor("#ffffff")

# Font configuration
FONT_REGISTERED = False
ARABIC_FONT_NAME = "SystemArabicFont"
ARABIC_FONT_BOLD_NAME = "SystemArabicFontBold"


def _ensure_arabic_fonts():
    """
    Ensures high-quality TrueType fonts supporting Arabic are registered with ReportLab.
    Falls back gracefully across standard Windows/system font directories.
    """
    global FONT_REGISTERED
    if FONT_REGISTERED:
        return

    regular_candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf"
    ]
    bold_candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
    ]

    reg_path = next((p for p in regular_candidates if os.path.isfile(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.isfile(p)), reg_path)

    if reg_path:
        try:
            pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, reg_path))
            pdfmetrics.registerFont(TTFont(ARABIC_FONT_BOLD_NAME, bold_path or reg_path))
            FONT_REGISTERED = True
            logger.info(f"Registered Arabic TrueType fonts from: {reg_path}")
        except Exception as e:
            logger.warning(f"Failed to register Arabic TTFont: {e}")
    else:
        logger.warning("No TrueType Arabic fonts found on system, falling back to standard Helvetica.")


def shape_arabic(text: Optional[str]) -> str:
    """
    Applies Arabic script joining (reshaping) and bidirectional ordering (BiDi).
    Handles empty/None values and mixed Arabic/English text safely.
    """
    if not text:
        return ""
    try:
        # Check if contains Arabic characters
        if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text):
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        return text
    except Exception as e:
        logger.debug(f"Arabic reshaping skipped: {e}")
        return text


class BarcodeService:
    """
    Core service generating:
    1. Crisp on-screen SVG Code 128 barcodes.
    2. Single-card student identity PDFs (mobile/print).
    3. Multi-card printable A4 sheets for group distribution.
    """

    @staticmethod
    def generate_barcode_svg(value: str) -> str:
        """
        Generates an inline vector SVG string for the Code 128 barcode.
        """
        d = createBarcodeDrawing(
            "Code128",
            value=value,
            barHeight=45,
            barWidth=0.85,
            humanReadable=True
        )
        return renderSVG.drawToString(d)

    @staticmethod
    def generate_student_card_pdf(
        student: Dict[str, Any],
        teacher_name: str = "TeacherSystem",
        group_name: Optional[str] = None
    ) -> bytes:
        """
        Generates a high-resolution, wallet-sized single student barcode ID card PDF.
        Dimensions: 350 pt x 230 pt (ideal for phone display and wallet card printing).
        """
        _ensure_arabic_fonts()
        font_regular = ARABIC_FONT_NAME if FONT_REGISTERED else "Helvetica"
        font_bold = ARABIC_FONT_BOLD_NAME if FONT_REGISTERED else "Helvetica-Bold"

        width, height = 350.0, 230.0
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(width, height))

        # 1. Background Card with Rounded Corners
        c.setFillColor(WHITE)
        c.setStrokeColor(SLATE_BORDER)
        c.setLineWidth(1.5)
        c.roundRect(8, 8, width - 16, height - 16, radius=10, fill=1, stroke=1)

        # 2. Header Banner
        c.setFillColor(TEAL_PRIMARY)
        c.roundRect(8, height - 52, width - 16, 44, radius=8, fill=1, stroke=0)
        # Flatten bottom corners of header
        c.rect(8, height - 52, width - 16, 12, fill=1, stroke=0)

        # Header Titles
        c.setFillColor(WHITE)
        c.setFont(font_bold, 12)
        system_title = shape_arabic("TeacherSystem | بطاقة الطالب الذكية")
        c.drawRightString(width - 20, height - 28, system_title)

        t_sub = shape_arabic(teacher_name or "المعلم")
        c.setFont(font_regular, 9)
        c.drawString(20, height - 28, t_sub)

        # 3. Student Information Section
        c.setFillColor(SLATE_TEXT)
        c.setFont(font_bold, 15)
        st_name = shape_arabic(student.get("full_name", ""))
        c.drawRightString(width - 20, height - 76, st_name)

        c.setFillColor(SLATE_MUTED)
        c.setFont(font_regular, 9.5)
        grade_label = student.get("grade_label") or student.get("grade_level", "")
        grp_display = group_name or student.get("primary_group_name") or "عام"
        info_line = shape_arabic(f"الصف: {grade_label}  |  المجموعة: {grp_display}")
        c.drawRightString(width - 20, height - 94, info_line)

        # 4. Code 128 Barcode (Opaque Student ID)
        barcode_val = student.get("student_id") or student.get("id") or ""
        d = createBarcodeDrawing(
            "Code128",
            value=barcode_val,
            barHeight=42,
            barWidth=0.8,
            humanReadable=True
        )

        # Center barcode horizontally
        scale_factor = min(1.0, (width - 40) / max(1, d.width))
        d.scale(scale_factor, scale_factor)
        scaled_w = d.width * scale_factor
        bc_x = (width - scaled_w) / 2.0
        d.drawOn(c, bc_x, 38)

        # 5. Footer Instructions
        c.setFillColor(SLATE_MUTED)
        c.setFont(font_regular, 7.5)
        footer_msg = shape_arabic("أبرز هذا الباركود عند حضور الحصص ورصد الامتحانات")
        c.drawCentredString(width / 2.0, 16, footer_msg)

        c.showPage()
        c.save()
        buffer.flush()
        pdf_data = buffer.getvalue()
        buffer.close()

        if not pdf_data.startswith(b"%PDF-"):
            logger.error("Generated student card PDF has invalid header signature.")
            raise ValueError("Invalid PDF generated: missing %PDF- header signature.")
        if b"%%EOF" not in pdf_data[-200:]:
            logger.error("Generated student card PDF has missing EOF trailer.")
            raise ValueError("Invalid PDF generated: missing %%EOF trailer marker.")

        return pdf_data

    @staticmethod
    def generate_group_cards_pdf(
        group: Dict[str, Any],
        students: List[Dict[str, Any]],
        teacher_name: str = "TeacherSystem"
    ) -> bytes:
        """
        Generates an A4 printable PDF containing a grid of student barcode cards
        (8 cards per page: 2 columns x 4 rows) with cutting guidelines.
        Handles empty groups, single-student, and multi-page large groups cleanly.
        """
        _ensure_arabic_fonts()
        font_regular = ARABIC_FONT_NAME if FONT_REGISTERED else "Helvetica"
        font_bold = ARABIC_FONT_BOLD_NAME if FONT_REGISTERED else "Helvetica-Bold"

        a4_width, a4_height = pagesizes.A4  # 595.27 x 841.89
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=pagesizes.A4)

        group_name = group.get("name", "مجموعة")
        grade_label = group.get("grade_label") or group.get("grade_level", "")

        # Handle Empty Group case
        if not students:
            c.setFont(font_bold, 18)
            c.setFillColor(TEAL_PRIMARY)
            c.drawCentredString(a4_width / 2.0, a4_height - 120, shape_arabic(f"بطاقات طلاب: {group_name}"))

            c.setFont(font_regular, 12)
            c.setFillColor(SLATE_MUTED)
            msg = shape_arabic("لا يوجد طلاب مسجلون حالياً في هذه المجموعة.")
            c.drawCentredString(a4_width / 2.0, a4_height - 160, msg)

            c.showPage()
            c.save()
            buffer.flush()
            pdf_data = buffer.getvalue()
            buffer.close()

            if not pdf_data.startswith(b"%PDF-"):
                logger.error("Generated empty group PDF has invalid header signature.")
                raise ValueError("Invalid PDF generated: missing %PDF- header signature.")
            return pdf_data

        # Grid specifications: 2 columns x 4 rows = 8 cards per A4 page
        cols = 2
        rows = 4
        cards_per_page = cols * rows

        margin_x = 24.0
        margin_y = 24.0
        gap_x = 16.0
        gap_y = 12.0

        card_w = (a4_width - (2 * margin_x) - ((cols - 1) * gap_x)) / cols  # ~263 pt
        card_h = (a4_height - (2 * margin_y) - ((rows - 1) * gap_y)) / rows  # ~189 pt

        for idx, st in enumerate(students):
            page_pos = idx % cards_per_page
            col = page_pos % cols
            row = rows - 1 - (page_pos // cols)  # Top to bottom

            x0 = margin_x + col * (card_w + gap_x)
            y0 = margin_y + row * (card_h + gap_y)

            # Draw single card cell inside grid
            # Card Boundary with dashed cutting lines
            c.saveState()
            c.setFillColor(WHITE)
            c.setStrokeColor(SLATE_BORDER)
            c.setLineWidth(0.8)
            c.setDash(3, 3)
            c.roundRect(x0, y0, card_w, card_h, radius=6, fill=1, stroke=1)
            c.restoreState()

            # Mini Header Banner
            c.setFillColor(TEAL_PRIMARY)
            banner_h = 28.0
            c.rect(x0, y0 + card_h - banner_h, card_w, banner_h, fill=1, stroke=0)

            c.setFillColor(WHITE)
            c.setFont(font_bold, 9)
            header_text = shape_arabic(f"TeacherSystem | {group_name}")
            c.drawRightString(x0 + card_w - 10, y0 + card_h - 18, header_text)

            c.setFont(font_regular, 7.5)
            c.drawString(x0 + 10, y0 + card_h - 18, shape_arabic(teacher_name or "المعلم"))

            # Student Name
            c.setFillColor(SLATE_TEXT)
            c.setFont(font_bold, 11.5)
            st_name = shape_arabic(st.get("full_name", ""))
            c.drawRightString(x0 + card_w - 10, y0 + card_h - 48, st_name)

            # Grade & Class Info
            c.setFillColor(SLATE_MUTED)
            c.setFont(font_regular, 8)
            st_grade = st.get("grade_label") or grade_label
            c.drawRightString(x0 + card_w - 10, y0 + card_h - 62, shape_arabic(f"الصف: {st_grade}"))

            # Barcode
            barcode_val = st.get("student_id") or st.get("id") or ""
            d = createBarcodeDrawing(
                "Code128",
                value=barcode_val,
                barHeight=36,
                barWidth=0.75,
                humanReadable=True
            )

            # Scale to fit comfortably inside card width (~230 pt max)
            max_bc_w = card_w - 24.0
            scale = min(1.0, max_bc_w / max(1, d.width))
            d.scale(scale, scale)
            scaled_bc_w = d.width * scale
            bc_x = x0 + (card_w - scaled_bc_w) / 2.0
            d.drawOn(c, bc_x, y0 + 16)

            # Check if page is full or last student
            if (idx + 1) % cards_per_page == 0 or (idx + 1) == len(students):
                c.showPage()

        c.save()
        buffer.flush()
        pdf_data = buffer.getvalue()
        buffer.close()

        if not pdf_data.startswith(b"%PDF-"):
            logger.error("Generated group cards PDF has invalid header signature.")
            raise ValueError("Invalid PDF generated: missing %PDF- header signature.")
        if b"%%EOF" not in pdf_data[-200:]:
            logger.error("Generated group cards PDF has missing EOF trailer.")
            raise ValueError("Invalid PDF generated: missing %%EOF trailer marker.")

        return pdf_data
