import 'package:flutter_test/flutter_test.dart';
import 'package:voltplan/core/network/api_exceptions.dart';
import 'package:voltplan/shared/models/analysis_result.dart';
import 'package:voltplan/shared/models/circuit.dart';
import 'package:voltplan/shared/models/cost_estimate.dart';
import 'package:voltplan/shared/models/electrical_point.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/models/room.dart';
import 'package:voltplan/shared/models/wiring_arc.dart';
import 'package:voltplan/shared/state/app_state.dart';

void main() {
  group('Model Serialization Tests', () {
    test('Project fromJson parses status and stages accurately', () {
      final json = {
        'id': 'p-101',
        'name': 'Kigali Villa',
        'client': 'Patrick M.',
        'building_type': 'Residential',
        'location': 'Kacyiru, Kigali',
        'standard': 'RS IEC 60364',
        'notes': 'High priority',
        'status': 'uploaded',
        'floor_plan_name': 'villa_plan.png',
        'rooms_count': 6,
        'electrical_points_count': 18,
        'circuits_count': 4,
        'estimated_cost_rwf': 4500000,
        'created_at': '2026-10-07T10:00:00Z',
        'updated_at': '2026-10-07T10:05:00Z',
      };

      final project = Project.fromJson(json);

      expect(project.id, 'p-101');
      expect(project.name, 'Kigali Villa');
      expect(project.currentStage, ProjectStage.aiAnalysis);
      expect(project.status, ProjectStatus.inProgress);
      expect(project.roomsCount, 6);
      expect(project.electricalPointsCount, 18);
      expect(project.circuitsCount, 4);
      expect(project.estimatedCostRwf, 4500000);
    });

    test('Room fromJson correctly captures dimensions and bounds', () {
      final json = {
        'id': 'r-01',
        'name': 'Master Bedroom',
        'area_m2': 18.5,
        'points_count': 5,
        'description': 'Master suite',
        'confidence': 0.94,
        'bounds': [0.1, 0.1, 0.4, 0.5],
      };

      final room = Room.fromJson(json);

      expect(room.id, 'r-01');
      expect(room.name, 'Master Bedroom');
      expect(room.areaM2, 18.5);
      expect(room.confidence, 0.94);
      expect(room.bounds, isNotNull);
      expect(room.bounds!.length, 4);
      expect(room.bounds![0], 0.1);
    });

    test('ElectricalPoint fromJson maps RS IEC 60364 specifications and review status', () {
      final json = {
        'id': 'pt_001',
        'room_id': 'r-01',
        'room_name': 'Living Room',
        'type': 'twin_socket',
        'quantity': 1,
        'power_rating_w': 250.0,
        'x_ratio': 0.25,
        'y_ratio': 0.35,
        'circuit_id': 'CKT-PWR-01',
        'recommended_cable': '3 x 2.5 mm² Cu/PVC',
        'recommended_protection': '20A Type B MCB + 30mA RCD',
        'rule_reference': 'RS IEC 60364-4-41',
        'status': 'RECOMMENDED',
        'review_notes': '13A twin socket outlet',
      };

      final point = ElectricalPoint.fromJson(json);

      expect(point.id, 'pt_001');
      expect(point.type, ElectricalPointType.socketDouble);
      expect(point.cableSize, '3 x 2.5 mm² Cu/PVC');
      expect(point.protectionMcb, '20A Type B MCB + 30mA RCD');
      expect(point.status, 'Recommended');
      expect(point.ruleReference, 'RS IEC 60364-4-41');
      expect(point.xRatio, 0.25);
      expect(point.yRatio, 0.35);
    });

    test('Circuit fromJson handles load and phase balancing', () {
      final json = {
        'id': 'CKT-LGT-01',
        'name': 'Lighting Circuit 1',
        'description': 'Living Room & Kitchen lighting',
        'circuit_type': 'lighting',
        'points_count': 4,
        'connected_load_w': 240.0,
        'phase': 'L1',
        'cable': '3 x 1.5 mm² Cu/PVC',
        'protection': '10A Type B MCB',
        'rcd': '30mA Type A RCD',
        'status': 'CALCULATED',
      };

      final circuit = Circuit.fromJson(json);

      expect(circuit.id, 'CKT-LGT-01');
      expect(circuit.code, 'LGT-01');
      expect(circuit.phase, 'L1');
      expect(circuit.loadKw, 0.24);
      expect(circuit.cableSize, '3 x 1.5 mm² Cu/PVC');
      expect(circuit.protectionMcb, '10A Type B MCB');
    });

    test('CostEstimate fromJson preserves Rwandan Franc breakdown and assumptions', () {
      final json = {
        'project_id': 'proj-1',
        'materials_cost_rwf': 3000000.0,
        'labor_cost_rwf': 840000.0,
        'contingency_cost_rwf': 360000.0,
        'grand_total_rwf': 4200000.0,
        'labor_percentage': 28.0,
        'contingency_percentage': 12.0,
        'currency': 'RWF',
        'assumptions': [
          'Labor calculated at 28%',
          'Contingency at 12%',
        ],
        'disclaimer': 'Preliminary engineering advisory cost estimate.',
      };

      final cost = CostEstimate.fromJson(json);

      expect(cost.materialsCostRwf, 3000000.0);
      expect(cost.laborCostRwf, 840000.0);
      expect(cost.contingencyCostRwf, 360000.0);
      expect(cost.grandTotalRwf, 4200000.0);
      expect(cost.currency, 'RWF');
      expect(cost.assumptions.length, 2);
    });

    test('AnalysisResult fromJson encapsulates full pipeline structure', () {
      final json = {
        'project_id': 'p-test',
        'status': 'completed',
        'current_step': 'completed',
        'standard_applied': 'RS IEC 60364',
        'rooms': [
          {
            'id': 'r1',
            'name': 'Living Room',
            'area_m2': 24.0,
            'points_count': 6,
            'confidence': 0.95,
          }
        ],
        'architectural_features': [
          {
            'type': 'door',
            'room_name': 'Living Room',
            'confidence': 0.92,
          }
        ],
        'observations': ['Rectangular floor layout'],
        'warnings': ['Verify bathroom zone 1 distances'],
        'electrical_points': [
          {
            'id': 'pt_1',
            'room_id': 'r1',
            'room_name': 'Living Room',
            'type': 'lighting',
            'quantity': 2,
            'power_rating_w': 120.0,
            'circuit_id': 'CKT-LGT-01',
            'recommended_cable': '3 x 1.5 mm²',
            'recommended_protection': '10A MCB',
            'rule_reference': 'RS IEC 60364',
            'status': 'RECOMMENDED',
          }
        ],
        'circuits': [
          {
            'id': 'CKT-LGT-01',
            'name': 'Lighting Circuit',
            'description': 'Main lighting',
            'circuit_type': 'lighting',
            'points_count': 2,
            'connected_load_w': 120.0,
            'phase': 'L1',
          }
        ],
        'boq_items': [
          {
            'id': 'b1',
            'category': 'Cables & Conduits',
            'item_code': 'CBL-1.5',
            'description': 'Electric Cable 1.5mm²',
            'specification': 'Cu/PVC 450/750V',
            'quantity': 2.0,
            'unit': 'rolls',
            'unit_price_rwf': 45000,
            'total_price_rwf': 90000,
          }
        ],
        'wiring_arcs': [
          {
            'id': 'arc-1',
            'circuit_id': 'CKT-LGT-01',
            'room_id': 'r1',
            'switch_id': 'sw_1',
            'luminaire_id': 'pt_1',
            'start_point': [0.15, 0.45],
            'control_point': [0.25, 0.40],
            'end_point': [0.35, 0.35],
            'length_norm': 0.28,
          }
        ],
        'cost_estimate': {
          'project_id': 'p-test',
          'materials_cost_rwf': 90000.0,
          'labor_cost_rwf': 25200.0,
          'contingency_cost_rwf': 10800.0,
          'grand_total_rwf': 126000.0,
        },
        'engineering_disclaimer': 'Must be reviewed by certified engineer.',
      };

      final result = AnalysisResult.fromJson(json);

      expect(result.projectId, 'p-test');
      expect(result.standardApplied, 'RS IEC 60364');
      expect(result.rooms.length, 1);
      expect(result.architecturalFeatures.length, 1);
      expect(result.warnings.length, 1);
      expect(result.electricalPoints.length, 1);
      expect(result.circuits.length, 1);
      expect(result.boqItems.length, 1);
      expect(result.wiringArcs.length, 1);
      expect(result.wiringArcs.first.id, 'arc-1');
      expect(result.wiringArcs.first.startPoint, [0.15, 0.45]);
      expect(result.costEstimate, isNotNull);
      expect(result.costEstimate!.grandTotalRwf, 126000.0);
    });

    test('WiringArc fromJson and toJson preserves Bézier control coordinates and length', () {
      final json = {
        'id': 'arc-master-01',
        'circuit_id': 'CKT-LGT-02',
        'room_id': 'room-master',
        'switch_id': 'sw-door-01',
        'luminaire_id': 'lum-center-01',
        'start_point': [0.12, 0.88],
        'control_point': [0.22, 0.75],
        'end_point': [0.25, 0.65],
        'length_norm': 0.265,
      };

      final arc = WiringArc.fromJson(json);

      expect(arc.id, 'arc-master-01');
      expect(arc.circuitId, 'CKT-LGT-02');
      expect(arc.roomId, 'room-master');
      expect(arc.switchId, 'sw-door-01');
      expect(arc.luminaireId, 'lum-center-01');
      expect(arc.startPoint, [0.12, 0.88]);
      expect(arc.controlPoint, [0.22, 0.75]);
      expect(arc.endPoint, [0.25, 0.65]);
      expect(arc.lengthNorm, 0.265);

      final encoded = arc.toJson();
      expect(encoded['id'], 'arc-master-01');
      expect(encoded['circuit_id'], 'CKT-LGT-02');
      expect(encoded['start_point'], [0.12, 0.88]);
    });
  });

  group('ApiException Tests', () {
    test('ApiException formats message and status code', () {
      final exception = ApiException('Server error occurred', statusCode: 500);
      expect(exception.toString(), 'ApiException (500): Server error occurred');
    });
  });

  group('AppState Integration Workflow', () {
    test('AppState runs analysis and populates results cleanly', () async {
      final state = AppState();
      expect(state.isAnalyzing, isFalse);

      await state.runAnalysisSimulation('sample-proj');

      expect(state.isAnalyzing, isFalse);
      expect(state.isAnalysisFinished, isTrue);
      expect(state.analysisStage, 5);
      expect(state.grandTotalCost, greaterThan(0));
    });
  });
}
