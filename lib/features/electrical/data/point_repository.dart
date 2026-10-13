import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/analysis_result.dart';
import '../../../shared/models/equipment_option.dart';

/// Manual equipment editing against the backend. Every call returns the full,
/// regenerated analysis (points, circuits, BOQ, cost).
class PointRepository {
  final ApiClient _client;

  PointRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<EquipmentOption>> getEquipmentCatalog() async {
    final data = await _client.get(ApiEndpoints.equipment);
    if (data is! List) return const [];
    return data
        .map((e) => EquipmentOption.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AnalysisResult> addPoint({
    required String projectId,
    required String typeId,
    required double x,
    required double y,
    int quantity = 1,
  }) async {
    final data = await _client.post(
      ApiEndpoints.projectPoints(projectId),
      body: {'type': typeId, 'x_ratio': x, 'y_ratio': y, 'quantity': quantity},
    );
    return AnalysisResult.fromJson(data as Map<String, dynamic>);
  }

  Future<AnalysisResult> movePoint({
    required String projectId,
    required String pointId,
    required double x,
    required double y,
  }) async {
    final data = await _client.patch(
      ApiEndpoints.projectPoint(projectId, pointId),
      body: {'x_ratio': x, 'y_ratio': y},
    );
    return AnalysisResult.fromJson(data as Map<String, dynamic>);
  }

  Future<AnalysisResult> deletePoint({
    required String projectId,
    required String pointId,
  }) async {
    final data = await _client.delete(ApiEndpoints.projectPoint(projectId, pointId));
    return AnalysisResult.fromJson(data as Map<String, dynamic>);
  }
}
