class Room {
  final String id;
  final String name;
  final double areaM2;
  final int pointsCount;
  final String description;
  final double confidence;
  final List<double>? bounds;
  final bool isAreaVerified;
  final bool isRectangularApproximation;
  final String areaStatus; // 'verified', 'approximate_calibrated', 'unscaled_estimate', 'unresolved'

  const Room({
    required this.id,
    required this.name,
    required this.areaM2,
    required this.pointsCount,
    this.description = '',
    this.confidence = 1.0,
    this.bounds,
    this.isAreaVerified = false,
    this.isRectangularApproximation = false,
    this.areaStatus = 'unscaled_estimate',
  });

  factory Room.fromJson(Map<String, dynamic> json) {
    List<double>? parsedBounds;
    if (json['bounds'] != null && json['bounds'] is List) {
      parsedBounds = (json['bounds'] as List)
          .map((e) => (e as num).toDouble())
          .toList();
    }

    final parsedArea = (json['area_m2'] as num?)?.toDouble() ?? 0.0;
    final fallbackStatus = parsedArea > 0 ? 'approximate_calibrated' : 'unscaled_estimate';

    return Room(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? 'Unnamed Room',
      areaM2: parsedArea,
      pointsCount: (json['points_count'] as num?)?.toInt() ?? 0,
      description: json['description'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      bounds: parsedBounds,
      isAreaVerified: json['is_area_verified'] as bool? ?? false,
      isRectangularApproximation: json['is_rectangular_approximation'] as bool? ?? false,
      areaStatus: json['area_status'] as String? ?? fallbackStatus,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'area_m2': areaM2,
        'points_count': pointsCount,
        'description': description,
        'confidence': confidence,
        'bounds': bounds,
        'is_area_verified': isAreaVerified,
        'is_rectangular_approximation': isRectangularApproximation,
        'area_status': areaStatus,
      };

  Room copyWith({
    String? id,
    String? name,
    double? areaM2,
    int? pointsCount,
    String? description,
    double? confidence,
    List<double>? bounds,
    bool? isAreaVerified,
    bool? isRectangularApproximation,
    String? areaStatus,
  }) {
    return Room(
      id: id ?? this.id,
      name: name ?? this.name,
      areaM2: areaM2 ?? this.areaM2,
      pointsCount: pointsCount ?? this.pointsCount,
      description: description ?? this.description,
      confidence: confidence ?? this.confidence,
      bounds: bounds ?? this.bounds,
      isAreaVerified: isAreaVerified ?? this.isAreaVerified,
      isRectangularApproximation:
          isRectangularApproximation ?? this.isRectangularApproximation,
      areaStatus: areaStatus ?? this.areaStatus,
    );
  }
}
