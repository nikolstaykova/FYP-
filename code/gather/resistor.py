"""Reading a resistor's colour bands: code finds the body and its bands, a model names the bands' colours, code
works out the value.

Models read a resistor badly from a photo (17 Nov, the learner's 270 Ω, red-violet-brown-gold: Haiku 3 of 6 right
on a zoomed crop, reading 720 or 2.7k: band order and the multiplier). Naming the colour of a band that is already
cut out and numbered is a much easier job than reading the value, so the work is split:

1. body(): the resistor's body, from a close-up: told from the background by colour, the thin legs opened away,
   turned to lie flat, cut out, enlarged, and colour-balanced against the background (white paper is best).
2. bands(): the colour along the body; what differs from the body colour is a band. Each band gets a number on
   the picture (strip()) and code's own guess at its colour (name()).
3. read(): a model names the numbered bands' colours without seeing code's guesses (a guess shown to a model is
   agreed with); where model and code differ, the bigger model looks at the same picture. value() tries both
   reading directions and keeps the one a real resistor could be (the gold or silver band last, an E-series value).
"""
import io
import json
import pathlib

import cv2
import numpy as np

COLOURS = ["black", "brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white", "gold", "silver"]
DIGIT = {c: i for i, c in enumerate(COLOURS[:10])}
MULT = {**{c: 10 ** i for i, c in enumerate(COLOURS[:10])}, "gold": 0.1, "silver": 0.01}
TOL = {"brown": "1%", "red": "2%", "green": "0.5%", "blue": "0.25%", "violet": "0.1%", "gold": "5%", "silver": "10%"}
# typical band colours in a balanced photo (RGB), for code's own guess
REF = {"black": (35, 32, 30), "brown": (110, 62, 40), "red": (190, 40, 42), "orange": (225, 115, 40),
       "yellow": (225, 200, 60), "green": (50, 130, 70), "blue": (45, 80, 170), "violet": (125, 75, 140),
       "grey": (128, 128, 128), "white": (235, 235, 230), "gold": (175, 140, 75), "silver": (185, 185, 185)}
E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
E24 = sorted(set(E12 + [11, 13, 16, 20, 24, 30, 36, 43, 51, 62, 75, 91]))


def _lab(rgb):
    return cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)


REF_LAB = {k: _lab(v) for k, v in REF.items()}


