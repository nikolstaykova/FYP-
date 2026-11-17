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

LABELS = ROOT / "data" / "wires" / "board" / "labels.json"
PHOTOS = ROOT / "data" / "wires" / "board"
OUT = ROOT / "research" / "recognition" / "runs" / "wire_geometry" / time.strftime("%Y%m%d-%H%M%S")
EDGE = 2000


def board_grid(img):
    c = board.holes(img)
    if len(c) < 60:
        return None
    idx, pl, s1, s2 = board.grid(c)
    if len(idx) < 60:
        return None
    if s1[0] * s2[1] - s1[1] * s2[0] < 0:  # a photo is never mirrored: rows must turn the same way as x then y
        pl = pl * [1, -1]
    flat, H, lo, inl = board.flatten(img, c, idx, pl, cell=36)
    pl = board.flatten.places
    return {"img": img, "H": H, "lo": lo, "places": pl, "holes": c, "inliers": inl, "flat": flat,
            "cols": (int(pl[:, 0].min()), int(pl[:, 0].max())), "rows": sorted(set(int(r) for r in pl[:, 1]))}


def where(g, x, y, cell=36):
    """A photo point -> (grid column, grid row) as floats, in the grid's own counting."""
    p = cv2.perspectiveTransform(np.float32([[[x, y]]]), g["H"])[0, 0] / cell - 1 + g["lo"]
    return float(p[0]), float(p[1])


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

def best_grid(img, sizes=(2000, 1400, 1000)):
    """The grid at a few photo sizes (the hole finder's local threshold suits some sizes better): the one that places
    the most holes."""
    best = None
    for E in sizes:
        im = cv2.resize(img, None, fx=E / max(img.shape[:2]), fy=E / max(img.shape[:2]), interpolation=cv2.INTER_AREA)
        try:
            g = board_grid(im)
        except (cv2.error, ValueError, IndexError):
            g = None
        if g and (best is None or g["inliers"] > best["inliers"]):
            best = g
    return best


def blocks(pl):
    """The grid rows grouped into runs of neighbouring rows; the two runs of about 5 rows with the most holes are the
    two halves (terminal strips). Returns [(rows of the upper half), (rows of the lower half)] in grid rows."""
    import collections
    count = collections.Counter(int(r) for r in pl[:, 1])
    full = max(count.values())
    rows = sorted(r for r, n in count.items() if n >= 0.6 * full)  # not the printed numbers' row (a few blobs)
    runs, cur = [], [rows[0]]
    for r in rows[1:]:
        if r == cur[-1] + 1:
            cur.append(r)
        else:
            runs.append(cur)
            cur = [r]
    runs.append(cur)
    big = sorted(runs, key=lambda run: -sum(count[r] for r in run))
    halves = [r for r in big if 4 <= len(r) <= 6][:2] or big[:2]
    return sorted(halves, key=lambda r: r[0])


COLUMNS = 65  # this board (measured on the labelled photos)


def extent(pl, rows):
    """First and last grid column of the board: the run of COLUMNS columns with the most holes in the two halves (both
    halves share their columns, so a half in shadow is helped by the other; stray blobs past the ends are left out)."""
    import collections
    seen = collections.Counter(int(c) for c, r in pl if int(r) in rows)
    if not seen:
        return None, None
    lo, hi = min(seen), max(seen)
    best = max(range(lo - COLUMNS + 1, hi + 1), key=lambda a: (sum(seen[c] for c in range(a, a + COLUMNS)), -abs(a - lo)))
    return best, best + COLUMNS - 1


