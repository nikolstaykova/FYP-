"""Where are an LED's legs when its body hides them? Geometry only, scored on labelled photos.

Photos in data/leds/jpg/, labels in data/leds/led_labels.json ({photo: {long, short, half, skip}}: printed columns).
The LED's coloured body is found on the straightened board; it stands about 8.6 mm tall, so in a photo from above its
top leans away from the point under the camera and its base is the blob's end nearest that point (as for wire
connectors). Its legs leave the base 2.54 mm apart (one column), half a column either side of the base's centre.

    python research/recognition/led_eval.py            # scores, and data/leds/debug/<photo>.jpg
"""
import json
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from validator import board, geometry as G  # noqa: E402

D = ROOT / "data" / "leds"


def analyse(path, cell=40):
    full = board.load(str(path))
    g = G.best_grid(full)
    flat, info = G.flat_board(str(path), cell=cell, g=g, src=full)
    occ = G.occupied(flat, info)
    flip = bool(occ[1].sum() > 1.3 * occ[0].sum() and occ[1].max() > 0.08)
    if flip:
        flat, info = G.flat_board(str(path), cell=cell, g=g, src=full, flip=True)
    shift, _ = G.printed_shift(flat, info)
    return flat, info, shift, G.leds(flat, info, shift)


def main():
    labels = json.loads((D / "led_labels.json").read_text()) if (D / "led_labels.json").exists() else {}
    (D / "debug").mkdir(exist_ok=True)
    pair_ok = n = 0
    for p in sorted((D / "jpg").glob("*.jpg")):
        flat, info, shift, found = analyse(p)
        lab = labels.get(p.stem) or {}
        want = sorted(c for c in (lab.get("long"), lab.get("short")) if c is not None)
        got = [sorted(l["columns"]) for l in found]
        hit = bool(want) and want in got
        if want and not lab.get("skip"):
            n += 1
            pair_ok += hit
        dbg = flat.copy()
        for l in found:
            cv2.drawContours(dbg, [np.int32(l["outline"])], -1, (255, 0, 255), 2)
            cv2.circle(dbg, tuple(int(v) for v in l["base"]), 6, (0, 0, 255), -1)
            for x in l["legs_x"]:
                cv2.line(dbg, (int(x), int(l["base"][1]) - 25), (int(x), int(l["base"][1]) + 25), (0, 0, 255), 2)
        cv2.imwrite(str(D / "debug" / f"{p.stem}.jpg"), dbg)
        print(f"{p.stem}  want {want or '?'} {lab.get('half', '')}  got {[(l['columns'], l['half'], l['sure']) for l in found]}"
              f"  {'ok' if hit else ('BAD' if want else '')}")
    if n:
        print(f"both legs right {pair_ok}/{n}")


if __name__ == "__main__":
    main()
