import os
from typing import List, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.logging import logger
from app.models.project import Project
from app.models.analysis import Analysis
from app.core.config import settings
from app.schemas.canonical_geometry import ScaleStatus
from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation
from app.services.vision_service import VisionService, VisionProviderError
from app.services.electrical_engine import ElectricalEngine
from app.services.circuit_engine import CircuitEngine
from app.services.boq_engine import BoqEngine
from app.services.cost_service import CostService
from app.services.geometry_validator import GeometryIssue, GeometryValidator, has_errors, summarize
from app.services.point_edit_service import PointEditService


GEOMETRY_CORRECTED_CODE = "geometry_corrected"


def analysis_image_path_for(project: Project) -> str:
    """The image the pipeline works on (display PNG when available)."""
    project_dir = os.path.dirname(project.floor_plan_path)
    display = os.path.join(project_dir, "display_plan.png")
    return display if os.path.exists(display) else project.floor_plan_path


def image_size_px(path: str) -> Tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except Exception:
        return 1200, 900


def ensure_feature_ids(features: List[ArchitecturalFeature]) -> List[ArchitecturalFeature]:
    """Gives every feature a stable id (feat_001, ...) without changing existing ids."""
    used = {f.id for f in features if f.id}
    counter = 1
    for f in features:
        if f.id:
            continue
        while f"feat_{counter:03d}" in used:
            counter += 1
        f.id = f"feat_{counter:03d}"
        used.add(f.id)
    return features


def link_features_to_rooms(rooms: List[RoomObservation], features: List[ArchitecturalFeature]) -> None:
    """Fills `room_id` from the room name where it is missing and unambiguous."""
    by_name = {}
    for r in rooms:
        by_name.setdefault((r.name or "").strip().lower(), []).append(r)
    for f in features:
        if f.room_id:
            continue
        matches = by_name.get((f.room or "").strip().lower(), [])
        if len(matches) == 1:
            f.room_id = matches[0].id


def validate_geometry(
    project: Project,
    analysis: Analysis,
    rooms: List[RoomObservation],
    features: List[ArchitecturalFeature],
    image_path: str,
) -> List[GeometryIssue]:
    """Runs the pre-generation checks and stores the result on the analysis."""
    issues = GeometryValidator.validate(
        rooms,
        features,
        scale_mm_per_pixel=project.scale_mm_per_pixel,
        image_size_px=image_size_px(image_path),
    )
    analysis.geometry_issues_data = [i.model_dump() for i in issues]
    return issues


def geometry_failure(issues: List[GeometryIssue]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "message": summarize(issues) + " Fix the rooms / doors and generate again.",
            "issues": [i.model_dump() for i in issues],
        },
    )


