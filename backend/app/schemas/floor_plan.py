from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RoomObservation(BaseModel):
    id: str = Field(..., description="Unique identifier for the detected room")
    name: str = Field(..., description="Inferred room function, e.g. Living Room, Master Bedroom, Kitchen")
    area_m2: Optional[float] = Field(None, description="Estimated floor area in m2, null if dimensions unreadable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of room detection and bounds")
    bounds: Optional[List[float]] = Field(
        None,
        description="Normalized bounding box [x1, y1, x2, y2] within 0.0 - 1.0 coordinates",
    )
    is_area_verified: bool = Field(False, description="True ONLY if scale and true geometry are confirmed")
    is_rectangular_approximation: bool = Field(
        False,
        description="True if polygon is a bounding box approximation rather than verified contour",
    )
    area_status: str = Field(
        "unscaled_estimate",
        description="Status of room area: verified, approximate_calibrated, unscaled_estimate, or unresolved",
    )
    is_manual: bool = Field(False, description="True if a user created or corrected this room")


class ArchitecturalFeature(BaseModel):
    id: Optional[str] = Field(None, description="Stable identifier, assigned when the feature is stored")
    room_id: Optional[str] = Field(None, description="Id of the associated room (preferred over the room name)")
    type: str = Field(..., description="Feature type: door, window, wall, entrance, balcony")
    room: str = Field(..., description="Associated room name")
    confidence: float = Field(..., ge=0.0, le=1.0)
    wall: Optional[str] = Field(None, description="Perimeter wall boundary: north, south, east, or west")
    door_position: Optional[List[float]] = Field(None, description="Normalized coordinates [x, y] of door opening")
    hinge_point: Optional[List[float]] = Field(None, description="Door hinge pivot coordinate [x, y] on wall")
    strike_side: Optional[str] = Field(None, description="Door handle/latch strike side (opposite hinges)")
    strike_point: Optional[List[float]] = Field(None, description="Door strike/latch jamb coordinate [x, y] on wall")
    swing_direction: Optional[str] = Field(None, description="Door swing direction: into_room or out_of_room")
    bounds: Optional[List[float]] = Field(None, description="Normalized bounding box [x1, y1, x2, y2]")
    coordinates: Optional[Dict[str, Any]] = None
    is_manual: bool = Field(False, description="True if a user created or corrected this feature")


class VisionAnalysisResult(BaseModel):
    rooms: List[RoomObservation] = Field(default_factory=list)
    architectural_features: List[ArchitecturalFeature] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
