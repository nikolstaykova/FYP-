"""v9 LEGO: render and compare. Geometry checks Claude's placements against the booklet's pictures, step by step,
instead of trusting its stud counting.

For each booklet step (booklets with step numbers as text):
  1. the pieces placed up to that step (Claude's placements, already corrected for earlier steps) are drawn by code
     (render.py) and the camera is fitted so the drawing covers the model in the step's picture
  2. what the step adds is found in the picture: pixels that changed since the previous step (step_diff.py) and have
     the colour of the new piece
  3. each new piece is tried at nearby placements (a few studs either way, a few plates up or down, the four quarter
     turns) and moved to the one whose drawn outline best covers those pixels, if that is clearly better than
     Claude's own placement
Pieces of steps that cannot be checked (the picture does not align with the previous one, the camera does not fit,
no pixels of the piece's colour changed) keep Claude's placement.

  python -m graph.v9 <v8 run dir> [...]   re-places every booklet of a v8 run; scores before and after
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import itertools
import json
import pathlib
import sys


import placement

import ar

import render

import ldraw_studs
from graph.lego_booklet import step_diff
import ldraw_geometry as geo

ROOT = pathlib.Path(__file__).resolve().parents[3]
MIN_FIT = 0.35      # camera fits below this IoU are not trusted
MIN_GAIN = 0.03     # a move must make the drawing agree with the picture this much better than Claude's placement


def _colour_mask(img, colour, tol=60):
    import numpy as np
    r, g, b = render.rgb(colour)
    d = np.abs(img.astype(np.int16) - np.array([b, g, r], np.int16)).sum(axis=2)
    return (d < tol).astype(np.uint8)


def _placed(info, pls, ids):
    out = []
    for i in ids:
        part = (info.get(i) or {}).get("ldraw")
        where = placement.place(part, placement.snapped(pls[i])) if part else None
        if where:
            out.append((i, part, where[0], where[1], info[i]["colour"]))
    return out


def candidates(pl, reach=2, layers=3):
    """Placements near `pl`: column and row up to `reach` studs either way, layer up to `layers` plates, the four
    quarter turns (upright pieces only)."""
    turns = [0, 90, 180, 270] if not (pl.get("tilt") or pl.get("roll")) and not pl.get("free_angle") else [pl.get("turn", 0)]
    for dc, dr, dl, t in itertools.product(range(-reach, reach + 1), range(-reach, reach + 1),
                                           range(-layers, layers + 1), turns):
        yield {**pl, "column": pl["column"] + dc, "row": pl["row"] + dr, "layer": pl["layer"] + dl, "turn": t}


def refine(response, pdf_bytes, log=None):
    """Claude's v8 placements -> (corrected placements {id: placement}, report)."""
    import cv2
    import numpy as np
    import pymupdf
    info = placement.piece_list(response["parts_list"])
    pls = {i: {k: v for k, v in p.items() if k in ("column", "row", "layer", "turn", "tilt", "roll", "free_angle")}
           for i, p in response["placements"].items() if i in info}
    step_of = {i: p["step"] for i, p in response["placements"].items() if i in info}
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    where = ar.booklet_steps(doc)
    report = {"steps": len(where), "checked": 0, "moved": 0, "kept": 0, "skipped": {}}
    prev = None
    for k, (page, crop) in enumerate(where, 1):
        img = step_diff._bgr(doc[page - 1], crop)
        new = [i for i, s in step_of.items() if s == k]
        changed = step_diff.changed_regions(prev, img, mask=True) if prev is not None else None
        prev = img
        if not new:
            continue
        if changed is None:
            report["skipped"]["no-align"] = report["skipped"].get("no-align", 0) + len(new)
            continue
        so_far = [i for i, s in step_of.items() if s <= k]
        placed_now = {w[0]: w for w in _placed(info, pls, so_far)}
        palette = sorted({w[4] for w in placed_now.values()})
        cam, fit, agree = render.fit_camera_colour(list(placed_now.values()), img, palette)
        if not cam or fit < MIN_FIT:
            report["skipped"]["camera"] = report["skipped"].get("camera", 0) + len(new)
            continue
        book = render.classify(img, palette)
        model = render.silhouette(list(placed_now.values()), cam, img.shape)
        near = cv2.dilate(model, np.ones((25, 25), np.uint8))  # changes far from the model: call-outs, arrows
        for i in new:
            part = info[i]["ldraw"]
            region = cv2.dilate(changed & near, np.ones((15, 15), np.uint8))
            if not part or region.sum() < 30 or i not in placed_now:
                report["skipped"]["no-pixels"] = report["skipped"].get("no-pixels", 0) + 1
                continue
            report["checked"] += 1
            rest = [w for v, w in placed_now.items() if v != i]
            rest_lab, rest_dep = render.raster(rest, cam, img.shape, palette)
            support_studs = [(pt, ax) for v in response["placements"][i].get("rests_on", []) if v in placed_now and v != i
                             for k_, pt, ax in ldraw_studs._world([placed_now[v][:4]])[v] if k_ == "stud"]
            rest_boxes = [ob for ob in (geo.world_box(o[1], o[2], o[3]) for o in rest) if ob]

            def physical(w):
                """The piece sits on the studs of a piece it says it rests on (if it names any) and fills no space
                another piece fills."""
                pos, rot = w
                if support_studs and not any(ldraw_studs.receives(pt, ax, part, pos, rot) for pt, ax in support_studs):
                    return False
                b = geo.world_box(part, pos, rot)
                return not any(all(min(b[j + 3], ob[j + 3]) - max(b[j], ob[j]) > 4 for j in range(3)) for ob in rest_boxes)

            def score(pl, check=True):
                w = placement.place(part, placement.snapped(pl))
                if not w or (check and not physical(w)):
                    return -1.0
                lab, dep = render.raster([(i, part, w[0], w[1], info[i]["colour"])], cam, img.shape, palette)
                comp = np.where(dep < rest_dep, lab, rest_lab)
                return render.agreement(comp, book, region | (lab >= 0))
            base = score(pls[i], check=False)
            best, best_s = pls[i], base
            for c in candidates(pls[i]):
                s_ = score(c)
                if s_ > best_s:
                    best, best_s = c, s_
            if best is not pls[i] and best_s >= base + MIN_GAIN:
                pls[i] = best
                placed_now = {w[0]: w for w in _placed(info, pls, so_far)}
                report["moved"] += 1
            else:
                report["kept"] += 1
        if log:
            log(f"step {k}: camera fit {fit:.2f}, {len(new)} new")
    return pls, report


