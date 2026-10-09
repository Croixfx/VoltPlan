import math
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
    WallClassification,
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


# =========================================================================
# 1. Round-Trip Transformations & Accuracy Tests
# =========================================================================

def test_pixel_to_canonical_round_trip():
    """Verify sub-pixel and sub-millimeter bidirectional round-trip transformation accuracy."""
    transform = PlanTransform(
        pixel_width=2000,
        pixel_height=1500,
        scale_mm_per_pixel=10.0,  # 1 px = 10 mm
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
        origin=CoordinateOrigin.TOP_LEFT,
        rotation_deg=0.0,
        is_scale_verified=True,
    )

    test_pixels = [(0.0, 0.0), (500.5, 300.25), (1000.0, 750.0), (1999.0, 1499.0)]
    for orig_px, orig_py in test_pixels:
        pt_mm = CoordinateTransformEngine.pixel_to_canonical(orig_px, orig_py, transform)
        back_px, back_py = CoordinateTransformEngine.canonical_to_pixel(pt_mm, transform)

        assert abs(back_px - orig_px) < 0.01, f"Pixel X round-trip error: {back_px} vs {orig_px}"
        assert abs(back_py - orig_py) < 0.01, f"Pixel Y round-trip error: {back_py} vs {orig_py}"


def test_normalized_to_canonical_round_trip():
    """Verify normalized display coordinates [0.0, 1.0] round-trip accurately with canonical mm."""
    transform = PlanTransform(
        pixel_width=1600,
        pixel_height=1200,
        scale_mm_per_pixel=12.5,
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
        origin=CoordinateOrigin.TOP_LEFT,
        rotation_deg=0.0,
        is_scale_verified=True,
    )

    test_norms = [(0.0, 0.0), (0.25, 0.5), (0.333, 0.667), (1.0, 1.0)]
    for nx, ny in test_norms:
        pt_mm = CoordinateTransformEngine.normalized_to_canonical(nx, ny, transform)
        back_nx, back_ny = CoordinateTransformEngine.canonical_to_normalized(pt_mm, transform)

        assert abs(back_nx - nx) <= 0.001, f"Normalized X round-trip error: {back_nx} vs {nx}"
        assert abs(back_ny - ny) <= 0.001, f"Normalized Y round-trip error: {back_ny} vs {ny}"


# =========================================================================
# 2. Scale & Resolution Invariance Tests
# =========================================================================

def test_different_resolutions_preserve_physical_dimensions():
    """
    A room measuring 4000 mm x 5000 mm should produce identical canonical millimeters
    regardless of whether the plan was rendered at 1000x800 or 4000x3200.
    """
    # Low-res image: 1000x800, scale = 20 mm/px -> Room is 200px x 250px
    transform_low = PlanTransform(
        pixel_width=1000,
        pixel_height=800,
        scale_mm_per_pixel=20.0,
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
        is_scale_verified=True,
    )

    # High-res image: 4000x3200, scale = 5 mm/px -> Room is 800px x 1000px
    transform_high = PlanTransform(
        pixel_width=4000,
        pixel_height=3200,
        scale_mm_per_pixel=5.0,
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
        is_scale_verified=True,
    )

    # In low-res: room normalized [0.1, 0.1, 0.3, 0.35]
    # px = [100, 80] to [300, 280] -> dx = 200px * 20 = 4000mm, dy = 200px * 20 = 4000mm
    pt1_low = CoordinateTransformEngine.pixel_to_canonical(100, 80, transform_low)
    pt2_low = CoordinateTransformEngine.pixel_to_canonical(300, 280, transform_low)

    # In high-res: same room at 4x resolution: px = [400, 320] to [1200, 1120]
    # dx = 800px * 5 = 4000mm, dy = 800px * 5 = 4000mm
    pt1_high = CoordinateTransformEngine.pixel_to_canonical(400, 320, transform_high)
    pt2_high = CoordinateTransformEngine.pixel_to_canonical(1200, 1120, transform_high)

    width_low = pt2_low.x - pt1_low.x
    width_high = pt2_high.x - pt1_high.x

    height_low = pt2_low.y - pt1_low.y
    height_high = pt2_high.y - pt1_high.y

    assert width_low == 4000.0
    assert width_high == 4000.0
    assert height_low == 4000.0
    assert height_high == 4000.0


