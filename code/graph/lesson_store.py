"""The lesson store: every made lesson as its record and graphs, checked, in one catalogue.

What it is   turns a lesson made by any route into what is stored: the lesson record, the steps graph
             (instruction.json) and, where the source has one, the physical graph (physical.json); assembles a
             stored lesson back into one view with its checks (ready or not, and why); keeps the catalogue
             (data/lessons/store/catalogue.json). Also the lesson record's helpers (the parts-list match, circuit
             nets, the final-check comparison) and the join table (one vocabulary for physical edges, LEGO and
             Arduino alike, GRAPH_SPEC §5).
Used for     the last step of making any lesson (register), and every read of a lesson (assemble: the tutor, the
             validator, the review pages).
Where        the command line after a lesson is made: python -m graph.lesson_store build lego 7613-1 / build
             arduino blink / validate (every lesson and part against the rules: the validator, below); lego_booklet/pdf_lesson.py registers booklet lessons; read by tutor_mcp.py,
             arduino/graphs.py, arduino/part_review.py, parts/part_catalogue.py and
             parts/part_metadata.py.

Every fact is stored once (DATA_STRUCTURE.md §2, rule 5): what follows from stored facts (the previous step, the
first step, a step's pins, which instances the learner gathers) is worked out when it is read, never stored twice.

  catalogue.json        the index: one row per lesson, its id, name, type and the path of its lesson record
  <id>/lesson.json      the lesson record: what the lesson says as a whole, and the path of each graph it HAS (a missing
                        one is null, never an empty graph)
  <id>/instruction.json what the learner does and in what order. Nodes are steps; edges are
                          NEXT_STEP   step -> the next step (the previous step is its reverse, not stored)
                          DEPENDS_ON  step -> a step that must come first, `via` the joins that make it so: one goes
                                      onto a part that step puts out, or a wire's end goes next to a part that step
                                      put in (the wire's join and the part's join into the same strip)
                          CHECK_NEEDS step -> a step whose part its check names (no order: the check waits for it)
                          ALIGNS_WITH step -> a step whose part its part must share a breadboard strip with (position,
                                      not order: whichever goes in first fixes the strip)
                          PLACES      step -> a part instance it puts in place (ACTS_ON in the first design)
                          MAKES       step -> a join (physical `joined` edge) it makes; its `electrical` twin follows
                          GATHERS     the gather step -> the lesson's parts list (whose rows point at the instances)
                          PROGRAMS    the upload step -> the board it loads the sketch onto (the pins: its code links)
  <id>/physical.json    the part instances of this one assembly and the connections between them (GRAPH_SPEC §4-5).
                        A node's `type` is a DEFINITION in the one parts catalogue (code/graph/parts/parts.json):
                        three identical pins are three nodes of one type
  <id>/document.json    (PDF-only lessons, later) pages, sections, steps and source references; no physical graph

Nothing here is invented: the LEGO physical graph is the set's 3D model (the same ids b1.. as its lesson), the
Arduino one is the circuit graph checked by laws E1-E11, and every PLACES / MAKES / DEPENDS_ON edge points at
something in the physical graph. In the physical graph `u` is always the side that goes in (a stud, pin, lead, wire
end, a bar into a clip) and `v` the side that takes it. `assemble` walks catalogue -> instruction graph -> physical graph -> part catalogue and
returns the lesson as one object, with checks that every link resolves and how long each lookup took.

  python -m graph.lesson_store build lego 2134-1
  python -m graph.lesson_store build arduino blink
  python -m graph.lesson_store show 2134-1
  python -m graph.lesson_store mermaid blink     (the graphs as a Mermaid diagram, for DATA_STRUCTURE.md)
  python -m graph.lesson_store audit blink 2134-1 (rebuild the source files from the network: lossless?)
Writes data/lessons/store/.

In this file, besides the store itself:
  the lesson record   what a lesson says about itself as a whole, and where each piece of its content belongs
                      (DATA_STRUCTURE.md §3.2); the parts-list match, circuit nets, the final-check comparison
  the join table      one vocabulary for physical edges, LEGO and Arduino alike (GRAPH_SPEC §5)
"""

import argparse
import collections
import json
import os
import pathlib
import re
import time
from graph import lesson_store


# ---- the store ------------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[2]
STORE = pathlib.Path(os.environ["LESSON_STORE"]) if os.environ.get("LESSON_STORE") else ROOT / "data" / "lessons" / "store"
PARTS = "code/graph/parts/parts.json"  # the one parts catalogue, LEGO and Arduino (parts/part_catalogue.py)
PART_CATALOGUES = {"lego": PARTS, "arduino": PARTS}
KINDS = ("lesson", "instruction", "physical", "document")  # the lesson record first: it points to the graphs


def _read(path, default=None):
    path = pathlib.Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def catalogue(store=None):
    return _read((store or STORE) / "catalogue.json", {"lessons": []})


def register(entry, graphs, store=None):
    """Save a lesson's graphs and its catalogue row (replacing any earlier row of the same id).
    graphs: {kind: graph or None}; only the kinds the lesson has get a file and a path."""
    store = store or STORE
    d = store / entry["lesson_id"]
    d.mkdir(parents=True, exist_ok=True)
    from graph.parts.lego import lego_ids
    lego_ids.unprint_graphs(graphs)  # a printed piece is its plain piece with a print (one card per design)
    reps = {}
    for kind in KINDS:  # the graphs first, so the lesson record can point to them
        g = graphs.get(kind)
        reps[kind] = None if g is None else f"{entry['lesson_id']}/{kind}.json"
    if graphs.get("lesson") is not None:
        graphs["lesson"]["graphs"] = {k: v for k, v in reps.items() if k != "lesson"}
    for kind in KINDS:
        if graphs.get(kind) is not None:
            (d / f"{kind}.json").write_text(json.dumps(graphs[kind], indent=1))
    row = {"lesson_id": entry["lesson_id"], "name": entry["title"], "lesson_type": entry["lesson_type"],
           "lesson": reps["lesson"]}  # the index; the record holds the rest
    from graph.filelock import locked
    with locked(store / "catalogue.json"):  # lessons made side by side (a batch) each add their row
        cat = catalogue(store)
        cat["lessons"] = [r for r in cat["lessons"] if r["lesson_id"] != entry["lesson_id"]] + [row]
        (store / "catalogue.json").write_text(json.dumps(cat, indent=1))
    sync_db(entry["lesson_id"], store)
    return row


def sync_db(lesson_id, store=None):
    """The saved lesson into the database too (graph.db), when one is set up in .env. Never stops a save: no
    database, or one that is paused or unreachable, only prints a note (`./pinpoint db load <id>` catches up).
    Off with PINPOINT_DB_SYNC=0 (tests, and lessons saved to another store)."""
    if os.environ.get("PINPOINT_DB_SYNC", "1") == "0" or (store and pathlib.Path(store) != STORE):
        return None
    try:
        from graph import db
        db.settings()
    except Exception:
        return None  # no database set up
    try:
        with db.driver() as d:
            return db.load_lesson(d, lesson_id, store)
    except Exception as e:  # paused, offline, wrong password
        print(f"  database: {lesson_id} not updated ({type(e).__name__}); run ./pinpoint db load {lesson_id}")
        return None


STEP_KINDS = ("step", "gather", "build", "upload", "overview")  # the NEXT_STEP chain; other nodes hang off it


def _rebrickable(set_id):
    """(set name, inventory rows) from the offline Rebrickable dump, or (None, None)."""
    try:
        from graph.parts.lego import inventory as rb
        name = next((r["name"] for r in rb._rows("sets") if r["set_num"] == set_id), None)
        return name, rb.RebrickableDump.set_parts(set_id, minifigs=True)
    except (OSError, KeyError):
        return None, None


