from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.electrical import Circuit, ElectricalPoint
from app.services.electrical_calculations import CapacityOptions, calculate

router = APIRouter(prefix="/projects", tags=["Calculations"])


@router.get("/{project_id}/calculations")
def get_calculations(
    project_id: str,
    method: str = "B2",
    ambient_c: int = 30,
    grouped_circuits: int = 1,
    db: Session = Depends(get_db),
):
    """Voltage drop, cable current-carrying capacity and maximum demand for the current design.
    Recomputed on every call from the stored design, so manual edits are always reflected.

    `method` (A2, B2, C), `ambient_c` and `grouped_circuits` set the installation conditions used for the
    cable capacity check; the defaults are B2, 30 C and no bunching."""
    try:
        capacity_options = CapacityOptions(method=method.upper(), ambient_c=ambient_c, grouped_circuits=grouped_circuits)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

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

    result = calculate(circuits, points, project.building_type, scale_verified, capacity_options)
    result["project_id"] = project_id
    result["geometry_needs_regeneration"] = bool(analysis.geometry_dirty)
    return result
