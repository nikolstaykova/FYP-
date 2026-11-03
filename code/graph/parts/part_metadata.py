"""Each part's metadata: drafted by Claude, checked by code.

What it is   what a teacher or learner wants beyond the card (a plain description, the specifications, the material,
             how each join holds and whether it comes apart by hand, what a power/ground swap does), drafted by
             Claude in fixed codes, one call per lesson for its new parts (LEGO: a picture of each part drawn from
             its LDraw shape; Arduino: its card), then checked by code (M1-M10) against the shape, the card and the
             join table. The vocabulary of every coded field is at the top of this file (CODES, FIELDS, the *_CODES
             lists).
Used for     the parts catalogue's metadata block; the tutor's answers about a part; the store validator's code checks.
Where        arduino/circuit_lesson.py and part_review.py (describe_new), lesson_store.py, parts/part_catalogue.py,
             parts/naming.py; on its own: python -m graph.parts.part_metadata.

The cards (code/graph/parts/arduino/cards_electronics.json, parts/lego/cards_lego.json) hold what code can trust: ports, inside behaviour, polarity. What a teacher or
a learner also wants (a plain description, the specifications, the material, how each join holds and whether it
comes apart by hand) is drafted by Claude, one call per lesson for every definition the lesson uses:
  LEGO      a VLM call: a picture of each part, drawn by code from its real LDraw shape, with its name and card
  Arduino   an LLM call: each part's card (ports, electrical values, placement rules)
Claude only adds; it never edits a card. Where it thinks a card is wrong it says so (`card_issues`), and code checks
the claim. Every answer is checked against what code already knows before it is kept:
  M1  one answer per definition asked for, no other ids
  M2  every join names a port kind the card has
  M3  `polarized` agrees with the card
  M4  LEGO: the size in studs and the size in mm agree with the part's real shape (LDraw box, 1 LDU = 0.4 mm)
  M5  a join's `reversible` agrees with the lesson's own edges where they say
  M6  Arduino: a specification the card also gives (forward_v, current_ma ...) agrees with it (15%)
  M7  LEGO: a card issue about the number of studs or anti-stud cells is confirmed or rejected from the shape
  M8  a join's `holds_by` agrees with GRAPH_SPEC §5.1 where it says (LEGO clutch: friction; breadboard and header
      pins and sockets: spring; screw terminal: force)
  M9  a join's `reversible` agrees with GRAPH_SPEC §5.1 where it says (LEGO, breadboard, headers: hand; screw: tool)
      (M8, M9: the rule wins; Claude's value is kept on the join as `overridden`)
  M10 `reverse_power` (what swapping power and ground does) is not 'not applicable' on a part with power pins (a
      battery excepted: it is the power); for the parts researched (DATA_STRUCTURE.md §7) the research wins
  M11 the metadata uses the standard fields only (Specs: the same names and units for every part), each filled-in
      field with its basis (card, image, maker page, general knowledge)
  C1  LEGO, code only: the card's stud and anti-stud ports agree in number with the shape (whatever Claude says)
Kept in each part's `metadata` block in the one parts catalogue (code/graph/parts/parts.json, parts/part_catalogue.py), beside its
`domain` (lego or arduino), with status `drafted (claude)` and the checks; the lesson assembler shows it beside
each part.

  python -m graph.parts.part_metadata blink 2134-1 [--model sonnet]   (only the parts that have no metadata yet)
  python -m graph.parts.part_metadata --catalogue arduino [--redo]     (every electronics card, 12 a call)
"""
import argparse
import base64
import collections
import io
import json
import math
import re
import time
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from graph import lesson_store
from graph.parts import part_catalogue


# ---- the vocabulary: every field that is a code, and the codes it may take --------------------------------------------------------------------------------
DOMAINS = ("lego", "arduino")


# the port kinds a card may give its ports (what the joins connect)
PORT_KINDS = ("stud", "anti-stud", "pin", "pin-hole", "axle", "axle-hole", "bar", "clip", "hinge", "ball", "socket",
              "lead", "header-pin", "header-socket", "wire-end", "breadboard-hole", "screw", "lug", "pad", "hole", "edge",
              "sleeve")


# what a join's other side may be: a port kind, or a connector a part is sold with
CONNECTORS = ("usb", "usb-micro", "usb-c", "barrel-jack", "battery-connector", "grove", "qwiic", "rf-connector", "rj45",
              "rca", "microsd", "mains", "fpc", "plug", "connector", "minifig-neck", "bare-wire")


MATES_CODES = PORT_KINDS + CONNECTORS + ("other",)


JOIN_METHODS = ("insert", "push-on", "screw", "snap", "clip", "slide", "rest", "solder", "twist", "clutch", "clamp")


HOLDS_BY_CODES = ("friction", "form", "force", "material", "gravity", "spring")


REVERSIBLE_CODES = ("hand", "tool", "damaging", "permanent")


REVERSE_POWER_CODES = ("damage", "no-harm", "protected", "n/a")


MATERIALS_CODES = ("abs", "polycarbonate", "rubber", "silicone", "pcb", "ceramic", "glass", "copper", "steel", "aluminium",
             "carbon", "metal", "semiconductor", "epoxy", "plastic", "fabric", "paper", "wood", "magnet", "other")


BASIS_CODES = ("card", "image", "maker-page", "general-knowledge")


INTERFACES = ("digital", "analog", "pwm", "i2c", "spi", "uart", "1-wire", "usb", "single-wire")


