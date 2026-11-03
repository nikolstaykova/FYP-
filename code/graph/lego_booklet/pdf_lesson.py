"""A LEGO lesson from the instruction booklet PDF alone.

What it is   the booklet route, end to end: the set's parts list (Rebrickable) and a numbered parts sheet; the
             booklet cut into its steps (booklet_layout, checked page by page by booklet_check); each step's
             picture, the overlay of what changed and the enlarged changes (step_diff); Claude reads each step
             against them (which parts, how many, where, the words); code checks every read and sends problems back;
             repairs place what no step read (recount, symmetry, size by code, allocation), the parts list is a hard
             limit and every piece is used; the lesson is built (record and steps graph, no physical graph: no join
             is guessed from a picture) and registered. A 3-in-1 set's booklet gives model A; a page that combines
             this set with another is left out.
Used for     a lesson for any LEGO set we have the booklet of, with or without a 3D model (DATA_STRUCTURE.md §3.5,
             §8.1).
Where        the command line: python -m graph.lego_booklet.pdf_lesson 30103-1 [--rebuild]; it writes
             data/lessons/booklet/<set>/ (pictures, reads) and registers the lesson through lesson_store.py.
"""
import argparse
import base64
import collections
import json
import pathlib
import re
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from graph.lego_booklet import booklet_size
from graph import lesson_store

ROOT = pathlib.Path(__file__).resolve().parents[3]
NL = "\n"
OUT = ROOT / "data" / "lessons" / "booklet"


class Added(BaseModel):
    part: str = Field(description="the inventory id, exactly as listed (lego-3022)")
    colour: str = Field(description="the inventory colour, exactly as listed")
    count: int = Field(ge=1)
    where: str = Field(description="where it goes, in plain words (on the front two studs of the base, ...)")


class StepRead(BaseModel):
    adds: List[Added] = Field(description="every piece this step adds, as inventory rows")
    callout: List[Added] = Field(description="the pieces drawn in this step's parts call-out box, if it has one "
                                             "(where: '')")
    subassembly: Optional[str] = Field(None, description="if this step builds something apart and attaches it: what")
    times: int = Field(1, description="how many times the booklet says to build this step (2x)")
    view: Optional[str] = Field(None, description="if the model is turned, flipped or zoomed in this step: how")
    instruction: str = Field(description="what the learner does, plainly, with colours and sizes")
    description: str = Field(description="the whole model as this step's picture shows it, in full: every part you "
                                         "can see, its colour and size, where it sits and which way it faces, and "
                                         "how the parts sit against each other (several sentences)")
    what_changed: str = Field(description="what is different from the previous picture, from the overlay and the two "
                                          "pictures: each new piece, where it went, and anything moved, turned or "
                                          "covered up ('' for the first step)")
    build_name: str = Field("", description="a short name for what this step's build makes, as a child would say "
                                          "it ('mailbox', 'flower stand', 'heart roof', 'Stephanie')")
    confidence: float = Field(ge=0, le=1)


SYSTEM = """You read a LEGO instruction booklet one step at a time, for a lesson that guides a child through it.
For each step you get the previous step's picture and this step's picture; red boxes on this one mark what changed.
Say which pieces this step ADDS (only the new ones), naming each with an id and colour from the set's inventory
EXACTLY as listed, and how many. Read the step's parts call-out box (the small box listing pieces with "1x", "2x")
separately. Say where each piece goes in plain words, whether the model is turned over, and write the instruction.
Describe the whole model as this picture shows it, in full (every part you can see, its colour, size, where it
sits and which way it faces), and separately what is different from the previous picture. The OVERLAY is made by
code: the previous picture is lined up on this one, what was already there is faded to grey, and what changed keeps
its colour with a red outline. It is a strong hint, not the truth: it can miss a change (a piece hidden under another,
a picture that did not line up) or mark something that is not a piece; the step's own picture decides.
LEGO models are often built symmetrically: a piece put on one side usually has a twin on the other side, added in
the same step even when the far side is hidden from view. Count the hidden twins too, and say "one on each side".
Arrows are never parts and never a change: an arrow shows a piece moving. The piece is at the arrow's START (look
there to see which piece it is); it goes where the arrow points. You are told where each arrow starts and ends, with
the area around its start enlarged.
A piece drawn beside the model with arrows pointing to its place is added in THAT step (the arrows show where it
goes); in the next picture it is in place and is not new there. You are told what the previous step added: never
add those again.
Never invent a piece that is not in the inventory; if you cannot tell which inventory row it is, pick the closest by
shape and colour and lower your confidence. The red boxes and the step numbers are reading aids for you: never
mention them, the overlay, the booklet, its pages or its printing in the instruction or the descriptions; write for
the child holding the pieces."""


def _img(png):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}}