def test_drawing_scale_calibration():
    """Verify scale calibration from dimension line OCR reference points."""
    base_transform = PlanTransform(
        pixel_width=1920,
        pixel_height=1080,
        scale_status=ScaleStatus.UNSCALED,
        is_scale_verified=False,
    )

    # User or OCR identifies 2 tick marks at (100, 200) and (500, 200), distance 400px representing 4800mm
    calibrated = CoordinateTransformEngine.calibrate_scale_from_points(
        p1_px=(100.0, 200.0),
        p2_px=(500.0, 200.0),
        physical_distance_mm=4800.0,
        transform=base_transform,
        source=ScaleStatus.CALIBRATED_DIMENSION,
    )

    assert calibrated.is_scale_verified is True
    assert calibrated.scale_status == ScaleStatus.CALIBRATED_DIMENSION
    assert calibrated.scale_mm_per_pixel == 12.0  # 4800 mm / 400 px = 12.0 mm/px


# =========================================================================
# 3. Rotations & Coordinate Origin Tests
# =========================================================================

@pytest.mark.parametrize("rotation", [0.0, 90.0, 180.0, 270.0])
def test_plan_rotations_preserve_relative_geometry(rotation):
    """Verify that 90, 180, 270 degree plan rotations preserve canonical distance between points."""
    transform = PlanTransform(
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
        rotation_deg=rotation,
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
        is_scale_verified=True,
    )

    # Two points 200 pixels apart horizontally
    p1 = CoordinateTransformEngine.pixel_to_canonical(200.0, 300.0, transform)
    p2 = CoordinateTransformEngine.pixel_to_canonical(400.0, 300.0, transform)

    dist_mm = p1.distance_to(p2)
    assert abs(dist_mm - 2000.0) < 0.1, f"Rotation {rotation} deg failed to preserve 2000mm distance: {dist_mm}"

    # Round trip test
    b1_px, b1_py = CoordinateTransformEngine.canonical_to_pixel(p1, transform)
    assert abs(b1_px - 200.0) < 0.05
    assert abs(b1_py - 300.0) < 0.05


def test_cartesian_bottom_left_origin():
    """Verify bottom-left Cartesian origin (CAD convention +Y up) inverts Y correctly."""
    t_top_left = PlanTransform(pixel_width=1000, pixel_height=800, scale_mm_per_pixel=1.0, origin=CoordinateOrigin.TOP_LEFT)
    t_bottom_left = PlanTransform(pixel_width=1000, pixel_height=800, scale_mm_per_pixel=1.0, origin=CoordinateOrigin.BOTTOM_LEFT)

    pt_top = CoordinateTransformEngine.pixel_to_canonical(100, 100, t_top_left)
    pt_bot = CoordinateTransformEngine.pixel_to_canonical(100, 100, t_bottom_left)

    assert pt_top.x == 100.0 and pt_top.y == 100.0
    assert pt_bot.x == 100.0 and pt_bot.y == 700.0  # 800 - 100 = 700


# =========================================================================
# 4. Non-Rectangular Rooms (L-Shaped, Holes, Areas)
# =========================================================================

def test_l_shaped_room_geometry_and_area():
    """
    Test an L-shaped room (6-point polygon) canonical representation:
    Dimensions: 6m x 6m overall with a 3m x 3m cutout.
    Total area should be: (6*6) - (3*3) = 36 - 9 = 27.0 m2.
    """
    pts = [
        Point2D_mm(x=0.0, y=0.0),
        Point2D_mm(x=6000.0, y=0.0),
        Point2D_mm(x=6000.0, y=3000.0),
        Point2D_mm(x=3000.0, y=3000.0),
        Point2D_mm(x=3000.0, y=6000.0),
        Point2D_mm(x=0.0, y=6000.0),
    ]
    l_poly = Polygon2D_mm(exterior=pts)

    assert abs(l_poly.area_m2 - 27.0) < 0.01, f"Expected 27.0 m2, got {l_poly.area_m2}"
    bbox = l_poly.bounding_box
    assert bbox.width == 6000.0
    assert bbox.height == 6000.0

    # Ensure centroid is inside or on the boundary
    centroid = l_poly.centroid
    assert 0.0 < centroid.x < 6000.0
    assert 0.0 < centroid.y < 6000.0


# =========================================================================
# 5. Scale Verification Gate & Uncalibrated Geometry Warnings
# =========================================================================

def test_unscaled_plan_triggers_verification_gate():
    """
    When plan scale cannot be verified, canonical model must mark is_scale_verified=False
    and include warnings preventing physical electrical certification.
    """
    rooms = [
        RoomObservation(id="r1", name="Master Bedroom", confidence=0.92, bounds=[0.1, 0.1, 0.5, 0.5])
    ]
    features = []

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        scale_mm_per_pixel=None,  # No scale established
        is_scale_verified=False,
    )

    assert plan.is_scale_verified is False
    assert plan.transform.is_scale_verified is False
    assert plan.rooms[0].is_area_verified is False
    assert len(plan.provenance.geometry_warnings) > 0
    assert "uncalibrated" in plan.provenance.geometry_warnings[0].lower()


