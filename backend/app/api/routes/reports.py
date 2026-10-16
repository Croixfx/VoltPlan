import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.project import Project
from app.services.report_service import build_report_pdf

router = APIRouter(prefix="/projects", tags=["Reports"])


@router.get("/{project_id}/report.pdf")
def download_report(project_id: str, db: Session = Depends(get_db)):
    """The client report: plan with symbols, equipment and circuit schedules, calculations, BOQ and cost."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis or analysis.status != "completed" or not analysis.circuits_data:
        raise HTTPException(status_code=409, detail="Run the analysis before creating the report.")

    pdf = build_report_pdf(project, analysis)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", project.name).strip("_") or "project"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="VoltPlan_{safe}_Report.pdf"'},
    )
