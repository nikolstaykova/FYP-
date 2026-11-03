"""Step 0, the parts check: from a few photos, what the learner has against what an Arduino lesson needs.

What it is   the learner uploads a few photos of their parts. 1 LOOK (Claude, all photos in one call): every object,
             counted once across photos, with the details that decide a substitute (resistor bands, board name,
             breadboard size, LED colour). 2 MATCH (code): each object to a catalogue part. 3 COMPARE (code): the
             lesson's parts list against what is there. 4 SUBSTITUTE (code): can what is there do the job, and
             what changes (pins moved, sketch lines rewritten). 5 RESEARCH: an object the catalogue does not know is
             looked up on the approved sites and carded (parts/mcp_server.lookup), then tried as a substitute.
Used for     the gather step before building; RECOGNITION.md section 2. The model choice is from the comparison there.
Where        reads the lesson store (data/lessons/store/<id>/lesson.json, assembled.json, physical.json) and the parts catalogue;
             research adds cards to the electronics card store, as any new lesson's parts do.
Run          ./pinpoint checker.gather blink photo1.jpg photo2.jpg [--model opus] [--no-research]
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
    """The lesson record, with the parts list from assembled.json (type, count, instances per part)."""
    rec = json.loads((STORE / lesson_id / "lesson.json").read_text())
    rec["parts_list"] = json.loads((STORE / lesson_id / "assembled.json").read_text())["parts_list"]
    phys = json.loads((STORE / lesson_id / "physical.json").read_text())
    return rec, phys


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


def resistor_ok(rec, cat, inst, want, have, board=None):
    """A resistor of another value: in series with an LED, any value keeping its current 5-20 mA (at the voltage of
    the board in use: the lesson's, or the one standing in for it); else within 10%."""
    sub = (rec.get("substitutions") or {}).get("parts", {}).get(inst, {})
    w, h = _ohms(want), _ohms(have)
    if h is None:
        return None, "its value could not be read: a close-up of its colour bands will tell"
    if sub.get("value") == "by-role" and "LED" in sub.get("why", ""):
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
        # same type first; values checked per instance
        for o in objs:
            if left == 0 or o["type"] != r["type"] or o["left"] == 0:
                continue
            take = min(left, o["left"])
            ok, why = True, ""
            if r["type"] == "resistor":
                ok, why = resistor_ok(rec, cat, r["instances"][0], r["values"][0], o["value"], board_in_use)
            elif r["type"] == "breadboard":
                ok, why = breadboard_ok(phys, o["value"])
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
    mark = {"have": "✓", "use instead": "↔", "check": "?", "missing": "✗"}
    out = [f"Parts check for {res['lesson']}:"]
    for r in res["parts"]:
        out.append(f"{mark.get(r['status'], '✗')} {r['part']} x{r['need']}: {r['status']}")
        for h in r["have"]:
            out.append(f"     {'have' if h['ok'] else 'have? check'} {h['count']} {h['object']}" + (f" ({h['value']})" if h["value"] else "")
                       + (f": {h['why']}" if h["why"] else ""))
        for u in r["use_instead"]:
            verdict = {True: "can use", None: "may use, check", False: "cannot use"}[u["ok"]]
            out.append(f"     {verdict} {u['object']}: {u['why']}")
    if res["not_needed"]:
        out.append("Also there, not needed: " + "; ".join(
            f"{x['count']} {x['object']}" + (f" ({x['value']})" if x["value"] else "") +
            ("" if x["type"] else " [not in the catalogue]") for x in res["not_needed"]))
    if res["retake"]:
        out.append("Could not tell: " + " | ".join(res["retake"]))
    if res["look"]:
        out.append(f"(look: {res['look'].get('seconds')} s, ${res['look'].get('cost_usd')})")
    return "\n".join(out)


def main(argv=None):
    a = list(argv or sys.argv[1:])
    model = a.pop(a.index("--model") + 1) if "--model" in a else "opus"
    if "--model" in a:
        a.remove("--model")
    research = "--no-research" not in a
    a = [x for x in a if x != "--no-research"]
    res = check(a[0], a[1:], model=model, research=research)
    out = ROOT / "data/parts_checks"
    out.mkdir(parents=True, exist_ok=True)
    name = f"{a[0]}-{pathlib.Path(a[1]).stem}.json"
    (out / name).write_text(json.dumps(res, indent=1, default=str))
    print(text(res))
    print(f"saved {out / name}")


if __name__ == "__main__":
    main()
