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
    return np.abs(np.angle(np.exp(1j * (a - b)))) < tol


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
        ln = np.linalg.norm(v, axis=1)
        return np.median(v[ln < np.percentile(ln, 30) * 1.3], axis=0)
    s1, s2 = step(a1), step(a2)
    # walk the grid from the middle: each hole's place is a neighbour's place plus one step (or two or three across a
    # gap: the channel down the middle, the space before the rails)
    moves = [(k * s, (k * dv[0], k * dv[1])) for s, dv in ((s1, (1, 0)), (s2, (0, 1))) for k in (1, -1, 2, -2, 3, -3)]
    place = {}
    start = int(np.argmin(((c - np.median(c, 0)) ** 2).sum(1)))
    place[start] = (0, 0)
    queue = [start]
    reach = 3.4 * max(np.linalg.norm(s1), np.linalg.norm(s2))
    while queue:
        i = queue.pop()
        for j in np.where(dist[i] < reach)[0]:
            if j in place:
                continue
            v = c[j] - c[i]
            for sv, dv in moves:
                if np.linalg.norm(v - sv) < 0.3 * min(np.linalg.norm(s1), np.linalg.norm(s2)):
                    place[j] = (place[i][0] + dv[0], place[i][1] + dv[1])
                    queue.append(j)
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
