"""
Pre-generation geometry checks.

Electrical equipment is placed from room boundaries and door positions, so
equipment generation must not start from geometry that is self-contradictory.
`GeometryValidator.validate` returns a list of issues; any issue with severity
"error" blocks generation. Nothing here repairs or guesses: the user fixes the
rooms / doors (see GeometryEditService) and generates again.

Rooms are axis-aligned rectangles (normalized bounds). An L-shaped room is
modelled as two adjacent rectangles.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation

ERROR = "error"
WARNING = "warning"

# --- thresholds (normalized plan units unless noted) -----------------------
BOUNDS_MARGIN = 0.005          # tolerance for bounds slightly outside [0, 1]
OVERLAP_ERROR_RATIO = 0.03     # overlap > 3% of the smaller room is an error
OVERLAP_MIN_AREA = 0.0002      # ignore hairline overlaps below this normalized area
DOOR_WALL_TOLERANCE = 0.02     # door centre must be this close to a room wall
FLOAT_EPS = 1e-9               # a value exactly on a limit must not fail because of floating-point rounding
MIN_ROOM_AREA_NORM = 0.001     # unscaled: smaller than 0.1% of the plan is not a room
WARN_ROOM_AREA_NORM = 0.004
# --- thresholds (metres, only when the scale is calibrated) -----------------
MIN_ROOM_SIDE_M = 0.6
WARN_ROOM_SIDE_M = 1.0
MIN_ROOM_AREA_M2 = 0.8
MAX_ROOM_AREA_M2 = 400.0
AREA_MISMATCH_RATIO = 0.4
MIN_DOOR_WIDTH_M = 0.4
MAX_DOOR_WIDTH_M = 3.0

WALLS = ("north", "south", "east", "west")


class GeometryIssue(BaseModel):
    code: str
    severity: str = Field(..., description="'error' blocks generation; 'warning' does not")
    message: str
    entity_ids: List[str] = Field(default_factory=list)


def has_errors(issues: Sequence[GeometryIssue]) -> bool:
    return any(i.severity == ERROR for i in issues)


def summarize(issues: Sequence[GeometryIssue], limit: int = 3) -> str:
    errors = [i for i in issues if i.severity == ERROR]
    shown = "; ".join(i.message for i in errors[:limit])
    more = f" (+{len(errors) - limit} more)" if len(errors) > limit else ""
    return f"Geometry check failed with {len(errors)} error(s): {shown}{more}"


def _valid_bounds(b: Optional[Sequence[float]]) -> bool:
    return bool(b) and len(b) >= 4 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in b[:4])


def wall_segment(bounds: Sequence[float], wall: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    x1, y1, x2, y2 = bounds[:4]
    return {
        "north": ((x1, y1), (x2, y1)),
        "south": ((x1, y2), (x2, y2)),
        "west": ((x1, y1), (x1, y2)),
        "east": ((x2, y1), (x2, y2)),
    }[wall]


def distance_to_segment(p: Sequence[float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length_sq))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def nearest_wall(bounds: Sequence[float], p: Sequence[float]) -> Tuple[str, float]:
    """The wall of a rectangle closest to point p and the distance to it."""
    best = min(WALLS, key=lambda w: distance_to_segment(p, *wall_segment(bounds, w)))
    return best, distance_to_segment(p, *wall_segment(bounds, best))


def _overlap_area(a: Sequence[float], b: Sequence[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _area(b: Sequence[float]) -> float:
    return (b[2] - b[0]) * (b[3] - b[1])


class GeometryValidator:
    @classmethod
    def validate(
        cls,
        rooms: Sequence[RoomObservation],
        features: Sequence[ArchitecturalFeature],
        scale_mm_per_pixel: Optional[float] = None,
        image_size_px: Optional[Tuple[int, int]] = None,
    ) -> List[GeometryIssue]:
        issues: List[GeometryIssue] = []
        calibrated = bool(scale_mm_per_pixel and scale_mm_per_pixel > 0 and image_size_px)

        def metres(norm_w: float, norm_h: float) -> Tuple[float, float]:
            w_px, h_px = image_size_px  # type: ignore[misc]
            return (norm_w * w_px * scale_mm_per_pixel / 1000.0, norm_h * h_px * scale_mm_per_pixel / 1000.0)  # type: ignore[operator]

        if not rooms:
            issues.append(GeometryIssue(
                code="no_rooms", severity=ERROR,
                message="No rooms are defined. Add at least one room before generating equipment.",
            ))

        # ---- rooms: identity -------------------------------------------------
        seen_ids: Dict[str, str] = {}
        seen_names: Dict[str, str] = {}
        for r in rooms:
            if r.id in seen_ids:
                issues.append(GeometryIssue(
                    code="duplicate_room_id", severity=ERROR, entity_ids=[r.id],
                    message=f"Two rooms share the id '{r.id}'.",
                ))
            seen_ids[r.id] = r.name
            if not r.name or not r.name.strip():
                issues.append(GeometryIssue(
                    code="room_unnamed", severity=ERROR, entity_ids=[r.id],
                    message="A room has no name. Equipment rules depend on the room type (bedroom, kitchen, ...).",
                ))
                continue
            key = r.name.strip().lower()
            if key in seen_names:
                issues.append(GeometryIssue(
                    code="duplicate_room_name", severity=WARNING, entity_ids=[r.id, seen_names[key]],
                    message=f"More than one room is named '{r.name}'. Give each room a distinct name "
                            "(e.g. 'Living Room' and 'Living Room 2') so doors attach to the right one.",
                ))
            seen_names[key] = r.id

        # ---- rooms: boundary --------------------------------------------------
        usable: List[RoomObservation] = []
        for r in rooms:
            label = f"'{r.name or r.id}'"
            if not _valid_bounds(r.bounds):
                issues.append(GeometryIssue(
                    code="room_no_boundary", severity=ERROR, entity_ids=[r.id],
                    message=f"Room {label} has no closed boundary.",
                ))
                continue
            x1, y1, x2, y2 = r.bounds[:4]
            if x2 <= x1 or y2 <= y1:
                issues.append(GeometryIssue(
                    code="room_degenerate", severity=ERROR, entity_ids=[r.id],
                    message=f"Room {label} has an empty or inverted boundary (it does not enclose an area).",
                ))
                continue
            if min(x1, y1) < -BOUNDS_MARGIN or max(x2, y2) > 1 + BOUNDS_MARGIN:
                issues.append(GeometryIssue(
                    code="room_out_of_plan", severity=ERROR, entity_ids=[r.id],
                    message=f"Room {label} extends outside the plan.",
                ))
                continue
            usable.append(r)

            # sizes
            area_norm = _area(r.bounds)
            if calibrated:
                w_m, h_m = metres(x2 - x1, y2 - y1)
                area_m2 = w_m * h_m
                if min(w_m, h_m) < MIN_ROOM_SIDE_M:
                    issues.append(GeometryIssue(
                        code="room_too_narrow", severity=ERROR, entity_ids=[r.id],
                        message=f"Room {label} is only {min(w_m, h_m):.2f} m wide (minimum {MIN_ROOM_SIDE_M} m). "
                                "Check its boundary or the plan scale.",
                    ))
                elif min(w_m, h_m) < WARN_ROOM_SIDE_M:
                    issues.append(GeometryIssue(
                        code="room_narrow", severity=WARNING, entity_ids=[r.id],
                        message=f"Room {label} is only {min(w_m, h_m):.2f} m wide; verify its boundary.",
                    ))
                if area_m2 < MIN_ROOM_AREA_M2 or area_m2 > MAX_ROOM_AREA_M2:
                    issues.append(GeometryIssue(
                        code="room_size_implausible", severity=ERROR, entity_ids=[r.id],
                        message=f"Room {label} measures {area_m2:.1f} m², which is not plausible "
                                f"({MIN_ROOM_AREA_M2}-{MAX_ROOM_AREA_M2:.0f} m²). Check its boundary or the plan scale.",
                    ))
                elif r.area_m2 and abs(area_m2 - r.area_m2) / r.area_m2 > AREA_MISMATCH_RATIO:
                    issues.append(GeometryIssue(
                        code="room_area_mismatch", severity=WARNING, entity_ids=[r.id],
                        message=f"Room {label}: boundary gives {area_m2:.1f} m² but the plan label says "
                                f"{r.area_m2:.1f} m². One of them is wrong.",
                    ))
            else:
                if area_norm < MIN_ROOM_AREA_NORM:
                    issues.append(GeometryIssue(
                        code="room_too_small", severity=ERROR, entity_ids=[r.id],
                        message=f"Room {label} covers {area_norm * 100:.2f}% of the plan, too small to be a room.",
                    ))
                elif area_norm < WARN_ROOM_AREA_NORM:
                    issues.append(GeometryIssue(
                        code="room_small", severity=WARNING, entity_ids=[r.id],
                        message=f"Room {label} is very small ({area_norm * 100:.2f}% of the plan); verify it.",
                    ))

        # ---- rooms: overlaps -------------------------------------------------
        for i in range(len(usable)):
            for j in range(i + 1, len(usable)):
                a, b = usable[i], usable[j]
                overlap = _overlap_area(a.bounds, b.bounds)
                if overlap <= OVERLAP_MIN_AREA:
                    continue
                ratio = overlap / min(_area(a.bounds), _area(b.bounds))
                severe = ratio > OVERLAP_ERROR_RATIO
                issues.append(GeometryIssue(
                    code="rooms_overlap", severity=ERROR if severe else WARNING, entity_ids=[a.id, b.id],
                    message=f"Rooms '{a.name}' and '{b.name}' overlap by {ratio * 100:.0f}% of the smaller room."
                            + ("" if severe else " (minor)"),
                ))

        # ---- doors -------------------------------------------------------------
        by_id = {r.id: r for r in usable}
        by_name = {r.name.strip().lower(): r for r in usable if r.name}
        rooms_with_door: set = set()

        def find_room(feat: ArchitecturalFeature) -> Optional[RoomObservation]:
            if feat.room_id and feat.room_id in by_id:
                return by_id[feat.room_id]
            return by_name.get((feat.room or "").strip().lower())

        for idx, f in enumerate(features):
            fid = f.id or f"feature_{idx + 1}"
            room = find_room(f)

            if f.type in ("door", "entrance"):
                if room is None:
                    issues.append(GeometryIssue(
                        code="door_unknown_room", severity=ERROR, entity_ids=[fid],
                        message=f"A door refers to room '{f.room}', which does not exist (or has no valid boundary).",
                    ))
                    continue
                rooms_with_door.add(room.id)
                pos = f.door_position
                if not pos or len(pos) < 2:
                    issues.append(GeometryIssue(
                        code="door_no_position", severity=ERROR, entity_ids=[fid, room.id],
                        message=f"A door in '{room.name}' has no position on the plan.",
                    ))
                    continue
                if not all(math.isfinite(v) for v in pos[:2]) or not (-BOUNDS_MARGIN <= pos[0] <= 1 + BOUNDS_MARGIN) \
                        or not (-BOUNDS_MARGIN <= pos[1] <= 1 + BOUNDS_MARGIN):
                    issues.append(GeometryIssue(
                        code="door_out_of_plan", severity=ERROR, entity_ids=[fid, room.id],
                        message=f"A door in '{room.name}' lies outside the plan.",
                    ))
                    continue
                if f.wall and f.wall in WALLS:
                    dist = distance_to_segment(pos, *wall_segment(room.bounds, f.wall))
                    wall = f.wall
                else:
                    wall, dist = nearest_wall(room.bounds, pos)
                if dist > DOOR_WALL_TOLERANCE + FLOAT_EPS:
                    where = f"the {f.wall} wall" if f.wall in WALLS else "any wall"
                    issues.append(GeometryIssue(
                        code="door_not_on_wall", severity=ERROR, entity_ids=[fid, room.id],
                        message=f"A door in '{room.name}' is not on {where} of the room "
                                f"(it is {dist * 100:.1f}% of the plan away from the wall; up to "
                                f"{DOOR_WALL_TOLERANCE * 100:.0f}% is allowed).",
                    ))
                    continue
                for label, pt in (("hinge", f.hinge_point), ("strike", f.strike_point)):
                    if pt and len(pt) >= 2 and distance_to_segment(pt, *wall_segment(room.bounds, wall)) > DOOR_WALL_TOLERANCE * 1.5 + FLOAT_EPS:
                        issues.append(GeometryIssue(
                            code=f"door_{label}_off_wall", severity=WARNING, entity_ids=[fid, room.id],
                            message=f"The {label} of a door in '{room.name}' is not on the same wall as the door.",
                        ))
                if calibrated and f.hinge_point and f.strike_point and len(f.hinge_point) >= 2 and len(f.strike_point) >= 2:
                    dw, dh = metres(f.strike_point[0] - f.hinge_point[0], f.strike_point[1] - f.hinge_point[1])
                    width = math.hypot(dw, dh)
                    if width < MIN_DOOR_WIDTH_M or width > MAX_DOOR_WIDTH_M:
                        issues.append(GeometryIssue(
                            code="door_width_implausible", severity=WARNING, entity_ids=[fid, room.id],
                            message=f"A door in '{room.name}' measures {width:.2f} m wide, which is not plausible.",
                        ))
            elif f.bounds and _valid_bounds(f.bounds) and room is not None:
                cx, cy = (f.bounds[0] + f.bounds[2]) / 2, (f.bounds[1] + f.bounds[3]) / 2
                rb = room.bounds
                slack = DOOR_WALL_TOLERANCE + FLOAT_EPS
                if not (rb[0] - slack <= cx <= rb[2] + slack and rb[1] - slack <= cy <= rb[3] + slack):
                    issues.append(GeometryIssue(
                        code="fixture_outside_room", severity=WARNING, entity_ids=[fid, room.id],
                        message=f"The {f.type} assigned to '{room.name}' lies outside that room.",
                    ))

        for r in usable:
            if r.id not in rooms_with_door and len(usable) > 1:
                issues.append(GeometryIssue(
                    code="room_no_door", severity=WARNING, entity_ids=[r.id],
                    message=f"Room '{r.name}' has no door; switch positions cannot be derived from a door.",
                ))

        return issues
