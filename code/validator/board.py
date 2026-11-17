"""The breadboard in a photo, made flat: every hole found and given its place in the grid (stage 1 of the step check).

The usual pipeline for checking a student's breadboard (perspective rectification -> where each lead goes in ->
netlist) starts here: OpenCV finds the holes (small dark squares on the white plastic), works out the grid they lie on
from the spacing between neighbours, and warps the photo to a flat, top-down board where every hole is at a known
spot. Then every column can be marked with a number on the image itself, so the model reads "the leg goes into the
column marked 13" instead of counting holes in a slanted photo (validator.arduino asks it; the netlist and the
verdict are CircuitQuest's logic, already there).

  holes(img)          the hole centres in the photo
  grid(centres)       each hole's (column, row) in the grid, and the grid's two step vectors
  flatten(img, ...)   the board warped flat (a homography from grid places to pixels)
Run: ./pinpoint validator.board <photo>   (writes <photo>.holes.jpg and <photo>.flat.jpg next to it, to look at)
"""
import sys

import cv2
import numpy as np


def holes(img):
    """The centres of the breadboard's holes: dark, small, square-ish blobs of about the same size, close together.
    Returns an (N, 2) float array (x, y) in the image's pixels."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    g = cv2.GaussianBlur(g, (3, 3), 0)
    # a hole is darker than the plastic around it: a local threshold finds it whatever the light
    block = max(15, int(min(h, w) / 60) | 1)
    bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 12)
    n, _, stats, cent = cv2.connectedComponentsWithStats(bw, 8)
    area = stats[1:, cv2.CC_STAT_AREA].astype(float)
    bw_, bh_ = stats[1:, cv2.CC_STAT_WIDTH].astype(float), stats[1:, cv2.CC_STAT_HEIGHT].astype(float)
    cent = cent[1:]
    ok = (area > 4) & (bw_ > 1) & (bh_ > 1) & (np.maximum(bw_, bh_) / np.minimum(bw_, bh_) < 2.2) \
        & (area / (bw_ * bh_) > 0.45)
    cand, a = cent[ok], area[ok]
    if len(cand) < 30:
        return cand
    # holes are all about the same size: keep the most common size band
    med = np.median(a)
    keep = (a > med / 3) & (a < med * 3)
    cand = cand[keep]
    # and they sit in a regular pattern: each has neighbours at about the same distance
    d = np.sqrt(((cand[:, None, :] - cand[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = np.sort(d, axis=1)[:, :2]
    pitch = np.median(nn[:, 0])
    good = (nn[:, 0] < pitch * 1.6) & (nn[:, 1] < pitch * 2.2)
    return cand[good]


def _ang(v):
    return np.arctan2(v[..., 1], v[..., 0])


def _close(a, b, tol):
    """Two directions within tol of each other; a direction and its reverse are the same (up = down: mod 180 degrees,
    or a board standing upright in the photo finds 'up' and 'down' as its two grid directions)."""
    return np.abs(np.angle(np.exp(2j * (a - b)))) / 2 < tol


def grid(c):
    """Each hole's integer place in the grid, from the step to its neighbours.
    Returns (indexes of the placed holes, places (N, 2) int: column along the board's long side, row across; the column
    step and the row step in pixels)."""
    d = c[None, :, :] - c[:, None, :]
    dist = np.sqrt((d ** 2).sum(-1))
    np.fill_diagonal(dist, np.inf)
    order = np.argsort(dist, axis=1)[:, :4]  # each hole's four nearest: its grid neighbours (not the diagonals)
    vec = d[np.arange(len(c))[:, None], order].reshape(-1, 2)
    vec[vec[:, 0] < 0] *= -1  # one half-plane: a step and its reverse are the same direction
    ang = _ang(vec)
    hist, edges = np.histogram(ang, bins=90, range=(-np.pi / 2, np.pi / 2))
    centres = (edges[:-1] + edges[1:]) / 2
    a1 = centres[np.argmax(hist)]
    other = np.where(~_close(centres, a1, np.radians(35)), hist, 0)
    a2 = centres[np.argmax(other)]

    def step(a):  # the shortest common step in that direction (not two holes on)
        v = vec[_close(ang, a, np.radians(8))]
        u = np.array([np.cos(a), np.sin(a)])
        v = np.where((v @ u < 0)[:, None], -v, v)  # up and down are one direction: point them all the same way
        ln = np.linalg.norm(v, axis=1)
        return np.median(v[ln < np.percentile(ln, 30) * 1.3], axis=0)
    s1, s2 = step(a1), step(a2)
    # walk the grid from the middle: each hole's place is a neighbour's place plus one step (or two or three across a
    # gap: the channel down the middle, the space before the rails)
    moves = [(k * s, (k * dv[0], k * dv[1])) for s, dv in ((s1, (1, 0)), (s2, (0, 1))) for k in (1, -1, 2, -2, 3, -3)]
    reach = 3.4 * max(np.linalg.norm(s1), np.linalg.norm(s2))
    tol = 0.3 * min(np.linalg.norm(s1), np.linalg.norm(s2))

    def walk(start):
        place = {start: (0, 0)}
        queue = [start]
        while queue:
            i = queue.pop()
            for j in np.where(dist[i] < reach)[0]:
                if j in place:
                    continue
                v = c[j] - c[i]
                for sv, dv in moves:
                    if np.linalg.norm(v - sv) < tol:
                        place[j] = (place[i][0] + dv[0], place[i][1] + dv[1])
                        queue.append(j)
                        break
        return place
    by_middle = np.argsort(((c - np.median(c, 0)) ** 2).sum(1))
    place = {}
    for start in [int(by_middle[0])] + [int(x) for x in by_middle[len(c) // 8::max(1, len(c) // 8)][:6]]:
        got = walk(start)
        if len(got) > len(place):
            place = got
        if len(place) > 0.6 * len(c):
            break
    idx = np.array(sorted(place))
    pl = np.array([place[i] for i in idx])
    if np.ptp(pl[:, 1]) > np.ptp(pl[:, 0]):  # the long side of the board is the column direction
        pl = pl[:, ::-1]
        s1, s2 = s2, s1
    if s1[0] < 0:  # columns run left to right in the photo, rows top to bottom: the flat board is not mirrored
        s1, pl = -s1, pl * [-1, 1]
    if s2[1] < 0:
        s2, pl = -s2, pl * [1, -1]
    return idx, pl, s1, s2


def flatten(img, c, idx, pl, cell=24):
    """The board warped flat: grid place (col, row) -> pixel (col * cell, row * cell), by a homography fitted to the
    holes (RANSAC: a few wrong holes do not matter). Returns (flat image, H from photo to flat, the grid's origin)."""
    src = c[idx].astype(np.float32)
    lo = pl.min(0)
    dst = ((pl - lo + 1) * cell).astype(np.float32)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, cell * 0.4)
    # the walk can miscount a gap (two rows or three across the channel), so one half fits and the other does not:
    # place every hole again from the fit (to the nearest grid point), fit again, a few times over
    allc = c.astype(np.float32).reshape(-1, 1, 2)
    for _ in range(4):
        g = cv2.perspectiveTransform(allc, H).reshape(-1, 2) / cell
        near = np.round(g)
        good = np.abs(g - near).max(1) < 0.3
        if good.sum() < 20:
            break
        H2, m2 = cv2.findHomography(c[good].astype(np.float32), (near[good] * cell).astype(np.float32), cv2.RANSAC, cell * 0.3)
        if H2 is None:
            break
        H, mask = H2, m2
    g = np.round(cv2.perspectiveTransform(allc, H).reshape(-1, 2) / cell)
    inl = np.abs(cv2.perspectiveTransform(allc, H).reshape(-1, 2) / cell - g).max(1) < 0.3
    pl = (g[inl] - 1).astype(int) + lo  # the places, from the final fit (for marking the columns)
    flatten.places = pl
    size = ((np.ptp(pl[:, 0]) + 3) * cell, (np.ptp(pl[:, 1]) + 3) * cell)
    return cv2.warpPerspective(img, H, (int(size[0]), int(size[1]))), H, lo, int(inl.sum())


