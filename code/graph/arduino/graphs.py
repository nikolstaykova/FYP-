"""An Arduino lesson as the stored graphs, and where a learner is in it.

What it is   arduino(lesson_id): the lesson's circuit graph and Wokwi diagram as the physical graph; its steps as
             the steps graph (what each step places and makes: grouped ports, wires that make both their ends, legs
             twisted or soldered together, a part twisted onto a wire's end); the sketch's pin links and the
             substitutions a learner may make; the record (the parts list matched to the build, the circuit's nets
             and the final check compared with them, where each piece of text belongs). export_arduino: the lesson
             back in its own format. And a learner's progress: from the joins they have made, in any order, which
             steps are done and which can come next (only DEPENDS_ON must come first), and which column two parts
             must share (ALIGNS_WITH, made from plan and aligns) (DATA_STRUCTURE.md §4.1).
Used for     storing an Arduino lesson; following a learner who does not build in the suggested order.
Where        lesson_store.py (build arduino, audit), tutor_mcp.py (progress).
"""
import collections
import itertools
import json
import pathlib
import re

from graph import lesson_store
from graph.lesson_store import (PARTS, PART_CATALOGUES, ROOT, _acts, _cards, _chain, _depends, _load, _order, _read,
                                   _rel, definition, describe)


def _arduino_targets(step, physical):
    """The instances and the edges a build step makes, read from the step's `at`: {port: hole} for the part the step
    places (the instance whose ports join exactly those holes), and {instance.port: hole} for each part it groups
    in (up to three suggested steps in one: a part and the wires to it). Returns ([instances], [edges])."""
    at = step.get("at") or {}
    nodes = {n["id"] for n in physical["nodes"]}
    joined = [e for e in physical["edges"] if e["type"] == "joined"]
    def owner(k):  # the instance a key names, the longest id first (an instance id may hold a dot: pb1.btn)
        i = next((n for n in sorted(nodes, key=len, reverse=True) if k.startswith(n + ".")), None)
        return (i, k[len(i) + 1:]) if i else None
    named = {k: owner(k) for k in at if owner(k)}
    bare = {k: v for k, v in at.items() if k not in named}
    insts, want = [], set()
    if bare:  # the step's own part: the one instance whose ports join exactly these holes
        by_inst = collections.defaultdict(set)
        for e in joined:
            for a, ap, b, bp in ((e["u"], e["u_port"], e["v"], e["v_port"]), (e["v"], e["v_port"], e["u"], e["u_port"])):
                by_inst[a].add((ap, f"{b}:{bp}"))
        match = [i for i, got in by_inst.items() if set(bare.items()) <= got]
        if len(match) == 1:  # more than one (two cables in the same sockets): the named keys still count
            insts.append(match[0])
            want |= {(match[0], p, *h.split(":", 1)) for p, h in bare.items()}
        elif not named:
            return [], []
    for k, (i, p) in named.items():
        if i not in insts:
            insts.append(i)
        want.add((i, p, *at[k].split(":", 1)))
    wires = {n["id"] for n in physical["nodes"] if "wire" in str(n.get("type", ""))}
    made = [e["id"] for e in joined
            if (e["u"], e["u_port"], e["v"], e["v_port"]) in want or (e["v"], e["v_port"], e["u"], e["u_port"]) in want
            or (e["u"] in insts and e["u"] in wires) or (e["v"] in insts and e["v"] in wires)  # a wire goes in whole;
            or (e.get("method") == "solder" and (e["u"] in insts or e["v"] in insts))]  # soldered with its part
    return insts, made                                                              # both its ends, one into a part


def _wokwi(physical, diagram):
    """The Wokwi diagram onto the physical graph: each part's Wokwi type, place and attrs on its node; each Wokwi
    connection's colour and route on the edges it draws (a lead in a hole: that joined edge; a wire: its two ends).
    Returns the connections that match nothing (audit() reports them)."""
    nodes = {n["id"]: n for n in physical["nodes"]}
    for wp in diagram.get("parts", []):
        if wp["id"] in nodes:
            nodes[wp["id"]].setdefault("props", {})["wokwi"] = {k: wp[k] for k in ("type", "top", "left", "attrs") if k in wp}
    ends = collections.defaultdict(list)  # (instance:port of the far side) -> joined edges
    for e in physical["edges"]:
        if e["type"] == "joined":
            ends[(f"{e['u']}:{e['u_port']}", f"{e['v']}:{e['v_port']}")].append(e)
    wire_end = {}  # far port -> (wire, edge) for wire ends
    for e in physical["edges"]:
        if e["type"] == "joined" and nodes.get(e["u"], {}).get("type") == "jumper-wire":
            wire_end[f"{e['v']}:{e['v_port']}"] = (e["u"], e)
    unmatched = []
    for c in diagram.get("connections", []):
        a, b, colour, route = (c + [None, None])[:4]
        hit = ends.get((a, b)) or ends.get((b, a))
        if not hit and a in wire_end and b in wire_end and wire_end[a][0] == wire_end[b][0]:
            w = wire_end[a][0]
            nodes[w]["props"].setdefault("wokwi", {}).update({"connection": [a, b], "colour": colour, "route": route})
            hit = [wire_end[a][1], wire_end[b][1]]
        if not hit:
            unmatched.append(c)
            continue
        for e in hit:
            e["wokwi"] = {"colour": colour, "route": route, "ends": [a, b]}
    physical["wokwi"] = {k: diagram[k] for k in ("version", "author", "editor", "dependencies") if k in diagram}
    return unmatched


