"""
Real-time live monitoring via WebSocket.
Accepts video frames (base64 JPEG), runs the full AI pipeline,
and streams back detection results + annotated thumbnails.
"""
from __future__ import annotations
import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.core.preprocessing.enhancer import enhancer
from app.core.detection.detector import detector
from app.core.detection.violation_rules import ViolationEngine
from app.core.ocr.plate_ocr import plate_ocr
from app.core.evidence.generator import evidence_generator
from app.models.violation import Violation, ViolationStatus

router = APIRouter(prefix="/live", tags=["Live Monitor"])
logger = logging.getLogger(__name__)

# ── Active WebSocket connections ──────────────────────────────────────────────
_active_connections: list[WebSocket] = []


# ── WebSocket Live Stream ─────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_live(ws: WebSocket):
    """
    Real-time frame processing via WebSocket.

    Protocol:
    1. Client sends JSON config message on connect:
       {"type": "config", "camera_id": "CAM-001", "location": "Main Rd", "stop_line_y": 400, "fps": 5}
    2. Client sends frame messages:
       {"type": "frame", "data": "<base64-encoded JPEG>"}
    3. Server responds per frame:
       {"type": "result", "frame_id": int, "processing_ms": float,
        "detected_objects": [...], "violations": [...], "annotated_frame": "<base64>",
        "stats": {"total_objects": int, "total_violations": int}}
    4. Client sends {"type": "stop"} to end session.
    """
    await ws.accept()
    _active_connections.append(ws)
    logger.info(f"Live WebSocket connected. Active: {len(_active_connections)}")

    # Session state
    engine = ViolationEngine()
    camera_id = "CAM-001"
    location = "Unknown"
    frame_count = 0
    session_violations = 0
    session_objects = 0
    session_start = time.time()

    try:
        while True:
            raw_msg = await ws.receive_text()
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── Config message ────────────────────────────────────────────
            if msg_type == "config":
                camera_id = msg.get("camera_id", camera_id)
                location = msg.get("location", location)
                stop_line_y = msg.get("stop_line_y")
                road_center_x = msg.get("road_center_x")

                engine = ViolationEngine(
                    stop_line_y=int(stop_line_y) if stop_line_y else None,
                    road_center_x=int(road_center_x) if road_center_x else None,
                )
                await ws.send_json({
                    "type": "config_ack",
                    "camera_id": camera_id,
                    "location": location,
                    "message": "Configuration applied",
                })
                continue

            # ── Stop message ──────────────────────────────────────────────
            if msg_type == "stop":
                duration = time.time() - session_start
                await ws.send_json({
                    "type": "session_summary",
                    "total_frames": frame_count,
                    "total_violations": session_violations,
                    "total_objects": session_objects,
                    "duration_seconds": round(duration, 1),
                    "avg_fps": round(frame_count / max(duration, 0.001), 1),
                })
                break

            # ── Frame message ─────────────────────────────────────────────
            if msg_type == "frame":
                frame_data = msg.get("data", "")
                if not frame_data:
                    await ws.send_json({"type": "error", "message": "No frame data"})
                    continue

                t_start = time.perf_counter()
                frame_count += 1

                try:
                    # Decode base64 JPEG to numpy array
                    img_bytes = base64.b64decode(frame_data)
                    bgr = enhancer.load_from_bytes(img_bytes)

                    # Enhance
                    preproc = enhancer.enhance(
                        bgr,
                        apply_clahe=True,
                        apply_denoise=False,  # skip for speed in live mode
                        apply_sharpen=False,   # skip for speed in live mode
                        apply_gamma=True,
                    )
                    enhanced = preproc.image

                    # Detect
                    det_result = detector.detect(enhanced)

                    # Violations
                    violations = engine.analyze(enhanced, det_result)

                    # OCR on violations
                    plate_results = {}
                    for i, v in enumerate(violations):
                        if v.bbox:
                            plate_result = plate_ocr.read_plate_from_bbox(enhanced, v.bbox)
                            if plate_result and plate_result.confidence > 0.30:
                                plate_results[i] = plate_result

                    # Generate annotated thumbnail
                    annotated = enhanced.copy()
                    # Draw detection boxes
                    for d in det_result.detections:
                        color = (0, 255, 0) if d.class_id == 0 else (255, 200, 0)
                        cv2.rectangle(annotated, (int(d.x1), int(d.y1)),
                                      (int(d.x2), int(d.y2)), color, 2)
                        label = f"{d.class_name} {d.confidence:.0%}"
                        cv2.putText(annotated, label, (int(d.x1), int(d.y1) - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

                    # Draw violation boxes
                    for v in violations:
                        if v.bbox:
                            vcolor = (0, 0, 255)
                            bx = v.bbox
                            cv2.rectangle(annotated, (int(bx["x1"]), int(bx["y1"])),
                                          (int(bx["x2"]), int(bx["y2"])), vcolor, 3)
                            vlabel = f"{v.violation_type.replace('_', ' ').upper()} {v.confidence:.0%}"
                            (tw, th), _ = cv2.getTextSize(vlabel, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                            cv2.rectangle(annotated,
                                          (int(bx["x1"]), int(bx["y1"]) - th - 8),
                                          (int(bx["x1"]) + tw + 8, int(bx["y1"])),
                                          vcolor, -1)
                            cv2.putText(annotated, vlabel,
                                        (int(bx["x1"]) + 4, int(bx["y1"]) - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

                    # Draw HUD
                    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    hud_text = f"{ts_str} | {camera_id} | {location}"
                    h_img, w_img = annotated.shape[:2]
                    overlay = annotated.copy()
                    cv2.rectangle(overlay, (0, 0), (w_img, 30), (10, 10, 10), -1)
                    cv2.addWeighted(overlay, 0.7, annotated, 0.3, 0, annotated)
                    cv2.putText(annotated, hud_text, (8, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)
                    cv2.putText(annotated, f"LIVE | Frame {frame_count}",
                                (w_img - 180, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 100), 1, cv2.LINE_AA)

                    # Encode annotated frame to base64
                    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    annotated_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

                    processing_ms = (time.perf_counter() - t_start) * 1000

                    # Update session stats
                    session_objects += len(det_result.detections)
                    session_violations += len(violations)

                    # Build violation details
                    violation_list = []
                    for i, v in enumerate(violations):
                        plate = plate_results.get(i)
                        violation_list.append({
                            "violation_type": v.violation_type,
                            "confidence": round(v.confidence, 3),
                            "vehicle_type": v.vehicle_type,
                            "description": v.description,
                            "plate_text": plate.clean_text if plate else None,
                            "plate_confidence": round(plate.confidence, 3) if plate else None,
                            "bbox": v.bbox,
                            "timestamp": datetime.now().isoformat(),
                        })

                    # Save significant violations to DB in background
                    if violations:
                        asyncio.create_task(
                            _save_violations_to_db(
                                violations, plate_results, enhanced,
                                camera_id, location
                            )
                        )

                    # Build detected objects list
                    objects_list = [
                        {
                            "class_name": d.class_name,
                            "confidence": round(d.confidence, 3),
                            "bbox": {"x1": d.x1, "y1": d.y1, "x2": d.x2, "y2": d.y2},
                        }
                        for d in det_result.detections
                    ]

                    # Send response
                    await ws.send_json({
                        "type": "result",
                        "frame_id": frame_count,
                        "processing_ms": round(processing_ms, 1),
                        "detected_objects": objects_list,
                        "violations": violation_list,
                        "annotated_frame": annotated_b64,
                        "stats": {
                            "total_objects": len(det_result.detections),
                            "total_violations": len(violations),
                            "session_violations": session_violations,
                            "session_objects": session_objects,
                            "session_frames": frame_count,
                            "image_size": f"{det_result.image_width}x{det_result.image_height}",
                        },
                    })

                except Exception as e:
                    logger.error(f"Frame processing error: {e}", exc_info=True)
                    await ws.send_json({
                        "type": "error",
                        "message": f"Frame processing failed: {str(e)}",
                        "frame_id": frame_count,
                    })
                continue

            # Unknown message type
            await ws.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("Live WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws in _active_connections:
            _active_connections.remove(ws)
        logger.info(f"Active connections: {len(_active_connections)}")


# ── Background DB save ────────────────────────────────────────────────────────

async def _save_violations_to_db(
    violations, plate_results, image, camera_id, location
):
    """Save detected violations to the database in background."""
    try:
        # Generate evidence
        ev = evidence_generator.generate(
            image, violations,
            camera_id=camera_id,
            location=location,
        )

        async with AsyncSessionLocal() as session:
            for i, v in enumerate(violations):
                plate = plate_results.get(i)
                record = Violation(
                    violation_type=v.violation_type,
                    confidence=v.confidence,
                    vehicle_type=v.vehicle_type,
                    plate_number=plate.clean_text if plate else None,
                    plate_confidence=plate.confidence if plate else None,
                    bbox=v.bbox,
                    location=location,
                    evidence_image_path=ev["evidence_path"],
                    evidence_thumbnail=ev["thumbnail"],
                    status=ViolationStatus.PENDING,
                )
                session.add(record)
            await session.commit()
            logger.debug(f"Saved {len(violations)} live violations to DB.")
    except Exception as e:
        logger.error(f"Failed to save live violations: {e}", exc_info=True)


# ── REST Endpoints ────────────────────────────────────────────────────────────

@router.get("/status", summary="Live monitor system status")
async def live_status():
    return {
        "active_connections": len(_active_connections),
        "detector_ready": detector._model is not None and detector._model != "stub",
        "model": settings.YOLO_MODEL_PATH,
        "device": settings.YOLO_DEVICE,
    }


@router.post(
    "/process-video",
    summary="Process an uploaded video file frame-by-frame",
)
async def process_video(
    file: UploadFile = File(..., description="Video file (MP4, AVI, etc.)"),
    camera_id: str = Form(default="CAM-001"),
    location: str = Form(default="Unknown"),
    skip_frames: int = Form(default=5, description="Process every Nth frame"),
    db: AsyncSession = Depends(get_db),
):
    """Process a video file and extract all violations."""
    content_type = file.content_type or ""
    if not (content_type.startswith("video/") or file.filename.endswith((".mp4", ".avi", ".mov", ".mkv"))):
        raise HTTPException(status_code=415, detail="Only video files accepted.")

    # Save temp video
    video_bytes = await file.read()
    temp_path = settings.UPLOAD_DIR / f"vid_{uuid.uuid4().hex}.mp4"
    temp_path.write_bytes(video_bytes)

    try:
        cap = cv2.VideoCapture(str(temp_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot open video file.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30

        engine = ViolationEngine()
        all_violations = []
        processed_frames = 0
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % skip_frames != 0:
                continue

            processed_frames += 1

            # Enhance
            preproc = enhancer.enhance(frame, apply_clahe=True, apply_denoise=False, apply_sharpen=False)
            enhanced = preproc.image

            # Detect
            det_result = detector.detect(enhanced)

            # Violations
            violations = engine.analyze(enhanced, det_result)

            for v in violations:
                plate_result = None
                if v.bbox:
                    plate_result = plate_ocr.read_plate_from_bbox(enhanced, v.bbox)

                all_violations.append({
                    "frame": frame_idx,
                    "timestamp_sec": round(frame_idx / fps, 2),
                    "violation_type": v.violation_type,
                    "confidence": round(v.confidence, 3),
                    "vehicle_type": v.vehicle_type,
                    "description": v.description,
                    "plate_text": plate_result.clean_text if plate_result and plate_result.confidence > 0.30 else None,
                })

                # Save to DB
                record = Violation(
                    violation_type=v.violation_type,
                    confidence=v.confidence,
                    vehicle_type=v.vehicle_type,
                    plate_number=plate_result.clean_text if plate_result and plate_result.confidence > 0.30 else None,
                    plate_confidence=plate_result.confidence if plate_result else None,
                    bbox=v.bbox,
                    location=location,
                    status=ViolationStatus.PENDING,
                )
                db.add(record)

        cap.release()
        await db.flush()

        return {
            "total_frames": total_frames,
            "processed_frames": processed_frames,
            "skip_rate": skip_frames,
            "violations_found": len(all_violations),
            "violations": all_violations,
            "video_fps": fps,
            "video_duration_sec": round(total_frames / fps, 1),
        }

    finally:
        # Clean up temp file
        try:
            temp_path.unlink()
        except Exception:
            pass
