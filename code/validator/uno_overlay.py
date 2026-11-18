"""The Arduino straightened onto a reference photo of the same board, with every digital pin's name written where a
wire's connector sits in it: the model reads the name instead of counting the header's black openings.

Why: the header and a wire's connector stand 1-2 cm above the board, so in a photo from above they look shifted
against the labels printed on the board, and the model miscounted by one socket (11 read as 12). Code can't count the
openings either (black in black, half covered). But the board's print (text, chips, pads) is rich in features, so each
photo is overlaid on a reference photo of the same board (SIFT features, a homography by RANSAC): that gives its
position, rotation and which way round in one go. Where a connector sits in the reference, pin by pin, was learned from
the learner's clicked photos (a straight row, 2.54 mm apart, with the 0.16" gap between 8 and 7).
18 Nov 2026, 43 clicked photos: overlaid 40 (3 had no blue board found), the pin nearest the click right 40/40 (each
photo scored with positions learned from the others).

  references: code/graph/parts/arduino/refs/<board>.jpg + .json (pins: name -> [x, y] in the reference image)
  analyse(photo)  -> {"board", "inliers", "image": JPEG of the straightened Arduino with the pin names} or None
  build(board, photo, clicks)  makes a reference (research/recognition/uno_reference.py)
"""
import json
import pathlib

import cv2
import numpy as np

from validator import board as _board

REFS = pathlib.Path(__file__).resolve().parents[1] / "graph" / "parts" / "arduino" / "refs"
# the digital header, block by block; between blocks 0.16" = 1.6 pitches (the Arduino's odd spacing between 8 and 7)
LAYOUTS = {
    "duemilanove": [["AREF", "GND", "13", "12", "11", "10", "9", "8"], ["7", "6", "5", "4", "3", "2", "1", "0"]],
    "uno-r3": [["SCL", "SDA", "AREF", "GND", "13", "12", "11", "10", "9", "8"], ["7", "6", "5", "4", "3", "2", "1", "0"]],
}
GAP = 1.6


def layout(name):
    """(order, {pin: position in pitches from the first opening})"""
    order, idx, k = [], {}, 0.0
    for b, block in enumerate(LAYOUTS[name]):
        if b:
            k += GAP - 1
        for pin in block:
            order.append(pin)
            idx[pin] = k
            k += 1
    return order, idx


ORDER, IDX = layout("duemilanove")
EDGE = 1400
MIN_INLIERS = 25
_sift = None
_refs = None


def _features(gray):
    global _sift
    if _sift is None:
        _sift = cv2.SIFT_create(nfeatures=4000)
    return _sift.detectAndCompute(gray, None)


def crop(img):
    """The Arduino's part of a photo (its blue board with a margin; the whole photo when no blue board is found),
    scaled to EDGE: (image, (x0, y0) in the photo, scale)."""
    H, W = img.shape[:2]
    f = 1200 / max(H, W)
    a = _board.arduino_box(cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))
    if a:
        x0, y0, x1, y1 = a["box"]
        mx, my = (x1 - x0) * .2, (y1 - y0) * .2
        bx = (int(max(0, (x0 - mx) * W)), int(max(0, (y0 - my) * H)), int(min(W, (x1 + mx) * W)), int(min(H, (y1 + my) * H)))
    else:
        bx = (0, 0, W, H)
    c = img[bx[1]:bx[3], bx[0]:bx[2]]
    s = EDGE / max(c.shape[:2])
    return cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), bx[:2], s


def _load_refs():
    global _refs
    if _refs is None:
        _refs = []
        for j in sorted(REFS.glob("*.json")):
            meta = json.loads(j.read_text())
            im = cv2.imread(str(j.with_suffix(".jpg")))
            if im is None:
                continue
            k, d = _features(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
            _refs.append({"board": j.stem, "image": im, "kp": k, "des": d, **meta})
    return _refs


def overlay(c):
    """The best reference for an Arduino crop: (ref, H crop -> reference, inliers) or None."""
    k, d = _features(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY))
    if d is None:
        return None
    best = None
    for ref in _load_refs():
        good = [m for m, n in cv2.BFMatcher().knnMatch(d, ref["des"], k=2) if m.distance < 0.75 * n.distance]
        if len(good) < MIN_INLIERS:
            continue
        src = np.float32([k[m.queryIdx].pt for m in good])
        dst = np.float32([ref["kp"][m.trainIdx].pt for m in good])
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        if H is None or int(mask.sum()) < MIN_INLIERS:
            continue
        if best is None or int(mask.sum()) > best[2]:
            best = (ref, H, int(mask.sum()))
    return best