def card_missing(graphs):
    """LEGO: a card for each part type of the lesson's graphs and parts list (a minifigure's legs and torso are only
    there) the catalogue has no definition for (Rebrickable and LDraw by code, Claude for what code cannot
    place), the same step as the booklet route (pdf_lesson.card_parts)."""
    from graph.lego_booklet.pdf_lesson import card_parts
    from graph.parts.cards import CardStore, add_used_ports
    from graph.parts import part_catalogue
    types = {n["type"] for g in graphs.values() if g for n in g.get("nodes", []) if str(n.get("type", "")).startswith("lego-")}
    types |= {r["part"] for r in ((graphs.get("lesson") or {}).get("parts_list") or {}).get("parts", []) if str(r.get("part", "")).startswith("lego-")}
    base = lambda t: (re.match(r"^(lego-\d+[a-z]?)p[a-z0-9]+$", t) or [None, t])[1]  # noqa: E731  a print: its design
    out = card_parts([{"part": base(t)} for t in sorted(types)])
    if graphs.get("physical"):  # and the ports the model joins the drafted cards by
        from graph.filelock import locked
        with locked(ROOT / "code" / "graph" / "parts" / "lego" / "cards_lego.json"):
            added = add_used_ports(CardStore(ROOT / "code" / "graph" / "parts" / "lego" / "cards_lego.json"), graphs["physical"])
        if added:
            part_catalogue.build()
            _CARDS.clear()
        out["ports_added"] = sum(len(v) for v in added.values())
    return out


def _rel(path):
    """A source path as stored: relative to the repo when inside it."""
    path = pathlib.Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _chain(step_ids):
    """The step order: NEXT_STEP a -> b. The previous step is its reverse (worked out on reading, not stored)."""
    return [{"type": "NEXT_STEP", "u": a, "v": b} for a, b in zip(step_ids, step_ids[1:])]


def _acts(acts, physical):
    """PLACES (step -> instance) and MAKES (step -> joined edge) from {step: [instance or edge ids]}. An `electrical`
    edge is not made by a step: it follows from the joined edge between the same ports."""
    kinds = {e["id"]: e["type"] for e in physical["edges"]}
    nodes = {n["id"] for n in physical["nodes"]}
    out = []
    for s, ts in acts.items():
        for t in ts:
            if t in nodes:
                out.append({"type": "PLACES", "u": s, "v": t})
            elif kinds.get(t) == "joined":
                out.append({"type": "MAKES", "u": s, "v": t})
    return out


def _depends(acts, added_by, physical, needs=None):
    """DEPENDS_ON and CHECK_NEEDS edges from the evidence: a step depends on the step that puts out a part one of
    its joins goes onto (`via` the physical edges); its check needs the step that places a part the check names
    (`parts`)."""
    edges = {e["id"]: e for e in physical["edges"] if e["type"] == "joined"}  # a join's electrical twin is no evidence
    out = {}
    for step, targets in acts.items():
        for t in targets:
            if t not in edges:
                continue
            for end in (edges[t]["u"], edges[t]["v"]):
                src = added_by.get(end)
                if src and src != step:
                    out.setdefault((step, src), []).append(t)
        for part in (needs or {}).get(step, ()):
            src = added_by.get(part)
            if src and src != step:
                out.setdefault((step, src), []).append(f"check:{part}")
    # DEPENDS_ON only for real order: a join of the step goes onto a part the other step puts out, so that step must
    # come first. CHECK_NEEDS when only the step's check names a part the other step places: no order at all (the
    # LED can go in before the resistor); the check completes once that part is in
    edges_out = []
    for (a, b), v in out.items():
        joins = sorted({x for x in v if not x.startswith("check:")})
        checks = sorted({x[len("check:"):] for x in v if x.startswith("check:")})
        if joins:
            edges_out.append({"type": "DEPENDS_ON", "u": a, "v": b, "via": joins})
        if checks and not joins:  # a step it already depends on needs no second edge
            edges_out.append({"type": "CHECK_NEEDS", "u": a, "v": b, "parts": checks})
    return edges_out


def _load(lesson_id, store=None):
    """(the lesson's index row with its record's facts, {kind: graph}): index -> lesson record -> the graphs it lists.
    `representations` is put together here from the record's paths; it is not stored a second time."""
    store = store or STORE
    row = next((r for r in catalogue(store)["lessons"] if r["lesson_id"] == lesson_id), None)
    if row is None:
        raise KeyError(f"{lesson_id} is not in the lesson catalogue")
    rec = _read(store / row["lesson"]) if row.get("lesson") else None
    reps = {"lesson": row.get("lesson"), **((rec or {}).get("graphs") or {})}
    info = {**row, "title": (rec or {}).get("name", row.get("name")), "source": (rec or {}).get("source"),
            "derived_from": (rec or {}).get("derived_from"), "representations": reps}
    return info, {k: (rec if k == "lesson" else _read(store / v)) if v else None for k, v in reps.items()}


def _order(inst):
    """The steps in the order a learner does them. One NEXT_STEP chain: from the step nothing comes before. A booklet
    lesson with several builds (SHOWS, STARTS): the overview, then each build in its SHOWS order, from the step it
    STARTS along NEXT_STEP, a step's own sub-build (the chain the step STARTS) just before the step itself."""
    nxt = {e["u"]: e["v"] for e in inst["edges"] if e["type"] == "NEXT_STEP"}
    shows = sorted((e for e in inst["edges"] if e["type"] == "SHOWS"), key=lambda e: e.get("order", 0))
    if shows:
        starts = collections.defaultdict(list)
        for e in inst["edges"]:
            if e["type"] == "STARTS":
                starts[e["u"]].append(e["v"])
        out = [shows[0]["u"]]

        def walk(first):
            cur = first
            while cur and cur not in out:
                for sub in starts.get(cur, []):
                    walk(sub)
                out.append(cur)
                cur = nxt.get(cur)
        for e in shows:
            for first in starts.get(e["v"], []):
                walk(first)
        return out
    steps = [n["id"] for n in inst["nodes"] if n["kind"] in STEP_KINDS]
    cur = next((i for i in steps if i not in set(nxt.values())), None)
    out = []
    while cur and cur not in out:
        out.append(cur)
        cur = nxt.get(cur)
    return out


