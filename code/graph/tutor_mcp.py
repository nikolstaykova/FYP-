"""The lesson data as tools for a tutoring agent.

What it is   an MCP server (stdio, read-only) whose tools return exactly what the lesson store holds, so an agent
             leading a learner never has to guess (DATA_STRUCTURE.md §4.2).
Used for     a tutor agent that leads a learner through a lesson, answers their questions and works out where they
             are from what they have built.
Where        started by the agent's MCP configuration (`claude -p --mcp-config ...`): python -m graph.tutor_mcp.
             Reads data/lessons/store through lesson_store.py; progress through arduino/graphs.py; part search
             through parts/cards.py (its search).

  lessons()                         the lesson catalogue
  lesson(lesson_id)                 the lesson record: about, how it works, parts list, expected result,
                                    troubleshooting that spans steps, what to try next, the steps in order
  step(lesson_id, step_id)          one step: text, goal, hints, why, its fixes, what it places and makes (ports),
                                    what it depends on and why, what it shares a column with, previous / next, and for
                                    the upload step the sketch and where it uses each board pin
  search_parts(query, domain)       free-text search over the catalogue, each hit with maker, model, chip and ports
  part(type_id)                     a part definition: card and metadata (description, specs, joins, polarity, what a
                                    power/ground swap does, what each pin can do)
  instance(lesson_id, instance_id)  one part in one lesson: its properties, the step that places it, its joins
  substitutions(lesson_id)          the pins the code may move to (and why others cannot), what each part may differ in
  progress(lesson_id, observed, moves)  where a learner is from what they have wired (arduino/graphs.py)
"""
import json
import sys

from graph import lesson_store
from graph.arduino import graphs


def _graphs(lesson_id):
    row, g = lesson_store._load(lesson_id)
    return row, g["lesson"] or {}, g["instruction"] or {"nodes": [], "edges": []}, g["physical"] or {"nodes": [], "edges": []}


def lessons():
    return [{"lesson_id": r["lesson_id"], "name": r["name"], "type": r["lesson_type"]} for r in lesson_store.catalogue()["lessons"]]


def lesson(lesson_id):
    row, rec, inst, phys = _graphs(lesson_id)
    order = lesson_store._order(inst)
    nodes = {n["id"]: n for n in inst["nodes"]}
    keep = ("name", "link", "lesson_type", "difficulty", "description", "how_it_works", "notes", "try_next",
            "troubleshooting", "expected_result", "parts_list")
    out = {k: rec[k] for k in keep if rec.get(k) not in (None, [], {})}
    if out.get("parts_list"):  # a row without a count (an Arduino gather list): its count is its instances, read here
        out["parts_list"] = {**out["parts_list"], "parts": [
            {**r, "count": r["count"] if r.get("count") is not None else len(r.get("instances", [])),
             **({"count_from": "the instances it covers"} if r.get("count") is None else {})}
            for r in out["parts_list"].get("parts", [])]}
    out["steps"] = [{"id": s, "kind": nodes[s]["kind"], "text": nodes[s]["text"]} for s in order]
    return out


def _port_text(e):
    return f"{e['u']}:{e['u_port']} -> {e['v']}:{e['v_port']}"


