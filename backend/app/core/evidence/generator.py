"""
Evidence image generator.
Draws bounding boxes, violation labels, plate text, timestamp,
camera ID and location onto annotated copies of input images.
Saves them to the structured evidence directory.
"""
from __future__ import annotations
import base64
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from app.config import settings, VIOLATION_COLORS, ViolationType
from app.core.detection.violation_rules import ViolationResult

logger = logging.getLogger(__name__)

# Font settings
FONT       = cv2.FONT_HERSHEY_SIMPLEX
SCALE      = settings.ANNOTATION_FONT_SCALE
THICKNESS  = settings.ANNOTATION_THICKNESS
PAD        = 6          # text padding pixels
THUMB_W    = 320        # thumbnail width


class EvidenceGenerator:
    """Annotates images with violation detections and saves evidence."""

    def generate(
        self,
        image: np.ndarray,
        violations: List[ViolationResult],
        *,
        camera_id: str = "CAM-001",
        location: str = "Unknown",
        original_path: Optional[str] = None,
    ) -> dict:
        """
        Produce annotated evidence image.

        Returns:
            {
                "evidence_path": str (absolute path),
                "thumbnail":     str (base64-encoded JPEG thumbnail),
                "annotated":     np.ndarray (full annotated image),
            }
        """
        annotated = image.copy()
        ts = datetime.now()

        # Draw all violation bounding boxes
        for v in violations:
            self._draw_violation(annotated, v)

        # Draw HUD overlay (timestamp, camera, location)
        self._draw_hud(annotated, ts, camera_id, location)

        # Optionally draw a "NO VIOLATIONS" banner
        if not violations:
            self._draw_banner(annotated, "NO VIOLATIONS DETECTED", (0, 200, 0))

        # Save evidence image
        evidence_path = self._save_evidence(annotated, ts)

        # Generate thumbnail
        thumb_b64 = self._make_thumbnail(annotated)

        return {
            "evidence_path": str(evidence_path),
            "thumbnail":     thumb_b64,
            "annotated":     annotated,
        }

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _draw_violation(self, img: np.ndarray, v: ViolationResult) -> None:
        color = VIOLATION_COLORS.get(v.violation_type, (0, 0, 255))
        bbox  = v.bbox or {}
        if not bbox:
            return

        x1 = int(bbox.get("x1", 0))
        y1 = int(bbox.get("y1", 0))
        x2 = int(bbox.get("x2", img.shape[1]))
        y2 = int(bbox.get("y2", img.shape[0]))

        # Bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, THICKNESS + 1)

        # Corner accent marks
        corner_len = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
        for cx, cy, dx, dy in [
            (x1, y1, 1, 1), (x2, y1, -1, 1),
            (x1, y2, 1, -1), (x2, y2, -1, -1),
        ]:
            cv2.line(img, (cx, cy), (cx + dx * corner_len, cy), color, THICKNESS + 2)
            cv2.line(img, (cx, cy), (cx, cy + dy * corner_len), color, THICKNESS + 2)

        # Label background + text
        label = f"{v.violation_type.replace('_', ' ').upper()} {v.confidence:.0%}"
        if v.violation_type == ViolationType.HELMET_VIOLATION and hasattr(v, 'related_objects'):
            pass  # could append plate info

        (tw, th), _ = cv2.getTextSize(label, FONT, SCALE, THICKNESS)
        label_y = max(y1 - PAD, th + PAD)
        cv2.rectangle(img, (x1, label_y - th - PAD), (x1 + tw + PAD * 2, label_y + PAD), color, -1)
        cv2.putText(img, label, (x1 + PAD, label_y), FONT, SCALE, (255, 255, 255), THICKNESS, cv2.LINE_AA)

    def _draw_hud(self, img: np.ndarray, ts: datetime, camera_id: str, location: str) -> None:
        h, w = img.shape[:2]
        hud_h = 55
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_h), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        ts_str  = ts.strftime("%Y-%m-%d  %H:%M:%S")
        cam_str = f"Cam: {camera_id}  |  {location}"

        cv2.putText(img, ts_str,  (10, 20),       FONT, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(img, cam_str, (10, 42),        FONT, 0.50, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(img, "TVDS v1.0", (w - 130, 20), FONT, 0.50, (100, 100, 100), 1, cv2.LINE_AA)

    def _draw_banner(self, img: np.ndarray, text: str, color: tuple) -> None:
        h, w = img.shape[:2]
        (tw, th), _ = cv2.getTextSize(text, FONT, 0.9, 2)
        x = (w - tw) // 2
        y = h - 20
        cv2.putText(img, text, (x, y), FONT, 0.9, color, 2, cv2.LINE_AA)

    # ── Storage helpers ───────────────────────────────────────────────────────

    def _save_evidence(self, img: np.ndarray, ts: datetime) -> Path:
        date_dir = settings.EVIDENCE_DIR / ts.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        filename = f"ev_{ts.strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        path = date_dir / filename
        cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return path

    def _make_thumbnail(self, img: np.ndarray) -> str:
        h, w = img.shape[:2]
        thumb_h = int(THUMB_W * h / w)
        thumb = cv2.resize(img, (THUMB_W, thumb_h), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok:
            return ""
        return base64.b64encode(buf.tobytes()).decode("utf-8")


# Module-level singleton
evidence_generator = EvidenceGenerator()
