"""Geometry for the step check: the breadboard's holes give an exact grid, so code counts columns.

The board is straightened from its holes (board.holes -> board.grid -> a homography), its two halves and its ends are
found, and every hole column gets the number printed on the board for it. Then:
  numbered_board(...)  the straightened board with every column's number written in yellow: the model reads a number
                       instead of counting holes (the model's usual mistake is one column off)
  read_ends(...)       code finds every jumper-wire connector (a dark blob bigger than a hole) and its column; it is
                       "sure" when three estimates of where the pin is agree (the blob's middle, its end away from the
                       wire, and its base by camera geometry: a connector stands up, so its top leans away from the
                       point under the camera)
  analyse(photo)       both, from one grid, with `trusted` (the board looks like the one the numbers are for)
Measured on 21 labelled photos of the learner's board (17 Nov 2026, PHOTO_TUNING.md sections 7-8): geometry first,
the model only where code is not sure: Opus 21/21 columns, Haiku 18/21.

Board: the learner's 830-hole board, 65 hole columns, printed 0 ... 60 with the number = hole column - 3; the bottom
half is printed the other way round (60 at the left). printed_shift checks the numbers against the printed marks.
"""
import cv2
import numpy as np

from validator import board

COLUMNS = 65  # this board (measured on the labelled photos)


LABEL_OFFSET = 3  # this board: printed number = hole count from the end minus 3 (measured on the labelled photos)


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


def best_grid(img, sizes=(2000, 1400, 1000)):
    """The grid at a few photo sizes (the hole finder's local threshold suits some sizes better): the one that places
    the most holes."""
    best = None
    cv2.setRNGSeed(0)  # the homography's RANSAC samples at random: the same photo must always give the same grid
    for E in sizes:
        im = cv2.resize(img, None, fx=E / max(img.shape[:2]), fy=E / max(img.shape[:2]), interpolation=cv2.INTER_AREA)
        try:
            g = board_grid(im)
        except (cv2.error, ValueError, IndexError):
            g = None
        if g and (best is None or g["inliers"] > best["inliers"]):
            best = g
    return best


def where(g, x, y, cell=36):
    """A photo point -> (grid column, grid row) as floats, in the grid's own counting."""
    p = cv2.perspectiveTransform(np.float32([[[x, y]]]), g["H"])[0, 0] / cell - 1 + g["lo"]
    return float(p[0]), float(p[1])


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


def flat_board(photo_path, cell=36, margin=3, g=None, src=None, flip=False):
    """The straightened board and how to read it: (flat BGR image, info) with info["idx_of"](x) -> hole column (1 =
    the board's first), info["half_of"](y) -> 0 upper / 1 lower / None, the halves' row-centre y ranges ("yr"), M (photo
    -> flat). g: a grid already found (best_grid); src: the full-size photo to cut from (sharper close-ups; g was found
    on a smaller copy); flip: turned half round (the board is printed the same both ways round, so the halves and the
    numbers read the same; see analyse)."""
    if g is None:
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
    T = np.array([[1, 0, (lo[0] - first + 1) * cell], [0, 1, (lo[1] - top + margin) * cell], [0, 0, 1]], float)
    S = np.diag([cell / 36, cell / 36, 1.0])
    W, H = (last - first + 3) * cell, (lo1 - top + 2 * margin + 2) * cell  # the same margin all round
    M = T @ S @ g["H"]
    img = g["img"]
    if src is not None:  # from the full-size photo: g's homography is for the smaller copy
        r = g["img"].shape[1] / src.shape[1]
        M = M @ np.diag([r, r, 1.0])
        img = src
    if flip:
        M = np.array([[-1, 0, W], [0, -1, H], [0, 0, 1]], float) @ M
    flat = cv2.warpPerspective(img, M, (int(W), int(H)))
    yr = {0: ((margin + 1) * cell, (margin + 1 + 4) * cell),  # row centres of the upper half: first..last
          1: ((lo1 - 4 - top + margin + 1) * cell, (lo1 - top + margin + 1) * cell)}

    def idx_of(x):
        return x / cell - 1  # 1 = the board's first hole column

    def half_of(y):
        for k, (a, b) in yr.items():
            if a - 1.2 * cell <= y <= b + 1.2 * cell:
                return k
        return None
    hh, ww = img.shape[:2]
    pc = cv2.perspectiveTransform(np.float32([[[ww / 2, hh / 2]]]), M)[0, 0]
    return flat, {"centre_flat": (float(pc[0]), float(pc[1])), "cell": cell, "idx_of": idx_of, "half_of": half_of,
                  "yr": yr, "M": M, "img": img, "g": g, "first": first, "last": last, "flip": flip,
                  "upside_down": False}  # turned round already when flip


