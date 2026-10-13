from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation
from app.services.geometry_validator import GeometryIssue


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    bounds: List[float] = Field(..., min_length=4, max_length=4, description="[x1, y1, x2, y2] normalized to the plan")


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    bounds: Optional[List[float]] = Field(None, min_length=4, max_length=4)


class DoorCreate(BaseModel):
    room_id: str
    wall: str = Field(..., description="north, south, east or west wall of the room")
    position: float = Field(0.5, ge=0.0, le=1.0, description="Door centre along the wall: 0 = west/north end, 1 = east/south end")
    swing_direction: str = Field("into_room", description="into_room or out_of_room")
    strike_side: Optional[str] = Field(None, description="Handle side: east/west on north-south walls, north/south on east-west walls")


class DoorUpdate(BaseModel):
    room_id: Optional[str] = None
    wall: Optional[str] = None
    position: Optional[float] = Field(None, ge=0.0, le=1.0)
    swing_direction: Optional[str] = None
    strike_side: Optional[str] = None


class GeometryResponse(BaseModel):
    project_id: str
    rooms: List[RoomObservation] = Field(default_factory=list)
    features: List[ArchitecturalFeature] = Field(default_factory=list)
    issues: List[GeometryIssue] = Field(default_factory=list)
    can_generate: bool = Field(..., description="False while any error-level issue remains")
    reviewed: bool = Field(..., description="A user has corrected rooms / doors")
    needs_regeneration: bool = Field(..., description="Rooms / doors changed since the equipment was last generated")
    scale_calibrated: bool = False
