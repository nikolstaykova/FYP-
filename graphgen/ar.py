"""AR support (v8): the build as steps an AR app can play and check, and how often a placement would point at the
right spot.

  python -m graphgen.ar <run dir> [<run dir> ...]   writes <case>/ar_steps.json for every LEGO case and AR_REPORT.md

1. Anchoring. Placements are relative to the model, so an AR app locks the model's grid onto one real piece: the
   ANCHOR is the first step's piece with the largest footprint (a vehicle base, a baseplate, a 2x8 plate). Every
   placement in the export is in the anchor's frame: its front-left-bottom corner is column 0, row 0, layer 0 and
   its long side runs along the columns (turn 0). The app finds the anchor in the camera image, and from then on a
   placement is a fixed offset from it.
2. Step export (`export`). Per booklet step: the pieces it adds (part, LDraw file, colour, placement in the anchor
   frame, LDraw position and rotation in LDU), and the joins each new piece makes with pieces already there. Plan A
   (an LDraw model, by code) and Plan B (Claude's v8 placements) export the same way.
3. Live check (`check_step`). What the camera saw (pieces with rough placements in the anchor frame) against what
   the step expects: each expected piece is right, misplaced (by how much) or missing; an observed piece not in the
   step is extra; the joins the observed pieces make (same snapping and stud matching as v8) are compared too.
4. Placement accuracy (`accuracy`). Claude's placed pieces against the set's real LDraw model, after the best
   alignment of the two frames (four quarter turns, a shift): a piece is IN PLACE when a real piece of the same
   design has its centre within half a stud across and half a plate up, and RIGHT when its box (so its
   orientation, up to symmetry) is also the same. This is how often an AR overlay would show the right spot.
"""
import collections
import json
import math
import pathlib
import sys

from . import ldraw_geometry as geo
from . import ldraw_studs, placement, stud_key, truth

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --- pieces as placed ---------------------------------------------------------------------------------------
def from_v8(response, steps=True):
    """A v8 response -> [{id, part_num, ldraw, colour, name, step, pos, rot}] with Claude's placements snapped and
    settled exactly as the build did (placement.joins), plus the joins."""
    info = placement.piece_list(response["parts_list"])
    pls = response["placements"]
    found, placed = placement.joins(
        {i: (info[i]["ldraw"], placement.snapped(p)) for i, p in pls.items() if (info.get(i) or {}).get("ldraw")},
        {i: set(p["rests_on"]) for i, p in pls.items()}, {i: p["step"] for i, p in pls.items()} if steps else None)
    where = {nid: (pos, rot) for nid, _, pos, rot in placed}
    out = [{"id": i, "part_num": info[i]["type"][5:], "ldraw": info[i]["ldraw"], "colour": info[i]["colour"],
            "name": info[i]["name"], "step": p["step"], "pos": where[i][0], "rot": where[i][1]}
           for i, p in pls.items() if i in where]
    return out, found


def from_ldraw(set_id):
    """Plan A: the set's LDraw model -> the same piece list (steps from the model's STEP lines), and its joins."""
    from . import ldraw_graph
    text = (ROOT / "research" / "raw" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    geo.register(text)
    flat = truth.flatten_mpd(text)
    real = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(flat, 1)]
    g = placement.upright(real)
    real = [(nid, ref, truth._apply(g, pos), truth._mul(g, rot)) for nid, ref, pos, rot in real]
    steps = ldraw_graph.steps_of(text)
    steps = steps if len(steps) == len(real) else [1] * len(real)
    out = [{"id": nid, "part_num": stud_key.design(ref), "ldraw": ref, "colour": colour, "name": "",
            "step": s, "pos": pos, "rot": rot}
           for (nid, ref, pos, rot), (_, colour, _, _), s in zip(real, flat, steps)]
    return out, ldraw_studs.connections(real)


# --- 1. anchoring ---------------------------------------------------------------------------------------------
def anchor_of(pieces):
    """The anchor: among the first step's pieces, the one with the largest footprint."""
    first = min(p["step"] for p in pieces)

    def area(p):
        b = geo.world_box(p["ldraw"], p["pos"], p["rot"])
        return (b[3] - b[0]) * (b[5] - b[2]) if b else 0
    return max((p for p in pieces if p["step"] == first), key=area)


def anchor_frame(anchor):
    """(rotation, origin) taking model coordinates into the anchor's frame: the anchor's turn (a quarter turn,
    whichever makes its long side run along the columns) is taken out, then its front-left-bottom corner is the
    origin."""
    turn = round((placement.angles(anchor["rot"]) or (0, 0, 0))[0] / 90) * 90
    b0 = geo.world_box(anchor["ldraw"], [0, 0, 0], placement.rotation(0, 0, 0))
    if b0 and (b0[5] - b0[2]) > (b0[3] - b0[0]):  # a part drawn front-to-back: it lies along the columns at turn 90
        turn -= 90
    r = placement._ry(math.radians(-turn))
    b = geo.world_box(anchor["ldraw"], truth._apply(r, anchor["pos"]), truth._mul(r, anchor["rot"]))
    return r, [b[0], b[4], b[2]]


def to_frame(p, frame):
    """A placed piece in the anchor frame: its LDraw pose and the placement an AR app reads."""
    r, o = frame
    pos = [v - o[i] for i, v in enumerate(truth._apply(r, p["pos"]))]
    rot = truth._mul(r, p["rot"])
    pl = placement.placement_of(p["ldraw"], pos, rot) or {}
    return {**{k: round(v, 2) for k, v in pl.items()}, "pos_ldu": [round(v, 2) for v in pos],
            "rot": [[round(v, 4) for v in row] for row in rot]}


# --- booklet pictures ----------------------------------------------------------------------------------------
def booklet_steps(pdf_path):
    """Where each step is in the booklet: [(page number, (x0, y0, x1, y1) in PDF points)], step 1 first. Step numbers
    are the booklet's large digits (page numbers are small); a page with several steps is split between them, side
    by side or one under another. [] for a scanned booklet (no text)."""
    import pymupdf
    doc = pdf_path if isinstance(pdf_path, pymupdf.Document) else pymupdf.open(pdf_path)
    words = [(i, w) for i, page in enumerate(doc) for w in page.get_text("words")
             if w[4].isdigit() and len(w[4]) <= 3 and (w[3] - w[1]) >= 18]
    if not words:
        return []
    size = collections.Counter(round(w[3] - w[1]) for _, w in words).most_common(1)[0][0]
    nums = [(i, w) for i, w in words if abs((w[3] - w[1]) - size) <= 0.15 * size]
    out = []
    for i in sorted({i for i, _ in nums}):
        rect = doc[i].rect
        here = sorted((w for j, w in nums if j == i), key=lambda w: (int(w[4]), w[1], w[0]))  # the digits ARE the steps
        for n, w in enumerate(here):
            # the next column of steps to the right ends this one; the next step below in this column ends it too
            right = min((v[0] for v in here if v[0] > w[0] + 50), default=rect.x1)
            below = min((v[1] for v in here if v[1] > w[1] + 40 and w[0] - 50 <= v[0] < right), default=rect.y1)
            out.append((i + 1, (max(0, w[0] - 10), max(0, w[1] - 10), right - 5, below - 5)))
    return out


def step_pictures(pdf_path, out_dir, n_steps, pages=None, dpi=110):
    """PNG per step in out_dir (step_001.png ...): the step's part of its page when the booklet has step numbers as
    text, else the whole page Claude said shows it (pages: {step: page}). Returns {step: {page, crop, file}}."""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    where = booklet_steps(pdf_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    got = {}
    for step in range(1, n_steps + 1):
        if step <= len(where):
            page, crop = where[step - 1]
        elif pages and pages.get(step) and 1 <= pages[step] <= len(doc):
            page, crop = pages[step], None
        else:
            continue
        pg = doc[page - 1]
        clip = pymupdf.Rect(*crop) if crop else pg.rect
        f = out_dir / f"step_{step:03}.png"
        pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=clip).save(str(f))
        got[step] = {"page": page, "crop": [round(v, 1) for v in crop] if crop else None, "file": f.name}
    return got


