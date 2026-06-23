"""
Report generation endpoints.
Exports violation data as CSV or PDF.
"""
from __future__ import annotations
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.violation import Violation

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/csv",
    summary="Download violations as CSV",
)
async def export_csv(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Violation).order_by(Violation.detected_at.desc())
    if date_from:
        stmt = stmt.where(Violation.detected_at >= date_from)
    if date_to:
        stmt = stmt.where(Violation.detected_at <= f"{date_to} 23:59:59")
    if violation_type:
        stmt = stmt.where(Violation.violation_type == violation_type)

    rows = (await db.execute(stmt)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Detected At", "Violation Type", "Confidence",
        "Vehicle Type", "Plate Number", "Plate Confidence",
        "Location", "Status", "Evidence Path",
    ])
    for r in rows:
        writer.writerow([
            str(r.id), r.detected_at, r.violation_type,
            f"{r.confidence:.2f}", r.vehicle_type, r.plate_number,
            f"{r.plate_confidence:.2f}" if r.plate_confidence else "",
            r.location, r.status.value if r.status else "",
            r.evidence_image_path or "",
        ])

    output.seek(0)
    filename = f"violations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/pdf",
    summary="Download violations summary as PDF",
)
async def export_pdf(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=501,
            detail="PDF export requires reportlab. Install with: pip install reportlab",
        )

    stmt = select(Violation).order_by(Violation.detected_at.desc()).limit(500)
    if date_from:
        stmt = stmt.where(Violation.detected_at >= date_from)
    if date_to:
        stmt = stmt.where(Violation.detected_at <= f"{date_to} 23:59:59")

    rows = (await db.execute(stmt)).scalars().all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("Traffic Violation Detection Report", styles["Title"]))
    elems.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elems.append(Spacer(1, 12))

    data = [["Date", "Type", "Confidence", "Plate", "Location", "Status"]]
    for r in rows:
        data.append([
            str(r.detected_at)[:16] if r.detected_at else "-",
            (r.violation_type or "").replace("_", " ").title(),
            f"{r.confidence:.0%}",
            r.plate_number or "-",
            (r.location or "-")[:25],
            (r.status.value if r.status else "-").title(),
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elems.append(table)

    doc.build(elems)
    buf.seek(0)
    filename = f"violations_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
