import io

import pytest
from PIL import Image

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation, VisionAnalysisResult
from app.services.geometry_snapper import DOOR_SNAP_TOLERANCE, snap_doors_to_walls
from app.services.geometry_validator import GeometryValidator, has_errors
from app.services.vision_service import VisionService

BEDROOM = RoomObservation(id="r1", name="Bedroom", confidence=0.9, bounds=[0.02, 0.14, 0.34, 0.52])
FOYER = RoomObservation(id="r7", name="Entrance Foyer", confidence=0.9, bounds=[0.02, 0.52, 0.26, 0.81])


def door(room, pos, wall=None, **kw):
    return ArchitecturalFeature(id="feat_001", type="door", room=room, confidence=0.9, door_position=pos, wall=wall, **kw)


def errors(rooms, feats):
    return [i for i in GeometryValidator.validate(rooms, feats) if i.severity == "error"]


# --------------------------------------------------------------------------- the rules
def test_a_door_a_few_percent_off_its_wall_is_moved_onto_it_and_reported():
    d = door("Bedroom", [0.30, 0.38], "east", hinge_point=[0.30, 0.35], strike_point=[0.30, 0.41])   # wall x=0.34, 4% away
    issues = snap_doors_to_walls([BEDROOM], [d])

    assert d.door_position == [0.34, 0.38]
    assert d.hinge_point == [0.34, 0.35] and d.strike_point == [0.34, 0.41]     # the leaf moves with it, width unchanged
    assert d.snapped_from == [0.30, 0.38] and d.wall == "east"
    assert [(i.code, i.severity) for i in issues] == [("door_snapped", "warning")]
    assert "4.0% of the plan off the east wall" in issues[0].message and "Check its position" in issues[0].message
    assert issues[0].entity_ids == ["feat_001", "r1"]
    assert not errors([BEDROOM], [d])                                            # it now passes the check


def test_doors_already_on_the_wall_are_left_alone():
    for x in (0.34, 0.33, 0.32):                    # 0, 1 and exactly 2% away: within the normal tolerance
        d = door("Bedroom", [x, 0.38], "east")
        assert snap_doors_to_walls([BEDROOM], [d]) == []
        assert d.door_position == [x, 0.38] and d.snapped_from is None


def test_doors_too_far_from_the_wall_are_not_guessed_at():
    five = door("Bedroom", [0.29, 0.38], "east")                                 # 5% away
    assert snap_doors_to_walls([BEDROOM], [five]) == [] and five.door_position == [0.29, 0.38]
    assert errors([BEDROOM], [five])                                             # still stops generation

    # the real case: an entrance mid-foyer labelled "west wall", 13% away
    foyer = door("Entrance Foyer", [0.15, 0.66], "west")
    assert snap_doors_to_walls([FOYER], [foyer]) == [] and foyer.door_position == [0.15, 0.66]
    assert errors([FOYER], [foyer])


def test_the_limit_is_four_percent_inclusive():
    on_limit = door("Bedroom", [0.34 - DOOR_SNAP_TOLERANCE, 0.38], "east")
    assert len(snap_doors_to_walls([BEDROOM], [on_limit])) == 1
    over = door("Bedroom", [0.34 - DOOR_SNAP_TOLERANCE - 0.002, 0.38], "east")
    assert snap_doors_to_walls([BEDROOM], [over]) == []


def test_a_door_is_only_moved_along_the_wall_it_names():
    # sits 3% from the south wall but is labelled "north": the label and the marker disagree, so nothing is assumed
    mislabelled = door("Bedroom", [0.20, 0.49], "north")
    assert snap_doors_to_walls([BEDROOM], [mislabelled]) == []
    assert mislabelled.door_position == [0.20, 0.49] and errors([BEDROOM], [mislabelled])


def test_an_unlabelled_door_snaps_to_the_nearest_wall_and_gets_labelled():
    d = door("Bedroom", [0.31, 0.38])                                            # 3% from the east wall, no label
    issues = snap_doors_to_walls([BEDROOM], [d])
    assert len(issues) == 1 and d.wall == "east" and d.door_position == [0.34, 0.38]


def test_a_door_beyond_the_end_of_its_wall_is_clamped_onto_the_wall():
    d = door("Bedroom", [0.315, 0.535], "east")                                  # 2.9% from the room's south-east corner
    assert len(snap_doors_to_walls([BEDROOM], [d])) == 1
    assert d.door_position == [0.34, 0.52]                                       # the end of the east wall, never past it

    near_corner = door("Bedroom", [0.33, 0.53], "east")                          # 1.4% away: within the normal tolerance
    assert snap_doors_to_walls([BEDROOM], [near_corner]) == [] and near_corner.door_position == [0.33, 0.53]