WIRELESS = ("wifi", "bluetooth", "lora", "nfc", "ir", "rf", "cellular")


SWAP_KINDS = ("not-polarized", "card-symmetric", "same-pin", "joined-inside", "strip", "rail")


CONNECT_WAYS = ("breadboard", "header-socket", "female-jumper", "onto-header-pin", "screw-terminal", "solder")


TAKES = ("lead", "pin", "header-pin", "wire-end", "lug")


TOOLS = ("screwdriver", "soldering iron")


STATUS = ("drafted", "verified")


VIA = ("llm", "vlm")


# the metadata fields a part may have: what Claude drafts, what code works out, and where the part came from
DRAFTED = ("description", "material", "material_text", "size_studs", "dimensions_mm", "polarized", "reverse_power",
           "specs", "basis", "joins", "learner_tips", "card_issues", "confidence", "overridden")


COMPUTED = ("fits", "connect_by", "takes", "interchangeable", "substitutes", "schema_version", "status", "drafted_by",
            "via", "lesson", "checks_failed")


PROVENANCE = ("domain", "source_catalogue", "card_made_by")


FIELDS = DRAFTED + COMPUTED + PROVENANCE


# field -> its codes, for checking a stored value (lists: every item must be one)
CODES = {"domain": DOMAINS, "reverse_power": REVERSE_POWER_CODES, "material": MATERIALS_CODES, "status": STATUS, "via": VIA}

ROOT = lesson_store.ROOT
OUT = part_catalogue.PATH  # the metadata block of each part in the one parts catalogue
LDU_MM = 0.4
STUD_MM = 1.7  # a stud's height
HOLDS_BY = {"stud": "friction", "anti-stud": "friction", "breadboard-hole": "spring", "screw": "force",  # GRAPH_SPEC §5.1
            "header-socket": "spring", "header-pin": "spring"}  # a header in a spring contact; leads and wire ends
# vary (a screw terminal clamps, a JST or RJ45 plug locks by form), so they are not ruled
POWER_PINS = {"VCC", "VDD", "V+", "5V", "3.3V", "3V3", "VIN", "VMOT", "VBAT", "POSITIVE", "+"}
# What a power/ground swap does, from the research for the polarity decision (DATA_STRUCTURE.md §7; sources there)
REVERSE_POWER = {"servo": "damage", "ds18b20": "damage", "oled-ssd1306": "damage", "sh1107-oled": "damage",
                 "tm1637-7segment": "damage", "nlsf595": "damage", "seven-segment": "no harm, does not work"}
REVERSIBLE = {"stud": "hand", "anti-stud": "hand", "breadboard-hole": "hand", "header-pin": "hand",
              "header-socket": "hand", "screw": "tool"}  # GRAPH_SPEC §5.1: LEGO, breadboard by hand; screws by tool


SCHEMA_VERSION = 2  # one fixed set of fields for every part (before: free-form specification names)
BASIS = Literal[BASIS_CODES]


class Specs(BaseModel):
    """The standard specification fields, the same names and units for every part; null when a field does not apply
    or is not known. Electrical names are the card's own `electrical` keys, so code compares them directly."""
    maker: Optional[str] = Field(None, description="the maker or brand, e.g. Arduino, Adafruit, LEGO")
    model: Optional[str] = Field(None, description="the maker's model or part number, e.g. ABX00021, DHT11, 3021")
    chip: Optional[str] = Field(None, description="the main chip: microcontroller, sensor or driver IC (ATmega328P, "
                                                  "DHT11, L298N); null if none")
    supply_v_min: Optional[float] = Field(None, description="V")
    supply_v_max: Optional[float] = Field(None, description="V")
    logic_v: Optional[float] = Field(None, description="V, the signal level of its pins")
    max_pin_current_ma: Optional[float] = Field(None, description="mA per pin")
    current_ma: Optional[float] = Field(None, description="mA, typical working current")
    forward_v: Optional[float] = Field(None, description="V, LEDs and diodes")
    resistance_ohm: Optional[float] = Field(None, description="only for a part whose resistance does not vary by copy")
    capacitance_uf: Optional[float] = Field(None, description="only for a part whose value does not vary by copy")
    interface: List[Literal[INTERFACES]] = Field(default_factory=list, description="how it talks to a board; "
                                                                                        "empty if it does not")
    digital_pins: Optional[int] = None
    analog_pins: Optional[int] = None
    pwm_pins: List[str] = Field(default_factory=list, description="board pins with PWM, as printed")
    wireless: List[Literal[WIRELESS]] = Field(default_factory=list, description="empty if none")
    measures: Optional[str] = Field(None, description="sensors: what it measures, e.g. 'temperature, humidity'")
    stud_count: Optional[int] = Field(None, description="LEGO: studs on top")
    anti_stud_count: Optional[int] = Field(None, description="LEGO: stud sockets underneath")
    slope_angle_deg: Optional[float] = Field(None, description="LEGO slopes")


class Join(BaseModel):
    port_kind: Literal[PORT_KINDS] = Field(description="one of the port kinds listed on the card")
    mates: List[Literal[MATES_CODES]] = Field(description="every kind of thing that goes into or onto it, as codes: "
                                                         "e.g. ['stud'] for an anti-stud, ['breadboard-hole', "
                                                         "'header-socket', 'wire-end'] for a component lead")
    mates_text: Optional[str] = Field(None, description="only if the codes miss something worth saying")
    method: Literal[JOIN_METHODS]
    holds_by: Literal[HOLDS_BY_CODES]
    reversible: Literal[REVERSIBLE_CODES]


