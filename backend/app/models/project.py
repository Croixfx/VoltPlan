import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    client = Column(String(255), nullable=False)
    building_type = Column(String(100), nullable=False, default="Residential")
    location = Column(String(255), nullable=False)
    standard = Column(String(100), nullable=False, default="RS IEC 60364")
    notes = Column(Text, nullable=True, default="")
    status = Column(String(50), nullable=False, default="created")

    floor_plan_name = Column(String(255), nullable=True)
    floor_plan_path = Column(String(512), nullable=True)
    floor_plan_content_type = Column(String(100), nullable=True)
    floor_plan_size = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    analysis = relationship("Analysis", back_populates="project", uselist=False, cascade="all, delete-orphan")
