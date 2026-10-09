class ApiEndpoints {
  // Default to localhost for desktop/local dev. Can be configured at runtime or via settings.
  static String baseUrl = 'http://127.0.0.1:8000/api';

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