class CardIssue(BaseModel):
    field: Literal["stud_count", "anti_stud_count", "ports", "name", "category", "other"]
    card_says: str
    should_be: str
    why: str


class PartMeta(BaseModel):
    part_type_id: str
    description: str = Field(description="1-2 plain sentences a learner understands")
    material: List[Literal[MATERIALS_CODES]] = Field(description="what it is made of, as codes, e.g. ['abs'], "
                                                                 "['pcb', 'plastic', 'metal']")
    size_studs: Optional[List[int]] = Field(None, description="LEGO only: footprint [w, l] in studs, shorter first")
    dimensions_mm: Optional[List[float]] = Field(None, description="LEGO only: [width, length, height] without studs")
    polarized: bool = Field(description="true if it can be fitted the wrong way round (turned or flipped in its holes, "
                                        "or its plug put on backwards) and then does not work or is damaged, so the "
                                        "lesson must say which way round: LEDs, diodes, electrolytic capacitors, buzzers, "
                                        "batteries, chips, 3-leg sensors and transistors, modules on a row of header "
                                        "pins, servo plugs. False if every way it fits works the same (resistor, plain "
                                        "wire, breadboard) or it fits only one way (a keyed plug). Always false for LEGO")
    reverse_power: Literal[REVERSE_POWER_CODES] = Field(
        description="what happens if its power and ground are swapped: 'damage' (it can be destroyed), 'no-harm' (no "
                    "harm, it does not work), 'protected' (it has reverse-polarity protection), or 'n/a' (no power "
                    "connection, e.g. a resistor, a wire, LEGO)")
    specs: Specs
    basis: Dict[str, BASIS] = Field(description="for each spec field you filled in: card, image, maker-page or "
                                               "general-knowledge")
    joins: List[Join]
    learner_tips: List[str] = Field(description="at most 2: how to hold, place or tell it apart")
    card_issues: List[CardIssue] = Field(description="only where the card looks wrong; empty if it looks right")
    confidence: float = Field(ge=0, le=1)


class Answer(BaseModel):
    parts: List[PartMeta]


SYSTEM = """You write catalogue metadata for parts used in step-by-step build lessons (LEGO and Arduino).
For each part you get its catalogue card (and for LEGO a picture drawn from its real 3D shape, in neutral grey;
colour is not a property of the part). Return one entry per part_type_id, in the same order, with no others.
- Describe the part TYPE, not one copy of it: no colours, no resistor values (a resistor's value belongs to each copy).
- Only state what you are sure of; mark each specification's basis: 'card' (it is on the card), 'image' (you read it
  from the picture) or 'general-knowledge'.
- Answer in the codes the schema lists (material, port kinds, what a join mates with, reverse_power, basis), not in
  your own words: code reads them. Only the description and the tips are free text.
- joins: one per port kind on the card that something connects to; say how it holds and how it comes apart, and
  in `mates` every kind of thing that goes into or onto it (codes). If the card lists NO ports, give one join per kind of connector the part has as sold, named with
  these kinds: header-pin, header-socket, lead, wire-end, screw, socket, pad, lug.
- card_issues: only if the card itself looks wrong (for example a 2 x 2 slope listed with only 2 anti-stud cells).
- holds_by: friction = pressed together and held by rubbing (LEGO clutch, a pin in a tight hole); spring = a metal
  spring contact grips it (breadboard holes, female header sockets, so also a male header pin, lead or wire end
  pushed into one); force = clamped (a screw terminal); material =
  solder or glue; form = shaped to lock (a keyed plug).
- reversible: hand = pulls out by hand; tool = needs a screwdriver or similar; damaging = comes apart only by
  damaging something; permanent = soldered or glued. Describe the part's own ports, as sold (pre-soldered headers
  plug in by hand; bare pads or solder lugs are permanent).
- specs: fill the standard fields that apply and leave the rest null; for each field you fill, say in `basis`
  where it comes from (card, image, maker-page, general-knowledge). Use the card's own values where it has them.
- LEGO sizes: 1 stud = 8 mm, a brick is 9.6 mm tall and a plate 3.2 mm, without studs."""


# ---------------------------------------------------------------- what the call sees

# ---------------------------------------------------------------- codes, not free text
# Everything but the description, the tips and the reasons (`why`) is stored as codes and numbers, so code can check
# and answer before Claude is asked. Claude drafts in words (the schema above); normalize() turns a draft into codes
# by code, and keeps the original phrase only where it says more than the codes (`material_text`, `mates_text`).
RP_CODE = {"damage": "damage", "no harm, does not work": "no-harm", "protected": "protected",
           "not applicable": "n/a"}
BASIS_CODE = {"general knowledge": "general-knowledge", "maker page": "maker-page"}
MATERIALS = [(r"\babs\b", "abs"), (r"polycarbonate|transparent|trans-clear", "polycarbonate"), (r"rubber", "rubber"),
             (r"silicone", "silicone"), (r"fib(re|er) ?glass|\bpcb\b|circuit board|fr-?4", "pcb"),
             (r"ceramic", "ceramic"), (r"(?<!fibre)(?<!fiber)(?<!fibre )(?<!fiber )glass", "glass"), (r"copper", "copper"), (r"steel", "steel"),
             (r"alumin", "aluminium"), (r"carbon", "carbon"), (r"metal", "metal"), (r"semiconductor", "semiconductor"),
             (r"epoxy", "epoxy"), (r"plastic|nylon|pvc|polymer", "plastic"), (r"fabric|textile|cloth", "fabric"),
             (r"paper|cardboard", "paper"), (r"wood", "wood"), (r"magnet", "magnet")]
