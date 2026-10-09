from typing import List, Optional
from pydantic import BaseModel, Field


class BOQItem(BaseModel):
    id: str
    category: str = Field(..., description="Cables & Conduits, Sockets & Switches, Luminaires, Distribution & Switchgear, Earthing & Protection")
    item_code: str
    description: str
    specification: str
    quantity: float = Field(..., ge=0.0)
    unit: str = Field(..., description="pcs, m, rolls, sets")
    unit_price_rwf: Optional[float] = Field(None, ge=0.0, description="Unit cost in RWF or null if unavailable")
    total_price_rwf: Optional[float] = Field(None, ge=0.0, description="Extended line cost in RWF")
    pricing_status: str = Field(
        "STANDARD_ESTIMATE",
        description="VERIFIED_LOCAL, STANDARD_ESTIMATE, or UNAVAILABLE",
    )
    notes: Optional[str] = None


class BOQResponse(BaseModel):
    project_id: str
    items: List[BOQItem]
    materials_subtotal_rwf: float = Field(..., ge=0.0)
    pricing_disclaimer: str = (
        "Preliminary bill of quantities derived from architectural floor plan analysis. "
        "Unit prices reflect Rwandan baseline market estimates (Kigali). Actual procurement prices may vary."
    )


class CostEstimateResponse(BaseModel):
    project_id: str
    materials_cost_rwf: float = Field(..., ge=0.0)
    labor_cost_rwf: Optional[float] = Field(None, ge=0.0)
    contingency_cost_rwf: Optional[float] = Field(None, ge=0.0)
    grand_total_rwf: Optional[float] = Field(None, ge=0.0)
    labor_percentage: float = 28.0
    contingency_percentage: float = 12.0
    currency: str = "RWF"
    is_labor_estimated: bool = True
    is_contingency_estimated: bool = True
    assumptions: List[str] = Field(
        default_factory=lambda: [
            "Labor estimated at 28% of verified materials subtotal based on standard Rwandan contractor rates.",
            "Contingency factor set to 12% for cable run deviations, conduit bends, and ancillary fasteners.",
            "All currency figures stated in Rwandan Francs (RWF).",
        ]
    )
    disclaimer: str = (
        "Advisory cost projection for preliminary engineering budget planning only. "
        "Not a formal contractor bid or procurement contract."
    )