def occupied(flat, info):
    """Where things sit on the board: per half, per hole column, how much more of it is covered than the board's usual
    column (so shade and the light's colour cancel out): parts are much more coloured than the board around them
    (resistor bodies, LEDs, wires) or much darker (black connectors, bigger than a hole). Returns {0: array, 1: array},
    index 0 = hole column 1; above about 0.08 = something is there."""
    cell = info["cell"]
    hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    n = info["last"] - info["first"] + 1
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.6),) * 2)
    out = {}
    for h, (a, b) in info["yr"].items():
        band = hsv[int(a - 0.5 * cell):int(b + 0.5 * cell), int(1.5 * cell):int((n + 1.5) * cell)]
        if band.size == 0:
            out[h] = np.zeros(n)
            continue
        S, V = band[..., 1].astype(float), band[..., 2].astype(float)
        colour = S > max(90, np.median(S) + 50)
        dark = cv2.morphologyEx((V < 0.45 * np.median(V)).astype(np.uint8), cv2.MORPH_OPEN, k) > 0  # not holes
        stuff = colour | dark
        col = np.array([stuff[:, int(i * cell):int((i + 1) * cell)].mean() for i in range(n)])
        out[h] = np.clip(col - np.median(col), 0, 1)
    return out



def to_flat(info, x, y):
    p = cv2.perspectiveTransform(np.float32([[[x, y]]]), info["M"])[0, 0]
    return float(p[0]), float(p[1])


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


def leds(flat, info, shift=(0, 0)):
    """LEDs on the board, and where their legs go in even when the body hides them. The body is a coloured dome
    (5 mm across, about 8.6 mm tall): a saturated blob two cells wide. Seen from above, its top leans away from the
    point under the camera, so its base is the blob's end nearest that point, half its width in (as a connector's).
    Its legs leave the base 2.54 mm apart, one column: half a column either side of the base's centre (an LED sits
    across two columns, its legs along the row). Returns [{"columns": [a, b], "half", "sure", "base", "legs_x",
    "outline"}]: sure when the base's centre falls clearly between two columns."""
    cell = info["cell"]
    hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    S, V = hsv[..., 1], hsv[..., 2]
    body = ((S > max(90, float(np.median(S)) + 50)) & (V > 60)).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.8),) * 2)  # thinner than this goes: wires, bands
    body = cv2.morphologyEx(cv2.morphologyEx(body, cv2.MORPH_CLOSE, k), cv2.MORPH_OPEN, k)
    cnts, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        area = cv2.contourArea(c)
        if not 1.5 * cell * cell <= area <= 12 * cell * cell:
            continue
        hull = cv2.contourArea(cv2.convexHull(c))
        if hull <= 0 or area / hull < 0.8:
            continue
        (x, y), (w, h), _ = cv2.minAreaRect(c)
        if max(w, h) > 3.2 * min(w, h):  # a dome leans into an oval, not a long strip
            continue
        pts = c.reshape(-1, 2).astype(float)
        cx, cy = pts.mean(0)
        pc = info.get("centre_flat")
        base = np.array([cx, cy])
        if pc is not None:
            u = np.array(pc) - base
            if np.linalg.norm(u) > 1:
                u = u / np.linalg.norm(u)
                v = np.array([-u[1], u[0]])
                width = np.percentile(pts @ v, 95) - np.percentile(pts @ v, 5)
                ends = pts[pts @ u > (pts @ u).max() - 0.3 * cell]
                base = ends.mean(0) - u * width / 2
        kh = info["half_of"](base[1])
        if kh is None:
            continue
        i = base[0] / cell - 1  # hole column, fractional
        legs = [i - 0.5, i + 0.5]
        frac = i - np.floor(i)
        half = ("bottom" if kh == 0 else "top") if info["upside_down"] else ("top" if kh == 0 else "bottom")
        out.append({"columns": sorted(int(label(round(l), kh, shift)) for l in legs), "half": half,
                    "sure": bool(abs(frac - 0.5) < 0.25), "base": (float(base[0]), float(base[1])),
                    "legs_x": [float((l + 1) * cell) for l in legs], "outline": pts.tolist()})
    return out


