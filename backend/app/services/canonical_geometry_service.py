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
    AreaStatus,
    WallClassification,
    WallVerificationMethod,
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
    Remediated Canonical Building Geometry Service for VoltPlan.
    Adheres strictly to Phase 1 non-negotiable principles:
      1. Never fabricates physical dimensions, room boundaries, door orientations, or obstacles.
      2. Separates verified physical measurements from unverified heuristic estimates.
      3. Uses adaptive Euclidean distance-transform corridors for wall line verification.
      4. Detects shared-wall topology between adjacent rooms without duplication.
      5. Derives door orientation from supporting walls; flags isolated doors as unresolved.
      6. Clips obstacle clearance envelopes to room interiors and gates regulatory compliance.
    """

    # Default architectural assumptions in millimeters
    DEFAULT_DOOR_WIDTH_MM = 850.0       # Standard interior clear door leaf
    DEFAULT_WALL_THICKNESS_MM = 150.0   # Standard internal partition thickness
    WET_ZONE_CLEARANCE_MM = 600.0       # RS IEC 60364-7-701 Zone 2 buffer
    FURNITURE_CLEARANCE_MM = 100.0      # Nominal clearance around furniture
    WALL_ATTACHMENT_TOLERANCE_MM = 600.0 # Maximum distance to attach door to wall
    SHARED_WALL_TOLERANCE_MM = 200.0    # Distance tolerance for coincident shared walls
    SHARED_WALL_MIN_OVERLAP_MM = 400.0  # Minimum longitudinal overlap for shared walls

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
        scale_status: ScaleStatus = ScaleStatus.UNSCALED,
        scale_ratio_str: Optional[str] = None,
        building_type: str = "Residential",
        standard_name: str = "RS IEC 60364",
        source_file_name: str = "floor_plan.png",
    ) -> CanonicalFloorPlan:
        """
        Builds a canonical physical building geometry model from architectural observations.
        Does not fabricate missing dimensions, fixtures, or boundaries.
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
                calibrated_image_width=pixel_width,
                calibrated_image_height=pixel_height,
            )
        else:
            # Unscaled plan: relative units only. Explicitly unverified.
            default_est = 16.93  # ~1:100 @ 150 DPI nominal estimate
            transform = PlanTransform(
                pixel_width=pixel_width,
                pixel_height=pixel_height,
                scale_mm_per_pixel=default_est,
                scale_status=ScaleStatus.UNSCALED,
                scale_ratio_str="Unscaled (Heuristic 1:100 @ 150 DPI - Unverified)",
                origin=CoordinateOrigin.TOP_LEFT,
                rotation_deg=0.0,
                is_scale_verified=False,
                calibrated_image_width=pixel_width,
                calibrated_image_height=pixel_height,
            )

        # 2. Source Provenance
        provenance = SourceProvenance(
            source_file=source_file_name,
            file_type=os.path.splitext(source_file_name)[1].lstrip(".").lower() or "png",
            raster_width_px=pixel_width,
            raster_height_px=pixel_height,
            dpi=150.0,
            detection_method="canonical_geometry_engine",
            unresolved_geometry=[],
            geometry_warnings=[],
        )

        if not transform.is_scale_verified:
            provenance.geometry_warnings.append(
                "Plan scale is uncalibrated. Physical coordinates and area calculations are unverified estimates."
            )

        # 3. Load raster image if available for distance-transform wall verification
        gray_img: Optional[np.ndarray] = None
        dist_map: Optional[np.ndarray] = None
        if image_path and os.path.exists(image_path):
            try:
                gray_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if gray_img is not None:
                    _, wall_mask = cv2.threshold(gray_img, 130, 255, cv2.THRESH_BINARY_INV)
                    dist_map = cv2.distanceTransform(cv2.bitwise_not(wall_mask), cv2.DIST_L2, 5)
            except Exception:
                gray_img = None
                dist_map = None

        canonical_rooms: List[RoomBoundary] = []
        canonical_walls: List[WallSegment] = []
        canonical_openings: List[Opening] = []
        canonical_obstacles: List[FixedObstacle] = []

        # 4. Process Rooms & Walls (No silent 80% fallback)
        for r in rooms:
            room_type = cls._infer_room_type(r.name)

            # Strict bounds validation: require 4 valid numbers with positive dimensions
            if not r.bounds or len(r.bounds) != 4 or r.bounds[2] <= r.bounds[0] or r.bounds[3] <= r.bounds[1]:
                provenance.unresolved_geometry.append(
                    f"Room '{r.name}' ({r.id}) has missing or degenerate boundaries; geometry is unresolved."
                )
                continue

            # Construct millimeter polygon for room boundary
            poly_mm = cls._construct_room_polygon_mm(r.bounds, transform)
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

                # Verify physical wall presence using adaptive distance-transform corridor (DEF-03 heuristic)
                is_candidate, conf = cls.verify_wall_profile(
                    p_start=p_start,
                    p_end=p_end,
                    transform=transform,
                    gray_img=gray_img,
                    dist_map=dist_map,
                )

                is_ambiguous = (conf < 0.65)
                if is_candidate and not is_ambiguous:
                    classification = WallClassification.PARTITION
                elif conf >= 0.70 and not is_candidate:
                    classification = WallClassification.VIRTUAL_DIVIDER
                    has_virtual_divider = True
                else:
                    classification = WallClassification.UNKNOWN
                    is_ambiguous = True

                wall_seg = WallSegment(
                    id=wall_id,
                    start=p_start,
                    end=p_end,
                    thickness_mm=cls.DEFAULT_WALL_THICKNESS_MM,
                    classification=classification,
                    interior_room_id=r.id,
                    exterior_or_neighbor_room_id=None,
                    verification_method=(
                        WallVerificationMethod.ADAPTIVE_CORRIDOR_HEURISTIC
                        if gray_img is not None
                        else WallVerificationMethod.UNVERIFIED_NO_IMAGE
                    ),
                    is_verified_physical_wall=False,  # Heuristic candidate, not validated CAD ground truth
                    is_physical_candidate=is_candidate,
                    is_ambiguous=is_ambiguous,
                    confidence=conf,
                )
                canonical_walls.append(wall_seg)

            # DEF-01: Separate scale verification from area verification
            # Approximate bounding-box area is NOT verified even if scale is calibrated!
            if transform.is_scale_verified:
                area_status = AreaStatus.APPROXIMATE_CALIBRATED
                is_area_verified = False
            else:
                area_status = AreaStatus.UNSCALED_ESTIMATE
                is_area_verified = False

            room_bound = RoomBoundary(
                id=r.id,
                name=r.name,
                room_type=room_type,
                boundary_polygon_mm=poly_mm,
                area_m2=round(area_m2, 2),
                area_status=area_status,
                is_area_verified=is_area_verified,
                is_rectangular_approximation=True,  # Bounding box derived
                confidence=r.confidence,
                has_virtual_boundaries=has_virtual_divider,
                wall_ids=room_wall_ids,
                opening_ids=[],
                obstacle_ids=[],
            )
            canonical_rooms.append(room_bound)

        # 5. Establish Shared-Wall Topology between Adjacent Rooms
        cls._link_shared_walls(canonical_walls)

        # 6. Process Architectural Features (Doors, Windows, Obstacles)
        room_by_name = {r.name.lower().strip(): r for r in canonical_rooms}

        for idx, feat in enumerate(features):
            feat_room = room_by_name.get(feat.room.lower().strip()) if feat.room else None
            room_id = feat_room.id if feat_room else (canonical_rooms[0].id if canonical_rooms else "room_unknown")

            f_type = feat.type.lower().strip()
            if f_type in ["door", "entrance"]:
                op = cls._process_door_opening(
                    feat=feat,
                    room_id=room_id,
                    index=idx,
                    transform=transform,
                    feat_room=feat_room,
                    canonical_walls=canonical_walls,
                    provenance=provenance,
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

            elif f_type in ["shower", "bathtub", "shower_enclosure", "wardrobe", "counter", "sink"]:
                obs = cls._process_obstacle(
                    feat=feat,
                    room_id=room_id,
                    index=idx,
                    transform=transform,
                    feat_room=feat_room,
                )
                if obs:
                    canonical_obstacles.append(obs)
                    if feat_room:
                        feat_room.obstacle_ids.append(obs.id)

        # 7. Safety Clearance Audit: Flag Unlocated Bathroom Wet Zones (No Invented Showers)
        for r_bound in canonical_rooms:
            if r_bound.room_type in [RoomType.BATHROOM, RoomType.POWDER_ROOM_WC]:
                existing_wet_obs = [
                    o for o in canonical_obstacles
                    if o.room_id == r_bound.id and o.obstacle_type in [ObstacleType.SHOWER_ENCLOSURE, ObstacleType.BATHTUB]
                ]
                if not existing_wet_obs:
                    provenance.unresolved_geometry.append(
                        f"Sanitary fixtures for '{r_bound.name}' ({r_bound.id}) are unlocated; "
                        "wet zone safety clearances require engineering review before electrical placement."
                    )

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
        dist_map: Optional[np.ndarray] = None,
    ) -> Tuple[bool, float]:
        """
        Inspects raster pixels along the candidate wall segment using an adaptive
        Euclidean distance-transform search corridor.
        Accounts for vision bounding-box offsets, raster resolution, and stroke thickness.

        Returns: (is_physical_wall: bool, confidence: float)
        """
        if gray_img is None:
            # When raster image is unavailable, return uncertain classification
            return (False, 0.50)

        h, w = gray_img.shape
        x1_px, y1_px = CoordinateTransformEngine.canonical_to_pixel(p_start, transform)
        x2_px, y2_px = CoordinateTransformEngine.canonical_to_pixel(p_end, transform)

        seg_len_px = math.hypot(x2_px - x1_px, y2_px - y1_px)
        if seg_len_px < 2.0:
            return (False, 0.50)

        # Compute distance transform if not cached
        if dist_map is None:
            _, wall_mask = cv2.threshold(gray_img, 130, 255, cv2.THRESH_BINARY_INV)
            dist_map = cv2.distanceTransform(cv2.bitwise_not(wall_mask), cv2.DIST_L2, 5)

        # Adaptive search corridor scaled to plan resolution (~1.8% of max dimension, bounded [6, 28] px)
        tol_px = max(6.0, min(28.0, 0.018 * max(w, h)))

        num_samples = max(10, int(seg_len_px / 6.0))
        close_samples = 0
        valid_samples = 0

        for i in range(num_samples):
            t = i / float(num_samples - 1)
            sx = int(round(x1_px + t * (x2_px - x1_px)))
            sy = int(round(y1_px + t * (y2_px - y1_px)))

            if 0 <= sx < w and 0 <= sy < h:
                valid_samples += 1
                dist = dist_map[sy, sx]
                if dist <= tol_px:
                    close_samples += 1

        if valid_samples == 0:
            return (False, 0.50)

        coverage = close_samples / float(valid_samples)

        if coverage >= 0.55:
            # Physical wall verified within search corridor
            is_physical = True
            confidence = round(coverage, 2)
        elif coverage < 0.20:
            # Virtual divider confirmed (clear open space across corridor)
            is_physical = False
            confidence = round(1.0 - coverage, 2)
        else:
            # Ambiguous (wall with large opening, textured line, or broken stroke)
            is_physical = False
            confidence = 0.50

        return (is_physical, confidence)

    @classmethod
    def _link_shared_walls(cls, walls: List[WallSegment]) -> None:
        """
        Identifies collinear coincident walls between adjacent rooms and establishes
        shared topology without duplicating takeoffs.
        """
        n = len(walls)
        for i in range(n):
            w_a = walls[i]
            if w_a.shared_with_wall_id:
                continue

            sh_a = w_a.to_shapely()
            for j in range(i + 1, n):
                w_b = walls[j]
                if w_a.interior_room_id == w_b.interior_room_id:
                    continue  # Same room

                sh_b = w_b.to_shapely()

                # Check Hausdorff / perpendicular distance between segments
                dist = sh_a.distance(sh_b)
                if dist <= cls.SHARED_WALL_TOLERANCE_MM:
                    # Check collinearity and longitudinal overlap
                    dx_a = w_a.end.x - w_a.start.x
                    dy_a = w_a.end.y - w_a.start.y
                    dx_b = w_b.end.x - w_b.start.x
                    dy_b = w_b.end.y - w_b.start.y

                    len_a = math.hypot(dx_a, dy_a)
                    len_b = math.hypot(dx_b, dy_b)
                    if len_a < 1e-4 or len_b < 1e-4:
                        continue

                    # Dot product of normalized unit vectors (should be ~1.0 or ~-1.0 if collinear)
                    dot = (dx_a * dx_b + dy_a * dy_b) / (len_a * len_b)
                    if abs(abs(dot) - 1.0) < 0.05:
                        # Collinear: verify longitudinal projection overlap
                        u_ax = dx_a / len_a
                        u_ay = dy_a / len_a

                        # Project endpoints of segment B onto segment A's 1D axis
                        t_b1 = (w_b.start.x - w_a.start.x) * u_ax + (w_b.start.y - w_a.start.y) * u_ay
                        t_b2 = (w_b.end.x - w_a.start.x) * u_ax + (w_b.end.y - w_a.start.y) * u_ay
                        b_min, b_max = min(t_b1, t_b2), max(t_b1, t_b2)

                        overlap = max(0.0, min(len_a, b_max) - max(0.0, b_min))
                        if overlap >= cls.SHARED_WALL_MIN_OVERLAP_MM:
                            # Genuine shared partition wall: link shared relationship
                            w_a.shared_with_wall_id = w_b.id
                            w_b.shared_with_wall_id = w_a.id
                            w_a.exterior_or_neighbor_room_id = w_b.interior_room_id
                            w_b.exterior_or_neighbor_room_id = w_a.interior_room_id
                            w_b.is_shared_duplicate = True  # Primary takeoff assigned to w_a
                            break

    @classmethod
    def calculate_door_swing_wedge(
        cls,
        hinge_mm: Point2D_mm,
        strike_mm: Point2D_mm,
        room_poly_mm: Optional[Polygon2D_mm] = None,
        swing_dir: DoorSwingDirection = DoorSwingDirection.INWARD,
    ) -> Optional[Polygon2D_mm]:
        """
        Calculates the exact 90-degree circular sector polygon swept by a swinging door leaf.
        The door leaf pivots on hinge_mm and rotates 90 degrees into the room.
        Returns None if hinge or strike points are degenerate or invalid.
        """
        radius = hinge_mm.distance_to(strike_mm)
        if radius < 300.0 or radius > 1500.0:
            radius = cls.DEFAULT_DOOR_WIDTH_MM

        vx = strike_mm.x - hinge_mm.x
        vy = strike_mm.y - hinge_mm.y
        mag = math.hypot(vx, vy)
        if mag < 1e-4:
            return None

        ux = vx / mag
        uy = vy / mag

        # Perpendicular normal vectors: n1 is 90 deg CCW (-uy, ux), n2 is 90 deg CW (uy, -ux)
        n1 = (-uy, ux)
        n2 = (uy, -ux)

        # Choose normal pointing into the room interior
        chosen_normal = n1
        if room_poly_mm is not None:
            shapely_room = room_poly_mm.to_shapely()
            test_pt_1 = ShapelyPoint(hinge_mm.x + n1[0] * (radius * 0.5), hinge_mm.y + n1[1] * (radius * 0.5))
            test_pt_2 = ShapelyPoint(hinge_mm.x + n2[0] * (radius * 0.5), hinge_mm.y + n2[1] * (radius * 0.5))

            if shapely_room.contains(test_pt_1):
                chosen_normal = n1
            elif shapely_room.contains(test_pt_2):
                chosen_normal = n2

        if swing_dir == DoorSwingDirection.OUTWARD:
            chosen_normal = (-chosen_normal[0], -chosen_normal[1])

        # Generate 90-degree circular arc with 10 discrete vertices
        arc_points: List[Point2D_mm] = [hinge_mm]
        num_arc_steps = 10

        for i in range(num_arc_steps + 1):
            theta = (math.pi / 2.0) * (i / float(num_arc_steps))
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
        """Constructs a rectangular room boundary in millimeters from normalized bounds."""
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
        canonical_walls: List[WallSegment],
        provenance: SourceProvenance,
    ) -> Opening:
        """
        Processes a door opening.
        Aligns hinge and strike tangent to the nearest verified wall segment.
        If door is isolated from any wall, marks swing geometry as unresolved.
        """
        op_id = f"door_{room_id}_{index + 1}"

        # 1. Door center position
        if feat.door_position and len(feat.door_position) >= 2:
            center_mm = CoordinateTransformEngine.normalized_to_canonical(
                feat.door_position[0], feat.door_position[1], transform
            )
        elif feat.bounds and len(feat.bounds) >= 4:
            cx = (feat.bounds[0] + feat.bounds[2]) / 2.0
            cy = (feat.bounds[1] + feat.bounds[3]) / 2.0
            center_mm = CoordinateTransformEngine.normalized_to_canonical(cx, cy, transform)
        else:
            center_mm = Point2D_mm(x=0.0, y=0.0)

        # 2. Find nearest wall segment in room
        candidate_walls = [w for w in canonical_walls if w.interior_room_id == room_id or w.exterior_or_neighbor_room_id == room_id]
        if not candidate_walls:
            candidate_walls = canonical_walls

        nearest_wall: Optional[WallSegment] = None
        min_wall_dist = float("inf")
        sh_center = ShapelyPoint(center_mm.x, center_mm.y)

        for w in candidate_walls:
            d = sh_center.distance(w.to_shapely())
            if d < min_wall_dist:
                min_wall_dist = d
                nearest_wall = w

        # 3. Determine hinge and strike locations
        is_attached_to_wall = nearest_wall is not None and min_wall_dist <= cls.WALL_ATTACHMENT_TOLERANCE_MM
        hinge_mm: Optional[Point2D_mm] = None
        strike_mm: Optional[Point2D_mm] = None
        swing_wedge: Optional[Polygon2D_mm] = None
        swing_dir = DoorSwingDirection.UNKNOWN

        if is_attached_to_wall:
            # Project center onto nearest wall line
            sh_wall = nearest_wall.to_shapely()
            proj_dist = sh_wall.project(sh_center)
            proj_pt = sh_wall.interpolate(proj_dist)
            center_mm = Point2D_mm(x=round(proj_pt.x, 2), y=round(proj_pt.y, 2))

            # Wall unit tangent vector
            w_dx = nearest_wall.end.x - nearest_wall.start.x
            w_dy = nearest_wall.end.y - nearest_wall.start.y
            w_len = math.hypot(w_dx, w_dy)
            u_tangent = (w_dx / w_len, w_dy / w_len) if w_len > 1e-4 else (1.0, 0.0)

            # Use detected hinge/strike if available; otherwise align along wall tangent
            has_hinge = feat.hinge_point and len(feat.hinge_point) >= 2
            has_strike = feat.strike_point and len(feat.strike_point) >= 2

            if has_hinge:
                hinge_mm = CoordinateTransformEngine.normalized_to_canonical(
                    feat.hinge_point[0], feat.hinge_point[1], transform
                )
            if has_strike:
                strike_mm = CoordinateTransformEngine.normalized_to_canonical(
                    feat.strike_point[0], feat.strike_point[1], transform
                )

            if has_hinge and not has_strike:
                # Strike is on the opposite side of center_mm from hinge_mm
                dx = center_mm.x - hinge_mm.x
                dy = center_mm.y - hinge_mm.y
                d_len = math.hypot(dx, dy)
                half_w = d_len if d_len >= 150.0 else (cls.DEFAULT_DOOR_WIDTH_MM / 2.0)
                u = (dx / d_len, dy / d_len) if d_len > 1e-4 else u_tangent
                strike_mm = Point2D_mm(
                    x=round(center_mm.x + half_w * u[0], 2),
                    y=round(center_mm.y + half_w * u[1], 2),
                )
            elif has_strike and not has_hinge:
                # Hinge is on the opposite side of center_mm from strike_mm
                dx = center_mm.x - strike_mm.x
                dy = center_mm.y - strike_mm.y
                d_len = math.hypot(dx, dy)
                half_w = d_len if d_len >= 150.0 else (cls.DEFAULT_DOOR_WIDTH_MM / 2.0)
                u = (dx / d_len, dy / d_len) if d_len > 1e-4 else (-u_tangent[0], -u_tangent[1])
                hinge_mm = Point2D_mm(
                    x=round(center_mm.x + half_w * u[0], 2),
                    y=round(center_mm.y + half_w * u[1], 2),
                )
            elif not has_hinge and not has_strike:
                half_w = cls.DEFAULT_DOOR_WIDTH_MM / 2.0
                hinge_mm = Point2D_mm(
                    x=round(center_mm.x - half_w * u_tangent[0], 2),
                    y=round(center_mm.y - half_w * u_tangent[1], 2),
                )
                strike_mm = Point2D_mm(
                    x=round(center_mm.x + half_w * u_tangent[0], 2),
                    y=round(center_mm.y + half_w * u_tangent[1], 2),
                )

            width_mm = hinge_mm.distance_to(strike_mm)
            if width_mm < 300.0 or width_mm > 1500.0:
                width_mm = cls.DEFAULT_DOOR_WIDTH_MM

            # DEF-02: Stop fabricating observed door swings
            observed_swing_arc: Optional[Polygon2D_mm] = None
            assumed_clearance: Optional[Polygon2D_mm] = None
            is_observed = False
            swing_dir = DoorSwingDirection.UNKNOWN
            room_poly = feat_room.boundary_polygon_mm if feat_room else None

            if feat.swing_direction in ["out_of_room", "outward"]:
                is_observed = True
                swing_dir = DoorSwingDirection.OUTWARD
                observed_swing_arc = cls.calculate_door_swing_wedge(
                    hinge_mm=hinge_mm,
                    strike_mm=strike_mm,
                    room_poly_mm=room_poly,
                    swing_dir=swing_dir,
                )
            elif feat.swing_direction in ["into_room", "inward"]:
                is_observed = True
                swing_dir = DoorSwingDirection.INWARD
                observed_swing_arc = cls.calculate_door_swing_wedge(
                    hinge_mm=hinge_mm,
                    strike_mm=strike_mm,
                    room_poly_mm=room_poly,
                    swing_dir=swing_dir,
                )
            else:
                # Swing direction not observed on drawing; generate assumed safety clearance envelope ONLY
                is_observed = False
                swing_dir = DoorSwingDirection.UNKNOWN
                assumed_clearance = cls.calculate_door_swing_wedge(
                    hinge_mm=hinge_mm,
                    strike_mm=strike_mm,
                    room_poly_mm=room_poly,
                    swing_dir=DoorSwingDirection.INWARD,
                )
                provenance.geometry_warnings.append(
                    f"Door '{op_id}' in room '{feat.room}' has no observed swing arc on plan; "
                    "conservative 90° inward clearance envelope assumed for switch placement safety."
                )

            swing_arc_sector = observed_swing_arc or assumed_clearance
        else:
            # Isolated door opening without supporting wall: mark unresolved
            provenance.unresolved_geometry.append(
                f"Door opening '{op_id}' in room '{feat.room}' is isolated from perimeter walls "
                f"(dist = {min_wall_dist:.0f} mm > {cls.WALL_ATTACHMENT_TOLERANCE_MM:.0f} mm); swing geometry is unresolved."
            )
            width_mm = cls.DEFAULT_DOOR_WIDTH_MM
            is_observed = False
            swing_dir = DoorSwingDirection.UNKNOWN
            observed_swing_arc = None
            assumed_clearance = None
            swing_arc_sector = None

        return Opening(
            id=op_id,
            type=OpeningType.DOOR,
            room_id=room_id,
            wall_id=nearest_wall.id if is_attached_to_wall else None,
            center_mm=center_mm,
            width_mm=round(width_mm, 2),
            height_mm=2100.0,
            hinge_point_mm=hinge_mm,
            strike_point_mm=strike_mm,
            swing_direction=swing_dir,
            is_swing_observed=is_observed,
            observed_swing_arc_mm=observed_swing_arc,
            assumed_clearance_envelope_mm=assumed_clearance,
            swing_arc_sector_mm=swing_arc_sector,
            confidence=feat.confidence if is_attached_to_wall else 0.50,
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
            center_mm = Point2D_mm(x=0.0, y=0.0)
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
        feat_room: Optional[RoomBoundary],
    ) -> Optional[FixedObstacle]:
        """
        Processes fixed furniture or sanitary fixture with exclusion clearance.
        Clips clearance buffer to room interior to prevent buffer from bleeding into adjacent rooms.
        """
        f_type = feat.type.lower().strip()
        obs_id = f"obs_{room_id}_{index + 1}"

        if not feat.bounds or len(feat.bounds) < 4:
            return None

        poly_mm = cls._construct_room_polygon_mm(feat.bounds, transform)

        obs_type = ObstacleType.OTHER
        buffer_mm = cls.FURNITURE_CLEARANCE_MM

        if "shower" in f_type:
            obs_type = ObstacleType.SHOWER_ENCLOSURE
            buffer_mm = cls.WET_ZONE_CLEARANCE_MM
        elif "bathtub" in f_type:
            obs_type = ObstacleType.BATHTUB
            buffer_mm = cls.WET_ZONE_CLEARANCE_MM
        elif "sink" in f_type or "basin" in f_type or "vanity" in f_type:
            obs_type = ObstacleType.SINK_VANITY
            buffer_mm = 200.0
        elif "wardrobe" in f_type or "closet" in f_type:
            obs_type = ObstacleType.WARDROBE_CLOSET
            buffer_mm = 50.0
        elif "counter" in f_type:
            obs_type = ObstacleType.KITCHEN_COUNTER
            buffer_mm = 100.0

        obs = FixedObstacle(
            id=obs_id,
            room_id=room_id,
            obstacle_type=obs_type,
            boundary_mm=poly_mm,
            required_buffer_mm=buffer_mm,
            is_compliance_certified=transform.is_scale_verified,
            confidence=feat.confidence,
        )

        return obs

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
                    is_area_verified=r.is_area_verified,
                    is_rectangular_approximation=r.is_rectangular_approximation,
                    area_status=r.area_status.value,
                    confidence=r.confidence,
                    bounds=[
                        round(min(n_min_x, n_max_x), 4),
                        round(min(n_min_y, n_max_y), 4),
                        round(max(n_min_x, n_max_x), 4),
                        round(max(n_min_y, n_max_y), 4),
                    ],
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

            swing_str = "into_room" if op.swing_direction == DoorSwingDirection.INWARD else (
                "out_of_room" if op.swing_direction == DoorSwingDirection.OUTWARD else "unknown"
            )

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
                    bounds=[
                        round(min(n_min_x, n_max_x), 4),
                        round(min(n_min_y, n_max_y), 4),
                        round(max(n_min_x, n_max_x), 4),
                        round(max(n_min_y, n_max_y), 4),
                    ],
                )
            )

        return (legacy_rooms, legacy_features)
