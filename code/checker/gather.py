"""The gather check, for both kinds of lesson: from a few photos, does the learner have what the lesson needs?

Electronics (an Arduino lesson's parts list): the question is open, "what is on the table?", because a different
board or resistor may still do the job.
  1 LOOK (Claude, all photos in one call): every object, counted once across photos, with the details that decide a
  substitute (resistor bands, board name, breadboard size, LED colour). 2 MATCH (code): each object to a catalogue
  part. 3 COMPARE (code): the lesson's parts list against what is there. 4 SUBSTITUTE (code): can what is there do
  the job, and what changes (pins moved, sketch lines rewritten). 5 RESEARCH: an object the catalogue does not know
  is looked up on the approved sites and carded (parts/mcp_server.lookup), then tried as a substitute.
LEGO (one gather card, about 10 pieces: graph/lego_gather.py): the question is closed, "are THESE pieces here?",
because a model cannot name LEGO pieces from scratch (tens of thousands of near-identical parts) but can tick off a
short list. Each piece goes to the model with its kind and size ("plate 2x2", "wheel", "minifigure head"); for each it
says there / another colour / wrong piece (something like it, but not it: what it is) / not sure / not there
(card_look). Close-ups: Haiku, then Opus once when it still cannot tell (card_closeup). card_result gives the
electronics check's shape, so the page and the tutor use one result screen for both.
Used for     the gather step (RECOGNITION.md section 2, CHECKER.md); research/recognition/lab/server.py (the flow).
Where        reads the lesson and the parts catalogue through the lesson store (the database when set up, else files);
             research adds cards to the electronics card store, as any new lesson's parts do.
Run          ./pinpoint checker.gather blink photo1.jpg photo2.jpg [--model opus] [--no-research]
             ./pinpoint checker.gather 60065-1 photo.jpg --card 1     (a LEGO lesson's gather card, by its number)
"""
import json
import pathlib
import re
import sys
from typing import Literal

from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[2]
STORE = ROOT / "data/lessons/store"
PARTS = ROOT / "code/graph/parts/parts.json"
BREADBOARD_COLUMNS = {"full": 63, "half": 30, "mini": 17}

LOOK = """You check the parts a learner has laid out for an Arduino lesson. You get one or more photos of the same
parts (from different angles or of different parts of the table). List every object you can see, ONCE even when it
is in several photos, including objects that are not on the lesson's list and objects you cannot name exactly.

For each object:
- name: what it is, as specifically as you can tell from the photo ("Arduino Mega 2560", "half-size breadboard",
  "red 5 mm LED", "resistor", "relay module", "SG90 servo"). Never leave an object out because it is unusual.
- lesson_part: the lesson part type it IS (same kind of part; a different value or colour still counts, e.g. a
  330 ohm resistor is `resistor`), or "none". A different board model is "none" (an Arduino Mega is not
  `arduino-uno`). Do not force an object into a lesson part.
- value: what tells it apart from others of its kind, read off the part: a resistor's ohms from its bands
  ("220", "10k"), a capacitor's value, an LED's colour, a board's printed model, a breadboard's size
  ("full", "half" or "mini"), a module's chip or markings. Empty when there is nothing to read.
- count: how many of exactly this object (same kind and value).
- photos: the photo numbers it is in.
- might_replace: when the object is NOT a lesson part but could perhaps do the job of one (another board for
  `arduino-uno`, e.g. a Seeeduino, a Nano or an ESP32; a tactile switch for a push button), that lesson part
  type, else "". replace_note: one line on why (e.g. "Uno-compatible clone"). A bare microcontroller chip, a
  shield or a module is not a board.
- unsure: empty when you are sure; otherwise what you cannot tell and what photo would settle it ("the bands are
  too small to read: a close-up of the two resistors").
Wires: count jumper wires as one entry per colour, or "about N" when tangled; their colour and length never
matter."""


class Seen(BaseModel):
    name: str
    lesson_part: str
    value: str = ""
    count: int = 1
    photos: list[int] = Field(default_factory=list)
    might_replace: str = ""
    replace_note: str = ""
    unsure: str = ""


class Looked(BaseModel):
    objects: list[Seen]


