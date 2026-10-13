import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/features/electrical/calculations_screen.dart';
import 'package:voltplan/features/electrical/data/calculations_repository.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/state/app_state.dart';

Future<List<http.Request>> _pumpScreen(WidgetTester tester, Map<String, dynamic> payload) async {
  tester.view.physicalSize = const Size(900, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final requests = <http.Request>[];
  final repository = CalculationsRepository(
    client: ApiClient(client: MockClient((req) async {
      requests.add(req);
      return http.Response(jsonEncode(payload), 200);
    })),
  );
  final project = Project(
    id: 'srv-1', name: 'Villa', client: 'C', buildingType: 'Residential', location: 'Kigali',
    standard: 'RS IEC 60364', status: ProjectStatus.completed, currentStage: ProjectStage.electricalDesign,
    updatedAt: DateTime(2026), createdAt: DateTime(2026),
  );
  final state = AppState();
  state.selectProject(project);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: CalculationsScreen(state: state, project: project, repository: repository),
  ));
  await tester.pumpAndSettle();
  return requests;
}


Map<String, dynamic> _capacityPayload({int grouped = 1, String method = 'B2'}) {
  final fail = grouped > 1;
  return {
    'disclaimer': 'PRELIMINARY', 'references': [],
    'max_demand': {
      'diversity_applied': true, 'connected_load_kw': 1, 'total_demand_kva': 1, 'total': {'total_demand_a': 5},
      'per_phase': {}, 'phase_imbalance_percent': 0,
      'suggested_main_switch': {'three_phase_supply_a': 16, 'single_phase_supply_a': 16, 'note': ''}, 'notes': [],
    },
    'voltage_drop': {'status': 'not_calculated', 'reason': 'No distribution board has been placed.', 'assumptions': [], 'circuits': []},
    'cable_capacity': {
      'status': 'calculated',
      'options': {
        'method': method, 'method_description': 'multi-core cable in conduit on a wall or embedded in masonry',
        'ambient_c': 30, 'ambient_factor': 1.0, 'grouped_circuits': grouped, 'grouping_factor': fail ? 0.8 : 1.0,
        'available': {'methods': ['A2', 'B2', 'C'], 'ambient_c': [30, 35, 40], 'grouped_circuits': [1, 2, 3, 4, 5, 6]},
      },
      'assumptions': ['Iz = It x Ca x Cg.'],
      'summary': {'circuits_checked': 3, 'failing': fail ? 1 : 0, 'marginal': fail ? 0 : 1},
      'circuits': [
        {
          'circuit_id': 'PWR-1', 'name': 'Power Sockets Circuit 1', 'status': fail ? 'fail' : 'pass',
          'reason': fail ? 'protective device 20 A exceeds the cable capacity 18.4 A' : null,
          'cable_mm2': 2.5, 'protective_device_a': 20.0, 'capacity_a': fail ? 18.4 : 23.0,
          'utilisation_percent': fail ? 108.7 : 87.0, 'max_grouped_circuits': 1,
          'recommended_cable_mm2': fail ? 4.0 : null, 'reduce_device_to_a': fail ? 16 : null,
        },
        {
          'circuit_id': 'LGT-1', 'name': 'Lighting Circuit 1', 'status': 'pass', 'reason': null,
          'cable_mm2': 1.5, 'protective_device_a': 10.0, 'capacity_a': 16.5, 'utilisation_percent': 60.6,
          'max_grouped_circuits': 6, 'recommended_cable_mm2': null, 'reduce_device_to_a': null,
        },
        {
          'circuit_id': 'WTR-1', 'name': 'Water Heater', 'status': fail ? 'pass' : 'marginal', 'reason': null,
          'cable_mm2': 2.5, 'protective_device_a': 20.0, 'capacity_a': 21.6, 'utilisation_percent': 92.6,
          'max_grouped_circuits': 2, 'recommended_cable_mm2': null, 'reduce_device_to_a': null,
        },
      ],
    },
  };
}

Future<List<http.Request>> _pumpDynamic(WidgetTester tester, Map<String, dynamic> Function(Uri) payloadFor) async {
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final requests = <http.Request>[];
  final repository = CalculationsRepository(
    client: ApiClient(client: MockClient((req) async {
      requests.add(req);
      return http.Response(jsonEncode(payloadFor(req.url)), 200);
    })),
  );
  final project = Project(
    id: 'srv-1', name: 'Villa', client: 'C', buildingType: 'Residential', location: 'Kigali',
    standard: 'RS IEC 60364', status: ProjectStatus.completed, currentStage: ProjectStage.electricalDesign,
    updatedAt: DateTime(2026), createdAt: DateTime(2026),
  );
  final state = AppState();
  state.selectProject(project);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light(),
    home: CalculationsScreen(state: state, project: project, repository: repository),
  ));
  await tester.pumpAndSettle();
  return requests;
}

