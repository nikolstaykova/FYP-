"""v9 LEGO: draw placed pieces from the booklet's viewpoint, so geometry can check Claude's placements against the
booklet picture (render and compare).

  camera      orthographic, like LEGO's isometric drawings: turned `az` degrees about the vertical, tipped `el` degrees
              towards the viewer, `scale` pixels per LDU, shifted by (tx, ty)
  draw        each piece as its real box (LDraw, top studs left out), faces filled in the piece's colour, back to front
  fit_camera  the camera under which the drawn model's outline best covers the model in the booklet picture
  object_mask the model in a booklet picture: pixels that differ from the page background
"""
import functools
import gzip
import csv
import math
import pathlib


import ldraw_geometry as geo

import truth

ROOT = pathlib.Path(__file__).resolve().parents[3]
FACES = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]


@functools.lru_cache(maxsize=None)
def _rebrickable_rgb():
    with gzip.open(ROOT / "data" / "sources" / "rebrickable" / "colors.csv.gz", "rt") as f:
        return {r["name"].lower(): tuple(int(r["rgb"][i:i + 2], 16) for i in (0, 2, 4)) for r in csv.DictReader(f)}


@functools.lru_cache(maxsize=None)
def _ldraw_rgb():
    out = {}
    text = geo._zip().read("ldraw/LDConfig.ldr").decode("utf-8", "replace")
    for line in text.splitlines():
        b = line.split()
        if len(b) > 6 and b[:2] == ["0", "!COLOUR"] and "CODE" in b and "VALUE" in b:
            v = b[b.index("VALUE") + 1].lstrip("#")
            out[b[b.index("CODE") + 1]] = tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    return out


def rgb(colour):
    """An LDraw colour code ('15') or a Rebrickable colour name ('White') -> (r, g, b); grey if unknown."""
    c = str(colour)
    return _ldraw_rgb().get(c) or _rebrickable_rgb().get(c.lower()) or (160, 160, 160)


def corners(part, pos, rot):
    b = geo.box(part)
    if b is None:
        return None
    return [[pos[i] + truth._apply(rot, [x, y, z])[i] for i in range(3)]
            for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]


def view(az, el):
    """Rotation taking LDraw world coordinates to the view: x right, y down on the page, z away from the viewer."""
    a, e = math.radians(az), math.radians(el)
    ry = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    rx = [[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]]
    return truth._mul(rx, ry)


def project(points, cam):
    r = view(cam["az"], cam["el"])
    out = []
    for p in points:
        q = truth._apply(r, p)
        out.append((q[0] * cam["scale"] + cam["tx"], q[1] * cam["scale"] + cam["ty"], q[2]))
    return out


def draw(pieces, cam, shape, background=(255, 255, 255), only=None):
    """pieces: [(id, part, pos, rot, colour)] -> (BGR image, {id: mask}) of the pieces drawn under `cam`, nearest on
    top. only: ids whose masks to return (default all)."""
    import cv2
    import numpy as np
    img = np.zeros((shape[0], shape[1], 3), np.uint8)
    img[:] = background[::-1]
    polys = []
    shade = {0: 0.75, 1: 0.75, 2: 1.0, 3: 0.55, 4: 0.85, 5: 0.65}
    for nid, part, pos, rot, colour in pieces:
        c = corners(part, pos, rot)
        if not c:
            continue
        p = project(c, cam)
        r, g, b = rgb(colour)
        for k, f in enumerate(FACES):
            pts = [p[i] for i in f]
            polys.append((sum(q[2] for q in pts) / 4, nid, [(q[0], q[1]) for q in pts],
                          (b * shade[k], g * shade[k], r * shade[k])))
    masks = {}
    for depth, nid, pts, bgr in sorted(polys, key=lambda t: -t[0]):  # far first
        arr = np.array(pts, np.int32)
        cv2.fillConvexPoly(img, arr, tuple(int(v) for v in bgr))
        if only is None or nid in only:
            m = masks.setdefault(nid, np.zeros(shape[:2], np.uint8))
            cv2.fillConvexPoly(m, arr, 1)
    return img, masks


def silhouette(pieces, cam, shape):
    import cv2
    import numpy as np
    m = np.zeros(shape[:2], np.uint8)
    for nid, part, pos, rot, _ in pieces:
        c = corners(part, pos, rot)
        if c:
            p = project(c, cam)
            hull = cv2.convexHull(np.array([(q[0], q[1]) for q in p], np.float32)).astype(np.int32)
            cv2.fillConvexPoly(m, hull, 1)
    return m


def object_mask(img, ignore_top=0.2):
    """The model in a booklet picture: pixels far (in Lab colour) from the page background (the commonest colour of
    the picture's border), largest blobs kept; the step number and parts call-out at the top left out."""
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.int16)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    bg = np.median(border, axis=0)
    m = (np.abs(lab - bg).sum(axis=2) > 40).astype(np.uint8)
    m[: int(ignore_top * m.shape[0])] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return m
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 0.15 * stats[1:, cv2.CC_STAT_AREA].max()]
    return np.isin(labels, keep).astype(np.uint8)