# ---- the lesson --------------------------------------------------------------------------------------------------
def lesson(lesson_id):
    """The lesson record, with the assembled parts list (type, count, instances per part), and its physical graph
    (the part instances): from the database when it is set up, through the lesson store."""
    from graph import lesson_store
    _, graphs = lesson_store._load(lesson_id)
    rec = dict(graphs["lesson"])
    rec["parts_list"] = lesson_store.assemble(lesson_id)["parts_list"]
    return rec, graphs.get("physical") or {"nodes": [], "edges": []}


def needs(rec, phys):
    """What the lesson needs: one row per part type, with the values its instances carry."""
    props = {n["id"]: n.get("props") or {} for n in phys["nodes"]}
    out = []
    for p in rec["parts_list"]:
        vals = [props.get(i, {}).get("value") or props.get(i, {}).get("colour") for i in p["instances"]]
        out.append({"type": p["type"], "name": p["name"], "count": p["count"], "instances": p["instances"],
                    "values": vals})
    return out


def columns_used(phys):
    cols = [int(m.group(1)) for e in phys["edges"] for port in (e.get("u_port"), e.get("v_port"))
            if port and (m := re.match(r"(\d+)[tb]\.", str(port)))]
    return max(cols, default=0)


# ---- 1 look -------------------------------------------------------------------------------------------------------
def look(photos, rec, model="opus"):
    from graph.extract import _image_block, claude_json
    content = []
    for i, p in enumerate(photos, 1):
        data = pathlib.Path(p).read_bytes()
        mt = "image/png" if str(p).lower().endswith(".png") else "image/jpeg"
        content += [{"type": "text", "text": f"Photo {i}:"}, _image_block(data, mt)]
    parts = "\n".join(f"- {p['type']}: {p['name']} x{p['count']}" for p in rec["parts_list"])
    content.append({"type": "text", "text": f"The lesson is \"{rec['name']}\". Its parts list:\n{parts}\n"
                                            "List every object in the photos."})
    out, stats = claude_json(LOOK, content, Looked, model=model, effort="medium", timeout=600)
    return out["objects"], stats


# ---- 2 match ------------------------------------------------------------------------------------------------------
def catalogue():
    p = json.loads(PARTS.read_text())
    return p.get("parts", p)


HEDGES = re.compile(r"\([^)]*\)|\b(?:clone|compatible|style|type|based|likely|possibly|probably|similar|or)\b|"
                    r"\b(?:blue|black|red|green|white|small|large)\b|-(?=\s)", re.I)


def core_name(name):
    """The name without hedges and looks: 'Arduino Nano clone (mini-USB)' -> 'Arduino Nano'."""
    return re.sub(r"\s+", " ", HEDGES.sub(" ", name)).strip(" ,-")


def match(seen, lesson_types, store):
    """Catalogue type for an object: the lesson part Claude named, else a search of the catalogue by name and value."""
    if seen["lesson_part"] in lesson_types:
        return seen["lesson_part"], "lesson part"
    from graph.parts.arduino import tutorial
    core = core_name(seen["name"])
    for q in dict.fromkeys([seen["name"], f"{seen['name']} {seen['value']}".strip(), core]):  # never the value alone
        if q:
            card_id, _ = tutorial.match(q, store)
            if card_id and card_id != "skip":
                return card_id, "catalogue"
    # a looser match: the top search hit, only when it shares a model-like word (letters and digits: esp32, sg90)
    models = {w for w in re.findall(r"[a-z0-9]+", f"{seen['name']} {seen['value']}".lower())
              if re.search(r"\d", w) and re.search(r"[a-z]", w)}
    for h in store.search(seen["name"])[:1]:
        if models & set(re.findall(r"[a-z0-9]+", h.id)):
            return h.id, "catalogue (model name)"
    return None, "not in the catalogue"


# ---- 4 substitute -------------------------------------------------------------------------------------------------
def _ohms(text):
    m = re.search(r"([\d.]+)\s*([kKmM]?)\s*(?:ohm|Ω|r\b)?", str(text or ""))
    if not m:
        return None
    return round(float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)])


