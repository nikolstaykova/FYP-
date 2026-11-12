"""The gather cards of a LEGO lesson: the learner finds the pieces for the next few steps, shows them to the camera,
builds them, then gathers again. Part of making a LEGO lesson: lesson_store.register calls add_cards, and the cards
are stored in the steps graph (and the database) like any other step.

A LEGO learner has the set, so there is no whole-set check, and finding pieces before every single step is too slow
on a big set. So the steps are split into groups, and a gather card goes before each group. Each card is checked
from one photo of the pieces laid out (gather.gather, the LEGO card check), so a card must stay small enough for a model to see
every piece: about PIECES pieces and at most KINDS different kinds.
- A numbered bag (from the booklet) always starts a new group: "Open bag 2 and find these pieces".
- A group holds at most MAX_STEPS steps. Sizes are balanced, so the last group is not a leftover, and a group with
  very few pieces joins a neighbour when the two still fit on one card.
- A booklet sub-build (7.1, 7.2, then 7 where it goes on) is gathered in one go, unless it is too big: then it is
  split at its sub-steps.
- A single step with more pieces than a card holds gets several cards in a row ("part 1 of 2").

Stored as: a `gather` node in the steps graph, in the step order just before the first step it gathers for, with a
COVERS link to each of those steps (DATA_STRUCTURE.md). Its pieces are not stored again: they are those steps'
pieces. Only a card that splits a big group says which of them it holds (`pieces` on its COVERS links).

  add_cards(graphs)    make the cards and put them in the lesson's steps graph (again: the same cards, not more)
  groups(steps)        the planning: steps [{number, bag, times, parts: [{what, count, ...}]}] ->
                       [{first, last, bag, open_bag, pieces, parts, part, of}] (first/last: step indexes)
  python -m graph.lesson_store gather [ids]   remake the cards of stored lessons (and send them to the database)
"""
import math
import re

PIECES = 10  # pieces per card, about
KINDS = 8  # different pieces per card, at most
MAX_STEPS = 8  # never more steps than this between two gather cards
TINY = 0.5  # a group under this share of the target joins a neighbour (when the two still fit)


def _pieces(step):
    """How many pieces the step uses (a sub-build made 4 times needs its pieces 4 times)."""
    return sum(p["count"] for p in step.get("parts") or []) * max(1, int(step.get("times") or 1))


def _kinds(steps, idx):
    return {p["what"] for i in idx for p in steps[i].get("parts") or []}


def _units(steps):
    """The steps in runs that are gathered together: a booklet sub-build (7.1, 7.2 ... then 7) is one run."""
    out, run = [], []
    for i, s in enumerate(steps):
        run.append(i)
        if "." not in str(s.get("number") or ""):  # a main step closes the run
            out.append(run)
            run = []
    if run:
        out.append(run)
    return out


def _segments(steps, units):
    """The units by bag: a new bag starts a new segment. Returns [(bag or None, [units])]."""
    segs = []
    for u in units:
        bag = next((steps[i].get("bag") for i in u if steps[i].get("bag") is not None), None)
        if not segs or (bag is not None and bag != segs[-1][0]):
            segs.append((bag, []))
        segs[-1][1].append(u)
    return segs


def _fits(steps, idx, limit):
    return sum(_pieces(steps[i]) for i in idx) <= limit * 1.25 and len(_kinds(steps, idx)) <= KINDS


def _split(steps, units):
    """Units into groups of about PIECES pieces (balanced), at most KINDS kinds and MAX_STEPS steps."""
    units = [x for u in units for x in ([[i] for i in u] if not _fits(steps, u, PIECES) else [u])]
    flat = [i for u in units for i in u]
    total = sum(_pieces(steps[i]) for i in flat)
    if _fits(steps, flat, PIECES) and len(flat) <= MAX_STEPS:
        return [units]
    target = total / max(1, math.ceil(total / PIECES))
    groups, cur = [], []
    for u in units:
        idx = [i for g in cur for i in g]
        got = sum(_pieces(steps[i]) for i in idx)
        n = sum(_pieces(steps[i]) for i in u)
        if cur and (got >= target or got + n > target * 1.25 or len(idx) + len(u) > MAX_STEPS
                    or len(_kinds(steps, idx + u)) > KINDS):
            groups.append(cur)
            cur = []
        cur.append(u)
    if cur:
        groups.append(cur)
    return _merge_tiny(steps, groups, target)


