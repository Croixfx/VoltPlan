import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/network/api_exceptions.dart';

enum AuthStatus {
  /// Asking the server whether, and as whom, the person is signed in.
  checking,

  /// The server could not be reached, so nothing is known yet.
  unreachable,

  signedOut,

  /// Signed in, or the server does not ask for sign-in (local development).
  signedIn,
}

/// Where the session token is kept between app launches.
abstract class SessionStore {
  Future<String?> read();
  Future<void> write(String? token);
}

class PrefsSessionStore implements SessionStore {
  static const _key = 'voltplan_session_token';

  @override
  Future<String?> read() async {
    try {
      return (await SharedPreferences.getInstance()).getString(_key);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> write(String? token) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (token == null) {
        await prefs.remove(_key);
      } else {
        await prefs.setString(_key, token);
      }
    } catch (_) {
      // Not being able to remember the sign-in only means signing in again next time.
    }
  }
}

/// Who is using the app. The backend keeps each person's projects apart; this holds the token that proves who
/// is asking.
class AuthState extends ChangeNotifier {
  /// The one in use by the running app (screens such as Settings reach it to offer "Sign out").
  static AuthState? instance;

  final ApiClient _client;
  final SessionStore _store;

  /// Called after a successful sign-in (or when no sign-in is needed) so the app can load the person's projects.
  final VoidCallback? onSignedIn;

  /// Called after signing out so the app can forget the previous person's data.
  final VoidCallback? onSignedOut;

  AuthState({ApiClient? client, SessionStore? store, this.onSignedIn, this.onSignedOut})
      : _client = client ?? ApiClient(),
        _store = store ?? PrefsSessionStore() {
    instance = this;
    ApiEndpoints.onSessionExpired = _sessionExpired;
  }

  AuthStatus _status = AuthStatus.checking;
  AuthStatus get status => _status;
  bool get isSignedIn => _status == AuthStatus.signedIn;

  String _email = '';
  String get email => _email;
  String _name = '';
  String get name => _name;

  /// False when the server lets anyone in (local development): there is nothing to sign out of.
  bool _loginRequired = true;
  bool get loginRequired => _loginRequired;

  String? _notice;

  /// A one-off message for the sign-in screen (for example "Your session ended").
  String? takeNotice() {
    final n = _notice;
    _notice = null;
    return n;
  }

  /// Works out where the person stands: no sign-in needed, signed in already, or signed out.
  Future<void> restore() async {
    _set(AuthStatus.checking);
    try {
      final health = await _client.get(ApiEndpoints.health);
      _loginRequired = health is Map && health['login_required'] == true;
    } catch (_) {
      _set(AuthStatus.unreachable);
      return;
    }

    if (!_loginRequired) {
      _set(AuthStatus.signedIn);
      onSignedIn?.call();
      return;
    }

    final token = await _store.read();
    if (token == null || token.isEmpty) {
      _set(AuthStatus.signedOut);
      return;
    }
    ApiEndpoints.userToken = token;
    try {
      final me = await _client.get(ApiEndpoints.authMe);
      _remember(me);
      _set(AuthStatus.signedIn);
      onSignedIn?.call();
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await _forget();
        _set(AuthStatus.signedOut);
      } else {
        _set(AuthStatus.unreachable);
      }
    } catch (_) {
      _set(AuthStatus.unreachable);
    }
  }

  /// Returns null on success, otherwise the reason to show.
  Future<String?> signIn(String email, String password) =>
      _enter(ApiEndpoints.authLogin, {'email': email.trim(), 'password': password});

  Future<String?> register(String email, String password, String name) => _enter(
        ApiEndpoints.authRegister,
        {'email': email.trim(), 'password': password, 'name': name.trim()},
      );

  Future<String?> _enter(String url, Map<String, dynamic> body) async {
    try {
      final data = await _client.post(url, body: body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      ApiEndpoints.userToken = token;
      await _store.write(token);
      _remember(data['user']);
      _set(AuthStatus.signedIn);
      onSignedIn?.call();
      return null;
    } on ApiException catch (e) {
      return e.message;
    } catch (e) {
      return 'Could not reach the server. Check your connection and try again.';
    }
  }

  Future<void> signOut() async {
    if (_status != AuthStatus.signedIn || !_loginRequired) return;
    await _forget();
    _set(AuthStatus.signedOut);
    onSignedOut?.call();
  }

  void _sessionExpired() {
    if (_status != AuthStatus.signedIn) return;
    _notice = 'Your session ended. Please sign in again.';
    signOut();
  }

  Future<void> _forget() async {
    ApiEndpoints.userToken = '';
    _email = '';
    _name = '';
    await _store.write(null);
  }

  void _remember(dynamic user) {
    if (user is Map) {
      _email = (user['email'] ?? '').toString();
      _name = (user['name'] ?? '').toString();
    }
  }

  void _set(AuthStatus status) {
    _status = status;
    notifyListeners();
  }
}
