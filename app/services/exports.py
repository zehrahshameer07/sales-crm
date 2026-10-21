"""CSV and PDF report files."""
import csv
import io
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import labels, schemas
from ..models import Activity
from ..timeutil import local_zone

CSV_COLUMNS = [
    "Start date", "Salesperson", "Customer", "Activity type", "Product", "Status", "Contact", "Location",
    "Follow-up date", "Follow-up notes", "End date", "Days to complete", "Notes", "Logged at", "Last updated",
]


def csv_safe(value) -> str:
    """Stop spreadsheet formula injection: cells that start with = + - @ are prefixed with an apostrophe."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _local(dt: datetime) -> str:
    return dt.astimezone(local_zone()).strftime("%Y-%m-%d %H:%M")


def activities_csv(activities: list[Activity]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for a in activities:
        writer.writerow([
            csv_safe(x) for x in (
                a.start_date.isoformat(),
                a.owner.full_name,
                a.customer_name,
                labels.TYPE[a.activity_type.value],
                labels.PRODUCT[a.product_interested.value] if a.product_interested else "",
                labels.STATUS[a.status.value],
                a.contact,
                a.location,
                a.follow_up_date.isoformat() if a.follow_up_date else "",
                a.follow_up_notes,
                a.end_date.isoformat() if a.end_date else "",
                a.days_to_complete if a.days_to_complete is not None else "",
                a.notes,
                _local(a.created_at),
                _local(a.updated_at),
            )
        ])
    return buffer.getvalue().encode("utf-8-sig")   # BOM so Excel opens it with the right encoding


# ---------------------------------------------------------------------- PDF
BRAND = colors.HexColor("#E8590C")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")
HEAD_BG = colors.HexColor("#FFF4EC")


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "", style)


def activities_pdf(
    activities: list[Activity], report: schemas.Report, generated_for: str, filters_text: str, truncated: bool
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm, title="FreeBees Sales CRM report", author="FreeBees Sales CRM",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, textColor=INK, alignment=0, spaceAfter=2)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=MUTED, leading=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, textColor=INK, spaceBefore=10, spaceAfter=4)
    cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=7.5, leading=9.5, textColor=INK)
    head = ParagraphStyle("h", parent=cell, fontName="Helvetica-Bold", textColor=INK)

    ov = report.overview
    story = [
        _p("FreeBees Sales CRM \u2014 Activity report", title),
        _p(f"{report.scope_label} \u00b7 Generated {_local(report.generated_at)} for {generated_for}", sub),
        _p(f"Filters: {filters_text}", sub),
        Spacer(1, 8),
    ]

    kpis = [
        ["Activities", "Pending", "In progress", "Completed", "Completion rate", "Avg. days to complete"],
        [
            str(ov.total), str(ov.pending), str(ov.in_progress), str(ov.completed), f"{ov.completion_rate}%",
            "-" if ov.durations.avg_days_to_complete is None else str(ov.durations.avg_days_to_complete),
        ],
    ]
    kpi_table = Table(kpis, colWidths=[44 * mm] * 6)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"), ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 15),
        ("TEXTCOLOR", (0, 1), (-1, 1), INK), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(kpi_table)

    if report.by_employee:
        story.append(_p("By employee", h2))
        rows = [[_p(h, head) for h in
                 ("Employee", "Role", "Manager", "Total", "Pending", "In progress", "Completed", "Completion", "Avg. days", "Overdue follow-ups")]]
        for r in report.by_employee:
            rows.append([
                _p(r.full_name, cell), _p(labels.ROLE[r.role.value], cell), _p(r.manager_name or "-", cell),
                str(r.total), str(r.pending), str(r.in_progress), str(r.completed), f"{r.completion_rate}%",
                "-" if r.avg_days_to_complete is None else str(r.avg_days_to_complete), str(r.follow_ups_overdue),
            ])
        t = Table(rows, colWidths=[42 * mm, 24 * mm, 36 * mm, 15 * mm, 17 * mm, 20 * mm, 20 * mm, 22 * mm, 18 * mm, 28 * mm],
                  repeatRows=1)
        t.setStyle(_grid_style())
        story.append(t)

    story.append(_p(f"Activities ({len(activities)}{'+' if truncated else ''})", h2))
    header = ["Start", "Salesperson", "Customer", "Type", "Status", "Follow-up", "End", "Days", "Location"]
    data = [[_p(h, head) for h in header]]
    for a in activities:
        data.append([
            a.start_date.strftime("%d %b %Y"), _p(a.owner.full_name, cell), _p(a.customer_name, cell),
            labels.TYPE[a.activity_type.value], labels.STATUS[a.status.value],
            a.follow_up_date.strftime("%d %b %Y") if a.follow_up_date else "-",
            a.end_date.strftime("%d %b %Y") if a.end_date else "-",
            "-" if a.days_to_complete is None else str(a.days_to_complete),
            _p(a.location or "-", cell),
        ])
    if len(data) == 1:
        data.append([_p("No activities match these filters.", cell)] + [""] * (len(header) - 1))
    table = Table(data, colWidths=[22 * mm, 36 * mm, 50 * mm, 20 * mm, 22 * mm, 24 * mm, 22 * mm, 12 * mm, 40 * mm],
                  repeatRows=1)
    table.setStyle(_grid_style(small=True))
    story.append(table)
    if truncated:
        story.append(_p("Only the first rows are shown. Narrow the filters or use the CSV export for everything.", sub))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(14 * mm, 8 * mm, "FreeBees Sales CRM")
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _grid_style(small: bool = False) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5 if small else 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ])
