"""The one parts catalogue: LEGO and Arduino parts together.

What it is   parts.json (parts/parts.json, DATA_STRUCTURE.md §3.4): built from the two card stores, each card with
             its metadata block (build); read with load, connection, either_way and swaps (the ports that can stand
             in for one another). Also the catalogue as the graph engine reads it (GRAPH_SPEC §6): one entry per
             part type with its ports (Catalogue), the verified Arduino seed from CircuitQuest (arduino_seed), and
             LEGO entries from a piece's name and size (lego_entry, brick_dims).
Used for     every lookup of what a part is: lessons, checks, the tutor, the validator.
Where        almost every module (arduino/, lego_booklet/pdf_lesson.py, lesson_store.py, parts/);
             rebuilt after new cards: python -m graph.parts.part_catalogue build (or stats).
"""

import argparse
import collections
import copy
import glob
import json
import pathlib
import re

from graph.arduino import pins


# ---- the catalogue as the graph engine reads it: part types, the Arduino seed, LEGO entries ------------------
CQ = pathlib.Path.home() / "Desktop" / "CirquitQuest"


UNO_PORTS = [str(n) for n in range(14)] + [f"A{n}" for n in range(6)] + [
    "GND.1", "GND.2", "GND.3", "5V", "3.3V", "VIN", "AREF", "IOREF", "RESET"]


def _entry(type_, name, category, ports, *, conducts=(), through=(), symmetric=(), polarized=False,
           connector=False, alias=None, status="verified", mirror_of=None, rotation="none", **extra):
    return {"type": type_, "name": name, "category": category,
            "ports": [{"name": p, "kind": k} for p, k in ports],
            "conducts": [list(g) for g in conducts], "through": [list(g) for g in through],
            "symmetric": [list(g) for g in symmetric], "polarized": polarized, "connector": connector,
            "alias": alias, "mirror_of": mirror_of, "rotation_symmetry": rotation, "status": status, **extra}


_META = {}


def _meta(t):
    """A part's metadata in the parts catalogue (parts.json), read once."""
    if not _META:
        import json as _json
        f = pathlib.Path(__file__).resolve().parents[3] / "code" / "graph" / "parts" / "parts.json"
        _META.update({k: v.get("metadata") or {} for k, v in _json.loads(f.read_text()).items()} if f.exists() else {})
    return _META.get(t) or {}


def _connects(t):  # how the part connects, as codes (breadboard, header-socket, solder…), for the circuit builder
    return _meta(t).get("connect_by") or []


def _takes(t):  # what its sockets take (lead, header-pin, wire-end…)
    return _meta(t).get("takes") or []


