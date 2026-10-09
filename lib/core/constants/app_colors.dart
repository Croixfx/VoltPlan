import 'package:flutter/material.dart';

/// Monochrome surfaces and controls, with blue reserved for key highlights.
class AppColors {
  AppColors._();

  // Neutral control tint retained for existing interactive accents.
  static const Color primaryBlue = Color(0xFF2457A6);
  static const Color primaryBlueDark = Color(0xFF1D4ED8);
  static const Color primaryBlueLight = Color(0xFF8AB4F8);
  static const Color accentBlue = primaryBlue;
  static const Color accentBlueLight = Color(0xFF9CC7FF);
  static const Color accentCyan = Color(0xFF0EA5E9);

  // Neutral Foundations (Light Mode)
  static const Color backgroundLight = Color(0xFFFAFAF9);
  static const Color surfaceLight = Color(0xFFFFFFFF);
  static const Color surfaceSecondaryLight = Color(0xFFF5F5F4);
  static const Color borderLight = Color(0xFFE7E5E4);
  static const Color borderSubtleLight = Color(0xFFD6D3D1);
  static const Color textPrimaryLight = Color(0xFF1C1917);
  static const Color textSecondaryLight = Color(0xFF57534E);
  static const Color textMutedLight = Color(0xFF78716C);

  // Neutral Foundations (Dark Mode)
  static const Color backgroundDark = Color(0xFF111110);
  static const Color surfaceDark = Color(0xFF1A1918);
  static const Color surfaceSecondaryDark = Color(0xFF262523);
  static const Color borderDark = Color(0xFF383633);
  static const Color borderSubtleDark = Color(0xFF4A4743);
  static const Color textPrimaryDark = Color(0xFFF5F5F4);
  static const Color textSecondaryDark = Color(0xFFC7C2BC);
  static const Color textMutedDark = Color(0xFFA8A29E);

  // Red is reserved for warnings and errors.
  static const Color statusWarning = Color(0xFFB42318);
  static const Color statusWarningDark = Color(0xFFFF8A80);
  static const Color statusGreen = Color(0xFF16A34A);

  // Architectural Drawing Canvas Palette
  static const Color canvasBg = Color(0xFF0A0F1D);
  static const Color canvasGrid = Color(0xFF162035);
  static const Color canvasWall = Color(0xFFCBD5E1);
  static const Color canvasRoomFill = Color(0x0C38BDF8);
  static const Color canvasDoor = Color(0xFF38BDF8);
  static const Color canvasDimension = Color(0xFF64748B);
}
