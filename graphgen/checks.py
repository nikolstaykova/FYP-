"""Checks run on Claude's graph before accepting it. Each problem is written so it can be sent
back to Claude for repair ("issue" text says what is wrong and where).

Electronics (circuit laws, on the logical view):
  E1 supply shorted   a net holds both a supply (5V, 3.3V, VIN) and GND
  E2 pin shorted      a board signal pin sits directly on a supply or GND net
  E3 part shorted     both legs of a two-legged part are on the same net
  E4 leg unconnected  a leg of a two-legged part touches nothing
  E5 floating input   a pin's only other connection is a switch contact, with no pull-up/pull-down
                      resistor (skipped when the code uses INPUT_PULLUP)
LEGO:
  L1 parts page       piece counts differ from the booklet's own parts page (when it has one)
  L2 unknown part     `lego-<number>` is not a real LEGO part number
  L3 separate pieces  the build falls apart into several unconnected groups
Both: the spec rules from validate.py (V2 unused part, V3 incompatible ports, V4 missing/over-used port).
v5 adds:
  E6 part count       the graph has FEWER of a part than the tutorial's list states (per value for resistors:
                      "2 x 220 ohm"); extra parts are allowed, the circuit text may add some
  E7 pin not wired    the tutorial's circuit section names a board pin ("digital pin 9", "analog in 0", A0,
                      GPIO17) and nothing is wired to it
  E8 wrong supply     a part's power pin is on a supply outside its rated range (a 3.3 V part on 5 V)
  E9 no LED resistor  an LED sits between a board pin and ground with no resistor in series
  E10 logic level     a 5 V board signal pin drives a 3.3 V part that is not 5 V tolerant
E8-E10 read the cards' electrical facts and skip what a card does not state.
  L5 stacking         (LEGO, from the cards' stud grids) a piece rests on a piece with no studs (a tile); a piece
                      rests on more pieces than it has stud cells underneath; two pieces rest on each other
"""
import collections
import re

from . import logical, validate
from .score import family, role

SUPPLY = {"5V", "3V3", "VIN"}
TWO_LEGGED = {"led", "resistor", "button", "buzzer"}


def _board_role(key, types):
    part, port = key.split(":", 1)
    return role("board", port) if family(types.get(part)) == "board" else None


def electronics(flat, catalogue, manual_text=""):
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    nets = logical.nets(flat, catalogue)
    net_of = {k: i for i, n in enumerate(nets) for k in n}
    pullup = "INPUT_PULLUP" in manual_text or "pull_up=True" in manual_text
    for net in nets:
        roles = {_board_role(k, types) for k in net} - {None}
        if "GND" in roles and roles & SUPPLY:
            issues.append(("E1", f"supply shorted to ground: {sorted(net)}"))
        signal = [k for k in net if _board_role(k, types) not in (None, "GND", *SUPPLY)]
        if signal and roles & ({"GND"} | SUPPLY):
            issues.append(("E2", f"board pin {signal} is wired straight to {sorted(roles & ({'GND'} | SUPPLY))} with nothing in between: {sorted(net)}"))
        others = [k for k in net if _board_role(k, types) is None]
        if signal and not pullup and others and all(family(types.get(k.split(':')[0])) == "button" for k in others):
            issues.append(("E5", f"pin {signal} connects only to a button contact {others}: it floats when the button is open "
                                 "(the pull-down/pull-up resistor must join this same pin net)"))
    for n in flat["nodes"]:
        fam = family(n["type"])
        if fam not in TWO_LEGGED:
            continue
        entry = catalogue.get(n["type"]) or {}
        legs = sorted({logical.canonical_port(entry, p["name"]) for p in entry.get("ports", [])})
        if len(legs) != 2:
            continue
        keys = [f"{n['id']}:{leg}" for leg in legs]
        if all(k in net_of for k in keys) and net_of[keys[0]] == net_of[keys[1]]:
            issues.append(("E3", f"{n['id']} ({n['type']}) has both legs on one net, so it is shorted out"))
        for k in keys:
            if k not in net_of:
                issues.append(("E4", f"leg {k} is not connected to anything"))
    return issues


