import json

import pytest
from PIL import Image

from app.core.config import settings
from tools import evaluate_plans as ev


@pytest.fixture
def plan(tmp_path):
    path = tmp_path / "villa.png"
    Image.new("RGB", (800, 600), (255, 255, 255)).save(path)
    return str(path)


def test_report_compares_rooms_names_equipment_and_demand(client, plan):
    reference = {
        "rooms": [
            {"name": "Living Room", "bounds": [0.06, 0.06, 0.52, 0.48],
             "equipment": {"lighting": 2, "twin_socket": 4}},
            {"name": "Study", "bounds": [0.68, 0.54, 0.94, 0.94], "equipment": {"twin_socket": 4}},   # AI says "Bedroom 1"
            {"name": "Garage", "bounds": [0.0, 0.96, 0.2, 1.0]},                                       # not detected
        ],
        "doors": 6,
        "max_demand_a": 50,
    }
    rep = ev.evaluate_plan(client, plan, reference)

    assert rep["pipeline"] == "completed" and rep["geometry_errors"] == []
    rooms = rep["rooms"]
    assert rooms["matched"] == 2 and rooms["reference"] == 3
    assert rooms["wrong_names"] == [{"reference": "Study", "detected": "Bedroom 1"}]
    assert rooms["missed"] == ["Garage"]
    assert "Central Corridor" in rooms["invented"]
    assert rep["doors"] == {"reference": 6, "detected": 6}

    eq = rep["equipment"]
    assert eq["by_type"]["lighting"]["electrician"] == 2
    assert eq["exact_match"] is not None and 0 <= eq["exact_match"] <= eq["within_one_of_electrician"] <= 1
    living = next(r for r in eq["per_room"] if r["room"] == "Living Room")
    assert living["matched"] and "smoke_detector" in living["differences"]      # VoltPlan proposes one, electrician did not list it

    calc = rep["calculations"]
    assert calc["voltage_drop_status"] == "not_calculated" and "scale" in calc["voltage_drop_reason"]
    assert calc["cable_capacity_failing"] == []                    # capacity does not need a scale or a board
    assert calc["electrician_max_demand_a"] == 50
    assert calc["max_demand_difference_percent"] == pytest.approx((calc["max_demand_a"] - 50) / 50 * 100, abs=0.1)


def test_scale_and_board_in_the_reference_enable_voltage_drop(client, plan):
    reference = {
        "scale": {"point_a": [0.1, 0.5], "point_b": [0.6, 0.5], "real_distance_mm": 10000},
        "rooms": [{"name": "Living Room"}],
        "distribution_board": {"x_ratio": 0.5, "y_ratio": 0.55},
    }
    rep = ev.evaluate_plan(client, plan, reference)
    assert rep["scale_calibrated"] is True and rep["distribution_board_placed"] is True
    assert rep["calculations"]["voltage_drop_status"] == "calculated"


def test_geometry_blocked_plans_are_reported_not_hidden(client, plan, monkeypatch):
    from app.schemas.floor_plan import RoomObservation, VisionAnalysisResult
    from app.services.vision_service import VisionService

    overlapping = VisionAnalysisResult(rooms=[
        RoomObservation(id="a", name="Living Room", confidence=0.9, bounds=[0.05, 0.05, 0.6, 0.5]),
        RoomObservation(id="b", name="Kitchen", confidence=0.9, bounds=[0.4, 0.05, 0.95, 0.5]),
    ])

    async def fake(**kwargs):
        return overlapping

    monkeypatch.setattr(VisionService, "analyze_floor_plan", staticmethod(fake))
    rep = ev.evaluate_plan(client, plan, {"rooms": [{"name": "Living Room"}, {"name": "Kitchen"}]})
    assert rep["pipeline"] == "blocked_by_geometry_checks"
    assert any("overlap" in m for m in rep["geometry_errors"])
    assert rep["rooms"]["matched"] == 2          # rooms are still compared so the failure can be diagnosed
    assert "equipment" not in rep


def test_markdown_report_is_readable(client, plan):
    rep = ev.evaluate_plan(client, plan, {"rooms": [{"name": "Living Room", "equipment": {"lighting": 2}}]})
    md = ev.render_markdown([rep], "mock")
    assert "MOCK PROVIDER" in md and "## villa" in md and "| lighting | 2 |" in md
    assert "Cable capacity" in md and "all circuits pass" in md


def test_real_provider_without_a_key_refuses_to_run(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(SystemExit) as exc:
        ev.run(str(tmp_path), "gemini", str(tmp_path / "out"))
    assert "Refusing to fall back to mock" in str(exc.value)


def test_empty_directory_explains_the_expected_layout(tmp_path):
    with pytest.raises(SystemExit) as exc:
        ev.run(str(tmp_path), "mock", str(tmp_path / "out"))
    assert "reference.json" in str(exc.value)


def test_run_writes_reports(tmp_path, monkeypatch):
    Image.new("RGB", (800, 600), (255, 255, 255)).save(tmp_path / "plan.png")
    (tmp_path / "plan.reference.json").write_text(json.dumps({"rooms": [{"name": "Living Room"}]}))
    reports = ev.run(str(tmp_path), "mock", str(tmp_path / "report"))
    assert len(reports) == 1 and reports[0]["pipeline"] == "completed"
    assert (tmp_path / "report.md").exists() and json.loads((tmp_path / "report.json").read_text())["provider"] == "mock"
