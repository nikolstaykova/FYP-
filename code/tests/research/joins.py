"""One vocabulary for physical edges, LEGO and Arduino alike (GRAPH_SPEC §5, DATA_STRUCTURE.md §3.3).

Every physical edge has the same shape in every domain:
  joined      id, u, u_port, v, v_port, method, holds_by, freedom, reversible     (u is the side that goes in)
  contact     id, u, u_port, v, v_port, method ("rest" when one rests on the other, else null: side by side)
  electrical  id, u, u_port, v, v_port                                            (current can flow)
with values only from GRAPH_SPEC §5.1. A join's attributes follow from the kinds of its two ports, by the one table
below (GRAPH_SPEC §5.2), so a stud in a socket and a wire end in a breadboard hole are described the same way.
Domain extras sit under their own name (`wokwi` on an Arduino edge) and never replace these.
"""
import re

# (kind going in, kind taking it) -> (method, holds_by, freedom, reversible)       GRAPH_SPEC §5.2
TABLE = {
    ("stud", "anti-stud"): ("insert", "friction", "rigid", "hand"),
    ("pin", "pin-hole"): ("insert", "friction", "revolute", "hand"),
    ("axle", "axle-hole"): ("insert", "form", "rigid", "hand"),
    ("axle", "pin-hole"): ("insert", None, "revolute", "hand"),
    ("bar", "clip"): ("snap", "spring", "revolute", "hand"),
    ("ball", "socket"): ("snap", "friction", "ball", "hand"),
    ("header-pin", "wire-end"): ("push-on", "spring", "rigid", "hand"),     # a female jumper pushed onto a male pin
    ("header-pin", "header-socket"): ("insert", "spring", "rigid", "hand"),
}
INTO_SPRING = {"breadboard-hole", "header-socket"}   # a spring contact grips what goes in
# Everything an electronics port can go into or onto: (its kind) -> [(the other port's kind, method, holds_by,
# reversible)]. The catalogue's `fits` for each part comes from this table, by code: a resistor's lead goes into a
# breadboard hole, but also a header socket, a female jumper end or a screw terminal, or it is soldered to a pad.
FITS = {  # "socket" (an antenna's SMA socket) and "hole" (a mounting hole) are not places a leg goes
    "lead": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
             ("wire-end", "push-on", "spring", "hand"), ("screw", "clamp", "force", "tool"),
             ("pad", "solder", "material", "tool")],
    "header-pin": [("header-socket", "insert", "spring", "hand"), ("breadboard-hole", "insert", "spring", "hand"),
                   ("wire-end", "push-on", "spring", "hand"), ("pad", "solder", "material", "tool")],
    "pin": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
            ("wire-end", "push-on", "spring", "hand"), ("pad", "solder", "material", "tool")],
    "wire-end": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
                 ("header-pin", "push-on", "spring", "hand"), ("screw", "clamp", "force", "tool"),
                 ("pad", "solder", "material", "tool")],
    "lug": [("screw", "clamp", "force", "tool"), ("pad", "solder", "material", "tool")],
}


def fits_into(kind_):
    """[(other kind, method, holds_by, reversible)] for a port kind: what goes in it as well as what it goes into."""
    out = list(FITS.get(kind_, []))
    for male, rows in FITS.items():
        for other, m, h, r in rows:
            if other == kind_ and not any(o == male for o, *_ in out):
                out.append((male, m, h, r))
    return out


GOES_IN = {"lead", "header-pin", "wire-end", "pin", "lug"}  # a leg, a male header pin, a wire's end, a lug
BY_NAME = [(r"^stud\b", "stud"), (r"^anti\b", "anti-stud"), (r"^pin$", "pin"), (r"^hole\b", "pin-hole"),
           (r"^axle$", "axle"), (r"^clip\b", "clip"), (r"^bar\b", "bar")]  # a port named as ldraw_studs names it


def kind(card, port):
    """A port's kind: from its card (by id, alias or the card's own pattern), else from the port's name."""
    from lesson_graphs import port_match
    if not port:
        return None
    for p in (card or {}).get("ports", []):
        if port_match({"ports": [p]}, port) in ("exact", "pattern"):
            return p["kind"]
    for rx, k in BY_NAME:
        if re.search(rx, port or ""):
            return k
    return None


def attrs(u_kind, v_kind):
    """(method, holds_by, freedom, reversible) for a join of these port kinds, or None when the table has no row."""
    for pair in ((u_kind, v_kind), (v_kind, u_kind)):  # the attributes do not depend on which end is written first
        if pair in TABLE:
            return TABLE[pair]
    if u_kind in GOES_IN and v_kind in INTO_SPRING:
        return ("insert", "spring", "rigid", "hand")
    return None


def describe(edge, cards_of):
    """Fill a joined edge's attributes from its port kinds (in place) where it does not state them. A value it does
    state is its own fact and is kept (a header soldered on: solder, tool); returned as [(field, stated, rule)] where
    it is not the table's, for review. cards_of(instance) -> its card."""
    if edge["type"] != "joined":
        return []
    rule = attrs(kind(cards_of(edge["u"]), edge["u_port"]), kind(cards_of(edge["v"]), edge["v_port"]))
    if rule is None:
        return []
    out = []
    for field, value in zip(("method", "holds_by", "freedom", "reversible"), rule):
        if edge.get(field) is None:
            edge[field] = value
        elif value is not None and edge[field] != value:
            out.append((field, edge[field], value))
    return out
