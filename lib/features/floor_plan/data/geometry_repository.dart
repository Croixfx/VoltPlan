import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/analysis_result.dart';
import '../../../shared/models/geometry.dart';

/// Room / door editing and equipment regeneration.
/// Every edit returns the backend's fresh [GeometryState] (including check results).
class GeometryRepository {
  final ApiClient _client;

  GeometryRepository({ApiClient? client}) : _client = client ?? ApiClient();

  GeometryState _state(dynamic data) =>
      GeometryState.fromJson(data as Map<String, dynamic>);

  Future<GeometryState> getGeometry(String projectId) async =>
      _state(await _client.get(ApiEndpoints.projectGeometry(projectId)));

  Future<GeometryState> addRoom(String projectId, String name, List<double> bounds) async =>
      _state(await _client.post(ApiEndpoints.projectRooms(projectId),
          body: {'name': name, 'bounds': bounds}));

  Future<GeometryState> updateRoom(String projectId, String roomId,
          {String? name, List<double>? bounds}) async =>
      _state(await _client.patch(ApiEndpoints.projectRoom(projectId, roomId), body: {
        'name': ?name,
        'bounds': ?bounds,
      }));

  Future<GeometryState> deleteRoom(String projectId, String roomId) async =>
      _state(await _client.delete(ApiEndpoints.projectRoom(projectId, roomId)));

  Future<GeometryState> addDoor(String projectId, String roomId, String wall,
          {double position = 0.5}) async =>
      _state(await _client.post(ApiEndpoints.projectDoors(projectId),
          body: {'room_id': roomId, 'wall': wall, 'position': position}));

  Future<GeometryState> updateDoor(String projectId, String doorId,
          {String? wall, double? position, String? swingDirection, String? strikeSide}) async =>
      _state(await _client.patch(ApiEndpoints.projectDoor(projectId, doorId), body: {
        'wall': ?wall,
        'position': ?position,
        'swing_direction': ?swingDirection,
        'strike_side': ?strikeSide,
      }));

  Future<GeometryState> deleteDoor(String projectId, String doorId) async =>
      _state(await _client.delete(ApiEndpoints.projectDoor(projectId, doorId)));

  Future<AnalysisResult> regenerate(String projectId) async => AnalysisResult.fromJson(
      await _client.post(ApiEndpoints.projectRegenerate(projectId)) as Map<String, dynamic>);
}
