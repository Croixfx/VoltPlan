import 'package:flutter/material.dart';
import '../core/constants/app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: 'Segoe UI',
      fontFamilyFallback: const ['sans-serif'],
      textTheme: _textTheme(isDark: false),
      colorScheme: const ColorScheme.light(
        primary: AppColors.textPrimaryLight,
        onPrimary: Colors.white,
        primaryContainer: AppColors.surfaceSecondaryLight,
        onPrimaryContainer: AppColors.textPrimaryLight,
        secondary: AppColors.textSecondaryLight,
        onSecondary: AppColors.surfaceLight,
        surface: AppColors.surfaceLight,
        onSurface: AppColors.textPrimaryLight,
        error: AppColors.statusWarning,
        onError: Colors.white,
        outline: AppColors.borderLight,
        outlineVariant: AppColors.borderSubtleLight,
      ),
      scaffoldBackgroundColor: AppColors.backgroundLight,
      dividerColor: AppColors.borderLight,
      dividerTheme: const DividerThemeData(
        color: AppColors.borderLight,
        thickness: 1,
        space: 1,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surfaceLight,
        foregroundColor: AppColors.textPrimaryLight,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AppColors.textPrimaryLight,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        iconTheme: IconThemeData(color: AppColors.textPrimaryLight, size: 22),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: _filledButtonStyle(isDark: false),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: _outlinedButtonStyle(isDark: false),
      ),
      textButtonTheme: TextButtonThemeData(
        style: _textButtonStyle(isDark: false),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: _iconButtonStyle(isDark: false),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surfaceLight,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.borderLight, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surfaceLight,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        hintStyle: const TextStyle(
          color: AppColors.textMutedLight,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: AppColors.textSecondaryLight,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderLight, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderLight, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(
            color: AppColors.primaryBlue,
            width: 1.5,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(
            color: AppColors.statusWarning,
            width: 1,
          ),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.surfaceLight,
        selectedItemColor: AppColors.accentBlue,
        unselectedItemColor: AppColors.textMutedLight,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
        selectedLabelStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: 'Segoe UI',
      fontFamilyFallback: const ['sans-serif'],
      textTheme: _textTheme(isDark: true),
      colorScheme: const ColorScheme.dark(
        primary: AppColors.textPrimaryDark,
        onPrimary: AppColors.textPrimaryLight,
        primaryContainer: AppColors.surfaceSecondaryDark,
        onPrimaryContainer: AppColors.textPrimaryDark,
        secondary: AppColors.textSecondaryDark,
        onSecondary: AppColors.surfaceDark,
        surface: AppColors.surfaceDark,
        onSurface: AppColors.textPrimaryDark,
        error: AppColors.statusWarningDark,
        onError: Colors.white,
        outline: AppColors.borderDark,
        outlineVariant: AppColors.borderSubtleDark,
      ),
      scaffoldBackgroundColor: AppColors.backgroundDark,
      dividerColor: AppColors.borderDark,
      dividerTheme: const DividerThemeData(
        color: AppColors.borderDark,
        thickness: 1,
        space: 1,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surfaceDark,
        foregroundColor: AppColors.textPrimaryDark,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AppColors.textPrimaryDark,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.3,
        ),
        iconTheme: IconThemeData(color: AppColors.textPrimaryDark, size: 22),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: _filledButtonStyle(isDark: true),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: _outlinedButtonStyle(isDark: true),
      ),
      textButtonTheme: TextButtonThemeData(
        style: _textButtonStyle(isDark: true),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: _iconButtonStyle(isDark: true),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surfaceDark,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.borderDark, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surfaceDark,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        hintStyle: const TextStyle(
          color: AppColors.textMutedDark,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: AppColors.textSecondaryDark,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderDark, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderDark, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(
            color: AppColors.primaryBlueLight,
            width: 1.5,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(
            color: AppColors.statusWarningDark,
            width: 1,
          ),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.surfaceDark,
        selectedItemColor: AppColors.accentBlueLight,
        unselectedItemColor: AppColors.textMutedDark,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
        selectedLabelStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  static ButtonStyle _filledButtonStyle({required bool isDark}) {
    return ButtonStyle(
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
        return isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight;
      }),
      foregroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) {
          return isDark ? AppColors.textMutedDark : AppColors.textMutedLight;
        }
        return isDark ? AppColors.textPrimaryLight : AppColors.surfaceLight;
      }),
      elevation: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.hovered) ? 2 : 0,
      ),
      side: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.focused)) {
          return BorderSide(
            color: isDark ? AppColors.textPrimaryLight : AppColors.surfaceLight,
            width: 2,
          );
        }
        return BorderSide.none;
      }),
      shape: WidgetStateProperty.all(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      animationDuration: const Duration(milliseconds: 140),
    );
  }

  static ButtonStyle _outlinedButtonStyle({required bool isDark}) {
    return ButtonStyle(
      foregroundColor: WidgetStateProperty.all(
        isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
      ),
      backgroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.hovered) ||
            states.contains(WidgetState.pressed)) {
          return isDark
              ? AppColors.surfaceSecondaryDark
              : AppColors.surfaceSecondaryLight;
        }
        return Colors.transparent;
      }),
      side: WidgetStateProperty.resolveWith(
        (states) => BorderSide(
          color: states.contains(WidgetState.hovered)
              ? (isDark
                    ? AppColors.borderSubtleDark
                    : AppColors.borderSubtleLight)
              : (isDark ? AppColors.borderDark : AppColors.borderLight),
        ),
      ),
      shape: WidgetStateProperty.all(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      animationDuration: const Duration(milliseconds: 140),
    );
  }

  static ButtonStyle _textButtonStyle({required bool isDark}) {
    return ButtonStyle(
      foregroundColor: WidgetStateProperty.all(
        isDark ? AppColors.accentBlueLight : AppColors.accentBlue,
      ),
      overlayColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.hovered) ||
            states.contains(WidgetState.focused)) {
          return (isDark ? AppColors.accentBlueLight : AppColors.accentBlue)
              .withValues(alpha: isDark ? 0.18 : 0.08);
        }
        if (states.contains(WidgetState.pressed)) {
          return (isDark ? AppColors.accentBlueLight : AppColors.accentBlue)
              .withValues(alpha: 0.16);
        }
        return Colors.transparent;
      }),
      animationDuration: const Duration(milliseconds: 140),
    );
  }

  static ButtonStyle _iconButtonStyle({required bool isDark}) {
    return ButtonStyle(
      foregroundColor: WidgetStateProperty.all(
        isDark ? AppColors.textSecondaryDark : AppColors.textSecondaryLight,
      ),
      overlayColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.hovered) ||
            states.contains(WidgetState.focused)) {
          return isDark
              ? AppColors.surfaceSecondaryDark
              : AppColors.surfaceSecondaryLight;
        }
        if (states.contains(WidgetState.pressed)) {
          return isDark ? AppColors.borderDark : AppColors.borderLight;
        }
        return Colors.transparent;
      }),
      shape: WidgetStateProperty.all(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      animationDuration: const Duration(milliseconds: 140),
    );
  }

  static TextTheme _textTheme({required bool isDark}) {
    final base = isDark
        ? Typography.material2021().white
        : Typography.material2021().black;
    return base
        .apply(
          fontFamily: 'Segoe UI',
          bodyColor: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
          displayColor: isDark
              ? AppColors.textPrimaryDark
              : AppColors.textPrimaryLight,
        )
        .copyWith(
          bodyLarge: base.bodyLarge?.copyWith(fontSize: 17, height: 1.5),
          bodyMedium: base.bodyMedium?.copyWith(fontSize: 16, height: 1.5),
          bodySmall: base.bodySmall?.copyWith(fontSize: 14, height: 1.45),
          labelLarge: base.labelLarge?.copyWith(fontSize: 15),
          labelMedium: base.labelMedium?.copyWith(fontSize: 14),
          labelSmall: base.labelSmall?.copyWith(fontSize: 13),
        );
  }
}