class PlanAnalysisService:
    """
    End-to-end floor plan analysis orchestrator.
    Transitions through real pipeline steps:
    preparing_document -> analyzing_plan -> validating_geometry -> generating_recommendations
    -> generating_boq -> completed

    Equipment is only generated from geometry that passes GeometryValidator; a failing
    check stops the run and reports the problems instead of guessing.
    """

    @classmethod
    async def run_pipeline(cls, project_id: str, db: Session, reset_geometry: bool = False) -> Analysis:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")

        if not project.floor_plan_path or not os.path.exists(project.floor_plan_path):
            raise HTTPException(
                status_code=400,
                detail="No architectural floor plan uploaded for this project. Upload a plan first.",
            )

        # Get or create Analysis record
        analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
        if analysis and analysis.geometry_reviewed and not reset_geometry:
            raise HTTPException(
                status_code=409,
                detail={
                    # `code` lets the app offer the right buttons; `message` is for people and uses no API terms.
                    "code": GEOMETRY_CORRECTED_CODE,
                    "message": (
                        "You have corrected rooms or doors in this project. Rebuild the design from your "
                        "corrections, or read the plan again with AI (this discards your corrections)."
                    ),
                },
            )
        if not analysis:
            analysis = Analysis(project_id=project_id)
            db.add(analysis)
        if reset_geometry:
            analysis.geometry_reviewed = False

        # Manually placed / moved points from the previous run are re-applied after regeneration
        previous_points_data = list(analysis.electrical_points_data or [])

        analysis.status = "processing"
        analysis.current_step = "preparing_document"
        analysis.error_message = None
        project.status = "processing"
        db.commit()

        try:
            # Step 1: Document preparation
            logger.info(f"[{project_id}] Step 1: Preparing architectural document: {project.floor_plan_name}")
            analysis_image_path = analysis_image_path_for(project)

            # Step 2: AI Vision Floor Plan Analysis
            logger.info(f"[{project_id}] Step 2: Analyzing floor plan via Vision AI")
            analysis.current_step = "analyzing_plan"
            db.commit()

            vision_result = await VisionService.analyze_floor_plan(
                image_path=analysis_image_path,
                building_type=project.building_type,
                standard=project.standard,
            )

            rooms = vision_result.rooms
            features = ensure_feature_ids(vision_result.architectural_features)
            link_features_to_rooms(rooms, features)

            analysis.rooms_data = [r.model_dump() for r in rooms]
            analysis.architectural_features_data = [f.model_dump() for f in features]
            analysis.observations = vision_result.observations
            analysis.warnings = list(vision_result.warnings)
            analysis.geometry_dirty = False
            if settings.AI_PROVIDER.lower() == "mock":
                analysis.warnings.append(
                    "DEMO DATA: AI_PROVIDER is 'mock', so rooms and fixtures are NOT read from the uploaded drawing."
                )
            db.commit()

            # Geometry checks. Stop here (keeping the detected rooms/doors for the editor) on errors.
            analysis.current_step = "validating_geometry"
            issues = validate_geometry(project, analysis, rooms, features, analysis_image_path)
            if has_errors(issues):
                logger.warning(f"[{project_id}] Geometry validation failed: {summarize(issues)}")
                analysis.status = "failed"
                analysis.error_message = summarize(issues)
                project.status = "failed"
                db.commit()
                raise geometry_failure(issues)
            db.commit()

            return cls._generate_design(project, analysis, rooms, features, analysis_image_path, previous_points_data, db)

        except HTTPException:
            raise

        except VisionProviderError as e:
            logger.error(f"[{project_id}] Vision provider failed: {e}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            project.status = "failed"
            db.commit()
            raise HTTPException(status_code=502, detail=f"AI vision provider error: {e}")

        except Exception as e:
            logger.error(f"[{project_id}] Analysis pipeline failed: {e}", exc_info=True)
            analysis.status = "failed"
            analysis.error_message = str(e)
            project.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Analysis pipeline failed during step '{analysis.current_step}': {str(e)}",
            )

    @classmethod
    def regenerate(cls, project_id: str, db: Session) -> Analysis:
        """Rebuild geometry, equipment, circuits, BOQ and cost from the STORED rooms / doors
        (e.g. after the user corrected them) without calling the AI again."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
        if not analysis or not analysis.rooms_data:
            raise HTTPException(status_code=409, detail="Run the analysis first so rooms and doors are detected.")
        if not project.floor_plan_path or not os.path.exists(project.floor_plan_path):
            raise HTTPException(status_code=400, detail="The floor plan file for this project is missing.")

        rooms = [RoomObservation(**r) for r in analysis.rooms_data]
        features = ensure_feature_ids([ArchitecturalFeature(**f) for f in (analysis.architectural_features_data or [])])
        link_features_to_rooms(rooms, features)
        image_path = analysis_image_path_for(project)

        # Validate BEFORE touching any existing result: a failed check leaves the current design intact.
        issues = validate_geometry(project, analysis, rooms, features, image_path)
        if has_errors(issues):
            db.commit()
            raise geometry_failure(issues)

        previous_points_data = list(analysis.electrical_points_data or [])
        analysis.status = "processing"
        analysis.current_step = "generating_recommendations"
        analysis.error_message = None
        project.status = "processing"
        analysis.architectural_features_data = [f.model_dump() for f in features]
        db.commit()
        try:
            return cls._generate_design(project, analysis, rooms, features, image_path, previous_points_data, db)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{project_id}] Regeneration failed: {e}", exc_info=True)
            analysis.status = "failed"
            analysis.error_message = str(e)
            project.status = "failed"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Regeneration failed: {e}")

    @classmethod
    def _generate_design(
        cls,
        project: Project,
        analysis: Analysis,
        rooms: List[RoomObservation],
        features: List[ArchitecturalFeature],
        analysis_image_path: str,
        previous_points_data: List[dict],
        db: Session,
    ) -> Analysis:
        """Canonical geometry -> equipment -> circuits -> BOQ -> cost, from validated rooms / doors."""
        project_id = project.id

        # Canonical Building Geometry Model (Phase 1)
        logger.info(f"[{project_id}] Establishing Canonical Building Geometry Model")
        img_w, img_h = image_size_px(analysis_image_path)

        from app.services.canonical_geometry_service import CanonicalGeometryService
        canonical_plan = CanonicalGeometryService.build_canonical_floor_plan(
            rooms=rooms,
            features=features,
            image_path=analysis_image_path,
            pixel_width=img_w,
            pixel_height=img_h,
            scale_mm_per_pixel=project.scale_mm_per_pixel,
            is_scale_verified=project.is_scale_calibrated,
            scale_status=ScaleStatus.USER_CALIBRATED if project.is_scale_calibrated else ScaleStatus.UNSCALED,
            building_type=project.building_type,
            standard_name=project.standard,
            source_file_name=project.floor_plan_name or "floor_plan.png",
        )
        analysis.canonical_geometry_data = canonical_plan.model_dump()
        if not canonical_plan.is_scale_verified:
            scale_warn = "Plan scale is uncalibrated. Physical coordinates and areas are heuristic architectural estimates."
            if scale_warn not in analysis.warnings:
                analysis.warnings = [*analysis.warnings, scale_warn]
        if canonical_plan.provenance.unresolved_geometry:
            for unres in canonical_plan.provenance.unresolved_geometry:
                if unres not in analysis.warnings:
                    analysis.warnings = [*analysis.warnings, unres]
        # Non-blocking geometry findings are surfaced as warnings
        for issue in analysis.geometry_issues_data or []:
            if issue.get("severity") == "warning" and issue["message"] not in analysis.warnings:
                analysis.warnings = [*analysis.warnings, issue["message"]]
        db.commit()

        # Deterministic Electrical Engineering Engine
        logger.info(f"[{project_id}] Generating deterministic electrical recommendations ({project.standard})")
        analysis.current_step = "generating_recommendations"
        db.commit()

        raw_points = ElectricalEngine.generate_recommendations(
            rooms=rooms,
            architectural_features=features,
            building_type=project.building_type,
            standard_name=project.standard,
            image_path=analysis_image_path,
            canonical_plan=canonical_plan,
        )

        raw_points, manual_notes = PointEditService.merge_manual_points(
            regenerated=raw_points,
            previous_points_data=previous_points_data,
            rooms=rooms,
            canonical_plan=canonical_plan,
        )
        for note in manual_notes:
            if note not in analysis.warnings:
                analysis.warnings = [*analysis.warnings, note]

        # Circuit Schedule Engine & Wiring Arcs
        logger.info(f"[{project_id}] Sizing and grouping circuits & generating CAD Bézier wiring arcs")
        updated_points, circuits = CircuitEngine.generate_circuits(
            points=raw_points,
            standard_name=project.standard,
        )
        wiring_arcs = CircuitEngine.generate_wiring_arcs(points=updated_points)

        analysis.electrical_points_data = [p.model_dump() for p in updated_points]
        analysis.circuits_data = [c.model_dump() for c in circuits]
        analysis.wiring_arcs_data = [a.model_dump() for a in wiring_arcs]
        db.commit()

        # BOQ & Cost Estimation Engine
        logger.info(f"[{project_id}] Generating dynamic BOQ & Cost Estimation (RWF)")
        analysis.current_step = "generating_boq"
        db.commit()

        boq_items, materials_subtotal = BoqEngine.generate_boq(
            rooms=rooms,
            points=updated_points,
            circuits=circuits,
        )

        cost_estimate = CostService.calculate_cost_estimate(
            project_id=project_id,
            materials_cost_rwf=materials_subtotal,
        )

        analysis.boq_items_data = [i.model_dump() for i in boq_items]
        analysis.cost_estimate_data = cost_estimate.model_dump()

        # Pipeline Completion
        analysis.status = "completed"
        analysis.current_step = "completed"
        analysis.geometry_dirty = False
        project.status = "analyzed"
        db.commit()
        db.refresh(analysis)
        db.refresh(project)

        logger.info(f"[{project_id}] Design generation completed successfully.")
        return analysis