def _board(physical, cards):
    """The board instance of a circuit (the part whose card is a board with described pins) and its card."""
    for n in physical["nodes"]:
        card = (definition(cards, n["type"])[0] or {})
        if card.get("pin_facts") or card.get("category") in ("board", "microcontroller-board"):
            return n["id"], card
    return None, {}


VISIBLE_MA = 5.0  # the least LED current that still lights it clearly (an assumption, stated where it is used)


def _substitutions(physical, cards, program, derived):
    """What may differ from the lesson and still be right (DATA_STRUCTURE.md §3.7).
      pins   for each board pin the code uses: what the code needs from it, the pins that can stand in (pins.py)
             and why each other pin cannot
      parts  for each instance: what may differ (the part's `substitutes` rule); a resistor in series with an LED may
             take any value that keeps the LED's current between VISIBLE_MA and the LED card's current_ma at the
             board's logic voltage"""
    from graph.arduino import pins
    board, bcard = _board(physical, cards)
    used = {e["v_port"] for e in physical["edges"] if e["v"] == board} | {e["u_port"] for e in physical["edges"] if e["u"] == board}
    serial = set()
    if any(l["kind"] == "fixed" and l["token"] == "Serial" for l in (program or {}).get("links", [])):
        serial = {p["id"] for p in bcard.get("ports", []) if any(c.startswith("uart") for c in p.get("can", []))}
        used |= serial  # the sketch talks over Serial: its serial pins are never offered as stand-ins
    out = {"pins": {}, "parts": {}}
    for l in (program or {}).get("links", []):
        if l["kind"] == "fixed":
            out["pins"][l["token"]] = {"needs": l["needs"], "fixed": l["via"][0], "stand_ins": [], "refused": {}}
        if l["kind"] != "code":
            continue
        pin = l["port"].split(":", 1)[1]
        row = out["pins"].setdefault(l["port"], {"needs": [], "lines": []})
        row["needs"] = sorted(set(row["needs"]) | set(l["needs"]))
        row["lines"].append(l["line"])
        ok, why = pins.stand_ins(bcard, pin, row["needs"], used - {pin})
        why.update({p: "kept for Serial, which the sketch uses" for p in serial if p in why and why[p].startswith("already")})
        row["stand_ins"], row["refused"] = ok, why
    for l in (program or {}).get("links", []):
        if l["kind"] == "unresolved":
            out["pins"][f"line {l['line']}: {l['token']}"] = {"needs": l["needs"], "unresolved": l["via"][0],
                                                             "stand_ins": [], "refused": {}}
    logic_v = float((bcard.get("electrical") or {}).get("logic_v") or 5.0)
    types = {n["id"]: n["type"] for n in physical["nodes"]}
    for n in physical["nodes"]:
        card = definition(cards, n["type"])[0] or {}
        rule = dict((card.get("metadata") or {}).get("substitutes") or {})
        if not rule:
            continue
        if rule.get("value") == "by role" and card.get("category") == "resistor":
            led = next((m.split(":")[0] for net in derived for m in net if m.startswith(n["id"] + ":")
                        for m in net if (definition(cards, types.get(m.split(":")[0], ""))[0] or {}).get("category") == "led"), None)
            led_card = definition(cards, types.get(led, ""))[0] or {} if led else {}
            el = led_card.get("electrical") or {}
            if led and el.get("forward_v") and el.get("current_ma"):
                drop = logic_v - float(el["forward_v"])
                rule = {"value_ohms": [round(drop / (float(el["current_ma"]) / 1000)), round(drop / (VISIBLE_MA / 1000))],
                        "why": f"in series with {led}: ({logic_v:g} V - {el['forward_v']:g} V) / current between "
                               f"{VISIBLE_MA:g} mA (still clearly lit, an assumption) and {el['current_ma']:g} mA "
                               f"(the LED card's limit)"}
            else:
                rule = {"value_ohms": None, "why": "not in series with an LED: keep the lesson's value"}
        out["parts"][n["id"]] = rule
    return out


