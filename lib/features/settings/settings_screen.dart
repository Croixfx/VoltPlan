import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/engineering_sheet.dart';
import '../../core/widgets/section_header.dart';
import '../../shared/state/app_state.dart';

class SettingsScreen extends StatelessWidget {
  final AppState state;

  const SettingsScreen({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ListenableBuilder(
      listenable: state,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(title: const Text('Profile & Settings')),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // User Profile Card
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
                    child: Row(
                      children: [
                        Container(
                          width: 52,
                          height: 52,
                          decoration: BoxDecoration(
                            color: AppColors.primaryBlue,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Center(
                            child: Text(
                              'PM',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                state.userName,
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: isDark
                                      ? AppColors.textPrimaryDark
                                      : AppColors.textPrimaryLight,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                state.companyName,
                                style: TextStyle(
                                  fontSize: 14,
                                  color: isDark
                                      ? AppColors.textSecondaryDark
                                      : AppColors.textSecondaryLight,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Rwanda Energy Regulatory Board (RURA) Certified',
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
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Engineering Preferences Section
                  const SectionHeader(
                    title: 'Engineering Standards',
                    subtitle: 'Regional codes and calculation parameters',
                  ),
                  const SizedBox(height: 8),

                  _buildSettingsGroup(
                    isDark: isDark,
                    children: [
                      _buildSettingsTile(
                        icon: Icons.verified_outlined,
                        title: 'Electrical Standard',
                        value: state.currentStandard,
                        isDark: isDark,
                        onTap: () => _showStandardPicker(context),
                      ),
                      const Divider(height: 1),
                      _buildSettingsTile(
                        icon: Icons.square_foot_outlined,
                        title: 'Units of Measurement',
                        value: state.unitSystem,
                        isDark: isDark,
                        onTap: () => _showUnitsPicker(context),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // App Configuration Section
                  const SectionHeader(
                    title: 'Application Preferences',
                    subtitle: 'Appearance and alerts',
                  ),
                  const SizedBox(height: 8),

                  _buildSettingsGroup(
                    isDark: isDark,
                    children: [
                      SwitchListTile(
                        secondary: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppColors.primaryBlue.withValues(
                              alpha: isDark ? 0.2 : 0.1,
                            ),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            isDark
                                ? Icons.dark_mode_outlined
                                : Icons.light_mode_outlined,
                            size: 20,
                            color: AppColors.primaryBlue,
                          ),
                        ),
                        title: Text(
                          'Dark Theme',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: isDark
                                ? AppColors.textPrimaryDark
                                : AppColors.textPrimaryLight,
                          ),
                        ),
                        subtitle: Text(
                          isDark
                              ? 'Precision dark engineering interface'
                              : 'Clean high-contrast light mode',
                          style: TextStyle(
                            fontSize: 14,
                            color: isDark
                                ? AppColors.textSecondaryDark
                                : AppColors.textSecondaryLight,
                          ),
                        ),
                        value: isDark,
                        activeThumbColor: AppColors.primaryBlue,
                        onChanged: (_) => state.toggleTheme(),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppColors.primaryBlue.withValues(
                              alpha: isDark ? 0.2 : 0.1,
                            ),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(
                            Icons.notifications_none,
                            size: 20,
                            color: AppColors.primaryBlue,
                          ),
                        ),
                        title: Text(
                          'Engineering Alerts',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: isDark
                                ? AppColors.textPrimaryDark
                                : AppColors.textPrimaryLight,
                          ),
                        ),
                        subtitle: Text(
                          'Overload warnings, code violations, and reviews',
                          style: TextStyle(
                            fontSize: 14,
                            color: isDark
                                ? AppColors.textSecondaryDark
                                : AppColors.textSecondaryLight,
                          ),
                        ),
                        value: state.notificationsEnabled,
                        activeThumbColor: AppColors.primaryBlue,
                        onChanged: (val) =>
                            state.updateProfile(notifications: val),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // Information & Support
                  const SectionHeader(title: 'System & Support'),
                  const SizedBox(height: 8),

                  _buildSettingsGroup(
                    isDark: isDark,
                    children: [
                      _buildSettingsTile(
                        icon: Icons.help_outline,
                        title: 'Help & Documentation',
                        value: 'Engineering guides',
                        isDark: isDark,
                        onTap: () => _showHelpDialog(context),
                      ),
                      const Divider(height: 1),
                      _buildSettingsTile(
                        icon: Icons.info_outline,
                        title: 'About VoltPlan',
                        value: 'v1.0.0 (Commercial UI/UX)',
                        isDark: isDark,
                        onTap: () => _showAboutDialog(context),
                      ),
                    ],
                  ),

                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildSettingsGroup({
    required bool isDark,
    required List<Widget> children,
  }) {
    return Material(
      color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Column(children: children),
    );
  }

  Widget _buildSettingsTile({
    required IconData icon,
    required String title,
    required String value,
    required bool isDark,
    required VoidCallback onTap,
  }) {
    return ListTile(
      onTap: onTap,
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppColors.primaryBlue.withValues(alpha: isDark ? 0.2 : 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, size: 20, color: AppColors.primaryBlue),
      ),
      title: Text(
        title,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
        ),
      ),
      trailing: SizedBox(
        width: 148,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Expanded(
              child: Text(
                value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.end,
                style: TextStyle(
                  fontSize: 14,
                  color: isDark
                      ? AppColors.textMutedDark
                      : AppColors.textMutedLight,
                ),
              ),
            ),
            const SizedBox(width: 4),
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

  void _showStandardPicker(BuildContext context) {
    EngineeringBottomSheet.show(
      context: context,
      title: 'Select Electrical Standard',
      subtitle: 'Determines cable sizing rules and safety margins',
      child: Column(
        children: AppConstants.electricalStandards.map((std) {
          final isSelected = state.currentStandard == std;
          return ListTile(
            title: Text(std, style: const TextStyle(fontSize: 14)),
            trailing: isSelected
                ? const Icon(Icons.check, color: AppColors.primaryBlue)
                : null,
            onTap: () {
              state.updateProfile(standard: std);
              Navigator.pop(context);
            },
          );
        }).toList(),
      ),
    );
  }

  void _showUnitsPicker(BuildContext context) {
    EngineeringBottomSheet.show(
      context: context,
      title: 'Units of Measurement',
      child: Column(
        children: [
          ListTile(
            title: const Text('Metric (mm / m / m²)'),
            subtitle: const Text('Rwandan & IEC international standard'),
            trailing: state.unitSystem.contains('Metric')
                ? const Icon(Icons.check, color: AppColors.primaryBlue)
                : null,
            onTap: () {
              state.updateProfile(unitSystem: 'Metric (mm / m / m²)');
              Navigator.pop(context);
            },
          ),
          ListTile(
            title: const Text('Imperial (in / ft / sq ft)'),
            subtitle: const Text('US NEC standard'),
            trailing: state.unitSystem.contains('Imperial')
                ? const Icon(Icons.check, color: AppColors.primaryBlue)
                : null,
            onTap: () {
              state.updateProfile(unitSystem: 'Imperial (in / ft / sq ft)');
              Navigator.pop(context);
            },
          ),
        ],
      ),
    );
  }

  void _showHelpDialog(BuildContext context) {
    EngineeringBottomSheet.show(
      context: context,
      title: 'VoltPlan Engineering Guide',
      subtitle: 'How to use VoltPlan in your workflow',
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Workflow Overview',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
          ),
          SizedBox(height: 6),
          Text(
            '1. Create Project with building type and Rwandan standard.\n2. Upload architectural floor plan (PDF, PNG, JPG).\n3. AI Analysis maps rooms, perimeter boundaries, and points.\n4. Review electrical recommendations grouped by room.\n5. Inspect the interactive Electrical Plan canvas with zoom/pan.\n6. Adjust quantities in the BOQ table.\n7. Review cost estimates in RWF and export client report.',
            style: TextStyle(fontSize: 14, height: 1.5),
          ),
        ],
      ),
    );
  }

  void _showAboutDialog(BuildContext context) {
    EngineeringBottomSheet.show(
      context: context,
      title: 'About VoltPlan',
      subtitle: 'Version 1.0.0 (Phase 1 Engineering Frontend)',
      child: Column(
        children: [
          const Text(
            'VoltPlan is an AI-assisted electrical planning and estimation platform for building professionals, certified electricians, and MEP consulting engineers.\n\nDesigned with precision engineering principles for the Rwandan construction and infrastructure market.',
            style: TextStyle(fontSize: 14, height: 1.4),
          ),
          const SizedBox(height: 20),
          AppButton(
            label: 'Close',
            variant: AppButtonVariant.secondary,
            isFullWidth: true,
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }
}
