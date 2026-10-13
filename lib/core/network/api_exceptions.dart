class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic details;

  ApiException(this.message, {this.statusCode, this.details});

  /// Machine-readable reason the backend attached to the error (e.g. `geometry_corrected`), or null.
  String? get code {
    final d = details;
    if (d is Map && d['detail'] is Map) {
      final c = (d['detail'] as Map)['code'];
      return c is String ? c : null;
    }
    return null;
  }

  @override
  String toString() {
    if (statusCode != null) {
      return 'ApiException ($statusCode): $message';
    }
    return 'ApiException: $message';
  }
}
