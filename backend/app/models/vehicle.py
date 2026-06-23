"""Vehicle ORM model."""
from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate_number = Column(String(32), nullable=True, index=True)
    vehicle_type = Column(String(32), nullable=True)      # car, motorcycle, bus, truck …
    color = Column(String(32), nullable=True)
    make = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    registration_state = Column(String(8), nullable=True)  # e.g. "MH", "DL"
    total_violations = Column(Integer, default=0)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), onupdate=func.now())
    notes = Column(Text, nullable=True)

    violations = relationship("Violation", back_populates="vehicle", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Vehicle {self.plate_number} ({self.vehicle_type})>"
