import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/analysis_result.dart';

class AnalysisRepository {
  final ApiClient _client;

  AnalysisRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<Map<String, dynamic>> triggerAnalysis(String projectId) async {
    final data = await _client.post(ApiEndpoints.analyzeProject(projectId));
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
