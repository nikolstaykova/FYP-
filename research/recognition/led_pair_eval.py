"""An LED's legs from two photos of the same position: from above, and low from the side (30-45 degrees).

The board is flat, so its hole grid straightens from any angle (geometry.flat_board); a leg's tip is at board level, so
in the straightened side photo it lands on its true hole, while the body (lifted) is smeared away from the camera.
In the side photo the legs are seen under the body: thin grey lines from the body down into the board. Each leg's end
away from the body is its hole. The photo from above gives the body's place (where to look) and a second opinion.

    python research/recognition/led_pair_eval.py      # scores on data/leds/pairs/labels.json, debug images
"""
import json
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from validator import board, geometry as G  # noqa: E402

D = ROOT / "data" / "leds" / "pairs"
CELL = 40


def straight(path):
    full = board.load(str(path))
    g = G.best_grid(full)
    flat, info = G.flat_board(str(path), cell=CELL, g=g, src=full)
    occ = G.occupied(flat, info)
    flip = bool(occ[1].sum() > 1.3 * occ[0].sum() and occ[1].max() > 0.08)
    if flip:
        flat, info = G.flat_board(str(path), cell=CELL, g=g, src=full, flip=True)
    shift, _ = G.printed_shift(flat, info)
    return flat, info, shift


def main():
    lab = json.loads((D / "labels.json").read_text())
    (D / "debug").mkdir(exist_ok=True)
    ok = n = 0
    for key, v in lab.items():
        if v.get("not_pair") or v.get("long") is None:
            continue
        tflat, tinfo, tshift = straight(D / "jpg" / f"{v['top']}.jpg")
        top = G.leds(tflat, tinfo, tshift)
        span = None
        if top:
            t = top[0]
            k = 0 if t["half"] == "top" else 1
            xs = [x for x, _ in t["outline"]]
            span = sorted(int(G.label(round(x / CELL - 1), k, tshift)) for x in (min(xs), max(xs)))
        flat, info, shift = straight(D / "jpg" / f"{v['side']}.jpg")
        found = G.led_legs_side(flat, info, shift, near=span)
        want = sorted([v["long"], v["short"]])
        got = found["columns"] if found else None
        n += 1
        ok += got == want
        dbg = found["debug"] if found else flat
        cv2.imwrite(str(D / "debug" / f"{v['side']}.jpg"), dbg)
        print(f"{key}  top body {span}  want {want} {v['row']}  got {got}  {'ok' if got == want else 'BAD'}  "
              f"{found and {k: found[k] for k in ('sure', 'rows', 'why')}}")
    print(f"both legs right {ok}/{n}")


if __name__ == "__main__":
    main()