def _components(flat):
    adj = collections.defaultdict(set)
    for e in flat["edges"]:
        if e["type"] in ("joined", "contact") and e["u"] != e["v"]:
            adj[e["u"]].add(e["v"])
            adj[e["v"]].add(e["u"])
    seen, groups = set(), 0
    for n in flat["nodes"]:
        if n["id"] in seen:
            continue
        groups += 1
        stack = [n["id"]]
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(adj[x] - seen)
    return groups


def booklet_inventory_page(page):
    """A parts page lists at least 5 Element IDs as text."""
    return sum(1 for t in page.get_text().split() if re.fullmatch(r"\d{6,7}", t)) >= 5


def booklet_inventory(pdf_bytes):
    """Element ID -> count from a booklet's own parts page(s), if it has any (text like '4x' then '300401')."""
    if not pdf_bytes:
        return {}
    import pymupdf
    inv = collections.Counter()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        if not booklet_inventory_page(page):
            continue
        tokens = page.get_text().split()
        for a, b in zip(tokens, tokens[1:]):
            m = re.fullmatch(r"(\d{1,3})x", a)
            if m and re.fullmatch(r"\d{6,7}", b):
                inv[b] += int(m.group(1))
    return dict(inv)


def lego(flat, part_nums, booklet_inv=None):
    issues = []
    if booklet_inv:
        built = collections.Counter()
        for n in flat["nodes"]:
            m = re.search(r"(\d{6,7})", f"{n['type']} {n.get('label') or ''}")
            if m:
                built[m.group(1)] += 1
        wrong = [(el, want, built.get(el, 0)) for el, want in booklet_inv.items() if built.get(el, 0) != want]
        extra = [el for el in built if el not in booklet_inv]
        if wrong or extra:
            issues.append(("L1", "piece counts differ from the booklet's parts page: "
                           + ", ".join(f"element {el}: page says {w}, graph has {b}" for el, w, b in wrong[:15])
                           + (f"; elements not on the page: {extra[:10]}" if extra else "")))
    for n in flat["nodes"]:
        m = re.match(r"^lego-([0-9a-z]+)$", n["type"].lower())
        if m and not re.fullmatch(r"\d{6,7}", m.group(1)) and m.group(1) not in part_nums:
            issues.append(("L2", f"{n['id']}: '{n['type']}' is not a real LEGO part number"))
    groups = _components(flat)
    if groups > 1:
        issues.append(("L3", f"the build is {groups} separate groups of pieces; connect them unless the booklet really builds separate models"))
    return issues


def run(flat, catalogue, domain, manual_text="", part_nums=frozenset(), booklet_inv=None):
    spec = [(r, m) for r, m in validate.validate(flat, catalogue)]
    if domain == "arduino":
        return spec + electronics(flat, catalogue, manual_text)
    return spec + lego(flat, part_nums, booklet_inv)


def repair_message(issues, limit=40):
    lines = [f"- [{rule}] {msg}" for rule, msg in issues[:limit]]
    more = f"\n- … and {len(issues) - limit} more" if len(issues) > limit else ""
    return ("Checking your graph found these problems:\n" + "\n".join(lines) + more +
            "\n\nReturn the COMPLETE corrected graph (same format). Fix every real problem; if one is not a real "
            "problem for this manual (e.g. the booklet truly builds separate models), keep that part and say why in notes.")


