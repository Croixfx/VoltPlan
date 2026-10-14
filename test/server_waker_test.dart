import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/api_endpoints.dart';
import 'package:voltplan/core/network/api_exceptions.dart';
import 'package:voltplan/core/network/server_waker.dart';
import 'package:voltplan/core/widgets/server_wake_banner.dart';

const _remote = 'https://remote.test/api';

/// A server that is asleep for the first [asleepFor] health checks, then answers.
class _Server {
  _Server({this.asleepFor = 0, this.healthDelay = Duration.zero});

  final int asleepFor;
  final Duration healthDelay;
  final requests = <http.Request>[];
  int _healthSeen = 0;

  /// What the (non-health) endpoints do; replaced per test.
  Future<http.Response> Function(http.Request) onApi = (_) async => http.Response(jsonEncode({'ok': true}), 200);

  List<String> get paths => requests.map((r) => r.url.path).toList();
  int get healthCalls => requests.where((r) => r.url.path.endsWith('/health')).length;
  int get apiCalls => requests.where((r) => !r.url.path.endsWith('/health')).length;

  Future<http.Response> handle(http.Request req) async {
    requests.add(req);
    if (req.url.path.endsWith('/health')) {
      if (healthDelay > Duration.zero) await Future<void>.delayed(healthDelay);
      return ++_healthSeen <= asleepFor
          ? http.Response('Service waking up', 503)
          : http.Response(jsonEncode({'status': 'ok'}), 200);
    }
    return onApi(req);
  }
}

class _Fixture {
  _Fixture({int asleepFor = 0, Duration healthDelay = Duration.zero, Duration budget = const Duration(seconds: 150)}) {
    server = _Server(asleepFor: asleepFor, healthDelay: healthDelay);
    waker = ServerWaker(
      budget: budget,
      pause: const Duration(seconds: 3),
      showNoticeAfter: const Duration(milliseconds: 1),
      now: () => clock,
      delay: (d) async => clock = clock.add(d), // time passes without anyone waiting
    );
    client = ApiClient(client: MockClient(server.handle), waker: waker);
  }

  late final _Server server;
  late final ServerWaker waker;
  late final ApiClient client;
  DateTime clock = DateTime(2026, 10, 14, 9);
}

