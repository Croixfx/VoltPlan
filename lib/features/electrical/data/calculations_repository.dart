import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

/// Voltage drop and maximum demand for the current design (GET /projects/{id}/calculations).
class CalculationsRepository {
  final ApiClient _client;

  CalculationsRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<Map<String, dynamic>> getCalculations(String projectId) async =>
      await _client.get(ApiEndpoints.projectCalculations(projectId)) as Map<String, dynamic>;
}
