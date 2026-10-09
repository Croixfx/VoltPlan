import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../shared/models/electrical_point.dart';
import '../../../shared/models/wiring_arc.dart';

class FloorPlanPainter extends CustomPainter {
  final List<ElectricalPoint> points;
  final ElectricalPoint? selectedPoint;
  final String activeLayer; // 'all', 'lighting', 'power', 'distribution'
  final bool isDark;
  final bool showBackground;
  final List<WiringArc>? wiringArcs;

  FloorPlanPainter({
    required this.points,
    this.selectedPoint,
    this.activeLayer = 'all',
    this.isDark = true,
    this.showBackground = true,
    this.wiringArcs,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;

    if (showBackground) {
      // Background fill
      final bgPaint = Paint()
        ..color = isDark ? const Color(0xFF0D131F) : const Color(0xFFF1F5F9);
      canvas.drawRect(Rect.fromLTWH(0, 0, width, height), bgPaint);

    // Subtle Architectural Grid
    final gridPaint = Paint()
      ..color = (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0))
          .withValues(alpha: 0.6)
      ..strokeWidth = 0.8;

    const gridSize = 24.0;
    for (double x = 0; x < width; x += gridSize) {
      canvas.drawLine(Offset(x, 0), Offset(x, height), gridPaint);
    }
    for (double y = 0; y < height; y += gridSize) {
      canvas.drawLine(Offset(0, y), Offset(width, y), gridPaint);
    }

    // Outer boundary margin
    final padX = width * 0.06;
    final padY = height * 0.06;
    final planW = width - (padX * 2);
    final planH = height - (padY * 2);

    // Define Room Rectangles
    // Top Row: Living Room (left 50%), Kitchen (right 50%)
    final rLiving = Rect.fromLTWH(padX, padY, planW * 0.50, planH * 0.44);
    final rKitchen = Rect.fromLTWH(
      padX + planW * 0.50,
      padY,
      planW * 0.50,
      planH * 0.44,
    );

    // Middle Corridor
    final rCorridor = Rect.fromLTWH(
      padX + planW * 0.40,
      padY + planW * 0.44,
      planW * 0.20,
      planH * 0.16,
    );

    // Bottom Row: Master Bedroom (left 45%), Bathroom (middle 20%), Bedroom 1 (right 35%)
    final rMaster = Rect.fromLTWH(
      padX,
      padY + planH * 0.52,
      planW * 0.45,
      planH * 0.48,
    );
    final rBathroom = Rect.fromLTWH(
      padX + planW * 0.45,
      padY + planH * 0.60,
      planW * 0.22,
      planH * 0.40,
    );
    final rBed1 = Rect.fromLTWH(
      padX + planW * 0.67,
      padY + planH * 0.52,
      planW * 0.33,
      planH * 0.48,
    );

    // Room fills
    final roomFill = Paint()
      ..color = (isDark ? const Color(0xFF162032) : const Color(0xFFFFFFFF))
      ..style = PaintingStyle.fill;

    canvas.drawRect(rLiving, roomFill);
    canvas.drawRect(rKitchen, roomFill);
    canvas.drawRect(rCorridor, roomFill);
    canvas.drawRect(rMaster, roomFill);
    canvas.drawRect(rBathroom, roomFill);
    canvas.drawRect(rBed1, roomFill);

    // Walls Paint
    final wallPaint = Paint()
      ..color = isDark ? const Color(0xFF94A3B8) : const Color(0xFF334155)
      ..strokeWidth = 3.5
      ..style = PaintingStyle.stroke;

    // Draw Room Walls
    canvas.drawRect(rLiving, wallPaint);
    canvas.drawRect(rKitchen, wallPaint);
    canvas.drawRect(rMaster, wallPaint);
    canvas.drawRect(rBathroom, wallPaint);
    canvas.drawRect(rBed1, wallPaint);

    // Doors & Windows
    _drawDoor(
      canvas,
      Offset(rLiving.right, rLiving.top + rLiving.height * 0.6),
      26,
      -math.pi / 2,
      isDark,
    );
    _drawDoor(
      canvas,
      Offset(rKitchen.left, rKitchen.top + rKitchen.height * 0.6),
      26,
      math.pi / 2,
      isDark,
    );
    _drawDoor(canvas, Offset(rMaster.right, rMaster.top + 20), 24, 0, isDark);
    _drawDoor(canvas, Offset(rBed1.left, rBed1.top + 20), 24, math.pi, isDark);

    // Windows (Cyan / Light Blue accents)
    _drawWindow(
      canvas,
      Offset(rLiving.left, rLiving.top + rLiving.height * 0.3),
      36,
      true,
      isDark,
    );
    _drawWindow(
      canvas,
      Offset(rKitchen.right, rKitchen.top + rKitchen.height * 0.3),
      36,
      true,
      isDark,
    );
    _drawWindow(
      canvas,
      Offset(rMaster.left + rMaster.width * 0.3, rMaster.bottom),
      42,
      false,
      isDark,
    );
    _drawWindow(
      canvas,
      Offset(rBed1.left + rBed1.width * 0.3, rBed1.bottom),
      40,
      false,
      isDark,
    );

    // Room Labels
    _drawRoomLabel(canvas, 'LIVING ROOM\n28.5 m²', rLiving.center, isDark);
    _drawRoomLabel(canvas, 'KITCHEN\n14.2 m²', rKitchen.center, isDark);
    _drawRoomLabel(
      canvas,
      'CORRIDOR\n8.5 m²',
      Offset(rCorridor.center.dx, rCorridor.center.dy - 10),
      isDark,
    );
    _drawRoomLabel(canvas, 'MASTER BEDROOM\n18.0 m²', rMaster.center, isDark);
    _drawRoomLabel(canvas, 'BATH\n4.8 m²', rBathroom.center, isDark);
    _drawRoomLabel(canvas, 'BEDROOM 1\n13.5 m²', rBed1.center, isDark);

    // Engineering stamp / Scale in top corner
    _drawEngineeringStamp(canvas, padX, padY, isDark);
    }

    // Draw Control / Switching Loops (curved dashed splines connecting switches to luminaires)
    if (activeLayer == 'all' || activeLayer == 'lighting') {
      _drawSwitchingLoops(canvas, size, isDark);
    }

    // Draw Electrical Symbols
    for (final pt in points) {
      if (!_shouldRenderPoint(pt)) continue;

      final ptOffset = Offset(pt.xRatio * width, pt.yRatio * height);
      final isSelected = selectedPoint?.id == pt.id;

      _drawElectricalSymbol(canvas, pt, ptOffset, isSelected, isDark);
    }
  }