def ohms(text):
    """'220', '10k', '4k7', '4.7K ohm', '10 kΩ' -> ohms as a float, or None."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([kKmM])?(\d*)", str(text or ""))
    if not m:
        return None
    value = float(m.group(1) + ("." + m.group(3) if m.group(3) else ""))
    return value * {"k": 1e3, "m": 1e6}.get((m.group(2) or "").lower(), 1)


def parts_count(flat, listed):
    """E6. listed: [(card type, stated count, stated value or None)] from the tutorial's parts list (only items with
    a count). Flags parts the graph has FEWER of; compared per value for resistors when the list gives one."""
    issues = []
    nodes = [n for n in flat["nodes"]]
    by_family = collections.Counter(family(n["type"]) for n in nodes)
    want_family, want_value = collections.Counter(), collections.Counter()
    for card_type, count, value in listed:
        fam = family(card_type)
        if fam in ("wire", "breadboard"):
            continue
        if fam == "resistor" and value is not None:
            want_value[value] += count
        want_family[fam] += count
    for fam, q in sorted(want_family.items()):
        if by_family[fam] < q:
            issues.append(("E6", f"the tutorial's parts list has {q} x {fam}, the graph has only {by_family[fam]}"))
    have_value = collections.Counter(ohms((n.get("props") or {}).get("value")) for n in nodes if family(n["type"]) == "resistor")
    for value, q in sorted(want_value.items()):
        if have_value[value] < q and by_family["resistor"] >= want_family["resistor"]:
            issues.append(("E6", f"the tutorial lists {q} x {value:g} ohm resistor, the graph has {have_value[value]} of that value"))
    return issues


NUMBER = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10}
MENTION = {"resistor": r"resistors?", "led": r"leds?"}


def text_mentions(text, fam):
    """How many of a part family the text describes: 'a 220 ohm resistor' = 1, 'two 10K resistors' = 2,
    'resistors' with no count = 2 (an upper bound, so it never undercounts). The count is looked for in the five
    words before the part name, stopping at punctuation; pin numbers and values (220 ohm, 10K) are not counts."""
    total = 0
    for clause in re.split(r"[,.;:()]", text):
        words = clause.split()
        for i, w in enumerate(words):
            if not re.fullmatch(MENTION[fam], w, re.I):
                continue
            count = None
            for j in range(i - 1, max(-1, i - 6), -1):
                prev = words[j].lower()
                if prev in NUMBER:
                    count = NUMBER[prev]
                    break
                if prev.isdigit() and not (j > 0 and words[j - 1].lower() in ("pin", "pins", "input", "in")) \
                        and not (j + 1 < len(words) and re.fullmatch(r"(ohms?|Ω|k|v|volts?|mm|[munpµ]?f|w)", words[j + 1], re.I)):
                    count = int(prev)
                    break
            total += count if count else (2 if w.lower().endswith("s") else 1)
    return total


def parts_extra(flat, manual, listed_all):
    """E6 (extra): more resistors or LEDs than the tutorial has room for: the larger of what its parts list states
    (an item without a count is 1; a plural without a count, "resistors", sets no limit; every alternative of an
    "X or Y" item counts) and what its circuit text describes. Only for kinds of part the list names."""
    issues = []
    got = collections.Counter(family(n["type"]) for n in flat["nodes"])
    text = circuit_text(manual)
    for fam in MENTION:
        if any(q is None for card, q in listed_all if family(card) == fam):
            continue  # the list says "resistors" without a number: no upper limit
        in_list = sum(q for card, q in listed_all if family(card) == fam)
        if not in_list:
            continue  # the list does not name this kind of part (e.g. LEDs listed, their resistors not): no limit
        allowed = max(in_list, text_mentions(text, fam))
        if got[fam] > allowed:
            issues.append(("E6", f"the graph has {got[fam]} x {fam}, but the tutorial's parts list and circuit text "
                                 f"describe at most {allowed}: check each one against the tutorial and remove any it "
                                 f"does not have"))
    return issues


CIRCUIT_HEADING = re.compile(r"^#+\s*(circuit|wiring|connect|build(ing)? the circuit|hardware setup|schematic)[^\n]*$", re.I | re.M)


def circuit_text(manual):
    """The tutorial's circuit section(s) only: pins in the code or elsewhere are not all wired."""
    out = []
    for m in CIRCUIT_HEADING.finditer(manual):
        body = manual[m.end():]
        nxt = re.search(r"^#+\s", body, re.M)
        out.append(body[: nxt.start() if nxt else len(body)])
    return "\n".join(out)


