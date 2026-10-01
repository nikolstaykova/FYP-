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
            ("pot", r"potentiometer|\bpot\b|pot-|trimmer"), ("led", r"\bled\b|led-|-led|^led"),
            ("resistor", r"resistor"), ("button", r"button|switch")]


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
    if fam in ("resistor", "button"):
        return "x"
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
