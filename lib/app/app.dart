import 'package:flutter/material.dart';
import '../core/constants/app_constants.dart';
import '../core/widgets/server_wake_banner.dart';
import '../features/auth/auth_gate.dart';
import '../features/auth/auth_state.dart';
import '../features/navigation/main_scaffold.dart';
import '../shared/state/app_state.dart';
import 'theme.dart';

class VoltPlanApp extends StatelessWidget {
  final AppState state;

  /// Who is signed in. Null shows the app straight away (used by tests of single screens).
  final AuthState? auth;

  const VoltPlanApp({super.key, required this.state, this.auth});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: state,
      builder: (context, _) {
        return MaterialApp(
          title: AppConstants.appName,
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light(),
          darkTheme: AppTheme.dark(),
          themeMode: state.themeMode,
          themeAnimationDuration: const Duration(milliseconds: 350),
          themeAnimationCurve: Curves.easeInOutCubic,
          builder: (context, child) => ServerWakeBanner(child: child ?? const SizedBox.shrink()),
          home: auth == null
              ? MainScaffold(state: state)
              : AuthGate(
                  auth: auth!,
                  signedIn: (_) => MainScaffold(state: state),
                ),
        );
      },
    );
  }
}