def named_pins(text):
    """Board pins the circuit text names: {"digital": {'9'}, "analog": {'A0'}, "gpio": {'GPIO17'}}. A bare "pin 4"
    is not counted (it may be a pin of the part, e.g. a MIDI socket); pin 13 is skipped next to "built-in"."""
    pins = {"digital": set(), "analog": set(), "gpio": set()}
    for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)):
        if re.search(r"built-?in|on-?board", sentence, re.I):
            sentence = re.sub(r"\bpin\s*13\b", "", sentence, flags=re.I)
        for n in re.findall(r"\banalog\s+(?:input\s+|in\s+)?(?:pins?\s+)?(\d)\b|\bA([0-7])\b", sentence, re.I):
            pins["analog"].add(f"A{n[0] or n[1]}")
        for n in re.findall(r"\b(?:digital|i/o|arduino|board)\s+(?:i/o\s+)?pin\s+(\d{1,2})\b|\bpin\s+(\d{1,2})\s+(?:of|on)\s+the\s+(?:arduino|board)", sentence, re.I):
            pins["digital"].add(str(int(n[0] or n[1])))
        for n in re.findall(r"\bGPIO\s?(\d{1,2})\b", sentence, re.I):
            pins["gpio"].add(f"GPIO{int(n)}")
    return pins


def pins_wired(flat, manual):
    """E7: every digital/GPIO board pin the circuit section names is wired. Analog pins only when the text names one
    and no analog pin is wired at all (tutorials often name two analog inputs for the same sensor)."""
    boards = {n["id"] for n in flat["nodes"] if family(n["type"]) == "board"}
    if not boards:
        return []
    used = {role("board", e[side + "_port"]) for e in flat["edges"] for side in ("u", "v")
            if e[side] in boards and e.get(side + "_port")}
    named = named_pins(circuit_text(manual))
    missing = sorted((named["digital"] | named["gpio"]) - used)
    if named["analog"] and not any(u.startswith("A") and u[1:].isdigit() for u in used):
        missing.append(" or ".join(sorted(named["analog"])))
    return [("E7", f"the tutorial's circuit section names board pin {p}, but nothing is wired to it") for p in missing]


def electrical(flat, catalogue):
    """E8-E10, from the cards' electrical facts."""
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    facts = lambda pid: (catalogue.get(types.get(pid)) or {}).get("electrical") or {}
    nets = logical.nets(flat, catalogue)
    board_logic = {pid: facts(pid).get("logic_v") for pid in types if family(types[pid]) == "board"}
    for net in nets:
        supply = {_board_role(k, types) for k in net} & {"5V", "3V3"}
        volts = 5.0 if "5V" in supply else 3.3 if "3V3" in supply else None
        for k in net:
            pid, port = k.split(":", 1)
            el = facts(pid)
            if volts and port in el.get("power_pins", []):  # E8
                if el.get("supply_v_max") is not None and volts > el["supply_v_max"] + 0.05:
                    issues.append(("E8", f"{pid} ({types[pid]}) is rated up to {el['supply_v_max']} V but {port} is on {volts:g} V"))
                if el.get("supply_v_min") is not None and volts < el["supply_v_min"] - 0.05:
                    issues.append(("E8", f"{pid} ({types[pid]}) needs at least {el['supply_v_min']} V but {port} is on {volts:g} V"))
        signal_boards = [k.split(":", 1)[0] for k in net if _board_role(k, types) not in (None, "GND", *SUPPLY)]
        if any(board_logic.get(b) == 5 for b in signal_boards):  # E10
            for k in net:
                pid, port = k.split(":", 1)
                el = facts(pid)
                if family(types.get(pid)) != "board" and el.get("logic_v") == 3.3 and el.get("five_v_tolerant") is False \
                        and port not in el.get("power_pins", []):
                    issues.append(("E10", f"5 V board pin drives {pid}:{port}, a 3.3 V input that is not 5 V tolerant"))
    net_of = {k: i for i, n in enumerate(nets) for k in n}
    for pid, t in types.items():  # E9
        if not facts(pid).get("needs_series_resistor") or family(t) != "led":
            continue
        legs = [net_of.get(f"{pid}:{leg}") for leg in ("A", "C")]
        if None in legs:
            continue
        a_net, c_net = nets[legs[0]], nets[legs[1]]
        others = [k for k in a_net | c_net if not k.startswith(pid + ":")]
        drives = any(_board_role(k, types) not in (None, "GND") for k in a_net)
        grounded = any(_board_role(k, types) == "GND" for k in c_net)
        if drives and grounded and not any(family(types.get(k.split(":", 1)[0])) == "resistor" for k in others):
            issues.append(("E9", f"{pid} is wired from a board pin to ground with no series resistor"))
    return issues