def _farads(text):
    """A capacitor's value in farads: "0.1uF", "100nF", "22 pF", "2200µF 16V", or the 3-digit code "104" (10 x 10^4
    pF = 100 nF); None if there is none."""
    t = str(text or "").replace("µ", "u").replace("μ", "u")
    m = re.search(r"([\d.]+)\s*([pnum])\s*f", t, re.I)
    if m:
        return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3}[m.group(2).lower()]
    m = re.fullmatch(r"\s*(\d)(\d)(\d)\s*", t)
    if m:
        return int(m.group(1) + m.group(2)) * 10 ** int(m.group(3)) * 1e-12
    return None


def _say_farads(f):
    for unit, k in (("µF", 1e-6), ("nF", 1e-9), ("pF", 1e-12)):
        if f >= k:
            return f"{f / k:g} {unit}"
    return f"{f:g} F"


def capacitor_ok(want, have):
    """A capacitor's value against the lesson's: within 20% (they are made to wide tolerances)."""
    w, h = _farads(want), _farads(have)
    if w is None:
        return True, ""
    if h is None:
        return None, "its value could not be read: a close-up of the printing on it will tell (104 means 100 nF)"
    if abs(h - w) / w <= 0.20:
        return True, f"{_say_farads(h)} is the lesson's {_say_farads(w)}"
    return False, f"this is {_say_farads(h)}; the lesson needs {_say_farads(w)}, and the circuit would not work the same"


def value_match(kind, want, have):
    """Does a value read off a part match the lesson's (resistors within 10%, capacitors within 20%, else the text)?"""
    if not want or not have:
        return False
    if kind == "resistor":
        w, h = _ohms(want), _ohms(have)
        return bool(w and h and abs(h - w) / w <= 0.10)
    if kind.startswith("capacitor"):
        w, h = _farads(want), _farads(have)
        return bool(w and h and abs(h - w) / w <= 0.20)
    return str(want).lower() in str(have).lower()


def resistor_ok(rec, cat, inst, want, have, board=None):
    """A resistor of another value: in series with an LED (the lesson's substitutions say so: value_ohms), any value
    keeping its current 5-20 mA (at the voltage of the board in use: the lesson's, or the one standing in for it);
    any other resistor (a timer, a divider, a pull-up) within 10% of the lesson's value."""
    sub = (rec.get("substitutions") or {}).get("parts", {}).get(inst, {})
    w, h = _ohms(want), _ohms(have)
    if h is None:
        return None, "its value could not be read: a close-up of its colour bands will tell"
    led = isinstance(sub.get("value_ohms"), list) or (sub.get("value") in ("by-role", "by role")
                                                       and "LED" in sub.get("why", "") and "value_ohms" not in sub)
    if led:
        board = cat.get(board or rec.get("board"), {})
        v = ((board.get("metadata") or {}).get("specs") or {}).get("logic_v") or 5.0
        vf = (cat.get("led", {}).get("electrical") or {}).get("forward_v") or 2.0
        lo, hi = (v - vf) / 0.020, (v - vf) / 0.005
        if lo <= h <= hi:
            return True, f"{h} Ω keeps the LED between 5 and 20 mA ({lo:.0f}-{hi:.0f} Ω is fine)"
        return False, (f"{h} Ω is too small: the LED would take more than 20 mA" if h < lo else
                       f"{h} Ω is too big: the LED would be very dim")
    if w and abs(h - w) / w <= 0.10:
        return True, f"{h} Ω is within 10% of {w} Ω"
    return False, f"this circuit needs about {w} Ω; {h} Ω would change how it works"


def spec_of(card):
    return (card.get("metadata") or {}).get("specs") or {}


