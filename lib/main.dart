import 'package:flutter/material.dart';
import 'app/app.dart';
import 'shared/state/app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final appState = AppState();
  runApp(VoltPlanApp(state: appState));
}