# --- 2. step export ---------------------------------------------------------------------------------------------
def export(set_id, pieces, found, source, pictures=None):
    """{set, source, anchor, steps: [{step, booklet: {page, crop, file}, add: [piece], joins: [[new, existing, how]]}]}."""
    anchor = anchor_of(pieces)
    frame = anchor_frame(anchor)
    by_step = collections.defaultdict(list)
    for p in pieces:
        by_step[p["step"]].append(p)
    step_of = {p["id"]: p["step"] for p in pieces}
    steps = []
    for s in sorted(by_step):
        new = {p["id"] for p in by_step[s]}
        joins = sorted([sorted(k)[0], sorted(k)[1], v[0]] for k, v in found.items()
                       if k & new and all(step_of.get(x, 1e9) <= s for x in k))
        steps.append({"step": s, "booklet": (pictures or {}).get(s), "add": [{"id": p["id"], "part": p["part_num"], "ldraw": p["ldraw"], "colour": p["colour"],
                                          "name": p["name"], **to_frame(p, frame)} for p in by_step[s]],
                      "joins": joins})
    return {"set": set_id, "source": source, "units": "column/row in studs, layer in plates, angles in degrees; "
                                                     "pos_ldu in LDraw units (1 stud = 20, 1 plate = 8, -y up)",
            "anchor": {"id": anchor["id"], "part": anchor["part_num"], "colour": anchor["colour"],
                       "how": "lock the grid onto this piece: its front-left-bottom corner is column 0, row 0, layer 0, "
                              "its long side along the columns"},
            "pieces": len(pieces), "steps": steps}


# --- 3. live check --------------------------------------------------------------------------------------------
def check_step(ar, step, observed, tol=(10.0, 4.0)):
    """What the camera saw against one step of an export. observed: [{part, colour?, column, row, layer, turn,
    tilt, roll, free_angle?}] in the anchor frame, for the pieces of this step (rough is fine: they are snapped
    like Claude's). Returns {right, misplaced: [{id, off_studs, off_plates, turned}], missing, extra, joins_missing,
    joins_extra}."""
    before = [p for st in ar["steps"] if st["step"] < step for p in st["add"]]
    want = next(st for st in ar["steps"] if st["step"] == step)
    fixed = {p["id"]: (p["ldraw"], {k: p[k] for k in ("column", "row", "layer", "turn", "tilt", "roll")}) for p in before}
    seen = {}
    for n, o in enumerate(observed):
        part = placement.ldraw_file(str(o["part"]))
        if part:
            seen[f"seen{n + 1}"] = (part, placement.snapped(o))
    found, placed = placement.joins({**{k: (a, {**b, "free_angle": True}) for k, (a, b) in fixed.items()}, **seen})
    at = {nid: geo.world_box(part, pos, rot) for nid, part, pos, rot in placed}
    centre = lambda b: [(b[i] + b[i + 3]) / 2 for i in range(3)]
    result = {"step": step, "right": [], "misplaced": [], "missing": [], "extra": []}
    free = set(seen)
    for p in want["add"]:
        part = p["ldraw"]
        wb = geo.world_box(part, p["pos_ldu"], p["rot"])
        cands = [s for s in free if seen[s][0] == part and at.get(s)]
        if not cands or not wb:
            result["missing"].append(p["id"])
            continue
        s = min(cands, key=lambda s: math.dist(centre(at[s]), centre(wb)))
        free.discard(s)
        d = [centre(at[s])[i] - centre(wb)[i] for i in range(3)]
        dims = lambda b: [round(b[i + 3] - b[i]) for i in range(3)]
        across, up = math.hypot(d[0], d[2]), abs(d[1])
        if across <= tol[0] and up <= tol[1] and dims(at[s]) == dims(wb):
            result["right"].append(p["id"])
        else:
            result["misplaced"].append({"id": p["id"], "seen_as": s, "off_studs": round(across / 20, 2),
                                        "off_plates": round(up / 8, 2), "turned": dims(at[s]) != dims(wb)})
    result["extra"] = sorted(free)
    return result


# --- 4. placement accuracy ----------------------------------------------------------------------------------------
def _boxes(pieces, turn=0.0):
    r = placement._ry(math.radians(turn))
    out = []
    for p in pieces:
        b = geo.world_box(p["ldraw"], truth._apply(r, p["pos"]), truth._mul(r, p["rot"]))
        if b:
            out.append((stud_key.canon(stud_key.design(p["ldraw"])), [(b[i] + b[i + 3]) / 2 for i in range(3)],
                        [round(b[i + 3] - b[i]) for i in range(3)]))
    return out


