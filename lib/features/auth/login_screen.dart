import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/widgets/app_button.dart';
import 'auth_state.dart';

/// Sign in or create an account. Each person only ever sees their own projects.
class LoginScreen extends StatefulWidget {
  final AuthState auth;

  const LoginScreen({super.key, required this.auth});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  bool _creating = false;
  bool _busy = false;
  bool _hidePassword = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _error = widget.auth.takeNotice();
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      _email.text.trim().contains('@') && _password.text.isNotEmpty && !_busy;

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final error = _creating
        ? await widget.auth.register(_email.text, _password.text, _name.text)
        : await widget.auth.signIn(_email.text, _password.text);
    if (!mounted) return;
    // On success the gate above replaces this screen, so only a failure needs handling here.
    setState(() {
      _busy = false;
      _error = error;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final secondary =
        isDark ? AppColors.textSecondaryDark : AppColors.textSecondaryLight;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppColors.primaryBlue,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.bolt, color: Colors.white),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        AppConstants.appName,
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Text(
                    _creating ? 'Create your account' : 'Sign in',
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _creating
                        ? 'Your projects are private to your account.'
                        : 'Sign in to see your projects.',
                    style: TextStyle(fontSize: 14, color: secondary),
                  ),
                  const SizedBox(height: 24),
                  if (_creating) ...[
                    TextField(
                      controller: _name,
                      enabled: !_busy,
                      textCapitalization: TextCapitalization.words,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Your name (optional)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: _email,
                    enabled: !_busy,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    textInputAction: TextInputAction.next,
                    onChanged: (_) => setState(() => _error = null),
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    enabled: !_busy,
                    obscureText: _hidePassword,
                    autofillHints: [
                      _creating ? AutofillHints.newPassword : AutofillHints.password,
                    ],
                    textInputAction: TextInputAction.done,
                    onChanged: (_) => setState(() => _error = null),
                    onSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      helperText: _creating ? 'At least 8 characters' : null,
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        tooltip: _hidePassword ? 'Show password' : 'Hide password',
                        icon: Icon(_hidePassword ? Icons.visibility : Icons.visibility_off),
                        onPressed: () => setState(() => _hidePassword = !_hidePassword),
                      ),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                  ],
                  const SizedBox(height: 20),
                  AppButton(
                    label: _creating ? 'Create account' : 'Sign in',
                    isLoading: _busy,
                    isFullWidth: true,
                    onPressed: _canSubmit ? _submit : null,
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => setState(() {
                              _creating = !_creating;
                              _error = null;
                            }),
                    child: Text(
                      _creating
                          ? 'I already have an account'
                          : 'New here? Create an account',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
