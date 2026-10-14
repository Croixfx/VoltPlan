"""
Snapping of near-miss doors.

AI readings place door markers a few percent off the wall they belong to. Blocking generation for that
makes every real plan stop for a trivial reason, so a door that is only slightly off the wall it claims
is moved onto that wall, recorded (`snapped_from`) and reported as a WARNING so the user can check it.

What is NOT snapped, because that would be guessing:
  * a door further than DOOR_SNAP_TOLERANCE from its wall (the foyer door that sat 13% from the wall);
  * a door whose labelled wall disagrees with where the marker is (it is only ever moved along the wall it
    names, or along the nearest wall when it names none).
Those keep failing the geometry checks and are fixed by the user in the Rooms & Doors editor.
"""
import math
from typing import List, Optional, Sequence, Tuple

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation
from app.services.geometry_validator import (
    DOOR_WALL_TOLERANCE,
    FLOAT_EPS,
    WALLS,
    WARNING,
    GeometryIssue,
    distance_to_segment,
    nearest_wall,
    wall_segment,
)

# Doors up to this far (normalized plan units, i.e. 4% of the plan) from their wall are snapped onto it.
DOOR_SNAP_TOLERANCE = 0.04


def closest_point_on_segment(p: Sequence[float], a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length_sq))
    return ax + t * dx, ay + t * dy


def _valid_point(pt: Optional[Sequence[float]]) -> bool:
    return bool(pt) and len(pt) >= 2


def _usable_bounds(room: RoomObservation) -> bool:
    b = room.bounds
    return bool(b) and len(b) >= 4 and b[2] > b[0] and b[3] > b[1]


def door_snapped_issues(
    rooms: Sequence[RoomObservation],
    features: Sequence[ArchitecturalFeature],
) -> List[GeometryIssue]:
    """A warning for every door that was snapped onto its wall and has not been touched by the user since.

    Derived from `snapped_from`, so the reminder is still there after a reload or a regeneration, and goes
    away once the user moves, flips or re-places the door in the editor (which confirms it)."""
    by_id = {r.id: r for r in rooms}
    by_name = {r.name.strip().lower(): r for r in rooms if r.name}
    issues: List[GeometryIssue] = []
    for idx, f in enumerate(features):
        if not _valid_point(f.snapped_from) or not _valid_point(f.door_position) or f.is_manual:
            continue
        room = by_id.get(f.room_id) if f.room_id else None
        room = room or by_name.get((f.room or "").strip().lower())
        offset = math.hypot(f.door_position[0] - f.snapped_from[0], f.door_position[1] - f.snapped_from[1])
        issues.append(GeometryIssue(
            code="door_snapped",
            severity=WARNING,
            entity_ids=[f.id or f"feature_{idx + 1}"] + ([room.id] if room else []),
            message=f"A door in '{room.name if room else f.room}' was {offset * 100:.1f}% of the plan off the "
                    f"{f.wall or 'nearest'} wall and was moved onto it. Check its position.",
        ))
    return issues


def snap_doors_to_walls(
    rooms: Sequence[RoomObservation],
    features: Sequence[ArchitecturalFeature],
) -> List[GeometryIssue]:
    """Moves near-miss doors onto their wall (in place) and returns one warning per snapped door."""
    by_id = {r.id: r for r in rooms if _usable_bounds(r)}
    by_name = {r.name.strip().lower(): r for r in rooms if r.name and _usable_bounds(r)}
    issues: List[GeometryIssue] = []

    for idx, f in enumerate(features):
        if f.type not in ("door", "entrance") or not _valid_point(f.door_position):
            continue
        room = by_id.get(f.room_id) if f.room_id else None
        room = room or by_name.get((f.room or "").strip().lower())
        if room is None:
            continue

        pos = f.door_position
        wall = f.wall if f.wall in WALLS else nearest_wall(room.bounds, pos)[0]
        a, b = wall_segment(room.bounds, wall)
        dist = distance_to_segment(pos, a, b)
        if dist <= DOOR_WALL_TOLERANCE + FLOAT_EPS or dist > DOOR_SNAP_TOLERANCE + FLOAT_EPS:
            continue   # already on the wall, or too far to be a rounding slip

        tx, ty = closest_point_on_segment(pos, a, b)
        dx, dy = tx - pos[0], ty - pos[1]
        f.snapped_from = [round(pos[0], 4), round(pos[1], 4)]
        f.door_position = [round(tx, 4), round(ty, 4)]
        for attr in ("hinge_point", "strike_point"):        # keep the door's width and orientation
            pt = getattr(f, attr)
            if _valid_point(pt):
                setattr(f, attr, [round(pt[0] + dx, 4), round(pt[1] + dy, 4)])
        f.wall = wall

        issues.append(GeometryIssue(
            code="door_snapped",
            severity=WARNING,
            entity_ids=[f.id or f"feature_{idx + 1}", room.id],
            message=f"A door in '{room.name}' was {dist * 100:.1f}% of the plan off the {wall} wall and was moved "
                    "onto it. Check its position.",
        ))
    return issues
