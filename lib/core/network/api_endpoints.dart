class ApiEndpoints {
  // Default to localhost for desktop/local dev. Can be configured at runtime or via settings.
  static String baseUrl = 'http://127.0.0.1:8000/api';

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