def arduino(lesson_id, lessons_dir=None):
    """1 Arduino lesson as a lesson record, a graph of its steps and its physical graph.
      lesson record  name, link, about, how it works, what to try next, the troubleshooting that spans steps, the
                     expected result (worked out from the circuit, compared with the lesson's final check), the parts
                     list (the gather step's, compared with the circuit)
      steps          gather -> build steps -> upload, and only steps. The upload step carries the sketch, its
                     walkthrough, its links to the circuit (pins.links) and what you should see; a step carries
                     the troubleshooting whose fix names only its parts (lesson_store.place)
      physical       the checked circuit graph, with the Wokwi layout on its nodes and edges
    Every field of the saved lesson, graph and Wokwi diagram is carried over (audit() checks)."""
    from graph.arduino import pins
    lessons_dir = pathlib.Path(lessons_dir or ROOT / "data" / "lessons" / "arduino")
    d = lessons_dir / lesson_id
    graph, saved = json.loads((d / "graph.json").read_text()), json.loads((d / "lesson.json").read_text())
    cards = _cards(PARTS)
    physical = {"lesson_id": lesson_id, "part_catalogue": PART_CATALOGUES["arduino"],
                "nodes": json.loads(json.dumps(graph["nodes"])), "edges": json.loads(json.dumps(graph["edges"])),
                "made_by": "Claude from the tutorial page, checked by laws E1-E11"}
    for e in physical["edges"]:  # the same shape as every domain's edges (the join table below)
        if e["type"] == "joined":
            describe(e, lambda i: definition(cards, next(n["type"] for n in physical["nodes"] if n["id"] == i))[0])
        else:
            for k in ("method", "freedom", "reversible", "holds_by"):
                if e.get(k) is None:
                    e.pop(k, None)
    diagram = _read(d / (saved.get("wokwi_diagram") or "diagram.json"), {})
    physical["wokwi_unmatched"] = _wokwi(physical, diagram)
    physical["wokwi"]["file"] = saved.get("wokwi_diagram")
    physical["wokwi"]["order"] = [wp["id"] for wp in diagram.get("parts", [])]
    stats = _read(d / "stats.json", {})
    extras = saved.get("extras") or {}
    code_text = (d / saved["code"]).read_text() if saved.get("code") and (d / saved["code"]).exists() else None

    steps, acts, added_by, needs, rel, items = [], {}, {}, {}, [], []
    named = {i for st in saved["steps"] if st.get("phase") == "build" for i in _arduino_targets(st, physical)[0]}
    for n, st in enumerate(saved["steps"], 1):
        node = {"id": st["id"], "kind": st.get("phase", "build"), "n": n, "text": st["clip"]}
        for k in ("goal", "hints", "strict", "suggested"):
            if k in st:
                node[k] = st[k]
        if (st.get("extras") or {}).get("why"):
            node["why"] = st["extras"]["why"]
        if st.get("phase") == "build":
            insts, made = _arduino_targets(st, physical)
            node["unresolved"] = not insts
            done = {x for v in acts.values() for x in v}
            # a part no step names, twisted (or soldered) onto a wire end this step puts in, goes on with that wire:
            # the learner twists it on here (a circuit built without a breadboard, parts on the wires' ends)
            by_edge = {e["id"]: e for e in physical["edges"]}
            for eid in list(made):
                e = by_edge.get(eid) or {}
                if e.get("method") in ("twist", "solder"):
                    for part in (e["u"], e["v"]):
                        if part not in named and part not in added_by and part not in insts:
                            insts.append(part)
            # a part an earlier step put in, named here only for its ends on a part this step places (a Grove cable's
            # far end into the module): joined here, not added again
            ends_on = collections.defaultdict(set)
            for k, v in (st.get("at") or {}).items():
                i = next((x for x in insts if k.startswith(x + ".")), None)
                if i:
                    ends_on[i].add(v.split(":", 1)[0])
            from graph.arduino.circuit_lesson import _kinds
            kinds = _kinds(physical)
            again = {i for i in insts if i in added_by and ends_on.get(i) and all(
                     t in insts or t not in added_by and kinds.get(t) == "component" for t in ends_on[i] - {i})}
            insts = [i for i in insts if i not in again]  # and the module those ends go into is this step's part
            insts += sorted({t for i in again for t in ends_on[i]} - set(insts) - set(added_by))
            for inst in insts:
                added_by.setdefault(inst, st["id"])
            while True:  # two parts' legs twisted (or soldered) together: made by the step that has both
                more = [e["id"] for e in physical["edges"]
                        if e["type"] == "joined" and e["id"] not in made and e["id"] not in done
                        and e.get("method") in ("twist", "solder") and {e["u"], e["v"]} & set(insts)
                        and {e["u"], e["v"]} <= set(added_by)]
                if not more:
                    break
                made += more
            acts[st["id"]] = insts + made
            needs[st["id"]] = [p.split(":")[0] for net in st.get("expected_nets", []) for p in net]
            for k in ("expected_nets", "expected_landing"):
                if k in st:
                    node[k] = st[k]
        if st.get("items"):
            items = st["items"]  # the parts list; it lives in the lesson record, not on the step
        if st.get("code") and code_text is not None:  # the upload step: the sketch and its links to the circuit
            board, bcard = _board(physical, cards)
            node["program"] = {"file": st["code"], "text": code_text, "sketch_from": saved.get("sketch_from"),
                               "board": saved.get("board"), "board_instance": board,
                               "walkthrough": extras.get("code_walkthrough", []),
                               "links": pins.links(code_text, board, bcard) if board else []}
            from graph.arduino.circuit_lesson import corrections  # a pin the tutorial reads unwired on purpose (a person's note)
            unwired = (corrections().get(lesson_id) or {}).get("unwired") or {}
            for l in node["program"]["links"]:
                if l.get("port") in unwired:
                    l["unwired"] = unwired[l["port"]]
        steps.append(node)
    by_id = {s["id"]: s for s in steps}
    gather = next((s["id"] for s in steps if s["kind"] == "gather"), None)
    upload = next((s["id"] for s in steps if s.get("program")), None)
    if gather:  # what no build step places (the board, the breadboard) the gather step sets out
        acts[gather] = [n["id"] for n in physical["nodes"] if n["id"] not in added_by]
        for i in acts[gather]:
            added_by[i] = gather
        # GATHERS: the gather step -> the lesson's parts list (whose rows point at the instances it covers)
        rel.append({"type": "GATHERS", "u": gather, "v": "lesson:parts_list"})
    # PROGRAMS: the upload step -> the board it loads the sketch onto (the pins it uses are its code links)
    if upload and by_id[upload]["program"].get("board_instance"):
        rel.append({"type": "PROGRAMS", "u": upload, "v": by_id[upload]["program"]["board_instance"]})
    # content at the narrowest place it applies to
    placed = {i: s for i, s in added_by.items() if s != gather}
    trouble = place(extras.get("troubleshooting", []), physical["nodes"], cards, placed, upload)
    for t in trouble:
        if t["where"] != "lesson":
            by_id[t["where"]].setdefault("troubleshooting", []).append({k: t[k] for k in ("text", "index", "evidence")})
    tries = [{"text": x, "index": i} for i, x in enumerate(extras.get("try_it", []))]
    see = [t for t in tries if re.match(r"\s*you should see\b", t["text"], re.I)]
    if upload and see:
        by_id[upload]["expected"] = [{**t, "evidence": "says what the finished build does"} for t in see]
    inst = {"lesson_id": lesson_id, "nodes": steps,
            "edges": _chain([s["id"] for s in steps]) + rel + _acts(acts, physical) + _depends(acts, added_by, physical, needs)}
    pass  # ALIGNS_WITH: where a step's part goes is set by a part of another step
    wire_ids = wires(physical, cards)
    inst["edges"] += aligns(plan(inst, physical, cards), is_wire=lambda port: port.split(":")[0] in wire_ids,
                               ids=join_ids(inst, physical))
    # CHECK_NEEDS only where nothing else links the two steps: a DEPENDS_ON (the step comes after anyway) or an
    # ALIGNS_WITH (a shared column: the check needs the other part) already says it
    linked = {(e["u"], e["v"]) for e in inst["edges"] if e["type"] in ("DEPENDS_ON", "ALIGNS_WITH")}
    inst["edges"] = [e for e in inst["edges"] if not (e["type"] == "CHECK_NEEDS" and (e["u"], e["v"]) in linked)]

    derived = nets(physical, cards)
    subs = _substitutions(physical, cards, by_id.get(upload, {}).get("program"), derived)
    stored = (saved.get("final_check") or {}).get("expected_nets")
    agree, why = compare_check(stored or [], derived, cards, {n["id"]: n["type"] for n in physical["nodes"]})
    listed = [{"part": t, "count": None} for t in items]
    record = {"lesson_id": lesson_id, "kind": "lesson", "lesson_type": "arduino", "name": saved["title"],
              "link": saved["source"].get("url"), "source": {"kind": "tutorial-link", **saved["source"],
                                                              "lesson_id": saved.get("id")},
              **{k: saved[k] for k in ("description", "difficulty", "board", "tools_used", "parts_used", "generated",
                                       "made_from") if k in saved},
              "how_it_works": extras.get("how_it_works"),
              "try_next": [t for t in tries if t not in see],
              "troubleshooting": [{k: t[k] for k in ("text", "index", "evidence")} for t in trouble if t["where"] == "lesson"],
              "expected_result": {"final_check": saved.get("final_check"), "from_circuit": derived,
                                  "agree": agree if stored else None, "problems": why if stored else []},
              "parts_list": {"from": "the gather step", "parts": listed,
                             "problems": match_parts(listed, physical, cards, definition)},
              "substitutions": subs,
              "stats": stats,
              "derived_from": _rel(d / "lesson.json")}
    entry = {"lesson_id": lesson_id, "title": saved["title"], "lesson_type": "arduino", "source": record["source"],
             "derived_from": record["derived_from"]}
    return entry, {"lesson": record, "instruction": inst, "physical": physical, "document": None}


