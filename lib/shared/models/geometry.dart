import 'dart:math' as math;
import 'dart:ui';

const List<String> kWalls = ['north', 'south', 'east', 'west'];

/// A room as an axis-aligned rectangle in plan ratios (0-1).
class GeoRoom {
  final String id;
  final String name;
  final Rect rect;
  final double? areaM2;
  final bool isManual;

  const GeoRoom({
    required this.id,
    required this.name,
    required this.rect,
    this.areaM2,
    this.isManual = false,
  });

  GeoRoom copyWith({String? name, Rect? rect}) => GeoRoom(
        id: id,
        name: name ?? this.name,
        rect: rect ?? this.rect,
        areaM2: areaM2,
        isManual: isManual,
      );

  /// Null when the backend sent no usable boundary.
  static GeoRoom? fromJson(Map<String, dynamic> json) {
    final b = (json['bounds'] as List?)?.map((e) => (e as num).toDouble()).toList();
    if (b == null || b.length < 4) return null;
    return GeoRoom(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      rect: Rect.fromLTRB(b[0], b[1], b[2], b[3]),
      areaM2: (json['area_m2'] as num?)?.toDouble(),
      isManual: json['is_manual'] as bool? ?? false,
    );
  }
}

class GeoDoor {
  final String id;
  final String roomId;
  final String wall;
  final Offset position;
  final String swingDirection; // into_room | out_of_room
  final String? strikeSide;
  final bool isManual;

  const GeoDoor({
    required this.id,
    required this.roomId,
    required this.wall,
    required this.position,
    this.swingDirection = 'into_room',
    this.strikeSide,
    this.isManual = false,
  });

  GeoDoor copyWith({String? wall, Offset? position}) => GeoDoor(
        id: id,
        roomId: roomId,
        wall: wall ?? this.wall,
        position: position ?? this.position,
        swingDirection: swingDirection,
        strikeSide: strikeSide,
        isManual: isManual,
      );

  static GeoDoor? fromJson(Map<String, dynamic> json) {
    final type = json['type'];
    final pos = (json['door_position'] as List?)?.map((e) => (e as num).toDouble()).toList();
    if ((type != 'door' && type != 'entrance') || pos == null || pos.length < 2) return null;
    return GeoDoor(
      id: json['id'] as String? ?? '',
      roomId: json['room_id'] as String? ?? '',
      wall: json['wall'] as String? ?? '',
      position: Offset(pos[0], pos[1]),
      swingDirection: json['swing_direction'] as String? ?? 'into_room',
      strikeSide: json['strike_side'] as String?,
      isManual: json['is_manual'] as bool? ?? false,
    );
  }
}

class GeoIssue {
  final String code;
  final String severity; // error | warning
  final String message;
  final List<String> entityIds;

  const GeoIssue({
    required this.code,
    required this.severity,
    required this.message,
    this.entityIds = const [],
  });

  bool get isError => severity == 'error';

  factory GeoIssue.fromJson(Map<String, dynamic> json) => GeoIssue(
        code: json['code'] as String? ?? '',
        severity: json['severity'] as String? ?? 'warning',
        message: json['message'] as String? ?? '',
        entityIds: (json['entity_ids'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      );
}

class GeometryState {
  final List<GeoRoom> rooms;
  final List<GeoDoor> doors;
  final List<GeoIssue> issues;
  final bool canGenerate;
  final bool reviewed;
  final bool needsRegeneration;

  const GeometryState({
    this.rooms = const [],
    this.doors = const [],
    this.issues = const [],
    this.canGenerate = true,
    this.reviewed = false,
    this.needsRegeneration = false,
  });

  GeometryState copyWith({List<GeoRoom>? rooms, List<GeoDoor>? doors}) => GeometryState(
        rooms: rooms ?? this.rooms,
        doors: doors ?? this.doors,
        issues: issues,
        canGenerate: canGenerate,
        reviewed: reviewed,
        needsRegeneration: needsRegeneration,
      );

  int get errorCount => issues.where((i) => i.isError).length;

  factory GeometryState.fromJson(Map<String, dynamic> json) => GeometryState(
        rooms: (json['rooms'] as List? ?? [])
            .map((r) => GeoRoom.fromJson(r as Map<String, dynamic>))
            .whereType<GeoRoom>()
            .toList(),
        doors: (json['features'] as List? ?? [])
            .map((f) => GeoDoor.fromJson(f as Map<String, dynamic>))
            .whereType<GeoDoor>()
            .toList(),
        issues: (json['issues'] as List? ?? [])
            .map((i) => GeoIssue.fromJson(i as Map<String, dynamic>))
            .toList(),
        canGenerate: json['can_generate'] as bool? ?? true,
        reviewed: json['reviewed'] as bool? ?? false,
        needsRegeneration: json['needs_regeneration'] as bool? ?? false,
      );
}

/// Wall of [r] closest to [p] and the position along it
/// (0 = west/north end, 1 = east/south end).
({String wall, double t, Offset point}) snapToWall(Rect r, Offset p) {
  Offset a(String w) => switch (w) {
        'north' => r.topLeft,
        'south' => r.bottomLeft,
        'west' => r.topLeft,
        _ => r.topRight,
      };
  Offset b(String w) => switch (w) {
        'north' => r.topRight,
        'south' => r.bottomRight,
        'west' => r.bottomLeft,
        _ => r.bottomRight,
      };

  String bestWall = kWalls.first;
  double bestDist = double.infinity;
  double bestT = 0.5;
  for (final w in kWalls) {
    final s = a(w);
    final e = b(w);
    final d = e - s;
    final lenSq = d.dx * d.dx + d.dy * d.dy;
    final t = lenSq == 0
        ? 0.0
        : (((p.dx - s.dx) * d.dx + (p.dy - s.dy) * d.dy) / lenSq).clamp(0.0, 1.0);
    final proj = Offset(s.dx + t * d.dx, s.dy + t * d.dy);
    final dist = (p - proj).distance;
    if (dist < bestDist) {
      bestDist = dist;
      bestWall = w;
      bestT = t;
    }
  }
  final s = a(bestWall);
  final e = b(bestWall);
  return (
    wall: bestWall,
    t: bestT,
    point: Offset(s.dx + bestT * (e.dx - s.dx), s.dy + bestT * (e.dy - s.dy)),
  );
}

/// Smallest room containing [p], or null.
GeoRoom? roomAt(List<GeoRoom> rooms, Offset p) {
  GeoRoom? best;
  double bestArea = double.infinity;
  for (final r in rooms) {
    if (r.rect.contains(p)) {
      final area = r.rect.width * r.rect.height;
      if (area < bestArea) {
        best = r;
        bestArea = area;
      }
    }
  }
  return best;
}

/// Keeps a dragged rectangle inside the plan and at least [min] wide/high.
Rect clampRect(Rect r, {double min = 0.02}) {
  final l = math.min(r.left, r.right).clamp(0.0, 1.0 - min);
  final t = math.min(r.top, r.bottom).clamp(0.0, 1.0 - min);
  final rr = math.max(r.left, r.right).clamp(l + min, 1.0);
  final bb = math.max(r.top, r.bottom).clamp(t + min, 1.0);
  return Rect.fromLTRB(l, t, rr, bb);
}
