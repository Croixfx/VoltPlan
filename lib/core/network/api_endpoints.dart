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

  /// The signed-in user's session token, sent as `Authorization: Bearer`. Empty when signed out, or when the server
  /// does not ask people to sign in (local development).
  static String userToken = '';

  /// Called when the server rejects the session token (expired, or the account is gone), so the app can sign out.
  static void Function()? onSessionExpired;

  /// Headers every request to the backend must carry, including plain image downloads.
  static Map<String, String> get authHeaders => {
        if (apiKey.isNotEmpty) 'X-API-Key': apiKey,
        if (userToken.isNotEmpty) 'Authorization': 'Bearer $userToken',
      };

  static String get authRegister => '$baseUrl/auth/register';
  static String get authLogin => '$baseUrl/auth/login';
  static String get authMe => '$baseUrl/auth/me';
  static String get adminOverview => '$baseUrl/admin/overview';
  static String get adminUsers => '$baseUrl/admin/users';
  static String adminProjects({String? query}) =>
      '$baseUrl/admin/projects${query == null || query.isEmpty ? '' : '?q=${Uri.encodeQueryComponent(query)}'}';
  static String adminDeactivate(String id) => '$baseUrl/admin/users/$id/deactivate';
  static String adminReactivate(String id) => '$baseUrl/admin/users/$id/reactivate';

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
  static String get projectPlanMatch => '$baseUrl/projects/plan-match';
  static String projectScaleSuggest(String id) => '$baseUrl/projects/$id/scale/suggest';
  static String projectReport(String id) => '$baseUrl/projects/$id/report.pdf';
  static String projectPlan(String id) => '$baseUrl/projects/$id/plan';
  static String projectPlanFile(String id) => '$baseUrl/projects/$id/plan/file';
  static String analyzeProject(String id) => '$baseUrl/projects/$id/analyze';
  static String analysis(String id) => '$baseUrl/projects/$id/analysis';
  static String analysisStatus(String id) => '$baseUrl/projects/$id/analysis/status';
  static String projectBoq(String id) => '$baseUrl/projects/$id/boq';
  static String projectCostEstimate(String id) => '$baseUrl/projects/$id/cost-estimate';
}