void main() {
  testWidgets('calculations: failing circuits and the demand summary are shown', (tester) async {
    final payload = {
        'disclaimer': 'PRELIMINARY CALCULATIONS FOR REVIEW BY A QUALIFIED ELECTRICIAN.',
        'references': ['Voltage drop: dV = 2 x Ib x L x rho / S'],
        'geometry_needs_regeneration': true,
        'max_demand': {
          'diversity_applied': true, 'connected_load_kw': 12.4, 'total_demand_kva': 14.3,
          'total': {'total_demand_a': 62.14},
          'per_phase': {'L1': {'total_demand_a': 23.4}},
          'phase_imbalance_percent': 12.0,
          'suggested_main_switch': {'three_phase_supply_a': 40, 'single_phase_supply_a': 63, 'note': 'Confirm with the utility.'},
          'notes': ['Household diversity applied.'],
        },
        'voltage_drop': {
          'status': 'calculated', 'assumptions': ['Final circuit only.'],
          'summary': {'circuits_checked': 2, 'failing': 1, 'marginal': 0},
          'circuits': [
            {'circuit_id': 'PWR-1', 'name': 'Power Sockets Circuit 1', 'status': 'fail', 'drop_percent': 7.45, 'limit_percent': 5.0,
             'length_m': 47.6, 'design_current_a': 20.0, 'cable_mm2': 2.5, 'recommended_cable_mm2': 4.0},
            {'circuit_id': 'LGT-1', 'name': 'Lighting Circuit 1', 'status': 'pass', 'drop_percent': 0.6, 'limit_percent': 3.0,
             'length_m': 17.7, 'design_current_a': 2.61, 'cable_mm2': 1.5},
          ],
        },
      };
    final requests = await _pumpScreen(tester, payload);
    expect(requests.single.url.path, '/api/projects/srv-1/calculations');

    expect(find.textContaining('PRELIMINARY'), findsOneWidget);
    expect(find.textContaining('Regenerate the equipment'), findsOneWidget);
    expect(find.byKey(const Key('max-demand-total')), findsOneWidget);
    expect(find.text('62.14 A'), findsOneWidget);
    expect(find.textContaining('3-phase supply: 40 A'), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('vd-row-PWR-1')), matching: find.text('FAIL')), findsOneWidget);
    expect(find.textContaining('use at least 4.0 mm²'), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('vd-row-LGT-1')), matching: find.text('PASS')), findsOneWidget);
  });

  testWidgets('calculations: missing inputs are explained, not estimated', (tester) async {
    final payload = {
        'disclaimer': 'PRELIMINARY', 'references': [],
        'max_demand': {
          'diversity_applied': true, 'connected_load_kw': 1, 'total_demand_kva': 1, 'total': {'total_demand_a': 5},
          'per_phase': {}, 'phase_imbalance_percent': 0,
          'suggested_main_switch': {'three_phase_supply_a': 16, 'single_phase_supply_a': 16, 'note': ''}, 'notes': [],
        },
        'voltage_drop': {
          'status': 'not_calculated', 'reason': 'The plan scale is not calibrated, so cable lengths cannot be measured.',
          'assumptions': [], 'circuits': [],
        },
      };
    final requests = await _pumpScreen(tester, payload);
    expect(requests.single.url.path, '/api/projects/srv-1/calculations');
    expect(find.byKey(const Key('vd-not-calculated')), findsOneWidget);
    expect(find.textContaining('scale is not calibrated'), findsOneWidget);
    expect(find.textContaining('never estimated'), findsOneWidget);
  });

  testWidgets('cable capacity: rows show capacity, utilisation and how many circuits may be bunched', (tester) async {
    final requests = await _pumpDynamic(tester, (_) => _capacityPayload());

    // the first request uses the documented defaults
    expect(requests.first.url.queryParameters, {'method': 'B2', 'ambient_c': '30', 'grouped_circuits': '1'});
    expect(find.text('Cable current capacity'), findsOneWidget);
    expect(find.byKey(const Key('cap-summary')), findsOneWidget);
    expect(find.textContaining('0 failing'), findsWidgets);

    final sockets = find.byKey(const Key('cap-row-PWR-1'));
    expect(find.descendant(of: sockets, matching: find.textContaining('capacity 23.0 A (87.0 % used)')), findsOneWidget);
    expect(find.descendant(of: sockets, matching: find.textContaining('must not share its route')), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('cap-row-LGT-1')), matching: find.textContaining('up to 6 circuits bunched')), findsOneWidget);
    expect(find.descendant(of: find.byKey(const Key('cap-row-WTR-1')), matching: find.text('MARGINAL')), findsOneWidget);
  });

  testWidgets('cable capacity: bunching more circuits re-runs the check and shows the fix', (tester) async {
    final requests = await _pumpDynamic(tester, (uri) =>
        _capacityPayload(grouped: int.parse(uri.queryParameters['grouped_circuits']!), method: uri.queryParameters['method']!));

    await tester.ensureVisible(find.byKey(const Key('cap-grouped')));
    await tester.tap(find.byKey(const Key('cap-grouped')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('2 together').last);
    await tester.pumpAndSettle();

    expect(requests.last.url.queryParameters['grouped_circuits'], '2');
    final row = find.byKey(const Key('cap-row-PWR-1'));
    expect(find.descendant(of: row, matching: find.text('FAIL')), findsOneWidget);
    expect(find.descendant(of: row, matching: find.textContaining('exceeds the cable capacity 18.4 A')), findsOneWidget);
    expect(find.descendant(of: row, matching: find.textContaining('use at least 4.0 mm²')), findsOneWidget);
    expect(find.descendant(of: row, matching: find.textContaining('reduce the device to 16 A')), findsOneWidget);
    expect(find.textContaining('1 failing'), findsWidgets);
    // the other figures stayed on screen while refreshing
    expect(find.byKey(const Key('max-demand-total')), findsOneWidget);
  });

  testWidgets('cable capacity: changing the installation method is sent to the backend', (tester) async {
    final requests = await _pumpDynamic(tester, (uri) => _capacityPayload(method: uri.queryParameters['method']!));
    await tester.ensureVisible(find.byKey(const Key('cap-method')));
    await tester.tap(find.byKey(const Key('cap-method')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('C').last);
    await tester.pumpAndSettle();
    expect(requests.last.url.queryParameters['method'], 'C');
    expect(find.textContaining('Method C'), findsOneWidget);
  });
}
