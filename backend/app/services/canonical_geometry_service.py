import math
import os
import uuid
from typing import List, Optional, Dict, Any, Tuple
import cv2
import numpy as np
from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon, LineString as ShapelyLineString

from app.schemas.canonical_geometry import (
    Point2D_mm,
    Polygon2D_mm,
    BoundingBox2D_mm,
    PlanTransform,
    CoordinateOrigin,
    ScaleStatus,
    WallClassification,
    WallSegment,
    OpeningType,
    DoorSwingDirection,
    Opening,
    ObstacleType,
    FixedObstacle,
    RoomType,
    RoomBoundary,
    SourceProvenance,
    FloorLevel,
    Building,
    CanonicalFloorPlan,
)
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.services.coordinate_transform import CoordinateTransformEngine


class CanonicalGeometryService:
    """
    Core service to build, validate, and adapt the Canonical Building Geometry Model.
    Provides:
      1. Canonical model construction from AI vision and architectural features.
      2. OpenCV morphological wall line profile verification (physical vs virtual divider).
      3. Precise 90-degree door swing wedge envelope generation for collision prevention.
      4. Fixed obstacle exclusion buffering (e.g. 600mm wet zone per RS IEC 60364-7-701).
      5. Full backward-compatibility adapter for legacy Flutter canvas / API consumption.
    """

    # Default architectural assumptions in millimeters
    DEFAULT_DOOR_WIDTH_MM = 850.0       # Standard interior clear door leaf
    DEFAULT_WALL_THICKNESS_MM = 150.0   # Standard internal partition thickness
    WET_ZONE_CLEARANCE_MM = 600.0       # RS IEC 60364 Zone 2 buffer
    FURNITURE_CLEARANCE_MM = 100.0      # Clearance around furniture

    @classmethod
    def build_canonical_floor_plan(
        cls,
        rooms: List[RoomObservation],
        features: List[ArchitecturalFeature],
        image_path: Optional[str] = None,
        pixel_width: int = 1200,
        pixel_height: int = 900,
        scale_mm_per_pixel: Optional[float] = None,
        is_scale_verified: bool = False,
        scale_status: ScaleStatus = ScaleStatus.ESTIMATED_HEURISTIC,
        scale_ratio_str: Optional[str] = None,
        building_type: str = "Residential",
        standard_name: str = "RS IEC 60364",
        source_file_name: str = "floor_plan.png",
    ) -> CanonicalFloorPlan:
        """
        Builds a canonical physical building geometry model from architectural observations.
        """
        # 1. Establish Plan Transform
        if scale_mm_per_pixel is not None and scale_mm_per_pixel > 0:
            transform = PlanTransform(
                pixel_width=pixel_width,
                pixel_height=pixel_height,
                scale_mm_per_pixel=round(scale_mm_per_pixel, 4),
                scale_status=scale_status if is_scale_verified else ScaleStatus.ESTIMATED_HEURISTIC,
                scale_ratio_str=scale_ratio_str or f"1 px = {scale_mm_per_pixel:.1f} mm",
                origin=CoordinateOrigin.TOP_LEFT,
                rotation_deg=0.0,
                is_scale_verified=is_scale_verified,
            )
        else:
            # Default architectural estimate (1:100 scale at ~150 DPI => ~16.93 mm/px)
            # Marked explicitly as unverified heuristic
            default_est = 16.93
            transform = PlanTransform(
                pixel_width=pixel_width,
                pixel_height=pixel_height,
                scale_mm_per_pixel=default_est,
                scale_status=ScaleStatus.ESTIMATED_HEURISTIC,
                scale_ratio_str="Estimated 1:100 (~16.9 mm/px)",
                origin=CoordinateOrigin.TOP_LEFT,
                rotation_deg=0.0,
                is_scale_verified=False,
            )

        # 2. Source Provenance
        provenance = SourceProvenance(
            source_file=source_file_name,
            file_type=os.path.splitext(source_file_name)[1].lstrip(".").lower() or "png",
            raster_width_px=pixel_width,
            raster_height_px=pixel_height,
            dpi=150.0,
            detection_method="ai_vision_canonical_fusion",
            unresolved_geometry=[],
            geometry_warnings=[],
        )

        if not transform.is_scale_verified:
            provenance.geometry_warnings.append(
                "Plan scale is uncalibrated. Area measurements and clearance buffers are provisional estimates."
            )

        # 3. Load raster image if available for OpenCV morphological wall verification
        gray_img: Optional[np.ndarray] = None
        if image_path and os.path.exists(image_path):
            try:
                gray_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            except Exception:
                gray_img = None

        canonical_rooms: List[RoomBoundary] = []
        canonical_walls: List[WallSegment] = []
        canonical_openings: List[Opening] = []
        canonical_obstacles: List[FixedObstacle] = []

        # 4. Process Rooms & Walls
        for r in rooms:
            room_type = cls._infer_room_type(r.name)
            bounds = r.bounds if r.bounds and len(r.bounds) == 4 else [0.1, 0.1, 0.9, 0.9]

            # Construct millimeter polygon for room boundary
            poly_mm = cls._construct_room_polygon_mm(bounds, transform)
            area_m2 = poly_mm.area_m2

            # Decompose boundary into 4 perimeter wall segments
            room_wall_ids: List[str] = []
            ext_pts = poly_mm.exterior
            num_pts = len(ext_pts)
            has_virtual_divider = False

            for i in range(num_pts):
                p_start = ext_pts[i]
                p_end = ext_pts[(i + 1) % num_pts]

                wall_id = f"wall_{r.id}_{i+1}"
                room_wall_ids.append(wall_id)

                # Verify physical wall presence using OpenCV raster line profile
                is_physical, conf = cls.verify_wall_profile(
                    p_start=p_start,
                    p_end=p_end,
                    transform=transform,
                    gray_img=gray_img,
                )

                classification = WallClassification.PARTITION if is_physical else WallClassification.VIRTUAL_DIVIDER
                if not is_physical:
                    has_virtual_divider = True

                wall_seg = WallSegment(
                    id=wall_id,
                    start=p_start,
                    end=p_end,
                    thickness_mm=cls.DEFAULT_WALL_THICKNESS_MM,
                    classification=classification,
                    interior_room_id=r.id,
                    is_verified_physical_wall=is_physical,
                    confidence=conf,
                )
                canonical_walls.append(wall_seg)

            room_bound = RoomBoundary(
                id=r.id,
                name=r.name,
                room_type=room_type,
                boundary_polygon_mm=poly_mm,
                area_m2=round(area_m2, 2),
                is_area_verified=transform.is_scale_verified,
                confidence=r.confidence,
                has_virtual_boundaries=has_virtual_divider,
                wall_ids=room_wall_ids,
                opening_ids=[],
                obstacle_ids=[],
            )
            canonical_rooms.append(room_bound)

        # 5. Process Architectural Features (Doors, Windows, Obstacles)
        room_by_name = {r.name.lower().strip(): r for r in canonical_rooms}

        for idx, feat in enumerate(features):
            feat_room = room_by_name.get(feat.room.lower().strip()) if feat.room else None
            room_id = feat_room.id if feat_room else (canonical_rooms[0].id if canonical_rooms else "room_1")

            f_type = feat.type.lower().strip()
            if f_type in ["door", "entrance"]:
                op = cls._process_door_opening(
                    feat=feat,
                    room_id=room_id,
                    index=idx,
                    transform=transform,
                    feat_room=feat_room,
                )
                canonical_openings.append(op)
                if feat_room:
                    feat_room.opening_ids.append(op.id)

            elif f_type == "window":
                op = cls._process_window_opening(
                    feat=feat,
                    room_id=room_id,
                    index=idx,
                    transform=transform,
                )
                canonical_openings.append(op)
                if feat_room:
                    feat_room.opening_ids.append(op.id)

            elif f_type in ["shower", "bathtub", "shower_enclosure", "wardrobe", "counter"]:
                obs = cls._process_obstacle(
                    feat=feat,
                    room_id=room_id,
                    index=idx,
                    transform=transform,
                )
                if obs:
                    canonical_obstacles.append(obs)
                    if feat_room:
                        feat_room.obstacle_ids.append(obs.id)

        # 6. Auto-detect Obstacles for Wet Rooms (Bathrooms without explicit shower feature)
        for r_bound in canonical_rooms:
            if r_bound.room_type in [RoomType.BATHROOM, RoomType.POWDER_ROOM_WC]:
                existing_wet_obs = [
                    o for o in canonical_obstacles
                    if o.room_id == r_bound.id and o.obstacle_type in [ObstacleType.SHOWER_ENCLOSURE, ObstacleType.BATHTUB]
                ]
                if not existing_wet_obs:
                    # Place standard corner shower enclosure (900mm x 900mm) with 600mm Zone 2 buffer
                    shower_obs = cls._create_default_shower_obstacle(r_bound, transform)
                    canonical_obstacles.append(shower_obs)
                    r_bound.obstacle_ids.append(shower_obs.id)

        building = Building(
            id=str(uuid.uuid4())[:8],
            name=f"{building_type} Structure",
            building_type=building_type,
            standard_applied=standard_name,
        )

        level = FloorLevel(
            id="lvl_0",
            name="Ground Floor",
            level_index=0,
            elevation_mm=0.0,
            height_clear_mm=2800.0,
        )

        return CanonicalFloorPlan(
            building=building,
            level=level,
            transform=transform,
            provenance=provenance,
            rooms=canonical_rooms,
            walls=canonical_walls,
            openings=canonical_openings,
            obstacles=canonical_obstacles,
            is_scale_verified=transform.is_scale_verified,
        )

    @classmethod
    def verify_wall_profile(
        cls,
        p_start: Point2D_mm,
        p_end: Point2D_mm,
        transform: PlanTransform,
        gray_img: Optional[np.ndarray],
    ) -> Tuple[bool, float]:
        """
        Inspects raster pixels along the candidate wall segment.
        A real physical wall has a continuous dark line profile (>55% dark pixels).
        An open-plan room divider or corridor boundary has few or no dark pixels.
        Returns: (is_physical_wall: bool, confidence: float)
        """
        if gray_img is None:
            # When raster image is unavailable, assume physical wall with moderate confidence
            return (True, 0.85)

        h, w = gray_img.shape
        # Map physical mm back to pixel coordinates
        x1_px, y1_px = CoordinateTransformEngine.canonical_to_pixel(p_start, transform)
        x2_px, y2_px = CoordinateTransformEngine.canonical_to_pixel(p_end, transform)

        # Generate sample points along the line segment
        seg_len_px = math.hypot(x2_px - x1_px, y2_px - y1_px)
        num_samples = max(5, int(seg_len_px / 4.0))

        dark_count = 0
        total_valid = 0

        for i in range(num_samples):
            t = i / max(1, num_samples - 1)
            sx = int(round(x1_px + t * (x2_px - x1_px)))
            sy = int(round(y1_px + t * (y2_px - y1_px)))

            if 0 <= sx < w and 0 <= sy < h:
                total_valid += 1
                # Check a 3x3 local patch around sample point to account for stroke thickness
                patch = gray_img[max(0, sy - 1):min(h, sy + 2), max(0, sx - 1):min(w, sx + 2)]
                if patch.size > 0 and np.min(patch) < 130:
                    dark_count += 1

        if total_valid == 0:
            return (True, 0.50)

        dark_ratio = dark_count / float(total_valid)
        is_physical = dark_ratio >= 0.55
        confidence = round(max(0.3, min(1.0, dark_ratio if is_physical else (1.0 - dark_ratio))), 2)

        return (is_physical, confidence)

    @classmethod
    def calculate_door_swing_wedge(
        cls,
        hinge_mm: Point2D_mm,
        strike_mm: Point2D_mm,
        room_poly_mm: Optional[Polygon2D_mm] = None,
        swing_dir: DoorSwingDirection = DoorSwingDirection.INWARD,
    ) -> Polygon2D_mm:
        """
        Calculates the exact 90-degree circular sector polygon swept by a swinging door leaf.
        The door leaf pivots on hinge_mm and rotates 90 degrees into the room.
        Electrical switches must NEVER land within this sweep polygon.
        """
        radius = hinge_mm.distance_to(strike_mm)
        if radius < 300.0 or radius > 1500.0:
            radius = cls.DEFAULT_DOOR_WIDTH_MM

        # Wall vector from hinge to strike
        vx = strike_mm.x - hinge_mm.x
        vy = strike_mm.y - hinge_mm.y
        mag = math.hypot(vx, vy)
        if mag < 1e-4:
            vx, vy = radius, 0.0
            mag = radius

        ux = vx / mag
        uy = vy / mag

        # Perpendicular normal vectors: n1 is 90 deg CCW (-uy, ux), n2 is 90 deg CW (uy, -ux)
        n1 = (-uy, ux)
        n2 = (uy, -ux)

        # Choose the normal pointing into the room interior
        chosen_normal = n1
        if room_poly_mm is not None:
            shapely_room = room_poly_mm.to_shapely()
            test_pt_1 = ShapelyPoint(hinge_mm.x + n1[0] * (radius * 0.5), hinge_mm.y + n1[1] * (radius * 0.5))
            test_pt_2 = ShapelyPoint(hinge_mm.x + n2[0] * (radius * 0.5), hinge_mm.y + n2[1] * (radius * 0.5))

            if shapely_room.contains(test_pt_1):
                chosen_normal = n1
            elif shapely_room.contains(test_pt_2):
                chosen_normal = n2

        # Invert if outward swing is explicitly requested
        if swing_dir == DoorSwingDirection.OUTWARD:
            chosen_normal = (-chosen_normal[0], -chosen_normal[1])

        # Generate 90-degree circular arc with 10 discrete vertices
        arc_points: List[Point2D_mm] = [hinge_mm]
        num_arc_steps = 10

        for i in range(num_arc_steps + 1):
            theta = (math.pi / 2.0) * (i / float(num_arc_steps))
            # Arc from closed leaf (u) towards open leaf (normal)
            px = hinge_mm.x + radius * (math.cos(theta) * ux + math.sin(theta) * chosen_normal[0])
            py = hinge_mm.y + radius * (math.cos(theta) * uy + math.sin(theta) * chosen_normal[1])
            arc_points.append(Point2D_mm(x=round(px, 2), y=round(py, 2)))

        return Polygon2D_mm(exterior=arc_points)

    @classmethod
    def _construct_room_polygon_mm(
        cls,
        bounds_norm: List[float],
        transform: PlanTransform,
    ) -> Polygon2D_mm:
        """Constructs a rectangular or polygonal room boundary in millimeters."""
        x1, y1, x2, y2 = bounds_norm[0], bounds_norm[1], bounds_norm[2], bounds_norm[3]
        pts_norm = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return CoordinateTransformEngine.polygon_to_canonical(pts_norm, transform, is_normalized=True)

    @classmethod
    def _process_door_opening(
        cls,
        feat: ArchitecturalFeature,
        room_id: str,
        index: int,
        transform: PlanTransform,
        feat_room: Optional[RoomBoundary],
    ) -> Opening:
        """Processes a door architectural feature into an Opening model."""
        op_id = f"door_{room_id}_{index + 1}"

        # Center point
        if feat.door_position and len(feat.door_position) >= 2:
            center_mm = CoordinateTransformEngine.normalized_to_canonical(
                feat.door_position[0], feat.door_position[1], transform
            )
        elif feat.bounds and len(feat.bounds) >= 4:
            cx = (feat.bounds[0] + feat.bounds[2]) / 2.0
            cy = (feat.bounds[1] + feat.bounds[3]) / 2.0
            center_mm = CoordinateTransformEngine.normalized_to_canonical(cx, cy, transform)
        else:
            center_mm = Point2D_mm(x=1000.0, y=1000.0)

        # Hinge & strike
        if feat.hinge_point and len(feat.hinge_point) >= 2:
            hinge_mm = CoordinateTransformEngine.normalized_to_canonical(
                feat.hinge_point[0], feat.hinge_point[1], transform
            )
        else:
            hinge_mm = Point2D_mm(x=center_mm.x - 425.0, y=center_mm.y)

        if feat.strike_point and len(feat.strike_point) >= 2:
            strike_mm = CoordinateTransformEngine.normalized_to_canonical(
                feat.strike_point[0], feat.strike_point[1], transform
            )
        else:
            strike_mm = Point2D_mm(x=center_mm.x + 425.0, y=center_mm.y)

        width_mm = hinge_mm.distance_to(strike_mm)
        if width_mm < 300.0 or width_mm > 1500.0:
            width_mm = cls.DEFAULT_DOOR_WIDTH_MM

        # Swing direction
        swing_dir = DoorSwingDirection.INWARD
        if feat.swing_direction == "out_of_room":
            swing_dir = DoorSwingDirection.OUTWARD

        # Door swing wedge sector polygon
        room_poly = feat_room.boundary_polygon_mm if feat_room else None
        swing_wedge = cls.calculate_door_swing_wedge(
            hinge_mm=hinge_mm,
            strike_mm=strike_mm,
            room_poly_mm=room_poly,
            swing_dir=swing_dir,
        )

        return Opening(
            id=op_id,
            type=OpeningType.DOOR,
            room_id=room_id,
            center_mm=center_mm,
            width_mm=round(width_mm, 2),
            height_mm=2100.0,
            hinge_point_mm=hinge_mm,
            strike_point_mm=strike_mm,
            swing_direction=swing_dir,
            swing_arc_sector_mm=swing_wedge,
            confidence=feat.confidence,
        )

    @classmethod
    def _process_window_opening(
        cls,
        feat: ArchitecturalFeature,
        room_id: str,
        index: int,
        transform: PlanTransform,
    ) -> Opening:
        """Processes a window architectural feature into an Opening model."""
        op_id = f"window_{room_id}_{index + 1}"
        if feat.bounds and len(feat.bounds) >= 4:
            cx = (feat.bounds[0] + feat.bounds[2]) / 2.0
            cy = (feat.bounds[1] + feat.bounds[3]) / 2.0
            center_mm = CoordinateTransformEngine.normalized_to_canonical(cx, cy, transform)
            p1_mm = CoordinateTransformEngine.normalized_to_canonical(feat.bounds[0], feat.bounds[1], transform)
            p2_mm = CoordinateTransformEngine.normalized_to_canonical(feat.bounds[2], feat.bounds[3], transform)
            width_mm = max(600.0, math.hypot(p2_mm.x - p1_mm.x, p2_mm.y - p1_mm.y))
        else:
            center_mm = Point2D_mm(x=2000.0, y=500.0)
            width_mm = 1200.0

        return Opening(
            id=op_id,
            type=OpeningType.WINDOW,
            room_id=room_id,
            center_mm=center_mm,
            width_mm=round(width_mm, 2),
            height_mm=1200.0,
            confidence=feat.confidence,
        )

    @classmethod
    def _process_obstacle(
        cls,
        feat: ArchitecturalFeature,
        room_id: str,
        index: int,
        transform: PlanTransform,
    ) -> Optional[FixedObstacle]:
        """Processes fixed furniture or wet obstacle with exclusion clearance."""
        f_type = feat.type.lower().strip()
        obs_id = f"obs_{room_id}_{index + 1}"

        if not feat.bounds or len(feat.bounds) < 4:
            return None

        # Millimeter boundary
        poly_mm = cls._construct_room_polygon_mm(feat.bounds, transform)

        obs_type = ObstacleType.OTHER
        buffer_mm = cls.FURNITURE_CLEARANCE_MM

        if "shower" in f_type:
            obs_type = ObstacleType.SHOWER_ENCLOSURE
            buffer_mm = cls.WET_ZONE_CLEARANCE_MM
        elif "bathtub" in f_type:
            obs_type = ObstacleType.BATHTUB
            buffer_mm = cls.WET_ZONE_CLEARANCE_MM
        elif "wardrobe" in f_type:
            obs_type = ObstacleType.WARDROBE_CLOSET
            buffer_mm = 50.0
        elif "counter" in f_type:
            obs_type = ObstacleType.KITCHEN_COUNTER
            buffer_mm = 100.0

        return FixedObstacle(
            id=obs_id,
            room_id=room_id,
            obstacle_type=obs_type,
            boundary_mm=poly_mm,
            required_buffer_mm=buffer_mm,
            confidence=feat.confidence,
        )

    @classmethod
    def _create_default_shower_obstacle(
        cls,
        room: RoomBoundary,
        transform: PlanTransform,
    ) -> FixedObstacle:
        """Creates a standard 900mm x 900mm shower enclosure in a corner with 600mm Zone 2 buffer."""
        bbox = room.boundary_polygon_mm.bounding_box
        # Corner: top-right corner of the room
        x2 = bbox.max_x - 100.0
        y1 = bbox.min_y + 100.0
        x1 = max(bbox.min_x, x2 - 900.0)
        y2 = min(bbox.max_y, y1 + 900.0)

        pts = [
            Point2D_mm(x=x1, y=y1),
            Point2D_mm(x=x2, y=y1),
            Point2D_mm(x=x2, y=y2),
            Point2D_mm(x=x1, y=y2),
        ]
        poly = Polygon2D_mm(exterior=pts)

        return FixedObstacle(
            id=f"shower_{room.id}_auto",
            room_id=room.id,
            obstacle_type=ObstacleType.SHOWER_ENCLOSURE,
            boundary_mm=poly,
            required_buffer_mm=cls.WET_ZONE_CLEARANCE_MM,
            confidence=0.90,
        )

    @staticmethod
    def _infer_room_type(name: str) -> RoomType:
        """Maps room name to standardized RoomType enum."""
        n = name.lower()
        if "master" in n and "bed" in n:
            return RoomType.MASTER_BEDROOM
        if "bed" in n:
            return RoomType.BEDROOM
        if "bath" in n or "wc" in n or "toilet" in n:
            return RoomType.BATHROOM
        if "kitchen" in n and "din" in n:
            return RoomType.KITCHEN_DINING
        if "kitchen" in n:
            return RoomType.KITCHEN
        if "living" in n or "lounge" in n or "salon" in n:
            return RoomType.LIVING_ROOM
        if "din" in n:
            return RoomType.DINING_ROOM
        if "corridor" in n or "hall" in n or "passage" in n:
            return RoomType.CORRIDOR_HALLWAY
        if "entry" in n or "foyer" in n:
            return RoomType.ENTRANCE_FOYER
        if "balcony" in n or "terrace" in n:
            return RoomType.BALCONY_TERRACE
        if "office" in n or "study" in n:
            return RoomType.OFFICE_STUDY
        return RoomType.OTHER

    # Backward-Compatibility Adapters
    @classmethod
    def to_legacy_rooms_and_features(
        cls,
        canonical_plan: CanonicalFloorPlan,
    ) -> Tuple[List[RoomObservation], List[ArchitecturalFeature]]:
        """
        Backward-compatibility adapter: maps canonical building geometry model
        back to legacy RoomObservation and ArchitecturalFeature models expected by
        existing Flutter UI canvas and downstream calculation engines.
        """
        legacy_rooms: List[RoomObservation] = []
        legacy_features: List[ArchitecturalFeature] = []
        transform = canonical_plan.transform

        for r in canonical_plan.rooms:
            # Map canonical millimeter bounding box back to normalized [0.0, 1.0]
            bbox = r.boundary_polygon_mm.bounding_box
            p_min = Point2D_mm(x=bbox.min_x, y=bbox.min_y)
            p_max = Point2D_mm(x=bbox.max_x, y=bbox.max_y)

            n_min_x, n_min_y = CoordinateTransformEngine.canonical_to_normalized(p_min, transform)
            n_max_x, n_max_y = CoordinateTransformEngine.canonical_to_normalized(p_max, transform)

            legacy_rooms.append(
                RoomObservation(
                    id=r.id,
                    name=r.name,
                    area_m2=r.area_m2,
                    confidence=r.confidence,
                    bounds=[round(n_min_x, 4), round(n_min_y, 4), round(n_max_x, 4), round(n_max_y, 4)],
                )
            )

        for op in canonical_plan.openings:
            cx, cy = CoordinateTransformEngine.canonical_to_normalized(op.center_mm, transform)
            feat_type = "door" if op.type == OpeningType.DOOR else "window"

            hinge_norm = None
            if op.hinge_point_mm:
                hx, hy = CoordinateTransformEngine.canonical_to_normalized(op.hinge_point_mm, transform)
                hinge_norm = [hx, hy]

            strike_norm = None
            if op.strike_point_mm:
                sx, sy = CoordinateTransformEngine.canonical_to_normalized(op.strike_point_mm, transform)
                strike_norm = [sx, sy]

            room_obj = canonical_plan.get_room_by_id(op.room_id)
            room_name = room_obj.name if room_obj else "Room"

            swing_str = "into_room" if op.swing_direction == DoorSwingDirection.INWARD else "out_of_room"

            legacy_features.append(
                ArchitecturalFeature(
                    type=feat_type,
                    room=room_name,
                    confidence=op.confidence,
                    door_position=[cx, cy] if feat_type == "door" else None,
                    hinge_point=hinge_norm,
                    strike_point=strike_norm,
                    swing_direction=swing_str if feat_type == "door" else None,
                    bounds=[max(0.0, cx - 0.02), max(0.0, cy - 0.02), min(1.0, cx + 0.02), min(1.0, cy + 0.02)],
                )
            )

        for obs in canonical_plan.obstacles:
            bbox = obs.boundary_mm.bounding_box
            p_min = Point2D_mm(x=bbox.min_x, y=bbox.min_y)
            p_max = Point2D_mm(x=bbox.max_x, y=bbox.max_y)

            n_min_x, n_min_y = CoordinateTransformEngine.canonical_to_normalized(p_min, transform)
            n_max_x, n_max_y = CoordinateTransformEngine.canonical_to_normalized(p_max, transform)

            room_obj = canonical_plan.get_room_by_id(obs.room_id) if obs.room_id else None
            room_name = room_obj.name if room_obj else "Room"

            type_name = "shower" if obs.obstacle_type == ObstacleType.SHOWER_ENCLOSURE else obs.obstacle_type.value
            legacy_features.append(
                ArchitecturalFeature(
                    type=type_name,
                    room=room_name,
                    confidence=obs.confidence,
                    bounds=[round(n_min_x, 4), round(n_min_y, 4), round(n_max_x, 4), round(n_max_y, 4)],
                )
            )

        return (legacy_rooms, legacy_features)
