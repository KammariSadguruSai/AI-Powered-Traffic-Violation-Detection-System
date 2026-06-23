"""
Analytics endpoints powering the dashboard.
Returns summary stats, type distribution, trends, and heatmap data.
"""
from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.violation import Violation, ViolationStatus
from app.models.camera import Camera
from app.schemas import (
    SummaryStats, ViolationTypeStat, AnalyticsTrends,
    TrendPoint, HeatmapPoint,
)
from app.config import ViolationType

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/summary",
    response_model=SummaryStats,
    summary="Dashboard KPI summary cards",
)
async def get_summary(db: AsyncSession = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())

    total      = (await db.execute(select(func.count(Violation.id)))).scalar_one()
    today      = (await db.execute(
        select(func.count(Violation.id)).where(Violation.detected_at >= today_start)
    )).scalar_one()
    pending    = (await db.execute(
        select(func.count(Violation.id)).where(Violation.status == ViolationStatus.PENDING)
    )).scalar_one()
    resolved   = (await db.execute(
        select(func.count(Violation.id)).where(Violation.status == ViolationStatus.RESOLVED)
    )).scalar_one()
    plates     = (await db.execute(
        select(func.count(func.distinct(Violation.plate_number)))
        .where(Violation.plate_number.isnot(None))
    )).scalar_one()
    cameras    = (await db.execute(
        select(func.count(Camera.id)).where(Camera.is_active == True)
    )).scalar_one()

    return SummaryStats(
        total_violations=total,
        today_violations=today,
        pending_violations=pending,
        resolved_violations=resolved,
        unique_plates=plates,
        active_cameras=cameras,
    )


@router.get(
    "/by-type",
    response_model=list[ViolationTypeStat],
    summary="Violation count by type for pie chart",
)
async def get_by_type(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Violation.violation_type, func.count(Violation.id).label("cnt"))
        .group_by(Violation.violation_type)
        .order_by(func.count(Violation.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    total = sum(r.cnt for r in rows) or 1

    return [
        ViolationTypeStat(
            violation_type=r.violation_type,
            count=r.cnt,
            percentage=round(r.cnt / total * 100, 1),
        )
        for r in rows
    ]


@router.get(
    "/trends",
    response_model=AnalyticsTrends,
    summary="Violation trends over time",
)
async def get_trends(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    days:   int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    from app.database import _is_sqlite
    from sqlalchemy import text

    since = datetime.now() - timedelta(days=days)
    since_str = since.isoformat()

    if _is_sqlite:
        # SQLite: use strftime for date grouping
        fmt_map = {"daily": "%Y-%m-%d", "weekly": "%Y-%W", "monthly": "%Y-%m"}
        fmt = fmt_map[period]
        stmt = text(f"""
            SELECT strftime('{fmt}', detected_at) AS bucket,
                   COUNT(id) AS cnt
            FROM violations
            WHERE detected_at >= :since
            GROUP BY bucket
            ORDER BY bucket
        """)
        rows = (await db.execute(stmt, {"since": since_str})).all()
        return AnalyticsTrends(
            period=period,
            data=[TrendPoint(date=str(r.bucket), count=r.cnt) for r in rows],
        )
    else:
        # PostgreSQL: use date_trunc
        if period == "daily":
            date_trunc = func.date_trunc("day", Violation.detected_at)
        elif period == "weekly":
            date_trunc = func.date_trunc("week", Violation.detected_at)
        else:
            date_trunc = func.date_trunc("month", Violation.detected_at)

        stmt = (
            select(date_trunc.label("bucket"), func.count(Violation.id).label("cnt"))
            .where(Violation.detected_at >= since)
            .group_by("bucket")
            .order_by("bucket")
        )
        rows = (await db.execute(stmt)).all()
        return AnalyticsTrends(
            period=period,
            data=[TrendPoint(date=str(r.bucket)[:10], count=r.cnt) for r in rows],
        )


@router.get(
    "/heatmap",
    response_model=list[HeatmapPoint],
    summary="Geographic heatmap data (for map overlay)",
)
async def get_heatmap(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Violation.latitude,
            Violation.longitude,
            Violation.location,
            func.count(Violation.id).label("weight"),
        )
        .where(Violation.latitude.isnot(None))
        .where(Violation.longitude.isnot(None))
        .group_by(Violation.latitude, Violation.longitude, Violation.location)
    )
    rows = (await db.execute(stmt)).all()

    return [
        HeatmapPoint(
            latitude=r.latitude,
            longitude=r.longitude,
            weight=r.weight,
            location=r.location or "",
        )
        for r in rows
    ]


@router.get(
    "/by-camera",
    summary="Violation counts grouped by camera",
)
async def by_camera(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Camera.camera_id,
            Camera.name,
            Camera.location,
            func.count(Violation.id).label("count"),
        )
        .outerjoin(Violation, Violation.camera_id == Camera.id)
        .group_by(Camera.id, Camera.camera_id, Camera.name, Camera.location)
        .order_by(func.count(Violation.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"camera_id": r.camera_id, "name": r.name, "location": r.location, "count": r.count}
        for r in rows
    ]
