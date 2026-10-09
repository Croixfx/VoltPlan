class ArchitecturalFeature {
  final String type;
  final String roomName;
  final double confidence;
  final String? wall;
  final String? strikeSide;
  final List<double>? doorPosition;
  final List<double>? strikePoint;
  final String? notes;

  const ArchitecturalFeature({
    required this.type,
    required this.roomName,
    required this.confidence,
    this.wall,
    this.strikeSide,
    this.doorPosition,
    this.strikePoint,
    this.notes,
  });

  factory ArchitecturalFeature.fromJson(Map<String, dynamic> json) {
    return ArchitecturalFeature(
      type: json['type'] as String? ?? 'feature',
      roomName: (json['room'] ?? json['room_name']) as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      wall: json['wall'] as String?,
      strikeSide: json['strike_side'] as String?,
      doorPosition: (json['door_position'] as List<dynamic>?)
          ?.map((e) => (e as num).toDouble())
          .toList(),
      strikePoint: (json['strike_point'] as List<dynamic>?)
          ?.map((e) => (e as num).toDouble())
          .toList(),
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'room_name': roomName,
        'confidence': confidence,
        if (wall != null) 'wall': wall,
        if (strikeSide != null) 'strike_side': strikeSide,
        if (doorPosition != null) 'door_position': doorPosition,
        if (strikePoint != null) 'strike_point': strikePoint,
        'notes': notes,
      };
}
