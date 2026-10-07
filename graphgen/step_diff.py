"""v8 LEGO: what each booklet step adds, found by comparing its picture with the previous step's.

LEGO booklets draw consecutive steps from the same camera, so after aligning the previous picture onto the
current one (ORB features + a RANSAC homography) the pixels that differ are the pieces this step adds. Those
regions are boxed in red on the step's picture, so Claude is shown WHERE the new pieces are instead of having to
find them; it still reads which pieces they are and their placements.

Left out of the boxes: the parts call-out (the top of the picture and its pale box: it lists the pieces, it does
not show where they go), the step number, and specks. A step whose picture does not align with the previous one
(the booklet turned the model, zoomed, or started a sub-assembly) gets no boxes and says so.
"""
import collections

from . import ar

DPI = 150


def _bgr(page, crop):
    import numpy as np
    import pymupdf
    pm = page.get_pixmap(matrix=pymupdf.Matrix(DPI / 72, DPI / 72), clip=pymupdf.Rect(*crop))
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.h, pm.w, pm.n)[:, :, :3]
    return a[:, :, ::-1].copy()


def changed_regions(prev, cur, min_inliers=60):
    """Boxes (x, y, w, h) on `cur` where it differs from `prev` once aligned; None if the two do not align."""
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
    diff[: int(0.22 * h), :] = 0  # the step number and the parts call-out sit at the top
    hsv = cv2.cvtColor(cur, cv2.COLOR_BGR2HSV)  # the call-out's pale cream box
    diff[(hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 225) & (cv2.cvtColor(cur, cv2.COLOR_BGR2LAB)[:, :, 2] > 135)] = 0
    _, th = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)
    th = cv2.dilate(cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts if cv2.contourArea(c) > 0.002 * h * w]
    return [b for b in boxes if b[2] * b[3] < 0.4 * h * w]  # a box over most of the picture: the view changed


def step_images(pdf_bytes):
    """[{step, page, crop, png, boxes}] for a booklet with step numbers as text, step 1 first: each step's picture
    as PNG, with the regions it adds boxed in red (boxes None when it does not align with the previous step).
    [] for a scanned booklet."""
    import cv2
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    where = ar.booklet_steps(doc)
    out, prev = [], None
    for n, (page, crop) in enumerate(where, 1):
        cur = _bgr(doc[page - 1], crop)
        boxes = changed_regions(prev, cur) if prev is not None else None
        marked = cur.copy()
        for x, y, w, h in boxes or ():
            cv2.rectangle(marked, (x, y), (x + w, y + h), (0, 0, 255), 4)
        out.append({"step": n, "page": page, "crop": crop, "boxes": boxes,
                    "png": cv2.imencode(".png", marked)[1].tobytes()})
        prev = cur
    return out


def summary(images):
    c = collections.Counter("first" if i["step"] == 1 else "boxed" if i["boxes"] else "no-align" if i["boxes"] is None
                            else "no-change" for i in images)
    return dict(c)
