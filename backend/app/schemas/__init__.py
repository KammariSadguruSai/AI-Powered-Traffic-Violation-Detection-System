"""Pydantic schemas for request/response serialization."""
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class ViolationStatusEnum(str, Enum):
    PENDING   = "pending"
    REVIEWED  = "reviewed"
    RESOLVED  = "resolved"
    DISPUTED  = "disputed"
    DISMISSED = "dismissed"


# ── Bounding Box ──────────────────────────────────────────────────────────────

class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


# ── Detection Result (internal AI output) ─────────────────────────────────────

class DetectedObject(BaseModel):
    class_id:    int
    class_name:  str
    confidence:  float
    bbox:        BBox
    track_id:    Optional[int] = None


class PlateResult(BaseModel):
    plate_text:  str
    confidence:  float
    bbox:        Optional[BBox] = None


class ViolationResult(BaseModel):
    violation_type:  str
    confidence:      float
    bbox:            Optional[BBox] = None
    vehicle_type:    Optional[str] = None
    plate:           Optional[PlateResult] = None
    description:     Optional[str] = None


class DetectionResponse(BaseModel):
    """Full result returned from the AI pipeline for one image."""
    image_id:          str
    processing_time_ms: float
    detected_objects:  List[DetectedObject] = []
    violations:        List[ViolationResult] = []
    evidence_path:     Optional[str] = None
    evidence_thumbnail: Optional[str] = None   # base64
    width:             int
    height:            int


# ── Camera Schemas ────────────────────────────────────────────────────────────

class CameraBase(BaseModel):
    camera_id:   str
    name:        str
    location:    Optional[str] = None
    latitude:    Optional[float] = None
    longitude:   Optional[float] = None
    rtsp_url:    Optional[str] = None
    description: Optional[str] = None


class CameraCreate(CameraBase):
    pass


class CameraOut(CameraBase):
    model_config = ConfigDict(from_attributes=True)
    id:         UUID
    is_active:  bool
    created_at: datetime


# ── Vehicle Schemas ───────────────────────────────────────────────────────────

class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:               UUID
    plate_number:     Optional[str]
    vehicle_type:     Optional[str]
    total_violations: int
    first_seen:       Optional[datetime]
    last_seen:        Optional[datetime]


# ── Violation Schemas ─────────────────────────────────────────────────────────

class ViolationBase(BaseModel):
    violation_type:   str
    confidence:       float
    vehicle_type:     Optional[str] = None
    plate_number:     Optional[str] = None
    plate_confidence: Optional[float] = None
    location:         Optional[str] = None
    latitude:         Optional[float] = None
    longitude:        Optional[float] = None


class ViolationCreate(ViolationBase):
    bbox:                Optional[Dict[str, float]] = None
    original_image_path: Optional[str] = None
    evidence_image_path: Optional[str] = None
    evidence_thumbnail:  Optional[str] = None
    camera_id:           Optional[UUID] = None
    vehicle_id:          Optional[UUID] = None


class ViolationOut(ViolationBase):
    model_config = ConfigDict(from_attributes=True)
    id:                  UUID
    detected_at:         datetime
    status:              ViolationStatusEnum
    evidence_thumbnail:  Optional[str] = None
    evidence_image_path: Optional[str] = None
    bbox:                Optional[Dict[str, float]] = None
    camera_id:           Optional[UUID] = None
    vehicle_id:          Optional[UUID] = None


class ViolationUpdate(BaseModel):
    status:          Optional[ViolationStatusEnum] = None
    reviewer_notes:  Optional[str] = None
    is_false_positive: Optional[bool] = None


# ── Analytics Schemas ─────────────────────────────────────────────────────────

class SummaryStats(BaseModel):
    total_violations:   int
    today_violations:   int
    pending_violations: int
    resolved_violations: int
    unique_plates:      int
    active_cameras:     int


class ViolationTypeStat(BaseModel):
    violation_type: str
    count:          int
    percentage:     float


class TrendPoint(BaseModel):
    date:  str          # ISO date string
    count: int


class AnalyticsTrends(BaseModel):
    period: str         # "daily" | "weekly" | "monthly"
    data:   List[TrendPoint]


class HeatmapPoint(BaseModel):
    latitude:  float
    longitude: float
    weight:    int
    location:  str


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedViolations(BaseModel):
    items:   List[ViolationOut]
    total:   int
    page:    int
    size:    int
    pages:   int