def _diff(a, b, path="", out=None, unordered=()):
    """Every place two JSON values differ: [(path, source, rebuilt)]. Lists named in `unordered` compare as sets."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in b:
                out.append((f"{path}.{k}", a[k], "<missing>"))
            elif k not in a:
                out.append((f"{path}.{k}", "<missing>", b[k]))
            else:
                _diff(a[k], b[k], f"{path}.{k}", out, unordered)
    elif isinstance(a, list) and isinstance(b, list):
        if path.rsplit(".", 1)[-1] in unordered:
            key = lambda x: json.dumps(x, sort_keys=True)  # noqa: E731
            a, b = sorted(a, key=key), sorted(b, key=key)
        if len(a) != len(b):
            out.append((path, f"{len(a)} items", f"{len(b)} items"))
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, unordered)
    elif a != b and not (isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-9):
        out.append((path, a, b))
    return out


def audit(lesson_id, store=None):
    """Is the network lossless? Rebuild the lesson's original files from the network alone and compare them, field
    by field, with the files it was made from. Returns {file: [(path, source, rebuilt)]}: empty lists mean every
    attribute of the source is in the network (as a node, an edge or a property), or follows from its edges."""
    from graph.arduino.graphs import export_arduino  # each route writes its own form back (imported here:
    from graph.lego_3d.graphs import export_lego    # the routes' graph builders import this module)
    row, _ = _load(lesson_id, store)
    src = ROOT / row["derived_from"]
    rebuilt = (export_lego if row["lesson_type"] == "lego" else export_arduino)(lesson_id, store)
    out = {}
    for name, value in rebuilt.items():
        f = src.parent / name
        if not f.exists():
            out[name] = [("", "<no source file>", "rebuilt")]
            continue
        orig = f.read_text() if not name.endswith(".json") else json.loads(f.read_text())
        out[name] = _diff(orig, value, unordered=("parts", "connections"))
    return out


_CARDS = {}


def _cards(rel):
    if rel not in _CARDS:
        _CARDS[rel] = json.loads((ROOT / rel).read_text())
    return _CARDS[rel]


def definition(cards, type_id):
    """The shared definition for an instance type, and how it was found. A printed LEGO piece (3003pe2) is its base
    design (3003) with the print as an instance property; a sized type (resistor-220) is its family."""
    if type_id in cards:
        return cards[type_id], "exact"
    from graph.parts.cards import resolve
    if resolve(type_id) in cards:
        return cards[resolve(type_id)], f"renamed {resolve(type_id)} (the same part, merged)"
    m = re.match(r"^(lego-\d+[a-z]?)(p[a-z0-9]+)$", type_id)
    if m and m.group(1) in cards:
        return cards[m.group(1)], f"base design {m.group(1)} (print is an instance property)"
    fam = type_id.rsplit("-", 1)[0]
    if fam != type_id and fam in cards:
        return cards[fam], f"family {fam} (value is an instance property)"
    return None, "missing"


def port_match(d, port):
    """How an edge's port is found on its definition: 'exact' (id or alias), 'pattern' (a named family such as the
    breadboard's '<column><bank>.<row>'), 'kind' (only its kind: LEGO 'stud.1' against the card's 'stud.1.1'), or None."""
    ids = [p["id"] for p in d["ports"]]
    if port in ids or any(port in p.get("aliases", []) for p in d["ports"]):
        return "exact"
    for i in ids:
        if "<" in i and re.fullmatch(re.sub(r"<[^>]+>", "[A-Za-z0-9]+", re.escape(i)), port):
            return "pattern"
    if any(i.split(".")[0] == port.split(".")[0] for i in ids):
        return "kind"
    return None


def _name(d, n):
    """An instance's name: its definition's, with the instance's own value (a resistor's ohms) where it has one."""
    if not d:
        return None
    v = n.get("props", {}).get("value")
    return f"{d.get('category', '').capitalize()} {v}".strip() if v else d.get("display_name")


def single_facts(inst, phys, rec):
    """Every fact once (DATA_STRUCTURE.md §2, rule 5): [problem] for each one stated twice."""
    out, seen = [], collections.Counter((e["type"], e["u"], e["v"]) for e in inst["edges"])
    out += [f"{t} {u} -> {v} is stored {n} times" for (t, u, v), n in seen.items() if n > 1]
    linked = {(e["u"], e["v"]) for e in inst["edges"] if e["type"] in ("DEPENDS_ON", "ALIGNS_WITH")}
    out += [f"CHECK_NEEDS {e['u']} -> {e['v']} repeats a DEPENDS_ON or ALIGNS_WITH" for e in inst["edges"]
            if e["type"] == "CHECK_NEEDS" and (e["u"], e["v"]) in linked]
    kinds = {e["id"]: e["type"] for e in phys["edges"]}
    out += [f"MAKES {e['u']} -> {e['v']}: a step makes joins, not {kinds.get(e['v'])} edges" for e in inst["edges"]
            if e["type"] == "MAKES" and kinds.get(e["v"]) != "joined"]
    stale = {"PREVIOUS_STEP": "the reverse of NEXT_STEP", "ACTS_ON": "PLACES or MAKES"}
    out += [f"{t} edges are not stored: {why}" for t, why in stale.items() if any(e["type"] == t for e in inst["edges"])]
    for k, why in (("port", "the join's own u_port"), ("pins", "the program's code links"), ("target", "PLACES or MAKES")):
        if any(k in e for e in inst["edges"] if e["type"] in ("PLACES", "MAKES", "PROGRAMS")):
            out.append(f"an edge stores `{k}`, which is {why}")
    if any("direction" in e for e in phys["edges"]):
        out.append("a physical edge stores `direction`: u is always the side that goes in")
    for k in ("first_step", "graphs_also_in_catalogue"):
        if k in rec:
            out.append(f"the lesson record stores `{k}`, which follows from its graphs")
    if any("uses_definitions" in n for n in inst["nodes"]):
        out.append("a step stores `uses_definitions`: the parts list is in the lesson record")
    return out


def assemble(lesson_id, store=None):
    """Catalogue row -> the graphs it lists -> the part definitions: the lesson as one object, with every link
    checked and the time each stage took."""
    store = store or STORE
    t = {}
    t0 = time.perf_counter()
    row, graphs = _load(lesson_id, store)
    t["load_ms"] = (time.perf_counter() - t0) * 1000
    problems = [f"catalogue lists {k} at {p} but the file is missing" for k, p in row["representations"].items()
                if p and graphs[k] is None]

    t1 = time.perf_counter()
    phys, inst = graphs.get("physical"), graphs.get("instruction")
    nodes = {n["id"]: n for n in (phys or {}).get("nodes", [])}
    edges = {e["id"]: e for e in (phys or {}).get("edges", [])}
    cards = _cards(phys["part_catalogue"]) if phys else {}
    defs, how_found = {}, collections.Counter()
    for n in nodes.values():
        d, how = definition(cards, n["type"])
        how_found["exact" if how == "exact" else "missing" if how == "missing" else "fallback"] += 1
        defs[n["id"]] = (d, how)
        if d is None:
            problems.append(f"{n['id']}: no definition for type {n['type']} in {phys['part_catalogue']}")
    ports = collections.Counter()
    for e in edges.values():
        for end, port in ((e["u"], e.get("u_port")), (e["v"], e.get("v_port"))):
            d = defs.get(end, (None,))[0]
            if port and d and d.get("ports"):
                how = port_match(d, port)
                ports[how or "not found"] += 1
                if how is None:
                    problems.append(f"{e['id']}: port {end}:{port} is not on {nodes[end]['type']}")
    # drafted metadata (part_metadata.py) beside each definition; an edge's missing join attributes from it
    meta = lambda d: (d or {}).get("metadata") if ((d or {}).get("metadata") or {}).get("description") else None  # noqa: E731
    about = {}
    for i, (d, how) in defs.items():
        m = meta(d)
        if m:
            about[i] = {"domain": m["domain"], "description": m["description"], "material": m["material"],
                        "specifications": {k: v for k, v in (m.get("specs") or {}).items() if v not in (None, [], "")},
                        "tips": m["learner_tips"], "status": m["status"], "checks_failed": m["checks_failed"]}
    filled = 0  # join attributes come from the one join table (the join table below), not from part metadata
    t["resolve_parts_ms"] = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    out_steps = []
    if inst:
        by = collections.defaultdict(list)
        for e in inst["edges"]:
            by[(e["type"], e["u"])].append(e)
        nxt = {e["u"]: e["v"] for e in inst["edges"] if e["type"] == "NEXT_STEP"}
        step_nodes = [s for s in inst["nodes"] if s["kind"] in STEP_KINDS]
        others = {s["id"]: s for s in inst["nodes"] if s["kind"] not in STEP_KINDS}
        heads = [s["id"] for s in step_nodes if s["id"] not in set(nxt.values())]
        first = [e["v"] for e in inst["edges"] if e["type"] == "FIRST_STEP"]
        if any(e["type"] == "SHOWS" for e in inst["edges"]):  # several builds: each its own chain, from its STARTS
            order = _order(inst)
        else:
            if first and first != heads[:1]:
                problems.append(f"FIRST_STEP is {first}, the chain starts at {heads}")
            if len(heads) != 1:
                problems.append(f"NEXT_STEP is not one chain (starts: {heads})")
            order, cur = [], heads[0] if heads else None
            while cur and cur not in order:
                order.append(cur)
                cur = nxt.get(cur)
        if len(order) != len(step_nodes):
            problems.append(f"NEXT_STEP reaches {len(order)} of {len(step_nodes)} steps")
        previous = {b: a for a, b in zip(order, order[1:])}  # the reverse of NEXT_STEP, worked out here
        pos = {s: i for i, s in enumerate(order)}
        step_by = {s["id"]: s for s in inst["nodes"]}
        added, made = collections.Counter(), collections.Counter()
        for sid in order:
            s = step_by[sid]
            parts, conns = [], []
            rec_rows = ((graphs.get("lesson") or {}).get("parts_list") or {}).get("parts", [])
            for a in by[("PLACES", sid)] + by[("MAKES", sid)]:
                if a["type"] == "PLACES" and a["v"].startswith("lesson:parts_list/"):  # a lesson with no physical graph
                    i = int(a["v"].rsplit("/", 1)[1])                                 # places parts-list rows
                    if i >= len(rec_rows):
                        problems.append(f"{sid} PLACES {a['v']}, which is not a row of the parts list")
                    else:
                        r = rec_rows[i]
                        parts.append({"instance": f"{a.get('count', 1)} x", "type": r["part"], "name": r.get("name"),
                                      "props": {"colour": r.get("colour")}, "where": a.get("where")})
                    continue
                if a["type"] == "PLACES" and a["v"] in nodes:
                    n = nodes[a["v"]]
                    d, how = defs[a["v"]]
                    added[a["v"]] += 1
                    parts.append({"instance": n["id"], "type": n["type"], "name": _name(d, n),
                                  "category": (d or {}).get("category"), "props": n.get("props", {}),
                                  "definition": how, "about": about.get(a["v"])})
                elif a["type"] == "MAKES" and edges.get(a["v"], {}).get("type") == "joined":
                    e = edges[a["v"]]
                    made[a["v"]] += 1
                    conns.append({"edge": e["id"], "type": e["type"], "from": f"{e['u']}:{e['u_port']}",
                                  "to": f"{e['v']}:{e['v_port']}", "method": e.get("method"),
                                  "holds_by": e.get("holds_by"), "reversible": e.get("reversible")})
                else:
                    problems.append(f"{sid} {a['type']} {a['v']}, which is not "
                                    f"{'an instance' if a['type'] == 'PLACES' else 'a join'} of the physical graph")
            for u in by[("USES", sid)]:
                if definition(cards, u["v"][len("def:"):])[0] is None:
                    problems.append(f"{sid} USES {u['v']}, which is not in the part catalogue")
            deps = by[("DEPENDS_ON", sid)]
            for dep in deps:
                if pos.get(dep["v"], 10 ** 9) >= pos[sid]:
                    problems.append(f"{sid} depends on {dep['v']}, which does not come before it")
            out_steps.append({**{k: v for k, v in s.items() if k not in ("id",)}, "id": sid, "parts": parts,
                              "previous": previous.get(sid), "next": next((e["v"] for e in by[("NEXT_STEP", sid)]), None),
                              "connections": [c for c in conns if "edge" in c],
                              "builds": [e["v"] for e in by[("BUILDS", sid)]],
                              "gathers": [i for e in by[("GATHERS", sid)] for row_ in (graphs.get("lesson") or {})
                                          .get("parts_list", {}).get("parts", []) for i in row_.get("instances", [])],
                              "attaches": [e["v"] for e in by[("ATTACHES", sid)]],
                              "depends_on": [{"step": d["v"], "via": d["via"]} for d in deps]})
        for e in inst["edges"]:
            if e["type"] in ("BUILDS", "ATTACHES"):
                for end in (e["u"], e["v"]):
                    if end not in step_by:
                        problems.append(f"{e['type']} edge {e['u']} -> {e['v']}: {end} is not a node")
        # the lesson record: its first step, its expected result and parts list, and the code-to-pin links
        rec = graphs.get("lesson") or {}
        problems += single_facts(inst, phys or {"edges": []}, rec)
        pass  # a stated value is the edge's own fact (a soldered header); where it is not the
        join_notes = []            # join table's (GRAPH_SPEC §5.2), it is listed for review, not an error
        for e in (phys or {"edges": []})["edges"]:
            for field, stated, rule in describe(dict(e), lambda i: defs.get(i, (None,))[0]):
                join_notes.append(f"{e['id']} {e['u']}:{e['u_port']} -> {e['v']}:{e['v_port']}: {field} is {stated}, "
                                  f"the join table says {rule}")
        er = rec.get("expected_result") or {}
        problems += [f"expected result: {x}" for x in er.get("problems", [])]
        problems += [f"parts list: {x}" for x in (rec.get("parts_list") or {}).get("problems", [])
                     if x != "no inventory for this set"]
        for s in step_nodes:
            if s.get("program") and not any(e["type"] == "PROGRAMS" and e["u"] == s["id"] for e in inst["edges"]):
                problems.append(f"{s['id']} has a program but no PROGRAMS edge to a board")
            for l in (s.get("program") or {}).get("links", []):
                if l["kind"] == "code" and l["port"] not in {f"{e['u']}:{e['u_port']}" for e in edges.values()} | \
                        {f"{e['v']}:{e['v_port']}" for e in edges.values()}:
                    if l.get("builtin_led") and all(v.startswith(("pinMode", "digitalWrite", "digitalRead"))
                                                    for v in l["via"]) and \
                            not all(v.startswith("digitalRead") for v in l["via"]):  # set up or driven (a read of a
                        # pin it also drives is the LED's own state, toggling it); reading it alone needs a wire
                        join_notes.append(f"{s['id']}: the code drives {l['port']} (line {l['line']}): the board's "
                                          f"built-in LED, no wire needed")
                    elif l.get("unwired"):  # the source reads it unwired on purpose (a floating pin as noise): the reason
                        join_notes.append(f"{s['id']}: the code reads {l['port']} (line {l['line']}) unwired on "
                                          f"purpose: {l['unwired']}")
                    else:
                        problems.append(f"{s['id']}: the code uses {l['port']} (line {l['line']}), which nothing is "
                                        f"wired to")
        rows_ = (rec.get("parts_list") or {}).get("parts", [])
        if not phys and rows_:  # a lesson whose steps place parts-list rows: every piece of the list is placed
            placed_ = collections.Counter()
            for e in inst["edges"]:
                if e["type"] == "PLACES" and e["v"].startswith("lesson:parts_list/"):
                    placed_[int(e["v"].rsplit("/", 1)[1])] += e.get("count", 1)
            for i, r in enumerate(rows_):
                if placed_[i] != (r.get("count") or 0):
                    problems.append(f"parts list #{i + 1} {r['part']} {r.get('colour', '')}: the list has "
                                    f"{r.get('count')}, the steps place {placed_[i]}")
        if phys:
            problems += [f"{i} is added by {c} steps" for i, c in added.items() if c > 1]
            problems += [f"{i} is never placed by a step" for i in nodes if not added[i]]
            for e in inst["edges"]:  # GATHERS points at the parts list, which must be there to gather
                if e["type"] == "GATHERS" and not (rec.get("parts_list") or {}).get("parts"):
                    problems.append(f"{e['u']} gathers the parts list, but the lesson has none")
            joined = [e for e in edges.values() if e["type"] == "joined"]
            problems += [f"{e['id']} ({e['u']}-{e['v']}) is never made by a step" for e in joined if not made[e["id"]]]
            problems += [f"{e} is made by {c} steps" for e, c in made.items() if c > 1]
    t["walk_steps_ms"] = (time.perf_counter() - t2) * 1000

    bom = collections.defaultdict(list)  # one definition, many instances (split by the instance's own value)
    for i, n in nodes.items():
        bom[(n["type"], _name(defs[i][0], n) or n["type"])].append(i)
    t["total_ms"] = (time.perf_counter() - t0) * 1000
    return {"lesson_id": lesson_id, "title": row["title"], "lesson_type": row["lesson_type"], "source": row["source"],
            "has": [k for k, p in row["representations"].items() if p],
            "parts_list": [{"type": k, "name": name, "count": len(v), "instances": v, "about": about.get(v[0])}
                           for (k, name), v in sorted(bom.items())],
            "lesson": {k: v for k, v in (graphs.get("lesson") or {}).items() if k not in ("kind",)},
            "steps": out_steps,
            "checks": {"ready": not problems, "problems": problems,
                       "review": [f"{n['id']}: {x}" for n in (inst or {"nodes": []})["nodes"] for x in n.get("problems") or []]
                       + [f"parts list: {w}" for w in (rec.get("parts_list") or {}).get("warnings", [])],
                       "definitions": dict(how_found),
                       "ports": dict(ports), "with_metadata": f"{len(about)}/{len(nodes)} instances",
                       "join_notes": join_notes if inst else [],
                       "edge_fields_filled_from_metadata": filled},
            "timing_ms": {k: round(v, 2) for k, v in t.items()}}


def to_md(view):
    lines = [f"# {view['title']} ({view['lesson_id']}, {view['lesson_type']})", "",
             f"Has: {', '.join(view['has'])}. Source: {view['source']}", ""]
    les = view.get("lesson", {})
    if les.get("description"):
        lines += [les["description"], ""]
    facts = [f"{k}: {les[k]}" for k in ("difficulty", "board", "tools_used") if les.get(k)]
    st = les.get("stats") or {}
    if st:
        facts.append(f"made in {st.get('seconds')} s for ${st.get('cost_usd')} ({st.get('model')}, "
                     f"{st.get('repairs')} repairs)")
    if facts:
        lines += ["*" + " · ".join(facts) + "*", ""]
    lines += ["## Parts", ""]
    for p in view["parts_list"]:
        dom = f" [{p['about']['domain']}]" if p.get("about") else ""
        lines.append(f"- {p['count']} × {p['name'] or p['type']} (`{p['type']}`){dom}: {', '.join(p['instances'])}")
        if p.get("about"):
            a = p["about"]
            lines.append(f"  - {a['description']} *{a['material']}; {a['status']}*")
            if a["tips"]:
                lines.append(f"  - tip: {a['tips'][0]}")
    lines += ["", "## Steps", ""]
    for s in view["steps"]:
        lines.append(f"**{s['n']}. {s['id']}** ({s['kind']}): {s['text']}")
        if s["parts"]:
            lines.append("  - parts: " + ", ".join(f"{p['instance']} {p['name'] or p['type']}" for p in s["parts"]))
        if s["connections"]:
            kinds = collections.defaultdict(list)  # a wire end in a hole is two edges: joined and electrical
            for c in s["connections"]:
                kinds[(c["from"], c["to"])].append(c["type"])
            how = {(c["from"], c["to"]): ", ".join(x for x in (c["holds_by"], c["reversible"] and f"undo: {c['reversible']}") if x)
                   for c in s["connections"] if c["type"] == "joined"}
            lines.append("  - connections: " + ", ".join(
                f"{a} → {b} ({'+'.join(t)}{'; ' + how[(a, b)] if how.get((a, b)) else ''})" for (a, b), t in kinds.items()))
        if s["depends_on"]:
            lines.append("  - needs: " + ", ".join(f"{d['step']} (via {', '.join(d['via'])})" for d in s["depends_on"]))
        for k, label in (("gathers", "gathers"), ("builds", "builds"), ("attaches", "attaches")):
            if s.get(k):
                lines.append(f"  - {label}: {', '.join(s[k])}")
        if s.get("why"):
            lines.append(f"  - why: {s['why']}")
        for t in s.get("troubleshooting", []):
            lines.append(f"  - if it goes wrong: {t['text']} *({t['evidence']})*")
        for t in s.get("expected", []):
            lines.append(f"  - you should see: {t['text']}")
        prog = s.get("program")
        if prog:
            lines.append(f"  - program `{prog['file']}`: " + ", ".join(
                f"line {l['line']} `{l['token']}` → {l['port']}" + (f" (needs {'+'.join(l['needs'])})" if l['needs'] else "")
                for l in prog["links"] if l["kind"] == "code"))
        if s.get("bag") is not None:
            lines.append(f"  - bag {s['bag']}")
        lines.append("")
    if les.get("how_it_works"):
        lines += ["## How it works", "", les["how_it_works"], ""]
    if les.get("troubleshooting"):
        lines += ["## Troubleshooting (spans steps)", ""] + [f"- {t['text']} *({t['evidence']})*" for t in les["troubleshooting"]] + [""]
    if les.get("try_next"):
        lines += ["## Try next", ""] + [f"- {t['text']}" for t in les["try_next"]] + [""]
    er = les.get("expected_result") or {}
    if er.get("from_circuit"):
        lines += ["## Expected result", "", "Worked out from the circuit: " + "; ".join(" = ".join(n) for n in er["from_circuit"]),
                  f"The lesson's final check {'agrees' if er.get('agree') else 'differs: ' + '; '.join(er.get('problems', []))}.", ""]
    if les.get("notes"):
        lines += ["## Notes", ""] + [f"- {x}" for x in les["notes"]] + [""]
    c = view["checks"]
    lines += ["## Checks", "", f"- definitions: {c['definitions']}; ports: {c['ports']}; metadata: "
              f"{c['with_metadata']}, {c['edge_fields_filled_from_metadata']} edge fields filled from it",
              f"- problems: {len(c['problems'])}"] + [f"  - {p}" for p in c["problems"]]
    lines += ["", f"Timing (ms): {view['timing_ms']}"]
    return "\n".join(lines) + "\n"


def to_mermaid(lesson_id, store=None):
    """The lesson's graphs as one Mermaid diagram, drawn from the stored files: steps (NEXT_STEP, DEPENDS_ON) on the
    left, part instances and their joins on the right, PLACES and GATHERS (through the parts list) between them, and
    each instance's definition from the shared catalogue."""
    row, g = _load(lesson_id, store)
    inst, phys, rec = g["instruction"], g["physical"], g.get("lesson") or {}
    q = lambda x: re.sub(r"[^A-Za-z0-9_]", "_", x)  # noqa: E731
    out = ["flowchart LR", f'  subgraph I["Instruction graph"]', "    direction TB"]
    shape = {"lesson": ('(("', '"))'), "program": ('[/"', '"/]'), "code-block": ('[/"', '"/]'),
             "explain": ('>"', '"]'), "check": ('{{"', '"}}'), "subassembly": ('[("', '")]')}
    for s in inst["nodes"]:
        a, b = shape.get(s["kind"], ('["', '"]'))
        out.append(f'    {q("s_" + s["id"])}{a}{s["id"]}{b}')
    out += [f'    {q("s_" + e["u"])} -->|{e["type"]}| {q("s_" + e["v"])}' for e in inst["edges"]
            if e["type"] in ("FIRST_STEP", "ABOUT", "VERIFIES", "PART_OF", "BUILDS", "ATTACHES")]
    out += [f'    {q("s_" + e["u"])} -->|NEXT| {q("s_" + e["v"])}' for e in inst["edges"] if e["type"] == "NEXT_STEP"]
    out += [f'    {q("s_" + e["u"])} -.->|DEPENDS_ON| {q("s_" + e["v"])}' for e in inst["edges"]
            if e["type"] == "DEPENDS_ON"]
    out += ["  end", f'  subgraph P["Physical graph"]']
    out += [f'    {q("p_" + n["id"])}(["{n["id"]}"])' for n in phys["nodes"]]
    seen = set()
    for e in phys["edges"]:
        k = (e["u"], e.get("u_port"), e["v"], e.get("v_port"))  # a wire end in a hole: joined and electrical
        if e["type"] == "joined" and k not in seen:
            seen.add(k)
            out.append(f'    {q("p_" + e["u"])} ---|{e.get("u_port")}→{e.get("v_port")}| {q("p_" + e["v"])}')
    out += ["  end", f'  subgraph C["Part catalogue (definitions)"]']
    types = sorted({n["type"] for n in phys["nodes"]})
    out += [f'    {q("t_" + t)}[["{t}"]]' for t in types]
    out += ["  end"]
    out += [f'  {q("s_" + e["u"])} ==>|PLACES| {q("p_" + e["v"])}' for e in inst["edges"] if e["type"] == "PLACES"]
    out += [f'  {q("s_" + e["u"])} -.->|GATHERS| {q("p_" + i)}' for e in inst["edges"] if e["type"] == "GATHERS"
            for r in (rec.get("parts_list") or {}).get("parts", []) for i in r.get("instances", [])]
    out += [f'  {q("p_" + n["id"])} -.-|type| {q("t_" + n["type"])}' for n in phys["nodes"]]
    return "\n".join(out)


