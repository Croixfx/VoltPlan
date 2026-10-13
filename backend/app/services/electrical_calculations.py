"""
Electrical calculations: voltage drop per final circuit and maximum demand.

PRELIMINARY ENGINEERING AIDS - NOT A SIGN-OFF. Every constant and assumption is listed in
the result (`assumptions`, `references`) so a qualified electrician can audit and correct
them. See docs/CALCULATION_REVIEW.md for the formulas, worked examples and a review checklist.

Nothing is guessed: if an input needed for a calculation is missing (calibrated scale,
distribution-board location, a parsable cable size) the result says so and that part is
reported as `not_calculated`.
"""
import math
import re
from typing import Dict, List, Optional, Tuple

from app.catalog import get_equipment
from app.schemas.electrical import Circuit, ElectricalPoint

# ----------------------------------------------------------------------------
# Constants (all reported back to the caller)
# ----------------------------------------------------------------------------
SUPPLY_VOLTAGE_V = 230.0                    # single-phase line-to-neutral
COPPER_RESISTIVITY_70C = 0.0225             # ohm.mm2/m: 1.25 x 0.018 at 70 C conductor temperature (IEC 60364 guide)
CEILING_HEIGHT_M = 2.7                      # assumed; cable drops use catalog mounting heights
ROUTING_FACTOR = 1.10                       # cable runs along walls (Manhattan distance) plus 10 % for bends/slack
AC_POWER_FACTOR = 0.85                      # air-conditioning compressors
LIGHTING_LIMIT_PCT = 3.0                    # IEC 60364-5-52 Annex G / BS 7671 App. 4 (LV public supply)
OTHER_LIMIT_PCT = 5.0
MARGINAL_FRACTION = 0.8                     # >80 % of the limit is flagged as marginal
STANDARD_SECTIONS_MM2 = [1.5, 2.5, 4.0, 6.0, 10.0, 16.0]
STANDARD_RATINGS_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125]   # IEC 60898-1 preferred values

# Household diversity - IET On-Site Guide (BS 7671) Appendix 1, Table 1B
LIGHTING_DIVERSITY = 0.66
OTHER_SOCKET_CIRCUIT_DIVERSITY = 0.40
COOKER_FIRST_AMPS = 10.0
COOKER_REMAINDER_FACTOR = 0.30
COOKER_SOCKET_ALLOWANCE_A = 5.0

DISCLAIMER = (
    "PRELIMINARY CALCULATIONS FOR REVIEW BY A QUALIFIED ELECTRICIAN. They are derived from a plan "
    "and the assumptions listed below, not from a site survey, and must be verified before use "
    "for procurement, permits or installation."
)

REFERENCES = [
    "Voltage drop: dV = 2 x Ib x L x rho / S (single-phase, copper, 70 C), reactance neglected for S <= 50 mm2 "
    "(IEC 60364-5-52 Annex G; BS 7671 Appendix 4).",
    "Voltage-drop limits: 3 % lighting, 5 % other uses, measured from the origin of the installation "
    "(IEC 60364-5-52 Table G.57.1; BS 7671 Appendix 4 s.6.4).",
    "Diversity for household installations: IET On-Site Guide (BS 7671) Appendix 1, Table 1B. "
    "IEC 60364 gives no fixed factors; local utility rules (EUCL/REG) may differ.",
]


def _round(v: float, places: int = 2) -> float:
    return round(v, places)


def parse_section_mm2(cable: Optional[str]) -> Optional[float]:
    """'3 x 2.5 mm² Cu/PVC' -> 2.5"""
    if not cable:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm", cable)
    return float(m.group(1)) if m else None


def parse_rating_a(protection: Optional[str]) -> Optional[float]:
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*A", protection or "")
    return float(m.group(1)) if m else None


def drop_volts(current_a: float, length_m: float, section_mm2: float) -> float:
    return 2.0 * current_a * length_m * COPPER_RESISTIVITY_70C / section_mm2


