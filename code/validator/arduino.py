"""The Arduino step check: after a build step, a photo of the breadboard, and is every leg where it should be?

The logic is CircuitQuest's (core/checker.py, core/engine.py "landing" checks), on what a photo can show. A photo
cannot show the exact hole, and does not need to: on a breadboard only the STRIP matters (a column on one half, or a
power rail), and on the Arduino the pin. So every leg of the step is checked as a place:
  strip  "14t"   column 14, top half (rows a-e; "b" is the bottom half, rows f-j)
  rail   "tp"    the top + rail ("tn" top -, "bp" bottom +, "bn" bottom -)
  pin    "uno:13" an Arduino pin (any GND is the same GND)
and each leg either SHARES a place with an earlier leg (it must be in that same strip: the model is asked "same
column as the resistor's leg?", which a photo shows much better than a number) or STARTS a new one (any free strip
will do: the model gives the column, counted from a leg it knows). A leg that starts a new strip somewhere else is
accepted and the lesson's column becomes the learner's for every later step ("we want column 3, you used 4": from
now on 3 means their 4). Verdicts, as CircuitQuest: pass; harmless (a resistor or wire turned round); moved
(accepted, in their columns); wrong (a leg that should share a strip does not, a strip that would join two things,
an LED the wrong way round, a pin that cannot stand in); unsure (the model could not read it: a close-up is asked).

The prompt is made for each step from the lesson (plan + prompt); a lesson can add its own words for a step (a
`check_note` on the step, stored with the lesson and in the database): `python -m validator.arduino note ...`.

  plan(lesson_id, step)                  the legs this step places, where, and what each must share
  prompt(plan_, state)                   what the model is asked
  look(photos, plan_, state)             the model's reading (Haiku; the legs it cannot read go to Opus once)
  judge(plan_, reading, state)           the verdict, leg by leg, and the learner's places from now on
  check(lesson_id, step, photos, state)  all of it
state: {"where": {lesson place: their place}} (the learner's columns and pins so far), sent back updated.

Run  ./pinpoint validator.arduino plan blink 2
     ./pinpoint validator.arduino check blink 2 photo.jpg [photo2.jpg]
     ./pinpoint validator.arduino note blink 2 "The LED is small: look closely at which leg is longer."
"""
import json
import pathlib
import re
import sys

# Testing Opus first (15 Nov): Haiku miscounted a column by one and was sure of it (step-20261115-213655-9d61:
# 14 for 13, twice), so it never asked Opus. Back to Haiku -> Opus once the photos are cropped and zoomed.
FIRST = "claude-opus-5-5"
SECOND = "claude-opus-5-5"
RAILS = {"tp": "the top + rail", "tn": "the top - rail", "bp": "the bottom + rail", "bn": "the bottom - rail"}
LEG = {"A": "long leg (+)", "C": "short leg (-)", "1": "one leg", "2": "other leg", "a": "one end", "b": "other end"}


# ---- the lesson: what this step places, and where --------------------------------------------------------------
def _lesson(lesson_id):
    from graph import lesson_store
    view = lesson_store.assemble(lesson_id)
    _, graphs = lesson_store._load(lesson_id)
    phys = graphs.get("physical") or {"nodes": []}
    nodes = {n["id"]: n for n in phys["nodes"]}
    cards = lesson_store._cards(lesson_store.PARTS)
    card = {i: (lesson_store.definition(cards, n.get("type"))[0] or {}) for i, n in nodes.items()}
    rec = graphs.get("lesson") or {}
    return view, nodes, card, rec


def _is_board(card_):
    return (card_.get("category") or "").lower() in ("microcontroller", "board", "microcontroller board") or \
        any(str(p.get("id", "")).upper().startswith("GND") for p in card_.get("ports") or []) and \
        len(card_.get("ports") or []) > 10


def place_of(end, nodes, card):
    """A join's other end as a place: ("strip", "14t"), ("rail", "tn"), ("pin", "uno:13"), ("part", "x:y")."""
    inst, _, port = str(end).partition(":")
    n = nodes.get(inst) or {}
    if (n.get("type") or "").startswith("breadboard"):
        m = re.match(r"(\d+)([tb])\.", port)
        if m:
            return "strip", f"{int(m.group(1))}{m.group(2)}"
        m = re.match(r"([tb][pn])\.", port)
        if m:
            return "rail", m.group(1)
    if _is_board(card.get(inst, {})):
        return "pin", f"{inst}:{'GND' if port.upper().startswith('GND') else port}"
    return "part", f"{inst}:{port}"


