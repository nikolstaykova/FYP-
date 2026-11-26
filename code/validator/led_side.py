"""An LED's legs from two photos of the same moment: from above, and low from the side (30-45 degrees).

From above, the LED's body hides a leg (the learner's legs are bent 3-5 columns apart and the body tilts, so geometry
from above only narrows it to a few columns). The board is flat, so its hole grid straightens from any angle: in the
straightened side photo a leg's tip lands on its true hole, and from low down the legs are seen under the body.
Code finds the LED from above, straightens and numbers both photos centred on it; the model reads the holes the legs
go into. 24 Nov 2026, 10 labelled positions: both legs right 10/10, all sure (from above alone 9/10, 1 sure).
PHOTO_TUNING.md section 15.

    read(top_photo, side_photo) -> {"columns": [a, b], "half", "long", "sure", "why", "cost_usd"} or None
"""
import json
import threading

from gather.gather_vlm import ask
from validator import board, geometry as G

MODEL = "claude-opus-5-5"
CELL = 40
_lock = threading.Lock()  # geometry seeds OpenCV's random generator: one photo at a time

Q = """Photo 1 is a breadboard from above, Photo 2 the same board, nothing moved, from low at the side. Both have been
straightened by code and every hole column carries its number in a yellow box, above and below each half (they match
the numbers printed on the board).
There is an LED on the board. Find where each of its two legs goes INTO a hole: follow each thin metal leg from the
LED down to the board, to the hole it disappears into, and read that hole's column number from the yellow box in line
with it. From above the LED's body hides a leg; Photo 2, from the side, shows them going in: read the columns there,
and use Photo 1 to check it is the same place. If you can see which leg is the longer one (the long leg is the +),
give its column as "long", else null.
Answer ONLY with JSON: {"columns": [a, b], "half": "top" or "bottom", "long": a column or null, "sure": true or false,
"why": "a few words"}"""


def _straight(path, orient=None):
    full = board.load(str(path))
    g = G.best_grid(full)
    flat, info = G.flat_board(str(path), cell=CELL, g=g, src=full)
    if flat is None:
        return None, None, None
    occ = G.occupied(flat, info)
    if G.orientation(g, occ, orient)[0]:  # the same way up as the step check (this lesson's board)
        flat, info = G.flat_board(str(path), cell=CELL, g=g, src=full, flip=True)
    shift, _ = G.printed_shift(flat, info)
    return flat, info, shift


def around(top_photo, orient=None):
    """The printed columns around the LED seen from above (4 either side of its body), or None."""
    with _lock:
        flat, info, shift = _straight(top_photo, orient)
        if flat is None:
            return None
        found = G.leds(flat, info, shift)
    if not found:
        return None
    k = 0 if found[0]["half"] == "top" else 1
    xs = [x for x, _ in found[0]["outline"]]
    a, b = sorted(int(G.label(round(x / CELL - 1), k, shift)) for x in (min(xs), max(xs)))
    return list(range(a - 4, b + 5))


def read(top_photo, side_photo, orient=None):
    try:
        cols = around(top_photo, orient)
        with _lock:
            t = G.analyse(str(top_photo), around=cols, orient=orient)
            s = G.analyse(str(side_photo), around=cols, orient=orient)
    except Exception:  # never let this break a check
        return None
    if not t.get("closeup") or not s.get("closeup") or not s.get("trusted"):
        return None
    out, st, _ = ask(MODEL, [(t["closeup"], "image/jpeg"), (s["closeup"], "image/jpeg")], Q, max_tokens=3000,
                     effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        a = json.loads(out[i:j + 1])
        columns = sorted(int(c) for c in a.get("columns") or [])
    except (ValueError, TypeError):
        return None
    if len(columns) != 2 or columns[0] == columns[1]:
        return None
    long_ = a.get("long")
    try:
        long_ = int(long_) if long_ is not None else None
    except (TypeError, ValueError):
        long_ = None
    return {"columns": columns, "half": a.get("half"), "long": long_ if long_ in columns else None,
            "sure": a.get("sure") is not False, "why": str(a.get("why") or ""), "cost_usd": st.get("cost_usd") or 0,
            "closeups": (t["closeup"], s["closeup"])}


def merge(plan_, readings, pair):
    """The pair's two columns put on the LED's legs. Which is the long leg: a leg read for sure from above that is in
    one of the two columns keeps it and the other leg takes the other; else the model's "long" from the side; else
    each leg takes the column nearer its own reading. Returns the keys set."""
    if not pair or not pair["sure"]:
        return []
    legs = [x for x in plan_["legs"] if x["kind"] == "strip" and "led" in (x["part"] + " " + x["who"]).lower()]
    if len(legs) != 2:
        return []
    longk = next((x["key"] for x in legs if "long" in x["who"].lower() or "+" in x["who"]), legs[0]["key"])
    shortk = next(x["key"] for x in legs if x["key"] != longk)
    a, b = pair["columns"]

    def col(k):
        try:
            return int((readings.get(k) or {}).get("column"))
        except (TypeError, ValueError):
            return None
    sure = {k: (readings.get(k) or {}).get("sure") is not False and col(k) in (a, b) for k in (longk, shortk)}
    if sure[longk]:
        lc = col(longk)
    elif sure[shortk]:
        lc = b if col(shortk) == a else a
    elif pair["long"] is not None:
        lc = pair["long"]
    else:
        cl = col(longk)
        lc = a if cl is None or abs(cl - a) <= abs(cl - b) else b
    sc = b if lc == a else a
    # the half as the step check read it (its board is turned the lesson's way up); the pair's own, else
    halves = [str((readings.get(k) or {}).get("half") or "") for k in (longk, shortk)]
    half = next((h for h in halves if h in ("top", "bottom")), None) or (pair["half"] if pair["half"] in ("top", "bottom") else "top")
    for k, c in ((longk, lc), (shortk, sc)):
        r = readings.setdefault(k, {"key": k})
        r.update(column=c, half=half, sure=True, by="side photo",
                 why=f"seen going in from the side: column {c} ({pair['why']})")
    return [longk, shortk]
