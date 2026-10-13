from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.analysis import _build_analysis_response
from app.db.database import get_db
from app.models.project import Project
from app.schemas.analysis import AnalysisResultResponse
from app.schemas.electrical import PointCreate, PointUpdate
from app.services.point_edit_service import PointEditError, PointEditService

router = APIRouter(prefix="/projects/{project_id}/points", tags=["Electrical Points"])


def _respond(project_id: str, analysis, db: Session) -> AnalysisResultResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    return _build_analysis_response(project, analysis)


@router.post("", response_model=AnalysisResultResponse, status_code=201)
def add_point(project_id: str, data: PointCreate, db: Session = Depends(get_db)):
    """Place a catalog equipment point. Circuits, BOQ and cost are regenerated."""
    try:
        analysis = PointEditService.add_point(project_id, data, db)
    except PointEditError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return _respond(project_id, analysis, db)


@router.patch("/{point_id}", response_model=AnalysisResultResponse)
def update_point(project_id: str, point_id: str, data: PointUpdate, db: Session = Depends(get_db)):
    """Move a point and/or change its quantity. The point becomes manual."""
    try:
        analysis = PointEditService.update_point(project_id, point_id, data, db)
    except PointEditError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return _respond(project_id, analysis, db)


@router.delete("/{point_id}", response_model=AnalysisResultResponse)
def delete_point(project_id: str, point_id: str, db: Session = Depends(get_db)):
    try:
        analysis = PointEditService.delete_point(project_id, point_id, db)
    except PointEditError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return _respond(project_id, analysis, db)