def _who(nodes, inst, port):
    n = nodes.get(inst) or {}
    label = re.sub(r"\s*\(.*?\)", "", n.get("label") or inst).strip()
    return f"the {label}'s {LEG.get(port, port)}"


def say_place(kind, p):
    """A place the way a person says it."""
    if kind == "strip":
        m = re.match(r"(\d+)([tb])$", p)
        return f"column {m.group(1)} ({'top' if m.group(2) == 't' else 'bottom'} half)" if m else p
    if kind == "rail":
        return RAILS.get(p, p)
    if kind == "pin":
        pin = p.split(":", 1)[1]
        return "the Arduino's GND" if pin == "GND" else f"the Arduino's pin {pin}"
    return p


def plan(lesson_id, step):
    """The legs a build step places: [{key, leg, part, who, kind, lesson, shares (an earlier leg, or None),
    polarized, swap_group}], with the step's words and the legs placed before it (landmarks). `step`: its number in
    the lesson (as the app counts, from 1) or its id."""
    view, nodes, card, rec = _lesson(lesson_id)
    steps = [s for s in view["steps"] if s.get("kind") != "overview"]
    idx = next((i for i, s in enumerate(steps) if s["id"] == str(step)), None)
    if idx is None and str(step).isdigit():
        idx = int(step) - 1
    if idx is None or not 0 <= idx < len(steps):
        raise ValueError(f"no step {step} in {lesson_id}")

    def legs_of(s):
        out = []
        for c in s.get("connections") or []:
            a, b = c["from"], c["to"]
            ka, _ = place_of(a, nodes, card)
            kb, _ = place_of(b, nodes, card)
            leg, other = (a, b) if ka == "part" else (b, a) if kb == "part" else (a, b)
            kind, where = place_of(other, nodes, card)
            if kind == "part" and place_of(leg, nodes, card)[0] == "part" and leg.split(":")[0] == other.split(":")[0]:
                continue
            out.append((leg, kind, where))
        return out

    earlier, seen_place = [], {}
    for s in steps[:idx]:
        for leg, kind, where in legs_of(s):
            earlier.append({"leg": leg, "who": _who(nodes, *leg.split(":", 1)), "kind": kind, "lesson": where})
            seen_place.setdefault(where, earlier[-1])
    s = steps[idx]
    legs, sym = [], {}
    for k, (leg, kind, where) in enumerate(legs_of(s), 1):
        inst, port = leg.split(":", 1)
        c = card.get(inst, {})
        polarized = bool((c.get("metadata") or {}).get("polarized"))
        two = len(c.get("ports") or []) == 2
        x = {"key": f"L{k}", "leg": leg, "part": inst, "who": _who(nodes, inst, port), "kind": kind, "lesson": where,
             "shares": seen_place.get(where), "polarized": polarized, "swap_group": inst if two and not polarized else None}
        legs.append(x)
        seen_place.setdefault(where, {"leg": leg, "who": x["who"], "kind": kind, "lesson": where, "this_step": x["key"]})
        sym.setdefault(inst, []).append(x["key"])
    for x in legs:  # only a part with both legs in this step can be turned round
        if x["swap_group"] and len(sym[x["part"]]) != 2:
            x["swap_group"] = None
    pins = {p: v for p, v in ((rec.get("substitutions") or {}).get("pins") or {}).items() if isinstance(v, dict)}
    return {"lesson_id": lesson_id, "step": s["id"], "n": idx + 1, "text": s.get("text") or "", "legs": legs,
            "earlier": earlier, "note": s.get("check_note") or "", "pins": pins}


