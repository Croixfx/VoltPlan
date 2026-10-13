import io

import pytest
from PIL import Image

from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation, VisionAnalysisResult
from app.services.vision_service import VisionService

# Mock-provider layout (normalized):
#   room_living   Living Room        [0.06,0.06,0.52,0.48]  door on its south wall
#   room_kitchen  Kitchen & Dining   [0.54,0.06,0.94,0.48]
#   room_corridor Central Corridor   [0.44,0.48,0.60,0.62]
#   room_master   Master Bedroom     [0.06,0.54,0.44,0.94]
#   room_bathroom En-Suite Bathroom  [0.46,0.64,0.66,0.94]
#   room_bed1     Bedroom 1          [0.68,0.54,0.94,0.94]


def _project(client, analyze=True):
    pid = client.post("/api/projects", json={"name": "Geometry Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    if analyze:
        assert client.post(f"/api/projects/{pid}/analyze").status_code == 200
    return pid


def _geo(client, pid):
    res = client.get(f"/api/projects/{pid}/geometry")
    assert res.status_code == 200
    return res.json()


def _room(geo, room_id):
    return next(r for r in geo["rooms"] if r["id"] == room_id)


def _doors(geo, room_id):
    return [f for f in geo["features"] if f["type"] == "door" and f["room_id"] == room_id]


def _points(client, pid, room_name=None):
    pts = client.get(f"/api/projects/{pid}/analysis").json()["electrical_points"]
    return [p for p in pts if room_name is None or p["room_name"] == room_name]


def _types(points):
    return {p["type"] for p in points}


def test_analysis_stores_ids_and_a_clean_geometry_report(client):
    pid = _project(client)
    geo = _geo(client, pid)
    assert geo["can_generate"] is True and geo["reviewed"] is False and geo["needs_regeneration"] is False
    assert all(f["id"] for f in geo["features"])
    assert all(d["room_id"] for d in geo["features"] if d["type"] == "door")


def test_rename_room_then_regenerate_changes_the_equipment(client):
    pid = _project(client)
    before = _points(client, pid, "Bedroom 1")
    assert "smoke_detector" in _types(before) and "data_point" not in _types(before)

    res = client.patch(f"/api/projects/{pid}/rooms/room_bed1", json={"name": "Home Office"})
    assert res.status_code == 200
    geo = res.json()
    assert geo["reviewed"] and geo["needs_regeneration"]
    assert _room(geo, "room_bed1")["name"] == "Home Office"
    assert all(d["room"] == "Home Office" for d in _doors(geo, "room_bed1"))   # doors follow the new name
    # Equipment is stale until regenerated
    assert "smoke_detector" in _types(_points(client, pid, "Bedroom 1"))

    regen = client.post(f"/api/projects/{pid}/regenerate")
    assert regen.status_code == 200
    after = [p for p in regen.json()["electrical_points"] if p["room_id"] == "room_bed1"]
    assert {p["room_name"] for p in after} == {"Home Office"}
    assert "data_point" in _types(after) and "smoke_detector" not in _types(after)
    assert regen.json()["geometry_needs_regeneration"] is False
    assert not client.get(f"/api/projects/{pid}/geometry").json()["needs_regeneration"]


def test_resizing_a_room_keeps_its_doors_on_the_wall(client):
    pid = _project(client)
    old_door = _doors(_geo(client, pid), "room_living")[0]
    assert old_door["wall"] == "south"

    res = client.patch(f"/api/projects/{pid}/rooms/room_living", json={"bounds": [0.06, 0.06, 0.52, 0.40]})
    assert res.status_code == 200
    geo = res.json()
    door = _doors(geo, "room_living")[0]
    assert door["door_position"][1] == pytest.approx(0.40, abs=1e-3)       # moved up with the south wall
    assert door["hinge_point"][1] == pytest.approx(0.40, abs=1e-3) and door["strike_point"][1] == pytest.approx(0.40, abs=1e-3)
    assert not any(i["code"] == "door_not_on_wall" for i in geo["issues"])
    assert _room(geo, "room_living")["is_manual"] is True
    assert _room(geo, "room_living")["area_m2"] < 28.5                       # estimate shrinks with the room


@pytest.mark.parametrize(
    "bounds,fragment",
    [
        ([0.5, 0.1, 0.1, 0.5], "enclose an area"),
        ([0.1, 0.1, 1.4, 0.5], "inside the plan"),
        ([0.1, 0.1, "x", 0.5], None),
    ],
)
def test_malformed_room_edits_are_rejected(client, bounds, fragment):
    pid = _project(client)
    res = client.patch(f"/api/projects/{pid}/rooms/room_living", json={"bounds": bounds})
    assert res.status_code == 422
    if fragment:
        assert fragment in res.json()["detail"]
    assert _room(_geo(client, pid), "room_living")["bounds"] == [0.06, 0.06, 0.52, 0.48]


def test_other_edit_rejections(client):
    pid = _project(client)
    assert client.patch(f"/api/projects/{pid}/rooms/nope", json={"name": "X"}).status_code == 404
    assert client.patch(f"/api/projects/{pid}/rooms/room_living", json={}).status_code == 422
    assert client.patch(f"/api/projects/{pid}/rooms/room_living", json={"name": "   "}).status_code == 422
    assert client.post(f"/api/projects/{pid}/rooms", json={"name": "Store", "bounds": [0.7, 0.1, 0.6, 0.2]}).status_code == 422
    door = _doors(_geo(client, pid), "room_living")[0]
    assert client.patch(f"/api/projects/{pid}/doors/{door['id']}", json={"wall": "up"}).status_code == 422
    assert client.patch(f"/api/projects/{pid}/doors/{door['id']}", json={"wall": "north", "strike_side": "north"}).status_code == 422
    assert client.patch(f"/api/projects/{pid}/doors/nope", json={"position": 0.5}).status_code == 404
    assert client.post(f"/api/projects/{pid}/doors", json={"room_id": "ghost", "wall": "north"}).status_code == 404
    assert not _geo(client, pid)["reviewed"]    # nothing was accepted


def test_geometry_requires_an_analysis(client):
    pid = _project(client, analyze=False)
    res = client.get(f"/api/projects/{pid}/geometry")
    assert res.status_code == 409 and "Run the analysis" in res.json()["detail"]


def test_overlap_is_reported_and_blocks_regeneration_without_touching_the_design(client):
    pid = _project(client)
    points_before = _points(client, pid)

    # Stretch the living room across the kitchen
    geo = client.patch(f"/api/projects/{pid}/rooms/room_living", json={"bounds": [0.06, 0.06, 0.80, 0.48]}).json()
    assert geo["can_generate"] is False
    overlap = next(i for i in geo["issues"] if i["code"] == "rooms_overlap" and i["severity"] == "error")
    assert set(overlap["entity_ids"]) == {"room_living", "room_kitchen"}

    res = client.post(f"/api/projects/{pid}/regenerate")
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "Geometry check failed" in detail["message"] and "overlap" in detail["message"]
    assert any(i["code"] == "rooms_overlap" for i in detail["issues"])
    # The previous design is still there and still "completed"
    assert _points(client, pid) == points_before
    assert client.get(f"/api/projects/{pid}/analysis/status").json()["status"] == "completed"

    # Fix it and regenerate
    fixed = client.patch(f"/api/projects/{pid}/rooms/room_living", json={"bounds": [0.06, 0.06, 0.52, 0.48]}).json()
    assert fixed["can_generate"] is True
    assert client.post(f"/api/projects/{pid}/regenerate").status_code == 200


def test_door_editing(client):
    pid = _project(client)
    geo = _geo(client, pid)
    door = _doors(geo, "room_master")[0]
    assert door["wall"] == "east"

    # Move to the west wall, hinge on the other side, opening outwards
    res = client.patch(
        f"/api/projects/{pid}/doors/{door['id']}",
        json={"wall": "west", "position": 0.25, "swing_direction": "out_of_room", "strike_side": "north"},
    )
    assert res.status_code == 200
    moved = next(f for f in res.json()["features"] if f["id"] == door["id"])
    assert moved["wall"] == "west" and moved["swing_direction"] == "out_of_room" and moved["is_manual"]
    assert moved["door_position"][0] == pytest.approx(0.06, abs=1e-3)
    assert moved["strike_point"][1] < moved["hinge_point"][1]            # strike on the north end
    assert not any(i["code"] == "door_not_on_wall" for i in res.json()["issues"])

    # Delete: room is left without a door -> warning, not an error
    res = client.delete(f"/api/projects/{pid}/doors/{door['id']}")
    assert res.status_code == 200
    assert any(i["code"] == "room_no_door" and i["entity_ids"] == ["room_master"] for i in res.json()["issues"])
    assert res.json()["can_generate"] is True

    # Add one back on the north wall
    res = client.post(f"/api/projects/{pid}/doors", json={"room_id": "room_master", "wall": "north", "position": 0.5})
    assert res.status_code == 201
    new = _doors(res.json(), "room_master")[0]
    assert new["id"] and new["wall"] == "north" and new["strike_side"] == "east"
    assert new["hinge_point"][0] < new["door_position"][0] < new["strike_point"][0]
    assert not any(i["code"] == "room_no_door" and i["entity_ids"] == ["room_master"] for i in res.json()["issues"])


def test_add_and_delete_room_flow_through_regeneration(client):
    pid = _project(client)
    # An extra cupboard-sized room tucked under the corridor
    res = client.post(f"/api/projects/{pid}/rooms", json={"name": "Store Room", "bounds": [0.62, 0.48, 0.80, 0.54]})
    assert res.status_code == 201
    store = next(r for r in res.json()["rooms"] if r["name"] == "Store Room")
    assert store["id"].startswith("room_manual_") and store["is_manual"]

    regen = client.post(f"/api/projects/{pid}/regenerate").json()
    assert any(p["room_id"] == store["id"] for p in regen["electrical_points"])

    res = client.delete(f"/api/projects/{pid}/rooms/room_kitchen")
    assert all(r["id"] != "room_kitchen" for r in res.json()["rooms"])
    assert not any(f["room_id"] == "room_kitchen" for f in res.json()["features"])
    regen = client.post(f"/api/projects/{pid}/regenerate").json()
    assert not any(p["room_id"] == "room_kitchen" for p in regen["electrical_points"])
    assert all(p["circuit_id"] in {c["id"] for c in regen["circuits"]} for p in regen["electrical_points"])


def test_regenerate_keeps_manual_equipment(client):
    pid = _project(client)
    client.post(f"/api/projects/{pid}/points", json={"type": "twin_socket", "x_ratio": 0.2, "y_ratio": 0.2})
    client.patch(f"/api/projects/{pid}/rooms/room_bed1", json={"name": "Guest Bedroom"})
    regen = client.post(f"/api/projects/{pid}/regenerate").json()
    manual = [p for p in regen["electrical_points"] if p["is_manual"]]
    assert len(manual) == 1 and manual[0]["room_name"] == "Living Room"


def test_regenerate_needs_an_analysis(client):
    pid = _project(client, analyze=False)
    assert client.post(f"/api/projects/{pid}/regenerate").status_code == 409
    assert client.post("/api/projects/missing/regenerate").status_code == 404


def test_reanalysis_will_not_silently_discard_corrections(client):
    pid = _project(client)
    client.patch(f"/api/projects/{pid}/rooms/room_bed1", json={"name": "Guest Bedroom"})

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 409 and "regenerate" in res.json()["detail"].lower()
    assert _room(_geo(client, pid), "room_bed1")["name"] == "Guest Bedroom"

    res = client.post(f"/api/projects/{pid}/analyze?reset_geometry=true")
    assert res.status_code == 200
    geo = _geo(client, pid)
    assert _room(geo, "room_bed1")["name"] == "Bedroom 1" and geo["reviewed"] is False


def test_ai_geometry_errors_stop_the_pipeline_and_can_be_fixed_in_the_editor(client, monkeypatch):
    bad = VisionAnalysisResult(
        rooms=[
            RoomObservation(id="a", name="Living Room", confidence=0.9, bounds=[0.05, 0.05, 0.60, 0.50]),
            RoomObservation(id="b", name="Kitchen", confidence=0.9, bounds=[0.40, 0.05, 0.95, 0.50]),   # overlaps living
        ],
        architectural_features=[
            ArchitecturalFeature(type="door", room="Living Room", confidence=0.9, door_position=[0.3, 0.30]),   # mid-room, not on a wall
            ArchitecturalFeature(type="door", room="Kitchen", confidence=0.9, door_position=[0.95, 0.3], wall="east"),
        ],
    )

    async def fake_vision(**kwargs):
        return bad

    monkeypatch.setattr(VisionService, "analyze_floor_plan", staticmethod(fake_vision))
    pid = _project(client, analyze=False)

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 422
    detail = res.json()["detail"]
    codes = {i["code"] for i in detail["issues"] if i["severity"] == "error"}
    assert {"rooms_overlap", "door_not_on_wall"} <= codes
    assert "Geometry check failed" in detail["message"]

    status = client.get(f"/api/projects/{pid}/analysis/status").json()
    assert status["status"] == "failed" and status["current_step"] == "validating_geometry"
    assert "Geometry check failed" in status["error_message"]
    # No equipment was invented
    assert client.get(f"/api/projects/{pid}/analysis").json()["electrical_points"] == []

    # The detected rooms / doors are available for correction
    geo = _geo(client, pid)
    assert geo["can_generate"] is False and len(geo["rooms"]) == 2
    door = next(f for f in geo["features"] if f["room"] == "Living Room")

    client.patch(f"/api/projects/{pid}/rooms/b", json={"bounds": [0.60, 0.05, 0.95, 0.50]})
    fixed = client.patch(f"/api/projects/{pid}/doors/{door['id']}", json={"wall": "south", "position": 0.4}).json()
    assert fixed["can_generate"] is True

    regen = client.post(f"/api/projects/{pid}/regenerate")
    assert regen.status_code == 200
    body = regen.json()
    assert body["status"] == "completed" and len(body["electrical_points"]) > 0
    assert body["geometry_reviewed"] is True