def test_verified_scale_marks_area_verified():
    """When scale is verified by calibration, room area is marked as verified."""
    rooms = [
        RoomObservation(id="r1", name="Living Room", confidence=0.95, bounds=[0.0, 0.0, 0.5, 0.5])
    ]
    features = []

    plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,  # 10 mm per px
        is_scale_verified=True,
        scale_status=ScaleStatus.CALIBRATED_DIMENSION,
    )

    assert plan.is_scale_verified is True
    assert plan.rooms[0].is_area_verified is True
    # 500px * 10 = 5000 mm = 5m. 5m * 5m = 25 m2
    assert abs(plan.rooms[0].area_m2 - 25.0) < 0.1


# =========================================================================
# 6. Morphological Wall Verification (Physical Wall vs Virtual Divider)
# =========================================================================

def test_morphological_wall_verification_separates_divider():
    """
    Synthetic raster test:
    Creates a 400x400 image where:
      - North, East, and West walls are drawn with thick black lines (intensity 0).
      - South wall is left completely blank/white (open archway into corridor).
    Verifies that North wall is classified as physical wall, and South is classified as virtual divider.
    """
    # 400x400 white canvas
    img = np.full((400, 400), 255, dtype=np.uint8)

    # Draw North wall: (50, 50) to (350, 50)
    cv2.line(img, (50, 50), (350, 50), 0, thickness=6)
    # Draw East wall: (350, 50) to (350, 350)
    cv2.line(img, (350, 50), (350, 350), 0, thickness=6)
    # Draw West wall: (50, 50) to (50, 350)
    cv2.line(img, (50, 50), (50, 350), 0, thickness=6)
    # South wall (50, 350) to (350, 350) is left WHITE (open plan / archway)

    transform = PlanTransform(
        pixel_width=400,
        pixel_height=400,
        scale_mm_per_pixel=10.0,
        origin=CoordinateOrigin.TOP_LEFT,
        is_scale_verified=True,
    )

    # Test North wall (Physical)
    p_north_start = CoordinateTransformEngine.pixel_to_canonical(50, 50, transform)
    p_north_end = CoordinateTransformEngine.pixel_to_canonical(350, 50, transform)
    is_north_phys, conf_north = CanonicalGeometryService.verify_wall_profile(
        p_north_start, p_north_end, transform, gray_img=img
    )
    assert is_north_phys is True
    assert conf_north >= 0.70

    # Test South wall (Virtual open divider)
    p_south_start = CoordinateTransformEngine.pixel_to_canonical(50, 350, transform)
    p_south_end = CoordinateTransformEngine.pixel_to_canonical(350, 350, transform)
    is_south_phys, conf_south = CanonicalGeometryService.verify_wall_profile(
        p_south_start, p_south_end, transform, gray_img=img
    )
    assert is_south_phys is False
    assert conf_south >= 0.70


# =========================================================================
# 7. Door Opening & 90-Degree Swing Sector Collision Envelope
# =========================================================================

def test_door_swing_wedge_geometry_and_collision():
    """
    Test that the 90-degree door swing wedge sector accurately identifies
    points inside the door swing sweep so switches are never mounted there.
    """
    hinge = Point2D_mm(x=1000.0, y=2000.0)
    strike = Point2D_mm(x=1850.0, y=2000.0)  # 850mm clear width

    room_poly = Polygon2D_mm(
        exterior=[
            Point2D_mm(x=1000.0, y=1000.0),
            Point2D_mm(x=5000.0, y=1000.0),
            Point2D_mm(x=5000.0, y=5000.0),
            Point2D_mm(x=1000.0, y=5000.0),
        ]
    )

    wedge_poly = CanonicalGeometryService.calculate_door_swing_wedge(
        hinge_mm=hinge,
        strike_mm=strike,
        room_poly_mm=room_poly,
        swing_dir=DoorSwingDirection.INWARD,
    )

    shapely_wedge = wedge_poly.to_shapely()

    # Point directly in the path of the door sweep (400mm out from hinge at 45 deg)
    mid_sweep_pt = ShapelyPoint(1000.0 + 400.0 * math.cos(math.pi / 4), 2000.0 + 400.0 * math.sin(math.pi / 4))
    assert shapely_wedge.contains(mid_sweep_pt) is True, "Point in door path should be inside swing wedge"

    # Switch mounted outside the door sweep (e.g. 200mm past the strike jamb along the wall)
    safe_switch_pt = ShapelyPoint(2050.0, 2000.0)
    assert shapely_wedge.contains(safe_switch_pt) is False, "Safe switch point must not be inside swing wedge"


