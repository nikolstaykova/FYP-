"""Claude's look at each booklet page, to check how code cut it into steps.

What it is   each page drawn with code's cut on it (a box and tag per step and panel, a percent grid); Claude says
             per box whether it is the whole step, where a sub-build goes, which steps were missed, and whether the
             page builds a combination with another set. Code checks each answer before it is used (a box must hold
             the step's own number and be more than the number). For a scanned booklet it first reads each page's
             step numbers.
Used for     fixing the steps code cut wrong (a step cut through its picture, a sub-build in the wrong step) before
             any step is read.
Where        lego_booklet/pdf_lesson.py (check, read_numbers); cached in
             data/lessons/booklet/<set>/layout_check.json and numbers.json. On its own: python -m
             graph.lego_booklet.booklet_check 30311-1.

Code finds the steps from the PDF itself (booklet_layout.cut: the big numbers, the cream sub-build panels, the
lines from a panel into a step), and its rules are right on most pages; where a page's drawing breaks a rule (a
small panel hanging into a step's row, a faint cream arrow code does not see) a step is cut wrong or a sub-build
goes into the wrong step. So each page is drawn with code's cut on it (each step's box with its number, each
panel with its id, a grid in percent) and Claude says, per box, whether it is right:

  main step   is the box the whole step (its model picture and its parts call-out, nothing of the next step)?
              if not, the box it should be, in percent of the page
  sub-build   which main step its result goes into (followed by the arrows, faint ones too), or a build of its own
              (a figure built on its own and set beside the model), and how many times it is built
  missed      a step no box covers (reported, not added: code adds a step only where the PDF has its number)

Code then checks each answer before it is used: a new box must hold the step's own number and lie on the page; a
step it goes into must be a main step that exists. What is used goes to booklet_layout.cut as its fixes; every
answer, used or refused, is kept (layout_check.json).

  .venv-research/bin/python -m graph.lego_booklet.booklet_check 30311-1
"""
import argparse
import base64
import concurrent.futures
import json
import os
import pathlib
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
PDFS = ROOT / "data" / "sources" / "lego_pdf"
DPI = 100

SYSTEM = """You check how a program cut one page of a LEGO instruction booklet into building steps.

The page is drawn with the program's cut on it: each MAIN step is a red box labelled with its number in a red tag
(M7 = main step 7; when a page has two step 7s, of two builds, the second is M7/2); each SUB-BUILD panel (a cream or coloured rectangle where a small piece is built apart, often
with small numbers and a '2x') is a blue box labelled with its id in a blue tag (P sub-2). A grey grid marks every
10% of the page, numbered along the top and left edges, so you can give positions as percent of the page.

For EVERY tag on the page, say:
- main step: is the red box the whole step? The whole step is its big number, the model picture of that step (all
  of it: no wing tip, wheel, arrow or floating piece cut off by the box's edge) and its parts call-out, and nothing
  that belongs to another step. In some booklets the parts call-out (the small panel with '1x' and the pieces) sits
  ABOVE the step number: it is part of that step. Look at each edge of the box: if it cuts through the step's own drawing, the box is
  wrong. If not, give the box it should be, as
  [left, top, right, bottom] in percent of the page. A small sub-build panel may sit inside a step's area; it is
  fine for the step's box to include it. Ignore art that is not a step (cover, warnings, 'Rate this set', other
  sets, the parts inventory, the website) - a step's box should not include it.
- sub-build panel: first, is it really a sub-build panel? The program sometimes draws a blue box that is not one
  (across part of a step's model, or overlapping a real panel); then say is_panel false and nothing more. If it is,
  which MAIN step number its finished piece goes into. Follow the arrows or lines from the panel,
  including faint cream or white ones, or see where the piece appears next. If the panel builds something that is
  put down on its own (a minifigure or figure standing beside the model, never attached), say "own build". Also
  say how many times it is built (the '2x' near it; 1 if none).
Then list any building step on the page that no box covers (missed), with its number if printed.
Last, say whether the page builds a combination model with ANOTHER set (other_set): small sets often end with a
page showing this set and another set joined ('8655 + 8658 =') and the steps to combine them. Those steps need the
other set's pieces, so they are not this set's build. A page of this set's own model is other_set false.
Use the numbers printed in the booklet, never your own."""