def _fit_box(model_mask, target_mask, cam):
    """Scale and shift `cam` so the model's outline has the target's height and centre."""
    import numpy as np
    ys, xs = np.nonzero(model_mask)
    ty, tx = np.nonzero(target_mask)
    if not len(xs) or not len(tx):
        return cam
    k = ((ty.max() - ty.min() + 1) / (ys.max() - ys.min() + 1) + (tx.max() - tx.min() + 1) / (xs.max() - xs.min() + 1)) / 2
    cam = {**cam, "scale": cam["scale"] * k, "tx": cam["tx"] * k, "ty": cam["ty"] * k}
    return cam


def iou(a, b):
    import numpy as np
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return inter / union if union else 0.0


def camera_at(pieces, target, az, el):
    """The camera at this angle, scaled and shifted so the drawn model's box matches the target's: (cam, IoU)."""
    import numpy as np
    ty, tx = np.nonzero(target)
    cam = {"az": az, "el": el, "scale": 1.0, "tx": 0.0, "ty": 0.0}
    pts = [q for _, part, pos, rot, _ in pieces for q in (corners(part, pos, rot) or [])]
    if not pts or not len(tx):
        return None, 0.0
    p = project(pts, cam)
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    k = ((ty.max() - ty.min()) / max(1e-6, max(ys) - min(ys)) + (tx.max() - tx.min()) / max(1e-6, max(xs) - min(xs))) / 2
    cam.update(scale=k, tx=(tx.min() + tx.max()) / 2 - k * (min(xs) + max(xs)) / 2,
               ty=(ty.min() + ty.max()) / 2 - k * (min(ys) + max(ys)) / 2)
    return cam, iou(silhouette(pieces, cam, target.shape), target)


def agreement(labels, book, region=None):
    """Share of pixels (where either picture shows the model, inside region) whose palette labels agree."""
    import numpy as np
    shown = (labels >= 0) | (book >= 0)
    if region is not None:
        shown &= region.astype(bool)
    n = shown.sum()
    return float(((labels == book) & shown).sum() / n) if n else 0.0


def fit_camera_colour(pieces, img, palette):
    """fit_camera, then the side the model faces: an outline fits equally well turned a quarter or half round (a
    cube looks the same), so the four turns are told apart by colour agreement with the picture."""
    target = object_mask(img)
    cam, fit = fit_camera(pieces, target)
    if not cam:
        return None, 0.0, 0.0
    book = classify(img, palette)
    best = None
    for turn in (0, 90, 180, 270):
        c, f = camera_at(pieces, target, (cam["az"] + turn) % 360, cam["el"])
        if c and f >= 0.8 * fit:
            a = agreement(raster(pieces, c, img.shape, palette)[0], book)
            if best is None or a > best[2]:
                best = (c, f, a)
    return best or (cam, fit, 0.0)


def fit_camera(pieces, target, azs=range(0, 360, 15), els=range(15, 50, 5)):
    """The camera whose drawing of `pieces` best covers the target mask (the model in the booklet picture).
    Returns (cam, iou)."""
    import numpy as np
    shape = target.shape
    ty, tx = np.nonzero(target)
    if not len(tx):
        return None, 0.0
    best = (None, -1.0)

    def place(az, el):
        cam = {"az": az, "el": el, "scale": 1.0, "tx": 0.0, "ty": 0.0}
        pts = [q for _, part, pos, rot, _ in pieces for q in (corners(part, pos, rot) or [])]
        p = project(pts, cam)
        xs, ys = [q[0] for q in p], [q[1] for q in p]
        k = ((ty.max() - ty.min()) / max(1e-6, max(ys) - min(ys)) + (tx.max() - tx.min()) / max(1e-6, max(xs) - min(xs))) / 2
        cam["scale"] = k
        cam["tx"] = (tx.min() + tx.max()) / 2 - k * (min(xs) + max(xs)) / 2
        cam["ty"] = (ty.min() + ty.max()) / 2 - k * (min(ys) + max(ys)) / 2
        return cam, iou(silhouette(pieces, cam, shape), target)
    for az in azs:
        for el in els:
            cam, score = place(az, el)
            if score > best[1]:
                best = (cam, score)
    az0, el0 = best[0]["az"], best[0]["el"]
    for az in np.arange(az0 - 7.5, az0 + 7.6, 2.5):
        for el in np.arange(el0 - 4, el0 + 4.1, 2):
            cam, score = place(float(az), float(el))
            if score > best[1]:
                best = (cam, score)
    return best


# --- real shapes (v9, second version) ------------------------------------------------------------------------
def _low(ref):
    """The library's low-detail version of a round primitive (8 segments for 16, 16 for 48), if there is one."""
    if ref.startswith("48/"):
        ref = ref[3:]
    if "/" not in ref and geo.text_of("8/" + ref) is not None:
        return "8/" + ref
    return ref