def board_ok(rec, cat, have_type):
    """Another board: every pin the sketch uses must exist on it and do what the code needs. Returns (ok, why,
    moves {old pin: new pin})."""
    card = cat.get(have_type) or {}
    ports = {p["id"]: p for p in card.get("ports", []) if p.get("can")}
    if not ports:
        return None, f"the catalogue does not yet say what {have_type}'s pins can do", {}
    want = cat.get(rec.get("board"), {})
    v_have, v_want = spec_of(card).get("logic_v"), spec_of(want).get("logic_v")
    from graph.arduino import pins
    moves, used = {}, set()
    for key, info in (rec.get("substitutions") or {}).get("pins", {}).items():
        pin, need = key.split(":", 1)[1], info.get("needs", [])
        # the same pin under this board's name for it (13, D13, GPIO13)
        same = next((q for q in (pin, f"D{pin}", f"GPIO{pin}") if q in ports), None)
        p = ports.get(same)
        if p and all(n in p["can"] for n in need) and not p.get("reserved"):
            used.add(same)
            if same != pin:
                moves[pin] = same
            continue
        ok, _ = pins.stand_ins(card, pin, need, used)
        if not ok:
            return False, f"no pin on it can do what pin {pin} does ({', '.join(need)})", {}
        moves[pin] = ok[0]
        used.add(ok[0])
    renamed = all(re.sub(r"^(D|GPIO)", "", b) == a for a, b in moves.items())
    why = ["the same pins, so the sketch does not change" if not moves else
           "the same pin numbers (" + ", ".join(f"{a} is {b}" for a, b in moves.items()) + " on this board)"
           if renamed else
           "move " + ", ".join(f"pin {a} → {b}" for a, b in moves.items()) + " (the sketch is rewritten to match)"]
    ok = True
    if v_have and v_want and v_have != v_want:
        # the lesson's parts that need more than this board gives (their card's minimum supply)
        hungry = sorted({p["name"] for p in rec["parts_list"] if not is_board(cat, p["type"])
                         and (spec_of(cat.get(p["type"]) or {}).get("supply_v_min") or 0) > v_have})
        ok = not hungry
        why.append(f"it works at {v_have} V, but {', '.join(hungry)} need more" if hungry else
                   f"it works at {v_have} V (the lesson's board at {v_want} V); the lesson's parts are fine at that")
    if spec_of(card).get("chip") != spec_of(want).get("chip"):
        why.append("choose this board in the Arduino IDE when uploading")
    return ok, "; ".join(why), moves


def rails_used(phys):
    return any(re.match(r"[tb][pn]\.", str(port)) for e in phys["edges"] for port in (e.get("u_port"), e.get("v_port")))


def breadboard_ok(phys, value):
    size = next((k for k in BREADBOARD_COLUMNS if k in str(value).lower()), None)
    need = columns_used(phys)
    if not size:
        return None, "its size could not be told: full (63 columns), half (30) or mini (17)?"
    if size == "mini" and rails_used(phys):
        return False, "the lesson uses the power rails, which a mini board does not have"
    if BREADBOARD_COLUMNS[size] >= need:
        return True, f"the lesson uses columns up to {need}; a {size} board has {BREADBOARD_COLUMNS[size]}"
    return False, f"the lesson uses columns up to {need}; a {size} board has only {BREADBOARD_COLUMNS[size]}"


BOARDS = {"board", "microcontroller-board"}  # cards from research use the longer name (seeeduino-lotus)


def is_board(cat, t):
    c = cat.get(t) or {}
    return c.get("category") in BOARDS or str(t).startswith(("arduino-", "esp32", "pi-pico"))


