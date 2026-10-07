"""Layer 0: the reusable part card, as agreed in the architecture discussion (RESEARCH.md R22).

A card describes a part TYPE and never a tutorial or set. Every card, whatever produced it (code, a shop page,
Rebrickable, a booklet), passes `gate()` before it is stored; a card that fails goes to quarantine instead of the
catalogue. `to_engine()` gives the graph engine's working form (catalogue._entry), so validation, the logical
view and scoring read cards unchanged.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from .. import catalogue as cat


class CardPort(BaseModel):
    id: str = Field(description="Canonical port id, e.g. '1', 'A', 'GND', 'stud.1.1', 'hole.top_left'")
    kind: str = Field(description="Standard connection type for compatibility checks: lead, header-pin, header-socket, "
                                  "breadboard-hole, wire-end, lug, stud, anti-stud, pin, pin-hole, axle, axle-hole, clip, "
                                  "bar, ball, socket, hinge, hole, screw, dowel, cam, groove, edge")
    gender: Optional[Literal["male", "female", "neutral"]] = None
    voltage_rating: Optional[float] = None
    aliases: List[str] = Field(default_factory=list, description="Other names for this port (D13, SCK, LED_BUILTIN)")


class IntrinsicBehaviour(BaseModel):
    is_connector_only: bool = Field(False, description="Exists only to join other parts (wire, breadboard, screw, Technic pin)")
    internal_conducts: List[List[str]] = Field(default_factory=list, description="Port groups shorted inside (breadboard strip, GND pins)")
    internal_pass_through: List[List[str]] = Field(default_factory=list, description="Ports joined through a component (resistor 1-2)")
    symmetric_port_groups: List[List[str]] = Field(default_factory=list, description="Interchangeable ports (resistor legs)")
    is_polarized: bool = False
    rotation_symmetry_deg: Optional[int] = Field(None, description="180 for a 2x4 brick, 90 for 2x2, null if none")
    mirror_twin_id: Optional[str] = None


class Electrical(BaseModel):
    """Electrical facts the laws need (v5). Null = not known; laws skip what they do not know."""
    supply_v_min: Optional[float] = Field(None, description="Lowest supply voltage on its power pin")
    supply_v_max: Optional[float] = Field(None, description="Highest supply voltage on its power pin")
    logic_v: Optional[float] = Field(None, description="Logic level of its signal pins: 3.3 or 5")
    five_v_tolerant: Optional[bool] = Field(None, description="Signal pins accept 5 V although logic is 3.3 V")
    max_pin_current_ma: Optional[float] = Field(None, description="Boards: most current one I/O pin may give")
    forward_v: Optional[float] = Field(None, description="LEDs: forward voltage")
    current_ma: Optional[float] = Field(None, description="Typical working current")
    needs_series_resistor: Optional[bool] = Field(None, description="Must have a current-limiting resistor in series (LEDs)")
    power_pins: List[str] = Field(default_factory=list, description="Ports that take the supply (VCC, VDD, V+, 3V3, VIN)")


class Dimensions(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class GridUnits(BaseModel):
    unit_type: str = "studs"
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class Geometry(BaseModel):
    dimensions_mm: Optional[Dimensions] = None
    grid_units: Optional[GridUnits] = None


class Source(BaseModel):
    platform: str = Field(description="adafruit, sparkfun, rebrickable, booklet, circuitquest, code ...")
    url: Optional[str] = None
    external_id: Optional[str] = None
    made_by: Literal["code", "claude", "verified"] = "claude"


class ManufacturerInfo(BaseModel):
    mpn: Optional[str] = None
    sku: Optional[str] = None
    datasheet_url: Optional[str] = None


class Layer0Card(BaseModel):
    part_type_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9.]+)*$",
                              description="Global id: <domain or category>-<official id> e.g. lego-3001, arduino-uno, temp-dht11")
    domain: Literal["electronics", "lego", "furniture"]
    display_name: str
    aliases: List[str] = Field(default_factory=list, description="Other names people use for this part (searched)")
    category: str
    ports: List[CardPort]
    intrinsic_behaviour: IntrinsicBehaviour = Field(default_factory=IntrinsicBehaviour)
    physical_geometry: Optional[Geometry] = None
    manufacturer_info: Optional[ManufacturerInfo] = None
    source: Source
    port_rule: Optional[str] = Field(None, description="Pattern-named ports (breadboard holes) instead of a full list")
    note: Optional[str] = Field(None, description="Wiring fact the builder must know (which pushbutton legs are joined)")
    electrical: Optional[Electrical] = None
    legs_together: bool = Field(False, description="Breadboard: all legs go in together, in pin order, in one row")
    straddles_gap: bool = Field(False, description="Breadboard: the part sits across the centre gap")
    port_alias_rule: Optional[dict] = Field(None, description="How port names fold together: {'mode': 'strip'} (breadboard "
                                                              "hole -> its strip) or {'mode': 'prefix', 'prefixes': ['GND']}")


def gate(card_dict):
    """Schema validation gate: (Layer0Card dict, None) or (None, error text)."""
    try:
        card = Layer0Card.model_validate(card_dict)
    except ValidationError as e:
        return None, str(e)[:500]
    names = [p.id for p in card.ports]
    if len(names) != len(set(names)):
        return None, "duplicate port ids"
    known = set(names)
    b = card.intrinsic_behaviour
    for group in b.internal_conducts + b.internal_pass_through + b.symmetric_port_groups:
        if not card.port_rule and any(p not in known and not any(n.startswith(p + ".") for n in known) for p in group):
            return None, f"behaviour names a port the card does not have: {group}"
    return card.model_dump(), None


_ROTATION = {"none": None, "180": 180, "90": 90, "any": 1}


def from_engine(entry, domain, source):
    """Engine entry (catalogue._entry) -> Layer 0 card dict."""
    rot = _ROTATION.get(str(entry.get("rotation_symmetry", "none")))
    return {"part_type_id": entry["type"], "domain": domain, "display_name": entry["name"], "category": entry["category"],
            "ports": [{"id": p["name"], "kind": p["kind"]} for p in entry["ports"]],
            "intrinsic_behaviour": {"is_connector_only": bool(entry.get("connector")),
                                    "internal_conducts": entry.get("conducts", []),
                                    "internal_pass_through": entry.get("through", []),
                                    "symmetric_port_groups": entry.get("symmetric", []),
                                    "is_polarized": bool(entry.get("polarized")), "rotation_symmetry_deg": rot,
                                    "mirror_twin_id": entry.get("mirror_of")},
            "source": source, "port_rule": entry.get("port_rule"), "note": entry.get("note"),
            "electrical": entry.get("electrical"), "legs_together": bool(entry.get("legs_together")),
            "straddles_gap": bool(entry.get("straddles_gap")),
            "port_alias_rule": entry.get("alias")}


def to_engine(card):
    """Layer 0 card dict -> engine entry the graph code reads."""
    b = card["intrinsic_behaviour"]
    rot = {None: "none", 180: "180", 90: "90", 1: "any"}.get(b.get("rotation_symmetry_deg"), "none")
    status = {"verified": "verified", "code": "imported"}.get(card["source"]["made_by"], "ingested")
    extra = {k: card[k] for k in ("port_rule", "note", "electrical", "legs_together", "straddles_gap") if card.get(k)}
    return cat._entry(card["part_type_id"], card["display_name"], card["category"], [(p["id"], p["kind"]) for p in card["ports"]],
                      conducts=b["internal_conducts"], through=b["internal_pass_through"], symmetric=b["symmetric_port_groups"],
                      polarized=b["is_polarized"], connector=b["is_connector_only"], alias=card.get("port_alias_rule"),
                      status=status, mirror_of=b.get("mirror_twin_id"), rotation=rot, source=card["source"], **extra)