def lego_geometry(flat, catalogue):
    """L5, on the `stack` joins a builder DECLARED (u rests on v, i.e. clutches it), using only what the cards state.
    The stud-cell count is used only for cards made by code (plain bricks, plates and tiles), whose grids are exact."""
    issues = []
    kinds = lambda t: [p["kind"] for p in (catalogue.get(t) or {}).get("ports", [])]
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    rests = collections.defaultdict(set)
    for e in flat["edges"]:
        if e.get("method") == "stack" and e["u"] in types and e["v"] in types:
            rests[e["u"]].add(e["v"])
    for upper, lowers in rests.items():
        for lower in lowers:
            k = kinds(types[lower])
            if k and "stud" not in k and (catalogue.get(types[lower]) or {}).get("category") == "tile":
                issues.append(("L5", f"{upper} ({types[upper]}) rests on {lower} ({types[lower]}), a tile with no studs to hold it"))
            if upper in rests.get(lower, ()):
                if upper < lower:
                    issues.append(("L5", f"{upper} and {lower} each rest on the other"))
        card = catalogue.get(types[upper]) or {}
        cells = sum(1 for x in kinds(types[upper]) if x == "anti-stud")
        exact = (card.get("source") or {}).get("made_by") == "code"  # only code-made cards have exact stud grids
        if exact and cells and len(lowers) > cells:
            issues.append(("L5", f"{upper} ({types[upper]}) rests on {len(lowers)} pieces but has only {cells} stud cells underneath"))
    return issues


# --- v7: Path B laws on the piece list (fixed ids, steps, rests_on, positions on the stud grid) --------------
SHAPE = re.compile(r"^(Brick|Plate|Tile|Slope)\b(.*?)(\d+) x (\d+)(?: x (\d+(?:/\d+)?))?", re.I)
NO_STUDS_ON_TOP = re.compile(r"^Tile\b(?!.*\b(stud|studs)\b)", re.I)  # a tile is smooth unless named with studs


def piece_shape(name):
    """'Brick 2 x 4' -> {'w': 2, 'l': 4, 'h': 3 (plates), 'smooth': False}; None for a piece that is not a plain
    block (Technic, minifigure, wheel ...). Slopes and modified bricks/plates/tiles keep their footprint."""
    m = SHAPE.match(re.sub(r"\s+", " ", name or "").strip())
    if not m:
        return None
    kind, w, l, tall = m.group(1).lower(), int(m.group(3)), int(m.group(4)), m.group(5)
    h = {"brick": 3, "slope": 3, "plate": 1, "tile": 1}[kind]
    if tall and kind in ("brick", "slope"):
        h = 2 if tall == "2/3" else 3 * int(tall) if tall.isdigit() else h
    return {"w": w, "l": l, "h": h, "smooth": bool(NO_STUDS_ON_TOP.match(name or ""))}


def cells(shape, pos):
    """The stud cells a placed piece covers: unturned, its long side runs along x."""
    a, b = max(shape["w"], shape["l"]), min(shape["w"], shape["l"])
    dx, dy = (b, a) if pos["turned"] else (a, b)
    return {(pos["x"] + i, pos["y"] + j) for i in range(dx) for j in range(dy)}