  bool _shouldRenderPoint(ElectricalPoint pt) {
    if (activeLayer == 'all') return true;
    if (activeLayer == 'lighting') {
      return pt.type == ElectricalPointType.light ||
          pt.type == ElectricalPointType.downlight ||
          pt.type == ElectricalPointType.switchPoint;
    }
    if (activeLayer == 'power') {
      return pt.type == ElectricalPointType.socketDouble ||
          pt.type == ElectricalPointType.socketSingle ||
          pt.type == ElectricalPointType.cookerPoint ||
          pt.type == ElectricalPointType.waterHeater;
    }
    if (activeLayer == 'distribution') {
      return pt.type == ElectricalPointType.distributionBoard;
    }
    return true;
  }

  void _drawRoomLabel(Canvas canvas, String text, Offset center, bool isDark) {
    final textSpan = TextSpan(
      text: text,
      style: TextStyle(
        color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
        fontSize: 10,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
        height: 1.3,
      ),
    );
    final textPainter = TextPainter(
      text: textSpan,
      textAlign: TextAlign.center,
      textDirection: TextDirection.ltr,
    )..layout();

    textPainter.paint(
      canvas,
      Offset(
        center.dx - (textPainter.width / 2),
        center.dy - (textPainter.height / 2),
      ),
    );
  }

