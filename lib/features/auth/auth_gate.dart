import 'package:flutter/material.dart';
import '../../core/widgets/app_button.dart';
import 'auth_state.dart';
import 'login_screen.dart';

/// Shows [signedIn] only for a signed-in person; everyone else gets the sign-in screen.
class AuthGate extends StatelessWidget {
  final AuthState auth;
  final WidgetBuilder signedIn;

  const AuthGate({super.key, required this.auth, required this.signedIn});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: auth,
      builder: (context, _) {
        switch (auth.status) {
          case AuthStatus.signedIn:
            return signedIn(context);
          case AuthStatus.signedOut:
            return LoginScreen(auth: auth);
          case AuthStatus.unreachable:
            return Scaffold(
              body: SafeArea(
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.cloud_off, size: 48),
                        const SizedBox(height: 16),
                        const Text(
                          "Can't reach the server",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Check your connection. A sleeping server can take about a minute to wake up.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 20),
                        AppButton(label: 'Try again', onPressed: auth.restore),
                      ],
                    ),
                  ),
                ),
              ),
            );
          case AuthStatus.checking:
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
      },
    );
  }
}