class Seen(BaseModel):
    tag: str = Field(description="The tag exactly as drawn: 'M7', 'M7/2', 'P sub-2' (nothing added)")
    box_ok: bool = Field(description="Main step: the red box is the whole step. Panel: true")
    box: Optional[List[float]] = Field(None, description="When box_ok is false: [left, top, right, bottom] percent")
    is_panel: Optional[bool] = Field(None, description="Panel: false when the blue box is not a sub-build panel")
    goes_into: Optional[str] = Field(None, description="Panel: the main step number its piece goes into, or 'own build'")
    times: Optional[int] = Field(None, description="Panel: how many times it is built")
    why: str = Field("", description="A few words: what you saw")


class Missed(BaseModel):
    number: str = ""
    kind: Literal["main", "sub-build"]
    box: List[float]


class PageCheck(BaseModel):
    tags: List[Seen]
    missed: List[Missed] = []
    other_set: bool = Field(False, description="The page's steps build a model that needs ANOTHER set's pieces too: a "
                                               "combination model (the page shows two sets joined, 'set A + set B "
                                               "='), not this set's own build")


def draw(page, steps, panels):
    """The page as PNG with code's cut drawn on it: red main-step boxes tagged M<n>, blue panels tagged P <id>, a
    grid every 10%."""
    import cv2
    import numpy as np
    pix = page.get_pixmap(dpi=DPI)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1].copy()
    k = DPI / 72
    h, w = im.shape[:2]
    for i in range(1, 10):
        x, y = int(w * i / 10), int(h * i / 10)
        cv2.line(im, (x, 0), (x, h), (170, 170, 170), 1)
        cv2.line(im, (0, y), (w, y), (170, 170, 170), 1)
        cv2.putText(im, str(i * 10), (x + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
        cv2.putText(im, str(i * 10), (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)

    def tag(rect, text, colour):
        x0, y0, x1, y1 = [int(v * k) for v in rect]
        cv2.rectangle(im, (x0, y0), (x1, y1), colour, 2)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(im, (x0, y0), (x0 + tw + 6, y0 + th + 6), colour, -1)
        cv2.putText(im, text, (x0 + 3, y0 + th + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    for s in steps:
        tag(s["crop"], s["tag"], (40, 40, 220))
    for b in panels:
        tag(b, f"P {b.id}", (220, 90, 30))
    ok, buf = cv2.imencode(".png", im)
    return buf.tobytes()


def _panels(doc, steps):
    """The panels code found, by id and page (as booklet_layout.cut numbers them)."""
    from graph.lego_booklet import booklet_layout as bl
    out, n = {}, 0
    for pno, page in enumerate(doc, 1):
        for b in bl._boxes(page):
            n += 1
            b.id = f"sub-{n}"
            out.setdefault(pno, []).append(b)
    return out


def ask(set_id, pno, png, model="sonnet"):
    from graph.extract import claude_json
    content = [{"type": "text", "text": f"LEGO set {set_id}, page {pno} of its instruction booklet."},
               {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(png).decode()}}]
    return claude_json(SYSTEM, content, PageCheck, model=model, effort="medium", timeout=600)


def key(page, step):
    """A main step's fix key: its page, number and the number's place (a page can hold two step 5s: two builds)."""
    return f"{page}:{step['label']}@{round(step['number'][0])},{round(step['number'][1])}"


def check(set_id, model="sonnet", workers=4, out=None):
    """{fixes, pages: [{page, answer, used, refused}], stats} for a booklet; cached in <out>/layout_check.json."""
    import pymupdf
    from graph.lego_booklet import booklet_layout as bl
    out = pathlib.Path(out or ROOT / "data" / "lessons" / "booklet" / set_id)
    f = out / "layout_check.json"
    if f.exists():
        saved = json.loads(f.read_text())
        if all("@" in k for k in saved["fixes"].get("crops", {})):  # an older cache keyed by number alone: redone
            return saved
    doc = pymupdf.open(PDFS / f"{set_id}.pdf")
    if bl.scanned(doc[min(2, doc.page_count - 1)]):
        read_numbers(set_id, out)  # a scan's numbers, before code can cut it
    cut = bl.cut(doc)
    from graph.lego_booklet import step_diff  # the crops as the lesson will use them (tightened to their content), so the check
    for s in cut:            # judges what is really cut (tightened, then grown over any shape it cut through)
        if s["kind"] == "main":
            s["crop"] = [round(v, 1) for v in step_diff.tighten(doc[s["page"] - 1], s["crop"])]
            up = step_diff.callout_above(doc[s["page"] - 1], s["crop"], s["number"]) if s.get("number") else None
            if up is not None and any(b.x0 < s["crop"][2] and s["crop"][0] < b.x1 and b.y1 > up and b.y0 < s["crop"][1]
                                      for b in bl._boxes(doc[s["page"] - 1])):
                up = None  # a sub-build panel above is its own step
            if up is not None and up < s["crop"][1]:
                s["crop"][1] = round(up, 1)
            keep = [tuple(x["number"]) for x in cut if x["page"] == s["page"] and x is not s and x.get("number")]
            s["crop"] = [round(v, 1) for v in step_diff.grow(doc[s["page"] - 1], s["crop"], keep)]
    mains = [s for s in cut if s["kind"] == "main"]
    for s in mains:  # one tag per box on its page: a page can hold two step 5s (two builds): M5 and M5/2
        twins = [o for o in mains if o["page"] == s["page"] and o["label"] == s["label"]]
        s["tag"] = f"M{s['label']}" if len(twins) == 1 or twins[0] is s else f"M{s['label']}/{twins.index(s) + 1}"
    panels = _panels(doc, cut)
    pages = sorted({s["page"] for s in mains} | set(panels))
    pngs = {p: draw(doc[p - 1], [s for s in mains if s["page"] == p], panels.get(p, [])) for p in pages}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        answers = dict(zip(pages, pool.map(lambda p: ask(set_id, p, pngs[p], model), pages)))
    fixes, report, cost, secs = {"crops": {}, "into": {}, "not_panel": [], "other_set_pages": []}, [], 0.0, 0.0
    labels = {s["label"] for s in mains}
    for p in pages:
        ans, st = answers[p]
        cost += st.get("cost_usd") or 0
        secs = max(secs, st.get("seconds") or 0)
        page = doc[p - 1]
        W, H = page.rect.width, page.rect.height
        used, refused = [], []
        if (ans.get("other_set") or bl.other_set(page, set_id)) and p != min(pages):  # never the first page:
            # the set's own build starts there
            fixes["other_set_pages"].append(p)
            used.append({"page": p, "other_set": True})
        for t in ans["tags"]:
            tg = t["tag"].strip()
            if tg.upper().startswith("M"):
                tg = tg.split()[0]  # 'M5' as drawn (an answer may add words: 'M5 (top)')
                s = next((x for x in mains if x["page"] == p and x["tag"] == tg), None)
                if not s or t["box_ok"] or not t.get("box") or len(t["box"]) != 4:
                    continue
                l, tp, r, b = t["box"]
                box = [max(0, l) * W / 100, max(0, tp) * H / 100, min(100, r) * W / 100, min(100, b) * H / 100]
                x0, y0, x1, y1 = s["number"]
                cx0, cy0, cx1, cy1 = s["crop"]
                area = (box[2] - box[0]) * (box[3] - box[1])
                if not (box[0] - 4 <= x0 and x1 <= box[2] + 4 and box[1] - 4 <= y0 and y1 <= box[3] + 4):
                    refused.append({"tag": tg, "box": t["box"], "why": "the box does not hold the step's own number"})
                elif area < 0.005 * W * H or box[2] - box[0] < 3 * (x1 - x0) or box[3] - box[1] < 2.5 * (y1 - y0):
                    refused.append({"tag": tg, "box": t["box"], "why": "too small to be a step (little more than its number)"})
                elif area < 0.5 * (cx1 - cx0) * (cy1 - cy0) and not any(
                        o is not s and o["page"] == p and cx0 <= o["number"][0] <= cx1 and cy0 <= o["number"][1] <= cy1
                        for o in mains):
                    refused.append({"tag": tg, "box": t["box"], "why": "much smaller than code's box, which holds no "
                                                                      "other step: it would cut the step's picture"})
                else:
                    fixes["crops"][key(p, s)] = [round(v, 1) for v in box]
                    used.append({"tag": tg, "box": [round(v, 1) for v in box], "why": t.get("why")})
            elif tg.upper().startswith("P"):
                pid = tg[1:].strip()
                if t.get("is_panel") is False:
                    fixes["not_panel"].append(pid)
                    used.append({"tag": tg, "is_panel": False, "why": t.get("why")})
                    continue
                into = (t.get("goes_into") or "").strip()
                if not into:
                    continue
                if into != "own build" and into not in labels:
                    refused.append({"tag": tg, "goes_into": into, "why": "no main step has that number"})
                    continue
                fixes["into"][pid] = into
                used.append({"tag": tg, "goes_into": into, "times": t.get("times"), "why": t.get("why")})
        report.append({"page": p, "answer": ans, "used": used, "refused": refused})
    # only what changes code's cut is a fix: an answer that agrees with it changes nothing
    code_into = {}
    for s in cut:
        if s["kind"] == "main":
            for a in s.get("attaches", []):
                code_into[a] = s["label"]
    alone = {s["box"] for s in cut if s["kind"] == "sub" and s.get("attached_by", "").startswith("stands alone")}
    fixes["into"] = {k: v for k, v in fixes["into"].items()
                     if not (v == code_into.get(k) and k not in alone) and not (v == "own build" and k in alone)}
    result = {"set": set_id, "model": model, "fixes": fixes, "pages": report,
              "stats": {"pages": len(pages), "cost_usd": round(cost, 4), "seconds": round(secs, 1),
                        "crops_fixed": len(fixes["crops"]), "panels_moved": len(fixes["into"]),
                        "missed": sum(len(r["answer"].get("missed") or []) for r in report)}}
    out.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(result, indent=1))
    for p, png in pngs.items():  # what Claude was shown, kept beside the answers
        (out / "layout_check").mkdir(exist_ok=True)
        (out / "layout_check" / f"page{p}.png").write_bytes(png)
    return result


NUMBERS = """You read the step numbers on one page of a scanned LEGO instruction booklet.

Give every building step number printed on the page: the big numbers of the main steps, and the small numbers
inside sub-build panels (cream or coloured boxes), with where the number's centre is, as percent of the page from
the left and from the top (a grey grid marks every 10%, numbered along the top and left edges). Also give each 'Nx'
mark (2x, 3x) near a panel. Not page numbers in a corner, not set numbers, not part counts in a parts call-out
('1x', '2x' beside a piece), not text."""


class Number(BaseModel):
    text: str = Field(description="The number as printed ('7'), or the mark ('2x')")
    kind: Literal["main", "sub-build", "times"]
    x: float = Field(description="Centre, percent of the page from the left")
    y: float = Field(description="Centre, percent of the page from the top")


class PageNumbers(BaseModel):
    numbers: List[Number]


def grid(page):
    """The page as PNG with a grey grid every 10%, numbered."""
    import cv2
    import numpy as np
    pix = page.get_pixmap(dpi=DPI)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1].copy()
    h, w = im.shape[:2]
    for i in range(1, 10):
        x, y = int(w * i / 10), int(h * i / 10)
        cv2.line(im, (x, 0), (x, h), (170, 170, 170), 1)
        cv2.line(im, (0, y), (w, y), (170, 170, 170), 1)
        cv2.putText(im, str(i * 10), (x + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
        cv2.putText(im, str(i * 10), (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
    return cv2.imencode(".png", im)[1].tobytes()


def read_numbers(set_id, out, model="sonnet", workers=4):
    """A scanned booklet's step numbers read by Claude, one look per page, into booklet_layout.SAID (where code
    snaps each to the glyph at its place). Cached in <out>/numbers.json. Returns the stats."""
    import pymupdf
    from graph.lego_booklet import booklet_layout as bl
    from graph.extract import claude_json
    out = pathlib.Path(out)
    f = out / "numbers.json"
    doc = pymupdf.open(PDFS / f"{set_id}.pdf")
    if f.exists():
        saved = json.loads(f.read_text())
    else:
        pages = [p for p in range(doc.page_count) if bl.scanned(doc[p])]

        def one(p):
            content = [{"type": "text", "text": f"LEGO set {set_id}, page {p + 1}."},
                       {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                    "data": base64.b64encode(grid(doc[p])).decode()}}]
            return claude_json(NUMBERS, content, PageNumbers, model=model, effort="low", timeout=300)
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            got = dict(zip(pages, pool.map(one, pages)))
        saved = {"set": set_id, "pages": {str(p): a["numbers"] for p, (a, _) in got.items()},
                 "stats": {"pages": len(pages), "cost_usd": round(sum(st.get("cost_usd") or 0 for _, st in got.values()), 4)}}
        out.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(saved, indent=1))
    for p, nums in saved["pages"].items():
        page = doc[int(p)]
        W, H = page.rect.width, page.rect.height
        bl.SAID[(os.path.basename(doc.name), int(p))] = [(n["x"] * W / 100, n["y"] * H / 100, n["text"].replace(" ", ""),
                                                          n["kind"]) for n in nums if n["kind"] != "times"]
        bl._OCR.pop((os.path.basename(doc.name), int(p)), None)
    return saved["stats"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    for s in a.sets:
        r = check(s, a.model)
        print(s, r["stats"], json.dumps(r["fixes"]))


if __name__ == "__main__":
    main()
