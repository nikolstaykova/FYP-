"""LEGO parts first: which pieces a set has, before any graph is built.

  RebrickableDump.set_parts(set_num)   official inventory from the local copy of Rebrickable's daily dump
  booklet_parts(pdf)                   fallback when Rebrickable lacks the set: the booklet's own parts page
                                       (Element IDs read by code), else Claude reads the parts boxes

Both return [{part_num, color_id, color, quantity, name, element_id}] with non-spare pieces only.
"""
import collections
import csv
import gzip
import pathlib
import threading
from typing import List, Optional

from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[2]
DUMP = ROOT / "research" / "raw" / "rebrickable"


def _rows(name):
    with gzip.open(DUMP / f"{name}.csv.gz", "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f)


class RebrickableDump:
    """Rebrickable's CSV dump loaded once per process (tables read lazily, shared by threads)."""
    _lock = threading.Lock()
    _tables = None

    @classmethod
    def tables(cls):
        with cls._lock:
            if cls._tables is None:
                parts = {r["part_num"]: r for r in _rows("parts")}
                cats = {r["id"]: r["name"] for r in _rows("part_categories")}
                colors = {r["id"]: r["name"] for r in _rows("colors")}
                inv = {}
                for r in _rows("inventories"):  # the first version is the set as sold
                    if r["set_num"] not in inv or int(r["version"]) < inv[r["set_num"]][1]:
                        inv[r["set_num"]] = (r["id"], int(r["version"]))
                by_inv = collections.defaultdict(list)
                wanted = {v[0] for v in inv.values()}
                for r in _rows("inventory_parts"):
                    if r["inventory_id"] in wanted and r["is_spare"] == "False":
                        by_inv[r["inventory_id"]].append(r)
                elements = {}
                for r in _rows("elements"):
                    elements.setdefault((r["part_num"], r["color_id"]), r["element_id"])
                el_to_part = {}
                for r in _rows("elements"):
                    el_to_part[r["element_id"]] = (r["part_num"], r["color_id"])
                cls._tables = {"parts": parts, "cats": cats, "colors": colors, "inv": inv, "by_inv": by_inv,
                               "elements": elements, "el_to_part": el_to_part}
            return cls._tables

    @classmethod
    def set_parts(cls, set_num):
        t = cls.tables()
        if set_num not in t["inv"]:
            return None
        merged = collections.Counter()
        for r in t["by_inv"][t["inv"][set_num][0]]:
            merged[(r["part_num"], r["color_id"])] += int(r["quantity"])
        return [cls.describe(p, c, q) for (p, c), q in sorted(merged.items())]

    @classmethod
    def describe(cls, part_num, color_id, quantity, element_id=None):
        t = cls.tables()
        part = t["parts"].get(part_num, {})
        return {"part_num": part_num, "color_id": color_id, "color": t["colors"].get(color_id, "?"), "quantity": quantity,
                "name": part.get("name", "?"), "category": t["cats"].get(part.get("part_cat_id"), "?"),
                "element_id": element_id or t["elements"].get((part_num, color_id))}


def designs(parts_list):
    """{part_num: (name, category)} for card making."""
    return {p["part_num"]: (p["name"], p["category"]) for p in parts_list}


def prompt_text(parts_list):
    lines = [f"- {p['quantity']}x lego-{p['part_num']} | {p['name']} | colour {p['color']}"
             + (f" | element {p['element_id']}" if p.get("element_id") else "") for p in parts_list]
    return (f"PARTS LIST ({sum(p['quantity'] for p in parts_list)} pieces, {len(parts_list)} lines):\n" + "\n".join(lines))


# --- Fallback: the set is not in Rebrickable --------------------------------------------
class BookletLine(BaseModel):
    element_id: Optional[str] = Field(description="Element ID printed next to the piece, or null")
    part_num: Optional[str] = Field(description="LEGO design number if you know it (e.g. 3001 for Brick 2 x 4), or null")
    name: str = Field(description="Piece name in Rebrickable style, e.g. 'Plate 1 x 2', 'Slope 45 2 x 2'")
    colour: str
    quantity: int


class BookletParts(BaseModel):
    parts: List[BookletLine]


def booklet_parts(pdf_bytes, model="sonnet", effort="low"):
    """Parts from the booklet. Returns (parts_list, stats, method)."""
    from ..checks import booklet_inventory
    t = RebrickableDump.tables()
    page = booklet_inventory(pdf_bytes)  # {element_id: count} from the parts page, by code
    known = {el: q for el, q in page.items() if el in t["el_to_part"]}
    if known and sum(known.values()) >= 0.8 * sum(page.values()):
        out = [RebrickableDump.describe(*t["el_to_part"][el], q, element_id=el) for el, q in sorted(known.items())]
        return out, {"seconds": 0.0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}, "booklet parts page (code)"
    from ..extract import _pdf_block, claude_json
    system = ("You read a LEGO building-instructions booklet and list every piece the model uses, with its total count: "
              "add up the parts boxes of all steps (a box inside a '2x' sub-assembly counts twice), or copy the parts page "
              "at the end if there is one. Give the LEGO design number when you know it.")
    res, stats = claude_json(system, [_pdf_block(pdf_bytes), {"type": "text", "text": "List the pieces."}], BookletParts,
                             model=model, effort=effort, timeout=1200)
    colour_id = {v.lower(): k for k, v in t["colors"].items()}
    merged = collections.Counter()
    for line in res["parts"]:
        part, color = None, colour_id.get(line["colour"].lower(), "-1")
        if line["element_id"] and line["element_id"] in t["el_to_part"]:
            part, color = t["el_to_part"][line["element_id"]]
        elif line["part_num"] and line["part_num"] in t["parts"]:
            part = line["part_num"]
        merged[(part or "x-" + "-".join(line["name"].lower().split())[:40], color, line["name"])] += line["quantity"]
    out = []
    for (part, color, name), q in sorted(merged.items()):
        d = RebrickableDump.describe(part, color, q)
        if d["name"] == "?":
            d.update(name=name, category="unknown")
        out.append(d)
    return out, stats, "Claude read the booklet"
