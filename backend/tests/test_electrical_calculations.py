import io

import pytest
from PIL import Image

from app.schemas.electrical import Circuit, ElectricalPoint
from app.services import electrical_calculations as calc


def pt(pid, ptype, x_mm=0.0, y_mm=0.0, power=0.0, circuit=None, qty=1, room="Room"):
    return ElectricalPoint(id=pid, room_id="r", room_name=room, type=ptype, power_rating_w=power, quantity=qty,
                           x_mm=x_mm, y_mm=y_mm, circuit_id=circuit, rule_reference="x")


def ckt(cid, ctype, cable, protection, phase="L1", name=None):
    return Circuit(id=cid, name=name or cid, description="", circuit_type=ctype, points_count=1,
                   connected_load_w=0.0, phase=phase, cable=cable, protection=protection)


DB = pt("db", "distribution_board", 0.0, 0.0)     # mounted at 1.5 m


# ---------------------------------------------------------------- helpers
def test_parsers():
    assert calc.parse_section_mm2("3 x 2.5 mm² Cu/PVC") == 2.5
    assert calc.parse_section_mm2("3 x 1.5 mm2") == 1.5
    assert calc.parse_section_mm2("Cat6 U/UTP") is None and calc.parse_section_mm2(None) is None
    assert calc.parse_rating_a("20A Type B MCB + 30mA RCD") == 20
    assert calc.parse_rating_a("N/A (ELV)") is None
    assert calc.next_standard_rating(26.09) == 32 and calc.next_standard_rating(32) == 32
    assert calc.next_standard_rating(500) is None


def test_voltage_drop_formula_matches_published_mv_per_amp_metre():
    # 2.5 mm2 copper: 2 x 0.0225 / 2.5 = 18 mV/A/m (BS 7671 Table 4D2B gives 18)
    assert calc.drop_volts(1.0, 1.0, 2.5) * 1000 == pytest.approx(18.0)
    # 1.5 mm2: 30 mV/A/m (table: 29) - slightly conservative
    assert calc.drop_volts(1.0, 1.0, 1.5) * 1000 == pytest.approx(30.0)


# ---------------------------------------------------------------- voltage drop
def test_lighting_circuit_voltage_drop_hand_calculation():
    # Ten 60 W luminaires, farthest at (10 m, 5 m) from the board. 1.5 mm2 cable.
    lights = [pt(f"l{i}", "lighting", 1000.0 * i, 0.0, 60.0, "LGT") for i in range(1, 10)]
    lights.append(pt("far", "lighting", 10000.0, 5000.0, 60.0, "LGT"))
    circuit = ckt("LGT", "lighting", "3 x 1.5 mm² Cu/PVC", "10A Type B")

    out = calc.voltage_drop([circuit], [DB] + lights, scale_verified=True)
    row = out["circuits"][0]

    ib = 10 * 60 / 230                                   # 2.6087 A
    length = (10 + 5) * 1.10 + (2.7 - 1.5) + 0.0         # 16.5 m route + 1.2 m up from the board, ceiling light: no drop
    dv = 2 * ib * length * 0.0225 / 1.5                  # volts
    assert row["farthest_point_id"] == "far"
    assert row["design_current_a"] == pytest.approx(ib, abs=0.01)
    assert row["length_m"] == pytest.approx(length, abs=0.01)
    assert row["drop_v"] == pytest.approx(dv, abs=0.01)
    assert row["drop_percent"] == pytest.approx(dv / 230 * 100, abs=0.01)
    assert row["limit_percent"] == 3.0 and row["status"] == "pass"
    assert row["recommended_cable_mm2"] is None


def test_socket_circuit_uses_protective_device_rating_and_fails_when_long():
    # 20 A radial of 2.5 mm2 to a socket 40 m away: classic voltage-drop failure.
    sock = pt("s1", "twin_socket", 40000.0, 0.0, 250.0, "PWR")
    circuit = ckt("PWR", "power", "3 x 2.5 mm² Cu/PVC", "20A Type B MCB + 30mA RCD")
    row = calc.voltage_drop([circuit], [DB, sock], True)["circuits"][0]

    length = 40 * 1.10 + (2.7 - 1.5) + (2.7 - 0.3)       # 44 + 1.2 + 2.4 = 47.6 m
    dv = 2 * 20 * length * 0.0225 / 2.5
    assert row["design_current_basis"].startswith("protective device rating")
    assert row["design_current_a"] == 20.0
    assert row["drop_v"] == pytest.approx(dv, abs=0.01)
    assert row["drop_percent"] > 5.0 and row["status"] == "fail" and row["limit_percent"] == 5.0
    # The suggested cable is the smallest standard section that meets 5 %
    rec = row["recommended_cable_mm2"]
    assert calc.drop_volts(20, length, rec) / 230 * 100 <= 5.0
    smaller = [s for s in calc.STANDARD_SECTIONS_MM2 if s < rec]
    assert all(calc.drop_volts(20, length, s) / 230 * 100 > 5.0 for s in smaller)


