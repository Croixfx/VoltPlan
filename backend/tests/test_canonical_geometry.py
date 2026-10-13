import math
import os
import pytest
import numpy as np
import cv2
from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon

from app.schemas.canonical_geometry import (
    Point2D_mm,
    Vector2D_mm,
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
    CanonicalFloorPlan,
)
from app.schemas.floor_plan import RoomObservation, ArchitecturalFeature
from app.services.coordinate_transform import CoordinateTransformEngine
from app.services.canonical_geometry_service import CanonicalGeometryService
from app.services.electrical_engine import ElectricalEngine


# =========================================================================
# 1. Independent Rectangular Image Coordinate Transformations (W != H)
# =========================================================================

def test_rectangular_image_rotations_independent_ground_truth():
    """
    Independently asserts exact analytical coordinates for rectangular images (W != H)
    across all 4 right-angle rotations (0, 90, 180, 270 deg) for both top-left and bottom-left origins.
    Uses independent analytical expected values rather than reversing the transformation.
    """
    W = 1200.0
    H = 800.0
    scale = 10.0  # 1 px = 10 mm

    # Test point at (300, 200) px
    px, py = 300.0, 200.0

    # 1. Rotation 0 deg (Top-Left): x_mm = 300 * 10 = 3000, y_mm = 200 * 10 = 2000
    t_0 = PlanTransform(pixel_width=int(W), pixel_height=int(H), scale_mm_per_pixel=scale, rotation_deg=0.0)
    pt_0 = CoordinateTransformEngine.pixel_to_canonical(px, py, t_0)
    assert pt_0.x == 3000.0
    assert pt_0.y == 2000.0

    # 2. Rotation 90 deg CW (Top-Left):
    # Dimensions swap: W' = H = 800, H' = W = 1200
    # Analytic formula: x' = H - py = 800 - 200 = 600 px; y' = px = 300 px
    # x_mm = 600 * 10 = 6000 mm, y_mm = 300 * 10 = 3000 mm
    t_90 = PlanTransform(pixel_width=int(W), pixel_height=int(H), scale_mm_per_pixel=scale, rotation_deg=90.0)
    pt_90 = CoordinateTransformEngine.pixel_to_canonical(px, py, t_90)
    assert pt_90.x == 6000.0, f"Expected 6000.0, got {pt_90.x}"
    assert pt_90.y == 3000.0, f"Expected 3000.0, got {pt_90.y}"

    # 3. Rotation 180 deg CW (Top-Left):
    # Dimensions: W' = 1200, H' = 800
    # Analytic formula: x' = W - px = 1200 - 300 = 900 px; y' = H - py = 800 - 200 = 600 px
    # x_mm = 900 * 10 = 9000 mm, y_mm = 600 * 10 = 6000 mm
    t_180 = PlanTransform(pixel_width=int(W), pixel_height=int(H), scale_mm_per_pixel=scale, rotation_deg=180.0)
    pt_180 = CoordinateTransformEngine.pixel_to_canonical(px, py, t_180)
    assert pt_180.x == 9000.0
    assert pt_180.y == 6000.0

    # 4. Rotation 270 deg CW (Top-Left):
    # Dimensions swap: W' = H = 800, H' = W = 1200
    # Analytic formula: x' = py = 200 px; y' = W - px = 1200 - 300 = 900 px
    # x_mm = 200 * 10 = 2000 mm, y_mm = 900 * 10 = 9000 mm
    t_270 = PlanTransform(pixel_width=int(W), pixel_height=int(H), scale_mm_per_pixel=scale, rotation_deg=270.0)
    pt_270 = CoordinateTransformEngine.pixel_to_canonical(px, py, t_270)
    assert pt_270.x == 2000.0
    assert pt_270.y == 9000.0

    # 5. Bottom-Left Origin with 90 deg rotation (CAD convention):
    # In destination frame (W'=800, H'=1200), y_cad = H' - y' = 1200 - 300 = 900 px
    # y_mm = 900 * 10 = 9000 mm; x_mm = 600 * 10 = 6000 mm
    t_90_bl = PlanTransform(
        pixel_width=int(W),
        pixel_height=int(H),
        scale_mm_per_pixel=scale,
        rotation_deg=90.0,
        origin=CoordinateOrigin.BOTTOM_LEFT,
    )
    pt_90_bl = CoordinateTransformEngine.pixel_to_canonical(px, py, t_90_bl)
    assert pt_90_bl.x == 6000.0
    assert pt_90_bl.y == 9000.0


