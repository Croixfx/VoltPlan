from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    client: str = Field(..., min_length=2, max_length=255)
    building_type: str = Field("Residential", max_length=100)
    location: str = Field(..., min_length=2, max_length=255)
    standard: str = Field("RS IEC 60364", max_length=100)
    notes: Optional[str] = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client: Optional[str] = None
    building_type: Optional[str] = None
    location: Optional[str] = None
    standard: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client: str
    building_type: str
    location: str
    standard: str
    notes: Optional[str] = ""
    status: str
    floor_plan_name: Optional[str] = None
    floor_plan_content_type: Optional[str] = None
    floor_plan_size: Optional[int] = None
    created_at: datetime
    updated_at: datetime