def arduino_seed():
    """Verified Arduino entries converted from CircuitQuest's library cards."""
    entries = {}
    for path in sorted(glob.glob(str(CQ / "library" / "parts" / "*.json"))):
        card = json.loads(pathlib.Path(path).read_text())
        cid, sub = card["id"], card.get("subtype", "")
        if cid.startswith("resistor-"):
            cid = "resistor"  # one type; the value is an instance property (R21)
            if cid in entries:
                continue
        pins = list((card.get("pins") or {}).keys())
        kind = {"wire-lead": "lead", "pin": "header-pin", "short-leg": "lead", "lug": "lug"}.get(card.get("leads"), "pin")
        through = [pins[:2]] if len(pins) == 2 and not card.get("connector_only") else []
        if len(pins) == 3 and sub == "potentiometer":
            through = [["GND", "SIG"], ["SIG", "VCC"]]
        if not pins and card.get("pin_domains"):  # boards: header pins from the card's pin domains
            doms = card["pin_domains"]  # a pin can be in two domains (analog and digital): list it once
            pins = list(dict.fromkeys([p for dom in doms.values() for p in dom]
                                      + ["GND.1", "GND.2", "GND.3", "5V", "3.3V", "VIN", "RESET"]))
            kind = "header-socket"
        if not pins and card.get("symmetric_pins"):  # e.g. the DIP switch lists its pins only as symmetric pairs
            pins = [p for group in card["symmetric_pins"] for p in group]
        if not pins:  # CircuitQuest takes these from the Wokwi element: the pinouts data (graph/parts/arduino/pinouts.py)
            from graph.parts.arduino.pinouts import load as _pinouts
            po = _pinouts().get(cid)
            if po:
                pins, kind = po["pins"], {"lead": "lead", "header-pin": "header-pin"}.get(po["kind"], "pin")
        entries[cid] = _entry(
            cid, card.get("display_name", cid), sub or card.get("type", "part"), [(p, kind) for p in pins],
            through=through, symmetric=card.get("symmetric_pins", []), polarized=bool(card.get("polarized")),
            connector=bool(card.get("connector_only")), alias=card.get("pin_aliases"),
            # breadboard placement facts (CircuitQuest PARTS.md): all legs go in together, in pin order, in one row;
            # the part sits across the centre gap
            legs_together=bool(card.get("legs_placed_together")), straddles_gap=bool(card.get("straddles_center_gap")))
    # Cards without explicit pins that the experiment needs.
    entries["arduino-uno"] = _entry("arduino-uno", "Arduino Uno R3", "board",
                                    [(p, "header-socket") for p in UNO_PORTS],
                                    alias={"mode": "prefix", "prefixes": ["GND"]})
    entries["breadboard"] = _entry(
        "breadboard", "Solderless breadboard", "breadboard", [("<column><bank>.<row>", "breadboard-hole")],
        connector=True, alias={"mode": "strip"},
        port_rule="Holes are named '<column><bank>.<row>': column 1-63 (a full breadboard, as in Wokwi; a half board has 1-30), bank 't' (top half, rows a-e) or 'b' "
                  "(bottom half, rows f-j), e.g. '12t.c', '7b.h'. The 5 holes of one column-bank are one strip. "
                  "Power rails: 'tp.<n>', 'tn.<n>', 'bp.<n>', 'bn.<n>' (each rail is one strip).")
    entries["jumper-wire"] = _entry("jumper-wire", "Jumper wire", "wire", [("a", "wire-end"), ("b", "wire-end")],
                                    conducts=[["a", "b"]], connector=True)
    # Modules whose cards have no pin list (Wokwi pin names).
    for mid, name, pins in [("hc-sr04", "HC-SR04 ultrasonic sensor", ["VCC", "TRIG", "ECHO", "GND"]),
                            ("servo", "Hobby servo", ["PWM", "V+", "GND"]),
                            ("dht22", "DHT22 temperature/humidity sensor", ["VCC", "SDA", "NC", "GND"]),
                            ("oled-ssd1306", "SSD1306 OLED (I2C)", ["GND", "VCC", "SCL", "SDA"]),
                            ("neopixel", "NeoPixel (WS2812)", ["VDD", "DOUT", "VSS", "DIN"]),
                            ("ir-receiver", "IR receiver", ["GND", "VCC", "DAT"])]:
        if mid in entries:
            entries[mid]["ports"] = [{"name": p, "kind": "header-pin"} for p in pins]
    entries["jumper-wire-mf"] = _entry("jumper-wire-mf", "Jumper wire, male to female", "wire",
                                       [("a", "wire-end"), ("b", "wire-end")], conducts=[["a", "b"]], connector=True)
    entries["alligator-clip-wire"] = _entry("alligator-clip-wire", "Alligator clip lead", "wire",
                                            [("a", "wire-end"), ("b", "wire-end")], conducts=[["a", "b"]], connector=True)
    entries["led"] = _entry("led", "LED", "led", [("A", "lead"), ("C", "lead")], through=[["A", "C"]], polarized=True)
    entries["pushbutton"] = _entry("pushbutton", "Pushbutton", "button",
                                   [("1.l", "lead"), ("1.r", "lead"), ("2.l", "lead"), ("2.r", "lead")],
                                   legs_together=True, straddles_gap=True,
                                   placement="4 legs, across the centre gap (as CircuitQuest's lessons place it): 1.l and "
                                             "1.r face each other across the gap in one column, 2.l and 2.r in another",
                                   through=[["1", "2"]], symmetric=[["1", "2"]],
                                   alias={"mode": "prefix", "prefixes": ["1", "2"]},
                                   note="4 legs in two pairs: 1.l and 1.r are ALWAYS joined inside (side 1), 2.l and 2.r "
                                        "are ALWAYS joined (side 2); pressing joins side 1 to side 2. Wire the input pin to one "
                                        "side and the supply to the OTHER side; a pull-down/pull-up resistor goes on the SAME "
                                        "side as the input pin.")
    return entries


