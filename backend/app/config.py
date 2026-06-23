"""
Central application configuration.
All settings are driven by environment variables (see .env.example).
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List
import os


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Traffic Violation Detection System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./traffic_violations.db"

    # ── Storage ───────────────────────────────────────────────────
    EVIDENCE_DIR: Path = BASE_DIR / "evidence"
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── YOLO Detection ───────────────────────────────────────────
    YOLO_MODEL_PATH: str = "yolov8n.pt"          # nano for speed; swap to yolov8m.pt for accuracy
    YOLO_CONFIDENCE_THRESHOLD: float = 0.45
    YOLO_IOU_THRESHOLD: float = 0.50
    YOLO_DEVICE: str = "cpu"                      # "cuda" if GPU available
    YOLO_IMG_SIZE: int = 640

    # ── License Plate Detection ───────────────────────────────────
    PLATE_MODEL_PATH: str = "yolov8n.pt"          # Replace with a plate-specific model if available
    PLATE_CONFIDENCE_THRESHOLD: float = 0.40
    OCR_ENGINE: str = "easyocr"                   # "easyocr" | "paddleocr"
    OCR_LANGUAGES: List[str] = ["en"]

    # ── Violation Thresholds ──────────────────────────────────────
    HELMET_CONFIDENCE_MIN: float = 0.50
    TRIPLE_RIDING_MIN_PERSONS: int = 3
    STOP_LINE_MARGIN_PX: int = 10
    PARKING_STATIONARY_FRAMES: int = 30

    # ── Tracking ─────────────────────────────────────────────────
    TRACKER_TYPE: str = "bytetrack"               # "bytetrack" | "deepsort"
    TRACKER_MAX_AGE: int = 30

    # ── Evidence Annotations ──────────────────────────────────────
    ANNOTATION_FONT_SCALE: float = 0.6
    ANNOTATION_THICKNESS: int = 2

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        # Look for .env in backend/ directory (where uvicorn runs from)
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure storage directories exist
settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# COCO class IDs used by default YOLOv8
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    1: "bicycle",
}
PERSON_CLASS_ID = 0

# Violation type constants
class ViolationType:
    HELMET_VIOLATION     = "helmet_violation"
    SEATBELT_VIOLATION   = "seatbelt_violation"
    TRIPLE_RIDING        = "triple_riding"
    WRONG_SIDE_DRIVING   = "wrong_side_driving"
    STOP_LINE_VIOLATION  = "stop_line_violation"
    RED_LIGHT_VIOLATION  = "red_light_violation"
    ILLEGAL_PARKING      = "illegal_parking"

    ALL = [
        HELMET_VIOLATION, SEATBELT_VIOLATION, TRIPLE_RIDING,
        WRONG_SIDE_DRIVING, STOP_LINE_VIOLATION,
        RED_LIGHT_VIOLATION, ILLEGAL_PARKING,
    ]

# Color palette per violation (BGR for OpenCV)
VIOLATION_COLORS = {
    ViolationType.HELMET_VIOLATION:     (0,   0,   255),   # red
    ViolationType.SEATBELT_VIOLATION:   (0,   165, 255),   # orange
    ViolationType.TRIPLE_RIDING:        (0,   255, 255),   # yellow
    ViolationType.WRONG_SIDE_DRIVING:   (255, 0,   255),   # magenta
    ViolationType.STOP_LINE_VIOLATION:  (255, 0,   0  ),   # blue
    ViolationType.RED_LIGHT_VIOLATION:  (0,   0,   200),   # dark-red
    ViolationType.ILLEGAL_PARKING:      (128, 0,   128),   # purple
}
