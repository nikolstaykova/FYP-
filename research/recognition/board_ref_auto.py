"""RESEARCH, not used by the app: a geometry reference made by code from a learner's photo (26 Nov 2026).

Measured against the real Duemilanove reference on 7 photos: the names land 0.3-0.8 of an opening off on average, the
worst pin 0.5-1.8 (the header is black on black, Opus reads the row ends only to about half an opening, and the
check on the drawn names passed some that were off). Not good enough to name a pin, so it is not switched on.
Run from the project root: python research/recognition/board_ref_auto.py <board> <photo> [drawn.jpg]

(What follows is the method as tried.)

The step check overlays a photo of the Arduino on a reference photo of the same board and writes each pin's name at
its opening (uno_overlay). A board without a reference only gets the model's reading. So when the parts check sees an
Uno-shaped board (female headers along both long edges) that has no reference, this makes one in the background:

1. code cuts the board out of the photo (its blue board), as the overlay does;
2. Opus, on that cut-out with a pixel grid, gives the first and last opening of each header row and the label printed
   by each end (which says the layout: SCL.. for an Uno R3 and later, AREF.. for older boards; the power row's length);
3. code fits the row's openings exactly (the comb, only a little either side of Opus's ends: a black header gives the
   comb little to hold on to, so it is never let slide a whole opening);
4. Opus checks the result: the yellow names code drew against the names printed on the board. Only then it is kept:
   data/board_refs/local_refs/<board> (the learner's photo: never in git) and the database (status "auto").

    make(board_id, photo) -> {"ok", "why", "rows", "cost_usd"}     (python -m validator.board_ref_auto board photo)
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "code"))

import cv2
import numpy as np

from validator import board as _board, uno_overlay as U

MODEL = "claude-opus-5-5"
TRIED = U.LOCAL_REFS.parent / "auto_tried.json"  # boards tried, and why it did not work (not again for the same photo)
MIN_EDGE = 650  # the board's long side in the photo, in pixels: smaller is too soft to find the openings in (26 Nov:
# from the parts photo, about 550 px, the names drifted 3/4 of an opening; from a step photo, about 1000 px, exact)
# boards with female headers along both long edges (the overlay's kind); a board added by investigate_board with
# "uno_layout" counts too
UNO_SHAPED = {"arduino-uno", "arduino-uno-r4-minima", "arduino-uno-r4-wifi", "arduino-uno-wifi-rev2",
              "arduino-leonardo", "arduino-duemilanove", "arduino-zero", "arduino-due", "arduino-due-r3",
              "arduino-mega", "arduino-yun", "arduino-yun-headers"}

FIND = """Photo 1 is an Arduino-style board seen from above, cut out by code, with a pixel grid: a thin line every 50
pixels, numbered along the top and the left edge. Find its two rows of female header sockets (black plastic strips
with square openings) along the long edges:
- "digital": pins 0..13, with AREF and GND (and on newer boards SDA, SCL) at one end;
- "power": the power and analog row (IOREF, RESET, 3V3, 5V, GND, VIN, then A0..A5, maybe more).
For each row give the pixel centre of its FIRST and LAST opening (read x and y off the grid), the label printed on
the board next to each of those two openings, and how many openings the row has in all (count them).
Answer ONLY with JSON: {"digital": {"first": [x, y], "first_label": "", "last": [x, y], "last_label": "",
"openings": 0}, "power": {"first": [x, y], "first_label": "", "last": [x, y], "last_label": "", "openings": 0}}
(a row you cannot see clearly: null)."""

VERIFY = """The photos are close-ups of the two ends of each header row of an Arduino-style board seen from above (black
plastic strips with square openings). Code has drawn a short yellow line, with a yellow name, at the opening it thinks
is each end one. IGNORE the labels printed on the board (they sit beside the openings, often half an opening or more
along). Look only at the black header itself: does each yellow line point at the middle of the very LAST opening at
that end of the strip (not the one before it, not past the end, not between two openings)?
Answer ONLY with JSON: {"ok": true or false, "ends": [{"photo": 1, "right": true, "off": "a few words"}], "why": ""}"""


def _grid(img, step=50):
    g = img.copy()
    h, w = g.shape[:2]
    for x in range(0, w, step):
        cv2.line(g, (x, 0), (x, h), (0, 255, 255) if x % 250 else (0, 160, 255), 1)
        if x % 100 == 0:
            cv2.putText(g, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(g, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    for y in range(0, h, step):
        cv2.line(g, (0, y), (w, y), (0, 255, 255) if y % 250 else (0, 160, 255), 1)
        if y % 100 == 0:
            cv2.putText(g, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(g, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return g


def _jpeg(img, q=88):
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()


def _json(text):
    i, j = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[i:j + 1])
    except ValueError:
        return {}


def layout_of(kind, r):
    """Which layout a row is from its two end labels and its count, and whether its ends must be swapped (the layout
    starts at SCL / AREF, or at NC / IOREF / RESET): (layout, swap) or (None, False)."""
    a, b = str(r.get("first_label") or "").upper().strip(), str(r.get("last_label") or "").upper().strip()
    n = int(r.get("openings") or 0)
    if kind == "digital":
        start = {"SCL", "SDA", "AREF"}
        swap = b in start or (a in {"0", "D0", "RX", "RX0", "RX<0"} and b not in {"0", "D0"})
        first = b if swap else a
        if n >= 24:
            return "mega", swap
        if first in {"SCL", "SDA"} or n >= 18:
            return "uno-r3", swap
        if first == "AREF" or n == 16:
            return "duemilanove", swap
        return None, False
    swap = a.startswith("A") and a[1:].isdigit() or a in {"CANTX", "DAC1"}
    last = a if swap else b
    if last in {"CANTX", "CANRX"}:
        return "power-analog-due", swap
    if n >= 22:
        return "power-analog-mega", swap
    if n >= 14:
        return "power-analog-8", swap
    if n >= 12:
        return "power-analog-6", swap
    return None, False


def _fit(ref, name, first, last):
    """The row's openings near the ends given: ({pin: xy}, fit) or None. The comb only nudges (a third of an opening
    along, a little across): it may not slide to the next opening."""
    order, idx = U.layout(name)
    a, b = np.array(first, float), np.array(last, float)
    if np.linalg.norm(b - a) < 50:
        return None
    u = (b - a) / np.linalg.norm(b - a)
    nrm = np.array([-u[1], u[0]])
    if (a - np.array([ref.shape[1] / 2, ref.shape[0] / 2])) @ nrm < 0:
        nrm = -nrm
    pitch = np.linalg.norm(b - a) / idx[order[-1]]
    got = U.openings(ref, a, u, nrm, pitch, order, idx, across_range=(-0.4, 0.4), spread=0.05, along_range=0.33)
    if got is None or got[1]["contrast"] < 20:
        return None
    pins, fit = got
    return {"layout": name, "from": "openings", "made": "auto", "fit": fit,
            "pins": {p: [round(float(v), 1) for v in pins[p]] for p in order}}


def _tried():
    try:
        return json.loads(TRIED.read_text())
    except (OSError, ValueError):
        return {}


def wanted(board_id, uno_layout=False):
    """Does this board want a reference made: Uno-shaped, none in the files or the database, not given up on."""
    if not (board_id in UNO_SHAPED or uno_layout):
        return False
    if U._ref_file(board_id) is not None or any(r["board"] == board_id for r in U._load_refs()):
        return False
    return len(_tried().get(board_id, [])) < 3  # three photos that would not do: stop trying


def make(board_id, photo, keep_bad=None, save=True):
    """A reference for board_id from photo (the board seen from above). Kept only when the check agrees. save=False:
    try only (nothing written; keep_bad gets the drawn names)."""
    from gather.gather_vlm import ask
    cost = 0.0

    def fail(why):
        if not save:
            return {"ok": False, "why": why, "cost_usd": round(cost, 4)}
        t = _tried()
        t.setdefault(board_id, []).append({"photo": pathlib.Path(photo).name, "why": why})
        TRIED.parent.mkdir(parents=True, exist_ok=True)
        TRIED.write_text(json.dumps(t, indent=1))
        return {"ok": False, "why": why, "cost_usd": round(cost, 4)}

    img = _board.load(str(photo))
    H, W = img.shape[:2]
    f = 1200 / max(H, W)
    box = _board.arduino_box(cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))
    if not box:
        return fail("no board found in the photo")
    x0, y0, x1, y1 = box["box"]
    if max((x1 - x0) * W, (y1 - y0) * H) < MIN_EDGE:
        return fail("the board is too small in the photo")
    ref, _, _ = U.crop(img)
    out, st, _ = ask(MODEL, [(_jpeg(_grid(ref)), "image/jpeg")], FIND, max_tokens=4000, effort="medium")
    cost += st.get("cost_usd") or 0
    found = _json(out)
    rows = []
    for kind in ("digital", "power"):
        r = found.get(kind)
        if not isinstance(r, dict) or not r.get("first") or not r.get("last"):
            continue
        name, swap = layout_of(kind, r)
        if not name:
            continue
        a, b = (r["last"], r["first"]) if swap else (r["first"], r["last"])
        row = _fit(ref, name, a, b)
        if row:
            rows.append(row)
    if not any(r["layout"] in ("uno-r3", "duemilanove", "mega") for r in rows):
        return fail(f"the digital header was not found ({out[:200]})")
    # the check: the names drawn as the overlay would, on the photo itself, read against the board's own print
    U.LOCAL_REFS.mkdir(parents=True, exist_ok=True)
    tmp = {"board": board_id, "image": ref, "rows": rows,
           **dict(zip(("kp", "des"), U._features(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY))))}
    drawn = _draw(ref, rows)
    out2, st2, _ = ask(MODEL, [(_jpeg(e), "image/jpeg") for e in _ends(drawn, rows)], VERIFY, max_tokens=2000,
                       effort="medium")
    cost += st2.get("cost_usd") or 0
    v = _json(out2)
    if keep_bad:
        pathlib.Path(keep_bad).write_bytes(_jpeg(drawn))
    if not save:
        verdict = v.get("ok") is True and all(e.get("right") is not False for e in v.get("ends") or [])
        return {"ok": verdict, "why": v.get("why") or "", "rows": [r["layout"] for r in rows],
                "cost_usd": round(cost, 4), "fits": [r["fit"] for r in rows], "made_rows": rows}
    if v.get("ok") is not True or not all(e.get("right") is not False for e in v.get("ends") or []):
        return fail(f"the names were off: {v.get('why') or out2[:120]}")
    if not save:
        return {"ok": True, "why": v.get("why") or "", "rows": [r["layout"] for r in rows], "cost_usd": round(cost, 4),
                "fits": [r["fit"] for r in rows], "made_rows": rows}
    cv2.imwrite(str(U.LOCAL_REFS / f"{board_id}.jpg"), ref, [cv2.IMWRITE_JPEG_QUALITY, 92])
    meta = {"photo": pathlib.Path(photo).name, "source": "the learner's own photo (made by code: board_ref_auto)",
            "made": "auto", "status": "auto", "rows": rows}
    (U.LOCAL_REFS / f"{board_id}.json").write_text(json.dumps(meta, indent=1))
    del tmp
    U._saved(board_id)
    return {"ok": True, "why": v.get("why") or "", "rows": [r["layout"] for r in rows], "cost_usd": round(cost, 4)}


def _ends(drawn, rows, k=3.0):
    """Close-ups (3x) of both ends of each row, the yellow names drawn: what the check looks at."""
    out = []
    for row in rows:
        order, _ = U.layout(row["layout"])
        a, b = np.array(row["pins"][order[0]]), np.array(row["pins"][order[-1]])
        pitch = np.linalg.norm(b - a) / (len(order) + 0.6 * (len(U.LAYOUTS[row["layout"]]) - 1))
        for p in (a, b):
            r = int(pitch * 3.2)
            x0, y0 = int(max(0, p[0] - r)), int(max(0, p[1] - r))
            c = drawn[y0:int(p[1] + r), x0:int(p[0] + r)]
            if c.size:
                out.append(cv2.resize(c, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC))
    return out


def _draw(ref, rows):
    """The names at the openings, as the overlay draws them (the photo is its own reference)."""
    out = ref.copy()
    mid = np.array([ref.shape[1] / 2, ref.shape[0] / 2])
    for row in rows:
        order, idx = U.layout(row["layout"])
        pins = {p: np.array(v, float) for p, v in row["pins"].items()}
        a, b = pins[order[0]], pins[order[-1]]
        u = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-u[1], u[0]])
        if (a - mid) @ nrm < 0:
            nrm = -nrm
        pitch = np.linalg.norm(b - a) / idx[order[-1]]
        for p, xy in pins.items():
            name = p.rstrip(".")
            cv2.line(out, tuple(int(v) for v in xy + nrm * pitch * 0.6), tuple(int(v) for v in xy + nrm * pitch * 1.3),
                     (0, 230, 255), 2)
            lab = xy + nrm * pitch * 1.9
            (tw, th), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            x, y = int(lab[0] - tw / 2), int(lab[1] + th / 2)
            cv2.rectangle(out, (x - 3, y - th - 3), (x + tw + 3, y + 4), (0, 230, 255), -1)
            cv2.putText(out, name, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    return out


def in_background(board_id, photo, uno_layout=False):
    """make() on its own thread when the board wants one (never holds up the learner's check)."""
    if not wanted(board_id, uno_layout):
        return False
    import threading
    threading.Thread(target=lambda: _log(board_id, make(board_id, photo)), daemon=True).start()
    return True


def _log(board_id, r):
    print(f"board reference for {board_id}: {'made' if r.get('ok') else 'not made'} ({r.get('why')}), "
          f"${r.get('cost_usd')}", file=sys.stderr)


if __name__ == "__main__":
    print(json.dumps(make(sys.argv[1], sys.argv[2], keep_bad=sys.argv[3] if len(sys.argv) > 3 else None), indent=1))