def load(path):
    """The photo the way it was taken (phones store the rotation separately: EXIF), as an OpenCV image."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


# ---- is the photo good enough to read? (free, before any model looks) -------------------------------------------
# Limits from the learner's own photos (16-17 Nov: a column was 38-43 px wide in the full photo, sharpness 84-650,
# one end at most 1.24x the other): none of them is turned away; a product shot (8 px columns) or a strongly slanted
# photo (0.63) is.
MIN_HOLES = 100
MIN_COLUMN_PX = 22
MAX_SLANT = 1.45
MIN_SHARP = 40


def quality(photo_path):
    """Is the board in this photo good enough to read? (ok, what to tell the learner, measurements). Fast (about
    0.2 s) and free: the hole grid tells how far, how slanted and how sharp the board is."""
    img = load(photo_path)
    H0, W0 = img.shape[:2]
    f = min(1.0, 1600 / max(H0, W0))
    im = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else img
    c = holes(im)
    m = {"holes": int(len(c))}
    if len(c) < MIN_HOLES:
        return False, "I can't find the breadboard in that photo. Take it from above, with the board filling the screen.", m
    try:
        idx, pl, s1, s2 = grid(c)
    except Exception:
        return True, "", m  # the grid could not be worked out: let the model try rather than block the learner
    m.update(placed=int(len(idx)), column_px=round(float(np.linalg.norm(s1)) / f, 1))
    if len(idx) < 0.5 * len(c):  # the grid covers too little of what looked like holes (an Arduino's header pins,
        return True, "", m       # a pattern on the table): not sure enough to turn the photo away
    if m["column_px"] < MIN_COLUMN_PX:
        return False, "The board is too far away to read the columns. Move closer, so the board fills the screen.", m
    cols = pl[:, 0]
    ends = []
    for sel in (cols <= np.percentile(cols, 15), cols >= np.percentile(cols, 85)):
        pts = c[idx][sel]
        if len(pts) > 3:
            d = np.sqrt(((pts[:, None] - pts[None]) ** 2).sum(-1))
            np.fill_diagonal(d, np.inf)
            ends.append(float(np.median(d.min(1))))
    if len(ends) == 2 and min(ends) > 0:
        m["slant"] = round(max(ends) / min(ends), 2)
        if m["slant"] > MAX_SLANT:
            return False, "The photo is too slanted. Hold the phone straight above the board.", m
    hull = cv2.convexHull(c.astype(np.float32))
    x0, y0, w, h = cv2.boundingRect(hull.astype(np.int32))
    m["sharp"] = round(float(cv2.Laplacian(cv2.cvtColor(im[y0:y0 + h, x0:x0 + w], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()))
    if m["sharp"] < MIN_SHARP:
        return False, "The photo is blurry. Hold the phone still and tap the screen to focus before you take it.", m
    return True, "", m


def arduino_box(im):
    """The Arduino in a frame, by its blue circuit board (Uno, Duemilanove and most clones are blue): its box as
    fractions of the frame and whether it touches an edge, or None (no big blue patch: not in the photo, or a board
    of another colour). The breadboard's thin blue rail lines are opened away."""
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (96, 55, 25), (128, 255, 235))  # dark blue PCB (measured on a Duemilanove: H 105, S 80, V 84)
    k = max(5, int(min(im.shape[:2]) * 0.02)) | 1
    blue = cv2.morphologyEx(blue, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))  # its printing
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))  # the rail lines
    n, lab, stats, _ = cv2.connectedComponentsWithStats(blue)
    H, W = im.shape[:2]
    best = None
    for x, y, w, h, area in stats[1:]:
        # an Arduino is a solid rectangle, about 1.3 : 1, a few percent of the frame (not jeans or a blue cloth)
        if area < 0.012 * W * H or w * h > 0.3 * W * H:
            continue
        solid, aspect = area / (w * h), max(w, h) / max(1, min(w, h))
        if solid < 0.55 or aspect > 2.0:
            continue
        if best is None or area > best[4]:
            best = (x, y, w, h, area)
    if best is None:
        return None
    x, y, w, h, area = best
    e = 0.01
    return {"box": [round(x / W, 3), round(y / H, 3), round((x + w) / W, 3), round((y + h) / H, 3)],
            "cut": bool(x < e * W or y < e * H or x + w > (1 - e) * W or y + h > (1 - e) * H)}


