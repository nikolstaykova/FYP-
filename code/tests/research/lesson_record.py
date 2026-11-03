"""The lesson record: what a lesson says about itself as a whole, and where each piece of its content belongs
(DATA_STRUCTURE.md §3.2). Content lives at the narrowest place it applies to:
  lesson        about · how it works · what to try next · troubleshooting that spans steps · expected result ·
                parts list
  upload step   the sketch, its walkthrough, its links to the circuit (code_links.py), what you should see,
                troubleshooting about the code and the upload
  build step    troubleshooting that names only the parts that step places
An entry moves down to a step only on evidence: the parts its fix names (the part after "symptom:", by name, colour,
legs) are all placed by that one step, or the fix is about the code and the upload. Anything else stays on the lesson. Every moved entry keeps its
place in the source list (`index`), so the source lesson can be rebuilt exactly (lesson_graphs.audit).

The expected result is worked out from the physical graph (its electrical nets, connectors folded away: a wire's two
ends, a breadboard strip, the board's GND pins are one), and the lesson's own final check is compared with it.
The parts list is the lesson's own list (Arduino: the gather step; LEGO: Rebrickable's inventory of the set). Each
row points to the physical instances it accounts for (match_parts), so a part missing from the list, or a row the
build does not fill, is named.
"""
import collections
import re

CODE_WORDS = re.compile(r"\b(upload\w*|sketch|IDE|USB|port|code|delay\(|Serial Monitor|board and port)\b", re.I)


def _mentions(text, nodes, cards):
    """The instances an entry names: an LED or its legs, the resistor, '<colour> wire', any wire. The board and the
    breadboard are everywhere and are not evidence."""
    found = set()
    t = text.lower()
    for n in nodes:
        card = cards.get(n["type"]) or {}
        cat = (card.get("category") or "").lower()
        colour = str((n.get("props") or {}).get("colour") or "").lower()
        if cat in ("board", "breadboard", "microcontroller-board"):
            continue
        if cat == "led" and (re.search(r"\bleds?\b(?! marked)", t) or re.search(r"\b(long|short) legs?\b", t)):
            found.add(n["id"])
        elif cat == "resistor" and re.search(r"\bresistors?\b", t):
            found.add(n["id"])
        elif cat in ("wire", "cable") or n["type"] == "jumper-wire":
            if colour and re.search(rf"\b{re.escape(colour)} wire\b", t):
                found.add(n["id"])
            elif re.search(r"\b(each|every|all|the) wires?\b", t) and not re.search(r"\b\w+ wire\b", t.replace("each wire", "")):
                found.add(n["id"])
            elif re.search(r"\beach wire\b|\bevery wire\b", t):
                found.add(n["id"])
    return found


def place(entries, nodes, cards, placed_by, upload_step):
    """Each entry -> (where, evidence): a step id or 'lesson'."""
    out = []
    for i, text in enumerate(entries):
        fix = text.split(":", 1)[1] if ":" in text else text  # "symptom: fix" -- the fix says where the problem is
        names = _mentions(fix, nodes, cards)
        steps = {placed_by[n] for n in names if n in placed_by}
        code = bool(CODE_WORDS.search(fix))
        if code and upload_step:
            steps.add(upload_step)
        if len(steps) == 1:
            where = next(iter(steps))
            why = (f"names {', '.join(sorted(names))}, placed by {where}" if names else "") + \
                  ("; " if names and code else "") + ("about the code or the upload" if code else "")
        else:
            where = "lesson"
            why = (f"spans {', '.join(sorted(steps))}" if steps else "names no single step's parts")
        out.append({"text": text, "index": i, "where": where, "evidence": why})
    return out


def _strip(port):
    return port.split(".", 1)[0]


