from typing import Dict, List
from app.engineering_rules.base import BaseElectricalStandard
from app.engineering_rules.rs_iec_60364 import RsIec60364Standard

_REGISTRY: Dict[str, BaseElectricalStandard] = {
    "RS IEC 60364": RsIec60364Standard(),
    "IEC 60364": RsIec60364Standard(),
    "RS IEC 60364 (Rwanda Standards / IEC)": RsIec60364Standard(),
}


class UnsupportedStandardError(ValueError):
    """The project asks for a standard that has no rule implementation. Never answered with another standard's
    rules: a design that looks compliant with the wrong code is worse than no design."""


def supported_standards() -> List[str]:
    return list(_REGISTRY)


def get_engineering_standard(standard_name: str) -> BaseElectricalStandard:
    """Returns the rules for the named standard, or raises UnsupportedStandardError."""
    cleaned = (standard_name or "").strip()
    try:
        return _REGISTRY[cleaned]
    except KeyError:
        raise UnsupportedStandardError(
            f"'{cleaned or 'no standard'}' is not supported yet: only RS IEC 60364 rules are implemented. "
            "Change the project's standard to RS IEC 60364 to generate a design."
        ) from None