def frame_hint(photo_path, arduino=False, min_pitch=18):
    """For the live camera (a frame about once a second): is the board ready to be photographed, and if not, what
    to do, in two or three words. Uses only what is reliable on real photos: the holes found (how many, how far
    apart = how close the board is, where they are = how much of the frame the board fills and whether it is in
    the middle) and how sharp they are; not the hole grid, which often places only part of a real board.
    Returns {"ok", "hint", "measure"}. Free, about 0.2 s."""
    img = load(photo_path)
    H0, W0 = img.shape[:2]
    f = min(1.0, 1200 / max(H0, W0))
    im = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else img
    H, W = im.shape[:2]
    c = holes(im)
    m = {"holes": int(len(c))}
    if len(c) < MIN_HOLES:
        return {"ok": False, "hint": "Find the breadboard", "measure": m}
    d = np.sqrt(((c[:, None] - c[None]) ** 2).sum(-1)) if len(c) <= 2500 else None
    if d is not None:
        np.fill_diagonal(d, np.inf)
        m["pitch_px"] = round(float(np.median(d.min(1))) / f, 1)  # the distance between holes, in the photo
    # the board's extent: the middle 96% of the holes (a few stray dots on the table do not count)
    x0, x1 = np.percentile(c[:, 0], [2, 98])
    y0, y1 = np.percentile(c[:, 1], [2, 98])
    fill = max((x1 - x0) / W, (y1 - y0) / H)  # along the board's long side
    cx, cy = (x0 + x1) / 2 / W - 0.5, (y0 + y1) / 2 / H - 0.5
    g = cv2.cvtColor(im[int(y0):int(y1) + 1, int(x0):int(x1) + 1], cv2.COLOR_BGR2GRAY)
    m.update(fill=round(float(fill), 2), off=[round(float(cx), 2), round(float(cy), 2)],
             sharp=round(float(cv2.Laplacian(g, cv2.CV_64F).var())))
    # the board fills most of the frame; less when the Arduino must be in the photo too (beside it)
    if fill < (0.45 if arduino else 0.6) or m.get("pitch_px", 99) < min_pitch:
        return {"ok": False, "hint": "Closer", "measure": m}
    edge = 0.015  # the board cut off at an edge of the frame: move the phone that way
    cut = [(x0 / W < edge, "Move left"), (x1 / W > 1 - edge, "Move right"), (y0 / H < edge, "Move up"), (y1 / H > 1 - edge, "Move down")]
    if any(c for c, _ in cut):
        return {"ok": False, "hint": next(h for c, h in cut if c), "measure": m}
    if not arduino and (abs(cx) > 0.12 or abs(cy) > 0.12):  # alone, the board sits in the middle
        hint = ("Move left" if cx < 0 else "Move right") if abs(cx) >= abs(cy) else ("Move up" if cy < 0 else "Move down")
        return {"ok": False, "hint": hint, "measure": m}
    if arduino:  # the Arduino must be in the photo too, whole: found by its blue board (free)
        a = arduino_box(im)
        m["arduino"] = a
        if a is None:
            return {"ok": False, "hint": "Get the Arduino in too", "soft": True, "measure": m}
        if a["cut"]:
            return {"ok": False, "hint": "Move back: the Arduino is cut off", "measure": m}
    if m["sharp"] < MIN_SHARP:
        return {"ok": False, "hint": "Hold still, tap to focus", "measure": m}
    return {"ok": True, "hint": "Hold still", "measure": m}