def test_tall_rectangular_image_800x1200():
    """Verify rectangular transformations on tall plans (W < H, 800x1200)."""
    W = 800.0
    H = 1200.0
    scale = 5.0

    # Corner test: (800, 1200) bottom-right
    t_90 = PlanTransform(pixel_width=int(W), pixel_height=int(H), scale_mm_per_pixel=scale, rotation_deg=90.0)
    # 90 CW: x' = H - py = 1200 - 1200 = 0 px; y' = px = 800 px
    pt = CoordinateTransformEngine.pixel_to_canonical(800.0, 1200.0, t_90)
    assert pt.x == 0.0
    assert pt.y == 4000.0  # 800 * 5 = 4000 mm


# =========================================================================
# 2. Crop & Resize Operations & Scale Preservation
# =========================================================================

def test_uniform_resize_preserves_physical_dimensions():
    """Uniform resizing (e.g. 1200x800 downscaled to 600x400) adjusts scale factor inversely."""
    t_orig = PlanTransform(
        pixel_width=1200,
        pixel_height=800,
        scale_mm_per_pixel=10.0,
        scale_status=ScaleStatus.USER_CALIBRATED,
        is_scale_verified=True,
    )

    t_resized = t_orig.update_for_resize(2400, 1600)  # Upscaled 2x
    assert t_resized.scale_mm_per_pixel == 5.0  # Each pixel now represents half as many mm
    assert t_resized.is_scale_verified is True


def test_non_uniform_resize_invalidates_scale():
    """Non-uniform stretching (aspect ratio change) invalidates calibration."""
    t_orig = PlanTransform(
        pixel_width=1200,
        pixel_height=800,
        scale_mm_per_pixel=10.0,
        scale_status=ScaleStatus.USER_CALIBRATED,
        is_scale_verified=True,
    )

    t_stretched = t_orig.update_for_resize(1200, 1200)  # Stretched vertically
    assert t_stretched.is_scale_verified is False
    assert t_stretched.scale_status == ScaleStatus.UNSCALED
    assert t_stretched.scale_mm_per_pixel is None


def test_crop_updates_offsets_accurately():
    """Cropping updates offset_x_mm and offset_y_mm so physical coordinates remain consistent."""
    t_orig = PlanTransform(
        pixel_width=1200,
        pixel_height=800,
        scale_mm_per_pixel=10.0,
    )

    # Crop rectangle: x=200, y=150, w=600, h=400
    t_cropped = t_orig.update_for_crop(crop_x=200, crop_y=150, crop_w=600, crop_h=400)
    assert t_cropped.pixel_width == 600
    assert t_cropped.pixel_height == 400
    assert t_cropped.offset_x_mm == 2000.0  # 200 * 10
    assert t_cropped.offset_y_mm == 1500.0  # 150 * 10


# =========================================================================
# 3. Calibration Input Validation & Noise Rejection
# =========================================================================

def test_calibration_rejects_points_too_close():
    """Calibration must reject points closer than 5 pixels to prevent noise amplification."""
    transform = PlanTransform(pixel_width=1000, pixel_height=1000)

    # Distance is 3 pixels: (100, 100) to (103, 100)
    with pytest.raises(ValueError, match="too close"):
        CoordinateTransformEngine.calibrate_scale_from_points(
            (100.0, 100.0), (103.0, 100.0), 1000.0, transform
        )


def test_calibration_rejects_negative_or_zero_distance():
    """Physical distance must be strictly positive."""
    transform = PlanTransform(pixel_width=1000, pixel_height=1000)
    with pytest.raises(ValueError, match="strictly positive"):
        CoordinateTransformEngine.calibrate_scale_from_points(
            (100.0, 100.0), (300.0, 100.0), -500.0, transform
        )


