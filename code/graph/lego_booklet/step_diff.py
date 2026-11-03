"""What each booklet step adds, found by comparing its picture with the previous step's.

What it is   the step pictures by code: each step cut from the page (tighten to the step, take in a parts call-out
             drawn above the number, grow to any shape the cut goes through); the previous picture aligned onto this
             one (ORB features and a homography) so the pixels that changed are what the step adds, boxed in red,
             and an overlay with what was already there faded; the booklet's arrows found from the PDF (a red line
             with a filled head) so they are never taken for a part.
Used for     showing Claude where a step's new pieces are, and giving code the changed areas it measures.
Where        lego_booklet/pdf_lesson.py (the cut, overlays, zooms, arrows), lego_booklet/booklet_check.py and
             booklet_size.py.

Left out of the boxes: the parts call-out (it lists the pieces, it does not show where they go), the step number,
and specks. A step whose picture does not align with the previous one (the booklet turned the model, zoomed, or
started a sub-build) gets no boxes and says so.
"""


DPI = 150


def _bgr(page, crop, dpi=DPI):
    import numpy as np
    import pymupdf
    pm = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=pymupdf.Rect(*crop))
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3]
    return a[:, :, ::-1].copy()


def number_corner(dpi=DPI):
    """The step number's corner of a step picture, in pixels: a cut starts 10 points left of and above its number,
    which is up to two digits of about 30 points."""
    return (int(60 * dpi / 72), int(48 * dpi / 72))


def moved(prev_arrows, prev_mask, shape):
    """Where the pieces the previous step drew floating on arrows now sit: a disc at each arrow's tip, as large as
    the piece at its start. Those pixels changed because a piece moved into place, not because one is new."""
    import cv2
    import numpy as np
    out = np.zeros(shape[:2], np.uint8)
    if not prev_arrows or prev_mask is None:
        return out
    n, lab, st, _ = cv2.connectedComponentsWithStats(prev_mask.astype(np.uint8))
    for a in prev_arrows:
        tx, ty = a["tail"]
        best, size = None, 40
        for i in range(1, n):
            x, y, w, h, _ = st[i]
            d = max(x - tx, tx - (x + w), 0) + max(y - ty, ty - (y + h), 0)
            if d < 60 and (best is None or d < best):
                best, size = d, max(w, h)
        cv2.circle(out, a["tip"], int(0.6 * size), 1, -1)
    return out


def gone(cur, mask):
    """A change mask without the pixels that are now the step's background: something went away there (a piece that
    floated beside the model and is now on it, its arrows), nothing new is there."""
    import numpy as np
    if mask is None:
        return None
    h, w = cur.shape[:2]
    corner = cur[: h // 8, w // 3:].reshape(-1, 3) // 8
    v, c = np.unique(corner, axis=0, return_counts=True)
    bg = v[c.argmax()] * 8 + 4
    out = mask.copy()
    out[np.abs(cur.astype(int) - bg).max(2) < 24] = 0
    return out


def changed_regions(prev, cur, min_inliers=60, mask=False, top=0.22, corner=None):
    """Boxes (x, y, w, h) on `cur` where it differs from `prev` once aligned (mask=True: the 0/1 mask of changed
    pixels instead); None if the two do not align. top: the share of the picture at the top left out (a booklet's
    parts call-out sits there; 0 keeps a piece drawn high up, such as one floating above the model on arrows), and
    corner: the step number's corner left out."""
    import cv2
    import numpy as np
    g1, g2 = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in (prev, cur))
    orb = cv2.ORB_create(4000)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None:
        return None
    m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2), key=lambda x: x.distance)[:500]
    if len(m) < 12:
        return None
    H, inl = cv2.findHomography(np.float32([k1[x.queryIdx].pt for x in m]), np.float32([k2[x.trainIdx].pt for x in m]),
                                cv2.RANSAC, 4.0)
    if H is None or int(inl.sum()) < min_inliers:
        return None
    h, w = g2.shape
    warped = cv2.warpPerspective(prev, H, (w, h), borderValue=(255, 255, 255))
    seen = cv2.warpPerspective(np.full(g1.shape, 255, np.uint8), H, (w, h))
    diff = cv2.absdiff(cv2.GaussianBlur(warped, (5, 5), 0), cv2.GaussianBlur(cur, (5, 5), 0)).max(axis=2)
    diff[seen < 255] = 0
    diff[: int(top * h), :] = 0  # the step number and the parts call-out sit at the top
    if corner and len(corner) == 4:  # the step number's own box (x0, y0, x1, y1 in pixels)
        diff[max(0, corner[1]):max(0, corner[3]), max(0, corner[0]):max(0, corner[2])] = 0
    elif corner:  # top=0: only the step number's corner (w, h in pixels); the call-out is found by its colour below
        diff[: corner[1], : corner[0]] = 0
    hsv = cv2.cvtColor(cur, cv2.COLOR_BGR2HSV)  # the call-out's pale cream box
    diff[(hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 225) & (cv2.cvtColor(cur, cv2.COLOR_BGR2LAB)[:, :, 2] > 135)] = 0
    _, th = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)
    if mask:
        return (cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0).astype(np.uint8)
    th = cv2.dilate(cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 0.002 * h * w]
    boxes = [b for b in boxes if b[2] * b[3] < 0.4 * h * w]  # a box over most of the picture: the view changed
    # most changed first: a box that is large but mostly background (a "turn the model" icon) comes last
    changed = lambda b: int((th[b[1]:b[1] + b[3], b[0]:b[0] + b[2]] > 0).sum() * (diff[b[1]:b[1] + b[3], b[0]:b[0] + b[2]] > 60).mean())
    edge = lambda b: b[0] <= 2 or b[1] <= 2 or b[0] + b[2] >= w - 2 or b[1] + b[3] >= h - 2
    return sorted(boxes, key=lambda b: (edge(b), -changed(b)))  # new pieces sit on the model, not at the edge


