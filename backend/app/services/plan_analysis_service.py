import os
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.logging import logger
from app.models.project import Project
from app.models.analysis import Analysis
from app.services.vision_service import VisionService
from app.services.electrical_engine import ElectricalEngine
from app.services.circuit_engine import CircuitEngine
from app.services.boq_engine import BoqEngine
from app.services.cost_service import CostService


class PlanAnalysisService:
    """
    End-to-end floor plan analysis orchestrator.
    Transitions through real pipeline steps:
    preparing_document -> analyzing_plan -> generating_recommendations -> generating_boq -> completed
    """

    @staticmethod
    async def run_pipeline(project_id: str, db: Session) -> Analysis:
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
        if not analysis:
            analysis = Analysis(project_id=project_id)
            db.add(analysis)

        analysis.status = "processing"
        analysis.current_step = "preparing_document"
        analysis.error_message = None
        project.status = "processing"
        db.commit()

        try:
            # Step 1: Document preparation
            logger.info(f"[{project_id}] Step 1: Preparing architectural document: {project.floor_plan_name}")
            # The display image is stored in project upload dir as display_plan.png
            project_dir = os.path.dirname(project.floor_plan_path)
            display_plan_path = os.path.join(project_dir, "display_plan.png")
            analysis_image_path = display_plan_path if os.path.exists(display_plan_path) else project.floor_plan_path

            # Step 2: AI Vision Floor Plan Analysis
            logger.info(f"[{project_id}] Step 2: Analyzing floor plan via Vision AI")
            analysis.current_step = "analyzing_plan"
            db.commit()

            vision_result = await VisionService.analyze_floor_plan(
                image_path=analysis_image_path,
                building_type=project.building_type,
                standard=project.standard,
            )

            analysis.rooms_data = [r.model_dump() for r in vision_result.rooms]
            analysis.architectural_features_data = [f.model_dump() for f in vision_result.architectural_features]
            analysis.observations = vision_result.observations
            analysis.warnings = vision_result.warnings
            db.commit()

            # Step 2.5: Canonical Building Geometry Model (Phase 1)
            logger.info(f"[{project_id}] Step 2.5: Establishing Canonical Building Geometry Model")
            img_w, img_h = 1200, 900
            try:
                import cv2
                img_mat = cv2.imread(analysis_image_path)
                if img_mat is not None:
                    img_h, img_w = img_mat.shape[:2]
            except Exception:
                pass

            from app.services.canonical_geometry_service import CanonicalGeometryService
            canonical_plan = CanonicalGeometryService.build_canonical_floor_plan(
                rooms=vision_result.rooms,
                features=vision_result.architectural_features,
                image_path=analysis_image_path,
                pixel_width=img_w,
                pixel_height=img_h,
                scale_mm_per_pixel=None,
                is_scale_verified=False,
                building_type=project.building_type,
                standard_name=project.standard,
                source_file_name=project.floor_plan_name or "floor_plan.png",
            )
            analysis.canonical_geometry_data = canonical_plan.model_dump()
            if not canonical_plan.is_scale_verified:
                scale_warn = "Plan scale is uncalibrated. Physical coordinates and areas are heuristic architectural estimates."
                if scale_warn not in analysis.warnings:
                    analysis.warnings.append(scale_warn)
            db.commit()

            # Step 3: Deterministic Electrical Engineering Engine
            logger.info(f"[{project_id}] Step 3: Generating deterministic electrical recommendations ({project.standard})")
            analysis.current_step = "generating_recommendations"
            db.commit()

            raw_points = ElectricalEngine.generate_recommendations(
                rooms=vision_result.rooms,
                architectural_features=vision_result.architectural_features,
                building_type=project.building_type,
                standard_name=project.standard,
                image_path=analysis_image_path,
            )

            # Step 4: Circuit Schedule Engine & Wiring Arcs
            logger.info(f"[{project_id}] Step 4: Sizing and grouping circuits & generating CAD Bézier wiring arcs")
            updated_points, circuits = CircuitEngine.generate_circuits(
                points=raw_points,
                standard_name=project.standard,
            )
            wiring_arcs = CircuitEngine.generate_wiring_arcs(points=updated_points)

            analysis.electrical_points_data = [p.model_dump() for p in updated_points]
            analysis.circuits_data = [c.model_dump() for c in circuits]
            analysis.wiring_arcs_data = [a.model_dump() for a in wiring_arcs]
            db.commit()

            # Step 5: BOQ & Cost Estimation Engine
            logger.info(f"[{project_id}] Step 5: Generating dynamic BOQ & Cost Estimation (RWF)")
            analysis.current_step = "generating_boq"
            db.commit()

            boq_items, materials_subtotal = BoqEngine.generate_boq(
                rooms=vision_result.rooms,
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
            project.status = "analyzed"
            db.commit()
            db.refresh(analysis)
            db.refresh(project)

            logger.info(f"[{project_id}] End-to-end analysis pipeline completed successfully.")
            return analysis

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
