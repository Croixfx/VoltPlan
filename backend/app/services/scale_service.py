import math
import os
from typing import Tuple

from fastapi import HTTPException
from PIL import Image

from app.models.project import Project
from app.schemas.project import ScaleCalibrationRequest
from app.services.plan_storage import ensure_plan_on_disk

# Reference segments shorter than this (in pixels) give an unreliable scale.
MIN_REFERENCE_PIXELS = 20.0
# Sanity bounds for building plans (mm per pixel): 0.5 mm .. 200 mm per pixel.
MIN_MM_PER_PIXEL = 0.5
MAX_MM_PER_PIXEL = 200.0


def analysis_image_path(project: Project) -> str:
    """The image the vision/geometry pipeline works on (display PNG when available)."""
    ensure_plan_on_disk(project)
    project_dir = os.path.dirname(project.floor_plan_path)
    display = os.path.join(project_dir, "display_plan.png")
    return display if os.path.exists(display) else project.floor_plan_path


def image_size(path: str) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size  # (width, height)


class ScaleService:
    @staticmethod
    def calibrate(project: Project, req: ScaleCalibrationRequest) -> dict:
        """Derive mm-per-pixel from two points and the real distance between them."""
        if not ensure_plan_on_disk(project):
            raise HTTPException(status_code=400, detail="Upload a floor plan before calibrating its scale.")

        width, height = image_size(analysis_image_path(project))
        dx = (req.point_a.x_ratio - req.point_b.x_ratio) * width
        dy = (req.point_a.y_ratio - req.point_b.y_ratio) * height
        ref_px = math.hypot(dx, dy)
        if ref_px < MIN_REFERENCE_PIXELS:
            raise HTTPException(
                status_code=422,
                detail=f"Reference points are too close together ({ref_px:.1f} px). Pick two points further apart.",
            )

        mm_per_px = req.real_distance_mm / ref_px
        if not (MIN_MM_PER_PIXEL <= mm_per_px <= MAX_MM_PER_PIXEL):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Calibrated scale of {mm_per_px:.2f} mm/px is implausible for a building plan. "
                    "Check the real distance (in millimetres) and the selected points."
                ),
            )

        calibration = {
            "point_a": req.point_a.model_dump(),
            "point_b": req.point_b.model_dump(),
            "real_distance_mm": req.real_distance_mm,
            "reference_pixels": round(ref_px, 3),
            "image_width_px": width,
            "image_height_px": height,
        }
        return {"scale_mm_per_pixel": mm_per_px, "calibration": calibration}
