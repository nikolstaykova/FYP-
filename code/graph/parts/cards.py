"""The part card stores: every part's card, LEGO and Arduino.

What it is   CardStore: the cards of one domain in one JSON file (parts/arduino/cards_electronics.json,
             parts/lego/cards_lego.json), with a quarantine file for cards that failed the gate; safe to share
             between threads; get() gives the graph engine's form of a card, with the notes, aliases and electrical
             facts kept beside the Arduino cards. store(domain) opens one store per process. Also: ports a 3D
             model's joins use added to LEGO cards (add_used_ports), and LEGO cards made in bulk (lego_cards) or by
             code for a plain brick (lego_card_code).
Used for     every lesson's parts: a part's card is read here, and a new part's card is stored here.
Where        arduino/ (circuit_graph, circuit_lesson, part_review), lego_booklet/pdf_lesson.py, lesson_store.py,
             parts/ (mcp_server, naming, part_catalogue). Making a card is parts/ingest.py's job.
"""
import collections
import json
import math
import pathlib
import re
import sys
import threading
from dataclasses import dataclass
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from graph.parts import part_catalogue

ALIASES = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "arduino" / "aliases.json").read_text()).items()
           if not k.startswith("_")}
NOTES = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "arduino" / "card_notes.json").read_text()).items()
         if not k.startswith("_")}
ELECTRICAL = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "arduino" / "electrical.json").read_text()).items()
              if not k.startswith("_")}
POWER_PIN = ("VCC", "VDD", "V+", "VIN", "3V3", "3.3V", "5V", "+5V", "+")


class CardStore:
    def __init__(self, path, seed=None, seed_domain="electronics"):
        self.path = pathlib.Path(path)
        self.lock = threading.RLock()
        self.cards = {}  # part_type_id -> Layer 0 card
        for t, e in (seed or {}).items():
            card, err = gate(from_engine(e, seed_domain, {"platform": "circuitquest", "made_by": "verified"}))
            if card:
                self.cards[t] = card
        self._index = None
        if self.path.exists():
            for t, c in json.loads(self.path.read_text()).items():
                if "part_type_id" not in c:  # an older store in engine form: convert once
                    made = (c.get("source") or {}).get("made_by", "claude")
                    c = from_engine(c, "lego" if t.startswith("lego-") else "electronics",
                                           {**(c.get("source") or {}), "platform": (c.get("source") or {}).get("platform", "unknown"),
                                            "made_by": made})
                card, err = gate(c)
                if card:
                    seeded = self.cards.get(t)
                    if seeded:  # facts the verified seed has and an older stored copy lacks (placement, notes)
                        for k in ("legs_together", "straddles_gap", "note", "port_alias_rule"):
                            if seeded.get(k) and not card.get(k):
                                card[k] = seeded[k]
                    self.cards[t] = card

        pass  # an id merged into another (redirects.json): not a card of its own
        for t in [t for t in self.cards if t in REDIRECTS]:
            self.cards.pop(t)
        for t, names in ALIASES.items():  # other names people use, from aliases.json (data)
            if t in self.cards:
                self.cards[t]["aliases"] = sorted(set(self.cards[t].get("aliases", [])) | set(names))
        for t, note in NOTES.items():  # wiring facts the source lacked, from card_notes.json (data)
            if t in self.cards and not self.cards[t].get("note"):
                self.cards[t]["note"] = note
        for t, card in self.cards.items():  # electrical facts: shop data first, then electrical.json (data)
            facts = {**ELECTRICAL.get(t, {}), **{k: v for k, v in (card.get("electrical") or {}).items() if v not in (None, [])}}
            if not facts.get("power_pins") and card["domain"] == "electronics" and card["category"] != "board":
                pins = [p["id"] for p in card["ports"] if p["id"].upper() in POWER_PIN]
                if pins:
                    facts["power_pins"] = pins
            if facts:
                card["electrical"] = facts

    def search(self, query, limit=5):
        """Free-text search over the cards (search.py, MongoDB $text style): [Hit(id, score, coverage)]."""
        with self.lock:
            if self._index is None:
                self._index = TextIndex({"part_type_id": 10, "aliases": 8, "display_name": 5, "category": 2})
                for t, c in self.cards.items():
                    self._index.add(t, c)
            return self._index.search(query, limit)

    def get(self, type_):
        c = self.cards.get(type_) or self.cards.get(resolve(type_))
        return to_engine(c) if c else None

    def put_layer0(self, cards):
        """Store cards. Several processes may share the file (parallel builds, their lookup_part servers): under a
        file lock, re-read it, add ours, write it back, so no process's cards are lost."""
        import fcntl
        with self.lock:
            self.cards.update({c["part_type_id"]: c for c in cards})
            self._index = None  # rebuilt on the next search
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path.with_suffix(".lock"), "w") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                if self.path.exists():
                    for t, c in json.loads(self.path.read_text()).items():
                        if t not in self.cards and "part_type_id" in c:
                            self.cards[t] = c
                self._write(self.path, self.cards)
                fcntl.flock(lk, fcntl.LOCK_UN)

    def refresh(self):
        """Pick up cards other processes stored since we loaded the file."""
        if self.path.exists():
            with self.lock:
                for t, c in json.loads(self.path.read_text()).items():
                    if t not in self.cards and "part_type_id" in c:
                        self.cards[t] = c
                        self._index = None

    def put(self, engine_entries, domain="lego"):
        """Engine-form entries (catalogue._entry) through the gate into the store."""
        for e in engine_entries:
            card, err = gate(from_engine(e, domain, e.get("source") or {"platform": "unknown"}))
            self.put_layer0([card]) if card else self.quarantine(e, err)

    def quarantine(self, card, reason):
        with self.lock:
            q = self.path.with_name(self.path.stem + "_quarantine.json")
            rows = json.loads(q.read_text()) if q.exists() else []
            rows.append({"card": card, "reason": reason})
            self._write(q, rows)

    @staticmethod
    def _write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(path)

    def index_text(self):
        """One line per card for a matching prompt: id | name | category."""
        return "\n".join(f"- {t} | {c['display_name']} | {c['category']}" for t, c in sorted(self.cards.items()))


# --- Entry points used by v3 ---------------------------------------------------------------
def ingest(store, wanted_type, label, query, log=None):
    from graph.parts import ingest as ing  # here: ingest uses this module's card form
    return ing.ingest_part(query, "electronics", store, wanted_id=wanted_type, label=label)


BUILDING = ("brick", "plate", "slope", "tile", "bracket", "wedge", "hinge", "panel", "container", "windscreen", "cone",
            "wheel arch", "round")


# a port name the 3D model's joins use -> its kind (ldraw_studs.connections, ldraw_graph's clip, bar and pin joins)
USED_KINDS = {"stud": "stud", "anti": "anti-stud", "bar": "bar", "clip": "clip", "pin": "pin", "hole": "pin-hole",
              "axle": "axle", "hinge": "hinge"}


def add_used_ports(store, physical, log=print):
    """LEGO cards Claude drafted (or code made from the LDraw library alone) get the studs and anti-studs a set's 3D model joins them by and they lack: the joins
    are found from the parts' real shapes (ldraw_studs.connections), so the shape shows the port is there: on any card
    (one made by code from a name alone can miss them too), studs, anti-studs, bars, clips, pins and holes. Ports are
    only added, never removed. Returns {part: [ports added]}."""
    import json as _json
    cards = _json.loads(store.path.read_text())
    kind_of = {n["id"]: n.get("type") for n in physical.get("nodes", [])}
    added = {}
    for e in physical.get("edges", []):
        for end, port in ((e.get("u"), e.get("u_port")), (e.get("v"), e.get("v_port"))):
            t = kind_of.get(end)
            if t and t not in cards:  # a printed piece: its card is its design's (3626bp85 -> 3626b)
                import re as _re
                m = _re.match(r"^(lego-\d+[a-z]?)p[a-z0-9]+$", t)
                t = m.group(1) if m else t
            c = cards.get(t)
            if not c or not port:
                continue
            kind = USED_KINDS.get(port.split(".")[0])
            if kind and port not in {p["id"] for p in c["ports"]}:
                c["ports"].append({"id": port, "kind": kind, "gender": None, "voltage_rating": None, "aliases": []})
                added.setdefault(t, []).append(port)
    for t in added:
        cards[t]["note"] = ((cards[t].get("note") or "") + " Ports the set's 3D model joins it by added by code.").strip()
    if added:
        store.path.write_text(_json.dumps(cards, indent=1))
        log(f"  ports added from the 3D model's joins: {added}")
    return added


def lego_cards(store, designs, batch_size=40, workers=4, log=print):
    from graph.parts import ingest as ing  # here: ingest uses this module's card form
    return ing.ingest_many(sorted(designs), "lego", store, batch_size=batch_size, workers=workers, log=log)


