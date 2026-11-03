"""How much new part a booklet step shows, measured by code.

What it is   each part's outline from the booklet's usual angle (its LDraw shape, lego_model.mesh), the picture's
             scale from step 1's single piece, and each step's new pixels sorted by colour; per step and colour, the
             measured area against the area its read pieces would cover.
Used for     code's own evidence for the reads: a step whose read leaves much of a colour unexplained is asked about
             again, and pieces still left go to the one step whose unexplained area of their colour they fit
             (flagged for review).
Where        lego_booklet/pdf_lesson.py (calibration, measure, check, fill; balance only with --balance, off by
             default).

Each LDraw part is drawn from the booklet's usual angle (three-quarter view from above) and its outline area counted
(`silhouette`, in LDraw units squared). Step 1 adds the first piece alone, so its area in pixels against its outline
gives the picture's scale. After that, the overlay's changed pixels of a step (step_diff: the previous picture lined
up on this one) are sorted by colour into the set's colours and turned into the same units. A new piece shows a
little less than its whole outline (its lower edge sits behind what is already built), so the measured/expected
ratio of a well-read step is about CAL; the running median of the steps so far replaces it once there are some.

  check     per step and colour: measured area, the area the step's read pieces would cover, and the ratio
  fill      copies still left of a part go to the one step that has unexplained area of their colour, when their
            size fits it (flagged for review)
Tested on the Car (30103-1): steps read right measure 0.55-0.97 of their pieces; the step whose read had only the
pink panel (and not the two tiles beside it) measured 2x the panel. Only coloured parts are measured: in a line
drawing black outlines, white and clear parts and greys cannot be told apart by colour.
"""
import collections
import functools
import gzip
import csv
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[3]
AZ, EL = 45, 40       # the booklet's three-quarter view, as far as areas go
CAL = 0.78            # a well-read step's measured/expected (the Car's median)
MORE, LESS = 1.5, 0.4  # beyond these (after calibration) a colour's area is not explained by what was read
MIN_AREA = 300        # LDraw units squared: smaller differences are left alone (outlines, shading)


@functools.lru_cache(maxsize=None)
def silhouette(part_num, k=0.5):
    """The outline area of one part seen from the booklet's angle, in LDraw units squared; None without a model."""
    import cv2
    import numpy as np
    from graph.parts.lego import lego_ids
    from graph import lego_model
    r = lego_model.view(AZ, EL)
    for name in (part_num, lego_ids.base(part_num)):
        try:
            tris = [[lego_model._apply(r, list(p)) for p in tri] for c, tri in lego_model.mesh(f"{name}.dat") if c != "24"]
        except Exception:
            tris = []
        if tris:
            a = np.array([[p[:2] for p in t] for t in tris]) * k
            a -= a.reshape(-1, 2).min(0)
            w, h = (a.reshape(-1, 2).max(0) + 3).astype(int)
            m = np.zeros((h, w), np.uint8)
            cv2.fillPoly(m, [t.astype(np.int32) for t in a], 1)
            return int(m.sum()) / (k * k)
    return None


@functools.lru_cache(maxsize=1)
def _rgb():
    f = ROOT / "data" / "sources" / "rebrickable" / "colors.csv.gz"
    return {r["name"]: tuple(int(r["rgb"][i:i + 2], 16) for i in (0, 2, 4)) for r in csv.DictReader(gzip.open(f, "rt"))}


