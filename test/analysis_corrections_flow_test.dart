import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/user_messages.dart';
import 'package:voltplan/features/analysis/ai_analysis_screen.dart';
import 'package:voltplan/features/analysis/data/analysis_repository.dart';
import 'package:voltplan/features/floor_plan/data/geometry_repository.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/state/app_state.dart';

const _pid = 'srv-1';
const _correctedMessage =
    'You have corrected rooms or doors in this project. Rebuild the design from your corrections, '
    'or read the plan again with AI (this discards your corrections).';

/// A stand-in for the backend that behaves like the real one around corrected rooms:
/// re-reading the plan is refused while corrections exist, "regenerate" rebuilds from them.
class _FakeBackend {
  final requests = <http.Request>[];
  bool corrected = false;
  bool regenerateBlocked = false;
  bool legacyRefusal = false; // an older server: plain-text 409 that mentions the API parameter
  http.Response? analyzeFailure;
  String roomName = 'Bedroom 1'; // what the AI read

  Iterable<http.Request> get analyzeCalls =>
      requests.where((r) => r.method == 'POST' && r.url.path.endsWith('/analyze'));
  Iterable<http.Request> get regenerateCalls =>
      requests.where((r) => r.method == 'POST' && r.url.path.endsWith('/regenerate'));

  Map<String, dynamic> _point(int i) => {
        'id': 'pt_$i', 'room_id': 'room_1', 'room_name': roomName, 'type': 'twin_socket',
        'x_ratio': 0.3, 'y_ratio': 0.3, 'circuit_id': 'CKT-PWR-01',
        'recommended_cable': '3 x 2.5 mm² Cu/PVC', 'recommended_protection': '20A Type B MCB',
      };

  http.Response _analysis({required int points}) => http.Response(
        jsonEncode({
          'project_id': _pid, 'status': 'completed', 'current_step': 'completed',
          'rooms': [
            {'id': 'room_1', 'name': roomName, 'confidence': 1.0, 'bounds': [0.1, 0.1, 0.5, 0.5]}
          ],
          'electrical_points': [for (var i = 1; i <= points; i++) _point(i)],
          'circuits': [], 'boq_items': [], 'warnings': [],
          'geometry_reviewed': corrected, 'geometry_needs_regeneration': false,
        }),
        200,
      );

  http.Response _geometry() => http.Response(
        jsonEncode({
          'project_id': _pid,
          'rooms': [
            {'id': 'room_1', 'name': roomName, 'confidence': 1.0, 'bounds': [0.1, 0.1, 0.5, 0.5], 'is_manual': corrected}
          ],
          'features': [], 'issues': [], 'can_generate': true,
          'reviewed': corrected, 'needs_regeneration': corrected,
        }),
        200,
      );

  Future<http.Response> handle(http.Request req) async {
    requests.add(req);
    final path = req.url.path;

    if (req.method == 'PATCH' && path.endsWith('/rooms/room_1')) {
      roomName = (jsonDecode(req.body) as Map)['name'] as String;
      corrected = true;
      return _geometry();
    }
    if (req.method == 'POST' && path.endsWith('/analyze')) {
      if (analyzeFailure != null) return analyzeFailure!;
      final discarding = req.url.queryParameters['reset_geometry'] == 'true';
      if (corrected && !discarding) {
        return legacyRefusal
            ? http.Response(
                jsonEncode({
                  'detail': 'This project has manually corrected rooms / doors. Use \'Regenerate\' to rebuild the '
                      'equipment from your corrections, or pass reset_geometry=true to discard the corrections.'
                }),
                409)
            : http.Response(jsonEncode({'detail': {'code': 'geometry_corrected', 'message': _correctedMessage}}), 409);
      }
      if (discarding) {
        corrected = false;
        roomName = 'Bedroom 1';
      }
      return http.Response('{}', 200);
    }
    if (req.method == 'GET' && path.endsWith('/analysis')) return _analysis(points: 29); // the AI's own reading
    if (req.method == 'POST' && path.endsWith('/regenerate')) {
      if (regenerateBlocked) {
        return http.Response(
            jsonEncode({
              'detail': {
                'message': "Geometry check failed with 1 error(s): Rooms 'Kitchen' and 'Living Room' overlap by 25% of "
                    'the smaller room. Fix the rooms / doors and generate again.',
                'issues': []
              }
            }),
            422);
      }
      return _analysis(points: 12); // rebuilt from the corrected rooms
    }
    return http.Response('{}', 404);
  }
}

