import asyncio

import pytest

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation
from app.services.geometry_validator import GeometryValidator, has_errors, summarize
from app.services.vision_service import MockVisionProvider


def room(rid, name, bounds, area=None):
    return RoomObservation(id=rid, name=name, confidence=0.9, bounds=bounds, area_m2=area)


def door(room_name, pos, wall=None, room_id=None, **kw):
    return ArchitecturalFeature(type="door", room=room_name, room_id=room_id, confidence=0.9,
                                door_position=pos, wall=wall, **kw)


def codes(issues, severity=None):
    return {i.code for i in issues if severity is None or i.severity == severity}


LIVING = room("r1", "Living Room", [0.1, 0.1, 0.5, 0.5])
KITCHEN = room("r2", "Kitchen", [0.5, 0.1, 0.9, 0.5])


def test_mock_provider_plan_passes_all_checks():
    result = asyncio.run(MockVisionProvider().analyze_floor_plan("x.png", "Residential", "RS IEC 60364"))
    issues = GeometryValidator.validate(result.rooms, result.architectural_features)
    assert not has_errors(issues), [i.message for i in issues]


def test_clean_plan_has_no_errors():
    issues = GeometryValidator.validate(
        [LIVING, KITCHEN],
        [door("Living Room", [0.3, 0.5], "south"), door("Kitchen", [0.5, 0.3], "west")],
    )
    assert not has_errors(issues)


@pytest.mark.parametrize(
    "bounds,code",
    [
        (None, "room_no_boundary"),
        ([0.1, 0.1], "room_no_boundary"),
        ([0.5, 0.1, 0.1, 0.5], "room_degenerate"),
        ([0.1, 0.1, 0.1, 0.5], "room_degenerate"),
        ([0.1, 0.1, 1.4, 0.5], "room_out_of_plan"),
        ([0.1, 0.1, 0.102, 0.102], "room_too_small"),
    ],
)
def test_bad_room_boundaries_are_errors(bounds, code):
    issues = GeometryValidator.validate([room("r1", "Hall", bounds)], [])
    assert code in codes(issues, "error")


def test_no_rooms_is_an_error():
    assert "no_rooms" in codes(GeometryValidator.validate([], []), "error")


def test_unnamed_and_duplicate_rooms():
    issues = GeometryValidator.validate([room("r1", "  ", [0.1, 0.1, 0.4, 0.4]), room("r1", "A", [0.5, 0.5, 0.9, 0.9])], [])
    assert {"room_unnamed", "duplicate_room_id"} <= codes(issues, "error")
    dup = GeometryValidator.validate([room("a", "Bedroom", [0.1, 0.1, 0.4, 0.4]), room("b", "bedroom", [0.5, 0.5, 0.9, 0.9])], [])
    assert "duplicate_room_name" in codes(dup, "warning") and not has_errors(dup)


def test_overlap_thresholds():
    touching = [room("a", "A", [0.1, 0.1, 0.5, 0.5]), room("b", "B", [0.5, 0.1, 0.9, 0.5])]
    assert "rooms_overlap" not in codes(GeometryValidator.validate(touching, []))

    minor = [room("a", "A", [0.1, 0.1, 0.5, 0.5]), room("b", "B", [0.495, 0.1, 0.9, 0.5])]  # ~1% of smaller
    res = GeometryValidator.validate(minor, [])
    assert "rooms_overlap" in codes(res, "warning") and not has_errors(res)

    major = [room("a", "A", [0.1, 0.1, 0.5, 0.5]), room("b", "B", [0.3, 0.1, 0.9, 0.5])]
    res = GeometryValidator.validate(major, [])
    assert "rooms_overlap" in codes(res, "error")
    assert set(next(i for i in res if i.code == "rooms_overlap").entity_ids) == {"a", "b"}


def test_door_must_sit_on_a_wall():
    far = door("Living Room", [0.3, 0.3], "south")      # middle of the room
    assert "door_not_on_wall" in codes(GeometryValidator.validate([LIVING], [far]), "error")

    wrong_wall = door("Living Room", [0.3, 0.5], "north")  # on the south wall but labelled north
    assert "door_not_on_wall" in codes(GeometryValidator.validate([LIVING], [wrong_wall]), "error")

    on_wall = door("Living Room", [0.3, 0.505], "south")
    assert not has_errors(GeometryValidator.validate([LIVING], [on_wall]))

    unlabeled = door("Living Room", [0.1, 0.3])           # west wall, no label: still fine
    assert not has_errors(GeometryValidator.validate([LIVING], [unlabeled]))

    off_plan_wall_span = door("Living Room", [0.8, 0.5], "south")   # right line, beyond the wall's length
    assert "door_not_on_wall" in codes(GeometryValidator.validate([LIVING], [off_plan_wall_span]), "error")


