class AppConstants {
  AppConstants._();

  static const String appName = 'VoltPlan';
  static const String appTagline = 'AI-Assisted Electrical Planning & Estimation';
  static const String defaultCurrency = 'RWF';
  static const String defaultStandard = 'RS IEC 60364';

  /// Only standards the server has design rules for. The server refuses the others, so none are offered here;
  /// add one back when its rules exist (backend/app/engineering_rules/registry.py).
  static const List<String> electricalStandards = [
    'RS IEC 60364 (Rwanda Standards / IEC)',
  ];

  static const List<String> buildingTypes = [
    'Residential',
    'Commercial',
    'Office',
    'Apartment',
    'Mixed-Use',
  ];

  static const List<String> supportedUploadFormats = ['PDF', 'PNG', 'JPG'];
  static const int maxUploadSizeBytes = 25 * 1024 * 1024; // 25 MB

  static const String disclaimerText =
      'Advisory recommendations for preliminary planning only. Not a substitute for calculations by a certified professional electrical engineer.';
}