MAGENTA = (255, 0, 255)  # BGR: a colour LEGO pieces almost never have, so a grid line is never taken for an edge


def tighten(page, crop, dpi=40):
    """A step's cut trimmed to the step itself (x0, y0, x1, y1 in PDF points). A step with no other step after it on
    the page is cut to the page's edge, which takes in what is not the build (a "rate this set" panel, an advert of
    other sets). Two things end a step first:
      a divider    a long straight line the booklet draws across the cut (a vertical one ends it on the right, a
                   horizontal one below)
      a new panel  going down (and to the right) from the step number, where the step's own background colour
                   has (almost) gone and stays gone to the cut's edge: another panel starts there (a model that fills
                   the cut's width takes the background away too, but only for its own rows)
    The step number's corner is always kept."""
    import numpy as np
    import pymupdf
    x0, y0, x1, y1 = crop
    for d in page.get_drawings():
        r = d["rect"]
        if d.get("type") != "s" or d.get("fill") is not None or max(d.get("color") or (1, 1, 1)) > 0.4:
            continue  # a divider is a dark stroke (red ones are arrows and marks)
        if r.width < 3 and r.height > 0.4 * (y1 - y0) and x0 + 60 < r.x0 < x1 and r.y0 < y1 and r.y1 > y0:
            x1 = min(x1, r.x0 - 4)
        if r.height < 3 and r.width > 0.4 * (x1 - x0) and y0 + 60 < r.y0 < y1 and r.x0 < x1 and r.x1 > x0:
            y1 = min(y1, r.y0 - 4)
    pm = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=pymupdf.Rect(x0, y0, x1, y1))
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
    h, w = a.shape[:2]
    if h < 10 or w < 10:
        return (x0, y0, x1, y1)
    corner = a[: max(2, h // 8), w // 3:]  # beside the number: the step's background
    vals, counts = np.unique(corner.reshape(-1, 3) // 8, axis=0, return_counts=True)
    bg = vals[counts.argmax()] * 8 + 4
    share = (np.abs(a - bg).max(axis=2) < 18).mean(axis=1)  # each row: how much of it is the step's background
    start, run = max(3, h // 6), max(3, h // 12)
    cut_y = h
    for y in range(start, h - run):  # another panel: the background goes, and stays gone to the cut's edge
        if (share[y:y + run] < 0.15).all() and (share[y:] < 0.15).mean() > 0.85:
            cut_y = y
            break
    cols = (np.abs(a[:cut_y] - bg).max(axis=2) < 18).mean(axis=0)  # and to the right: columns without it
    start, run = max(3, w // 4), max(3, w // 12)
    for x in range(start, w - run):
        if (cols[x:x + run] < 0.15).all() and (cols[x:] < 0.15).mean() > 0.85:
            x1 = x0 + (x1 - x0) * x / w
            break
    if cut_y < h:
        y1 = y0 + (y1 - y0) * cut_y / h
    return (x0, y0, x1, y1)


def _red(c):
    return bool(c) and c[0] > 0.6 and c[1] < 0.35 and c[2] < 0.35


def arrows(page, crop, dpi=DPI):
    """The booklet's arrows in one step: [{"tip": (x, y), "tail": (x, y)}] in the step picture's pixels. An arrow is
    a red line ending in a small filled red head. The line is often clipped (it starts off the page), so its visible
    start is found by walking back along it in the picture until the red stops: there is the piece it moves."""
    import numpy as np
    import pymupdf
    x0, y0, x1, y1 = crop
    box = pymupdf.Rect(x0, y0, x1, y1)
    dr = page.get_drawings()
    heads = [d for d in dr if d.get("type") == "f" and _red(d.get("fill")) and d["rect"].intersects(box)
             and max(d["rect"].width, d["rect"].height) < 25]
    lines = [(it[1], it[2]) for d in dr if d.get("type") == "s" and _red(d.get("color"))
             for it in d["items"] if it[0] == "l"]
    if not heads:
        return []
    pm = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=box)
    im = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
    k = dpi / 72
    px = lambda p: ((p[0] - x0) * k, (p[1] - y0) * k)
    def red_at(x, y):
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < pm.w and 0 <= yi < pm.h):
            return False
        a = im[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3].reshape(-1, 3)
        return bool(((a[:, 0] > 150) & (a[:, 1] < 110) & (a[:, 2] < 110)).any())
    out = []
    for h in heads:
        pts = [it[1] for it in h["items"] if it[0] == "l"]
        near = [(a, b) for a, b in lines if min(abs(e.x - c.x) + abs(e.y - c.y) for e in (a, b) for c in pts) < 6]
        if not near:
            continue
        a, b = near[0]
        end, far = (a, b) if min(abs(a.x - c.x) + abs(a.y - c.y) for c in pts) < \
            min(abs(b.x - c.x) + abs(b.y - c.y) for c in pts) else (b, a)
        tip = max(pts, key=lambda c: abs(c.x - far.x) + abs(c.y - far.y))
        (ex, ey), (fx, fy) = px((end.x, end.y)), px((far.x, far.y))
        n = max(1, int(np.hypot(fx - ex, fy - ey)))
        dx, dy = (fx - ex) / n, (fy - ey) / n
        last, miss = (ex, ey), 0
        for i in range(1, n):
            x, y = ex + dx * i, ey + dy * i
            if red_at(x, y):
                last, miss = (x, y), 0
            else:
                miss += 1
                if miss > 6 * k / 2:
                    break
        out.append({"tip": tuple(round(v) for v in px((tip.x, tip.y))), "tail": tuple(round(v) for v in last),
                    "width": round(1.5 * k + 6)})
    return out


def arrow_mask(shape, arrs):
    """A 0/1 mask of the arrows (line and head), a little wider: what is not a piece in a change."""
    import cv2
    import numpy as np
    m = np.zeros(shape[:2], np.uint8)
    for a in arrs:
        cv2.line(m, a["tail"], a["tip"], 1, a["width"])
        cv2.circle(m, a["tip"], 3 * a["width"], 1, -1)  # the head
    return m


def grow(page, crop, keep_out=(), dpi=72, margin=0.15):
    """A step's cut grown so it cuts through none of the step's own drawing: each separate shape of drawing that lies
    mostly inside the cut but crosses its edge (a model, a piece and its arrow) is the step's, so the cut takes it
    in whole; a shape mostly outside belongs to a neighbour and stays out. The cut never takes in another step's
    number or panel (keep_out: rects in PDF points), and grows at most `margin` of its size each way (a cut edge,
    not a neighbour: a shape that reaches further is left to the page check).
    Returns (x0, y0, x1, y1)."""
    import cv2
    import numpy as np
    import pymupdf
    x0, y0, x1, y1 = crop
    W, H = page.rect.width, page.rect.height
    mx, my = margin * (x1 - x0), margin * (y1 - y0)
    X0, Y0, X1, Y1 = max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)
    k = dpi / 72
    pm = page.get_pixmap(matrix=pymupdf.Matrix(k, k), clip=pymupdf.Rect(X0, Y0, X1, Y1))
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
    to = lambda v, o: int(round((v - o) * k))  # noqa: E731
    cx0, cy0, cx1, cy1 = to(x0, X0), to(y0, Y0), to(x1, X0), to(y1, Y0)
    inner = a[max(0, cy0):cy1, max(0, cx0):cx1]
    if inner.size == 0:
        return crop
    vals, counts = np.unique(inner.reshape(-1, 3) // 8, axis=0, return_counts=True)
    bg = vals[counts.argmax()] * 8 + 4  # the step's own background: its commonest colour
    ink = (np.abs(a - bg).max(axis=2) >= 24).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    inside = np.zeros_like(ink, dtype=bool)
    inside[max(0, cy0):cy1, max(0, cx0):cx1] = True
    keep = [(to(o[0], X0), to(o[1], Y0), to(o[2], X0), to(o[3], Y0)) for o in keep_out]
    nx0, ny0, nx1, ny1 = cx0, cy0, cx1, cy1
    for i in range(1, n):
        bx, by, bw, bh, area = st[i]
        if area < 12 or bw > 0.95 * pm.w or bh > 0.95 * pm.h:
            continue  # a speck, or the page's own background art
        if min(bw, bh) <= 4 * k and max(bw, bh) > 30 * k:
            continue  # a thin straight line: a divider between steps, not a step's drawing
        crosses = bx < cx0 or by < cy0 or bx + bw > cx1 or by + bh > cy1
        if not crosses:
            continue
        mine = (lab[by:by + bh, bx:bx + bw] == i)
        share = (mine & inside[by:by + bh, bx:bx + bw]).sum() / max(1, mine.sum())
        if share < 0.5:
            continue  # mostly outside: a neighbour's
        r = (bx, by, bx + bw, by + bh)
        if any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3] for o in keep):
            continue  # it would take in another step's number or panel
        nx0, ny0, nx1, ny1 = min(nx0, r[0]), min(ny0, r[1]), max(nx1, r[2]), max(ny1, r[3])
    pad = 3
    back = lambda v, o: o + v / k  # noqa: E731
    return (max(0, back(nx0 - (pad if nx0 < cx0 else 0), X0)), max(0, back(ny0 - (pad if ny0 < cy0 else 0), Y0)),
            min(W, back(nx1 + (pad if nx1 > cx1 else 0), X0)), min(H, back(ny1 + (pad if ny1 > cy1 else 0), Y0)))


def callout_above(page, crop, number, dpi=50, reach=220, gap=45):
    """A step's parts call-out drawn ABOVE its number (some booklets put it there): a panel lighter than the page
    around it, ending at most `gap` points above the number, inside the step's columns. Returns the new top (PDF
    points), or None when there is none."""
    import numpy as np
    import pymupdf
    x0, y0, x1, y1 = crop
    top = max(0, number[1] - reach)
    if number[1] - top < 20:
        return None
    k = dpi / 72
    pm = page.get_pixmap(matrix=pymupdf.Matrix(k, k), clip=pymupdf.Rect(x0, top, x1, number[1]))
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3].astype(int)
    if a.size == 0:
        return None
    lum = a.mean(axis=2)
    bg = np.median(lum[-max(2, pm.h // 10):])  # just above the number: the page's own background
    light = (lum > bg + 18).mean(axis=1)  # each row: how much of it is lighter than the background (a panel)
    rows = np.nonzero(light > 0.25)[0]
    if not len(rows):
        return None
    end = rows.max()  # the panel's bottom row, then up while it lasts
    if (pm.h - end) / k > gap:
        return None
    start = end
    while start > 0 and light[start - 1] > 0.15:
        start -= 1
    if (end - start) / k < 12:
        return None  # a line, not a panel
    return top + start / k - 3
