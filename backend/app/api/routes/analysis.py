from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.project import Project
from app.models.analysis import Analysis
from app.schemas.analysis import AnalysisResultResponse, AnalysisStatusResponse
from app.schemas.boq import BOQResponse, CostEstimateResponse, BOQItem
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.schemas.electrical import ElectricalPoint, Circuit, WiringArc
from app.services.plan_analysis_service import PlanAnalysisService

router = APIRouter(prefix="/projects", tags=["Analysis"])


@router.post("/{project_id}/analyze", response_model=AnalysisResultResponse)
async def trigger_analysis(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = await PlanAnalysisService.run_pipeline(project_id, db)
    return _build_analysis_response(project, analysis)


@router.get("/{project_id}/analysis", response_model=AnalysisResultResponse)
def get_analysis_result(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis performed for this project yet.")

    return _build_analysis_response(project, analysis)


@router.get("/{project_id}/analysis/status", response_model=AnalysisStatusResponse)
def get_analysis_status(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis:
        return AnalysisStatusResponse(
            project_id=project_id,
            status=project.status,
            current_step="uploading" if not project.floor_plan_path else "ready_for_analysis",
            error_message=None,
            updated_at=project.updated_at,
        )

    return AnalysisStatusResponse(
        project_id=project_id,
        status=analysis.status,
        current_step=analysis.current_step,
        error_message=analysis.error_message,
        updated_at=analysis.updated_at,
    )


@router.get("/{project_id}/boq", response_model=BOQResponse)
def get_project_boq(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis or not analysis.boq_items_data:
        raise HTTPException(status_code=404, detail="BOQ not available. Run analysis on the project floor plan first.")

    boq_items = [BOQItem(**item) for item in analysis.boq_items_data]
    subtotal = sum(i.total_price_rwf or 0.0 for i in boq_items)

    return BOQResponse(
        project_id=project_id,
        items=boq_items,
        materials_subtotal_rwf=subtotal,
    )


@router.get("/{project_id}/cost-estimate", response_model=CostEstimateResponse)
def get_project_cost_estimate(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
    if not analysis or not analysis.cost_estimate_data:
        raise HTTPException(status_code=404, detail="Cost estimate not available. Run analysis on the project first.")

    return CostEstimateResponse(**analysis.cost_estimate_data)


def _build_analysis_response(project: Project, analysis: Analysis) -> AnalysisResultResponse:
    rooms = [RoomObservation(**r) for r in (analysis.rooms_data or [])]
    features = [ArchitecturalFeature(**f) for f in (analysis.architectural_features_data or [])]
    electrical_points = [ElectricalPoint(**p) for p in (analysis.electrical_points_data or [])]
    circuits = [Circuit(**c) for c in (analysis.circuits_data or [])]
    wiring_arcs = [WiringArc(**a) for a in (analysis.wiring_arcs_data or [])]
    boq_items = [BOQItem(**b) for b in (analysis.boq_items_data or [])]

    cost_estimate = None
    if analysis.cost_estimate_data:
        cost_estimate = CostEstimateResponse(**analysis.cost_estimate_data)

    return AnalysisResultResponse(
        project_id=project.id,
        status=analysis.status,
        current_step=analysis.current_step,
        standard_applied=project.standard,
        rooms=rooms,
        architectural_features=features,
        observations=analysis.observations or [],
        warnings=analysis.warnings or [],
        electrical_points=electrical_points,
        circuits=circuits,
        wiring_arcs=wiring_arcs,
        boq_items=boq_items,
        cost_estimate=cost_estimate,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )
