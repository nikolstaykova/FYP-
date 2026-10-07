"""The Layer 0 card store, and the parts-list step that uses it.

  CardStore      Layer 0 cards in one JSON file (+ a quarantine file for cards that failed the gate), safe to
                 share between worker threads. get() hands the graph engine its working form.
  match_parts    electronics: Claude lists a tutorial's parts and matches each to a stored card (v3 step)

Making cards is ingest.py's job; `ingest` and `lego_cards` here are the entry points v3 calls.
"""
import json
import pathlib
import threading
from typing import List, Optional

from pydantic import BaseModel, Field

from .. import catalogue as cat
from . import ingest as ing
from . import schema
from .search import TextIndex

ALIASES = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "aliases.json").read_text()).items()
           if not k.startswith("_")}
NOTES = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "card_notes.json").read_text()).items()
         if not k.startswith("_")}
ELECTRICAL = {k: v for k, v in json.loads((pathlib.Path(__file__).parent / "electrical.json").read_text()).items()
              if not k.startswith("_")}
POWER_PIN = ("VCC", "VDD", "V+", "VIN", "3V3", "3.3V", "5V", "+5V", "+")


class CardStore:
    def __init__(self, path, seed=None, seed_domain="electronics"):
        self.path = pathlib.Path(path)
        self.lock = threading.RLock()
        self.cards = {}  # part_type_id -> Layer 0 card
        for t, e in (seed or {}).items():
            card, err = schema.gate(schema.from_engine(e, seed_domain, {"platform": "circuitquest", "made_by": "verified"}))
            if card:
                self.cards[t] = card
        self._index = None
        if self.path.exists():
            for t, c in json.loads(self.path.read_text()).items():
                if "part_type_id" not in c:  # an older store in engine form: convert once
                    made = (c.get("source") or {}).get("made_by", "claude")
                    c = schema.from_engine(c, "lego" if t.startswith("lego-") else "electronics",
                                           {**(c.get("source") or {}), "platform": (c.get("source") or {}).get("platform", "unknown"),
                                            "made_by": made})
                card, err = schema.gate(c)
                if card:
                    seeded = self.cards.get(t)
                    if seeded:  # facts the verified seed has and an older stored copy lacks (placement, notes)
                        for k in ("legs_together", "straddles_gap", "note", "port_alias_rule"):
                            if seeded.get(k) and not card.get(k):
                                card[k] = seeded[k]
                    self.cards[t] = card

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
        c = self.cards.get(type_)
        return schema.to_engine(c) if c else None

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
            card, err = schema.gate(schema.from_engine(e, domain, e.get("source") or {"platform": "unknown"}))
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
    return ing.ingest_part(query, "electronics", store, wanted_id=wanted_type, label=label)


def lego_cards(store, designs, batch_size=40, workers=4, log=print):
    return ing.ingest_many(sorted(designs), "lego", store, batch_size=batch_size, workers=workers, log=log)


def lego_card_code(part_num, name):
    """Plain brick/plate/tile from its name alone, as an engine entry (no model call)."""
    from . import sources
    card = sources.Rebrickable().deterministic({"part_num": part_num, "name": name, "url": ""})
    return schema.to_engine(card) if card else None


# --- Electronics: the tutorial's parts list, matched to the store ---------------------------
class PartLine(BaseModel):
    label: str = Field(description="The part as the tutorial names it")
    quantity: int
    catalogue_type: Optional[str] = Field(description="Catalogue type id that is this part, or null if none fits")
    new_type: Optional[str] = Field(description="If catalogue_type is null: the type id this part should get, by the naming rules")
    search_query: Optional[str] = Field(description="If catalogue_type is null: a short shop search query (product name, chip)")
    category: str


class PartsList(BaseModel):
    parts: List[PartLine] = Field(description="Every physical part the tutorial uses, wires and breadboard included")


def match_parts(manual_text, store, model="sonnet", effort="low"):
    """Claude reads the tutorial's parts and matches each to a stored card. Returns (parts, stats)."""
    from ..extract import claude_json
    system = ("You list the physical parts an electronics tutorial uses and match each to the part catalogue.\n"
              "Use a catalogue type whenever one is the same kind of part (any resistor value -> resistor, any LED colour "
              "-> led). Only propose a new type for a part the catalogue really lacks.\n\n" +
              ing.NAMING + "\n\nCATALOGUE:\n" + store.index_text())
    out, stats = claude_json(system, [{"type": "text", "text": "TUTORIAL:\n" + manual_text[:30000]}], PartsList,
                             model=model, effort=effort)
    return out["parts"], stats
