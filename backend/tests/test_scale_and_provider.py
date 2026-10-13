import asyncio
import io

import pytest
from PIL import Image

from app.core.config import settings
from app.services.vision_service import VisionProviderError, VisionService


def _make_project_with_plan(client, width=1000, height=500):
    pid = client.post(
        "/api/projects",
        json={"name": "Scale Test", "client": "Client", "location": "Kigali"},
    ).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    res = client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    assert res.status_code == 200
    return pid


def _cal(ax, ay, bx, by, mm):
    return {
        "point_a": {"x_ratio": ax, "y_ratio": ay},
        "point_b": {"x_ratio": bx, "y_ratio": by},
        "real_distance_mm": mm,
    }


def test_calibrate_scale_computes_mm_per_pixel(client):
    pid = _make_project_with_plan(client)
    # 0.1 -> 0.6 of 1000 px width = 500 px, representing 10 m
    res = client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 10000))
    assert res.status_code == 200
    body = res.json()
    assert body["scale_mm_per_pixel"] == pytest.approx(20.0)
    assert body["reference_pixels"] == pytest.approx(500.0)
    project = client.get(f"/api/projects/{pid}").json()
    assert project["is_scale_calibrated"] is True
    assert project["scale_mm_per_pixel"] == pytest.approx(20.0)


def test_calibrate_rejects_close_points_and_implausible_scale(client):
    pid = _make_project_with_plan(client)
    assert client.put(f"/api/projects/{pid}/scale", json=_cal(0.5, 0.5, 0.501, 0.5, 1000)).status_code == 422
    # 500 px for 1 km => 2000 mm/px
    assert client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 1_000_000)).status_code == 422


def test_calibrate_requires_plan(client):
    pid = client.post("/api/projects", json={"name": "No Plan", "client": "Client", "location": "Kigali"}).json()["id"]
    assert client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 5000)).status_code == 400


def test_reupload_resets_calibration(client):
    pid = _make_project_with_plan(client)
    client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 10000))
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p2.png", buf, "image/png")})
    assert client.get(f"/api/projects/{pid}").json()["is_scale_calibrated"] is False
    assert client.get(f"/api/projects/{pid}/scale").status_code == 404


def test_clear_scale(client):
    pid = _make_project_with_plan(client)
    client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 10000))
    assert client.delete(f"/api/projects/{pid}/scale").status_code == 204
    assert client.get(f"/api/projects/{pid}").json()["is_scale_calibrated"] is False


def test_analysis_uses_calibrated_scale(client):
    pid = _make_project_with_plan(client)
    client.put(f"/api/projects/{pid}/scale", json=_cal(0.1, 0.5, 0.6, 0.5, 10000))
    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 200
    transform = res.json()["canonical_geometry"]["transform"]
    assert transform["is_scale_verified"] is True
    assert transform["scale_status"] == "user_calibrated"
    assert transform["scale_mm_per_pixel"] == pytest.approx(20.0)


def test_uncalibrated_analysis_stays_unverified_and_flags_demo_data(client):
    pid = _make_project_with_plan(client)
    body = client.post(f"/api/projects/{pid}/analyze").json()
    assert body["canonical_geometry"]["transform"]["is_scale_verified"] is False
    assert any("DEMO DATA" in w for w in body["warnings"])


def test_real_provider_without_key_fails_instead_of_mock(client, monkeypatch):
    pid = _make_project_with_plan(client)
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 502
    status = client.get(f"/api/projects/{pid}/analysis/status").json()
    assert status["status"] == "failed"
    assert "GEMINI_API_KEY" in status["error_message"]


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "bogus")
    with pytest.raises(VisionProviderError):
        asyncio.run(VisionService.analyze_floor_plan("x.png"))