def analyse(photo_path):
    """The Arduino straightened onto its reference, every digital pin's name written in yellow where a connector in
    that socket sits, beside it on the outside of the header. None when no reference matches."""
    try:
        img = _board.load(photo_path)
        c, _, _ = crop(img)
        got = overlay(c)
    except Exception:
        return None
    if got is None:
        return None
    ref, H, inl = got
    flat = cv2.warpPerspective(c, H, (ref["image"].shape[1], ref["image"].shape[0]))
    order, idx = layout(ref.get("layout", "duemilanove"))
    pins = {p: np.array(v, float) for p, v in ref["pins"].items()}
    a, b = pins[order[0]], pins[order[-1]]
    u = (b - a) / np.linalg.norm(b - a)
    nrm = np.array([-u[1], u[0]])
    mid = np.array([flat.shape[1] / 2, flat.shape[0] / 2])
    if (a - mid) @ nrm < 0:  # the labels go on the outer side of the header, away from the board's middle
        nrm = -nrm
    pitch = np.linalg.norm(b - a) / idx[order[-1]]
    if ref.get("layout"):  # a reference made from a straight-down photo marks the openings themselves: look near them
        comb = openings(flat, a, u, nrm, pitch, order, idx, across_range=(-0.6, 0.6), spread=0.06, along_range=0.8)
    else:  # made from clicks on the connectors, which stand out from the openings: look further in
        comb = openings(flat, a, u, nrm, pitch, order, idx)
    if comb is not None:  # the openings themselves, found in this photo
        pins, fit = comb
    else:
        fit = None
    out = flat.copy()
    for p, xy in pins.items():
        tip = xy + nrm * pitch * 0.6
        lab = xy + nrm * pitch * 1.9
        cv2.line(out, tuple(int(v) for v in tip), tuple(int(v) for v in (xy + nrm * pitch * 1.3)), (0, 230, 255), 2)
        (tw, th), _ = cv2.getTextSize(p, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        x, y = int(lab[0] - tw / 2), int(lab[1] + th / 2)
        cv2.rectangle(out, (x - 3, y - th - 3), (x + tw + 3, y + 4), (0, 230, 255), -1)
        cv2.putText(out, p, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return {"board": ref["board"], "inliers": inl, "image": buf.tobytes(), "openings": fit}


def openings(flat, a, u, nrm, pitch, order=None, idx=None, across_range=(-0.6, 1.6), spread=0.1, along_range=2.5):
    """The header's 16 openings in the straightened photo: a comb of known shape (equal spacing, 1.6 spacings between
    8 and 7) slid along the header row until its teeth sit on the dark openings and the gaps between them on the
    lighter plastic. Searched: how far across the row (the header's top looks shifted against the print), along it,
    and the spacing (±10%). Returns ({pin: (x, y)}, {"contrast", ...}) or None when no clear row of openings is seen."""
    order, idx = order or ORDER, idx or IDX
    g = cv2.GaussianBlur(cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32)
    Hh, Ww = g.shape
    ks = np.array([idx[p] for p in order])
    gaps = np.array([(idx[order[i]] + idx[order[i + 1]]) / 2 for i in range(len(order) - 1)])
    big = [i for i in range(len(order) - 1) if idx[order[i + 1]] - idx[order[i]] > 1.2]
    # past each end of the header, and the middle of the wider gap between 8 and 7, there is no opening: a comb slid
    # by a whole socket still has most teeth on openings, but then one end tooth falls off the header
    ends = np.array([-1.0, idx[order[-1]] + 1.0] + [(idx[order[i]] + idx[order[i + 1]]) / 2 for i in big])

    def val(pts):
        x = np.clip(pts[:, 0].round().astype(int), 0, Ww - 1)
        y = np.clip(pts[:, 1].round().astype(int), 0, Hh - 1)
        return g[y, x]
    best = None
    for across in np.arange(across_range[0], across_range[1], 0.08) * pitch:  # the openings' row (default: from
        for p in np.arange(1 - spread, 1 + spread + 0.001, 0.01) * pitch:   # the learned connector row inwards)
            for along in np.arange(-along_range, along_range + 0.01, 0.06) * pitch:
                o = a + u * along - nrm * across
                teeth = val(o + np.outer(ks * p, u))
                between = val(o + np.outer(gaps * p, u))
                past = val(o + np.outer(ends * p, u))
                dark = float(np.median(teeth))
                score = float(np.median(between) - dark) + float(min(past.min() - dark, 40))
                if best is None or score > best[0]:
                    best = (score, o, p, across, along)
    score, o, p, across, along = best
    if score < 12:  # no clear row of dark openings between lighter plastic
        return None
    pins = {pn: o + u * idx[pn] * p for pn in order}
    return pins, {"contrast": round(score, 1), "spacing": round(float(p), 1), "across": round(float(across), 1),
                  "along": round(float(along), 1)}


def build_from_row(board_id, photo, layout_name, first, last, source="", tight=False):
    """A reference from a straight-down photo of the board (no parallax): `first` and `last` are roughly where the
    first and last openings of the digital header are in the cropped reference (as `crop` makes it, read off a grid
    once); the comb finds the openings exactly."""
    REFS.mkdir(parents=True, exist_ok=True)
    ref, _, _ = crop(_board.load(photo))
    order, idx = layout(layout_name)
    a, b = np.array(first, float), np.array(last, float)
    u = (b - a) / np.linalg.norm(b - a)
    nrm = np.array([-u[1], u[0]])
    if (a - np.array([ref.shape[1] / 2, ref.shape[0] / 2])) @ nrm < 0:
        nrm = -nrm
    pitch = np.linalg.norm(b - a) / idx[order[-1]]
    got = openings(ref, a, u, nrm, pitch, order, idx, across_range=(-0.15, 0.15) if tight else (-0.4, 0.4),
                   spread=0.015 if tight else 0.05, along_range=0.25 if tight else 1.0)
    if got is None:
        raise ValueError(f"{board_id}: no clear row of openings near the row given")
    pins, fit = got
    cv2.imwrite(str(REFS / f"{board_id}.jpg"), ref, [cv2.IMWRITE_JPEG_QUALITY, 92])
    meta = {"photo": pathlib.Path(photo).name, "source": source, "layout": layout_name, "fit": fit,
            "pins": {p: [round(float(v), 1) for v in pins[p]] for p in order}}
    (REFS / f"{board_id}.json").write_text(json.dumps(meta, indent=1))
    global _refs
    _refs = None
    return meta


def build(board_id, ref_photo, clicked):
    """A reference: the Arduino of ref_photo (cropped as `crop` does), and where a connector sits pin by pin, fitted as
    a straight row over the clicks of other photos overlaid on it. clicked: [(photo, pin, (x, y) fractions)]."""
    REFS.mkdir(parents=True, exist_ok=True)
    ref, _, _ = crop(_board.load(ref_photo))
    cv2.imwrite(str(REFS / f"{board_id}.jpg"), ref, [cv2.IMWRITE_JPEG_QUALITY, 92])
    global _refs
    _refs = [{"board": board_id, "image": ref, "pins": {}, **dict(zip(("kp", "des"), _features(
        cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY))))}]
    pts = []
    for photo, pin, (fx, fy) in clicked:
        if pin not in IDX:
            continue
        img = _board.load(photo)
        c, (x0, y0), s = crop(img)
        got = overlay(c)
        if got is None:
            continue
        H = got[1]
        Hh, Ww = img.shape[:2]
        p = cv2.perspectiveTransform(np.float32([[[(fx * Ww - x0) * s, (fy * Hh - y0) * s]]]), H)[0, 0]
        pts.append((IDX[pin], p))
    for _ in range(3):  # a straight row; the worst tenth dropped twice
        K = np.array([[1, k] for k, _ in pts])
        X = np.array([q for _, q in pts])
        coef, *_ = np.linalg.lstsq(K, X, rcond=None)
        res = np.linalg.norm(K @ coef - X, axis=1)
        if len(pts) > 8:
            pts = [pt for pt, r in zip(pts, res) if r <= np.percentile(res, 90)]
    meta = {"photo": pathlib.Path(ref_photo).name, "fitted_from": len(pts),
            "pins": {p: [round(float(v), 1) for v in coef[0] + coef[1] * IDX[p]] for p in ORDER}}
    (REFS / f"{board_id}.json").write_text(json.dumps(meta, indent=1))
    _refs = None
    return meta
