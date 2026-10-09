class Circuit {
  final String id;
  final String code; // e.g. LGT-01, CKT-PWR-01
  final String name; // e.g. Lighting, General Sockets
  final String description;
  final int pointsCount;
  final String cableSize; // e.g. 1.5 mm², 2.5 mm²
  final String protectionMcb; // e.g. 10A MCB, 20A MCB
  final String status; // 'Recommended', 'Calculated', 'Review'
  final double loadKw;
  final String phase; // L1, L2, L3
  final String rcd;
  final String circuitType;
  final String reviewNotes;

  const Circuit({
    required this.id,
    required this.code,
    required this.name,
    required this.description,
    required this.pointsCount,
    required this.cableSize,
    required this.protectionMcb,
    required this.status,
    required this.loadKw,
    this.phase = 'L1',
    this.rcd = '30mA Type A RCD',
    this.circuitType = 'power',
    this.reviewNotes = '',
  });

  bool get isDedicated =>
      circuitType.toLowerCase().contains('dedicated') ||
      name.toLowerCase().contains('cooker') ||
      name.toLowerCase().contains('water heater') ||
      name.toLowerCase().contains('heater') ||
      name.toLowerCase().contains('ac') ||
      name.toLowerCase().contains('special');

  double get connectedLoadKw => loadKw;

  factory Circuit.fromJson(Map<String, dynamic> json) {
    final id = json['id'] as String? ?? 'CKT-01';
    final loadW = (json['connected_load_w'] as num?)?.toDouble() ?? 0.0;
    final loadKw = double.parse((loadW / 1000.0).toStringAsFixed(2));

    String status = 'Calculated';
    final rawStatus = (json['status'] as String? ?? 'CALCULATED').toUpperCase();
    if (rawStatus.contains('REVIEW')) {
      status = 'Review';
    } else {
      status = 'Recommended';
    }

    return Circuit(
      id: id,
      code: id.replaceFirst('CKT-', ''),
      name: json['name'] as String? ?? 'Circuit',
      description: json['description'] as String? ?? '',
      pointsCount: (json['points_count'] as num?)?.toInt() ?? 0,
      cableSize: json['cable'] as String? ?? '3 x 2.5 mm² Cu/PVC',
      protectionMcb: json['protection'] as String? ?? '20A Type B MCB',
      status: status,
      loadKw: loadKw,
      phase: json['phase'] as String? ?? 'L1',
      rcd: json['rcd'] as String? ?? '30mA Type A RCD',
      circuitType: json['circuit_type'] as String? ?? 'power',
      reviewNotes: json['review_notes'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'code': code,
        'name': name,
        'description': description,
        'points_count': pointsCount,
        'cable': cableSize,
        'protection': protectionMcb,
        'status': status,
        'connected_load_w': loadKw * 1000.0,
        'phase': phase,
        'rcd': rcd,
        'circuit_type': circuitType,
        'review_notes': reviewNotes,
      };
}
