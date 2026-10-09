import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.db.database import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        name=data.name.strip(),
        client=data.client.strip(),
        building_type=data.building_type,
        location=data.location.strip(),
        standard=data.standard,
        notes=data.notes.strip() if data.notes else "",
        status="created",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    q: Optional[str] = Query(None, description="Search query by name, client, or location"),
    db: Session = Depends(get_db),
):
    query = db.query(Project)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Project.name.ilike(search),
                Project.client.ilike(search),
                Project.location.ilike(search),
            )
        )
    return query.order_by(desc(Project.created_at)).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if project.floor_plan_path:
        project_dir = os.path.dirname(project.floor_plan_path)
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir, ignore_errors=True)

    db.delete(project)
    db.commit()
    return None
