import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:file_picker/file_picker.dart';
import 'package:cross_file/cross_file.dart';
import 'package:voltplan/app/app.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/constants/app_colors.dart';
import 'package:voltplan/core/widgets/app_button.dart';
import 'package:voltplan/core/widgets/metric_card.dart';
import 'package:voltplan/features/floor_plan/upload_plan_screen.dart';
import 'package:voltplan/features/analysis/ai_analysis_screen.dart';
import 'package:voltplan/features/projects/create_project_screen.dart';
import 'package:voltplan/shared/models/project.dart';
import 'package:voltplan/shared/state/app_state.dart';

final class TestPlatformFile extends PlatformFile {
  @override
  final String name;
  final Uint8List bytes;

  TestPlatformFile({required this.name, required this.bytes});

  @override
  Uri get uri => Uri.file('/test/$name');

  @override
  XFile get xFile => XFile.fromData(bytes, name: name);

  @override
  int? lengthSync() => bytes.length;

  @override
  Future<int?> length() async => bytes.length;

  @override
  Future<Uint8List> readAsBytes() async => bytes;

  @override
  Stream<Uint8List> readAsByteStream() => Stream.value(bytes);
}

class FakeFilePickerPlatform extends FilePickerPlatform {
  PlatformFile? fileToReturn;
  Object? errorToThrow;
  int pickFileCallCount = 0;

  @override
  Future<PlatformFile?> pickFile({
    String? dialogTitle,
    String? initialDirectory,
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    Function(FilePickerStatus)? onFileLoading,
    int compressionQuality = 0,
    AndroidOptions androidOptions = const AndroidOptions(),
    DarwinOptions darwinOptions = const DarwinOptions(),
    WindowsOptions windowsOptions = const WindowsOptions(),
    LinuxOptions linuxOptions = const LinuxOptions(),
    WebOptions webOptions = const WebOptions(),
  }) async {
    pickFileCallCount++;
    if (errorToThrow != null) {
      throw errorToThrow!;
    }
    return fileToReturn;
  }
}

