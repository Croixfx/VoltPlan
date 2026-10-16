import 'package:flutter/material.dart';
import 'app/app.dart';
import 'features/auth/auth_state.dart';
import 'shared/state/app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final appState = AppState();
  final auth = AuthState(
    onSignedIn: () {
      final name = AuthState.instance?.name ?? '';
      if (name.isNotEmpty) appState.updateProfile(name: name);
      appState.checkBackendConnection();
    },
    onSignedOut: appState.clearForSignOut,
  )..restore();
  runApp(VoltPlanApp(state: appState, auth: auth));
}