  void _drawDoor(
    Canvas canvas,
    Offset pivot,
    double radius,
    double startAngle,
    bool isDark,
  ) {
    final doorPaint = Paint()
      ..color = AppColors.accentCyan
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final arcRect = Rect.fromCircle(center: pivot, radius: radius);
    canvas.drawArc(arcRect, startAngle, math.pi / 2, false, doorPaint);

    final endX = pivot.dx + radius * math.cos(startAngle);
    final endY = pivot.dy + radius * math.sin(startAngle);
    canvas.drawLine(pivot, Offset(endX, endY), doorPaint);
  }

  void _drawWindow(
    Canvas canvas,
    Offset center,
    double length,
    bool isVertical,
    bool isDark,
  ) {
    final winPaint = Paint()
      ..color = const Color(0xFF38BDF8)
      ..strokeWidth = 2.0;

    if (isVertical) {
      canvas.drawLine(
        Offset(center.dx - 2, center.dy - length / 2),
        Offset(center.dx - 2, center.dy + length / 2),
        winPaint,
      );
      canvas.drawLine(
        Offset(center.dx + 2, center.dy - length / 2),
        Offset(center.dx + 2, center.dy + length / 2),
        winPaint,
      );
    } else {
      canvas.drawLine(
        Offset(center.dx - length / 2, center.dy - 2),
        Offset(center.dx + length / 2, center.dy - 2),
        winPaint,
      );
      canvas.drawLine(
        Offset(center.dx - length / 2, center.dy + 2),
        Offset(center.dx + length / 2, center.dy + 2),
        winPaint,
      );
    }
  }

  void _drawEngineeringStamp(Canvas canvas, double x, double y, bool isDark) {
    final textSpan = TextSpan(
      text: 'SCALE 1:50  •  RS IEC 60364',
      style: TextStyle(
        color: isDark ? const Color(0xFF475569) : const Color(0xFF94A3B8),
        fontSize: 9,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
    );
    final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)
      ..layout();
    tp.paint(canvas, Offset(x + 4, y + 4));
  }

  void _drawSwitchingLoops(Canvas canvas, Size size, bool isDark) {
    final loopPaint = Paint()
      ..color = (isDark ? AppColors.accentCyan : const Color(0xFF0284C7))
          .withValues(alpha: 0.70)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    // 1. If deterministic wiring arcs are provided from backend GeometryEngine, use them directly
    if (wiringArcs != null && wiringArcs!.isNotEmpty) {
      for (final arc in wiringArcs!) {
        if (arc.startPoint.length >= 2 &&
            arc.controlPoint.length >= 2 &&
            arc.endPoint.length >= 2) {
          final p0 = Offset(
            arc.startPoint[0] * size.width,
            arc.startPoint[1] * size.height,
          );
          final ctrl = Offset(
            arc.controlPoint[0] * size.width,
            arc.controlPoint[1] * size.height,
          );
          final p1 = Offset(
            arc.endPoint[0] * size.width,
            arc.endPoint[1] * size.height,
          );
          _drawDashedSplineWithControl(canvas, p0, ctrl, p1, loopPaint);
        }
      }
      return;
    }

    // 2. Fallback dynamic spline calculation based on room points
    final Map<String, List<ElectricalPoint>> roomPoints = {};
    for (final pt in points) {
      roomPoints.putIfAbsent(pt.roomId, () => []).add(pt);
    }

    for (final entry in roomPoints.entries) {
      final rPoints = entry.value;
      final switches = rPoints
          .where((p) => p.type == ElectricalPointType.switchPoint)
          .toList();
      final lights = rPoints
          .where((p) =>
              p.type == ElectricalPointType.light ||
              p.type == ElectricalPointType.downlight)
          .toList();

      if (switches.isEmpty || lights.isEmpty) continue;

      for (final light in lights) {
        final ltPos = Offset(light.xRatio * size.width, light.yRatio * size.height);

        ElectricalPoint nearestSw = switches.first;
        double minDist = double.infinity;
        for (final sw in switches) {
          final swPos = Offset(sw.xRatio * size.width, sw.yRatio * size.height);
          final d = (ltPos - swPos).distance;
          if (d < minDist) {
            minDist = d;
            nearestSw = sw;
          }
        }

        final swPos = Offset(nearestSw.xRatio * size.width, nearestSw.yRatio * size.height);
        _drawDashedSpline(canvas, swPos, ltPos, loopPaint);
      }
    }
  }

