"""Where a sketch uses each board pin.

What it is   every place the code names a board pin: the port it means (LED_BUILTIN, a number, a constant,
             analogRead(0) as A0) and what the code needs from it (digital, pwm, analog); found once, when the
             lesson is built (DATA_STRUCTURE.md §3.7).
Used for     checking that every pin the sketch uses is wired (or is the board's built-in LED), and adapting the
             code when a part moves to another pin, by editing exactly these places.
Where        lesson_store.py (the upload step's program links).

  pinMode(LED_BUILTIN, OUTPUT)       -> uno:13, needs digital       (site: the token LED_BUILTIN)
  int led = 9;  analogWrite(led, b)  -> uno:9,  needs digital + pwm (site: the 9 in the declaration)
  analogRead(A0)                     -> uno:A0, needs analog        (site: the A0)
  analogRead(0)                      -> uno:A0 as well (a bare number there is the analog input's)
  // declare pin 9 to be an output   -> uno:9, a comment mention    (site: the 9; kept in step with the code)
A pin the code computes (an array, arithmetic, a function argument) cannot be pinned to one port: it is reported as
`unresolved` and a swap of it is refused rather than guessed. Pins the code uses through a library (Wire: I2C,
Serial: pins 0 and 1) are `fixed`: they cannot move.
"""
import re

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
