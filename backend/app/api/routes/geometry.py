from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.analysis import _build_analysis_response
from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.analysis import AnalysisResultResponse
from app.schemas.geometry import DoorCreate, DoorUpdate, GeometryResponse, RoomCreate, RoomUpdate
from app.services.geometry_edit_service import GeometryEditError, GeometryEditService
from app.services.plan_analysis_service import PlanAnalysisService

router = APIRouter(prefix="/projects/{project_id}", tags=["Rooms & Doors"])


def _call(fn, *args):
    try:
        return fn(*args)
    except GeometryEditError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/geometry", response_model=GeometryResponse)
def get_geometry(project_id: str, db: Session = Depends(get_db)):
    """Detected / corrected rooms and doors with the current geometry-check results."""
    return _call(GeometryEditService.get_geometry, project_id, db)


@router.post("/rooms", response_model=GeometryResponse, status_code=201)
def add_room(project_id: str, data: RoomCreate, db: Session = Depends(get_db)):
    return _call(GeometryEditService.add_room, project_id, data, db)


@router.patch("/rooms/{room_id}", response_model=GeometryResponse)
def update_room(project_id: str, room_id: str, data: RoomUpdate, db: Session = Depends(get_db)):
    """Rename a room and/or change its boundary. Doors stay on their wall."""
    return _call(GeometryEditService.update_room, project_id, room_id, data, db)


@router.delete("/rooms/{room_id}", response_model=GeometryResponse)
def delete_room(project_id: str, room_id: str, db: Session = Depends(get_db)):
    """Delete a room together with its doors and fixtures."""
    return _call(GeometryEditService.delete_room, project_id, room_id, db)


@router.post("/doors", response_model=GeometryResponse, status_code=201)
def add_door(project_id: str, data: DoorCreate, db: Session = Depends(get_db)):
    return _call(GeometryEditService.add_door, project_id, data, db)


@router.patch("/doors/{feature_id}", response_model=GeometryResponse)
def update_door(project_id: str, feature_id: str, data: DoorUpdate, db: Session = Depends(get_db)):
    return _call(GeometryEditService.update_door, project_id, feature_id, data, db)


@router.delete("/doors/{feature_id}", response_model=GeometryResponse)
def delete_door(project_id: str, feature_id: str, db: Session = Depends(get_db)):
    return _call(GeometryEditService.delete_door, project_id, feature_id, db)


@router.post("/regenerate", response_model=AnalysisResultResponse)
def regenerate(project_id: str, db: Session = Depends(get_db)):
    """Rebuild equipment, circuits, BOQ and cost from the stored (corrected) rooms and doors.
    Runs the geometry checks first and stops with 422 + the issue list if any fail."""
    analysis = PlanAnalysisService.regenerate(project_id, db)
    project = db.query(Project).filter(Project.id == project_id).first()
    return _build_analysis_response(project, analysis)
