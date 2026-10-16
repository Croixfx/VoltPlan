import io

import pytest
from PIL import Image

from app.core.config import settings
from app.services import scale_suggestion_service as svc
from app.services.scale_suggestion_service import _validate


def _good(**over):
    base = {"found": True, "point_a": [100, 500], "point_b": [600, 500], "label_text": "10000", "value": 10000,
            "unit": "mm", "confidence": 0.9, "note": "overall width"}
    base.update(over)
    return base


def test_valid_reading_becomes_a_suggestion():
    s = _validate(_good(), 1000, 800)
    assert s["real_distance_mm"] == 10000.0
    assert s["scale_mm_per_pixel"] == pytest.approx(20.0)  # 500 px for 10 m
    assert s["point_a"] == {"x_ratio": 0.1, "y_ratio": 0.5}


def test_units_are_converted():
    assert _validate(_good(value=1000, unit="cm"), 1000, 800)["real_distance_mm"] == 10000.0
    assert _validate(_good(value=10, unit="m"), 1000, 800)["real_distance_mm"] == 10000.0


@pytest.mark.parametrize("raw, fragment", [
    ({"found": False, "note": "No dimensions on this drawing"}, "No dimensions"),
    (_good(unit="ft"), "not one of"),
    (_good(point_a=[100, 1400]), "outside"),
    (_good(value=-5), "positive"),
    (_good(confidence=0.3), "not confident"),
    (_good(point_a=[500, 500], point_b=[502, 500]), "too close"),
    (_good(value=10_000_000), "longer than 200 m"),
    (_good(value=1), "not plausible"),
    ({"found": True}, "incomplete"),
])
def test_unusable_readings_are_refused_with_a_reason(raw, fragment):
    with pytest.raises(ValueError) as e:
        _validate(raw, 1000, 800)
    assert fragment in str(e.value)


def _project_with_plan(client):
    pid = client.post("/api/projects", json={
        "name": "Scale test", "client": "Some Client", "building_type": "Residential", "location": "Kigali",
        "standard": "RS IEC 60364", "notes": ""}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (1000, 800), "white").save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    return pid


def test_suggest_endpoint_returns_but_never_saves(client, monkeypatch):
    pid = _project_with_plan(client)
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    async def fake(_encoded):
        return _good()

    monkeypatch.setattr(svc, "_ask_gemini", fake)
    res = client.post(f"/api/projects/{pid}/scale/suggest")
    assert res.status_code == 200, res.text
    assert res.json()["real_distance_mm"] == 10000.0
    assert client.get(f"/api/projects/{pid}").json()["is_scale_calibrated"] is False


def test_suggest_endpoint_explains_when_nothing_is_readable(client, monkeypatch):
    pid = _project_with_plan(client)
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    async def fake(_encoded):
        return {"found": False, "note": "The drawing has no dimension lines."}

    monkeypatch.setattr(svc, "_ask_gemini", fake)
    res = client.post(f"/api/projects/{pid}/scale/suggest")
    assert res.status_code == 422
    assert "no dimension lines" in res.json()["detail"]


def test_suggest_with_the_demo_provider_says_so(client):
    pid = _project_with_plan(client)
    res = client.post(f"/api/projects/{pid}/scale/suggest")
    assert res.status_code == 422
    assert "by hand" in res.json()["detail"]


def test_suggest_needs_a_plan_and_a_project(client):
    pid = client.post("/api/projects", json={
        "name": "No plan yet", "client": "Some Client", "building_type": "Residential", "location": "Kigali",
        "standard": "RS IEC 60364", "notes": ""}).json()["id"]
    assert client.post(f"/api/projects/{pid}/scale/suggest").status_code == 400
    assert client.post("/api/projects/nope/scale/suggest").status_code == 404
