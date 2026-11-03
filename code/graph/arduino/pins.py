"""Board pins: what each one can do, and where the sketch uses it.

What it is   per board pin: what it can do (digital, analog, pwm, interrupt, i2c, spi, uart), its builtin name
             (LED_BUILTIN), why a lesson should not use it (pins 0 and 1 on an Uno), the pins that are one and the
             same (every GND), and which pins can stand in for which (stand_ins); from CircuitQuest's board cards
             and the boards' documented pinouts. And the sketch's links to the circuit (links): every place the code
             names a board pin (LED_BUILTIN, a number, a constant, analogRead(0) as A0), the port it means and what
             the code needs from it; rewrite edits the sketch at exactly those places when a part moves pin
             (DATA_STRUCTURE.md §3.7).
Used for     the substitutions a lesson allows, the check that every pin the sketch uses is wired (or is the board's
             own LED), and the tutor's answers about pins.
Where        arduino/graphs.py (links, stand_ins), parts/part_catalogue.py (annotate, cq_card).
"""
import json
import pathlib
import re

CQ_PARTS = pathlib.Path.home() / "Desktop" / "CirquitQuest" / "library" / "parts"

# Documented pinouts: docs.arduino.cc (Uno Rev3, Nano, Mega 2560 Rev3, Leonardo hardware pages)
FACTS = {
    "arduino-uno": {"pwm": "3 5 6 9 10 11", "interrupt": "2 3", "uart": {"0": "RX", "1": "TX"}, "upload_uart": True,
                    "analog_digital": "A0 A1 A2 A3 A4 A5"},
    "arduino-nano": {"pwm": "3 5 6 9 10 11", "interrupt": "2 3", "uart": {"0": "RX", "1": "TX"}, "upload_uart": True,
                     "analog_digital": "A0 A1 A2 A3 A4 A5"},  # A6, A7 are analog inputs only
    "arduino-mega": {"pwm": "2 3 4 5 6 7 8 9 10 11 12 13 44 45 46", "interrupt": "2 3 18 19 20 21",
                     "uart": {"0": "RX", "1": "TX", "19": "RX1", "18": "TX1", "17": "RX2", "16": "TX2",
                              "15": "RX3", "14": "TX3"}, "upload_uart": True,
                     "analog_digital": " ".join(f"A{i}" for i in range(16))},
    "arduino-leonardo": {"pwm": "3 5 6 9 10 11 13", "interrupt": "0 1 2 3 7", "uart": {"0": "RX", "1": "TX"},
                         "upload_uart": False,  # native USB: pins 0 and 1 are free (Serial1)
                         "analog_digital": "A0 A1 A2 A3 A4 A5"},
    # no CircuitQuest card: only what Arduino's store page states (14 digital, 6 analog; PWM pins not named)
    "arduino-uno-wifi-rev2": {"digital": [str(i) for i in range(14)], "analog": [f"A{i}" for i in range(6)],
                              "uart": {"0": "RX", "1": "TX"}, "upload_uart": False,
                              "source": "store.arduino.cc tech specs"},
}


