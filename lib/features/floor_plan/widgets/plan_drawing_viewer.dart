import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/models/electrical_point.dart';
import '../../../shared/models/project.dart';
import '../../../shared/models/wiring_arc.dart';
import 'floor_plan_painter.dart';

class PlanDrawingViewer extends StatefulWidget {
  final Project project;
  final List<ElectricalPoint> points;
  final bool isDark;
  final String activeLayer;
  final ElectricalPoint? selectedPoint;
  final bool showPointsOverlay;
  final List<WiringArc>? wiringArcs;
  final void Function(ElectricalPoint point)? onPointTap;
  final void Function(ElectricalPoint point, double newX, double newY)? onPointPanUpdate;

  const PlanDrawingViewer({
    super.key,
    required this.project,
    this.points = const [],
    required this.isDark,
    this.activeLayer = 'all',
    this.selectedPoint,
    this.showPointsOverlay = true,
    this.wiringArcs,
    this.onPointTap,
    this.onPointPanUpdate,
  });

  @override
  State<PlanDrawingViewer> createState() => _PlanDrawingViewerState();
}

class _PlanDrawingViewerState extends State<PlanDrawingViewer> {
  ImageProvider? _imageProvider;
  double _aspectRatio = 800.0 / 650.0;
  bool _hasImage = false;
  bool _isLoading = false;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _setupImageProvider();
  }

  @override
  void didUpdateWidget(covariant PlanDrawingViewer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.project.id != oldWidget.project.id ||
        widget.project.floorPlanBytes != oldWidget.project.floorPlanBytes ||
        widget.project.floorPlanName != oldWidget.project.floorPlanName) {
      _setupImageProvider();
    }
  }

  bool get _isPdf =>
      widget.project.floorPlanName?.toLowerCase().endsWith('.pdf') ?? false;

  void _setupImageProvider() {
    final bool hasDirectImageBytes = widget.project.floorPlanBytes != null &&
        widget.project.floorPlanBytes!.isNotEmpty &&
        !_isPdf;

    if (hasDirectImageBytes) {
      _imageProvider = MemoryImage(widget.project.floorPlanBytes!);
      _hasImage = true;
      _hasError = false;
      _resolveAspectRatio();
    } else if (widget.project.floorPlanName != null &&
        widget.project.id.isNotEmpty) {
      final url = ApiEndpoints.projectPlanFile(widget.project.id);
      _imageProvider = NetworkImage(url);
      _hasImage = true;
      _hasError = false;
      _resolveAspectRatio();
    } else {
      _imageProvider = null;
      _hasImage = false;
      _aspectRatio = 800.0 / 650.0;
    }
  }

  void _resolveAspectRatio() {
    if (_imageProvider == null) return;
    _isLoading = true;

    final ImageStream stream =
        _imageProvider!.resolve(const ImageConfiguration());
    ImageStreamListener? listener;

    listener = ImageStreamListener(
      (ImageInfo info, bool synchronousCall) {
        if (!mounted) return;
        final int w = info.image.width;
        final int h = info.image.height;
        if (w > 0 && h > 0) {
          setState(() {
            _aspectRatio = w / h;
            _isLoading = false;
            _hasError = false;
          });
        }
      },
      onError: (dynamic error, StackTrace? stackTrace) {
        if (!mounted) return;
        setState(() {
          _isLoading = false;
          _hasError = true;
        });
      },
    );

    stream.addListener(listener);
  }

  void _handlePointTap(TapUpDetails details, Size size) {
    if (widget.points.isEmpty || widget.onPointTap == null) return;

    final tapOffset = details.localPosition;
    ElectricalPoint? hitPoint;
    double minDistance = 28.0; // hit test radius in logical pixels

    for (final pt in widget.points) {
      final ptOffset = Offset(
        pt.xRatio * size.width,
        pt.yRatio * size.height,
      );
      final dist = (tapOffset - ptOffset).distance;
      if (dist < minDistance) {
        minDistance = dist;
        hitPoint = pt;
      }
    }

    if (hitPoint != null) {
      widget.onPointTap!(hitPoint);
    }
  }


  @override
  Widget build(BuildContext context) {
    // 1. Fallback to vector blueprint when no plan uploaded or loading error
    if (!_hasImage || _imageProvider == null || _hasError) {
      return _buildFallbackVector();
    }

    // 2. Render real drawing with strict aspect ratio matching
    // This ensures electrical points map 1:1 onto the architectural drawing,
    // with ZERO letterbox floating symbols outside the plan canvas.
    return Center(
      child: AspectRatio(
        aspectRatio: _aspectRatio,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final canvasSize = constraints.biggest;

            return GestureDetector(
              behavior: HitTestBehavior.translucent,
              onTapUp: widget.onPointTap != null
                  ? (details) => _handlePointTap(details, canvasSize)
                  : null,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  // Architectural Drawing
                  Container(
                    color: widget.isDark
                        ? const Color(0xFF0D131F)
                        : const Color(0xFFF8FAFC),
                    child: Image(
                      image: _imageProvider!,
                      fit: BoxFit.fill,
                      errorBuilder: (context, error, stackTrace) {
                        if (_isPdf) {
                          return _buildPdfDocumentPlaceholder();
                        }
                        return _buildFallbackVector();
                      },
                    ),
                  ),

                  // Loading Overlay
                  if (_isLoading)
                    Positioned.fill(
                      child: Container(
                        color: (widget.isDark
                                ? AppColors.surfaceDark
                                : AppColors.surfaceLight)
                            .withValues(alpha: 0.6),
                        child: Center(
                          child: SizedBox(
                            width: 28,
                            height: 28,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                AppColors.primaryBlue,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),

                  // Electrical Points Overlay (Locked 1:1 to Plan Boundaries)
                  if (widget.showPointsOverlay && widget.points.isNotEmpty)
                    Positioned.fill(
                      child: CustomPaint(
                        size: canvasSize,
                        painter: FloorPlanPainter(
                          points: widget.points,
                          selectedPoint: widget.selectedPoint,
                          activeLayer: widget.activeLayer,
                          isDark: widget.isDark,
                          showBackground: false,
                          wiringArcs: widget.wiringArcs,
                        ),
                      ),
                    ),

                  // Interactive Drag Handle on Selected Point
                  if (widget.selectedPoint != null && widget.onPointPanUpdate != null)
                    _buildSelectedDragHandle(widget.selectedPoint!, canvasSize),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildSelectedDragHandle(ElectricalPoint pt, Size canvasSize) {
    const handleSize = 44.0;
    final px = pt.xRatio * canvasSize.width;
    final py = pt.yRatio * canvasSize.height;

    return Positioned(
      left: px - (handleSize / 2),
      top: py - (handleSize / 2),
      width: handleSize,
      height: handleSize,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onPanUpdate: (details) {
          final curPx = pt.xRatio * canvasSize.width;
          final curPy = pt.yRatio * canvasSize.height;
          final newX = ((curPx + details.delta.dx) / canvasSize.width).clamp(0.015, 0.985);
          final newY = ((curPy + details.delta.dy) / canvasSize.height).clamp(0.015, 0.985);
          widget.onPointPanUpdate!(pt, newX, newY);
        },
        child: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.primaryBlue, width: 2.2),
            color: AppColors.primaryBlue.withValues(alpha: 0.22),
            boxShadow: [
              BoxShadow(
                color: AppColors.primaryBlue.withValues(alpha: 0.35),
                blurRadius: 8,
                spreadRadius: 1,
              ),
            ],
          ),
          child: const Center(
            child: Icon(
              Icons.open_with_rounded,
              size: 20,
              color: Colors.white,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFallbackVector() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final canvasSize = constraints.biggest;
        return GestureDetector(
          behavior: HitTestBehavior.translucent,
          onTapUp: widget.onPointTap != null
              ? (details) => _handlePointTap(details, canvasSize)
              : null,
          child: Stack(
            fit: StackFit.expand,
            children: [
              CustomPaint(
                size: canvasSize,
                painter: FloorPlanPainter(
                  points: widget.showPointsOverlay ? widget.points : const [],
                  selectedPoint: widget.selectedPoint,
                  activeLayer: widget.activeLayer,
                  isDark: widget.isDark,
                  showBackground: true,
                  wiringArcs: widget.wiringArcs,
                ),
              ),
              if (widget.selectedPoint != null && widget.onPointPanUpdate != null)
                _buildSelectedDragHandle(widget.selectedPoint!, canvasSize),
            ],
          ),
        );
      },
    );
  }

  Widget _buildPdfDocumentPlaceholder() {
    return Container(
      color: widget.isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
      padding: const EdgeInsets.all(20),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.picture_as_pdf,
                size: 36,
                color: Colors.redAccent,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              widget.project.floorPlanName ?? 'Architectural Plan (PDF)',
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: widget.isDark
                    ? AppColors.textPrimaryDark
                    : AppColors.textPrimaryLight,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Rendering document with AI Vision processing...',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                color: widget.isDark
                    ? AppColors.textMutedDark
                    : AppColors.textMutedLight,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
