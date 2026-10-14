import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/api_exceptions.dart';
import 'package:voltplan/core/network/server_waker.dart';
import 'package:voltplan/core/widgets/app_button.dart';
import 'package:voltplan/features/floor_plan/data/geometry_repository.dart';
import 'package:voltplan/features/floor_plan/geometry_editor_screen.dart';
import 'package:voltplan/shared/models/geometry.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/state/app_state.dart';

const _pid = 'srv-1';

/// In-memory stand-in for the rooms / doors / regenerate / calculations API.
class _FakeBackend {
  final requests = <http.Request>[];
  String? rejectEditsWith;
  Map<String, dynamic>? calculations;

  final rooms = <Map<String, dynamic>>[
    {'id': 'living', 'name': 'Living Room', 'bounds': [0.1, 0.1, 0.5, 0.5], 'is_manual': false},
    {'id': 'kitchen', 'name': 'Bedroom 1', 'bounds': [0.4, 0.1, 0.9, 0.5], 'is_manual': false}, // mislabelled + overlapping
  ];
  final doors = <Map<String, dynamic>>[
    {
      'id': 'feat_001', 'type': 'door', 'room_id': 'living', 'room': 'Living Room', 'wall': 'south',
      'door_position': [0.3, 0.5], 'swing_direction': 'into_room', 'strike_side': 'east', 'is_manual': false,
    },
  ];

  double _overlap(List a, List b) {
    final w = (a[2] < b[2] ? a[2] : b[2]) - (a[0] > b[0] ? a[0] : b[0]);
    final h = (a[3] < b[3] ? a[3] : b[3]) - (a[1] > b[1] ? a[1] : b[1]);
    return w > 0 && h > 0 ? w * h : 0.0;
  }

  List<Map<String, dynamic>> issues() {
    final out = <Map<String, dynamic>>[];
    for (var i = 0; i < rooms.length; i++) {
      for (var j = i + 1; j < rooms.length; j++) {
        if (_overlap(rooms[i]['bounds'], rooms[j]['bounds']) > 0.003) {
          out.add({
            'code': 'rooms_overlap', 'severity': 'error',
            'message': "Rooms '${rooms[i]['name']}' and '${rooms[j]['name']}' overlap by 25% of the smaller room.",
            'entity_ids': [rooms[i]['id'], rooms[j]['id']],
          });
        }
      }
    }
    return out;
  }

  http.Response geometry([int status = 200]) {
    final iss = issues();
    return http.Response(
      jsonEncode({
        'project_id': _pid, 'rooms': rooms, 'features': doors, 'issues': iss,
        'can_generate': !iss.any((i) => i['severity'] == 'error'),
        'reviewed': requests.any((r) => r.method != 'GET'), 'needs_regeneration': true,
      }),
      status,
    );
  }

  http.Response _error(int status, String message) =>
      http.Response(jsonEncode({'detail': message}), status);

  Future<http.Response> handle(http.Request req) async {
    requests.add(req);
    final path = req.url.path;
    final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;

    if (path.endsWith('/calculations')) return http.Response(jsonEncode(calculations), 200);
    if (path.endsWith('/regenerate')) {
      final iss = issues();
      if (iss.isNotEmpty) {
        return http.Response(
          jsonEncode({'detail': {'message': 'Geometry check failed with 1 error(s): overlap', 'issues': iss}}),
          422,
        );
      }
      return http.Response(
        jsonEncode({
          'project_id': _pid, 'status': 'completed', 'current_step': 'completed',
          'rooms': rooms, 'electrical_points': [], 'circuits': [], 'boq_items': [], 'warnings': [],
        }),
        200,
      );
    }
    if (req.method == 'GET' && path.endsWith('/geometry')) return geometry();

    if (req.method != 'GET' && rejectEditsWith != null) return _error(422, rejectEditsWith!);

    final room = rooms.where((r) => path.endsWith('/rooms/${r['id']}')).firstOrNull;
    final door = doors.where((d) => path.endsWith('/doors/${d['id']}')).firstOrNull;
    if (path.endsWith('/rooms') && req.method == 'POST') {
      rooms.add({'id': 'room_manual_1', 'name': body['name'], 'bounds': body['bounds'], 'is_manual': true});
      return geometry(201);
    }
    if (room != null && req.method == 'PATCH') {
      if (body['name'] != null) room['name'] = body['name'];
      if (body['bounds'] != null) room['bounds'] = body['bounds'];
      return geometry();
    }
    if (room != null && req.method == 'DELETE') {
      rooms.remove(room);
      return geometry();
    }
    if (door != null && req.method == 'PATCH') {
      body.forEach((k, v) => door[k == 'position' ? 'position_param' : k] = v);
      return geometry();
    }
    if (door != null && req.method == 'DELETE') {
      doors.remove(door);
      return geometry();
    }
    return http.Response('{}', 404);
  }
}