def position_joins(pieces, info):
    """Pairs (upper, lower) where code finds, from the positions alone, that upper sits on lower's top and covers at
    least one of its cells (lower not a smooth tile)."""
    placed = {i: (info[i]["shape"], p["position"]) for i, p in pieces.items()
              if p.get("position") and i in info and info[i]["shape"]}
    by_top = collections.defaultdict(list)
    for i, (shape, pos) in placed.items():
        by_top[pos["layer"] + shape["h"]].append(i)
    out = []
    for u, (shape, pos) in placed.items():
        mine = cells(shape, pos)
        for v in by_top.get(pos["layer"], ()):
            if v != u and not placed[v][0]["smooth"] and mine & cells(*placed[v]):
                out.append((u, v))
    return out


def lego_pieces(pieces, info, duplicates=(), limit=60):
    """L6-L10 on a v7 answer. pieces: {id: {step, rests_on, position}}; info: {id: {type, name, shape}} from the
    parts list. Returns [(rule, message)].
      L6  ids: every id of the piece list once, no other ids
      L7  order: a piece rests only on pieces added at an earlier or the same step, never on itself
      L8  nothing rests on a smooth tile
      L9  capacity: a piece rests on at most as many pieces as it has cells underneath; at most as many pieces rest
          on a piece as it has studs on top
      L10 positions: a piece said to rest on another sits on its top layer over a shared cell; two pieces never fill
          the same space; pieces the positions put on top of each other are listed in rests_on"""
    issues = []
    missing = [i for i in info if i not in pieces]
    unknown = [i for i in pieces if i not in info]
    if missing:
        issues.append(("L6", f"{len(missing)} ids of the piece list are missing: {', '.join(missing[:30])}"
                             + (" …" if len(missing) > 30 else "")))
    if unknown:
        issues.append(("L6", f"ids not in the piece list: {', '.join(unknown[:30])}"))
    for i in duplicates:
        issues.append(("L6", f"{i} is listed more than once"))
    shape = lambda i: (info.get(i) or {}).get("shape")
    on_top = collections.Counter()
    for i, p in pieces.items():
        for below in p["rests_on"]:
            if below == i:
                issues.append(("L7", f"{i} rests on itself"))
            elif below in pieces and pieces[below]["step"] > p["step"]:
                issues.append(("L7", f"{i} (step {p['step']}) rests on {below}, which is added later (step {pieces[below]['step']})"))
            if shape(below) and shape(below)["smooth"]:
                issues.append(("L8", f"{i} rests on {below} ({info[below]['name']}), a smooth tile with no studs"))
            on_top[below] += 1
        s = shape(i)
        if s and len(p["rests_on"]) > s["w"] * s["l"]:
            issues.append(("L9", f"{i} ({info[i]['name']}) rests on {len(p['rests_on'])} pieces but has only "
                                 f"{s['w'] * s['l']} cells underneath"))
    for below, n in on_top.items():
        s = shape(below)
        if s and not s["smooth"] and n > s["w"] * s["l"]:
            issues.append(("L9", f"{n} pieces rest on {below} ({info[below]['name']}), which has only {s['w'] * s['l']} studs"))
    placed = {i: (shape(i), p["position"]) for i, p in pieces.items() if p.get("position") and shape(i)}
    computed = set(position_joins(pieces, info))
    for i, p in pieces.items():
        for below in p["rests_on"]:
            if i in placed and below in placed and (i, below) not in computed:
                (su, pu), (sb, pb) = placed[i], placed[below]
                why = (f"its bottom is at layer {pu['layer']} but the top of {below} is at layer {pb['layer'] + sb['h']}"
                       if pu["layer"] != pb["layer"] + sb["h"] else "they share no stud cell")
                issues.append(("L10", f"{i} rests on {below}, but their positions disagree: {why}"))
    for u, v in sorted(computed):
        if v not in pieces[u]["rests_on"]:
            issues.append(("L10", f"the positions put {u} on top of {v}, but {u}'s rests_on does not list {v}"))
    ids = sorted(placed)
    cover = {i: cells(*placed[i]) for i in ids}
    for n, a in enumerate(ids):
        (sa, pa) = placed[a]
        for b in ids[n + 1:]:
            (sb, pb) = placed[b]
            if pa["layer"] < pb["layer"] + sb["h"] and pb["layer"] < pa["layer"] + sa["h"] and cover[a] & cover[b]:
                issues.append(("L10", f"{a} and {b} fill the same space (layers and cells overlap)"))
    return issues[:limit] + ([("L10", f"… and {len(issues) - limit} more problems of the same kinds")] if len(issues) > limit else [])