# ---- 3 compare + 4 substitute + 5 research -----------------------------------------------------------------------
def check(lesson_id, photos, model="opus", research=True, seen=None):
    """The whole parts check. `seen` skips the photo call (tests and re-runs)."""
    from graph.parts import mcp_server
    rec, phys = lesson(lesson_id)
    cat = catalogue()
    store = mcp_server._store()
    stats = {}
    if seen is None:
        seen, stats = look(photos, rec, model)
    rows = needs(rec, phys)
    types = {r["type"] for r in rows}
    objs = []
    for s in seen:
        t, how = match(s, types, store)
        # research only what could matter for this lesson: an unknown object that might stand in for a lesson part
        if t is None and research and s.get("might_replace") in types:
            found = mcp_server.lookup(f"{s['name']} {s['value']}".strip(), store=store)
            if found.get("found"):
                t, how = found["type"], f"researched: {found.get('source') or found['from']}"
        objs.append({**s, "type": t, "matched_by": how, "left": s["count"]})

    report, board_in_use = [], None
    rows.sort(key=lambda r: not is_board(cat, r["type"]))  # boards first: other checks depend on the board in use
    for r in rows:
        line = {"part": r["name"], "type": r["type"], "need": r["count"], "have": [], "use_instead": [], "status": ""}
        left = r["count"]
        # same type first, the ones whose value matches this row before the rest, and the ones that match another
        # row of the same type (a lesson needing a 10k and a 220) last; values checked per instance
        others = [x["values"][0] for x in rows if x is not r and x["type"] == r["type"] and x["values"]]
        mine = r["values"][0] if r["values"] else None
        order = sorted(objs, key=lambda o: (0 if value_match(r["type"], mine, o["value"]) else
                                            2 if any(value_match(r["type"], v, o["value"]) for v in others) else 1))
        for o in order:
            if left == 0 or o["type"] != r["type"] or o["left"] == 0:
                continue
            take = min(left, o["left"])
            ok, why = True, ""
            if r["type"] == "resistor":
                ok, why = resistor_ok(rec, cat, r["instances"][0], r["values"][0], o["value"], board_in_use)
            elif r["type"] == "breadboard":
                ok, why = breadboard_ok(phys, o["value"])
            elif r["type"].startswith("capacitor") or (cat.get(r["type"]) or {}).get("category") == "capacitor":
                ok, why = capacitor_ok(r["values"][0], o["value"])
            elif r["values"][0] and o["value"] and str(r["values"][0]).lower() not in o["value"].lower():
                free = (rec.get("substitutions") or {}).get("parts", {}).get(r["instances"][0], {})
                if "colour" in free.get("free", []):
                    why = f"the lesson's is {r['values'][0]}; {free.get('why', 'any colour works')}"
            if ok is False and (o.get("unsure") or re.search(r"possibl|probabl|likely|\?", o["value"] or "", re.I)):
                ok, why = None, f"read as {o['value']}, but not for sure: {why}; a close-up will tell"
            if ok is False:
                line["use_instead"].append({"object": o["name"], "value": o["value"], "ok": False, "why": why})
                continue
            o["left"] -= take
            left -= take
            line["have"].append({"object": o["name"], "value": o["value"], "count": take, "ok": ok, "why": why})
        # a missing board: another board may stand in
        if left and is_board(cat, r["type"]):
            for o in objs:
                if o["left"] and o["type"] != r["type"] and (o["type"] and is_board(cat, o["type"])
                                                             or o.get("might_replace") == r["type"]):
                    # refused only when the catalogue knows it is not a board (a type from the wider store has no
                    # card here, e.g. seeeduino-lotus: offered to check, like an unknown clone)
                    if o["type"] in cat and not is_board(cat, o["type"]):
                        ok, why, moves = False, (f"it is a {cat[o['type']].get('category') or 'part'}, "
                                                 "not a board: on its own it cannot run the sketch"), {}
                    elif o["type"] in cat:
                        ok, why, moves = board_ok(rec, cat, o["type"])
                    else:
                        ok, why, moves = None, (o.get("replace_note") or "may do the job") + \
                            "; not in the catalogue, so its pins could not be checked", {}
                    line["use_instead"].append({"object": o["name"], "type": o["type"], "ok": ok, "why": why,
                                                "pin_moves": moves})
                    if ok is not False:
                        o["left"] -= 1
                        left -= 1
                        board_in_use = o["type"]
                        break
        # another object Claude thinks might do the job (not a board): offered, to be checked
        if left and not is_board(cat, r["type"]):
            for o in objs:
                if o["left"] and o.get("might_replace") == r["type"] and o["type"] != r["type"]:
                    line["use_instead"].append({"object": o["name"], "type": o["type"], "ok": None,
                                                "why": o.get("replace_note") or "may do the same job"})
                    o["left"] -= 1
                    left -= 1
                    if not left:
                        break
        good = sum(h["count"] for h in line["have"]) + sum(1 for u in line["use_instead"] if u["ok"] is not False)
        unsure = any(h["ok"] is None for h in line["have"]) or any(u["ok"] is None for u in line["use_instead"])
        line["status"] = ("check" if not left and unsure else
                          "have" if not left and not line["use_instead"] else
                          "use instead" if not left else
                          "missing" if good == 0 else f"missing {left}")
        report.append(line)
    extra = [{"object": o["name"], "value": o["value"], "count": o["left"], "type": o["type"],
              "matched_by": o["matched_by"]} for o in objs if o["left"]]
    unsure = [f"{o['name']}: {o['unsure']}" for o in objs if o.get("unsure")]
    return {"lesson": lesson_id, "photos": [str(p) for p in photos], "parts": report, "not_needed": extra,
            "retake": unsure, "seen": objs, "look": stats}


