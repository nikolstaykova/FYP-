"""Compare a model-built graph with the ground truth.

Arduino: instance ids and port spellings differ between runs, so nets are
compared by signature: each port becomes (family, role), e.g. ('led', 'A'),
('board', '13'), ('resistor', 'x'); symmetric legs share one role.
LEGO: part ids are given to the model, so contacts are compared directly,
on the parts whose geometry the ground truth can compute (plain bricks,
plates, tiles).
"""
import collections
import re

FAMILIES = [("board", r"arduino|uno"), ("breadboard", r"breadboard"), ("wire", r"wire|jumper|cable"),
            ("pot", r"potentiometer|\bpot\b|pot-|trimmer"),
            ("photoresistor", r"photo.?resistor|photocell|\bldr\b"), ("fsr", r"\bfsr\b|force.?sens"),
            ("led", r"\bled\b|led-|-led|^led"),
            ("resistor", r"resistor"), ("button", r"button|switch"),
            ("capacitor", r"capacitor"), ("crystal", r"crystal|xtal"), ("joystick", r"joystick")]
# Part kinds are compared by family, so naming differences between catalogues (capacitor-22pf vs capacitor-ceramic,
# crystal-16mhz vs crystal, analog-joystick vs joystick-analog-2axis) are not counted as different parts.


def family(type_):
    t = re.sub(r"^(cq|wokwi)-", "", (type_ or "").lower())  # answer key uses Wokwi/CircuitQuest type names
    for fam, pattern in FAMILIES:
        if re.search(pattern, t):
            return fam
    return t


def role(fam, port):
    p = (port or "").strip()
    up = p.upper()
    if fam == "board":
        if up.startswith("GND"):
            return "GND"
        if up in ("3V3", "3.3V", "3.3"):
            return "3V3"
        if up in ("5V", "+5V", "VCC"):
            return "5V"
        m = re.match(r"^(?:D|PIN\s*|DIGITAL\s*)?(\d+)$", up)
        if m:
            return str(int(m.group(1)))
        return up
    if fam == "led":
        if up in ("A", "ANODE", "+", "LONG", "POSITIVE"):
            return "A"
        if up in ("C", "K", "CATHODE", "-", "SHORT", "NEGATIVE"):
            return "C"
        return up
    if fam == "pot":
        return "wiper" if up in ("SIG", "WIPER", "W", "MIDDLE", "CENTER", "2", "OUT") else "end"
    if fam in ("resistor", "button", "crystal"):
        return "x"
    if fam == "capacitor":  # electrolytic legs are polar, ceramic legs are not
        return "neg" if up in ("NEG", "-", "C", "K") else "pos" if up in ("POS", "+", "A") else "x"
    return up


def signature(net, types):
    return tuple(sorted((family(types.get(k.split(":")[0])), role(family(types.get(k.split(":")[0])), k.split(":", 1)[1]))
                        for k in net))


def score_arduino(flat, nets, truth, drop_parts=()):
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    t_types = truth["types"]
    t_nets = [frozenset(p for p in n if p.split(":")[0] not in drop_parts) for n in truth["nets"]]
    t_nets = [n for n in t_nets if len(n) >= 2]
    want = collections.Counter(signature(n, t_types) for n in t_nets)
    got = collections.Counter(signature(n, types) for n in nets)
    matched = sum((want & got).values())
    inv_want = collections.Counter(family(t) for pid, t in t_types.items()
                                   if pid not in drop_parts and family(t) not in ("breadboard", "wire"))
    inv_got = collections.Counter(family(n["type"]) for n in flat["nodes"] if family(n["type"]) not in ("breadboard", "wire"))
    return {
        "nets_expected": len(t_nets), "nets_built": len(nets), "nets_matched": matched,
        "net_precision": round(matched / len(nets), 3) if nets else 0.0,
        "net_recall": round(matched / len(t_nets), 3) if t_nets else 0.0,
        "all_nets_correct": matched == len(t_nets) == len(nets),
        "inventory_correct": inv_want == inv_got,
        "inventory_expected": dict(inv_want), "inventory_built": dict(inv_got),
        "missing_nets": [list(s) for s in (want - got)], "extra_nets": [list(s) for s in (got - want)],
    }


def score_lego(flat, truth):
    edges = {frozenset([e["u"], e["v"]]) for e in flat["edges"] if e["type"] == "joined" and e["u"] != e["v"]}
    s = truth["scoreable"]
    pred = {e for e in edges if e <= s}
    gold = truth["contacts"]
    tp = len(pred & gold)
    ids_kept = {n["id"] for n in flat["nodes"]} >= {n["id"] for n in truth["nodes"]}
    return {"parts_expected": len(truth["nodes"]), "parts_built": len(flat["nodes"]), "all_part_ids_kept": ids_kept,
            "joined_edges": len(edges), "scoreable_parts": len(s), "contacts_expected": len(gold),
            "contacts_predicted_among_scoreable": len(pred), "contacts_correct": tp,
            "contact_precision": round(tp / len(pred), 3) if pred else 0.0,
            "contact_recall": round(tp / len(gold), 3) if gold else 0.0}


