import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/engineering_sheet.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/models/electrical_point.dart';
import '../../shared/state/app_state.dart';
import '../floor_plan/widgets/plan_drawing_viewer.dart';
import 'circuits_screen.dart';

class ElectricalPlanCanvasScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  const ElectricalPlanCanvasScreen({
    super.key,
    required this.state,
    required this.project,
  });

  @override
  State<ElectricalPlanCanvasScreen> createState() =>
      _ElectricalPlanCanvasScreenState();
}

class _ElectricalPlanCanvasScreenState
    extends State<ElectricalPlanCanvasScreen> {
  final TransformationController _transformationController =
      TransformationController();
  String _activeLayer = 'all'; // 'all', 'lighting', 'power', 'distribution'
  ElectricalPoint? _selectedPoint;

  void _resetZoom() {
    _transformationController.value = Matrix4.identity();
  }

  void _showPointInspectionBottomSheet(ElectricalPoint point) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    EngineeringBottomSheet.show(
      context: context,
      title: point.label,
      subtitle: '${point.roomName}  •  Circuit ${point.circuitId}',
      child: Column(
        children: [
          _buildDetailRow('Component', point.type.label, isDark),
          _buildDetailRow('Room', point.roomName, isDark),
          _buildDetailRow('Quantity', '${point.quantity} allocated', isDark),
          _buildDetailRow('Recommended Cable', point.cableSize, isDark),
          _buildDetailRow('Circuit', point.circuitId, isDark),
          _buildDetailRow('Protection', point.protectionMcb, isDark),
          _buildDetailRow('Status', point.status, isDark, isBadge: true),
        ],
      ),
      actions: [
        AppButton(
          label: 'View Circuit Schedule',
          variant: AppButtonVariant.primary,
          icon: Icons.alt_route,
          onPressed: () {
            Navigator.pop(context);
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => CircuitsScreen(
                  state: widget.state,
                  project: widget.project,
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  Widget _buildDetailRow(
    String label,
    String value,
    bool isDark, {
    bool isBadge = false,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              color: isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
            ),
          ),
          if (isBadge)
            StatusBadge(status: value, isSmall: true)
          else
            Text(
              value,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: isDark
                    ? AppColors.textPrimaryDark
                    : AppColors.textPrimaryLight,
              ),
            ),
        ],
      ),
    );
  }

  void _showLegendBottomSheet() {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    EngineeringBottomSheet.show(
      context: context,
      title: 'Symbol Legend & Standards',
      subtitle: '${widget.project.standard} Installation Guidelines (IEC 60617 / ANSI)',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.ceilingLight,
              isDark: isDark,
            ),
            title: 'Ceiling Luminaire / Light Point',
            standardRef: 'IEC 60617-11-13-01 • ANSI/IEEE 315',
            description:
                'Circle with edge-to-edge diagonal crosslines (X). Centered or placed in uniform arrays for 150–300 lux illuminance.',
            cable: '3 x 1.5 mm² Cu/PVC • 10A Type B MCB',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.downlight,
              isDark: isDark,
            ),
            title: 'Recessed Downlight / Spot Point',
            standardRef: 'IEC 60617-11-13-03',
            description:
                'Circle with solid filled center core. Task lighting for kitchens, corridors, and focal architectural features.',
            cable: '3 x 1.5 mm² Cu/PVC • 10A Type B MCB',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.wallSwitch,
              isDark: isDark,
            ),
            title: '1-Way Wall Switch (Single-Pole)',
            standardRef: 'IEC 60617-11-14-01',
            description:
                'Open circle with 45° radial arm & terminal contact tick (no numbers). Mounted 150 mm from latch side of door frame, 1.2 m AFFL.',
            cable: '3 x 1.5 mm² Cu/PVC • 10A Type B MCB',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.twoWaySwitch,
              isDark: isDark,
            ),
            title: '2-Way Switch (Stairway / Hallway)',
            standardRef: 'IEC 60617-11-14-02',
            description:
                'Open circle with two arms extending in opposite directions. Multi-way switching for stairs, master bedrooms, and corridors.',
            cable: '3 x 1.5 mm² Cu/PVC • 10A Type B MCB',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.socketDouble,
              isDark: isDark,
            ),
            title: 'Twin 13A Switched Socket-Outlet',
            standardRef: 'IEC 60617-11-13-02 • RS IEC 60364',
            description:
                'Standard semicircle with 2 radial tines snapped flush to perimeter walls. Max 4 m spacing along perimeter walls, 300–450 mm AFFL.',
            cable: '3 x 2.5 mm² Cu/PVC • 20A Type B MCB + 30mA RCD',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.socketGfci,
              isDark: isDark,
            ),
            title: 'GFCI Socket-Outlet (Wet Areas / Kitchen)',
            standardRef: 'IEC 60364-7-701 • RS 565 Clause 6.1',
            description:
                'Semicircle with standard GFCI notation. Mandatory in bathrooms (Zone 2/3) and above kitchen worktop splash zones.',
            cable: '3 x 2.5 mm² Cu/PVC • 20A MCB + 10mA/30mA RCD',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.switchingLoop,
              isDark: isDark,
            ),
            title: 'Switching / Control Loops',
            standardRef: 'Architectural Drafting Convention',
            description:
                'Curved dashed splines tracing physical control wiring from wall switches directly to the exact luminaires they command.',
            cable: 'Conduit Embedded Switch Leg • 1.5 mm² Cu',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.distributionBoard,
              isDark: isDark,
            ),
            title: 'Main Distribution Board (MDB / DB)',
            standardRef: 'IEC 60617-11-17-01',
            description:
                'Elongated diagonally split half-shaded rectangle mounted flush to wall, labeled DB. Central load center with 63A 30mA RCD main protection.',
            cable: '16 mm² Cu Sub-main • Multi-way Metal Enclosure',
            isDark: isDark,
          ),
          _buildLegendItem(
            badge: _IecSymbolBadge(
              type: _IecBadgeType.dedicatedAppliance,
              isDark: isDark,
            ),
            title: 'Dedicated Radial (Cooker / WH / AC)',
            standardRef: 'RS IEC 60364 Clause 4.2',
            description:
                'Heavy load radial circuits for Cooker [C] and Water Heater [WH] with adjacent double-pole isolators.',
            cable: '3 x 4.0–6.0 mm² Cu/PVC • 25A–32A Type B MCB',
            isDark: isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem({
    required Widget badge,
    required String title,
    required String standardRef,
    required String description,
    required String cable,
    required bool isDark,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark
            ? AppColors.surfaceSecondaryDark
            : AppColors.surfaceSecondaryLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          badge,
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  standardRef,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: isDark ? AppColors.accentCyan : const Color(0xFF0284C7),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    height: 1.35,
                    color: isDark
                        ? AppColors.textSecondaryDark
                        : AppColors.textSecondaryLight,
                  ),
                ),
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.primaryBlue.withValues(alpha: isDark ? 0.2 : 0.08),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    cable,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primaryBlue,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : AppColors.backgroundLight,
      appBar: AppBar(
        title: const Text('Electrical Plan'),
        actions: [
          IconButton(
            icon: const Icon(Icons.menu_book_outlined),
            tooltip: 'Symbol Legend & Standards',
            onPressed: _showLegendBottomSheet,
          ),
          IconButton(
            icon: const Icon(Icons.center_focus_strong_outlined),
            tooltip: 'Fit Canvas',
            onPressed: _resetZoom,
          ),
          IconButton(
            icon: const Icon(Icons.alt_route_outlined),
            tooltip: 'Circuits Schedule',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => CircuitsScreen(
                    state: widget.state,
                    project: widget.project,
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          // Zoomable & Pannable Vector Architectural Canvas
          LayoutBuilder(
            builder: (context, constraints) {
              final canvasWidth =
                  constraints.maxWidth < 600 ? 760.0 : constraints.maxWidth;
              final canvasHeight =
                  constraints.maxWidth < 600 ? 600.0 : constraints.maxHeight;

              return InteractiveViewer(
                transformationController: _transformationController,
                minScale: 0.4,
                maxScale: 4.0,
                constrained: false,
                boundaryMargin: const EdgeInsets.all(300),
                child: Center(
                  child: Container(
                    width: canvasWidth,
                    height: canvasHeight,
                    decoration: BoxDecoration(
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.25),
                          blurRadius: 20,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: PlanDrawingViewer(
                      project: widget.project,
                      points: widget.state.electricalPoints,
                      selectedPoint: _selectedPoint,
                      activeLayer: _activeLayer,
                      isDark: isDark,
                      showPointsOverlay: true,
                      wiringArcs: widget.state.wiringArcs,
                      onPointTap: (point) {
                        setState(() => _selectedPoint = point);
                        widget.state.setInspectedPoint(point);
                      },
                      onPointPanUpdate: (point, newX, newY) {
                        widget.state.updatePointPosition(point.id, newX, newY);
                        setState(() {
                          _selectedPoint = widget.state.electricalPoints.firstWhere(
                            (p) => p.id == point.id,
                            orElse: () => point,
                          );
                        });
                      },
                    ),
                  ),
                ),
              );
            },
          ),

          // Top Layer Filter Bar
          Positioned(
            top: 12,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: (isDark ? AppColors.surfaceDark : AppColors.surfaceLight)
                    .withValues(alpha: 0.92),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? AppColors.borderDark : AppColors.borderLight,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 10,
                  ),
                ],
              ),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildLayerTab(
                      'all',
                      'All Symbols (${widget.state.electricalPoints.length})',
                      isDark,
                    ),
                    const SizedBox(width: 6),
                    _buildLayerTab('lighting', 'Lighting & Switches', isDark),
                    const SizedBox(width: 6),
                    _buildLayerTab('power', 'Power Sockets', isDark),
                    const SizedBox(width: 6),
                    _buildLayerTab('distribution', 'Main DB', isDark),
                  ],
                ),
              ),
            ),
          ),

          // Bottom Position Adjustment Toolbar (when point selected) or Navigation Hint (when none)
          Positioned(
            bottom: 16,
            left: 16,
            right: 16,
            child: _selectedPoint != null
                ? _buildNudgeToolbar(_selectedPoint!, isDark)
                : _buildHintBar(isDark),
          ),
        ],
      ),
    );
  }

  Widget _buildNudgeToolbar(ElectricalPoint point, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: (isDark ? AppColors.surfaceDark : AppColors.surfaceLight)
            .withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.primaryBlue.withValues(alpha: 0.6),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.18),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(point.type.icon, size: 16, color: AppColors.primaryBlue),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${point.label} • ${point.roomName}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primaryBlue.withValues(alpha: isDark ? 0.2 : 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'X: ${(point.xRatio * 100).toStringAsFixed(1)}%  Y: ${(point.yRatio * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: AppColors.primaryBlue,
                  ),
                ),
              ),
              const SizedBox(width: 4),
              IconButton(
                icon: const Icon(Icons.info_outline, size: 18),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                tooltip: 'Inspect Specifications',
                onPressed: () => _showPointInspectionBottomSheet(point),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 18),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                tooltip: 'Done',
                onPressed: () => setState(() => _selectedPoint = null),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Drag on canvas or nudge:',
                style: TextStyle(
                  fontSize: 11,
                  color: isDark ? AppColors.textSecondaryDark : AppColors.textSecondaryLight,
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildNudgeBtn(Icons.arrow_back, 'Left', () {
                    widget.state.nudgePoint(point.id, -0.006, 0);
                    _refreshSelectedPoint(point.id);
                  }, isDark),
                  const SizedBox(width: 4),
                  _buildNudgeBtn(Icons.arrow_upward, 'Up', () {
                    widget.state.nudgePoint(point.id, 0, -0.006);
                    _refreshSelectedPoint(point.id);
                  }, isDark),
                  const SizedBox(width: 4),
                  _buildNudgeBtn(Icons.arrow_downward, 'Down', () {
                    widget.state.nudgePoint(point.id, 0, 0.006);
                    _refreshSelectedPoint(point.id);
                  }, isDark),
                  const SizedBox(width: 4),
                  _buildNudgeBtn(Icons.arrow_forward, 'Right', () {
                    widget.state.nudgePoint(point.id, 0.006, 0);
                    _refreshSelectedPoint(point.id);
                  }, isDark),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _refreshSelectedPoint(String pointId) {
    setState(() {
      _selectedPoint = widget.state.electricalPoints.firstWhere(
        (p) => p.id == pointId,
        orElse: () => _selectedPoint!,
      );
    });
  }

  Widget _buildNudgeBtn(IconData icon, String tooltip, VoidCallback onTap, bool isDark) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.all(5),
        decoration: BoxDecoration(
          color: isDark ? AppColors.surfaceSecondaryDark : AppColors.surfaceSecondaryLight,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
          ),
        ),
        child: Icon(
          icon,
          size: 16,
          color: isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
        ),
      ),
    );
  }

  Widget _buildHintBar(bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: (isDark ? AppColors.surfaceDark : AppColors.surfaceLight)
            .withValues(alpha: 0.94),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Row(
              children: [
                const Icon(
                  Icons.touch_app_outlined,
                  size: 16,
                  color: AppColors.primaryBlue,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Drag anywhere to scroll/pan • Tap symbol to move & inspect • Pinch to zoom',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: isDark
                          ? AppColors.textSecondaryDark
                          : AppColors.textSecondaryLight,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          InkWell(
            onTap: _resetZoom,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 6,
                vertical: 2,
              ),
              child: Text(
                '100%',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: isDark
                      ? AppColors.textPrimaryDark
                      : AppColors.textPrimaryLight,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLayerTab(String layerKey, String label, bool isDark) {
    final isSelected = _activeLayer == layerKey;

    return InkWell(
      onTap: () => setState(() => _activeLayer = layerKey),
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primaryBlue
              : (isDark
                    ? AppColors.surfaceSecondaryDark
                    : AppColors.surfaceSecondaryLight),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
            color: isSelected
                ? Colors.white
                : (isDark
                      ? AppColors.textSecondaryDark
                      : AppColors.textSecondaryLight),
          ),
        ),
      ),
    );
  }
}

enum _IecBadgeType {
  ceilingLight,
  downlight,
  wallSwitch,
  twoWaySwitch,
  socketDouble,
  socketGfci,
  switchingLoop,
  distributionBoard,
  dedicatedAppliance,
}

class _IecSymbolBadge extends StatelessWidget {
  final _IecBadgeType type;
  final bool isDark;

  const _IecSymbolBadge({required this.type, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Center(
        child: CustomPaint(
          size: const Size(36, 36),
          painter: _IecBadgePainter(type: type, isDark: isDark),
        ),
      ),
    );
  }
}

class _IecBadgePainter extends CustomPainter {
  final _IecBadgeType type;
  final bool isDark;

  const _IecBadgePainter({required this.type, required this.isDark});

  @override
  void paint(Canvas canvas, Size size) {
    final strokeColor =
        isDark ? AppColors.textPrimaryDark : const Color(0xFF1E293B);
    final center = Offset(size.width / 2, size.height / 2);

    final strokePaint = Paint()
      ..color = strokeColor
      ..strokeWidth = 1.8
      ..style = PaintingStyle.stroke;

    final fillPaint = Paint()
      ..color = strokeColor
      ..style = PaintingStyle.fill;

    switch (type) {
      case _IecBadgeType.ceilingLight:
        const radius = 9.0;
        canvas.drawCircle(center, radius, strokePaint);
        const offset = radius * 0.7071;
        canvas.drawLine(
          Offset(center.dx - offset, center.dy - offset),
          Offset(center.dx + offset, center.dy + offset),
          strokePaint,
        );
        canvas.drawLine(
          Offset(center.dx - offset, center.dy + offset),
          Offset(center.dx + offset, center.dy - offset),
          strokePaint,
        );
        break;

      case _IecBadgeType.downlight:
        const radius = 8.5;
        canvas.drawCircle(center, radius, strokePaint);
        canvas.drawCircle(center, 3.2, fillPaint);
        break;

      case _IecBadgeType.wallSwitch:
        final swCenter = Offset(center.dx - 2, center.dy + 4);
        const radius = 5.0;
        canvas.drawCircle(swCenter, radius, strokePaint);
        const cos45 = 0.7071;
        const sin45 = 0.7071;
        const armLen = 11.0;
        final armEnd = Offset(
          swCenter.dx + (radius + armLen) * cos45,
          swCenter.dy - (radius + armLen) * sin45,
        );
        canvas.drawLine(
          Offset(swCenter.dx + radius * cos45, swCenter.dy - radius * sin45),
          armEnd,
          strokePaint,
        );
        canvas.drawLine(
          armEnd,
          Offset(armEnd.dx - 3.5 * sin45, armEnd.dy - 3.5 * cos45),
          strokePaint,
        );
        break;

      case _IecBadgeType.twoWaySwitch:
        const radius = 5.0;
        canvas.drawCircle(center, radius, strokePaint);
        const cos45 = 0.7071;
        const sin45 = 0.7071;
        const armLen = 8.5;
        // Arm 1 (upper right)
        final armEnd1 = Offset(
          center.dx + (radius + armLen) * cos45,
          center.dy - (radius + armLen) * sin45,
        );
        canvas.drawLine(
          Offset(center.dx + radius * cos45, center.dy - radius * sin45),
          armEnd1,
          strokePaint,
        );
        canvas.drawLine(
          armEnd1,
          Offset(armEnd1.dx - 3.0 * sin45, armEnd1.dy - 3.0 * cos45),
          strokePaint,
        );
        // Arm 2 (lower left)
        final armEnd2 = Offset(
          center.dx - (radius + armLen) * cos45,
          center.dy + (radius + armLen) * sin45,
        );
        canvas.drawLine(
          Offset(center.dx - radius * cos45, center.dy + radius * sin45),
          armEnd2,
          strokePaint,
        );
        canvas.drawLine(
          armEnd2,
          Offset(armEnd2.dx + 3.0 * sin45, armEnd2.dy + 3.0 * cos45),
          strokePaint,
        );
        break;

      case _IecBadgeType.socketDouble:
        final sockCenter = Offset(center.dx, center.dy + 4);
        const radius = 8.5;
        final arcRect = Rect.fromCircle(center: sockCenter, radius: radius);
        // baseline
        canvas.drawLine(
          Offset(sockCenter.dx - radius, sockCenter.dy),
          Offset(sockCenter.dx + radius, sockCenter.dy),
          strokePaint,
        );
        // curved arc
        canvas.drawArc(arcRect, math.pi, math.pi, false, strokePaint);
        // 2 radial tines
        const tineLen = 6.0;
        canvas.drawLine(
          Offset(sockCenter.dx - 4.0, sockCenter.dy - radius),
          Offset(sockCenter.dx - 4.0, sockCenter.dy - radius - tineLen),
          strokePaint,
        );
        canvas.drawLine(
          Offset(sockCenter.dx + 4.0, sockCenter.dy - radius),
          Offset(sockCenter.dx + 4.0, sockCenter.dy - radius - tineLen),
          strokePaint,
        );
        break;

      case _IecBadgeType.socketGfci:
        final sockCenter = Offset(center.dx - 5, center.dy + 4);
        const radius = 7.5;
        final arcRect = Rect.fromCircle(center: sockCenter, radius: radius);
        canvas.drawLine(
          Offset(sockCenter.dx - radius, sockCenter.dy),
          Offset(sockCenter.dx + radius, sockCenter.dy),
          strokePaint,
        );
        canvas.drawArc(arcRect, math.pi, math.pi, false, strokePaint);
        const tineLen = 5.0;
        canvas.drawLine(
          Offset(sockCenter.dx - 3.0, sockCenter.dy - radius),
          Offset(sockCenter.dx - 3.0, sockCenter.dy - radius - tineLen),
          strokePaint,
        );
        canvas.drawLine(
          Offset(sockCenter.dx + 3.0, sockCenter.dy - radius),
          Offset(sockCenter.dx + 3.0, sockCenter.dy - radius - tineLen),
          strokePaint,
        );
        final textSpan = TextSpan(
          text: 'GFCI',
          style: TextStyle(
            color: isDark ? AppColors.accentCyan : const Color(0xFF0284C7),
            fontSize: 7.5,
            fontWeight: FontWeight.w900,
          ),
        );
        final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
        tp.paint(canvas, Offset(sockCenter.dx + radius + 1, sockCenter.dy - radius - 2));
        break;

      case _IecBadgeType.switchingLoop:
        final loopPaint = Paint()
          ..color = isDark ? AppColors.accentCyan : const Color(0xFF0284C7)
          ..strokeWidth = 1.6
          ..style = PaintingStyle.stroke;
        final path = Path()
          ..moveTo(6, 26)
          ..quadraticBezierTo(14, 4, 30, 10);
        for (final metric in path.computeMetrics()) {
          double dist = 0.0;
          while (dist < metric.length) {
            final len = math.min(4.0, metric.length - dist);
            canvas.drawPath(metric.extractPath(dist, dist + len), loopPaint);
            dist += 4.0 + 3.0;
          }
        }
        canvas.drawCircle(const Offset(6, 26), 2.0, fillPaint);
        canvas.drawCircle(const Offset(30, 10), 2.0, fillPaint);
        break;

      case _IecBadgeType.distributionBoard:
        const dbW = 28.0;
        const dbH = 12.0;
        final dbRect = Rect.fromCenter(
            center: Offset(center.dx, center.dy - 3), width: dbW, height: dbH);
        final dbPath = Path()
          ..moveTo(dbRect.left, dbRect.top)
          ..lineTo(dbRect.right, dbRect.top)
          ..lineTo(dbRect.left, dbRect.bottom)
          ..close();
        canvas.drawPath(dbPath, fillPaint);
        canvas.drawRect(dbRect, strokePaint);
        final dbText = TextSpan(
          text: 'DB',
          style: TextStyle(
            color: strokeColor,
            fontSize: 8.5,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.5,
          ),
        );
        final dbTp = TextPainter(text: dbText, textDirection: TextDirection.ltr)..layout();
        dbTp.paint(canvas, Offset(center.dx - (dbTp.width / 2), dbRect.bottom + 1.5));
        break;

      case _IecBadgeType.dedicatedAppliance:
        final appRect = RRect.fromRectAndRadius(
          Rect.fromCenter(center: center, width: 26, height: 22),
          const Radius.circular(4),
        );
        canvas.drawRRect(appRect, strokePaint);
        final appText = TextSpan(
          text: 'C',
          style: TextStyle(
            color: strokeColor,
            fontSize: 12.0,
            fontWeight: FontWeight.w800,
          ),
        );
        final appTp = TextPainter(text: appText, textDirection: TextDirection.ltr)..layout();
        appTp.paint(canvas, Offset(center.dx - (appTp.width / 2), center.dy - (appTp.height / 2)));
        break;
    }
  }

  @override
  bool shouldRepaint(covariant _IecBadgePainter oldDelegate) =>
      oldDelegate.type != type || oldDelegate.isDark != isDark;
}