ADDED_EDGE = ("direction", "wokwi", "filled_from_metadata", "holds_by")  # what the network adds to a source edge


SOURCE_EDGE_FIELDS = ("method", "freedom", "reversible")  # every edge of a source graph.json has these (null if none)


ADDED_NODE = ("wokwi",)                                      # ... and to a source node's props


def export_arduino(lesson_id, store=None):
    """The saved Arduino lesson.json, graph.json, diagram.json and stats.json, rebuilt from the network alone: the
    lesson record, its steps (with the content moved down to them, put back in its source order) and the physical
    graph."""
    row, g = _load(lesson_id, store)
    les, inst, phys = g["lesson"], g["instruction"], g["physical"]
    nodes = {n["id"]: n for n in inst["nodes"]}
    edges = {e["id"]: e for e in phys["edges"]}
    steps, prog, trouble, tries = [], {}, list(les.get("troubleshooting", [])), list(les.get("try_next", []))
    for sid in _order(inst):
        st = nodes[sid]
        out = {"id": sid, "phase": st["kind"], "clip": st["text"]}
        for k in ("strict", "goal", "hints", "suggested", "expected_nets", "expected_landing"):
            if k in st:
                out[k] = st[k]
        if st.get("why"):
            out["extras"] = {"why": st["why"]}
        if any(e["type"] == "GATHERS" and e["u"] == sid for e in inst["edges"]):  # the parts list it gathers
            out["items"] = [r["part"] for r in (les.get("parts_list") or {}).get("parts", [])]
        if st.get("program"):
            prog = st["program"]
            out["code"] = prog["file"]
        trouble += st.get("troubleshooting", [])
        tries += st.get("expected", [])
        at = {}
        for e in inst["edges"]:  # the step's holes: each join it makes, the new part's port -> where it goes
            if e["type"] == "MAKES" and e["u"] == sid:
                pe = edges[e["v"]]
                at[pe["u_port"]] = f"{pe['v']}:{pe['v_port']}"
        if at:
            out["at"] = at
        steps.append(out)
    extras = {}
    if les.get("how_it_works") is not None:
        extras["how_it_works"] = les["how_it_works"]
    if prog.get("walkthrough"):
        extras["code_walkthrough"] = prog["walkthrough"]
    if tries:
        extras["try_it"] = [t["text"] for t in sorted(tries, key=lambda t: t["index"])]
    if trouble:
        extras["troubleshooting"] = [t["text"] for t in sorted(trouble, key=lambda t: t["index"])]
    src = {k: v for k, v in les["source"].items() if k not in ("kind", "lesson_id")}
    lesson = {"id": les["source"].get("lesson_id"), "title": les["name"], "source": src,
              **{k: les[k] for k in ("description", "difficulty", "board", "tools_used", "parts_used", "generated",
                                     "made_from") if k in les},
              "code": prog.get("file"), "wokwi_diagram": phys.get("wokwi", {}).get("file"), "steps": steps,
              "extras": extras, "sketch_from": prog.get("sketch_from")}
    if (les.get("expected_result") or {}).get("final_check") is not None:
        lesson["final_check"] = les["expected_result"]["final_check"]
    graph = {"nodes": [{**n, "props": {k: v for k, v in n.get("props", {}).items() if k not in ADDED_NODE}}
                       for n in phys["nodes"]],
             "edges": [{**{k: v for k, v in e.items() if k not in ADDED_EDGE},
                        **{k: None for k in SOURCE_EDGE_FIELDS if k not in e}} for e in phys["edges"]]}
    w = phys.get("wokwi", {})
    by = {n["id"]: n for n in phys["nodes"]}
    parts = [{"id": i, **by[i]["props"]["wokwi"]} for i in w.get("order", []) if "wokwi" in by[i].get("props", {})]
    for p_ in parts:
        for k in ("connection", "colour", "route"):
            p_.pop(k, None)
    conns, seen = [], set()
    for n in phys["nodes"]:  # a wire: one connection between its two far ends
        ww = n.get("props", {}).get("wokwi", {})
        if "connection" in ww:
            conns.append(ww["connection"] + [ww["colour"], ww["route"]])
            seen.update(e["id"] for e in phys["edges"] if e["u"] == n["id"] and e["type"] == "joined")
    for e in phys["edges"]:
        if "wokwi" in e and e["id"] not in seen:
            conns.append(e["wokwi"]["ends"] + [e["wokwi"]["colour"], e["wokwi"]["route"]])
    conns += phys.get("wokwi_unmatched", [])
    diagram = {**{k: v for k, v in w.items() if k not in ("file", "order")}, "parts": parts, "connections": conns}
    return {"lesson.json": lesson, "graph.json": graph, "diagram.json": diagram, "stats.json": les.get("stats"),
            prog.get("file") or "code.ino": prog.get("text")}