@functools.lru_cache(maxsize=None)
def mesh_low(part, depth=0):
    """mesh() with round primitives at low detail: for the 3D viewer (smaller, faster on a phone)."""
    text = geo.text_of(part)
    if text is None or depth > 12:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if not b:
            continue
        if b[0] == "3" and len(b) >= 11:
            v = [float(x) for x in b[2:11]]
            out.append((b[1], (tuple(v[0:3]), tuple(v[3:6]), tuple(v[6:9]))))
        elif b[0] == "4" and len(b) >= 14:
            v = [float(x) for x in b[2:14]]
            p = [tuple(v[i:i + 3]) for i in range(0, 12, 3)]
            out += [(b[1], (p[0], p[1], p[2])), (b[1], (p[0], p[2], p[3]))]
        elif b[0] == "1" and len(b) >= 15:
            ref = _low(truth.ldraw_key(" ".join(b[14:])))
            pos = [float(x) for x in b[2:5]]
            rot = truth._mat([float(x) for x in b[5:14]])
            for c, tri in mesh_low(ref, depth + 1):
                cc = b[1] if c == "16" else c
                out.append((cc, tuple(tuple(pos[i] + truth._apply(rot, list(p))[i] for i in range(3)) for p in tri)))
    return tuple(out)


@functools.lru_cache(maxsize=None)
def mesh(part, depth=0):
    """A library part's triangles in its own coordinates: ((colour code, (p1, p2, p3)), ...); colour '16' means the
    piece's own colour. Sub-files and primitives are followed (studs, slopes, curves all included)."""
    text = geo.text_of(part)
    if text is None or depth > 12:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if not b:
            continue
        if b[0] == "3" and len(b) >= 11:
            v = [float(x) for x in b[2:11]]
            out.append((b[1], (tuple(v[0:3]), tuple(v[3:6]), tuple(v[6:9]))))
        elif b[0] == "4" and len(b) >= 14:
            v = [float(x) for x in b[2:14]]
            p = [tuple(v[i:i + 3]) for i in range(0, 12, 3)]
            out += [(b[1], (p[0], p[1], p[2])), (b[1], (p[0], p[2], p[3]))]
        elif b[0] == "1" and len(b) >= 15:
            ref = truth.ldraw_key(" ".join(b[14:]))
            pos = [float(x) for x in b[2:5]]
            rot = truth._mat([float(x) for x in b[5:14]])
            for c, tri in mesh(ref, depth + 1):
                cc = b[1] if c == "16" else c
                out.append((cc, tuple(tuple(pos[i] + truth._apply(rot, list(p))[i] for i in range(3)) for p in tri)))
    return tuple(out)


def _tris(part, pos, rot, colour, cam):
    """Projected triangles of a placed piece: [(depth, (3 points), colour)]."""
    r = view(cam["az"], cam["el"])
    m = truth._mul(r, rot)
    o = truth._apply(r, pos)
    out = []
    for c, tri in mesh(part):
        if c == "24":  # edge colour: lines, not faces
            continue
        pts = []
        for p in tri:
            q = truth._apply(m, list(p))
            pts.append(((q[0] + o[0]) * cam["scale"] + cam["tx"], (q[1] + o[1]) * cam["scale"] + cam["ty"], q[2] + o[2]))
        out.append((sum(q[2] for q in pts) / 3, pts, colour if c == "16" else c))
    return out


def raster(pieces, cam, shape, palette):
    """Real-shape drawing of placed pieces: (label image: index into palette per pixel, -1 background; depth image).
    pieces: [(id, part, pos, rot, colour)]; palette: [colour] (a piece's colour, LDraw codes for printed parts)."""
    import cv2
    import numpy as np
    labels = np.full(shape[:2], -1, np.int16)
    depth = np.full(shape[:2], np.inf, np.float32)
    rgbs = np.array([rgb(c) for c in palette], np.float32)
    tris = [t for nid, part, pos, rot, colour in pieces for t in _tris(part, pos, rot, colour, cam)]
    for z, pts, c in sorted(tris, key=lambda t: -t[0]):  # far first: nearer triangles paint over
        arr = np.array([[p[0], p[1]] for p in pts], np.int32)
        lab = palette.index(c) if c in palette else int(np.argmin(((rgbs - np.array(rgb(c), np.float32)) ** 2).sum(1)))
        cv2.fillConvexPoly(labels, arr, lab)
        cv2.fillConvexPoly(depth, arr, float(z))
    return labels, depth


def classify(img, palette, background_tol=40):
    """A booklet picture as palette labels: each pixel's nearest palette colour (Lab distance); the page background
    and black outlines are -1."""
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    bg = np.median(border, axis=0)
    pal = np.array([rgb(c)[::-1] for c in palette], np.uint8).reshape(-1, 1, 3)
    pal_lab = cv2.cvtColor(pal, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    d = ((lab[:, :, None, :] - pal_lab[None, None]) ** 2).sum(-1)
    out = d.argmin(-1).astype(np.int16)
    out[np.abs(lab - bg).sum(-1) < background_tol] = -1
    out[lab[:, :, 0] < 25] = -1  # outlines
    return out