# ---- the question to the model ---------------------------------------------------------------------------------
LOOK = """You check one step of an Arduino build on a breadboard, from photos. The step said: "{text}"

How a breadboard works: the holes are numbered along the long edge (the numbers are printed, usually every 5: 1, 5,
10, 15...), and lettered across (a-e on one half, f-j on the other, with a gap in the middle). Each COLUMN on one half
is one strip: its five holes are joined. The halves are separate. The long rows along both edges are the power rails:
+ (red line) and - (blue line). On the Arduino, every pin socket has its label printed beside it (13, 12, ~11, GND,
5V, A0...). A jumper wire's end has a black plastic connector, wider than a hole, which hides the hole it is in: the
metal pin is at the connector's end AWAY from where the wire leaves it, at that end's middle (not under the middle of
the black part, and not where the wire's colour is).
{earlier}
For each item below, find that leg (or wire end) in the photos and answer what is asked:
{items}
Count columns from a leg you are sure of when you cannot read the printed number. Do not guess: if you cannot see a
leg, or cannot tell its column, say so ("sure": false, and "why": one short sentence, at most 15 words). If
something placed earlier looks pulled out or moved, list it in "moved".{note}
Answer ONLY with JSON: {{"legs": [{{"key": "L1", "offset": null, "same": null, "column": 0, "half": "", "rail": "", "pin": "", "sure": true, "why": ""}}], "moved": []}}
("offset" and "same" only where asked; "half": "top" or "bottom"; "rail": "top +", "top -", "bottom +" or "bottom -";
"pin": the Arduino label, as printed.)"""


def their(where, kind, p):
    """The learner's place for a lesson place, so far."""
    return where.get(p, p)


def prompt(plan_, state=None):
    where = (state or {}).get("where") or {}
    earlier = ""
    if plan_["earlier"]:
        ls = [f"  - {e['who']}: {say_place(e['kind'], their(where, e['kind'], e['lesson']))}" for e in plan_["earlier"]]
        earlier = "\nAlready on the board (checked before; use them as landmarks):\n" + "\n".join(ls[-14:]) + "\n"
    items = []
    for x in plan_["legs"]:
        sh = x["shares"]
        if x["kind"] == "pin":
            pin = their(where, "pin", x["lesson"])
            items.append(f"- {x['key']}: {x['who']}. Which Arduino pin socket is it in? The lesson wants "
                         f"{say_place('pin', pin)}. Give \"pin\".")
        elif x["kind"] == "rail":
            items.append(f"- {x['key']}: {x['who']}. Which power rail is it in? The lesson wants "
                         f"{RAILS.get(their(where, 'rail', x['lesson']), x['lesson'])}. Give \"rail\".")
        elif x["kind"] == "part":
            items.append(f"- {x['key']}: {x['who']}. Is it connected to {x['lesson']}? Give \"same\".")
        elif sh:
            ref = sh["who"] + (" (placed in this step too)" if sh.get("this_step") else "")
            at = "" if sh.get("this_step") else f", which is in {say_place('strip', their(where, 'strip', x['lesson']))}"
            items.append(f"- {x['key']}: {x['who']}. Find it and count the columns between it and {ref}{at}. "
                         "Give its \"column\" and \"half\", and \"offset\": how many columns it is from that leg (0 if "
                         "it is in exactly the same column; 1 or -1 if it is one column off, towards higher or lower "
                         "numbers; and so on). One column off is a common mistake, so count the holes carefully.")
        else:
            items.append(f"- {x['key']}: {x['who']}. Which column and which half is it in? (The lesson suggests "
                         f"{say_place('strip', x['lesson'])}, but any free column is fine.) Give \"column\" and \"half\".")
    note = f"\nAbout this step: {plan_['note']}" if plan_.get("note") else ""
    return LOOK.format(text=plan_["text"], earlier=earlier, items="\n".join(items), note=note)


def _answer(text):
    i, j = text.find("{"), text.rfind("}")
    try:
        d = json.loads(text[i:j + 1])
    except ValueError:
        return {}, []
    legs = {x["key"]: x for x in d.get("legs") or [] if isinstance(x, dict) and x.get("key")}
    return legs, [str(m) for m in d.get("moved") or [] if m]


def reading_place(x, r):
    """What the model read for a leg, as a place (or None when it could not tell)."""
    if not r or r.get("sure") is False:
        return None
    if x["kind"] == "pin":
        pin = str(r.get("pin") or "").strip().upper().lstrip("~D").replace("PIN", "").strip()
        if not pin:
            return None
        board = x["lesson"].split(":")[0]
        return f"{board}:{'GND' if pin.startswith('GND') else pin}"
    if x["kind"] == "rail":
        t = str(r.get("rail") or "").lower()
        if not t:
            return None
        return ("t" if "top" in t else "b") + ("n" if "-" in t or "minus" in t or "neg" in t or "blue" in t else "p")
    col = r.get("column")
    try:
        col = int(col)
    except (TypeError, ValueError):
        return None
    if col <= 0:
        return None
    half = str(r.get("half") or "").lower()
    return f"{col}{'b' if half.startswith('b') else 't'}"


