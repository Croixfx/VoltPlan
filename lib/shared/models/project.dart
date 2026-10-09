import 'dart:typed_data';

enum ProjectStage {
  floorPlan(1, 'Floor Plan'),
  aiAnalysis(2, 'AI Analysis'),
  electricalDesign(3, 'Electrical Design'),
  boq(4, 'BOQ'),
  costEstimate(5, 'Cost Estimate'),
  report(6, 'Report');

  final int step;
  final String title;
  const ProjectStage(this.step, this.title);
}

enum ProjectStatus {
  inProgress('In Progress'),
  completed('Completed'),
  reviewRequired('Review Required'),
  active('Active');

  final String label;
  const ProjectStatus(this.label);
}

class Project {
  final String id;
  final String name;
  final String client;
  final String buildingType;
  final String location;
  final String standard;
  final String notes;
  final ProjectStatus status;
  final ProjectStage currentStage;
  final DateTime updatedAt;
  final DateTime createdAt;
  final String? floorPlanName;
  final Uint8List? floorPlanBytes;
  final int roomsCount;
  final int electricalPointsCount;
  final int circuitsCount;
  final num estimatedCostRwf;

  const Project({
    required this.id,
    required this.name,
    required this.client,
    required this.buildingType,
    required this.location,
    required this.standard,
    this.notes = '',
    required this.status,
    required this.currentStage,
    required this.updatedAt,
    required this.createdAt,
    this.floorPlanName,
    this.floorPlanBytes,
    this.roomsCount = 0,
    this.electricalPointsCount = 0,
    this.circuitsCount = 0,
    this.estimatedCostRwf = 0,
  });

  Project copyWith({
    String? id,
    String? name,
    String? client,
    String? buildingType,
    String? location,
    String? standard,
    String? notes,
    ProjectStatus? status,
    ProjectStage? currentStage,
    DateTime? updatedAt,
    DateTime? createdAt,
    String? floorPlanName,
    Uint8List? floorPlanBytes,
    int? roomsCount,
    int? electricalPointsCount,
    int? circuitsCount,
    num? estimatedCostRwf,
  }) {
    return Project(
      id: id ?? this.id,
      name: name ?? this.name,
      client: client ?? this.client,
      buildingType: buildingType ?? this.buildingType,
      location: location ?? this.location,
      standard: standard ?? this.standard,
      notes: notes ?? this.notes,
      status: status ?? this.status,
      currentStage: currentStage ?? this.currentStage,
      updatedAt: updatedAt ?? this.updatedAt,
      createdAt: createdAt ?? this.createdAt,
      floorPlanName: floorPlanName ?? this.floorPlanName,
      floorPlanBytes: floorPlanBytes ?? this.floorPlanBytes,
      roomsCount: roomsCount ?? this.roomsCount,
      electricalPointsCount:
          electricalPointsCount ?? this.electricalPointsCount,
      circuitsCount: circuitsCount ?? this.circuitsCount,
      estimatedCostRwf: estimatedCostRwf ?? this.estimatedCostRwf,
    );
  }

  factory Project.fromJson(Map<String, dynamic> json) {
    final statusStr = json['status'] as String? ?? 'created';
    ProjectStatus status = ProjectStatus.inProgress;
    ProjectStage stage = ProjectStage.floorPlan;

    if (statusStr == 'uploaded') {
      stage = ProjectStage.aiAnalysis;
      status = ProjectStatus.inProgress;
    } else if (statusStr == 'processing') {
      stage = ProjectStage.aiAnalysis;
      status = ProjectStatus.inProgress;
    } else if (statusStr == 'analyzed' || statusStr == 'completed') {
      stage = ProjectStage.electricalDesign;
      status = ProjectStatus.completed;
    } else if (statusStr == 'failed') {
      status = ProjectStatus.reviewRequired;
    }

    DateTime createdAt = DateTime.now();
    if (json['created_at'] != null) {
      createdAt = DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now();
    }
    DateTime updatedAt = createdAt;
    if (json['updated_at'] != null) {
      updatedAt = DateTime.tryParse(json['updated_at'].toString()) ?? createdAt;
    }

    return Project(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? 'Untitled Project',
      client: json['client'] as String? ?? '',
      buildingType: json['building_type'] as String? ?? 'Residential',
      location: json['location'] as String? ?? '',
      standard: json['standard'] as String? ?? 'RS IEC 60364',
      notes: json['notes'] as String? ?? '',
      status: status,
      currentStage: stage,
      updatedAt: updatedAt,
      createdAt: createdAt,
      floorPlanName: json['floor_plan_name'] as String?,
      roomsCount: (json['rooms_count'] as num?)?.toInt() ?? 0,
      electricalPointsCount: (json['electrical_points_count'] as num?)?.toInt() ?? 0,
      circuitsCount: (json['circuits_count'] as num?)?.toInt() ?? 0,
      estimatedCostRwf: (json['estimated_cost_rwf'] as num?) ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'client': client,
        'building_type': buildingType,
        'location': location,
        'standard': standard,
        'notes': notes,
        'status': status.name,
        'floor_plan_name': floorPlanName,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
      };
}
