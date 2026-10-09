import pytest
from app.schemas.floor_plan import RoomObservation
from app.services.electrical_engine import ElectricalEngine
from app.services.circuit_engine import CircuitEngine


def test_circuit_engine_grouping_and_phases():
    rooms = [
        RoomObservation(
            id="room_living",
            name="Living Room",
            room_type="living",
            area_m2=24.0,
            confidence=0.95,
            bounds=[0.05, 0.05, 0.45, 0.45],
        ),
        RoomObservation(
            id="room_kitchen",
            name="Kitchen",
            room_type="kitchen",
            area_m2=12.0,
            confidence=0.90,
            bounds=[0.55, 0.05, 0.90, 0.45],
        ),
        RoomObservation(
            id="room_bed",
            name="Bedroom 1",
            room_type="bedroom",
            area_m2=16.0,
            confidence=0.92,
            bounds=[0.05, 0.55, 0.45, 0.90],
        ),
    ]

    points = ElectricalEngine.generate_recommendations(rooms, building_type="Residential")
    updated_points, circuits = CircuitEngine.generate_circuits(points, standard_name="RS IEC 60364")

    # Verify circuits were generated
    assert len(circuits) >= 3

    # All points must now have an assigned circuit_id
    for pt in updated_points:
        assert pt.circuit_id is not None
        assert any(c.id == pt.circuit_id for c in circuits)

    # Lighting circuit verification
    lgt_circuits = [c for c in circuits if c.circuit_type == "lighting"]
    assert len(lgt_circuits) >= 1
    for c in lgt_circuits:
        assert "1.5 mm²" in (c.cable or "")
        assert "10A" in (c.protection or "")
        assert c.status == "CALCULATED"

    # Kitchen power circuit verification (dedicated)
    kit_circuits = [c for c in circuits if "KIT" in c.id or "Kitchen" in c.name]
    assert len(kit_circuits) >= 1
    for c in kit_circuits:
        assert "2.5 mm²" in (c.cable or "")

    # Cooker appliance circuit
    cooker_circuits = [c for c in circuits if "CKR" in c.id or "Cooker" in c.name]
    assert len(cooker_circuits) == 1
    assert "6.0 mm²" in (cooker_circuits[0].cable or "")
    assert "32A" in (cooker_circuits[0].protection or "")

    # Phase balancing across L1, L2, L3
    assigned_phases = set(c.phase for c in circuits)
    assert len(assigned_phases) > 1, "Circuits should be balanced across multiple phases"
