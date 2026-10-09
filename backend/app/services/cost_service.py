from app.schemas.boq import CostEstimateResponse


class CostService:
    """
    Cost estimation service for preliminary budgeting in Rwandan Francs (RWF).
    Maintains clean separation between material costs and modeled installation assumptions.
    """

    @staticmethod
    def calculate_cost_estimate(
        project_id: str,
        materials_cost_rwf: float,
        labor_percentage: float = 28.0,
        contingency_percentage: float = 12.0,
    ) -> CostEstimateResponse:
        materials_total = round(materials_cost_rwf, 2)
        labor_total = round(materials_total * (labor_percentage / 100.0), 2)
        contingency_total = round(materials_total * (contingency_percentage / 100.0), 2)
        grand_total = round(materials_total + labor_total + contingency_total, 2)

        assumptions = [
            f"Installation labor calculated at {labor_percentage:.0f}% of materials subtotal based on standard Rwandan contractor rates for licensed wiremen.",
            f"Unforeseen contingency factored at {contingency_percentage:.0f}% to accommodate conduit path detours, structural obstacles, and auxiliary mounting hardware.",
            "All pricing calculated in Rwandan Francs (RWF) at current local distributor price averages (Kigali baseline).",
        ]

        disclaimer = (
            "Preliminary engineering advisory cost estimate. "
            "Excludes civil builder's work, excavation, and utility connection fees (REG/EUCL). "
            "Final installation quotation must be confirmed with an on-site licensed electrical contractor."
        )

        return CostEstimateResponse(
            project_id=project_id,
            materials_cost_rwf=materials_total,
            labor_cost_rwf=labor_total,
            contingency_cost_rwf=contingency_total,
            grand_total_rwf=grand_total,
            labor_percentage=labor_percentage,
            contingency_percentage=contingency_percentage,
            currency="RWF",
            is_labor_estimated=True,
            is_contingency_estimated=True,
            assumptions=assumptions,
            disclaimer=disclaimer,
        )
