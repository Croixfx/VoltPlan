import math
import re
from collections import Counter
from typing import Dict, List, Tuple
from app.catalog import all_equipment
from app.schemas.floor_plan import RoomObservation
from app.schemas.electrical import ElectricalPoint, Circuit
from app.schemas.boq import BOQItem


def _rating_amps(protection: str) -> int:
    """Leading amp rating of a protection string such as '20A Type B MCB + 30mA RCD'."""
    match = re.match(r"\s*(\d+)\s*A", protection or "")
    return int(match.group(1)) if match else 0


class BoqEngine:
    """
    Deterministic Bill of Quantities (BOQ) generation engine.
    Calculates required equipment, conductors, conduits, and accessories dynamically from
    detected points, circuits, and room floor areas. Per-equipment BOQ lines, cable runs
    and pricing come from the equipment catalog (app.catalog).
    """

    @staticmethod
    def generate_boq(
        rooms: List[RoomObservation],
        points: List[ElectricalPoint],
        circuits: List[Circuit],
    ) -> Tuple[List[BOQItem], float]:
        items: List[BOQItem] = []
        item_counter = 1

        def add_item(**kwargs) -> None:
            nonlocal item_counter
            items.append(BOQItem(id=f"boq_{item_counter:03d}", pricing_status="STANDARD_ESTIMATE", **kwargs))
            item_counter += 1

        # Point counts by catalog type
        counts: Counter = Counter()
        for p in points:
            counts[p.type] += p.quantity
        catalog = all_equipment()

        # Circuit counts by type
        lgt_circuits_count = len([c for c in circuits if c.circuit_type == "lighting"])
        pwr_circuits_count = len([c for c in circuits if c.circuit_type == "power"])

        # Cable run estimates by conductor section, from catalog run lengths per point.
        # Home-run allowance per circuit: ~18 m lighting, ~22 m power.
        runs_m: Dict[str, float] = {"1.5": 0.0, "2.5": 0.0, "6.0": 0.0}
        for spec in catalog:
            if spec.cable_section_mm2 in runs_m:
                runs_m[spec.cable_section_mm2] += counts[spec.type_id] * spec.cable_run_m
        est_lighting_cable_m = max(runs_m["1.5"] + (lgt_circuits_count * 18.0), 50.0)
        est_power_cable_m = max(runs_m["2.5"] + (pwr_circuits_count * 22.0), 80.0)
        est_heavy_cable_m = runs_m["6.0"]
        est_conduit_m = (est_lighting_cable_m + est_power_cable_m + est_heavy_cable_m) * 0.45

        # ----------------------------------------------------
        # 1. Cables & Conduits
        # ----------------------------------------------------
        rolls_1_5 = math.ceil(est_lighting_cable_m / 100.0)
        add_item(
            category="Cables & Conduits",
            item_code="CBL-1.5-CU",
            description="Electric Cable 3 x 1.5 mm² Cu/PVC",
            specification="Plain annealed copper, PVC insulated 450/750V (RS IEC 60227 / BS 6004)",
            quantity=float(rolls_1_5),
            unit="rolls (100m)",
            unit_price_rwf=48000.0,
            total_price_rwf=rolls_1_5 * 48000.0,
            notes="Allocated for radial lighting circuits, switch drops and detection circuits.",
        )

        rolls_2_5 = math.ceil(est_power_cable_m / 100.0)
        add_item(
            category="Cables & Conduits",
            item_code="CBL-2.5-CU",
            description="Electric Cable 3 x 2.5 mm² Cu/PVC",
            specification="Plain annealed copper, PVC insulated 450/750V (RS IEC 60227 / BS 6004)",
            quantity=float(rolls_2_5),
            unit="rolls (100m)",
            unit_price_rwf=78000.0,
            total_price_rwf=rolls_2_5 * 78000.0,
            notes="Allocated for socket outlet radials, water heaters, and AC points.",
        )

        if est_heavy_cable_m > 0:
            rolls_6_0 = math.ceil(est_heavy_cable_m / 50.0)  # 50m roll
            add_item(
                category="Cables & Conduits",
                item_code="CBL-6.0-CU",
                description="Heavy Duty Cable 3 x 6.0 mm² Cu/PVC",
                specification="High current stranded copper conductor, PVC sheath 450/750V",
                quantity=float(rolls_6_0),
                unit="rolls (50m)",
                unit_price_rwf=85000.0,
                total_price_rwf=rolls_6_0 * 85000.0,
                notes="Dedicated supply for electric cooker / range unit.",
            )

        conduit_pipes = math.ceil(est_conduit_m / 3.0)
        add_item(
            category="Cables & Conduits",
            item_code="CND-20MM-PVC",
            description="Heavy Gauge PVC Electrical Conduit (20mm)",
            specification="High impact rigid PVC conduit pipe, 3-meter length (BS 4607 / RS IEC 61386)",
            quantity=float(conduit_pipes),
            unit="pcs (3m)",
            unit_price_rwf=3200.0,
            total_price_rwf=conduit_pipes * 3200.0,
            notes="Concealed in-wall and in-slab wiring containment.",
        )

        # ----------------------------------------------------
        # 2. Equipment (catalog-driven: sockets, switches, appliances, luminaires, safety, ...)
        # ----------------------------------------------------
        for spec in catalog:
            count = counts[spec.type_id]
            if count <= 0:
                continue
            for line in spec.boq_lines:
                qty = count * line.qty_per_point
                add_item(
                    category=line.category,
                    item_code=line.item_code,
                    description=line.description,
                    specification=line.specification,
                    quantity=float(qty),
                    unit=line.unit,
                    unit_price_rwf=line.unit_price_rwf,
                    total_price_rwf=qty * line.unit_price_rwf,
                    notes=line.notes,
                )

        # ----------------------------------------------------
        # 3. Distribution & Switchgear
        # ----------------------------------------------------
        total_ways = max(len(circuits) + 4, 12)  # Extra spare ways
        add_item(
            category="Distribution & Switchgear",
            item_code=f"DB-{total_ways}W-SPN",
            description=f"{total_ways}-Way Flush Distribution Consumer Unit",
            specification="Sheet steel enclosure, IP40, with 100A DP main isolator switch (IEC 61439-3)",
            quantity=1.0,
            unit="set",
            unit_price_rwf=135000.0,
            total_price_rwf=135000.0,
            notes="Central distribution board containing RCD and outgoing protective MCBs.",
        )

        add_item(
            category="Distribution & Switchgear",
            item_code="RCD-63A-30MA",
            description="63A 30mA Double Pole RCD / RCCB",
            specification="Type A residual current circuit breaker for AC and pulsating DC protection (IEC 61008-1)",
            quantity=1.0,
            unit="pcs",
            unit_price_rwf=38000.0,
            total_price_rwf=38000.0,
            notes="Mandatory 30mA electric shock protection for general socket outlets.",
        )

        # Miniature Circuit Breakers: one per circuit, grouped by rating
        mcb_by_rating = Counter(_rating_amps(c.protection) for c in circuits if _rating_amps(c.protection) > 0)
        total_mcbs = sum(mcb_by_rating.values())
        if total_mcbs > 0:
            breakdown = ", ".join(f"{amps}A x{n}" for amps, n in sorted(mcb_by_rating.items()))
            add_item(
                category="Distribution & Switchgear",
                item_code="MCB-1P-ASSORTED",
                description=f"Single Pole MCBs ({breakdown})",
                specification="6kA breaking capacity, thermal-magnetic overcurrent protection (RS IEC 60898-1)",
                quantity=float(total_mcbs),
                unit="pcs",
                unit_price_rwf=8500.0,
                total_price_rwf=total_mcbs * 8500.0,
                notes="Individual circuit branch overcurrent protection.",
            )

        # ----------------------------------------------------
        # 4. Earthing & Protection
        # ----------------------------------------------------
        add_item(
            category="Earthing & Protection",
            item_code="EARTH-ROD-16MM",
            description="Copper-Bonded Earth Rod (16mm x 1.5m) with Pit & Clamp",
            specification="High tensile steel core molecularly bonded with 99.9% pure copper (BS 7430 / IEC 62561)",
            quantity=1.0,
            unit="set",
            unit_price_rwf=45000.0,
            total_price_rwf=45000.0,
            notes="Primary building earth electrode achieving target resistance < 10 ohms.",
        )

        add_item(
            category="Earthing & Protection",
            item_code="SPD-T2-40KA",
            description="Type 2 Surge Protection Device (SPD)",
            specification="Single phase 230V Class II surge arrester 40kA with status indicator (IEC 61643-11)",
            quantity=1.0,
            unit="pcs",
            unit_price_rwf=55000.0,
            total_price_rwf=55000.0,
            notes="Protects sensitive domestic electronics against line transient overvoltages.",
        )

        materials_subtotal = sum(i.total_price_rwf or 0.0 for i in items)
        return items, materials_subtotal