def test_marginal_status_and_safety_circuit_uses_lighting_limit():
    # Pick a length that lands between 80 % and 100 % of the 3 % limit for one smoke alarm on 1.5 mm2
    # dV% = 2*Ib*L*0.0225/1.5/230*100 ; Ib = 5/230 -> need L ~ 2.6/(0.0225*2*5/230/1.5*100/230...) solve numerically
    target_pct = 0.9 * 3.0
    ib = 5 / 230
    length_needed = target_pct / 100 * 230 * 1.5 / (2 * ib * 0.0225)
    horizontal_mm = (length_needed - (2.7 - 1.5)) / 1.10 * 1000       # ceiling-mounted alarm: no outlet drop
    sd = pt("sd", "smoke_detector", horizontal_mm, 0.0, 5.0, "SAF")
    row = calc.voltage_drop([ckt("SAF", "safety", "3 x 1.5 mm² Cu/PVC", "6A Type B")], [DB, sd], True)["circuits"][0]
    assert row["limit_percent"] == 3.0
    assert row["drop_percent"] == pytest.approx(target_pct, abs=0.02)
    assert row["status"] == "marginal"


def test_nothing_is_guessed_when_inputs_are_missing():
    circuit = ckt("LGT", "lighting", "3 x 1.5 mm² Cu/PVC", "10A Type B")
    light = pt("l", "lighting", 1000.0, 0.0, 60.0, "LGT")

    no_scale = calc.voltage_drop([circuit], [DB, light], scale_verified=False)
    assert no_scale["status"] == "not_calculated" and "scale" in no_scale["reason"]
    assert no_scale["circuits"][0]["status"] == "not_calculated" and "drop_percent" not in no_scale["circuits"][0]

    no_board = calc.voltage_drop([circuit], [light], scale_verified=True)
    assert no_board["status"] == "not_calculated" and "distribution board" in no_board["reason"]

    bad_cable = calc.voltage_drop([ckt("LGT", "lighting", "special cable", "10A Type B")], [DB, light], True)
    assert bad_cable["circuits"][0]["status"] == "not_calculated" and "could not be read" in bad_cable["circuits"][0]["reason"]

    empty = calc.voltage_drop([circuit], [DB], True)
    assert empty["circuits"][0]["status"] == "not_calculated"


def test_elv_circuits_are_not_assessed():
    elv = ckt("ELV", "elv", "Cat6", "N/A (ELV)", phase="N/A")
    assert calc.voltage_drop([elv], [DB, pt("d", "data_point", 1000.0, 0.0, 0.0, "ELV")], True)["circuits"] == []


# ---------------------------------------------------------------- maximum demand
def _household():
    circuits = [
        ckt("LGT-1", "lighting", "3 x 1.5 mm² Cu/PVC", "10A Type B", "L1"),
        ckt("LGT-2", "lighting", "3 x 1.5 mm² Cu/PVC", "10A Type B", "L2"),
        ckt("PWR-1", "power", "3 x 2.5 mm² Cu/PVC", "20A Type B", "L3"),
        ckt("PWR-2", "power", "3 x 2.5 mm² Cu/PVC", "20A Type B", "L1"),
        ckt("CKR", "appliance", "3 x 6.0 mm² Cu/PVC", "32A Type B", "L2"),
        ckt("WTR", "appliance", "3 x 2.5 mm² Cu/PVC", "20A Type B", "L3"),
    ]
    points = [
        pt("a", "lighting", power=600.0, circuit="LGT-1"),
        pt("b", "lighting", power=600.0, circuit="LGT-2"),
        pt("c", "twin_socket", power=250.0, circuit="PWR-1"),
        pt("d", "twin_socket", power=250.0, circuit="PWR-2"),
        pt("e", "cooker_point", power=6000.0, circuit="CKR"),
        pt("f", "water_heater", power=2500.0, circuit="WTR"),
    ]
    return circuits, points