def _merge_tiny(steps, groups, target):
    """A group with only a few pieces (or none: a step that attaches what was built) joins its smaller neighbour,
    when the two still fit on one card (an empty group always joins)."""
    def size(g):
        return sum(_pieces(steps[i]) for u in g for i in u)
    while len(groups) > 1:
        order = sorted(range(len(groups)), key=lambda j: size(groups[j]))
        for k in order:
            if size(groups[k]) >= target * TINY:
                return groups
            for j in sorted({k - 1, k + 1} & set(range(len(groups))), key=lambda j: size(groups[j])):
                a, b = sorted((j, k))
                idx = [i for g in groups[a] + groups[b] for i in g]
                if size(groups[k]) == 0 or _fits(steps, idx, PIECES):
                    groups[a:b + 1] = [groups[a] + groups[b]]
                    break
            else:
                continue
            break
        else:
            return groups
    return groups


def _parts(steps, idx):
    """The pieces of these steps, added up, in the order they are first used (each keeps its other fields)."""
    got = {}
    for i in idx:
        times = max(1, int(steps[i].get("times") or 1))
        for p in steps[i].get("parts") or []:
            if p["what"] in got:
                got[p["what"]]["count"] += p["count"] * times
            else:
                got[p["what"]] = {**p, "count": p["count"] * times}
    return list(got.values())


def _chunks(parts):
    """A list too long for one card, in cards of about PIECES pieces and at most KINDS kinds (a row is never split)."""
    total = sum(p["count"] for p in parts)
    n = max(math.ceil(total / (PIECES * 1.25)), math.ceil(len(parts) / KINDS))
    target = total / n
    out, cur = [], []
    for p in parts:
        got = sum(x["count"] for x in cur)
        if cur and (got >= target or got + p["count"] > target * 1.25 or len(cur) >= KINDS):
            out.append(cur)
            cur = []
        cur.append(p)
    return out + ([cur] if cur else [])


def groups(steps):
    """The gather cards of a LEGO lesson's steps (see the module doc)."""
    if not steps:
        return []
    out = []
    for bag, units in _segments(steps, _units(steps)):
        for k, g in enumerate(_split(steps, units)):
            idx = [i for u in g for i in u]
            parts = _parts(steps, idx)
            cards = [parts] if not parts or (sum(p["count"] for p in parts) <= PIECES * 1.25
                                             and len(parts) <= KINDS) else _chunks(parts)
            for c, chunk in enumerate(cards):
                out.append({"first": idx[0], "last": idx[-1], "bag": bag, "open_bag": bag is not None and k == 0 and c == 0,
                            "pieces": sum(p["count"] for p in chunk), "parts": chunk, "part": c + 1, "of": len(cards)})
    return out


# ---- in the lesson's steps graph --------------------------------------------------------------------------------
OPEN_BAG = re.compile(r"open bag \d+\.?$", re.I)


def plan_steps(graphs):
    """The lesson's build steps in the learner's order, as groups() wants them: [{id, number, bag, times, parts}],
    parts [{what, count, type, colour}]. 3D lessons place pieces (physical nodes), booklet lessons place rows of
    the parts list with a count. "Open bag N" steps are left out (their bag's card says to open it)."""
    from graph import lesson_store
    inst = graphs.get("instruction") or {"nodes": [], "edges": []}
    phys = {n["id"]: n for n in (graphs.get("physical") or {}).get("nodes", [])}
    rows = ((graphs.get("lesson") or {}).get("parts_list") or {}).get("parts", [])
    nodes = {n["id"]: n for n in inst["nodes"]}
    placed = {}
    for e in inst["edges"]:
        if e["type"] != "PLACES":
            continue
        ref = re.match(r"lesson:parts_list/(\d+)$", str(e["v"]))
        if ref and int(ref.group(1)) < len(rows):
            r = rows[int(ref.group(1))]
            piece = (r.get("part"), r.get("colour"), r.get("name") or r.get("part"), e.get("count") or 1)
        elif e["v"] in phys:
            n = phys[e["v"]]
            piece = (n.get("type"), (n.get("props") or {}).get("colour"), n.get("label") or n.get("type"), 1)
        else:
            continue
        placed.setdefault(e["u"], []).append(piece)
    out = []
    for sid in lesson_store._order(inst):
        s = nodes.get(sid) or {}
        if s.get("kind") not in ("step", "build"):
            continue
        if not placed.get(sid) and OPEN_BAG.match((s.get("text") or "").strip()):
            continue
        parts = {}
        for typ, colour, name, count in placed.get(sid, []):
            what = f"{colour} {name}".strip() if colour else name
            p = parts.setdefault(what, {"what": what, "count": 0, "type": typ, "colour": colour})
            p["count"] += count
        times = int(s.get("times") or 1) if str(s.get("times") or 1).isdigit() else 1
        out.append({"id": sid, "number": str(s.get("number") or s.get("n") or ""), "bag": s.get("bag"),
                    "times": times, "parts": list(parts.values())})
    return out