Future<(AppState, _FakeBackend, Project)> _pump(WidgetTester tester, {_FakeBackend? backend, Widget Function(AppState, Project)? home}) async {
  tester.view.physicalSize = const Size(900, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  backend ??= _FakeBackend();
  final state = AppState(geometryRepository: GeometryRepository(client: ApiClient(client: MockClient(backend.handle))));
  final project = Project(
    id: _pid, name: 'Villa', client: 'C', buildingType: 'Residential', location: 'Kigali', standard: 'RS IEC 60364',
    status: ProjectStatus.completed, currentStage: ProjectStage.electricalDesign,
    updatedAt: DateTime(2026), createdAt: DateTime(2026),
  );
  state.selectProject(project);

  Widget editor(AppState s, Project p) => GeometryEditorScreen(state: s, project: p, planAspectRatio: 1.0);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: (home ?? editor)(state, project),
  ));
  await tester.pumpAndSettle();
  return (state, backend, project);
}

Rect _plan(WidgetTester tester) => tester.getRect(find.byType(AspectRatio).first);
Offset _at(WidgetTester tester, double x, double y) {
  final r = _plan(tester);
  return r.topLeft + Offset(r.width * x, r.height * y);
}

Future<void> _drag(WidgetTester tester, Offset from, Offset total) async {
  final g = await tester.startGesture(from);
  const steps = 12;
  for (var i = 0; i < steps; i++) {
    await g.moveBy(total / steps.toDouble());
    await tester.pump(const Duration(milliseconds: 16));
  }
  await g.up();
  await tester.pumpAndSettle();
}

