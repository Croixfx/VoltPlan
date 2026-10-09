class CostEstimate {
  final String projectId;
  final double materialsCostRwf;
  final double laborCostRwf;
  final double contingencyCostRwf;
  final double grandTotalRwf;
  final double laborPercentage;
  final double contingencyPercentage;
  final String currency;
  final bool isLaborEstimated;
  final bool isContingencyEstimated;
  final List<String> assumptions;
  final String disclaimer;

  const CostEstimate({
    required this.projectId,
    required this.materialsCostRwf,
    required this.laborCostRwf,
    required this.contingencyCostRwf,
    required this.grandTotalRwf,
    this.laborPercentage = 28.0,
    this.contingencyPercentage = 12.0,
    this.currency = 'RWF',
    this.isLaborEstimated = true,
    this.isContingencyEstimated = true,
    this.assumptions = const [],
    this.disclaimer = '',
  });

  factory CostEstimate.fromJson(Map<String, dynamic> json) {
    return CostEstimate(
      projectId: json['project_id'] as String? ?? '',
      materialsCostRwf: (json['materials_cost_rwf'] as num?)?.toDouble() ?? 0.0,
      laborCostRwf: (json['labor_cost_rwf'] as num?)?.toDouble() ?? 0.0,
      contingencyCostRwf: (json['contingency_cost_rwf'] as num?)?.toDouble() ?? 0.0,
      grandTotalRwf: (json['grand_total_rwf'] as num?)?.toDouble() ?? 0.0,
      laborPercentage: (json['labor_percentage'] as num?)?.toDouble() ?? 28.0,
      contingencyPercentage: (json['contingency_percentage'] as num?)?.toDouble() ?? 12.0,
      currency: json['currency'] as String? ?? 'RWF',
      isLaborEstimated: json['is_labor_estimated'] as bool? ?? true,
      isContingencyEstimated: json['is_contingency_estimated'] as bool? ?? true,
      assumptions: (json['assumptions'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      disclaimer: json['disclaimer'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'project_id': projectId,
        'materials_cost_rwf': materialsCostRwf,
        'labor_cost_rwf': laborCostRwf,
        'contingency_cost_rwf': contingencyCostRwf,
        'grand_total_rwf': grandTotalRwf,
        'labor_percentage': laborPercentage,
        'contingency_percentage': contingencyPercentage,
        'currency': currency,
        'is_labor_estimated': isLaborEstimated,
        'is_contingency_estimated': isContingencyEstimated,
        'assumptions': assumptions,
        'disclaimer': disclaimer,
      };
}