void main() {
  group('VoltPlan App Tests', () {
    test('Theme typography uses readable mobile body sizes', () {
      expect(AppTheme.light().textTheme.bodyMedium?.fontSize, 16);
      expect(AppTheme.light().textTheme.bodySmall?.fontSize, 14);
      expect(AppTheme.dark().textTheme.bodyMedium?.fontSize, 16);
      expect(
        AppTheme.light().scaffoldBackgroundColor,
        AppColors.backgroundLight,
      );
    });

    test('Light-mode blue has accessible contrast on white', () {
      expect(
        AppColors.primaryBlue.computeLuminance(),
        lessThanOrEqualTo(0.183),
      );
      expect(AppColors.accentBlue, AppColors.primaryBlue);
    });

    testWidgets('App renders dashboard smoke test', (
      WidgetTester tester,
    ) async {
      final state = AppState();
      await tester.pumpWidget(VoltPlanApp(state: state));
      await tester.pumpAndSettle();

      // Verify Dashboard elements
      expect(find.text('Good morning, Eng. Patrick Mugabo'), findsOneWidget);
      expect(find.text('+ New Project'), findsOneWidget);
      expect(find.text('Recent Projects'), findsOneWidget);
      expect(find.text('Modern Family House'), findsOneWidget);
    });

    testWidgets('Dashboard fits a standard mobile viewport', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetViewInsets);

      await tester.pumpWidget(VoltPlanApp(state: AppState()));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Recent Projects'), findsOneWidget);
      expect(find.byType(MetricCard), findsNothing);
    });

    testWidgets(
      'New project form includes same-screen plan and address search',
      (WidgetTester tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: CreateProjectScreen(state: AppState()),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Choose plan'), findsOneWidget);
        expect(find.text('Project Name *'), findsOneWidget);
        expect(find.text('Client Name *'), findsOneWidget);
        expect(find.byTooltip('Search address'), findsOneWidget);

        await tester.tap(find.byTooltip('Search address'));
        await tester.pumpAndSettle();
        expect(find.text('Find project address'), findsOneWidget);
        expect(
          find.text('Search queries are sent to OpenStreetMap Nominatim.'),
          findsOneWidget,
        );
        tester.view.viewInsets = const FakeViewPadding(bottom: 300);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('Primary buttons use monochrome hover colors in both themes', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: Center(
              child: AppButton(label: 'Continue', onPressed: _noop),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      var button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(
        button.style!.backgroundColor!.resolve({WidgetState.hovered}),
        AppColors.textSecondaryLight,
      );
      expect(
        button.style!.backgroundColor!.resolve({}),
        AppColors.textPrimaryLight,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark(),
          home: const Scaffold(
            body: Center(
              child: AppButton(label: 'Continue', onPressed: _noop),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(
        button.style!.backgroundColor!.resolve({WidgetState.hovered}),
        AppColors.textSecondaryDark,
      );
      expect(
        button.style!.backgroundColor!.resolve({}),
        AppColors.textPrimaryDark,
      );
      expect(
        button.style!.backgroundColor!.resolve({WidgetState.pressed}),
        AppColors.textMutedDark,
      );
    });

    testWidgets('Bottom navigation switches tabs cleanly', (
      WidgetTester tester,
    ) async {
      final state = AppState();
      await tester.pumpWidget(VoltPlanApp(state: state));
      await tester.pumpAndSettle();

      // Tap Projects tab
      await tester.tap(find.text('Projects'));
      await tester.pumpAndSettle();
      expect(
        find.text('Search by project, client, or location...'),
        findsOneWidget,
      );

      // Tap Materials tab (BOQ)
      await tester.tap(find.text('Materials'));
      await tester.pumpAndSettle();
      expect(find.text('Bill of Quantities (BOQ)'), findsOneWidget);
      expect(find.text('Materials Subtotal'), findsOneWidget);

      // Tap Profile tab
      await tester.tap(find.text('Profile'));
      await tester.pumpAndSettle();
      expect(find.text('Profile & Settings'), findsOneWidget);
      expect(find.text('Dark Theme'), findsOneWidget);

      // Toggle dark theme
      await tester.ensureVisible(find.text('Dark Theme'));
      await tester.tap(find.text('Dark Theme'));
      await tester.pumpAndSettle();
      expect(state.themeMode, ThemeMode.dark);
      expect(
        Theme.of(tester.element(find.text('Dark Theme'))).brightness,
        Brightness.dark,
      );
    });

    test('AppState project creation and filtering', () {
      final state = AppState();
      final initialCount = state.projects.length;

      final project = state.createProject(
        name: 'Gisozi Commercial Center',
        client: 'Gisozi Dev Ltd',
        buildingType: 'Commercial',
        location: 'Kigali, Gisozi',
        standard: 'RS IEC 60364',
      );

      expect(state.projects.length, initialCount + 1);
      expect(state.projects.first.name, 'Gisozi Commercial Center');
      expect(state.selectedProject?.id, project.id);

      // Search filter test
      state.setSearchQuery('Gisozi');
      expect(state.filteredProjects.length, 1);
      expect(state.filteredProjects.first.name, 'Gisozi Commercial Center');

      // Clear search
      state.setSearchQuery('');
      expect(state.filteredProjects.length, initialCount + 1);
    });

    test('AppState stores the selected plan with the new project', () {
      final state = AppState();
      final planBytes = Uint8List.fromList([1, 2, 3, 4]);

      final project = state.createProject(
        name: 'West Wing Plan',
        client: 'Sample Client',
        buildingType: 'Residential',
        location: 'Kigali, Rwanda',
        standard: 'RS IEC 60364',
        floorPlanName: 'West_Wing_Plan.pdf',
        floorPlanBytes: planBytes,
      );

      expect(project.floorPlanName, 'West_Wing_Plan.pdf');
      expect(project.floorPlanBytes, same(planBytes));
      expect(project.currentStage, ProjectStage.aiAnalysis);
    });

    test('AppState BOQ quantity update recalculates totals', () {
      final state = AppState();
      final initialTotal = state.totalBoqCost;
      expect(initialTotal, greaterThan(0));

      final firstItem = state.boqItems.first;
      final newQty = firstItem.quantity + 10;
      state.updateBoqQuantity(firstItem.id, newQty);

      expect(state.totalBoqCost, initialTotal + (10 * firstItem.unitPriceRwf));
      expect(state.materialsCost, state.totalBoqCost);
      expect(state.laborCost, greaterThan(0));
      expect(state.contingencyCost, greaterThan(0));
      expect(
        state.grandTotalCost,
        state.materialsCost + state.laborCost + state.contingencyCost,
      );
    });

    testWidgets(
      'CreateProjectScreen file picker selects plan, sets name, and allows removal',
      (WidgetTester tester) async {
        final originalPlatform = FilePickerPlatform.instance;
        final fakePicker = FakeFilePickerPlatform();
        FilePickerPlatform.instance = fakePicker;
        addTearDown(() => FilePickerPlatform.instance = originalPlatform);

        fakePicker.fileToReturn = TestPlatformFile(
          name: 'Kigali_Heights_Commercial_Plan.pdf',
          bytes: Uint8List.fromList([1, 2, 3, 4, 5]),
        );

        final state = AppState();
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: CreateProjectScreen(state: state),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Choose plan'), findsOneWidget);

        // Tap choose plan
        await tester.tap(find.text('Choose plan'));
        await tester.pumpAndSettle();

        expect(fakePicker.pickFileCallCount, 1);
        expect(find.text('Kigali_Heights_Commercial_Plan.pdf'), findsOneWidget);
        expect(find.text('Change'), findsOneWidget);

        // Project name should be populated from the filename
        final nameField = tester.widget<TextFormField>(
          find.widgetWithText(TextFormField, 'Kigali Heights Commercial Plan'),
        );
        expect(nameField.controller?.text, 'Kigali Heights Commercial Plan');

        // Remove plan
        await tester.tap(find.byTooltip('Remove selected plan'));
        await tester.pumpAndSettle();

        expect(find.text('Choose plan'), findsOneWidget);
        expect(find.text('Kigali_Heights_Commercial_Plan.pdf'), findsNothing);
      },
    );

    testWidgets(
      'CreateProjectScreen file picker shows error when file exceeds 25 MB',
      (WidgetTester tester) async {
        final originalPlatform = FilePickerPlatform.instance;
        final fakePicker = FakeFilePickerPlatform();
        FilePickerPlatform.instance = fakePicker;
        addTearDown(() => FilePickerPlatform.instance = originalPlatform);

        // File size greater than 25 MB
        fakePicker.fileToReturn = TestPlatformFile(
          name: 'Huge_Plan.pdf',
          bytes: Uint8List(26 * 1024 * 1024),
        );

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: CreateProjectScreen(state: AppState()),
          ),
        );
        await tester.pumpAndSettle();

        await tester.tap(find.text('Choose plan'));
        await tester.pumpAndSettle();

        expect(find.text('Choose a plan smaller than 25 MB.'), findsOneWidget);
        expect(find.text('Choose plan'), findsOneWidget);
      },
    );

    testWidgets(
      'UploadPlanScreen native file picker uploads plan and transitions to analysis',
      (WidgetTester tester) async {
        final originalPlatform = FilePickerPlatform.instance;
        final fakePicker = FakeFilePickerPlatform();
        FilePickerPlatform.instance = fakePicker;
        addTearDown(() => FilePickerPlatform.instance = originalPlatform);

        final testBytes = Uint8List.fromList([10, 20, 30, 40]);
        fakePicker.fileToReturn = TestPlatformFile(
          name: 'Custom_Villa_Design.png',
          bytes: testBytes,
        );

        final state = AppState();
        final project = state.createProject(
          name: 'Custom Villa',
          client: 'Jane Doe',
          buildingType: 'Residential',
          location: 'Kigali',
          standard: 'RS IEC 60364',
        );

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: UploadPlanScreen(state: state, project: project),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Upload from Device'), findsOneWidget);

        // Tap Upload from Device
        await tester.tap(find.text('Upload from Device'));
        await tester.pump(); // Trigger setState loading
        await tester.pump(const Duration(milliseconds: 400)); // Complete upload delay
        await tester.pump(); // Route push
        await tester.pump(const Duration(milliseconds: 300)); // Transition

        expect(fakePicker.pickFileCallCount, 1);
        final updatedProject = state.projects.firstWhere((p) => p.id == project.id);
        expect(updatedProject.floorPlanName, 'Custom_Villa_Design.png');
        expect(updatedProject.floorPlanBytes, testBytes);
        // Should have navigated to AiAnalysisScreen
        expect(find.byType(AiAnalysisScreen), findsOneWidget);

        // Advance simulation timers so no pending timers remain
        await tester.pump(const Duration(seconds: 6));
      },
    );

    testWidgets(
      'UploadPlanScreen cancels cleanly when user dismisses file picker',
      (WidgetTester tester) async {
        final originalPlatform = FilePickerPlatform.instance;
        final fakePicker = FakeFilePickerPlatform();
        FilePickerPlatform.instance = fakePicker;
        addTearDown(() => FilePickerPlatform.instance = originalPlatform);

        fakePicker.fileToReturn = null; // Dismissed

        final state = AppState();
        final project = state.projects.first;

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: UploadPlanScreen(state: state, project: project),
          ),
        );
        await tester.pumpAndSettle();

        await tester.tap(find.text('Upload from Device'));
        await tester.pumpAndSettle();

        expect(fakePicker.pickFileCallCount, 1);
        expect(find.text('Upload from Device'), findsOneWidget);
        expect(find.byType(UploadPlanScreen), findsOneWidget);
      },
    );

    testWidgets(
      'UploadPlanScreen selects sample drawing directly',
      (WidgetTester tester) async {
        final state = AppState();
        final project = state.createProject(
          name: 'Sample Project',
          client: 'Client',
          buildingType: 'Residential',
          location: 'Kigali',
          standard: 'RS IEC 60364',
        );

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: UploadPlanScreen(state: state, project: project),
          ),
        );
        await tester.pumpAndSettle();

        // Ensure first sample plan's Select button is visible and tap it
        final selectButtons = find.widgetWithText(AppButton, 'Select');
        expect(selectButtons, findsWidgets);

        await tester.ensureVisible(selectButtons.first);
        await tester.pumpAndSettle();

        await tester.tap(selectButtons.first);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 500));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));

        expect(find.byType(AiAnalysisScreen), findsOneWidget);

        // Advance simulation timers so no pending timers remain
        await tester.pump(const Duration(seconds: 6));
      },
    );
  });
}

void _noop() {}
