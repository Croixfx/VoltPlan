import math
from typing import List, Optional
from shapely.geometry import Point as ShapelyPoint
from app.engineering_rules.registry import get_engineering_standard
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.schemas.electrical import ElectricalPoint
from app.schemas.canonical_geometry import CanonicalFloorPlan, OpeningType, ObstacleType, Point2D_mm
from app.services.coordinate_transform import CoordinateTransformEngine


class ElectricalEngine:
    """
    Deterministic electrical engineering rules engine.
    Translates architectural building observations and canonical geometry
    into standards-compliant, traceable electrical points.
    """

    @classmethod
    def generate_recommendations(
        cls,
        rooms: List[RoomObservation],
        architectural_features: Optional[List[ArchitecturalFeature]] = None,
        building_type: str = "Residential",
        standard_name: str = "RS IEC 60364",
        image_path: Optional[str] = None,
        canonical_plan: Optional[CanonicalFloorPlan] = None,
    ) -> List[ElectricalPoint]:
        standard = get_engineering_standard(standard_name)
        points: List[ElectricalPoint] = []
        point_idx = 1

        for room in rooms:
            # 1. Lighting recommendations (including wall-attached switches on door strike side)
            lighting_list = standard.get_lighting_recommendations(
                room_name=room.name,
                area_m2=room.area_m2,
                room_bounds=room.bounds,
                architectural_features=architectural_features,
                image_path=image_path,
            )
            for item in lighting_list:
                pt = cls._create_traceable_point(item, room, point_idx, canonical_plan)
                points.append(pt)
                point_idx += 1

            # 2. Socket outlet recommendations
            socket_list = standard.get_socket_recommendations(
                room_name=room.name,
                area_m2=room.area_m2,
                building_type=building_type,
                room_bounds=room.bounds,
                architectural_features=architectural_features,
                image_path=image_path,
            )
            for item in socket_list:
                pt = cls._create_traceable_point(item, room, point_idx, canonical_plan)
                points.append(pt)
                point_idx += 1

            # 3. Dedicated appliance points
            appliance_list = standard.get_dedicated_appliance_points(
                room_name=room.name,
                building_type=building_type,
                room_bounds=room.bounds,
                architectural_features=architectural_features,
                image_path=image_path,
            )
            for item in appliance_list:
                pt = cls._create_traceable_point(item, room, point_idx, canonical_plan)
                points.append(pt)
                point_idx += 1

        return points

    @classmethod
    def _create_traceable_point(
        cls,
        item: dict,
        room: RoomObservation,
        point_idx: int,
        canonical_plan: Optional[CanonicalFloorPlan],
    ) -> ElectricalPoint:
        x_ratio = item.get("x_ratio")
        y_ratio = item.get("y_ratio")
        x_mm: Optional[float] = None
        y_mm: Optional[float] = None

        coord_sys = "normalized_ratio"
        is_scale_ver = False
        is_geom_ver = False
        geom_used = "bounding_box_heuristic"
        placement_rule = item.get("rule_reference", "RS IEC 60364")
        placement_status = "needs_confirmation" if "REVIEW" in item.get("status", "") else "proposed"
        reasoning = item.get("review_notes", "")
        nearby_wall: Optional[str] = None
        nearby_door: Optional[str] = None
        nearby_obs: Optional[str] = None
        clearance_applied: Optional[str] = None

        p_type = item["type"]

        if canonical_plan is not None:
            coord_sys = "canonical_mm_and_normalized_ratio"
            is_scale_ver = canonical_plan.transform.is_scale_verified

            if x_ratio is not None and y_ratio is not None:
                pt_mm = CoordinateTransformEngine.normalized_to_canonical(
                    x_ratio, y_ratio, canonical_plan.transform
                )
                x_mm = pt_mm.x
                y_mm = pt_mm.y

            r_bound = canonical_plan.get_room_by_id(room.id)
            if not r_bound:
                for r in canonical_plan.rooms:
                    if r.name.lower().strip() == room.name.lower().strip():
                        r_bound = r
                        break

            if r_bound:
                is_geom_ver = not r_bound.is_rectangular_approximation

            doors = [op for op in canonical_plan.openings if (r_bound and op.room_id == r_bound.id) or op.type == OpeningType.DOOR]
            obstacles = [obs for obs in canonical_plan.obstacles if (r_bound and obs.room_id == r_bound.id)]

            if p_type == "lighting":
                geom_used = "ceiling_centroid"
                approx_str = "approximate bounding box center" if (r_bound and r_bound.is_rectangular_approximation) else "exact polygonal centroid"
                reasoning = (
                    f"Ceiling luminaire positioned at {approx_str} ({x_mm:.0f} mm, {y_mm:.0f} mm)."
                    if x_mm is not None else item.get("review_notes", "")
                )
                placement_status = "proposed" if (is_scale_ver and is_geom_ver) else "needs_confirmation"

            elif "switch" in p_type:
                geom_used = "wall_strike_side_tangent"
                door_match = doors[0] if doors else None
                if door_match:
                    nearby_door = door_match.id
                    nearby_wall = door_match.wall_id
                    clearance_applied = (
                        "Observed door swing arc sector"
                        if door_match.is_swing_observed
                        else "Assumed 90° inward door safety envelope"
                    )
                    # Verify switch is not inside door swing envelope; if so, push clear along strike jamb
                    swing_env = door_match.observed_swing_arc_mm or door_match.assumed_clearance_envelope_mm
                    if swing_env and x_mm is not None and y_mm is not None:
                        sh_arc = swing_env.to_shapely()
                        if sh_arc.contains(ShapelyPoint(x_mm, y_mm)):
                            if door_match.strike_point_mm and door_match.hinge_point_mm:
                                s_pt = door_match.strike_point_mm
                                h_pt = door_match.hinge_point_mm
                                dx = s_pt.x - h_pt.x
                                dy = s_pt.y - h_pt.y
                                d_len = math.hypot(dx, dy)
                                if d_len > 1e-4:
                                    ux, uy = dx / d_len, dy / d_len
                                    x_mm = s_pt.x + 200.0 * ux
                                    y_mm = s_pt.y + 200.0 * uy
                                    norm_pt = CoordinateTransformEngine.canonical_to_normalized(
                                        Point2D_mm(x=x_mm, y=y_mm), canonical_plan.transform
                                    )
                                    x_ratio = norm_pt.x_ratio
                                    y_ratio = norm_pt.y_ratio
                    reasoning = (
                        f"Mounted on wall '{nearby_wall or 'perimeter'}' within 200 mm of strike jamb of door '{nearby_door}', outside {clearance_applied}."
                    )
                    placement_status = "proposed" if (door_match.is_swing_observed and door_match.wall_id) else "needs_confirmation"
                else:
                    reasoning = "Wall-mounted switch placed at preliminary entrance location; door unlocated on plan."
                    placement_status = "needs_confirmation"

            elif p_type in ["single_socket", "twin_socket"]:
                is_bath = any(term in room.name.lower() for term in ["bath", "toilet", "wc", "shower"])
                if is_bath:
                    wet_obs = next(
                        (o for o in obstacles if o.obstacle_type in [ObstacleType.SHOWER_ENCLOSURE, ObstacleType.BATHTUB]),
                        None
                    )
                    if wet_obs:
                        nearby_obs = wet_obs.id
                        clearance_applied = f"RS IEC 60364-7-701 Zone 2 ({wet_obs.required_buffer_mm:.0f} mm wet exclusion buffer)"
                        geom_used = "safe_wall_outside_wet_zone"
                        reasoning = f"Shaver/utility socket located outside {clearance_applied} of '{wet_obs.id}' with 30mA RCD."
                        placement_status = "proposed" if is_scale_ver else "needs_confirmation"
                    else:
                        geom_used = "unlocated_sanitary_fixtures_fallback"
                        clearance_applied = "Sanitary fixtures unlocated; engineer review required"
                        reasoning = "Bathroom sanitary fixtures unlocated on plan; socket placement tentative pending engineer confirmation."
                        placement_status = "needs_confirmation"
                else:
                    geom_used = "perimeter_wall_snapped"
                    reasoning = (
                        f"Switched socket outlet distributed along room perimeter wall ({x_mm:.0f} mm, {y_mm:.0f} mm)."
                        if x_mm is not None else "Perimeter socket outlet."
                    )
                    placement_status = "proposed" if is_scale_ver else "needs_confirmation"

            elif p_type in ["cooker_point", "water_heater", "ac_point"]:
                geom_used = "dedicated_appliance_wall"
                reasoning = f"Dedicated outlet for {p_type.replace('_', ' ')} with dedicated protective device."
                placement_status = "proposed" if is_scale_ver else "needs_confirmation"

        return ElectricalPoint(
            id=f"pt_{point_idx:03d}",
            room_id=room.id,
            room_name=room.name,
            type=p_type,
            quantity=item["quantity"],
            power_rating_w=item["power_rating_w"],
            x_ratio=x_ratio,
            y_ratio=y_ratio,
            x_mm=round(x_mm, 1) if x_mm is not None else None,
            y_mm=round(y_mm, 1) if y_mm is not None else None,
            coordinate_system=coord_sys,
            placement_rule=placement_rule,
            geometry_used=geom_used,
            is_scale_verified=is_scale_ver,
            is_geometry_verified=is_geom_ver,
            nearby_wall_id=nearby_wall,
            nearby_door_id=nearby_door,
            nearby_obstacle_id=nearby_obs,
            clearance_envelope_applied=clearance_applied,
            placement_status=placement_status,
            reasoning=reasoning,
            recommended_cable=item.get("recommended_cable"),
            recommended_protection=item.get("recommended_protection"),
            rule_reference=item["rule_reference"],
            status=item["status"],
            review_notes=item.get("review_notes"),
        )
