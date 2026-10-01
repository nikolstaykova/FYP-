"""What Claude returns for one manual: GRAPH_SPEC.md in structured-output form.

Structured outputs need closed objects, so free-form maps are written as lists
(`props` as key/value pairs, port groups as lists of lists).
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EdgeType = Literal["joined", "contact", "electrical", "blocks", "anchored"]
OverrideKind = Literal["replace", "props", "mirror", "add", "remove", "attach"]


class Port(BaseModel):
    name: str = Field(description="Port name, e.g. 'A', '1', '13', 'GND', 'stud.1.1'")
    kind: str = Field(description="Port kind, e.g. lead, header-pin, header-socket, breadboard-hole, stud, anti-stud, pin-hole")


class PartTypeDraft(BaseModel):
    """A catalogue entry for a part type the catalogue does not have yet."""
    type: str = Field(description="New part type id, GRAPH_SPEC §3, e.g. 'photoresistor', 'lego-3001'")
    name: str
    category: str = Field(description="e.g. resistor, led, board, sensor, connector, brick, plate")
    ports: List[Port]
    conducts: List[List[str]] = Field(description="Groups of this part's ports that are one electrical node (a wire's two ends). Empty if none")
    through: List[List[str]] = Field(description="Port pairs joined THROUGH the component, not one node; ordered from->to when directional (LED: ['A','C'])")
    symmetric: List[List[str]] = Field(description="Groups of interchangeable ports (resistor legs). Empty if none")
    polarized: bool
    connector: bool = Field(description="True if the part's only job is to join other parts (wire, breadboard, Technic pin)")
    mirror_of: Optional[str] = Field(description="Part type id of its mirror twin, or null")
    rotation_symmetry: Literal["none", "180", "90", "any"]


class KeyValue(BaseModel):
    key: str
    value: str


class PartRef(BaseModel):
    id: str = Field(description="Instance id, GRAPH_SPEC §3, e.g. r1, led1, uno, wire3, b12")
    type: str = Field(description="Catalogue part type, or a type from new_part_types")
    label: Optional[str] = Field(description="The manual's own name for it, or null")
    props: List[KeyValue] = Field(description="Instance properties: colour, value. Empty if none")


class EdgeOut(BaseModel):
    type: EdgeType
    u: str = Field(description="Part id")
    u_port: Optional[str] = Field(description="Port on u, or null if not port-specific")
    v: str = Field(description="Part id")
    v_port: Optional[str]
    method: Optional[str] = Field(description="insert, push-on, screw, slide, snap, solder, clip, rest ... or null")
    freedom: Optional[str] = Field(description="rigid, revolute, slider, cylindrical, ball, flexible, or null")
    reversible: Optional[str] = Field(description="hand, tool, damaging, permanent, or null")


class Override(BaseModel):
    copy: int = Field(description="Which copy (1-based) this override applies to")
    kind: OverrideKind
    target: str = Field(description="replace/props/remove: local part id. attach: the external endpoint 'part:port' as written in the template. mirror: ''. add: new local part id")
    value: str = Field(description="replace/add: part type. props: 'key=value'. attach: the endpoint 'part:port' to use for this copy. mirror/remove: ''")


class Repeat(BaseModel):
    """A sub-assembly built `times` times. Written once; code expands it."""
    group: str = Field(description="Group name; copies become <group><n>.<local id>, e.g. ledblock2.r")
    times: int
    parts: List[PartRef] = Field(description="Parts of ONE copy, with local ids")
    edges: List[EdgeOut] = Field(description="Edges of one copy. Endpoints that are not local part ids refer to parts outside the repeat")
    overrides: List[Override]


class ExtractedGraph(BaseModel):
    title: str
    source_id: str = Field(description="Official id: tutorial URL, LEGO set number, Sauder model number")
    new_part_types: List[PartTypeDraft] = Field(description="Only part types NOT in the provided catalogue")
    parts: List[PartRef] = Field(description="Every physical part outside repeats, including wires, connectors and the board")
    edges: List[EdgeOut]
    repeats: List[Repeat]
    notes: List[str] = Field(description="Assumptions or ambiguities in the manual. Empty if none")
