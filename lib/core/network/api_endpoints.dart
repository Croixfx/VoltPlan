class ApiEndpoints {
  // Defaults to localhost for desktop/local dev. Release builds point at a deployed backend with
  //   flutter build apk --release --dart-define=API_BASE_URL=https://your-host/api
  static String baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000/api',
  );

  /// Shared key for a deployed backend, sent as `X-API-Key` (build with --dart-define=API_KEY=...).
  /// Empty for local development, where the backend does not require one.
  static String apiKey = const String.fromEnvironment('API_KEY');

  /// Headers every request to the backend must carry, including plain image downloads.
  static Map<String, String> get authHeaders =>
      apiKey.isEmpty ? const {} : {'X-API-Key': apiKey};

  static String get equipment => '$baseUrl/equipment';
  static String projectPoints(String id) => '$baseUrl/projects/$id/points';
  static String projectPoint(String id, String pointId) =>
      '$baseUrl/projects/$id/points/$pointId';
  static String projectGeometry(String id) => '$baseUrl/projects/$id/geometry';
  static String projectRooms(String id) => '$baseUrl/projects/$id/rooms';
  static String projectRoom(String id, String roomId) =>
      '$baseUrl/projects/$id/rooms/$roomId';
  static String projectDoors(String id) => '$baseUrl/projects/$id/doors';
  static String projectDoor(String id, String doorId) =>
      '$baseUrl/projects/$id/doors/$doorId';
  static String projectRegenerate(String id) =>
      '$baseUrl/projects/$id/regenerate';
  static String projectCalculations(String id) =>
      '$baseUrl/projects/$id/calculations';
  static String projectScale(String id) => '$baseUrl/projects/$id/scale';
  static String get health => '$baseUrl/health';
  static String get projects => '$baseUrl/projects';
  static String project(String id) => '$baseUrl/projects/$id';
  static String projectPlan(String id) => '$baseUrl/projects/$id/plan';
  static String projectPlanFile(String id) => '$baseUrl/projects/$id/plan/file';
  static String analyzeProject(String id) => '$baseUrl/projects/$id/analyze';
  static String analysis(String id) => '$baseUrl/projects/$id/analysis';
  static String analysisStatus(String id) => '$baseUrl/projects/$id/analysis/status';
  static String projectBoq(String id) => '$baseUrl/projects/$id/boq';
  static String projectCostEstimate(String id) => '$baseUrl/projects/$id/cost-estimate';
}
