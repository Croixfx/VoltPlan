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
}
