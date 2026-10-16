import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/engineering_sheet.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/models/electrical_point.dart';
import '../../shared/state/app_state.dart';
import '../floor_plan/geometry_editor_screen.dart';
import '../floor_plan/widgets/floor_plan_painter.dart';
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
  String? _selectedId;

  // Manual equipment editing
  bool _editMode = false;
  bool _busy = false;
  String? _armedTypeId; // equipment type armed for placement
  String? _dragId;
  Offset? _dragOrigin;

  String get _projectId => (widget.state.selectedProject ?? widget.project).id;

  /// Always resolved from the live list so it reflects backend refreshes.
  ElectricalPoint? get _selectedPoint {
    final id = _selectedId;
    if (id == null) return null;
    for (final p in widget.state.electricalPoints) {
      if (p.id == id) return p;
    }
    return null;
  }

  void _toast(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: error ? Colors.red.shade700 : null,
          duration: Duration(seconds: error ? 5 : 2),
        ),
      );
  }

  void _toggleEditMode() {
    setState(() {
      _editMode = !_editMode;
      _armedTypeId = null;
    });
    if (_editMode) widget.state.loadEquipmentCatalog();
  }

  Future<void> _runEdit(
    Future<String?> Function() action, {
    String? success,
  }) async {
    if (_busy) return;
    setState(() => _busy = true);
    final error = await action();
    if (!mounted) return;
    setState(() => _busy = false);
    if (error != null) {
      _toast(error, error: true);
    } else if (success != null) {
      _toast(success);
    }
  }

  void _onPlanTapEdit(double x, double y, ElectricalPoint? hit) {
    if (_busy) return;
    final armed = _armedTypeId;
    if (armed != null) {
      final catalog = widget.state.equipmentCatalog;
      final name =
          catalog
              .where((o) => o.typeId == armed)
              .map((o) => o.name)
              .firstOrNull ??
          armed;
      _runEdit(
        () => widget.state.addElectricalPoint(_projectId, armed, x, y),
        success: '$name placed. Circuits, BOQ and cost updated.',
      );
      return;
    }
    setState(() => _selectedId = hit?.id);
  }

  void _onDragUpdate(ElectricalPoint point, double x, double y) {
    if (_busy) return;
    if (_dragId != point.id) {
      _dragId = point.id;
      _dragOrigin = Offset(point.xRatio, point.yRatio);
    }
    widget.state.updatePointPosition(point.id, x, y);
    setState(() {});
  }

  Future<void> _onDragEnd(ElectricalPoint _) async {
    final id = _dragId;
    final origin = _dragOrigin;
    _dragId = null;
    _dragOrigin = null;
    if (id == null || origin == null || _busy) return;

    ElectricalPoint? current;
    for (final p in widget.state.electricalPoints) {
      if (p.id == id) current = p;
    }
    if (current == null) return;

    final x = current.xRatio;
    final y = current.yRatio;
    setState(() => _busy = true);
    final error = await widget.state.moveElectricalPoint(_projectId, id, x, y);
    if (!mounted) return;
    setState(() => _busy = false);
    if (error != null) {
      // The backend rejected the new position: snap back to where it was.
      widget.state.updatePointPosition(id, origin.dx, origin.dy);
      setState(() {});
      _toast(error, error: true);
    }
  }

  void _nudgeSelected(double dx, double dy) {
    final point = _selectedPoint;
    if (point == null) return;
    _runEdit(
      () => widget.state.moveElectricalPoint(
        _projectId,
        point.id,
        (point.xRatio + dx).clamp(0.0, 1.0),
        (point.yRatio + dy).clamp(0.0, 1.0),
      ),
    );
  }

  Future<void> _deleteSelected() async {
    final point = _selectedPoint;
    if (point == null || _busy) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete equipment?'),
        content: Text(
          'Remove ${point.label} from ${point.roomName}? '
          'Circuits, BOQ and cost will be regenerated.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _runEdit(
      () => widget.state.deleteElectricalPoint(_projectId, point.id),
      success: '${point.label} deleted.',
    );
    if (mounted) setState(() => _selectedId = null);
  }

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
      subtitle:
          '${widget.project.standard} Installation Guidelines (IEC 60617 / ANSI)',
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
                    color: isDark
                        ? AppColors.accentCyan
                        : const Color(0xFF0284C7),
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
                  padding: const EdgeInsets.symmetric(
                    horizontal: 7,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primaryBlue.withValues(
                      alpha: isDark ? 0.2 : 0.08,
                    ),
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
            icon: const Icon(Icons.meeting_room_outlined),
            tooltip: 'Fix rooms & doors',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => GeometryEditorScreen(
                  state: widget.state,
                  project: widget.project,
                ),
              ),
            ),
          ),
          IconButton(
            icon: Icon(
              _editMode ? Icons.edit_off_outlined : Icons.edit_outlined,
            ),
            tooltip: _editMode
                ? 'Exit component editing'
                : 'Add / edit components',
            onPressed: _toggleEditMode,
          ),
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
              final canvasWidth = constraints.maxWidth < 600
                  ? 760.0
                  : constraints.maxWidth;
              final canvasHeight = constraints.maxWidth < 600
                  ? 600.0
                  : constraints.maxHeight;

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
                      onPointTap: _editMode
                          ? null
                          : (point) {
                              setState(() => _selectedId = point.id);
                              widget.state.setInspectedPoint(point);
                            },
                      onPlanTap: _editMode ? _onPlanTapEdit : null,
                      onPointPanUpdate: _editMode ? _onDragUpdate : null,
                      onPointPanEnd: _editMode ? _onDragEnd : null,
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
                    _buildLayerTab('safety', 'Safety & Comms', isDark),
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
            child: _editMode
                ? _buildEditPanel(isDark)
                : (_selectedPoint != null
                      ? _buildNudgeToolbar(_selectedPoint!, isDark)
                      : _buildHintBar(isDark)),
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
                    color: isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primaryBlue.withValues(
                    alpha: isDark ? 0.2 : 0.1,
                  ),
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
                onPressed: () => setState(() => _selectedId = null),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEditPanel(bool isDark) {
    final point = _selectedPoint;
    final catalog = widget.state.equipmentCatalog;
    final muted = isDark
        ? AppColors.textSecondaryDark
        : AppColors.textSecondaryLight;

    String instruction;
    if (_armedTypeId != null) {
      final name =
          catalog
              .where((o) => o.typeId == _armedTypeId)
              .map((o) => o.name)
              .firstOrNull ??
          _armedTypeId!;
      instruction = 'Tap inside a room to place: $name';
    } else if (point != null) {
      instruction =
          '${point.label} • ${point.roomName}${point.isManual ? ' • manual' : ''}';
    } else {
      instruction =
          'Tap a symbol to select it, or choose a catalog item below to add it.';
    }

    return Container(
      key: const Key('equipment-edit-panel'),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: BoxDecoration(
        color: (isDark ? AppColors.surfaceDark : AppColors.surfaceLight)
            .withValues(alpha: 0.97),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: FloorPlanPainter.manualColor, width: 1.5),
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
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          Row(
            children: [
              const Icon(
                Icons.edit_outlined,
                size: 16,
                color: FloorPlanPainter.manualColor,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  instruction,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight,
                  ),
                ),
              ),
              if (point != null && _armedTypeId == null) ...[
                _buildNudgeBtn(
                  Icons.arrow_back,
                  'Nudge left',
                  () => _nudgeSelected(-0.01, 0),
                  isDark,
                ),
                const SizedBox(width: 4),
                _buildNudgeBtn(
                  Icons.arrow_upward,
                  'Nudge up',
                  () => _nudgeSelected(0, -0.01),
                  isDark,
                ),
                const SizedBox(width: 4),
                _buildNudgeBtn(
                  Icons.arrow_downward,
                  'Nudge down',
                  () => _nudgeSelected(0, 0.01),
                  isDark,
                ),
                const SizedBox(width: 4),
                _buildNudgeBtn(
                  Icons.arrow_forward,
                  'Nudge right',
                  () => _nudgeSelected(0.01, 0),
                  isDark,
                ),
                const SizedBox(width: 6),
                IconButton(
                  key: const Key('delete-point-button'),
                  icon: const Icon(
                    Icons.delete_outline,
                    size: 20,
                    color: Colors.red,
                  ),
                  tooltip: 'Delete selected equipment',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 32,
                    minHeight: 32,
                  ),
                  onPressed: _busy ? null : _deleteSelected,
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Add component from catalog',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: 4),
          SizedBox(
            height: 36,
            child: catalog.isEmpty
                ? Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'No components are available in the catalog.',
                      style: TextStyle(fontSize: 11, color: muted),
                    ),
                  )
                : ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: catalog.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 6),
                    itemBuilder: (context, i) {
                      final option = catalog[i];
                      final armed = _armedTypeId == option.typeId;
                      return ChoiceChip(
                        key: Key('equipment-chip-${option.typeId}'),
                        avatar: Icon(option.pointType.icon, size: 16),
                        label: Text(
                          option.name,
                          style: const TextStyle(fontSize: 12),
                        ),
                        selected: armed,
                        onSelected: _busy
                            ? null
                            : (on) => setState(() {
                                _armedTypeId = on ? option.typeId : null;
                                if (on) _selectedId = null;
                              }),
                      );
                    },
                  ),
          ),
          const SizedBox(height: 4),
          Text(
            'Drag the highlighted handle to move • dashed amber ring = manual point (kept on re-analysis)',
            style: TextStyle(fontSize: 10.5, color: muted),
          ),
        ],
      ),
    );
  }

  Widget _buildNudgeBtn(
    IconData icon,
    String tooltip,
    VoidCallback onTap,
    bool isDark,
  ) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.all(5),
        decoration: BoxDecoration(
          color: isDark
              ? AppColors.surfaceSecondaryDark
              : AppColors.surfaceSecondaryLight,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
          ),
        ),
        child: Icon(
          icon,
          size: 16,
          color: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
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
                    'Drag to pan • Tap a symbol to inspect • Pinch to zoom • Pencil icon edits equipment',
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
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
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
    final strokeColor = isDark
        ? AppColors.textPrimaryDark
        : const Color(0xFF1E293B);
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
        final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)
          ..layout();
        tp.paint(
          canvas,
          Offset(sockCenter.dx + radius + 1, sockCenter.dy - radius - 2),
        );
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
          center: Offset(center.dx, center.dy - 3),
          width: dbW,
          height: dbH,
        );
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
        final dbTp = TextPainter(text: dbText, textDirection: TextDirection.ltr)
          ..layout();
        dbTp.paint(
          canvas,
          Offset(center.dx - (dbTp.width / 2), dbRect.bottom + 1.5),
        );
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
        final appTp = TextPainter(
          text: appText,
          textDirection: TextDirection.ltr,
        )..layout();
        appTp.paint(
          canvas,
          Offset(center.dx - (appTp.width / 2), center.dy - (appTp.height / 2)),
        );
        break;
    }
  }

  @override
  bool shouldRepaint(covariant _IecBadgePainter oldDelegate) =>
      oldDelegate.type != type || oldDelegate.isDark != isDark;
}
