import 'dart:typed_data';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/project.dart';

class ProjectRepository {
  final ApiClient _client;

  ProjectRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<bool> checkHealth() async {
    try {
      final res = await _client.get(ApiEndpoints.health);
      return res != null && res['status'] == 'healthy';
    } catch (_) {
      return false;
    }
  }

  Future<List<Project>> getProjects({String? search, String? status}) async {
    String url = ApiEndpoints.projects;
    final queryParams = <String>[];
    if (search != null && search.isNotEmpty) {
      queryParams.add('search=${Uri.encodeComponent(search)}');
    }
    if (status != null && status.isNotEmpty) {
      queryParams.add('status=${Uri.encodeComponent(status)}');
    }
    if (queryParams.isNotEmpty) {
      url += '?${queryParams.join('&')}';
    }

    final data = await _client.get(url);
    if (data is List) {
      return data
          .map((item) => Project.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  Future<Project> getProject(String projectId) async {
    final data = await _client.get(ApiEndpoints.project(projectId));
    return Project.fromJson(data as Map<String, dynamic>);
  }

  Future<Project> createProject({
    required String name,
    required String client,
    required String buildingType,
    required String location,
    required String standard,
    String notes = '',
  }) async {
    final payload = {
      'name': name,
      'client': client,
      'building_type': buildingType,
      'location': location,
      'standard': standard,
      'notes': notes,
    };

    final data = await _client.post(ApiEndpoints.projects, body: payload);
    return Project.fromJson(data as Map<String, dynamic>);
  }

  Future<Project> uploadPlan({
    required String projectId,
    required Uint8List fileBytes,
    required String filename,
  }) async {
    final data = await _client.uploadFile(
      ApiEndpoints.projectPlan(projectId),
      fileBytes,
      filename,
    );
    return Project.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteProject(String projectId) async {
    await _client.delete(ApiEndpoints.project(projectId));
  }
}
