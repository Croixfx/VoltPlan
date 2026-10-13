import io

import pytest
from PIL import Image

from app.schemas.electrical import Circuit, ElectricalPoint
from app.services import electrical_calculations as calc
from app.services.electrical_calculations import CapacityOptions, cable_capacity


def ckt(cid, ctype, cable, protection, name=None):
    return Circuit(id=cid, name=name or cid, description="", circuit_type=ctype, points_count=1,
                   connected_load_w=0.0, phase="L1", cable=cable, protection=protection)


def pt(pid, ptype, power, circuit, qty=1):
    return ElectricalPoint(id=pid, room_id="r", room_name="Room", type=ptype, power_rating_w=power,
                           quantity=qty, circuit_id=circuit, rule_reference="x")


SOCKETS = ckt("PWR", "power", "3 x 2.5 mm² Cu/PVC", "20A Type B MCB + 30mA RCD")
LIGHTS = ckt("LGT", "lighting", "3 x 1.5 mm² Cu/PVC", "10A Type B")
LIGHT_PTS = [pt("l1", "lighting", 60.0, "LGT")]


def row(circuits, points, **opts):
    return cable_capacity(circuits, points, CapacityOptions(**opts))["circuits"][0]


def test_tabulated_values_match_iec_60364_5_52_table_b52_2():
    t = calc.tabulated_capacity_a
    assert [t("B2", s) for s in (1.5, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0)] == [16.5, 23.0, 30.0, 38.0, 52.0, 69.0, 90.0]
    assert [t("C", s) for s in (1.5, 2.5, 6.0)] == [19.5, 27.0, 46.0]
    assert [t("A2", s) for s in (1.5, 2.5)] == [14.0, 18.5]
    assert t("B2", 35.0) is None            # beyond the transcribed table


def test_20a_socket_radial_on_2_5mm2_passes_when_not_bunched():
    r = row([SOCKETS], [pt("s", "twin_socket", 250.0, "PWR")])
    # Iz = 23 A x 1.00 x 1.00 ; 20 A device -> 87 % of the capacity
    assert r["capacity_a"] == 23.0 and r["protective_device_a"] == 20.0
    assert r["utilisation_percent"] == pytest.approx(20 / 23 * 100, abs=0.1)
    assert r["status"] == "pass" and r["reason"] is None
    assert r["design_current_a"] == 20.0 and r["design_current_basis"].startswith("protective device rating")
    # Another circuit sharing the route is already too many for method B2
    assert r["max_grouped_circuits"] == 1


def test_bunching_with_one_more_circuit_makes_the_same_cable_fail():
    r = row([SOCKETS], [pt("s", "twin_socket", 250.0, "PWR")], grouped_circuits=2)
    # Iz = 23 x 0.80 = 18.4 A < 20 A device
    assert r["capacity_a"] == pytest.approx(18.4)
    assert r["status"] == "fail" and "exceeds the cable capacity 18.4 A" in r["reason"]
    # Fixes: a 4 mm2 cable (30 x 0.8 = 24 A) or a 16 A device (<= 18.4 A)
    assert r["recommended_cable_mm2"] == 4.0
    assert r["reduce_device_to_a"] == 16


def test_installation_method_changes_the_result():
    pts = [pt("s", "twin_socket", 250.0, "PWR")]
    clipped = row([SOCKETS], pts, method="C", grouped_circuits=2)
    # 27 x 0.80 = 21.6 A: a 20 A device fits, but with under 10 % margin
    assert clipped["capacity_a"] == pytest.approx(27 * 0.80) and clipped["status"] == "marginal"
    assert clipped["max_grouped_circuits"] == 2                                                    # 27 x 0.70 = 18.9 < 20

    insulated = row([SOCKETS], pts, method="A2")
    assert insulated["capacity_a"] == 18.5 and insulated["status"] == "fail"                       # 20 A device on 18.5 A


def test_hot_ambient_is_marginal_when_the_device_is_just_inside_the_capacity():
    r = row([SOCKETS], [pt("s", "twin_socket", 250.0, "PWR")], ambient_c=40)
    # 23 x 0.87 = 20.01 A vs 20 A device: legal but with no margin
    assert r["capacity_a"] == pytest.approx(20.01, abs=0.005)
    assert r["status"] == "marginal" and r["reason"] is None


def test_combined_derating_and_recommendation():
    r = row([LIGHTS], LIGHT_PTS, ambient_c=40, grouped_circuits=6)
    iz = 16.5 * 0.87 * 0.57                                      # 8.18 A, below the 10 A device
    assert r["capacity_a"] == pytest.approx(iz, abs=0.01)
    assert r["status"] == "fail"
    assert r["recommended_cable_mm2"] == 2.5                     # 23 x 0.87 x 0.57 = 11.4 A >= 10 A
    assert r["reduce_device_to_a"] == 6                          # largest preferred rating <= 8.18 A and >= Ib


