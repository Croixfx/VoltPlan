from typing import List, Optional
from app.engineering_rules.registry import get_engineering_standard
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.schemas.electrical import ElectricalPoint


class ElectricalEngine:
    """
    Deterministic electrical engineering rules engine.
    Translates architectural building observations into standards-compliant electrical points.
    """

    @staticmethod
    def generate_recommendations(
        rooms: List[RoomObservation],
        architectural_features: Optional[List[ArchitecturalFeature]] = None,
        building_type: str = "Residential",
        standard_name: str = "RS IEC 60364",
        image_path: Optional[str] = None,
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
                points.append(
                    ElectricalPoint(
                        id=f"pt_{point_idx:03d}",
                        room_id=room.id,
                        room_name=room.name,
                        type=item["type"],
                        quantity=item["quantity"],
                        power_rating_w=item["power_rating_w"],
                        x_ratio=item.get("x_ratio"),
                        y_ratio=item.get("y_ratio"),
                        recommended_cable=item.get("recommended_cable"),
                        recommended_protection=item.get("recommended_protection"),
                        rule_reference=item["rule_reference"],
                        status=item["status"],
                        review_notes=item.get("review_notes"),
                    )
                )
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
                points.append(
                    ElectricalPoint(
                        id=f"pt_{point_idx:03d}",
                        room_id=room.id,
                        room_name=room.name,
                        type=item["type"],
                        quantity=item["quantity"],
                        power_rating_w=item["power_rating_w"],
                        x_ratio=item.get("x_ratio"),
                        y_ratio=item.get("y_ratio"),
                        recommended_cable=item.get("recommended_cable"),
                        recommended_protection=item.get("recommended_protection"),
                        rule_reference=item["rule_reference"],
                        status=item["status"],
                        review_notes=item.get("review_notes"),
                    )
                )
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
                points.append(
                    ElectricalPoint(
                        id=f"pt_{point_idx:03d}",
                        room_id=room.id,
                        room_name=room.name,
                        type=item["type"],
                        quantity=item["quantity"],
                        power_rating_w=item["power_rating_w"],
                        x_ratio=item.get("x_ratio"),
                        y_ratio=item.get("y_ratio"),
                        recommended_cable=item.get("recommended_cable"),
                        recommended_protection=item.get("recommended_protection"),
                        rule_reference=item["rule_reference"],
                        status=item["status"],
                        review_notes=item.get("review_notes"),
                    )
                )
                point_idx += 1

        return points
