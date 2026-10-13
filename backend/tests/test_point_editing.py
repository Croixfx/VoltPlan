import io

import pytest
from PIL import Image

from app.schemas.electrical import ElectricalPoint
from app.schemas.floor_plan import RoomObservation
from app.services.point_edit_service import PointEditService

# Mock-provider rooms (normalized bounds):
#   Living Room [0.06,0.06,0.52,0.48]   Kitchen & Dining [0.54,0.06,0.94,0.48]
#   Central Corridor [0.42,0.48,0.60,0.62]   Master Bedroom [0.06,0.54,0.44,0.94]
#   En-Suite Bathroom [0.46,0.64,0.66,0.94]  Bedroom 1 [0.68,0.54,0.94,0.94]
LIVING = (0.2, 0.2)
BATHROOM = (0.55, 0.8)
BEDROOM = (0.8, 0.7)
OUTSIDE = (0.02, 0.02)


def _project(client, analyze=True):
    pid = client.post("/api/projects", json={"name": "Edit Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    if analyze:
        assert client.post(f"/api/projects/{pid}/analyze").status_code == 200
    return pid


def _add(client, pid, type_id, pos, **extra):
    return client.post(
        f"/api/projects/{pid}/points",
        json={"type": type_id, "x_ratio": pos[0], "y_ratio": pos[1], **extra},
    )


def _analysis(client, pid):
    return client.get(f"/api/projects/{pid}/analysis").json()


def _boq_qty(analysis, code):
    return next((i["quantity"] for i in analysis["boq_items"] if i["item_code"] == code), 0)


def test_add_point_is_manual_and_regenerates_everything(client):
    pid = _project(client)
    before = _analysis(client, pid)

    res = _add(client, pid, "twin_socket", LIVING)
    assert res.status_code == 201
    after = res.json()

    new = [p for p in after["electrical_points"] if p["is_manual"]]
    assert len(new) == 1
    pt = new[0]
    assert pt["manual_origin"] == "added" and pt["placement_status"] == "manual"
    assert pt["room_name"] == "Living Room" and pt["x_mm"] is not None
    assert pt["circuit_id"] in {c["id"] for c in after["circuits"]}

    assert _boq_qty(after, "SKT-13A-TWIN") == _boq_qty(before, "SKT-13A-TWIN") + 1
    assert after["cost_estimate"]["grand_total_rwf"] > before["cost_estimate"]["grand_total_rwf"]
    # Persisted: a fresh read agrees
    assert len(_analysis(client, pid)["electrical_points"]) == len(before["electrical_points"]) + 1


@pytest.mark.parametrize(
    "type_id,pos,fragment",
    [
        ("twin_socket", OUTSIDE, "outside every detected room"),
        ("twin_socket", BATHROOM, "not allowed in"),
        ("cooker_point", BEDROOM, "can only be placed in"),
        ("smoke_detector", BATHROOM, "not allowed in"),
        ("outdoor_light", LIVING, "can only be placed in"),
        ("flux_capacitor", LIVING, "Unknown equipment type"),
    ],
)
def test_invalid_placements_are_rejected_with_clear_errors(client, type_id, pos, fragment):
    pid = _project(client)
    before = _analysis(client, pid)
    res = _add(client, pid, type_id, pos)
    assert res.status_code == 422
    assert fragment in res.json()["detail"]
    assert len(_analysis(client, pid)["electrical_points"]) == len(before["electrical_points"])


def test_edit_requires_completed_analysis(client):
    pid = _project(client, analyze=False)
    res = _add(client, pid, "twin_socket", LIVING)
    assert res.status_code == 409
    assert "Run the analysis" in res.json()["detail"]
    assert _add(client, "missing", "twin_socket", LIVING).status_code == 404


def test_only_one_distribution_board(client):
    pid = _project(client)
    assert _add(client, pid, "distribution_board", LIVING).status_code == 201
    res = _add(client, pid, "distribution_board", BEDROOM)
    assert res.status_code == 409


def test_move_auto_point_becomes_manual_and_records_origin(client):
    pid = _project(client)
    point = next(p for p in _analysis(client, pid)["electrical_points"] if p["type"] == "lighting" and p["room_name"] == "Living Room")

    res = client.patch(f"/api/projects/{pid}/points/{point['id']}", json={"x_ratio": 0.3, "y_ratio": 0.25})
    assert res.status_code == 200
    moved = next(p for p in res.json()["electrical_points"] if p["id"] == point["id"])
    assert moved["is_manual"] and moved["manual_origin"] == "moved"
    assert (moved["x_ratio"], moved["y_ratio"]) == (0.3, 0.25)
    assert (moved["original_x_ratio"], moved["original_y_ratio"]) == (point["x_ratio"], point["y_ratio"])
    assert moved["x_mm"] != point["x_mm"]
    assert moved["placement_status"] == "manual"


def test_move_into_forbidden_room_is_rejected_and_point_unchanged(client):
    pid = _project(client)
    sock = next(p for p in _analysis(client, pid)["electrical_points"] if p["type"] == "twin_socket")
    res = client.patch(f"/api/projects/{pid}/points/{sock['id']}", json={"x_ratio": BATHROOM[0], "y_ratio": BATHROOM[1]})
    assert res.status_code == 422 and "not allowed in" in res.json()["detail"]
    same = next(p for p in _analysis(client, pid)["electrical_points"] if p["id"] == sock["id"])
    assert (same["x_ratio"], same["y_ratio"]) == (sock["x_ratio"], sock["y_ratio"])
    assert not same["is_manual"]


def test_move_validation_errors(client):
    pid = _project(client)
    pts = _analysis(client, pid)["electrical_points"]
    light = next(p for p in pts if p["type"] == "lighting")
    url = f"/api/projects/{pid}/points/{light['id']}"
    assert client.patch(url, json={"x_ratio": 0.3}).status_code == 422          # needs both coordinates
    assert client.patch(url, json={"x_ratio": 0.02, "y_ratio": 0.02}).status_code == 422  # outside rooms
    assert client.patch(url, json={"x_ratio": 1.5, "y_ratio": 0.2}).status_code == 422     # schema bounds
    assert client.patch(f"/api/projects/{pid}/points/pt_999", json={"x_ratio": 0.3, "y_ratio": 0.2}).status_code == 404


def test_change_quantity_marks_manual(client):
    pid = _project(client)
    sock = next(p for p in _analysis(client, pid)["electrical_points"] if p["type"] == "twin_socket")
    res = client.patch(f"/api/projects/{pid}/points/{sock['id']}", json={"quantity": 3})
    assert res.status_code == 200
    updated = next(p for p in res.json()["electrical_points"] if p["id"] == sock["id"])
    assert updated["quantity"] == 3 and updated["is_manual"]


def test_delete_point_regenerates_boq(client):
    pid = _project(client)
    before = _analysis(client, pid)
    sock = next(p for p in before["electrical_points"] if p["type"] == "twin_socket")
    res = client.delete(f"/api/projects/{pid}/points/{sock['id']}")
    assert res.status_code == 200
    after = res.json()
    assert all(p["id"] != sock["id"] for p in after["electrical_points"])
    assert _boq_qty(after, "SKT-13A-TWIN") == _boq_qty(before, "SKT-13A-TWIN") - sock["quantity"]
    assert client.delete(f"/api/projects/{pid}/points/{sock['id']}").status_code == 404


def test_manual_points_survive_reanalysis(client):
    pid = _project(client)
    added = _add(client, pid, "smoke_detector", (0.3, 0.3)).json()
    added_pt = next(p for p in added["electrical_points"] if p["is_manual"])

    pts = added["electrical_points"]
    light = next(p for p in pts if p["type"] == "lighting" and p["room_name"] == "Living Room")
    n_lights = sum(1 for p in pts if p["type"] == "lighting")
    client.patch(f"/api/projects/{pid}/points/{light['id']}", json={"x_ratio": 0.35, "y_ratio": 0.35})

    assert client.post(f"/api/projects/{pid}/analyze").status_code == 200
    again = _analysis(client, pid)
    manual = [p for p in again["electrical_points"] if p["is_manual"]]

    assert {p["manual_origin"] for p in manual} == {"added", "moved"}
    assert any(p["type"] == "smoke_detector" and p["x_ratio"] == added_pt["x_ratio"] for p in manual)
    moved = next(p for p in manual if p["manual_origin"] == "moved")
    assert (moved["x_ratio"], moved["y_ratio"]) == (0.35, 0.35)
    # The moved light replaced its auto counterpart instead of duplicating it
    assert sum(1 for p in again["electrical_points"] if p["type"] == "lighting") == n_lights
    assert any("preserved" in w for w in again["warnings"])
    # Everything still maps to a real circuit
    ids = {c["id"] for c in again["circuits"]}
    assert all(p["circuit_id"] in ids for p in again["electrical_points"])


def test_merge_drops_manual_point_that_is_no_longer_in_a_valid_room():
    rooms = [RoomObservation(id="r1", name="Living Room", confidence=0.9, bounds=[0.0, 0.0, 0.5, 0.5])]
    manual_ok = ElectricalPoint(
        id="pt_010", room_id="old", room_name="Old", type="twin_socket", power_rating_w=250.0,
        x_ratio=0.2, y_ratio=0.2, rule_reference="x", is_manual=True, manual_origin="added",
    ).model_dump()
    manual_outside = {**manual_ok, "id": "pt_011", "x_ratio": 0.9, "y_ratio": 0.9}

    points, notes = PointEditService.merge_manual_points([], [manual_ok, manual_outside], rooms)
    assert [p.x_ratio for p in points] == [0.2]
    assert points[0].room_id == "r1" and points[0].room_name == "Living Room"
    assert any("no longer inside a detected room" in n for n in notes)
