import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../../core/constants/app_colors.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/section_header.dart';
import '../../shared/models/project.dart';
import '../../shared/mock_data/mock_data.dart';
import '../../shared/state/app_state.dart';
import '../analysis/ai_analysis_screen.dart';

class UploadPlanScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  const UploadPlanScreen({
    super.key,
    required this.state,
    required this.project,
  });

  @override
  State<UploadPlanScreen> createState() => _UploadPlanScreenState();
}

class _UploadPlanScreenState extends State<UploadPlanScreen> {
  String? _selectedFile;
  bool _isUploading = false;

  @override
  void initState() {
    super.initState();
    _selectedFile = widget.project.floorPlanName;
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _pickFileFromDevice() async {
    if (_isUploading) return;

    setState(() => _isUploading = true);
    try {
      final file = await FilePicker.pickFile(
        dialogTitle: 'Select Architectural Plan',
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'png', 'jpg', 'jpeg'],
      );

      if (file == null || !mounted) {
        if (mounted) setState(() => _isUploading = false);
        return;
      }

      final size = await file.length();
      if (!mounted) return;

      final bytes = await file.readAsBytes();
      if (!mounted) return;

      final effectiveSize = size ?? bytes.length;
      if (effectiveSize > 25 * 1024 * 1024) {
        _showMessage('Choose a plan smaller than 25 MB.');
        setState(() => _isUploading = false);
        return;
      }

      setState(() => _selectedFile = file.name);

      await widget.state.uploadProjectPlan(
        widget.project.id,
        file.name,
        bytes,
      );

      final activeProj = widget.state.selectedProject ?? widget.project;

      if (mounted) {
        setState(() => _isUploading = false);
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) =>
                AiAnalysisScreen(state: widget.state, project: activeProj),
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        _showMessage('Failed to upload floor plan: $error');
        setState(() => _isUploading = false);
      }
    }
  }

  void _handleUpload(String fileName) async {
    if (_isUploading) return;

    setState(() {
      _selectedFile = fileName;
      _isUploading = true;
    });

    await Future.delayed(const Duration(milliseconds: 400));

    widget.state.setProjectFloorPlan(widget.project.id, fileName);

    if (mounted) {
      setState(() => _isUploading = false);
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) =>
              AiAnalysisScreen(state: widget.state, project: widget.project),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(title: const Text('Upload Architectural Plan')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header text
              Text(
                'Upload Floor Plan',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.4,
                  color: isDark
                      ? AppColors.textPrimaryDark
                      : AppColors.textPrimaryLight,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Upload the architectural drawing to enable automated room detection, electrical symbol allocation, and BOQ estimation.',
                style: TextStyle(
                  fontSize: 14,
                  color: isDark
                      ? AppColors.textSecondaryDark
                      : AppColors.textSecondaryLight,
                  height: 1.4,
                ),
              ),

              const SizedBox(height: 24),

              // Large Upload Area
              Material(
                color: isDark
                    ? AppColors.surfaceDark
                    : AppColors.surfaceSecondaryLight,
                borderRadius: BorderRadius.circular(16),
                child: InkWell(
                  borderRadius: BorderRadius.circular(16),
                  onTap: _isUploading ? null : _pickFileFromDevice,
                  child: Container(
                    padding: const EdgeInsets.all(32),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isDark
                            ? AppColors.borderSubtleDark
                            : AppColors.primaryBlue.withValues(alpha: 0.4),
                        width: 1.8,
                        strokeAlign: BorderSide.strokeAlignInside,
                      ),
                    ),
                    child: Column(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppColors.primaryBlue.withValues(
                              alpha: isDark ? 0.2 : 0.1,
                            ),
                            shape: BoxShape.circle,
                          ),
                          child: _isUploading
                              ? const SizedBox(
                                  width: 40,
                                  height: 40,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 3,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      AppColors.primaryBlue,
                                    ),
                                  ),
                                )
                              : const Icon(
                                  Icons.cloud_upload_outlined,
                                  size: 40,
                                  color: AppColors.primaryBlue,
                                ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _selectedFile != null
                              ? 'Selected: $_selectedFile'
                              : 'Drag & drop or tap to browse',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: isDark
                                ? AppColors.textPrimaryDark
                                : AppColors.textPrimaryLight,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Supported formats: PDF, PNG, JPG',
                          style: TextStyle(
                            fontSize: 14,
                            color: isDark
                                ? AppColors.textSecondaryDark
                                : AppColors.textSecondaryLight,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Maximum file size: 25 MB',
                          style: TextStyle(
                            fontSize: 13,
                            color: isDark
                                ? AppColors.textMutedDark
                                : AppColors.textMutedLight,
                          ),
                        ),
                        const SizedBox(height: 20),
                        AppButton(
                          label: 'Upload from Device',
                          icon: Icons.file_upload_outlined,
                          isLoading: _isUploading,
                          onPressed: _pickFileFromDevice,
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 28),

              // Recent Floor Plans / Sample Engineering Drawings
              const SectionHeader(
                title: 'Sample Engineering Drawings',
                subtitle:
                    'Select a pre-configured architectural plan for immediate analysis',
              ),
              const SizedBox(height: 8),

              ...MockData.sampleFloorPlans.map((sampleName) {
                final isSelected = _selectedFile == sampleName;
                final isPdf = sampleName.endsWith('.pdf');

                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Material(
                    color: isDark
                        ? AppColors.surfaceDark
                        : AppColors.surfaceLight,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                      side: BorderSide(
                        color: isSelected
                            ? AppColors.primaryBlue
                            : (isDark
                                  ? AppColors.borderDark
                                  : AppColors.borderLight),
                        width: isSelected ? 1.5 : 1,
                      ),
                    ),
                    child: ListTile(
                      onTap: _isUploading
                          ? null
                          : () => _handleUpload(sampleName),
                      leading: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: isPdf
                              ? Colors.red.withValues(alpha: isDark ? 0.2 : 0.1)
                              : AppColors.primaryBlue.withValues(
                                  alpha: isDark ? 0.2 : 0.1,
                                ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          isPdf ? Icons.picture_as_pdf : Icons.image_outlined,
                          size: 20,
                          color: isPdf ? Colors.red : AppColors.primaryBlue,
                        ),
                      ),
                      title: Text(
                        sampleName,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: isDark
                              ? AppColors.textPrimaryDark
                              : AppColors.textPrimaryLight,
                        ),
                      ),
                      subtitle: Text(
                        'Vector architectural layout • 1.8 MB',
                        style: TextStyle(
                          fontSize: 13,
                          color: isDark
                              ? AppColors.textMutedDark
                              : AppColors.textMutedLight,
                        ),
                      ),
                      trailing: AppButton(
                        label: 'Select',
                        height: 32,
                        variant: AppButtonVariant.secondary,
                        onPressed: _isUploading
                            ? null
                            : () => _handleUpload(sampleName),
                      ),
                    ),
                  ),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }
}
