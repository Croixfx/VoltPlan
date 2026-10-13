"""
Manual correction of rooms and doors.

The AI's room boundaries, names and door positions are the source of most bad
equipment placement. This service lets a user fix them at the source. Edits are
stored on the analysis; equipment is rebuilt from them by
`PlanAnalysisService.regenerate` after the geometry checks pass.

Individual edits are rejected only when they are malformed (inverted bounds,
unknown room, impossible wall). Cross-entity problems such as overlapping rooms
or a door drifting off its wall are reported as issues and block *generation*,
not editing, so a layout can be repaired step by step.
"""
import math
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.project import Project
from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation
from app.schemas.geometry import DoorCreate, DoorUpdate, GeometryResponse, RoomCreate, RoomUpdate
from app.services.geometry_validator import WALLS, has_errors, wall_segment
from app.services.plan_analysis_service import (
    analysis_image_path_for,
    ensure_feature_ids,
    image_size_px,
    link_features_to_rooms,
    validate_geometry,
)

DEFAULT_DOOR_WIDTH_MM = 900.0
HEURISTIC_MM_PER_PIXEL = 16.93   # same nominal 1:100 @ 150 DPI estimate the canonical model uses when unscaled
SWING_DIRECTIONS = ("into_room", "out_of_room")
STRIKE_SIDES = {"north": ("east", "west"), "south": ("east", "west"), "east": ("north", "south"), "west": ("north", "south")}
DOOR_TYPES = ("door", "entrance")