def test_door_references():
    ghost = door("Garage", [0.3, 0.5], "south")
    assert "door_unknown_room" in codes(GeometryValidator.validate([LIVING], [ghost]), "error")

    no_pos = ArchitecturalFeature(type="door", room="Living Room", confidence=0.9)
    assert "door_no_position" in codes(GeometryValidator.validate([LIVING], [no_pos]), "error")

    by_id = door("stale name", [0.3, 0.5], "south", room_id="r1")   # id wins over a stale name
    assert not has_errors(GeometryValidator.validate([LIVING], [by_id]))


def test_hinge_off_wall_is_only_a_warning():
    d = door("Living Room", [0.3, 0.5], "south", hinge_point=[0.27, 0.3], strike_point=[0.33, 0.5])
    res = GeometryValidator.validate([LIVING], [d])
    assert "door_hinge_off_wall" in codes(res, "warning") and not has_errors(res)


def test_room_without_door_is_a_warning():
    res = GeometryValidator.validate([LIVING, KITCHEN], [door("Living Room", [0.3, 0.5], "south")])
    assert any(i.code == "room_no_door" and i.entity_ids == ["r2"] for i in res)
    assert not has_errors(res)


def test_sizes_checked_in_metres_only_when_calibrated():
    # 1000x800 px plan at 10 mm/px => 10 m x 8 m
    sized = dict(scale_mm_per_pixel=10.0, image_size_px=(1000, 800))
    sliver = room("r1", "Corridor", [0.1, 0.1, 0.105, 0.6])      # 5 cm wide
    assert "room_too_narrow" in codes(GeometryValidator.validate([sliver], [], **sized), "error")

    hall = room("r2", "Hall", [0.0, 0.0, 1.0, 1.0])               # 80 m² is fine
    assert not has_errors(GeometryValidator.validate([hall], [], **sized))

    tiny_scale = dict(scale_mm_per_pixel=100.0, image_size_px=(1000, 800))   # same box => 8000 m²
    assert "room_size_implausible" in codes(GeometryValidator.validate([hall], [], **tiny_scale), "error")

    # Same boundaries without a scale: nothing can be said in metres
    assert not has_errors(GeometryValidator.validate([hall], []))


def test_label_area_mismatch_warns():
    lying = room("r1", "Bedroom", [0.1, 0.1, 0.5, 0.5], area=40.0)   # 4 m x 3.2 m = 12.8 m² by scale
    res = GeometryValidator.validate([lying], [], scale_mm_per_pixel=10.0, image_size_px=(1000, 800))
    assert "room_area_mismatch" in codes(res, "warning")


def test_door_width_when_calibrated():
    d = door("Living Room", [0.3, 0.5], "south", hinge_point=[0.1, 0.5], strike_point=[0.5, 0.5])   # 4 m wide
    res = GeometryValidator.validate([LIVING], [d], scale_mm_per_pixel=10.0, image_size_px=(1000, 800))
    assert "door_width_implausible" in codes(res, "warning")


def test_summary_lists_errors_only():
    res = GeometryValidator.validate([room("a", "A", [0.1, 0.1, 0.5, 0.5]), room("b", "B", [0.3, 0.1, 0.9, 0.5])], [])
    text = summarize(res)
    assert text.startswith("Geometry check failed with 1 error(s)") and "overlap" in text


def test_a_door_exactly_at_the_limit_is_not_rejected_by_rounding():
    # Real case from a Gemini reading: door at x=0.32 on a wall at x=0.34 is "2.0% away", exactly the limit.
    # 0.34 - 0.32 is 0.020000000000000018 in floating point, which used to push it over.
    bedroom = room("r1", "Bedroom", [0.02, 0.14, 0.34, 0.52])
    at_limit = door("Bedroom", [0.32, 0.38], "east")
    assert not has_errors(GeometryValidator.validate([bedroom], [at_limit]))
    # clearly beyond the limit is still rejected, and the message says what is allowed
    beyond = door("Bedroom", [0.31, 0.38], "east")
    res = GeometryValidator.validate([bedroom], [beyond])
    msg = next(i.message for i in res if i.code == "door_not_on_wall")
    assert "3.0% of the plan away" in msg and "up to 2% is allowed" in msg


def test_a_door_in_the_middle_of_a_room_is_rejected_even_if_it_names_a_wall():
    # Real case: an entrance placed mid-foyer but labelled "west wall" (13% away)
    foyer = room("r7", "Entrance Foyer", [0.02, 0.52, 0.26, 0.81])
    entrance = ArchitecturalFeature(type="entrance", room="Entrance Foyer", confidence=0.9,
                                    door_position=[0.15, 0.66], wall="west")
    res = GeometryValidator.validate([foyer], [entrance])
    assert "door_not_on_wall" in codes(res, "error")