def test_household_maximum_demand_hand_calculation():
    circuits, points = _household()
    md = calc.maximum_demand(circuits, points, "Residential")

    lighting = 2 * 600 / 230 * 0.66                       # 66 % of connected lighting current
    sockets = 20 + 0.4 * 20                               # largest circuit + 40 % of the other
    cooker_ib = 6000 / 230
    cooker = 10 + 0.3 * (cooker_ib - 10) + 5              # On-Site Guide cooker rule with socket in unit
    heater = 2500 / 230                                   # no diversity
    expected = lighting + sockets + cooker + heater

    assert md["diversity_applied"] is True
    assert md["total"]["total_demand_a"] == pytest.approx(expected, abs=0.02)
    assert md["total"]["demand_a"]["sockets_a"] == pytest.approx(28.0)
    assert md["total"]["demand_a"]["cooking_a"] == pytest.approx(cooker, abs=0.01)
    assert md["total_demand_kva"] == pytest.approx(expected * 0.23, abs=0.01)
    # 3.44 + 28.0 + 19.83 + 10.87 = 62.14 A -> the 63 A rating (62.14 <= 63)
    assert expected == pytest.approx(62.14, abs=0.01)
    assert md["suggested_main_switch"]["single_phase_supply_a"] == 63
    # Phases are assessed on their own circuits: L1 = LGT-1 + PWR-2, L2 = LGT-2 + CKR, L3 = PWR-1 + WTR
    l1 = 600 / 230 * 0.66 + 20
    assert md["per_phase"]["L1"]["total_demand_a"] == pytest.approx(l1, abs=0.02)
    assert set(md["per_phase"]) == {"L1", "L2", "L3"}
    worst = max(p["total_demand_a"] for p in md["per_phase"].values())
    assert md["suggested_main_switch"]["three_phase_supply_a"] == calc.next_standard_rating(worst)
    assert 0 <= md["phase_imbalance_percent"] <= 100


def test_non_residential_gets_no_diversity():
    circuits, points = _household()
    res = calc.maximum_demand(circuits, points, "Residential")
    com = calc.maximum_demand(circuits, points, "Commercial")
    assert com["diversity_applied"] is False
    assert com["total"]["total_demand_a"] == com["total"]["total_connected_a"]
    assert com["total"]["total_demand_a"] > res["total"]["total_demand_a"]
    assert "no diversity" in com["notes"][0]


def test_elv_and_distribution_board_do_not_add_demand():
    circuits, points = _household()
    base = calc.maximum_demand(circuits, points, "Residential")["total"]["total_demand_a"]
    circuits.append(ckt("ELV", "elv", "Cat6", "N/A (ELV)", phase="N/A"))
    points.append(pt("g", "data_point", circuit="ELV"))
    points.append(DB)
    assert calc.maximum_demand(circuits, points, "Residential")["total"]["total_demand_a"] == base


def test_empty_design():
    md = calc.maximum_demand([], [], "Residential")
    assert md["total"]["total_demand_a"] == 0 and md["suggested_main_switch"]["three_phase_supply_a"] is None


# ---------------------------------------------------------------- API
def _project(client):
    pid = client.post("/api/projects", json={"name": "Calc Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    return pid


def test_calculations_endpoint_guides_the_user_step_by_step(client):
    pid = _project(client)
    assert client.get(f"/api/projects/{pid}/calculations").status_code == 409     # no analysis yet
    assert client.get("/api/projects/missing/calculations").status_code == 404

    client.post(f"/api/projects/{pid}/analyze")
    res = client.get(f"/api/projects/{pid}/calculations")
    assert res.status_code == 200
    body = res.json()
    assert body["disclaimer"].startswith("PRELIMINARY") and body["references"]
    # Maximum demand needs no geometry, so it is available straight away
    assert body["max_demand"]["total"]["total_demand_a"] > 0
    # Voltage drop refuses to guess without a scale
    assert body["voltage_drop"]["status"] == "not_calculated" and "scale" in body["voltage_drop"]["reason"]

    # Calibrated, but still no distribution board
    client.put(f"/api/projects/{pid}/scale", json={
        "point_a": {"x_ratio": 0.1, "y_ratio": 0.5}, "point_b": {"x_ratio": 0.6, "y_ratio": 0.5}, "real_distance_mm": 10000})
    client.post(f"/api/projects/{pid}/regenerate")
    body = client.get(f"/api/projects/{pid}/calculations").json()
    assert body["voltage_drop"]["status"] == "not_calculated" and "distribution board" in body["voltage_drop"]["reason"]

    # Place the board in the corridor: now every mains circuit is assessed
    placed = client.post(f"/api/projects/{pid}/points", json={"type": "distribution_board", "x_ratio": 0.5, "y_ratio": 0.55})
    assert placed.status_code == 201
    body = client.get(f"/api/projects/{pid}/calculations").json()
    vd = body["voltage_drop"]
    assert vd["status"] == "calculated"
    assert vd["circuits"] and all(r["status"] in ("pass", "marginal", "fail") for r in vd["circuits"])
    assert all(r["length_m"] > 0 and r["drop_percent"] >= 0 for r in vd["circuits"])
    assert vd["summary"]["circuits_checked"] == len(vd["circuits"])
    assert any("sub-mains" in a for a in vd["assumptions"])
