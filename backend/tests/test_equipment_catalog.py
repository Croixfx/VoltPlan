import pytest

from app.catalog import (
    BoqLine,
    CircuitClass,
    EquipmentCategory,
    EquipmentSpec,
    Mount,
    all_equipment,
    get_equipment,
    register_equipment,
)
from app.schemas.electrical import ElectricalPoint
from app.schemas.floor_plan import RoomObservation
from app.services.boq_engine import BoqEngine
from app.services.circuit_engine import CircuitEngine
from app.services.electrical_engine import ElectricalEngine


def _room(rid, name, bounds, area=20.0):
    return RoomObservation(id=rid, name=name, room_type="other", area_m2=area, confidence=0.9, bounds=bounds)


def _rooms():
    return [
        _room("living", "Living Room", [0.05, 0.05, 0.45, 0.45], 24.0),
        _room("kitchen", "Kitchen", [0.55, 0.05, 0.9, 0.45], 12.0),
        _room("master", "Master Bedroom", [0.05, 0.55, 0.45, 0.9], 16.0),
        _room("bath", "Bathroom", [0.5, 0.55, 0.7, 0.9], 6.0),
        _room("corridor", "Central Corridor", [0.45, 0.45, 0.6, 0.55], 5.0),
        _room("veranda", "Veranda", [0.75, 0.55, 0.95, 0.9], 8.0),
        _room("office", "Home Office", [0.72, 0.1, 0.95, 0.4], 10.0),
    ]


def _run(building_type="Residential"):
    points = ElectricalEngine.generate_recommendations(_rooms(), building_type=building_type)
    points, circuits = CircuitEngine.generate_circuits(points)
    boq, _ = BoqEngine.generate_boq(_rooms(), points, circuits)
    return points, circuits, boq


def test_every_catalog_entry_is_consistent():
    ids = [e.type_id for e in all_equipment()]
    assert len(ids) == len(set(ids))
    for spec in all_equipment():
        assert spec.name and spec.rule_reference
        if spec.circuit_class == CircuitClass.DEDICATED:
            assert spec.dedicated is not None
        for line in spec.boq_lines:
            assert line.unit_price_rwf > 0 and line.qty_per_point > 0


def test_duplicate_registration_and_missing_dedicated_rejected():
    with pytest.raises(ValueError):
        register_equipment(get_equipment("lighting"))
    with pytest.raises(ValueError):
        register_equipment(EquipmentSpec(
            type_id="bogus_dedicated", name="x", category=EquipmentCategory.APPLIANCE, symbol="x",
            mount=Mount.WALL, mounting_height_mm=None, default_power_w=1.0,
            circuit_class=CircuitClass.DEDICATED, cable=None, protection=None, rule_reference="x",
        ))


def test_new_equipment_is_proposed_in_the_right_rooms():
    points, _, _ = _run()
    by_room = {}
    for p in points:
        by_room.setdefault(p.room_id, set()).add(p.type)

    assert "smoke_detector" in by_room["master"] and "smoke_detector" in by_room["living"]
    assert "smoke_detector" in by_room["corridor"]
    assert "smoke_detector" not in by_room["bath"]
    assert "extractor_fan" in by_room["bath"] and "extractor_fan" in by_room["kitchen"]
    assert "outdoor_light" in by_room["veranda"]
    assert "data_point" in by_room["office"] and "tv_point" in by_room["living"]
    # Residential: no escape lighting
    assert not any(p.type == "emergency_light" for p in points)


def test_emergency_lighting_only_for_non_residential_circulation():
    points, _, _ = _run(building_type="Commercial")
    emergency = [p for p in points if p.type == "emergency_light"]
    assert [p.room_id for p in emergency] == ["corridor"]


def test_wet_room_fan_requires_engineer_review():
    points, _, _ = _run()
    fan = next(p for p in points if p.type == "extractor_fan" and p.room_id == "bath")
    assert "REVIEW" in fan.status


def test_every_point_maps_to_a_real_circuit():
    points, circuits, _ = _run(building_type="Commercial")
    ids = {c.id for c in circuits}
    for p in points:
        assert p.circuit_id in ids, p.type


def test_circuit_classes_route_new_equipment():
    points, circuits, _ = _run(building_type="Commercial")
    by_id = {c.id: c for c in circuits}
    for p in points:
        if p.type in ("smoke_detector", "emergency_light"):
            assert p.circuit_id == "CKT-SAF-01"
        if p.type in ("extractor_fan", "outdoor_light"):
            assert by_id[p.circuit_id].circuit_type == "lighting"
        if p.type in ("data_point", "tv_point"):
            assert by_id[p.circuit_id].circuit_type == "elv"
    assert by_id["CKT-SAF-01"].protection.startswith("6A")


def test_boq_includes_catalog_lines_with_correct_quantities():
    points, _, boq = _run()
    by_code = {i.item_code: i for i in boq}
    n_smoke = sum(p.quantity for p in points if p.type == "smoke_detector")
    n_data = sum(p.quantity for p in points if p.type == "data_point")
    assert by_code["SAF-SMK-230V"].quantity == n_smoke
    assert by_code["COM-RJ45-C6"].quantity == n_data
    assert by_code["COM-CBL-C6"].quantity == n_data * 20
    assert by_code["LUM-OUT-WALL-IP65"].quantity == 1
    assert "SAF-EML-3H" not in by_code  # none placed in residential


def test_mcb_breakdown_follows_circuit_protection():
    _, circuits, boq = _run()
    mcb = next(i for i in boq if i.item_code == "MCB-1P-ASSORTED")
    n_with_rating = sum(1 for c in circuits if c.protection and c.protection[0].isdigit())
    assert mcb.quantity == n_with_rating
    assert "6A x1" in mcb.description  # safety circuit


def test_unknown_point_type_still_gets_a_circuit():
    pt = ElectricalPoint(id="x", room_id="r", room_name="Room", type="mystery", power_rating_w=10.0, rule_reference="r")
    pts, circuits = CircuitEngine.generate_circuits([pt])
    assert pts[0].circuit_id == "CKT-GEN-01"


def test_equipment_api(client):
    res = client.get("/api/equipment")
    assert res.status_code == 200
    ids = {e["type_id"] for e in res.json()}
    assert {"lighting", "smoke_detector", "data_point", "distribution_board"} <= ids

    only_safety = client.get("/api/equipment?category=safety").json()
    assert {e["type_id"] for e in only_safety} == {"smoke_detector", "emergency_light"}

    assert client.get("/api/equipment/smoke_detector").json()["circuit_class"] == "safety"
    assert client.get("/api/equipment/nope").status_code == 404
