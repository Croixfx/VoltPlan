import 'dart:convert';
import 'dart:typed_data';

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

  test('the report is downloaded as raw bytes with the API key', () async {
    ApiEndpoints.apiKey = 'secret-key';
    final pdf = Uint8List.fromList([0x25, 0x50, 0x44, 0x46, 0x2d, 0xff, 0x00, 0x80]);
    late http.Request seen;
    final client = ApiClient(
      waker: ServerWaker.disabled(),
      client: MockClient((req) async {
        seen = req;
        return http.Response.bytes(pdf, 200, headers: {'content-type': 'application/pdf'});
      }),
    );

    final bytes = await client.getBytes(ApiEndpoints.projectReport('p1'));

    expect(bytes, pdf, reason: 'binary data must not be decoded as text');
    expect(seen.url.path, endsWith('/projects/p1/report.pdf'));
    expect(seen.headers['X-API-Key'], 'secret-key');
  });

  test('a report that cannot be made explains why', () async {
    final client = ApiClient(
      waker: ServerWaker.disabled(),
      client: MockClient((req) async => http.Response(
            jsonEncode({'detail': 'Run the analysis before creating the report.'}),
            409,
          )),
    );

    await expectLater(
      client.getBytes(ApiEndpoints.projectReport('p1')),
      throwsA(isA<ApiException>()
          .having((e) => e.statusCode, 'status', 409)
          .having((e) => e.message, 'message', contains('Run the analysis'))),
    );
  });
}