Future<(AppState, _FakeBackend, Project)> _pumpScreen(
  WidgetTester tester, {
  required _FakeBackend backend,
  bool correctRoomsFirst = false,
}) async {
  tester.view.physicalSize = const Size(900, 2600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final client = ApiClient(client: MockClient(backend.handle));
  final state = AppState(
    analysisRepository: AnalysisRepository(client: client),
    geometryRepository: GeometryRepository(client: client),
  );
  final project = Project(
    id: _pid, name: 'Villa', client: 'C', buildingType: 'Residential', location: 'Kigali',
    standard: 'RS IEC 60364', status: ProjectStatus.inProgress, currentStage: ProjectStage.aiAnalysis,
    updatedAt: DateTime(2026), createdAt: DateTime(2026),
  );
  state.selectProject(project);

  if (correctRoomsFirst) {
    // Exactly what the Rooms & Doors editor does when the user renames a room.
    final geometry = await state.geometryRepository.updateRoom(_pid, 'room_1', name: 'Kitchen');
    state.noteGeometry(geometry);
    backend.requests.clear();
  }

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: AiAnalysisScreen(state: state, project: project),
  ));
  await tester.pumpAndSettle();
  return (state, backend, project);
}

void expectNoApiTermsOnScreen() {
  for (final term in ['reset_geometry', '/api', 'X-API-Key', '=true', '409', '422']) {
    expect(find.textContaining(term), findsNothing, reason: 'the screen must not show "$term"');
  }
}