def body(img_rgb):
    """The resistor's body, straightened and cut out: (strip RGB, info) or (None, why). img_rgb: a close-up."""
    H0, W0 = img_rgb.shape[:2]
    f = min(1.0, 900 / max(H0, W0))
    im = cv2.resize(img_rgb, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else img_rgb.copy()
    lab = cv2.cvtColor(im, cv2.COLOR_RGB2LAB).astype(float)
    border = np.concatenate([lab[:6].reshape(-1, 3), lab[-6:].reshape(-1, 3), lab[:, :6].reshape(-1, 3), lab[:, -6:].reshape(-1, 3)])
    bg = np.median(border, 0)
    # by colour more than by brightness: the body is beige (or blue) with coloured bands; the legs are grey metal and
    # their shadows on the paper are only darker, so neither counts
    wt = np.array([0.3, 1.0, 1.0])
    dist = np.linalg.norm((lab - bg) * wt, axis=2)
    spread = np.percentile(np.linalg.norm((border - bg) * wt, axis=1), 95)  # how much the background varies
    mask = (dist > max(9.0, spread * 1.5)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))  # specks
    k = max(5, int(min(im.shape[:2]) * 0.03)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))  # dark bands
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    if dt.max() < 3:
        return None, "no resistor body found"
    # the legs are thin, the body is thick: open with a disc a little under the body's half-thickness
    r = max(2, int(dt.max() * 0.6))
    thick = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    n, labels, stats, cent = cv2.connectedComponentsWithStats(thick)
    if n < 2:
        return None, "no resistor body found"
    # the biggest thick blob nearest the middle (the finder centred the resistor)
    H, W = im.shape[:2]
    score = [stats[i, cv2.CC_STAT_AREA] / (1 + np.hypot(*(cent[i] - (W / 2, H / 2))) / max(W, H)) for i in range(1, n)]
    i = 1 + int(np.argmax(score))
    pts = np.column_stack(np.where(labels == i))[:, ::-1].astype(np.float32)
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    if w < h:
        w, h, ang = h, w, ang + 90
    if w < 2.0 * h * 0.8:  # a body is long: about 2.5 to 3.5 times its thickness
        return None, "the body is not clear (too round: seen end on, or not a resistor)"
    # straighten in the full-size image and cut out the body (its middle, without the tapered ends' edges)
    s = 1 / f
    M = cv2.getRotationMatrix2D((cx * s, cy * s), ang, 1.0)
    rot = cv2.warpAffine(img_rgb, M, (W0, H0), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    x0, x1 = int(cx * s - w * s * 0.58), int(cx * s + w * s * 0.58)
    y0, y1 = int(cy * s - h * s * 0.32), int(cy * s + h * s * 0.32)
    strip = rot[max(0, y0):y1, max(0, x0):x1]
    if strip.size == 0:
        return None, "no resistor body found"
    # colour balance from the background, when it is white or grey (paper, a table top), not wood
    bg_rgb = cv2.cvtColor(np.uint8([[bg]]), cv2.COLOR_LAB2RGB)[0, 0].astype(float)
    hsv = cv2.cvtColor(np.uint8([[bg_rgb]]), cv2.COLOR_RGB2HSV)[0, 0]
    white_bg = bool(hsv[1] < 50 and hsv[2] > 110)
    if white_bg:
        strip = np.clip(strip.astype(float) * (bg_rgb.mean() / np.maximum(bg_rgb, 1)), 0, 255).astype(np.uint8)
    k = 1200 / strip.shape[1]
    strip = cv2.resize(strip, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    bg_strip = bg_rgb * (bg_rgb.mean() / np.maximum(bg_rgb, 1)) if white_bg else bg_rgb
    return strip, {"length_px": round(float(w * s)), "thickness_px": round(float(h * s)), "white_background": white_bg,
                   "background": [round(float(v)) for v in bg_strip]}


def bands(strip, background=None):
    """The bands along a straightened body: [{"from", "to" (fractions of the length), "rgb", "code"}].
    background: its RGB, to trim the ends of the strip that are past the body."""
    lab = cv2.cvtColor(strip, cv2.COLOR_RGB2LAB).astype(float)
    h, w = lab.shape[:2]
    mid = lab[int(h * 0.25):int(h * 0.75)]
    # each column's colour, without the shine (the brightest rows)
    L = mid[:, :, 0]
    keep = L <= np.percentile(L, 85, axis=0, keepdims=True)
    prof = np.array([np.median(mid[keep[:, x], x], 0) if keep[:, x].any() else np.median(mid[:, x], 0) for x in range(w)])
    prof = cv2.GaussianBlur(prof.reshape(1, w, 3).astype(np.float32), (9, 1), 0).reshape(w, 3)
    lo, hi = 0, w
    if background is not None:  # past the body's ends: background (or a leg) in the middle rows
        bgl = _lab(background)
        on_body = np.linalg.norm((prof - bgl) * np.array([0.3, 1, 1]), axis=1) > 8
        xs = np.where(on_body)[0]
        if len(xs):
            lo, hi = int(xs[0]), int(xs[-1]) + 1
    lo, hi = lo + int(w * 0.015), hi - int(w * 0.015)  # the very ends: the body's edge in shadow
    body_lab = np.median(prof[lo:hi], 0)
    diff = np.linalg.norm(prof - body_lab, axis=1)
    diff[:lo] = 0
    diff[hi:] = 0
    thr = max(12.0, 0.35 * float(diff.max()))
    on = diff > thr
    runs, x = [], 0
    while x < w:
        if on[x]:
            y = x
            while y < w and on[y]:
                y += 1
            runs.append([x, y])
            x = y
        else:
            x += 1
    merged = []
    for a, b in runs:  # one band split by a reflection: join runs closer than 1.5% of the length
        if merged and a - merged[-1][1] < w * 0.015:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        if b - a < w * 0.02:
            continue
        a2, b2 = a + (b - a) // 4, b - (b - a) // 4  # the band's middle
        rgb = cv2.cvtColor(np.uint8([[np.median(prof[a2:b2 + 1], 0)]]), cv2.COLOR_LAB2RGB)[0, 0]
        out.append({"from": round(a / w, 3), "to": round(b / w, 3), "rgb": [int(v) for v in rgb], "code": name(rgb)})
    return out


def name(rgb):
    """Code's guess at a band's colour: the nearest typical colour (Lab), with the dark and grey ones by rule."""
    hsv = cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2HSV)[0, 0]
    if hsv[2] < 55:
        return "black"
    lab = _lab(rgb)
    return min(REF_LAB, key=lambda k: np.linalg.norm(REF_LAB[k] - lab))


def strip_image(strip, found):
    """The body with each band numbered above it (what the model is shown), as JPEG bytes."""
    h, w = strip.shape[:2]
    pad = 70
    out = cv2.copyMakeBorder(strip, pad, 20, 20, 20, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for k, b in enumerate(found, 1):
        x = 20 + int((b["from"] + b["to"]) / 2 * w)
        cv2.line(out, (x, pad - 14), (x, pad + 4), (0, 0, 0), 2)
        t = str(k)
        (tw, th), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
        cv2.putText(out, t, (x - tw // 2, pad - 22), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()


def _ohms(v):
    if v >= 1e6:
        return f"{v / 1e6:g}M"
    if v >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


def value(colours):
    """The value from the band colours, either way round: {"ohms", "text", "bands" (in reading order),
    "tolerance", "sure"} or None. Prefers the direction with the gold/silver band last and a standard value."""
    best = None
    for seq in (list(colours), list(colours)[::-1]):
        if len(seq) < 3 or len(seq) > 6:
            continue
        n = len(seq)
        tol = seq[-1] if n >= 4 else None
        digits = seq[:2] if n <= 4 else seq[:3]
        mult = seq[len(digits)]
        if any(c not in DIGIT for c in digits) or mult not in MULT or (tol and tol not in TOL):
            continue
        sig = int("".join(str(DIGIT[c]) for c in digits))
        ohms = sig * MULT[mult]
        score = 0
        if tol in ("gold", "silver"):
            score += 2
        if seq[0] in ("gold", "silver"):
            score -= 3
        two = int(str(sig)[:2]) if sig >= 10 else sig
        if two in E12:
            score += 2
        elif two in E24:
            score += 1
        if seq[0] == "black":
            score -= 2
        cand = {"ohms": round(ohms, 4), "text": _ohms(ohms) + " Ω", "bands": seq, "tolerance": TOL.get(tol), "score": score}
        if best is None or score > best["score"]:
            best = cand
    if best:
        best["sure"] = best.pop("score") >= 3 and 1 <= best["ohms"] <= 10e6  # a plausible value for a kit
    return best


ASK = """This is a resistor's body, straightened, with its colour bands numbered 1 to {n} above them.
Name the colour of each numbered band. Use only these names: {names}.
(Brown is dark and dull; red is bright; orange is between red and yellow; gold is a metallic yellow-brown, often
the last band and a little apart; violet is purple.) If a numbered mark is on plain body colour, not a band, say
"none" for it. If there is a band with no number, say so in "missed".
Answer ONLY with JSON: {{"bands": ["red", "violet", ...], "missed": ""}}"""


def read(photo_path, first="claude-haiku-5-5", second="claude-opus-5-5", keep=None):
    """A resistor's value from a close-up photo: Haiku finds the resistor and it is cut from the full-size photo,
    code finds the body and its bands, a model names the numbered bands' colours (Haiku; Opus on the same picture
    when Haiku's colours do not make a sure value), code works out the value.
    Returns {"value": value() or None, "bands", "code", "model", "by", "cost_usd", "why", "white_paper"}.
    keep: a folder to save the numbered strip in (resistor_strip.jpg). On a coloured background (wood) the body is
    often not found: "white_paper" asks for the resistor on white paper; the caller can fall back to a plain look."""
    from PIL import Image
    from gather import gather_vlm as vlm
    crop, cost = vlm.zoom(photo_path, what="the resistor's body (the small beige or blue part with coloured bands; "
                          "include all its bands, not the long legs)")
    if not crop:
        return {"value": None, "why": "no resistor found in the photo", "cost_usd": round(cost, 5)}
    img = np.asarray(Image.open(io.BytesIO(crop[0])).convert("RGB"))
    strip, info = body(img)
    if strip is None:
        return {"value": None, "why": info, "white_paper": True, "cost_usd": round(cost, 5)}
    found = bands(strip, info["background"])
    found = [b for b in found if 0.03 < (b["from"] + b["to"]) / 2 < 0.97]  # not the very ends (a leg's start)
    if not 3 <= len(found) <= 6:
        return {"value": None, "why": f"found {len(found)} bands, not 3 to 6", "code": [b["code"] for b in found],
                "white_paper": not info["white_background"], "info": info, "cost_usd": round(cost, 5)}
    pic = strip_image(strip, found)
    if keep:
        (pathlib.Path(keep) / "resistor_strip.jpg").write_bytes(pic)
    code = [b["code"] for b in found]
    said, v, used = [], None, first
    for model in (first, second):
        used = model
        out, st, _ = vlm.ask(model, [(pic, "image/jpeg")], ASK.format(n=len(found), names=", ".join(COLOURS)),
                             max_tokens=1500, effort="low")
        cost += st.get("cost_usd") or 0
        i, j = out.find("{"), out.rfind("}")
        try:
            said = [str(c).lower().strip() for c in json.loads(out[i:j + 1])["bands"]]
        except Exception:
            said = []
        said = [c for c in said if c in COLOURS]
        v = value(said) if said else None
        if v and v["sure"]:
            break
    return {"value": v, "bands": v["bands"] if v else said, "code": code, "model": said,
            "by": f"bands found by code, colours named by {used}", "cost_usd": round(cost, 5), "info": info,
            **({} if v else {"why": "the band colours do not make a resistor value"})}


def main(argv=None):
    import sys
    for p in (argv or sys.argv[1:]):
        print(p, json.dumps(read(p), default=str))


if __name__ == "__main__":
    main()