# --- v6: breadboard placement (CircuitQuest's physical logic) and pin tables ---------------------------------
HOLE = re.compile(r"^(\d+)([tb])\.([a-j])$")  # catalogue breadboard holes: column, bank (top/bottom half), row


def _legs_on_breadboard(flat, catalogue, nid):
    """{port: (column, bank, row)} for a part's legs that sit in breadboard holes."""
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    out = {}
    for e in flat["edges"]:
        if e["type"] != "joined":
            continue
        for me, other in (("u", "v"), ("v", "u")):
            if e[me] == nid and (catalogue.get(types.get(e[other])) or {}).get("category") == "breadboard":
                m = HOLE.match(e.get(other + "_port") or "")
                if m and e.get(me + "_port"):
                    out[e[me + "_port"]] = (int(m.group(1)), m.group(2), m.group(3))
    return out


def placement(flat, catalogue):
    """B1 a part that sits across the centre gap has legs on both halves, facing each other in the same columns.
    B2 a part whose legs go in together (placed in one go) has them side by side in one row, at most 2 holes
       apart (2.54 or 5 mm leg spacing), in the card's pin order (per half, for a part across the gap). Only parts placed on a breadboard; from the cards' CircuitQuest facts."""
    issues = []
    for n in flat["nodes"]:
        card = catalogue.get(n["type"]) or {}
        if not (card.get("legs_together") or card.get("straddles_gap")):
            continue
        legs = _legs_on_breadboard(flat, catalogue, n["id"])
        if len(legs) < 2:
            continue
        banks = {b for _, b, _ in legs.values()}
        if card.get("straddles_gap"):
            cols = {b: sorted(c for c, bb, _ in legs.values() if bb == b) for b in banks}
            if banks != {"t", "b"}:
                issues.append(("B1", f"{n['id']} ({n['type']}) must sit across the centre gap, legs on both halves; "
                                     f"all its legs are on one half"))
            elif cols["t"] != cols["b"]:
                issues.append(("B1", f"{n['id']} ({n['type']}) across the gap: its legs should face each other in the "
                                     f"same columns (top {cols['t']}, bottom {cols['b']})"))
        if card.get("legs_together"):
            order = [p["name"] for p in card.get("ports", [])]
            for bank in banks:
                row = [(port, c, r) for port, (c, b, r) in legs.items() if b == bank]
                if len(row) < 2:
                    continue
                columns = sorted(c for _, c, _ in row)
                gaps = [b - a for a, b in zip(columns, columns[1:])]
                if any(g > 2 for g in gaps) and not card.get("straddles_gap"):  # 2.54 or 5 mm leg spacing
                    issues.append(("B2", f"{n['id']} ({n['type']}): its legs go in together as one part, side by side "
                                         f"(at most 2 holes apart); they are in columns {columns}"))
                ranked = [order.index(p) for p, _, _ in sorted(row, key=lambda x: x[1]) if p in order]
                if len(ranked) > 2 and ranked != sorted(ranked) and ranked != sorted(ranked, reverse=True):
                    issues.append(("B2", f"{n['id']} ({n['type']}): legs out of the card's pin order "
                                         f"({', '.join(order)}) along the row"))
    return issues