def cq_card(part_id):
    f = CQ_PARTS / f"{part_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def annotate(card, cq):
    """The board card's ports with `can`, `builtin`, `reserved` and `same_as` (in place). Returns how many ports got
    a capability, or 0 when CircuitQuest describes no pins for this part."""
    facts = FACTS.get(card["part_type_id"], {})
    if (not cq or not cq.get("pin_domains")) and facts.get("digital"):  # a board known only from its documented pinout
        cq = {"pin_domains": {"digital": facts["digital"], "analog": facts.get("analog", [])}}
    if not cq or not cq.get("pin_domains"):
        return 0
    can = {}
    add = lambda pin, c: can.setdefault(pin, []).append(c) if c not in can.get(pin, []) else None  # noqa: E731
    for pin in cq["pin_domains"].get("digital", []):
        add(pin, "digital")
    for pin in cq["pin_domains"].get("analog", []):
        add(pin, "analog")
    for pin in facts.get("analog_digital", "").split():
        add(pin, "digital")
    for pin in facts.get("pwm", "").split():
        add(pin, "pwm")
    for pin in facts.get("interrupt", "").split():
        add(pin, "interrupt")
    for pin, role in facts.get("uart", {}).items():
        add(pin, "digital")
        add(pin, f"uart:{role}")
    for pin, p in (cq.get("protocol_pins") or {}).items():
        add(pin, f"{p['protocol'].lower()}:{p['role']}")
    prefixes = (cq.get("pin_aliases") or {}).get("prefixes", []) if (cq.get("pin_aliases") or {}).get("mode") == "prefix" else []
    n = 0
    for port in card.get("ports", []):
        pid = port["id"]
        for pre in prefixes:  # GND.1, GND.2 ... are one pin inside the board
            if pid.startswith(pre) and pid != pre and re.fullmatch(re.escape(pre) + r"(\.\d+)?", pid):
                port["same_as"] = pre
        if pid in can:
            port["can"] = can[pid]
            n += 1
        if cq.get("led_builtin") == pid:
            port["builtin"] = "LED_BUILTIN"
        if facts.get("upload_uart") and pid in ("0", "1"):
            port["reserved"] = "carries the USB upload and Serial"
    card.setdefault("pin_facts", {})
    card["pin_facts"] = {"source": facts.get("source") or ("CircuitQuest board card" + (" + documented pinout" if facts else "")),
                         "pwm_known": bool(facts.get("pwm"))}
    return n


def stand_ins(card, pin, needs, used):
    """Which pins of this board can stand in for `pin`, for code that needs `needs` from it. used: pins already taken
    by other parts. Returns ([pin], {pin: why not}) over every pin with a capability."""
    ports = {p["id"]: p for p in card.get("ports", []) if p.get("can")}
    known = {c for p in ports.values() for c in p["can"]}
    ok, why = [], {}
    for pid, p in ports.items():
        if pid == pin:
            continue
        missing = [n for n in needs if n not in p["can"]]
        unknown = [n for n in missing if n not in known]
        if unknown:
            why[pid] = f"the board's card does not say which pins can do {', '.join(unknown)}"
        elif missing:
            why[pid] = f"cannot do {', '.join(missing)}"
        elif p.get("reserved"):
            why[pid] = p["reserved"]
        elif pid in used:
            why[pid] = "already used by another part"
        else:
            ok.append(pid)
    return ok, why


# ---- where the sketch uses each pin (its links to the circuit), and rewriting it at those places ------
NEEDS = {"pinMode": ["digital"], "digitalWrite": ["digital"], "digitalRead": ["digital"], "analogRead": ["analog"],
         "analogWrite": ["digital", "pwm"], "tone": ["digital"], "noTone": ["digital"], "pulseIn": ["digital"],
         "attach": ["digital"], "digitalPinToInterrupt": ["interrupt"]}


PIN = r"(?:A\d{1,2}|\d{1,2})"


DECL = re.compile(r"\b(?:const\s+)?(?:int|byte|uint8_t|short|long|unsigned\s+int)\s+(\w+)\s*=\s*(" + PIN + r"|LED_BUILTIN)\s*;")


DEFINE = re.compile(r"^\s*#define\s+(\w+)\s+(" + PIN + r"|LED_BUILTIN)\b", re.M)


CALL = re.compile(r"\b(?:(\w+)[ \t]*\.[ \t]*)?(" + "|".join(NEEDS) + r")\s*\(\s*([^,()]+?)\s*[,)]")  # obj.fn on one line


COMMENT_PIN = re.compile(r"\bpin\s+(" + PIN + r")\b", re.I)


FIXED = {"Wire": ("i2c", "Wire (I2C) uses the board's SDA and SCL pins"),
         "Serial": ("uart", "Serial uses pins 0 and 1 (RX, TX)")}