void main() {
  final originalBase = ApiEndpoints.baseUrl;
  setUp(() => ApiEndpoints.baseUrl = _remote);
  tearDown(() => ApiEndpoints.baseUrl = originalBase);

  group('waking a sleeping server', () {
    test('the first request waits for the server to wake, then goes through', () async {
      final f = _Fixture(asleepFor: 2, healthDelay: const Duration(milliseconds: 10));
      final shown = <bool>[];
      f.waker.isWaking.addListener(() => shown.add(f.waker.isWaking.value));

      final result = await f.client.get('$_remote/projects');

      expect(result, {'ok': true});
      expect(f.server.paths, ['/api/health', '/api/health', '/api/health', '/api/projects']); // 2 asleep, 1 awake, then the call
      expect(shown, [true, false]); // the notice appeared while waiting and went away
      expect(f.waker.isWaking.value, isFalse);
      expect(f.clock.difference(DateTime(2026, 10, 14, 9)), const Duration(seconds: 6)); // two pauses of 3 s
    });

    test('no notice flashes up when the server answers straight away', () async {
      final f = _Fixture();
      final shown = <bool>[];
      f.waker.isWaking.addListener(() => shown.add(f.waker.isWaking.value));
      await f.client.get('$_remote/projects');
      expect(shown, isEmpty);
    });

    test('while the server was recently heard from nothing is probed; after 10 idle minutes it is', () async {
      final f = _Fixture();
      await f.client.get('$_remote/projects');
      await f.client.get('$_remote/projects');
      expect(f.server.healthCalls, 1); // one probe for the first call, none for the second

      f.clock = f.clock.add(const Duration(minutes: 9));
      await f.client.get('$_remote/projects');
      expect(f.server.healthCalls, 1); // 9 idle minutes: still within the window (and this call refreshes it)

      f.clock = f.clock.add(const Duration(minutes: 11)); // 11 idle minutes since the last answer: it has gone to sleep
      await f.client.get('$_remote/projects');
      expect(f.server.healthCalls, 2);
    });

    test('a local development server is never probed', () async {
      ApiEndpoints.baseUrl = 'http://127.0.0.1:8000/api';
      final f = _Fixture();
      await f.client.get('http://127.0.0.1:8000/api/projects');
      await f.client.get('http://localhost:8000/api/projects');
      expect(f.server.healthCalls, 0);
      expect(f.server.apiCalls, 2);
    });

    test('a disabled waker never probes', () async {
      final server = _Server();
      final client = ApiClient(client: MockClient(server.handle), waker: ServerWaker.disabled());
      await client.get('$_remote/projects');
      expect(server.healthCalls, 0);
    });

    test('two requests at once share a single wake-up', () async {
      final f = _Fixture(asleepFor: 1, healthDelay: const Duration(milliseconds: 5));
      final results = await Future.wait([f.client.get('$_remote/a'), f.client.get('$_remote/b')]);
      expect(results, [{'ok': true}, {'ok': true}]);
      expect(f.server.healthCalls, 2); // one failed + one succeeded for BOTH requests, not four
      expect(f.server.apiCalls, 2);
    });

    test('after the budget the real request is sent anyway and reports its own error', () async {
      final f = _Fixture(asleepFor: 1000, budget: const Duration(seconds: 10));
      f.server.onApi = (_) async => throw http.ClientException('connection refused');

      await expectLater(
        f.client.post('$_remote/projects', body: {'name': 'x'}),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', contains('Network connection error'))),
      );
      expect(f.server.healthCalls, 5); // t = 0, 3, 6, 9, 12 s, then it stopped waiting
      expect(f.server.apiCalls, 1);
      expect(f.waker.isWaking.value, isFalse);
    });
  });

  group('requests that fail after the server was believed awake', () {
    test('a read that fails is retried once after waking the server', () async {
      final f = _Fixture();
      await f.client.get('$_remote/warmup'); // the server is now known to be awake
      f.server.requests.clear();

      var failures = 1;
      f.server.onApi = (_) async {
        if (failures-- > 0) throw http.ClientException('connection reset'); // it went back to sleep
        return http.Response(jsonEncode({'ok': 'after wake'}), 200);
      };

      expect(await f.client.get('$_remote/projects'), {'ok': 'after wake'});
      expect(f.server.paths, ['/api/projects', '/api/health', '/api/projects']); // try, wake, try again
    });

    test('a read that fails twice reports the network error', () async {
      final f = _Fixture();
      f.server.onApi = (_) async => throw http.ClientException('no route');
      await expectLater(
        f.client.get('$_remote/projects'),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', contains('Network connection error'))),
      );
      expect(f.server.apiCalls, 2); // original + exactly one retry
    });

    test('writes are never repeated, so nothing can be created twice', () async {
      final f = _Fixture();
      await f.client.get('$_remote/warmup');
      f.server.requests.clear();
      f.server.onApi = (_) async => throw http.ClientException('connection reset');

      for (final send in <Future<dynamic> Function()>[
        () => f.client.post('$_remote/projects', body: {'name': 'x'}),
        () => f.client.put('$_remote/projects/1/scale', body: {'a': 1}),
        () => f.client.patch('$_remote/projects/1', body: {'a': 1}),
        () => f.client.delete('$_remote/projects/1'),
      ]) {
        await expectLater(send(), throwsA(isA<ApiException>()));
      }
      expect(f.server.apiCalls, 4); // one attempt each
      expect(f.server.healthCalls, 0);
    });

    test('an error answer proves the server is awake: no probing, no retry', () async {
      final f = _Fixture();
      await f.client.get('$_remote/warmup');
      f.server.requests.clear();
      f.server.onApi = (_) async => http.Response(jsonEncode({'detail': 'Invalid or missing API key.'}), 401);

      await expectLater(
        f.client.get('$_remote/projects'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 401)),
      );
      expect(f.server.paths, ['/api/projects']);
    });

    test('uploads wait for a sleeping server too', () async {
      final f = _Fixture(asleepFor: 1);
      // MultipartRequest sends through its own client, which a fake cannot intercept; what matters here is that the
      // wake-up probe ran against the injected client before the upload was attempted.
      try {
        await f.client.uploadFile('$_remote/projects/1/plan', Uint8List.fromList([1, 2, 3]), 'plan.png');
      } catch (_) {}
      expect(f.server.healthCalls, 2);
    });
  });

  group('the on-screen notice', () {
    testWidgets('appears while waking, disappears afterwards, and never blocks taps', (tester) async {
      final waker = ServerWaker.disabled();
      var taps = 0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ServerWakeBanner(
            waker: waker,
            child: Align(
              alignment: Alignment.bottomCenter,
              child: ElevatedButton(onPressed: () => taps++, child: const Text('Under the notice')),
            ),
          ),
        ),
      ));
      expect(find.byKey(const Key('server-wake-banner')), findsNothing);

      waker.isWaking.value = true;
      await tester.pump();
      expect(find.byKey(const Key('server-wake-banner')), findsOneWidget);
      expect(find.textContaining('Waking the server up'), findsOneWidget);

      await tester.tap(find.text('Under the notice'));
      expect(taps, 1); // touches pass through the notice

      waker.isWaking.value = false;
      await tester.pump();
      expect(find.byKey(const Key('server-wake-banner')), findsNothing);
    });
  });
}