LOCATE = """This photo shows a breadboard{and_arduino}. In this step the learner put in: {parts}.
Find where those legs go into the board. Give a "board" box that contains all those legs where they enter the holes,
the printed column numbers nearest to them (the numbers along the edge of that half), and a margin of a few columns
on each side.{arduino_ask}
Coordinates from 0 to 1000 across the image (x, left to right) and down it (y, top to bottom).
Answer ONLY with JSON: {{"board": [x0, y0, x1, y1]{arduino_json}}}"""
LOCATE_ARDUINO = (' Also give an "arduino" box around the Arduino\'s pin header(s) where this step\'s wires plug in, with '
                  'the printed pin labels beside them (null if no Arduino is in the photo).')


def _crop(im, box, edge, margin=0.15):
    """A box (0-1000) cut from the full-size image with a margin, enlarged to `edge` and sharpened, as JPEG."""
    import io
    from PIL import Image, ImageFilter
    W, H = im.size
    try:
        x0, y0, x1, y1 = [float(v) / 1000 for v in box]
    except Exception:
        return None
    x0, x1, y0, y1 = x0 * W, x1 * W, y0 * H, y1 * H
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    mx, my = margin * (x1 - x0) + 0.02 * W, margin * (y1 - y0) + 0.02 * H  # the box is only roughly right
    c = im.crop((int(max(0, x0 - mx)), int(max(0, y0 - my)), int(min(W, x1 + mx)), int(min(H, y1 + my))))
    s = edge / max(c.size)
    if s > 1:
        c = c.resize((round(c.width * s), round(c.height * s)), Image.LANCZOS)
    c = c.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=90)
    return buf.getvalue(), "image/jpeg"


def zoom(photo, plan_, edge=1600):
    """One photo, split for reading: the breadboard around this step's parts, and (when a wire goes to an Arduino
    pin) the Arduino's pin header, each cut from the FULL-size photo and enlarged. One quick Haiku look finds both
    boxes (about 0.05 cents). (16 Nov: the board crop took the columns read right from 60% to 80% with Haiku, 50% to
    90% with Opus; research/recognition/step_crop.py.)
    Returns ({"board": image or None, "arduino": image or None}, cost)."""
    from PIL import Image, ImageOps
    from gather import gather_vlm as vlm
    parts = sorted({x["who"].split("'s ")[0].replace("the ", "") for x in plan_["legs"]})
    pins = any(x["kind"] == "pin" for x in plan_["legs"])
    q = LOCATE.format(parts=", ".join(parts), and_arduino=" and an Arduino" if pins else "",
                      arduino_ask=LOCATE_ARDUINO if pins else "", arduino_json=', "arduino": [x0, y0, x1, y1]' if pins else "")
    out, st, _ = vlm.ask(FINDER, [vlm.shrink(photo, 1600, 85)], q, max_tokens=2500, effort="low")
    cost = st.get("cost_usd") or 0
    i, j = out.find("{"), out.rfind("}")
    try:
        boxes = json.loads(out[i:j + 1])
    except Exception:
        return {"board": None, "arduino": None}, cost
    im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    return {"board": _crop(im, boxes.get("board") or boxes.get("box"), edge),
            "arduino": _crop(im, boxes.get("arduino"), edge, margin=0.1) if pins and boxes.get("arduino") else None}, cost


FINDER = "claude-haiku-5-5"


def shots(lesson_id, step):
    """The photos a step check needs, in order: the breadboard, and the Arduino too when a leg or wire goes into one
    of its pins (one photo close enough to read the columns cannot show the Arduino's pin labels as well)."""
    p = plan(lesson_id, step)
    kinds = {x["kind"] for x in p["legs"]}
    out = (["board"] if kinds - {"pin"} else []) + (["arduino"] if "pin" in kinds else [])
    return {"step": p["step"], "n": p["n"], "shots": out if p["legs"] else []}