def describe_parts(lesson_id, domain, store=None, call=None):
    """Every part the lesson uses goes through the metadata rules (part_metadata.describe_new): the catalogue is
    rebuilt from the card stores first (a card added while the lesson was made), then only parts with no metadata
    are drafted, checked, stored as codes, and given the fields code works out."""
    from graph.parts import part_metadata
    from graph.parts import part_catalogue
    part_catalogue.build()
    _CARDS.clear()
    row, g = _load(lesson_id, store or STORE)
    cards = _cards(PARTS)
    types = {n["type"] for n in (g.get("physical") or {}).get("nodes", [])}
    types |= {r["part"] for r in ((g.get("lesson") or {}).get("parts_list") or {}).get("parts", []) if r.get("part")}
    ids = sorted({(definition(cards, t)[0] or {}).get("part_type_id") or t for t in types})
    return part_metadata.describe_new(ids, domain, call=call, label=lesson_id)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("kind", choices=["lego", "arduino"])
    b.add_argument("ids", nargs="+")
    b.add_argument("--no-metadata", action="store_true", help="do not draft metadata for parts that have none")
    s = sub.add_parser("show")
    s.add_argument("ids", nargs="+")
    m = sub.add_parser("mermaid")
    m.add_argument("ids", nargs="+")
    au = sub.add_parser("audit")
    au.add_argument("ids", nargs="+")
    sub.add_parser("validate", help="every stored lesson and every part against the data structure's rules")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        validate_main()
        return
    if a.cmd == "audit":
        for lid in a.ids:
            for name, diffs in audit(lid).items():
                print(f"{lid} {name}: {'lossless' if not diffs else f'{len(diffs)} differences'}")
                for d in diffs[:15]:
                    print(f"   {d[0]}: source {str(d[1])[:80]!r} | rebuilt {str(d[2])[:80]!r}")
        return
    if a.cmd == "mermaid":
        for lid in a.ids:
            print(to_mermaid(lid))
        return
    from graph.arduino.graphs import arduino  # each route's graph builder (imported here: they import this module)
    from graph.lego_3d.graphs import lego
    for lid in a.ids:
        if a.cmd == "build":
            t0 = time.perf_counter()
            entry, graphs = (lego if a.kind == "lego" else arduino)(lid)
            register(entry, graphs)
            print(f"{lid}: built in {time.perf_counter() - t0:.1f}s")
            if a.kind == "lego":  # a card for every piece the catalogue does not have yet (as the booklet route)
                print(f"  cards: {card_missing(graphs)}")
            if not a.no_metadata:  # the metadata rules for any part this lesson brings that has none yet
                print(f"  parts: {describe_parts(lid, 'lego' if a.kind == 'lego' else 'arduino')}")
        view = assemble(lid)
        (STORE / lid / "assembled.json").write_text(json.dumps(view, indent=1))
        (STORE / lid / "assembled.md").write_text(to_md(view))
        print(to_md(view))


