"""A LEGO set's pieces, and the LEGO part data new cards come from: Rebrickable.

What it is   the set's official inventory from the local copy of Rebrickable's daily dump
             (data/sources/rebrickable): [{part_num, color_id, color, quantity, name, element_id}], spare pieces
             left out, with the dump's part and category tables (RebrickableDump). And Rebrickable as a site
             (Rebrickable, a site adapter of parts/ingest.py): a part's data from the dump first, the live API
             (REBRICKABLE_API_KEY) for one missing from it; a plain brick, plate or tile becomes a card by code.
Used for     every LEGO lesson's parts list, before anything is read or planned; and the card of a LEGO piece the
             card store does not have.
Where        lesson_store.py, lego_model.py (the set's model against its inventory), lego_3d/ (lesson, graphs); the
             adapter through parts/ingest.py (adapters, route) and parts/cards.py (lego_card_code).
"""
import collections
import csv
import gzip
import json
import os
import pathlib
import re
import threading

from graph.parts.ingest import SiteAdapter, fetch


ROOT = pathlib.Path(__file__).resolve().parents[4]
DUMP = ROOT / "data" / "sources" / "rebrickable"


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

    _figs = None

    @classmethod
    def minifig_parts(cls):
        """{set inventory id: Counter[(part, colour)]} of the parts of the minifigures in each set (Rebrickable lists a
        set's minifigures apart from its parts; a 3D model of the set builds them)."""
        with cls._lock:
            if cls._figs is None:
                figs = collections.defaultdict(list)
                for r in _rows("inventory_minifigs"):
                    figs[r["inventory_id"]].append((r["fig_num"], int(r["quantity"])))
                fig_inv = {}
                for r in _rows("inventories"):
                    if r["set_num"].startswith("fig-") and (r["set_num"] not in fig_inv or int(r["version"]) < fig_inv[r["set_num"]][1]):
                        fig_inv[r["set_num"]] = (r["id"], int(r["version"]))
                wanted = {fig_inv[f][0] for v in figs.values() for f, _ in v if f in fig_inv}
                fig_parts = collections.defaultdict(collections.Counter)
                for r in _rows("inventory_parts"):
                    if r["inventory_id"] in wanted and r["is_spare"] == "False":
                        fig_parts[r["inventory_id"]][(r["part_num"], r["color_id"])] += int(r["quantity"])
                out = collections.defaultdict(collections.Counter)
                for inv_id, rows in figs.items():
                    for f, q in rows:
                        for k, n in fig_parts.get(fig_inv.get(f, (None,))[0], {}).items():
                            out[inv_id][k] += n * q
                cls._figs = out
            return cls._figs

    @classmethod
    def set_parts(cls, set_num, minifigs=False):
        """The set's parts as sold (no spares); minifigs=True adds the parts of its minifigures."""
        t = cls.tables()
        if set_num not in t["inv"]:
            return None
        merged = collections.Counter()
        for r in t["by_inv"][t["inv"][set_num][0]]:
            merged[(r["part_num"], r["color_id"])] += int(r["quantity"])
        if minifigs:
            merged.update(cls.minifig_parts().get(t["inv"][set_num][0], {}))
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


# ---- Rebrickable as the site a new LEGO card comes from ----------------------------------------------
class Rebrickable(SiteAdapter):
    """LEGO parts: the local copy of Rebrickable's daily dump first; a part missing from it goes to the live API
    (needs REBRICKABLE_API_KEY). Plain bricks, plates and tiles become cards by code."""
    domain = "rebrickable.com"

    def part_number(self, target):
        m = re.search(r"rebrickable\.com/parts/([^/]+)", target)
        return m.group(1) if m else re.sub(r"^lego-", "", target)

    def fetch_data(self, target):
        from graph.parts.lego.inventory import RebrickableDump
        num = self.part_number(target)
        t = RebrickableDump.tables()
        part = t["parts"].get(num)
        if part is None and os.environ.get("REBRICKABLE_API_KEY"):
            raw = fetch(f"https://rebrickable.com/api/v3/lego/parts/{num}/",
                        headers={"Authorization": "key " + os.environ["REBRICKABLE_API_KEY"]})
            part = raw and json.loads(raw)
            part = part and {"part_num": part["part_num"], "name": part["name"], "part_cat_id": str(part["part_cat_id"])}
        if not part:
            return None
        return {"title": part["name"], "url": f"https://rebrickable.com/parts/{num}/", "jsonld": None,
                "text": json.dumps({"part_num": num, "name": part["name"],
                                    "category": t["cats"].get(part.get("part_cat_id"), "?")}),
                "part_num": num, "name": part["name"], "category": t["cats"].get(part.get("part_cat_id"), "?")}

    def deterministic(self, content):
        from graph.parts import part_catalogue
        from graph.parts import cards
        if not content or not part_catalogue.brick_dims(content["name"]):
            return None
        e = part_catalogue.lego_entry(content["part_num"], content["name"])
        return cards.from_engine(e, "lego", {"platform": "rebrickable", "url": content["url"],
                                              "external_id": content["part_num"], "made_by": "code"})