def hole_x(col, k, info, shift=(0, 0)):
    """A printed column on half k -> its x in the flat image (label's inverse)."""
    i = col + LABEL_OFFSET + shift[0] if k == 0 else COLUMNS + 1 - (col + LABEL_OFFSET) + shift[1]
    return (i + 1) * info["cell"]


def led_legs_side(flat, info, shift=(0, 0), near=None):
    """An LED's legs in a low photo from the side, straightened (flat_board works at any angle: the board is flat).
    A leg's tip is at board level, so it lands on its true hole; the body is lifted, so it is smeared away from the
    camera, and from low down the legs are seen under it: thin grey lines from the body into the board. Each leg is
    the grey line touching the body; its end farthest from the body is in its hole (the nearest hole to that end).
    near: the printed columns the photo from above saw the body over ([first, last]): the body must be there (a
    red rail line is coloured too). Returns {"columns": [a, b], "half", "rows", "sure", "why", "debug": image} or
    None (no body)."""
    cell = info["cell"]
    hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    S, V = hsv[..., 1], hsv[..., 2]
    body = ((S > max(90, float(np.median(S)) + 50)) & (V > 50)).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.8),) * 2)
    body = cv2.morphologyEx(cv2.morphologyEx(body, cv2.MORPH_CLOSE, k), cv2.MORPH_OPEN, k)
    n, lab, st, cen = cv2.connectedComponentsWithStats(body, 8)
    def fits(i):
        w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if not 1.5 * cell * cell <= st[i, cv2.CC_STAT_AREA] <= 30 * cell * cell or max(w, h) > 3.5 * min(w, h):
            return False
        if near:  # over the columns seen from above (either half: the side photo may be the other way round)
            x = cen[i][0]
            return any(min(hole_x(c, k, info, shift) for c in near) - 3 * cell <= x <=
                       max(hole_x(c, k, info, shift) for c in near) + 3 * cell for k in (0, 1))
        return True
    blobs = [i for i in range(1, n) if fits(i)]
    if not blobs:
        return None
    b = max(blobs, key=lambda i: st[i, cv2.CC_STAT_AREA])
    bmask = (lab == b).astype(np.uint8)
    bx, by = cen[b]
    # the board's own brightness around each point, so shade does not count as a leg
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY).astype(float)
    local = cv2.medianBlur(gray.astype(np.uint8), int(cell * 1.5) | 1).astype(float)
    dark = (gray < 0.78 * local) & (S < 80)
    # the holes are dark too: blank a square at every hole (a leg's tip is at a hole's edge, its line runs between)
    holes = np.zeros_like(bmask)
    xs = [(i + 1) * cell for i in range(info["last"] - info["first"] + 3)]
    rows_y = {}
    for kh, (a, z) in info["yr"].items():
        for r in range(5):
            y = a + r * cell
            rows_y[(kh, r)] = y
            for x in xs:
                h = int(cell * 0.27)
                holes[int(y) - h:int(y) + h + 1, int(x) - h:int(x) + h + 1] = 1
    legs = (dark & (holes == 0) & (cv2.dilate(bmask, np.ones((3, 3), np.uint8)) == 0)).astype(np.uint8)
    legs = cv2.morphologyEx(legs, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    # only next to the body: within 4 cells of it (the clear collar under the coloured dome breaks the line)
    win = cv2.dilate(bmask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 8),) * 2))
    legs = legs & (win > 0).astype(np.uint8)
    # a leg's pieces (cut by the blanked holes and highlights) joined into one line
    joined = cv2.dilate(legs, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 0.5),) * 2))
    near_body = cv2.dilate(bmask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(cell * 2.2),) * 2))
    m, ll, ls, _ = cv2.connectedComponentsWithStats(joined, 8)
    found = []
    for i in range(1, m):
        comp = (ll == i) & (legs > 0)
        size = int(comp.sum())
        if size < 0.12 * cell * cell or not ((ll == i) & (near_body > 0)).any():
            continue
        ys, xs_ = np.nonzero(comp)
        pts = np.c_[xs_, ys].astype(float)
        far = pts[np.argmax(((pts - [bx, by]) ** 2).sum(1))]
        reach = float(np.sqrt(((far - [bx, by]) ** 2).sum()))
        found.append((reach, far, size))
    dbg = flat.copy()
    cv2.drawContours(dbg, cv2.findContours(bmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], -1, (255, 0, 255), 2)
    dbg[legs > 0] = (0, 200, 255)
    found.sort(key=lambda f: -f[2])
    tips = []
    for reach, far, area in found[:2]:
        # the hole the tip is in: the nearest hole centre to the far end
        best = min(((abs(x - far[0]) + abs(y - far[1]), x, y, kh, r) for (kh, r), y in rows_y.items() for x in xs))
        _, x, y, kh, r = best
        col = int(label(round(x / cell - 1), kh, shift))
        tips.append((col, kh, r))
        cv2.circle(dbg, (int(x), int(y)), int(cell * 0.4), (0, 0, 255), 3)
    if len(tips) < 2:
        return {"columns": None, "half": None, "rows": None, "sure": False, "why": f"{len(tips)} leg(s) seen",
                "debug": dbg}
    kh = tips[0][1]
    half = ("bottom" if kh == 0 else "top") if info["upside_down"] else ("top" if kh == 0 else "bottom")
    rows = ["ABCDE"[r] if k_ == 0 else "FGHIJ"[r] for _, k_, r in tips]
    sure = tips[0][1] == tips[1][1] and tips[0][0] != tips[1][0]
    return {"columns": sorted(t[0] for t in tips), "half": half, "rows": rows, "sure": sure, "why": "", "debug": dbg}


