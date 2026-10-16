import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_exceptions.dart';
import 'package:voltplan/features/floor_plan/scale_calibration_screen.dart';
import 'package:voltplan/features/floor_plan/scale_suggestion.dart';
import 'package:voltplan/shared/state/app_state.dart';

void main() {
  test('a suggestion is read from the server answer', () {
    final s = ScaleSuggestion.fromJson({
      'point_a': {'x_ratio': 0.1, 'y_ratio': 0.2},
      'point_b': {'x_ratio': 0.6, 'y_ratio': 0.2},
      'real_distance_mm': 6000.0,
      'label_text': '6000',
      'confidence': 0.95,
      'note': 'overall width',
    });
    expect(s.pointA, const Offset(0.1, 0.2));
    expect(s.pointB, const Offset(0.6, 0.2));
    expect(s.realDistanceMm, 6000);
  });

  Future<AppState> open(WidgetTester tester, ScaleSuggester suggester) async {
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

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
        home: ScaleCalibrationScreen(
          state: state,
          project: project,
          returnToCaller: true,
          suggestScale: suggester,
        ),
      ),
    );
    await tester.pump();
    return state;
  }

  testWidgets('reading the scale fills the distance but does not save it', (tester) async {
    final state = await open(
      tester,
      (_) async => const ScaleSuggestion(
        pointA: Offset(0.1, 0.2),
        pointB: Offset(0.6, 0.2),
        realDistanceMm: 6000,
        labelText: '6000',
        confidence: 0.95,
        note: 'overall width',
      ),
    );

    await tester.tap(find.text('Read scale from drawing'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Read "6000" from the drawing'), findsOneWidget);
    expect(find.widgetWithText(TextField, '6000'), findsOneWidget);
    // nothing is calibrated until the user presses save
    expect(state.selectedProject?.isScaleCalibrated ?? false, isFalse);
    expect(state.projects.any((p) => p.isScaleCalibrated), isFalse);
  });

  testWidgets('when nothing can be read, the reason is shown and nothing is filled in', (tester) async {
    await open(
      tester,
      (_) async => throw ApiException('The drawing has no dimension lines.', statusCode: 422),
    );

    await tester.tap(find.text('Read scale from drawing'));
    await tester.pumpAndSettle();

    expect(find.text('The drawing has no dimension lines.'), findsOneWidget);
    expect(find.textContaining('Read "'), findsNothing);
  });
}