def nets(physical, cards):
    """The circuit's electrical nets from the physical graph: [sorted ports], connectors folded away."""
    types = {n["id"]: n["type"] for n in physical["nodes"]}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def key(part, port):
        card = cards.get(types.get(part)) or {}
        rule = card.get("port_alias_rule") or {}
        if rule.get("mode") == "strip":
            port = _strip(port)
        elif rule.get("mode") == "prefix":
            port = next((p for p in rule.get("prefixes", []) if port.startswith(p)), port)
        return f"{part}:{port}"

    for e in physical["edges"]:
        if e["type"] == "electrical":
            a, b = find(key(e["u"], e["u_port"])), find(key(e["v"], e["v_port"]))
            parent[a] = b
    for part, t in types.items():
        ib = (cards.get(t) or {}).get("intrinsic_behaviour") or {}  # joined inside the part: a strip, a cable's wires
        for group in ib.get("internal_conducts", []) + _wires_through(cards.get(t) or {}):
            for a, b in zip(group, group[1:]):
                parent[find(key(part, a))] = find(key(part, b))
    groups = collections.defaultdict(set)
    for k in list(parent):
        part = k.split(":", 1)[0]
        if ((cards.get(types.get(part)) or {}).get("intrinsic_behaviour") or {}).get("is_connector_only"):
            continue
        groups[find(k)].add(k)
    return sorted(sorted(g) for g in groups.values()  # a net joins two parts or more: a chip's own unused input and
                  if len({k.split(":", 1)[0] for k in g}) >= 2)  # output (joined only through it) is none


def _wires_through(card):
    """A cable's or connector's wires (internal_pass_through) join its ends into one net. A component's
    pass-through (a resistor 1-2, an LED A-C, a driver chip's input to its output) is a path through the part, not a
    wire: its two sides are two nets."""
    ib = card.get("intrinsic_behaviour") or {}
    if ib.get("is_connector_only") or card.get("category") in ("cable", "connector"):
        return ib.get("internal_pass_through", [])
    return []


def port_nets(physical, cards):
    """Every port the physical graph uses -> the index of its net in nets(physical, cards), connectors included (a
    wire's ends, a breadboard hole share the net of what they join). Ports on no net of two or more parts: None."""
    types = {n["id"]: n["type"] for n in physical["nodes"]}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def key(part, port):
        rule = (cards.get(types.get(part)) or {}).get("port_alias_rule") or {}
        if rule.get("mode") == "strip":
            port = _strip(port)
        elif rule.get("mode") == "prefix":
            port = next((q for q in rule.get("prefixes", []) if port.startswith(q)), port)
        return f"{part}:{port}"

    raw = set()
    for e in physical["edges"]:
        for part, port in ((e["u"], e.get("u_port")), (e["v"], e.get("v_port"))):
            if port is not None:
                raw.add(f"{part}:{port}")
                parent[find(f"{part}:{port}")] = find(key(part, port))
        if e["type"] == "electrical":
            parent[find(key(e["u"], e["u_port"]))] = find(key(e["v"], e["v_port"]))
    for part, t in types.items():
        ib = (cards.get(t) or {}).get("intrinsic_behaviour") or {}  # joined inside the part: a strip, a cable's wires
        for group in ib.get("internal_conducts", []) + _wires_through(cards.get(t) or {}):
            for a, b in zip(group, group[1:]):
                parent[find(key(part, a))] = find(key(part, b))
    derived = nets(physical, cards)
    root_of = {find(p): i for i, net in enumerate(derived) for p in net}
    return {p: root_of.get(find(p)) for p in sorted(raw)}


