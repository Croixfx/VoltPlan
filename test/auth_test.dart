import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/api_endpoints.dart';
import 'package:voltplan/core/network/server_waker.dart';
import 'package:voltplan/features/auth/auth_gate.dart';
import 'package:voltplan/features/auth/auth_state.dart';

class MemoryStore implements SessionStore {
  String? token;
  MemoryStore([this.token]);
  @override
  Future<String?> read() async => token;
  @override
  Future<void> write(String? t) async => token = t;
}

/// A tiny stand-in server: [loginRequired], the one valid token, and the account behind it.
class FakeServer {
  bool loginRequired = true;
  bool reachable = true;
  String validToken = 'good-token';
  final seenAuth = <String?>[];

  http.Response answer(http.Request req) {
    if (!reachable) throw http.ClientException('offline');
    seenAuth.add(req.headers['Authorization']);
    final path = req.url.path;
    http.Response json(Object body, [int status = 200]) => http.Response(jsonEncode(body), status);
    if (path.endsWith('/health')) return json({'status': 'ok', 'login_required': loginRequired});
    if (path.endsWith('/auth/me')) {
      return req.headers['Authorization'] == 'Bearer $validToken'
          ? json({'id': 'u1', 'email': 'ana@example.com', 'name': 'Ana'})
          : json({'detail': 'Please sign in again.'}, 401);
    }
    if (path.endsWith('/auth/login') || path.endsWith('/auth/register')) {
      final body = jsonDecode(req.body) as Map;
      if (body['password'] == 'wrong') return json({'detail': 'Wrong email or password.'}, 401);
      return json({
        'access_token': validToken,
        'token_type': 'bearer',
        'user': {'id': 'u1', 'email': body['email'], 'name': body['name'] ?? ''},
      });
    }
    return json({'detail': 'Please sign in again.'}, 401);
  }
}

void main() {
  late FakeServer server;
  late MemoryStore store;
  late int signedInCalls;
  late int signedOutCalls;

  AuthState makeAuth() => AuthState(
        client: ApiClient(waker: ServerWaker.disabled(), client: MockClient((r) async => server.answer(r))),
        store: store,
        onSignedIn: () => signedInCalls++,
        onSignedOut: () => signedOutCalls++,
      );

  setUp(() {
    server = FakeServer();
    store = MemoryStore();
    signedInCalls = 0;
    signedOutCalls = 0;
    ApiEndpoints.userToken = '';
  });
  tearDown(() {
    ApiEndpoints.userToken = '';
    ApiEndpoints.onSessionExpired = null;
  });

  test('no saved session: the person must sign in', () async {
    final auth = makeAuth();
    await auth.restore();
    expect(auth.status, AuthStatus.signedOut);
    expect(signedInCalls, 0);
  });

  test('a saved session is checked with the server and restored', () async {
    store.token = 'good-token';
    final auth = makeAuth();
    await auth.restore();
    expect(auth.status, AuthStatus.signedIn);
    expect(auth.email, 'ana@example.com');
    expect(ApiEndpoints.userToken, 'good-token');
    expect(signedInCalls, 1);
  });

  test('a saved session the server no longer accepts is dropped', () async {
    store.token = 'stale-token';
    final auth = makeAuth();
    await auth.restore();
    expect(auth.status, AuthStatus.signedOut);
    expect(store.token, isNull);
    expect(ApiEndpoints.userToken, isEmpty);
  });

  test('a server that does not ask for sign-in lets the app straight in', () async {
    server.loginRequired = false;
    final auth = makeAuth();
    await auth.restore();
    expect(auth.status, AuthStatus.signedIn);
    expect(auth.loginRequired, isFalse);
    expect(signedInCalls, 1);
    await auth.signOut(); // nothing to sign out of
    expect(auth.status, AuthStatus.signedIn);
  });

  test('an unreachable server is reported, not mistaken for a signed-out person', () async {
    server.reachable = false;
    store.token = 'good-token';
    final auth = makeAuth();
    await auth.restore();
    expect(auth.status, AuthStatus.unreachable);
    expect(store.token, 'good-token', reason: 'the saved sign-in must survive a bad connection');
  });

  test('signing in stores the token and sends it with every request', () async {
    final auth = makeAuth();
    await auth.restore();
    expect(await auth.signIn('Ana@Example.com ', 'right'), isNull);
    expect(auth.status, AuthStatus.signedIn);
    expect(store.token, 'good-token');
    expect(ApiEndpoints.authHeaders['Authorization'], 'Bearer good-token');
  });

  test('a wrong password shows the server message and stays signed out', () async {
    final auth = makeAuth();
    await auth.restore();
    expect(await auth.signIn('ana@example.com', 'wrong'), 'Wrong email or password.');
    expect(auth.status, AuthStatus.signedOut);
    expect(store.token, isNull);
  });

  test('signing out forgets the token and tells the app to clear its data', () async {
    final auth = makeAuth();
    await auth.restore();
    await auth.signIn('ana@example.com', 'right');
    await auth.signOut();
    expect(auth.status, AuthStatus.signedOut);
    expect(store.token, isNull);
    expect(ApiEndpoints.userToken, isEmpty);
    expect(signedOutCalls, 1);
  });

  test('a rejected token signs the person out with an explanation', () async {
    final auth = makeAuth();
    await auth.restore();
    await auth.signIn('ana@example.com', 'right');

    server.validToken = 'rotated'; // the server stops accepting the old token
    final client = ApiClient(waker: ServerWaker.disabled(), client: MockClient((r) async => server.answer(r)));
    await expectLater(client.get('http://x/api/projects'), throwsA(anything));
    await Future<void>.delayed(Duration.zero);

    expect(auth.status, AuthStatus.signedOut);
    expect(signedOutCalls, 1);
    expect(auth.takeNotice(), contains('sign in again'));
  });

  testWidgets('the gate shows the sign-in screen, then the app once signed in', (tester) async {
    final auth = makeAuth();
    await auth.restore();

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: AuthGate(auth: auth, signedIn: (_) => const Scaffold(body: Text('PROJECTS'))),
    ));
    expect(find.text('PROJECTS'), findsNothing);
    expect(find.text('Sign in'), findsWidgets);

    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'ana@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'right');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in').first);
    await tester.pumpAndSettle();

    expect(find.text('PROJECTS'), findsOneWidget);
  });

  testWidgets('the gate says so when the server cannot be reached', (tester) async {
    server.reachable = false;
    final auth = makeAuth();
    await auth.restore();
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: AuthGate(auth: auth, signedIn: (_) => const Text('PROJECTS')),
    ));
    expect(find.text("Can't reach the server"), findsOneWidget);
    expect(find.text('PROJECTS'), findsNothing);
  });
}
