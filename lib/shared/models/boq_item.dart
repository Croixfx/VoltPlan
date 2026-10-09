enum BoqCategory {
  all('All Items'),
  cables('Cables'),
  lighting('Lighting'),
  switches('Switches'),
  sockets('Sockets'),
  protection('Protection'),
  distributionBoard('Distribution Board'),
  conduits('Conduits'),
  accessories('Accessories');

  final String label;
  const BoqCategory(this.label);

  static BoqCategory fromBackendCategory(String cat) {
    final lower = cat.toLowerCase();
    if (lower.contains('cable') || lower.contains('conduit')) {
      return BoqCategory.cables;
    } else if (lower.contains('luminaire') || lower.contains('light')) {
      return BoqCategory.lighting;
    } else if (lower.contains('switch')) {
      return BoqCategory.switches;
    } else if (lower.contains('socket')) {
      return BoqCategory.sockets;
    } else if (lower.contains('distribution') || lower.contains('board') || lower.contains('consumer')) {
      return BoqCategory.distributionBoard;
    } else if (lower.contains('protection') || lower.contains('earth') || lower.contains('rcd') || lower.contains('mcb')) {
      return BoqCategory.protection;
    } else {
      return BoqCategory.accessories;
    }
  }
}

class BoqItem {
  final String id;
  final BoqCategory category;
  final String item;
  final String specification;
  final double quantity;
  final String unit; // m, pcs, sets, rolls
  final num unitPriceRwf;
  final String? itemCode;
  final String? pricingStatus;
  final String? notes;

  const BoqItem({
    required this.id,
    required this.category,
    required this.item,
    required this.specification,
    required this.quantity,
    required this.unit,
    required this.unitPriceRwf,
    this.itemCode,
    this.pricingStatus = 'STANDARD_ESTIMATE',
    this.notes,
  });

  num get totalRwf => quantity * unitPriceRwf;

  factory BoqItem.fromJson(Map<String, dynamic> json) {
    final catStr = json['category'] as String? ?? 'General';
    final category = BoqCategory.fromBackendCategory(catStr);

    return BoqItem(
      id: json['id'] as String? ?? '',
      category: category,
      item: json['description'] as String? ?? json['item'] as String? ?? 'Equipment',
      specification: json['specification'] as String? ?? '',
      quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
      unit: json['unit'] as String? ?? 'pcs',
      unitPriceRwf: (json['unit_price_rwf'] as num?) ?? (json['unitPriceRwf'] as num?) ?? 0,
      itemCode: json['item_code'] as String?,
      pricingStatus: json['pricing_status'] as String? ?? 'STANDARD_ESTIMATE',
      notes: json['notes'] as String?,
    );
  }

  BoqItem copyWith({
    String? id,
    BoqCategory? category,
    String? item,
    String? specification,
    double? quantity,
    String? unit,
    num? unitPriceRwf,
    String? itemCode,
    String? pricingStatus,
    String? notes,
  }) {
    return BoqItem(
      id: id ?? this.id,
      category: category ?? this.category,
      item: item ?? this.item,
      specification: specification ?? this.specification,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      unitPriceRwf: unitPriceRwf ?? this.unitPriceRwf,
      itemCode: itemCode ?? this.itemCode,
      pricingStatus: pricingStatus ?? this.pricingStatus,
      notes: notes ?? this.notes,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'category': category.label,
        'item': item,
        'description': item,
        'specification': specification,
        'quantity': quantity,
        'unit': unit,
        'unit_price_rwf': unitPriceRwf,
        'total_price_rwf': totalRwf,
        'item_code': itemCode,
        'pricing_status': pricingStatus,
        'notes': notes,
      };
}