def _lab(rgb):
    import cv2
    import numpy as np
    return cv2.cvtColor(np.uint8([[rgb[::-1]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)


def _model(im):
    """The model's pixels in a step picture: not the step's background, not the step number; the largest blob."""
    import cv2
    import numpy as np
    h, w = im.shape[:2]
    corner = im[: h // 8, w // 3:].reshape(-1, 3) // 8
    v, c = np.unique(corner, axis=0, return_counts=True)
    bg = v[c.argmax()] * 8 + 4
    m = (np.abs(im.astype(int) - bg).max(2) > 30).astype(np.uint8)
    m[: int(0.2 * h), : int(0.2 * w)] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    return lab == 1 + st[1:, 4].argmax() if n > 1 else m > 0


def measure(set_id, steps, first_part, colours, dpi=300):
    """{step: {colour: measured area, "*": all new area}} for the steps that line up with the previous one, and the
    scale (pixels per LDraw unit squared) from step 1, which adds `first_part` alone. colours: the set's colours."""
    import cv2
    import numpy as np
    import pymupdf
    from graph.lego_booklet import step_diff
    doc = pymupdf.open(ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf")
    imgs = [step_diff._bgr(doc[s["page"] - 1], s["crop"], dpi) for s in steps]
    ref = silhouette(first_part)
    if not ref:
        return {}, None
    scale = _model(imgs[0]).sum() / ref
    idx = {s["step"]: i for i, s in enumerate(steps)}
    prev = {k: (idx.get(s["prev"]) if "kind" in s else (k - 1 if k else None)) for k, s in enumerate(steps)}
    out, masks = {}, {}
    for k in range(1, len(steps)):  # every step's change against its own previous step (in its build or sub-build):
        j = prev[k]                 # not the arrows, not a piece that only moved into place
        if j is None:
            masks[k] = (None, None)
            continue
        from graph.lego_booklet.pdf_lesson import corner as _corner
        m = step_diff.gone(imgs[k], step_diff.changed_regions(imgs[j], imgs[k], mask=True, top=0,
                                                               corner=_corner(steps[k]) if dpi == 300 else
                                                               step_diff.number_corner(dpi)))
        raw = None if m is None else m.copy()
        if m is not None and steps[j].get("arrows"):
            m[step_diff.moved(steps[j]["arrows"], masks.get(j, (None, None))[1], m.shape) > 0] = 0
        if m is not None and steps[k].get("arrows"):  # an arrow is not a piece
            m[step_diff.arrow_mask(m.shape, steps[k]["arrows"]) > 0] = 0
        masks[k] = (m, raw)
    for k in range(1, len(steps)):  # "*": every changed pixel, whatever its colour (white parts too)
        m = masks[k][0]
        if m is not None:
            m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            out[steps[k]["step"]] = {"*": m.sum() / scale}
    pal = {c: _lab(_rgb()[c]) for c in colours if c in _rgb()}
    chrom = {c: v for c, v in pal.items() if np.hypot(v[1] - 128, v[2] - 128) >= 15}  # coloured parts only:
    names = list(chrom)                     # black outlines, white and clear parts and greys cannot be told apart
    if not names:                           # by colour in a line drawing, so they are not measured
        return out, scale
    hue = np.array([np.arctan2(chrom[c][2] - 128, chrom[c][1] - 128) for c in names])
    sat = np.array([np.hypot(chrom[c][1] - 128, chrom[c][2] - 128) for c in names])
    for k in range(1, len(steps)):
        m = masks[k][0]
        if m is None:
            continue
        lab = cv2.cvtColor(imgs[k], cv2.COLOR_BGR2LAB).astype(float)
        a, b = lab[..., 1] - 128, lab[..., 2] - 128
        c_pix, h_pix = np.hypot(a, b), np.arctan2(b, a)
        dh = np.abs((h_pix[..., None] - hue + np.pi) % (2 * np.pi) - np.pi)  # hue distance to each set colour
        best = dh.argmin(2)
        ok = (m > 0) & (dh.min(2) < np.radians(25)) & (c_pix >= 0.4 * sat[best])  # clearly that hue, saturated enough
        got = {}
        for i, c in enumerate(names):
            mask = (ok & (best == i)).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))  # not thin lines or specks
            if mask.sum():
                got[c] = mask.sum() / scale
        out[steps[k]["step"]].update(got)
    return out, scale


def expected(read):
    """{colour: the area the step's read pieces would cover}."""
    e = collections.Counter()
    for a in read["adds"]:
        s = silhouette(a["part"][len("lego-"):])
        if s:
            e[a["colour"]] += s * a["count"] * read.get("times", 1)
    return e


def check(read, measured, cal=CAL):
    """[problem] for one step: a colour of which the step shows much more new area than its read pieces of that
    colour cover (a piece of the same colour missed, beside or under another). Only this direction is asked: new
    area with no piece of its colour read can be a piece that moved into place (drawn beside the model one step,
    pressed on the next), and too little area can be a piece hidden behind the model."""
    out, e = [], expected(read)
    for c, x in e.items():
        m = measured.get(c, 0)
        if c in measured and x and m - x * cal > MIN_AREA and m / (x * cal) > MORE:
            out.append(f"the new {c} area in this picture is about {m / (x * cal):.1f} times what the {c} pieces you "
                       f"read would cover: is another {c} piece there (beside or under the one you read)?")
    return out


def calibration(reads, areas):
    """The median measured/expected over the steps whose areas are explained (CAL until there are three)."""
    r = []
    for rd in reads:  # over the measured (coloured) parts only
        m = areas.get(rd["step"])
        e = {c: v for c, v in expected(rd).items() if m and c in m}
        if m and sum(e.values()) > MIN_AREA:
            r.append(sum(m[c] for c in e) / sum(e.values()))
    r = [x for x in r if 0.4 < x < 1.6]
    return statistics.median(r) if len(r) >= 3 else CAL


def fill(reads, inventory, areas):
    """Copies still left of a part: to the one step whose new area of that colour is not explained by its read and
    fits them (their outlines 0.6-2 times the unexplained area: a piece partly hidden shows less, never more),
    flagged for review. Returns (reads, still left, phase)."""
    cal = calibration(reads, areas)
    used = collections.Counter()
    for r in reads:
        for a in r["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * r.get("times", 1)
    left = {(r["part"], r["colour"]): r["count"] - used[(r["part"], r["colour"])] for r in inventory
            if r["count"] > used[(r["part"], r["colour"])]}
    placed = []
    for k, n in list(left.items()):
        size = silhouette(k[0][len("lego-"):])
        if not size:
            continue
        spare = {}
        for r in reads:
            m = (areas.get(r["step"]) or {}).get(k[1], 0)
            extra = m / cal - expected(r).get(k[1], 0)
            if extra > MIN_AREA:
                spare[r["step"]] = extra
        if len(spare) != 1:
            continue
        st, extra = next(iter(spare.items()))
        if not 0.6 <= n * size / extra <= 2.0:  # uneven: a piece partly hidden shows less than its outline, never more
            continue
        r = next(x for x in reads if x["step"] == st)
        same = next((a for a in r["adds"] if (a["part"], a["colour"]) == k), None)
        if same:
            same["count"] += n
        else:
            r["adds"].append({"part": k[0], "colour": k[1], "count": n, "where": "beside the other new pieces"})
        r.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]} (by size)")
        r.setdefault("problems", []).append(f"{n}x {k[0]} {k[1]} placed here by size: the step shows about "
                                            f"{extra:.0f} units of unexplained {k[1]}, {n} of them cover "
                                            f"{n * size:.0f}; check the picture")
        left[k] = 0
        placed.append({"part": k[0], "colour": k[1], "count": n, "step": st, "by": "size",
                       "unexplained": round(extra), "fits": round(n * size)})
    still = [f"{k[0]} {k[1]}: {n} never added" for k, n in left.items() if n > 0]
    return reads, still, {"step": "size", "try": 0, "seconds": 0, "cost_usd": 0, "problems": [],
                          "placed": placed, "calibration": round(cal, 3)}


def _total(read):
    return sum(expected(read).values())


def balance(reads, areas, pick=None, most=3, pairs=None):
    """A piece read one step too early or too late, found by the steps' whole new area (every colour, white parts
    too). Two neighbouring steps are compared with each other (the scale cancels out): where one shows much less new
    area for what it was read to add than the next (under 0.45 of it), the pieces whose move to the other step would
    even them out are the candidates. One kind of candidate: code moves it. Several (two white mudguards of about one
    size): pick(src, dst, candidates) -> the one that moved, or None (Claude, with both pictures); code takes only a
    candidate. Both steps are flagged and reworded. Returns (reads, phase)."""
    import math
    tot = lambda r: (areas.get(r["step"]) or {}).get("*")
    ratios = [tot(r) / _total(r) for r in reads if tot(r) and _total(r) > MIN_AREA]
    ratios = [x for x in ratios if 0.3 < x < 1.6]
    cal = statistics.median(ratios) if len(ratios) >= 3 else CAL
    moves, asked = [], []
    for _ in range(most):
        found = None
        by = {r["step"]: r for r in reads}  # pairs: (previous step, step) in one build or sub-build
        for a, b in ([(by[x], by[y]) for x, y in pairs if x in by and y in by] if pairs else zip(reads, reads[1:])):
            ta, tb, ea, eb = tot(a), tot(b), _total(a), _total(b)
            if not (ta and tb) or ea <= MIN_AREA or eb <= MIN_AREA:
                continue
            rel = (ta / ea) / (tb / eb)
            if 0.45 <= rel <= 1 / 0.45:
                continue
            src, dst = (a, b) if rel < 1 else (b, a)  # src was read to add more than it shows
            ts, td, es, ed = (ta, tb, ea, eb) if src is a else (tb, ta, eb, ea)
            cands = []
            for piece in src["adds"]:
                size = silhouette(piece["part"][len("lego-"):])
                if not size or es - size <= 0:
                    continue
                new_rel = (ts / (es - size)) / (td / (ed + size))
                ok = 0.5 <= ts / ((es - size) * cal) <= 2.0 and 0.5 <= td / ((ed + size) * cal) <= 2.0
                if ok and abs(math.log(new_rel)) < abs(math.log(min(rel, 1 / rel))) - 0.5:
                    cands.append(piece)
            kinds = {(c["part"], c["colour"]) for c in cands}
            if not kinds:
                continue
            if len(kinds) == 1:
                found = (src, dst, cands[0], "code", rel)
            elif pick:
                ans = pick(src, dst, cands)
                asked.append({"from": src["step"], "to": dst["step"], "candidates": sorted(f"{k[0]} {k[1]}" for k in kinds),
                              "answer": ans and f"{ans['part']} {ans['colour']}"})
                hit = next((c for c in cands if ans and (c["part"], c["colour"]) == (ans["part"], ans["colour"])), None)
                if hit:
                    found = (src, dst, hit, "claude, from the candidates code found", rel)
            if found:
                break
        if not found:
            break
        src, dst, piece, how, rel = found
        piece["count"] -= 1
        if piece["count"] <= 0:
            src["adds"].remove(piece)
        same = next((x for x in dst["adds"] if (x["part"], x["colour"]) == (piece["part"], piece["colour"])), None)
        if same:
            same["count"] += 1
        else:
            dst["adds"].append({**piece, "count": 1})
        what = f"1x {piece['part']} {piece['colour']}"
        for r, verb in ((src, f"moved to step {dst['step']}"), (dst, f"moved here from step {src['step']}")):
            r.setdefault("problems", []).append(f"{what} {verb} by area (step {src['step']} showed "
                                                f"{min(rel, 1 / rel):.2f} of step {dst['step']}'s new area for its "
                                                f"pieces; chosen by {how}): check the pictures")
            r["reword"] = True
        moves.append({"piece": what, "from": src["step"], "to": dst["step"], "by": how, "relative": round(rel, 2)})
    return reads, {"step": "balance", "try": 0, "seconds": 0, "cost_usd": 0, "problems": [], "placed": moves,
                   "asked": asked, "calibration": round(cal, 3)}
