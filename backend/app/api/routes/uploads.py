import hashlib
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.plan_file import PlanFile
from app.models.project import Project
from app.schemas.project import ProjectResponse
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.document_service import DocumentService
from app.services.plan_storage import ensure_plan_on_disk, store_plan
from app.core.logging import logger

router = APIRouter(prefix="/projects", tags=["Uploads"])


def _owned_by(db: Session, project_id: str, user: User) -> bool:
    return db.query(Project.owner_id).filter(Project.id == project_id).scalar() == user.id


@router.post("/plan-match", response_model=Optional[ProjectResponse])
async def find_matching_plan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """Find one of the signed-in user's projects that already stores this exact floor-plan file."""
    DocumentService.validate_file(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB.")

    digest = hashlib.sha256(content).hexdigest()
    match = (
        db.query(PlanFile)
        .join(Project, Project.id == PlanFile.project_id)
        .filter(PlanFile.original_sha256 == digest)
        .filter(Project.owner_id == user.id if user is not None else True)
        .order_by(Project.updated_at.desc())
        .first()
    )
    if match is None:
        # Backfill hashes for plans uploaded before duplicate detection was introduced.
        backfilled = False
        for stored in db.query(PlanFile).filter(PlanFile.original_sha256.is_(None)).all():
            stored_digest = hashlib.sha256(stored.original_bytes).hexdigest()
            stored.original_sha256 = stored_digest
            backfilled = True
            if stored_digest == digest and (user is None or _owned_by(db, stored.project_id, user)):
                match = stored
        if backfilled:
            db.commit()
    if match is None:
        return None

    return db.query(Project).filter(Project.id == match.project_id).first()


@router.post("/{project_id}/plan", response_model=ProjectResponse)
async def upload_floor_plan(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    logger.info(f"Received file upload for project {project_id}: {file.filename}")
    save_result = await DocumentService.save_uploaded_file(file, project_id)

    project.floor_plan_name = save_result["filename"]
    project.floor_plan_path = save_result["raw_file_path"]
    project.floor_plan_content_type = save_result["content_type"]
    project.floor_plan_size = save_result["size"]
    project.status = "uploaded"
    store_plan(db, project)  # the disk is wiped on restart; this copy survives
    # A new drawing invalidates any previous scale calibration ...
    project.scale_mm_per_pixel = None
    project.scale_calibration = None
    # ... and the room / door corrections made on the old drawing, which would otherwise block re-analysis forever
    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if analysis:
        analysis.status = "pending"
        analysis.current_step = "uploading"
        analysis.error_message = None
        analysis.rooms_data = []
        analysis.architectural_features_data = []
        analysis.observations = []
        analysis.warnings = []
        analysis.canonical_geometry_data = None
        analysis.geometry_reviewed = False
        analysis.geometry_dirty = False
        analysis.geometry_issues_data = []
        analysis.electrical_points_data = []
        analysis.circuits_data = []
        analysis.wiring_arcs_data = []
        analysis.boq_items_data = []
        analysis.cost_estimate_data = {}

    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/plan/file")
def get_floor_plan_file(
    project_id: str,
    format: str = "display",  # "display" for normalized PNG, "original" for original
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if not ensure_plan_on_disk(project, db):
        raise HTTPException(status_code=404, detail="No floor plan file found for this project.")

    project_dir = os.path.dirname(project.floor_plan_path)
    display_image_path = os.path.join(project_dir, "display_plan.png")

    if format == "display" and os.path.exists(display_image_path):
        return FileResponse(
            display_image_path,
            media_type="image/png",
            filename=f"{project.name}_display.png",
        )

    return FileResponse(
        project.floor_plan_path,
        media_type=project.floor_plan_content_type or "application/octet-stream",
        filename=project.floor_plan_name,
    )
