"""Violation ORM model — central record for each detected infraction."""
from sqlalchemy import (
    Column, String, Float, DateTime, Text,
    ForeignKey, JSON, Boolean, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ViolationStatus(str, enum.Enum):
    PENDING   = "pending"
    REVIEWED  = "reviewed"
    RESOLVED  = "resolved"
    DISPUTED  = "disputed"
    DISMISSED = "dismissed"


class Violation(Base):
    __tablename__ = "violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Detection metadata
    violation_type   = Column(String(64), nullable=False, index=True)
    confidence       = Column(Float, nullable=False)
    detected_at      = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Vehicle info
    vehicle_type     = Column(String(32), nullable=True)
    plate_number     = Column(String(32), nullable=True, index=True)
    plate_confidence = Column(Float, nullable=True)

    # Spatial metadata
    bbox             = Column(JSON, nullable=True)   # {x1, y1, x2, y2}
    location         = Column(String(255), nullable=True)
    latitude         = Column(Float, nullable=True)
    longitude        = Column(Float, nullable=True)

    # Evidence
    original_image_path  = Column(String(512), nullable=True)
    evidence_image_path  = Column(String(512), nullable=True)
    evidence_thumbnail   = Column(Text, nullable=True)   # base64 small preview

    # Status & review
    status           = Column(SAEnum(ViolationStatus, native_enum=False), default=ViolationStatus.PENDING, index=True)
    reviewer_notes   = Column(Text, nullable=True)
    is_false_positive = Column(Boolean, default=False)

    # Relations
    camera_id   = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=True)
    vehicle_id  = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)

    camera  = relationship("Camera",  back_populates="violations")
    vehicle = relationship("Vehicle", back_populates="violations")

    def __repr__(self) -> str:
        return f"<Violation {self.violation_type} | plate={self.plate_number} | {self.detected_at}>"
