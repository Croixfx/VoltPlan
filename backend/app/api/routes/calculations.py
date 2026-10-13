from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.electrical import Circuit, ElectricalPoint
from app.services.electrical_calculations import calculate

router = APIRouter(prefix="/projects", tags=["Calculations"])


@router.get("/{project_id}/calculations")
def get_calculations(project_id: str, db: Session = Depends(get_db)):
    """Voltage drop per circuit and maximum demand for the current design.
    Recomputed on every call from the stored design, so manual edits are always reflected."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis or analysis.status != "completed" or not analysis.circuits_data:
        raise HTTPException(status_code=409, detail="Run the analysis before calculating voltage drop and demand.")

    points = [ElectricalPoint(**p) for p in (analysis.electrical_points_data or [])]
    circuits = [Circuit(**c) for c in (analysis.circuits_data or [])]
    transform = (analysis.canonical_geometry_data or {}).get("transform", {})
    scale_verified = bool(transform.get("is_scale_verified")) and project.is_scale_calibrated

    result = calculate(circuits, points, project.building_type, scale_verified)
    result["project_id"] = project_id
    result["geometry_needs_regeneration"] = bool(analysis.geometry_dirty)
    return result