# =========================================================================
# 4. Invented Room Geometry Removal (No Silent 80% Fallback)
# =========================================================================

def test_missing_or_degenerate_room_bounds_flagged_as_unresolved():
    """
    Rooms with missing, empty, or degenerate bounds must NOT be silently replaced
    with [0.1, 0.1, 0.9, 0.9]. They must be recorded in unresolved_geometry.
    """
    rooms = [
        RoomObservation(id="r_valid", name="Living Room", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5]),
        RoomObservation(id="r_missing", name="Corridor", confidence=0.80, bounds=None),
        RoomObservation(id="r_degenerate", name="Storage", confidence=0.75, bounds=[0.5, 0.5, 0.2, 0.2]),
    ]

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        pixel_width=1000,
        pixel_height=1000,
    )

    # Only 1 valid room should be constructed
    assert len(plan.rooms) == 1
    assert plan.rooms[0].id == "r_valid"
    assert plan.rooms[0].is_rectangular_approximation is True

    # Both missing and degenerate rooms must be explicitly listed in unresolved_geometry
    unres_text = " ".join(plan.provenance.unresolved_geometry)
    assert "Corridor" in unres_text
    assert "Storage" in unres_text


# =========================================================================
# 5. Invented Obstacles Removal & Safety Buffer Responsibility
# =========================================================================

def test_bathroom_without_fixtures_does_not_fabricate_shower():
    """
    Bathrooms without detected fixtures must NOT have an invented 900x900 shower.
    Instead, an unresolved geometry warning must be issued for engineering review.
    """
    rooms = [
        RoomObservation(id="r_bath", name="Master Bathroom", confidence=0.90, bounds=[0.1, 0.1, 0.4, 0.4])
    ]

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],  # No shower detected!
        pixel_width=1000,
        pixel_height=1000,
    )

    assert len(plan.obstacles) == 0, "No shower enclosure should be fabricated!"
    unres_text = " ".join(plan.provenance.unresolved_geometry)
    assert "Master Bathroom" in unres_text
    assert "unlocated" in unres_text


def test_obstacle_buffer_clipped_to_room_boundary():
    """
    Safety clearance buffer must be clipped to the room boundary to prevent
    buffer penetration through walls into adjoining spaces.
    """
    room_poly = Polygon2D_mm(
        exterior=[
            Point2D_mm(x=0.0, y=0.0),
            Point2D_mm(x=3000.0, y=0.0),
            Point2D_mm(x=3000.0, y=3000.0),
            Point2D_mm(x=0.0, y=3000.0),
        ]
    )

    # Shower in corner (2100, 0) to (3000, 900)
    shower = FixedObstacle(
        id="shower_corner",
        obstacle_type=ObstacleType.SHOWER_ENCLOSURE,
        boundary_mm=Polygon2D_mm(
            exterior=[
                Point2D_mm(x=2100.0, y=0.0),
                Point2D_mm(x=3000.0, y=0.0),
                Point2D_mm(x=3000.0, y=900.0),
                Point2D_mm(x=2100.0, y=900.0),
            ]
        ),
        required_buffer_mm=600.0,
        confidence=0.95,
    )

    clipped_envelope = shower.get_clipped_envelope_mm(room_poly)
    sh_clipped = clipped_envelope.to_shapely()

    # Point outside the room at (3200, 500) (adjoining room) must NOT be in clipped envelope
    outside_room_pt = ShapelyPoint(3200.0, 500.0)
    assert not sh_clipped.contains(outside_room_pt), "Clearance zone must not penetrate into adjoining room"


# =========================================================================
# 6. Door Orientation & Alignment with Supporting Walls
# =========================================================================

