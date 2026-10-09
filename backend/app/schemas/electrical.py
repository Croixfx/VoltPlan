from typing import Optional, List
from pydantic import BaseModel, Field


class ElectricalPoint(BaseModel):
    id: str
    room_id: str
    room_name: str
    type: str = Field(
        ...,
        description="lighting, twin_socket, single_socket, ac_point, cooker_point, water_heater, switch_1way, switch_2way, distribution_board",
    )
    quantity: int = Field(1, ge=1)
    power_rating_w: float = Field(..., ge=0.0)
    x_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized X coordinate on floor plan")
    y_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized Y coordinate on floor plan")
    circuit_id: Optional[str] = None
    recommended_cable: Optional[str] = None
    recommended_protection: Optional[str] = None
    rule_reference: str
    status: str = Field(
        "RECOMMENDED",
        description="CALCULATED, RECOMMENDED, or REQUIRES_ENGINEER_REVIEW",
    )
    review_notes: Optional[str] = None


class Circuit(BaseModel):
    id: str
    name: str
    description: str
    circuit_type: str = Field("power", description="lighting, power, appliance, sub_distribution")
    points_count: int = Field(..., ge=0)
    connected_load_w: float = Field(..., ge=0.0)
    phase: str = Field("L1", description="Assigned phase (L1, L2, L3)")
    cable: Optional[str] = Field(None, description="Recommended conductor cross-section or null if review required")
    protection: Optional[str] = Field(None, description="MCB curve and rating e.g. 10A Type B")
    rcd: Optional[str] = Field(None, description="Residual current protection e.g. 30mA Type A")
    status: str = Field("CALCULATED", description="CALCULATED or REQUIRES_ENGINEER_REVIEW")
    review_notes: Optional[str] = None


class WiringArc(BaseModel):
    id: str
    circuit_id: Optional[str] = None
    room_id: str
    switch_id: str
    luminaire_id: str
    start_point: List[float] = Field(..., description="[x, y] start coordinate at switch")
    control_point: List[float] = Field(..., description="[x, y] quadratic Bézier control point")
    end_point: List[float] = Field(..., description="[x, y] end coordinate at luminaire")
    length_norm: float = Field(..., description="Normalized spline arc length")

