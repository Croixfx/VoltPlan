import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/api_endpoints.dart';
import 'package:voltplan/core/network/api_exceptions.dart';
import 'package:voltplan/core/network/server_waker.dart';

void main() {
  final originalKey = ApiEndpoints.apiKey;
  tearDown(() => ApiEndpoints.apiKey = originalKey);

  ApiClient clientRecording(List<http.Request> seen, {int status = 200}) => ApiClient(
        waker: ServerWaker.disabled(),
        client: MockClient((req) async {
          seen.add(req);
          return http.Response(jsonEncode(status == 200 ? {'ok': true} : {'detail': 'Invalid or missing API key.'}), status);
        }),
      );

  test('no key configured: no auth header is sent (local development)', () async {
    ApiEndpoints.apiKey = '';
    expect(ApiEndpoints.authHeaders, isEmpty);

    final seen = <http.Request>[];
    await clientRecording(seen).get('http://x/api/projects');
    expect(seen.single.headers.containsKey('X-API-Key'), isFalse);
  });

  test('with a key, every kind of request carries X-API-Key', () async {
    ApiEndpoints.apiKey = 'secret-key';
    expect(ApiEndpoints.authHeaders, {'X-API-Key': 'secret-key'});

    final seen = <http.Request>[];
    final client = clientRecording(seen);
    await client.get('http://x/api/projects');
    await client.post('http://x/api/projects', body: {'a': 1});
    await client.put('http://x/api/projects/1/scale', body: {'a': 1});
    await client.patch('http://x/api/projects/1', body: {'a': 1});
    await client.delete('http://x/api/projects/1');

    expect(seen.map((r) => r.method), ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']);
    for (final r in seen) {
      expect(r.headers['X-API-Key'], 'secret-key', reason: '${r.method} ${r.url}');
      expect(r.headers['Accept'], 'application/json');
    }
  });

  test('a rejected key surfaces the backend message', () async {
    ApiEndpoints.apiKey = 'wrong';
    final seen = <http.Request>[];
    await expectLater(
      clientRecording(seen, status: 401).get('http://x/api/projects'),
      throwsA(isA<ApiException>()
          .having((e) => e.statusCode, 'status', 401)
          .having((e) => e.message, 'message', 'Invalid or missing API key.')),
    );
  });

  test('the key is not part of any URL (it would end up in logs)', () {
    ApiEndpoints.apiKey = 'secret-key';
    expect(ApiEndpoints.projectPlanFile('p1'), isNot(contains('secret-key')));
    expect(ApiEndpoints.projects, isNot(contains('secret-key')));
  });
}