def lego_card_code(part_num, name):
    """Plain brick/plate/tile from its name alone, as an engine entry (no model call)."""
    from graph.parts.lego import inventory
    card = inventory.Rebrickable().deterministic({"part_num": part_num, "name": name, "url": ""})
    return to_engine(card) if card else None


LEGO_STORE = pathlib.Path(__file__).resolve().parents[3] / "code" / "graph" / "parts" / "lego" / "cards_lego.json"
_stores = {}


def store(domain, run_dir=None, path=None):
    """One card store per domain per process. Electronics starts from the verified seed; ingested cards are written
    to `path` (the shared store) or else to the run folder."""
    if domain not in _stores:
        if domain == "lego":
            _stores[domain] = CardStore(path or LEGO_STORE)
        else:
            _stores[domain] = CardStore(path or (run_dir / "cards_electronics.json"), seed=part_catalogue.arduino_seed())
    return _stores[domain]


# ---- a card's form, and the gate every card passes -----------------------------------------------------------
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
                              description="Global id by the naming rules (graph/parts/naming.py): lego-3001, arduino-uno, dht11")
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
    return part_catalogue._entry(card["part_type_id"], card["display_name"], card["category"], [(p["id"], p["kind"]) for p in card["ports"]],
                      conducts=b["internal_conducts"], through=b["internal_pass_through"], symmetric=b["symmetric_port_groups"],
                      polarized=b["is_polarized"], connector=b["is_connector_only"], alias=card.get("port_alias_rule"),
                      status=status, mirror_of=b.get("mirror_twin_id"), rotation=rot, source=card["source"], **extra)


# ---- free-text search over cards -----------------------------------------------------------------------------
STOP = set("""a an and are as at be but by for from has have in into is it its of on or that the this to was were
will with x pcs pc piece pieces generic optional any other e.g eg etc board module kit""".split())


def stem(w):
    """A small English stemmer (Porter step 1 style): plurals and -ing/-ed. Numbers and model codes are kept."""
    if re.search(r"\d", w) or len(w) <= 3:
        return w
    for suf, rep in (("sses", "ss"), ("ies", "y"), ("ing", ""), ("ed", ""), ("es", "e"), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[: len(w) - len(suf)] + rep
    return w


def tokens(text):
    """Lowercase, split on anything not a letter/digit (hc-sr04 -> hc, sr04, hcsr04), drop stop words, stem."""
    out = []
    for raw in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower()):
        parts = raw.split("-")
        if len(parts) > 1 and any(re.search(r"\d", p) for p in parts):
            out.append("".join(parts))  # model codes are searched joined too: hc-sr04 -> hcsr04
        out += parts
    return [stem(t) for t in out if t not in STOP]


@dataclass
class Hit:
    id: str
    score: float
    coverage: float


class TextIndex:
    def __init__(self, weights):
        self.weights = weights
        self.docs = {}  # id -> {field: Counter(term)}
        self.text = {}  # id -> lowercased text of all fields, for phrase checks

    def add(self, doc_id, doc):
        fields = {}
        for f in self.weights:
            v = doc.get(f)
            v = " ".join(v) if isinstance(v, (list, tuple)) else (v or "")
            fields[f] = collections.Counter(tokens(v.replace("-", " ") + " " + v))
        self.docs[doc_id] = fields
        self.text[doc_id] = " ".join(" ".join(doc.get(f)) if isinstance(doc.get(f), list) else str(doc.get(f) or "")
                                     for f in self.weights).lower()

    @staticmethod
    def parse(query):
        phrases = [p.lower() for p in re.findall(r'"([^"]+)"', query)]
        rest = re.sub(r'"[^"]+"', " ", query)
        negs = {stem(t) for t in re.findall(r"(?:^|\s)-([a-z0-9]+)", rest.lower())}
        rest = re.sub(r"(?:^|\s)-[a-z0-9]+", " ", rest)
        terms = list(dict.fromkeys(tokens(rest + " " + " ".join(phrases))))
        return terms, phrases, negs

    def search(self, query, limit=5):
        terms, phrases, negs = self.parse(query)
        if not terms:
            return []
        total_w = sum(self.weights.values())
        hits = []
        for doc_id, fields in self.docs.items():
            if any(t in c for c in fields.values() for t in negs):
                continue
            if any(p not in self.text[doc_id] for p in phrases):
                continue
            score, found = 0.0, set()
            for f, counts in fields.items():
                n = sum(counts.values()) or 1
                for t in terms:
                    if counts[t]:
                        found.add(t)
                        # weight × frequency coefficient: more repeats help less, longer fields dilute
                        score += self.weights[f] * (1 + math.log(counts[t])) * (0.5 + 0.5 / math.sqrt(n))
            if found:
                cov = len(found) / len(terms)
                hits.append(Hit(doc_id, round(score / total_w, 4), round(cov, 3)))
        return sorted(hits, key=lambda h: (-h.score, -h.coverage))[:limit]