def score_drafts(drafts, verified):
    """First-time part creation: compare model-drafted types with verified entries of the same family."""
    by_family = {}
    for e in verified.values():
        by_family.setdefault(family(e["type"]), e)
    rows = []
    for d in drafts:
        fam = family(d["type"])
        ref = by_family.get(fam)
        if not ref or fam in ("breadboard", "wire", "board"):
            rows.append({"type": d["type"], "family": fam, "checked": False})
            continue
        rows.append({"type": d["type"], "family": fam, "checked": True,
                     "polarized_ok": d["polarized"] == ref["polarized"],
                     "symmetric_ok": bool(d["symmetric"]) == bool(ref["symmetric"]),
                     "port_count_ok": len(d["ports"]) in (len(ref["ports"]), len({p["name"].split(".")[0] for p in ref["ports"]}))})
    return rows


def score_lego_drafts(drafts, describe_dims):
    """LEGO drafts: does a drafted brick/plate/tile have the right number of studs and anti-studs?"""
    rows = []
    for d in drafts:
        dims = describe_dims(d["type"])
        if not dims:
            rows.append({"type": d["type"], "checked": False})
            continue
        kind, w, l = dims
        studs = sum(1 for p in d["ports"] if p["kind"] == "stud")
        anti = sum(1 for p in d["ports"] if "anti" in p["kind"])
        rows.append({"type": d["type"], "checked": True, "studs": studs, "anti_studs": anti,
                     "studs_ok": studs == (0 if kind == "tile" else w * l), "anti_ok": anti in (w * l, 1)})
    return rows


def _element_id(node):
    for text in (node["type"], node.get("label") or ""):
        m = re.search(r"(\d{6,7})", text)
        if m:
            return m.group(1)
    return None


def score_lego_pdf(flat, truth_, elements, part_nums=frozenset()):
    """Parts: the model's pieces vs the official inventory, at two levels:
      exact  = part + colour, via the Element ID (only when the booklet has an inventory page);
      design = part shape only, via the Element ID or a `lego-<design number>` type.
    Connections: design-level pairs among plain bricks/plates/tiles vs LDraw geometry."""
    exact, design = collections.Counter(), collections.Counter()
    design_of, unmapped = {}, 0
    for n in flat["nodes"]:
        el = _element_id(n)
        part = elements.get(el) if el else None
        if part:
            exact[f"{part[0]}/{part[1]}"] += 1
            design_of[n["id"]] = part[0]
        else:
            m = re.match(r"^lego-([0-9a-z]+)$", n["type"].lower())
            if m and m.group(1) in part_nums:
                design_of[n["id"]] = m.group(1)
            else:
                unmapped += 1
                continue
        design[design_of[n["id"]]] += 1
    want_exact = collections.Counter(truth_["inventory"])
    want_design = collections.Counter()
    for key, q in truth_["inventory"].items():
        want_design[key.split("/")[0]] += q
    m_exact = sum((want_exact & exact).values())
    m_design = sum((want_design & design).values())
    pairs = collections.Counter()
    s = truth_["scoreable_designs"]
    for e in flat["edges"]:
        if e["type"] == "joined" and e["u"] in design_of and e["v"] in design_of:
            a, b = design_of[e["u"]], design_of[e["v"]]
            if a in s and b in s:
                pairs[tuple(sorted((a, b)))] += 1
    gold = truth_["pairs"]
    tp = sum((gold & pairs).values())
    built = len(flat["nodes"])
    return {"pieces_expected": truth_["pieces"], "pieces_built": built, "pieces_unmapped": unmapped,
            "inventory_matched": m_design, "exact_matched": m_exact,
            "inventory_precision": round(m_design / built, 3) if built else 0.0,
            "inventory_recall": round(m_design / truth_["pieces"], 3) if truth_["pieces"] else 0.0,
            "exact_recall": round(m_exact / truth_["pieces"], 3) if truth_["pieces"] else 0.0,
            "joined_edges": sum(1 for e in flat["edges"] if e["type"] == "joined"),
            "contacts_expected": sum(gold.values()), "contacts_predicted": sum(pairs.values()), "contacts_correct": tp,
            "contact_precision": round(tp / sum(pairs.values()), 3) if pairs else None,
            "contact_recall": round(tp / sum(gold.values()), 3) if gold else None}


