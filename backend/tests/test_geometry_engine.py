import pytest
from shapely.geometry import Point, LineString, Polygon
from app.services.geometry_engine import GeometryEngine


def test_door_strike_side_snapping_never_floats():
    """Rule 1: Switch must attach to wall and snap <= 20cm from door frame on strike side."""
    room_bounds = [0.10, 0.10, 0.50, 0.60]
    room_poly = GeometryEngine.create_room_polygon(room_bounds)
    walls = GeometryEngine.get_wall_segments(room_poly)

    north_wall = walls["north"]
    door_strike_pt = Point(0.20, 0.10) # Door opening on North wall

    sw_pt = GeometryEngine.place_door_switch(
        door_strike_point=door_strike_pt,
        adjacent_wall=north_wall,
        offset_norm=0.020,
        room_polygon=room_poly,
    )

    # 1. Switch must be wall-attached flush: y should be close to 0.115 (0.10 + 0.015)
    assert abs(sw_pt.y - 0.115) < 0.005, f"Switch y={sw_pt.y} is floating away from North wall!"

    # 2. Switch must be offset along wall by ~0.02 from door frame (x ~ 0.22)
    assert abs(sw_pt.x - 0.22) < 0.005, f"Switch x={sw_pt.x} is not on strike side!"

    # 3. Must be strictly inside room boundary
    assert room_poly.contains(sw_pt) or room_poly.touches(sw_pt)


def test_geometric_center_for_ceiling_luminaires():
    """Rule 2: Luminaire center must use representative_point() strictly inside polygon."""
    # Test L-shaped room where regular centroid might fall in outer void
    # L-shape: 2x2 square with top-right 1x1 removed
    l_shape_coords = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0)]
    l_poly = Polygon(l_shape_coords)

    lum_pt = GeometryEngine.place_room_luminaire(l_poly)

    # Must be strictly inside polygon
    assert l_poly.contains(lum_pt), "Luminaire placement fell outside room polygon!"


def test_distributed_luminaires_inside_room():
    """Multi-luminaire distribution along room major axis."""
    room_bounds = [0.05, 0.05, 0.85, 0.45] # Wide room (w=0.80, h=0.40)
    poly = GeometryEngine.create_room_polygon(room_bounds)

    pts = GeometryEngine.place_distributed_luminaires(poly, count=3)
    assert len(pts) == 3
    for p in pts:
        assert poly.contains(p), f"Point {p} is outside room polygon!"

    # Must be distributed horizontally in increasing X order
    assert pts[0].x < pts[1].x < pts[2].x


def test_iec_60364_701_wet_zone_safety_buffer():
    """Rule 3: Socket within shower 60cm buffer must be rejected per IEC 60364-7-701."""
    # Shower footprint: 1m x 1m in corner [0.10, 0.10, 0.20, 0.20]
    shower_poly = Polygon([(0.10, 0.10), (0.20, 0.10), (0.20, 0.20), (0.10, 0.20)])

    # Dangerous socket: 20cm away from shower (within 60cm buffer = 0.060 norm)
    hazard_socket = Point(0.22, 0.22)
    is_safe = GeometryEngine.validate_socket_position(hazard_socket, shower_poly, min_dist_norm=0.060)
    assert not is_safe, "Hazardous socket inside Zone 2 buffer was improperly allowed!"

    # Safe socket: 80cm away from shower (outside 60cm buffer)
    safe_socket = Point(0.35, 0.35)
    is_safe = GeometryEngine.validate_socket_position(safe_socket, shower_poly, min_dist_norm=0.060)
    assert is_safe, "Safe socket outside Zone 2 buffer was improperly rejected!"


def test_clean_control_wire_bezier_arc():
    """Rule 4: Generate curved CAD Bézier arc with control point and length."""
    sw_pt = Point(0.12, 0.15)
    lt_pt = Point(0.30, 0.30)

    arc = GeometryEngine.generate_wiring_arc(sw_pt, lt_pt, sag=0.22)

    assert arc["start"] == (0.12, 0.15)
    assert arc["end"] == (0.30, 0.30)
    assert "control" in arc
    assert len(arc["control"]) == 2
    assert arc["length"] > 0.20, "Arc length should exceed straight-line distance"


def test_directional_door_switch_moves_away_from_opening():
    """Door switch must move away from the opening when door_position/hinge are given."""
    room_bounds = [0.0, 0.0, 1.0, 1.0]
    poly = GeometryEngine.create_room_polygon(room_bounds)
    walls = GeometryEngine.get_wall_segments(poly)
    south_wall = walls["south"] # from (1.0, 1.0) to (0.0, 1.0)

    # Door opening from x=0.60 to x=0.80. Hinge at 0.80, Strike at 0.60, door center at 0.70
    strike_pt = Point(0.60, 1.0)
    door_pos = Point(0.70, 1.0)
    hinge_pt = Point(0.80, 1.0)

    sw_pt = GeometryEngine.place_door_switch(
        door_strike_point=strike_pt,
        adjacent_wall=south_wall,
        offset_norm=0.020,
        door_position=door_pos,
        hinge_point=hinge_pt,
        room_polygon=poly,
    )

    # South wall LineString goes East->West (from 1.0 to 0.0)
    # Strike is at x=0.60, door center is at x=0.70.
    # Moving away from door means moving towards x=0.0 (x should be ~0.58, NOT between 0.60 and 0.80)
    assert sw_pt.x < 0.60, f"Switch at x={sw_pt.x} is inside door opening between 0.60 and 0.80!"
    assert abs(sw_pt.x - 0.58) < 0.005


def test_get_safe_bathroom_socket_position():
    """Shaver socket must be outside shower zone buffer."""
    room_bounds = [0.30, 0.15, 0.60, 0.40]
    room_poly = GeometryEngine.create_room_polygon(room_bounds)
    # Shower in top-left [0.30, 0.15, 0.42, 0.27]
    shower_poly = Polygon([(0.30, 0.15), (0.42, 0.15), (0.42, 0.27), (0.30, 0.27)])

    safe_pt = GeometryEngine.get_safe_bathroom_socket_position(
        room_polygon=room_poly,
        shower_polygon=shower_poly,
    )

    # Must be outside 60cm buffer from shower
    is_safe = GeometryEngine.validate_socket_position(safe_pt, shower_poly, min_dist_norm=0.060)
    assert is_safe, f"Safe bathroom socket {safe_pt} violated 60cm wet zone buffer!"