# ---- the lesson record ------------------------------------------------------------------------------
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

    def lead(p):  # a connector's pin as the wire inside it: a Grove cable's jumper.3 and grove.3 are one lead
        part, port = p.split(":", 1)
        beh = (cards.get(types.get(part)) or {}).get("intrinsic_behaviour") or {}
        g = next((g for g in beh.get("internal_pass_through", []) + beh.get("internal_conducts", []) if port in g), None)
        return f"{part}:{'|'.join(sorted(g))}" if g else p
    via = collections.defaultdict(set)  # pairs that meet at a connector's pin (a header pin to the resistor, the same
    for pair in stored_pairs:           # pin to the LCD's A, or the two ends of one Grove lead) name the parts on both
        for p in pair:                  # sides as one net
            if folded(p):
                via[lead(p)] |= {q for q in pair if not folded(q)}
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


# ---- a learner's progress: done, next, and which column two parts share --------------------------
def _rules(cards, types):
    def rule(inst):
        return (lesson_store.definition(cards, types.get(inst, ""))[0] or {}).get("port_alias_rule") or {}
    return rule


def _where(cards, types, rule, inst, port):
    """A port as the check compares it: ('strip', 'bb1:12t') for a breadboard hole (any hole of the strip will do),
    ('port', 'uno:GND') for one of a group of the same pins, else ('port', 'uno:13'). From the part's stored groups in
    the catalogue (parts_db.connection: strips, rails, same pins); the card's old naming rule where it has none."""
    from graph.parts import part_catalogue
    found = part_catalogue.connection(lesson_store.definition(cards, types.get(inst, ""))[0], port)
    if found:
        kind, name = found
        return ("strip" if kind in ("strip", "rail") else "port"), f"{inst}:{name}"
    r = rule(inst)
    if r.get("mode") == "strip":
        return "strip", f"{inst}:{port.split('.', 1)[0]}"
    if r.get("mode") == "prefix":
        port = next((x for x in r.get("prefixes", []) if port.startswith(x)), port)
    return "port", f"{inst}:{port}"


