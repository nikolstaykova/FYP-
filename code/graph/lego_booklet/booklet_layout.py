"""A LEGO booklet's layout, read from the PDF by code.

What it is   finds the builds, their main steps, the boxed sub-builds and the order a child does them in
             (DATA_STRUCTURE.md §3.5); on a scanned booklet (no text layer) reads the numbers by OCR (Apple Vision)
             and the numbers Claude read per page, and finds the cream panels by colour; leaves out pages that build
             a combination with another set. Code only.
Used for     cutting a booklet into the steps a lesson is read from.
Where        lego_booklet/pdf_lesson.py (cut) and lego_booklet/booklet_check.py (draws code's cut for the page
             check).

  main steps   the booklet's big step numbers: the largest digit size that occurs more than once (page numbers and
               the numbers inside sub-build boxes are smaller)
  reading      column by column, top to bottom, page after page; a new build starts where the numbers start again
               (a mailbox 1-3, then a flower stand 1-8 on the same page); a build carries on across columns and pages
  sub-builds   the cream panels: a piece built apart and then attached as one. Its own steps are its smaller numbers
               (none: the whole panel is one step), "2x" beside it builds it that many times, and it attaches in the
               main step its arrow points into; without such an arrow, in the last step of its build (a figure
               placed in the finished model)
  order        each main step comes after the sub-builds it attaches, which come after the main step before it
  previous     a step's previous picture: the step before it in its own sub-build or build (the first step of a
               sub-build starts from nothing)
cut(doc) -> [{step, label, kind (main|sub), build, box, times, prev, attaches, page, crop}] in the lesson's order.
"""
import os
import re

CREAM = lambda f: bool(f) and min(f) > 0.6 and f[0] - f[2] > 0.12 and f[0] > 0.9  # a sub-build panel's fill
MULT = re.compile(r"^(\d+)\s*x$|^x\s*(\d+)$", re.I)


def _vision(png, W, H):
    """Apple Vision text recognition on a PNG: [(x0, y0, x1, y1, text)] in page points (W x H)."""
    import Quartz
    import Vision
    from Foundation import NSData
    src = Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(png, len(png)), None)
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    out = []
    for o in req.results() or []:
        b = o.boundingBox()
        x0, y0 = b.origin.x * W, (1 - b.origin.y - b.size.height) * H
        out.append((x0, y0, x0 + b.size.width * W, y0 + b.size.height * H, o.topCandidates_(1)[0].string().strip()))
    return out


_OCR = {}
MAIN_H = {}  # doc name -> the height of its step numbers, as read so far


_SCANNED = {}


def scanned(page):
    """A page of a scanned booklet: most of the booklet's pages have no text layer (a picture each), so its numbers
    are read from the picture. A text booklet's picture-only cover is not scanned: it has no steps to read."""
    name = os.path.basename(page.parent.name)
    if name not in _SCANNED:
        doc = page.parent
        bare = sum(1 for p in doc if not p.get_text("words") and p.get_images())
        _SCANNED[name] = bare >= 0.8 * doc.page_count
    return _SCANNED[name] and not page.get_text("words")


def words(page):
    """The page's words as page.get_text('words') gives them; on a scanned page, read from its picture (ocr)."""
    return page.get_text("words") if not scanned(page) else ocr(page)


# numbers Claude read on a scanned page, with a rough place: {(doc name, page index): [(x, y, text)]} in points
# (booklet_check.read_numbers); each is snapped to the glyph at that place
SAID = {}


