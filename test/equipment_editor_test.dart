import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/features/electrical/data/point_repository.dart';
import 'package:voltplan/features/electrical/electrical_plan_canvas_screen.dart';
import 'package:voltplan/features/floor_plan/widgets/plan_drawing_viewer.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/state/app_state.dart';

const _projectId = 'srv-1';

Map<String, dynamic> _point(
  String id,
  String type,
  double x,
  double y, {
  bool manual = false,
}) => {
  'id': id,
  'room_id': 'living',
  'room_name': 'Living Room',
  'type': type,
  'quantity': 1,
  'x_ratio': x,
  'y_ratio': y,
  'circuit_id': 'CKT-PWR-01',
  'recommended_cable': '3 x 2.5 mm² Cu/PVC',
  'recommended_protection': '20A Type B MCB',
  'status': 'RECOMMENDED',
  'is_manual': manual,
  'manual_origin': manual ? 'added' : null,
  'placement_status': manual ? 'manual' : 'proposed',
};

http.Response _analysis(List<Map<String, dynamic>> points) => http.Response(
  jsonEncode({
    'project_id': _projectId,
    'status': 'completed',
    'current_step': 'completed',
    'electrical_points': points,
    'rooms': [],
    'circuits': [],
    'boq_items': [],
    'warnings': [],
  }),
  200,
  headers: {'content-type': 'application/json'},
);

/// A tiny fake of the VoltPlan points API that records the requests it receives.
class _FakeBackend {
  final requests = <http.Request>[];
  String? rejectWith; // when set, mutations are rejected with this message
  var points = <Map<String, dynamic>>[
    _point('pt_001', 'twin_socket', 0.25, 0.25),
  ];

  Future<http.Response> handle(http.Request req) async {
    requests.add(req);
    final path = req.url.path;
    if (path.endsWith('/equipment')) {
      return http.Response(
        jsonEncode([
          {
            'type_id': 'twin_socket',
            'name': '13A Twin Socket Outlet',
            'category': 'socket',
          },
          {
            'type_id': 'smoke_detector',
            'name': 'Smoke Detector',
            'category': 'safety',
          },
        ]),
        200,
      );
    }
    if (!path.contains('/points')) return http.Response('{}', 404);

    if (rejectWith != null) {
      return http.Response(jsonEncode({'detail': rejectWith}), 422);
    }
    final body = req.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(req.body) as Map<String, dynamic>;
    switch (req.method) {
      case 'POST':
        points = [
          ...points,
          _point(
            'pt_002',
            body['type'] as String,
            body['x_ratio'] as double,
            body['y_ratio'] as double,
            manual: true,
          ),
        ];
      case 'PATCH':
        final id = path.split('/').last;
        points = [
          for (final p in points)
            if (p['id'] == id)
              _point(
                id,
                p['type'] as String,
                body['x_ratio'] as double,
                body['y_ratio'] as double,
                manual: true,
              )
            else
              p,
        ];
      case 'DELETE':
        final id = path.split('/').last;
        points = points.where((p) => p['id'] != id).toList();
    }
    return _analysis(points);
  }
}

Future<(AppState, _FakeBackend)> _pumpCanvas(WidgetTester tester) async {
  tester.view.physicalSize = const Size(900, 1400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final backend = _FakeBackend();
  final state = AppState(
    pointRepository: PointRepository(
      client: ApiClient(client: MockClient(backend.handle)),
    ),
  );
  final project = Project(
    id: _projectId,
    name: 'Villa',
    client: 'Client',
    buildingType: 'Residential',
    location: 'Kigali',
    standard: 'RS IEC 60364',
    status: ProjectStatus.completed,
    currentStage: ProjectStage.electricalDesign,
    updatedAt: DateTime(2026),
    createdAt: DateTime(2026),
  );
  state.selectProject(project);
  // Load the server's design into state (as after an analysis run).
  await state.deleteElectricalPoint(
    _projectId,
    'no-such-point',
  ); // no-op that syncs state
  backend.requests.clear();

  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light(),
      home: ElectricalPlanCanvasScreen(state: state, project: project),
    ),
  );
  await tester.pumpAndSettle();
  return (state, backend);
}

/// Drags like a finger would: many small moves (a single big jump is swallowed by the touch slop).
Future<void> _dragHandle(WidgetTester tester, Offset total) async {
  final gesture = await tester.startGesture(
    tester.getCenter(find.byIcon(Icons.open_with_rounded)),
  );
  const steps = 12;
  for (var i = 0; i < steps; i++) {
    await gesture.moveBy(total / steps.toDouble());
    await tester.pump(const Duration(milliseconds: 16));
  }
  await gesture.up();
  await tester.pumpAndSettle();
}

Offset _planPoint(WidgetTester tester, double xr, double yr) {
  final rect = tester.getRect(find.byType(PlanDrawingViewer));
  return rect.topLeft + Offset(rect.width * xr, rect.height * yr);
}