def smallest_compliant_section(current_a: float, length_m: float, limit_pct: float) -> Optional[float]:
    for s in STANDARD_SECTIONS_MM2:
        if drop_volts(current_a, length_m, s) / SUPPLY_VOLTAGE_V * 100.0 <= limit_pct:
            return s
    return None


def next_standard_rating(amps: float) -> Optional[int]:
    return next((r for r in STANDARD_RATINGS_A if r >= amps), None)


# ----------------------------------------------------------------------------
# Design current
# ----------------------------------------------------------------------------
def _point_current(p: ElectricalPoint) -> float:
    pf = AC_POWER_FACTOR if p.type == "ac_point" else 1.0
    return (p.power_rating_w * p.quantity) / (SUPPLY_VOLTAGE_V * pf)


def design_current_a(circuit: Circuit, pts: List[ElectricalPoint]) -> Tuple[float, str]:
    """(Ib, basis). Socket circuits are taken at their protective-device rating because the real
    load behind a socket is unknown; every other circuit uses the sum of its connected loads."""
    if circuit.circuit_type == "power":
        rating = parse_rating_a(circuit.protection)
        if rating:
            return rating, "protective device rating (socket circuit)"
    return sum(_point_current(p) for p in pts), "sum of connected loads"


def _is_applicable(circuit: Circuit) -> bool:
    return circuit.circuit_type != "elv" and parse_rating_a(circuit.protection) is not None


# ----------------------------------------------------------------------------
# Voltage drop
# ----------------------------------------------------------------------------
def _mount_height_m(p: ElectricalPoint) -> float:
    spec = get_equipment(p.type)
    if spec is None or spec.mounting_height_mm is None:
        return CEILING_HEIGHT_M          # ceiling mounted
    return spec.mounting_height_mm / 1000.0


def _cable_length_m(db: ElectricalPoint, p: ElectricalPoint) -> float:
    horizontal_m = (abs(p.x_mm - db.x_mm) + abs(p.y_mm - db.y_mm)) / 1000.0 * ROUTING_FACTOR
    vertical_m = (CEILING_HEIGHT_M - _mount_height_m(db)) + (CEILING_HEIGHT_M - _mount_height_m(p))
    return horizontal_m + vertical_m


def _base_assumptions(db: Optional[ElectricalPoint]) -> List[str]:
    return [
        f"Supply {SUPPLY_VOLTAGE_V:.0f} V single-phase per circuit; copper conductors at 70 C, "
        f"resistivity {COPPER_RESISTIVITY_70C} ohm.mm2/m; reactance neglected.",
        "Only the final circuit from the distribution board is assessed; voltage drop in the incoming "
        "supply / sub-mains is not included and must be added.",
        f"Cable route = Manhattan distance between board and farthest point x {ROUTING_FACTOR} "
        f"+ vertical runs (ceiling height {CEILING_HEIGHT_M} m; board and outlet heights from the equipment catalog).",
        "The whole circuit load is assumed at the farthest point (conservative for lighting and sockets).",
        "Socket circuits use the protective-device rating as design current; other circuits use connected load "
        f"(air conditioning at power factor {AC_POWER_FACTOR}).",
        f"Limits: {LIGHTING_LIMIT_PCT:.0f} % lighting and safety lighting, {OTHER_LIMIT_PCT:.0f} % everything else.",
        "Cable current-carrying capacity (installation method, grouping, ambient temperature) is NOT checked.",
    ] + ([f"Distribution board located at the user-placed point '{db.id}' in '{db.room_name}'."] if db else [])


