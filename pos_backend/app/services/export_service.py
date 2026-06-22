"""Export engine — PDF (reportlab) and Excel (openpyxl) generators.

Shared by admin reports export endpoints.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side


# ── PDF ────────────────────────────────────────────────────────────


def generate_pdf(title: str, columns: list[str], rows: list[list], company: str = "NEOGAS") -> bytes:
    """Generate a landscape PDF table report.

    Args:
        title: Report title
        columns: Column headers
        rows: List of row lists (all values as strings)
        company: Company name for header
    """
    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=(page_w, page_h),
                           leftMargin=15*mm, rightMargin=15*mm,
                           topMargin=15*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=14, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle2', parent=styles['Normal'], fontSize=8, textColor=colors.grey)

    elements = []
    elements.append(Paragraph(f"<b>{company}</b> — {title}", title_style))
    elements.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 5*mm))

    # Build table data
    table_data = [columns] + rows

    # Calculate column widths proportionally
    avail_w = page_w - 30*mm
    col_w = avail_w / len(columns)
    col_widths = [col_w] * len(columns)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()


# ── Excel ──────────────────────────────────────────────────────────


def generate_excel(title: str, columns: list[str], rows: list[list], company: str = "NEOGAS") -> bytes:
    """Generate an Excel workbook with one sheet.

    Args:
        title: Sheet title
        columns: Column headers
        rows: List of row lists
        company: Company name
    """
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel sheet name max 31 chars

    # Header style
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="1a365d", end_color="1a365d", fill_type="solid")
    header_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    # Company + date row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    ws.cell(row=1, column=1, value=f"{company} — {title}").font = Font(bold=True, size=12)
    ws.cell(row=2, column=1, value=f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}").font = Font(size=9, color="666666")

    # Headers at row 3
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=3, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Data rows starting at row 4
    for row_idx, row in enumerate(rows, 4):
        for col_idx, value in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            cell.font = Font(size=9)

    # Auto-fit column widths (approximate)
    for col_idx in range(1, len(columns) + 1):
        max_len = len(columns[col_idx - 1])
        for row in rows:
            cell_val = str(row[col_idx - 1]) if col_idx <= len(row) else ""
            max_len = max(max_len, len(cell_val))
        ws.column_dimensions[ws.cell(row=3, column=col_idx).column_letter].width = min(max_len + 4, 40)

    # Freeze header
    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