# ---- one part under two ids, made one ------------------------------------------------------------------------
HERE = pathlib.Path(__file__).parent
REDIRECTS_PATH = HERE / "redirects.json"
ROOT = HERE.parents[2]
CARDS = ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json"


def redirects():
    if not REDIRECTS_PATH.exists():
        return {}
    return {k: v for k, v in json.loads(REDIRECTS_PATH.read_text()).items() if not k.startswith("_")}


REDIRECTS = redirects()


def resolve(type_id, table=None):
    table = REDIRECTS if table is None else table
    seen = set()
    while type_id in table and type_id not in seen:
        seen.add(type_id)
        type_id = table[type_id]
    return type_id


def _norm(port_id):
    return re.sub(r"[^A-Z0-9]", "", port_id.upper())  # A.1 and A1, BAT_1 and BAT1


def merge(keep, drop, cards_path=CARDS, name=None, log=print):
    """Merge the cards `drop` into `keep` (which may be one of them, or an id none of them has yet). Returns the
    kept card. Writes the card store, parts.json's metadata and redirects.json; part_catalogue.build() is the caller's."""
    from graph.parts import part_catalogue
    cards = json.loads(cards_path.read_text())
    group = [t for t in [keep, *drop] if t in cards]
    richest = max(group, key=lambda t: (len(cards[t]["ports"]), t == keep))
    card = json.loads(json.dumps(cards[richest]))
    have = {_norm(p["id"]) for p in card["ports"]} | {_norm(a) for p in card["ports"] for a in p.get("aliases", [])}
    for t in group:  # a port only a dropped card had (a graph may name it): kept, as an alias where it is one
        for p in cards[t]["ports"]:
            if _norm(p["id"]) in have:
                continue
            twin = next((q for q in card["ports"] if _norm(q["id"]).rstrip("T") == _norm(p["id"]).rstrip("T")), None)
            if twin:  # BAT and BATT
                twin.setdefault("aliases", []).append(p["id"])
                log(f"  {t}:{p['id']} -> alias of {twin['id']}")
            else:
                card["ports"].append(p)
                log(f"  {t}:{p['id']} added")
            have.add(_norm(p["id"]))
    elec = {}
    for t in sorted(group, key=lambda t: len(json.dumps(cards[t].get("electrical") or {}))):
        elec.update({k: v for k, v in (cards[t].get("electrical") or {}).items() if v not in (None, [])})
    card["electrical"] = elec or card.get("electrical")
    card["aliases"] = sorted({a for t in group for a in cards[t].get("aliases", [])})
    card["part_type_id"] = keep
    if name:
        card["display_name"] = name
    parts = part_catalogue.load()
    meta = (parts.get(richest) or {}).get("metadata") or (parts.get(keep) or {}).get("metadata")
    for t in group:
        cards.pop(t, None)
        if t != keep:
            parts.pop(t, None)
    cards[keep] = card
    if meta:
        parts[keep] = {**card, "metadata": {**meta, "status": "drafted"}}  # rechecked against the merged card
    cards_path.write_text(json.dumps(dict(sorted(cards.items())), indent=1))
    part_catalogue.save(parts)
    table = json.loads(REDIRECTS_PATH.read_text()) if REDIRECTS_PATH.exists() else {
        "_doc": "Ids a card no longer has -> the id it is now (graph/parts/cards.py). Graphs from earlier runs "
                "keep the old id; CardStore.get, lesson_store.definition and the naming rules follow these."}
    for t in drop:
        if t != keep:
            table[t] = keep
    for k, v in list(table.items()):  # no chains: an id merged twice points at the last one
        if not k.startswith("_"):
            table[k] = resolve(v, {a: b for a, b in table.items() if not a.startswith("_")})
    REDIRECTS_PATH.write_text(json.dumps(table, indent=1))
    REDIRECTS.clear()
    REDIRECTS.update(redirects())
    log(f"{keep}: {len(card['ports'])} ports from {richest}; redirects {[t for t in drop if t != keep]}")
    return card



if __name__ == "__main__":
    merge(sys.argv[1], sys.argv[2:])
