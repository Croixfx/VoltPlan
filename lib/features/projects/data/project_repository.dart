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

  /// Calibrates plan scale from two points (image ratios 0-1) and the real
  /// distance between them in millimetres. Returns the resulting mm/pixel.
  Future<double> calibrateScale({
    required String projectId,
    required double ax,
    required double ay,
    required double bx,
    required double by,
    required double realDistanceMm,
  }) async {
    final data = await _client.put(
      ApiEndpoints.projectScale(projectId),
      body: {
        'point_a': {'x_ratio': ax, 'y_ratio': ay},
        'point_b': {'x_ratio': bx, 'y_ratio': by},
        'real_distance_mm': realDistanceMm,
      },
    );
    return (data['scale_mm_per_pixel'] as num).toDouble();
  }

  Future<void> deleteProject(String projectId) async {
    await _client.delete(ApiEndpoints.project(projectId));
  }
}