void main() {
  group('after the user corrected rooms', () {
    testWidgets('correct rooms -> regenerate -> the design appears', (tester) async {
      final backend = _FakeBackend();
      final (state, _, _) = await _pumpScreen(tester, backend: backend, correctRoomsFirst: true);

      // The screen tried to read the plan again, which would discard the corrections, and was refused.
      expect(backend.analyzeCalls, hasLength(1));
      expect(find.text('Analysis Error'), findsOneWidget);
      expect(find.text(_correctedMessage), findsOneWidget);
      expect(state.hasGeometryCorrections, isTrue);

      // The two explicit choices replace the bare retry that would repeat the refused call.
      expect(find.byKey(const Key('regenerate-design-button')), findsOneWidget);
      expect(find.byKey(const Key('reread-plan-button')), findsOneWidget);
      expect(find.text('Regenerate design'), findsOneWidget);
      expect(find.text('Re-read plan with AI'), findsOneWidget);
      expect(find.text('Retry Analysis'), findsNothing);
      expect(find.text('Re-analyze'), findsNothing);
      expectNoApiTermsOnScreen();

      // After a failure the pipeline card must not keep claiming that it is processing.
      expect(find.text('AI Vision Pipeline in Progress'), findsNothing);
      expect(find.text('Processing'), findsNothing);
      expect(find.text('Analysis Stopped'), findsOneWidget);

      await tester.tap(find.byKey(const Key('regenerate-design-button')));
      await tester.pumpAndSettle();

      // It rebuilt from the corrections: no second AI reading, the design is on screen.
      expect(backend.regenerateCalls, hasLength(1));
      expect(backend.analyzeCalls, hasLength(1));
      expect(find.text('Analysis Error'), findsNothing);
      expect(find.text('Analysis Complete'), findsOneWidget);
      expect(find.text('Analysis Pipeline Completed'), findsOneWidget);
      expect(find.text('Preliminary Extraction Summary'), findsOneWidget);
      expect(state.isAnalysisFinished, isTrue);
      expect(state.electricalPoints, hasLength(12)); // the rebuilt design, not the AI's original 29
      expect(state.rooms.single.name, 'Kitchen'); // from the corrected room
      expect(state.hasGeometryCorrections, isTrue);
      expect(find.byKey(const Key('regenerate-design-button')), findsNothing);
    });

    testWidgets('re-reading the plan asks first; keeping the corrections sends nothing', (tester) async {
      final backend = _FakeBackend();
      final (state, _, _) = await _pumpScreen(tester, backend: backend, correctRoomsFirst: true);

      await tester.tap(find.byKey(const Key('reread-plan-button')));
      await tester.pumpAndSettle();
      expect(find.text('Re-read the plan with AI?'), findsOneWidget);
      expect(find.textContaining('The rooms and doors you corrected will be lost'), findsOneWidget);
      expectNoApiTermsOnScreen();

      await tester.tap(find.byKey(const Key('cancel-reread-button')));
      await tester.pumpAndSettle();
      expect(backend.analyzeCalls, hasLength(1)); // nothing was sent
      expect(state.hasGeometryCorrections, isTrue);
      expect(find.byKey(const Key('regenerate-design-button')), findsOneWidget);
    });

    testWidgets('confirming re-reads the plan and discards the corrections', (tester) async {
      final backend = _FakeBackend();
      final (state, _, _) = await _pumpScreen(tester, backend: backend, correctRoomsFirst: true);

      await tester.tap(find.byKey(const Key('reread-plan-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-reread-button')));
      await tester.pumpAndSettle();

      expect(backend.analyzeCalls, hasLength(2));
      expect(backend.analyzeCalls.last.url.queryParameters['reset_geometry'], 'true'); // sent, but never shown
      expect(find.text('Analysis Complete'), findsOneWidget);
      expect(state.hasGeometryCorrections, isFalse);
      expect(state.electricalPoints, hasLength(29)); // the AI's fresh reading
      expect(state.rooms.single.name, 'Bedroom 1');
    });

    testWidgets('if the checks still fail, the reason is shown and both choices stay available', (tester) async {
      final backend = _FakeBackend()..regenerateBlocked = true;
      final (state, _, _) = await _pumpScreen(tester, backend: backend, correctRoomsFirst: true);

      await tester.tap(find.byKey(const Key('regenerate-design-button')));
      await tester.pumpAndSettle();

      expect(backend.regenerateCalls, hasLength(1));
      expect(find.textContaining("Rooms 'Kitchen' and 'Living Room' overlap"), findsOneWidget);
      expect(find.byKey(const Key('regenerate-design-button')), findsOneWidget);
      expect(find.byKey(const Key('reread-plan-button')), findsOneWidget);
      expect(find.byKey(const Key('fix-rooms-doors-button')), findsOneWidget); // a way to fix what the checks found
      expect(find.text('AI Vision Pipeline in Progress'), findsNothing);
      expect(find.text('Analysis Stopped'), findsOneWidget);
      expect(state.isAnalysisFinished, isFalse);
      expectNoApiTermsOnScreen();
    });

    testWidgets('an older server that names the API parameter is shown in plain words', (tester) async {
      final backend = _FakeBackend()..legacyRefusal = true;
      final (state, _, _) = await _pumpScreen(tester, backend: backend, correctRoomsFirst: true);

      expect(find.text(_correctedMessage), findsOneWidget);
      expectNoApiTermsOnScreen();
      expect(state.hasGeometryCorrections, isTrue);
      expect(find.byKey(const Key('regenerate-design-button')), findsOneWidget);
      expect(find.text('Retry Analysis'), findsNothing);
    });
  });

  group('without corrections', () {
    testWidgets('a failed analysis keeps a single Retry, hides the stale card, and retry works', (tester) async {
      final backend = _FakeBackend()
        ..analyzeFailure = http.Response(
            jsonEncode({'detail': 'AI vision provider error: Gemini rejected the request (HTTP 503: high demand).'}), 502);
      final (state, _, _) = await _pumpScreen(tester, backend: backend);

      expect(find.textContaining('high demand'), findsOneWidget);
      expect(find.byKey(const Key('retry-analysis-button')), findsOneWidget);
      expect(find.byKey(const Key('regenerate-design-button')), findsNothing);
      expect(find.byKey(const Key('reread-plan-button')), findsNothing);
      expect(find.text('AI Vision Pipeline in Progress'), findsNothing);
      expect(find.text('Processing'), findsNothing);
      expect(state.hasGeometryCorrections, isFalse);

      backend.analyzeFailure = null; // Google recovers
      await tester.tap(find.byKey(const Key('retry-analysis-button')));
      await tester.pumpAndSettle();

      expect(backend.analyzeCalls, hasLength(2));
      expect(backend.analyzeCalls.last.url.queryParameters, isEmpty); // a plain retry never discards anything
      expect(find.text('Analysis Complete'), findsOneWidget);
      expect(find.text('Analysis Error'), findsNothing);
    });
  });

  group('messages for people', () {
    test('API terms are removed or replaced', () {
      expect(friendlyApiMessage('Use it, or pass reset_geometry=true to discard'), contains('corrected rooms or doors'));
      expect(friendlyApiMessage('Gemini rejected the request (HTTP 404: model not found). Check /api/ai/check.'),
          'Gemini rejected the request (HTTP 404: model not found).');
      expect(friendlyApiMessage('Plain message stays as it is.'), 'Plain message stays as it is.');
    });
  });
}
