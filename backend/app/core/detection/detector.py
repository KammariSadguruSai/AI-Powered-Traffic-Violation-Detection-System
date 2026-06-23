"""
YOLOv8 vehicle and person detector.
Wraps the ultralytics API and returns structured DetectedObject instances.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings, VEHICLE_CLASSES, PERSON_CLASS_ID

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    class_id:   int
    class_name: str
    confidence: float
    x1: float; y1: float; x2: float; y2: float
    track_id:   Optional[int] = None

    @property
    def bbox(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    def iou(self, other: "Detection") -> float:
        ix1 = max(self.x1, other.x1); iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2); iy2 = min(self.y2, other.y2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass
class DetectorResult:
    detections:      List[Detection] = field(default_factory=list)
    inference_ms:    float = 0.0
    image_width:     int = 0
    image_height:    int = 0

    @property
    def vehicles(self) -> List[Detection]:
        return [d for d in self.detections if d.class_id in VEHICLE_CLASSES]

    @property
    def persons(self) -> List[Detection]:
        return [d for d in self.detections if d.class_id == PERSON_CLASS_ID]

    @property
    def motorcycles(self) -> List[Detection]:
        return [d for d in self.detections if d.class_id == 3]  # COCO id=3


class YOLODetector:
    """
    Singleton-friendly YOLOv8 wrapper.
    Lazy-loads the model on first inference call to avoid startup latency.
    """

    def __init__(
        self,
        model_path: str = settings.YOLO_MODEL_PATH,
        confidence: float = settings.YOLO_CONFIDENCE_THRESHOLD,
        iou: float = settings.YOLO_IOU_THRESHOLD,
        device: str = settings.YOLO_DEVICE,
        img_size: int = settings.YOLO_IMG_SIZE,
    ):
        self._model_path = model_path
        self._confidence = confidence
        self._iou = iou
        self._device = device
        self._img_size = img_size
        self._model = None

    # ── Lazy loader ───────────────────────────────────────────────────────────

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO model: {self._model_path} on {self._device}")
            self._model = YOLO(self._model_path)
            self._model.to(self._device)
            logger.info("YOLO model loaded successfully.")
        except ImportError:
            logger.warning(
                "ultralytics not installed — YOLO detection disabled. "
                "Install with: pip install ultralytics"
            )
            self._model = "stub"  # sentinel so we only warn once
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self._model = "stub"

    # ── Inference ─────────────────────────────────────────────────────────────

    def detect(self, image: np.ndarray) -> DetectorResult:
        """
        Run inference on a BGR numpy image.
        Returns an empty result gracefully if YOLO is not installed.
        """
        self._load_model()
        h, w = image.shape[:2]

        # Stub mode — YOLO not available
        if self._model == "stub":
            return DetectorResult(image_width=w, image_height=h, inference_ms=0.0)

        t0 = time.perf_counter()

        results = self._model.predict(
            source=image,
            conf=self._confidence,
            iou=self._iou,
            imgsz=self._img_size,
            device=self._device,
            verbose=False,
        )

        inference_ms = (time.perf_counter() - t0) * 1000
        detections = self._parse_results(results, w, h)

        return DetectorResult(
            detections=detections,
            inference_ms=inference_ms,
            image_width=w,
            image_height=h,
        )

    def _parse_results(self, results, img_w: int, img_h: int) -> List[Detection]:
        detections: List[Detection] = []
        if not results:
            return detections

        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.cpu().numpy()
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls  = int(box.cls[0])

                class_name = result.names.get(cls, str(cls))

                detections.append(Detection(
                    class_id=cls,
                    class_name=class_name,
                    confidence=conf,
                    x1=float(xyxy[0]), y1=float(xyxy[1]),
                    x2=float(xyxy[2]), y2=float(xyxy[3]),
                ))

        return detections


# Module-level singleton
detector = YOLODetector()
