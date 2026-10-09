import 'package:flutter/material.dart';

enum ElectricalPointType {
  light('Ceiling Light', Icons.lightbulb_outline),
  downlight('Downlight', Icons.highlight),
  socketDouble('Double Socket', Icons.power_outlined),
  socketSingle('Single Socket', Icons.power_outlined),
  switchPoint('Wall Switch', Icons.toggle_on_outlined),
  distributionBoard('Distribution Board', Icons.electrical_services),
  cookerPoint('Cooker Point', Icons.soup_kitchen_outlined),
  waterHeater('Water Heater Point', Icons.water_damage_outlined),
  tvPoint('TV Outlet', Icons.tv);

  final String label;
  final IconData icon;
  const ElectricalPointType(this.label, this.icon);

  static ElectricalPointType fromBackendType(String type) {
    switch (type.toLowerCase()) {
      case 'lighting':
        return ElectricalPointType.light;
      case 'downlight':
        return ElectricalPointType.downlight;
      case 'twin_socket':
      case 'socket_double':
        return ElectricalPointType.socketDouble;
      case 'single_socket':
      case 'socket_single':
        return ElectricalPointType.socketSingle;
      case 'switch_1way':
      case 'switch_2way':
      case 'switch':
        return ElectricalPointType.switchPoint;
      case 'distribution_board':
        return ElectricalPointType.distributionBoard;
      case 'cooker_point':
      case 'appliance_cooker':
        return ElectricalPointType.cookerPoint;
      case 'water_heater':
      case 'appliance_water_heater':
        return ElectricalPointType.waterHeater;
      case 'tv_point':
        return ElectricalPointType.tvPoint;
      default:
        return ElectricalPointType.socketSingle;
    }
  }
}

class ElectricalPoint {
  final String id;
  final String roomId;
  final String roomName;
  final ElectricalPointType type;
  final String label;
  final int quantity;
  final String cableSize;
  final String circuitId;
  final String protectionMcb;
  final String status; // 'Recommended', 'Calculated', 'Requires Engineer Review'
  final double xRatio; // 0.0 to 1.0 (relative to canvas width)
  final double yRatio; // 0.0 to 1.0 (relative to canvas height)
  final double powerRatingW;
  final String ruleReference;
  final String reviewNotes;

  const ElectricalPoint({
    required this.id,
    required this.roomId,
    required this.roomName,
    required this.type,
    required this.label,
    this.quantity = 1,
    required this.cableSize,
    required this.circuitId,
    required this.protectionMcb,
    this.status = 'Recommended',
    required this.xRatio,
    required this.yRatio,
    this.powerRatingW = 0.0,
    this.ruleReference = 'RS IEC 60364',
    this.reviewNotes = '',
  });

  factory ElectricalPoint.fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String? ?? 'single_socket';
    final pointType = ElectricalPointType.fromBackendType(typeStr);

    String normalizedStatus = 'Recommended';
    final rawStatus = (json['status'] as String? ?? 'RECOMMENDED').toUpperCase();
    if (rawStatus.contains('REVIEW')) {
      normalizedStatus = 'Requires Engineer Review';
    } else if (rawStatus == 'CALCULATED') {
      normalizedStatus = 'Calculated';
    } else {
      normalizedStatus = 'Recommended';
    }

    String label = pointType.label;
    if (typeStr == 'switch_2way') {
      label = '2-Way Switch';
    } else if (typeStr == 'switch_1way') {
      label = '1-Way Switch';
    } else if (typeStr == 'cooker_point') {
      label = '45A Cooker Outlet';
    } else if (typeStr == 'water_heater') {
      label = '20A Water Heater Isolator';
    } else if (typeStr == 'ac_point') {
      label = 'AC Isolator';
    }

    return ElectricalPoint(
      id: json['id'] as String? ?? '',
      roomId: json['room_id'] as String? ?? '',
      roomName: json['room_name'] as String? ?? 'General Area',
      type: pointType,
      label: label,
      quantity: (json['quantity'] as num?)?.toInt() ?? 1,
      cableSize: json['recommended_cable'] as String? ?? '3 x 2.5 mm² Cu/PVC',
      circuitId: json['circuit_id'] as String? ?? 'CKT-GEN',
      protectionMcb: json['recommended_protection'] as String? ?? '16A Type B MCB',
      status: normalizedStatus,
      xRatio: (json['x_ratio'] as num?)?.toDouble() ?? 0.5,
      yRatio: (json['y_ratio'] as num?)?.toDouble() ?? 0.5,
      powerRatingW: (json['power_rating_w'] as num?)?.toDouble() ?? 0.0,
      ruleReference: json['rule_reference'] as String? ?? 'RS IEC 60364',
      reviewNotes: json['review_notes'] as String? ?? '',
    );
  }

  ElectricalPoint copyWith({
    String? id,
    String? roomId,
    String? roomName,
    ElectricalPointType? type,
    String? label,
    int? quantity,
    String? cableSize,
    String? circuitId,
    String? protectionMcb,
    String? status,
    double? xRatio,
    double? yRatio,
    double? powerRatingW,
    String? ruleReference,
    String? reviewNotes,
  }) {
    return ElectricalPoint(
      id: id ?? this.id,
      roomId: roomId ?? this.roomId,
      roomName: roomName ?? this.roomName,
      type: type ?? this.type,
      label: label ?? this.label,
      quantity: quantity ?? this.quantity,
      cableSize: cableSize ?? this.cableSize,
      circuitId: circuitId ?? this.circuitId,
      protectionMcb: protectionMcb ?? this.protectionMcb,
      status: status ?? this.status,
      xRatio: xRatio ?? this.xRatio,
      yRatio: yRatio ?? this.yRatio,
      powerRatingW: powerRatingW ?? this.powerRatingW,
      ruleReference: ruleReference ?? this.ruleReference,
      reviewNotes: reviewNotes ?? this.reviewNotes,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'room_id': roomId,
        'room_name': roomName,
        'type': type.name,
        'label': label,
        'quantity': quantity,
        'cable_size': cableSize,
        'circuit_id': circuitId,
        'protection_mcb': protectionMcb,
        'status': status,
        'x_ratio': xRatio,
        'y_ratio': yRatio,
        'power_rating_w': powerRatingW,
        'rule_reference': ruleReference,
        'review_notes': reviewNotes,
      };
}
