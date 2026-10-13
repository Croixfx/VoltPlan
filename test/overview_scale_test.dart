import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/features/floor_plan/scale_calibration_screen.dart';
import 'package:voltplan/features/projects/project_overview_screen.dart';
import 'package:voltplan/shared/state/app_state.dart';

void main() {
  testWidgets('overview shows scale status and opens calibration', (tester) async {
    final state = AppState();
    final project = state.createProject(
      name: 'Villa',
      client: 'Client',
      buildingType: 'Residential',
      location: 'Kigali',
      standard: 'RS IEC 60364',
      floorPlanName: 'plan.png',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: ProjectOverviewScreen(state: state, project: project),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Scale not calibrated • positions are estimates'), findsOneWidget);

    await tester.ensureVisible(find.text('Calibrate Scale'));
    await tester.tap(find.text('Calibrate Scale'));
    await tester.pumpAndSettle();

    expect(find.byType(ScaleCalibrationScreen), findsOneWidget);
    // Opened from an existing project: cancel returns instead of starting analysis
    expect(find.text('Cancel'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(find.byType(ProjectOverviewScreen), findsOneWidget);
  });

  testWidgets('overview reflects a calibrated scale', (tester) async {
    final state = AppState();
    final project = state.createProject(
      name: 'Villa',
      client: 'Client',
      buildingType: 'Residential',
      location: 'Kigali',
      standard: 'RS IEC 60364',
      floorPlanName: 'plan.png',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: ProjectOverviewScreen(state: state, project: project),
      ),
    );
    await tester.pumpAndSettle();

    final idx = state.projects.indexWhere((p) => p.id == project.id);
    state.projects[idx] = state.projects[idx].copyWith(scaleMmPerPixel: 20.0);
    state.notifyListeners();
    await tester.pumpAndSettle();

    expect(find.text('Scale calibrated • 1 px = 20.0 mm'), findsOneWidget);
    expect(find.text('Recalibrate'), findsOneWidget);
  });
}