def read_ends(photo_path):
    """Every wire end code can find: [{"column", "half": "top"/"bottom", "sure", "candidates", "at": flat point}].
    sure = the connector's middle, its end away from the wire and its base (camera geometry) give the same column.
    Returns (ends, info) or ([], why)."""
    flat, info = flat_board(photo_path)
    if flat is None:
        return [], info
    shift, _ = printed_shift(flat, info)
    out = []
    for c in connectors(flat, info):
        k = c["half"]
        cols = {key: label(round(info["idx_of"](pt[0])), k, shift)
                for key, pt in (("centre", c["centre"]), ("far", c["far"]), ("base", c["base"])) if pt is not None}
        vals = list(cols.values())
        col = cols.get("base", cols["centre"])
        half = ("bottom" if k == 0 else "top") if info["upside_down"] else ("top" if k == 0 else "bottom")
        big = c["area"] >= 1.0 * info["cell"] ** 2  # a connector is at least a cell; smaller dark blobs are shadows
        out.append({"column": col, "half": half, "sure": big and len(vals) == 3 and len(set(vals)) == 1,
                    "candidates": sorted(set(vals)), "at": c["centre"], "upper": k == 0})
    return out, info


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
    T = np.array([[1, 0, (lo[0] - first + 1) * cell], [0, 1, (lo[1] - top + margin) * cell], [0, 0, 1]], float)
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
                           "upside_down": False}  # turned round already when flip


