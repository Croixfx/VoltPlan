import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(String(50), nullable=False, default="pending")
    current_step = Column(String(50), nullable=False, default="uploading")
    error_message = Column(Text, nullable=True)

    # Architectural observations from AI vision
    rooms_data = Column(JSON, nullable=False, default=list)
    architectural_features_data = Column(JSON, nullable=False, default=list)
    observations = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)

    # Deterministic Engineering Results
    electrical_points_data = Column(JSON, nullable=False, default=list)
    circuits_data = Column(JSON, nullable=False, default=list)
    wiring_arcs_data = Column(JSON, nullable=False, default=list)
    boq_items_data = Column(JSON, nullable=False, default=list)
    cost_estimate_data = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project", back_populates="analysis")
