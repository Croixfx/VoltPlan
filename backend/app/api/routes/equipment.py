from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.catalog import all_equipment, get_equipment

router = APIRouter(prefix="/equipment", tags=["Equipment"])


@router.get("")
def list_equipment(category: Optional[str] = None) -> List[dict]:
    """The electrical equipment catalog (types, symbols, loads, protection)."""
    items = [e.to_dict() for e in all_equipment()]
    if category:
        items = [e for e in items if e["category"] == category.lower()]
    return items


@router.get("/{type_id}")
def get_equipment_type(type_id: str) -> dict:
    spec = get_equipment(type_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown equipment type '{type_id}'.")
    return spec.to_dict()