# ---- the join table --------------------------------------------------------------------------------------
# (kind going in, kind taking it) -> (method, holds_by, freedom, reversible)       GRAPH_SPEC §5.2
TABLE = {
    ("stud", "anti-stud"): ("insert", "friction", "rigid", "hand"),
    ("pin", "pin-hole"): ("insert", "friction", "revolute", "hand"),
    ("axle", "axle-hole"): ("insert", "form", "rigid", "hand"),
    ("axle", "pin-hole"): ("insert", None, "revolute", "hand"),
    ("bar", "clip"): ("snap", "spring", "revolute", "hand"),
    ("ball", "socket"): ("snap", "friction", "ball", "hand"),
    ("header-pin", "wire-end"): ("push-on", "spring", "rigid", "hand"),     # a female jumper pushed onto a male pin
    ("header-pin", "header-socket"): ("insert", "spring", "rigid", "hand"),
}


INTO_SPRING = {"breadboard-hole", "header-socket"}   # a spring contact grips what goes in


# Everything an electronics port can go into or onto: (its kind) -> [(the other port's kind, method, holds_by,
# reversible)]. The catalogue's `fits` for each part comes from this table, by code: a resistor's lead goes into a
# breadboard hole, but also a header socket, a female jumper end or a screw terminal, or it is soldered to a pad.
FITS = {  # "socket" (an antenna's SMA socket) and "hole" (a mounting hole) are not places a leg goes
    "lead": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
             ("wire-end", "push-on", "spring", "hand"), ("screw", "clamp", "force", "tool"),
             ("pad", "solder", "material", "tool")],
    "header-pin": [("header-socket", "insert", "spring", "hand"), ("breadboard-hole", "insert", "spring", "hand"),
                   ("wire-end", "push-on", "spring", "hand"), ("pad", "solder", "material", "tool")],
    "pin": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
            ("wire-end", "push-on", "spring", "hand"), ("pad", "solder", "material", "tool")],
    "wire-end": [("breadboard-hole", "insert", "spring", "hand"), ("header-socket", "insert", "spring", "hand"),
                 ("header-pin", "push-on", "spring", "hand"), ("screw", "clamp", "force", "tool"),
                 ("pad", "solder", "material", "tool")],
    "lug": [("screw", "clamp", "force", "tool"), ("pad", "solder", "material", "tool")],
}


