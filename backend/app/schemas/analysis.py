from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.schemas.electrical import ElectricalPoint, Circuit, WiringArc
from app.schemas.boq import BOQItem, CostEstimateResponse


class AnalysisStatusResponse(BaseModel):
    project_id: str
    status: str = Field(..., description="pending, processing, completed, failed")
    current_step: str = Field(
        ...,
        description="uploading, preparing_document, analyzing_plan, generating_recommendations, generating_boq, completed",
    )
    error_message: Optional[str] = None
    updated_at: datetime


class AnalysisResultResponse(BaseModel):
    project_id: str
    status: str
    current_step: str
    standard_applied: str

    rooms: List[RoomObservation] = Field(default_factory=list)
    architectural_features: List[ArchitecturalFeature] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    electrical_points: List[ElectricalPoint] = Field(default_factory=list)
    circuits: List[Circuit] = Field(default_factory=list)
    wiring_arcs: List[WiringArc] = Field(default_factory=list)
    boq_items: List[BOQItem] = Field(default_factory=list)
    cost_estimate: Optional[CostEstimateResponse] = None

    engineering_disclaimer: str = (
        "PRELIMINARY AI-ASSISTED ELECTRICAL PLANNING OUTPUT. "
        "Calculations and layout comply with configured baseline parameters of RS IEC 60364 / IEC 60364. "
        "All conductor sizing, circuit breaker selections, and protective devices must be validated by a certified "
        "professional electrical engineer before procurement or installation."
    )
    created_at: datetime
    updated_at: datetime
