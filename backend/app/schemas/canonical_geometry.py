import math
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint, LineString as ShapelyLineString


class ScaleStatus(str, Enum):
    CALIBRATED_DIMENSION = "calibrated_dimension"  # Verified against calibrated reference dimension (interactive or verified metadata; automated OCR not yet implemented)
    USER_CALIBRATED = "user_calibrated"            # User calibrated reference length on plan
    CAD_METADATA = "cad_metadata"                  # Extracted from vector CAD/BIM header
    ESTIMATED_HEURISTIC = "estimated_heuristic"    # Unverified architectural assumption (e.g. 1:100 scale)
    UNSCALED = "unscaled"                          # Dimensionless; physical rules cannot be marked as verified


class AreaStatus(str, Enum):
    VERIFIED = "verified"                                  # Calibrated scale AND exact confirmed polygonal contour
    APPROXIMATE_CALIBRATED = "approximate_calibrated"      # Calibrated scale, but bounding-box rectangular approximation
    UNSCALED_ESTIMATE = "unscaled_estimate"                # Uncalibrated heuristic scale estimate
    UNRESOLVED = "unresolved"                              # Missing, empty, or degenerate boundary


class WallVerificationMethod(str, Enum):
    ADAPTIVE_CORRIDOR_HEURISTIC = "adaptive_corridor_heuristic"
    CAD_VECTOR_EXACT = "cad_vector_exact"
    UNVERIFIED_RASTER = "unverified_raster"
    UNVERIFIED_NO_IMAGE = "unverified_no_image"


class CoordinateOrigin(str, Enum):
    TOP_LEFT = "top_left"          # Standard image/raster screen coordinates (+X right, +Y down)
    BOTTOM_LEFT = "bottom_left"    # Standard Cartesian / CAD world coordinates (+X right, +Y up)


class Point2D_mm(BaseModel):
    """2D Point represented strictly in real-world millimetres (mm)."""
    x: float = Field(..., description="X coordinate in millimeters")
    y: float = Field(..., description="Y coordinate in millimeters")

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_shapely(self) -> ShapelyPoint:
        return ShapelyPoint(self.x, self.y)

    def distance_to(self, other: "Point2D_mm") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Vector2D_mm(BaseModel):
    dx: float
    dy: float

    @property
    def magnitude(self) -> float:
        return math.hypot(self.dx, self.dy)

    def normalized(self) -> "Vector2D_mm":
        mag = self.magnitude
        if mag < 1e-6:
            return Vector2D_mm(dx=0.0, dy=0.0)
        return Vector2D_mm(dx=self.dx / mag, dy=self.dy / mag)


