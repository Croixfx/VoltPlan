import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/boq_item.dart';
import '../../../shared/models/cost_estimate.dart';

class BoqRepository {
  final ApiClient _client;

  BoqRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<BoqItem>> getBoqItems(String projectId) async {
    final data = await _client.get(ApiEndpoints.projectBoq(projectId));
    if (data is Map<String, dynamic> && data['items'] is List) {
      return (data['items'] as List)
          .map((item) => BoqItem.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  Future<CostEstimate> getCostEstimate(String projectId) async {
    final data = await _client.get(ApiEndpoints.projectCostEstimate(projectId));
    return CostEstimate.fromJson(data as Map<String, dynamic>);
  }
}
