import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'api_exceptions.dart';

class ApiClient {
  final http.Client _client;

  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  Map<String, String> get _defaultHeaders => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Future<dynamic> get(String url, {Map<String, String>? headers}) async {
    try {
      final response = await _client
          .get(
            Uri.parse(url),
            headers: {..._defaultHeaders, ...(headers ?? {})},
          )
          .timeout(const Duration(seconds: 30));

      return _processResponse(response);
    } catch (e) {
      _handleError(e);
    }
  }

  Future<dynamic> post(
    String url, {
    dynamic body,
    Map<String, String>? headers,
  }) async {
    try {
      final response = await _client
          .post(
            Uri.parse(url),
            headers: {..._defaultHeaders, ...(headers ?? {})},
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(const Duration(seconds: 45));

      return _processResponse(response);
    } catch (e) {
      _handleError(e);
    }
  }

  Future<dynamic> patch(
    String url, {
    dynamic body,
    Map<String, String>? headers,
  }) async {
    try {
      final response = await _client
          .patch(
            Uri.parse(url),
            headers: {..._defaultHeaders, ...(headers ?? {})},
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(const Duration(seconds: 30));

      return _processResponse(response);
    } catch (e) {
      _handleError(e);
    }
  }

  Future<dynamic> delete(String url, {Map<String, String>? headers}) async {
    try {
      final response = await _client
          .delete(
            Uri.parse(url),
            headers: {..._defaultHeaders, ...(headers ?? {})},
          )
          .timeout(const Duration(seconds: 30));

      return _processResponse(response);
    } catch (e) {
      _handleError(e);
    }
  }

  Future<dynamic> uploadFile(
    String url,
    Uint8List fileBytes,
    String filename, {
    String fieldName = 'file',
    Map<String, String>? fields,
  }) async {
    try {
      final request = http.MultipartRequest('POST', Uri.parse(url));

      if (fields != null) {
        request.fields.addAll(fields);
      }

      final multipartFile = http.MultipartFile.fromBytes(
        fieldName,
        fileBytes,
        filename: filename,
      );
      request.files.add(multipartFile);

      final streamedResponse =
          await request.send().timeout(const Duration(seconds: 60));
      final response = await http.Response.fromStream(streamedResponse);

      return _processResponse(response);
    } catch (e) {
      _handleError(e);
    }
  }

  dynamic _processResponse(http.Response response) {
    final statusCode = response.statusCode;

    if (statusCode >= 200 && statusCode < 300) {
      if (response.body.isEmpty) return null;
      try {
        return jsonDecode(response.body);
      } catch (_) {
        return response.body;
      }
    }

    String errorMessage = 'Request failed with status $statusCode';
    dynamic details;

    try {
      final errorJson = jsonDecode(response.body);
      if (errorJson is Map<String, dynamic> && errorJson.containsKey('detail')) {
        errorMessage = errorJson['detail'].toString();
        details = errorJson;
      }
    } catch (_) {
      if (response.body.isNotEmpty) {
        errorMessage = response.body;
      }
    }

    throw ApiException(
      errorMessage,
      statusCode: statusCode,
      details: details,
    );
  }

  void _handleError(dynamic error) {
    if (error is ApiException) {
      throw error;
    }
    throw ApiException('Network connection error: ${error.toString()}');
  }

  void close() {
    _client.close();
  }
}
