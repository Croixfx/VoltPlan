from typing import Dict
from app.engineering_rules.base import BaseElectricalStandard
from app.engineering_rules.rs_iec_60364 import RsIec60364Standard

_REGISTRY: Dict[str, BaseElectricalStandard] = {
    "RS IEC 60364": RsIec60364Standard(),
    "IEC 60364": RsIec60364Standard(),
    "RS IEC 60364 (Rwanda Standards / IEC)": RsIec60364Standard(),
}


def get_engineering_standard(standard_name: str) -> BaseElectricalStandard:
    """
    Returns configured electrical engineering standard.
    Defaults to RS IEC 60364.
    """
    cleaned = standard_name.strip()
    return _REGISTRY.get(cleaned, RsIec60364Standard())
