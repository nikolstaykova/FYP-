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
    copy_number: int = Field(description="Which copy (1-based) this override applies to")
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


# --- v5 LEGO output formats: pieces say what they rest on; code turns that into joins ---------
class Position(BaseModel):
    """Where a piece sits in the finished model, in LEGO units: x, y = the stud cell of its corner nearest the
    model's front-left, layer = height of its BOTTOM in plates above the lowest piece (a brick is 3 plates)."""
    x: int
    y: int
    layer: int
    turned: bool = Field(description="True if its long side runs front-to-back instead of left-to-right")


class PieceOut(BaseModel):
    id: str = Field(description="b1, b2, ... in build order; never reused")
    type: str = Field(description="lego-<number> exactly as in the parts list")
    colour: str
    rests_on: List[str] = Field(description="EVERY piece directly underneath this one that its bottom clutches "
                                            "(a brick bridging two bricks lists both); [] for the first piece of a model")
    position: Optional[Position] = Field(description="Its position (positions format only), else null")


class OtherJoin(BaseModel):
    """A connection that is not one piece resting on another: a pin in a hole, an axle through, a clip on a bar,
    a hinge, a piece attached sideways."""
    u: str
    v: str
    method: Optional[str]
    freedom: Optional[str]


class PlacedPiece(BaseModel):
    """v7: one piece of the PIECE LIST (its id fixes type and colour), where it goes and what it rests on."""
    id: str = Field(description="The piece's id from the PIECE LIST (p1, p2, ...), exactly; every id once")
    step: int = Field(description="The booklet step that adds it, counted through the whole booklet in order")
    rests_on: List[str] = Field(description="Ids of EVERY piece directly underneath that its bottom clutches; [] if none")
    position: Optional[Position] = Field(description="Its place on the stud grid; null only if it is not on the grid "
                                                     "(sideways, hinged, on a pin)")


class LegoPiecesV7(BaseModel):
    title: str
    source_id: str
    pieces: List[PlacedPiece]
    other_joins: List[OtherJoin]
    notes: List[str]


class Placement(BaseModel):
    """v8: where a piece sits in the finished model, read off the booklet's pictures (placement.py turns it into
    LDraw coordinates; it also accepts a `relative_to` piece, which this schema no longer asks for)."""
    column: float = Field(description="Studs from the left to the piece's left edge (front-left corner); half studs allowed")
    row: float = Field(description="Studs from the front to the piece's front edge (front-left corner); half studs allowed")
    layer: float = Field(description="Height of the piece's lowest point in plates above the lowest piece (a brick is 3 plates)")
    turn: float = Field(description="Degrees clockwise seen from above, 0-360; 0 = as in the PIECE LIST size")
    tilt: float = Field(description="Degrees its top tips towards the front, 0-360; 90 = studs face the front")
    roll: float = Field(description="Degrees its top tips towards the right, 0-360; 90 = studs face the right")
    free_angle: bool = Field(description="True only if held at an angle that is not a quarter turn (turntable, hinge, clip)")


class PlacedPieceV8(BaseModel):
    """v8: one piece of the PIECE LIST, its step, what it rests on and its placement."""
    id: str = Field(description="The piece's id from the PIECE LIST (p1, p2, ...), exactly; every id once")
    step: int = Field(description="The booklet step that adds it, counted through the whole booklet in order")
    page: int = Field(description="The PDF page (1 = the cover) showing that step")
    rests_on: List[str] = Field(description="Ids of EVERY piece directly underneath that its bottom clutches; [] if none")
    placement: Placement


class LegoPiecesV8(BaseModel):
    title: str
    source_id: str
    pieces: List[PlacedPieceV8]
    other_joins: List[OtherJoin]
    notes: List[str]


class LegoPiecesDelta(BaseModel):
    """What one booklet page adds."""
    title: str
    source_id: str
    pieces: List[PieceOut]
    other_joins: List[OtherJoin]
    notes: List[str]