def voltage_drop(
    circuits: List[Circuit],
    points: List[ElectricalPoint],
    scale_verified: bool,
) -> Dict:
    db = next((p for p in points if p.type == "distribution_board" and p.x_mm is not None and p.y_mm is not None), None)
    result: Dict = {
        "status": "calculated",
        "reason": None,
        "limits_percent": {"lighting": LIGHTING_LIMIT_PCT, "other": OTHER_LIMIT_PCT},
        "assumptions": _base_assumptions(db),
        "circuits": [],
    }

    def blocked(reason: str) -> Dict:
        result["status"] = "not_calculated"
        result["reason"] = reason
        result["circuits"] = [
            {"circuit_id": c.id, "name": c.name, "circuit_type": c.circuit_type, "phase": c.phase,
             "status": "not_calculated", "reason": reason}
            for c in circuits if _is_applicable(c)
        ]
        return result

    if not scale_verified:
        return blocked("The plan scale is not calibrated, so cable lengths cannot be measured. Calibrate the scale first.")
    if db is None:
        return blocked("No distribution board has been placed on the plan. Place the board to measure cable lengths.")

    by_circuit: Dict[str, List[ElectricalPoint]] = {}
    for p in points:
        if p.circuit_id:
            by_circuit.setdefault(p.circuit_id, []).append(p)

    for c in circuits:
        if not _is_applicable(c):
            continue
        row: Dict = {"circuit_id": c.id, "name": c.name, "circuit_type": c.circuit_type, "phase": c.phase}
        pts = [p for p in by_circuit.get(c.id, []) if p.x_mm is not None and p.y_mm is not None]
        section = parse_section_mm2(c.cable)
        if not pts:
            result["circuits"].append({**row, "status": "not_calculated", "reason": "The circuit has no positioned points."})
            continue
        if section is None:
            result["circuits"].append({**row, "status": "not_calculated", "reason": f"Cable size '{c.cable}' could not be read."})
            continue

        farthest = max(pts, key=lambda p: _cable_length_m(db, p))
        length = _cable_length_m(db, farthest)
        ib, basis = design_current_a(c, by_circuit.get(c.id, []))
        dv = drop_volts(ib, length, section)
        pct = dv / SUPPLY_VOLTAGE_V * 100.0
        limit = LIGHTING_LIMIT_PCT if c.circuit_type in ("lighting", "safety") else OTHER_LIMIT_PCT
        status = "fail" if pct > limit else ("marginal" if pct > limit * MARGINAL_FRACTION else "pass")
        result["circuits"].append({
            **row,
            "status": status,
            "reason": None,
            "cable_mm2": section,
            "design_current_a": _round(ib),
            "design_current_basis": basis,
            "length_m": _round(length),
            "farthest_point_id": farthest.id,
            "drop_v": _round(dv),
            "drop_percent": _round(pct),
            "limit_percent": limit,
            "recommended_cable_mm2": smallest_compliant_section(ib, length, limit) if status == "fail" else None,
        })

    failing = [r for r in result["circuits"] if r["status"] == "fail"]
    result["summary"] = {
        "circuits_checked": sum(1 for r in result["circuits"] if r["status"] != "not_calculated"),
        "failing": len(failing),
        "marginal": sum(1 for r in result["circuits"] if r["status"] == "marginal"),
    }
    return result


# ----------------------------------------------------------------------------
# Maximum demand
# ----------------------------------------------------------------------------
def _demand(circuits: List[Circuit], points: List[ElectricalPoint], apply_diversity: bool) -> Dict:
    """Maximum demand (A) for a set of circuits, grouped as in On-Site Guide Table 1B."""
    by_circuit: Dict[str, List[ElectricalPoint]] = {}
    for p in points:
        if p.circuit_id:
            by_circuit.setdefault(p.circuit_id, []).append(p)

    lighting: List[float] = []
    sockets: List[float] = []
    cookers: List[float] = []
    other: List[float] = []
    for c in circuits:
        if not _is_applicable(c):
            continue
        pts = by_circuit.get(c.id, [])
        ib, _ = design_current_a(c, pts)
        if c.circuit_type in ("lighting", "safety"):
            lighting.append(ib)
        elif c.circuit_type == "power":
            sockets.append(ib)
        elif any(p.type == "cooker_point" for p in pts):
            cookers.append(ib)
        else:
            other.append(ib)

    connected = {
        "lighting_a": sum(lighting), "sockets_a": sum(sockets), "cooking_a": sum(cookers), "other_a": sum(other),
    }
    if not apply_diversity:
        demand = dict(connected)
    else:
        ordered = sorted(sockets, reverse=True)
        socket_demand = (ordered[0] + OTHER_SOCKET_CIRCUIT_DIVERSITY * sum(ordered[1:])) if ordered else 0.0
        cook_demand = 0.0
        for ib in cookers:
            cook_demand += COOKER_FIRST_AMPS + COOKER_REMAINDER_FACTOR * max(0.0, ib - COOKER_FIRST_AMPS) \
                           + COOKER_SOCKET_ALLOWANCE_A
        demand = {
            "lighting_a": LIGHTING_DIVERSITY * connected["lighting_a"],
            "sockets_a": socket_demand,
            "cooking_a": cook_demand,
            "other_a": connected["other_a"],
        }
    return {
        "connected_a": {k: _round(v) for k, v in connected.items()},
        "demand_a": {k: _round(v) for k, v in demand.items()},
        "total_connected_a": _round(sum(connected.values())),
        "total_demand_a": _round(sum(demand.values())),
    }


