import pytest
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.services.electrical_engine import ElectricalEngine


def test_living_room_recommendations():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_living",
        name="Living Room",
        room_type="living",
        area_m2=25.0,
        confidence=0.95,
        bounds=[0.05, 0.05, 0.45, 0.45],
    )

    points = engine.generate_recommendations([room], building_type="Residential")

    # Verify lighting points generated (for 25m2 -> 2 luminaires)
    lighting = [p for p in points if p.type == "lighting"]
    assert len(lighting) == 2
    for p in lighting:
        assert p.recommended_cable == "3 x 1.5 mm² Cu/PVC"
        assert p.recommended_protection == "10A Type B MCB"
        assert p.status == "RECOMMENDED"

    # Verify switch points generated
    switches = [p for p in points if "switch" in p.type]
    assert len(switches) >= 1

    # Verify socket points generated (Living room standard -> 4 sockets)
    sockets = [p for p in points if p.type == "twin_socket"]
    assert len(sockets) == 4
    for p in sockets:
        assert p.recommended_cable == "3 x 2.5 mm² Cu/PVC"
        assert p.recommended_protection == "20A Type B MCB + 30mA RCD"


def test_bathroom_safety_zones_iec_60364_701():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_bath",
        name="Master Bathroom",
        room_type="bathroom",
        area_m2=6.0,
        confidence=0.90,
        bounds=[0.55, 0.05, 0.75, 0.30],
    )

    points = engine.generate_recommendations([room], building_type="Residential")

    # Sockets in standard bathroom must not be standard twin sockets per IEC 60364-7-701
    standard_sockets = [p for p in points if p.type == "twin_socket"]
    assert len(standard_sockets) == 0, "Standard twin sockets are prohibited in bathroom per IEC 60364-7-701"

    # Must be shaver / protected socket requiring engineer review for zone compliance
    shaver_sockets = [p for p in points if p.type == "single_socket"]
    assert len(shaver_sockets) >= 1
    assert shaver_sockets[0].status == "REQUIRES_ENGINEER_REVIEW"
    assert "60364-7-701" in shaver_sockets[0].rule_reference


def test_kitchen_high_power_appliances():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_kitchen",
        name="Kitchen",
        room_type="kitchen",
        area_m2=14.0,
        confidence=0.92,
        bounds=[0.55, 0.35, 0.90, 0.70],
    )

    points = engine.generate_recommendations([room], building_type="Residential")
    point_types = [p.type for p in points]

    # Kitchen must have cooker dedicated point
    assert "cooker_point" in point_types
    cooker = next(p for p in points if p.type == "cooker_point")
    assert cooker.recommended_cable == "3 x 6.0 mm² Cu/PVC"
    assert "32A" in cooker.recommended_protection

    # Bathroom dedicated water heater test
    bath_room = RoomObservation(
        id="room_bath",
        name="Family Bathroom",
        room_type="bathroom",
        area_m2=8.0,
        confidence=0.92,
        bounds=[0.1, 0.1, 0.3, 0.3],
    )
    bath_points = engine.generate_recommendations([bath_room], building_type="Residential")
    bath_types = [p.type for p in bath_points]
    assert "water_heater" in bath_types
    heater = next(p for p in bath_points if p.type == "water_heater")
    assert "20A" in heater.recommended_protection


def test_missing_area_flags_engineer_review():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_unknown",
        name="Storage Room",
        room_type="other",
        area_m2=None,
        confidence=0.45,
        bounds=None,
    )

    points = engine.generate_recommendations([room], building_type="Residential")

    # Lighting point for room with unverified area must carry REQUIRES_ENGINEER_REVIEW status
    lighting = [p for p in points if p.type == "lighting"]
    assert len(lighting) >= 1
    assert lighting[0].status == "REQUIRES_ENGINEER_REVIEW"
    assert "REQUIRES ENGINEER REVIEW" in (lighting[0].review_notes or "")


def test_switch_spatial_rules_wall_attachment_and_door_strike():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_bed",
        name="Bedroom",
        area_m2=16.0,
        confidence=0.92,
        bounds=[0.10, 0.10, 0.40, 0.50],
    )
    door = ArchitecturalFeature(
        type="door",
        room="Bedroom",
        confidence=0.90,
        wall="north",
        door_position=[0.20, 0.10],
        strike_side="right",
        strike_point=[0.22, 0.115],
    )

    points = engine.generate_recommendations(
        rooms=[room],
        architectural_features=[door],
        building_type="Residential",
    )

    switches = [p for p in points if "switch" in p.type]
    assert len(switches) >= 1
    sw = switches[0]

    # Rule 1: Switch MUST attach to a wall—never float in open space
    # North wall y1 is 0.10, wall_inset is 0.015 -> y=0.115
    assert abs(sw.y_ratio - 0.115) < 0.005, f"Switch y={sw.y_ratio} not attached flush to North wall!"

    # Rule 2: Mount within 20 cm of door frame on handle/latch (strike) side
    assert abs(sw.x_ratio - 0.24) < 0.01, f"Switch x={sw.x_ratio} not at door strike side!"
    assert "strike" in (sw.review_notes or "").lower()


def test_switch_spatial_rule_fallback_attaches_to_wall():
    engine = ElectricalEngine()
    room = RoomObservation(
        id="room_living",
        name="Living Room",
        area_m2=24.0,
        confidence=0.90,
        bounds=[0.05, 0.05, 0.45, 0.45],
    )

    points = engine.generate_recommendations(
        rooms=[room],
        architectural_features=None,
        building_type="Residential",
    )

    switches = [p for p in points if "switch" in p.type]
    assert len(switches) >= 1
    sw = switches[0]

    # Must attach to a wall (distance to nearest wall <= 0.02, never floating)
    x1, y1, x2, y2 = 0.05, 0.05, 0.45, 0.45
    d_north = abs(sw.y_ratio - y1)
    d_south = abs(sw.y_ratio - y2)
    d_west = abs(sw.x_ratio - x1)
    d_east = abs(sw.x_ratio - x2)
    min_dist_to_wall = min(d_north, d_south, d_west, d_east)
    assert min_dist_to_wall <= 0.02, f"Switch at ({sw.x_ratio}, {sw.y_ratio}) is floating in open space!"

