import math
from typing import List, Tuple, Dict
from shapely.geometry import Point
from app.engineering_rules.registry import get_engineering_standard
from app.schemas.electrical import ElectricalPoint, Circuit, WiringArc
from app.services.geometry_engine import GeometryEngine


class CircuitEngine:
    """
    Deterministic circuit schedule engine.
    Groups electrical points into balanced circuits according to standard capacity rules.
    """

    @staticmethod
    def generate_circuits(
        points: List[ElectricalPoint],
        standard_name: str = "RS IEC 60364",
    ) -> Tuple[List[ElectricalPoint], List[Circuit]]:
        standard = get_engineering_standard(standard_name)
        rules = standard.get_circuit_rules()

        circuits: List[Circuit] = []
        updated_points = [p.model_copy() for p in points]

        # Phase allocation cycle
        phases = ["L1", "L2", "L3"]
        phase_idx = 0

        # Separate points by functional class
        lighting_pts = [p for p in updated_points if p.type == "lighting"]
        kitchen_pwr_pts = [p for p in updated_points if p.type == "twin_socket" and "kitchen" in p.room_name.lower()]
        general_pwr_pts = [p for p in updated_points if p.type == "twin_socket" and "kitchen" not in p.room_name.lower()]
        appliance_pts = [p for p in updated_points if p.type in ["cooker_point", "water_heater", "ac_point", "single_socket"]]

        # 1. Lighting Circuits
        max_lgt_pts = rules.get("max_lighting_points_per_circuit", 10)
        lgt_circuit_idx = 1
        room_to_lgt_circuit = {}

        for i in range(0, len(lighting_pts), max_lgt_pts):
            chunk = lighting_pts[i : i + max_lgt_pts]
            ckt_id = f"CKT-LGT-{lgt_circuit_idx:02d}"
            tot_w = sum(p.power_rating_w * p.quantity for p in chunk)
            assigned_phase = phases[phase_idx % len(phases)]
            phase_idx += 1

            for p in chunk:
                p.circuit_id = ckt_id
                room_to_lgt_circuit[p.room_id] = ckt_id

            circuits.append(
                Circuit(
                    id=ckt_id,
                    name=f"Lighting Circuit {lgt_circuit_idx}",
                    description=f"Lighting for {', '.join(set(p.room_name for p in chunk))}",
                    circuit_type="lighting",
                    points_count=len(chunk),
                    connected_load_w=tot_w,
                    phase=assigned_phase,
                    cable=rules.get("lighting_cable", "3 x 1.5 mm² Cu/PVC"),
                    protection=rules.get("lighting_mcb", "10A Type B"),
                    rcd="30mA Type A RCD (Shared / Sub-bank)",
                    status="CALCULATED",
                    review_notes="Standard lighting radial. Maximum 10-12 luminaires per circuit.",
                )
            )
            lgt_circuit_idx += 1

        # Assign switches to lighting circuits
        default_lgt_circuit = circuits[0].id if circuits else "CKT-LGT-01"
        for p in updated_points:
            if "switch" in p.type:
                p.circuit_id = room_to_lgt_circuit.get(p.room_id, default_lgt_circuit)

        # 2. Kitchen Power Circuits (Dedicated radial)
        kitchen_pwr_pts = [
            p for p in updated_points
            if (p.type in ["twin_socket", "single_socket"]) and ("kitchen" in p.room_name.lower())
        ]
        if kitchen_pwr_pts:
            ckt_id = "CKT-PWR-KIT"
            tot_w = sum(p.power_rating_w * p.quantity for p in kitchen_pwr_pts)
            assigned_phase = phases[phase_idx % len(phases)]
            phase_idx += 1

            for p in kitchen_pwr_pts:
                p.circuit_id = ckt_id

            circuits.append(
                Circuit(
                    id=ckt_id,
                    name="Kitchen Worktop Sockets",
                    description="Countertop small appliance sockets (RS IEC 60364-8-1)",
                    circuit_type="power",
                    points_count=len(kitchen_pwr_pts),
                    connected_load_w=tot_w,
                    phase=assigned_phase,
                    cable=rules.get("socket_cable", "3 x 2.5 mm² Cu/PVC"),
                    protection=rules.get("socket_mcb", "20A Type B"),
                    rcd="30mA Type A RCD",
                    status="CALCULATED",
                    review_notes="Dedicated kitchen socket circuit to prevent nuisance tripping.",
                )
            )

        # 3. General Socket Circuits
        general_pwr_pts = [
            p for p in updated_points
            if (p.type in ["twin_socket", "single_socket"])
            and ("kitchen" not in p.room_name.lower())
            and p.circuit_id is None
        ]
        max_pwr_pts = rules.get("max_sockets_per_radial_circuit", 6)
        pwr_circuit_idx = 1
        for i in range(0, len(general_pwr_pts), max_pwr_pts):
            chunk = general_pwr_pts[i : i + max_pwr_pts]
            ckt_id = f"CKT-PWR-{pwr_circuit_idx:02d}"
            tot_w = sum(p.power_rating_w * p.quantity for p in chunk)
            assigned_phase = phases[phase_idx % len(phases)]
            phase_idx += 1

            for p in chunk:
                p.circuit_id = ckt_id

            circuits.append(
                Circuit(
                    id=ckt_id,
                    name=f"Power Sockets Circuit {pwr_circuit_idx}",
                    description=f"Sockets for {', '.join(set(p.room_name for p in chunk))}",
                    circuit_type="power",
                    points_count=len(chunk),
                    connected_load_w=tot_w,
                    phase=assigned_phase,
                    cable=rules.get("socket_cable", "3 x 2.5 mm² Cu/PVC"),
                    protection=rules.get("socket_mcb", "20A Type B"),
                    rcd="30mA Type A RCD",
                    status="CALCULATED",
                    review_notes="Radial 20A socket outlet circuit with 30mA RCD shock protection.",
                )
            )
            pwr_circuit_idx += 1

        # 4. Dedicated Appliance Circuits
        dedicated_pts = [
            p for p in updated_points
            if p.type in ["cooker_point", "water_heater", "ac_point"]
        ]
        for app_pt in dedicated_pts:
            if app_pt.type == "cooker_point":
                ckt_id = "CKT-APP-CKR"
                app_pt.circuit_id = ckt_id
                assigned_phase = phases[phase_idx % len(phases)]
                phase_idx += 1
                circuits.append(
                    Circuit(
                        id=ckt_id,
                        name="Electric Cooker Circuit",
                        description=f"Dedicated 32A cooker supply ({app_pt.room_name})",
                        circuit_type="appliance",
                        points_count=1,
                        connected_load_w=app_pt.power_rating_w,
                        phase=assigned_phase,
                        cable=rules.get("cooker_cable", "3 x 6.0 mm² Cu/PVC"),
                        protection=rules.get("cooker_mcb", "32A Type B"),
                        rcd="30mA Type A RCD",
                        status="CALCULATED",
                        review_notes="Direct feed from consumer unit to 45A cooker control unit.",
                    )
                )
            elif app_pt.type == "water_heater":
                ckt_id = f"CKT-APP-WTR-{phase_idx:02d}"
                app_pt.circuit_id = ckt_id
                assigned_phase = phases[phase_idx % len(phases)]
                phase_idx += 1
                circuits.append(
                    Circuit(
                        id=ckt_id,
                        name=f"Water Heater ({app_pt.room_name})",
                        description="Dedicated fixed water heater supply",
                        circuit_type="appliance",
                        points_count=1,
                        connected_load_w=app_pt.power_rating_w,
                        phase=assigned_phase,
                        cable=rules.get("water_heater_cable", "3 x 2.5 mm² Cu/PVC"),
                        protection=rules.get("water_heater_mcb", "20A Type B"),
                        rcd="30mA Type A RCD",
                        status="CALCULATED",
                        review_notes="Dedicated circuit for water heating equipment with 30mA RCD.",
                    )
                )
            elif app_pt.type == "ac_point":
                ckt_id = f"CKT-APP-AC-{phase_idx:02d}"
                app_pt.circuit_id = ckt_id
                assigned_phase = phases[phase_idx % len(phases)]
                phase_idx += 1
                circuits.append(
                    Circuit(
                        id=ckt_id,
                        name=f"Air Conditioner ({app_pt.room_name})",
                        description="Air conditioner compressor unit",
                        circuit_type="appliance",
                        points_count=1,
                        connected_load_w=app_pt.power_rating_w,
                        phase=assigned_phase,
                        cable="3 x 2.5 mm² Cu/PVC",
                        protection="16A Type C MCB",
                        rcd="30mA Type A RCD",
                        status="CALCULATED",
                        review_notes="Type C curve MCB specified for motor starting inrush current.",
                    )
                )

        # Fallback: any unassigned point defaults to the general socket circuit or first circuit
        fallback_ckt = circuits[0].id if circuits else "CKT-GEN-01"
        for p in updated_points:
            if not p.circuit_id:
                p.circuit_id = fallback_ckt

        return updated_points, circuits

    @staticmethod
    def generate_wiring_arcs(
        points: List[ElectricalPoint],
    ) -> List[WiringArc]:
        """
        Stage 3: Generates clean CAD Bézier spline loops connecting each wall switch
        to its commanded luminaire(s) using GeometryEngine.
        """
        arcs: List[WiringArc] = []
        arc_idx = 1

        # Group points by room
        room_switches: Dict[str, List[ElectricalPoint]] = {}
        room_lights: Dict[str, List[ElectricalPoint]] = {}

        for p in points:
            if "switch" in p.type and p.x_ratio is not None and p.y_ratio is not None:
                room_switches.setdefault(p.room_id, []).append(p)
            elif p.type == "lighting" and p.x_ratio is not None and p.y_ratio is not None:
                room_lights.setdefault(p.room_id, []).append(p)

        for room_id, lights in room_lights.items():
            switches = room_switches.get(room_id, [])
            if not switches:
                continue

            for lt in lights:
                # Find closest switch in room
                nearest_sw = min(
                    switches,
                    key=lambda s: math.hypot(s.x_ratio - lt.x_ratio, s.y_ratio - lt.y_ratio),
                )
                sw_pt = Point(nearest_sw.x_ratio, nearest_sw.y_ratio)
                lt_pt = Point(lt.x_ratio, lt.y_ratio)

                arc_geom = GeometryEngine.generate_wiring_arc(sw_pt, lt_pt, sag=0.22)

                arcs.append(
                    WiringArc(
                        id=f"arc_{arc_idx:03d}",
                        circuit_id=nearest_sw.circuit_id or lt.circuit_id,
                        room_id=room_id,
                        switch_id=nearest_sw.id,
                        luminaire_id=lt.id,
                        start_point=[arc_geom["start"][0], arc_geom["start"][1]],
                        control_point=[arc_geom["control"][0], arc_geom["control"][1]],
                        end_point=[arc_geom["end"][0], arc_geom["end"][1]],
                        length_norm=arc_geom["length"],
                    )
                )
                arc_idx += 1

        return arcs

