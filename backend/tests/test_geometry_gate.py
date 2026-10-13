import io

from PIL import Image

from app.models.analysis import Analysis
from app.schemas.floor_plan import ArchitecturalFeature, RoomObservation, VisionAnalysisResult
from app.services.vision_service import VisionService


def _project(client):
    pid = client.post("/api/projects", json={"name": "Gate Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    return pid


def _bad_result():
    return VisionAnalysisResult(
        rooms=[
            RoomObservation(id="a", name="Living Room", confidence=0.9, bounds=[0.05, 0.05, 0.60, 0.50]),
            RoomObservation(id="b", name="Kitchen", confidence=0.9, bounds=[0.40, 0.05, 0.95, 0.50]),   # overlaps the living room
        ],
        architectural_features=[
            ArchitecturalFeature(type="door", room="Living Room", confidence=0.9, door_position=[0.3, 0.30]),   # mid-room
        ],
    )


def test_bad_geometry_stops_generation_and_reports_every_problem(client, monkeypatch):
    async def fake_vision(**kwargs):
        return _bad_result()

    monkeypatch.setattr(VisionService, "analyze_floor_plan", staticmethod(fake_vision))
    pid = _project(client)

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 422
    detail = res.json()["detail"]
    errors = {i["code"] for i in detail["issues"] if i["severity"] == "error"}
    assert {"rooms_overlap", "door_not_on_wall"} <= errors
    assert detail["message"].startswith("Geometry check failed with 2 error(s)")

    status = client.get(f"/api/projects/{pid}/analysis/status").json()
    assert status["status"] == "failed" and status["current_step"] == "validating_geometry"

    # No equipment was invented from the bad geometry, but the detected rooms and doors are kept for correction
    body = client.get(f"/api/projects/{pid}/analysis").json()
    assert body["electrical_points"] == [] and body["circuits"] == [] and body["boq_items"] == []
    assert len(body["rooms"]) == 2 and all(f["id"] for f in body["architectural_features"])
    assert {i["code"] for i in body["geometry_issues"]} >= {"rooms_overlap", "door_not_on_wall"}


def test_clean_geometry_passes_the_gate_and_warnings_do_not_block(client):
    pid = _project(client)
    res = client.post(f"/api/projects/{pid}/analyze")        # mock provider: a valid plan
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed" and len(body["electrical_points"]) > 0
    assert body["geometry_reviewed"] is False and body["geometry_needs_regeneration"] is False
    assert not any(i["severity"] == "error" for i in body["geometry_issues"])


def test_reanalysis_is_refused_when_rooms_were_corrected_by_a_user(client, db_session):
    pid = _project(client)
    assert client.post(f"/api/projects/{pid}/analyze").status_code == 200

    analysis = db_session.query(Analysis).filter(Analysis.project_id == pid).first()
    analysis.geometry_reviewed = True            # what the room / door editor sets
    db_session.commit()

    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 409 and "corrected" in res.json()["detail"]
    assert client.post(f"/api/projects/{pid}/analyze?reset_geometry=true").status_code == 200
    db_session.refresh(analysis)
    assert analysis.geometry_reviewed is False