def compare_check(stored_pairs, derived, cards, types):
    """Does the lesson's final check say the same as the circuit? Each stored pair must be inside one derived net,
    and each derived net must be named by some pair. Returns (agree, [problem])."""
    def canon(p):
        part, port = p.split(":", 1)
        rule = (cards.get(types.get(part)) or {}).get("port_alias_rule") or {}
        if rule.get("mode") == "prefix":
            port = next((x for x in rule.get("prefixes", []) if port.startswith(x)), port)
        return f"{part}:{port}"
    where = {p: i for i, net in enumerate(derived) for p in net}
    folded = lambda p: ((cards.get(types.get(p.split(":", 1)[0])) or {}).get("intrinsic_behaviour")  # noqa: E731
                        or {}).get("is_connector_only")  # a cable's own pin: folded away, its net is its ends'
    problems, covered = [], set()
    via = collections.defaultdict(set)  # pairs that meet at a connector's pin (a header pin to the resistor, the same
    for pair in stored_pairs:           # pin to the LCD's A) name the parts on both sides as one net
        for p in pair:
            if folded(p):
                via[p] |= {q for q in pair if not folded(q)}
    stored_pairs = list(stored_pairs) + [sorted(v) for v in via.values() if len(v) >= 2]
    for pair in stored_pairs:
        kept = [p for p in pair if not folded(p)]
        if len(kept) < 2:
            continue  # it only names the cable's two ends: nothing to compare
        ids = {where.get(canon(p)) for p in kept}
        if None in ids or len(ids) != 1:
            problems.append(f"final check pair {pair} is not one net of the circuit")
        else:
            covered |= ids
    for i, net in enumerate(derived):
        if i not in covered:
            problems.append(f"the circuit's net {net} is not in the final check")
    return not problems, problems


def _ohms(v):
    """'10k' -> 10000.0, '220' -> 220.0, '4.7uF' -> 4.7e-06; None if it is not a value."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(k|m|meg|u|n|p)?\s*(ohms?|r|f)?", str(v or "").strip().lower())
    if not m:
        return None
    mult = {"k": 1e3, "m": 1e6, "meg": 1e6, "u": 1e-6, "n": 1e-9, "p": 1e-12}.get(m.group(2), 1)
    if m.group(3) == "f" and m.group(2) == "m":
        mult = 1e-3
    return round(float(m.group(1)) * mult, 15)


def _valued(t, value=None):
    """(family, value) for a valued part: 'resistor-220' or a 'resistor' whose value is 220; else None."""
    from graph.parts.naming import VALUE_PARTS
    fam, _, v = str(t).partition("-")
    if fam in VALUE_PARTS and (v or value) and _ohms(v or value) is not None:
        return fam, _ohms(v or value)
    return None


def match_parts(listed, physical, cards, definition):
    """Each parts-list row -> the physical instances it accounts for (in place: row["instances"]), matched by
    definition (a printed or sized type is its base: 3003pr0053 and 3003pe2 are both lego-3003) and, when the row
    names one, colour. A row with no count takes every match. Returns [problem]: a row with too few or too many
    instances, an instance no row accounts for."""
    base = lambda t: (definition(cards, t)[0] or {}).get("part_type_id", t)  # noqa: E731
    colour = lambda n: str((n.get("props") or {}).get("colour") or "").lower()  # noqa: E731
    free = list(physical["nodes"])
    problems = []
    for row in sorted(listed, key=lambda r: r.get("colour") is None):  # rows that name a colour first
        want = base(row["part"])
        hits = [n for n in free if base(n["type"]) == want and (not row.get("colour") or colour(n) == row["colour"].lower())]
        if _valued(row["part"]):  # 'resistor-220' on the list: a resistor of value 220 in the build, not any resistor
            val = lambda n: _valued(n["type"], (n.get("props") or {}).get("value"))  # noqa: E731
            hits = [n for n in hits if val(n) in (None, _valued(row["part"]))] or \
                [n for n in free if val(n) == _valued(row["part"])]
        take = hits if row.get("count") is None else hits[:row["count"]]
        row["instances"] = [n["id"] for n in take]
        free = [n for n in free if n not in take]
        if row.get("count") is None and not take:
            problems.append(f"{row['part']} is listed but not in the build")
        elif row.get("count") is not None and len(take) < row["count"]:
            problems.append(f"{row['part']}{' ' + row['colour'] if row.get('colour') else ''}: the list says "
                            f"{row['count']}, the build has {len(take)}")
    problems += [f"{n['id']} ({n['type']}) is in the build but not on the parts list" for n in free]
    return problems