def zooms(png, scale=2, pad=24):
    """The booklet's red boxes (what a step changed) cut out of a step picture and enlarged: [png bytes]. A box as
    wide as the picture (the page footer) is not a change."""
    import cv2
    import numpy as np
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    b, g, r = im[..., 0].astype(int), im[..., 1].astype(int), im[..., 2].astype(int)
    red = ((r > 200) & (g < 70) & (b < 70)).astype(np.uint8)
    out, seen = [], []
    for c in cv2.findContours(red, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if w < 40 or h < 40 or w > 0.9 * im.shape[1]:
            continue
        if any(abs(x - a) + abs(y - b_) + abs(x + w - a - c_) + abs(y + h - b_ - d) < 80 for a, b_, c_, d in seen):
            continue  # a box's inner and outer edge are one box
        seen.append((x, y, w, h))
        crop = im[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ok, enc = cv2.imencode(".png", crop)
        if ok:
            out.append(enc.tobytes())
    return out[:4]


DPI = 300  # the booklets' own pictures are 300 DPI: a thin seam between two tiles survives


def arrow_crop(set_id, step, arrs, pad=110, scale=2):
    """The area around the arrows' starts (where the piece they move is drawn), enlarged, from the clean PDF (no
    red boxes): png bytes."""
    import cv2
    import pymupdf
    from graph.lego_booklet import step_diff
    doc = pymupdf.open(ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf")
    im = step_diff._bgr(doc[step["page"] - 1], step["crop"], DPI)
    xs, ys = [a["tail"][0] for a in arrs], [a["tail"][1] for a in arrs]
    x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
    x1, y1 = min(im.shape[1], max(xs) + pad), min(im.shape[0], max(ys) + pad)
    crop = cv2.resize(im[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.imencode(".png", crop)[1].tobytes()


def prev_of(steps, s):
    """The step whose picture comes before this one: the step before it in its own sub-build or build (the layout's
    `prev`); the first step of a sub-build or build has none. A cache cut before the layout parser: the list order."""
    if "kind" in s:
        return next((x for x in steps if x["step"] == s["prev"]), None) if s.get("prev") else None
    k = steps.index(s)
    return steps[k - 1] if k else None


def _layout(doc, fixes=None):
    """booklet_layout.cut (with the page check's fixes), with each panel that stands alone (a figure: no line from it into a step) made a build
    of its own, and each step given its id by the booklet's own numbers (stand-7, stand-7.1)."""
    from graph.lego_booklet import booklet_layout
    steps = booklet_layout.cut(doc, fixes)
    booklet_layout.split_columns(doc, steps)
    builds = max([s["build"] for s in steps] + [-1]) + 1
    alone = {}
    for s in steps:
        if s["kind"] == "sub" and s.get("attached_by", "").startswith("stands alone"):
            if s["box"] not in alone:
                alone[s["box"]] = builds
                builds += 1
            k = sum(1 for x in steps if x.get("box") == s["box"] and x["step"] <= s["step"])
            s.update(kind="main", build=alone[s["box"]], label=s["label"].split("· ")[-1] if "· " in s["label"]
                     else str(k))  # numbered from 1, as a build of its own
    for s in steps:
        s["attaches"] = [a for a in s["attaches"] if a not in alone]
    return steps


def corner(s):
    """The step number's box in the step picture's pixels (it is not always the cut's top-left corner)."""
    from graph.lego_booklet import step_diff
    if not s.get("number"):
        return step_diff.number_corner(DPI)
    k = DPI / 72
    n = s["number"]
    return (int((n[0] - s["crop"][0]) * k) - 6, int((n[1] - s["crop"][1]) * k) - 6,
            int((n[2] - s["crop"][0]) * k) + 6, int((n[3] - s["crop"][1]) * k) + 6)


CHECK_LAYOUT = True  # booklet_check: a look at each page before its steps are read (off: code's cut alone)


THREE_IN_ONE = {"672"}  # Rebrickable's 'Creator 3-in-1': one set of pieces, three models, each from all of them


def _theme(set_id):
    import csv
    import gzip
    f = ROOT / "data" / "sources" / "rebrickable" / "sets.csv.gz"
    if not f.exists():
        return None
    with gzip.open(f, "rt") as fh:
        return next((r["theme_id"] for r in csv.DictReader(fh) if r["set_num"] == set_id), None)


def first_model(set_id, steps, theme=None):
    """A 3-in-1 set's booklet holds three models, each built from ALL the set's pieces (the numbers start at 1 for
    each): the lesson is the first (model A, the box's); the others are not more steps of it. Only for a 3-in-1 set
    (its Rebrickable theme): another set's second build that starts at 1 (a second vehicle, a figure) is part of the
    set. Returns (steps, [alternate model: {build, steps, pages}])."""
    if (theme or _theme(set_id)) not in THREE_IN_ONE:
        return steps, []
    builds = {}
    for s in steps:
        if s["kind"] == "main":
            builds.setdefault(s["build"], []).append(s)
    models = [b for b, ms in builds.items() if ms[0]["label"] == "1" and len(ms) >= 5]
    if len(models) < 2:
        return steps, []
    first = min(s["step"] for s in steps if s["build"] == models[1])  # where model B starts: the rest are alternates
    alts = [{"build": b, "steps": len(builds[b]), "pages": sorted({s["page"] for s in steps if s["build"] == b})}
            for b in models[1:]]
    return [s for s in steps if s["step"] < first], alts


def booklet(set_id, out):
    """The booklet's steps as pictures, cut by code (cached): [{step, kind, build, box, times, prev, page, crop,
    boxes, png, arrows}] in the lesson's order (booklet_layout: builds, main steps, the sub-builds inside them)."""
    import cv2
    import pymupdf
    from graph.lego_booklet import step_diff
    meta = out / "steps.json"
    if meta.exists():
        steps = json.loads(meta.read_text())
        if steps and "kind" in steps[0]:
            return steps
        old = out / "before_layout"  # a cut from before the layout parser: kept aside, cut again
        old.mkdir(exist_ok=True)
        for f in ("steps.json", "steps", "overlays", "zooms", "reads.json"):
            if (out / f).exists():
                (out / f).rename(old / f)
    doc = pymupdf.open(ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf")
    from graph.lego_booklet import booklet_check, booklet_layout  # a scan: its step numbers read first (OCR, and Claude per page)
    if booklet_layout.scanned(doc[min(2, doc.page_count - 1)]):
        print(f"  scanned booklet: numbers read {booklet_check.read_numbers(set_id, out)}")
    # Claude looks at each page with code's cut drawn on it; code checks its answers
    fixes = booklet_check.check(set_id, out=out)["fixes"] if CHECK_LAYOUT else None
    steps = _layout(doc, fixes)
    steps, alts = first_model(set_id, steps)
    if alts:
        (out / "alternate_models.json").write_text(json.dumps(alts, indent=1))
        print(f"  3-in-1 set: model A only ({len(alts)} alternate models in the booklet left for their own lessons)")
    (out / "steps").mkdir(parents=True, exist_ok=True)
    imgs = {}
    fixed = {k for k in ((fixes or {}).get("crops") or {})}  # boxes the page check set: not trimmed again
    for s in steps:
        if s["kind"] == "main" and not s.get("box") and s.get("number") and booklet_check.key(s["page"], s) not in fixed:
            s["crop"] = [round(v, 1) for v in step_diff.tighten(doc[s["page"] - 1], s["crop"])]
    for s in steps:  # a parts call-out drawn above the number is the step's too (some booklets put it there)
        if s["kind"] == "main" and not s.get("box") and s.get("number"):
            up = step_diff.callout_above(doc[s["page"] - 1], s["crop"], s["number"])
            panels = booklet_layout._boxes(doc[s["page"] - 1])  # a sub-build panel above is its own step, not this
            if up is not None and any(b.x0 < s["crop"][2] and s["crop"][0] < b.x1 and b.y1 > up and b.y0 < s["crop"][1]
                                      for b in panels):
                up = None
            if up is not None and up < s["crop"][1]:
                s["crop"][1] = round(up, 1)
    for s in steps:  # and no cut goes through the step's own drawing (a model, a piece and its arrow): it grows
        if s["kind"] == "main" and not s.get("box"):  # to take the cut shapes in, never another step's number
            page = doc[s["page"] - 1]
            keep = [tuple(x["number"]) for x in steps if x["page"] == s["page"] and x is not s and x.get("number")]
            s["crop"] = [round(v, 1) for v in step_diff.grow(page, s["crop"], keep)]
        imgs[s["step"]] = step_diff._bgr(doc[s["page"] - 1], s["crop"], DPI)
    for s in steps:
        cur = imgs[s["step"]]
        pv = prev_of(steps, s)
        boxes = step_diff.changed_regions(imgs[pv["step"]], cur, top=0, corner=corner(s)) if pv else None
        marked = cur.copy()
        for x, y, w, h in boxes or ():
            cv2.rectangle(marked, (x, y), (x + w, y + h), (0, 0, 255), max(4, round(4 * DPI / 150)))
        f = out / "steps" / f"step{s['step']}.png"
        cv2.imwrite(str(f), marked)
        s.update(boxes=boxes, png=str(f.relative_to(ROOT)), arrows=step_diff.arrows(doc[s["page"] - 1], s["crop"], DPI))
    meta.write_text(json.dumps(steps, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    return steps


def overlays(set_id, steps, out):
    """Each step's picture laid over the previous one, by code (cached in out/overlays/): the previous picture is
    aligned onto this one (step_diff: ORB features + a homography), everything that was already there is faded to
    grey, and what changed stays in full colour with a red outline. Rendered from the PDF without the red boxes,
    so the boxes are not taken for a change. {step: path} for the steps that align with the previous one."""
    import cv2
    import numpy as np
    import pymupdf
    from graph.lego_booklet import step_diff
    folder = out / "overlays"
    folder.mkdir(parents=True, exist_ok=True)
    doc, got, masks = None, {}, {}
    for s in steps:
        f = folder / f"step{s['step']}.png"
        if f.exists():
            got[s["step"]] = str(f.relative_to(ROOT))
            continue
        doc = doc or pymupdf.open(ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf")
        cur = step_diff._bgr(doc[s["page"] - 1], s["crop"], DPI)
        pv = prev_of(steps, s)
        prev = step_diff._bgr(doc[pv["page"] - 1], pv["crop"], DPI) if pv else None
        m = step_diff.gone(cur, step_diff.changed_regions(prev, cur, mask=True, top=0, corner=corner(s))) \
            if prev is not None else None
        if m is not None and pv.get("arrows"):  # a piece that floated on arrows is now in place: moved, not new
            m[step_diff.moved(pv["arrows"], masks.get(pv["step"]), m.shape) > 0] = 0
        masks[s["step"]] = None if m is None else m.copy()
        if m is None:
            continue
        if s.get("arrows"):  # an arrow is not a piece: never a change
            m[step_diff.arrow_mask(m.shape, s["arrows"]) > 0] = 0
        m = cv2.dilate(m, np.ones((5 * DPI // 150, 5 * DPI // 150), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        H, W = m.shape
        for i in range(1, n):  # not a change: specks, page lines, the footer, anything touching the picture's edge
            x, y, w, h, area = st[i]
            sc = DPI / 150  # the sizes below were set at 150 DPI
            edge = x <= 2 or y <= 2 or x + w >= W - 2 or y + h >= H - 2  # touching the edge: a footer or a page
            if area < 150 * sc * sc or min(w, h) < 12 * sc or max(w, h) > 8 * min(w, h) or \
                    (edge and (max(w, h) > 0.8 * max(W, H) or min(w, h) < 30 * sc)) or \
                    (w * h > 0.2 * W * H and area < 0.3 * w * h):  # line, not a piece drawn up to it; a large, hollow one is
                m[lab == i] = 0                                                         # the page's background
        grey = cv2.cvtColor(cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        faded = cv2.addWeighted(grey, 0.35, np.full_like(cur, 255), 0.65, 0)
        img = np.where(m[..., None] > 0, cur, faded)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, [c for c in cnts if cv2.contourArea(c) > 30], -1, (0, 0, 255), 2)
        cv2.imwrite(str(f), img)
        got[s["step"]] = str(f.relative_to(ROOT))
    return got


IDS = re.compile(r"\blego-[0-9a-z]+|\b\d{4,5}[a-z]?\d*(?:pr\d+|c\d+)\w*\b")


def check_words(answer):
    """[problem] for the words a child reads: no part ids (lego-3069b, 92818c01pr0001) in them."""
    return [f"the {k.replace('_', ' ')} names a part by its id ({', '.join(sorted(set(IDS.findall(answer[k]))))}): name "
            f"it by colour, size and shape" for k in ("instruction", "description", "what_changed")
            if answer.get(k) and IDS.search(answer[k])]


COUNT_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
               "eight": 8, "nine": 9, "ten": 10, "both": 2, "single": 1}
KINDS = ("plate", "brick", "tile", "slope", "wedge", "bracket", "wheel", "tyre", "tire", "panel", "bar", "clip",
         "hinge", "axle", "pin", "cone", "dish", "arch", "round", "lever", "jumper", "grille", "mudguard")


def check_counts(read, inventory):
    """[problem] where a step's words say a different number of a piece than it adds ('take two yellow 2 x 2
    plates', and it adds one): the count right before the piece's colour or kind, sizes ('2 x 2') not counted."""
    names = {(r["part"], r["colour"]): r.get("name", "") for r in inventory}
    text = re.sub(r"\b\d+\s*[x×]\s*\d+(\s*[x×]\s*[\d/ ]+)?\b", " SIZE ", (read.get("instruction") or "").lower())
    words = re.findall(r"[a-z]+|\d+", text)
    out = []
    for a in read["adds"]:
        colour = (a["colour"] or "").lower().split()[-1:] or [""]
        kind = next((k for k in KINDS if k in names.get((a["part"], a["colour"]), "").lower()), None)
        said = []
        for i, w in enumerate(words):
            n = COUNT_WORDS.get(w) or (int(w) if w.isdigit() and int(w) <= 20 else None)
            if not n:
                continue
            ahead = words[i + 1:i + 6]
            if colour[0] in ahead and (kind is None or any(x.startswith(kind) for x in ahead)):
                said.append(n)
        if said and a["count"] not in said and max(said) > 1:
            out.append(f"the words say {max(said)} {a['colour']} {kind or 'pieces'} ({a['part']}), but the step adds "
                       f"{a['count']}: make the count and the words agree with the picture")
    return out


_RGB = {}


def _colour_rgb():
    """Rebrickable's colour name -> (r, g, b, transparent)."""
    if not _RGB:
        import csv
        import gzip
        with gzip.open(ROOT / "data" / "sources" / "rebrickable" / "colors.csv.gz", "rt") as f:
            for r in csv.DictReader(f):
                h = r["rgb"]
                _RGB[r["name"]] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), r["is_trans"] == "True")
    return _RGB


def check_colours(read, s, doc):
    """[problem] where a step is read as adding a piece whose colour is nowhere in what the step changed (the
    changed areas code found against the previous step; the whole step when it found none): a black plate read
    where nothing black appeared. White, transparent and unknown colours are not judged (white is in every picture)."""
    import cv2
    import numpy as np
    from graph.lego_booklet import step_diff
    page = doc[s["page"] - 1]
    im = step_diff._bgr(page, s["crop"], DPI)
    boxes = s.get("boxes") or []
    if boxes:
        mask = np.zeros(im.shape[:2], bool)
        for x, y, w, h in boxes:
            mask[max(0, y):y + h, max(0, x):x + w] = True
    else:
        mask = np.ones(im.shape[:2], bool)
    all_lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab, whole = all_lab[mask], all_lab.reshape(-1, 3)
    if lab.size == 0:
        return []
    out = []
    for a in read["adds"]:
        c = _colour_rgb().get(a["colour"])
        if not c or c[3] or a["colour"].lower() in ("white", "[no color/any color]"):
            continue
        ref = cv2.cvtColor(np.uint8([[[c[2], c[1], c[0]]]]), cv2.COLOR_BGR2LAB).astype(np.float32)[0, 0]
        dark = max(c[:3]) < 70  # black is drawn dark grey: a wider match
        tol = 45 if dark else 40  # booklets draw colours lighter
        if (np.linalg.norm(lab - ref, axis=1) < tol).mean() >= 0.002:
            continue
        if (np.linalg.norm(whole - ref, axis=1) < tol).mean() < 0.001:  # the change boxes can miss a piece: only a
            out.append(f"{a['part']} {a['colour']}: no {a['colour'].lower()} anywhere in this step's picture: is it "
                       f"really this colour, and really added in this step?")  # colour absent from the whole step
    return out


def check_read(read, inventory, used):
    """[problem] for one step's read: unknown rows, more than the inventory has left, call-out disagreeing."""
    rows = {(r["part"], r["colour"]): r for r in inventory}
    out = check_words(read) + check_counts(read, inventory)
    for a in read["adds"]:
        r = rows.get((a["part"], a["colour"]))
        if r is None:
            out.append(f"{a['part']} {a['colour']} is not in the inventory (use an id and colour exactly as listed)")
            continue
        left = r["count"] - used[(a["part"], a["colour"])]
        if a["count"] * read.get("times", 1) > left:
            out.append(f"{a['part']} {a['colour']}: this step adds {a['count'] * read.get('times', 1)}, only {left} left")
    if read["callout"]:
        want = collections.Counter({(a["part"], a["colour"]): a["count"] for a in read["callout"]})
        got = collections.Counter({(a["part"], a["colour"]): a["count"] for a in read["adds"]})
        if want != got:
            out.append(f"the call-out shows {dict(want)}, the step adds {dict(got)}: they should agree")
    return out


def part_sheet(inventory, out, cell=160, cols=6):
    """The set's parts as pictures, numbered as the inventory is listed (#1, #2, ...), on one sheet: the matcher sees
    what each row looks like instead of only its name. Rebrickable's render of the part in its colour, else the
    element photo; a row with neither keeps its number and name only. Cached in out/parts/. Returns the sheet path."""
    import cv2
    import numpy as np
    import urllib.request
    import gzip
    import csv
    reb = ROOT / "data" / "sources" / "rebrickable"
    colour_id = {r["name"]: r["id"] for r in csv.DictReader(gzip.open(reb / "colors.csv.gz", "rt"))}
    elements = {}
    for r in csv.DictReader(gzip.open(reb / "elements.csv.gz", "rt")):
        elements.setdefault((r["part_num"], r["color_id"]), r["element_id"])
    folder = out / "parts"
    folder.mkdir(parents=True, exist_ok=True)
    tiles = []
    for n, r in enumerate(inventory, 1):
        num, cid = r["part"][len("lego-"):], colour_id.get(r["colour"], "")
        f = folder / f"{n:02d}_{num}_{cid}.png"
        if not f.exists():
            urls = [f"https://cdn.rebrickable.com/media/parts/ldraw/{cid}/{num}.png"]
            if (num, cid) in elements:
                urls.append(f"https://cdn.rebrickable.com/media/parts/elements/{elements[(num, cid)]}.jpg")
            for u in urls:
                try:
                    data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "pinpoint"}),
                                                  timeout=20).read()
                except Exception:
                    continue
                im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
                if im is not None:
                    if im.ndim == 3 and im.shape[2] == 4:  # transparent render on white
                        a = im[..., 3:4] / 255.0
                        im = (im[..., :3] * a + 255 * (1 - a)).astype(np.uint8)
                    cv2.imwrite(str(f), im)
                    break
        im = cv2.imread(str(f)) if f.exists() else None
        tile = np.full((cell + 40, cell, 3), 255, np.uint8)
        if im is not None:
            k = (cell - 10) / max(im.shape[:2])
            im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            y, x = 35 + (cell - 10 - im.shape[0]) // 2, (cell - im.shape[1]) // 2
            tile[y:y + im.shape[0], x:x + im.shape[1]] = im
        cv2.putText(tile, f"#{n}  x{r['count']}", (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.rectangle(tile, (0, 0), (cell - 1, cell + 39), (200, 200, 200), 1)
        tiles.append(tile)
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    path = out / "parts_sheet.png"
    cv2.imwrite(str(path), sheet)
    return path


def context(steps, s):
    """What the reader is told about where this step sits: in a sub-build (and whether it starts from nothing), or a
    main step that puts finished sub-builds on (their pieces are counted in their own steps). '' for a plain step."""
    if "kind" not in s:
        return ""
    if s["kind"] == "sub":
        own = [x for x in steps if x.get("box") == s["box"]]
        main = next((x for x in steps if s["box"] in x.get("attaches", [])), None)
        txt = (f"THIS IS STEP {own.index(s) + 1} OF {len(own)} OF A SUB-BUILD (a piece built apart, in a box on the "
               f"page, then put on the model as one piece in step {main['step'] if main else '?'})"
               + (f"; THE BOOKLET SAYS TO BUILD IT {s['times']} TIMES (count each piece once here: code multiplies)"
                  if s["times"] > 1 else "") + ".")
        if s is own[0]:
            txt += " It starts from nothing: every piece in this picture is new."
        return txt
    if s.get("attaches"):
        subs = [x for x in steps if x.get("box") in s["attaches"]]
        return (f"THIS STEP PUTS ON {len(s['attaches'])} FINISHED SUB-BUILD(S), built just before in steps "
                f"{', '.join(str(x['step']) for x in subs)}. The sub-build's own pieces are counted in those steps: "
                f"do not list them again. But a step that puts a sub-build on usually ALSO adds loose pieces of its "
                f"own (a plate under it, a tile beside it): look at everything else that is new in this picture and "
                f"list every one of those pieces. Say in the instruction where the sub-build goes and where each "
                f"loose piece goes.")
    pv = prev_of(steps, s)
    if pv is None and s["step"] != steps[0]["step"]:
        return "THIS STEP STARTS A NEW, SEPARATE BUILD: it starts from nothing; every piece in this picture is new."
    return ""


def read_steps(set_id, steps, inventory, model="sonnet", effort="high", repairs=2, sheet=None, overlay=None,
               size=None):
    """Claude reads each step, with the previous picture; code checks each read and sends problems back.
    size: {} to measure each step's new area by code (booklet_size) and ask once where it is not explained; filled
    with the areas and scale once step 1 is read."""
    import pymupdf
    from graph import extract
    doc = pymupdf.open(ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf")  # the change's colours (check_colours)
    used = collections.Counter()
    reads, phases = [], []
    for k, s in enumerate(steps):
        inv_text = "\n".join(f"- #{n} | {r['part']} | {r['colour']} | {r['name']} | {r['count']} in the set, "
                             f"{r['count'] - used[(r['part'], r['colour'])]} not used yet"
                             for n, r in enumerate(inventory, 1))
        content = [{"type": "text", "text": f"Set {set_id}. STEP {s['step']} of {len(steps)}.\nINVENTORY (# | id | "
                                            f"colour | name | count):\n{inv_text}"}]
        if sheet:
            content += [{"type": "text", "text": "THE SET'S PARTS, numbered as the inventory (#n, xcount in the set). "
                                                 "Match every new piece in this step to one of these by shape, size "
                                                 "and colour, and count the copies:"},
                        _img(pathlib.Path(sheet).read_bytes())]
        pv = prev_of(steps, s)
        where = context(steps, s)
        if where:
            content.append({"type": "text", "text": where})
        if pv:
            last = next(r for r in reads if r["step"] == pv["step"])
            content.append({"type": "text", "text": f"THE PREVIOUS STEP ({pv['step']}) ADDED (already on the "
                                                    f"model, or shown with arrows going on; not new here):" + NL +
                            (NL.join(f"- {a['count']}x {a['part']} {a['colour']}: {a['where']}" for a in last["adds"])
                             or "- nothing")})
            content += [{"type": "text", "text": f"PREVIOUS STEP ({pv['step']}):"},
                        _img((ROOT / pv["png"]).read_bytes())]
        content += [{"type": "text", "text": f"THIS STEP ({s['step']}); red boxes mark what changed:"},
                    _img((ROOT / s["png"]).read_bytes())]
        if overlay and overlay.get(s["step"]):
            content += [{"type": "text", "text": "OVERLAY (made by code; what was already there faded to grey, what "
                                                 "changed in colour with a red outline):"},
                        _img((ROOT / overlay[s["step"]]).read_bytes())]
        elif pv:
            content.append({"type": "text", "text": "(No overlay: this picture does not line up with the previous one, "
                                                    "so compare the two pictures yourself.)"})
        if s.get("arrows"):
            content.append({"type": "text", "text": "ARROWS in this step (found by code in the PDF, in this picture's "
                                                    "pixels; not parts):" + NL + NL.join(
                f"{i}. starts at {a['tail']}, points to {a['tip']}" for i, a in enumerate(s["arrows"], 1))
                + NL + "THE AREA AROUND THE ARROWS' START (the piece they move), enlarged:"})
            content.append(_img(arrow_crop(set_id, s, s["arrows"])))
        if sheet:
            z = zooms((ROOT / s["png"]).read_bytes())
            if z:
                content.append({"type": "text", "text": "WHAT THIS STEP CHANGED, enlarged:"})
                content += [_img(x) for x in z]
        problems, tries = None, 0
        while True:
            t0 = time.monotonic()
            read, st = extract.claude_json(SYSTEM, content, StepRead, model=model, effort=effort, timeout=600)
            if "kind" in s:
                read["times"] = s["times"]  # how many times is the layout's (a sub-build's "2x"), not a guess
            problems = check_read(read, inventory, used) + check_colours(read, s, doc)  # the change's own colours
            if size is not None and not tries and size["areas"].get(s["step"]):  # asked once: the area is evidence,
                seen = read  # not the truth. A step that puts a sub-build on: its pieces count as new area here too
                if s.get("attaches"):
                    subs = [x["step"] for x in steps if x.get("box") in s["attaches"]]
                    seen = {**read, "adds": read["adds"] + [{**a, "count": a["count"]} for r in reads if r["step"] in subs
                                                            for a in r["adds"]]}
                problems += booklet_size.check(seen, size["areas"][s["step"]],
                                               booklet_size.calibration(reads, size["areas"]))
            phases.append({"step": s["step"], "try": tries, "seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"),
                           "problems": problems})
            if not problems or tries >= repairs:
                break
            tries += 1
            content = content + [{"type": "text", "text": "Your answer had problems; answer again for this step:\n- " +
                                                          "\n- ".join(problems)}]
        for a in read["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * read.get("times", 1)
        reads.append({**read, "step": s["step"], "problems": [x for x in problems if "area in this picture" not in x]})
        if not k and size is not None and len(read["adds"]) == 1 and read["adds"][0]["count"] == 1:
            # step 1 adds one piece alone: its area gives the pictures' scale
            areas, scale = booklet_size.measure(set_id, steps, read["adds"][0]["part"][len("lego-"):],
                                                sorted({r["colour"] for r in inventory}), DPI)
            size.update(areas=areas, scale=scale)
    leftover = [f"{r['part']} {r['colour']}: {r['count'] - used[(r['part'], r['colour'])]} never added"
                for r in inventory if r["count"] > used[(r["part"], r["colour"])]]
    return reads, leftover, phases


class Seen(BaseModel):
    part: str
    colour: str
    step: int
    in_change: int = Field(ge=0, description="how many copies of this piece are inside what this step changed")
    where: str = Field(description="where they sit, for the instruction ('' when none)")


class Counts(BaseModel):
    seen: List[Seen]


def reconcile(set_id, steps, reads, inventory, leftover, model="opus", effort="high", rounds=1):
    """Pieces no step added: Claude counts each one inside every step's change (the step's picture and its changed
    area enlarged), without being told what the steps were read to add, so a step already holding a copy does not
    draw the rest. Code then gives each copy to the first step that shows more copies than its read has, within what
    is left. Returns (reads, leftover, phase)."""
    from graph import extract
    if not leftover:
        return reads, leftover, None
    used = collections.Counter()
    for r in reads:
        for a in r["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * r.get("times", 1)
    left = {(r["part"], r["colour"]): r["count"] - used[(r["part"], r["colour"])] for r in inventory
            if r["count"] > used[(r["part"], r["colour"])]}
    names = {(r["part"], r["colour"]): r["name"] for r in inventory}
    missing = NL.join(f"- {k[0]} | {k[1]} | {names.get(k, '')}" for k in left)
    content = [{"type": "text", "text": f"Set {set_id}. For each of these pieces and for every step, count how many "
                                        f"copies are inside what the step changed (the enlarged area): a copy there "
                                        f"is one the step adds. Look closely: a flat piece can sit beside or under a "
                                        f"bigger one added with it. Answer every piece for every step, 0 when none."
                                        f"{NL}{missing}{NL}The steps:"}]
    for s in steps:
        png = (ROOT / s["png"]).read_bytes()
        content += [{"type": "text", "text": f"STEP {s['step']}:"}, _img(png)]
        z = zooms(png)
        if z:
            content.append({"type": "text", "text": f"STEP {s['step']}, what it changed, enlarged:"})
            content += [_img(x) for x in z]
    seen, st, counts = {}, {"seconds": 0, "cost_usd": 0}, []
    for _ in range(rounds):  # a hidden piece is missed now and then: keep the higher count of each step
        ans, s1 = extract.claude_json(SYSTEM, content, Counts, model=model, effort=effort, timeout=600)
        st = {k: (st[k] or 0) + (s1.get(k) or 0) for k in st}
        counts.append(ans["seen"])
        for x in ans["seen"]:
            k = (x["part"], x["colour"], x["step"])
            if k not in seen or x["in_change"] > seen[k]["in_change"]:
                seen[k] = x
    by = {r["step"]: r for r in reads}
    taken = []
    for k in list(left):
        for s in steps:  # the booklet's order: the first step showing more than its read has
            x = seen.get((*k, s["step"]))
            r = by.get(s["step"])
            if not x or not r or left[k] <= 0:
                continue
            had = sum(a["count"] for a in r["adds"] if (a["part"], a["colour"]) == k)
            n = min(x["in_change"] - had, left[k])
            if n <= 0:
                continue
            r["adds"].append({"part": k[0], "colour": k[1], "count": n, "where": x["where"]})
            r.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]}")
            left[k] -= n
            taken.append({"part": k[0], "colour": k[1], "count": n, "step": s["step"], "where": x["where"]})
    for k in left:  # copies still left: if only one step was seen adding this piece, the rest go there too
        if left[k] <= 0:
            continue
        seen_in = [sp for sp in steps if (x := seen.get((*k, sp["step"]))) and x["in_change"] > 0 and
                   x["in_change"] > sum(a["count"] for a in by[sp["step"]]["adds"] if (a["part"], a["colour"]) == k)
                   - sum(t["count"] for t in taken if t["step"] == sp["step"] and (t["part"], t["colour"]) == k)]
        if len(seen_in) != 1:
            continue
        where, n = seen_in[0]["step"], left[k]
        r = by[where]
        same = next(a for a in r["adds"] if (a["part"], a["colour"]) == k)
        same["count"] += n
        r.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]} (the only step seen adding it)")
        r.setdefault("problems", []).append(f"{n}x {k[0]} {k[1]} placed here by rule (the only step seen adding it, "
                                            f"but counted fewer): check the picture")
        left[k] = 0
        taken.append({"part": k[0], "colour": k[1], "count": n, "step": where, "where": same["where"], "by": "rule"})
    still = [f"{k[0]} {k[1]}: {n} never added" for k, n in left.items() if n > 0]
    return reads, still, {"step": "reconcile", "try": 0, "seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"),
                          "problems": still, "placed": taken, "counts": counts}


SIDE = re.compile(r"\b(near|far|one|each|left|right|front|back|visible) side|\bon the (left|right)\b|\bvisible\b", re.I)
TWIN = re.compile(r"\b(left|right)\b", re.I)


def symmetry(steps, reads, inventory):
    """The booklet route's S11 (left/right twins go together, lesson.py), as code:
      fill   copies of a part still left, where exactly one step added that same number of them on one side (the
             near side, the left, the visible ones): the twins on the far side, hidden from view, go to that step
             too; flagged for review
      twins  a part named Left and its Right twin (Wing 2 x 3 Left / Right) are added in the same step or one
             apart; problems on the later step otherwise
    Returns (reads, still left, phase)."""
    used = collections.Counter()
    for r in reads:
        for a in r["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * r.get("times", 1)
    left = {(r["part"], r["colour"]): r["count"] - used[(r["part"], r["colour"])] for r in inventory
            if r["count"] > used[(r["part"], r["colour"])]}
    placed = []
    for k, n in list(left.items()):
        one_side = [(r, a) for r in reads for a in r["adds"] if (a["part"], a["colour"]) == k and a["count"] == n
                    and SIDE.search(a.get("where") or "")]
        if len(one_side) != 1:
            continue
        r, a = one_side[0]
        a["count"] += n
        r.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]} (twins on the far side)")
        r.setdefault("problems", []).append(f"{n}x {k[0]} {k[1]} added as the hidden twins of the {n} on one side "
                                            f"(symmetry): check the picture")
        left[k] = 0
        placed.append({"part": k[0], "colour": k[1], "count": n, "step": r["step"], "where": a["where"], "by": "symmetry"})
    names = {(r["part"], r["colour"]): r["name"] for r in inventory}
    step_of = {}
    for r in reads:
        for a in r["adds"]:
            step_of.setdefault((a["part"], a["colour"]), r["step"])
    twins = []
    for k, nm in names.items():
        m = TWIN.search(nm or "")
        if not m or m.group(1).lower() != "left":
            continue
        other = next((j for j, n2 in names.items() if j[1] == k[1] and j != k and n2 and
                      TWIN.sub("#", n2) == TWIN.sub("#", nm) and TWIN.search(n2).group(1).lower() == "right"), None)
        if other and k in step_of and other in step_of and abs(step_of[k] - step_of[other]) > 1:
            later = max(step_of[k], step_of[other])
            msg = (f"{nm} (step {step_of[k]}) and {names[other]} (step {step_of[other]}) are left/right twins, but "
                   f"far apart: LEGO puts them in the same step or one after the other")
            next(r for r in reads if r["step"] == later).setdefault("problems", []).append(msg)
            twins.append(msg)
    still = [f"{k[0]} {k[1]}: {n} never added" for k, n in left.items() if n > 0]
    return reads, still, {"step": "symmetry", "try": 0, "seconds": 0, "cost_usd": 0, "problems": twins,
                          "placed": placed}


class Allocation(BaseModel):
    part: str
    colour: str
    count: int = Field(ge=1)
    step: int = Field(description="the step that adds it")
    where: str
    evidence: str = Field(description="what in that step's picture shows the piece")
    confidence: float = Field(ge=0, le=1, description="how sure: below 0.6 is a guess, and a guess is not taken")


class Allocations(BaseModel):
    allocations: List[Allocation]


def allocate(set_id, steps, reads, inventory, model="opus", effort="high", call=None, images=True, use_all=True):
    """The last try before the lesson is final: pieces still on the parts list that no step adds. Claude gets every
    step's picture with what each step was read to add and its descriptions, and gives each piece a step. Code takes
    an answer only for a real step, within what is left, when that step's own description or what changed names the
    piece's colour; each one is flagged on the step for review. Every piece of the set is used: one refused (a guess,
    colour not in the words) still goes to Claude's step, flagged as a guess, and one with no answer to the last step
    (use_all; a 3-in-1 set's model A may leave pieces for its other models, so there it is off).
    Returns (reads, still left, phase or None)."""
    from graph import extract
    used = collections.Counter()
    for r in reads:
        for a in r["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * r.get("times", 1)
    names = {(r["part"], r["colour"]): r["name"] for r in inventory}
    left = {(r["part"], r["colour"]): r["count"] - used[(r["part"], r["colour"])] for r in inventory
            if r["count"] > used[(r["part"], r["colour"])]}
    if not left:
        return reads, [], None
    content = [{"type": "text", "text": f"Set {set_id}. Every piece of the set is used in the build, but no step was "
                                        f"found adding these:" + NL + NL.join(f"- {k[0]} | {k[1]} | {names.get(k, '')} "
                                                                              f"| {n} left" for k, n in left.items())
                                        + NL + "Give each one the step that adds it: the first step whose picture "
                                        "shows it. Each step, with what it was read to add and how it was described:"}]
    for s, r in zip(steps, reads):
        content += [{"type": "text", "text": f"STEP {s['step']}: adds " + (", ".join(
            f"{a['count']}x {a['part']} {a['colour']}" for a in r["adds"]) or "nothing") + f"{NL}Description: "
            f"{r.get('description', '')}{NL}What changed: {r.get('what_changed', '')}"}]
        if images:
            content.append(_img((ROOT / s["png"]).read_bytes()))
    ans, st = (call or (lambda *a: extract.claude_json(*a, model=model, effort=effort, timeout=600)))(
        SYSTEM, content, Allocations)
    by = {r["step"]: r for r in reads}
    taken, refused = [], []
    for x in ans["allocations"]:
        k, r = (x["part"], x["colour"]), by.get(x["step"])
        words = " ".join(str((r or {}).get(f, "")) for f in ("description", "what_changed")).lower()
        colour = re.sub(r"^(trans|light|dark|medium|bright)[- ]", "", k[1].lower()).split()[-1] if k[1] else ""
        why = ("not a step" if not r else "not left" if k not in left or not 0 < x["count"] <= left[k] else
               f"step {x['step']}'s words do not mention {colour}" if colour and colour not in words else
               f"a guess (confidence {x.get('confidence')})" if (x.get("confidence") or 0) < 0.6 else None)
        if why:
            refused.append(f"{x['count']}x {k[0]} {k[1]} to step {x['step']}: {why}")
            continue
        r["adds"].append({"part": k[0], "colour": k[1], "count": x["count"], "where": x["where"]})
        r.setdefault("added_on_reconcile", []).append(f"{x['count']}x {k[0]} {k[1]} (allocated at the end)")
        r.setdefault("problems", []).append(f"{x['count']}x {k[0]} {k[1]} allocated here at the end ({x['evidence']}): "
                                            f"check the picture")
        left[k] -= x["count"]
        taken.append({**x, "by": "allocation"})
    for x in sorted(ans["allocations"] if use_all else [], key=lambda x: -(x.get("confidence") or 0)):  # every
        # piece is used (not in a 3-in-1 set's model A, which may leave some of the set's pieces for B and C): what
        k, r = (x["part"], x["colour"]), by.get(x["step"])                         # is still left goes to Claude's
        n = min(x["count"], left.get(k, 0))                                        # best step, flagged as a guess
        if not r or n <= 0:
            continue
        r["adds"].append({"part": k[0], "colour": k[1], "count": n, "where": x["where"]})
        r.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]} (placed by guess at the end)")
        r.setdefault("problems", []).append(f"{n}x {k[0]} {k[1]} placed here by guess (confidence "
                                            f"{x.get('confidence')}; {x['evidence']}): check the picture")
        left[k] -= n
        taken.append({**x, "count": n, "by": "guess"})
    last = by.get(steps[-1]["step"]) if steps else None
    for k, n in left.items():  # no answer at all: the last step, where the model is finished
        if n > 0 and last is not None and use_all:
            last["adds"].append({"part": k[0], "colour": k[1], "count": n, "where": "unknown: not found in any picture"})
            last.setdefault("added_on_reconcile", []).append(f"{n}x {k[0]} {k[1]} (not found; put on the last step)")
            last.setdefault("problems", []).append(f"{n}x {k[0]} {k[1]} not found in any step: put on the last step, "
                                                   f"find where it goes")
            taken.append({"part": k[0], "colour": k[1], "count": n, "step": last["step"], "by": "last step"})
            left[k] = 0
    still = [f"{k[0]} {k[1]}: {n} never added" for k, n in left.items() if n > 0]
    return reads, still, {"step": "allocate", "try": 0, "seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"),
                          "problems": still + refused, "placed": taken}


class Reworded(BaseModel):
    instruction: str = Field(description="what the learner does in this step, covering EVERY piece listed")
    what_changed: str = Field(description="what is different from the previous picture, every listed piece included")


def reword(set_id, steps, reads, model="sonnet", effort="high", overlay=None):
    """A step the leftover repair added a piece to was worded without it: Claude rewrites its instruction and what
    changed, from its pictures and the full list of what it now adds. Returns the phases (one call per such step)."""
    from graph import extract
    phases = []
    for k, (s, r) in enumerate(zip(steps, reads)):
        if not (r.get("added_on_reconcile") or r.get("reword")):
            continue
        adds = NL.join(f"- {a['count']}x {a['part']} {a['colour']}: {a['where']}" for a in r["adds"])
        content = [{"type": "text", "text": f"Set {set_id}, step {s['step']}. This step adds ALL of these pieces "
                                            f"(the last ones were found after it was first worded):{NL}{adds}{NL}"
                                            f"Its instruction so far: {r['instruction']}{NL}"
                                            f"What changed, so far: {r.get('what_changed', '')}{NL}"
                                            f"Rewrite both so they cover every piece, in the order a child would do "
                                            f"them. Name pieces by colour, size and shape as a child sees them, never "
                                            f"by their ids. The pictures:"}]
        pv = prev_of(steps, s)
        if pv:
            content += [{"type": "text", "text": "PREVIOUS STEP:"}, _img((ROOT / pv["png"]).read_bytes())]
        content += [{"type": "text", "text": "THIS STEP:"}, _img((ROOT / s["png"]).read_bytes())]
        if overlay and overlay.get(s["step"]):
            content += [{"type": "text", "text": "OVERLAY:"}, _img((ROOT / overlay[s["step"]]).read_bytes())]
        for tries in range(3):
            ans, st = extract.claude_json(SYSTEM, content, Reworded, model=model, effort=effort, timeout=600)
            problems = check_words(ans)
            phases.append({"step": f"reword {s['step']}", "try": tries, "seconds": st.get("seconds"),
                           "cost_usd": st.get("cost_usd"), "problems": problems})
            if not problems:
                break
            content = content + [{"type": "text", "text": "Your answer had problems; answer again:" + NL + "- " +
                                                          (NL + "- ").join(problems)}]
        r.update(instruction=ans["instruction"], what_changed=ans["what_changed"], reworded=True)
    return phases


class Pick(BaseModel):
    part: str = Field(description="the candidate's id exactly as listed, or 'none'")
    colour: str
    evidence: str = Field(description="what in the two pictures shows it")


def picker(set_id, steps, inventory, overlay=None, model="opus", effort="high"):
    """For booklet_size.balance: which of the candidate pieces (that code found by area) first appears in the later
    step? Claude gets both steps' pictures, the later step's overlay and each candidate's picture."""
    from graph import extract
    by = {s["step"]: s for s in steps}
    sheet = {(r["part"], r["colour"]): n for n, r in enumerate(inventory, 1)}
    folder = OUT / set_id / "parts"

    def pick(src, dst, cands):
        early, late = sorted((src, dst), key=lambda r: r["step"])
        names = {(r["part"], r["colour"]): r["name"] for r in inventory}
        kinds = sorted({(c["part"], c["colour"]) for c in cands})
        content = [{"type": "text", "text": f"Set {set_id}. Step {src['step']} was read to add these pieces, but it "
                                            f"shows less new area than they would cover, and step {dst['step']} "
                                            f"shows more than its pieces cover. One of these pieces is most likely "
                                            f"really added in step {dst['step']}: which one? Look for the step where "
                                            f"each one FIRST appears. Answer 'none' if each one is in step "
                                            f"{src['step']}'s picture." + NL + NL.join(
                f"- {k[0]} | {k[1]} | {names.get(k, '')}" for k in kinds)}]
        for k in kinds:
            f = next(folder.glob(f"{sheet.get(k, 0):02d}_*"), None)
            if f:
                content += [{"type": "text", "text": f"{k[0]} {k[1]}:"}, _img(f.read_bytes())]
        for r in (early, late):
            content += [{"type": "text", "text": f"STEP {r['step']}:"}, _img((ROOT / by[r["step"]]["png"]).read_bytes())]
        if overlay and overlay.get(late["step"]):
            content += [{"type": "text", "text": f"STEP {late['step']} OVERLAY (what changed in colour):"},
                        _img((ROOT / overlay[late["step"]]).read_bytes())]
        ans, st = extract.claude_json(SYSTEM, content, Pick, model=model, effort=effort, timeout=600)
        pick.calls.append({"seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"), "answer": ans})
        return None if ans["part"] == "none" else ans
    pick.calls = []
    return pick


class Named(BaseModel):
    key: str
    name: str = Field(description="one to three words, as a child would call it ('mailbox', 'flower stand', 'roof')")


class Names(BaseModel):
    names: List[Named]


def name_builds(set_id, steps, reads, model="sonnet", effort="low"):
    """Short names for the builds and sub-builds, in one call: the set's own name and what each one looks like
    finished (its last step's description). {"build": {build index: name}, "box": {panel id: name}}, and the phase."""
    from graph import extract
    name, _ = lesson_store._rebrickable(set_id)
    rd = {r["step"]: r for r in reads}
    items = []
    for b in sorted({s["build"] for s in steps if s["kind"] == "main"}):
        ms = [s for s in steps if s["build"] == b and s["kind"] == "main"]
        items.append((f"build-{b}", "a separate build", rd[ms[-1]["step"]].get("description", ""),
                      rd[ms[-1]["step"]].get("build_name", "")))
    for box in sorted({s["box"] for s in steps if s["kind"] == "sub"}):
        own = [s for s in steps if s.get("box") == box]
        items.append((f"box-{box}", "a sub-build (built apart, then put on)", rd[own[-1]["step"]].get("description", ""),
                      rd[own[-1]["step"]].get("build_name", "")))
    if not items:
        return {"build": {}, "box": {}}, None
    text = (f"LEGO set {set_id}: \"{name}\". Give each of these a short name a child would use (one to three words; "
            f"use the set's own words where they fit, such as 'mailbox' for a mailbox). Two must not share a name." + NL +
            NL.join(f"- {k}: {kind}; read as '{bn}'; finished it looks like: {desc[:400]}" for k, kind, desc, bn in items))
    ans, st = extract.claude_json("You name the parts of a LEGO lesson for a child.", [{"type": "text", "text": text}],
                                  Names, model=model, effort=effort, timeout=300)
    got = {n["key"]: n["name"].strip() for n in ans["names"]}
    out = {"build": {}, "box": {}}
    for k, *_ in items:
        if got.get(k):
            kind, _, key = k.partition("-")
            out[kind][int(key) if kind == "build" else key] = got[k]
    return out, {"step": "names", "try": 0, "seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"), "problems": []}