def main(argv):
    import stud_key
    key = stud_key.load()
    for run in map(pathlib.Path, argv):
        tot = {"before": 0, "after": 0, "n": 0, "tp_b": 0, "tp_a": 0, "w_b": 0, "w_a": 0, "real": 0}
        for d in sorted(p for p in run.iterdir() if (p / "response.json").exists()):
            r = json.loads((d / "response.json").read_text())
            pdf = ROOT / "data" / "sources" / "lego_pdf" / f"{d.name}.pdf"
            if not r.get("placements") or not pdf.exists():
                continue
            new_pls, rep = refine(r, pdf.read_bytes())
            r2 = {**r, "placements": {i: {**p, **new_pls.get(i, {})} for i, p in r["placements"].items()}}
            real = ar.from_ldraw(d.name)[0]
            row = {"set": d.name, **rep}
            for tag, resp in (("before", r), ("after", r2)):
                cl, found = ar.from_v8(resp)
                a = ar.accuracy(cl, real)
                row[tag] = a["in_place"]
                des = {p["id"]: stud_key.canon(p["part_num"]) for p in cl}
                import collections
                got = collections.Counter(tuple(sorted((des[x], des[y]))) for x, y in (sorted(k) for k in found))
                tp = sum((got & key[d.name]["pairs"]).values())
                tot["tp_b" if tag == "before" else "tp_a"] += tp
                tot["w_b" if tag == "before" else "w_a"] += sum(got.values())
            tot["before"] += row["before"]
            tot["after"] += row["after"]
            tot["n"] += len(cl)
            tot["real"] += sum(key[d.name]["pairs"].values())
            (d / "placements_v9.json").write_text(json.dumps({"placements": new_pls, "report": rep}, indent=1))
            print(f"{d.name:9} in place {row['before']:3} -> {row['after']:3} of {len(cl)}  checked {rep['checked']} "
                  f"moved {rep['moved']} skipped {rep['skipped']}", flush=True)
        n = max(1, tot["n"])
        print(f"{run.name}: in place {tot['before'] / n:.0%} -> {tot['after'] / n:.0%}; joins recall "
              f"{tot['tp_b'] / max(1, tot['real']):.0%} -> {tot['tp_a'] / max(1, tot['real']):.0%}, precision "
              f"{tot['tp_b'] / max(1, tot['w_b']):.0%} -> {tot['tp_a'] / max(1, tot['w_a']):.0%}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