def upside_down(img, g, halves, cell=36, margin=8):
    """On an upright board each rail has its blue (-) line above its red (+) line. The board is warped flat with room
    for the rails (8 rows above and below the halves); in the bands outside the two halves, the row where red is
    strongest and the row where blue is strongest are compared, each side votes. True / False / None (can't tell)."""
    pl, lo = g["places"], g["lo"]  # the homography maps grid place p to (p - lo + 1) * 36
    top, bot = halves[0][0], halves[-1][-1]
    x0, x1 = int(pl[:, 0].min()), int(pl[:, 0].max())
    # grid (col, row) -> flat pixel ((col - x0 + 1) * cell, (row - top + margin) * cell)
    T = np.array([[1, 0, (lo[0] - x0) * cell], [0, 1, (lo[1] - top + margin - 1) * cell], [0, 0, 1]], float)
    W, Hh = (x1 - x0 + 3) * cell, (bot - top + 2 * margin) * cell
    flat = cv2.warpPerspective(img, T @ g["H"], (int(W), int(Hh)))
    hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    red = (cv2.inRange(hsv, (0, 70, 60), (12, 255, 255)) | cv2.inRange(hsv, (160, 70, 60), (180, 255, 255))).sum(1)
    blue = cv2.inRange(hsv, (92, 70, 40), (132, 255, 255)).sum(1)
    votes = []
    for a, b in ((0, (margin - 1) * cell), ((bot - top + margin + 1) * cell, int(Hh))):  # above, below the halves
        r, bl = red[a:b], blue[a:b]
        if r.max() < 255 * cell * 3 or bl.max() < 255 * cell * 3:  # no line there (at least 3 cells' worth)
            continue
        votes.append(int(np.argmax(r)) < int(np.argmax(bl)))
    upside_down.flat = flat
    if not votes or len(set(votes)) > 1:
        return None
    return votes[0]


LABEL_OFFSET = 3  # this board: printed number = hole count from the end minus 3 (measured on the labelled photos)


def read_point(g, x, y, cell=36):
    """A photo point -> {"column": printed number, "half": "t"/"b", "row": 0-4 within the half, "fit": distance to the
    hole centre in columns}."""
    pl = g["places"]
    halves = blocks(pl)
    col, row = where(g, x, y, cell)
    flip = upside_down(g["img"], g, halves, cell)
    k = min(range(len(halves)), key=lambda i: min(abs(row - r) for r in halves[i]))
    first, last = extent(pl, [r for h_ in halves for r in h_])
    if first is None:
        return None
    idx = round(col) - first + 1  # 1 = the first hole column at the left of that half (in the flat image)
    n = last - first + 1
    if flip:  # turn the board the right way up: left becomes right, the upper half becomes the lower one
        idx, k = n - idx + 1, 1 - k
    # upright: the top half counts up left to right, the bottom half counts up right to left
    number = idx - LABEL_OFFSET if k == 0 else (n - idx + 1) - LABEL_OFFSET
    return {"column": number, "half": "t" if k == 0 else "b", "fit": round(abs(col - round(col)), 2), "n": n,
            "flip": flip, "row": round(row - halves[k][0], 1) if not flip else round(halves[k][-1] - row, 1)}


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

