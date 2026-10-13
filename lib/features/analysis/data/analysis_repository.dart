import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/analysis_result.dart';

class AnalysisRepository {
  final ApiClient _client;

  AnalysisRepository({ApiClient? client}) : _client = client ?? ApiClient();

  /// [discardCorrections] re-reads the plan with AI even though the user corrected rooms / doors,
  /// which throws those corrections away. Without it the backend refuses (409, code geometry_corrected).
  Future<Map<String, dynamic>> triggerAnalysis(String projectId, {bool discardCorrections = false}) async {
    final url = discardCorrections
        ? '${ApiEndpoints.analyzeProject(projectId)}?reset_geometry=true'
        : ApiEndpoints.analyzeProject(projectId);
    final data = await _client.post(url);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getAnalysisStatus(String projectId) async {
    final data = await _client.get(ApiEndpoints.analysisStatus(projectId));
    return data as Map<String, dynamic>;
  }

  Future<AnalysisResult> getAnalysisResult(String projectId) async {
    final data = await _client.get(ApiEndpoints.analysis(projectId));
    return AnalysisResult.fromJson(data as Map<String, dynamic>);
  }
}
