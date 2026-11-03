"""The 3D hint viewer: the model built so far, and the step's new pieces flying into place.

What it is   every piece as its real LDraw shape (lego_model.mesh) at its exact place in the model, written for a
             web page (three.js): the steps, the palette and the geometry; on Hint the step's new pieces are lifted
             above the model and lowered into place. substeps plays each step as physical actions (a piece held in
             place while an axle is pushed through it, or put on in turn).
Used for     showing a learner where a step's pieces go; and the 3D route's check that a step's words say what the
             3D page shows (lesson.words_vs_3d).
Where        lego_3d/lesson.py (substeps); on its own: python -m graph.lego_3d.lesson_viewer 31040-1 ->
             data/lessons/lego3d/<set>/viewer/{index.html, lesson.json}.
"""
import json
import pathlib
import struct
import sys

import math
import re

from graph.lego_3d import lesson
from graph import lego_model

ROOT = pathlib.Path(__file__).resolve().parents[3]
HTML = pathlib.Path(__file__).with_name("lesson_viewer.html")
VOX = 4.0  # LDU: the cube size of the real-shape collision test


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _short(name):
    return re.sub(r"\s+", " ", name).replace(" x ", "×").strip()


def copies(pieces, asm):
    """A step that builds the same thing several times (four wheels): its pieces split into groups joined among
    themselves, all with the same pieces (part and colour). Returns the groups (one group when there are no copies)."""
    left, groups = set(pieces), []
    near = lambda i: (asm.fastens.get(i, set()) | {(set(k) - {i}).pop() for k in asm.touch if i in k and len(k) == 2})
    while left:
        seed = min(left, key=lambda i: pieces.index(i))
        g, todo = {seed}, [seed]
        while todo:
            for o in near(todo.pop()) & left - g:
                g.add(o)
                todo.append(o)
        left -= g
        groups.append(sorted(g, key=pieces.index))
    sig = lambda g: sorted((asm.where[i][1], next(r[2] for r in ROWS[0] if r[0] == i)) for i in g)
    if len(groups) > 1 and all(sig(g) == sig(groups[0]) for g in groups):
        return groups
    return [list(pieces)]


ROWS = [()]




def choose_view(sight, new, last):
    """The view a step is shown from: the last one if it shows every new piece, else the one that shows them best
    (from above when it can). `turn` when it goes from above to below or back: the model is turned over."""
    from graph.lego_3d.assembly import VIEWS
    if not new:
        return last, False
    score = {v: min(sight.seen(i, v) for i in new) for v in VIEWS}
    ok = [v for v in VIEWS if score[v] >= 0.15]
    if last in ok:
        return last, False
    view = max(VIEWS, key=lambda v: (v in ok, v[1] < 0, score[v]))
    return view, bool(last and (last[1] < 0) != (view[1] < 0))


def swings(nid, built, asm, step=()):
    """Arms that can turn out of the way: built pieces touching nid that hang on one pin line only (one round pin,
    or pins on one axis), so a hand can swing them aside, put nid in, and swing them back (42124 booklet 64)."""
    out = []
    for n in sorted(built, key=lambda i: (len(i), i)):
        t = (lego_model.library_title(lego_model.resolve(asm.where[n][1])) or "").lower()
        if n in asm.figs or frozenset((n, nid)) not in asm.touch or n in asm.fastens.get(nid, set()):
            continue  # not a neighbour, or the piece goes into it (then it must stay where it is)
        if not re.search(r"beam|liftarm", t):  # only arms: beams and liftarms, not pins or connectors
            continue
        if not any(n in asm.fastens.get(x, set()) and nid in asm.fastens.get(x, set()) for x in step if x != nid):
            continue  # nothing in this step goes into both the arm and the piece: the arm need not move
        on = asm.fastens.get(n, set()) & built
        joins = [asm.joins.get(frozenset((n, o))) for o in on]
        if not on or any(j is None or j[0] != "pin" for j in joins):
            continue
        b = asm.boxes[n]
        inside = lambda p: all(b[k] - 2 <= p[k] <= b[k + 3] + 2 for k in range(3))
        pins = [(p, a) for o in on for kind, p, a in asm.feats.get(o, []) if kind == "pin" and inside(p)]
        axled = lambda o: asm.long_axle(o) or "axle" in (lego_model.library_title(lego_model.resolve(asm.where[o][1])) or "").lower()
        if not pins or any(axled(o) for o in on):  # on an axle (or an axle pin's cross end) it cannot turn
            continue
        p0, a0 = pins[0]
        line = all(abs(abs(sum(a[k] * a0[k] for k in range(3))) - 1) < 1e-3  # all on one axis line
                   and math.dist([p[k] - p0[k] for k in range(3)],
                                 [sum((p[j] - p0[j]) * a0[j] for j in range(3)) * a0[k] for k in range(3)]) < 2
                   for p, a in pins)
        if line:
            out.append({"piece": n, "at": [round(p0[0], 2), round(-p0[1], 2), round(p0[2], 2)],
                        "axis": [round(a0[0], 4), round(-a0[1], 4), round(a0[2], 4)]})
    return out


