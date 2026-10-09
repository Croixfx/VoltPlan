import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/section_header.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import '../floor_plan/upload_plan_screen.dart';
import '../floor_plan/widgets/plan_drawing_viewer.dart';
import '../analysis/ai_analysis_screen.dart';
import '../electrical/electrical_recommendations_screen.dart';
import '../electrical/electrical_plan_canvas_screen.dart';
import '../electrical/circuits_screen.dart';
import '../boq/boq_screen.dart';
import '../cost_estimate/cost_estimate_screen.dart';
import '../reports/report_screen.dart';

class ProjectOverviewScreen extends StatelessWidget {
  final AppState state;
  final Project project;

  const ProjectOverviewScreen({
    super.key,
    required this.state,
    required this.project,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final currentProject = state.projects.firstWhere(
      (p) => p.id == project.id,
      orElse: () => project,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Project Overview'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined, size: 20),
            tooltip: 'Share Project',
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Project summary copied to clipboard'),
                ),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Project Header Card
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
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                currentProject.name,
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: -0.3,
                                  color: isDark
                                      ? AppColors.textPrimaryDark
                                      : AppColors.textPrimaryLight,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${currentProject.client}  •  ${currentProject.location}',
                                style: TextStyle(
                                  fontSize: 14,
                                  color: isDark
                                      ? AppColors.textSecondaryDark
                                      : AppColors.textSecondaryLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                        StatusBadge(status: currentProject.status.label),
                      ],
                    ),
                    const SizedBox(height: 14),
                    Divider(
                      color: isDark
                          ? AppColors.borderDark
                          : AppColors.borderLight,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildMetaItem(
                          'Standard',
                          currentProject.standard.split(' ').first,
                          isDark,
                        ),
                        _buildMetaItem(
                          'Building',
                          currentProject.buildingType,
                          isDark,
                        ),
                        _buildMetaItem(
                          'Rooms',
                          currentProject.roomsCount > 0
                              ? '${currentProject.roomsCount}'
                              : 'Pending',
                          isDark,
                        ),
                        _buildMetaItem(
                          'Estimated',
                          currentProject.estimatedCostRwf > 0
                              ? Formatters.formatRwf(
                                  currentProject.estimatedCostRwf,
                                )
                              : 'Pending',
                          isDark,
                          isHighlight: true,
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Progress Timeline (1. Floor Plan, 2. AI Analysis, 3. Electrical Design, 4. BOQ, 5. Cost Estimate, 6. Report)
              SectionHeader(
                title: 'Engineering Workflow',
                subtitle:
                    'Stage ${currentProject.currentStage.step} of 6: ${currentProject.currentStage.title}',
              ),
              const SizedBox(height: 10),
              _buildProgressTimeline(context, currentProject, isDark),

              const SizedBox(height: 24),

              // Architectural Floor Plan Preview Card
              SectionHeader(
                title: 'Architectural Floor Plan',
                subtitle:
                    currentProject.floorPlanName ??
                    'No plan uploaded yet (PDF, PNG, JPG)',
                actionLabel: currentProject.floorPlanName != null
                    ? 'Re-upload'
                    : null,
                onAction: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => UploadPlanScreen(
                        state: state,
                        project: currentProject,
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 8),

              _buildPlanPreviewCard(context, currentProject, isDark),

              const SizedBox(height: 28),

              // Workflow Action Grid
              const SectionHeader(
                title: 'Project Modules',
                subtitle: 'Direct navigation into electrical design stages',
              ),
              const SizedBox(height: 12),
              _buildModuleGrid(context, currentProject, isDark),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMetaItem(
    String label,
    String value,
    bool isDark, {
    bool isHighlight = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 13,
            color: isDark ? AppColors.textMutedDark : AppColors.textMutedLight,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: isHighlight
                ? AppColors.primaryBlue
                : (isDark
                      ? AppColors.textPrimaryDark
                      : AppColors.textPrimaryLight),
          ),
        ),
      ],
    );
  }

  Widget _buildProgressTimeline(
    BuildContext context,
    Project project,
    bool isDark,
  ) {
    final stages = ProjectStage.values;
    final currentStep = project.currentStage.step;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: stages.map((stage) {
          final isCompleted = stage.step < currentStep;
          final isCurrent = stage.step == currentStep;

          Color nodeColor;
          if (isCompleted) {
            nodeColor = isDark
                ? AppColors.textPrimaryDark
                : AppColors.textPrimaryLight;
          } else if (isCurrent) {
            nodeColor = AppColors.accentBlue;
          } else {
            nodeColor = isDark ? AppColors.borderDark : AppColors.borderLight;
          }

          return Expanded(
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: isCompleted || isCurrent
                        ? nodeColor
                        : Colors.transparent,
                    shape: BoxShape.circle,
                    border: Border.all(color: nodeColor, width: 2),
                  ),
                  child: Center(
                    child: isCompleted
                        ? Icon(
                            Icons.check,
                            size: 16,
                            color: isDark
                                ? AppColors.textPrimaryLight
                                : AppColors.surfaceLight,
                          )
                        : Text(
                            '${stage.step}',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: isCurrent
                                  ? Colors.white
                                  : (isDark
                                        ? AppColors.textMutedDark
                                        : AppColors.textMutedLight),
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  stage.title,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
                    color: isCurrent
                        ? AppColors.accentBlue
                        : (isDark
                              ? AppColors.textSecondaryDark
                              : AppColors.textSecondaryLight),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildPlanPreviewCard(
    BuildContext context,
    Project project,
    bool isDark,
  ) {
    if (project.floorPlanName == null) {
      return Container(
        height: 180,
        decoration: BoxDecoration(
          color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
          ),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.cloud_upload_outlined,
                size: 38,
                color: isDark
                    ? AppColors.textMutedDark
                    : AppColors.textMutedLight,
              ),
              const SizedBox(height: 12),
              Text(
                'No Architectural Drawing Uploaded',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: isDark
                      ? AppColors.textPrimaryDark
                      : AppColors.textPrimaryLight,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Supported: PDF, PNG, JPG (Max 25 MB)',
                style: TextStyle(
                  fontSize: 14,
                  color: isDark
                      ? AppColors.textMutedDark
                      : AppColors.textMutedLight,
                ),
              ),
              const SizedBox(height: 14),
              AppButton(
                label: 'Upload Floor Plan',
                icon: Icons.upload_file,
                height: 38,
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          UploadPlanScreen(state: state, project: project),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: SizedBox(
              height: 200,
              child: PlanDrawingViewer(
                project: project,
                points: state.electricalPoints,
                isDark: isDark,
                showPointsOverlay: project.currentStage.step >= ProjectStage.electricalDesign.step,
                wiringArcs: state.wiringArcs,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        project.floorPlanName!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: isDark
                              ? AppColors.textPrimaryDark
                              : AppColors.textPrimaryLight,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        project.roomsCount > 0
                            ? '${project.roomsCount} Rooms Identified • ${project.electricalPointsCount} Points'
                            : 'Plan uploaded • Ready for AI automated analysis',
                        style: TextStyle(
                          fontSize: 13,
                          color: isDark
                              ? AppColors.textMutedDark
                              : AppColors.textMutedLight,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                if (project.roomsCount == 0 && project.currentStage.step <= ProjectStage.aiAnalysis.step)
                  AppButton(
                    label: 'Start AI',
                    icon: Icons.auto_awesome,
                    height: 36,
                    variant: AppButtonVariant.primary,
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => AiAnalysisScreen(
                            state: state,
                            project: project,
                          ),
                        ),
                      );
                    },
                  )
                else
                  AppButton(
                    label: 'Open Canvas',
                    icon: Icons.fullscreen,
                    height: 36,
                    variant: AppButtonVariant.secondary,
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ElectricalPlanCanvasScreen(
                            state: state,
                            project: project,
                          ),
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleGrid(BuildContext context, Project project, bool isDark) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.auto_awesome_outlined,
                title: 'AI Analysis',
                subtitle: 'Room & point detection',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          AiAnalysisScreen(state: state, project: project),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.checklist_rtl_outlined,
                title: 'Recommendations',
                subtitle: 'Grouped by room',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ElectricalRecommendationsScreen(
                        state: state,
                        project: project,
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.architecture_outlined,
                title: 'Electrical Plan',
                subtitle: 'Zoom & pan overlay',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ElectricalPlanCanvasScreen(
                        state: state,
                        project: project,
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.alt_route_outlined,
                title: 'Circuits',
                subtitle: 'Schedules & breakers',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          CircuitsScreen(state: state, project: project),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.inventory_2_outlined,
                title: 'BOQ / Materials',
                subtitle: 'Quantities & specs',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => BoqScreen(state: state, project: project),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildModuleTile(
                context: context,
                icon: Icons.request_quote_outlined,
                title: 'Cost Estimate',
                subtitle: 'Materials & labor breakdown',
                isDark: isDark,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          CostEstimateScreen(state: state, project: project),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _buildModuleTile(
          context: context,
          icon: Icons.description_outlined,
          title: 'Engineering Report Preview & PDF Generation',
          subtitle: 'Comprehensive client-ready documentation and export',
          isDark: isDark,
          isFullWidth: true,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ReportScreen(state: state, project: project),
              ),
            );
          },
        ),
      ],
    );
  }

  Widget _buildModuleTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required bool isDark,
    required VoidCallback onTap,
    bool isFullWidth = false,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
          ),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.primaryBlue.withValues(
                  alpha: isDark ? 0.2 : 0.1,
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, size: 20, color: AppColors.primaryBlue),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: isDark
                          ? AppColors.textPrimaryDark
                          : AppColors.textPrimaryLight,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 13,
                      color: isDark
                          ? AppColors.textSecondaryDark
                          : AppColors.textSecondaryLight,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              size: 18,
              color: isDark
                  ? AppColors.textMutedDark
                  : AppColors.textMutedLight,
            ),
          ],
        ),
      ),
    );
  }
}