def fits_into(kind_):
    """[(other kind, method, holds_by, reversible)] for a port kind: what goes in it as well as what it goes into."""
    out = list(FITS.get(kind_, []))
    for male, rows in FITS.items():
        for other, m, h, r in rows:
            if other == kind_ and not any(o == male for o, *_ in out):
                out.append((male, m, h, r))
    return out


GOES_IN = {"lead", "header-pin", "wire-end", "pin", "lug"}  # a leg, a male header pin, a wire's end, a lug
BY_NAME = [(r"^stud\b", "stud"), (r"^anti\b", "anti-stud"), (r"^pin$", "pin"), (r"^hole\b", "pin-hole"),
           (r"^axle$", "axle"), (r"^clip\b", "clip"), (r"^bar\b", "bar")]  # a port named as ldraw_studs names it


def kind(card, port):
    """A port's kind: from its card (by id, alias or the card's own pattern), else from the port's name."""
    if not port:
        return None
    for p in (card or {}).get("ports", []):
        if port_match({"ports": [p]}, port) in ("exact", "pattern"):
            return p["kind"]
    for rx, k in BY_NAME:
        if re.search(rx, port or ""):
            return k
    return None


def attrs(u_kind, v_kind):
    """(method, holds_by, freedom, reversible) for a join of these port kinds, or None when the table has no row."""
    for pair in ((u_kind, v_kind), (v_kind, u_kind)):  # the attributes do not depend on which end is written first
        if pair in TABLE:
            return TABLE[pair]
    if u_kind in GOES_IN and v_kind in INTO_SPRING:
        return ("insert", "spring", "rigid", "hand")
    return None


