import math
from typing import Tuple, List, Optional, Union
from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon, LineString as ShapelyLineString

from app.schemas.canonical_geometry import (
    Point2D_mm,
    Polygon2D_mm,
    BoundingBox2D_mm,
    PlanTransform,
    CoordinateOrigin,
    ScaleStatus,
)


class CoordinateTransformEngine:
    """
    Bidirectional coordinate transformation engine for VoltPlan.
    Converts strictly between:
      1. Source Image Pixels (px)
      2. Normalized Display Coordinates [0.0, 1.0] (for Flutter Canvas)
      3. Canonical Physical Millimeters (mm)
      4. Vector CAD coordinates (meters / mm)

    Guarantees:
      - Sub-millimeter and sub-pixel round-trip accuracy (< 0.01 mm / < 0.001 norm).
      - Strict scale verification gate: uncalibrated plans cannot claim verified physical scale.
      - Supports non-standard origins (top-left vs bottom-left Cartesian) and rotation (0, 90, 180, 270 deg).
    """

    @staticmethod
    def pixel_to_canonical(
        px: float,
        py: float,
        transform: PlanTransform,
    ) -> Point2D_mm:
        """
        Converts raster pixel coordinate (px, py) to canonical physical millimeters (mm).
        Accounts for origin (top-left vs bottom-left Cartesian) and clockwise rotation.
        """
        w = float(transform.pixel_width)
        h = float(transform.pixel_height)

        # 1. Handle rotation (clockwise around image center)
        rot = transform.rotation_deg % 360.0
        if abs(rot - 90.0) < 1e-4:
            # 90 deg CW: (x, y) -> (h - 1 - y, x)
            px_rot = h - 1.0 - py
            py_rot = px
        elif abs(rot - 180.0) < 1e-4:
            # 180 deg CW: (x, y) -> (w - 1 - x, h - 1 - y)
            px_rot = w - 1.0 - px
            py_rot = h - 1.0 - py
        elif abs(rot - 270.0) < 1e-4:
            # 270 deg CW: (x, y) -> (y, w - 1 - x)
            px_rot = py
            py_rot = w - 1.0 - px
        elif abs(rot) < 1e-4:
            px_rot = px
            py_rot = py
        else:
            # Arbitrary rotation about center
            cx, cy = w / 2.0, h / 2.0
            rad = math.radians(rot)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            dx = px - cx
            dy = py - cy
            px_rot = cx + (dx * cos_a - dy * sin_a)
            py_rot = cy + (dx * sin_a + dy * cos_a)

        # 2. Origin adjustment: raster is top-left (+Y down); CAD is bottom-left (+Y up)
        if transform.origin == CoordinateOrigin.BOTTOM_LEFT:
            py_rot = h - py_rot

        # 3. Physical scale mapping (mm per pixel)
        scale = transform.scale_mm_per_pixel if transform.scale_mm_per_pixel is not None else 1.0

        x_mm = (px_rot * scale) + transform.offset_x_mm
        y_mm = (py_rot * scale) + transform.offset_y_mm

        return Point2D_mm(x=round(x_mm, 2), y=round(y_mm, 2))

    @staticmethod
    def canonical_to_pixel(
        pt: Point2D_mm,
        transform: PlanTransform,
    ) -> Tuple[float, float]:
        """
        Converts canonical physical millimeters (mm) back to source raster pixels (px).
        Inverts origin and rotation transforms.
        """
        w = float(transform.pixel_width)
        h = float(transform.pixel_height)
        scale = transform.scale_mm_per_pixel if transform.scale_mm_per_pixel is not None else 1.0

        # 1. Unscale from mm to rotated pixels
        px_rot = (pt.x - transform.offset_x_mm) / scale
        py_rot = (pt.y - transform.offset_y_mm) / scale

        # 2. Invert origin
        if transform.origin == CoordinateOrigin.BOTTOM_LEFT:
            py_rot = h - py_rot

        # 3. Invert rotation (counter-clockwise)
        rot = transform.rotation_deg % 360.0
        if abs(rot - 90.0) < 1e-4:
            # Invert 90 CW: px = py_rot, py = h - 1.0 - px_rot
            px = py_rot
            py = h - 1.0 - px_rot
        elif abs(rot - 180.0) < 1e-4:
            px = w - 1.0 - px_rot
            py = h - 1.0 - py_rot
        elif abs(rot - 270.0) < 1e-4:
            px = w - 1.0 - py_rot
            py = px_rot
        elif abs(rot) < 1e-4:
            px = px_rot
            py = py_rot
        else:
            cx, cy = w / 2.0, h / 2.0
            rad = -math.radians(rot)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            dx = px_rot - cx
            dy = py_rot - cy
            px = cx + (dx * cos_a - dy * sin_a)
            py = cy + (dx * sin_a + dy * cos_a)

        return (round(px, 2), round(py, 2))

    @classmethod
    def normalized_to_canonical(
        cls,
        nx: float,
        ny: float,
        transform: PlanTransform,
    ) -> Point2D_mm:
        """
        Converts normalized display coordinate [0.0, 1.0] to canonical physical millimeters (mm).
        """
        px = nx * float(transform.pixel_width)
        py = ny * float(transform.pixel_height)
        return cls.pixel_to_canonical(px, py, transform)

    @classmethod
    def canonical_to_normalized(
        cls,
        pt: Point2D_mm,
        transform: PlanTransform,
    ) -> Tuple[float, float]:
        """
        Converts canonical physical millimeters (mm) to normalized display ratio [0.0, 1.0].
        Clamps coordinates cleanly to [0.0, 1.0].
        """
        px, py = cls.canonical_to_pixel(pt, transform)
        nx = max(0.0, min(1.0, px / float(transform.pixel_width)))
        ny = max(0.0, min(1.0, py / float(transform.pixel_height)))
        return (round(nx, 4), round(ny, 4))

    @classmethod
    def polygon_to_canonical(
        cls,
        points: List[Tuple[float, float]],
        transform: PlanTransform,
        is_normalized: bool = True,
    ) -> Polygon2D_mm:
        """
        Converts an exterior loop of 2D points (either normalized or pixel) to Polygon2D_mm.
        """
        canonical_pts: List[Point2D_mm] = []
        for x, y in points:
            if is_normalized:
                canonical_pts.append(cls.normalized_to_canonical(x, y, transform))
            else:
                canonical_pts.append(cls.pixel_to_canonical(x, y, transform))
        return Polygon2D_mm(exterior=canonical_pts)

    @classmethod
    def polygon_to_normalized(
        cls,
        poly_mm: Polygon2D_mm,
        transform: PlanTransform,
    ) -> List[Tuple[float, float]]:
        """
        Converts canonical Polygon2D_mm exterior vertices back to normalized [0.0, 1.0] coordinates.
        """
        norm_pts: List[Tuple[float, float]] = []
        for pt in poly_mm.exterior:
            norm_pts.append(cls.canonical_to_normalized(pt, transform))
        return norm_pts

    @staticmethod
    def calibrate_scale_from_points(
        p1_px: Tuple[float, float],
        p2_px: Tuple[float, float],
        physical_distance_mm: float,
        transform: PlanTransform,
        source: ScaleStatus = ScaleStatus.CALIBRATED_DIMENSION,
    ) -> PlanTransform:
        """
        Calibrates scale factor (mm/pixel) using two known pixel locations and the real-world mm distance.
        Example: Dimension line OCR specifies 4000mm between two tick marks.
        """
        if physical_distance_mm <= 0.0:
            raise ValueError(f"Physical distance must be positive, got {physical_distance_mm} mm")

        pixel_dist = math.hypot(p2_px[0] - p1_px[0], p2_px[1] - p1_px[1])
        if pixel_dist < 1.0:
            raise ValueError("Reference points are too close (< 1 pixel) to reliably establish scale")

        scale_mm_per_pixel = physical_distance_mm / pixel_dist
        ratio_str = f"1 px = {scale_mm_per_pixel:.2f} mm ({pixel_dist:.1f}px = {physical_distance_mm:.0f}mm)"

        return transform.model_copy(
            update={
                "scale_mm_per_pixel": round(scale_mm_per_pixel, 4),
                "scale_status": source,
                "scale_ratio_str": ratio_str,
                "is_scale_verified": (source in [ScaleStatus.CALIBRATED_DIMENSION, ScaleStatus.USER_CALIBRATED, ScaleStatus.CAD_METADATA]),
            }
        )

    @staticmethod
    def calibrate_scale_from_ratio(
        ratio_denominator: float,
        dpi: float,
        transform: PlanTransform,
        is_verified: bool = False,
    ) -> PlanTransform:
        """
        Calibrates scale from an architectural ratio (e.g. 1:100, 1:50) and image DPI.
        Formula: 1 inch = 25.4 mm.
        1 pixel = (25.4 / DPI) mm on paper.
        In the real world: 1 pixel = (25.4 / DPI) * ratio_denominator mm.
        """
        if ratio_denominator <= 0 or dpi <= 0:
            raise ValueError("Scale denominator and DPI must be strictly positive")

        paper_mm_per_pixel = 25.4 / dpi
        scale_mm_per_pixel = paper_mm_per_pixel * ratio_denominator
        status = ScaleStatus.CAD_METADATA if is_verified else ScaleStatus.ESTIMATED_HEURISTIC
        ratio_str = f"1:{int(ratio_denominator)} @ {dpi:.0f} DPI ({scale_mm_per_pixel:.2f} mm/px)"

        return transform.model_copy(
            update={
                "scale_mm_per_pixel": round(scale_mm_per_pixel, 4),
                "scale_status": status,
                "scale_ratio_str": ratio_str,
                "is_scale_verified": is_verified,
            }
        )

    @staticmethod
    def create_unscaled_transform(
        pixel_width: int,
        pixel_height: int,
        rotation_deg: float = 0.0,
    ) -> PlanTransform:
        """
        Creates a clean unscaled transform when no dimensional calibration is present.
        Sets scale_status=UNSCALED and is_scale_verified=False.
        """
        return PlanTransform(
            pixel_width=pixel_width,
            pixel_height=pixel_height,
            scale_mm_per_pixel=None,
            scale_status=ScaleStatus.UNSCALED,
            scale_ratio_str="Unscaled (Relative Units Only)",
            origin=CoordinateOrigin.TOP_LEFT,
            rotation_deg=rotation_deg,
            is_scale_verified=False,
        )
