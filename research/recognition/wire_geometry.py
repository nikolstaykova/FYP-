"""Geometry only, no model: the holes give the grid, the grid gives the column of a point.

For each labelled photo (data/wires/board/labels.json), the clicked wire end (x, y) is put through the board's
homography (validator/board.py: holes -> grid -> flatten) to a grid column, counted from one end of the board.
Then: does one fixed rule turn that count into the printed number for every photo? If yes, geometry can count columns
and the model only has to find the end (or not even that).

    python research/recognition/wire_geometry.py
Writes research/recognition/runs/wire_geometry/<time>/: each photo flattened, with the holes found, the click and
the column geometry gives.
"""
import json
import pathlib
import sys
import time

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from validator import board  # noqa: E402
from validator.geometry import *  # noqa: E402,F401,F403  (moved to code/validator/geometry.py)
from validator.geometry import _ends  # noqa: E402,F401

LABELS = ROOT / "data" / "wires" / "board" / "labels.json"
PHOTOS = ROOT / "data" / "wires" / "board"
OUT = ROOT / "research" / "recognition" / "runs" / "wire_geometry" / time.strftime("%Y%m%d-%H%M%S")
EDGE = 2000






def main():
    OUT.mkdir(parents=True)
    labels = json.loads(LABELS.read_text())
    rows = []
    for name, lab in sorted(labels.items()):
        if not any(e.get("column") is not None for e in lab["ends"]):
            continue
        img = board.load(str(PHOTOS / f"{name}.jpg"))
        f = EDGE / max(img.shape[:2])
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        try:
            g = board_grid(img)
        except cv2.error:
            g = None
        if g is None:
            print(f"{name}: grid not found ({len(board.holes(img))} holes)")
            rows.append({"photo": name, "grid": False})
            continue
        c0, c1 = g["cols"]
        r = g["rows"]
        for e in lab["ends"]:
            if e.get("column") is None:
                continue
            col, row = where(g, e["x"] * w, e["y"] * h)
            k = round(col) - c0  # 0 = the first column found at the photo's left
            rows.append({"photo": name, "grid": True, "label": e["column"], "half": e["half"], "from_left": k,
                         "from_right": c1 - round(col), "frac": round(col - round(col), 2), "row": round(row - r[0], 1),
                         "cols_found": c1 - c0 + 1, "rows_found": len(r), "inliers": g["inliers"]})
            vis = img.copy()
            for x, y in g["holes"].astype(int):
                cv2.circle(vis, (x, y), 2, (0, 0, 255), -1)
            cv2.circle(vis, (int(e["x"] * w), int(e["y"] * h)), 14, (0, 255, 255), 3)
            cv2.imwrite(str(OUT / f"{name}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    print(f"{'photo':10} {'label':>5} {'half':>4} {'left':>5} {'right':>5} {'frac':>5} {'row':>5} {'cols':>5} {'rows':>4} holes")
    for r in rows:
        if r["grid"]:
            print(f"{r['photo']:10} {r['label']:>5} {r['half']:>4} {r['from_left']:>5} {r['from_right']:>5} {r['frac']:>5} "
                  f"{r['row']:>5} {r['cols_found']:>5} {r['rows_found']:>4} {r['inliers']}")
    print(OUT)


if __name__ == "__main__" and not ({"--v2", "--v3"} & set(sys.argv)):
    main()


# ---- v2: count from the end of the main blocks, decide which way up from the rails ---------------------------------















def main2():
    labels = json.loads(LABELS.read_text())
    ok = tot = 0
    for name, lab in sorted(labels.items()):
        ends = [e for e in lab["ends"] if e.get("column") is not None]
        if not ends:
            continue
        g = best_grid(board.load(str(PHOTOS / f"{name}.jpg")))
        if g is not None:
            h, w = g["img"].shape[:2]
        for e in ends:
            tot += 1
            if g is None:
                print(f"{name}: no grid    true {e['column']}{e['half']}")
                continue
            r = read_point(g, e["x"] * w, e["y"] * h)
            if r is None:
                print(f"{name}: no half    true {e['column']}{e['half']}")
                continue
            good = r["column"] == e["column"]
            ok += good
            print(f"{name}: {'ok ' if good else 'BAD'} true {e['column']:>2}{e['half']}  geometry {r['column']:>2}{r['half']}"
                  f"  cols {r['n']} flip {r['flip']} fit {r['fit']} row {r['row']}")
    print(f"geometry: {ok}/{tot} columns right")


if __name__ == "__main__" and "--v2" in sys.argv:
    main2()
    sys.exit()


# ---- geometry + model: the board straightened, every column numbered with its printed number ----------------------



# ---- code finds the pin: the black connector on the straightened board ----------------------------------------------











def main3():
    """Code finds the connector; which point of it gives the right column: its centre, or its end away from the wire?"""
    labels = json.loads(LABELS.read_text())
    score = {"centre": 0, "far": 0, "base": 0, "click": 0}
    tot = 0
    vis_dir = OUT
    vis_dir.mkdir(parents=True, exist_ok=True)
    for name, lab in sorted(labels.items()):
        ends = [e for e in lab["ends"] if e.get("column") is not None]
        if not ends:
            continue
        flat, info = flat_board(str(PHOTOS / f"{name}.jpg"))
        for e in ends:
            tot += 1
            if flat is None:
                print(f"{name}: {info}")
                continue
            h, w = info["img"].shape[:2]
            fx, fy = to_flat(info, e["x"] * w, e["y"] * h)
            shift, marks = printed_shift(flat, info)
            cs = connectors(flat, info)
            if not cs:
                print(f"{name}: no connector found   true {e['column']}")
                continue
            c = min(cs, key=lambda c: (c["centre"][0] - fx) ** 2 + (c["centre"][1] - fy) ** 2)  # the clicked one
            row = {}
            for key, pt in (("centre", c["centre"]), ("far", c["far"] or c["centre"]),
                            ("base", c["base"] or c["centre"]), ("click", (fx, fy))):
                k = c["half"] if key != "click" else (info["half_of"](fy) if info["half_of"](fy) is not None else c["half"])
                row[key] = label(round(info["idx_of"](pt[0])), k, shift)
                score[key] += row[key] == e["column"]
            print(f"{name}: true {e['column']:>2}  centre {row['centre']:>2}  far-from-wire {row['far']:>2}  base {row['base']:>2}  "
                  f"click {row['click']:>2}  shift {shift} ({marks} marks)  connectors {len(cs)}{'' if c['far'] else '  (no wire seen)'}")
            vis = flat.copy()
            for cc in cs:
                cv2.circle(vis, tuple(int(v) for v in cc["centre"]), 8, (0, 255, 255), 2)
                if cc["far"]:
                    cv2.circle(vis, tuple(int(v) for v in cc["far"]), 6, (255, 0, 255), -1)
            cv2.imwrite(str(vis_dir / f"{name}_conn.jpg"), vis)
    print({k: f"{v}/{tot}" for k, v in score.items()})
    print(vis_dir)


if __name__ == "__main__" and "--v3" in sys.argv:
    main3()
    sys.exit()


# ---- geometry first: code reads every connector; it is sure when its three estimates of the pin agree ------------