def step(lesson_id, step_id):
    row, rec, inst, phys = _graphs(lesson_id)
    nodes = {n["id"]: n for n in inst["nodes"]}
    if step_id not in nodes:
        return {"error": f"no step {step_id}; steps are {lesson_store._order(inst)}"}
    s = dict(nodes[step_id])
    edges = {e["id"]: e for e in phys["edges"]}
    order = lesson_store._order(inst)
    i = order.index(step_id) if step_id in order else None
    out = {k: v for k, v in s.items() if k not in ("program",)}
    out["previous"] = order[i - 1] if i else None
    out["next"] = order[i + 1] if i is not None and i + 1 < len(order) else None
    rows = (rec.get("parts_list") or {}).get("parts", [])
    out["places"] = [e["v"] if not e["v"].startswith("lesson:parts_list/") else  # booklet lessons: parts-list rows
                     {**{k: rows[int(e["v"].rsplit("/", 1)[1])].get(k) for k in ("part", "colour", "name")},
                      "count": e.get("count"), "where": e.get("where")}
                     for e in inst["edges"] if e["type"] == "PLACES" and e["u"] == step_id]
    if s.get("source"):  # a booklet lesson's step: where in the booklet it is
        out["booklet"] = {"page": s["source"]["page"], "picture": s["source"]["picture"]}
    out["makes"] = [_port_text(edges[e["v"]]) for e in inst["edges"] if e["type"] == "MAKES" and e["u"] == step_id]
    out["depends_on"] = [{"step": e["v"], "via": [_port_text(edges[x]) for x in e["via"] if x in edges]}
                         for e in inst["edges"] if e["type"] == "DEPENDS_ON" and e["u"] == step_id]
    out["shares_a_column_with"] = [{"step": e["v"], "ports": e["ports"]} for e in inst["edges"]
                                   if e["type"] == "ALIGNS_WITH" and step_id in (e["u"], e["v"])]
    if any(e["type"] == "GATHERS" and e["u"] == step_id for e in inst["edges"]):
        out["gathers"] = (rec.get("parts_list") or {}).get("parts", [])
    if s.get("program"):
        p = s["program"]
        out["program"] = {"file": p["file"], "code": p["text"], "board": p.get("board_instance"),
                          "uses_pins": [{"line": l["line"], "token": l["token"], "port": l["port"], "needs": l["needs"]}
                                        for l in p.get("links", []) if l["kind"] == "code"],
                          "walkthrough": p.get("walkthrough", [])}
    return out


def part(type_id):
    cards = lesson_store._cards(lesson_store.PARTS)
    card, how = lesson_store.definition(cards, type_id)
    if not card:
        return {"error": f"no part {type_id} in the catalogue"}
    m = card.get("metadata") or {}
    out = {"type_id": card["part_type_id"], "found_as": how, "name": card.get("display_name"), "domain": m.get("domain"),
           "category": card.get("category"), "polarized": (card.get("intrinsic_behaviour") or {}).get("is_polarized"),
           "electrical": card.get("electrical"), "note": card.get("note"),
           "ports": [{k: p.get(k) for k in ("id", "kind", "can", "builtin", "reserved", "same_as") if p.get(k) is not None}
                     for p in card.get("ports", [])][:60]}
    out.update({k: m[k] for k in ("description", "material", "specs", "basis", "joins", "learner_tips", "reverse_power",
                                  "substitutes", "status") if m.get(k) not in (None, [], {})})
    return out


_INDEX = []


def search_parts(query, domain=None, limit=8):
    """Free-text search over the parts catalogue (ids, names, aliases, category; search.py): each hit with what tells
    parts apart (maker, model, chip, ports)."""
    from graph.parts.cards import TextIndex
    cards = lesson_store._cards(lesson_store.PARTS)
    if not _INDEX:
        idx = TextIndex({"part_type_id": 10, "aliases": 8, "display_name": 5, "category": 2})
        for t, c in cards.items():
            idx.add(t, c)
        _INDEX.append(idx)
    out = []
    for h in _INDEX[0].search(query, limit=40):
        c = cards[h.id]
        m = c.get("metadata") or {}
        if domain and m.get("domain") != domain:
            continue
        sp = m.get("specs") or {}
        out.append({"type_id": h.id, "name": c.get("display_name"), "category": c.get("category"),
                    "domain": m.get("domain"), "maker": sp.get("maker"), "model": sp.get("model"), "chip": sp.get("chip"),
                    "aliases": c.get("aliases", [])[:6], "ports": len(c.get("ports") or []),
                    "match": round(h.coverage, 2)})
        if len(out) >= limit:
            break
    return out


