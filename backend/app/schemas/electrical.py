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
    # Stage 2: Traceable Electrical Placement Provenance
    x_mm: Optional[float] = Field(None, description="Canonical physical X coordinate in millimeters")
    y_mm: Optional[float] = Field(None, description="Canonical physical Y coordinate in millimeters")
    coordinate_system: str = Field(
        "canonical_mm_and_normalized_ratio",
        description="Coordinate system specification",
    )
    placement_rule: Optional[str] = Field(None, description="Explicit rule reference governing placement")
    geometry_used: Optional[str] = Field(
        None,
        description="Geometric basis used: wall_strike_side_tangent, room_centroid, perimeter_wall_snapped, etc.",
    )
    is_scale_verified: bool = Field(False, description="True if scale was calibrated")
    is_geometry_verified: bool = Field(False, description="True if room polygon was exact verified contour")
    nearby_wall_id: Optional[str] = Field(None, description="Associated wall segment ID if attached/snapped")
    nearby_door_id: Optional[str] = Field(None, description="Associated opening ID if switch/entrypoint")
    nearby_obstacle_id: Optional[str] = Field(None, description="Associated obstacle ID if wet zone or appliance")
    clearance_envelope_applied: Optional[str] = Field(
        None,
        description="Safety buffer or door-swing clearance zone evaluated during placement",
    )
    placement_status: str = Field(
        "proposed",
        description="proposed, needs_confirmation, or unresolved",
    )
    reasoning: Optional[str] = Field(
        None,
        description="Human-readable architectural and engineering justification for point placement",
    )


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

