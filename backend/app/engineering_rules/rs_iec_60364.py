import math
from typing import List, Optional, Dict, Any
from shapely.geometry import Point, LineString, Polygon
from app.engineering_rules.base import BaseElectricalStandard
from app.services.geometry_engine import GeometryEngine


class RsIec60364Standard(BaseElectricalStandard):
    """
    Rwandan Standard / International Electrotechnical Commission (RS IEC 60364).
    Low-voltage electrical installations standard for Rwanda.
    """

    def get_standard_code(self) -> str:
        return "RS IEC 60364"

    def get_lighting_recommendations(
        self,
        room_name: str,
        area_m2: Optional[float],
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        name_lower = room_name.lower()
        points = []

        # Determine points count
        count = 1
        review_required = False
        notes = "Standard minimum: 1 central luminaire."

        if area_m2 is not None:
            if area_m2 > 35:
                count = 3
                notes = f"Large room ({area_m2:.1f} m²): 3 distributed lighting points recommended."
            elif area_m2 > 18:
                count = 2
                notes = f"Medium room ({area_m2:.1f} m²): 2 distributed lighting points recommended."
            else:
                count = 1
                notes = f"Standard room ({area_m2:.1f} m²): 1 central luminaire."
        else:
            review_required = True
            notes = "Area dimensions unverified; preliminary allocation of 1 luminaire. REQUIRES ENGINEER REVIEW."

        # Compute luminaire point coordinates if bounds available
        coords = self._distribute_points(count, room_bounds, offset_ratio=0.5, image_path=image_path)

        for i in range(count):
            pt_coord = coords[i] if i < len(coords) else (None, None)
            points.append({
                "type": "lighting",
                "quantity": 1,
                "power_rating_w": 60.0,
                "x_ratio": pt_coord[0],
                "y_ratio": pt_coord[1],
                "recommended_cable": "3 x 1.5 mm² Cu/PVC",
                "recommended_protection": "10A Type B MCB",
                "rule_reference": "RS IEC 60364-5-52 / CIBSE SLL Code for Lighting",
                "status": "REQUIRES_ENGINEER_REVIEW" if review_required else "RECOMMENDED",
                "review_notes": notes,
            })

        # Add switch point(s) for the room conforming to strict spatial rules:
        # 1. Every switch MUST attach directly to a wall perimeter—never float in open space.
        # 2. Mount within 20 cm of the door frame on the handle/latch (strike) side strictly
        #    outside the door opening swing (RS IEC 60364-5-53 / NECA 1).
        is_2way = "corridor" in name_lower or "hall" in name_lower or "stair" in name_lower
        switch_type = "switch_2way" if is_2way else "switch_1way"

        sw_coord = self._get_switch_position(
            room_name=room_name,
            room_bounds=room_bounds,
            architectural_features=architectural_features,
            is_secondary=False,
            image_path=image_path,
        )

        points.append({
            "type": switch_type,
            "quantity": 1,
            "power_rating_w": 0.0,
            "x_ratio": sw_coord[0],
            "y_ratio": sw_coord[1],
            "recommended_cable": "3 x 1.5 mm² Cu/PVC",
            "recommended_protection": "10A Type B MCB",
            "rule_reference": "RS IEC 60364-5-53 / NECA 1: Wall-Attached Switch Placement",
            "status": "RECOMMENDED",
            "review_notes": (
                "Mounted flush on wall within 20 cm of door frame on handle/latch (strike) side "
                "outside the door opening swing."
            ),
        })

        if is_2way:
            sw_coord_2 = self._get_switch_position(
                room_name=room_name,
                room_bounds=room_bounds,
                architectural_features=architectural_features,
                is_secondary=True,
                image_path=image_path,
            )
            points.append({
                "type": "switch_2way",
                "quantity": 1,
                "power_rating_w": 0.0,
                "x_ratio": sw_coord_2[0],
                "y_ratio": sw_coord_2[1],
                "recommended_cable": "3 x 1.5 mm² Cu/PVC",
                "recommended_protection": "10A Type B MCB",
                "rule_reference": "RS IEC 60364-5-53: Multi-Way Switching",
                "status": "RECOMMENDED",
                "review_notes": (
                    "Secondary 2-way switch mounted flush on wall within 20 cm of exit door frame on strike side."
                ),
            })

        return points

    def get_socket_recommendations(
        self,
        room_name: str,
        area_m2: Optional[float],
        building_type: str,
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        name_lower = room_name.lower()
        points = []

        # Bathroom special case: IEC 60364-7-701 strict zone restrictions
        if any(term in name_lower for term in ["bath", "toilet", "wc", "washroom", "shower"]):
            shower_poly = None
            if architectural_features:
                for f in architectural_features:
                    f_type = f.get("type") if isinstance(f, dict) else getattr(f, "type", None)
                    f_bounds = f.get("bounds") if isinstance(f, dict) else getattr(f, "bounds", None)
                    if f_type in ["shower", "bathtub"] and f_bounds and len(f_bounds) >= 4:
                        shower_poly = GeometryEngine.create_room_polygon(f_bounds)
                        break

            room_poly = GeometryEngine.create_room_polygon(room_bounds)
            safe_pt = GeometryEngine.get_safe_bathroom_socket_position(
                room_poly,
                shower_polygon=shower_poly,
            )
            if image_path:
                safe_pt = GeometryEngine.snap_to_physical_wall(safe_pt, image_path=image_path, room_polygon=room_poly)

            points.append({
                "type": "single_socket",
                "quantity": 1,
                "power_rating_w": 50.0,  # Shaver outlet
                "x_ratio": round(safe_pt.x, 3),
                "y_ratio": round(safe_pt.y, 3),
                "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                "recommended_protection": "16A Type B MCB + 30mA RCD",
                "rule_reference": "RS IEC 60364-7-701: Locations containing a bath or shower (Outside Zone 2)",
                "status": "RECOMMENDED" if shower_poly else "REQUIRES_ENGINEER_REVIEW",
                "review_notes": (
                    "IEC 60364-7-701 zone restrictions: Sockets prohibited in Zone 0 and Zone 1. "
                    "Positioned on safe wall outside Zone 2 buffer (~60 cm) with 30mA RCD protection."
                ),
            })
            return points

        # Kitchen socket rules
        if "kitchen" in name_lower or "pantry" in name_lower:
            count = 4
            coords = self._distribute_points(count, room_bounds, offset_ratio=0.8, image_path=image_path)
            for i in range(count):
                pt_coord = coords[i] if i < len(coords) else (None, None)
                points.append({
                    "type": "twin_socket",
                    "quantity": 1,
                    "power_rating_w": 500.0,  # Typical kitchen appliance allowance per twin socket
                    "x_ratio": pt_coord[0],
                    "y_ratio": pt_coord[1],
                    "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                    "recommended_protection": "20A Type B MCB + 30mA RCD",
                    "rule_reference": "RS IEC 60364-8-1: Kitchen Worktop Power Outlets",
                    "status": "RECOMMENDED",
                    "review_notes": "13A twin socket outlet positioned above countertop.",
                })
            # Add refrigerator socket
            rf_coord = None
            if architectural_features:
                for f in architectural_features:
                    f_type = f.get("type") if isinstance(f, dict) else getattr(f, "type", None)
                    f_bounds = f.get("bounds") if isinstance(f, dict) else getattr(f, "bounds", None)
                    if f_type == "refrigerator" and f_bounds and len(f_bounds) >= 4:
                        rf_coord = ((f_bounds[0] + f_bounds[2]) / 2.0, (f_bounds[1] + f_bounds[3]) / 2.0)
                        break

            if rf_coord is None:
                rf_coord = self._get_perimeter_point(room_bounds, position="west")

            points.append({
                "type": "single_socket",
                "quantity": 1,
                "power_rating_w": 350.0,
                "x_ratio": round(rf_coord[0], 3),
                "y_ratio": round(rf_coord[1], 3),
                "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                "recommended_protection": "16A Type B MCB + 30mA RCD",
                "rule_reference": "RS IEC 60364-5-53: Dedicated Refrigerator Outlet",
                "status": "RECOMMENDED",
                "review_notes": "Dedicated single socket for refrigeration equipment.",
            })
            return points

        # General rooms: Living Room, Bedrooms, Offices, Corridors
        count = 2
        review_required = False
        notes = "Standard room baseline allocation."

        if "living" in name_lower or "lounge" in name_lower or "salon" in name_lower:
            count = 4
            notes = "Living area: minimum 4 twin switched socket outlets for entertainment/accessories."
        elif "master" in name_lower:
            count = 3
            notes = "Master bedroom: 3 twin socket outlets (bedside and vanity/dresser)."
        elif "bed" in name_lower:
            count = 2
            notes = "Standard bedroom: 2 twin socket outlets."
        elif "office" in name_lower or "study" in name_lower:
            count = 4
            notes = "Home office / study: 4 twin socket outlets for computing workstations."
        elif "corridor" in name_lower or "hall" in name_lower:
            count = 1
            notes = "Circulation area: 1 service twin socket for maintenance."
        elif "veranda" in name_lower or "balcony" in name_lower or "terrace" in name_lower:
            count = 1
            notes = "Exterior covered space: 1 IP55 weatherproof socket. RCD protected."
        else:
            if area_m2 is None:
                review_required = True
                notes = "Room area unverified; preliminary socket allocation. REQUIRES ENGINEER REVIEW."

        coords = self._distribute_points(count, room_bounds, offset_ratio=0.8, image_path=image_path)
        for i in range(count):
            pt_coord = coords[i] if i < len(coords) else (None, None)
            points.append({
                "type": "twin_socket",
                "quantity": 1,
                "power_rating_w": 250.0,
                "x_ratio": pt_coord[0],
                "y_ratio": pt_coord[1],
                "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                "recommended_protection": "20A Type B MCB + 30mA RCD",
                "rule_reference": "RS IEC 60364-4-41: Socket Outlets with 30mA RCD",
                "status": "REQUIRES_ENGINEER_REVIEW" if review_required else "RECOMMENDED",
                "review_notes": notes,
            })

        return points

    def get_dedicated_appliance_points(
        self,
        room_name: str,
        building_type: str,
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        name_lower = room_name.lower()
        points = []

        # Kitchen: Cooker Point
        if "kitchen" in name_lower:
            ck_coord = None
            if architectural_features:
                for f in architectural_features:
                    f_type = f.get("type") if isinstance(f, dict) else getattr(f, "type", None)
                    f_bounds = f.get("bounds") if isinstance(f, dict) else getattr(f, "bounds", None)
                    if f_type in ["cooker_stove", "cooker"] and f_bounds and len(f_bounds) >= 4:
                        ck_coord = ((f_bounds[0] + f_bounds[2]) / 2.0, (f_bounds[1] + f_bounds[3]) / 2.0)
                        break

            if ck_coord is None:
                ck_coord = self._get_perimeter_point(room_bounds, position="south")

            points.append({
                "type": "cooker_point",
                "quantity": 1,
                "power_rating_w": 6000.0,  # 6 kW cooker baseline
                "x_ratio": round(ck_coord[0], 3),
                "y_ratio": round(ck_coord[1], 3),
                "recommended_cable": "3 x 6.0 mm² Cu/PVC",
                "recommended_protection": "32A Type B MCB",
                "rule_reference": "RS IEC 60364-5-52: Electric Range / Cooker Circuit",
                "status": "RECOMMENDED",
                "review_notes": "45A DP Cooker control unit with 13A socket outlet.",
            })

        # Bathroom: Water Heater / Geyser
        if any(term in name_lower for term in ["bath", "shower", "washroom"]):
            # RS IEC 60364-7-701: Fixed Water Heating Equipment must NEVER be in Zone 0, 1, or 2 (near shower/tub)
            # Find shower position if any to avoid wet wall
            shower_wall = "north"
            if architectural_features:
                for f in architectural_features:
                    f_type = f.get("type") if isinstance(f, dict) else getattr(f, "type", None)
                    f_bounds = f.get("bounds") if isinstance(f, dict) else getattr(f, "bounds", None)
                    if f_type in ["shower", "bathtub"] and f_bounds and room_bounds:
                        if f_bounds[1] <= (room_bounds[1] + room_bounds[3]) / 2:
                            shower_wall = "north"
                        else:
                            shower_wall = "south"
                        break

            dry_pos = "south" if shower_wall == "north" else "north"
            wh_coord = self._get_perimeter_point(room_bounds, position=dry_pos)
            points.append({
                "type": "water_heater",
                "quantity": 1,
                "power_rating_w": 2500.0,  # 2.5 kW water heater baseline
                "x_ratio": wh_coord[0],
                "y_ratio": wh_coord[1],
                "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                "recommended_protection": "20A Type B MCB + 30mA RCD",
                "rule_reference": "RS IEC 60364-7-701: Fixed Water Heating Equipment",
                "status": "RECOMMENDED",
                "review_notes": "20A DP Isolator with neon indicator mounted outside wet zone (Zone 3).",
            })

        # Living Room & Master Bedroom: AC point if applicable
        if "living" in name_lower or "master" in name_lower:
            ac_coord = self._get_perimeter_point(room_bounds, position="north")
            points.append({
                "type": "ac_point",
                "quantity": 1,
                "power_rating_w": 2000.0,  # 12,000 BTU split AC unit
                "x_ratio": ac_coord[0],
                "y_ratio": ac_coord[1],
                "recommended_cable": "3 x 2.5 mm² Cu/PVC",
                "recommended_protection": "16A Type C MCB",
                "rule_reference": "RS IEC 60364-5-52: Air Conditioning Motor Load (Type C Curve)",
                "status": "RECOMMENDED",
                "review_notes": "Dedicated 20A rotary isolator for AC compressor unit.",
            })

        return points

    def get_circuit_rules(self) -> Dict[str, Any]:
        return {
            "max_lighting_points_per_circuit": 12,
            "max_lighting_wattage_per_circuit": 1000,
            "lighting_cable": "3 x 1.5 mm² Cu/PVC",
            "lighting_mcb": "10A Type B",
            "max_sockets_per_radial_circuit": 8,
            "max_socket_wattage_per_circuit": 3000,
            "socket_cable": "3 x 2.5 mm² Cu/PVC",
            "socket_mcb": "20A Type B",
            "cooker_cable": "3 x 6.0 mm² Cu/PVC",
            "cooker_mcb": "32A Type B",
            "water_heater_cable": "3 x 2.5 mm² Cu/PVC",
            "water_heater_mcb": "20A Type B",
            "rcd_rating": "63A 30mA Type A RCD",
            "main_switch": "100A DP Isolator",
        }

    # Helper coordinate geometry
    def _distribute_points(
        self,
        count: int,
        bounds: Optional[List[float]],
        offset_ratio: float = 0.5,
        shower_polygon: Optional[Polygon] = None,
        image_path: Optional[str] = None,
    ) -> List[tuple]:
        if not bounds or len(bounds) < 4:
            return [(None, None)] * count

        poly = GeometryEngine.create_room_polygon(bounds)

        # Luminaires (offset_ratio <= 0.6): distribute along room axes using GeometryEngine
        if offset_ratio <= 0.6:
            pts = GeometryEngine.place_distributed_luminaires(poly, count)
            return [(round(p.x, 3), round(p.y, 3)) for p in pts]

        # Perimeter wall sockets: distribute along wall perimeter using GeometryEngine
        socket_pts = GeometryEngine.distribute_wall_sockets(
            poly,
            count,
            shower_polygon=shower_polygon,
            image_path=image_path,
        )
        return [(round(p.x, 3), round(p.y, 3)) for p in socket_pts]

    def _get_perimeter_point(
        self,
        bounds: Optional[List[float]],
        position: str = "entrance",
    ) -> tuple:
        if not bounds or len(bounds) < 4:
            return (None, None)
        x1, y1, x2, y2 = bounds[0], bounds[1], bounds[2], bounds[3]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        if position == "entrance":
            return (round(x1 + (x2 - x1) * 0.15, 3), round(y2 - 0.02, 3))
        elif position == "north":
            return (round(cx, 3), round(y1 + 0.02, 3))
        elif position == "south":
            return (round(cx, 3), round(y2 - 0.02, 3))
        elif position == "east":
            return (round(x2 - 0.02, 3), round(cy, 3))
        elif position == "west":
            return (round(x1 + 0.02, 3), round(cy, 3))
        return (round(cx, 3), round(cy, 3))

    def _get_switch_position(
        self,
        room_name: str,
        room_bounds: Optional[List[float]],
        architectural_features: Optional[List[Any]] = None,
        is_secondary: bool = False,
        image_path: Optional[str] = None,
    ) -> tuple:
        """
        Calculates wall-attached switch coordinates conforming to strict architectural spatial rules:
        1. Switch MUST attach directly to a perimeter wall (never float in open space).
        2. Mount switch within 20 cm of the door frame on the handle/latch (strike) side strictly
           outside the door opening swing (RS IEC 60364-5-53 / NECA 1).
        Uses Shapely-backed GeometryEngine and OpenCV physical wall snapping.
        """
        if not room_bounds or len(room_bounds) < 4:
            return (None, None)

        room_poly = GeometryEngine.create_room_polygon(room_bounds)
        walls = GeometryEngine.get_wall_segments(room_poly)
        name_lower = room_name.lower()

        # 1. Search for matching door in architectural features by room name or spatial proximity
        door_feat = None
        if architectural_features:
            for feat in architectural_features:
                f_type = feat.get("type") if isinstance(feat, dict) else getattr(feat, "type", None)
                f_room = feat.get("room") if isinstance(feat, dict) else getattr(feat, "room", "")
                if f_type in ("door", "entrance") and (f_room.lower() in name_lower or name_lower in f_room.lower()):
                    door_feat = feat
                    break

            if not door_feat:
                for feat in architectural_features:
                    f_type = feat.get("type") if isinstance(feat, dict) else getattr(feat, "type", None)
                    if f_type in ("door", "entrance"):
                        d_pos = feat.get("door_position") if isinstance(feat, dict) else getattr(feat, "door_position", None)
                        h_pt = feat.get("hinge_point") if isinstance(feat, dict) else getattr(feat, "hinge_point", None)
                        c_pt = d_pos or h_pt
                        if c_pt and len(c_pt) == 2:
                            p = Point(c_pt[0], c_pt[1])
                            if room_poly.distance(p) <= 0.06:
                                door_feat = feat
                                break

        if door_feat and not is_secondary:
            strike_pt = door_feat.get("strike_point") if isinstance(door_feat, dict) else getattr(door_feat, "strike_point", None)
            d_pos = door_feat.get("door_position") if isinstance(door_feat, dict) else getattr(door_feat, "door_position", None)
            h_pt = door_feat.get("hinge_point") if isinstance(door_feat, dict) else getattr(door_feat, "hinge_point", None)

            d_pos_point = Point(d_pos[0], d_pos[1]) if d_pos and len(d_pos) == 2 else None
            h_point = Point(h_pt[0], h_pt[1]) if h_pt and len(h_pt) == 2 else None

            if strike_pt and len(strike_pt) == 2:
                s_point = Point(strike_pt[0], strike_pt[1])
                closest_wall = min(walls.values(), key=lambda w: w.distance(s_point))
                sw_point = GeometryEngine.place_door_switch(
                    s_point,
                    closest_wall,
                    offset_norm=GeometryEngine.DOOR_STRIKE_OFFSET_NORM,
                    door_position=d_pos_point,
                    hinge_point=h_point,
                    room_polygon=room_poly,
                    image_path=image_path,
                )
                minx, miny, maxx, maxy = room_poly.bounds
                safe_x = max(minx + 0.015, min(sw_point.x, maxx - 0.015))
                safe_y = max(miny + 0.015, min(sw_point.y, maxy - 0.015))
                return (round(safe_x, 3), round(safe_y, 3))

            d_wall = door_feat.get("wall") if isinstance(door_feat, dict) else getattr(door_feat, "wall", None)
            if d_wall and d_pos and len(d_pos) == 2:
                wall_line = walls.get(d_wall.lower(), walls["south"])
                d_point = Point(d_pos[0], d_pos[1])
                sw_point = GeometryEngine.place_door_switch(
                    d_point,
                    wall_line,
                    offset_norm=GeometryEngine.DOOR_STRIKE_OFFSET_NORM,
                    door_position=d_pos_point,
                    hinge_point=h_point,
                    room_polygon=room_poly,
                    image_path=image_path,
                )
                minx, miny, maxx, maxy = room_poly.bounds
                safe_x = max(minx + 0.015, min(sw_point.x, maxx - 0.015))
                safe_y = max(miny + 0.015, min(sw_point.y, maxy - 0.015))
                return (round(safe_x, 3), round(safe_y, 3))

        # 2. Architectural layout heuristic via GeometryEngine
        if is_secondary:
            if "corridor" in name_lower or "hall" in name_lower or "stair" in name_lower:
                exit_wall = walls["south"]
                mid_pt = Point((room_bounds[0] + room_bounds[2]) / 2.0, room_bounds[3])
                sw_point = GeometryEngine.place_door_switch(mid_pt, exit_wall, offset_norm=0.0, room_polygon=room_poly, image_path=image_path)
                return (sw_point.x, sw_point.y)
            else:
                east_wall = walls["east"]
                mid_pt = Point(room_bounds[2], (room_bounds[1] + room_bounds[3]) / 2.0)
                sw_point = GeometryEngine.place_door_switch(mid_pt, east_wall, offset_norm=0.0, room_polygon=room_poly, image_path=image_path)
                return (sw_point.x, sw_point.y)

        # Target entrance wall selection based on topology
        if "corridor" in name_lower or "hall" in name_lower:
            target_wall = walls["north"]
            ref_pt = Point(room_bounds[0] + (room_bounds[2] - room_bounds[0]) * 0.20, room_bounds[1])
        elif "living" in name_lower or "salon" in name_lower or "lounge" in name_lower:
            target_wall = walls["south"]
            ref_pt = Point(room_bounds[0] + (room_bounds[2] - room_bounds[0]) * 0.18, room_bounds[3])
        elif "kitchen" in name_lower:
            target_wall = walls["west"]
            ref_pt = Point(room_bounds[0], room_bounds[1] + (room_bounds[3] - room_bounds[1]) * 0.25)
        elif any(b in name_lower for b in ["bath", "toilet", "wc", "shower"]):
            target_wall = walls["north"]
            ref_pt = Point(room_bounds[0] + (room_bounds[2] - room_bounds[0]) * 0.35, room_bounds[1])
        elif "master" in name_lower:
            target_wall = walls["east"]
            ref_pt = Point(room_bounds[2], room_bounds[1] + (room_bounds[3] - room_bounds[1]) * 0.22)
        else:
            if room_bounds[1] >= 0.5:
                target_wall = walls["north"]
                ref_pt = Point(room_bounds[0] + (room_bounds[2] - room_bounds[0]) * 0.20, room_bounds[1])
            else:
                target_wall = walls["south"]
                ref_pt = Point(room_bounds[0] + (room_bounds[2] - room_bounds[0]) * 0.20, room_bounds[3])

        sw_point = GeometryEngine.place_door_switch(
            ref_pt,
            target_wall,
            offset_norm=GeometryEngine.DOOR_STRIKE_OFFSET_NORM,
            room_polygon=room_poly,
            image_path=image_path,
        )
        return (sw_point.x, sw_point.y)
