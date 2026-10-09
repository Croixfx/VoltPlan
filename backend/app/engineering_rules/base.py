from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class BaseElectricalStandard(ABC):
    @abstractmethod
    def get_standard_code(self) -> str:
        """Returns standard code name, e.g. RS IEC 60364"""
        pass

    @abstractmethod
    def get_lighting_recommendations(
        self,
        room_name: str,
        area_m2: Optional[float],
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates recommended lighting points and controls for a room."""
        pass

    @abstractmethod
    def get_socket_recommendations(
        self,
        room_name: str,
        area_m2: Optional[float],
        building_type: str,
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates recommended socket outlets for a room."""
        pass

    @abstractmethod
    def get_dedicated_appliance_points(
        self,
        room_name: str,
        building_type: str,
        room_bounds: Optional[List[float]] = None,
        architectural_features: Optional[List[Any]] = None,
        image_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates heavy appliance connections (cooker, water heater, AC)."""
        pass

    @abstractmethod
    def get_circuit_rules(self) -> Dict[str, Any]:
        """Returns circuit capacity, breaker sizing, and cable rules."""
        pass
