import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import '../floor_plan/widgets/floor_plan_painter.dart';
import '../electrical/electrical_recommendations_screen.dart';

class AiAnalysisScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  const AiAnalysisScreen({
    super.key,
    required this.state,
    required this.project,
  });

  @override
  State<AiAnalysisScreen> createState() => _AiAnalysisScreenState();
}

class _AiAnalysisScreenState extends State<AiAnalysisScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!widget.state.isAnalysisFinished && !widget.state.isAnalyzing) {
        widget.state.runRealAnalysis(widget.project.id);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) {
        final isFinished = widget.state.isAnalysisFinished;
        final isAnalyzing = widget.state.isAnalyzing;
        final stage = widget.state.analysisStage;
        final error = widget.state.analysisErrorMessage;

        final rooms = widget.state.rooms;
        final points = widget.state.electricalPoints;
        final circuits = widget.state.circuits;
        final features = widget.state.architecturalFeatures;
        final warnings = widget.state.analysisWarnings;
        final hasPlanBytes = widget.project.floorPlanBytes != null &&
            widget.project.floorPlanBytes!.isNotEmpty;

        return Scaffold(
          appBar: AppBar(
            title: Text(
              isFinished ? 'Analysis Complete' : 'Analyzing Floor Plan',
            ),
            actions: [
              if (isFinished || error != null)
                TextButton.icon(
                  onPressed: () {
                    widget.state.runRealAnalysis(widget.project.id);
                  },
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text(
                    'Re-analyze',
                    style: TextStyle(color: AppColors.primaryBlue),
                  ),
                ),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Plan Preview Thumbnail with Electrical Overlay
                  Container(
                    height: 200,
                    decoration: BoxDecoration(
                      color: isDark
                          ? AppColors.surfaceDark
                          : AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isDark
                            ? AppColors.borderDark
                            : AppColors.borderLight,
                      ),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Stack(
                        children: [
                          if (hasPlanBytes)
                            Positioned.fill(
                              child: Image.memory(
                                widget.project.floorPlanBytes!,
                                fit: BoxFit.contain,
                                errorBuilder: (context, error, stackTrace) =>
                                    const SizedBox(),
                              ),
                            ),
                          Positioned.fill(
                            child: CustomPaint(
                              painter: FloorPlanPainter(
                                points: isFinished ? points : const [],
                                isDark: isDark,
                                activeLayer: 'all',
                                showBackground: !hasPlanBytes,
                                wiringArcs: isFinished ? widget.state.wiringArcs : null,
                              ),
                            ),
                          ),
                          if (isAnalyzing)
                            Positioned.fill(
                              child: Container(
                                color: (isDark ? Colors.black : Colors.white)
                                    .withValues(alpha: 0.45),
                                child: Center(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 16,
                                      vertical: 10,
                                    ),
                                    decoration: BoxDecoration(
                                      color: isDark
                                          ? AppColors.surfaceDark
                                          : AppColors.surfaceLight,
                                      borderRadius: BorderRadius.circular(20),
                                      border: Border.all(
                                        color: isDark
                                            ? AppColors.borderDark
                                            : AppColors.borderLight,
                                      ),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        const SizedBox(
                                          width: 16,
                                          height: 16,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            valueColor:
                                                AlwaysStoppedAnimation<Color>(
                                              AppColors.primaryBlue,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 10),
                                        Text(
                                          'Processing architectural plan...',
                                          style: TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w600,
                                            color: isDark
                                                ? AppColors.textPrimaryDark
                                                : AppColors.textPrimaryLight,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Error Display if any
                  if (error != null) ...[
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: Colors.red.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.error_outline,
                              color: Colors.red, size: 20),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Analysis Error',
                                  style: TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: Colors.red,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  error,
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: isDark
                                        ? AppColors.textSecondaryDark
                                        : AppColors.textSecondaryLight,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                ElevatedButton.icon(
                                  onPressed: () {
                                    widget.state
                                        .runRealAnalysis(widget.project.id);
                                  },
                                  icon: const Icon(Icons.refresh, size: 14),
                                  label: const Text('Retry Analysis'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.red,
                                    foregroundColor: Colors.white,
                                    visualDensity: VisualDensity.compact,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Stage Progression Stepper Card
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: isDark
                          ? AppColors.surfaceDark
                          : AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: isDark
                            ? AppColors.borderDark
                            : AppColors.borderLight,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              isFinished
                                  ? 'Analysis Pipeline Completed'
                                  : 'AI Vision Pipeline in Progress',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                letterSpacing: -0.2,
                                color: isDark
                                    ? AppColors.textPrimaryDark
                                    : AppColors.textPrimaryLight,
                              ),
                            ),
                            StatusBadge(
                              status: isFinished ? 'Completed' : 'Processing',
                              isSmall: true,
                            ),
                          ],
                        ),
                        if (widget.state.analysisStatusMessage.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            widget.state.analysisStatusMessage,
                            style: TextStyle(
                              fontSize: 13,
                              color: AppColors.primaryBlue,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                        const SizedBox(height: 16),
                        _buildStageRow(
                          'Step 1: Document preparation & page rasterization',
                          1,
                          stage,
                          isDark,
                        ),
                        _buildStageRow(
                          'Step 2: AI Vision architectural rooms extraction',
                          2,
                          stage,
                          isDark,
                        ),
                        _buildStageRow(
                          'Step 3: RS IEC 60364 electrical points engineering',
                          3,
                          stage,
                          isDark,
                        ),
                        _buildStageRow(
                          'Step 4: Circuit grouping & phase balancing (L1, L2, L3)',
                          4,
                          stage,
                          isDark,
                        ),
                        _buildStageRow(
                          'Step 5: Dynamic BOQ & Rwandan cost estimate (RWF)',
                          5,
                          stage,
                          isDark,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Results Summary when Finished
                  if (isFinished) ...[
                    // Key metrics
                    Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: isDark
                            ? AppColors.surfaceDark
                            : AppColors.surfaceSecondaryLight,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: isDark
                              ? AppColors.borderDark
                              : AppColors.borderLight,
                          width: 1,
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(6),
                                decoration: BoxDecoration(
                                  color: isDark
                                      ? AppColors.textPrimaryDark
                                      : AppColors.textPrimaryLight,
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  Icons.check,
                                  color: isDark
                                      ? AppColors.textPrimaryLight
                                      : AppColors.surfaceLight,
                                  size: 16,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Text(
                                'Preliminary Extraction Summary',
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: isDark
                                      ? AppColors.textPrimaryDark
                                      : AppColors.textPrimaryLight,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Row(
                            children: [
                              Expanded(
                                child: _buildResultMetric(
                                  title: 'Rooms Detected',
                                  value: '${rooms.length} Rooms',
                                  icon: Icons.meeting_room_outlined,
                                  isDark: isDark,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _buildResultMetric(
                                  title: 'Electrical Points',
                                  value: '${points.length} Points',
                                  icon: Icons.power_outlined,
                                  isDark: isDark,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              Expanded(
                                child: _buildResultMetric(
                                  title: 'Recommended Circuits',
                                  value: '${circuits.length} Circuits',
                                  icon: Icons.alt_route_outlined,
                                  isDark: isDark,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _buildResultMetric(
                                  title: 'Consumer Unit',
                                  value: '1 Main DB',
                                  icon: Icons.electrical_services,
                                  isDark: isDark,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 18),

                    // Detected Rooms list
                    if (rooms.isNotEmpty) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: isDark
                              ? AppColors.surfaceDark
                              : AppColors.surfaceLight,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: isDark
                                ? AppColors.borderDark
                                : AppColors.borderLight,
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'DETECTED ROOMS & DIMENSIONS',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                                color: isDark
                                    ? AppColors.textMutedDark
                                    : AppColors.textMutedLight,
                              ),
                            ),
                            const SizedBox(height: 12),
                            ListView.separated(
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              itemCount: rooms.length,
                              separatorBuilder: (context, index) => Divider(
                                color: isDark
                                    ? AppColors.borderDark
                                    : AppColors.borderLight,
                                height: 1,
                              ),
                              itemBuilder: (context, idx) {
                                final r = rooms[idx];
                                final hasArea = r.areaM2 > 0;
                                final areaText = hasArea
                                    ? '${r.areaM2.toStringAsFixed(1)} m²'
                                    : 'Area unverified (Review)';

                                return Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 8),
                                  child: Row(
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceBetween,
                                    children: [
                                      Row(
                                        children: [
                                          Icon(
                                            Icons.check_circle_outline,
                                            size: 16,
                                            color: hasArea
                                                ? AppColors.statusGreen
                                                : Colors.amber,
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            r.name,
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
                                      Text(
                                        areaText,
                                        style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w500,
                                          color: hasArea
                                              ? (isDark
                                                  ? AppColors.textSecondaryDark
                                                  : AppColors.textSecondaryLight)
                                              : Colors.amber,
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // Architectural Features list
                    if (features.isNotEmpty) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: isDark
                              ? AppColors.surfaceDark
                              : AppColors.surfaceLight,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: isDark
                                ? AppColors.borderDark
                                : AppColors.borderLight,
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'ARCHITECTURAL OPENINGS & FEATURES',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                                color: isDark
                                    ? AppColors.textMutedDark
                                    : AppColors.textMutedLight,
                              ),
                            ),
                            const SizedBox(height: 10),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: features.map((f) {
                                return Chip(
                                  visualDensity: VisualDensity.compact,
                                  backgroundColor: isDark
                                      ? AppColors.surfaceSecondaryDark
                                      : AppColors.surfaceSecondaryLight,
                                  label: Text(
                                    '${f.type.toUpperCase()} • ${f.roomName}',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: isDark
                                          ? AppColors.textSecondaryDark
                                          : AppColors.textSecondaryLight,
                                    ),
                                  ),
                                );
                              }).toList(),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // Engineering Warnings Card if any
                    if (warnings.isNotEmpty) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.amber.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: Colors.amber.withValues(alpha: 0.4),
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: const [
                                Icon(Icons.warning_amber_rounded,
                                    color: Colors.amber, size: 20),
                                SizedBox(width: 8),
                                Text(
                                  'ENGINEERING REVIEW ITEMS',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.amber,
                                    letterSpacing: 0.4,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            ...warnings.map(
                              (w) => Padding(
                                padding: const EdgeInsets.only(bottom: 6),
                                child: Text(
                                  '• $w',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: isDark
                                        ? AppColors.textPrimaryDark
                                        : AppColors.textPrimaryLight,
                                    height: 1.35,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // RS IEC 60364 Engineering Disclaimer Banner
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isDark
                            ? AppColors.surfaceSecondaryDark
                            : AppColors.surfaceSecondaryLight,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: isDark
                              ? AppColors.borderDark
                              : AppColors.borderLight,
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.verified_outlined,
                            size: 18,
                            color: AppColors.primaryBlue,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              widget.state.engineeringDisclaimer.isNotEmpty
                                  ? widget.state.engineeringDisclaimer
                                  : 'Preliminary electrical planning output adhering to baseline RS IEC 60364 parameters. Final drawings and protective device curves must be validated by a licensed professional electrical engineer.',
                              style: TextStyle(
                                fontSize: 13,
                                color: isDark
                                    ? AppColors.textSecondaryDark
                                    : AppColors.textSecondaryLight,
                                height: 1.35,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 24),

                    AppButton(
                      label: 'View Electrical Recommendations',
                      icon: Icons.arrow_forward,
                      isFullWidth: true,
                      onPressed: () {
                        widget.state.advanceProjectStage(
                          widget.project.id,
                          ProjectStage.electricalDesign,
                        );
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => ElectricalRecommendationsScreen(
                              state: widget.state,
                              project: widget.project,
                            ),
                          ),
                        );
                      },
                    ),
                  ] else ...[
                    // Disclaimer during processing
                    Text(
                      'AI analysis uses computer vision heuristics to detect perimeter boundaries, doorways, and fixtures according to Rwandan RS IEC 60364 electrical codes.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        color: isDark
                            ? AppColors.textMutedDark
                            : AppColors.textMutedLight,
                        height: 1.4,
                      ),
                    ),
                  ],
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildStageRow(
    String text,
    int stageIndex,
    int currentStage,
    bool isDark,
  ) {
    final isDone =
        stageIndex < currentStage || (currentStage == 5 && stageIndex == 5);
    final isActive = stageIndex == currentStage && currentStage != 5;

    Widget iconWidget;
    if (isDone) {
      iconWidget = Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          color: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
          shape: BoxShape.circle,
        ),
        child: Icon(
          Icons.check,
          size: 14,
          color: isDark ? AppColors.textPrimaryLight : AppColors.surfaceLight,
        ),
      );
    } else if (isActive) {
      iconWidget = Container(
        width: 22,
        height: 22,
        padding: const EdgeInsets.all(4),
        child: const CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(AppColors.primaryBlue),
        ),
      );
    } else {
      iconWidget = Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
            width: 1.5,
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          iconWidget,
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isActive || isDone
                    ? FontWeight.w600
                    : FontWeight.w400,
                color: isDone
                    ? (isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight)
                    : (isActive
                        ? AppColors.primaryBlue
                        : (isDark
                            ? AppColors.textMutedDark
                            : AppColors.textMutedLight)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultMetric({
    required String title,
    required String value,
    required IconData icon,
    required bool isDark,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.primaryBlue),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 12,
                    color: isDark
                        ? AppColors.textMutedDark
                        : AppColors.textMutedLight,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
