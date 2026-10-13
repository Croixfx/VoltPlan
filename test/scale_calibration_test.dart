import 'package:flutter_test/flutter_test.dart';
import 'package:voltplan/features/floor_plan/scale_calibration_screen.dart';
import 'package:voltplan/shared/models/project.dart';

void main() {
  group('parseDistanceMm', () {
    test('converts metres and millimetres', () {
      expect(parseDistanceMm('4.5', ScaleUnit.metres), 4500);
      expect(parseDistanceMm('4,5', ScaleUnit.metres), 4500);
      expect(parseDistanceMm(' 900 ', ScaleUnit.millimetres), 900);
    });

    test('rejects empty, non-numeric, zero and negative input', () {
      for (final bad in ['', 'abc', '0', '-3', 'NaN', 'Infinity']) {
        expect(parseDistanceMm(bad, ScaleUnit.metres), isNull, reason: bad);
      }
    });
  });

  test('Project parses scale calibration from the backend', () {
    final base = {'id': 'p1', 'name': 'Villa', 'status': 'uploaded'};
    expect(Project.fromJson(base).isScaleCalibrated, isFalse);
    final cal = Project.fromJson({...base, 'scale_mm_per_pixel': 20.0});
    expect(cal.isScaleCalibrated, isTrue);
    expect(cal.scaleMmPerPixel, 20.0);
  });
}
