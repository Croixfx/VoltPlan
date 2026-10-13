"""
Manual editing of electrical points.

The backend is the source of truth: every add / move / delete is validated
against the detected rooms and the equipment catalog, then circuits, wiring
arcs, BOQ and cost are regenerated from the full point list.

User-placed and user-moved points are flagged `is_manual` and are carried over
when the analysis pipeline is re-run (see `merge_manual_points`).
"""
import math
import re
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.catalog import EquipmentSpec, get_equipment
from app.core.logging import logger
from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.canonical_geometry import CanonicalFloorPlan
from app.schemas.electrical import ElectricalPoint, PointCreate, PointUpdate
from app.schemas.floor_plan import RoomObservation
from app.services.boq_engine import BoqEngine
from app.services.circuit_engine import CircuitEngine
from app.services.coordinate_transform import CoordinateTransformEngine
from app.services.cost_service import CostService

# A regenerated auto point this close (normalized) to a moved point's original
# position is considered the same point and is dropped on re-run.
_REPLACE_RADIUS = 0.12


class PointEditError(Exception):
    """A rejected edit. `status_code` maps directly onto the HTTP response."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _room_area(room: RoomObservation) -> float:
    b = room.bounds
    return (b[2] - b[0]) * (b[3] - b[1])


def find_room(rooms: List[RoomObservation], x: float, y: float) -> Optional[RoomObservation]:
    """Smallest room whose bounds contain (x, y)."""
    containing = [
        r for r in rooms
        if r.bounds and len(r.bounds) >= 4
        and r.bounds[0] <= x <= r.bounds[2] and r.bounds[1] <= y <= r.bounds[3]
    ]
    return min(containing, key=_room_area) if containing else None


def _next_point_id(points: List[ElectricalPoint]) -> str:
    highest = 0
    for p in points:
        match = re.fullmatch(r"pt_(\d+)", p.id)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"pt_{highest + 1:03d}"


def _millimetres(analysis_geometry: Optional[dict], x: float, y: float) -> Tuple[Optional[float], Optional[float], bool]:
    if not analysis_geometry:
        return None, None, False
    try:
        plan = CanonicalFloorPlan(**analysis_geometry)
        return _plan_mm(plan, x, y)
    except Exception:
        return None, None, False


def _plan_mm(plan: CanonicalFloorPlan, x: float, y: float) -> Tuple[Optional[float], Optional[float], bool]:
    pt = CoordinateTransformEngine.normalized_to_canonical(x, y, plan.transform)
    return round(pt.x, 1), round(pt.y, 1), plan.transform.is_scale_verified


class PointEditService:
    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _context(project_id: str, db: Session) -> Tuple[Project, Analysis, List[ElectricalPoint], List[RoomObservation]]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise PointEditError("Project not found.", 404)
        analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
        if not analysis or analysis.status != "completed":
            raise PointEditError("Run the analysis before editing electrical points.", 409)
        points = [ElectricalPoint(**p) for p in (analysis.electrical_points_data or [])]
        rooms = [RoomObservation(**r) for r in (analysis.rooms_data or [])]
        return project, analysis, points, rooms

    @staticmethod
    def _validate_placement(spec: EquipmentSpec, rooms: List[RoomObservation], x: float, y: float) -> RoomObservation:
        room = find_room(rooms, x, y)
        if room is None:
            raise PointEditError(
                f"Position ({x:.3f}, {y:.3f}) is outside every detected room. "
                "Place the point inside a room."
            )
        reason = spec.check_room(room.name, getattr(room, "room_type", "") or "")
        if reason:
            raise PointEditError(reason)
        return room

    @staticmethod
    def _recompute(project: Project, analysis: Analysis, points: List[ElectricalPoint], rooms: List[RoomObservation], db: Session) -> Analysis:
        """Regenerate circuits, wiring arcs, BOQ and cost from the full point list."""
        for p in points:
            p.circuit_id = None
        updated_points, circuits = CircuitEngine.generate_circuits(points, standard_name=project.standard)
        arcs = CircuitEngine.generate_wiring_arcs(points=updated_points)
        boq_items, materials_subtotal = BoqEngine.generate_boq(rooms=rooms, points=updated_points, circuits=circuits)
        cost = CostService.calculate_cost_estimate(project_id=project.id, materials_cost_rwf=materials_subtotal)

        # Assign new lists so SQLAlchemy detects the JSON column changes.
        analysis.electrical_points_data = [p.model_dump() for p in updated_points]
        analysis.circuits_data = [c.model_dump() for c in circuits]
        analysis.wiring_arcs_data = [a.model_dump() for a in arcs]
        analysis.boq_items_data = [i.model_dump() for i in boq_items]
        analysis.cost_estimate_data = cost.model_dump()
        db.commit()
        db.refresh(analysis)
        return analysis

    # --------------------------------------------------------------------- API
    @classmethod
    def add_point(cls, project_id: str, data: PointCreate, db: Session) -> Analysis:
        project, analysis, points, rooms = cls._context(project_id, db)

        spec = get_equipment(data.type)
        if spec is None:
            raise PointEditError(f"Unknown equipment type '{data.type}'.")
        room = cls._validate_placement(spec, rooms, data.x_ratio, data.y_ratio)
        if spec.type_id == "distribution_board" and any(p.type == "distribution_board" for p in points):
            raise PointEditError("The project already has a distribution board.", 409)

        x_mm, y_mm, scale_verified = _millimetres(analysis.canonical_geometry_data, data.x_ratio, data.y_ratio)
        points.append(ElectricalPoint(
            id=_next_point_id(points),
            room_id=room.id,
            room_name=room.name,
            type=spec.type_id,
            quantity=data.quantity,
            power_rating_w=spec.default_power_w,
            x_ratio=round(data.x_ratio, 3),
            y_ratio=round(data.y_ratio, 3),
            x_mm=x_mm,
            y_mm=y_mm,
            coordinate_system="canonical_mm_and_normalized_ratio" if x_mm is not None else "normalized_ratio",
            placement_rule="Manual placement",
            geometry_used="manual",
            is_scale_verified=scale_verified,
            placement_status="manual",
            reasoning=f"{spec.name} placed manually by the user in {room.name}.",
            recommended_cable=spec.cable,
            recommended_protection=spec.protection,
            rule_reference=spec.rule_reference,
            status="RECOMMENDED",
            review_notes="Placed manually. The engineer must verify clearances and compliance on site.",
            is_manual=True,
            manual_origin="added",
        ))
        logger.info(f"[{project_id}] Manual point added: {spec.type_id} in {room.name}")
        return cls._recompute(project, analysis, points, rooms, db)

    @classmethod
    def update_point(cls, project_id: str, point_id: str, data: PointUpdate, db: Session) -> Analysis:
        project, analysis, points, rooms = cls._context(project_id, db)
        point = next((p for p in points if p.id == point_id), None)
        if point is None:
            raise PointEditError(f"Electrical point '{point_id}' not found.", 404)

        moving = data.x_ratio is not None or data.y_ratio is not None
        if moving and (data.x_ratio is None or data.y_ratio is None):
            raise PointEditError("Provide both x_ratio and y_ratio to move a point.")

        if moving:
            spec = get_equipment(point.type)
            new_room = find_room(rooms, data.x_ratio, data.y_ratio)
            if new_room is None:
                raise PointEditError(
                    f"Position ({data.x_ratio:.3f}, {data.y_ratio:.3f}) is outside every detected room. "
                    "Move the point inside a room."
                )
            if spec is not None:
                reason = spec.check_room(new_room.name, getattr(new_room, "room_type", "") or "")
                if reason:
                    raise PointEditError(reason)

            if not point.is_manual:
                point.original_x_ratio = point.x_ratio
                point.original_y_ratio = point.y_ratio
                point.manual_origin = "moved"
            point.is_manual = True
            point.x_ratio = round(data.x_ratio, 3)
            point.y_ratio = round(data.y_ratio, 3)
            point.room_id = new_room.id
            point.room_name = new_room.name
            point.x_mm, point.y_mm, point.is_scale_verified = _millimetres(
                analysis.canonical_geometry_data, point.x_ratio, point.y_ratio
            )
            point.placement_rule = "Manual placement"
            point.geometry_used = "manual"
            point.placement_status = "manual"
            point.nearby_wall_id = point.nearby_door_id = point.nearby_obstacle_id = None
            point.clearance_envelope_applied = None
            point.reasoning = f"Position set manually by the user in {new_room.name}."
            point.review_notes = "Position set manually. The engineer must verify clearances and compliance on site."

        if data.quantity is not None:
            point.quantity = data.quantity
            if not point.is_manual:
                point.is_manual = True
                point.manual_origin = "moved"
                point.original_x_ratio = point.x_ratio
                point.original_y_ratio = point.y_ratio
                point.placement_status = "manual"

        logger.info(f"[{project_id}] Manual point updated: {point_id}")
        return cls._recompute(project, analysis, points, rooms, db)

    @classmethod
    def delete_point(cls, project_id: str, point_id: str, db: Session) -> Analysis:
        project, analysis, points, rooms = cls._context(project_id, db)
        remaining = [p for p in points if p.id != point_id]
        if len(remaining) == len(points):
            raise PointEditError(f"Electrical point '{point_id}' not found.", 404)
        logger.info(f"[{project_id}] Point deleted: {point_id}")
        return cls._recompute(project, analysis, remaining, rooms, db)

    # ------------------------------------------------------- analysis re-runs
    @staticmethod
    def merge_manual_points(
        regenerated: List[ElectricalPoint],
        previous_points_data: Optional[List[dict]],
        rooms: List[RoomObservation],
        canonical_plan: Optional[CanonicalFloorPlan] = None,
    ) -> Tuple[List[ElectricalPoint], List[str]]:
        """Carry user-placed / user-moved points over into freshly generated ones.

        A moved point replaces its auto-generated counterpart (nearest regenerated
        point of the same type to the original position). A manual point is
        dropped, with a warning, if it no longer lies in a valid room.
        """
        warnings: List[str] = []
        previous: List[ElectricalPoint] = []
        for raw in previous_points_data or []:
            if not raw.get("is_manual"):
                continue
            try:
                previous.append(ElectricalPoint(**raw))
            except Exception:
                continue
        if not previous:
            return regenerated, warnings

        points = list(regenerated)
        for manual in previous:
            spec = get_equipment(manual.type)
            room = find_room(rooms, manual.x_ratio, manual.y_ratio)
            if room is None:
                warnings.append(
                    f"Manual {manual.type.replace('_', ' ')} '{manual.id}' was dropped: it is no longer inside a detected room."
                )
                continue
            reason = spec.check_room(room.name, getattr(room, "room_type", "") or "") if spec else None
            if reason:
                warnings.append(f"Manual {manual.type.replace('_', ' ')} '{manual.id}' was dropped: {reason}")
                continue

            if manual.manual_origin == "moved" and manual.original_x_ratio is not None and manual.original_y_ratio is not None:
                candidates = [p for p in points if not p.is_manual and p.type == manual.type and p.x_ratio is not None]
                if candidates:
                    nearest = min(
                        candidates,
                        key=lambda p: math.hypot(p.x_ratio - manual.original_x_ratio, p.y_ratio - manual.original_y_ratio),
                    )
                    dist = math.hypot(nearest.x_ratio - manual.original_x_ratio, nearest.y_ratio - manual.original_y_ratio)
                    if dist <= _REPLACE_RADIUS:
                        points.remove(nearest)

            manual.id = _next_point_id(points)
            manual.room_id = room.id
            manual.room_name = room.name
            if canonical_plan is not None:
                manual.x_mm, manual.y_mm, manual.is_scale_verified = _plan_mm(canonical_plan, manual.x_ratio, manual.y_ratio)
            manual.circuit_id = None
            points.append(manual)

        kept = sum(1 for p in points if p.is_manual)
        if kept:
            warnings.append(f"{kept} manually placed or moved point(s) were preserved from the previous design.")
        return points, warnings
