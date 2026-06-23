"""
Image upload and AI processing endpoint.
Orchestrates: enhance → detect → violations → OCR → evidence → DB save.
"""
from __future__ import annotations
import logging
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas import DetectionResponse, ViolationCreate, ViolationOut
from app.core.preprocessing.enhancer import enhancer
from app.core.detection.detector import detector
from app.core.detection.violation_rules import ViolationEngine
from app.core.ocr.plate_ocr import plate_ocr
from app.core.evidence.generator import evidence_generator
from app.models.violation import Violation, ViolationStatus

router = APIRouter(prefix="/upload", tags=["Upload & Detection"])
logger = logging.getLogger(__name__)

# Max upload size check
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Shared violation engine (stateful for tracking across frames per camera)
_engines: dict[str, ViolationEngine] = {}


def _get_engine(camera_id: str) -> ViolationEngine:
    if camera_id not in _engines:
        _engines[camera_id] = ViolationEngine()
    return _engines[camera_id]


@router.post(
    "/image",
    response_model=DetectionResponse,
    summary="Process a single traffic image",
    description=(
        "Upload a traffic surveillance image. The system will enhance it, "
        "detect vehicles and persons, identify violations, extract license "
        "plates, generate annotated evidence, and save the record."
    ),
)
async def process_image(
    file:      UploadFile = File(..., description="JPEG or PNG image"),
    camera_id: str        = Form(default="CAM-001"),
    location:  str        = Form(default="Unknown"),
    stop_line_y: Optional[int] = Form(default=None, description="Stop-line Y pixel (optional)"),
    db: AsyncSession = Depends(get_db),
):
    t_start = time.perf_counter()

    # ── Validate upload ───────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only image files (JPEG, PNG, WEBP) are accepted.",
        )

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )

    # ── Save original ─────────────────────────────────────────────────────────
    image_id = uuid.uuid4().hex
    orig_path = settings.UPLOAD_DIR / f"{image_id}.jpg"
    orig_path.write_bytes(raw)

    # ── Preprocess ────────────────────────────────────────────────────────────
    try:
        bgr = enhancer.load_from_bytes(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    preproc = enhancer.enhance(bgr, apply_clahe=True, apply_denoise=False, apply_sharpen=True)
    enhanced = preproc.image

    # ── Detect ───────────────────────────────────────────────────────────────
    det_result = detector.detect(enhanced)

    # ── Violations ───────────────────────────────────────────────────────────
    engine = _get_engine(camera_id)
    if stop_line_y is not None:
        engine._stop_rule.stop_line_y = stop_line_y

    violations = engine.analyze(enhanced, det_result)

    # ── OCR plates ───────────────────────────────────────────────────────────
    plate_map: dict = {}   # violation_idx → PlateOCRResult
    for i, v in enumerate(violations):
        if v.bbox:
            plate_result = plate_ocr.read_plate_from_bbox(enhanced, v.bbox)
            if plate_result and plate_result.confidence > 0.30:
                plate_map[i] = plate_result

    # ── Evidence image ────────────────────────────────────────────────────────
    ev = evidence_generator.generate(
        enhanced, violations,
        camera_id=camera_id,
        location=location,
        original_path=str(orig_path),
    )

    # ── Persist to DB ─────────────────────────────────────────────────────────
    saved_violations = []
    for i, v in enumerate(violations):
        plate = plate_map.get(i)
        record = Violation(
            violation_type      = v.violation_type,
            confidence          = v.confidence,
            vehicle_type        = v.vehicle_type,
            plate_number        = plate.clean_text if plate else None,
            plate_confidence    = plate.confidence if plate else None,
            bbox                = v.bbox,
            location            = location,
            original_image_path = str(orig_path),
            evidence_image_path = ev["evidence_path"],
            evidence_thumbnail  = ev["thumbnail"],
            status              = ViolationStatus.PENDING,
        )
        db.add(record)
        saved_violations.append(record)

    await db.flush()

    processing_ms = (time.perf_counter() - t_start) * 1000

    # ── Build response ────────────────────────────────────────────────────────
    from app.schemas import DetectedObject, ViolationResult as SchemaViolation, BBox, PlateResult

    detected_objs = [
        DetectedObject(
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            bbox=BBox(x1=d.x1, y1=d.y1, x2=d.x2, y2=d.y2),
            track_id=d.track_id,
        )
        for d in det_result.detections
    ]

    schema_violations = []
    for i, v in enumerate(violations):
        plate = plate_map.get(i)
        schema_violations.append(SchemaViolation(
            violation_type=v.violation_type,
            confidence=v.confidence,
            bbox=BBox(**v.bbox) if v.bbox else None,
            vehicle_type=v.vehicle_type,
            description=v.description,
            plate=PlateResult(
                plate_text=plate.clean_text,
                confidence=plate.confidence,
            ) if plate else None,
        ))

    return DetectionResponse(
        image_id=image_id,
        processing_time_ms=round(processing_ms, 1),
        detected_objects=detected_objs,
        violations=schema_violations,
        evidence_path=ev["evidence_path"],
        evidence_thumbnail=ev["thumbnail"],
        width=det_result.image_width,
        height=det_result.image_height,
    )


@router.post(
    "/batch",
    summary="Process multiple images in one request",
)
async def process_batch(
    files:     list[UploadFile] = File(...),
    camera_id: str              = Form(default="CAM-001"),
    location:  str              = Form(default="Unknown"),
    db: AsyncSession = Depends(get_db),
):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 images per batch.")

    results = []
    for f in files:
        try:
            # Reuse single-image logic per file
            result = await process_image(
                file=f, camera_id=camera_id, location=location, db=db
            )
            results.append({"filename": f.filename, "result": result})
        except HTTPException as e:
            results.append({"filename": f.filename, "error": e.detail})

    return {"batch_results": results, "total": len(files)}