# =========================================================================
# 8. Fixed Obstacles & RS IEC 60364-7-701 Exclusion Buffer Tests
# =========================================================================

def test_shower_obstacle_600mm_wet_zone_clearance():
    """
    Tests that fixed shower enclosure has mandatory 600mm Zone 2 exclusion buffer.
    Verifies that a point within 600mm is flagged as restricted, and a point > 600mm is clear.
    """
    # 900mm x 900mm shower enclosure in corner (3000, 3000) to (3900, 3900)
    shower_pts = [
        Point2D_mm(x=3000.0, y=3000.0),
        Point2D_mm(x=3900.0, y=3000.0),
        Point2D_mm(x=3900.0, y=3900.0),
        Point2D_mm(x=3000.0, y=3900.0),
    ]
    shower_obs = FixedObstacle(
        id="shower_1",
        obstacle_type=ObstacleType.SHOWER_ENCLOSURE,
        boundary_mm=Polygon2D_mm(exterior=shower_pts),
        required_buffer_mm=600.0,  # 600mm Zone 2 buffer
        confidence=1.0,
    )

    envelope = shower_obs.exclusion_envelope_mm.to_shapely()

    # Point at (2800, 3500) is 200mm from shower edge -> INSIDE 600mm buffer (VIOLATION)
    unsafe_pt = ShapelyPoint(2800.0, 3500.0)
    assert envelope.contains(unsafe_pt) is True, "Point 200mm from shower must be inside wet exclusion envelope"

    # Point at (2200, 3500) is 800mm from shower edge -> OUTSIDE 600mm buffer (COMPLIANT)
    safe_pt = ShapelyPoint(2200.0, 3500.0)
    assert envelope.contains(safe_pt) is False, "Point 800mm from shower must be outside wet exclusion envelope"


# =========================================================================
# 9. Invalid & Contradictory Geometry Handling
# =========================================================================

def test_invalid_polygon_rejected():
    """Pydantic must reject polygon with fewer than 3 vertices."""
    with pytest.raises(ValueError):
        Polygon2D_mm(exterior=[Point2D_mm(x=0, y=0), Point2D_mm(x=10, y=10)])


def test_invalid_calibration_distance_rejected():
    """Negative or zero calibration distance must raise ValueError."""
    transform = PlanTransform(pixel_width=1000, pixel_height=1000)
    with pytest.raises(ValueError):
        CoordinateTransformEngine.calibrate_scale_from_points((0, 0), (100, 100), -500.0, transform)

    with pytest.raises(ValueError):
        CoordinateTransformEngine.calibrate_scale_from_points((50, 50), (50, 50), 1000.0, transform)


# =========================================================================
# 10. Backward-Compatibility Adapter
# =========================================================================

def test_canonical_to_legacy_adapter_maintains_flutter_contract():
    """
    Verifies that canonical geometry adapts seamlessly to legacy RoomObservation
    and ArchitecturalFeature objects expected by the Flutter canvas.
    """
    rooms = [
        RoomObservation(id="r_bed", name="Bedroom 1", confidence=0.9, bounds=[0.1, 0.1, 0.4, 0.4])
    ]
    features = [
        ArchitecturalFeature(
            type="door",
            room="Bedroom 1",
            confidence=0.88,
            door_position=[0.15, 0.40],
            hinge_point=[0.12, 0.40],
            strike_point=[0.18, 0.40],
            swing_direction="into_room",
        )
    ]

    canonical_plan = CanonicalGeometryService.build_canonical_floor_plan(
        rooms=rooms,
        features=features,
        pixel_width=1000,
        pixel_height=1000,
        scale_mm_per_pixel=10.0,
        is_scale_verified=True,
    )

    legacy_rooms, legacy_features = CanonicalGeometryService.to_legacy_rooms_and_features(canonical_plan)

    assert len(legacy_rooms) == 1
    assert legacy_rooms[0].name == "Bedroom 1"
    assert legacy_rooms[0].bounds == [0.1, 0.1, 0.4, 0.4]

    assert len(legacy_features) >= 1
    door_feat = legacy_features[0]
    assert door_feat.type == "door"
    assert door_feat.door_position is not None
    assert abs(door_feat.door_position[0] - 0.15) < 0.01
    assert abs(door_feat.door_position[1] - 0.40) < 0.01
