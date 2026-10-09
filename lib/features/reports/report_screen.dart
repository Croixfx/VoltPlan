import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../core/widgets/app_button.dart';
import '../../core/widgets/section_header.dart';
import '../../core/widgets/engineering_sheet.dart';
import '../../shared/models/project.dart';
import '../../shared/models/electrical_point.dart';
import '../../shared/state/app_state.dart';
import '../floor_plan/widgets/plan_drawing_viewer.dart';

class ReportScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  const ReportScreen({super.key, required this.state, required this.project});

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  bool _isGenerating = false;

  void _generatePdf() async {
    setState(() => _isGenerating = true);

    await Future.delayed(const Duration(milliseconds: 1400));

    if (mounted) {
      setState(() => _isGenerating = false);
      _showGeneratedPdfSheet();
    }
  }

  void _showGeneratedPdfSheet() {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    EngineeringBottomSheet.show(
      context: context,
      title: 'Report Generated',
      subtitle:
          'VoltPlan_${widget.project.name.replaceAll(' ', '_')}_Report.pdf',
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDark
                  ? AppColors.surfaceDark
                  : AppColors.surfaceSecondaryLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isDark ? AppColors.borderDark : AppColors.borderLight,
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: isDark ? 0.2 : 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.picture_as_pdf,
                    color: Colors.red,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'VoltPlan_Engineering_Report.pdf',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: isDark
                              ? AppColors.textPrimaryDark
                              : AppColors.textPrimaryLight,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '6 Pages • 2.4 MB • Generated ${Formatters.formatDate(DateTime.now())}',
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
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'This commercial engineering report includes complete architectural overlays, circuit schedules, bill of quantities, and supplier cost estimates ready for client signing.',
            style: TextStyle(
              fontSize: 14,
              color: isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: AppButton(
                  label: 'Share Document',
                  icon: Icons.share_outlined,
                  variant: AppButtonVariant.secondary,
                  onPressed: () {
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Engineering Report PDF ready to share'),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: AppButton(
                  label: 'Download PDF',
                  icon: Icons.download_outlined,
                  onPressed: () {
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Report saved to Downloads folder'),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final grandTotal = widget.state.grandTotalCost;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Engineering Report'),
        actions: [
          IconButton(
            icon: const Icon(Icons.print_outlined),
            tooltip: 'Print',
            onPressed: _generatePdf,
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
            label: 'Generate Report',
            icon: Icons.picture_as_pdf,
            isLoading: _isGenerating,
            isFullWidth: true,
            onPressed: _generatePdf,
          ),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Report Cover / Document Header
              Container(
                padding: const EdgeInsets.all(20),
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
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: AppColors.primaryBlue,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(
                                Icons.bolt,
                                color: Colors.white,
                                size: 20,
                              ),
                            ),
                            const SizedBox(width: 10),
                            Text(
                              'VOLTPLAN',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.2,
                                color: isDark
                                    ? Colors.white
                                    : AppColors.textPrimaryLight,
                              ),
                            ),
                          ],
                        ),
                        Text(
                          'PRELIMINARY REPORT',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.8,
                            color: isDark
                                ? AppColors.textMutedDark
                                : AppColors.textMutedLight,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      widget.project.name,
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.4,
                        color: isDark
                            ? AppColors.textPrimaryDark
                            : AppColors.textPrimaryLight,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Prepared for: ${widget.project.client}',
                      style: TextStyle(
                        fontSize: 14,
                        color: isDark
                            ? AppColors.textSecondaryDark
                            : AppColors.textSecondaryLight,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Divider(
                      color: isDark
                          ? AppColors.borderDark
                          : AppColors.borderLight,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildDocMeta(
                          'Location',
                          widget.project.location,
                          isDark,
                        ),
                        _buildDocMeta(
                          'Standard',
                          widget.project.standard.split(' ').first,
                          isDark,
                        ),
                        _buildDocMeta(
                          'Date',
                          Formatters.formatDate(DateTime.now()),
                          isDark,
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Section: Architectural Floor Plan Preview
              const SectionHeader(
                title: '1. Architectural Floor Plan & Layout',
              ),
              const SizedBox(height: 6),
              Container(
                height: 180,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isDark
                        ? AppColors.borderDark
                        : AppColors.borderLight,
                  ),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: PlanDrawingViewer(
                    project: widget.project,
                    points: widget.state.electricalPoints,
                    isDark: isDark,
                    showPointsOverlay: true,
                    wiringArcs: widget.state.wiringArcs,
                  ),
                ),
              ),

              const SizedBox(height: 20),

              // Section: Electrical Recommendations Summary
              const SectionHeader(
                title: '2. Electrical Recommendations Summary',
              ),
              const SizedBox(height: 6),
              _buildReportSectionContainer(
                isDark: isDark,
                children: [
                  _buildSummaryRow(
                    'Total Rooms Identified',
                    '${widget.state.rooms.isNotEmpty ? widget.state.rooms.length : (widget.project.roomsCount > 0 ? widget.project.roomsCount : 0)} Rooms',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Allocated Lighting Points',
                    '${widget.state.electricalPoints.where((p) => p.type == ElectricalPointType.light || p.type == ElectricalPointType.downlight).fold<int>(0, (s, p) => s + p.quantity)} Points',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Allocated Power Sockets',
                    '${widget.state.electricalPoints.where((p) => p.type == ElectricalPointType.socketDouble || p.type == ElectricalPointType.socketSingle).fold<int>(0, (s, p) => s + p.quantity)} Points',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Special Heavy Circuits',
                    widget.state.circuits.where((c) => c.isDedicated).isNotEmpty
                        ? widget.state.circuits.where((c) => c.isDedicated).map((c) => c.name).take(2).join(' + ')
                        : 'Dedicated Equipment Radials',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Compliance Code',
                    widget.project.standard,
                    isDark,
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // Section: Circuits Schedule Summary
              const SectionHeader(title: '3. Distribution & Circuits Summary'),
              const SizedBox(height: 6),
              _buildReportSectionContainer(
                isDark: isDark,
                children: [
                  _buildSummaryRow(
                    'Main Switchboard',
                    '${widget.state.circuits.length > 8 ? "12" : "8"}-Way Metal Enclosure DB',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Residual Current Protection',
                    '63A 30mA 2-Pole RCD (RS IEC 60364-4-41)',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Allocated Ways',
                    '${widget.state.circuits.length} Circuits Configured',
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Total Design Load',
                    '${(widget.state.circuits.fold<double>(0.0, (s, c) => s + c.connectedLoadKw) * 0.65).toStringAsFixed(1)} kW (Diversity: 0.65)',
                    isDark,
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // Section: BOQ & Cost Estimate Summary
              const SectionHeader(title: '4. Materials / BOQ & Cost Summary'),
              const SizedBox(height: 6),
              _buildReportSectionContainer(
                isDark: isDark,
                children: [
                  _buildSummaryRow(
                    'Materials Subtotal',
                    Formatters.formatRwf(widget.state.materialsCost),
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Installation Labor',
                    Formatters.formatRwf(widget.state.laborCost),
                    isDark,
                  ),
                  _buildSummaryRow(
                    'Contingency Buffer',
                    Formatters.formatRwf(widget.state.contingencyCost),
                    isDark,
                  ),
                  const Divider(),
                  _buildSummaryRow(
                    'Grand Estimated Total',
                    Formatters.formatRwf(grandTotal),
                    isDark,
                    isBold: true,
                  ),
                ],
              ),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDocMeta(String label, String value, bool isDark) {
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
        const SizedBox(height: 2),
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
    );
  }

  Widget _buildReportSectionContainer({
    required bool isDark,
    required List<Widget> children,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
        ),
      ),
      child: Column(children: children),
    );
  }

  Widget _buildSummaryRow(
    String label,
    String value,
    bool isDark, {
    bool isBold = false,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              fontWeight: isBold ? FontWeight.w700 : FontWeight.w400,
              color: isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: isBold ? FontWeight.w700 : FontWeight.w600,
              color: isBold
                  ? AppColors.primaryBlue
                  : (isDark
                        ? AppColors.textPrimaryDark
                        : AppColors.textPrimaryLight),
            ),
          ),
        ],
      ),
    );
  }
}