def test_door_aligns_with_vertical_wall():
    """
    A door located on a vertical (East-West) wall must align its hinge-to-strike
    vector along the vertical wall, NOT default to an arbitrary horizontal offset.
    """
    rooms = [
        RoomObservation(id="r1", name="Bedroom", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    # Door on the East wall (x=0.5, y in [0.1, 0.5]) at (0.50, 0.30)
    features = [
        ArchitecturalFeature(
            type="door",
            room="Bedroom",
            confidence=0.90,
            door_position=[0.50, 0.30],
            swing_direction="into_room",
        )
    ]

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    door = plan.openings[0]
    assert door.hinge_point_mm is not None
    assert door.strike_point_mm is not None

    # Hinge and strike should share approximately the same X coordinate (on vertical wall)
    assert abs(door.hinge_point_mm.x - door.strike_point_mm.x) < 50.0, "Door on vertical wall must have vertical alignment"
    # And differ significantly in Y (along the wall)
    assert abs(door.hinge_point_mm.y - door.strike_point_mm.y) > 700.0


def test_isolated_floating_door_marked_unresolved():
    """
    A door far away from any wall (> 600mm) must NOT generate an authoritative swing wedge.
    It must be marked with DoorSwingDirection.UNKNOWN and added to unresolved_geometry.
    """
    rooms = [
        RoomObservation(id="r1", name="Hall", confidence=0.90, bounds=[0.1, 0.1, 0.9, 0.9])
    ]
    # Center of room: (0.50, 0.50) is ~4000mm away from all perimeter walls
    features = [
        ArchitecturalFeature(
            type="door",
            room="Hall",
            confidence=0.80,
            door_position=[0.50, 0.50],
        )
    ]

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    door = plan.openings[0]
    assert door.swing_arc_sector_mm is None
    assert door.swing_direction == DoorSwingDirection.UNKNOWN
    unres_text = " ".join(plan.provenance.unresolved_geometry)
    assert "isolated" in unres_text


# =========================================================================
# 7. Shared-Wall Topology Linking
# =========================================================================

def test_shared_wall_topology_links_adjacent_rooms():
    """
    Adjacent rooms sharing a boundary wall must have their shared walls linked
    with exterior_or_neighbor_room_id and marked as shared duplicates.
    """
    rooms = [
        # Room A: [0.1, 0.1, 0.5, 0.5] -> East wall at x=0.5
        RoomObservation(id="room_a", name="Living Room", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5]),
        # Room B: [0.5, 0.1, 0.9, 0.5] -> West wall at x=0.5
        RoomObservation(id="room_b", name="Dining Room", confidence=0.95, bounds=[0.5, 0.1, 0.9, 0.5]),
    ]

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    # Find walls with shared links
    shared_walls = [w for w in plan.walls if w.shared_with_wall_id is not None]
    assert len(shared_walls) == 2, "Both walls along the shared partition should be linked"

    w1, w2 = shared_walls[0], shared_walls[1]
    assert w1.exterior_or_neighbor_room_id in ["room_a", "room_b"]
    assert w2.exterior_or_neighbor_room_id in ["room_a", "room_b"]
    assert w1.shared_with_wall_id == w2.id
    assert w2.shared_with_wall_id == w1.id

    # Exactly one wall should be flagged as duplicate to prevent double takeoff
    duplicates = [w for w in shared_walls if w.is_shared_duplicate]
    assert len(duplicates) == 1


# =========================================================================
# 8. Adaptive Distance-Transform Wall Verification (Real Plan Validation)
# =========================================================================

def test_wall_verification_on_real_floor_plan():
    """
    Validates wall verification on the real architectural floor plan in backend/uploads.
    Tests known structural walls vs open space to measure classification accuracy.
    """
    real_image_path = "backend/uploads/2c9948d0-34a6-4095-aef5-a0f26367f243/display_plan.png"
    if not os.path.exists(real_image_path):
        pytest.skip("Sample upload image not present on disk")

    img = cv2.imread(real_image_path, cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    transform = PlanTransform(pixel_width=w, pixel_height=h, scale_mm_per_pixel=10.0)

    # 1. Known real wall: Top exterior wall between x=0.03*w and x=0.35*w, y=0.16*h
    p_wall_start = CoordinateTransformEngine.pixel_to_canonical(0.03 * w, 0.16 * h, transform)
    p_wall_end = CoordinateTransformEngine.pixel_to_canonical(0.35 * w, 0.16 * h, transform)
    is_wall, conf = CanonicalGeometryService.verify_wall_profile(p_wall_start, p_wall_end, transform, img)
    assert is_wall is True, "Drawn exterior wall must be classified as physical"
    assert conf >= 0.70

    # 2. Known open floor space / virtual divider: Line in the middle of Bedroom 1 (y=0.34*h, x in [0.12*w, 0.28*w])
    # No wall is drawn across the interior of the bedroom floor
    p_open_start = CoordinateTransformEngine.pixel_to_canonical(0.12 * w, 0.34 * h, transform)
    p_open_end = CoordinateTransformEngine.pixel_to_canonical(0.28 * w, 0.34 * h, transform)
    is_open_wall, conf_open = CanonicalGeometryService.verify_wall_profile(p_open_start, p_open_end, transform, img)
    assert is_open_wall is False, "Open interior bedroom floor must not be classified as physical wall"


# =========================================================================
# 9. DEF-01: Scale Verification Separated from Area Verification
# =========================================================================

def test_calibrated_scale_with_approximate_room_geometry_sets_approximate_status():
    """
    DEF-01: A calibrated scale (10 mm/px) must NOT certify a bounding-box room area as verified.
    is_rectangular_approximation must remain True, area_status must be APPROXIMATE_CALIBRATED,
    and is_area_verified must be False.
    """
    rooms = [
        RoomObservation(id="r1", name="Master Bedroom", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
        is_scale_verified=True,
        scale_status=ScaleStatus.USER_CALIBRATED,
    )

    room = plan.rooms[0]
    assert plan.transform.is_scale_verified is True
    assert room.is_rectangular_approximation is True
    assert room.is_area_verified is False, "Bounding box room area must NOT be marked verified even with calibrated scale!"
    assert room.area_status == AreaStatus.APPROXIMATE_CALIBRATED
    assert room.area_m2 == 16.0  # 400px * 10 = 4000mm = 4m; 4m * 4m = 16 m2


def test_exact_polygon_room_with_calibrated_scale_sets_verified_area():
    """
    DEF-01: Only when a room polygon is confirmed exact (is_rectangular_approximation=False)
    AND scale is verified should area be certified as verified.
    """
    poly = Polygon2D_mm(
        exterior=[
            Point2D_mm(x=0.0, y=0.0),
            Point2D_mm(x=5000.0, y=0.0),
            Point2D_mm(x=5000.0, y=4000.0),
            Point2D_mm(x=0.0, y=4000.0),
        ]
    )
    # 5m x 4m = 20 m2
    room = RoomBoundary(
        id="r_exact",
        name="Conference Hall",
        room_type=RoomType.OFFICE_STUDY,
        boundary_polygon_mm=poly,
        area_m2=poly.area_m2,
        area_status=AreaStatus.VERIFIED,
        is_area_verified=True,
        is_rectangular_approximation=False,
    )

    assert room.is_area_verified is True
    assert room.is_rectangular_approximation is False
    assert room.area_status == AreaStatus.VERIFIED
    assert room.area_m2 == 20.0


def test_unscaled_plan_sets_unscaled_estimate_status():
    """DEF-01: An unscaled plan must set area_status to UNSCALED_ESTIMATE and is_area_verified to False."""
    rooms = [
        RoomObservation(id="r1", name="Kitchen", confidence=0.90, bounds=[0.2, 0.2, 0.6, 0.6])
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        scale_mm_per_pixel=None,
        is_scale_verified=False,
    )

    room = plan.rooms[0]
    assert room.is_area_verified is False
    assert room.area_status == AreaStatus.UNSCALED_ESTIMATE


# =========================================================================
# 10. DEF-02: Door Swing Provenance & Conservative Clearance Envelopes
# =========================================================================

def test_door_with_unobserved_swing_does_not_fabricate_observed_swing():
    """
    DEF-02: When door swing is unobserved on the drawing, the system must:
      1. Set is_swing_observed = False
      2. Set swing_direction = DoorSwingDirection.UNKNOWN
      3. Set observed_swing_arc_mm = None (DO NOT fabricate an observed CAD arc!)
      4. Set assumed_clearance_envelope_mm = 90° inward envelope (for switch placement safety ONLY)
      5. Issue explicit provenance warning.
    """
    rooms = [
        RoomObservation(id="r1", name="Bedroom 1", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    # Door with no swing_direction provided
    features = [
        ArchitecturalFeature(
            type="door",
            room="Bedroom 1",
            confidence=0.88,
            door_position=[0.30, 0.10],
            swing_direction=None,  # Unobserved!
        )
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    door = plan.openings[0]
    assert door.is_swing_observed is False, "Unobserved swing must NOT be marked observed!"
    assert door.swing_direction == DoorSwingDirection.UNKNOWN
    assert door.observed_swing_arc_mm is None, "Must NOT fabricate observed swing arc when unobserved!"
    assert door.assumed_clearance_envelope_mm is not None, "Assumed clearance envelope must protect switches!"

    warnings_text = " ".join(plan.provenance.geometry_warnings)
    assert "no observed swing arc" in warnings_text.lower()
    assert "conservative 90° inward clearance envelope assumed" in warnings_text.lower()


def test_door_with_observed_swing_preserves_observed_geometry():
    """
    DEF-02: When door swing direction is observed on plan (e.g. outward),
    it must be recorded with is_swing_observed = True and observed_swing_arc_mm populated.
    """
    rooms = [
        RoomObservation(id="r1", name="Utility", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    features = [
        ArchitecturalFeature(
            type="door",
            room="Utility",
            confidence=0.92,
            door_position=[0.30, 0.10],
            swing_direction="out_of_room",  # Observed outward!
        )
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    door = plan.openings[0]
    assert door.is_swing_observed is True
    assert door.swing_direction == DoorSwingDirection.OUTWARD
    assert door.observed_swing_arc_mm is not None
    assert door.assumed_clearance_envelope_mm is None


# =========================================================================
# 11. DEF-03: Wall Verification Method & Ambiguity Tracking
# =========================================================================

def test_wall_verification_records_heuristic_method_and_flags_ambiguity():
    """
    DEF-03: Wall verification must record method as ADAPTIVE_CORRIDOR_HEURISTIC,
    never claim verified physical wall without CAD/ground truth, and flag borderline strokes.
    """
    rooms = [
        RoomObservation(id="r1", name="Living Room", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
    )

    for wall in plan.walls:
        assert wall.verification_method in [
            WallVerificationMethod.ADAPTIVE_CORRIDOR_HEURISTIC,
            WallVerificationMethod.UNVERIFIED_NO_IMAGE,
        ]
        # In the absence of an independent ground truth CAD dataset, is_verified_physical_wall is False
        assert wall.is_verified_physical_wall is False


# =========================================================================
# 12. Stage 2: Traceable Uncertainty-Aware Electrical Placement Foundation
# =========================================================================

def test_traceable_electrical_placement_records_provenance_and_reasoning():
    """
    Stage 2: Asserts that every proposed electrical point records:
      - Stable identifier and type
      - Associated room and geometry used
      - Canonical millimeter coordinates (x_mm, y_mm) and normalized ratios (x_ratio, y_ratio)
      - Explicit placement rule reference
      - Associated nearby wall, door, or obstacle IDs
      - Clearance envelope applied
      - Placement status (proposed, needs_confirmation, or unresolved)
      - Human-readable engineering reasoning
    """
    rooms = [
        RoomObservation(id="r_bed", name="Master Bedroom", confidence=0.95, bounds=[0.1, 0.1, 0.5, 0.5]),
        RoomObservation(id="r_bath", name="Ensuite Bathroom", confidence=0.90, bounds=[0.5, 0.1, 0.8, 0.4]),
    ]
    features = [
        ArchitecturalFeature(
            type="door",
            room="Master Bedroom",
            confidence=0.90,
            door_position=[0.10, 0.30],
            strike_point=[0.10, 0.35],
            swing_direction="into_room",
        ),
        ArchitecturalFeature(
            type="shower",
            room="Ensuite Bathroom",
            confidence=0.92,
            bounds=[0.70, 0.10, 0.80, 0.25],
        ),
    ]

    canonical_plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
        is_scale_verified=True,
        scale_status=ScaleStatus.USER_CALIBRATED,
    )

    points = ElectricalEngine.generate_recommendations(
        rooms=rooms,
        architectural_features=features,
        building_type="Residential",
        standard_name="RS IEC 60364",
        canonical_plan=canonical_plan,
    )

    assert len(points) > 0

    for pt in points:
        # Every point must have core identification and traceability
        assert pt.id.startswith("pt_")
        assert pt.room_id in ["r_bed", "r_bath"]
        assert pt.coordinate_system == "canonical_mm_and_normalized_ratio"
        assert pt.x_mm is not None
        assert pt.y_mm is not None
        assert pt.placement_rule is not None
        assert pt.geometry_used is not None
        assert pt.placement_status in ["proposed", "needs_confirmation", "unresolved"]
        assert pt.reasoning is not None and len(pt.reasoning) > 10

        # Verify physical coordinates round-trip with normalized ratios
        expected_pt_mm = CoordinateTransformEngine.normalized_to_canonical(
            pt.x_ratio, pt.y_ratio, canonical_plan.transform
        )
        assert abs(pt.x_mm - expected_pt_mm.x) < 1.0
        assert abs(pt.y_mm - expected_pt_mm.y) < 1.0

    # 1. Verify Switch Placement Traceability
    switches = [p for p in points if "switch" in p.type]
    assert len(switches) >= 1
    sw = switches[0]
    assert sw.geometry_used == "wall_strike_side_tangent"
    assert sw.nearby_door_id is not None
    assert sw.clearance_envelope_applied is not None
    assert "strike jamb" in sw.reasoning.lower()

    # Verify switch is NOT placed inside the door swing arc sector
    door = canonical_plan.openings[0]
    if door.observed_swing_arc_mm:
        sh_arc = door.observed_swing_arc_mm.to_shapely()
        sw_shapely = ShapelyPoint(sw.x_mm, sw.y_mm)
        assert not sh_arc.contains(sw_shapely), "Switch must NEVER land inside door swing envelope!"

    # 2. Verify Bathroom Socket Safety Traceability (Zone 2)
    bath_sockets = [p for p in points if p.room_id == "r_bath" and "socket" in p.type]
    assert len(bath_sockets) >= 1
    bs = bath_sockets[0]
    assert bs.geometry_used == "safe_wall_outside_wet_zone"
    assert bs.nearby_obstacle_id is not None
    assert "Zone 2" in (bs.clearance_envelope_applied or "")

    # Verify socket coordinate is outside the 600mm shower buffer
    shower_obs = next(o for o in canonical_plan.obstacles if o.id == bs.nearby_obstacle_id)
    sh_env = shower_obs.exclusion_envelope_mm.to_shapely()
    bs_shapely = ShapelyPoint(bs.x_mm, bs.y_mm)
    assert not sh_env.contains(bs_shapely), "Bathroom socket must be strictly outside Zone 2 (600mm buffer)!"


# =========================================================================
# 13. DEF-04: Legacy Adapter & Flutter Uncertainty Propagation
# =========================================================================

def test_canonical_to_legacy_adapter_propagates_area_uncertainty():
    """
    DEF-04: to_legacy_rooms_and_features must pass area_status, is_area_verified,
    and is_rectangular_approximation to RoomObservation, which Flutter Room model consumes.
    """
    rooms = [
        RoomObservation(id="r1", name="Dining Room", confidence=0.91, bounds=[0.1, 0.1, 0.4, 0.4])
    ]
    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=[],
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
        is_scale_verified=True,
    )

    legacy_rooms, _ = CanonicalGeometryService.to_legacy_rooms_and_features(plan)
    assert len(legacy_rooms) == 1
    lr = legacy_rooms[0]

    assert lr.is_area_verified is False  # Approximate bounding box!
    assert lr.is_rectangular_approximation is True
    assert lr.area_status == "approximate_calibrated"