HW_FAMILIES = [("led", r"\bLEDs?\b"), ("resistor", r"resistor"), ("pot", r"potentiometer"), ("button", r"button|switch"),
               ("servo", r"servo"), ("buzzer", r"piezo|buzzer|speaker"), ("photoresistor", r"photo ?resistor|photocell|LDR"),
               ("lcd", r"\bLCD\b|display"), ("motor", r"\bmotor\b"), ("sensor", r"sensor"), ("transistor", r"transistor"),
               ("capacitor", r"capacitor"), ("diode", r"diode")]


def score_hardware(flat, hardware):
    """Tutorials without an answer key: are the part families the tutorial lists all in the graph?"""
    listed = {fam for item in hardware for fam, pat in HW_FAMILIES if re.search(pat, item, re.I)}
    built = " ".join(f"{n['type']} {n.get('label') or ''}" for n in flat["nodes"]).lower()
    present = {fam for fam in listed if re.search(dict(HW_FAMILIES)[fam], built, re.I) or fam in built}
    return {"families_listed": sorted(listed), "families_missing": sorted(listed - present),
            "hardware_recall": round(len(present) / len(listed), 3) if listed else None}


# --- Equivalent circuits (v5 scoring): series order does not matter -------------------------
SERIES = ("resistor", "led")


def _series_chains(nets, types):
    """Replace every chain of two-legged parts in series (resistors, LEDs) by one virtual part, so that
    pin 13 -> resistor -> LED -> GND and pin 13 -> LED -> resistor -> GND compare equal.
    Returns (nets with chain ends renamed, types for the virtual parts)."""
    fam = lambda pid: family(types.get(pid))
    legs = collections.defaultdict(list)  # series part -> [(net index, port)]
    for i, net in enumerate(nets):
        for k in net:
            pid, port = k.split(":", 1)
            if fam(pid) in SERIES:
                legs[pid].append((i, port))
    internal = {i for i, net in enumerate(nets)
                if len(net) == 2 and all(fam(k.split(":", 1)[0]) in SERIES for k in net)
                and len({k.split(":", 1)[0] for k in net}) == 2}
    adj = collections.defaultdict(set)
    for i in internal:
        a, b = (k.split(":", 1)[0] for k in nets[i])
        adj[a].add(b)
        adj[b].add(a)
    seen, renamed, new_types = set(), {}, {}
    for start in sorted(legs):
        if start in seen or len(adj[start]) > 1:
            continue  # start chains at an end (0 or 1 series neighbour)
        chain, prev, cur = [], None, start
        while cur and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            prev, cur = cur, (nxt[0] if nxt else None)
        ends = []
        for pid in (chain[0], chain[-1]):
            for i, port in legs[pid]:
                if i not in internal and (len(chain) > 1 or len(ends) < 2):
                    ends.append((pid, port, i))
        ends = ends[:2]
        if len(ends) < 2:
            continue
        # LED direction along the chain, from end 0 to end 1: forward if it is entered at its anode
        forward = backward = 0
        for n, pid in enumerate(chain):
            if fam(pid) != "led":
                continue
            if n == 0:  # entered from the chain's first end
                in_port = ends[0][1]
            else:  # entered through the net it shares with the previous part
                prev = chain[n - 1]
                in_port = next((p for i, p in legs[pid] if i in internal and any(k.startswith(prev + ":") for k in nets[i])), None)
            forward += role("led", in_port) == "A"
            backward += role("led", in_port) == "C"
        n_r = sum(1 for p in chain if fam(p) == "resistor")
        n_l = sum(1 for p in chain if fam(p) == "led")
        cid = f"chain{len(new_types) + 1}"
        new_types[cid] = f"series-r{n_r}-l{n_l}"
        if n_l and (forward == n_l or backward == n_l):  # polarised: the anode end is 'p'
            a_end, c_end = (ends[0], ends[1]) if forward == n_l else (ends[1], ends[0])
            renamed[f"{a_end[0]}:{a_end[1]}"] = f"{cid}:p"
            renamed[f"{c_end[0]}:{c_end[1]}"] = f"{cid}:q"
        else:
            for pid, port, _ in ends:
                renamed[f"{pid}:{port}"] = f"{cid}:x"
    out = []
    for i, net in enumerate(nets):
        if i in internal and all(k.split(":", 1)[0] in seen for k in net):
            continue
        out.append(frozenset(renamed.get(k, k) for k in net))
    return out, {**types, **new_types}


UNPOLAR = ("buzzer", "speaker")  # a piezo disc or a speaker plays the same either way round


def _unpolar(nets, types):
    """Equivalent scoring: the two legs of a piezo buzzer or speaker are interchangeable."""
    def key(k):
        part, port = k.split(":", 1)
        return f"{part}:x" if any(u in family(types.get(part)) for u in UNPOLAR) else k
    return [frozenset(key(k) for k in n) for n in nets]