  void _drawDashedSpline(
    Canvas canvas,
    Offset p0,
    Offset p1,
    Paint paint, {
    double dash = 4.0,
    double gap = 3.0,
  }) {
    final d = (p1 - p0).distance;
    if (d < 8) return;

    final mid = Offset((p0.dx + p1.dx) / 2, (p0.dy + p1.dy) / 2);
    final nx = -(p1.dy - p0.dy) / d;
    final ny = (p1.dx - p0.dx) / d;
    final ctrl = Offset(mid.dx + nx * (d * 0.22), mid.dy + ny * (d * 0.22));

    _drawDashedSplineWithControl(canvas, p0, ctrl, p1, paint, dash: dash, gap: gap);
  }

  void _drawDashedSplineWithControl(
    Canvas canvas,
    Offset p0,
    Offset ctrl,
    Offset p1,
    Paint paint, {
    double dash = 4.0,
    double gap = 3.0,
  }) {
    final d = (p1 - p0).distance;
    if (d < 8) return;

    final path = Path()
      ..moveTo(p0.dx, p0.dy)
      ..quadraticBezierTo(ctrl.dx, ctrl.dy, p1.dx, p1.dy);

    for (final metric in path.computeMetrics()) {
      double distance = 0.0;
      while (distance < metric.length) {
        final len = math.min(dash, metric.length - distance);
        canvas.drawPath(metric.extractPath(distance, distance + len), paint);
        distance += dash + gap;
      }
    }
  }

  void _drawElectricalSymbol(
    Canvas canvas,
    ElectricalPoint pt,
    Offset pos,
    bool isSelected,
    bool isDark,
  ) {
    final symbolColor = isDark
        ? AppColors.textPrimaryDark
        : const Color(0xFF1E293B);

    final bgFillColor = isDark
        ? const Color(0xFF0F172A)
        : Colors.white;

    final bgPaint = Paint()
      ..color = bgFillColor
      ..style = PaintingStyle.fill;

    final strokePaint = Paint()
      ..color = symbolColor
      ..strokeWidth = 1.6
      ..style = PaintingStyle.stroke;

    // Selection Halo
    if (isSelected) {
      final glowPaint = Paint()
        ..color = AppColors.primaryBlue.withValues(alpha: 0.25)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pos, 16, glowPaint);

      final ringPaint = Paint()
        ..color = AppColors.primaryBlue
        ..strokeWidth = 1.8
        ..style = PaintingStyle.stroke;
      canvas.drawCircle(pos, 15, ringPaint);
    }