# --- LEGO: imported on demand from the LDraw parts library ----------------------
DIMS = re.compile(r"^(Brick|Plate|Tile)\s+(\d+)\s*x\s*(\d+)\s*$", re.I)


def brick_dims(description):
    """(kind, w, l) for plain bricks/plates/tiles, else None."""
    m = DIMS.match(re.sub(r"\s+", " ", description).strip())
    return (m.group(1).lower(), int(m.group(2)), int(m.group(3))) if m else None


def lego_entry(part_file, description):
    """A catalogue entry imported from the LDraw library (no model involved)."""
    num = part_file[:-4] if part_file.endswith(".dat") else part_file
    dims = brick_dims(description)
    ports = []
    if dims:
        kind, w, l = dims
        if kind != "tile":
            ports += [(f"stud.{i}.{j}", "stud") for i in range(1, w + 1) for j in range(1, l + 1)]
        ports += [(f"anti.{i}.{j}", "anti-stud") for i in range(1, w + 1) for j in range(1, l + 1)]
    rotation = "none"
    if dims:
        rotation = "90" if dims[1] == dims[2] else "180"
    mirror = None
    if re.search(r"\b(Left|Right)\b", description):
        mirror = "(LDraw: see the Left/Right twin)"
    return _entry(f"lego-{num}", description, dims[0] if dims else "lego-part", ports,
                  status="imported", rotation=rotation, mirror_of=mirror)


def _placement(e):
    """'legs together in one row, in order GND, SIG, VCC; across the centre gap'."""
    out = []
    if e.get("legs_together"):
        order = ", ".join(p["name"] for p in e["ports"][:16])
        out.append("all legs in neighbouring holes of one row" + (f", in order {order}" if order else ""))
    if e.get("straddles_gap"):
        out.append("sits across the centre gap, half its legs on each half, facing each other in the same columns")
    return e.get("placement") or "; ".join(out)


def _facts(el):
    """Electrical facts as short text: 'supply 3.3-6.0 V; logic 5 V; LED forward 2.0 V, 20 mA, needs a series resistor'."""
    out = []
    if el.get("supply_v_min") is not None or el.get("supply_v_max") is not None:
        out.append(f"supply {el.get('supply_v_min', '?')}-{el.get('supply_v_max', '?')} V"
                   + (f" on {'/'.join(el['power_pins'])}" if el.get("power_pins") else ""))
    if el.get("logic_v"):
        out.append(f"logic {el['logic_v']} V" + (" (NOT 5 V tolerant)" if el.get("five_v_tolerant") is False else ""))
    if el.get("max_pin_current_ma"):
        out.append(f"max {el['max_pin_current_ma']} mA per I/O pin")
    if el.get("forward_v"):
        out.append(f"forward {el['forward_v']} V")
    if el.get("current_ma"):
        out.append(f"about {el['current_ma']} mA")
    if el.get("needs_series_resistor"):
        out.append("needs a series resistor")
    return "; ".join(out)


