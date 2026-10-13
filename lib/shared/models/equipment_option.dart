import 'electrical_point.dart';

/// One entry of the backend equipment catalog (GET /api/equipment).
class EquipmentOption {
  final String typeId;
  final String name;
  final String category;
  final List<String> allowedRooms;
  final List<String> forbiddenRooms;

  const EquipmentOption({
    required this.typeId,
    required this.name,
    required this.category,
    this.allowedRooms = const [],
    this.forbiddenRooms = const [],
  });

  ElectricalPointType get pointType =>
      ElectricalPointType.fromBackendType(typeId);

  factory EquipmentOption.fromJson(Map<String, dynamic> json) {
    List<String> strings(dynamic v) =>
        (v as List?)?.map((e) => e.toString()).toList() ?? const [];
    return EquipmentOption(
      typeId: json['type_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      allowedRooms: strings(json['allowed_rooms']),
      forbiddenRooms: strings(json['forbidden_rooms']),
    );
  }

  /// Used when the catalog endpoint is unreachable. Mirrors backend/app/catalog.
  static const List<EquipmentOption> fallback = [
    EquipmentOption(typeId: 'lighting', name: 'LED Ceiling Luminaire', category: 'lighting'),
    EquipmentOption(typeId: 'switch_1way', name: '1-Way Light Switch', category: 'switching'),
    EquipmentOption(typeId: 'switch_2way', name: '2-Way Light Switch', category: 'switching'),
    EquipmentOption(typeId: 'twin_socket', name: '13A Twin Socket Outlet', category: 'socket'),
    EquipmentOption(typeId: 'single_socket', name: '13A Single Socket / Shaver Outlet', category: 'socket'),
    EquipmentOption(typeId: 'cooker_point', name: '45A Cooker Control Unit', category: 'appliance'),
    EquipmentOption(typeId: 'water_heater', name: 'Water Heater Isolator', category: 'appliance'),
    EquipmentOption(typeId: 'ac_point', name: 'Air Conditioner Isolator', category: 'appliance'),
    EquipmentOption(typeId: 'extractor_fan', name: 'Extractor Fan', category: 'ventilation'),
    EquipmentOption(typeId: 'outdoor_light', name: 'Outdoor Wall Luminaire', category: 'lighting'),
    EquipmentOption(typeId: 'smoke_detector', name: 'Smoke Detector (Mains, Interlinked)', category: 'safety'),
    EquipmentOption(typeId: 'emergency_light', name: 'Emergency Luminaire', category: 'safety'),
    EquipmentOption(typeId: 'data_point', name: 'Data Outlet (Cat6)', category: 'communications'),
    EquipmentOption(typeId: 'tv_point', name: 'TV / Satellite Outlet', category: 'communications'),
    EquipmentOption(typeId: 'distribution_board', name: 'Consumer Unit / Distribution Board', category: 'distribution'),
  ];
}
