import 'room.dart';
import 'architectural_feature.dart';
import 'electrical_point.dart';
import 'circuit.dart';
import 'wiring_arc.dart';
import 'boq_item.dart';
import 'cost_estimate.dart';

class AnalysisResult {
  final String projectId;
  final String status;
  final String currentStep;
  final String standardApplied;
  final List<Room> rooms;
  final List<ArchitecturalFeature> architecturalFeatures;
  final List<String> observations;
  final List<String> warnings;
  final List<ElectricalPoint> electricalPoints;
  final List<Circuit> circuits;
  final List<BoqItem> boqItems;
  final List<WiringArc> wiringArcs;
  final CostEstimate? costEstimate;
  final String engineeringDisclaimer;

  const AnalysisResult({
    required this.projectId,
    required this.status,
    required this.currentStep,
    required this.standardApplied,
    required this.rooms,
    required this.architecturalFeatures,
    required this.observations,
    required this.warnings,
    required this.electricalPoints,
    required this.circuits,
    required this.boqItems,
    this.wiringArcs = const [],
    this.costEstimate,
    required this.engineeringDisclaimer,
  });

  AnalysisResult copyWith({
    String? projectId,
    String? status,
    String? currentStep,
    String? standardApplied,
    List<Room>? rooms,
    List<ArchitecturalFeature>? architecturalFeatures,
    List<String>? observations,
    List<String>? warnings,
    List<ElectricalPoint>? electricalPoints,
    List<Circuit>? circuits,
    List<BoqItem>? boqItems,
    List<WiringArc>? wiringArcs,
    CostEstimate? costEstimate,
    String? engineeringDisclaimer,
  }) {
    return AnalysisResult(
      projectId: projectId ?? this.projectId,
      status: status ?? this.status,
      currentStep: currentStep ?? this.currentStep,
      standardApplied: standardApplied ?? this.standardApplied,
      rooms: rooms ?? this.rooms,
      architecturalFeatures: architecturalFeatures ?? this.architecturalFeatures,
      observations: observations ?? this.observations,
      warnings: warnings ?? this.warnings,
      electricalPoints: electricalPoints ?? this.electricalPoints,
      circuits: circuits ?? this.circuits,
      boqItems: boqItems ?? this.boqItems,
      wiringArcs: wiringArcs ?? this.wiringArcs,
      costEstimate: costEstimate ?? this.costEstimate,
      engineeringDisclaimer: engineeringDisclaimer ?? this.engineeringDisclaimer,
    );
  }

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    final rawRooms = (json['rooms'] as List<dynamic>?) ?? [];
    final rooms = rawRooms
        .map((r) => Room.fromJson(r as Map<String, dynamic>))
        .toList();

    final rawFeatures = (json['architectural_features'] as List<dynamic>?) ?? [];
    final features = rawFeatures
        .map((f) => ArchitecturalFeature.fromJson(f as Map<String, dynamic>))
        .toList();

    final rawObservations = (json['observations'] as List<dynamic>?) ?? [];
    final observations = rawObservations.map((o) => o.toString()).toList();

    final rawWarnings = (json['warnings'] as List<dynamic>?) ?? [];
    final warnings = rawWarnings.map((w) => w.toString()).toList();

    final rawPoints = (json['electrical_points'] as List<dynamic>?) ?? [];
    final points = rawPoints
        .map((p) => ElectricalPoint.fromJson(p as Map<String, dynamic>))
        .toList();

    final rawCircuits = (json['circuits'] as List<dynamic>?) ?? [];
    final circuits = rawCircuits
        .map((c) => Circuit.fromJson(c as Map<String, dynamic>))
        .toList();

    final rawBoq = (json['boq_items'] as List<dynamic>?) ?? [];
    final boqItems = rawBoq
        .map((b) => BoqItem.fromJson(b as Map<String, dynamic>))
        .toList();

    final rawArcs = (json['wiring_arcs'] as List<dynamic>?) ?? [];
    final wiringArcs = rawArcs
        .map((a) => WiringArc.fromJson(a as Map<String, dynamic>))
        .toList();

    CostEstimate? costEst;
    if (json['cost_estimate'] != null && json['cost_estimate'] is Map<String, dynamic>) {
      costEst = CostEstimate.fromJson(json['cost_estimate'] as Map<String, dynamic>);
    }

    return AnalysisResult(
      projectId: json['project_id'] as String? ?? '',
      status: json['status'] as String? ?? 'completed',
      currentStep: json['current_step'] as String? ?? 'completed',
      standardApplied: json['standard_applied'] as String? ?? 'RS IEC 60364',
      rooms: rooms,
      architecturalFeatures: features,
      observations: observations,
      warnings: warnings,
      electricalPoints: points,
      circuits: circuits,
      boqItems: boqItems,
      wiringArcs: wiringArcs,
      costEstimate: costEst,
      engineeringDisclaimer: json['engineering_disclaimer'] as String? ?? '',
    );
  }
}
