from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


def _check_standard(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    # imported here: the rule modules import the schemas, so a top-level import would be circular
    from app.engineering_rules.registry import UnsupportedStandardError, get_engineering_standard

    try:
        get_engineering_standard(value)
    except UnsupportedStandardError as e:
        raise ValueError(str(e)) from None
    return value


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    client: str = Field(..., min_length=2, max_length=255)
    building_type: str = Field("Residential", max_length=100)
    location: str = Field(..., min_length=2, max_length=255)
    standard: str = Field("RS IEC 60364", max_length=100)
    notes: Optional[str] = ""

    _standard_has_rules = field_validator("standard")(_check_standard)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client: Optional[str] = None
    building_type: Optional[str] = None
    location: Optional[str] = None
    standard: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    _standard_has_rules = field_validator("standard")(_check_standard)


class ScalePoint(BaseModel):
    """A point on the plan image as a ratio (0-1) of image width/height."""
    x_ratio: float = Field(..., ge=0.0, le=1.0)
    y_ratio: float = Field(..., ge=0.0, le=1.0)


class ScaleCalibrationRequest(BaseModel):
    point_a: ScalePoint
    point_b: ScalePoint
    real_distance_mm: float = Field(..., gt=0, le=200_000)


class ScaleCalibrationResponse(BaseModel):
    project_id: str
    scale_mm_per_pixel: float
    reference_pixels: float
    real_distance_mm: float
    image_width_px: int
    image_height_px: int


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
    scale_mm_per_pixel: Optional[float] = None
    is_scale_calibrated: bool = False
    created_at: datetime
    updated_at: datetime