def mark(flat, pl, cell=36, band=40):
    """Number every column on the flat board (1 = the leftmost found), in a band above and below and in the channel
    down the middle, so the model reads the marker of the column a leg goes into instead of counting holes.
    Returns (marked image, the column numbers' x positions in it)."""
    h, w = flat.shape[:2]
    out = cv2.copyMakeBorder(flat, band, band, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cols = range(int(pl[:, 0].min()), int(pl[:, 0].max()) + 1)
    rows = sorted(set(int(r) for r in pl[:, 1]))
    gaps = [r for r in range(rows[0], rows[-1]) if r not in rows]  # the channel and the rail gaps: no holes
    mid = sorted(gaps, key=lambda r: abs(r - (rows[0] + rows[-1]) / 2))[:1]
    xs = {}
    lo = pl.min(0)
    for k, col in enumerate(cols, 1):
        x = int((col - lo[0] + 1) * cell)
        xs[k] = x
        t = str(k)
        (tw, th), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        for y in [band // 2 + th // 2, h + band + band // 2 + th // 2] + [int((r - lo[1] + 1) * cell) + band + th // 2 for r in mid]:
            cv2.rectangle(out, (x - tw // 2 - 2, y - th - 2), (x + tw // 2 + 2, y + 3), (0, 220, 255), -1)
            cv2.putText(out, t, (x - tw // 2, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return out, xs


def flat_marked(photo_path, cell=36):
    """The photo's board, flat and with every column numbered: (image, how many holes agreed) or (None, 0)."""
    img = load(photo_path)
    if max(img.shape[:2]) > 2000:
        f = 2000 / max(img.shape[:2])
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    c = holes(img)
    if len(c) < 60:
        return None, 0
    idx, pl, _, _ = grid(c)
    if len(idx) < 60:
        return None, 0
    flat, H, lo, inliers = flatten(img, c, idx, pl, cell=cell)
    out, _ = mark(flat, flatten.places, cell=cell)
    return out, inliers


def main(path):
    img = load(path)
    img = cv2.resize(img, None, fx=1600 / max(img.shape[:2]), fy=1600 / max(img.shape[:2])) if max(img.shape[:2]) > 1600 else img
    c = holes(img)
    print(f"{len(c)} holes found")
    out = img.copy()
    for x, y in c.astype(int):
        cv2.circle(out, (x, y), 3, (0, 0, 255), -1)
    cv2.imwrite(path + ".holes.jpg", out)
    idx, pl, s1, s2 = grid(c)
    print(f"{len(idx)} holes placed in the grid: {np.ptp(pl[:, 0]) + 1} columns x {np.ptp(pl[:, 1]) + 1} rows; steps {s1.round(1)} {s2.round(1)}")
    flat, H, lo, inliers = flatten(img, c, idx, pl, cell=36)
    print(f"flattened with {inliers} holes agreeing")
    cv2.imwrite(path + ".flat.jpg", mark(flat, flatten.places, cell=36)[0])


if __name__ == "__main__":
    main(sys.argv[1])