MATES = [(r"anti-?stud|underside tube|tubes? (under|below)", "anti-stud"), (r"\bstuds?\b", "stud"),
         (r"pin ?hole|technic hole", "pin-hole"), (r"axle ?hole|cross hole", "axle-hole"), (r"\baxle\b", "axle"),
         (r"\bclip\b", "clip"), (r"\bbar\b|handle", "bar"), (r"\bball\b", "ball"), (r"breadboard", "breadboard-hole"),
         (r"female (jumper|dupont)|jumper (wire )?(end|socket)|dupont|(?<!male )jumper wire", "wire-end"),
         (r"(?<!fe)male header|header pin|(?<!fe)male jumper", "header-pin"),
         (r"female header|header socket|hat socket|female socket|stacking header", "header-socket"),
         (r"component lead|\blead\b|\blegs?\b", "lead"), (r"screw|driver terminal|terminal block", "screw"),
         (r"solder|\bpad\b|perfboard", "pad"), (r"usb-?c\b", "usb-c"), (r"micro-?usb|usb micro", "usb-micro"),
         (r"\busb\b", "usb"), (r"barrel|dc jack|power plug", "barrel-jack"), (r"battery (connector|plug|clip)|jst", "battery-connector"),
         (r"grove", "grove"), (r"qwiic|stemma", "qwiic"), (r"\bsma\b|u\.?fl|antenna", "rf-connector"),
         (r"rj-?45|ethernet", "rj45"), (r"rca", "rca"), (r"micro ?sd", "microsd"), (r"mains|wall outlet", "mains"),
         (r"battery terminal|9v", "battery-connector"), (r"fpc|ribbon|flex cable|csi", "fpc"),
         (r"molex|connector plug|\bplug\b", "plug"), (r"\bheader\b", "header-pin"),
         (r"neck pin|top of a minifig|top of a minidoll|\bhead\b", "minifig-neck"), (r"hinge", "hinge"),
         (r"wheel|shaft", "axle-hole"), (r"door", "hinge"),
]
MATES_FALLBACK = [(r"bare wire|stripped wire|motor wire|wire ends?\b|\bwires?\b", "bare-wire"),  # only when nothing
                  (r"\bsocket\b", "socket"), (r"connector", "connector")]                     # more specific matched


def _codes(text, table):
    t = str(text or "").lower()
    out = []
    for rx, code in table:
        if re.search(rx, t) and code not in out:
            out.append(code)
    return out


def normalize(m):
    """A part's metadata as codes and numbers (idempotent: stored metadata already in codes stays as it is)."""
    m = dict(m)
    if isinstance(m.get("size_studs"), str):
        ws = [int(x) for x in re.findall(r"\d+", m["size_studs"])[:2]]
        m["size_studs"] = sorted(ws) if len(ws) == 2 else None
    if m.get("reverse_power") in RP_CODE:
        m["reverse_power"] = RP_CODE[m["reverse_power"]]
    if isinstance(m.get("overridden"), dict) and m["overridden"].get("reverse_power") in RP_CODE:
        m["overridden"] = {**m["overridden"], "reverse_power": RP_CODE[m["overridden"]["reverse_power"]]}
    if isinstance(m.get("material"), str):
        m["material_text"] = m["material"]
        m["material"] = _codes(m["material"], MATERIALS) or ["other"]
    joins = []
    for j in m.get("joins") or []:
        j = dict(j)
        if "mates_with" in j:
            j["mates_text"] = j.pop("mates_with")
            j["mates"] = _codes(j["mates_text"], MATES) or _codes(j["mates_text"], MATES_FALLBACK) or ["other"]
        joins.append(j)
    if "joins" in m:
        m["joins"] = joins
    if m.get("basis"):
        m["basis"] = {k: BASIS_CODE.get(v, v) for k, v in m["basis"].items()}
    sp = dict(m.get("specs") or {})
    for k in ("interface", "wireless"):
        if isinstance(sp.get(k), list):
            sp[k] = [{"single-wire": "1-wire", "onewire": "1-wire"}.get(c, c) for c in
                     (x.strip().lower().replace(" ", "-") for x in sp[k] if x and x.strip().lower() != "none")]
    if sp:
        m["specs"] = sp
    if isinstance(m.get("substitutes"), dict) and m["substitutes"].get("value") == "by role":
        m["substitutes"] = {**m["substitutes"], "value": "by-role"}
    if isinstance(m.get("status"), str) and m["status"].startswith("drafted"):
        m["status"] = "drafted"
    if "checks_failed" in m:
        m["checks_failed"] = [c if isinstance(c, dict) else {"rule": c.split(":", 1)[0].strip(),
                                                              "message": c.split(":", 1)[1].strip() if ":" in c else c}
                              for c in m["checks_failed"] or []]
    return m


