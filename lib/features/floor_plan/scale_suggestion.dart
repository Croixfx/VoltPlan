import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';

/// A calibration the server read off the drawing. It is only a proposal: the user checks the two marked points
/// and the distance against the plan before saving.
class ScaleSuggestion {
  final Offset pointA; // image ratios 0-1
  final Offset pointB;
  final double realDistanceMm;
  final String labelText;
  final double confidence;
  final String note;

  const ScaleSuggestion({
    required this.pointA,
    required this.pointB,
    required this.realDistanceMm,
    required this.labelText,
    required this.confidence,
    required this.note,
  });

  factory ScaleSuggestion.fromJson(Map<String, dynamic> json) {
    Offset point(dynamic p) => Offset(
          (p['x_ratio'] as num).toDouble(),
          (p['y_ratio'] as num).toDouble(),
        );
    return ScaleSuggestion(
      pointA: point(json['point_a']),
      pointB: point(json['point_b']),
      realDistanceMm: (json['real_distance_mm'] as num).toDouble(),
      labelText: (json['label_text'] ?? '').toString(),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      note: (json['note'] ?? '').toString(),
    );
  }
}

typedef ScaleSuggester = Future<ScaleSuggestion> Function(String projectId);

/// Asks the server to read a dimension label off the plan. Throws an `ApiException` with the reason when
/// nothing usable was found.
Future<ScaleSuggestion> fetchScaleSuggestion(String projectId) async {
  final data = await ApiClient().post(ApiEndpoints.projectScaleSuggest(projectId));
  return ScaleSuggestion.fromJson(data as Map<String, dynamic>);
}
