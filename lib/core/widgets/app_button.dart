import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

enum AppButtonVariant { primary, secondary, outline, text }

class AppButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final AppButtonVariant variant;
  final bool isLoading;
  final bool isFullWidth;
  final double height;

  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.variant = AppButtonVariant.primary,
    this.isLoading = false,
    this.isFullWidth = false,
    this.height = 48,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primaryForeground = isDark
        ? AppColors.textPrimaryLight
        : AppColors.surfaceLight;

    Widget buttonContent = Row(
      mainAxisSize: isFullWidth ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (isLoading) ...[
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(
                variant == AppButtonVariant.primary
                    ? primaryForeground
                    : (isDark
                          ? AppColors.textPrimaryDark
                          : AppColors.textPrimaryLight),
              ),
            ),
          ),
          const SizedBox(width: 10),
        ] else if (icon != null) ...[
          Icon(icon, size: 18),
          const SizedBox(width: 8),
        ],
        Text(
          label,
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.2,
          ),
        ),
      ],
    );

    switch (variant) {
      case AppButtonVariant.primary:
        return SizedBox(
          width: isFullWidth ? double.infinity : null,
          height: height,
          child: FilledButton(
            onPressed: isLoading ? null : onPressed,
            style: ButtonStyle(
              backgroundColor: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.disabled)) {
                  return isDark
                      ? AppColors.surfaceSecondaryDark
                      : AppColors.surfaceSecondaryLight;
                }
                if (states.contains(WidgetState.pressed)) {
                  return isDark
                      ? AppColors.textMutedDark
                      : AppColors.textSecondaryLight;
                }
                if (states.contains(WidgetState.hovered)) {
                  return isDark
                      ? AppColors.textSecondaryDark
                      : AppColors.textSecondaryLight;
                }
                return isDark
                    ? AppColors.textPrimaryDark
                    : AppColors.textPrimaryLight;
              }),
              foregroundColor: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.disabled)) {
                  return isDark
                      ? AppColors.textMutedDark
                      : AppColors.textMutedLight;
                }
                return primaryForeground;
              }),
              elevation: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.hovered)) return 2;
                return 0;
              }),
              shape: WidgetStateProperty.all(
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              padding: WidgetStateProperty.all(
                const EdgeInsets.symmetric(horizontal: 20),
              ),
              animationDuration: const Duration(milliseconds: 140),
            ),
            child: buttonContent,
          ),
        );

      case AppButtonVariant.secondary:
        return SizedBox(
          width: isFullWidth ? double.infinity : null,
          height: height,
          child: FilledButton(
            onPressed: isLoading ? null : onPressed,
            style: ButtonStyle(
              backgroundColor: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.hovered) ||
                    states.contains(WidgetState.pressed)) {
                  return isDark ? AppColors.borderDark : AppColors.borderLight;
                }
                return isDark
                    ? AppColors.surfaceSecondaryDark
                    : AppColors.surfaceSecondaryLight;
              }),
              foregroundColor: WidgetStateProperty.all(
                isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
              ),
              side: WidgetStateProperty.resolveWith((states) {
                return BorderSide(
                  color: states.contains(WidgetState.hovered)
                      ? (isDark
                            ? AppColors.borderSubtleDark
                            : AppColors.borderSubtleLight)
                      : (isDark ? AppColors.borderDark : AppColors.borderLight),
                );
              }),
              shape: WidgetStateProperty.all(
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              padding: WidgetStateProperty.all(
                const EdgeInsets.symmetric(horizontal: 20),
              ),
              animationDuration: const Duration(milliseconds: 140),
            ),
            child: buttonContent,
          ),
        );

      case AppButtonVariant.outline:
        return SizedBox(
          width: isFullWidth ? double.infinity : null,
          height: height,
          child: OutlinedButton(
            onPressed: isLoading ? null : onPressed,
            style: ButtonStyle(
              shape: WidgetStateProperty.all(
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              padding: WidgetStateProperty.all(
                const EdgeInsets.symmetric(horizontal: 20),
              ),
              animationDuration: const Duration(milliseconds: 140),
            ),
            child: buttonContent,
          ),
        );

      case AppButtonVariant.text:
        return SizedBox(
          width: isFullWidth ? double.infinity : null,
          height: height,
          child: TextButton(
            onPressed: isLoading ? null : onPressed,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.accentBlue,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16),
            ),
            child: buttonContent,
          ),
        );
    }
  }
}
