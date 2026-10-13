import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/network/api_exceptions.dart';
import '../../core/widgets/app_button.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import 'data/calculations_repository.dart';

/// Voltage drop per circuit and maximum demand for the main supply.
/// These are preliminary figures that an electrician must verify; the screen
/// shows every assumption and says plainly when something cannot be calculated.
class CalculationsScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  /// Injectable for tests; defaults to the real backend.
  final CalculationsRepository? repository;

  const CalculationsScreen({super.key, required this.state, required this.project, this.repository});

  @override
  State<CalculationsScreen> createState() => _CalculationsScreenState();
}

class _CalculationsScreenState extends State<CalculationsScreen> {
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;

  // Installation conditions for the cable-capacity check
  String _method = 'B2';
  int _ambientC = 30;
  int _grouped = 1;

  String get _pid => (widget.state.selectedProject ?? widget.project).id;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _data == null; // keep showing the previous figures while they refresh
      _error = null;
    });
    try {
      final data = await (widget.repository ?? CalculationsRepository()).getCalculations(
        _pid,
        method: _method,
        ambientC: _ambientC,
        groupedCircuits: _grouped,
      );
      if (mounted) setState(() => _data = data);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Calculations'),
        actions: [IconButton(tooltip: 'Recalculate', icon: const Icon(Icons.refresh), onPressed: _load)],
      ),
      body: SafeArea(child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              AppButton(label: 'Try again', onPressed: _load, height: 38),
            ],
          ),
        ),
      );
    }
    final data = _data!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _banner(data['disclaimer'] as String? ?? ''),
        if (data['geometry_needs_regeneration'] == true)
          _banner('Rooms or doors were corrected after the equipment was generated. '
              'Regenerate the equipment so these figures match.', color: Colors.red),
        const SizedBox(height: 12),
        _maxDemandCard(data['max_demand'] as Map<String, dynamic>),
        const SizedBox(height: 12),
        _voltageDropCard(data['voltage_drop'] as Map<String, dynamic>),
        if (data['cable_capacity'] != null) ...[
          const SizedBox(height: 12),
          _capacityCard(data['cable_capacity'] as Map<String, dynamic>),
        ],
        const SizedBox(height: 12),
        _references(List<String>.from(data['references'] as List? ?? const [])),
      ],
    );
  }

  Widget _banner(String text, {Color color = Colors.orange}) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Text(text, style: const TextStyle(fontSize: 12.5)),
      );

  Widget _card({required String title, required List<Widget> children}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    // Material (not a decorated Container) so ExpansionTile / ink effects paint correctly.
    return Material(
      color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: isDark ? AppColors.borderDark : AppColors.borderLight),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _maxDemandCard(Map<String, dynamic> md) {
    final total = md['total'] as Map<String, dynamic>;
    final suggested = md['suggested_main_switch'] as Map<String, dynamic>;
    final phases = (md['per_phase'] as Map<String, dynamic>? ?? {});
    final notes = List<String>.from(md['notes'] as List? ?? const []);
    String rating(dynamic v) => v == null ? 'above 125 A' : '$v A';

    return _card(title: 'Maximum demand', children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text('${total['total_demand_a']} A',
              key: const Key('max-demand-total'),
              style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
          const SizedBox(width: 10),
          Text('${md['total_demand_kva']} kVA at 230 V', style: const TextStyle(fontSize: 13)),
        ],
      ),
      const SizedBox(height: 4),
      Text('Connected load ${md['connected_load_kw']} kW • '
          '${md['diversity_applied'] == true ? 'household diversity applied' : 'no diversity applied'}',
          style: const TextStyle(fontSize: 12.5)),
      const Divider(height: 20),
      Text('Suggested main switch', style: Theme.of(context).textTheme.labelLarge),
      Text('3-phase supply: ${rating(suggested['three_phase_supply_a'])} per phase • '
          'single-phase supply: ${rating(suggested['single_phase_supply_a'])}',
          key: const Key('main-switch'), style: const TextStyle(fontSize: 13)),
      const SizedBox(height: 4),
      Text(suggested['note'] as String? ?? '', style: const TextStyle(fontSize: 12)),
      if (phases.isNotEmpty) ...[
        const Divider(height: 20),
        Text('Per phase (imbalance ${md['phase_imbalance_percent']} %)', style: Theme.of(context).textTheme.labelLarge),
        for (final e in phases.entries)
          Text('${e.key}: ${(e.value as Map<String, dynamic>)['total_demand_a']} A',
              style: const TextStyle(fontSize: 13)),
      ],
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Assumptions', style: TextStyle(fontSize: 13)),
        children: [for (final n in notes) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $n', style: const TextStyle(fontSize: 12)))],
      ),
    ]);
  }

  Widget _voltageDropCard(Map<String, dynamic> vd) {
    final circuits = List<Map<String, dynamic>>.from(vd['circuits'] as List? ?? const []);
    final assumptions = List<String>.from(vd['assumptions'] as List? ?? const []);

    if (vd['status'] != 'calculated') {
      return _card(title: 'Voltage drop', children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.info_outline, color: Colors.orange, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(vd['reason'] as String? ?? 'Not calculated.',
                  key: const Key('vd-not-calculated'), style: const TextStyle(fontSize: 13)),
            ),
          ],
        ),
        const SizedBox(height: 4),
        const Text('Voltage drop is only reported when it can be measured, never estimated.',
            style: TextStyle(fontSize: 12)),
      ]);
    }

    final summary = vd['summary'] as Map<String, dynamic>? ?? {};
    return _card(title: 'Voltage drop', children: [
      Text('${summary['circuits_checked']} circuits checked • ${summary['failing']} failing • '
          '${summary['marginal']} marginal',
          style: const TextStyle(fontSize: 13)),
      const SizedBox(height: 8),
      for (final c in circuits) _circuitRow(c),
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Assumptions', style: TextStyle(fontSize: 13)),
        children: [for (final a in assumptions) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $a', style: const TextStyle(fontSize: 12)))],
      ),
    ]);
  }

  Widget _dropdown<T>({
    required Key fieldKey,
    required String label,
    required T value,
    required List<T> items,
    required String Function(T) text,
    required ValueChanged<T> onChanged,
  }) {
    return SizedBox(
      width: 165,
      child: DropdownButtonFormField<T>(
        key: fieldKey,
        initialValue: value,
        isDense: true,
        isExpanded: true,
        decoration: InputDecoration(labelText: label, isDense: true, border: const OutlineInputBorder()),
        items: [for (final i in items) DropdownMenuItem(value: i, child: Text(text(i), style: const TextStyle(fontSize: 13)))],
        onChanged: (v) {
          if (v != null && v != value) onChanged(v);
        },
      ),
    );
  }

  Widget _capacityCard(Map<String, dynamic> cap) {
    final options = cap['options'] as Map<String, dynamic>;
    final available = options['available'] as Map<String, dynamic>;
    final circuits = List<Map<String, dynamic>>.from(cap['circuits'] as List? ?? const []);
    final assumptions = List<String>.from(cap['assumptions'] as List? ?? const []);
    final summary = cap['summary'] as Map<String, dynamic>? ?? {};

    return _card(title: 'Cable current capacity', children: [
      Text('Is every cable big enough for the breaker protecting it?  Ib ≤ In ≤ Iz',
          style: const TextStyle(fontSize: 12.5)),
      const SizedBox(height: 10),
      Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          _dropdown<String>(
            fieldKey: const Key('cap-method'),
            label: 'Installation',
            value: options['method'] as String,
            items: List<String>.from(available['methods'] as List),
            text: (m) => m,
            onChanged: (v) {
              setState(() => _method = v);
              _load();
            },
          ),
          _dropdown<int>(
            fieldKey: const Key('cap-ambient'),
            label: 'Ambient',
            value: options['ambient_c'] as int,
            items: List<int>.from(available['ambient_c'] as List),
            text: (t) => '$t °C',
            onChanged: (v) {
              setState(() => _ambientC = v);
              _load();
            },
          ),
          _dropdown<int>(
            fieldKey: const Key('cap-grouped'),
            label: 'Bunched circuits',
            value: options['grouped_circuits'] as int,
            items: List<int>.from(available['grouped_circuits'] as List),
            text: (n) => n == 1 ? 'none' : '$n together',
            onChanged: (v) {
              setState(() => _grouped = v);
              _load();
            },
          ),
        ],
      ),
      const SizedBox(height: 4),
      Text('Method ${options['method']}: ${options['method_description']}',
          key: const Key('cap-method-description'), style: const TextStyle(fontSize: 12)),
      const SizedBox(height: 10),
      Text('${summary['circuits_checked']} circuits checked • ${summary['failing']} failing • '
          '${summary['marginal']} marginal',
          key: const Key('cap-summary'), style: const TextStyle(fontSize: 13)),
      const SizedBox(height: 8),
      for (final c in circuits) _capacityRow(c),
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Assumptions', style: TextStyle(fontSize: 13)),
        children: [for (final a in assumptions) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $a', style: const TextStyle(fontSize: 12)))],
      ),
    ]);
  }

  Widget _capacityRow(Map<String, dynamic> c) {
    final status = c['status'] as String? ?? 'not_calculated';
    final color = switch (status) {
      'pass' => Colors.green,
      'marginal' => Colors.orange,
      'fail' => Colors.red,
      _ => Colors.grey,
    };
    final lines = <String>[];
    if (status == 'not_calculated') {
      lines.add(c['reason'] as String? ?? '');
    } else {
      lines.add('${c['cable_mm2']} mm² cable, ${c['protective_device_a']} A device → capacity ${c['capacity_a']} A '
          '(${c['utilisation_percent']} % used)');
      if (c['reason'] != null) lines.add(c['reason'] as String);
      if (status == 'fail') {
        final fixes = <String>[
          if (c['recommended_cable_mm2'] != null) 'use at least ${c['recommended_cable_mm2']} mm²',
          if (c['reduce_device_to_a'] != null) 'or reduce the device to ${c['reduce_device_to_a']} A',
        ];
        if (fixes.isNotEmpty) lines.add(fixes.join(' '));
      } else {
        final n = c['max_grouped_circuits'];
        lines.add(n == 1 ? 'must not share its route with other circuits' : 'fine with up to $n circuits bunched');
      }
    }
    return Padding(
      key: Key('cap-row-${c['circuit_id']}'),
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${c['name']}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                for (final l in lines) Text(l, style: const TextStyle(fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
            child: Text(status.replaceAll('_', ' ').toUpperCase(),
                style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: color)),
          ),
        ],
      ),
    );
  }

  Widget _circuitRow(Map<String, dynamic> c) {
    final status = c['status'] as String? ?? 'not_calculated';
    final color = switch (status) {
      'pass' => Colors.green,
      'marginal' => Colors.orange,
      'fail' => Colors.red,
      _ => Colors.grey,
    };
    final subtitle = status == 'not_calculated'
        ? (c['reason'] as String? ?? '')
        : '${c['length_m']} m • ${c['design_current_a']} A • ${c['cable_mm2']} mm²'
            '${c['recommended_cable_mm2'] != null ? ' • use at least ${c['recommended_cable_mm2']} mm²' : ''}';
    return Padding(
      key: Key('vd-row-${c['circuit_id']}'),
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${c['name']}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                Text(subtitle, style: const TextStyle(fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          if (status != 'not_calculated')
            Text('${c['drop_percent']} % / ${c['limit_percent']} %', style: const TextStyle(fontSize: 12.5)),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(status.replaceAll('_', ' ').toUpperCase(),
                style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: color)),
          ),
        ],
      ),
    );
  }

  Widget _references(List<String> refs) => ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Formulas and references', style: TextStyle(fontSize: 13)),
        children: [for (final r in refs) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $r', style: const TextStyle(fontSize: 12)))],
      );
}
