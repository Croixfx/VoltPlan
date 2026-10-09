import math
from typing import List, Tuple
from app.schemas.floor_plan import RoomObservation
from app.schemas.electrical import ElectricalPoint, Circuit
from app.schemas.boq import BOQItem


class BoqEngine:
    """
    Deterministic Bill of Quantities (BOQ) generation engine.
    Calculates required equipment, conductors, conduits, and accessories dynamically from
    detected points, circuits, and room floor areas.
    """

    @staticmethod
    def generate_boq(
        rooms: List[RoomObservation],
        points: List[ElectricalPoint],
        circuits: List[Circuit],
    ) -> Tuple[List[BOQItem], float]:
        items: List[BOQItem] = []
        item_counter = 1

        # Point counts by type
        lighting_count = sum(p.quantity for p in points if p.type == "lighting")
        sw1_count = sum(p.quantity for p in points if p.type == "switch_1way")
        sw2_count = sum(p.quantity for p in points if p.type == "switch_2way")
        twin_socket_count = sum(p.quantity for p in points if p.type == "twin_socket")
        single_socket_count = sum(p.quantity for p in points if p.type == "single_socket")
        cooker_count = sum(p.quantity for p in points if p.type == "cooker_point")
        water_heater_count = sum(p.quantity for p in points if p.type == "water_heater")
        ac_count = sum(p.quantity for p in points if p.type == "ac_point")

        # Circuit counts by type
        lgt_circuits_count = len([c for c in circuits if c.circuit_type == "lighting"])
        pwr_circuits_count = len([c for c in circuits if c.circuit_type == "power"])
        mcb_10a_count = lgt_circuits_count
        mcb_20a_count = pwr_circuits_count + water_heater_count
        mcb_32a_count = cooker_count
        mcb_16a_count = ac_count

        # Estimate average run lengths based on room areas or standard residential distances
        total_floor_area = sum(r.area_m2 or 20.0 for r in rooms)
        # Average perimeter wiring distance heuristic: ~1.2m conduit & ~3.5m single wire per point + home run allowance
        est_lighting_cable_m = max((lighting_count * 12.0) + (lgt_circuits_count * 18.0), 50.0)
        est_power_cable_m = max((twin_socket_count * 16.0) + (pwr_circuits_count * 22.0), 80.0)
        est_cooker_cable_m = cooker_count * 25.0
        est_conduit_m = (est_lighting_cable_m + est_power_cable_m + est_cooker_cable_m) * 0.45

        # ----------------------------------------------------
        # 1. Cables & Conduits
        # ----------------------------------------------------
        # 1.5mm2 Cable (Rolls of 100m)
        rolls_1_5 = math.ceil(est_lighting_cable_m / 100.0)
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Cables & Conduits",
                item_code="CBL-1.5-CU",
                description="Electric Cable 3 x 1.5 mm² Cu/PVC",
                specification="Plain annealed copper, PVC insulated 450/750V (RS IEC 60227 / BS 6004)",
                quantity=float(rolls_1_5),
                unit="rolls (100m)",
                unit_price_rwf=48000.0,
                total_price_rwf=rolls_1_5 * 48000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Allocated for radial lighting circuits and switch drops.",
            )
        )
        item_counter += 1

        # 2.5mm2 Cable (Rolls of 100m)
        rolls_2_5 = math.ceil(est_power_cable_m / 100.0)
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Cables & Conduits",
                item_code="CBL-2.5-CU",
                description="Electric Cable 3 x 2.5 mm² Cu/PVC",
                specification="Plain annealed copper, PVC insulated 450/750V (RS IEC 60227 / BS 6004)",
                quantity=float(rolls_2_5),
                unit="rolls (100m)",
                unit_price_rwf=78000.0,
                total_price_rwf=rolls_2_5 * 78000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Allocated for socket outlet radials, water heaters, and AC points.",
            )
        )
        item_counter += 1

        # 6.0mm2 Cable if cooker present
        if cooker_count > 0:
            rolls_6_0 = math.ceil(est_cooker_cable_m / 50.0)  # 50m roll
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Cables & Conduits",
                    item_code="CBL-6.0-CU",
                    description="Heavy Duty Cable 3 x 6.0 mm² Cu/PVC",
                    specification="High current stranded copper conductor, PVC sheath 450/750V",
                    quantity=float(rolls_6_0),
                    unit="rolls (50m)",
                    unit_price_rwf=85000.0,
                    total_price_rwf=rolls_6_0 * 85000.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Dedicated supply for electric cooker / range unit.",
                )
            )
            item_counter += 1

        # PVC Conduits (3m lengths)
        conduit_pipes = math.ceil(est_conduit_m / 3.0)
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Cables & Conduits",
                item_code="CND-20MM-PVC",
                description="Heavy Gauge PVC Electrical Conduit (20mm)",
                specification="High impact rigid PVC conduit pipe, 3-meter length (BS 4607 / RS IEC 61386)",
                quantity=float(conduit_pipes),
                unit="pcs (3m)",
                unit_price_rwf=3200.0,
                total_price_rwf=conduit_pipes * 3200.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Concealed in-wall and in-slab wiring containment.",
            )
        )
        item_counter += 1

        # ----------------------------------------------------
        # 2. Sockets & Switches
        # ----------------------------------------------------
        if twin_socket_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SKT-13A-TWIN",
                    description="13A 2-Gang Switched Socket Outlet",
                    specification="British standard 3-pin safety shuttered, with double pole switches (BS 1363)",
                    quantity=float(twin_socket_count),
                    unit="pcs",
                    unit_price_rwf=4500.0,
                    total_price_rwf=twin_socket_count * 4500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Flush mounted on wall at 300mm / 1100mm AFFL.",
                )
            )
            item_counter += 1

        if single_socket_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SKT-13A-SNGL",
                    description="13A 1-Gang Switched Socket / Shaver Outlet",
                    specification="Shuttered safety socket / dual voltage isolated shaver unit (BS 1363 / EN 61558)",
                    quantity=float(single_socket_count),
                    unit="pcs",
                    unit_price_rwf=5500.0,
                    total_price_rwf=single_socket_count * 5500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Dedicated appliances and bathroom shaver safety point.",
                )
            )
            item_counter += 1

        if sw1_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SW-1G-1W",
                    description="10AX 1-Gang 1-Way Plate Switch",
                    specification="Molded white faceplate, fluorescent / inductive load rated (BS EN 60669-1)",
                    quantity=float(sw1_count),
                    unit="pcs",
                    unit_price_rwf=2800.0,
                    total_price_rwf=sw1_count * 2800.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Standard room lighting control at doorway entrance.",
                )
            )
            item_counter += 1

        if sw2_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SW-1G-2W",
                    description="10AX 1-Gang 2-Way Plate Switch",
                    specification="Two-way switching control for multi-entrance locations (BS EN 60669-1)",
                    quantity=float(sw2_count),
                    unit="pcs",
                    unit_price_rwf=3400.0,
                    total_price_rwf=sw2_count * 3400.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Paired switching for corridors, stairways, and master bedroom.",
                )
            )
            item_counter += 1

        if cooker_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SW-45A-CKR",
                    description="45A DP Cooker Control Unit with 13A Socket",
                    specification="Double pole switch with neon indicator and auxiliary socket (BS 4177)",
                    quantity=float(cooker_count),
                    unit="pcs",
                    unit_price_rwf=14500.0,
                    total_price_rwf=cooker_count * 14500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Surface or flush mount adjacent to kitchen range.",
                )
            )
            item_counter += 1

        if water_heater_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SW-20A-DP-WH",
                    description="20A Double Pole Water Heater Switch",
                    specification="Surface mounted DP isolator with neon pilot indicator (BS EN 60669-2-4)",
                    quantity=float(water_heater_count),
                    unit="pcs",
                    unit_price_rwf=6500.0,
                    total_price_rwf=water_heater_count * 6500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Dedicated isolation outside wet shower area.",
                )
            )
            item_counter += 1

        if ac_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Sockets & Switches",
                    item_code="SW-20A-ISO-AC",
                    description="20A IP65 Weatherproof Rotary AC Isolator",
                    specification="3-pole lockable rotary motor disconnect switch (IEC 60947-3)",
                    quantity=float(ac_count),
                    unit="pcs",
                    unit_price_rwf=18000.0,
                    total_price_rwf=ac_count * 18000.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Positioned adjacent to air conditioning outdoor condenser unit.",
                )
            )
            item_counter += 1

        # ----------------------------------------------------
        # 3. Luminaires
        # ----------------------------------------------------
        if lighting_count > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Luminaires",
                    item_code="LUM-LED-15W",
                    description="15W Recessed LED Ceiling Downlight Fixture",
                    specification="Die-cast aluminum, 4000K neutral white, 1350lm, CRI>80, IP44 (RS IEC 60598)",
                    quantity=float(lighting_count),
                    unit="pcs",
                    unit_price_rwf=12500.0,
                    total_price_rwf=lighting_count * 12500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="High efficiency architectural ceiling lighting fixtures.",
                )
            )
            item_counter += 1

        # ----------------------------------------------------
        # 4. Distribution & Switchgear
        # ----------------------------------------------------
        # Consumer unit
        total_ways = max(len(circuits) + 4, 12)  # Extra spare ways
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Distribution & Switchgear",
                item_code=f"DB-{total_ways}W-SPN",
                description=f"{total_ways}-Way Flush Distribution Consumer Unit",
                specification="Sheet steel enclosure, IP40, with 100A DP main isolator switch (IEC 61439-3)",
                quantity=1.0,
                unit="set",
                unit_price_rwf=135000.0,
                total_price_rwf=135000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Central distribution board containing RCD and outgoing protective MCBs.",
            )
        )
        item_counter += 1

        # Residual Current Device (RCD)
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Distribution & Switchgear",
                item_code="RCD-63A-30MA",
                description="63A 30mA Double Pole RCD / RCCB",
                specification="Type A residual current circuit breaker for AC and pulsating DC protection (IEC 61008-1)",
                quantity=1.0,
                unit="pcs",
                unit_price_rwf=38000.0,
                total_price_rwf=38000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Mandatory 30mA electric shock protection for general socket outlets.",
            )
        )
        item_counter += 1

        # Miniature Circuit Breakers (MCBs)
        total_mcbs = mcb_10a_count + mcb_20a_count + mcb_16a_count + mcb_32a_count
        if total_mcbs > 0:
            items.append(
                BOQItem(
                    id=f"boq_{item_counter:03d}",
                    category="Distribution & Switchgear",
                    item_code="MCB-1P-ASSORTED",
                    description=f"Single Pole MCBs (10A x{mcb_10a_count}, 16A x{mcb_16a_count}, 20A x{mcb_20a_count}, 32A x{mcb_32a_count})",
                    specification="6kA breaking capacity, thermal-magnetic overcurrent protection (RS IEC 60898-1)",
                    quantity=float(total_mcbs),
                    unit="pcs",
                    unit_price_rwf=8500.0,
                    total_price_rwf=total_mcbs * 8500.0,
                    pricing_status="STANDARD_ESTIMATE",
                    notes="Individual circuit branch overcurrent protection.",
                )
            )
            item_counter += 1

        # ----------------------------------------------------
        # 5. Earthing & Protection
        # ----------------------------------------------------
        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Earthing & Protection",
                item_code="EARTH-ROD-16MM",
                description="Copper-Bonded Earth Rod (16mm x 1.5m) with Pit & Clamp",
                specification="High tensile steel core molecularly bonded with 99.9% pure copper (BS 7430 / IEC 62561)",
                quantity=1.0,
                unit="set",
                unit_price_rwf=45000.0,
                total_price_rwf=45000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Primary building earth electrode achieving target resistance < 10 ohms.",
            )
        )
        item_counter += 1

        items.append(
            BOQItem(
                id=f"boq_{item_counter:03d}",
                category="Earthing & Protection",
                item_code="SPD-T2-40KA",
                description="Type 2 Surge Protection Device (SPD)",
                specification="Single phase 230V Class II surge arrester 40kA with status indicator (IEC 61643-11)",
                quantity=1.0,
                unit="pcs",
                unit_price_rwf=55000.0,
                total_price_rwf=55000.0,
                pricing_status="STANDARD_ESTIMATE",
                notes="Protects sensitive domestic electronics against line transient overvoltages.",
            )
        )

        materials_subtotal = sum(i.total_price_rwf or 0.0 for i in items)
        return items, materials_subtotal