class GeometryEditError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GeometryEditService:
    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _context(project_id: str, db: Session) -> Tuple[Project, Analysis, List[RoomObservation], List[ArchitecturalFeature]]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise GeometryEditError("Project not found.", 404)
        analysis = db.query(Analysis).filter(Analysis.project_id == project_id).first()
        if not analysis or not analysis.rooms_data:
            raise GeometryEditError("Run the analysis first so rooms and doors are detected.", 409)
        rooms = [RoomObservation(**r) for r in analysis.rooms_data]
        features = ensure_feature_ids([ArchitecturalFeature(**f) for f in (analysis.architectural_features_data or [])])
        link_features_to_rooms(rooms, features)
        return project, analysis, rooms, features

    @staticmethod
    def _image_path(project: Project) -> str:
        return analysis_image_path_for(project) if project.floor_plan_path else ""

    @classmethod
    def _response(cls, project: Project, analysis: Analysis, rooms, features, issues) -> GeometryResponse:
        return GeometryResponse(
            project_id=project.id,
            rooms=rooms,
            features=features,
            issues=issues,
            can_generate=not has_errors(issues),
            reviewed=bool(analysis.geometry_reviewed),
            needs_regeneration=bool(analysis.geometry_dirty),
            scale_calibrated=project.is_scale_calibrated,
        )

    @classmethod
    def _save(cls, project, analysis, rooms, features, db: Session, edited: bool = True) -> GeometryResponse:
        issues = validate_geometry(project, analysis, rooms, features, cls._image_path(project)) \
            if project.floor_plan_path else []
        analysis.rooms_data = [r.model_dump() for r in rooms]
        analysis.architectural_features_data = [f.model_dump() for f in features]
        if edited:
            analysis.geometry_reviewed = True
            analysis.geometry_dirty = True
        db.commit()
        db.refresh(analysis)
        return cls._response(project, analysis, rooms, features, issues)

    @staticmethod
    def _check_bounds(bounds: List[float]) -> List[float]:
        if len(bounds) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bounds):
            raise GeometryEditError("Room bounds must be four numbers [x1, y1, x2, y2].")
        x1, y1, x2, y2 = [round(float(v), 4) for v in bounds]
        if min(x1, y1, x2, y2) < 0.0 or max(x1, y1, x2, y2) > 1.0:
            raise GeometryEditError("Room bounds must stay inside the plan (0.0 - 1.0).")
        if x2 <= x1 or y2 <= y1:
            raise GeometryEditError("Room bounds must enclose an area: x2 > x1 and y2 > y1.")
        return [x1, y1, x2, y2]

    @staticmethod
    def _room_by_id(rooms: List[RoomObservation], room_id: str) -> RoomObservation:
        for r in rooms:
            if r.id == room_id:
                return r
        raise GeometryEditError(f"Room '{room_id}' not found.", 404)

    @staticmethod
    def _next_id(prefix: str, existing: List[Optional[str]]) -> str:
        used = {e for e in existing if e}
        n = 1
        while f"{prefix}{n}" in used:
            n += 1
        return f"{prefix}{n}"

    @staticmethod
    def _recompute_area(project: Project, room: RoomObservation, old_bounds: Optional[List[float]], image_path: str) -> None:
        w = room.bounds[2] - room.bounds[0]
        h = room.bounds[3] - room.bounds[1]
        room.is_rectangular_approximation = True
        room.is_area_verified = False
        if project.is_scale_calibrated and image_path:
            img_w, img_h = image_size_px(image_path)
            mm = project.scale_mm_per_pixel
            room.area_m2 = round((w * img_w * mm / 1000.0) * (h * img_h * mm / 1000.0), 2)
            room.area_status = "approximate_calibrated"
        else:
            old_area = (old_bounds[2] - old_bounds[0]) * (old_bounds[3] - old_bounds[1]) if old_bounds else None
            if room.area_m2 and old_area:
                room.area_m2 = round(room.area_m2 * (w * h) / old_area, 2)   # scale the AI's estimate with the new size
            else:
                room.area_m2 = None
            room.area_status = "unscaled_estimate"

    # ------------------------------------------------------------- door geometry
    @staticmethod
    def _door_width_norm(project: Project, wall: str, image_path: str) -> float:
        mm_per_px = project.scale_mm_per_pixel if project.is_scale_calibrated else HEURISTIC_MM_PER_PIXEL
        img_w, img_h = image_size_px(image_path) if image_path else (1200, 900)
        span_px = img_w if wall in ("north", "south") else img_h
        return DEFAULT_DOOR_WIDTH_MM / (mm_per_px * span_px)

    @staticmethod
    def _door_fraction(bounds: List[float], wall: str, point: List[float]) -> float:
        (ax, ay), (bx, by) = wall_segment(bounds, wall)
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        return 0.5 if length_sq == 0 else max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length_sq))

    @classmethod
    def _apply_door(
        cls,
        feature: ArchitecturalFeature,
        project: Project,
        room: RoomObservation,
        wall: str,
        position: float,
        swing: str,
        strike_side: Optional[str],
        image_path: str,
    ) -> None:
        if wall not in WALLS:
            raise GeometryEditError(f"Wall must be one of: {', '.join(WALLS)}.")
        if swing not in SWING_DIRECTIONS:
            raise GeometryEditError(f"Swing direction must be one of: {', '.join(SWING_DIRECTIONS)}.")
        sides = STRIKE_SIDES[wall]
        strike_side = strike_side or sides[0]
        if strike_side not in sides:
            raise GeometryEditError(f"On the {wall} wall the handle side must be {' or '.join(sides)}.")

        (ax, ay), (bx, by) = wall_segment(room.bounds, wall)
        wall_len = math.hypot(bx - ax, by - ay)
        width = cls._door_width_norm(project, wall, image_path)
        if wall_len < width:
            raise GeometryEditError(
                f"The {wall} wall of '{room.name}' is too short to hold a door. Enlarge the room or choose another wall."
            )
        # keep the whole leaf on the wall
        margin = (width / 2.0) / wall_len
        t = min(max(position, margin), 1.0 - margin)
        cx, cy = ax + t * (bx - ax), ay + t * (by - ay)
        ux, uy = ((bx - ax) / wall_len, (by - ay) / wall_len)
        # +axis side is east (horizontal wall) or south (vertical wall)
        sign = 1.0 if strike_side in ("east", "south") else -1.0
        half = width / 2.0

        feature.room_id = room.id
        feature.room = room.name
        feature.wall = wall
        feature.door_position = [round(cx, 4), round(cy, 4)]
        feature.strike_point = [round(cx + sign * ux * half, 4), round(cy + sign * uy * half, 4)]
        feature.hinge_point = [round(cx - sign * ux * half, 4), round(cy - sign * uy * half, 4)]
        feature.strike_side = strike_side
        feature.swing_direction = swing
        feature.is_manual = True
        feature.confidence = 1.0

    @classmethod
    def _current_door_params(cls, feature: ArchitecturalFeature, room: RoomObservation) -> Tuple[str, float]:
        """(wall, fraction) of an existing door on its room, from its stored position."""
        from app.services.geometry_validator import nearest_wall
        pos = feature.door_position or [(room.bounds[0] + room.bounds[2]) / 2, (room.bounds[1] + room.bounds[3]) / 2]
        wall = feature.wall if feature.wall in WALLS else nearest_wall(room.bounds, pos)[0]
        return wall, cls._door_fraction(room.bounds, wall, pos)

    # ----------------------------------------------------------------------- API
    @classmethod
    def get_geometry(cls, project_id: str, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        issues = validate_geometry(project, analysis, rooms, features, cls._image_path(project)) \
            if project.floor_plan_path else []
        return cls._response(project, analysis, rooms, features, issues)

    @classmethod
    def add_room(cls, project_id: str, data: RoomCreate, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        name = data.name.strip()
        if not name:
            raise GeometryEditError("A room needs a name (e.g. Bedroom, Kitchen).")
        room = RoomObservation(
            id=cls._next_id("room_manual_", [r.id for r in rooms]),
            name=name,
            confidence=1.0,
            bounds=cls._check_bounds(data.bounds),
            is_manual=True,
        )
        cls._recompute_area(project, room, None, cls._image_path(project))
        rooms.append(room)
        return cls._save(project, analysis, rooms, features, db)

    @classmethod
    def update_room(cls, project_id: str, room_id: str, data: RoomUpdate, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        room = cls._room_by_id(rooms, room_id)
        if data.name is None and data.bounds is None:
            raise GeometryEditError("Nothing to change: provide a name and/or bounds.")

        old_name, old_bounds = room.name, list(room.bounds) if room.bounds else None

        if data.name is not None:
            new_name = data.name.strip()
            if not new_name:
                raise GeometryEditError("A room needs a name (e.g. Bedroom, Kitchen).")
            room.name = new_name
            for f in features:
                if f.room_id == room.id or (not f.room_id and (f.room or "").strip().lower() == old_name.strip().lower()):
                    f.room = new_name
                    f.room_id = room.id

        if data.bounds is not None:
            room.bounds = cls._check_bounds(data.bounds)
            image_path = cls._image_path(project)
            cls._recompute_area(project, room, old_bounds, image_path)
            # Doors stay attached to their wall at the same relative position
            for f in features:
                if f.type in DOOR_TYPES and (f.room_id == room.id) and old_bounds and f.door_position:
                    old_room = room.model_copy(update={"bounds": old_bounds})
                    wall, t = cls._current_door_params(f, old_room)
                    was_manual, was_confidence = f.is_manual, f.confidence
                    try:
                        cls._apply_door(f, project, room, wall, t, f.swing_direction or "into_room",
                                        f.strike_side if f.strike_side in STRIKE_SIDES[wall] else None, image_path)
                    except GeometryEditError:
                        pass   # wall became too short: leave the door; the checks will flag it
                    # the position was re-derived from the room, not authored by the user
                    f.is_manual, f.confidence = was_manual, was_confidence
        room.is_manual = True
        return cls._save(project, analysis, rooms, features, db)

    @classmethod
    def delete_room(cls, project_id: str, room_id: str, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        room = cls._room_by_id(rooms, room_id)
        rooms = [r for r in rooms if r.id != room.id]
        features = [
            f for f in features
            if not (f.room_id == room.id or (not f.room_id and (f.room or "").strip().lower() == room.name.strip().lower()))
        ]
        return cls._save(project, analysis, rooms, features, db)

    @classmethod
    def add_door(cls, project_id: str, data: DoorCreate, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        room = cls._room_by_id(rooms, data.room_id)
        if not room.bounds:
            raise GeometryEditError(f"Room '{room.name}' has no boundary, so it has no walls for a door.")
        feature = ArchitecturalFeature(type="door", room=room.name, room_id=room.id, confidence=1.0)
        cls._apply_door(feature, project, room, data.wall, data.position, data.swing_direction,
                        data.strike_side, cls._image_path(project))
        features.append(feature)
        ensure_feature_ids(features)
        return cls._save(project, analysis, rooms, features, db)

    @classmethod
    def _find_door(cls, features: List[ArchitecturalFeature], feature_id: str) -> ArchitecturalFeature:
        for f in features:
            if f.id == feature_id and f.type in DOOR_TYPES:
                return f
        raise GeometryEditError(f"Door '{feature_id}' not found.", 404)

    @classmethod
    def update_door(cls, project_id: str, feature_id: str, data: DoorUpdate, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        door = cls._find_door(features, feature_id)
        room = cls._room_by_id(rooms, data.room_id or door.room_id or "")
        if not room.bounds:
            raise GeometryEditError(f"Room '{room.name}' has no boundary, so it has no walls for a door.")

        cur_wall, cur_t = (cls._current_door_params(door, room)
                           if door.door_position and (data.room_id is None or data.room_id == door.room_id)
                           else (data.wall or "north", 0.5))
        wall = data.wall or cur_wall
        if wall not in WALLS:
            raise GeometryEditError(f"Wall must be one of: {', '.join(WALLS)}.")
        t = data.position if data.position is not None else (cur_t if wall == cur_wall else 0.5)
        strike = data.strike_side if data.strike_side is not None else (
            door.strike_side if door.strike_side in STRIKE_SIDES[wall] else None)
        cls._apply_door(door, project, room, wall, t, data.swing_direction or door.swing_direction or "into_room",
                        strike, cls._image_path(project))
        return cls._save(project, analysis, rooms, features, db)

    @classmethod
    def delete_door(cls, project_id: str, feature_id: str, db: Session) -> GeometryResponse:
        project, analysis, rooms, features = cls._context(project_id, db)
        door = cls._find_door(features, feature_id)
        features = [f for f in features if f is not door]
        return cls._save(project, analysis, rooms, features, db)