def ocr(page):
    """A scanned page's numbers and 'Nx' marks, [(x0, y0, x1, y1, text, 0, 0, 0)] in page points:
      1 Apple Vision over the whole page at two resolutions (each misses some), joined
      2 the numbers Claude read on the page (SAID), each snapped to the dark glyph nearest its place that is as
        tall as the step numbers: the text from the reading, the exact box from the picture
      3 every other solid dark glyph of that height Vision did not read is cut out with a margin, enlarged and read
        on its own; a solid upright bar standing clear is a '1'"""
    import cv2
    import numpy as np
    key = (os.path.basename(page.parent.name), page.number)
    if key in _OCR:
        return _OCR[key]
    W, H = page.rect.width, page.rect.height
    found = []
    for dpi in (150, 300):
        for w in _vision(page.get_pixmap(dpi=dpi).tobytes("png"), W, H):
            t = w[4].replace(" ", "")
            if (t.isdigit() and len(t) <= 3) or MULT.match(t):
                if not any(v[4] == t and abs(v[0] - w[0]) < 6 and abs(v[1] - w[1]) < 6 for v in found):
                    found.append((w[0], w[1], w[2], w[3], t))
    dpi = 150
    k = dpi / 72
    pix = page.get_pixmap(dpi=dpi)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
    gray = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    n, lab, st, _ = cv2.connectedComponentsWithStats((gray < 70).astype(np.uint8), 8)
    tall = [w[3] - w[1] for w in found if w[4].isdigit() and w[3] - w[1] >= 10]
    seen = lambda x, y, w, h: any(v[0] * k - 4 <= x + w / 2 <= v[2] * k + 4 and  # noqa: E731
                                  v[1] * k - 4 <= y + h / 2 <= v[3] * k + 4 for v in found)
    main_h = max([w[3] - w[1] for w in found if w[4].isdigit() and w[3] - w[1] >= 18] or [0]) or \
        MAIN_H.get(key[0], 0)  # the step numbers' height: this page's, or the booklet's (a page number is smaller)
    if main_h:
        MAIN_H[key[0]] = max(MAIN_H.get(key[0], 0), main_h)
    for cx, cy, text, kind in SAID.get(key, []):  # Claude's numbers, snapped to the glyphs at their place
        if any(v[4] == text and v[0] - 30 <= cx <= v[2] + 30 and v[1] - 30 <= cy <= v[3] + 30 for v in found):
            continue  # Vision read it too
        lo, hi = (0.6, 1.4) if kind == "main" else (0.25, 0.95)  # a main number's height, or a panel's small one
        cand = [i for i in range(1, n) if st[i][2] <= 1.1 * st[i][3] and st[i][4] / (st[i][2] * st[i][3]) > 0.3
                and st[i][3] >= 8 * k and (not main_h or lo * main_h * k <= st[i][3] <= hi * main_h * k)
                and not seen(*st[i][:4])]  # not a glyph that already has its number
        near = sorted(cand, key=lambda i: abs(st[i][0] + st[i][2] / 2 - cx * k) + abs(st[i][1] + st[i][3] / 2 - cy * k))
        far = not near or abs(st[near[0]][0] + st[near[0]][2] / 2 - cx * k) + \
            abs(st[near[0]][1] + st[near[0]][3] / 2 - cy * k) > 0.06 * (W + H) * k
        if far:  # no free glyph where it was said (the digit touches the drawing): Claude's place, a number's size
            if kind == "main" and main_h:
                hw = 0.35 * main_h * max(1, len(text))
                found.append((cx - hw, cy - main_h / 2, cx + hw, cy + main_h / 2, text))
            continue
        i = near[0]
        x, y, w, h, _ = st[i]
        group = [i] + [j for j in cand if j != i and abs(st[j][1] - y) < 0.25 * h and abs(st[j][3] - h) < 0.25 * h
                       and (0 <= st[j][0] - (x + w) < 0.5 * h or 0 <= x - (st[j][0] + st[j][2]) < 0.5 * h)][:len(text) - 1]
        x0 = min(st[j][0] for j in group) / k
        y0 = min(st[j][1] for j in group) / k
        x1 = max(st[j][0] + st[j][2] for j in group) / k
        y1 = max(st[j][1] + st[j][3] for j in group) / k
        found.append((x0, y0, x1, y1, text))
    tall = [w[3] - w[1] for w in found if w[4].isdigit() and w[3] - w[1] >= 10]
    if tall:
        h_est = sorted(tall)[len(tall) // 2]
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if not (0.75 * h_est * k <= h <= 1.3 * h_est * k and w <= 0.95 * h and a / (w * h) > 0.3) or seen(x, y, w, h):
                continue
            r = max(2, int(0.3 * h))  # clear space beside and above it (a step's model may start just below)
            around = np.concatenate([gray[max(0, y - r):y, x:x + w].ravel(), gray[y:y + h, max(0, x - r):x].ravel(),
                                     gray[y:y + h, x + w:x + w + r].ravel()])
            if around.size and (around < 70).mean() > 0.02:
                continue  # something dark next to it: part of a picture, not a number on its own
            m = int(0.6 * h)
            crop = im[max(0, y - m):y + h + m, max(0, x - m):x + w + m]
            big = cv2.resize(crop, None, fx=160 / crop.shape[0], fy=160 / crop.shape[0], interpolation=cv2.INTER_CUBIC)
            ok, buf = cv2.imencode(".png", cv2.cvtColor(big, cv2.COLOR_RGB2BGR))
            got = [t for *_, t in _vision(buf.tobytes(), 1, 1) if t.replace(" ", "").isdigit()]
            text = got[0].replace(" ", "") if got else ("1" if w / h < 0.45 and a / (w * h) > 0.5 else None)
            if text:
                found.append((x / k, y / k, (x + w) / k, (y + h) / k, text))
    tight = []  # every number's box tight to its glyphs (Vision's boxes have a margin, snapped ones do not): one
    for w in found:  # size for one kind of number, as the layout compares sizes
        x0, y0, x1, y1 = [v * k for v in w[:4]]
        ins = [i for i in range(1, n) if x0 - 3 <= st[i][0] and st[i][0] + st[i][2] <= x1 + 3 and y0 - 3 <= st[i][1]
               and st[i][1] + st[i][3] <= y1 + 3 and st[i][3] > 0.4 * (y1 - y0)]
        if ins:
            w = (min(st[i][0] for i in ins) / k, min(st[i][1] for i in ins) / k,
                 max(st[i][0] + st[i][2] for i in ins) / k, max(st[i][1] + st[i][3] for i in ins) / k, w[4])
        over = lambda v: max(0, min(v[2], w[2]) - max(v[0], w[0])) * max(0, min(v[3], w[3]) - max(v[1], w[1])) > \
            0.5 * min((v[2] - v[0]) * (v[3] - v[1]), (w[2] - w[0]) * (w[3] - w[1]))  # noqa: E731
        if not any(v[4] == w[4] and over(v) for v in tight):  # read twice (two passes, boxes a little apart)
            tight.append(w)
    said = SAID.get(key, [])

    def kind_of(w):  # the kind Claude gave the number at this place, if it gave one
        hit = [kd for cx, cy, t, kd in said if t == w[4] and w[0] - 25 <= cx <= w[2] + 25 and w[1] - 25 <= cy <= w[3] + 25]
        return hit[0] if hit else 0
    out = [(*w, kind_of(w), 0, 0) for w in tight]
    _OCR[key] = out
    return out


def other_set(page, set_id):
    """The page builds a combination with another set: its printed text names this set and another set number
    ('8655 + 8658 =' over the joined model). Years (19xx, 20xx) and the booklet's own long code are not set numbers."""
    import re
    W, H = page.rect.width, page.rect.height
    text = " ".join(x[4] for x in _vision(page.get_pixmap(dpi=150).tobytes("png"), W, H)) if scanned(page) \
        else page.get_text()
    nums = set(re.findall(r"(?<![\d.])\d{4,5}(?![\d.])", text)) - {n for n in re.findall(r"\b(?:19|20)\d\d\b", text)}
    own = set_id.split("-")[0]
    return own in nums and bool(nums - {own})


def _digits(page):
    out = []
    for w in words(page):  # a number can be in the text twice (an outline drawn over it)
        if w[4].isdigit() and len(w[4]) <= 3 and not w[4].startswith("0") and (w[3] - w[1]) >= 10 and \
                not any(v[4] == w[4] and abs(v[0] - w[0]) < 4 and abs(v[1] - w[1]) < 4 for v in out):
            out.append(w)
    return out


def _connectors(page, box):
    """The booklet's connector lines that leave a sub-build panel: [far end point]. A connector is a dark line (a
    thin filled bar or a stroked path, followed through its bends to where it ends), one end on or just inside the
    panel's edge and the other end well outside it. Coloured lines are the panel's own arrows, which can run off
    the page (clipped), and are not connectors."""
    import pymupdf
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if d.get("type") == "f" and len(d["items"]) == 1 and d["items"][0][0] == "re" and min(r.width, r.height) < 2.5:
            if max(d.get("fill") or (1, 1, 1)) >= 0.4:
                continue
            c = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            pts = [(r.x0, c[1]), (r.x1, c[1])] if r.width > r.height else [(c[0], r.y0), (c[0], r.y1)]
        elif d.get("type") == "f" and max(d.get("fill") or (1, 1, 1)) < 0.4 and d["items"] and \
                all(it[0] == "l" for it in d["items"]):  # a line drawn as a thin filled shape (it may bend)
            pts = [(it[1].x, it[1].y) for it in d["items"]] + [(d["items"][-1][2].x, d["items"][-1][2].y)]
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
            length = sum(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:]))
            if not length or area / length > 2:  # not thin: a piece, a panel
                continue
            inside = [q for q in pts if _inside(pymupdf.Point(*q), box, 0)]
            outside = [q for q in pts if not _inside(pymupdf.Point(*q), box, 10)]
            if inside and outside:  # from inside the panel to the farthest point out of it
                cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
                out.append(pymupdf.Point(*max(outside, key=lambda q: abs(q[0] - cx) + abs(q[1] - cy))))
            continue
        elif d.get("type") == "s" and max(d.get("color") or (1, 1, 1)) < 0.4:
            pts = []
            for it in d["items"]:
                if it[0] == "l":
                    for q in (it[1], it[2]):
                        if not pts or abs(pts[-1][0] - q.x) + abs(pts[-1][1] - q.y) > 0.5:
                            pts.append((q.x, q.y))
            if len(pts) < 2:
                continue
        else:
            continue
        for near, far in ((pts[0], pts[-1]), (pts[-1], pts[0])):
            pn, pf = pymupdf.Point(*near), pymupdf.Point(*far)
            if _inside(pn, box, 4) and not _inside(pf, box, 10):  # from the panel (its edge, or behind its picture)
                out.append(pf)
                break
    return out