class Catalogue:
    def __init__(self, entries=None):
        self.entries = copy.deepcopy(entries or {})
        self.created = []  # types added on demand during this run

    def has(self, type_):
        return type_ in self.entries

    def get(self, type_):
        return self.entries.get(type_)

    def add_drafts(self, drafts):
        """Add model-drafted entries for types not already present (store on demand).
        A later draft of an existing *unverified* type adds the ports the first draft missed."""
        added = []
        for d in drafts:
            d = dict(d)
            have = self.entries.get(d["type"])
            if have:
                if have.get("status") == "unverified":
                    names = {p["name"] for p in have["ports"]}
                    have["ports"] += [p for p in d["ports"] if p["name"] not in names]
                continue
            d.update(alias=None, status="unverified")
            self.entries[d["type"]] = d
            added.append(d["type"])
        self.created += added
        return added

    def prompt_text(self, types=None, electrical=False, placement=False):
        """Compact one-line-per-type listing for the prompt. electrical=True adds each card's electrical facts (v5);
        placement=True its breadboard placement facts (v6)."""
        lines = []
        for t in sorted(types or self.entries):
            e = self.entries[t]
            ports = e.get("port_rule") or ", ".join(p["name"] for p in e["ports"][:40])
            if len(e["ports"]) > 40:
                ports += f", … ({len(e['ports'])} ports)"
            flags = [f for f, on in (("polarized", e["polarized"]), ("connector", e["connector"])) if on]
            if e["symmetric"]:
                flags.append("symmetric " + "/".join("=".join(g) for g in e["symmetric"]))
            lines.append(f"- {t} | {e['name']} | ports: {ports}" + (f" | {', '.join(flags)}" if flags else "")
                         + (f" | NOTE: {e['note']}" if e.get("note") else "")
                         + (f" | ELECTRICAL: {_facts(e['electrical'])}" if electrical and e.get("electrical") else "")
                         + (f" | BREADBOARD: {_placement(e)}" if placement and (e.get("legs_together") or e.get("straddles_gap")) else "")
                         + (f" | CONNECTS: {', '.join(w['way'] for w in _connects(t))}" if _connects(t) else "")
                         + (f" | TAKES: {', '.join(w['what'] for w in _takes(t))}" if _takes(t) else ""))
        return "\n".join(lines)

    def to_json(self):
        return self.entries


# ---- parts.json: building it from the card stores, reading it ------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[3]


PATH = ROOT / "code" / "graph" / "parts" / "parts.json"


STORES = {"lego": "code/graph/parts/lego/cards_lego.json", "arduino": "code/graph/parts/arduino/cards_electronics.json"}




# Part-level substitutes: what a copy may differ in and still be right (instance properties, not other parts).
# A resistor's allowed values depend on what it does in the circuit, so the lesson works them out (substitutes.py)
SUBSTITUTES = {
    "led": {"free": ["colour"], "why": "any colour lights the same way (forward voltage differs a little)"},
    "jumper-wire": {"free": ["colour", "length"], "why": "a wire's colour and length do not change the circuit"},
    "resistor": {"value": "by role", "why": "worked out per lesson: a resistor in series with an LED may take any "
                                            "value that keeps its current between about 5 and 20 mA"},
    "lego": {"free": ["colour"], "why": "a colour swap builds the same shape (AR check accepts it)"},
}


def load(path=PATH):
    return json.loads(path.read_text()) if path.exists() else {}


def swaps(part, port, parts=None):
    """The ports this one can stand in for (and that can stand in for it), from the part's stored groups:
    swaps("breadboard", "12t.c") -> ["12t.a", "12t.b", "12t.d", "12t.e"]. Worked out on read, not stored per port."""
    parts = parts or load()
    groups = ((parts.get(part) or {}).get("metadata") or {}).get("interchangeable") or []
    return sorted({x for g in groups if port in g.get("ports", []) for x in g["ports"] if x != port})


def save(parts, path=PATH):
    path.write_text(json.dumps(dict(sorted(parts.items())), indent=1))


def of_domain(parts, domain):
    return {k: v for k, v in parts.items() if v["metadata"]["domain"] == domain}


def fits(card, examples):
    """Every port kind of the part -> what it can go into or onto (joins.FITS, by code, not drafted): the other port's
    kind, how they join, what holds them, how it is undone, and up to four catalogue parts that have that port."""
    from graph import lesson_store
    out = {}
    for k in sorted({p["kind"] for p in card.get("ports", [])}):
        rows = [{"with": o, "method": m, "holds_by": h, "reversible": r,
                 "examples": [x for x in examples.get(o, []) if o != "wire-end" or  # a leg pushes into a female end
                              any(w in x for w in ("alligator", "female", "clip"))][:4]}
                for o, m, h, r in lesson_store.fits_into(k)]
        if rows:
            out[k] = rows
    return out