def look(photos, plan_, state=None, model=FIRST, keys=None, zoomed=None):
    """The model's reading of the photos: ({key: answer}, moved, stats). keys: only these legs (a second look).
    zoomed: zoom()'s close-ups of the board and the Arduino; the model sees them, then the whole photo."""
    from gather import gather_vlm as vlm
    p = dict(plan_, legs=[x for x in plan_["legs"] if not keys or x["key"] in keys])
    z = zoomed or {}
    images, said = [], []
    if z.get("numbered"):
        up = "bottom (rows f-j)" if z.get("upside_down") else "top (rows a-e)"
        images.append(z["numbered"])
        said.append("the breadboard straightened by code, with every column's number written in yellow: the yellow "
                    "row above the upper half belongs to the upper half, the one below the lower half to the lower "
                    f"half; the upper half here is the board's {up} half. These numbers are exact (computed from the "
                    "holes): read a leg's column from the yellow numbers instead of counting holes")
    if z.get("board"):
        images.append(z["board"])
        said.append("a close-up of the breadboard around this step's parts (read the columns here)")
    if z.get("arduino"):
        images.append(z["arduino"])
        said.append("a close-up of the Arduino's pins (read the pin labels here)")
    images.append(vlm.shrink(photos[0], 1600, 85))
    said.append("the whole photo (to see where things are and follow the wires)")
    for ph in photos[1:]:
        images.append(vlm.shrink(ph, 1600, 85))
        said.append("another photo of the same build")
    q = ("The images, in order: " + "; ".join(f"{k}) {w}" for k, w in enumerate(said, 1)) + ". They are all the "
         "same build, so a leg in a close-up is the same leg in the whole photo.\n") + prompt(p, state)
    out, stats, _ = vlm.ask(model, images, q, max_tokens=3000, effort="low" if model == FIRST else "medium")
    legs, moved = _answer(out)
    return legs, moved, {**stats, "raw": out[:3000]}


# ---- the verdict ------------------------------------------------------------------------------------------------
def _pin_ok(plan_, lesson_pin, read):
    """Can the pin the learner used stand in for the lesson's? (The lesson's substitutions, as the tutor knows them.)"""
    sub = plan_["pins"].get(lesson_pin) or {}
    pin = read.split(":", 1)[1]
    if pin in (sub.get("refused") or {}):
        return False, sub["refused"][pin]
    return pin in [str(s) for s in sub.get("stand_ins") or []], ""


def _offset(r):
    """How many columns the model counted from the leg it should share (0 = the same column), or None."""
    try:
        return int((r or {}).get("offset"))
    except (TypeError, ValueError):
        return None


def _judge_one(plan_, x, read, r, where, used):
    """One leg: (status, their place or None, words). status: ok, moved, wrong, unsure."""
    lesson = x["lesson"]
    off = _offset(r)
    if read is None:
        if x["kind"] == "strip" and x["shares"] and r and r.get("sure") is not False and off is not None:
            want = where.get(lesson, lesson)
            if off == 0:
                return "ok", want, ""
            m = re.match(r"(\d+)([tb])$", want)
            got = f"{int(m.group(1)) + off}{m.group(2)}" if m else None
            return "wrong", got, (f"it should be in the same column as {x['shares']['who']} ({say_place('strip', want)}), "
                                  f"but it's {abs(off)} column{'s' if abs(off) > 1 else ''} off"
                                  + (f" (in {say_place('strip', got)})" if got else ""))
        if x["kind"] == "strip" and x["shares"] and r and r.get("same") is True and off is None:
            return "ok", where.get(lesson, lesson), ""  # only "same", no column: taken as said
        return "unsure", None, (r or {}).get("why") or "I couldn't see it clearly"
    want = where.get(lesson)
    if x["kind"] == "pin":
        want = want or lesson
        if read == want:
            return "ok", read, ""
        ok, why = _pin_ok(plan_, lesson, read)
        if ok and read not in used:
            return "moved", read, f"{say_place('pin', read)} instead of {say_place('pin', want)}: that works (the sketch uses that pin then)"
        return "wrong", read, (f"{say_place('pin', read)} can't be used: {why}" if why else
                               f"it should go in {say_place('pin', want)}, not {say_place('pin', read)}")
    if x["kind"] in ("strip", "rail"):
        if x["shares"]:
            want = want or lesson
            same = (r or {}).get("same")
            ref = x["shares"]["who"]
            if x["kind"] == "strip" and off is not None:
                agrees = (off == 0) == (read == want)  # the offset and the column read say the same thing
                if not agrees:
                    return "unsure", None, f"I can't tell for sure if it's in the same column as {ref}"
                if off == 0:
                    return "ok", want, ""
            elif same is True and read == want or (same is None and read == want):
                return "ok", want, ""
            return "wrong", read, f"it should be in the same {'column' if x['kind'] == 'strip' else 'rail'} as {ref} ({say_place(x['kind'], want)}), but it's in {say_place(x['kind'], read)}"
        if x["kind"] == "rail" and read[1] != lesson[1]:
            return "wrong", read, f"it should go in a {'+' if lesson[1] == 'p' else '-'} rail, not {say_place('rail', read)}"
        if read in used and used[read] != lesson:
            return "wrong", read, f"{say_place(x['kind'], read)} already has something else in it, so they would be joined"
        if read == lesson:
            return "ok", read, ""
        return "moved", read, f"{say_place(x['kind'], read)} instead of {say_place(x['kind'], lesson)}: that's fine"
    same = (r or {}).get("same")
    return ("ok", lesson, "") if same is not False else ("wrong", None, f"it should be connected to {lesson}")