void main() {
  testWidgets(
    'edit mode: pick equipment from the catalog, place it, backend result is applied',
    (tester) async {
      final (state, backend) = await _pumpCanvas(tester);

      expect(find.byKey(const Key('equipment-edit-panel')), findsNothing);
      await tester.tap(find.byTooltip('Add / edit components'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('equipment-edit-panel')), findsOneWidget);
      expect(find.text('Add component from catalog'), findsOneWidget);
      // Catalog comes from the backend
      expect(
        find.byKey(const Key('equipment-chip-smoke_detector')),
        findsOneWidget,
      );

      await tester.tap(find.byKey(const Key('equipment-chip-twin_socket')));
      await tester.pump();
      expect(
        find.textContaining(
          'Tap inside a room to place: 13A Twin Socket Outlet',
        ),
        findsOneWidget,
      );

      await tester.tapAt(_planPoint(tester, 0.6, 0.5));
      await tester.pumpAndSettle();

      final post = backend.requests.singleWhere((r) => r.method == 'POST');
      expect(post.url.path, '/api/projects/$_projectId/points');
      final body = jsonDecode(post.body) as Map<String, dynamic>;
      expect(body['type'], 'twin_socket');
      expect(body['x_ratio'], closeTo(0.6, 0.02));
      expect(body['y_ratio'], closeTo(0.5, 0.02));

      final manual = state.electricalPoints.where((p) => p.isManual).toList();
      expect(manual, hasLength(1));
      expect(manual.single.manualOrigin, 'added');
      expect(find.textContaining('placed'), findsOneWidget);
    },
  );

  testWidgets('a backend rejection is shown to the user and nothing changes', (
    tester,
  ) async {
    final (state, backend) = await _pumpCanvas(tester);
    backend.rejectWith = "13A Twin Socket Outlet is not allowed in 'Bathroom'.";

    await tester.tap(find.byTooltip('Add / edit components'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('equipment-chip-twin_socket')));
    await tester.pump();
    await tester.tapAt(_planPoint(tester, 0.7, 0.7));
    await tester.pumpAndSettle();

    expect(find.textContaining("not allowed in 'Bathroom'"), findsOneWidget);
    expect(state.electricalPoints.where((p) => p.isManual), isEmpty);
    expect(state.electricalPoints, hasLength(1));
  });

  testWidgets('select a point, drag it to move it, backend marks it manual', (
    tester,
  ) async {
    final (state, backend) = await _pumpCanvas(tester);

    await tester.tap(find.byTooltip('Add / edit components'));
    await tester.pumpAndSettle();
    await tester.tapAt(_planPoint(tester, 0.25, 0.25));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('delete-point-button')), findsOneWidget);

    await _dragHandle(tester, const Offset(120, 0));

    final patch = backend.requests.singleWhere((r) => r.method == 'PATCH');
    expect(patch.url.path, '/api/projects/$_projectId/points/pt_001');
    final body = jsonDecode(patch.body) as Map<String, dynamic>;
    expect(body['x_ratio'] as double, greaterThan(0.3));
    expect(body['y_ratio'], closeTo(0.25, 0.02));

    final moved = state.electricalPoints.single;
    expect(moved.isManual, isTrue);
    expect(moved.xRatio, greaterThan(0.3));
  });

  testWidgets('a rejected move snaps the point back', (tester) async {
    final (state, backend) = await _pumpCanvas(tester);
    backend.rejectWith =
        'Position (0.900, 0.250) is outside every detected room.';

    await tester.tap(find.byTooltip('Add / edit components'));
    await tester.pumpAndSettle();
    await tester.tapAt(_planPoint(tester, 0.25, 0.25));
    await tester.pumpAndSettle();
    await _dragHandle(tester, const Offset(120, 0));

    expect(find.textContaining('outside every detected room'), findsOneWidget);
    final p = state.electricalPoints.single;
    expect(p.xRatio, closeTo(0.25, 0.001));
    expect(p.isManual, isFalse);
  });

  testWidgets(
    'delete asks for confirmation and removes the point via the backend',
    (tester) async {
      final (state, backend) = await _pumpCanvas(tester);

      await tester.tap(find.byTooltip('Add / edit components'));
      await tester.pumpAndSettle();
      await tester.tapAt(_planPoint(tester, 0.25, 0.25));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('delete-point-button')));
      await tester.pumpAndSettle();
      expect(find.text('Delete equipment?'), findsOneWidget);
      // Cancelling does nothing
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(backend.requests.where((r) => r.method == 'DELETE'), isEmpty);

      await tester.tap(find.byKey(const Key('delete-point-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(backend.requests.where((r) => r.method == 'DELETE'), hasLength(1));
      expect(state.electricalPoints, isEmpty);
    },
  );

  testWidgets('without edit mode, dragging and placing are not available', (
    tester,
  ) async {
    final (_, backend) = await _pumpCanvas(tester);
    await tester.tapAt(_planPoint(tester, 0.25, 0.25));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.open_with_rounded), findsNothing);
    expect(backend.requests, isEmpty);
  });

  testWidgets('local-only projects explain why editing is unavailable', (
    tester,
  ) async {
    final state = AppState();
    final project = state.createProject(
      name: 'Local only',
      client: 'Client',
      buildingType: 'Residential',
      location: 'Kigali',
      standard: 'RS IEC 60364',
    ); // id starts with proj-: not on the server
    final error = await state.addElectricalPoint(
      project.id,
      'twin_socket',
      0.5,
      0.5,
    );
    expect(error, contains('synced with the backend'));
  });
}