def plan(inst, phys, cards):
    """Each step's joins: [(step, new part's port, kind, target)] with kind 'strip' (a breadboard strip) or
    'port' (a board pin or another part's port, GND pins as GND)."""
    types = {n["id"]: n["type"] for n in phys["nodes"]}
    rule = _rules(cards, types)
    edges = {e["id"]: e for e in phys["edges"]}
    out = []
    for e in inst["edges"]:
        if e["type"] != "MAKES":
            continue
        pe = edges.get(e["v"])
        if not pe or pe["type"] != "joined":
            continue
        p, (ti, tp) = f"{pe['u']}:{pe['u_port']}", (pe["v"], pe["v_port"])
        out.append((e["u"], p, *_where(cards, types, rule, ti, tp)))
    return out


def wires(phys, cards):
    """The wire instances of a circuit (jumper wires, cables): a wire has no place of its own."""
    return {n["id"] for n in phys["nodes"] if n["type"] == "jumper-wire" or
            (lesson_store.definition(cards, n["type"])[0] or {}).get("category") in ("wire", "cable")}


def join_ids(inst, phys):
    """{new part's port: the joined edge it goes in by}, for the joins the steps make."""
    edges = {e["id"]: e for e in phys["edges"]}
    return {f"{edges[e['v']]['u']}:{edges[e['v']]['u_port']}": e["v"] for e in inst["edges"]
            if e["type"] == "MAKES" and e["v"] in edges}