def substeps(steps, rows, pieces_info):
    """Each step piece by piece, in an order that can really be built (assembly.py): the direction each piece goes
    on, a one-line instruction from what it fastens to, and whether something already built is in its way."""
    from graph.lego_3d import assembly
    asm = assembly.Assembly(rows)
    ROWS[0] = rows
    info = {p["id"]: p for p in pieces_info}
    label = lambda i: f"{info[i]['colour'].lower()} {_short(info[i]['name'])}" if i in info else i
    import collections
    model, side, out, blocked = set(), collections.defaultdict(set), [], 0
    sight = collections.defaultdict(lambda: assembly.Sightlines(asm))  # what each section shows from the 8 views
    last_view = {}
    for st in steps:
        subs = []
        attach_dir = None
        if st.get("attach") in side:  # a finished sub-assembly joins the model, along the way its joins go
            block = side.pop(st["attach"])
            into = side[st["subassembly"]] if st.get("subassembly") else model  # or into a bigger sub-assembly
            dirs = [asm.approach(i, into)[0] for i in block if asm.fastens.get(i, set()) & into]
            if dirs:
                v = [sum(d[k] for d in dirs) for k in range(3)]
                n = math.sqrt(sum(x * x for x in v)) or 1.0
                attach_dir = [round(v[0] / n, 3), round(-v[1] / n, 3), round(v[2] / n, 3)]
            into |= block
            for i in block:
                sight[st.get("subassembly") or ""].add(i)
        built = side[st["subassembly"]] if st.get("subassembly") else model
        sec = st.get("subassembly") or ""
        view, turn = choose_view(sight[sec], [i for i in st["pieces"] if asm.voxels(i)], last_view.get(sec))  # built off to the side: meets only itself
        # pieces drawn apart but sold as one (a motor's cable: '..._subpart1.ldr') come with the piece they belong to
        extra = [i for i in st["pieces"] if "_subpart" in asm.where[i][1]]
        st = dict(st, pieces=[i for i in st["pieces"] if i not in extra])
        groups = copies(st["pieces"], asm)
        first = set(groups[0]) if len(groups) > 1 else set(st["pieces"])
        rest = list(st["pieces"])
        fresh = not built  # a new group: its pieces go on one by one, never as a block pushed into the lone start
        # piece at the end (42124 block 42: the motor with its pins and cross block, pushed into the 5-hole beam last)
        if not built and len(rest) > 2:  # a new group: its main piece down first, then blocks made in the hand go onto it
            plan = asm.order_step(rest, set())  # its start piece, then the rest inside out, a big part last
            nid, d, partners, _ = plan[0]
            rest = [x[0] for x in plan]
            subs.append({"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)],
                         "text": f"Put the {label(nid)} down to start.", "blocked": False, "copy": nid not in first})
            built.add(nid)
            rest.remove(nid)
        # a step that joins several official steps is played one official step at a time, in LEGO's order: blocks
        # made in the hand never mix them (42124 booklet: the cross block onto the axle pin, then its half pin)
        offi = {p["id"]: p.get("official_step") or 0 for p in pieces_info}
        for rest in [[i for i in rest if offi.get(i, 0) == o] for o in sorted({offi.get(i, 0) for i in rest})]:
            for g, link in ([] if fresh else assembly.in_hand(list(rest), built, asm)):  # put together in the hand, then pushed on as one block
                d0, partners0 = asm.approach(link, built)
                for nid, d, partners, blocker in asm.order_step(g, set()):
                    rel, other = partners[0] if partners else (None, None)
                    text = (f"In your hand: put the {label(nid)} {rel} the {label(other)}." if other
                            else f"In your hand: take the {label(nid)}.")
                    subs.append({"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)], "text": text,
                                 "blocked": False, "copy": nid not in first, "hand": [round(d0[0], 3), round(-d0[1], 3), round(d0[2], 3)]})
                rel, other = partners0[0] if partners0 else ("onto", None)
                subs.append({"piece": link, "group": g, "dir": [round(d0[0], 3), round(-d0[1], 3), round(d0[2], 3)],
                             "text": f"Push the block you made {rel} the {label(other)}." if other else "Put the block in place.",
                             "blocked": False, "copy": False})
                built |= set(g)
                rest = [i for i in rest if i not in g]
            for nid, d, partners, blocker in asm.order_step(rest, built):
                rel, other = partners[0] if partners else (None, None)
                text = f"Put the {label(nid)} {rel} the {label(other)}." if other else f"Put the {label(nid)} down to start."
                axle = [] if asm.fastens.get(nid, set()) & built else asm.must_thread(
                    nid, [i for i in rest if i not in built], built - {nid})  # held: only what has nothing to go onto yet
                if axle:  # threaded: held in its place, lined up with the holes the axle comes through (42124 booklet 64)
                    via = sorted(asm.fastens.get(axle[0], set()) & built - {nid}, key=lambda i: (len(i), i))
                    into = f"through the {label(via[0])} into it" if via else "into it"
                    text = (f"Hold the {label(nid)} in its place, lined up with the holes: next the "
                            f"{label(axle[0])} is pushed {into}.")
                sub = {"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)], "text": text,
                       "blocked": blocker is not None, "copy": nid not in first}
                arms = swings(nid, built, asm, [i for i in rest if i not in built]) if axle or blocker is not None else []
                if arms:  # tight fit: turn the arms aside on their pin, put it in, turn them back
                    kinds = list(dict.fromkeys(label(a["piece"]) for a in arms))
                    names = " and ".join(kinds) if len(kinds) > 1 or len(arms) == 1 else f"two {kinds[0]}s"
                    pins = "its pin" if len(arms) == 1 else "their pins"
                    sub["swing"] = arms
                    sub["text"] = f"Turn the {names} out a little on {pins} to make room. " + text
                subs.append(sub)
                blocked += blocker is not None
                built.add(nid)
        for i in extra:  # with the piece of this step it belongs to (the one it touches, else the first)
            owner = next((x for x in subs if not x.get("group") and frozenset((i, x["piece"])) in asm.touch), subs[0] if subs else None)
            if owner is None:
                continue
            owner["group"] = (owner.get("group") or [owner["piece"]]) + [i]
            built.add(i)
        for i in st["pieces"]:
            sight[sec].add(i)
        last_view[sec] = view
        for x in subs:  # 1:1 lengths: how many studs long an axle or a beam is
            m = re.search(r"\b(?:axle|beam)\s+(\d+(?:\.\d+)?)\b", (info.get(x["piece"]) or {}).get("name", "").lower())
            if m and not x.get("group"):
                x["len"] = float(m.group(1))
        out.append({"subs": subs, "attach_dir": attach_dir, "copies": len(groups) if len(groups) > 1 else 1,
                    "view": [view[0], -view[1], view[2]] if view else None, "turn": turn})
    substeps.blocked = blocked
    return out