def text(res):
    mark = {"have": "✓", "use instead": "↔", "use another colour": "↔", "check": "?", "missing": "✗", "skipped": "–"}
    out = [f"Parts check for {res['lesson']}:"]
    for r in res["parts"]:
        out.append(f"{mark.get(r['status'], '✗')} {r['part']} x{r['need']}: {r['status']}")
        for h in r["have"]:
            out.append(f"     {'have' if h.get('ok', True) else 'have? check'} {h['count']} {h['object']}" + (f" ({h['value']})" if h.get("value") else "")
                       + (f": {h['why']}" if h.get("why") else ""))
        for u in r["use_instead"]:
            verdict = {True: "can use", None: "may use, check", False: "cannot use"}[u["ok"]]
            out.append(f"     {verdict} {u['object']}: {u['why']}")
    if res["not_needed"]:
        out.append("Also there, not needed: " + "; ".join(
            f"{x.get('count', '')} {x['object']}".strip() + (f" ({x['value']})" if x.get("value") else "") +
            ("" if x.get("type", True) else " [not in the catalogue]") for x in res["not_needed"]))
    if res.get("retake"):
        out.append("Could not tell: " + " | ".join(res["retake"]))
    if res["look"]:
        out.append(f"(look: {res['look'].get('seconds')} s, ${res['look'].get('cost_usd')})")
    return "\n".join(out)


# ---- LEGO: one gather card ---------------------------------------------------------------------------------------
CARD_FIRST = "claude-haiku-5-5"  # the first look and close-ups
CARD_SECOND = "claude-opus-5-5"  # once, for a close-up Haiku still cannot tell
MANY = 3  # this many identical pieces or more: seeing some is enough (a model cannot count ten 1x1 studs)

KINDS = [  # (words in the piece's name, what it is, said plainly): the first that fits
    (("minifig head", "minifigure head"), "minifigure head"), (("torso",), "minifigure torso"),
    (("hips and legs", "minifig legs", "legs"), "minifigure legs"), (("hair",), "minifigure hair"),
    (("helmet",), "helmet"), (("hat", "cap"), "hat"), (("tyre", "tire"), "tyre (rubber)"),
    (("wheel holder", "wheels holder", "wheel pins"), None), (("wheel",), "wheel"), (("steering",), "steering wheel"),
    (("windscreen", "windshield"), "windscreen"), (("door",), "door"), (("fence",), "fence"), (("panel",), "panel"),
    (("slope", "sloped"), "slope"), (("wedge",), "wedge"), (("dish",), "dish"), (("cone",), "cone"),
    (("tile",), "tile"), (("plate",), "plate"), (("brick",), "brick"), (("bar",), "bar"), (("axle",), "axle"),
    (("pin",), "pin"), (("hinge",), "hinge"), (("clip",), "clip"), (("antenna",), "antenna"), (("lever",), "lever"),
]


def piece_kind(name):
    """What a LEGO piece is, plainly, with its size: "plate 2x2", "round plate 1x1", "wheel", "minifigure head"."""
    n = name.lower()
    size = re.search(r"(\d+)\s*x\s*(\d+)(?:\s*x\s*(\d+(?:/\d+)?))?", n)
    kind = next((k for words, k in KINDS if any(re.search(rf"\b{re.escape(w)}", n) for w in words)), "")
    if kind is None:  # a plate with wheel pins: a plate, not a wheel
        kind = "plate" if "plate" in n else "brick"
    if not kind:
        return ""
    if "round" in n and kind in ("plate", "brick", "tile"):
        kind = "round " + kind
    if size and kind in ("plate", "brick", "tile", "slope", "wedge", "panel", "round plate", "round brick", "round tile"):
        kind += " " + "x".join(x for x in size.groups() if x)
    return kind


def card_items(card):
    """A gather card's pieces with keys p1, p2... (`card`: a gather card from tutor.live.steps)."""
    return [{"key": f"p{i}", "what": p["what"], "kind": piece_kind(p["what"]), "count": p["count"],
             "colour": p.get("colour"), "about": p.get("about") or ""} for i, p in enumerate(card.get("parts") or [], 1)]


