import 'package:flutter_test/flutter_test.dart';
import 'package:voltplan/shared/models/electrical_point.dart';

void main() {
  test('catalog equipment types map to their own point types', () {
    const expected = {
      'ac_point': ElectricalPointType.acPoint,
      'extractor_fan': ElectricalPointType.extractorFan,
      'smoke_detector': ElectricalPointType.smokeDetector,
      'emergency_light': ElectricalPointType.emergencyLight,
      'data_point': ElectricalPointType.dataPoint,
      'outdoor_light': ElectricalPointType.outdoorLight,
      'tv_point': ElectricalPointType.tvPoint,
    };
    expected.forEach((backendType, type) {
      expect(ElectricalPointType.fromBackendType(backendType), type,
          reason: backendType);
    });
  });

  test('ElectricalPoint.fromJson parses a smoke detector', () {
    final pt = ElectricalPoint.fromJson({
      'id': 'pt_001',
      'room_id': 'r1',
      'room_name': 'Bedroom 1',
      'type': 'smoke_detector',
      'circuit_id': 'CKT-SAF-01',
      'recommended_cable': '3 x 1.5 mm² Cu/PVC',
      'recommended_protection': '6A Type B MCB',
    });
    expect(pt.type, ElectricalPointType.smokeDetector);
    expect(pt.label, 'Interlinked Smoke Alarm');
    expect(pt.circuitId, 'CKT-SAF-01');
  });
}
