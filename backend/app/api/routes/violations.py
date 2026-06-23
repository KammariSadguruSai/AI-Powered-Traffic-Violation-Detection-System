"""
CRUD routes for violation records.
Supports filtering, pagination, plate search, and status updates.
"""
from __future__ import annotations
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.violation import Violation, ViolationStatus
from app.schemas import (
    ViolationOut, ViolationUpdate, PaginatedViolations,
)

router = APIRouter(prefix="/violations", tags=["Violations"])


@router.get(
    "",
    response_model=PaginatedViolations,
    summary="List violations with filters",
)
async def list_violations(
    page:            int            = Query(1, ge=1),
    size:            int            = Query(20, ge=1, le=100),
    violation_type:  Optional[str]  = Query(None),
    status:          Optional[str]  = Query(None),
    plate:           Optional[str]  = Query(None, description="Partial plate search"),
    camera_id:       Optional[str]  = Query(None),
    date_from:       Optional[str]  = Query(None, description="ISO date YYYY-MM-DD"),
    date_to:         Optional[str]  = Query(None, description="ISO date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Violation).order_by(Violation.detected_at.desc())

    if violation_type:
        stmt = stmt.where(Violation.violation_type == violation_type)
    if status:
        stmt = stmt.where(Violation.status == status)
    if plate:
        stmt = stmt.where(Violation.plate_number.ilike(f"%{plate}%"))
    if date_from:
        stmt = stmt.where(Violation.detected_at >= date_from)
    if date_to:
        stmt = stmt.where(Violation.detected_at <= f"{date_to} 23:59:59")

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginate
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedViolations(
        items=[ViolationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )


@router.get(
    "/{violation_id}",
    response_model=ViolationOut,
    summary="Get a single violation by ID",
)
async def get_violation(
    violation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Violation, violation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found.")
    return ViolationOut.model_validate(row)


@router.put(
    "/{violation_id}",
    response_model=ViolationOut,
    summary="Update violation status or add reviewer notes",
)
async def update_violation(
    violation_id: UUID,
    body: ViolationUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Violation, violation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found.")

    if body.status is not None:
        row.status = body.status
    if body.reviewer_notes is not None:
        row.reviewer_notes = body.reviewer_notes
    if body.is_false_positive is not None:
        row.is_false_positive = body.is_false_positive

    await db.flush()
    return ViolationOut.model_validate(row)


@router.delete(
    "/{violation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a violation record",
)
async def delete_violation(
    violation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Violation, violation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found.")
    await db.delete(row)
    await db.flush()


@router.get(
    "/search/plate",
    response_model=PaginatedViolations,
    summary="Search violations by license plate number",
)
async def search_by_plate(
    plate: str      = Query(..., min_length=2),
    page:  int      = Query(1, ge=1),
    size:  int      = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Violation)
        .where(Violation.plate_number.ilike(f"%{plate.upper()}%"))
        .order_by(Violation.detected_at.desc())
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * size
    rows = (await db.execute(stmt.offset(offset).limit(size))).scalars().all()

    return PaginatedViolations(
        items=[ViolationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 1,
    )
