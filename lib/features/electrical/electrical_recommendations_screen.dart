import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/engineering_sheet.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/models/electrical_point.dart';
import '../../shared/state/app_state.dart';
import 'electrical_plan_canvas_screen.dart';

class ElectricalRecommendationsScreen extends StatelessWidget {
  final AppState state;
  final Project project;

  const ElectricalRecommendationsScreen({
    super.key,
    required this.state,
    required this.project,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Group electrical points by room
    final pointsByRoom = <String, List<ElectricalPoint>>{};
    for (final pt in state.electricalPoints) {
      pointsByRoom.putIfAbsent(pt.roomName, () => []).add(pt);
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Electrical Recommendations'),
        actions: [
          IconButton(
            icon: const Icon(Icons.architecture_outlined),
            tooltip: 'View Plan Canvas',
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
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
          border: Border(
            top: BorderSide(
              color: isDark ? AppColors.borderDark : AppColors.borderLight,
            ),
          ),
        ),
        child: SafeArea(
          child: AppButton(
            label: 'View Electrical Plan Canvas',
            icon: Icons.map_outlined,
            isFullWidth: true,
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
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Engineering Disclaimer Banner
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
                      Icons.shield_outlined,
                      size: 20,
                      color: AppColors.primaryBlue,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        AppConstants.disclaimerText,
                        style: TextStyle(
                          fontSize: 14,
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

              const SizedBox(height: 20),

              // Room Groups
              ...pointsByRoom.entries.map((entry) {
                final roomName = entry.key;
                final roomPoints = entry.value;

                return Padding(
                  padding: const EdgeInsets.only(bottom: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Room Title with point count
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            roomName.toUpperCase(),
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.5,
                              color: isDark
                                  ? AppColors.textMutedDark
                                  : AppColors.textMutedLight,
                            ),
                          ),
                          Text(
                            '${roomPoints.length} items',
                            style: TextStyle(
                              fontSize: 14,
                              color: isDark
                                  ? AppColors.textMutedDark
                                  : AppColors.textMutedLight,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),

                      // Room items container
                      Material(
                        color: isDark
                            ? AppColors.surfaceDark
                            : AppColors.surfaceLight,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(
                            color: isDark
                                ? AppColors.borderDark
                                : AppColors.borderLight,
                          ),
                        ),
                        child: ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: roomPoints.length,
                          separatorBuilder: (_, _) => Divider(
                            color: isDark
                                ? AppColors.borderDark
                                : AppColors.borderLight,
                            height: 1,
                          ),
                          itemBuilder: (context, idx) {
                            final point = roomPoints[idx];
                            return _buildPointTile(context, point, isDark);
                          },
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPointTile(
    BuildContext context,
    ElectricalPoint point,
    bool isDark,
  ) {
    return ListTile(
      onTap: () => _showPointInspection(context, point, isDark),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppColors.primaryBlue.withValues(alpha: isDark ? 0.2 : 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(point.type.icon, size: 20, color: AppColors.primaryBlue),
      ),
      title: Text(
        '${point.quantity}x ${point.label}',
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
        ),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 2),
        child: Text(
          'Cable: ${point.cableSize}  •  Circuit: ${point.circuitId}',
          style: TextStyle(
            fontSize: 14,
            color: isDark
                ? AppColors.textSecondaryDark
                : AppColors.textSecondaryLight,
          ),
        ),
      ),
      trailing: StatusBadge(status: point.status, isSmall: true),
    );
  }

  void _showPointInspection(
    BuildContext context,
    ElectricalPoint point,
    bool isDark,
  ) {
    EngineeringBottomSheet.show(
      context: context,
      title: point.label,
      subtitle: '${point.roomName} • Electrical Specification',
      child: Column(
        children: [
          _buildSpecRow('Component Type', point.type.label, isDark),
          _buildSpecRow('Room', point.roomName, isDark),
          _buildSpecRow(
            'Allocated Quantity',
            '${point.quantity} units',
            isDark,
          ),
          _buildSpecRow('Recommended Cable', point.cableSize, isDark),
          _buildSpecRow('Assigned Circuit', point.circuitId, isDark),
          _buildSpecRow('Protection Device', point.protectionMcb, isDark),
          _buildSpecRow(
            'Engineering Status',
            point.status,
            isDark,
            isBadge: true,
          ),
        ],
      ),
    );
  }

  Widget _buildSpecRow(
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
}
