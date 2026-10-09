import pytest
from app.schemas.floor_plan import RoomObservation
from app.services.electrical_engine import ElectricalEngine
from app.services.circuit_engine import CircuitEngine
from app.services.boq_engine import BoqEngine
from app.services.cost_service import CostService


def test_boq_and_cost_estimation():
    rooms = [
        RoomObservation(
            id="r1",
            name="Living Room",
            room_type="living",
            area_m2=20.0,
            confidence=0.9,
            bounds=[0.1, 0.1, 0.5, 0.5],
        ),
        RoomObservation(
            id="r2",
            name="Kitchen",
            room_type="kitchen",
            area_m2=10.0,
            confidence=0.9,
            bounds=[0.5, 0.1, 0.9, 0.5],
        ),
    ]

    points = ElectricalEngine.generate_recommendations(rooms, building_type="Residential")
    updated_points, circuits = CircuitEngine.generate_circuits(points, standard_name="RS IEC 60364")

    boq_items, materials_subtotal = BoqEngine.generate_boq(rooms, updated_points, circuits)

    # 1. Verify items are generated
    assert len(boq_items) > 5
    assert materials_subtotal > 0

    # 2. Check essential categories
    categories = set(i.category for i in boq_items)
    assert "Cables & Conduits" in categories
    assert "Sockets & Switches" in categories
    assert "Distribution & Switchgear" in categories

    # 3. Verify item totals sum up to materials_subtotal
    calc_subtotal = sum(i.total_price_rwf for i in boq_items)
    assert abs(calc_subtotal - materials_subtotal) < 0.1

    # 4. Verify cost estimation math (materials, labor 28%, contingency 12%)
    cost_est = CostService.calculate_cost_estimate(
        project_id="test_proj_1",
        materials_cost_rwf=materials_subtotal,
        labor_percentage=28.0,
        contingency_percentage=12.0,
    )

    assert cost_est.currency == "RWF"
    assert cost_est.materials_cost_rwf == round(materials_subtotal, 2)
    assert cost_est.labor_cost_rwf == round(materials_subtotal * 0.28, 2)
    assert cost_est.contingency_cost_rwf == round(materials_subtotal * 0.12, 2)
    assert cost_est.grand_total_rwf == round(cost_est.materials_cost_rwf + cost_est.labor_cost_rwf + cost_est.contingency_cost_rwf, 2)
    assert cost_est.is_labor_estimated is True
    assert cost_est.is_contingency_estimated is True
    assert len(cost_est.assumptions) >= 3
