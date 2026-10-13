"""
Single source of truth for electrical equipment.

Every point type the system can place (lighting, sockets, appliances, ...) is
declared here once. The rules engine, circuit engine, BOQ engine and the API
read from this catalog, so adding equipment means adding one `EquipmentSpec`
(plus a placement rule in the engineering standard if it should be proposed
automatically).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class EquipmentCategory(str, Enum):
    LIGHTING = "lighting"
    SWITCHING = "switching"
    SOCKET = "socket"
    APPLIANCE = "appliance"
    VENTILATION = "ventilation"
    SAFETY = "safety"
    COMMUNICATIONS = "communications"
    DISTRIBUTION = "distribution"


class CircuitClass(str, Enum):
    LIGHTING = "lighting"      # shares radial lighting circuits
    SWITCH = "switch"          # follows the lighting circuit of its room
    SOCKET = "socket"          # kitchen / general socket radials
    DEDICATED = "dedicated"    # own circuit and protective device per point
    SAFETY = "safety"          # shared interlinked detection / escape-lighting circuit
    ELV = "elv"                # extra-low-voltage / structured cabling, no mains circuit
    NONE = "none"              # not allocated to a final circuit (e.g. the DB itself)


class Mount(str, Enum):
    CEILING = "ceiling"
    WALL = "wall"
    FLOOR = "floor"


@dataclass(frozen=True)
class BoqLine:
    item_code: str
    category: str
    description: str
    specification: str
    unit: str
    unit_price_rwf: float
    notes: str = ""
    qty_per_point: float = 1.0


@dataclass(frozen=True)
class DedicatedCircuit:
    id_template: str            # may use {n}
    name_template: str          # may use {room}
    description_template: str   # may use {room}
    review_notes: str
    circuit_type: str = "appliance"
    cable_rule_key: Optional[str] = None       # override key in standard.get_circuit_rules()
    protection_rule_key: Optional[str] = None


@dataclass(frozen=True)
class EquipmentSpec:
    type_id: str
    name: str
    category: EquipmentCategory
    symbol: str                       # symbol key used by clients to draw it
    mount: Mount
    mounting_height_mm: Optional[int]
    default_power_w: float
    circuit_class: CircuitClass
    cable: Optional[str]
    protection: Optional[str]
    rule_reference: str
    cable_section_mm2: Optional[str] = None   # "1.5" | "2.5" | "6.0": feeds BOQ cable estimate
    cable_run_m: float = 0.0                  # average cable run per point
    dedicated: Optional[DedicatedCircuit] = None
    boq_lines: Tuple[BoqLine, ...] = field(default_factory=tuple)
    # Room-type rules, matched as keywords against the room name / type.
    # Empty `allowed_rooms` means "any room"; `forbidden_rooms` always wins.
    allowed_rooms: Tuple[str, ...] = ()
    forbidden_rooms: Tuple[str, ...] = ()
    room_rule_note: str = ""

    def check_room(self, room_name: str, room_type: str = "") -> Optional[str]:
        """Returns a human-readable rejection reason, or None if the room is acceptable."""
        text = f"{room_name} {room_type}".lower()
        note = f" {self.room_rule_note}" if self.room_rule_note else ""
        if any(k in text for k in self.forbidden_rooms):
            return f"{self.name} is not allowed in '{room_name}'.{note}"
        if self.allowed_rooms and not any(k in text for k in self.allowed_rooms):
            return (
                f"{self.name} can only be placed in: {', '.join(self.allowed_rooms)} "
                f"(not '{room_name}').{note}"
            )
        return None

    def to_dict(self) -> dict:
        return {
            "type_id": self.type_id,
            "name": self.name,
            "category": self.category.value,
            "symbol": self.symbol,
            "mount": self.mount.value,
            "mounting_height_mm": self.mounting_height_mm,
            "default_power_w": self.default_power_w,
            "circuit_class": self.circuit_class.value,
            "cable": self.cable,
            "protection": self.protection,
            "rule_reference": self.rule_reference,
            "allowed_rooms": list(self.allowed_rooms),
            "forbidden_rooms": list(self.forbidden_rooms),
        }


_REGISTRY: Dict[str, EquipmentSpec] = {}


def register_equipment(spec: EquipmentSpec) -> EquipmentSpec:
    if spec.type_id in _REGISTRY:
        raise ValueError(f"Equipment '{spec.type_id}' is already registered.")
    if spec.circuit_class == CircuitClass.DEDICATED and spec.dedicated is None:
        raise ValueError(f"Dedicated-circuit equipment '{spec.type_id}' needs a DedicatedCircuit definition.")
    _REGISTRY[spec.type_id] = spec
    return spec


def get_equipment(type_id: str) -> Optional[EquipmentSpec]:
    return _REGISTRY.get(type_id)


def all_equipment() -> List[EquipmentSpec]:
    """All registered equipment in registration order."""
    return list(_REGISTRY.values())


def circuit_class_of(type_id: str) -> Optional[CircuitClass]:
    spec = _REGISTRY.get(type_id)
    return spec.circuit_class if spec else None


# --------------------------------------------------------------------------
# Catalog. Order matters: BOQ lines are emitted in registration order.
# --------------------------------------------------------------------------
_SOCKETS_SWITCHES = "Sockets & Switches"
_WET = ("bath", "shower", "toilet", "wc", "washroom")
_KITCHEN = ("kitchen", "pantry")
_UTILITY = ("laundry", "utility")
_EXTERIOR = ("veranda", "balcony", "terrace", "porch", "entrance", "foyer",
             "garage", "garden", "exterior", "outdoor", "patio")

register_equipment(EquipmentSpec(
    type_id="twin_socket", forbidden_rooms=_WET, room_rule_note="RS IEC 60364-7-701: switched twin sockets are not permitted in bathrooms; use a shaver unit outside Zone 2.", name="13A Twin Socket Outlet", category=EquipmentCategory.SOCKET,
    symbol="socket_double", mount=Mount.WALL, mounting_height_mm=300, default_power_w=250.0,
    circuit_class=CircuitClass.SOCKET, cable="3 x 2.5 mm² Cu/PVC", protection="20A Type B MCB + 30mA RCD",
    rule_reference="RS IEC 60364-4-41: Socket Outlets with 30mA RCD",
    cable_section_mm2="2.5", cable_run_m=16.0,
    boq_lines=(BoqLine(
        "SKT-13A-TWIN", _SOCKETS_SWITCHES, "13A 2-Gang Switched Socket Outlet",
        "British standard 3-pin safety shuttered, with double pole switches (BS 1363)",
        "pcs", 4500.0, "Flush mounted on wall at 300mm / 1100mm AFFL."),),
))

register_equipment(EquipmentSpec(
    type_id="single_socket", name="13A Single Socket / Shaver Outlet", category=EquipmentCategory.SOCKET,
    symbol="socket_single", mount=Mount.WALL, mounting_height_mm=300, default_power_w=350.0,
    circuit_class=CircuitClass.SOCKET, cable="3 x 2.5 mm² Cu/PVC", protection="16A Type B MCB + 30mA RCD",
    rule_reference="RS IEC 60364-5-53: Dedicated Single Outlet",
    boq_lines=(BoqLine(
        "SKT-13A-SNGL", _SOCKETS_SWITCHES, "13A 1-Gang Switched Socket / Shaver Outlet",
        "Shuttered safety socket / dual voltage isolated shaver unit (BS 1363 / EN 61558)",
        "pcs", 5500.0, "Dedicated appliances and bathroom shaver safety point."),),
))

register_equipment(EquipmentSpec(
    type_id="switch_1way", name="1-Way Light Switch", category=EquipmentCategory.SWITCHING,
    symbol="switch", mount=Mount.WALL, mounting_height_mm=1100, default_power_w=0.0,
    circuit_class=CircuitClass.SWITCH, cable="3 x 1.5 mm² Cu/PVC", protection="10A Type B MCB",
    rule_reference="RS IEC 60364-5-53 / NECA 1: Wall-Attached Switch Placement",
    boq_lines=(BoqLine(
        "SW-1G-1W", _SOCKETS_SWITCHES, "10AX 1-Gang 1-Way Plate Switch",
        "Molded white faceplate, fluorescent / inductive load rated (BS EN 60669-1)",
        "pcs", 2800.0, "Standard room lighting control at doorway entrance."),),
))

register_equipment(EquipmentSpec(
    type_id="switch_2way", name="2-Way Light Switch", category=EquipmentCategory.SWITCHING,
    symbol="switch", mount=Mount.WALL, mounting_height_mm=1100, default_power_w=0.0,
    circuit_class=CircuitClass.SWITCH, cable="3 x 1.5 mm² Cu/PVC", protection="10A Type B MCB",
    rule_reference="RS IEC 60364-5-53: Multi-Way Switching",
    boq_lines=(BoqLine(
        "SW-1G-2W", _SOCKETS_SWITCHES, "10AX 1-Gang 2-Way Plate Switch",
        "Two-way switching control for multi-entrance locations (BS EN 60669-1)",
        "pcs", 3400.0, "Paired switching for corridors, stairways, and master bedroom."),),
))

register_equipment(EquipmentSpec(
    type_id="cooker_point", allowed_rooms=_KITCHEN, room_rule_note="A cooker control unit belongs in the kitchen.", name="45A Cooker Control Unit", category=EquipmentCategory.APPLIANCE,
    symbol="cooker", mount=Mount.WALL, mounting_height_mm=1300, default_power_w=6000.0,
    circuit_class=CircuitClass.DEDICATED, cable="3 x 6.0 mm² Cu/PVC", protection="32A Type B MCB",
    rule_reference="RS IEC 60364-5-52: Electric Range / Cooker Circuit",
    cable_section_mm2="6.0", cable_run_m=25.0,
    dedicated=DedicatedCircuit(
        id_template="CKT-APP-CKR", name_template="Electric Cooker Circuit",
        description_template="Dedicated 32A cooker supply ({room})",
        review_notes="Direct feed from consumer unit to 45A cooker control unit.",
        cable_rule_key="cooker_cable", protection_rule_key="cooker_mcb"),
    boq_lines=(BoqLine(
        "SW-45A-CKR", _SOCKETS_SWITCHES, "45A DP Cooker Control Unit with 13A Socket",
        "Double pole switch with neon indicator and auxiliary socket (BS 4177)",
        "pcs", 14500.0, "Surface or flush mount adjacent to kitchen range."),),
))

register_equipment(EquipmentSpec(
    type_id="water_heater", allowed_rooms=_WET + _KITCHEN + _UTILITY, room_rule_note="Fixed water heaters belong in bathrooms, kitchens or utility rooms.", name="Water Heater Isolator", category=EquipmentCategory.APPLIANCE,
    symbol="water_heater", mount=Mount.WALL, mounting_height_mm=2000, default_power_w=2500.0,
    circuit_class=CircuitClass.DEDICATED, cable="3 x 2.5 mm² Cu/PVC", protection="20A Type B MCB + 30mA RCD",
    rule_reference="RS IEC 60364-7-701: Fixed Water Heating Equipment",
    dedicated=DedicatedCircuit(
        id_template="CKT-APP-WTR-{n:02d}", name_template="Water Heater ({room})",
        description_template="Dedicated fixed water heater supply",
        review_notes="Dedicated circuit for water heating equipment with 30mA RCD.",
        cable_rule_key="water_heater_cable", protection_rule_key="water_heater_mcb"),
    boq_lines=(BoqLine(
        "SW-20A-DP-WH", _SOCKETS_SWITCHES, "20A Double Pole Water Heater Switch",
        "Surface mounted DP isolator with neon pilot indicator (BS EN 60669-2-4)",
        "pcs", 6500.0, "Dedicated isolation outside wet shower area."),),
))

register_equipment(EquipmentSpec(
    type_id="ac_point", forbidden_rooms=_WET, room_rule_note="Air-conditioning equipment is not permitted in wet rooms.", name="Air Conditioner Isolator", category=EquipmentCategory.APPLIANCE,
    symbol="ac", mount=Mount.WALL, mounting_height_mm=2200, default_power_w=2000.0,
    circuit_class=CircuitClass.DEDICATED, cable="3 x 2.5 mm² Cu/PVC", protection="16A Type C MCB",
    rule_reference="RS IEC 60364-5-52: Air Conditioning Motor Load (Type C Curve)",
    dedicated=DedicatedCircuit(
        id_template="CKT-APP-AC-{n:02d}", name_template="Air Conditioner ({room})",
        description_template="Air conditioner compressor unit",
        review_notes="Type C curve MCB specified for motor starting inrush current."),
    boq_lines=(BoqLine(
        "SW-20A-ISO-AC", _SOCKETS_SWITCHES, "20A IP65 Weatherproof Rotary AC Isolator",
        "3-pole lockable rotary motor disconnect switch (IEC 60947-3)",
        "pcs", 18000.0, "Positioned adjacent to air conditioning outdoor condenser unit."),),
))

register_equipment(EquipmentSpec(
    type_id="lighting", name="LED Ceiling Luminaire", category=EquipmentCategory.LIGHTING,
    symbol="light", mount=Mount.CEILING, mounting_height_mm=None, default_power_w=60.0,
    circuit_class=CircuitClass.LIGHTING, cable="3 x 1.5 mm² Cu/PVC", protection="10A Type B MCB",
    rule_reference="RS IEC 60364-5-52 / CIBSE SLL Code for Lighting",
    cable_section_mm2="1.5", cable_run_m=12.0,
    boq_lines=(BoqLine(
        "LUM-LED-15W", "Luminaires", "15W Recessed LED Ceiling Downlight Fixture",
        "Die-cast aluminum, 4000K neutral white, 1350lm, CRI>80, IP44 (RS IEC 60598)",
        "pcs", 12500.0, "High efficiency architectural ceiling lighting fixtures."),),
))

# --- Equipment added through the catalog -----------------------------------

register_equipment(EquipmentSpec(
    type_id="outdoor_light", allowed_rooms=_EXTERIOR, room_rule_note="Outdoor luminaires belong in exterior or entrance spaces.", name="Outdoor Wall Luminaire", category=EquipmentCategory.LIGHTING,
    symbol="light_wall", mount=Mount.WALL, mounting_height_mm=2200, default_power_w=20.0,
    circuit_class=CircuitClass.LIGHTING, cable="3 x 1.5 mm² Cu/PVC", protection="10A Type B MCB",
    rule_reference="RS IEC 60364-5-52 / IEC 60598-2-5: Exterior Luminaires (min. IP54)",
    cable_section_mm2="1.5", cable_run_m=12.0,
    boq_lines=(BoqLine(
        "LUM-OUT-WALL-IP65", "Luminaires", "IP65 LED Outdoor Wall Light",
        "Die-cast aluminium bulkhead, 20W LED, IP65, UV-stable diffuser (IEC 60598-2-5)",
        "pcs", 22000.0, "Entrance / veranda lighting. Weatherproof glands required."),),
))

register_equipment(EquipmentSpec(
    type_id="extractor_fan", allowed_rooms=_WET + _KITCHEN + _UTILITY, room_rule_note="Extract fans serve wet rooms, kitchens and utility rooms.", name="Extractor Fan", category=EquipmentCategory.VENTILATION,
    symbol="fan", mount=Mount.CEILING, mounting_height_mm=None, default_power_w=25.0,
    circuit_class=CircuitClass.LIGHTING, cable="3 x 1.5 mm² Cu/PVC", protection="10A Type B MCB",
    rule_reference="RS IEC 60364-7-701: Fans in bathroom zones (min. IPX4); ventilation for wet rooms",
    cable_section_mm2="1.5", cable_run_m=10.0,
    boq_lines=(BoqLine(
        "FAN-EXT-100", "Ventilation", "100mm Axial Extractor Fan with Humidity Timer",
        "IPX4 rated, 25W, run-on timer, backdraught shutter (IEC 60335-2-80)",
        "pcs", 24000.0, "Wet-room and kitchen extract. Confirm IP rating against installed zone."),),
))

register_equipment(EquipmentSpec(
    type_id="smoke_detector", forbidden_rooms=_WET + _KITCHEN, room_rule_note="Steam and cooking fumes cause false alarms; use a heat detector instead.", name="Smoke Detector (Mains, Interlinked)", category=EquipmentCategory.SAFETY,
    symbol="smoke_detector", mount=Mount.CEILING, mounting_height_mm=None, default_power_w=5.0,
    circuit_class=CircuitClass.SAFETY, cable="3 x 1.5 mm² Cu/PVC", protection="6A Type B MCB",
    rule_reference="EN 14604 / IEC 60364-5-56: Fire detection and alarm (mains with battery backup)",
    cable_section_mm2="1.5", cable_run_m=8.0,
    boq_lines=(BoqLine(
        "SAF-SMK-230V", "Safety & Detection", "230V Optical Smoke Alarm with Battery Backup",
        "Interlinkable photoelectric alarm, 85dB, 10-year sealed lithium backup (EN 14604)",
        "pcs", 28000.0, "Ceiling mounted, interlinked on a dedicated detection circuit."),),
))

register_equipment(EquipmentSpec(
    type_id="emergency_light", name="Emergency Luminaire", category=EquipmentCategory.SAFETY,
    symbol="emergency_light", mount=Mount.CEILING, mounting_height_mm=None, default_power_w=8.0,
    circuit_class=CircuitClass.SAFETY, cable="3 x 1.5 mm² Cu/PVC", protection="6A Type B MCB",
    rule_reference="IEC 60364-5-56 / IEC 60598-2-22: Emergency escape lighting (3 h autonomy)",
    cable_section_mm2="1.5", cable_run_m=10.0,
    boq_lines=(BoqLine(
        "SAF-EML-3H", "Safety & Detection", "LED Emergency Luminaire, 3-Hour Maintained",
        "8W LED, Ni-MH battery, 3 h autonomy, self-test (IEC 60598-2-22)",
        "pcs", 45000.0, "Escape routes and corridors in non-residential occupancies."),),
))

register_equipment(EquipmentSpec(
    type_id="data_point", forbidden_rooms=_WET, room_rule_note="Communications outlets are not permitted in wet rooms.", name="Data Outlet (Cat6)", category=EquipmentCategory.COMMUNICATIONS,
    symbol="data", mount=Mount.WALL, mounting_height_mm=300, default_power_w=0.0,
    circuit_class=CircuitClass.ELV, cable="Cat6 U/UTP LSZH", protection="N/A (ELV)",
    rule_reference="ISO/IEC 11801 / TIA-568: Structured cabling outlet",
    boq_lines=(
        BoqLine("COM-RJ45-C6", "Data & Communications", "Cat6 RJ45 Data Outlet, 1-Gang",
                "Unshielded keystone jack in flush faceplate (ISO/IEC 11801)", "pcs", 6500.0,
                "Segregate from mains cabling by at least 50 mm."),
        BoqLine("COM-CBL-C6", "Data & Communications", "Cat6 U/UTP LSZH Cable",
                "4-pair solid copper, LSZH sheath (ISO/IEC 11801)", "m", 900.0,
                "Allowance of 20 m per outlet back to the patch point.", qty_per_point=20.0),
    ),
))

register_equipment(EquipmentSpec(
    type_id="tv_point", forbidden_rooms=_WET, room_rule_note="Communications outlets are not permitted in wet rooms.", name="TV / Satellite Outlet", category=EquipmentCategory.COMMUNICATIONS,
    symbol="tv", mount=Mount.WALL, mounting_height_mm=1100, default_power_w=0.0,
    circuit_class=CircuitClass.ELV, cable="RG6 coaxial", protection="N/A (ELV)",
    rule_reference="EN 50083 / IEC 60728: Home distribution network outlet",
    boq_lines=(
        BoqLine("COM-TV-FP", "Data & Communications", "TV / Satellite Coaxial Outlet, 1-Gang",
                "Isolated F-type / IEC coaxial outlet in flush faceplate (IEC 60728)", "pcs", 4500.0,
                "Mount next to a twin socket at the TV position."),
        BoqLine("COM-CBL-RG6", "Data & Communications", "RG6 Coaxial Cable",
                "75 ohm RG6 quad-shield coaxial cable (IEC 61196)", "m", 700.0,
                "Allowance of 15 m per outlet.", qty_per_point=15.0),
    ),
))

register_equipment(EquipmentSpec(
    type_id="distribution_board", forbidden_rooms=_WET, room_rule_note="Distribution boards must not be installed in wet rooms.", name="Consumer Unit / Distribution Board", category=EquipmentCategory.DISTRIBUTION,
    symbol="db", mount=Mount.WALL, mounting_height_mm=1500, default_power_w=0.0,
    circuit_class=CircuitClass.NONE, cable=None, protection="100A DP main isolator",
    rule_reference="IEC 61439-3: Distribution boards",
    # BOQ for the board is sized from the number of circuits in BoqEngine.
))