def _run(plan_, readings, where0, order):
    """Judge the legs in order, with the readings swapped as `order` says. Returns (results, where)."""
    where = dict(where0)
    used = {v: k for k, v in where.items()}
    for e in plan_["earlier"]:  # what the earlier legs occupy (in the learner's places)
        used.setdefault(their(where, e["kind"], e["lesson"]), e["lesson"])
    out = []
    for x in plan_["legs"]:
        r = readings.get(order.get(x["key"], x["key"]))
        read = reading_place(x, r)
        status, place, words = _judge_one(plan_, x, read, r, where, used)
        if place and status in ("ok", "moved") and x["kind"] != "part":
            where[x["lesson"]] = place
            used[place] = x["lesson"]
        out.append({"key": x["key"], "leg": x["leg"], "who": x["who"], "kind": x["kind"], "status": status,
                    "place": say_place(x["kind"], place) if place else None, "words": words})
    return out, where


def judge(plan_, readings, state=None):
    """The step's verdict from the model's readings: CircuitQuest's order, pass < harmless/moved < unsure < wrong.
    A part with both legs in this step that is not polarized may be turned round (harmless); a polarized one
    (an LED) turned round is wrong, and said so."""
    where0 = dict((state or {}).get("where") or {})
    best = _run(plan_, readings, where0, {})
    swapped = []
    groups = {}
    for x in plan_["legs"]:
        if x["swap_group"]:
            groups.setdefault(x["swap_group"], []).append(x["key"])
    for g, (a, b) in ((g, ks) for g, ks in groups.items() if len(ks) == 2):  # turned round: try it
        trial = _run(plan_, readings, where0, {a: b, b: a})
        bad = lambda res: sum(r["status"] in ("wrong", "unsure") for r in res[0])  # noqa: E731
        if bad(trial) < bad(best):
            best, swapped = trial, swapped + [g]
    results, where = best
    reversed_ = []
    for x in plan_["legs"]:  # an LED the wrong way round: its two legs read where the other should be
        if x["polarized"]:
            mates = [y for y in plan_["legs"] if y["part"] == x["part"] and y is not x]
            if len(mates) == 1:
                y = mates[0]
                rx, ry = reading_place(x, readings.get(x["key"])), reading_place(y, readings.get(y["key"]))
                wx, wy = where0.get(x["lesson"], x["lesson"]), where0.get(y["lesson"], y["lesson"])
                if rx and ry and rx == wy and ry == wx and x["part"] not in reversed_:
                    reversed_.append(x["part"])
    for res in results:
        part = res["leg"].split(":")[0]
        if part in reversed_:
            res["status"] = "wrong"
            res["words"] = "the LED is the wrong way round: the long leg (+) goes where the short leg is now"
    st = [r["status"] for r in results]
    verdict = ("wrong" if "wrong" in st else "unsure" if "unsure" in st else
               "moved" if "moved" in st else "harmless" if swapped else "pass")
    changed = {k: v for k, v in where.items() if where0.get(k) != v and k != v}
    columns = {}
    for k, v in where.items():  # for the screen: the lesson's column numbers -> theirs (same half)
        a, b = re.match(r"(\d+)[tb]$", k), re.match(r"(\d+)[tb]$", v)
        if a and b and a.group(1) != b.group(1):
            columns[a.group(1)] = b.group(1)
    return {"verdict": verdict, "legs": results, "turned_round": swapped, "reversed": reversed_,
            "changed": {k: v for k, v in changed.items()}, "columns": columns, "state": {"where": where}}


def _asks(res):
    out = []
    for r in res["legs"]:
        if r["status"] == "unsure":
            out.append({"key": r["key"], "kind": "tell",
                        "message": f"I can't see {r['who']} clearly. Which column is it in, and on which half?"})
        elif r["status"] == "wrong":
            out.append({"key": r["key"], "kind": "fix", "message": f"{r['who'][0].upper() + r['who'][1:]}: {r['words']}."})
    return out