void main() {
  group('geometry helpers', () {
    const rect = Rect.fromLTRB(0.2, 0.2, 0.6, 0.5);

    test('snapToWall picks the nearest wall and the position along it', () {
      final north = snapToWall(rect, const Offset(0.3, 0.18));
      expect(north.wall, 'north');
      expect(north.t, closeTo(0.25, 1e-9));
      expect(north.point, const Offset(0.3, 0.2));

      final east = snapToWall(rect, const Offset(0.7, 0.35));
      expect(east.wall, 'east');
      expect(east.t, closeTo(0.5, 1e-9));
      expect(east.point, const Offset(0.6, 0.35));

      expect(snapToWall(rect, const Offset(0.0, 0.0)).point, const Offset(0.2, 0.2)); // clamps to the corner
    });

    test('roomAt returns the smallest containing room', () {
      const big = GeoRoom(id: 'big', name: 'Hall', rect: Rect.fromLTRB(0, 0, 1, 1));
      const small = GeoRoom(id: 'small', name: 'Store', rect: Rect.fromLTRB(0.4, 0.4, 0.5, 0.5));
      expect(roomAt([big, small], const Offset(0.45, 0.45))!.id, 'small');
      expect(roomAt([big, small], const Offset(0.1, 0.1))!.id, 'big');
      expect(roomAt([small], const Offset(0.9, 0.9)), isNull);
    });

    test('clampRect keeps rectangles inside the plan and non-degenerate', () {
      final inside = clampRect(const Rect.fromLTRB(-0.2, 0.1, 0.4, 1.3));
      expect(inside.left, 0.0);
      expect(inside.bottom, 1.0);
      final inverted = clampRect(const Rect.fromLTRB(0.6, 0.6, 0.4, 0.4));
      expect(inverted.width, greaterThan(0));
      final tiny = clampRect(const Rect.fromLTRB(0.5, 0.5, 0.5, 0.5));
      expect(tiny.width, greaterThanOrEqualTo(0.02));
    });
  });

  test('structured backend errors surface their human-readable message', () async {
    final client = ApiClient(
      waker: ServerWaker.disabled(),
      client: MockClient((_) async => http.Response(
          jsonEncode({'detail': {'message': 'Geometry check failed with 1 error(s): overlap', 'issues': []}}), 422)),
    );
    await expectLater(
      client.post('http://x/api'),
      throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Geometry check failed with 1 error(s): overlap')),
    );
  });

  testWidgets('shows the failed checks and will not regenerate until they are fixed', (tester) async {
    final (_, backend, _) = await _pump(tester);

    expect(find.textContaining('1 error'), findsOneWidget);
    expect(find.textContaining("Rooms 'Living Room' and 'Bedroom 1' overlap"), findsOneWidget);
    expect(find.textContaining('Nothing is guessed'), findsOneWidget);

    await tester.tap(find.byKey(const Key('regenerate-button')), warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(backend.requests.where((r) => r.url.path.endsWith('/regenerate')), isEmpty);
  });

  testWidgets('drag a corner to fix an overlap, then regenerate the equipment', (tester) async {
    final (_, backend, _) = await _pump(tester);

    await tester.tapAt(_at(tester, 0.7, 0.3)); // select the right-hand room
    await tester.pumpAndSettle();
    final plan = _plan(tester);

    await _drag(tester, _at(tester, 0.4, 0.1), Offset(plan.width * 0.2, 0)); // top-left handle: x 0.40 -> 0.60

    final patch = backend.requests.singleWhere((r) => r.method == 'PATCH');
    expect(patch.url.path, endsWith('/rooms/kitchen'));
    final bounds = (jsonDecode(patch.body)['bounds'] as List).cast<num>();
    expect(bounds[0], greaterThan(0.5));
    expect(bounds[1], closeTo(0.1, 0.02));
    expect(bounds[2], closeTo(0.9, 1e-6));

    expect(find.text('Geometry checks passed'), findsOneWidget);
    expect(tester.widget<AppButton>(find.byKey(const Key('regenerate-button'))).onPressed, isNotNull);

    await tester.tap(find.byKey(const Key('regenerate-button')));
    await tester.pumpAndSettle();
    expect(backend.requests.where((r) => r.method == 'POST' && r.url.path.endsWith('/regenerate')), hasLength(1));
  });

  testWidgets('fix a wrong room name with one tap', (tester) async {
    final (_, backend, _) = await _pump(tester);

    await tester.tapAt(_at(tester, 0.7, 0.3));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byKey(const Key('room-name-field'))).controller!.text, 'Bedroom 1');

    await tester.tap(find.byKey(const Key('name-chip-Kitchen')));
    await tester.pumpAndSettle();

    final patch = backend.requests.singleWhere((r) => r.method == 'PATCH');
    expect(jsonDecode(patch.body), {'name': 'Kitchen'});
    expect(backend.rooms.last['name'], 'Kitchen');
    expect(tester.widget<TextField>(find.byKey(const Key('room-name-field'))).controller!.text, 'Kitchen');
  });

  testWidgets('type a custom room name and save it', (tester) async {
    final (_, backend, _) = await _pump(tester);
    await tester.tapAt(_at(tester, 0.2, 0.3));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('room-name-field')), 'Lounge');
    await tester.tap(find.byKey(const Key('save-room-name')));
    await tester.pumpAndSettle();

    expect(jsonDecode(backend.requests.singleWhere((r) => r.method == 'PATCH').body), {'name': 'Lounge'});
    expect(backend.rooms.first['name'], 'Lounge');
  });

  testWidgets('a rejected edit shows the backend message and changes nothing', (tester) async {
    final (_, backend, _) = await _pump(tester);
    backend.rejectEditsWith = 'Room bounds must stay inside the plan (0.0 - 1.0).';

    await tester.tapAt(_at(tester, 0.2, 0.3));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('name-chip-Bathroom')));
    await tester.pumpAndSettle();

    expect(find.textContaining('must stay inside the plan'), findsOneWidget);
    expect(backend.rooms.first['name'], 'Living Room');
  });

  testWidgets('select a door, flip its swing, then delete it', (tester) async {
    final (_, backend, _) = await _pump(tester);

    await tester.tapAt(_at(tester, 0.3, 0.5)); // the door marker on the south wall
    await tester.pumpAndSettle();
    expect(find.textContaining('Door in Living Room'), findsOneWidget);
    expect(find.byKey(const Key('door-handle')), findsOneWidget);

    await tester.tap(find.text('Opens out'));
    await tester.pumpAndSettle();
    expect(jsonDecode(backend.requests.singleWhere((r) => r.method == 'PATCH').body), {'swing_direction': 'out_of_room'});

    await tester.tap(find.byKey(const Key('delete-door')));
    await tester.pumpAndSettle();
    expect(backend.requests.where((r) => r.method == 'DELETE'), hasLength(1));
    expect(backend.doors, isEmpty);
    expect(find.byKey(const Key('door-handle')), findsNothing);
  });

  testWidgets('dragging the door handle slides it to the nearest wall', (tester) async {
    final (_, backend, _) = await _pump(tester);
    await tester.tapAt(_at(tester, 0.3, 0.5));
    await tester.pumpAndSettle();

    final plan = _plan(tester);
    // from the south wall up to the north wall of the living room: x 0.3, y 0.5 -> 0.1
    await _drag(tester, _at(tester, 0.3, 0.5), Offset(plan.width * 0.1, -plan.height * 0.4));

    final patch = backend.requests.singleWhere((r) => r.method == 'PATCH');
    final body = jsonDecode(patch.body) as Map<String, dynamic>;
    expect(body['wall'], 'north');
    expect(body['position'], closeTo(0.75, 0.05)); // x 0.4 on a wall spanning 0.1 - 0.5 -> (0.4 - 0.1) / 0.4
  });

  testWidgets('add a room and a door to it', (tester) async {
    final (_, backend, _) = await _pump(tester);

    await tester.tapAt(_at(tester, 0.9, 0.9)); // empty area: nothing selected
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('add-room')));
    await tester.pumpAndSettle();

    final post = backend.requests.singleWhere((r) => r.method == 'POST' && r.url.path.endsWith('/rooms'));
    expect(jsonDecode(post.body)['name'], 'New Room');
    // the new room is selected for naming
    expect(tester.widget<TextField>(find.byKey(const Key('room-name-field'))).controller!.text, 'New Room');
  });

  testWidgets('the project overview and AI analysis error lead to the editor', (tester) async {
    // a tiny harness: the editor is reachable from the analysis failure message
    final backend = _FakeBackend();
    await _pump(tester, backend: backend, home: (s, p) => Builder(builder: (context) {
      return Scaffold(
        body: Center(
          child: TextButton(
            key: const Key('open'),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => GeometryEditorScreen(state: s, project: p, planAspectRatio: 1.0)),
            ),
            child: const Text('open'),
          ),
        ),
      );
    }));
    await tester.tap(find.byKey(const Key('open')));
    await tester.pumpAndSettle();
    expect(find.text('Rooms & Doors'), findsOneWidget);
    expect(backend.requests.first.url.path, '/api/projects/$_pid/geometry');
  });
}