def pin_tables(manual):
    """Markdown tables in the tutorial with a board-pin column: [{column header: cell}] rows, board pin parsed
    ('16 (analog pin 2)' -> 'A2', '13' -> '13')."""
    rows = []
    for block in re.findall(r"((?:^\|.*\|\s*$\n?){3,})", manual, re.M):
        lines = [l.strip().strip("|") for l in block.strip().splitlines()]
        head = [re.sub(r"[*_`]", "", h).strip().lower() for h in lines[0].split("|")]
        board = next((i for i, h in enumerate(head) if re.search(r"arduino|board", h) and "pin" in h), None)
        if board is None:
            continue
        for line in lines[2:]:
            cells = [re.sub(r"[*_`]", "", c).strip() for c in line.split("|")]
            if len(cells) != len(head):
                continue
            a = re.search(r"analog\s*(?:pin\s*)?(\d)", cells[board], re.I)
            d = re.match(r"\s*(\d{1,2})", cells[board])
            pin = f"A{a.group(1)}" if a else (str(int(d.group(1))) if d else None)
            if pin:
                rows.append({"_pin": pin, **{h: cells[i] for i, h in enumerate(head) if i != board}})
    return rows


def pin_table_law(flat, catalogue, manual):
    """E11: the tutorial's pin table says which part port goes to which board pin (row 5 -> pin 13): check it.
    A port is found from the column header's initial plus the cell (Row 5 -> R5, Column 2 -> C2) on any part that has
    it; the board pin must be on the same net, directly or through one resistor."""
    rows = pin_tables(manual)
    if not rows:
        return []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    nets = logical.nets(flat, catalogue)
    net_of = {k: i for i, net in enumerate(nets) for k in net}
    boards = [pid for pid, t in types.items() if family(t) == "board"]
    reach = {}  # net index -> nets reachable through one resistor
    for pid, t in types.items():
        if family(t) == "resistor":
            ends = [net_of.get(f"{pid}:{leg}") for leg in ("1", "2")]
            if None not in ends:
                reach.setdefault(ends[0], set()).add(ends[1])
                reach.setdefault(ends[1], set()).add(ends[0])
    issues = []
    for row in rows:
        for head, cell in row.items():
            if head == "_pin" or not re.fullmatch(r"\d{1,2}", cell or ""):
                continue
            port = head[:1].upper() + cell
            owners = [pid for pid, t in types.items() if any(p["name"] == port for p in (catalogue.get(t) or {}).get("ports", []))]
            if len(owners) != 1 or not boards:
                continue
            here = net_of.get(f"{owners[0]}:{port}")
            want = {net_of.get(f"{b}:{row['_pin']}") for b in boards} - {None}
            if here is None or not ({here} | reach.get(here, set())) & want:
                issues.append(("E11", f"the tutorial's pin table puts {owners[0]}:{port} ({head} {cell}) on board pin "
                                      f"{row['_pin']}, but the graph does not connect them"))
    return issues


def matrix_resistors(flat, catalogue):
    """E12: on a part with row and column pins (R1.., C1..: an LED matrix), the current-limiting resistors are all on
    the rows or all on the columns, never mixed."""
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    nets = logical.nets(flat, catalogue)
    for pid, t in types.items():
        ports = [p["name"] for p in (catalogue.get(t) or {}).get("ports", [])]
        rows = [p for p in ports if re.fullmatch(r"R\d+", p)]
        cols = [p for p in ports if re.fullmatch(r"C\d+", p)]
        if len(rows) < 2 or len(cols) < 2:
            continue
        with_res = lambda group: [p for p in group if any(f"{pid}:{p}" in n and any(
            family(types.get(k.split(":")[0])) == "resistor" for k in n) for n in nets)]
        on_rows, on_cols = with_res(rows), with_res(cols)
        if on_rows and on_cols:
            fewer, side = (on_rows, "rows") if len(on_rows) <= len(on_cols) else (on_cols, "columns")
            issues.append(("E12", f"{pid} ({t}) has resistors on both rows and columns: move the ones on {side} "
                                  f"({', '.join(fewer)}) to the other side, so every resistor is on the same side"))
    return issues