class BoundingBox2D_mm(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return max(0.0, self.max_x - self.min_x)

    @property
    def height(self) -> float:
        return max(0.0, self.max_y - self.min_y)

    @property
    def area_m2(self) -> float:
        return (self.width * self.height) / 1_000_000.0


class Polygon2D_mm(BaseModel):
    """
    Planar polygon in real-world millimetres.
    Exterior loop with optional interior holes (for structural pillars, shafts).
    """
    exterior: List[Point2D_mm] = Field(..., min_length=3, description="Outer loop vertices in mm")
    interiors: List[List[Point2D_mm]] = Field(default_factory=list, description="Hole loops in mm")

    def to_shapely(self) -> ShapelyPolygon:
        ext_coords = [(p.x, p.y) for p in self.exterior]
        int_coords = [[(p.x, p.y) for p in hole] for hole in self.interiors]
        return ShapelyPolygon(ext_coords, int_coords)

    @classmethod
    def from_shapely(cls, poly: ShapelyPolygon) -> "Polygon2D_mm":
        exterior_pts = [Point2D_mm(x=round(c[0], 2), y=round(c[1], 2)) for c in poly.exterior.coords[:-1]]
        interior_pts = []
        for interior in poly.interiors:
            interior_pts.append([Point2D_mm(x=round(c[0], 2), y=round(c[1], 2)) for c in interior.coords[:-1]])
        return cls(exterior=exterior_pts, interiors=interior_pts)

    @property
    def area_m2(self) -> float:
        """Computes true floor area in square meters from millimeter polygon."""
        poly = self.to_shapely()
        return poly.area / 1_000_000.0

    @property
    def centroid(self) -> Point2D_mm:
        poly = self.to_shapely()
        return Point2D_mm(x=round(poly.centroid.x, 2), y=round(poly.centroid.y, 2))

    @property
    def bounding_box(self) -> BoundingBox2D_mm:
        minx = min(p.x for p in self.exterior)
        maxx = max(p.x for p in self.exterior)
        miny = min(p.y for p in self.exterior)
        maxy = max(p.y for p in self.exterior)
        return BoundingBox2D_mm(min_x=minx, min_y=miny, max_x=maxx, max_y=maxy)


class PlanTransform(BaseModel):
    """
    Rigorous invertible 2D coordinate transformation model.
    Converts between source image pixels, normalized [0, 1] UI display ratios,
    and canonical real-world physical millimeters (mm).
    """
    pixel_width: int = Field(..., ge=1, description="Width of source raster image in pixels")
    pixel_height: int = Field(..., ge=1, description="Height of source raster image in pixels")
    scale_mm_per_pixel: Optional[float] = Field(None, gt=0.0, description="Millimeters represented by 1 raster pixel")
    scale_status: ScaleStatus = Field(ScaleStatus.UNSCALED, description="Confidence/origin of the scale measurement")
    scale_ratio_str: Optional[str] = Field(None, description="Human readable ratio e.g. '1:100 @ 144 DPI'")
    origin: CoordinateOrigin = Field(CoordinateOrigin.TOP_LEFT, description="Coordinate origin definition")
    rotation_deg: float = Field(0.0, description="Plan orientation rotation clockwise in degrees (0, 90, 180, 270)")
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    is_scale_verified: bool = Field(False, description="True ONLY if verified by real dimension or CAD metadata")
    image_sha256: Optional[str] = Field(None, description="SHA-256 hash of the calibrated source image to detect edits/crops")
    calibrated_image_width: Optional[int] = Field(None, description="Width of source image at time of calibration")
    calibrated_image_height: Optional[int] = Field(None, description="Height of source image at time of calibration")

    def update_for_resize(self, new_width: int, new_height: int) -> "PlanTransform":
        """Updates transform when image is resized uniformly. Invalidates if aspect ratio changes."""
        if new_width <= 0 or new_height <= 0:
            raise ValueError(f"Invalid resize dimensions: {new_width}x{new_height}")

        orig_aspect = self.pixel_width / float(self.pixel_height)
        new_aspect = new_width / float(new_height)

        if abs(orig_aspect - new_aspect) > 0.01:
            # Non-uniform stretch invalidates scale
            return self.model_copy(update={
                "pixel_width": new_width,
                "pixel_height": new_height,
                "scale_mm_per_pixel": None,
                "scale_status": ScaleStatus.UNSCALED,
                "is_scale_verified": False,
                "scale_ratio_str": "Invalidated by non-uniform resize",
            })

        # Uniform resize scales scale_mm_per_pixel inversely
        scale_mult = float(self.pixel_width) / float(new_width)
        new_scale = (self.scale_mm_per_pixel * scale_mult) if self.scale_mm_per_pixel else None

        return self.model_copy(update={
            "pixel_width": new_width,
            "pixel_height": new_height,
            "scale_mm_per_pixel": round(new_scale, 4) if new_scale else None,
        })

    def update_for_crop(self, crop_x: float, crop_y: float, crop_w: int, crop_h: int) -> "PlanTransform":
        """Updates transform for a cropped region of the image."""
        if crop_w <= 0 or crop_h <= 0:
            raise ValueError(f"Invalid crop dimensions: {crop_w}x{crop_h}")

        scale = self.scale_mm_per_pixel if self.scale_mm_per_pixel else 1.0
        new_offset_x = self.offset_x_mm + (crop_x * scale)
        new_offset_y = self.offset_y_mm + (crop_y * scale)

        return self.model_copy(update={
            "pixel_width": crop_w,
            "pixel_height": crop_h,
            "offset_x_mm": round(new_offset_x, 2),
            "offset_y_mm": round(new_offset_y, 2),
        })

    def pixel_to_canonical(self, px: float, py: float) -> Point2D_mm:
        """Converts raw image pixel (px, py) to canonical physical millimeters."""
        if not self.scale_mm_per_pixel:
            # When unscaled, 1 pixel = 1 unit (arbitrary normalized scale)
            scale = 1.0
        else:
            scale = self.scale_mm_per_pixel

        # Origin conversion
        if self.origin == CoordinateOrigin.BOTTOM_LEFT:
            py = self.pixel_height - py

        # Scale to millimeters
        x_mm = (px * scale) + self.offset_x_mm
        y_mm = (py * scale) + self.offset_y_mm
        return Point2D_mm(x=round(x_mm, 2), y=round(y_mm, 2))

    def canonical_to_pixel(self, pt: Point2D_mm) -> Tuple[float, float]:
        """Converts canonical physical millimeters back to image pixels."""
        scale = self.scale_mm_per_pixel if self.scale_mm_per_pixel else 1.0
        px = (pt.x - self.offset_x_mm) / scale
        py = (pt.y - self.offset_y_mm) / scale

        if self.origin == CoordinateOrigin.BOTTOM_LEFT:
            py = self.pixel_height - py

        return (round(px, 2), round(py, 2))

    def normalized_to_canonical(self, nx: float, ny: float) -> Point2D_mm:
        """Converts normalized display ratio [0.0, 1.0] to canonical physical millimeters."""
        px = nx * self.pixel_width
        py = ny * self.pixel_height
        return self.pixel_to_canonical(px, py)

    def canonical_to_normalized(self, pt: Point2D_mm) -> Tuple[float, float]:
        """Converts canonical physical millimeters to normalized display ratio [0.0, 1.0]."""
        px, py = self.canonical_to_pixel(pt)
        nx = max(0.0, min(1.0, px / self.pixel_width))
        ny = max(0.0, min(1.0, py / self.pixel_height))
        return (round(nx, 4), round(ny, 4))


class WallClassification(str, Enum):
    STRUCTURAL = "structural"              # Concrete / reinforced load-bearing core wall
    PARTITION = "partition"                # Interior drywall or masonry dividing wall
    VIRTUAL_DIVIDER = "virtual_divider"    # Open-plan boundary (e.g. living/dining/corridor divider)
    PERIMETER = "perimeter"                # External building envelope boundary
    UNKNOWN = "unknown"


class WallSegment(BaseModel):
    """Individual structural or partition wall line segment."""
    id: str
    start: Point2D_mm
    end: Point2D_mm
    thickness_mm: Optional[float] = Field(None, description="Physical wall thickness in mm (e.g. 150mm, 200mm)")
    classification: WallClassification = WallClassification.UNKNOWN
    interior_room_id: Optional[str] = None
    exterior_or_neighbor_room_id: Optional[str] = None
    shared_with_wall_id: Optional[str] = Field(None, description="ID of coincident shared wall segment in neighboring room")
    is_shared_duplicate: bool = Field(False, description="True if this wall segment duplicates an already-registered shared partition")
    verification_method: WallVerificationMethod = Field(
        WallVerificationMethod.ADAPTIVE_CORRIDOR_HEURISTIC,
        description="Method used to detect or verify physical wall presence",
    )
    is_verified_physical_wall: bool = Field(False, description="True if proven by continuous dark pixels or CAD line")
    is_physical_candidate: bool = Field(False, description="True if heuristic corridor suggests physical wall presence")
    is_ambiguous: bool = Field(False, description="True if wall evidence is borderline and requires user/field confirmation")
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def length_mm(self) -> float:
        return self.start.distance_to(self.end)

    def to_shapely(self) -> ShapelyLineString:
        return ShapelyLineString([(self.start.x, self.start.y), (self.end.x, self.end.y)])


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    ENTRANCE = "entrance"
    OPEN_PASSAGE = "open_passage"


class DoorSwingDirection(str, Enum):
    INWARD = "inward"
    OUTWARD = "outward"
    SLIDING = "sliding"
    POCKET = "pocket"
    DOUBLE_ACTING = "double_acting"
    UNKNOWN = "unknown"


class Opening(BaseModel):
    """Door or window opening in a wall."""
    id: str
    type: OpeningType
    room_id: str
    wall_id: Optional[str] = None
    center_mm: Point2D_mm
    width_mm: Optional[float] = Field(None, description="Clear door opening width in mm (e.g. 800mm, 900mm)")
    height_mm: Optional[float] = Field(None, description="Clear vertical opening height in mm (e.g. 2100mm)")
    hinge_point_mm: Optional[Point2D_mm] = None
    strike_point_mm: Optional[Point2D_mm] = None
    swing_direction: DoorSwingDirection = DoorSwingDirection.UNKNOWN
    is_swing_observed: bool = Field(
        False,
        description="True ONLY if door swing direction and arc were explicitly observed on the architectural plan",
    )
    observed_swing_arc_mm: Optional[Polygon2D_mm] = Field(
        None,
        description="Exact circular sector swept by door leaf strictly when observed on the drawing",
    )
    assumed_clearance_envelope_mm: Optional[Polygon2D_mm] = Field(
        None,
        description="Conservative safety clearance envelope assumed for switch placement when swing direction is unobserved",
    )
    swing_arc_sector_mm: Optional[Polygon2D_mm] = Field(
        None,
        description="Clearance sector envelope (observed or assumed). Switches must NEVER land inside this envelope.",
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class ObstacleType(str, Enum):
    SHOWER_ENCLOSURE = "shower_enclosure"
    BATHTUB = "bathtub"
    SINK_VANITY = "sink_vanity"
    TOILET_WC = "toilet_wc"
    COOKER_STOVE = "cooker_stove"
    REFRIGERATOR = "refrigerator"
    KITCHEN_COUNTER = "kitchen_counter"
    WARDROBE_CLOSET = "wardrobe_closet"
    BED = "bed"
    DESK = "desk"
    COLUMN_PILLAR = "column_pillar"
    OTHER = "other"


class FixedObstacle(BaseModel):
    """
    Fixed furniture or sanitary fixture that restricts electrical placement.
    Contains exclusion buffer to enforce RS IEC 60364 clearances.
    """
    id: str
    room_id: Optional[str] = None
    obstacle_type: ObstacleType
    boundary_mm: Polygon2D_mm
    required_buffer_mm: float = Field(
        0.0,
        description="Mandatory exclusion clearance buffer in mm (e.g. 600mm Zone 2 buffer for showers)",
    )
    is_compliance_certified: bool = Field(
        False,
        description="True ONLY if clearance buffer is calculated against verified physical scale and regulatory standard",
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def exclusion_envelope_mm(self) -> Polygon2D_mm:
        """Returns the raw boundary polygon expanded by required_buffer_mm."""
        if self.required_buffer_mm <= 0.0:
            return self.boundary_mm
        buffered = self.boundary_mm.to_shapely().buffer(self.required_buffer_mm)
        return Polygon2D_mm.from_shapely(buffered)

    def get_clipped_envelope_mm(self, room_poly_mm: Optional[Polygon2D_mm]) -> Polygon2D_mm:
        """
        Returns the exclusion envelope clipped to the room interior polygon,
        preventing safety zones from penetrating drywall partitions into adjacent rooms.
        """
        raw_env = self.exclusion_envelope_mm
        if room_poly_mm is None:
            return raw_env

        sh_raw = raw_env.to_shapely()
        sh_room = room_poly_mm.to_shapely()

        intersection = sh_raw.intersection(sh_room)
        if intersection.is_empty or not hasattr(intersection, "exterior"):
            return raw_env

        return Polygon2D_mm.from_shapely(intersection)


class RoomType(str, Enum):
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    KITCHEN_DINING = "kitchen_dining"
    DINING_ROOM = "dining_room"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    BATHROOM = "bathroom"
    POWDER_ROOM_WC = "powder_room_wc"
    OFFICE_STUDY = "office_study"
    CORRIDOR_HALLWAY = "corridor_hallway"
    ENTRANCE_FOYER = "entrance_foyer"
    BALCONY_TERRACE = "balcony_terrace"
    UTILITY_STORE = "utility_store"
    OTHER = "other"


class RoomBoundary(BaseModel):
    """
    Fully-specified room in canonical physical units.
    Contains closed polygon boundary, area, and links to walls, openings, and interior obstacles.
    """
    id: str
    name: str
    room_type: RoomType
    boundary_polygon_mm: Polygon2D_mm
    area_m2: Optional[float] = Field(None, description="Physical floor area in m2; verified ONLY if scale and true geometry are confirmed")
    area_status: AreaStatus = Field(
        AreaStatus.UNSCALED_ESTIMATE,
        description="Explicit area status: verified, approximate_calibrated, unscaled_estimate, or unresolved",
    )
    is_area_verified: bool = Field(
        False,
        description="True ONLY if calculated from verified millimeter scale AND verified contour (not a bounding box approximation)",
    )
    is_rectangular_approximation: bool = Field(
        False,
        description="True if polygon is a bounding box approximation rather than verified contour",
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    has_virtual_boundaries: bool = Field(
        False,
        description="True if room shares an open-plan virtual divider with an adjacent space",
    )
    wall_ids: List[str] = Field(default_factory=list)
    opening_ids: List[str] = Field(default_factory=list)
    obstacle_ids: List[str] = Field(default_factory=list)


class SourceProvenance(BaseModel):
    """Full architectural audit provenance."""
    source_file: str
    file_type: str  # pdf, png, jpg, dwg, ifc
    raster_width_px: int
    raster_height_px: int
    dpi: Optional[float] = None
    detection_method: str  # ai_vision, cv_contour, manual_cad, mock
    unresolved_geometry: List[str] = Field(default_factory=list)
    geometry_warnings: List[str] = Field(default_factory=list)


class FloorLevel(BaseModel):
    id: str
    name: str = "Ground Floor"
    level_index: int = 0
    elevation_mm: float = 0.0
    height_clear_mm: float = 2800.0  # Default 2.8m finished ceiling height


class Building(BaseModel):
    id: str
    name: str
    building_type: str = "Residential"
    standard_applied: str = "RS IEC 60364"


class CanonicalFloorPlan(BaseModel):
    """
    Top-level Canonical Building Geometry Model.
    Serves as the trusted, format-independent engineering representation of the floor plan.
    """
    building: Building
    level: FloorLevel
    transform: PlanTransform
    provenance: SourceProvenance
    rooms: List[RoomBoundary] = Field(default_factory=list)
    walls: List[WallSegment] = Field(default_factory=list)
    openings: List[Opening] = Field(default_factory=list)
    obstacles: List[FixedObstacle] = Field(default_factory=list)
    is_scale_verified: bool = Field(False, description="Mandatory gate: false prevents physical rules from being certified")

    def get_room_by_id(self, room_id: str) -> Optional[RoomBoundary]:
        for r in self.rooms:
            if r.id == room_id:
                return r
        return None

    def get_obstacles_for_room(self, room_id: str) -> List[FixedObstacle]:
        return [o for o in self.obstacles if o.room_id == room_id]

    def get_openings_for_room(self, room_id: str) -> List[Opening]:
        return [op for op in self.openings if op.room_id == room_id]