def maximum_demand(circuits: List[Circuit], points: List[ElectricalPoint], building_type: str) -> Dict:
    residential = (building_type or "").strip().lower() == "residential"
    total = _demand(circuits, points, residential)

    phases: Dict[str, Dict] = {}
    for ph in ("L1", "L2", "L3"):
        subset = [c for c in circuits if c.phase == ph]
        if subset:
            phases[ph] = _demand(subset, points, residential)
    max_phase_a = max((p["total_demand_a"] for p in phases.values()), default=0.0)
    min_phase_a = min((p["total_demand_a"] for p in phases.values()), default=0.0)
    imbalance = _round((max_phase_a - min_phase_a) / max_phase_a * 100.0, 1) if max_phase_a else 0.0

    connected_kw = sum(p.power_rating_w * p.quantity for p in points if (get_equipment(p.type) is None or
                       get_equipment(p.type).circuit_class.value not in ("elv", "none"))) / 1000.0

    notes = [
        "Socket circuits are assessed at their protective-device rating; other circuits at connected load.",
        "Heating, water heating and air conditioning are taken at 100 % (no diversity).",
        f"Supply assumed {SUPPLY_VOLTAGE_V:.0f} V per phase; kVA = A x {SUPPLY_VOLTAGE_V:.0f} / 1000 (power factor 1).",
        "Future load growth is NOT included. Add an allowance agreed with the client.",
    ]
    if residential:
        notes.insert(0, "Household diversity applied (IET On-Site Guide Table 1B): lighting 66 %; sockets 100 % of the "
                        "largest circuit + 40 % of the others; cooker 10 A + 30 % of the rest + 5 A for a socket in "
                        "the unit.")
    else:
        notes.insert(0, f"Building type '{building_type}' is not residential: no diversity is applied "
                        "(100 % of the design currents). Apply a justified diversity if appropriate.")

    return {
        "diversity_applied": residential,
        "connected_load_kw": _round(connected_kw),
        "total": total,
        "total_demand_kva": _round(total["total_demand_a"] * SUPPLY_VOLTAGE_V / 1000.0),
        "per_phase": phases,
        "phase_imbalance_percent": imbalance,
        "suggested_main_switch": {
            "three_phase_supply_a": next_standard_rating(max_phase_a) if phases else None,
            "single_phase_supply_a": next_standard_rating(total["total_demand_a"]),
            "note": "Smallest standard rating not below the maximum demand. Confirm against the utility "
                    "connection offer, earthing system and incoming cable.",
        },
        "notes": notes,
    }


def calculate(
    circuits: List[Circuit],
    points: List[ElectricalPoint],
    building_type: str,
    scale_verified: bool,
) -> Dict:
    return {
        "voltage_drop": voltage_drop(circuits, points, scale_verified),
        "max_demand": maximum_demand(circuits, points, building_type),
        "references": REFERENCES,
        "disclaimer": DISCLAIMER,
    }