def numbered(photo_path, cell=26, margin=3):
    """The board flat, straightened by code, with every column of each half labelled in yellow with the number printed
    on the board for it (top half's numbers above it, bottom half's below it). The model then reads a label instead of
    counting holes. In the flat image the upper half always counts up left to right and the lower half right to left,
    whichever way up the photo was taken. Returns (JPEG bytes, info) or (None, why)."""
    g = best_grid(board.load(photo_path))
    if g is None:
        return None, "no grid"
    pl = g["places"]
    halves = blocks(pl)
    if len(halves) < 2:
        return None, "one half only"
    first, last = extent(pl, [r for h_ in halves for r in h_])
    k0 = g["img"].shape[1] / 2000  # best_grid's image may be smaller than 2000: cell is per grid step anyway
    top, bot = halves[0][0], halves[-1][-1]
    lo = g["lo"]  # the homography maps grid place p to (p - lo + 1) * 36
    T = np.array([[1, 0, (lo[0] - first + 1) * cell], [0, 1, (lo[1] - top + margin + 1) * cell], [0, 0, 1]], float)
    S = np.diag([cell / 36, cell / 36, 1.0])  # H maps to 36 px per step
    W, H = (last - first + 3) * cell, (bot - top + 2 * margin + 3) * cell
    flat = cv2.warpPerspective(g["img"], T @ S @ g["H"], (int(W), int(H)))
    band = cell
    out = cv2.copyMakeBorder(flat, band, band, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    up0, lo1 = halves[0][-1] - 4, halves[1][0] + 4  # each half is 5 rows (one may be missed in shadow)
    y = {0: (up0 - top + margin + 1) * cell + band - int(cell * 0.85),  # just above the upper half
         1: (lo1 - top + margin + 1) * cell + band + int(cell * 0.85)}  # just below the lower half
    for col in range(first, last + 1):
        idx = col - first + 1
        x = int((col - first + 2) * cell)
        for k in (0, 1):
            num = idx - LABEL_OFFSET if k == 0 else (COLUMNS - idx + 1) - LABEL_OFFSET
            t = str(num)
            (tw, th), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            yy = int(y[k])
            cv2.rectangle(out, (x - tw // 2 - 1, yy - th // 2 - 2), (x + tw // 2 + 1, yy + th // 2 + 2), (0, 230, 255), -1)
            cv2.putText(out, t, (x - tw // 2, yy + th // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    flip = upside_down(g["img"], g, halves)
    return buf.tobytes(), {"columns": last - first + 1, "holes": int(g["inliers"]), "size": out.shape[1::-1],
                           "upside_down": flip}


# ---- code finds the pin: the black connector on the straightened board ----------------------------------------------

def flat_board(photo_path, cell=36, margin=3):
    """The straightened board and how to read it: (flat BGR image, info) with info["col"](x, half) -> printed number,
    info["half_of"](y) -> 0 upper / 1 lower / None, the halves' y ranges, the grid's holes in flat pixels."""
    g = best_grid(board.load(photo_path))
    if g is None:
        return None, "no grid"
    pl = g["places"]
    halves = blocks(pl)
    if len(halves) < 2:
        return None, "one half only"
    first, last = extent(pl, [r for h_ in halves for r in h_])
    up0, lo1 = halves[0][-1] - 4, halves[1][0] + 4
    top = up0
    lo = g["lo"]
    T = np.array([[1, 0, (lo[0] - first + 1) * cell], [0, 1, (lo[1] - top + margin + 1) * cell], [0, 0, 1]], float)
    S = np.diag([cell / 36, cell / 36, 1.0])
    M = T @ S @ g["H"]
    W, H = (last - first + 3) * cell, (lo1 - top + 2 * margin + 3) * cell
    flat = cv2.warpPerspective(g["img"], M, (int(W), int(H)))
    yr = {0: ((margin + 1) * cell, (margin + 1 + 4) * cell),  # row centres of the upper half: first..last
          1: ((lo1 - 4 - top + margin + 1) * cell, (lo1 - top + margin + 1) * cell)}

    def idx_of(x):
        return x / cell - 1  # 1 = the board's first hole column

    def half_of(y):
        for k, (a, b) in yr.items():
            if a - 1.2 * cell <= y <= b + 1.2 * cell:
                return k
        return None
    hh, ww = g["img"].shape[:2]
    pc = cv2.perspectiveTransform(np.float32([[[ww / 2, hh / 2]]]), M)[0, 0]
    return flat, {"centre_flat": (float(pc[0]), float(pc[1])), "cell": cell, "idx_of": idx_of, "half_of": half_of, "yr": yr, "M": M, "img": g["img"],
                  "upside_down": upside_down(g["img"], g, halves), "first": first, "last": last}


def label(idx, k, shift=(0, 0)):
    """Hole column (1 = the board's first) -> the printed number on that half, with a per-half correction."""
    i = idx - shift[k]
    return i - LABEL_OFFSET if k == 0 else (COLUMNS - i + 1) - LABEL_OFFSET


def printed_shift(flat, info):
    """Do our column numbers sit under the board's own printed numbers (0, 5, 10 ... 60)? The printed numbers are a
    line of about 13 dark marks just outside each half (a line of holes has 65). Slide a strip over the 3 rows outside
    each half, keep the strip whose marks look like that, and compare the marks with the columns our numbering puts
    the printed numbers at (hole column 3, 8, 13 ...: idx = 3 mod 5, both halves). The median offset, rounded, is how
    far our numbering is out (usually 0). Returns ((upper shift, lower shift), how many marks each was based on)."""
    cell = info["cell"]
    shifts, used = [], []
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    for k in (0, 1):
        a, b = info["yr"][k]
        lo_, hi_ = (a - 3.5 * cell, a + 0.5 * cell) if k == 0 else (b - 0.5 * cell, b + 3.5 * cell)
        best = None
        for y0 in np.arange(max(0, lo_), max(0, hi_ - 0.8 * cell), cell / 6):
            band = gray[int(y0):int(y0 + 0.8 * cell)]
            if band.shape[0] < 5:
                continue
            bw = cv2.adaptiveThreshold(band, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, int(cell) | 1, 18)
            bw = cv2.dilate(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (int(cell * 0.45), 1)))
            n, _, st, cen = cv2.connectedComponentsWithStats(bw, 8)
            marks = [cen[i][0] for i in range(1, n) if 0.3 * cell < st[i, cv2.CC_STAT_WIDTH] < 1.6 * cell
                     and st[i, cv2.CC_STAT_HEIGHT] > 0.3 * cell]
            if 8 <= len(marks) <= 16:
                res = [((info["idx_of"](x) - 3) + 2.5) % 5 - 2.5 for x in marks]
                spread = float(np.median(np.abs(np.array(res) - np.median(res))))
                if best is None or spread < best[0]:
                    best = (spread, res)
        if best is None or best[0] > 0.35:  # no clear line of printed numbers
            shifts.append(0)
            used.append(0)
        else:
            shifts.append(int(round(float(np.median(best[1])))))
            used.append(len(best[1]))
    return tuple(shifts), tuple(used)


def connectors(flat, info):
    """Black connectors on the board: dark (not the holes, which are small) blobs over a half. For each: its centre,
    and the end away from where the coloured wire leaves it. Returns a list of dicts with flat-pixel points."""
    cell = info["cell"]
    hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 130, 75))
    # the connector's glossy top breaks it into pieces: close the gaps first (a hole stays a small square), then open
    # with a disc bigger than a hole and smaller than the connector
    kc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.35), int(cell * 0.35)))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kc)
    cnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    dark = cv2.drawContours(np.zeros_like(dark), cnts, -1, 255, -1)  # fill the highlights inside
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.6), int(cell * 0.6)))
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)  # the holes go, the connector stays
    sat = cv2.inRange(hsv, (0, 70, 50), (180, 255, 255))  # coloured wire (red, green, grey has low saturation: below)
    n, lab, st, cen = cv2.connectedComponentsWithStats(dark, 8)
    out = []
    for i in range(1, n):
        area = st[i, cv2.CC_STAT_AREA]
        if area < 0.6 * cell * cell or area > 12 * cell * cell:
            continue
        cx, cy = cen[i]
        if info["half_of"](cy) is None:
            continue
        ys, xs = np.nonzero(lab == i)
        pts = np.c_[xs, ys].astype(float)
        # where does the wire leave? the coloured (or any non-board) pixels just around the blob
        ring = cv2.dilate((lab == i).astype(np.uint8), np.ones((int(cell * 0.5),) * 2, np.uint8)) - (lab == i)
        wire = np.c_[np.nonzero(ring & (sat > 0))[::-1]].astype(float)
        far = None
        if len(wire) > 15:
            wc = wire.mean(0)
            far = pts[np.argmax(((pts - wc) ** 2).sum(1))]
            # the far end's middle: blob points within half a cell of the farthest point
            near = pts[((pts - far) ** 2).sum(1) < (0.5 * cell) ** 2]
            far = near.mean(0)
        # the base: a connector stands up from the board, so in a photo from above its top leans away from the point
        # under the camera (the photo's centre); the base (the pin) is the blob's end nearest that point, half the
        # connector's width in from it
        pc = info.get("centre_flat")
        base = None
        if pc is not None:
            u = np.array(pc) - np.array([cx, cy])
            if np.linalg.norm(u) > 1:
                u = u / np.linalg.norm(u)
                v = np.array([-u[1], u[0]])
                along, across = pts @ u, pts @ v
                width = np.percentile(across, 90) - np.percentile(across, 10)
                endpts = pts[along > along.max() - 0.3 * cell]
                base = endpts.mean(0) - u * width / 2
        out.append({"centre": (float(cx), float(cy)), "far": None if far is None else (float(far[0]), float(far[1])),
                    "base": None if base is None else (float(base[0]), float(base[1])),
                    "area": int(area), "half": info["half_of"](cy)})
    return out


def to_flat(info, x, y):
    p = cv2.perspectiveTransform(np.float32([[[x, y]]]), info["M"])[0, 0]
    return float(p[0]), float(p[1])


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
