import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'api_endpoints.dart';

/// Free hosting puts the backend to sleep after about 15 minutes without traffic, and waking it takes up to
/// a minute, which is longer than a normal request is allowed to wait. Instead of failing the user's first
/// tap of the day, the app first polls `/health` until the server answers, shows a "waking up" notice while
/// that takes noticeable time, and only then sends the real request.
///
/// Probing first (rather than retrying the request) means a "create project" that timed out is never sent
/// twice. Local development servers never sleep, so they are not probed.
class ServerWaker {
  ServerWaker({
    this.awakeFor = const Duration(minutes: 10),
    this.probeTimeout = const Duration(seconds: 15),
    this.budget = const Duration(seconds: 150),
    this.pause = const Duration(seconds: 3),
    this.showNoticeAfter = const Duration(seconds: 2),
    DateTime Function()? now,
    Future<void> Function(Duration)? delay,
  })  : _enabled = true,
        _now = now ?? DateTime.now,
        _delay = delay ?? ((d) => Future<void>.delayed(d));

  /// A waker that never probes (for tests and for servers known to be always on).
  ServerWaker.disabled()
      : awakeFor = Duration.zero,
        probeTimeout = Duration.zero,
        budget = Duration.zero,
        pause = Duration.zero,
        showNoticeAfter = Duration.zero,
        _enabled = false,
        _now = DateTime.now,
        _delay = ((d) => Future<void>.delayed(d));

  /// The instance every [ApiClient] uses unless told otherwise.
  static final ServerWaker shared = ServerWaker();

  /// A request this soon after the last answer is assumed to reach a server that is awake.
  final Duration awakeFor;
  final Duration probeTimeout;

  /// How long to keep polling before giving up and letting the real request report its own error.
  final Duration budget;
  final Duration pause;
  final Duration showNoticeAfter;
  final bool _enabled;
  final DateTime Function() _now;
  final Future<void> Function(Duration) _delay;

  /// True while the app is waiting for a sleeping server (drives the on-screen notice).
  final ValueNotifier<bool> isWaking = ValueNotifier<bool>(false);

  DateTime? _lastAnswer;
  Future<void>? _inFlight;

  static bool isLocalHost(Uri uri) => const {'localhost', '127.0.0.1', '::1', '10.0.2.2'}.contains(uri.host);

  bool _needsProbe(Uri request) {
    if (!_enabled || isLocalHost(request)) return false;
    final last = _lastAnswer;
    return last == null || _now().difference(last) > awakeFor;
  }

  /// The server answered something (any HTTP status): it is awake.
  void markAwake() => _lastAnswer = _now();

  /// A request failed at the network level: do not trust the "awake" assumption any more.
  void markStale() => _lastAnswer = null;

  /// Completes once the server answers `/health`, or after [budget] (the real request then reports the error).
  /// Concurrent callers share one probe.
  Future<void> ensureAwake(http.Client client, Uri request) {
    if (!_needsProbe(request)) return Future<void>.value();
    return _inFlight ??= _probe(client).whenComplete(() => _inFlight = null);
  }

  Future<void> _probe(http.Client client) async {
    final health = Uri.parse(ApiEndpoints.health);
    final deadline = _now().add(budget);
    final notice = Timer(showNoticeAfter, () => isWaking.value = true);
    try {
      while (true) {
        try {
          final response = await client.get(health, headers: ApiEndpoints.authHeaders).timeout(probeTimeout);
          if (response.statusCode == 200) {
            markAwake();
            return;
          }
        } catch (_) {
          // still asleep (or no connection yet): keep trying until the budget is used up
        }
        if (!_now().isBefore(deadline)) return;
        await _delay(pause);
      }
    } finally {
      notice.cancel();
      isWaking.value = false;
    }
  }
}