def aligns(joins, is_wire=lambda port: False, ids=None):
    """Position edges, per breadboard strip, from the first step (suggested order) that puts a port in it:
      a wire's end next to a part's leg   DEPENDS_ON: a wire has no place of its own, its end goes where that part
                                          went, so that step comes first (step-3's wire goes in the column of the
                                          resistor's left leg). `via` the two joins into the strip, as for any
                                          DEPENDS_ON: the evidence, not a second kind of dependency
      part next to part (or the wire first)  ALIGNS_WITH: they share the column, either may go in first"""
    ids = ids or {}
    by_strip = collections.defaultdict(list)
    for step, port, kind, target in joins:
        if kind == "strip":
            by_strip[target].append((step, port))
    deps, al = {}, {}
    for strip, rows in by_strip.items():
        first_step, first_port = rows[0]
        for step, port in rows[1:]:
            if step == first_step:
                continue
            if is_wire(port) and not is_wire(first_port):
                deps.setdefault((step, first_step), set()).update(x for x in (ids.get(port), ids.get(first_port)) if x)
            else:
                al.setdefault((step, first_step), []).append([port, first_port, strip.split(":", 1)[1]])
    return ([{"type": "DEPENDS_ON", "u": a, "v": b, "via": sorted(v, key=lambda x: int(x[1:]) if x[1:].isdigit() else x)}
             for (a, b), v in deps.items()] +
            [{"type": "ALIGNS_WITH", "u": a, "v": b, "ports": v} for (a, b), v in al.items()])