def accuracy(claude, real, tol=(10.0, 4.0), tries=400):
    """Claude's placed pieces against the real model's, after the best alignment (4 quarter turns x the shift
    that puts the most pieces in place). Returns {pieces, in_place, right, turn, shift}."""
    true = _boxes(real)
    by_design = collections.defaultdict(list)
    for i, (d, c, dims) in enumerate(true):
        by_design[d].append(i)
    best = {"in_place": -1}
    for turn in (0, 90, 180, 270):
        mine = _boxes(claude, turn)
        cands = collections.Counter()
        rare = sorted(mine, key=lambda m: len(by_design.get(m[0], ())))  # rare designs give few, good candidates
        for d, c, _ in rare:
            for j in by_design.get(d, ())[:6]:
                cands[tuple(round(true[j][1][i] - c[i]) for i in range(3))] += 1
            if len(cands) > tries:
                break
        for shift, _ in cands.most_common(tries):
            used, inplace, right = set(), 0, 0
            for d, c, dims in mine:
                c2 = [c[i] + shift[i] for i in range(3)]
                hit = None
                for j in by_design.get(d, ()):
                    if j in used:
                        continue
                    tc = true[j][1]
                    if math.hypot(c2[0] - tc[0], c2[2] - tc[2]) <= tol[0] and abs(c2[1] - tc[1]) <= tol[1]:
                        hit = j if hit is None or true[j][2] == dims else hit
                if hit is not None:
                    used.add(hit)
                    inplace += 1
                    right += true[hit][2] == dims
            if inplace > best["in_place"]:
                best = {"in_place": inplace, "right": right, "turn": turn, "shift": list(shift)}
    return {"pieces": len(claude), "real_pieces": len(true), **best}


# --- the run --------------------------------------------------------------------------------------------------
def main(argv):
    key = json.loads((ROOT / "research" / "data" / "lego_stud_key.json").read_text())
    for run in map(pathlib.Path, argv):
        rows = []
        for d in sorted(p for p in run.iterdir() if (p / "response.json").exists()):
            r = json.loads((d / "response.json").read_text())
            set_id = d.name
            if r.get("placements"):
                pieces, found = from_v8(r)
                source = "claude (v8 placements)"
            elif (ROOT / "research" / "raw" / "lego" / f"{set_id}.mpd").exists() and r["stats"].get("builder", "").startswith("ldraw"):
                pieces, found = from_ldraw(set_id)
                source = "ldraw model (plan A)"
            else:
                continue
            if not pieces:
                continue
            pdf = ROOT / "research" / "raw" / "lego_pdf" / f"{set_id}.pdf"
            pages = {p["step"]: p.get("page") for p in (r.get("placements") or {}).values() if p.get("page")}
            pictures = step_pictures(pdf, d / "ar_pages", max(p["step"] for p in pieces), pages) if pdf.exists() else {}
            (d / "ar_steps.json").write_text(json.dumps(export(set_id, pieces, found, source, pictures), indent=1))
            row = {"set": set_id, "source": source, "pieces": len(pieces), "trusted": key.get(set_id, {}).get("trusted"),
                   "steps": len({p["step"] for p in pieces}), "steps_with_picture": len(pictures),
                   "picture_from": "step numbers in the PDF" if booklet_steps(pdf) else ("pages Claude named" if pictures else "none")}
            if source.startswith("claude") and (ROOT / "research" / "raw" / "lego" / f"{set_id}.mpd").exists():
                row.update(accuracy(pieces, from_ldraw(set_id)[0]))
            rows.append(row)
            print(f"{set_id:9} {source:24} pieces {len(pieces):4}" + (
                f"  in place {row['in_place']:4} ({row['in_place'] / len(pieces):.0%})  right {row['right']:4} "
                f"({row['right'] / len(pieces):.0%})" if "in_place" in row else ""), flush=True)
        scored = [x for x in rows if "in_place" in x]
        n = sum(x["pieces"] for x in scored)
        lines = [f"# AR placements: {run.name}", "",
                 "Each case has `ar_steps.json`: the anchor piece, then every step's new pieces with their placement "
                 "in the anchor's frame and the joins they make (graphgen/ar.py).", ""]
        if scored:
            lines += [f"**{len(scored)} sets, {n} pieces placed by Claude.** In place (centre within half a stud and "
                      f"half a plate of a real piece of the same design): **{sum(x['in_place'] for x in scored) / n:.0%}**; "
                      f"right (also the same orientation): **{sum(x['right'] for x in scored) / n:.0%}**.", "",
                      "| Set | Pieces | In place | Right | Trusted model | Steps with a booklet picture |",
                 "|---|---:|---:|---:|---|---|"]
            lines += [f"| {x['set']} | {x['pieces']} | {x['in_place'] / x['pieces']:.0%} | {x['right'] / x['pieces']:.0%} | "
                      f"{'yes' if x['trusted'] else 'no'} | {x['steps_with_picture']} / {x['steps']} ({x['picture_from']}) |"
                      for x in scored]
        (run / "AR_REPORT.md").write_text("\n".join(lines) + "\n")
        (run / "ar_accuracy.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