def _geometry(photo):
    """validator.geometry.analyse, never breaking a check (a photo it can't read just isn't helped)."""
    try:
        from validator import geometry
        return geometry.analyse(photo)
    except Exception as e:
        return {"trusted": False, "why": f"error: {e}", "ends": []}


def _snap(plan_, readings, geo):
    """Geometry first: a wire end the model read in a column, with a connector code is SURE of in the same half and at
    most one column away (the model's usual mistake), takes code's column (the offset moves with it); when they agree,
    the reading is sure even if the model wasn't. Only wire ends: a resistor or LED leg has no connector.
    Returns the keys geometry set or confirmed."""
    if not geo.get("trusted"):
        return []
    done = []
    for x in plan_["legs"]:
        r = readings.get(x["key"])
        if x["kind"] != "strip" or not r or "wire" not in (x["part"] + " " + x["who"]).lower():
            continue
        try:
            col = int(r.get("column"))
        except (TypeError, ValueError):
            continue
        half = "b" if str(r.get("half") or "").lower().startswith("b") else "t"
        near = [e for e in geo.get("ends") or [] if e["sure"] and e["half"][0] == half and abs(e["column"] - col) <= 1]
        if len(near) != 1:
            continue
        if near[0]["column"] == col:  # the model and code agree: that is sure, whatever the model felt
            if r.get("sure") is False:
                r["sure"] = True
                r["by"] = "model + geometry"
                r["why"] = f"geometry agrees: column {col} ({r.get('why') or ''})"[:200]
                done.append(x["key"])
            continue
        d = near[0]["column"] - col
        r["column"] = near[0]["column"]
        if _offset(r) is not None:
            r["offset"] = _offset(r) + d
        r["by"] = "geometry"
        r["why"] = f"geometry: the connector's pin is in column {r['column']} (the model said {col})"
        done.append(x["key"])
    return done


def check(lesson_id, step, photos, state=None, keep=None):
    """The whole check of one step: plan, Haiku's look, the verdict. The legs Haiku cannot read go straight to Opus,
    on the same photo (no retake); only a leg Opus cannot read either asks the learner for a closer photo.
    Returns the verdict with `asks` (what to tell or ask the learner), `say` (for the tutor) and the cost.
    keep: a folder to save the close-ups in (board.jpg, arduino.jpg: what the model was shown)."""
    p = plan(lesson_id, step)
    if not p["legs"]:
        return {"verdict": "pass", "legs": [], "asks": [], "state": state or {"where": {}}, "steps": [],
                "say": "Nothing to check on the board in this step.", "step": p["step"], "n": p["n"]}
    try:  # is the photo good enough to read at all? (free, a fraction of a second: no model is asked otherwise)
        from validator import board
        ok, why, m = board.quality(photos[0])
    except Exception:
        ok, why, m = True, "", {}
    if not ok:
        return {"verdict": "retake", "legs": [], "asks": [{"key": "", "kind": "retake", "message": why}], "say": why,
                "state": state or {"where": {}}, "readings": {}, "steps": [], "cost_usd": 0, "photo": m,
                "step": p["step"], "n": p["n"]}
    zoomed, zcost = zoom(photos[0], p)
    geo = _geometry(photos[0])
    if geo.get("trusted"):
        zoomed = {"numbered": (geo["numbered"], "image/jpeg"), "upside_down": geo.get("upside_down"), **zoomed}
    if keep:
        for k, v in zoomed.items():
            if v and isinstance(v, tuple):
                (pathlib.Path(keep) / f"{k}.jpg").write_bytes(v[0])
    readings, moved, st = look(photos, p, state, zoomed=zoomed)
    steps = [{"what": "finding the parts", "model": FINDER, "cost_usd": zcost},
             {"what": "step check" + (" (" + " + ".join(k for k, v in zoomed.items() if isinstance(v, tuple)) + " close-ups + whole photo)" if any(isinstance(v, tuple) for v in zoomed.values()) else " (whole photo)"), **{k: st.get(k) for k in ("model", "seconds", "cost_usd")}}]
    snapped = _snap(p, readings, geo)
    res = judge(p, readings, state)
    unsure = [r["key"] for r in res["legs"] if r["status"] == "unsure"]
    if unsure and SECOND != FIRST:  # the same photo, the bigger model, only those legs
        more, moved2, st2 = look(photos, p, state, model=SECOND, keys=unsure, zoomed=zoomed)
        steps.append({"what": "step check, second look", **{k: st2.get(k) for k in ("model", "seconds", "cost_usd")}})
        readings.update(more)
        moved += moved2
        snapped += _snap(p, readings, geo)
        res = judge(p, readings, state)
    steps.insert(1, {"what": "geometry (the board straightened, columns numbered, connectors found)",
                     "used": bool(geo.get("trusted")), "why": geo.get("why", ""), "connectors": len(geo.get("ends") or []),
                     "set_by_geometry": snapped, "cost_usd": 0})
    good = [r for r in res["legs"] if r["status"] in ("ok", "moved")]
    say = {"pass": "Everything in this step is in the right place.",
           "harmless": "All right: " + ", ".join(res["turned_round"]) + " is turned round, which is fine for it.",
           "moved": "It's all connected right, in their own columns: " + "; ".join(r["words"] for r in good if r["words"]),
           "unsure": "I couldn't see everything: " + "; ".join(f"{r['who']}: {r['words']}" for r in res["legs"] if r["status"] == "unsure"),
           "wrong": "Something needs fixing: " + "; ".join(f"{r['who']}: {r['words']}" for r in res["legs"] if r["status"] == "wrong"),
           }[res["verdict"]]
    return {**res, "asks": _asks(res), "moved_earlier": moved[:5], "say": say, "step": p["step"], "n": p["n"],
            "readings": readings, "steps": steps, "cost_usd": round(sum(s.get("cost_usd") or 0 for s in steps), 6)}