def describe(edge, cards_of):
    """Fill a joined edge's attributes from its port kinds (in place) where it does not state them. A value it does
    state is its own fact and is kept (a header soldered on: solder, tool); returned as [(field, stated, rule)] where
    it is not the table's, for review. cards_of(instance) -> its card."""
    if edge["type"] != "joined":
        return []
    rule = attrs(kind(cards_of(edge["u"]), edge["u_port"]), kind(cards_of(edge["v"]), edge["v_port"]))
    if rule is None:
        return []
    out = []
    for field, value in zip(("method", "holds_by", "freedom", "reversible"), rule):
        if edge.get(field) is None:
            edge[field] = value
        elif value is not None and edge[field] != value:
            out.append((field, edge[field], value))
    return out


# ---- the validator: every stored lesson and every part against the data structure's rules ------------
ROOT = pathlib.Path(__file__).resolve().parents[2]


OUT = ROOT / "data" / "validation"


RECORD_FIELDS = ("lesson_id", "name", "lesson_type", "source", "graphs")


NODE_KINDS = set(lesson_store.STEP_KINDS) | {"product", "subassembly", "lesson", "part", "board"}


INSTRUCTION_EDGES = {  # edge type -> the fields it must carry
    "NEXT_STEP": (), "PLACES": (), "MAKES": (), "DEPENDS_ON": (), "ALIGNS_WITH": (), "CHECK_NEEDS": (),
    "GATHERS": (), "PROGRAMS": (), "BUILDS": (), "ATTACHES": (), "FIRST_STEP": (), "USES": (),
    "SHOWS": ("order",), "STARTS": ()}


PHYSICAL_EDGES = {"joined": ("u_port", "v_port"), "contact": (), "electrical": ("u_port", "v_port")}


STEP_ID = re.compile(r"^(step-\d+|gather|upload-code|overview|[a-z0-9]+(-[a-z0-9]+)*-\d+(\.\d+)?)$")


PART_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


LEGO_ID = re.compile(r"^lego-[0-9a-z]+$")


def _codes(field, values, allowed, out, where=""):
    bad = [v for v in (values if isinstance(values, list) else [values]) if v is not None and v not in allowed]
    if bad:
        out.append(("P2", f"{where}{field}: {', '.join(map(str, bad))} not in the vocabulary"))


def part(t, v):
    """[(rule, message)] for one part of the catalogue."""
    from graph.parts import part_metadata  # here: they import this module
    out = []
    m = v.get("metadata") or {}
    unknown = sorted(set(m) - set(part_metadata.FIELDS))
    if unknown:
        out.append(("P1", f"metadata fields not in the structure: {', '.join(unknown)}"))
    for f, allowed in part_metadata.CODES.items():
        if f in m:
            _codes(f, m[f], allowed, out)
    if m.get("size_studs") is not None and not (isinstance(m["size_studs"], list) and len(m["size_studs"]) == 2
                                                and all(isinstance(x, int) for x in m["size_studs"])):
        out.append(("P2", f"size_studs is {m['size_studs']!r}, not [w, l] studs"))
    for k, b in (m.get("basis") or {}).items():
        _codes("basis", b, part_metadata.BASIS_CODES, out, f"{k} ")
    sp = m.get("specs") or {}
    _codes("specs.interface", sp.get("interface") or [], part_metadata.INTERFACES, out)
    _codes("specs.wireless", sp.get("wireless") or [], part_metadata.WIRELESS, out)
    for i, j in enumerate(m.get("joins") or []):
        if "mates_with" in j:
            out.append(("P2", f"joins[{i}] has free text mates_with, not mates codes"))
        _codes("port_kind", j.get("port_kind"), part_metadata.PORT_KINDS, out, f"joins[{i}].")
        _codes("mates", j.get("mates") or [], part_metadata.MATES_CODES, out, f"joins[{i}].")
        _codes("method", j.get("method"), part_metadata.JOIN_METHODS, out, f"joins[{i}].")
        _codes("holds_by", j.get("holds_by"), part_metadata.HOLDS_BY_CODES, out, f"joins[{i}].")
        _codes("reversible", j.get("reversible"), part_metadata.REVERSIBLE_CODES, out, f"joins[{i}].")
    for k, rows in (m.get("fits") or {}).items():
        _codes("fits", k, part_metadata.PORT_KINDS, out)
        for r in rows:
            _codes("fits.with", r.get("with"), part_metadata.PORT_KINDS, out, f"{k} ")
            _codes("fits.method", r.get("method"), part_metadata.JOIN_METHODS, out, f"{k} ")
            _codes("fits.holds_by", r.get("holds_by"), part_metadata.HOLDS_BY_CODES, out, f"{k} ")
            _codes("fits.reversible", r.get("reversible"), part_metadata.REVERSIBLE_CODES, out, f"{k} ")
    for g in m.get("interchangeable") or []:
        _codes("interchangeable.kind", g.get("kind"), part_metadata.SWAP_KINDS, out)
    for w in m.get("connect_by") or []:
        _codes("connect_by.way", w.get("way"), part_metadata.CONNECT_WAYS, out)
        _codes("connect_by.tool", w.get("tool"), part_metadata.TOOLS, out)
    for w in m.get("takes") or []:
        _codes("takes.what", w.get("what"), part_metadata.TAKES, out)
    for c in m.get("checks_failed") or []:
        if not isinstance(c, dict):
            out.append(("P2", f"checks_failed holds text, not {{rule, message}}: {str(c)[:60]}"))
    _codes("port kinds", sorted({p["kind"] for p in v.get("ports") or [] if "<" not in p.get("id", "")} |
                                {p["kind"] for p in v.get("ports") or [] if "<" in p.get("id", "")}),
           part_metadata.PORT_KINDS, out)
    if out and out[-1][1].startswith("port kinds"):
        out[-1] = ("P3", out[-1][1])
    if m.get("description"):
        need = [f for f in ("polarized", "reverse_power", "specs", "basis", "joins", "material") if f not in m]
        if need:
            out.append(("P4", f"described, but without {', '.join(need)}"))
    if m.get("domain") == "arduino" and v.get("ports"):
        need = [f for f in ("fits", "interchangeable") if f not in m]
        if not (m.get("connect_by") or m.get("takes")) and m.get("fits"):
            need.append("connect_by or takes")
        if need:
            out.append(("P5", f"electronics part without {', '.join(need)}"))
    if not PART_ID.match(t) or (m.get("domain") == "lego" and not LEGO_ID.match(t)):
        out.append(("P6", f"id {t!r} does not follow the naming pattern"))
    if m.get("domain") == "arduino" and not v.get("ports") and not v.get("port_rule") and \
            str(v.get("category") or "").lower() not in ("consumable", "cable", "tool", "tools"):
        out.append(("P8", "an electronics part with no pins: no lesson can say which leg goes where (graph/parts/arduino/pinouts.py)"))
    return out


