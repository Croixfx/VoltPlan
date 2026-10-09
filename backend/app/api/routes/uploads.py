import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.project import Project
from app.schemas.project import ProjectResponse
from app.services.document_service import DocumentService
from app.core.logging import logger

router = APIRouter(prefix="/projects", tags=["Uploads"])


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

    if not project.floor_plan_path or not os.path.exists(project.floor_plan_path):
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
