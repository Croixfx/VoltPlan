import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

/// Voltage drop and maximum demand for the current design (GET /projects/{id}/calculations).
class CalculationsRepository {
  final ApiClient _client;

  CalculationsRepository({ApiClient? client}) : _client = client ?? ApiClient();

  /// [method], [ambientC] and [groupedCircuits] are the installation conditions used for the
  /// cable current-capacity check (defaults: method B2, 30 C, circuits not bunched).
  Future<Map<String, dynamic>> getCalculations(
    String projectId, {
    String method = 'B2',
    int ambientC = 30,
    int groupedCircuits = 1,
  }) async {
    final url = '${ApiEndpoints.projectCalculations(projectId)}'
        '?method=$method&ambient_c=$ambientC&grouped_circuits=$groupedCircuits';
    return await _client.get(url) as Map<String, dynamic>;
  }
}