def render_part(ldraw, size=320):
    """PNG of one LDraw part, drawn by code from its real triangles: grey, lit from above, seen from the front-right."""
    from PIL import Image, ImageDraw
    from graph import lego_model
    eye = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    cam = {"az": 35, "el": 30, "scale": 1.0, "tx": 0.0, "ty": 0.0}
    tris = []
    for c, tri in lego_model.mesh(ldraw):
        if c == "24":
            continue
        r = lego_model.view(cam["az"], cam["el"])
        pts = [lego_model._apply(r, list(p)) for p in tri]
        u = [pts[1][i] - pts[0][i] for i in range(3)]
        v = [pts[2][i] - pts[0][i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        k = math.sqrt(sum(x * x for x in n)) or 1
        light = abs(-0.3 * n[0] - 0.8 * n[1] - 0.5 * n[2]) / k  # view y is down: the light is above
        tris.append((sum(p[2] for p in pts) / 3, pts, light))
    if not tris:
        return None
    xs = [p[0] for _, pts, _ in tris for p in pts]
    ys = [p[1] for _, pts, _ in tris for p in pts]
    s = 0.8 * size / max(max(xs) - min(xs), max(ys) - min(ys), 1)
    ox, oy = size / 2 - s * (min(xs) + max(xs)) / 2, size / 2 - s * (min(ys) + max(ys)) / 2
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for _, pts, light in sorted(tris, key=lambda t: -t[0]):
        g = int(90 + 150 * light)
        d.polygon([(p[0] * s + ox, p[1] * s + oy) for p in pts], fill=(g, g, g + 8), outline=(70, 70, 75))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _card_text(card):
    keep = {k: card.get(k) for k in ("part_type_id", "display_name", "category", "aliases", "intrinsic_behaviour",
                                     "electrical", "port_rule", "note") if card.get(k)}
    kinds = collections.Counter(p["kind"] for p in card.get("ports", []))
    keep["port_kinds"] = dict(kinds)
    if len(card.get("ports", [])) <= 30:
        keep["ports"] = [p["id"] for p in card["ports"]]
    return json.dumps(keep)


def definitions_of(lesson_id, store=None):
    """The definitions a lesson uses: {part_type_id: (card, an instance's LDraw file or None)}, and the domain."""
    store = store or lesson_store.STORE
    row, graphs = lesson_store._load(lesson_id, store)
    phys = graphs["physical"]
    cards = lesson_store._cards(phys["part_catalogue"])
    out = {}
    for n in phys["nodes"]:
        card, _ = lesson_store.definition(cards, n["type"])
        if card and card["part_type_id"] not in out:
            ldraw = n.get("props", {}).get("ldraw")
            if ldraw and card["part_type_id"] != n["type"]:  # a printed copy: draw the plain base design
                ldraw = card["part_type_id"][len("lego-"):] + ".dat"
            out[card["part_type_id"]] = (card, ldraw)
    return out, row["lesson_type"], phys


# ---------------------------------------------------------------- checks

def _box_mm(ldraw):
    """(width, length, height) in mm of the part's body: the footprint of its stud grid (lego_model.grid: handles
    and clips sticking out left out), the height of the material over that footprint (top studs left out)."""
    from graph import lego_model
    g = lego_model.grid(ldraw)
    if g is None:
        return None
    (x0, nx), (z0, nz) = g[:2]
    ys = [p[1] for c, t in lego_model.mesh(ldraw) if c != "24" for p in t
          if x0 - 0.5 <= p[0] <= x0 + 20 * nx + 0.5 and z0 - 0.5 <= p[2] <= z0 + 20 * nz + 0.5]
    w, l = sorted([20 * nx * LDU_MM, 20 * nz * LDU_MM])
    tops = [p[1] for k, p, a in lego_model.features(ldraw) if k == "stud" and a[1] < -0.95]
    top = min(tops) if tops else min(ys)  # the body's top: where its studs stand (LDraw -Y is up)
    return w, l, (max(ys) - top) * LDU_MM if ys else None


def lego_counts(ldraw):
    """(top studs, underside cells) from the part's real shape: studs from its stud primitives, cells with material
    from its stud grid (lego_model.grid)."""
    from graph import lego_model
    studs = len({tuple(round(c, 1) for c in p) for k, p, a in lego_model.features(ldraw)  # a stud drawn twice
                 if k == "stud" and a[1] < -0.95})                                       # is one stud
    g = lego_model.grid(ldraw)
    return studs, len(g[2]) if g else None


def check(meta, asked, domain, physical):
    """[(rule, definition, message)] for one call's answer."""
    issues = []
    got = {m["part_type_id"]: m for m in meta}
    for t in asked:
        if t not in got:
            issues.append(("M1", t, "no answer"))
    for t in got:
        if t not in asked:
            issues.append(("M1", t, "answered a definition that was not asked for"))
    # what the lesson's own edges say about reversibility, by definition and port kind
    physical = physical or {"part_catalogue": None, "nodes": [], "edges": []}  # the whole catalogue: no lesson edges
    cards = lesson_store._cards(physical["part_catalogue"]) if physical["part_catalogue"] else {}
    types = {n["id"]: lesson_store.definition(cards, n["type"])[0] for n in physical["nodes"]}
    seen = collections.defaultdict(set)
    for e in physical["edges"]:
        for end, port in ((e["u"], e.get("u_port")), (e["v"], e.get("v_port"))):
            card = types.get(end)
            if card and port and e.get("reversible"):
                kind = next((p["kind"] for p in card["ports"] if lesson_store.port_match({"ports": [p]}, port) in ("exact", "pattern")), None)
                if kind:
                    seen[(card["part_type_id"], kind)].add(e["reversible"])
    for t, m in got.items():
        if t not in asked:
            continue
        card, ldraw = asked[t]
        kinds = {p["kind"] for p in card.get("ports", [])}
        for j in m["joins"]:
            found = []
            if kinds and j["port_kind"] not in kinds:
                found.append(("M2", t, f"join on port kind '{j['port_kind']}', which the card does not have ({sorted(kinds)})"))
            said = seen.get((t, j["port_kind"]))
            if said and j["reversible"] not in said:
                found.append(("M5", t, f"{j['port_kind']} join '{j['reversible']}', the lesson's edges say {sorted(said)}"))
            # M8, M9: where GRAPH_SPEC §5.1 rules a port kind, the rule wins; what Claude said is kept as `overridden`
            for field, rules in (("holds_by", HOLDS_BY), ("reversible", REVERSIBLE)):
                rule = rules.get(j["port_kind"])
                if rule and j[field] != rule:
                    j.setdefault("overridden", {})[field] = j[field]
                    j[field] = rule
            j["checked"] = not found  # the lesson assembler fills edges only from joins that passed
            if not kinds:
                j["card_has_no_ports"] = True  # the part's connectors as sold; the card has no ports to tie it to
            issues += found
        # M10: what a power/ground swap does, against the research (DATA_STRUCTURE.md §7) and the card's ports
        rp = RP_CODE.get(m.get("reverse_power"), m.get("reverse_power"))  # words (a draft) or codes (stored)
        m["reverse_power"] = rp
        if t in REVERSE_POWER and rp != RP_CODE.get(REVERSE_POWER[t], REVERSE_POWER[t]):  # the research wins, Claude's word is kept
            m.setdefault("overridden", {})["reverse_power"] = rp
            m["reverse_power"] = rp = RP_CODE.get(REVERSE_POWER[t], REVERSE_POWER[t])
        names = {p["id"].upper().split(".")[0] for p in card.get("ports", [])}
        source = card.get("category") in ("battery", "battery-holder", "power-supply")  # it IS the power
        if domain == "arduino" and rp == "n/a" and names & POWER_PINS and not source:
            issues.append(("M10", t, f"reverse_power 'not applicable', but it has power pins {sorted(names & POWER_PINS)}"))
        pol = (card.get("intrinsic_behaviour") or {}).get("is_polarized")
        if pol is not None and bool(pol) != m["polarized"]:
            issues.append(("M3", t, f"polarized={m['polarized']}, the card says {pol}"))
        if domain == "lego" and ldraw:
            real = _box_mm(ldraw)
            if real and real[2] and m.get("dimensions_mm") and len(m["dimensions_mm"]) == 3:
                w, l, h = sorted(m["dimensions_mm"][:2]) + [m["dimensions_mm"][2]]
                bad = [n for n, a, b in (("width", w, real[0]), ("length", l, real[1])) if abs(a - b) > 0.12 * b + 0.5]
                if abs(h - real[2]) > 0.12 * real[2] + 0.5 and abs(h - real[2] - STUD_MM) > 0.12 * real[2] + 0.5:
                    bad.append("height")
                if bad:
                    issues.append(("M4", t, f"dimensions {m['dimensions_mm']} mm; the shape is {real[0]:.1f} x "
                                            f"{real[1]:.1f} x {real[2]:.1f} mm ({', '.join(bad)} off)"))
            if real and m.get("size_studs"):
                ws = m["size_studs"] if isinstance(m["size_studs"], list) else re.findall(r"\d+", m["size_studs"])
                cells = sorted([max(1, round(real[0] / 8)), max(1, round(real[1] / 8))])
                if len(ws) >= 2 and sorted(map(int, ws[:2])) != cells:
                    issues.append(("M4", t, f"size {m['size_studs']} studs; the shape is {cells[0]} x {cells[1]}"))
            studs, cells = lego_counts(ldraw)
            on_card = collections.Counter(p["kind"] for p in card.get("ports", []))
            for kind, n in (("stud", studs), ("anti-stud", cells)):
                if n is not None and on_card[kind] != n:  # code's own check of the card, whatever Claude says
                    issues.append(("C1", t, f"the card lists {on_card[kind]} {kind} ports; the shape has {n}"))
            for ci in m["card_issues"]:
                if ci["field"] in ("stud_count", "anti_stud_count"):
                    truth_n = studs if ci["field"] == "stud_count" else cells
                    claim = re.findall(r"\d+", ci["should_be"])
                    ci["checked"] = ("confirmed" if claim and truth_n is not None and int(claim[0]) == truth_n
                                     else "rejected")
                    ci["from_shape"] = truth_n
                    if ci["checked"] == "rejected":
                        issues.append(("M7", t, f"card issue '{ci['field']}: {ci['should_be']}' rejected: the shape has {truth_n}"))
        if domain == "arduino":
            for k, v in (card.get("electrical") or {}).items():
                a = (m.get("specs") or {}).get(k)
                if not isinstance(a, (int, float)) or not isinstance(v, (int, float)) or isinstance(v, bool):
                    continue
                if abs(a - v) > 0.15 * abs(v) + 1e-9:
                    issues.append(("M6", t, f"{k} = {a}, the card says {v}"))
        # M11: the standard fields only, each with its basis
        specs, basis = m.get("specs") or {}, m.get("basis") or {}
        filled = [k for k, v in specs.items() if v not in (None, [], "", ["none"])]  # "none" is an answer, not a claim
        unbased = [k for k in filled if k not in basis]
        if unbased:
            issues.append(("M11", t, f"no basis given for {', '.join(unbased)}"))
        allowed = {"card", "image", "maker page", "general knowledge", "maker-page", "general-knowledge"}  # words or codes
        odd = sorted({f"{k}: {v}" for k, v in basis.items() if v not in allowed})
        if odd:
            issues.append(("M11", t, f"basis not one of card, image, maker page, general knowledge: {'; '.join(odd)}"))
        m["schema_version"] = SCHEMA_VERSION
    return issues


# ---------------------------------------------------------------- one lesson's definitions

def enrich(lesson_id, model="sonnet", effort="medium", store=None, call=None, redo=False, path=None):
    """Draft and check metadata for the definitions one lesson uses that have none yet (all of them with `redo`):
    a new lesson with one new part costs one part, not the forty already in the catalogue. call: (system, content,
    schema) -> (dict, stats); the default is one `claude -p` call (extract.claude_json). Returns
    {definition: entry}, stats, issues; no call at all when nothing is missing."""
    asked, domain, physical = definitions_of(lesson_id, store)
    have = load(path or OUT)
    skipped = [] if redo else sorted(t for t in asked if t in have)
    asked = {t: v for t, v in asked.items() if t not in skipped}
    if not asked:
        return {}, {"lesson": lesson_id, "domain": domain, "definitions": 0, "skipped": len(skipped), "images": 0,
                    "seconds": 0, "cost_usd": 0, "issues": 0, "rules": {}}, []
    if call is None:
        from graph import extract
        call = lambda system, content, schema: extract.claude_json(system, content, schema, model=model,  # noqa: E731
                                                                    effort=effort, timeout=900)
    entries, stats, issues = draft(asked, domain, physical, lesson_id, call)
    stats["skipped"] = len(skipped)
    return entries, stats, issues


def draft(asked, domain, physical, label, call):
    """One call for these definitions ({id: (card, LDraw file or None)}), checked; physical: the lesson's graph or None."""
    t0 = time.perf_counter()
    model = "?"
    content, images = [{"type": "text", "text": f"{label} ({domain}): {len(asked)} parts."}], 0
    for t, (card, ldraw) in asked.items():
        content.append({"type": "text", "text": f"PART {t}\nCARD: {_card_text(card)}"})
        png = render_part(ldraw) if domain == "lego" and ldraw else None
        if png:
            images += 1
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                        "data": base64.b64encode(png).decode()}})
    prep = time.perf_counter() - t0
    answer, stats = call(SYSTEM, content, Answer)
    t1 = time.perf_counter()
    issues = check(answer["parts"], asked, domain, physical)
    stats.update({"lesson": label, "domain": domain, "definitions": len(asked), "images": images,
                  "prep_seconds": round(prep, 2), "check_seconds": round(time.perf_counter() - t1, 3),
                  "issues": len(issues), "rules": dict(collections.Counter(r for r, _, _ in issues))})
    by = collections.defaultdict(list)
    for r, t, msg in issues:
        by[t].append({"rule": r, "message": msg})
    out = {}
    for m in answer["parts"]:
        if m["part_type_id"] in asked:
            out[m["part_type_id"]] = {**m, "status": "drafted", "checks_failed": by.get(m["part_type_id"], []),
                                      "drafted_by": stats.get("model", model), "via": "vlm" if images else "llm",
                                      "lesson": label}
    return out, stats, issues


