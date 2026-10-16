from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.project import Project
from app.schemas.project import ScaleCalibrationRequest, ScaleCalibrationResponse
from app.services.plan_storage import ensure_plan_on_disk
from app.services.scale_service import ScaleService
from app.services.scale_suggestion_service import suggest_scale
from app.services.vision_service import VisionProviderError

router = APIRouter(prefix="/projects", tags=["Scale"])


def _get_project(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _to_response(project: Project) -> ScaleCalibrationResponse:
    cal = project.scale_calibration or {}
    return ScaleCalibrationResponse(
        project_id=project.id,
        scale_mm_per_pixel=project.scale_mm_per_pixel,
        reference_pixels=cal.get("reference_pixels", 0.0),
        real_distance_mm=cal.get("real_distance_mm", 0.0),
        image_width_px=cal.get("image_width_px", 0),
        image_height_px=cal.get("image_height_px", 0),
    )


@router.put("/{project_id}/scale", response_model=ScaleCalibrationResponse)
def calibrate_scale(project_id: str, data: ScaleCalibrationRequest, db: Session = Depends(get_db)):
    """Calibrate plan scale from two points on the plan and the real distance between them."""
    project = _get_project(project_id, db)
    result = ScaleService.calibrate(project, data)
    project.scale_mm_per_pixel = result["scale_mm_per_pixel"]
    project.scale_calibration = result["calibration"]
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.post("/{project_id}/scale/suggest")
async def suggest_project_scale(project_id: str, db: Session = Depends(get_db)):
    """Reads a dimension label off the drawing and proposes a calibration. Nothing is saved: the user checks the
    two points and the distance on the plan, then confirms with PUT /scale."""
    project = _get_project(project_id, db)
    if not ensure_plan_on_disk(project):
        raise HTTPException(status_code=400, detail="Upload a floor plan before calibrating its scale.")
    try:
        return await suggest_scale(project)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except VisionProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{project_id}/scale", response_model=ScaleCalibrationResponse)
def get_scale(project_id: str, db: Session = Depends(get_db)):
    project = _get_project(project_id, db)
    if not project.is_scale_calibrated:
        raise HTTPException(status_code=404, detail="Scale has not been calibrated for this project.")
    return _to_response(project)


@router.delete("/{project_id}/scale", status_code=204)
def clear_scale(project_id: str, db: Session = Depends(get_db)):
    project = _get_project(project_id, db)
    project.scale_mm_per_pixel = None
    project.scale_calibration = None
    db.commit()
    return None
