import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'api_endpoints.dart';
import 'api_exceptions.dart';
import 'server_waker.dart';

class ApiClient {
  final http.Client _client;
  final ServerWaker _waker;

  /// [waker] defaults to the shared one, which wakes a sleeping free-tier server before the first request.
  ApiClient({http.Client? client, ServerWaker? waker})
      : _client = client ?? http.Client(),
        _waker = waker ?? ServerWaker.shared;

  Map<String, String> get _defaultHeaders => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...ApiEndpoints.authHeaders,
      };

  /// Plain reads are safe to repeat, so one that fails at the network level is retried once after the
  /// server has been woken. Writes are never repeated.
  Future<dynamic> get(String url, {Map<String, String>? headers}) =>
      _send('GET', url, headers: headers, timeout: const Duration(seconds: 30), retryAfterWake: true);

  /// Downloads a binary answer (a PDF report). Errors come back as the usual [ApiException].
  Future<Uint8List> getBytes(String url, {Duration timeout = const Duration(seconds: 90)}) async {
    final uri = Uri.parse(url);
    try {
      await _waker.ensureAwake(_client, uri);
      final request = http.Request('GET', uri)
        ..headers.addAll({'Accept': '*/*', ...ApiEndpoints.authHeaders});
      final response = await http.Response.fromStream(await _client.send(request).timeout(timeout));
      _waker.markAwake();
      if (response.statusCode >= 200 && response.statusCode < 300) return response.bodyBytes;
      _processResponse(response); // throws the error carried by the response
      throw ApiException('Request failed with status ${response.statusCode}');
    } catch (e) {
      _handleError(e);
      rethrow;
    }
  }

  /// 100 s: analysing a plan with a real AI model (including its own retries) can take longer than 45 s.
  Future<dynamic> post(String url, {dynamic body, Map<String, String>? headers}) =>
      _send('POST', url, body: body, headers: headers, timeout: const Duration(seconds: 100));

  Future<dynamic> put(String url, {dynamic body, Map<String, String>? headers}) =>
      _send('PUT', url, body: body, headers: headers, timeout: const Duration(seconds: 30));

  Future<dynamic> patch(String url, {dynamic body, Map<String, String>? headers}) =>
      _send('PATCH', url, body: body, headers: headers, timeout: const Duration(seconds: 30));

  Future<dynamic> delete(String url, {Map<String, String>? headers}) =>
      _send('DELETE', url, headers: headers, timeout: const Duration(seconds: 30));

  Future<dynamic> _send(
    String method,
    String url, {
    dynamic body,
    Map<String, String>? headers,
    required Duration timeout,
    bool retryAfterWake = false,
  }) async {
    final uri = Uri.parse(url);

    Future<http.Response> attempt() async {
      final request = http.Request(method, uri)..headers.addAll({..._defaultHeaders, ...(headers ?? {})});
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _client.send(request).timeout(timeout);
      return http.Response.fromStream(streamed);
    }

    try {
      await _waker.ensureAwake(_client, uri);
      try {
        return _finish(await attempt());
      } catch (e) {
        if (e is ApiException || !retryAfterWake || ServerWaker.isLocalHost(uri)) rethrow;
        // The server did not answer in time: it may have gone back to sleep. Wake it, then try once more.
        _waker.markStale();
        await _waker.ensureAwake(_client, uri);
        return _finish(await attempt());
      }
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
      final uri = Uri.parse(url);
      await _waker.ensureAwake(_client, uri);

      final request = http.MultipartRequest('POST', uri);
      request.headers.addAll(ApiEndpoints.authHeaders);

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
          await request.send().timeout(const Duration(seconds: 90));
      final response = await http.Response.fromStream(streamedResponse);

      return _finish(response);
    } catch (e) {
      _handleError(e);
    }
  }

  /// Any HTTP answer, even an error, proves the server is awake.
  dynamic _finish(http.Response response) {
    _waker.markAwake();
    return _processResponse(response);
  }

  dynamic _processResponse(http.Response response) {
    final statusCode = response.statusCode;

    // A rejected session token (not a wrong password, which arrives while signed out) means "sign in again".
    if (statusCode == 401 && ApiEndpoints.userToken.isNotEmpty) {
      ApiEndpoints.onSessionExpired?.call();
    }

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
        final detail = errorJson['detail'];
        // Structured errors (e.g. geometry checks) carry a human-readable `message`.
        errorMessage = detail is Map && detail['message'] != null
            ? detail['message'].toString()
            : detail.toString();
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
