import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/widgets/app_button.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import '../analysis/ai_analysis_screen.dart';

enum ScaleUnit {
  metres('m', 1000),
  millimetres('mm', 1);

  final String label;
  final double toMm;
  const ScaleUnit(this.label, this.toMm);
}

/// Converts user input in [unit] to millimetres. Returns null when the input
/// is not a positive number.
double? parseDistanceMm(String text, ScaleUnit unit) {
  final value = double.tryParse(text.trim().replaceAll(',', '.'));
  if (value == null || !value.isFinite || value <= 0) return null;
  return value * unit.toMm;
}

/// Lets the user mark two points on the uploaded plan and enter the real
/// distance between them, so the backend can verify the drawing scale.
class ScaleCalibrationScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  /// When true (opened from an existing project) the screen pops with `true`
  /// after saving instead of continuing into AI analysis.
  final bool returnToCaller;

  const ScaleCalibrationScreen({
    super.key,
    required this.state,
    required this.project,
    this.returnToCaller = false,
  });

  @override
  State<ScaleCalibrationScreen> createState() => _ScaleCalibrationScreenState();
}

class _ScaleCalibrationScreenState extends State<ScaleCalibrationScreen> {
  final TextEditingController _distanceController = TextEditingController();
  ScaleUnit _unit = ScaleUnit.metres;
  Offset? _pointA; // image ratios 0-1
  Offset? _pointB;
  double? _aspectRatio;
  bool _imageFailed = false;
  bool _isSaving = false;
  String? _error;

  late final String _imageUrl = ApiEndpoints.projectPlanFile(widget.project.id);

  @override
  void initState() {
    super.initState();
    final stream = NetworkImage(_imageUrl, headers: ApiEndpoints.authHeaders).resolve(const ImageConfiguration());
    late final ImageStreamListener listener;
    listener = ImageStreamListener(
      (info, _) {
        if (mounted) {
          setState(() => _aspectRatio = info.image.width / info.image.height);
        }
        stream.removeListener(listener);
      },
      onError: (_, _) {
        if (mounted) setState(() => _imageFailed = true);
        stream.removeListener(listener);
      },
    );
    stream.addListener(listener);
  }

  @override
  void dispose() {
    _distanceController.dispose();
    super.dispose();
  }

  void _onTap(Offset local, Size size) {
    if (_isSaving) return;
    final p = Offset(
      (local.dx / size.width).clamp(0.0, 1.0),
      (local.dy / size.height).clamp(0.0, 1.0),
    );
    setState(() {
      _error = null;
      if (_pointA == null || _pointB != null) {
        _pointA = p;
        _pointB = null;
      } else {
        _pointB = p;
      }
    });
  }

  void _reset() => setState(() {
        _pointA = null;
        _pointB = null;
        _error = null;
      });

  bool get _canSave =>
      _pointA != null &&
      _pointB != null &&
      parseDistanceMm(_distanceController.text, _unit) != null;

  void _continueToAnalysis({bool saved = false}) {
    if (widget.returnToCaller) {
      Navigator.pop(context, saved);
      return;
    }
    final project = widget.state.selectedProject ?? widget.project;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => AiAnalysisScreen(state: widget.state, project: project),
      ),
    );
  }

  Future<void> _save() async {
    final mm = parseDistanceMm(_distanceController.text, _unit);
    if (_pointA == null || _pointB == null || mm == null) return;

    setState(() {
      _isSaving = true;
      _error = null;
    });
    final error = await widget.state.calibrateProjectScale(
      projectId: widget.project.id,
      ax: _pointA!.dx,
      ay: _pointA!.dy,
      bx: _pointB!.dx,
      by: _pointB!.dy,
      realDistanceMm: mm,
    );
    if (!mounted) return;
    if (error != null) {
      setState(() {
        _isSaving = false;
        _error = error;
      });
      return;
    }
    setState(() => _isSaving = false);
    _continueToAnalysis(saved: true);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final secondary =
        isDark ? AppColors.textSecondaryDark : AppColors.textSecondaryLight;

    final instruction = _pointA == null
        ? 'Tap the first end of a dimension you know (e.g. a dimensioned wall).'
        : _pointB == null
            ? 'Now tap the second end of that dimension.'
            : 'Enter the real distance between the two points.';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Calibrate Plan Scale'),
        actions: [
          TextButton(
            onPressed: _isSaving ? null : _continueToAnalysis,
            child: Text(widget.returnToCaller ? 'Cancel' : 'Skip'),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      instruction,
                      style: TextStyle(fontSize: 14, color: secondary),
                    ),
                  ),
                  if (_pointA != null)
                    IconButton(
                      tooltip: 'Reset points',
                      onPressed: _isSaving ? null : _reset,
                      icon: const Icon(Icons.refresh),
                    ),
                ],
              ),
            ),
            Expanded(child: _buildPlan(isDark)),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _distanceController,
                          enabled: !_isSaving,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          onChanged: (_) => setState(() => _error = null),
                          decoration: const InputDecoration(
                            labelText: 'Real distance',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      SegmentedButton<ScaleUnit>(
                        segments: [
                          for (final u in ScaleUnit.values)
                            ButtonSegment(value: u, label: Text(u.label)),
                        ],
                        selected: {_unit},
                        onSelectionChanged: _isSaving
                            ? null
                            : (s) => setState(() => _unit = s.first),
                      ),
                    ],
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _error!,
                      style: const TextStyle(color: Colors.red, fontSize: 13),
                    ),
                  ],
                  const SizedBox(height: 12),
                  AppButton(
                    label: widget.returnToCaller
                        ? 'Save Scale'
                        : 'Save Scale & Continue',
                    icon: Icons.straighten,
                    isLoading: _isSaving,
                    onPressed: _canSave ? _save : null,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Without a calibrated scale, positions and areas stay marked as unverified estimates.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: secondary),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlan(bool isDark) {
    if (_imageFailed) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'The plan image could not be loaded from the server. '
            'Check the connection, or skip calibration for now.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    final aspect = _aspectRatio;
    if (aspect == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return Container(
      color: isDark ? AppColors.surfaceDark : AppColors.surfaceSecondaryLight,
      child: InteractiveViewer(
        minScale: 1,
        maxScale: 6,
        child: Center(
          child: AspectRatio(
            aspectRatio: aspect,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final size = constraints.biggest;
                return GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapUp: (d) => _onTap(d.localPosition, size),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.network(_imageUrl, headers: ApiEndpoints.authHeaders, fit: BoxFit.fill),
                      CustomPaint(
                        painter: _ReferencePainter(_pointA, _pointB),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _ReferencePainter extends CustomPainter {
  final Offset? a;
  final Offset? b;

  _ReferencePainter(this.a, this.b);

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = AppColors.primaryBlue
      ..strokeWidth = 2;
    final fill = Paint()..color = AppColors.primaryBlue;
    final ring = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    Offset px(Offset r) => Offset(r.dx * size.width, r.dy * size.height);

    if (a != null && b != null) {
      canvas.drawLine(px(a!), px(b!), line);
    }
    for (final p in [a, b]) {
      if (p == null) continue;
      canvas.drawCircle(px(p), 6, fill);
      canvas.drawCircle(px(p), 6, ring);
    }
  }

  @override
  bool shouldRepaint(_ReferencePainter old) => old.a != a || old.b != b;
}