def _slug(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", (name or "build").lower()).strip("-") or "build"
    out, n = base, 2
    while out in taken:
        out, n = f"{base}-{n}", n + 1
    taken.add(out)
    return out


def card_parts(inventory):
    """A card in the LEGO catalogue for every part of the set's inventory (Rebrickable and LDraw by code, Claude for
    what code cannot place: parts.cards.lego_cards), then the catalogue rebuilt. Returns what was done."""
    from graph.parts.cards import CardStore, lego_cards
    from graph.parts import part_catalogue
    cards = lesson_store._cards(lesson_store.PARTS)
    from graph.parts.lego.lego_ids import unprinted
    plain = [unprinted(r["part"])[0] for r in inventory]  # a print is not a part of its own: its plain piece's card
    missing = sorted({t[len("lego-"):] for t in plain if lesson_store.definition(cards, t)[0] is None})
    if not missing:
        return {"missing": 0}
    st = lego_cards(CardStore(ROOT / "code" / "graph" / "parts" / "lego" / "cards_lego.json"), missing, batch_size=20, workers=1)
    part_catalogue.build()
    lesson_store._CARDS.clear()
    return {"missing": len(missing), **{k: st.get(k) for k in ("made_by_code", "made_by_claude", "not_found", "cost_usd")}}


def attach_overcount(steps, reads, inventory):
    """A step that puts a finished sub-build on also shows that sub-build's pieces, and a read sometimes counts one of
    them again as a loose piece of the step (the garbage truck's 4 wheels, built 4x, and a 5th 'added' where they go
    on). Where the set's count is passed and the step attaches a sub-build with that same piece, the extra comes off
    the attaching step, by code. Returns (reads, phase)."""
    rd = {r["step"]: r for r in reads}
    count = {(r["part"], r["colour"]): r["count"] for r in inventory}
    used = collections.Counter()
    for r in reads:
        for a in r["adds"]:
            used[(a["part"], a["colour"])] += a["count"] * r.get("times", 1)
    removed = []
    for s in steps:
        r = rd.get(s["step"])
        if not r or not s.get("attaches"):
            continue
        in_subs = {(a["part"], a["colour"]) for x in steps if x.get("box") in s["attaches"]
                   for a in rd.get(x["step"], {}).get("adds", [])}
        for a in list(r["adds"]):
            k = (a["part"], a["colour"])
            over = used[k] - count.get(k, 0)
            if k in in_subs and over > 0:
                take = min(over, a["count"])
                a["count"] -= take
                used[k] -= take * r.get("times", 1)
                removed.append({"step": s["step"], "part": a["part"], "colour": a["colour"], "count": take})
                if a["count"] == 0:
                    r["adds"].remove(a)
    return reads, {"step": "attach overcount", "try": 0, "seconds": 0, "cost_usd": 0, "placed": [],
                   "removed": removed, "problems": []}


def enforce_inventory(set_id, steps, reads, inventory, model="opus", effort="high", call=True):
    """No piece is placed more times than the set has (a hard rule: the parts list is known). For each piece placed
    too often, Claude counts it in each step that places it (the step's picture and its change enlarged), and code
    keeps what each step shows, capped so the total is at most the set's count; what is still over comes off the
    steps it is least sure of, last steps first. call=False: code only (a rebuild). Returns (reads, phase)."""
    from graph import extract
    count = {(r["part"], r["colour"]): r["count"] for r in inventory}
    by = {r["step"]: r for r in reads}
    times = lambda r: r.get("times", 1)  # noqa: E731

    def placed(k):
        return [(r, a) for r in reads for a in r["adds"] if (a["part"], a["colour"]) == k]
    over = {k: sum(a["count"] * times(r) for r, a in placed(k)) - n for k, n in count.items()}
    over = {k: v for k, v in over.items() if v > 0}
    if not over:
        return reads, None
    names = {(r["part"], r["colour"]): r["name"] for r in inventory}
    st, seen, removed = {"seconds": 0, "cost_usd": 0}, {}, []
    if call:
        content = [{"type": "text", "text": f"Set {set_id}. Each piece below was read in more steps than the set has "
                                            f"copies of it. For each piece and each step shown, count the copies "
                                            f"inside what that step changed (the enlarged area): a copy there is one "
                                            f"the step adds; a copy already built before is not. 0 when none." + NL +
                                            NL.join(f"- {k[0]} | {k[1]} | {names.get(k, '')} (the set has "
                                                    f"{count[k]})" for k in over) + NL + "The steps:"}]
        for sn in sorted({r["step"] for k in over for r, _ in placed(k)}):
            s = next(x for x in steps if x["step"] == sn)
            png = (ROOT / s["png"]).read_bytes()
            content += [{"type": "text", "text": f"STEP {sn} (built {s.get('times', 1)} time(s)):"}, _img(png)]
            content += [_img(x) for x in (zooms(png) or [])]
        ans, s1 = extract.claude_json(SYSTEM, content, Counts, model=model, effort=effort, timeout=600)
        st = {k: (st[k] or 0) + (s1.get(k) or 0) for k in st}
        seen = {(x["part"], x["colour"], x["step"]): x["in_change"] for x in ans["seen"]}
    for k, n in over.items():
        rows = placed(k)
        for r, a in rows:  # what a step's picture does not show comes off first
            shown = seen.get((*k, r["step"]))
            if shown is not None and shown < a["count"] and n > 0:
                take = min(a["count"] - shown, (n + times(r) - 1) // times(r))
                a["count"] -= take
                n -= take * times(r)
                removed.append({"step": r["step"], "part": k[0], "colour": k[1], "count": take, "by": "count"})
        for r, a in sorted(rows, key=lambda ra: (by[ra[0]["step"]].get("confidence", 1), -ra[0]["step"])):
            while n > 0 and a["count"] > 0:  # still over: off the least sure steps, the last first
                a["count"] -= 1
                n -= times(r)
                removed.append({"step": r["step"], "part": k[0], "colour": k[1], "count": 1, "by": "cap"})
        for r, a in rows:
            if a["count"] <= 0 and a in r["adds"]:
                r["adds"].remove(a)
            r["reword"] = True  # its words must follow what it now adds
    return reads, {"step": "inventory", "try": 0, "seconds": st.get("seconds"), "cost_usd": st.get("cost_usd"),
                   "placed": [], "removed": removed, "problems": []}


def build(set_id, reads, steps, inventory, leftover, phases, overlay=None, names=None, model_a=False):
    """The lesson record and the steps graph (no physical graph).
      builds      one `product` node per build (a model, or a figure built on its own), named from the reads, with
                  its result (its last step's picture and description); the overview step SHOWS each, in order
      steps       numbered as the booklet: `stand-7`; a sub-build's steps inside the main step that needs it:
                  `stand-7.1`. A build STARTS at its step 1, a main step STARTS its sub-build (name, times), and
                  NEXT_STEP runs only inside one build or one sub-build
      parts       PLACES step -> parts-list row {count (times the build's "2x"), where}; a 3-in-1 set's model A
                  (model_a): the list is what its steps place, each row with the set's own count
    Each step holds where it came from in the booklet (source: page, crop, picture, overlay, changed regions,
    arrows). Which build a step is in, and the whole order, are worked out from the edges (lesson_store._order)."""
    name, _ = lesson_store._rebrickable(set_id)
    rows = [{"part": r["part"], "count": r["count"], "colour": r["colour"], "name": r["name"], "steps": []}
            for r in inventory]
    index = {(r["part"], r["colour"]): i for i, r in enumerate(rows)}
    pdf = f"data/sources/lego_pdf/{set_id}.pdf"
    rd = {r["step"]: r for r in reads}
    layout = "kind" in steps[0]
    if not layout:  # an old cut (one build, no sub-builds)
        for i, s in enumerate(steps):
            s.update(kind="main", build=0, box=None, times=1, attaches=[], label=str(s["step"]),
                     prev=steps[i - 1]["step"] if i else None)

    def common(xs):
        xs = [x.strip().lower() for x in xs if x and x.strip()]
        return collections.Counter(xs).most_common(1)[0][0] if xs else ""
    taken, slug, sub_name = set(), {}, {}
    builds = sorted({s["build"] for s in steps if s["kind"] == "main"}, key=lambda b: min(
        x["step"] for x in steps if x["build"] == b))
    for b in builds:  # a build's name: what its own main steps were read to make (the last ones count most)
        ms = [s for s in steps if s["build"] == b and s["kind"] == "main"]
        slug[b] = _slug((names or {}).get("build", {}).get(b) or common(
            [rd[s["step"]].get("build_name") for s in ms[-2:]] + [rd[s["step"]].get("build_name") for s in ms]), taken)
    for box in {s["box"] for s in steps if s["kind"] == "sub"}:
        sub_name[box] = (names or {}).get("box", {}).get(box) or \
            common([rd[s["step"]].get("build_name") for s in steps if s.get("box") == box]) or "sub-build"
    ids = {}
    for b in builds:
        for s in steps:
            if s["build"] == b and s["kind"] == "main":
                ids[s["step"]] = f"{slug[b]}-{s['label'] if layout else s['step']}"
    for s in steps:
        if s["kind"] == "sub":
            main = next(x for x in steps if s["box"] in x.get("attaches", []))
            own = [x for box in main["attaches"] for x in steps if x.get("box") == box]  # all its sub-builds, in order:
            ids[s["step"]] = f"{ids[main['step']]}.{own.index(s) + 1}"                   # 9.1-9.4, then 9.5
    nodes, edges = [], []
    for s in steps:
        r = rd[s["step"]]
        node = {"id": ids[s["step"]], "kind": "step", "number": ids[s["step"]].rsplit("-", 1)[1],
                "text": r["instruction"], "description": r.get("description") or r.get("looks_like"),
                "what_changed": r.get("what_changed"), "view": r.get("view"), "times": s["times"],
                "confidence": r["confidence"],
                "source": {"page": s["page"], "crop": s["crop"], "picture": s["png"],
                           "overlay": (overlay or {}).get(s["step"]), "booklet_label": s.get("label"),
                           "changed_regions": len(s["boxes"]) if isinstance(s.get("boxes"), list) else s.get("boxes"),
                           "arrows": s.get("arrows") or []}}
        if r.get("callout"):
            node["callout"] = [f"{a['count']}x {a['part']} {a['colour']}" for a in r["callout"]]
        for k in ("problems", "added_on_reconcile"):
            if r.get(k):
                node["problems" if k == "problems" else "added_by_repair"] = r[k]
        nodes.append(node)
        placed = {}  # one PLACES per step and row: two reads of the same piece in a step add up
        for a in r["adds"]:
            i = index.get((a["part"], a["colour"]))
            if i is None:
                continue
            n = a["count"] * s["times"]
            if i in placed:
                placed[i]["count"] += n
                placed[i]["where"] += "; " + a["where"]
                continue
            placed[i] = {"type": "PLACES", "u": node["id"], "v": f"lesson:parts_list/{i}", "count": n,
                         "where": a["where"]}
            edges.append(placed[i])
            rows[i]["steps"].append(node["id"])
    products = []
    for n_b, b in enumerate(builds, 1):
        ms = [s for s in steps if s["build"] == b and s["kind"] == "main"]
        last = rd[ms[-1]["step"]]
        role = "figure" if ms[0].get("box") else "model"  # a panel that stands alone: a figure built on its own
        pid = f"build:{slug[b]}"
        products.append({"id": pid, "kind": "product", "name": slug[b].replace("-", " "), "role": role,
                         "result": {"picture": ms[-1]["png"], "description": last.get("description"),
                                    "from": ids[ms[-1]["step"]]}})
        edges.append({"type": "SHOWS", "u": "overview", "v": pid, "order": n_b})
        edges.append({"type": "STARTS", "u": pid, "v": ids[ms[0]["step"]]})
        edges += [{"type": "NEXT_STEP", "u": ids[x["step"]], "v": ids[y["step"]]} for x, y in zip(ms, ms[1:])]
        for m in ms:
            for box in m.get("attaches", []):
                own = [x for x in steps if x.get("box") == box]
                edges.append({"type": "STARTS", "u": ids[m["step"]], "v": ids[own[0]["step"]],
                              "name": sub_name[box], "times": own[0]["times"]})
                edges += [{"type": "NEXT_STEP", "u": ids[x["step"]], "v": ids[y["step"]]} for x, y in zip(own, own[1:])]
    overview = {"id": "overview", "kind": "overview",
                "text": "Today you build " + ", ".join(p["name"] for p in products[:-1]) +
                        (" and " if len(products) > 1 else "") + products[-1]["name"] + "."}
    source_list = "Rebrickable inventory of the set (with its minifigures)"
    if model_a:  # a 3-in-1 set's model A: its parts list is what its steps place (the rest is for models B and C)
        used = collections.Counter()
        for e in edges:
            if e["type"] == "PLACES" and e["v"].startswith("lesson:parts_list/"):
                used[int(e["v"].rsplit("/", 1)[1])] += e["count"]
        keep = [i for i in range(len(rows)) if used[i]]
        new_i = {i: k for k, i in enumerate(keep)}
        rows = [{**rows[i], "count": used[i], "set_count": rows[i]["count"]} for i in keep]
        for e in edges:
            if e["type"] == "PLACES" and e["v"].startswith("lesson:parts_list/"):
                e["v"] = f"lesson:parts_list/{new_i[int(e['v'].rsplit('/', 1)[1])]}"
        source_list += ": the pieces model A uses (the set's other pieces are for its models B and C)"
    inst = {"lesson_id": set_id, "nodes": [overview] + products + nodes, "edges": edges, "order": "strict"}
    final = steps[[i for i, s in enumerate(steps) if s["kind"] == "main"][-1]]
    record = {"lesson_id": set_id, "kind": "lesson", "lesson_type": "lego", "name": name or set_id,
              "link": f"https://rebrickable.com/sets/{set_id}/",
              "source": {"kind": "booklet-pdf", "set": set_id, "file": pdf, "pages": sorted({x["page"] for x in steps})},
              "result": {"picture": final["png"], "description": rd[final["step"]].get("description")},
              "parts_list": {"from": source_list, "parts": rows},
              "order": "strict: the booklet's order inside each build; a sub-build just before the step it is part of",
              "stats": {"seconds": round(sum(p["seconds"] or 0 for p in phases), 1),
                        "cost_usd": round(sum(p["cost_usd"] or 0 for p in phases), 4), "calls": len(phases)},
              "derived_from": pdf}
    return record, inst


def answer_key(set_id, reads, inventory, steps=None):
    """Score what the booklet route found against the set's 3D model, where there is one (it is never used to build):
      coverage  how many of the model's pieces are inventory rows the booklet route has a step add
      order     the model is built in some order; give each model piece the booklet step that adds its inventory row
                (copies in the model's order), then count the pairs of pieces the two orders put the same way round.
                A model's own step numbers are its author's (one per piece in some files), so they are not compared.
                Only pairs inside one build count (steps: the layout): separate builds (a mailbox, a flower stand)
                have no order between them, and a model file lists them in whatever order its author chose."""
    from graph.parts.lego import lego_ids
    from graph.lego_3d import lesson as lego_lesson
    if not (ROOT / "data" / "sources" / "lego" / f"{set_id}.mpd").exists():
        return None
    pieces = lego_lesson.model_of(set_id)
    rows = [{**r} for r in inventory]
    phys = [{"id": p["id"], "type": f"lego-{p['part_num']}", "label": p["name"], "props": {"colour": p["colour"]}}
            for p in pieces]
    problems, notes = lego_ids.match(rows, phys)
    rank = {p["id"]: k for k, p in enumerate(pieces)}  # the model's build order (its file order, step by step)
    queue = collections.defaultdict(list)  # inventory row -> the booklet steps that add it, a slot per copy
    for r in reads:
        for a in r["adds"]:
            for _ in range(a["count"] * r.get("times", 1)):
                queue[(a["part"], a["colour"])].append(r["step"])
    step_of = {}
    for row in rows:
        slots = queue.get((row["part"], row["colour"]), [])
        for pid, st in zip(sorted(row.get("instances", []), key=rank.get), slots):
            step_of[pid] = st
    placed = sorted(step_of, key=rank.get)
    same = total = 0
    build_of = {x["step"]: x.get("build", 0) for x in steps or []}
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if step_of[a] != step_of[b] and build_of.get(step_of[a], 0) == build_of.get(step_of[b], 0):
                total += 1
                same += step_of[a] < step_of[b]
    return {"model_pieces": len(pieces), "matched_to_a_booklet_step": len(step_of),
            "order_agreement": round(same / total, 3) if total else None, "pairs": total,
            "inventory_vs_model": problems, "colour_notes": notes}


def rebuild(set_id):
    """The lesson again from the saved reads (reads.json): no step is read again, only the graphs remade (after a fix
    to how they are built). Returns the checks."""
    out = ROOT / "data" / "lessons" / "booklet" / set_id
    saved = json.loads((out / "reads.json").read_text())
    steps = booklet(set_id, out)
    _, inv = lesson_store._rebrickable(set_id)
    inventory = [{"part": f"lego-{r['part_num']}", "colour": r["color"], "name": r["name"], "count": r["quantity"]}
                 for r in inv]
    overlay = overlays(set_id, steps, out)
    names = saved.get("names")
    if names is None:  # a run from before the names were kept: name them again (one short call)
        names, _ = name_builds(set_id, steps, saved["reads"])
        saved["names"] = names
        (out / "reads.json").write_text(json.dumps(saved, indent=1))
    names = {"build": {int(k): v for k, v in (names.get("build") or {}).items()}, "box": names.get("box") or {}}
    if not any(p.get("step") == "attach overcount" for p in saved["phases"]):  # a rule added since the run
        saved["reads"], ph = attach_overcount(steps, saved["reads"], inventory)
        saved["phases"].append(ph)
        (out / "reads.json").write_text(json.dumps(saved, indent=1))
    if saved["leftover"]:  # a run from before every piece had to be used: place the rest now (one call)
        saved["reads"], saved["leftover"], ph = allocate(set_id, steps, saved["reads"], inventory,
                                                         use_all=not (out / "alternate_models.json").exists())
        if ph:
            saved["phases"].append(ph)
            saved["phases"] += reword(set_id, steps, saved["reads"], overlay=overlay)
        (out / "reads.json").write_text(json.dumps(saved, indent=1))
    saved["reads"], ph = enforce_inventory(set_id, steps, saved["reads"], inventory, call=False)  # code only
    if ph:
        saved["phases"].append(ph)
        (out / "reads.json").write_text(json.dumps(saved, indent=1))
    record, inst = build(set_id, saved["reads"], steps, inventory, saved["leftover"], saved["phases"], overlay, names,
                         model_a=(out / "alternate_models.json").exists())
    lid = f"{set_id}-pdf"
    for g in (record, inst):
        g["lesson_id"] = lid
    lesson_store.register({"lesson_id": lid, "title": record["name"] + " (booklet only)", "lesson_type": "lego"},
                {"lesson": record, "instruction": inst, "physical": None, "document": None})
    return lesson_store.assemble(lid)["checks"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--rebuild", action="store_true", help="remake the graphs from the saved reads (no model call)")
    ap.add_argument("--balance", action="store_true", help="move pieces between neighbouring steps by their areas "
                                                           "(off: it moved more wrong than right, booklet_eval)")
    ap.add_argument("--model", default="sonnet", help="reads each step")
    ap.add_argument("--repair-model", default="opus", help="counts the pieces no step added (sonnet missed them)")
    ap.add_argument("--no-sheet", action="store_true", help="give the parts list as text only, without pictures")
    a = ap.parse_args(argv)
    if a.rebuild:
        for set_id in a.sets:
            c = rebuild(set_id)
            print(f"{set_id}: {'READY' if c['ready'] else 'NOT READY: ' + '; '.join(c['problems'][:6])}")
        return
    for set_id in a.sets:
        out = OUT / set_id
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        steps = booklet(set_id, out)
        _, inv = lesson_store._rebrickable(set_id)
        inventory = [{"part": f"lego-{r['part_num']}", "colour": r["color"], "name": r["name"], "count": r["quantity"]}
                     for r in inv]
        print(f"  cards: {card_parts(inventory)}")  # every part of the set has a card before anything is read
        sheet = None if a.no_sheet else part_sheet(inventory, out)
        overlay = overlays(set_id, steps, out)
        size = {"areas": {}}
        reads, leftover, phases = read_steps(set_id, steps, inventory, a.model, sheet=sheet, overlay=overlay, size=size)
        reads, leftover, ph = reconcile(set_id, steps, reads, inventory, leftover, a.repair_model)
        if ph:
            phases.append(ph)
            print(f"  reconcile: placed {[f'{x['count']}x {x['part']} in step {x['step']}' for x in ph['placed']]}")
        reads, leftover, ph = symmetry(steps, reads, inventory)  # S11: hidden twins, left/right pairs (code)
        phases.append(ph)
        if ph["placed"] or ph["problems"]:
            print(f"  symmetry: placed {[f'{x['count']}x {x['part']} in step {x['step']}' for x in ph['placed']]}"
                  f"{'; ' + str(ph['problems']) if ph['problems'] else ''}")
        if a.balance:  # off by default: scored against the 3D models it moved more pieces wrong than right (1 of 5)
            pick = picker(set_id, steps, inventory, overlay, a.repair_model)
            pairs = [(pv["step"], s["step"]) for s in steps if (pv := prev_of(steps, s)) and not s.get("attaches")]
            reads, ph = booklet_size.balance(reads, size["areas"], pick, pairs=pairs)  # code finds it, Claude picks
            ph.update(seconds=sum(c["seconds"] or 0 for c in pick.calls),   # among candidates
                      cost_usd=sum(c["cost_usd"] or 0 for c in pick.calls))
            phases.append(ph)
            if ph["placed"]:
                print(f"  balance: moved {[f'{m['piece']} {m['from']}->{m['to']}' for m in ph['placed']]}")
        reads, leftover, ph = booklet_size.fill(reads, inventory, size["areas"])  # code: by the size of new area
        phases.append(ph)
        if ph["placed"]:
            print(f"  size: placed {[f'{x['count']}x {x['part']} in step {x['step']}' for x in ph['placed']]}")
        reads, leftover, ph = allocate(set_id, steps, reads, inventory, a.repair_model,  # the last try: all used?
                                       use_all=not (out / "alternate_models.json").exists())
        if ph:
            phases.append(ph)
            print(f"  allocate: placed {[f'{x['count']}x {x['part']} in step {x['step']}' for x in ph['placed']]}"
                  f"{'; refused ' + str(ph['problems']) if ph['problems'] else ''}")
        reads, ph = attach_overcount(steps, reads, inventory)  # a sub-build's piece counted again where it goes on
        phases.append(ph)
        if ph["removed"]:
            print(f"  attach overcount: removed {[f'{x['count']}x {x['part']} from step {x['step']}' for x in ph['removed']]}")
        reads, ph = enforce_inventory(set_id, steps, reads, inventory, a.repair_model)  # never more than the set has
        if ph:
            phases.append(ph)
            print(f"  inventory: removed {[f'{x['count']}x {x['part']} from step {x['step']} ({x['by']})' for x in ph['removed']]}")
        if any(r.get("added_on_reconcile") or r.get("reword") for r in reads):
            phases += reword(set_id, steps, reads, a.model, overlay=overlay)  # its words now cover what was added
        names, ph = name_builds(set_id, steps, reads)
        if ph:
            phases.append(ph)
        record, inst = build(set_id, reads, steps, inventory, leftover, phases, overlay, names,
                             model_a=(out / "alternate_models.json").exists())
        lid = f"{set_id}-pdf"
        for g in (record, inst):
            g["lesson_id"] = lid
        lesson_store.register({"lesson_id": lid, "title": record["name"] + " (booklet only)", "lesson_type": "lego"},
                    {"lesson": record, "instruction": inst, "physical": None, "document": None})
        print(f"  parts: {lesson_store.describe_parts(lid, 'lego')}")  # the metadata rules for parts that have none yet
        checks = lesson_store.assemble(lid)["checks"]  # final: every piece of the parts list placed, every link resolves
        print(f"  {'READY' if checks['ready'] else 'NOT READY'}" + ("" if checks["ready"] else ": " +
              "; ".join(checks["problems"][:6])) + (f" ({len(checks['review'])} to review)" if checks["review"] else ""))
        key = answer_key(set_id, reads, inventory, steps)
        (out / "reads.json").write_text(json.dumps({"reads": reads, "leftover": leftover, "phases": phases, "names": names,
                                                    "answer_key": key}, indent=1))
        print(f"{set_id}: {len(steps)} steps in {time.monotonic() - t0:.0f}s, ${record['stats']['cost_usd']}; "
              f"{sum(1 for p in phases if p['try'])} repairs; never added: {leftover or 'none'}")
        for r in reads:
            print(f"  step {r['step']}: " + ", ".join(f"{x['count']}x {x['part']} {x['colour']}" for x in r["adds"])
                  + (f"  PROBLEMS {r['problems']}" if r["problems"] else ""))
        if key:
            print(f"  answer key: {key['matched_to_a_booklet_step']}/{key['model_pieces']} model pieces matched to a "
                  f"booklet step; order agreement {key['order_agreement']} over {key['pairs']} pairs")


if __name__ == "__main__":
    main()