CARD_LOOK = """The learner is about to build a LEGO model and has laid out the pieces for the next few steps. Here is the
list of pieces they should have (each: key, how many, its name, WHAT KIND OF PIECE it is and its size, a description):
{items}

Look at the photos and, for EACH piece on the list (by its key), first find the piece on the table that could be it,
then check it is that KIND of piece and that size (a 2x2 plate, not a 2x3 plate or a 2x2 brick; a wheel, not a tyre;
a minifigure head, not a 1x1 round brick), then say:
- "there": it is that piece, in the right colour. `seen`: how many you can see.
- "other_colour": it is that piece (same kind and size) in another colour. `colour_seen`: which.
- "wrong_piece": something similar is there but it is NOT that piece (another size, or another kind). `seen_as`: what
  it is, in a few words ("a 2x3 plate", "a 1x1 round brick").
- "unsure": something that could be it, but you cannot tell (too small, blurry, hidden, or two list items look alike).
  `why`: what you cannot tell. `ask`: one short, friendly question asking for the close-up that would settle it ("I can
  see a grey plate, but I can't count its studs. Can you hold it up close to the camera?").
- "not_there": nothing like it at all.
Count studs when they show; a plate is thin, a brick three times as tall, a tile has no studs on top. A minifigure part
with another face, print, hair or accessory counts as "there". Each piece in the photos can be only one item on the
list. Do not guess: when you cannot tell, say "unsure".
Answer ONLY with JSON: {{"pieces": [{{"key": "p1", "status": "there", "seen": 1, "colour_seen": "", "seen_as": "", "why": "", "ask": ""}}],
"extra": ["short name of any piece on the table that is not on the list"]}}"""


def _card_list(its):
    return "\n".join(f'- {x["key"]}: {x["count"]}x {x["what"]}' + (f' [kind: {x["kind"]}]' if x.get("kind") else "")
                     + (f' ({x["about"]})' if x["about"] else "") for x in its)


def _card_answer(text):
    i, j = text.find("{"), text.rfind("}")
    try:
        d = json.loads(text[i:j + 1])
    except ValueError:
        return [], []
    pieces = [p for p in d.get("pieces") or [] if isinstance(p, dict) and p.get("key")]
    return pieces, [str(x) for x in d.get("extra") or [] if x][:8]


def card_look(photos, its, model=CARD_FIRST, effort="low", small=True):
    """One look at the photos with the card's list. Returns ({key: verdict}, extra pieces, stats).
    small: the photos at 768 px, JPEG 35 (the first look, CHECKER.md §3.7); close-ups go at full size."""
    from checker import gather_vlm as vlm
    images = [vlm.shrink(p) if small else (pathlib.Path(p).read_bytes(), vlm.media_type(p)) for p in photos]
    out, stats, _ = vlm.ask(model, images, CARD_LOOK.format(items=_card_list(its)), max_tokens=4000, effort=effort)
    pieces, extra = _card_answer(out)
    known = {x["key"] for x in its}
    blank = {"seen": 0, "colour_seen": "", "seen_as": "", "why": "", "ask": "", "by": model}
    got = {p["key"]: {**blank, "status": p.get("status") or "unsure",
                      "seen": int(p.get("seen") or 0) if str(p.get("seen") or 0).isdigit() else 0,
                      **{k: p.get(k) or "" for k in ("colour_seen", "seen_as", "why", "ask")}}
           for p in pieces if p["key"] in known}
    for x in its:  # a piece the model left out was not seen
        got.setdefault(x["key"], {**blank, "status": "not_there"})
    return got, extra, {**stats, "raw": out[:3000]}


def card_closeup(photo, its, state_verdicts):
    """A close-up for one or more open pieces: Haiku first; the pieces it still cannot tell go to Opus once.
    Returns (new verdicts for those keys, steps for the cost log)."""
    got, _, st = card_look([photo], its, CARD_FIRST, small=False)
    steps = [{"what": "close-up", **{k: st.get(k) for k in ("model", "seconds", "cost_usd")}}]
    still = [x for x in its if got[x["key"]]["status"] == "unsure"
             and not any(v.get("by") == CARD_SECOND for k, v in state_verdicts.items() if k == x["key"])]
    if still:
        more, _, st2 = card_look([photo], still, CARD_SECOND, effort="medium", small=False)
        got.update(more)
        steps.append({"what": "close-up, second look", **{k: st2.get(k) for k in ("model", "seconds", "cost_usd")}})
    for k in got:
        got[k]["closeup"] = True
    return got, steps