def enrich_catalogue(domain, model="sonnet", effort="medium", batch=12, workers=3, redo=False, call=None, only=None):
    """Draft and check metadata for every card of a domain's catalogue, `batch` cards a call, `workers` calls at once;
    saved after each call, so a stopped run resumes (cards that already have metadata are skipped unless `redo`)."""
    import concurrent.futures as cf
    if call is None:
        from graph import extract
        call = lambda system, content, schema: extract.claude_json(system, content, schema, model=model,  # noqa: E731
                                                                    effort=effort, timeout=900)
    cards = part_catalogue.of_domain(part_catalogue.load(), domain)
    have = load()
    todo = [t for t in sorted(cards) if (redo or t not in have) and (only is None or t in only)]
    groups = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    runs, all_issues = [], []

    def one(k, ids):
        asked = {t: (cards[t], (t[len("lego-"):] + ".dat") if domain == "lego" else None) for t in ids}
        return k, draft(asked, domain, None, f"{domain} catalogue batch {k}/{len(groups)}", call)

    with cf.ThreadPoolExecutor(workers) as pool:
        futs = [pool.submit(one, k, g) for k, g in enumerate(groups, 1)]
        for f in cf.as_completed(futs):
            try:
                k, (entries, stats, issues) = f.result()
            except Exception as e:  # one failed call: its cards stay to do, the run goes on
                print(f"  batch failed: {str(e)[:200]}")
                continue
            save(entries)
            runs.append(stats)
            all_issues += issues
            print(f"  batch {k}/{len(groups)}: {len(entries)} cards in {stats.get('seconds')}s ${stats.get('cost_usd')}"
                  f"; {len(issues)} check failures {stats['rules']}", flush=True)
    return runs, all_issues