def strip_cards(inst):
    """The steps graph without its LEGO gather cards (so the cards can be made again): the step order closes up."""
    cards = {n["id"] for n in inst["nodes"] if n.get("kind") == "gather" and "of" in n}  # a LEGO card (not Arduino's)
    if not cards:
        return inst
    after = {e["u"]: e["v"] for e in inst["edges"] if e["type"] == "NEXT_STEP" and e["u"] in cards}
    edges = []
    for e in inst["edges"]:
        if e["u"] in cards or e["type"] == "COVERS":
            continue
        v = e["v"]
        while v in cards:  # whatever led to a card now leads to the step after it
            v = after.get(v)
        if v is not None:
            edges.append({**e, "v": v})
    inst["nodes"] = [n for n in inst["nodes"] if n["id"] not in cards]
    inst["edges"] = edges
    return inst


def add_cards(graphs):
    """Make the gather cards of a LEGO lesson and put them in its steps graph (replacing any made before).
    Returns how many cards there are."""
    inst = graphs.get("instruction")
    if not inst:
        return 0
    strip_cards(inst)
    steps = plan_steps(graphs)
    made = []
    for k, g in enumerate(groups(steps), 1):
        span = steps[g["first"]: g["last"] + 1]
        first, last = g["first"] + 1, g["last"] + 1
        what = f"step {first}" if first == last else f"steps {first} to {last}"
        lead = (f"Open bag {g['bag']} and find" if g["open_bag"] else
                f"From bag {g['bag']}, find" if g["bag"] is not None else "Find")
        part = f" (part {g['part']} of {g['of']})" if g["of"] > 1 else ""
        card = {"id": f"gather-{k}", "kind": "gather",
                "title": (f"Bag {g['bag']}: find the pieces" if g["bag"] is not None else "Find the pieces") + part,
                "text": f"{lead} these pieces for {what}{part} ({g['pieces']} pieces). Lay them out flat on a plain "
                        "table, a little apart, and show them to the camera (or tap each one when you have it).",
                "bag": g["bag"], "open_bag": g["open_bag"], "pieces": g["pieces"], "part": g["part"], "of": g["of"]}
        covers = []
        mine = {p["what"] for p in g["parts"]}
        for s in span:
            e = {"type": "COVERS", "u": card["id"], "v": s["id"]}
            if g["of"] > 1:  # a split card holds some of these steps' pieces: which ones
                pcs = [{"type": p["type"], "colour": p["colour"], "count": p["count"] * s["times"]}
                       for p in s["parts"] if p["what"] in mine]
                if not pcs:
                    continue
                e["pieces"] = pcs
            covers.append(e)
        made.append((card, span[0]["id"], covers))
    # into the step order, just before the first step it gathers for (cards for the same step in their order):
    # - a step with its own sub-build (it STARTS one: the learner builds that first) gets the card as one more
    #   thing it STARTS, after the sub-build, so the card comes between the sub-build and the step;
    # - otherwise whatever led to the step (NEXT_STEP, or a build's STARTS) now leads to the card, and the card
    #   leads to the step.
    for card, before, covers in made:
        if any(e["type"] == "STARTS" and e["u"] == before for e in inst["edges"]):
            inst["edges"].append({"type": "STARTS", "u": before, "v": card["id"]})
        else:
            for e in inst["edges"]:
                if e["type"] in ("NEXT_STEP", "STARTS") and e["v"] == before:
                    e["v"] = card["id"]
            inst["edges"].append({"type": "NEXT_STEP", "u": card["id"], "v": before})
        inst["nodes"].append(card)
        inst["edges"] += covers
    return len(made)