    switch (pt.type) {
      // 1. Ceiling Light / Luminaire: Standard circle with an 'X' through it (IEC 60617 / ANSI)
      case ElectricalPointType.light:
        const double radius = 8.5;
        // Background mask to hide drawing lines
        canvas.drawCircle(pos, radius, bgPaint);
        // Outer circle
        canvas.drawCircle(pos, radius, strokePaint);
        // 'X' through it from edge to edge
        const double offset = radius * 0.7071;
        canvas.drawLine(
          Offset(pos.dx - offset, pos.dy - offset),
          Offset(pos.dx + offset, pos.dy + offset),
          strokePaint,
        );
        canvas.drawLine(
          Offset(pos.dx - offset, pos.dy + offset),
          Offset(pos.dx + offset, pos.dy - offset),
          strokePaint,
        );
        break;

      // 2. Downlight / Recessed Light: Circle with a filled center dot (IEC 60617)
      case ElectricalPointType.downlight:
        const double radius = 7.5;
        canvas.drawCircle(pos, radius, bgPaint);
        canvas.drawCircle(pos, radius, strokePaint);
        final dotPaint = Paint()
          ..color = symbolColor
          ..style = PaintingStyle.fill;
        canvas.drawCircle(pos, 2.8, dotPaint);
        break;

      // 3. Wall Switches: Small open circle with 45° radial arm(s). NO numbers inside! (IEC 60617)
      case ElectricalPointType.switchPoint:
        const double radius = 4.5;
        canvas.drawCircle(pos, radius, bgPaint);
        canvas.drawCircle(pos, radius, strokePaint);

        final bool is2Way = pt.label.toLowerCase().contains('2-way') ||
            pt.label.toLowerCase().contains('two-way') ||
            pt.reviewNotes.toLowerCase().contains('2-way');

        const double cos45 = 0.7071;
        const double sin45 = 0.7071;
        const double armLen = 8.0;

        // Arm 1 extending outward at 45 degrees
        final armStart1 = Offset(pos.dx + radius * cos45, pos.dy - radius * sin45);
        final armEnd1 = Offset(pos.dx + (radius + armLen) * cos45, pos.dy - (radius + armLen) * sin45);
        canvas.drawLine(armStart1, armEnd1, strokePaint);

        // Terminal contact tick on Arm 1
        final tickEnd1 = Offset(armEnd1.dx - 3.0 * sin45, armEnd1.dy - 3.0 * cos45);
        canvas.drawLine(armEnd1, tickEnd1, strokePaint);

        // Two-way switch: Arm 2 in opposite direction
        if (is2Way) {
          final armStart2 = Offset(pos.dx - radius * cos45, pos.dy + radius * sin45);
          final armEnd2 = Offset(pos.dx - (radius + armLen) * cos45, pos.dy + (radius + armLen) * sin45);
          canvas.drawLine(armStart2, armEnd2, strokePaint);

          final tickEnd2 = Offset(armEnd2.dx + 3.0 * sin45, armEnd2.dy + 3.0 * cos45);
          canvas.drawLine(armEnd2, tickEnd2, strokePaint);
        }
        break;

      // 4. Power Outlets / Receptacles (IEC 60617 Standard Semicircle with tines)
      case ElectricalPointType.socketDouble:
        _drawIecSocket(
          canvas,
          pos,
          isDouble: true,
          pt: pt,
          symbolColor: symbolColor,
          bgPaint: bgPaint,
          strokePaint: strokePaint,
          isDark: isDark,
        );
        break;

      case ElectricalPointType.socketSingle:
        _drawIecSocket(
          canvas,
          pos,
          isDouble: false,
          pt: pt,
          symbolColor: symbolColor,
          bgPaint: bgPaint,
          strokePaint: strokePaint,
          isDark: isDark,
        );
        break;

      // 5. Main Distribution Board (DB / Consumer Unit): Solid/diagonally split half-shaded rectangle labeled "DB"
      case ElectricalPointType.distributionBoard:
        const double dbW = 28.0;
        const double dbH = 10.0;
        final dbRect = Rect.fromCenter(center: pos, width: dbW, height: dbH);

        // Background mask
        canvas.drawRect(dbRect, bgPaint);

        // Diagonally split half-shaded rectangle (IEC standard)
        final path = Path()
          ..moveTo(dbRect.left, dbRect.top)
          ..lineTo(dbRect.right, dbRect.top)
          ..lineTo(dbRect.left, dbRect.bottom)
          ..close();
        final fillPaint = Paint()
          ..color = symbolColor
          ..style = PaintingStyle.fill;
        canvas.drawPath(path, fillPaint);

        // Outer border
        final dbBorderPaint = Paint()
          ..color = symbolColor
          ..strokeWidth = 1.8
          ..style = PaintingStyle.stroke;
        canvas.drawRect(dbRect, dbBorderPaint);

        // Architectural "DB" text notation
        final textSpan = TextSpan(
          text: 'DB',
          style: TextStyle(
            color: isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
            fontSize: 8.5,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.5,
          ),
        );
        final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
        tp.paint(canvas, Offset(pos.dx - (tp.width / 2), pos.dy + (dbH / 2) + 2));
        break;

      // 6. Dedicated High-Power Points (Cooker, Water Heater, TV)
      case ElectricalPointType.cookerPoint:
        _drawDedicatedPoint(canvas, pos, 'C', symbolColor, bgPaint, strokePaint, isDark);
        break;

      case ElectricalPointType.waterHeater:
        _drawDedicatedPoint(canvas, pos, 'WH', symbolColor, bgPaint, strokePaint, isDark);
        break;

      case ElectricalPointType.tvPoint:
        _drawDedicatedPoint(canvas, pos, 'TV', symbolColor, bgPaint, strokePaint, isDark);
        break;
    }
  }

  void _drawIecSocket(
    Canvas canvas,
    Offset pos, {
    required bool isDouble,
    required ElectricalPoint pt,
    required Color symbolColor,
    required Paint bgPaint,
    required Paint strokePaint,
    required bool isDark,
  }) {
    const double radius = 7.5;
    final arcRect = Rect.fromCircle(center: pos, radius: radius);

    // Semicircle background fill
    final semiPath = Path()
      ..moveTo(pos.dx - radius, pos.dy)
      ..arcTo(arcRect, math.pi, math.pi, false)
      ..close();
    canvas.drawPath(semiPath, bgPaint);

    // Flat baseline against wall
    canvas.drawLine(
      Offset(pos.dx - radius, pos.dy),
      Offset(pos.dx + radius, pos.dy),
      strokePaint,
    );

    // Curved semicircle arc (IEC 60617)
    canvas.drawArc(arcRect, math.pi, math.pi, false, strokePaint);

    // Radial tines extending outward from curved arc
    const double tineLen = 5.5;
    if (isDouble) {
      // Duplex / Twin Socket: two parallel radial tines
      canvas.drawLine(
        Offset(pos.dx - 3.5, pos.dy - radius),
        Offset(pos.dx - 3.5, pos.dy - radius - tineLen),
        strokePaint,
      );
      canvas.drawLine(
        Offset(pos.dx + 3.5, pos.dy - radius),
        Offset(pos.dx + 3.5, pos.dy - radius - tineLen),
        strokePaint,
      );
    } else {
      // Single Socket: one radial tine in center
      canvas.drawLine(
        Offset(pos.dx, pos.dy - radius),
        Offset(pos.dx, pos.dy - radius - tineLen),
        strokePaint,
      );
    }

    // Wet-area / Shaver socket tag notation (only for explicit GFCI or bathroom shaver outlets)
    final bool isGfci = pt.label.toLowerCase().contains('gfci') ||
        (pt.roomName.toLowerCase().contains('bath') && pt.type == ElectricalPointType.socketSingle);

    if (isGfci) {
      final textSpan = TextSpan(
        text: 'GFCI',
        style: TextStyle(
          color: isDark ? AppColors.accentCyan : const Color(0xFF0369A1),
          fontSize: 7.0,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.2,
        ),
      );
      final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset(pos.dx + radius + 1.5, pos.dy - radius - 2));
    }
  }

  void _drawDedicatedPoint(
    Canvas canvas,
    Offset pos,
    String tag,
    Color symbolColor,
    Paint bgPaint,
    Paint strokePaint,
    bool isDark,
  ) {
    const double size = 14.0;
    final rect = Rect.fromCenter(center: pos, width: size, height: size);
    canvas.drawRect(rect, bgPaint);
    canvas.drawRect(rect, strokePaint);

    final textSpan = TextSpan(
      text: tag,
      style: TextStyle(
        color: symbolColor,
        fontSize: tag.length > 1 ? 7.5 : 8.5,
        fontWeight: FontWeight.w800,
      ),
    );
    final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
    tp.paint(canvas, Offset(pos.dx - (tp.width / 2), pos.dy - (tp.height / 2)));
  }

  @override
  bool shouldRepaint(covariant FloorPlanPainter oldDelegate) {
    return oldDelegate.selectedPoint?.id != selectedPoint?.id ||
        oldDelegate.activeLayer != activeLayer ||
        oldDelegate.points != points ||
        oldDelegate.isDark != isDark ||
        oldDelegate.showBackground != showBackground;
  }
}
