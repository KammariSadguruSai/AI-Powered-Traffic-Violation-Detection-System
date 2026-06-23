"""
License plate OCR module.
Primary: EasyOCR  |  Fallback: PaddleOCR
Validates extracted text against Indian registration plate formats.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from typing import Optional, List

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Indian plate format examples: MH12AB1234, DL 3C AB 1234, TN 09 CD 5678
_INDIAN_PLATE_PATTERN = re.compile(
    r"^[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4}$",
    re.IGNORECASE,
)

# Generic fallback (alphanumeric, 4-12 chars)
_GENERIC_PLATE_PATTERN = re.compile(r"^[A-Z0-9\s\-]{4,12}$", re.IGNORECASE)


@dataclass
class PlateOCRResult:
    raw_text:    str
    clean_text:  str
    confidence:  float
    is_valid:    bool           # matches Indian format
    engine_used: str


class PlateOCR:
    """
    Multi-engine OCR for license plate text extraction.
    Tries EasyOCR first; falls back to PaddleOCR if unavailable.
    """

    def __init__(self):
        self._easy_reader = None
        self._paddle_ocr  = None
        self._engine      = settings.OCR_ENGINE
        self._langs       = settings.OCR_LANGUAGES

    # ── Public API ────────────────────────────────────────────────────────────

    def read_plate(self, roi: np.ndarray) -> Optional[PlateOCRResult]:
        """
        Extract plate text from a cropped plate image (BGR numpy array).
        Returns None if no readable text found.
        """
        if roi is None or roi.size == 0:
            return None

        # Pre-process the ROI for better OCR accuracy
        processed = self._preprocess_plate(roi)

        if self._engine == "easyocr":
            result = self._easyocr_read(processed)
        else:
            result = self._paddleocr_read(processed)

        # Fallback chain
        if result is None or result.confidence < 0.30:
            alt_result = (
                self._paddleocr_read(processed)
                if self._engine == "easyocr"
                else self._easyocr_read(processed)
            )
            if alt_result and (result is None or alt_result.confidence > result.confidence):
                result = alt_result

        return result

    def read_plate_from_bbox(
        self, image: np.ndarray, bbox: dict
    ) -> Optional[PlateOCRResult]:
        """Crop the plate region from a full image using bbox and run OCR."""
        h, w = image.shape[:2]
        x1 = int(max(0, bbox.get("x1", 0)))
        y1 = int(max(0, bbox.get("y1", 0)))
        x2 = int(min(w, bbox.get("x2", w)))
        y2 = int(min(h, bbox.get("y2", h)))
        roi = image[y1:y2, x1:x2]
        return self.read_plate(roi)

    # ── Engine implementations ────────────────────────────────────────────────

    def _easyocr_read(self, roi: np.ndarray) -> Optional[PlateOCRResult]:
        try:
            if self._easy_reader is None:
                import easyocr
                logger.info("Initialising EasyOCR reader…")
                self._easy_reader = easyocr.Reader(
                    self._langs,
                    gpu=settings.YOLO_DEVICE == "cuda",
                    verbose=False,
                )

            results: List = self._easy_reader.readtext(roi, detail=1, paragraph=False)
            if not results:
                return None

            # Pick highest-confidence result
            best = max(results, key=lambda r: r[2])
            raw  = best[1].strip().upper()
            conf = float(best[2])
            return self._build_result(raw, conf, "easyocr")

        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")
            return None

    def _paddleocr_read(self, roi: np.ndarray) -> Optional[PlateOCRResult]:
        try:
            if self._paddle_ocr is None:
                from paddleocr import PaddleOCR
                logger.info("Initialising PaddleOCR…")
                self._paddle_ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    use_gpu=settings.YOLO_DEVICE == "cuda",
                    show_log=False,
                )

            result = self._paddle_ocr.ocr(roi, cls=True)
            if not result or not result[0]:
                return None

            lines = result[0]
            best  = max(lines, key=lambda l: l[1][1])
            raw   = best[1][0].strip().upper()
            conf  = float(best[1][1])
            return self._build_result(raw, conf, "paddleocr")

        except Exception as e:
            logger.warning(f"PaddleOCR failed: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _preprocess_plate(self, roi: np.ndarray) -> np.ndarray:
        """Upscale, greyscale, and binarise for better OCR accuracy."""
        import cv2
        # Upscale small plates
        h, w = roi.shape[:2]
        if w < 200:
            scale = 200 / w
            roi = cv2.resize(roi, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # CLAHE for contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        gray  = clahe.apply(gray)
        # Otsu binarization
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Back to BGR for OCR engines that expect 3-channel
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def _clean_plate(self, raw: str) -> str:
        """Remove noise characters; keep letters, digits, spaces."""
        cleaned = re.sub(r"[^A-Z0-9\s]", "", raw.upper()).strip()
        return cleaned

    def _build_result(self, raw: str, conf: float, engine: str) -> PlateOCRResult:
        clean = self._clean_plate(raw)
        valid = bool(_INDIAN_PLATE_PATTERN.match(clean.replace(" ", "")))
        if not valid:
            valid = bool(_GENERIC_PLATE_PATTERN.match(clean))
        return PlateOCRResult(
            raw_text=raw,
            clean_text=clean,
            confidence=conf,
            is_valid=valid,
            engine_used=engine,
        )


# Module-level singleton
plate_ocr = PlateOCR()