def _short(what):
    return what if len(what) < 40 else what[:38].rsplit(" ", 1)[0] + "…"


def card_result(its, verdicts, dismissed=(), extra=()):
    """The verdicts in the electronics check's shape: {parts: [...], asks: [...], not_needed: [...]}."""
    parts, asks = [], []
    for x in its:
        v = verdicts.get(x["key"]) or {"status": "not_there", "seen": 0}
        st, need, seen = v["status"], x["count"], v.get("seen") or 0
        name = _short(x["what"])
        row = {"type": x["key"], "part": x["what"], "need": need, "have": [], "use_instead": []}
        if st == "there" and (seen >= need or (need >= MANY and seen >= 1) or seen == 0):
            row["status"] = "have"
            note = "" if seen >= need or seen == 0 else f"I can see {seen}; make sure you have {need}"
            row["have"] = [{"object": x["what"], "count": need, "why": note}]
        elif st == "there":  # fewer than needed of a piece that is easy to count
            row["status"] = "check"
            row["have"] = [{"object": x["what"], "count": seen, "why": f"I can see {seen} of the {need}"}]
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "find", "message": f"I can see {seen} of the {need} {name}. "
                             "Can you find the rest and show me?"})
        elif st == "other_colour":
            row["status"] = "use another colour"
            c = v.get("colour_seen") or "another colour"
            row["use_instead"] = [{"object": f"{c} {x['what']}".strip(), "ok": True,
                                   "why": "only the colour is different, so the build still works"}]
        elif st == "unsure":
            row["status"] = "check"
            row["have"] = [{"object": x["what"], "count": seen, "why": v.get("why") or "needs a better look"}]
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "closeup", "message": v.get("ask") or
                             f"I'm not sure about the {name}. Can you hold it up close to the camera?"})
        elif st == "wrong_piece":  # something like it, but not it: say what it is, and what is needed
            row["status"] = "skipped" if x["key"] in dismissed else "missing"
            what_it_is = v.get("seen_as") or "a different piece"
            row["use_instead"] = [{"object": what_it_is, "ok": False,
                                   "why": f"that is {what_it_is}, not a {x.get('kind') or name}"}]
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "find", "message": f"That looks like {what_it_is}, not the "
                             f"{x.get('kind') or name} I need ({name}). Can you find the right one and show me?"})
        else:
            row["status"] = "skipped" if x["key"] in dismissed else "missing"
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "find", "message": f"I can't see the {name}. "
                             "If you have it, show it to me."})
        parts.append(row)
    return {"parts": parts, "asks": asks[:4], "not_needed": [{"object": e} for e in extra]}


def check_card(lesson_id, card_no, photos):
    """The whole first look for one LEGO gather card (the command line; the app goes through the server's flow)."""
    from tutor import live
    steps = live.steps(lesson_id)["steps"]
    card = steps[int(card_no) - 1] if 0 < int(card_no) <= len(steps) else None
    if not card or card["kind"] != "gather":
        raise ValueError(f"card {card_no} is not a gather card")
    its = card_items(card)
    verdicts, extra, stats = card_look(photos, its)
    return {"lesson": f"{lesson_id}, card {card_no}", **card_result(its, verdicts, extra=extra), "look": stats}


def main(argv=None):
    a = list(argv or sys.argv[1:])
    model = a.pop(a.index("--model") + 1) if "--model" in a else "opus"
    if "--model" in a:
        a.remove("--model")
    research = "--no-research" not in a
    a = [x for x in a if x != "--no-research"]
    card = a.pop(a.index("--card") + 1) if "--card" in a else None
    a = [x for x in a if x != "--card"]
    res = check_card(a[0], card, a[1:]) if card else check(a[0], a[1:], model=model, research=research)
    out = ROOT / "data/parts_checks"
    out.mkdir(parents=True, exist_ok=True)
    name = f"{a[0]}-{pathlib.Path(a[1]).stem}.json"
    (out / name).write_text(json.dumps(res, indent=1, default=str))
    print(text(res))
    print(f"saved {out / name}")


if __name__ == "__main__":
    main()