def progress(lesson_id, observed, moves=None, store=None):
    row, g = lesson_store._load(lesson_id, store)
    rec, inst, phys = g["lesson"], g["instruction"], g["physical"]
    if rec.get("lesson_type") != "arduino":
        raise ValueError("progress works for Arduino lessons only (LEGO needs `blocks` edges first)")
    cards = lesson_store._cards(lesson_store.PARTS)
    types = {n["id"]: n["type"] for n in phys["nodes"]}
    rule = _rules(cards, types)
    back = {v: k for k, v in (moves or {}).items()}  # actual -> planned
    joins = plan(inst, phys, cards)
    order = lesson_store._order(inst)
    # a wire's end takes its column from the part it goes next to: it never fixes a column itself
    wire_ids = wires(phys, cards)
    follows = {p for _, p, k, _ in joins if k == "strip" and p.split(":")[0] in wire_ids}
    nodes = {n["id"]: n for n in inst["nodes"]}

    def norm(port):  # an observed port as the plan names it: through the pin map; GND pins as GND; holes as strips
        port = back.get(port, port)
        i, p = port.split(":", 1)
        return _where(cards, types, rule, i, p)

    planned_ports = {p for _, p, _, _ in joins}
    seen = collections.defaultdict(set)  # a new part's port -> what it is joined to, as (kind, target)
    when = {}  # a new part's port -> when it went in (the order of `observed`)
    unexpected = []
    for n_obs, (a, b) in enumerate(observed):
        ka, ta = norm(a)
        kb, tb = norm(b)
        pa, pb = back.get(a, a), back.get(b, b)
        if pa in planned_ports or pa.split(":")[0] in {p.split(":")[0] for p in planned_ports}:
            seen[pa].add((kb, tb))
            when.setdefault(pa, n_obs)
        elif pb in planned_ports or pb.split(":")[0] in {p.split(":")[0] for p in planned_ports}:
            seen[pb].add((ka, ta))
            when.setdefault(pb, n_obs)
        else:
            unexpected.append((a, b))
    # parts with symmetric legs: try each way round, keep the one that breaks the fewest relations
    sym = {}  # from the catalogue's either-way-round groups (parts_db.either_way); the card's own field where none
    from graph.parts import part_catalogue
    for i, t in types.items():
        card = lesson_store.definition(cards, t)[0] or {}
        groups = part_catalogue.either_way(card) or [list(g) for g in (card.get("intrinsic_behaviour") or {}).get(
            "symmetric_port_groups") or []]
        for gr in groups:
            if i in wire_ids:
                continue  # a wire's two ends: each end follows the part it goes with already
            sym.setdefault(i, []).append(list(gr))
    choices = [[]]
    for i, groups in sym.items():
        for gr in groups:
            choices = [c + [(i, gr, perm)] for c in choices for perm in itertools.permutations(gr)]

    def evaluate(choice):
        swap = {f"{i}:{a}": f"{i}:{b}" for i, gr, perm in choice for a, b in zip(gr, perm)}
        got, at = {}, {}  # planned port -> its observed (kind, target)s, and when it went in
        for port, targets in seen.items():
            got[swap.get(port, port)] = targets
            at[swap.get(port, port)] = when.get(port, 0)
        strips = collections.defaultdict(list)  # planned strip -> [(when, observed strip)]
        for step, port, kind, target in joins:
            for k, t in got.get(port, ()):
                if kind == "strip" and k == "strip":
                    strips[target].append((port in follows, at[port], t))
        layout, problems = {}, []
        for s, obs in strips.items():  # a part's leg fixes the strip (the first in), never a wire's end before it
            layout[s] = min(obs)[1]
            layout[s] = min(obs)[2]
            if len({t for *_, t in obs}) > 1:
                problems.append(("split", s, sorted({t for *_, t in obs})))
        users = collections.defaultdict(list)
        for s, o in layout.items():
            users[o].append(s)
        for o, ss in users.items():
            if len(ss) > 1:
                problems.append(("short", o, sorted(ss)))
        return got, layout, problems

    got, layout, problems = min((evaluate(c) for c in choices), key=lambda r: len(r[2]))
    shorted = {s for kind, o, ss in problems if kind == "short" for s in ss}
    who = {p: s for s, p, _, _ in joins}
    errors = []
    for kind, a, b in problems:
        ports = [p for _, p, k, t in joins if k == "strip" and t in ([a] if kind == "split" else b) and p in got]
        if kind == "split":
            fixed = layout[a]
            late = [p for p in ports if not any(k == "strip" and t == fixed for k, t in got[p])]
            first = [p for p in ports if p not in late]
            errors.append(f"{', '.join(f'{p} ({who[p]})' for p in late)} must go in column {fixed.split(':', 1)[1]}, "
                          f"with {', '.join(f'{p} ({who[p]})' for p in first)}")
        else:
            errors.append(f"{', '.join(f'{p} ({who[p]})' for p in ports)} are all in column {a.split(':', 1)[1]}: "
                          f"they belong in different columns, so this joins circuits that must stay apart")
    steps = {}
    for sid in order:
        mine = [(p, k, t) for s, p, k, t in joins if s == sid]
        made, missing, wrong, targets = [], [], [], {}
        for p, k, t in mine:
            obs = got.get(p)
            if not obs:
                missing.append(p)
                taken = set(layout.values())
                if k == "strip" and t in layout:
                    targets[p] = f"{layout[t].split(':', 1)[1]} (where that strip's other part already is)"
                elif k == "strip":
                    targets[p] = ("any free column, e.g. " + t.split(":", 1)[1]) if t not in taken else \
                        f"any free column ({t.split(':', 1)[1]} is taken)"
                else:
                    targets[p] = t.split(":", 1)[1]
                continue
            ok = any(kk == k and (tt == t if k == "port" else (t in layout and layout[t] == tt and t not in shorted))
                     for kk, tt in obs)
            (made if ok else wrong).append(p)
        status = ("not a wiring step" if not mine else "wrong" if wrong else "done" if not missing
                  else "partly done" if made else "not started")
        steps[sid] = {"status": status, "made": made, "missing": missing, "wrong": wrong, "targets": targets,
                      "text": nodes[sid]["text"]}
    first_open = None
    for k, sid in enumerate(order):
        st = steps[sid]
        if st["status"] in ("not started", "partly done", "wrong", "too early") and first_open is None:
            first_open = sid
        open_ = lambda d: steps[d["v"]]["status"] in ("not started", "partly done", "wrong", "too early")  # noqa: E731
        # DEPENDS_ON is strict order: a step done before a step it depends on is not credited (too early)
        st["blocked_by"] = [d["v"] for d in inst["edges"] if d["type"] == "DEPENDS_ON" and d["u"] == sid and open_(d)
                            and st["status"] in ("done", "partly done")]
        if st["blocked_by"]:
            st["status"] = "too early"
            st["why"] = [f"{d['v']} first (via {', '.join(d['via'])})"
                         for d in inst["edges"] if d["type"] == "DEPENDS_ON" and d["u"] == sid and d["v"] in st["blocked_by"]]
        st["check_waits_for"] = sorted({d["v"] for d in inst["edges"] if d["type"] in ("CHECK_NEEDS", "ALIGNS_WITH")
                                        and d["u"] == sid and open_(d)})  # a shared column: the check needs it too
        st["early"] = st["status"] in ("done", "partly done") and any(
            steps[o]["status"] in ("not started", "partly done", "wrong") for o in order[:k])
    return {"lesson_id": lesson_id, "steps": steps, "next": first_open, "errors": errors, "unexpected": unexpected,
            "to_fix": [s for s in order if steps[s]["status"] == "wrong"],
            "layout": {s.split(":", 1)[1]: o.split(":", 1)[1] for s, o in layout.items()},
            "done": [s for s in order if steps[s]["status"] == "done"]}
