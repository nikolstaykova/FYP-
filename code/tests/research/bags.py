"""Which pieces of a set are in bag 1, bag 2.

What it is   Claude reads the booklet only for its numbered bags (the bag pictures and each step's parts call-out);
             code checks the answer (every part in bags exactly as often as the set has it; bags numbered 1, 2, 3
             with consecutive steps) and puts every piece of the 3D model into a bag.
Used for     planning a big 3D-route lesson bag by bag, each section starting with 'Open bag N'.
Where        lego_3d/lesson.py (sections: read, assign); cached in data/lessons/lego3d/<set>/bags.json.
"""
import collections
import pathlib
import re
from typing import List

from pydantic import BaseModel, Field

from graph import lego_model

ROOT = pathlib.Path(__file__).resolve().parents[3]
BAG_REPAIRS = 2


class BagLine(BaseModel):
    line: int = Field(description="Number of the parts-list line (L1, L2 ... -> 1, 2 ...)")
    count: int = Field(description="How many of that line this bag's steps use")


class Bag(BaseModel):
    bag: int = Field(description="The number printed on the bag in the booklet (1, 2, 3 ...)")
    first_step: int
    last_step: int
    parts: List[BagLine]


class Section(BaseModel):
    kind: str = Field(description="'main' (part of the set's main model, the one on the box front), 'minifigure' "
                                  "(a figure or small accessory built on its own), or 'alternate' (a DIFFERENT model "
                                  "built from the same pieces: a 3-in-1 B or C model, a B model)")
    name: str = Field(description="What the section builds, in a few words (e.g. 'red jeep', 'dune buggy', 'pilot')")
    first_page: int
    last_page: int


class BagPlan(BaseModel):
    sections: List[Section] = Field(description="The booklet's building sections in page order")
    numbered_bags: bool = Field(description="False if the booklet shows no numbered bags (then one bag: all parts)")
    bags: List[Bag] = Field(description="Bags of the MAIN model only")
    notes: List[str]


BAGS_SYSTEM = """You read an official LEGO instruction booklet (attached) for two things only: its SECTIONS and its numbered BAGS.
SECTIONS: a booklet can hold more than the main model. Step numbers start again at 1 for each section. Say what each
section is: part of the MAIN model (the box-front model: its chapters, sub-models built separately and attached,
later bags), a MINIFIGURE or small accessory built on its own, or an ALTERNATE build (a different, complete model from
the same pieces, as in 3-in-1 sets: it ends with its own finished model). Give each section's first and last page.
BAGS (main model only). LEGO marks numbered bags in one or both of these ways: an OVERVIEW page near the start that
shows bag icons with big numbers (1, 2, 3 ...) next to pictures of the model at each stage; and/or a bag icon with a
big number where each bag's section starts. If either appears, the booklet HAS numbered bags. Use the overview's
pictures and the section starts to find where each bag's steps begin.
Sections of a booklet start with a picture of a bag with a big number: open bag 1, build steps ..., open bag 2, ...
For each bag give its number, the first and last booklet step built from it, and how many of each line of the
PARTS LIST below its steps use (read the parts call-out box of every step in the bag's section and add them up).
Every part the MAIN model uses must end up in exactly one bag, as many times as it uses it (an alternate build reuses
the same pieces, so do not count its call-outs again). Pieces not shown in any
call-out (spares are not listed) go in the bag whose steps use them. If the booklet has no numbered bags, return
numbered_bags = false and one bag (number 1) with every part."""


def parts_list(set_id):
    from graph.parts.lego import inventory as pl
    return pl.RebrickableDump.set_parts(set_id, minifigs=True) or []


def check_bags(plan, parts, restarts=()):
    issues = []
    secs = plan.get("sections") or []
    if secs and not any(x["kind"] == "main" for x in secs):
        issues.append(("B3", "no section is the main model"))
    for a, b in zip(secs, secs[1:]):
        if b["first_page"] <= a["last_page"]:
            issues.append(("B3", f"sections overlap or are out of page order: '{a['name']}' pages {a['first_page']}-"
                                 f"{a['last_page']}, '{b['name']}' pages {b['first_page']}-{b['last_page']}"))
    starts = {x["first_page"] for x in secs}
    missed = [p for p in restarts if not any(abs(p - q) <= 1 for q in starts)]
    if secs and missed:
        issues.append(("B3", f"step numbers start again on page(s) {missed}, but no section starts there"))
    want = {i: p["quantity"] for i, p in enumerate(parts, 1)}
    got = collections.Counter()
    for b in plan["bags"]:
        for x in b["parts"]:
            got[x["line"]] += x["count"]
    wrong = [(i, want.get(i, 0), got.get(i, 0)) for i in sorted(set(want) | set(got)) if want.get(i, 0) != got.get(i, 0)]
    if wrong:
        issues.append(("B1", "bag counts differ from the parts list: " + ", ".join(
            f"L{i} ({parts[i - 1]['name'][:30] if 0 < i <= len(parts) else '?'}): list {w}, bags {g}" for i, w, g in wrong[:40])))
    nums = [b["bag"] for b in plan["bags"]]
    if nums != list(range(1, len(nums) + 1)):
        issues.append(("B2", f"bags should be numbered 1, 2, 3 ... in booklet order; got {nums}"))
    steps = [(b["first_step"], b["last_step"]) for b in plan["bags"]]
    for (a1, b1), (a2, b2) in zip(steps, steps[1:]):
        if a2 <= b1:
            issues.append(("B2", f"bag steps overlap or go backwards: {a1}-{b1} then {a2}-{b2}"))
    return issues