def instance(lesson_id, instance_id):
    row, rec, inst, phys = _graphs(lesson_id)
    n = next((x for x in phys["nodes"] if x["id"] == instance_id), None)
    if not n:
        return {"error": f"no instance {instance_id}; instances are {[x['id'] for x in phys['nodes']]}"}
    return {"id": instance_id, "type": n["type"], "label": n.get("label"), "props": n.get("props", {}),
            "placed_by": [e["u"] for e in inst["edges"] if e["type"] == "PLACES" and e["v"] == instance_id],
            "joins": [_port_text(e) + f" ({e['type']}" + (f", {e['method']}, {e['holds_by']}, undo by {e['reversible']}"
                                                         if e["type"] == "joined" else "") + ")"
                      for e in phys["edges"] if instance_id in (e["u"], e["v"]) and e["type"] != "electrical"]}


def substitutions(lesson_id):
    row, rec, inst, phys = _graphs(lesson_id)
    return rec.get("substitutions") or {"note": "this lesson has no substitution data"}


def progress(lesson_id, observed, moves=None):
    pairs = [tuple(x.split("-", 1)) if isinstance(x, str) and "->" not in x else
             tuple(p.strip() for p in x.split("->")) if isinstance(x, str) else tuple(x) for x in observed]
    r = graphs.progress(lesson_id, pairs, moves or {})
    return {"next": r["next"], "errors": r["errors"], "to_fix": r["to_fix"], "unexpected": r["unexpected"],
            "layout (planned column -> learner's column)": r["layout"],
            "steps": {s: {k: v for k, v in st.items() if k in ("status", "early", "blocked_by", "why", "check_waits_for",
                                                                  "targets", "wrong", "missing")}
                      for s, st in r["steps"].items()}}


def _tool(name, desc, props, required):
    return {"name": name, "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": required}}


S = {"type": "string"}
TOOLS = [
    _tool("lessons", "List the lessons in the store (id, name, type).", {}, []),
    _tool("lesson", "A lesson's record: about, how it works, parts list, expected result, troubleshooting, try next, "
                    "and its steps in order.", {"lesson_id": S}, ["lesson_id"]),
    _tool("step", "One step of a lesson: text, goal, hints, why, fixes, what it places and the joins it makes (ports), "
                  "what must come first and why, previous/next; for the upload step the sketch and its pin uses.",
          {"lesson_id": S, "step_id": S}, ["lesson_id", "step_id"]),
    _tool("part", "A part definition from the catalogue (e.g. led, resistor, servo, arduino-uno, lego-3021): "
                  "description, specifications, how its joins hold and come apart, polarity, what swapping power and "
                  "ground does, what each pin can do.", {"type_id": S}, ["type_id"]),
    _tool("search_parts", "Search the parts catalogue by name, model or alias (e.g. 'uno wifi rev2', 'red led', "
                          "'dht11'). Each hit has its type id, name, maker, model, chip and number of ports.",
          {"query": S, "domain": {"type": "string", "enum": ["arduino", "lego"]}}, ["query"]),
    _tool("instance", "One part in one lesson (e.g. led1, r1, wire2, b4): its properties, the step that places it, "
                      "its joins.", {"lesson_id": S, "instance_id": S}, ["lesson_id", "instance_id"]),
    _tool("substitutions", "What may differ from the lesson and still be right: pins the code may move to (and why "
                           "the others cannot), what each part may differ in.", {"lesson_id": S}, ["lesson_id"]),
    _tool("progress", "Where a learner is, from what they have wired, in the order it went in. observed: list of "
                      "'port -> port' strings with the lesson's instance ids, e.g. 'r1:1 -> bb1:12t.a'. moves: the "
                      "learner's pin map, e.g. {\"uno:13\": \"uno:12\"}.",
          {"lesson_id": S, "observed": {"type": "array", "items": S}, "moves": {"type": "object"}},
          ["lesson_id", "observed"]),
]
FUNCS = {"lessons": lessons, "lesson": lesson, "step": step, "part": part, "instance": instance, "search_parts": search_parts,
         "substitutions": substitutions, "progress": progress}


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:
            continue
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "lessons", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call" and params.get("name") in FUNCS:
            try:
                out = FUNCS[params["name"]](**(params.get("arguments") or {}))
                result = {"content": [{"type": "text", "text": json.dumps(out)[:60000]}], "isError": False}
            except Exception as e:  # the agent gets an answer, never a hang
                result = {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown {method}"}}),
                  flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
