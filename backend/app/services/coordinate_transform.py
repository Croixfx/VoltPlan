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
    Standardized Affine 2D Coordinate Transformation Engine for VoltPlan.
    Converts strictly between:
      1. Source Image Pixels (continuous px, where [0, W] x [0, H] spans the image extent)
      2. Normalized Display Coordinates [0.0, 1.0] (for Flutter Canvas)
      3. Canonical Physical Millimeters (mm)
      4. Vector CAD coordinates (Cartesian bottom-left origin)

    Guarantees:
      - Rigorous affine matrix transformations for rectangular images (W != H).
      - Bounding box dimension swapping on right-angle rotations (90°, 270°: W' = H, H' = W).
      - Correct origin inversion accounting for post-rotation coordinate frames.
      - Scale verification gating: uncalibrated plans remain explicitly unverified.
      - Rejection of degenerate calibration distances (< 5.0 px, <= 0.0 mm).
    """

    @staticmethod
    def _compute_frame_dimensions(w: float, h: float, rot: float) -> Tuple[float, float]:
        """Calculates destination frame dimensions (W', H') after rotation."""
        rot_norm = rot % 360.0
        if abs(rot_norm - 90.0) < 1e-4 or abs(rot_norm - 270.0) < 1e-4:
            return (h, w)
        return (w, h)

    @classmethod
    def pixel_to_canonical(
        cls,
        px: float,
        py: float,
        transform: PlanTransform,
    ) -> Point2D_mm:
        """
        Converts raster pixel coordinate (px, py) to canonical physical millimeters (mm).
        Uses continuous affine coordinate transformations with exact frame dimension tracking.
        """
        w = float(transform.pixel_width)
        h = float(transform.pixel_height)
        rot = transform.rotation_deg % 360.0

        # 1. Continuous rotation transformation
        # Bounding box aligned right-angle rotations
        if abs(rot - 90.0) < 1e-4:
            # 90 deg CW: (px, py) in [0, W]x[0, H] -> (H - py, px) in [0, H]x[0, W]
            px_rot = h - py
            py_rot = px
            dest_w, dest_h = h, w
        elif abs(rot - 180.0) < 1e-4:
            # 180 deg CW: (px, py) in [0, W]x[0, H] -> (W - px, H - py) in [0, W]x[0, H]
            px_rot = w - px
            py_rot = h - py
            dest_w, dest_h = w, h
        elif abs(rot - 270.0) < 1e-4:
            # 270 deg CW: (px, py) in [0, W]x[0, H] -> (py, W - px) in [0, H]x[0, W]
            px_rot = py
            py_rot = w - px
            dest_w, dest_h = h, w
        elif abs(rot) < 1e-4:
            px_rot = px
            py_rot = py
            dest_w, dest_h = w, h
        else:
            # Arbitrary rotation about image center (cx, cy)
            cx, cy = w / 2.0, h / 2.0
            rad = math.radians(rot)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            dx = px - cx
            dy = py - cy
            px_rot = cx + (dx * cos_a - dy * sin_a)
            py_rot = cy + (dx * sin_a + dy * cos_a)
            dest_w, dest_h = w, h

        # 2. Origin adjustment: raster is top-left (+Y down); CAD is bottom-left (+Y up)
        # Note: Must use dest_h (destination frame height), which is W if rotated 90/270 deg!
        if transform.origin == CoordinateOrigin.BOTTOM_LEFT:
            py_rot = dest_h - py_rot

        # 3. Physical scale mapping (mm per pixel)
        scale = transform.scale_mm_per_pixel if transform.scale_mm_per_pixel is not None else 1.0

        x_mm = (px_rot * scale) + transform.offset_x_mm
        y_mm = (py_rot * scale) + transform.offset_y_mm

        return Point2D_mm(x=round(x_mm, 2), y=round(y_mm, 2))

    @classmethod
    def canonical_to_pixel(
        cls,
        pt: Point2D_mm,
        transform: PlanTransform,
    ) -> Tuple[float, float]:
        """
        Converts canonical physical millimeters (mm) back to source raster pixels (px).
        Strict inverse of pixel_to_canonical.
        """
        w = float(transform.pixel_width)
        h = float(transform.pixel_height)
        scale = transform.scale_mm_per_pixel if transform.scale_mm_per_pixel is not None else 1.0
        rot = transform.rotation_deg % 360.0

        # Destination frame dimensions
        if abs(rot - 90.0) < 1e-4 or abs(rot - 270.0) < 1e-4:
            dest_w, dest_h = h, w
        else:
            dest_w, dest_h = w, h

        # 1. Unscale from mm to rotated pixels
        px_rot = (pt.x - transform.offset_x_mm) / scale
        py_rot = (pt.y - transform.offset_y_mm) / scale

        # 2. Invert origin in destination frame
        if transform.origin == CoordinateOrigin.BOTTOM_LEFT:
            py_rot = dest_h - py_rot

        # 3. Invert rotation
        if abs(rot - 90.0) < 1e-4:
            # Invert 90 deg CW: px = py_rot, py = H - px_rot
            px = py_rot
            py = h - px_rot
        elif abs(rot - 180.0) < 1e-4:
            # Invert 180 deg CW: px = W - px_rot, py = H - py_rot
            px = w - px_rot
            py = h - py_rot
        elif abs(rot - 270.0) < 1e-4:
            # Invert 270 deg CW: px = W - py_rot, py = px_rot
            px = w - py_rot
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
        source: ScaleStatus = ScaleStatus.USER_CALIBRATED,
    ) -> PlanTransform:
        """
        Calibrates scale factor (mm/pixel) using two verified pixel reference locations.
        Rejects degenerate distances (< 5.0 px, <= 0.0 mm).
        Records image width and height at time of calibration for invalidation checks.
        """
        if physical_distance_mm <= 0.0:
            raise ValueError(f"Physical distance must be strictly positive, got {physical_distance_mm} mm")

        pixel_dist = math.hypot(p2_px[0] - p1_px[0], p2_px[1] - p1_px[1])
        if pixel_dist < 5.0:
            raise ValueError(
                f"Reference points are too close ({pixel_dist:.1f} px < 5.0 px) to reliably establish scale. "
                "Select two distant landmark points for calibration."
            )

        scale_mm_per_pixel = physical_distance_mm / pixel_dist
        ratio_str = f"1 px = {scale_mm_per_pixel:.2f} mm ({pixel_dist:.1f}px = {physical_distance_mm:.0f}mm)"

        is_verified = source in [
            ScaleStatus.CALIBRATED_DIMENSION,
            ScaleStatus.USER_CALIBRATED,
            ScaleStatus.CAD_METADATA,
        ]

        return transform.model_copy(
            update={
                "scale_mm_per_pixel": round(scale_mm_per_pixel, 4),
                "scale_status": source,
                "scale_ratio_str": ratio_str,
                "is_scale_verified": is_verified,
                "calibrated_image_width": transform.pixel_width,
                "calibrated_image_height": transform.pixel_height,
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
        NOTE: Unless backed by vector CAD/BIM header metadata, this is an ESTIMATED HEURISTIC,
        because raster file DPI metadata rarely matches actual physical paper print scaling.
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
                "calibrated_image_width": transform.pixel_width,
                "calibrated_image_height": transform.pixel_height,
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
