"""Camera ORM model."""
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    ip_address = Column(String(255), nullable=True)
    rtsp_url = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("camera_groups.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    group = relationship("CameraGroup", back_populates="cameras")
    violations = relationship("Violation", back_populates="camera", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Camera {self.camera_id} @ {self.location}>"