WAYS = {"breadboard-hole": ("breadboard", "on a breadboard (no solder)"),
        "header-socket": ("header-socket", "into a header socket (on a board)"),
        "wire-end": ("female-jumper", "with a female jumper wire or a clip"),
        "header-pin": ("onto-header-pin", "pushed onto a header pin"),
        "screw": ("screw-terminal", "in a screw terminal (with a screwdriver)"),
        "pad": ("solder", "soldered (to a pad, a perfboard or a wire)")}


TAKES = {"lead": "a part's leg (resistor, LED…)", "pin": "a module's pin", "header-pin": "a header pin",
         "wire-end": "a male jumper wire", "lug": "a lug"}


TOOL = {"screw-terminal": "screwdriver", "solder": "soldering iron"}


def connect_by(fits_):
    """From `fits`, as data: how the part connects (its legs, pins or wire ends go into or onto something; a leg or
    pin can always be soldered too) and what its sockets, holes or terminals take.
    {"connect_by": [{way, tool, text}], "takes": [{what, text}]}, from no tools to tools."""
    from graph import lesson_store
    by, takes = {}, {}
    for kind_, rows in fits_.items():
        if kind_ in lesson_store.FITS:  # this port goes into or onto something
            for r in rows:
                if r["with"] in WAYS:
                    by.setdefault(r["with"], WAYS[r["with"]])
            by.setdefault("pad", WAYS["pad"])
        else:  # things go into this port
            for r in rows:
                if r["with"] in TAKES:
                    takes.setdefault(r["with"], TAKES[r["with"]])
    order = list(WAYS)
    return {"connect_by": [{"way": WAYS[k][0], "tool": TOOL.get(WAYS[k][0]), "text": WAYS[k][1]}
                           for k in sorted(by, key=order.index)],
            "takes": [{"what": k, "text": v} for k, v in takes.items()]}


def strips(card):
    """A breadboard's swap groups, written out: each column-bank's 5 holes ('12t.a'…'12t.e', '12b.f'…'12b.j') and
    each power rail ('tp.1'…'tp.63'). Columns and rail holes run 1-63 (a full breadboard, as the lessons use)."""
    out = []
    for c in range(1, 64):
        out.append({"kind": "strip", "name": f"{c}t", "ports": [f"{c}t.{r}" for r in "abcde"],
                    "why": "one metal strip: the same connection"})
        out.append({"kind": "strip", "name": f"{c}b", "ports": [f"{c}b.{r}" for r in "fghij"],
                    "why": "one metal strip: the same connection"})
    for rail, name in (("tp", "top +"), ("tn", "top −"), ("bp", "bottom +"), ("bn", "bottom −")):
        out.append({"kind": "rail", "name": rail, "ports": [f"{rail}.{n}" for n in range(1, 64)],
                    "why": f"the {name} power rail: one connection"})
    return out


def interchangeable(card):
    """Ports that can stand in for each other, written out as groups [{kind, ports, why}], by code:
      not-polarized   the two legs of a part that is not polarized (a resistor's 1 and 2)
      card-symmetric  groups the card marks as interchangeable (a pushbutton's sides)
      same-pin        pins marked the same (the Uno's GND.1, GND.2, GND.3)
      joined-inside   ports joined inside the part (a wire's two ends)
      strip, rail     a breadboard's 5-hole strips and its power rails"""
    ports = card.get("ports", [])
    ib = card.get("intrinsic_behaviour") or {}
    out = []
    legs = [p["id"] for p in ports if p["kind"] in ("lead", "pin")]
    if len(legs) == 2 and not ib.get("is_polarized"):
        out.append({"kind": "not-polarized", "ports": legs, "why": "not polarized: either leg in either place"})
    for g in ib.get("symmetric_port_groups") or []:
        if sorted(g) != sorted(legs):
            out.append({"kind": "card-symmetric", "ports": list(g), "why": "the card marks them as interchangeable"})
    same = {}
    for p in ports:
        if p.get("same_as"):
            same.setdefault(p["same_as"], []).append(p["id"])
    for name, ids in same.items():
        if len(ids) > 1:
            out.append({"kind": "same-pin", "name": name, "ports": ids, "why": f"all {name}: any one can be used"})
    for g in ib.get("internal_conducts") or []:
        if len(g) > 1:
            out.append({"kind": "joined-inside", "ports": list(g), "why": "joined inside the part: either one either way"})
    if any("<" in p["id"] for p in ports) and "strip" in (card.get("port_rule") or ""):
        out += strips(card)
    return out