def export(set_id, src=None):
    d = (src or lesson.OUT) / set_id
    data = json.loads((d / "lesson.json").read_text())
    steps = data["lesson"]["steps"]
    rows = lesson.placed(set_id)
    palette, pal_index, blob, pieces = [], {}, bytearray(), []
    for nid, ref, colour, pos, rot in rows:
        tris = []
        for code, tri in lego_model.mesh_low(ref):
            if code == "24":
                continue
            c = colour if code == "16" else code
            if c not in pal_index:
                pal_index[c] = len(palette)
                palette.append("#%02x%02x%02x" % lego_model.rgb(c))
            pts = [[pos[i] + lego_model._apply(rot, list(p))[i] for i in range(3)] for p in tri]
            tris.append((pal_index[c], pts))
        start = len(blob)
        for _, pts in tris:
            for p in pts:
                blob += struct.pack("<3h", *(max(-32768, min(32767, round(v * 2))) for v in p))
        colours_at = len(blob)
        blob += bytes(c for c, _ in tris)
        if len(blob) % 2:
            blob += b"\0"
        pieces.append({"id": nid, "tris": len(tris), "at": start, "colours_at": colours_at})
    name = data["lesson"].get("title", set_id)
    subs = substeps(steps, rows, data.get("pieces", []))
    out = {"set": set_id, "title": name, "palette": palette, "pieces": pieces,
           "steps": [{"pieces": s["pieces"], "instruction": s["instruction"], "subassembly": s.get("subassembly", ""),
                      "attach": s.get("attach", ""), "bag": s.get("bag"), "substeps": sub["subs"],
                      "attach_dir": sub["attach_dir"], "copies": sub["copies"], "view": sub["view"],
                      "turn": sub["turn"]} for s, sub in zip(steps, subs)]}
    v = d / "viewer"
    v.mkdir(parents=True, exist_ok=True)
    out["geometry"] = __import__("base64").b64encode(bytes(blob)).decode()  # artifacts serve text, not binary files
    (v / "lesson.json").write_text(json.dumps(out))
    page = HTML.read_text().replace("{{TITLE}}", name.split(" ", 1)[-1] or set_id)
    (v / "index.html").write_text(page)
    return v, len(blob)


if __name__ == "__main__":
    args = sys.argv[1:]
    src = pathlib.Path(args.pop(args.index("--from") + 1)) if "--from" in args else None
    if "--from" in args:
        args.remove("--from")
    for s in args:
        v, n = export(s, src)
        print(f"{s}: {v} ({n / 1e6:.1f} MB of geometry)")