def read(set_id, pdf_bytes, model="sonnet", effort="high"):
    """Claude reads the booklet's bags. Returns (plan, parts, stats)."""
    from graph.extract import SubscriptionSession
    parts = parts_list(set_id)
    listing = "\n".join(f"L{i} | {p['part_num']} | {p['name']} | {p['color']} | x{p['quantity']}"
                        for i, p in enumerate(parts, 1))
    import pymupdf
    builds = lego_model.booklet_builds(pymupdf.open(stream=pdf_bytes, filetype="pdf"))
    restarts = [b[0][0] for b in builds[1:]]
    hint = (f"\n\nSTEP NUMBERS START AGAIN on page(s) {restarts} (found in the booklet's text): each of those starts a "
            f"section." if restarts else "")
    text = f"LEGO set {set_id}. PARTS LIST ({len(parts)} lines, minifigures included):\n{listing}{hint}"
    s = SubscriptionSession(text, "", "lego-v8", pdf=pdf_bytes, model=model, effort=effort, timeout=1800,
                            schema=BagPlan, system=BAGS_SYSTEM)
    phases = []
    try:
        plan, st = s.first()
        issues = check_bags(plan, parts, restarts)
        phases.append({"phase": "bags", **st, "issues": len(issues)})
        for n in range(BAG_REPAIRS):
            if not issues:
                break
            plan, st = s.repair("The bags have problems:\n" + "\n".join(f"- {r}: {m}" for r, m in issues) +
                                "\n\nReturn the COMPLETE corrected bags.")
            issues = check_bags(plan, parts, restarts)
            phases.append({"phase": f"repair{n + 1}", **st, "issues": len(issues)})
    finally:
        s.close()
    secs = plan.get("sections") or []
    stats = {"bags": len(plan["bags"]), "numbered": plan["numbered_bags"],
             "sections": [f"{x['kind']}: {x['name']} (pages {x['first_page']}-{x['last_page']})" for x in secs],
             "alternate_builds": sum(1 for x in secs if x["kind"] == "alternate"), "issues_final": [list(i) for i in issues],
             "seconds": round(sum(p["seconds"] for p in phases), 1),
             "cost_usd": round(sum(p["cost_usd"] for p in phases), 4), "repairs": len(phases) - 1}
    return plan, parts, stats


def _colour_key(name):
    return re.sub(r"[^a-z]", "", (name or "").lower().replace("grey", "gray"))


def assign(plan, parts, pieces):
    """{piece id: bag number} for the 3D model's pieces (in build order): each piece to the earliest bag that still
    has one of its design, preferring one of its colour. Pieces with no match go to the bag of the piece before."""
    left = collections.defaultdict(collections.Counter)  # bag -> Counter[(design, colour)]
    for b in plan["bags"]:
        for x in b["parts"]:
            if 0 < x["line"] <= len(parts):
                p = parts[x["line"] - 1]
                left[b["bag"]][(lego_model.canon(p["part_num"]), _colour_key(p["color"]))] += x["count"]
    order = [b["bag"] for b in plan["bags"]]
    out, last = {}, order[0] if order else 1
    for p in pieces:
        d, c = lego_model.canon(p["part_num"]), _colour_key(p["colour"])
        bag = next((b for b in order if left[b][(d, c)] > 0), None)
        if bag is None:
            bag = next((b for b in order if any(k[0] == d and v > 0 for k, v in left[b].items())), None)
            if bag is not None:
                k = next(k for k, v in left[bag].items() if k[0] == d and v > 0)
                left[bag][k] -= 1
        else:
            left[bag][(d, c)] -= 1
        out[p["id"]] = bag if bag is not None else last
        last = out[p["id"]]
    return out