def numbered_from(flat, info, shift=(0, 0)):
    """The straightened board (flat_board) with every column's printed number in yellow: the upper half's numbers in a
    row just above it, the lower half's just below it. JPEG bytes."""
    cell = info["cell"]
    band = cell
    out = cv2.copyMakeBorder(flat, band, band, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    ys = {0: info["yr"][0][0] + band - 0.85 * cell, 1: info["yr"][1][1] + band + 0.85 * cell}
    for idx in range(1, info["last"] - info["first"] + 2):
        x = int((idx + 1) * cell)
        for k in (0, 1):
            t = str(label(idx, k, shift))
            (tw, th), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            y = int(ys[k])
            cv2.rectangle(out, (x - tw // 2 - 1, y - th // 2 - 2), (x + tw // 2 + 1, y + th // 2 + 2), (0, 230, 255), -1)
            cv2.putText(out, t, (x - tw // 2, y + th // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def analyse(photo_path, cell=30, closeup_cell=56, around=None):
    """Geometry for one step photo, from one grid: {"trusted", "why", "numbered" (the whole board straightened with
    every column's number, JPEG), "closeup" (the part of it where things sit, cut from the full-size photo, bigger,
    numbered, JPEG), "ends" (read_ends' list), "shift", "marks"}. trusted: the board has this board's 65 columns and
    its printed numbers, where they can be seen, sit where our numbering puts them (at most one column out,
    corrected). When it is not trusted nothing from geometry is used and the check runs as before.
    Which half is "top": this board is printed the same both ways round (its rails clip on either way too, so their
    colours don't tell), so the halves can't be told apart from the board itself. The half the parts are on is the
    top half (blink and most first lessons build in one half); the image is turned round to put it on top."""
    try:
        full = board.load(photo_path)
        g = best_grid(full)
        flat, info = flat_board(photo_path, cell=cell, g=g)
        if flat is None:
            return {"trusted": False, "why": info, "numbered": None, "closeup": None, "ends": []}
        occ = occupied(flat, info)
        flip = bool(occ[1].sum() > 1.3 * occ[0].sum() and occ[1].max() > 0.08)
        if flip:
            flat, info = flat_board(photo_path, cell=cell, g=g, flip=True)
            occ = occupied(flat, info)
    except Exception as e:  # never let geometry break a check
        return {"trusted": False, "why": f"error: {e}", "numbered": None, "closeup": None, "ends": []}
    shift, marks = printed_shift(flat, info)
    seen = [s_ for s_, m in zip(shift, marks) if m]
    trusted = info["last"] - info["first"] + 1 == COLUMNS and bool(seen) and all(abs(s_) <= 1 for s_ in seen)
    why = "" if trusted else ("the printed numbers could not be found" if not seen else
                              f"the printed numbers are {shift} columns from where they should be")
    out = {"trusted": trusted, "why": why, "shift": shift, "marks": marks, "flipped": flip, "ends": [],
           "numbered": None, "closeup": None, "upside_down": False}
    if not trusted:
        return out
    out["ends"] = _ends(flat, info, shift)
    out["numbered"] = numbered_from(flat, info, shift)
    # the close-up: the columns where something sits (both halves), 4 columns either side, from the full-size photo
    busy = np.where(np.maximum(occ[0], occ[1]) > 0.08)[0]
    if around:  # printed columns to centre on (an LED seen in another photo), on whichever half they are
        opts = []
        for k in (0, 1):  # the half where something sits over those columns
            ix = np.array(sorted({int(round(hole_x(c, k, info, shift) / info["cell"] - 1)) - 1 for c in around}))
            ix = ix[(ix >= 0) & (ix < len(occ[0]))]
            opts.append((float(np.maximum(occ[0], occ[1])[ix].sum()) if len(ix) else -1, k, ix))
        # an LED's coloured body in this photo says which: in a photo from the side the lifted body smears over
        # the far half, so where things "sit" is not enough there
        seen = [l["base"][0] / info["cell"] - 2 for l in leds(flat, info, shift)]
        near_led = [o for o in opts if len(o[2]) and any(o[2].min() - 3 <= x <= o[2].max() + 3 for x in seen)]
        busy = (near_led[0] if len(near_led) == 1 else max(opts, key=lambda o: o[0]))[2]
    try:
        hi, hinfo = flat_board(photo_path, cell=closeup_cell, g=g, src=full, flip=flip)
        pic = cv2.imdecode(np.frombuffer(numbered_from(hi, hinfo, shift), np.uint8), cv2.IMREAD_COLOR)
        if len(busy):
            a, b = max(0, busy.min() - 4), min(len(occ[0]) - 1, busy.max() + 4)
            if b - a < 16:  # at least 17 columns, so the printed numbers either side are in it
                a, b = max(0, (a + b) // 2 - 8), min(len(occ[0]) - 1, (a + b) // 2 + 8)
            pic = pic[:, int((a + 1.5) * closeup_cell):int((b + 2.5) * closeup_cell)]
            out["closeup_columns"] = [int(label(a + 1, 0, shift)), int(label(b + 1, 0, shift))]
        ok, buf = cv2.imencode(".jpg", pic, [cv2.IMWRITE_JPEG_QUALITY, 90])
        out["closeup"] = buf.tobytes()
    except Exception:
        pass
    return out


def _ends(flat, info, shift):
    out = []
    for c in connectors(flat, info):
        k = c["half"]
        cols = {key: label(round(info["idx_of"](pt[0])), k, shift)
                for key, pt in (("centre", c["centre"]), ("far", c["far"]), ("base", c["base"])) if pt is not None}
        vals = list(cols.values())
        big = c["area"] >= 1.0 * info["cell"] ** 2
        half = ("bottom" if k == 0 else "top") if info["upside_down"] else ("top" if k == 0 else "bottom")
        out.append({"column": cols.get("base", cols["centre"]), "half": half,
                    "sure": big and len(vals) == 3 and len(set(vals)) == 1, "candidates": sorted(set(vals))})
    return out