SAME = ("strip", "rail", "same-pin")                         # groups that are one connection: any port in it will do


EITHER_WAY = ("not-polarized", "card-symmetric", "joined-inside")  # groups whose ports swap: either way round


def connection(card, port):
    """The connection a port is part of, from the card's stored groups: (kind, name) for a strip, a rail or a
    same-pin group ('strip', '12t'), or None when the port stands alone."""
    for g in ((card or {}).get("metadata") or {}).get("interchangeable") or []:
        if g.get("kind") in SAME and port in g.get("ports", []):
            return g["kind"], g.get("name") or g["ports"][0]
    return None


def either_way(card):
    """The card's groups of ports that may swap (a resistor's legs, a wire's ends): [[port, ...]]."""
    return [list(g["ports"]) for g in ((card or {}).get("metadata") or {}).get("interchangeable") or []
            if g.get("kind") in EITHER_WAY]


def build(path=PATH):
    """parts.json from the card stores: each card as it is (its own `domain` field moves into metadata), with the
    metadata block it already had here. Returns {domain: count}."""
    from graph.filelock import locked
    with locked(path):
        return _build(path)


def _build(path):
    parts = load(path)
    examples = collections.defaultdict(list)  # a port kind -> the electronics parts that have it
    for t, card in sorted(json.loads((ROOT / STORES["arduino"]).read_text()).items()):
        for k in sorted({p["kind"] for p in card.get("ports", [])}):
            if t not in examples[k]:
                examples[k].append(t)
    out, counts = {}, collections.Counter()
    for domain, rel in STORES.items():
        for t, card in json.loads((ROOT / rel).read_text()).items():
            if t in out:
                raise ValueError(f"{t} is in two card stores")
            meta = dict((parts.get(t) or {}).get("metadata") or {})
            meta.pop("part_type_id", None)
            meta.update({"domain": domain, "source_catalogue": rel,
                         "card_made_by": (card.get("source") or {}).get("made_by")})
            if t in SUBSTITUTES or domain == "lego":
                meta["substitutes"] = SUBSTITUTES.get(t) or SUBSTITUTES["lego"]
            entry = json.loads(json.dumps({**{k: v for k, v in card.items() if k != "domain"}, "metadata": meta}))
            from graph.parts.part_metadata import normalize  # codes, not free text (stored metadata from before is converted)
            entry["metadata"] = normalize(entry["metadata"])
            if domain == "arduino":  # a copy: the card store is not changed
                pins.annotate(entry, pins.cq_card(t))
                entry["metadata"]["fits"] = fits(entry, examples)  # by code, after the pin facts (same_as)
                entry["metadata"]["interchangeable"] = interchangeable(entry)
                entry["metadata"].update(connect_by(entry["metadata"]["fits"]))
            out[t] = entry
            counts[domain] += 1
    save(out, path)
    return dict(counts)


def stats(parts):
    rows = {}
    for domain in STORES:
        d = of_domain(parts, domain)
        drafted = [v for v in d.values() if v["metadata"].get("description")]
        rows[domain] = {"parts": len(d), "with_metadata": len(drafted),
                        "with_joins": sum(1 for v in drafted if v["metadata"].get("joins")),
                        "checks_failed": sum(1 for v in drafted if v["metadata"].get("checks_failed"))}
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "stats"])
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(f"{PATH.relative_to(ROOT)}: {build()}")
    for domain, row in stats(load()).items():
        print(f"  {domain:8} {row}")


if __name__ == "__main__":
    main()
