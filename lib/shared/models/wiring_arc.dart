class WiringArc {
  final String id;
  final String? circuitId;
  final String roomId;
  final String switchId;
  final String luminaireId;
  final List<double> startPoint;
  final List<double> controlPoint;
  final List<double> endPoint;
  final double lengthNorm;

  const WiringArc({
    required this.id,
    this.circuitId,
    required this.roomId,
    required this.switchId,
    required this.luminaireId,
    required this.startPoint,
    required this.controlPoint,
    required this.endPoint,
    required this.lengthNorm,
  });

  factory WiringArc.fromJson(Map<String, dynamic> json) {
    return WiringArc(
      id: json['id'] as String? ?? '',
      circuitId: json['circuit_id'] as String?,
      roomId: json['room_id'] as String? ?? '',
      switchId: json['switch_id'] as String? ?? '',
      luminaireId: json['luminaire_id'] as String? ?? '',
      startPoint: (json['start_point'] as List<dynamic>?)
              ?.map((e) => (e as num).toDouble())
              .toList() ??
          [0.0, 0.0],
      controlPoint: (json['control_point'] as List<dynamic>?)
              ?.map((e) => (e as num).toDouble())
              .toList() ??
          [0.0, 0.0],
      endPoint: (json['end_point'] as List<dynamic>?)
              ?.map((e) => (e as num).toDouble())
              .toList() ??
          [0.0, 0.0],
      lengthNorm: (json['length_norm'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (circuitId != null) 'circuit_id': circuitId,
        'room_id': roomId,
        'switch_id': switchId,
        'luminaire_id': luminaireId,
        'start_point': startPoint,
        'control_point': controlPoint,
        'end_point': endPoint,
        'length_norm': lengthNorm,
      };
}