def test_things_that_are_not_doors_or_have_no_room_are_ignored_and_the_pass_is_idempotent():
    window = ArchitecturalFeature(id="w", type="window", room="Bedroom", confidence=0.9, door_position=[0.30, 0.38])
    ghost = door("Garage", [0.30, 0.38], "east")
    no_position = ArchitecturalFeature(id="n", type="door", room="Bedroom", confidence=0.9)
    assert snap_doors_to_walls([BEDROOM], [window, ghost, no_position]) == []

    d = door("Bedroom", [0.30, 0.38], "east")
    assert len(snap_doors_to_walls([BEDROOM], [d])) == 1
    assert snap_doors_to_walls([BEDROOM], [d]) == []                             # second pass finds nothing to do


def test_rooms_without_a_usable_boundary_are_skipped():
    broken = RoomObservation(id="b", name="Broken", confidence=0.9, bounds=[0.5, 0.5, 0.1, 0.1])
    assert snap_doors_to_walls([broken], [door("Broken", [0.3, 0.3], "east")]) == []


# --------------------------------------------------------------------------- through the pipeline
def _project(client):
    pid = client.post("/api/projects", json={"name": "Snap Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    return pid


def _reading(extra_doors=()):
    return VisionAnalysisResult(
        rooms=[
            RoomObservation(id="living", name="Living Room", confidence=0.9, bounds=[0.05, 0.05, 0.50, 0.50]),
            RoomObservation(id="kitchen", name="Kitchen", confidence=0.9, bounds=[0.50, 0.05, 0.95, 0.50]),
        ],
        architectural_features=[
            # the living-room door is 3% off its east wall (x=0.50); the kitchen door is exactly on its west wall
            ArchitecturalFeature(type="door", room="Living Room", confidence=0.9, door_position=[0.47, 0.30], wall="east"),
            ArchitecturalFeature(type="door", room="Kitchen", confidence=0.9, door_position=[0.50, 0.30], wall="west"),
            *extra_doors,
        ],
    )


def test_a_near_miss_door_no_longer_stops_the_analysis(client, monkeypatch):
    async def fake(**kwargs):
        return _reading()

    monkeypatch.setattr(VisionService, "analyze_floor_plan", staticmethod(fake))
    pid = _project(client)

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 200 and res.json()["status"] == "completed"
    assert any("moved onto it" in w for w in res.json()["warnings"])             # the user is told

    geo = client.get(f"/api/projects/{pid}/geometry").json()
    living_door = next(f for f in geo["features"] if f["room"] == "Living Room")
    assert living_door["door_position"] == [0.5, 0.3] and living_door["snapped_from"] == [0.47, 0.3]
    assert any(i["code"] == "door_snapped" and i["severity"] == "warning" for i in geo["issues"])
    assert geo["can_generate"] is True and not any(i["severity"] == "error" for i in geo["issues"])
    kitchen_door = next(f for f in geo["features"] if f["room"] == "Kitchen")
    assert kitchen_door["snapped_from"] is None                                  # untouched

    # regenerating does not snap the door a second time, and the reminder stays until the user looks at it
    assert client.post(f"/api/projects/{pid}/regenerate").status_code == 200
    geo = client.get(f"/api/projects/{pid}/geometry").json()
    living_door = next(f for f in geo["features"] if f["room"] == "Living Room")
    assert living_door["door_position"] == [0.5, 0.3] and living_door["snapped_from"] == [0.47, 0.3]
    reminder = next(i for i in geo["issues"] if i["code"] == "door_snapped")
    assert "3.0% of the plan off the east wall" in reminder["message"] and living_door["id"] in reminder["entity_ids"]

    # moving the door in the editor confirms it: the reminder goes away
    res = client.patch(f"/api/projects/{pid}/doors/{living_door['id']}", json={"position": 0.4})
    assert res.status_code == 200
    assert not any(i["code"] == "door_snapped" for i in res.json()["issues"])
    assert next(f for f in res.json()["features"] if f["id"] == living_door["id"])["snapped_from"] is None


def test_a_genuinely_misplaced_door_still_stops_with_a_clear_error_while_near_misses_are_fixed(client, monkeypatch):
    far = ArchitecturalFeature(type="entrance", room="Kitchen", confidence=0.9, door_position=[0.72, 0.28], wall="west")

    async def fake(**kwargs):
        return _reading([far])

    monkeypatch.setattr(VisionService, "analyze_floor_plan", staticmethod(fake))
    pid = _project(client)

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 422
    issues = res.json()["detail"]["issues"]
    errs = [i for i in issues if i["severity"] == "error"]
    assert [e["code"] for e in errs] == ["door_not_on_wall"] and "Kitchen" in errs[0]["message"]
    assert any(i["code"] == "door_snapped" for i in issues)                      # the near miss was still fixed

    geo = client.get(f"/api/projects/{pid}/geometry").json()
    entrance = next(f for f in geo["features"] if f["type"] == "entrance")
    assert entrance["door_position"] == [0.72, 0.28] and entrance["snapped_from"] is None   # the far door is not guessed at