def test_design_current_above_the_device_rating_is_reported():
    big = [pt("l", "lighting", 3000.0, "LGT")]                   # 13.04 A on a 10 A device
    r = row([LIGHTS], big)
    assert r["status"] == "fail" and "design current 13.0 A exceeds the protective device rating 10 A" in r["reason"]
    # a bigger cable would not help: the cable only needs to carry the (larger) device after it is upsized
    assert r["recommended_cable_mm2"] == 1.5


def test_heavy_circuits_in_the_default_design():
    cooker = ckt("CKR", "appliance", "3 x 6.0 mm² Cu/PVC", "32A Type B")
    r = row([cooker], [pt("c", "cooker_point", 6000.0, "CKR")])
    assert r["capacity_a"] == 38.0 and r["status"] == "pass"
    assert r["design_current_a"] == pytest.approx(6000 / 230, abs=0.01)


def test_unreadable_or_untabulated_cables_are_not_calculated():
    odd = row([ckt("X", "power", "special", "20A")], [])
    assert odd["status"] == "not_calculated" and "could not be read" in odd["reason"]
    big = row([ckt("X", "power", "3 x 35 mm² Cu/PVC", "125A")], [])
    assert big["status"] == "not_calculated" and "No tabulated capacity for 35 mm2" in big["reason"]


def test_elv_circuits_are_skipped():
    elv = ckt("ELV", "elv", "Cat6", "N/A (ELV)")
    assert cable_capacity([elv], [])["circuits"] == []


@pytest.mark.parametrize(
    "kwargs",
    [{"method": "Z"}, {"ambient_c": 33}, {"ambient_c": 50}, {"grouped_circuits": 0}, {"grouped_circuits": 9}],
)
def test_unsupported_conditions_are_rejected_not_approximated(kwargs):
    with pytest.raises(ValueError):
        CapacityOptions(**kwargs)


def test_summary_and_assumptions():
    out = cable_capacity([SOCKETS, LIGHTS], [pt("s", "twin_socket", 250.0, "PWR")] + LIGHT_PTS,
                         CapacityOptions(grouped_circuits=2))
    assert out["summary"] == {"circuits_checked": 2, "failing": 1, "marginal": 0}      # sockets fail, lights pass
    assert out["options"]["grouping_factor"] == 0.8 and out["options"]["method"] == "B2"
    assert any("Table B.52.2" in a for a in out["assumptions"]) and any("Not checked" in a for a in out["assumptions"])
    assert out["options"]["available"]["grouped_circuits"] == [1, 2, 3, 4, 5, 6]


# --------------------------------------------------------------------------- API
def _project(client):
    pid = client.post("/api/projects", json={"name": "Capacity Test", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    client.post(f"/api/projects/{pid}/analyze")
    return pid


def test_capacity_needs_no_scale_or_board_and_responds_to_conditions(client):
    pid = _project(client)

    body = client.get(f"/api/projects/{pid}/calculations").json()
    cap = body["cable_capacity"]
    # Unlike voltage drop, capacity never depends on the scale or a placed board
    assert body["voltage_drop"]["status"] == "not_calculated"
    assert cap["status"] == "calculated" and cap["circuits"]
    assert cap["options"]["method"] == "B2" and cap["options"]["grouped_circuits"] == 1
    assert cap["summary"]["failing"] == 0                       # the generated design is adequate when not bunched
    sockets = [r for r in cap["circuits"] if r["circuit_type"] == "power"]
    assert sockets and all(r["capacity_a"] == 23.0 for r in sockets)

    bunched = client.get(f"/api/projects/{pid}/calculations?grouped_circuits=2&method=b2").json()["cable_capacity"]
    failing = {r["circuit_id"] for r in bunched["circuits"] if r["status"] == "fail"}
    # 2.5 mm2 / 20 A (all socket radials and the water heater) and 6 mm2 / 32 A (cooker: 38 x 0.8 = 30.4 A) fail
    # as soon as another circuit shares the route; lighting, AC and detection circuits still pass
    assert {r["circuit_id"] for r in sockets} <= failing and "CKT-APP-CKR" in failing
    assert bunched["summary"]["failing"] == len(sockets) + 2
    assert all(r["recommended_cable_mm2"] == 4.0 for r in bunched["circuits"] if r["status"] == "fail" and r["circuit_type"] == "power")

    clipped = client.get(f"/api/projects/{pid}/calculations?method=C&grouped_circuits=2").json()["cable_capacity"]
    assert clipped["summary"]["failing"] == 0


def test_capacity_api_rejects_unsupported_conditions(client):
    pid = _project(client)
    for query in ("method=Z", "ambient_c=33", "grouped_circuits=12"):
        res = client.get(f"/api/projects/{pid}/calculations?{query}")
        assert res.status_code == 422 and "not supported" in res.json()["detail"]