def _comments(code):
    """[(start, end)] of every comment."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"//[^\n]*", code)]
    spans += [(m.start(), m.end()) for m in re.finditer(r"/\*.*?\*/", code, re.S)]
    return spans


def _in(spans, i):
    return any(a <= i < b for a, b in spans)


def _line(code, i):
    return code.count("\n", 0, i) + 1


def links(code, board_id, board_card):
    """[link] for a sketch on the board instance `board_id` (its card gives LED_BUILTIN)."""
    comments = _comments(code)
    builtin = next((p["id"] for p in board_card.get("ports", []) if p.get("builtin") == "LED_BUILTIN"
                    or "LED_BUILTIN" in (p.get("aliases") or [])), None)  # a card may give it as the pin's alias
    pins = {p["id"] for p in board_card.get("ports", [])}
    consts = {}  # name -> (value, start, end of the value)
    for rx in (DECL, DEFINE):
        for m in rx.finditer(code):
            if not _in(comments, m.start()):
                consts[m.group(1)] = (m.group(2), m.start(2), m.end(2))
    out, by_site = [], {}

    def site(value, start, end, via):
        pin = builtin if value == "LED_BUILTIN" else value
        if via.startswith("analogRead") and value.isdigit() and f"A{value}" in pins:
            pin = f"A{value}"  # analogRead(0) reads A0: a bare number there is the analog input's number
        if pin not in pins:
            return None
        key = (start, end)
        if key not in by_site:
            by_site[key] = {"kind": "code", "token": value, "start": start, "end": end, "line": _line(code, start),
                            "port": f"{board_id}:{pin}", "needs": [], "via": []}
            out.append(by_site[key])
            if pin == builtin:  # the board's own LED is on it: driving it needs no wiring
                by_site[key]["builtin_led"] = True
        by_site[key]["via"].append(via)
        return by_site[key]

    for m in CALL.finditer(code):
        if _in(comments, m.start()):
            continue
        obj, fn, arg = m.group(1), m.group(2), m.group(3).strip()
        if fn == "attach" and not obj:
            continue
        needs = NEEDS[fn]
        if re.fullmatch(PIN + r"|LED_BUILTIN", arg):
            link = site(arg, m.start(3), m.start(3) + len(arg), f"{fn}() line {_line(code, m.start())}")
        elif arg in consts:
            v, a, b = consts[arg]
            link = site(v, a, b, f"{fn}({arg}) line {_line(code, m.start())}")
        elif fn == "digitalPinToInterrupt" or re.fullmatch(r"\w+", arg) is None or arg not in consts:
            out.append({"kind": "unresolved", "token": arg, "start": m.start(3), "end": m.start(3) + len(arg),
                        "line": _line(code, m.start()), "port": None, "needs": needs,
                        "via": [f"{fn}({arg}) line {_line(code, m.start())}: the pin is computed, not named"]})
            continue
        if link:
            link["needs"] = sorted(set(link["needs"]) | set(needs))
    for name, (lib_need, why) in FIXED.items():
        m = re.search(r"\b" + name + r"\s*\.\s*begin\s*\(", code)
        if m and not _in(comments, m.start()):
            out.append({"kind": "fixed", "token": name, "start": m.start(), "end": m.start() + len(name),
                        "line": _line(code, m.start()), "port": None, "needs": [lib_need], "via": [why]})
    # comment mentions of a pin, on or just above a line that uses it ("// declare pin 9 to be an output:" over
    # pinMode(led, ...)): kept in step with the code. A header comment about the board is left alone
    used = {}  # port -> lines that use it
    for l in out:
        if l["kind"] == "code":
            for v in l["via"]:
                n = re.search(r"line (\d+)", v)
                used.setdefault(l["port"], set()).add(int(n.group(1)) if n else l["line"])
    for a, b in comments:
        for m in COMMENT_PIN.finditer(code, a, b):
            port, line = f"{board_id}:{m.group(1)}", _line(code, m.start(1))
            if line in used.get(port, set()) or line + 1 in used.get(port, set()):
                out.append({"kind": "comment", "token": m.group(1), "start": m.start(1), "end": m.end(1),
                            "line": _line(code, m.start(1)), "port": port, "needs": [], "via": ["comment"]})
    return sorted(out, key=lambda l: l["start"])


def rewrite(code, links, moves):
    """The sketch with each linked place moved (moves: {old port: new port}); LED_BUILTIN becomes the new pin's
    number. Edits run from the end, so earlier offsets stay right."""
    out = code
    for l in sorted(links, key=lambda l: -l["start"]):
        if l["kind"] in ("code", "comment") and l["port"] in moves:
            new = moves[l["port"]].split(":", 1)[1]
            out = out[:l["start"]] + new + out[l["end"]:]
    return out