def told(lesson_id, step, state, readings, places):
    """What the learner SAYS about the legs the photo could not show ("the short leg is in column 18"), judged exactly
    as a reading of the photo: added to the photo's readings and the step judged again (a column already taken, or
    one that should be shared and is not, is still caught). places: {leg key: {"column", "half"} or {"pin"} or
    {"rail"}}. Returns the same shape as check()."""
    p = plan(lesson_id, step)
    readings = {k: dict(v) for k, v in (readings or {}).items()}
    for k, v in (places or {}).items():
        if k in {x["key"] for x in p["legs"]}:
            readings[k] = {"key": k, **{f: v.get(f) for f in ("column", "half", "rail", "pin") if v.get(f) not in (None, "")},
                           "sure": True, "by": "the learner said"}
    res = judge(p, readings, state)
    words = "; ".join(f"{r['who']}: {r['words']}" for r in res["legs"] if r["status"] in ("wrong", "unsure"))
    say = {"pass": "From what they told you, everything in this step is in the right place.",
           "harmless": "From what they told you, it's all right.",
           "moved": "From what they told you, it's connected right, in their own columns.",
           "unsure": "Still not settled: " + words, "wrong": "From what they told you, something needs fixing: " + words}[res["verdict"]]
    return {**res, "asks": _asks(res), "say": say, "step": p["step"], "n": p["n"], "readings": readings, "steps": [],
            "cost_usd": 0, "from": "the learner"}


# ---- a lesson's own words for a step's check --------------------------------------------------------------------
def set_note(lesson_id, step, note):
    """Store a step's own check words in the lesson (the steps graph, then the database): appended to the prompt."""
    from graph import lesson_store
    p = plan(lesson_id, step)
    d = lesson_store.STORE / lesson_id
    inst = json.loads((d / "instruction.json").read_text())
    for n in inst["nodes"]:
        if n["id"] == p["step"]:
            if note:
                n["check_note"] = note
            else:
                n.pop("check_note", None)
    (d / "instruction.json").write_text(json.dumps(inst, indent=1))
    lesson_store.sync_db(lesson_id)
    return p["step"]


def main(argv=None):
    a = list(argv or sys.argv[1:])
    if not a or a[0] not in ("plan", "prompt", "check", "note"):
        print(__doc__.split("Run")[1])
        return
    cmd, lid, step, rest = a[0], a[1], a[2], a[3:]
    if cmd == "plan":
        print(json.dumps(plan(lid, step), indent=1))
    elif cmd == "prompt":
        print(prompt(plan(lid, step)))
    elif cmd == "note":
        print("stored for", set_note(lid, step, " ".join(rest)))
    else:
        res = check(lid, step, rest)
        print(json.dumps({k: res[k] for k in ("verdict", "legs", "changed", "columns", "asks", "say", "cost_usd")}, indent=1))


if __name__ == "__main__":
    main()