def _cream_panels(page, dpi=72):
    """A scanned page's sub-build panels, from its picture: large, nearly rectangular areas of panel cream."""
    import cv2
    import numpy as np
    pix = page.get_pixmap(dpi=dpi)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].astype(np.float32) / 255
    r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    mask = ((np.minimum(np.minimum(r, g), b) > 0.6) & (r - b > 0.12) & (r > 0.9)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    k = dpi / 72
    out = []
    import pymupdf
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w / k > 40 and h / k > 30 and w < 0.7 * pix.w and a / (w * h) > 0.55:  # a panel, with pieces drawn on it
            out.append(pymupdf.Rect(x / k, y / k, (x + w) / k, (y + h) / k))
    return out


def _boxes(page):
    if scanned(page):
        return _cream_panels(page)
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if d.get("fill") is not None and CREAM(d["fill"]) and r.width > 40 and r.height > 30 \
                and r.width < 0.7 * page.rect.width:
            if not any(abs(r.x0 - b.x0) + abs(r.y0 - b.y0) + abs(r.x1 - b.x1) + abs(r.y1 - b.y1) < 6 for b in out):
                out.append(r)
    return out


def _inside(p, r, pad=8):
    return r.x0 - pad <= p.x <= r.x1 + pad and r.y0 - pad <= p.y <= r.y1 + pad


def _regions(digits, bounds, others=()):
    """Each digit's region: from just above-left of it to the next digit to its right (a new column) or below it in
    its column, within bounds (x0, y0, x1, y1); others: more rects that end a region (a box beside or below)."""
    x0b, y0b, x1b, y1b = bounds
    out = []
    for w in digits:
        right = min([v[0] for v in digits if v[0] > w[0] + 30] + [o.x0 for o in others  # a box beside it, in
                    if o.x0 > w[0] + 30 and o.y0 <= w[3] and o.y1 >= w[1]] + [x1b])    # its own row
        below = min([v[1] for v in digits if v[1] > w[1] + 15 and w[0] - 30 <= v[0] < right] +
                    [o.y0 for o in others if o.y0 > w[3] and o.x0 < right and o.x1 > w[0]] + [y1b])
        out.append((max(x0b, w[0] - 10), max(y0b, w[1] - 10), right - 5, below - 5))
    return out


def cut(doc, fixes=None):
    """fixes (booklet_check.py, a look at each page): {"crops": {"<page>:<number>": [x0, y0, x1, y1]} for a main step
    whose region the rules cut wrong, "into": {"sub-<n>": "<main step number>" | "own build"} for a panel the rules
    attached wrong, "other_set_pages": [page] built with another set's pieces (8655 + 8658 =), left out}."""
    fixes = fixes or {}
    other = set(fixes.get("other_set_pages") or [])  # a page that builds a combination with another set: not ours
    pages = [(i + 1, p, _digits(p), _boxes(p)) for i, p in enumerate(doc) if i + 1 not in other]
    tol = 0.35 if any(scanned(p) for _, p, _, _ in pages) else 0.15  # a scan's measured sizes vary more
    sizes = sorted({round(w[3] - w[1]) for _, _, ds, _ in pages for w in ds}, reverse=True)
    main_size = next((s for s in sizes if sum(1 for _, _, ds, _ in pages for w in ds
                                              if abs((w[3] - w[1]) - s) <= tol * s) >= 2), None)
    if main_size is None:
        return []
    def is_main(w):  # a scan: the kind Claude read it as, where it read one; else by its size
        if len(w) > 5 and w[5] in ("main", "sub-build"):
            return w[5] == "main"
        return abs((w[3] - w[1]) - main_size) <= tol * main_size
    steps, boxes, skipped = [], [], []
    build, last, lasts = -1, None, {}
    for pno, page, ds, bx in pages:
        mains = [w for w in ds if is_main(w) and not any(_inside(_pt(w), b, 0) and _cream_at(page, w) for b in bx)]
        cols = []
        mid = lambda w: (w[0] + w[2]) / 2  # noqa: E731  (a '1' is narrow: its centre, not its left edge)
        for w in sorted(mains, key=mid):  # columns: digits within 40 points of each other in x
            if cols and abs(mid(w) - mid(cols[-1][0])) < 40:
                cols[-1].append(w)
            else:
                cols.append([w])
        order = [w for c in cols for w in sorted(c, key=lambda w: w[1])]
        regs = dict(zip(map(tuple, order), _regions(order, (0, 0, page.rect.x1, page.rect.y1), bx)))
        for w in order:
            n = int(w[4])
            cont = [b for b, m in lasts.items() if m == n - 1]  # the build this number continues (two models'
            if cont:                                            # steps can share a page); the earliest when two do
                build = cont[0]                                 # (a model's arm ends at 5 too, then goes on it)
            elif last is None or n <= last or n == 1:
                build = max(lasts, default=-1) + 1
            lasts[build] = n
            last = n
            crop = (fixes.get("crops") or {}).get(f"{pno}:{n}@{round(round(w[0], 1))},{round(round(w[1], 1))}") \
                or regs[tuple(w)]  # the page check's box for this very number (by its place: two builds' 5s)
            steps.append({"kind": "main", "label": str(n), "build": build, "page": pno, "crop": crop,
                          "box": None, "times": 1, "attaches": [], "_at": (pno, w[0], w[1]),
                          "number": [round(v, 1) for v in w[:4]]})
        mults = [w for w in words(page) if MULT.match(w[4])]
        for b in bx:
            n_box = len(boxes) + 1 + sum(1 for x in skipped)
            if f"sub-{n_box}" in (fixes.get("not_panel") or []):  # the page check: not a sub-build panel
                skipped.append(n_box)
                continue
            subs = sorted([w for w in ds if not is_main(w) and _inside(_pt(w), b, 0)], key=lambda w: int(w[4]))
            m = next((w for w in mults if _inside(_pt(w), b, 20)), None)
            times = int(next(g for g in MULT.match(m[4]).groups() if g)) if m else 1
            boxes.append({"id": f"sub-{n_box}", "page": pno, "rect": b, "times": times,
                          "lines": _connectors(page, b), "x": b.x0, "y": b.y0,
                          "steps": [{"kind": "sub", "label": w[4], "page": pno, "crop": r, "times": times,
                                     "number": [round(v, 1) for v in w[:4]]}
                                    for w, r in zip(subs, _regions(subs, tuple(b)))] or
                                   [{"kind": "sub", "label": "", "page": pno, "crop": tuple(b), "times": times}]})
    # where each sub-build attaches:
    #   a line from the panel into a main step: there
    #   a line to somewhere else (a minifigure drawn standing beside the model): it stands alone, and goes into the
    #     finished model in the last step of its build
    #   no line: the next main step in reading order on its page (column by column), unless that is the first step
    #     of a build (nothing to attach it to yet): then, as above, the last step of the build
    for bxi in boxes:
        page_steps = [s for s in steps if s["page"] == bxi["page"]]
        target, how = None, ""
        said = (fixes.get("into") or {}).get(bxi["id"])
        if said and said != "own build":  # the page check saw which step it goes into
            near = sorted((s for s in steps if s["label"] == str(said)), key=lambda s: abs(s["page"] - bxi["page"]))
            target, how = (near[0], "the page check: it goes into this step") if near else (None, "")
        elif said == "own build":
            b_build = next((s["build"] for s in sorted(page_steps, key=lambda s: abs(s["_at"][1] - bxi["x"]))),
                           steps[-1]["build"] if steps else 0)
            target = [s for s in steps if s["build"] == b_build][-1]
            how = "stands alone: the page check saw a build of its own"
        for far in ([] if target else bxi["lines"]):
            target = next((s for s in page_steps if _inside(far, _R(s["crop"]), 12)), None)
            if target:
                how = "a line from it into this step"
                break
        if target is None and not bxi["lines"] and not said:
            after = sorted((s for s in page_steps if (round(s["_at"][1] / 40), s["_at"][2]) >
                            (round(bxi["x"] / 40), bxi["y"]) or (abs(s["_at"][1] - bxi["x"]) < 40 and
                                                                s["_at"][2] > bxi["y"])),
                           key=lambda s: (round(s["_at"][1] / 40), s["_at"][2]))
            nxt = after[0] if after else None
            first = nxt is not None and nxt is next(s for s in steps if s["build"] == nxt["build"])
            if nxt is not None and not first:
                target, how = nxt, "the next step after it in reading order"
        if target is None and bxi["lines"] and not said:  # the line leads to a picture outside every step: the build's result
            for far in bxi["lines"]:
                crop = picture_at(doc[bxi["page"] - 1], far)
                if crop:
                    bxi["steps"].append({"kind": "sub", "label": str(len(bxi["steps"]) + 1), "page": bxi["page"],
                                         "crop": crop, "times": bxi["times"], "result_of_panel": True})
                    break
        if target is None:
            b_build = (page_steps or steps)[-1]["build"] if not bxi["lines"] else \
                next((s["build"] for s in sorted(page_steps, key=lambda s: abs(s["_at"][1] - bxi["x"]))), 0)
            target, how = [s for s in steps if s["build"] == b_build][-1], "stands alone: the last step of its build"
        bxi["target"], bxi["how"] = target, how
        target["attaches"].append(bxi["id"])
    out = []
    for s in steps:
        for bxi in boxes:
            if bxi["target"] is s:
                first = len(out)
                for k, sub in enumerate(bxi["steps"]):
                    out.append({**sub, "build": s["build"], "box": bxi["id"], "attached_by": bxi["how"],
                                "label": f"{bxi['id']}" + (f" · {sub['label']}" if sub["label"] else ""),
                                "prev": first + k if k else None, "attaches": []})
        prev_main = next((i for i in range(len(out) - 1, -1, -1) if out[i]["kind"] == "main" and
                          out[i]["build"] == s["build"]), None)
        out.append({**{k: v for k, v in s.items() if k != "_at"}, "prev": None if prev_main is None else prev_main + 1})
    for i, s in enumerate(out, 1):
        s["step"] = i
        s["crop"] = [round(v, 1) for v in s["crop"]]
        s["prev"] = None if s["prev"] is None else s["prev"]  # 1-based lesson step number
    return out


def split_columns(doc, steps, dpi=40):
    """Two steps one above the other in a column are split at the empty strip of background between their
    pictures, not at the lower step's number: a model can stand taller than its number (a mailbox's roof above the
    "2"), and cut at the number its top would be in the step above. Changes the crops in place."""
    import numpy as np
    import pymupdf
    for a in steps:
        for b in steps:
            if a is b or a["page"] != b["page"] or abs(a["crop"][0] - b["crop"][0]) > 6 or \
                    abs(a["crop"][3] + 5 - b["crop"][1]) > 12 or not b.get("number"):
                continue
            page = doc[a["page"] - 1]
            x0, x1 = max(a["crop"][0], b["crop"][0]), min(a["crop"][2], b["crop"][2]) - 12  # not the next column
            y0, y1 = a["crop"][1] + 30, b["number"][3]  # the strip lies above the lower number's foot
            if y1 - y0 < 10:
                continue
            pm = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=pymupdf.Rect(x0, y0, x1, y1))
            im = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
            vals, counts = np.unique(im.reshape(-1, 3) // 8, axis=0, return_counts=True)
            bg = vals[counts.argmax()] * 8 + 4
            nx0 = int((b["number"][0] - x0) * dpi / 72) - 2  # the number itself is not a picture
            nx1 = int((b["number"][2] - x0) * dpi / 72) + 2
            clean = (np.abs(im - bg).max(axis=2) < 24)
            clean[:, max(0, nx0):max(0, nx1)] = True
            empty = clean.mean(axis=1) > 0.98
            best, run, start = None, 0, 0
            for i, e in enumerate(list(empty) + [False]):
                if e:
                    if not run:
                        start = i
                    run += 1
                else:
                    if run and (best is None or run > best[1] or (run == best[1] and start > best[0])):
                        best = (start, run)
                    run = 0
            if best and best[1] >= 2:
                mid = y0 + (best[0] + best[1] / 2) * 72 / dpi
                if mid < b["crop"][1]:  # only ever raise the split: the lower picture starts above its number
                    a["crop"] = [a["crop"][0], a["crop"][1], a["crop"][2], round(mid, 1)]
                    b["crop"] = [b["crop"][0], round(mid, 1), b["crop"][2], b["crop"][3]]


def picture_at(page, point, dpi=40, reach=200):
    """The picture a connector line points at, outside every step (a figure drawn finished beside its panel): the
    shapes not of the background nearest the point, and every shape close to them, as a crop in PDF points."""
    import cv2
    import numpy as np
    import pymupdf
    x0, y0 = max(0, point.x - 25), max(0, point.y - reach)
    x1, y1 = min(page.rect.x1, point.x + reach), min(page.rect.y1, point.y + reach)
    pm = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=pymupdf.Rect(x0, y0, x1, y1))
    im = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
    vals, counts = np.unique(im.reshape(-1, 3) // 8, axis=0, return_counts=True)
    bg = vals[counts.argmax()] * 8 + 4
    ink = cv2.morphologyEx((np.abs(im - bg).max(axis=2) >= 24).astype(np.uint8), cv2.MORPH_CLOSE,
                           np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink)
    k = dpi / 72
    px, py = (point.x - x0) * k, (point.y - y0) * k
    dist = lambda i: max(st[i][0] - px, px - st[i][0] - st[i][2], 0) + max(st[i][1] - py, py - st[i][1] - st[i][3], 0)
    cand = [i for i in range(1, n) if st[i][4] > 8 and st[i][2] < 0.9 * pm.w]
    if not cand:
        return None
    first = min(cand, key=dist)
    if dist(first) > 15 * k:
        return None
    chosen, grew = {first}, True
    while grew:
        grew = False
        bx0 = min(st[i][0] for i in chosen); by0 = min(st[i][1] for i in chosen)
        bx1 = max(st[i][0] + st[i][2] for i in chosen); by1 = max(st[i][1] + st[i][3] for i in chosen)
        for i in cand:
            if i not in chosen:
                x, y, w, h, _ = st[i]
                if x <= bx1 + 6 * k and x + w >= bx0 - 6 * k and y <= by1 + 6 * k and y + h >= by0 - 6 * k:
                    chosen.add(i)
                    grew = True
    pad = 6
    return [round(x0 + bx0 / k - pad, 1), round(y0 + by0 / k - pad, 1), round(x0 + bx1 / k + pad, 1),
            round(y0 + by1 / k + pad, 1)]


def _pt(w):
    import pymupdf
    return pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)


def _R(c):
    import pymupdf
    return pymupdf.Rect(*c)


def _cream_at(page, w):
    """Is the digit on a sub-build panel (the box's outline is not always a rectangle)?"""
    import pymupdf
    pm = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), clip=pymupdf.Rect(w[0] - 6, w[1], w[0] - 1, w[3]))
    r, g, b = pm.pixel(0, pm.h // 2)[:3]
    return r > 230 and r - b > 30