def recheck(domain, path=OUT):
    """The checks again on stored metadata (after a rule changes), no model call. Returns the failures."""
    data, cards, issues = load(path), part_catalogue.of_domain(part_catalogue.load(path), domain), []
    for t, m in data.items():
        if t not in cards:
            continue
        for j in m["joins"]:
            j.pop("checked", None)
            j.pop("card_has_no_ports", None)
        found = check([{**m, "part_type_id": t}], {t: (cards[t], (t[len("lego-"):] + ".dat") if domain == "lego" else None)},
                      domain, None)
        m["checks_failed"] = [{"rule": r, "message": msg} for r, _, msg in found]
        issues += found
    save(data, path)
    return issues


def load(path=OUT):
    """{part id: its drafted metadata} for the parts that have some."""
    return {t: v["metadata"] for t, v in part_catalogue.load(path).items() if v["metadata"].get("description")}


def describe_new(type_ids, domain, model="sonnet", effort="medium", call=None, path=OUT, label="new parts"):
    """The metadata rules for the parts a new lesson brings, the same for every way a lesson is made:
      1 card       the part has a card in the catalogue (the caller makes sure: shops, Claude's draft, Rebrickable)
      2 draft      Claude drafts its metadata in the standard fields, only for parts that have none
                   (a LEGO part with a picture of its 3D shape)
      3 check      code checks the draft: M1-M11 (polarity, sizes against the 3D shape, values against the card,
                   every value's source named), C1 (the card's own stud counts)
      4 codes      it is stored as codes, not free text (normalize), apart from the description and the tips
      5 computed   the catalogue is rebuilt, which adds what code works out: fits, connect_by, takes,
                   interchangeable ports, substitutes, pin facts
    Returns the stats ({"described": 0} and no call when every part has metadata already)."""
    parts = part_catalogue.load(path)
    have = load(path)
    todo = sorted({t for t in type_ids if t in parts and t not in have})
    missing = sorted({t for t in type_ids if t not in parts})
    if not todo:
        return {"described": 0, "already": len(set(type_ids)) - len(missing), "no_card": missing, "cost_usd": 0}
    if call is None:
        from graph import extract
        call = lambda system, content, schema: extract.claude_json(system, content, schema, model=model,  # noqa: E731
                                                                    effort=effort, timeout=900)
    asked = {t: (parts[t], (t[len("lego-"):] + ".dat") if domain == "lego" else None) for t in todo}
    entries, stats, issues = draft(asked, domain, None, label, call)
    save(entries, path)
    return {"described": len(entries), "already": len(set(type_ids)) - len(todo) - len(missing), "no_card": missing,
            "checks_failed": len(issues), "seconds": stats.get("seconds"), "cost_usd": stats.get("cost_usd")}