def score_equivalent(flat, nets, truth, drop_parts=(), unpolar=True):
    """Like score_arduino's nets, but series order of resistors/LEDs and the legs of a buzzer/speaker do not matter."""
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    t_nets = [frozenset(p for p in n if p.split(":")[0] not in drop_parts) for n in truth["nets"]]
    t_nets = [n for n in t_nets if len(n) >= 2]
    loose = _unpolar if unpolar else (lambda n, t: list(n))
    g_nets, g_types = _series_chains(loose(nets, types), types)
    w_nets, w_types = _series_chains(loose(t_nets, truth["types"]), truth["types"])
    want = collections.Counter(signature(n, w_types) for n in w_nets)
    got = collections.Counter(signature(n, g_types) for n in g_nets)
    matched = sum((want & got).values())
    return {"eq_nets_expected": sum(want.values()), "eq_nets_built": sum(got.values()), "eq_nets_matched": matched,
            "eq_all_correct": want == got}


# --- Substitute board pins (v5 scoring, CircuitQuest's rule) ----------------------------------
# CircuitQuest (core/engine.py, _try_pin_substitution) accepts a component on another pin of the SAME pool: any
# digital pin for a digital pin, any analog pin for an analog one, and rewrites the code to match. Not substitutable:
# 5V/GND/3V3, pins wired to a part's bus legs (I2C/SPI/serial are fixed in hardware), and every pin of a sketch that
# loops over pin numbers. Added here: a pin the code drives with analogWrite()/tone() needs a PWM substitute.
PWM = {"3", "5", "6", "9", "10", "11"}  # Arduino Uno
BUS_LEGS = re.compile(r"^(SDA|SCL|MOSI|MISO|SCK|SS|CS|TX|RX|TXD|RXD|DIN|CLK)$", re.I)


def pins_fixed(manual):
    """A sketch that walks its pins in a loop and uses the loop variable AS the pin (for (pin = 2; pin < 8; pin++)
    digitalWrite(pin, ...)) cannot follow a moved pin. A loop over an array of pins (col[thisPin]) can."""
    for var in re.findall(r"for\s*\(\s*(?:int\s+|byte\s+)?(\w+)\s*=\s*\d+\s*;", manual):
        if re.search(rf"(?:pinMode|digitalWrite|digitalRead|analogWrite|analogRead|tone)\s*\(\s*{re.escape(var)}\s*[,)]", manual):
            return True
    return False


def _pin_class(sig_role, pwm_needed):
    """Pool a board role belongs to, or None if it must stay exactly as it is."""
    if re.fullmatch(r"A[0-5]", sig_role):
        return "analog"
    if sig_role.isdigit() and sig_role not in ("0", "1"):
        return "pwm" if pwm_needed and sig_role in PWM else "digital"
    return None


def score_substitute(flat, nets, truth, drop_parts=(), manual=""):
    """Every connection right if board pins may be swapped within their pool (see above). Series order and
    buzzer legs are accepted too (score_equivalent). Returns {"sub_all_correct": bool, ...}."""
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    t_nets = [frozenset(p for p in n if p.split(":")[0] not in drop_parts) for n in truth["nets"]]
    t_nets = [n for n in t_nets if len(n) >= 2]
    g_nets, g_types = _series_chains(_unpolar(nets, types), types)
    w_nets, w_types = _series_chains(_unpolar(t_nets, truth["types"]), truth["types"])
    fixed = pins_fixed(manual)
    pwm_needed = bool(re.search(r"analogWrite|tone\s*\(", manual))

    def abstract(net_list, tps):
        """Replace substitutable board pins by their pool; returns [(signature, {pool: [pins]})]."""
        out = []
        for net in net_list:
            sig, pins = [], collections.defaultdict(list)
            bus = any(BUS_LEGS.match(k.split(":", 1)[1]) for k in net if family(tps.get(k.split(":")[0])) != "board")
            for k in net:
                part, port = k.split(":", 1)
                fam = family(tps.get(part))
                r = role(fam, port)
                cls = None if (fixed or bus or fam != "board") else _pin_class(r, pwm_needed)
                if cls:
                    pins[cls].append(r)
                    sig.append((fam, cls))
                else:
                    sig.append((fam, r))
            out.append((tuple(sorted(sig)), pins))
        return out

    want, got = abstract(w_nets, w_types), abstract(g_nets, g_types)
    if collections.Counter(s for s, _ in want) != collections.Counter(s for s, _ in got):
        return {"sub_all_correct": False}
    # The same shapes exist; a PWM pin in the answer key needs a PWM pin in the graph (the abstraction already
    # demands it when the code uses analogWrite/tone), and no board pin may serve two nets.
    used = [p for _, pins in got for ps in pins.values() for p in ps]
    return {"sub_all_correct": len(used) == len(set(used))}