def lesson(lid, row):
    """[(rule, message)] for one lesson of the store."""
    from graph.parts import part_catalogue  # here: they import this module
    out = []
    try:
        info, g = lesson_store._load(lid)
    except Exception as e:
        return [("L1", f"cannot be loaded: {e}")]
    rec, inst, phys = g.get("lesson") or {}, g.get("instruction"), g.get("physical")
    miss = [f for f in RECORD_FIELDS if not rec.get(f)]
    if miss:
        out.append(("L1", f"the record lacks {', '.join(miss)}"))
    for k, p in (rec.get("graphs") or {}).items():
        if p and not (lesson_store.STORE / p).exists():
            out.append(("L1", f"the {k} graph {p} is missing"))
    try:
        checks = lesson_store.assemble(lid)["checks"]
        out += [("L2", p) for p in checks["problems"]]
    except Exception as e:
        out.append(("L2", f"the assembler fails: {e}"))
    if inst:
        steps = [n["id"] for n in inst["nodes"] if n["kind"] in lesson_store.STEP_KINDS]
        order = lesson_store._order(inst)
        if sorted(order) != sorted(steps) or len(order) != len(set(order)):
            lost = sorted(set(steps) - set(order))
            out.append(("L3", f"the order reaches {len(set(order))} of {len(steps)} steps"
                              + (f" (not: {', '.join(lost[:6])})" if lost else "")))
        bad = [s for s in steps if not STEP_ID.match(s)]
        if bad:
            out.append(("L4", f"step ids not in the naming: {', '.join(bad[:6])}"))
        kinds = {n["kind"] for n in inst["nodes"]} - NODE_KINDS
        if kinds:
            out.append(("L5", f"node kinds not in the structure: {', '.join(sorted(kinds))}"))
        for e in inst["edges"]:
            if e["type"] not in INSTRUCTION_EDGES:
                out.append(("L5", f"edge type {e['type']} is not in the structure"))
            elif [f for f in INSTRUCTION_EDGES[e["type"]] if f not in e]:
                out.append(("L5", f"{e['type']} {e['u']} -> {e['v']} lacks {INSTRUCTION_EDGES[e['type']]}"))
    if phys:
        for e in phys["edges"]:
            if e["type"] not in PHYSICAL_EDGES:
                out.append(("L5", f"physical edge type {e['type']} is not in the structure"))
    cards = lesson_store._cards(lesson_store.PARTS)
    parts = part_catalogue.load()
    types = {n["type"] for n in (phys or {}).get("nodes", [])}
    types |= {r["part"] for r in (rec.get("parts_list") or {}).get("parts", []) if r.get("part")}
    nocard, nometa = [], []
    for t in sorted(types):
        c, _ = lesson_store.definition(cards, t)
        if not c:
            nocard.append(t)
        elif not ((parts.get(c["part_type_id"]) or {}).get("metadata") or {}).get("description"):
            nometa.append(c["part_type_id"])
    if nocard:
        out.append(("L6", f"parts with no card: {', '.join(nocard[:8])}"))
    if nometa:
        out.append(("L6", f"parts with no metadata: {', '.join(sorted(set(nometa))[:8])}"
                          + (f" (+{len(set(nometa)) - 8})" if len(set(nometa)) > 8 else "")))
    return out


def run():
    from graph.parts import part_catalogue  # here: they import this module
    t0 = time.monotonic()
    lessons = {}
    for row in json.loads((lesson_store.STORE / "catalogue.json").read_text())["lessons"]:
        lessons[row["lesson_id"]] = {"type": row.get("lesson_type"), "issues": lesson(row["lesson_id"], row)}
    parts = {}
    for t, v in part_catalogue.load().items():
        found = part(t, v)
        if found:
            parts[t] = found
    from graph.parts import naming  # P7: a card that is another card by its model number (a part under two ids), for review
    from graph.parts.cards import CardStore
    store = CardStore(ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json")
    for t, card in sorted(store.cards.items()):
        hit = naming._same_model(t, card.get("display_name"), store)
        page = naming.same_page(t, card, store)
        if hit:
            parts.setdefault(t, []).append(("P7", f"is '{hit[0]}' by its model {hit[1]} (a part under two ids?)"))
        elif page:
            parts.setdefault(t, []).append(("P7", f"is made from the shop page of '{page}' (a part under two ids?)"))
    rules = collections.Counter(r for x in lessons.values() for r, _ in x["issues"])
    rules.update(r for x in parts.values() for r, _ in x)
    report = {"date": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.monotonic() - t0, 1),
              "lessons": {"checked": len(lessons), "valid": sum(1 for x in lessons.values() if not x["issues"])},
              "parts": {"checked": len(part_catalogue.load()), "valid": len(part_catalogue.load()) - len(parts)},
              "by_rule": dict(sorted(rules.items())), "lesson_issues": {k: v for k, v in lessons.items() if v["issues"]},
              "part_issues": parts}
    return report


def validation_md(r):
    lines = [f"# Level 1 validation ({r['date']})", "",
             f"Lessons: **{r['lessons']['valid']}/{r['lessons']['checked']}** valid · parts: "
             f"**{r['parts']['valid']}/{r['parts']['checked']}** valid · {r['seconds']} s", "",
             "| rule | issues |", "|---|---|"] + [f"| {k} | {n} |" for k, n in r["by_rule"].items()] + ["", "## Lessons", ""]
    for lid, x in r["lesson_issues"].items():
        lines.append(f"- **{lid}** ({x['type']}): " + "; ".join(f"{a} {b}" for a, b in x["issues"]))
    lines += ["", "## Parts", ""]
    for t, xs in sorted(r["part_issues"].items()):
        lines.append(f"- `{t}`: " + "; ".join(f"{a} {b}" for a, b in xs))
    return "\n".join(lines) + "\n"


def validate_main():
    r = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(r, indent=1))
    (OUT / "report.md").write_text(validation_md(r))
    print(f"lessons {r['lessons']['valid']}/{r['lessons']['checked']} valid · parts {r['parts']['valid']}/"
          f"{r['parts']['checked']} valid · {r['seconds']} s · by rule {r['by_rule']}")
    for lid, x in r["lesson_issues"].items():
        print(f"  {lid}: " + "; ".join(f"{a} {b}"[:150] for a, b in x["issues"][:4]))
    shown = collections.Counter()
    for t, xs in r["part_issues"].items():
        for a, b in xs:
            shown[(a, re.sub(r"\[\d+\]", "[i]", b)[:90])] += 1
    for (a, b), n in shown.most_common(20):
        print(f"  {n:4} × {a} {b}")



if __name__ == "__main__":
    main()