def save(entries, path=OUT):
    """Write drafted metadata into each part's metadata block, as codes (normalize); its domain and provenance stay
    as they are, and the catalogue is rebuilt so the fields code works out (fits, connect_by, interchangeable…)
    are there too."""
    from graph.filelock import locked
    with locked(path):  # lessons made side by side each add their parts' metadata
        parts = part_catalogue.load(path)
        entries = {t: normalize(e) for t, e in entries.items()}
        for t, e in entries.items():
            keep = {k: parts[t]["metadata"][k] for k in ("domain", "source_catalogue", "card_made_by")}
            parts[t]["metadata"] = {**{k: v for k, v in e.items() if k != "part_type_id"}, **keep}
        part_catalogue.save(parts, path)
        part_catalogue.build(path)  # the computed fields come back with the new metadata
    lesson_store._CARDS.pop(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lessons", nargs="*")
    ap.add_argument("--catalogue", choices=["arduino", "lego"], help="every card of this catalogue instead of lessons")
    ap.add_argument("--recheck", choices=["arduino", "lego"], help="run the checks again on stored metadata (no call)")
    ap.add_argument("--redo", action="store_true", help="also parts that already have metadata (default: only new ones)")
    ap.add_argument("--only", choices=["failed", "no-joins"], nargs="+",
                    help="--catalogue: redo only cards whose metadata failed a check / has no joins")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--effort", default="medium")
    a = ap.parse_args(argv)
    runs = []
    if a.recheck:
        issues = recheck(a.recheck)
        print(f"{a.recheck}: {len(issues)} check failures {dict(collections.Counter(r for r, _, _ in issues))}")
        for r, t, msg in issues:
            print(f"  {r} {t}: {msg}")
        return
    if a.catalogue:
        t0 = time.perf_counter()
        only = None
        if a.only:
            have, cards = load(), part_catalogue.of_domain(part_catalogue.load(), a.catalogue)
            only = set()
            for t in cards:
                m = have.get(t)
                if m and "no-joins" in a.only and not m["joins"]:
                    only.add(t)
                if m and "failed" in a.only:  # failed then, or would fail the checks as they are now
                    if m["checks_failed"] or check([{**m, "part_type_id": t}], {t: (cards[t], None)}, "arduino" if a.catalogue == "arduino" else a.catalogue, None):
                        only.add(t)
            print(f"redoing {len(only)} cards")
        runs, issues = enrich_catalogue(a.catalogue, a.model, a.effort, redo=a.redo or bool(only), only=only)
        print(f"{a.catalogue} catalogue: {sum(r['definitions'] for r in runs)} cards in {time.perf_counter() - t0:.0f}s "
              f"wall, ${sum(r.get('cost_usd', 0) for r in runs):.3f}; {len(issues)} check failures "
              f"{dict(collections.Counter(r for r, _, _ in issues))}")
    for lid in a.lessons:
        entries, stats, issues = enrich(lid, a.model, a.effort, redo=a.redo)
        if entries:
            save(entries)
        runs.append(stats)
        print(f"{lid}: {stats['definitions']} definitions drafted ({stats['images']} pictures), {stats['skipped']} "
              f"already had metadata; {stats['seconds']}s, ${stats['cost_usd']}; {len(issues)} check failures {stats['rules']}")
        for r, t, msg in issues:
            print(f"  {r} {t}: {msg}")
    log = ROOT / "data" / "lessons" / "store" / "part_metadata_runs.json"
    log.write_text(json.dumps(lesson_store._read(log, []) + runs, indent=1))


if __name__ == "__main__":
    main()
