"""The lesson store and parts catalogue in Neo4j (DATA_STRUCTURE.md §10).

The database is where the code reads lessons and parts (lesson_store._load and catalogue, part_catalogue.load go
through `lesson`, `index`, `parts_text` here), and where saves go too (lesson_store.register -> save_lesson,
part_catalogue.save -> save_parts). The JSON files are written as well, as the backup and for git; `./pinpoint db
load` rebuilds the database from them. Every node and link keeps the element it came from (`src`) and its place in
its file, so what is read back is exactly what the files hold (`./pinpoint db check`). With PINPOINT_DATA=files
(the tests), or when the database cannot be reached (one warning), the code uses the files.

The graph (the plan in Pinpoint Lesson Data §1, simplified 4 Nov 2026: the parts list is links, not nodes):
  (:Lesson)-[:FIRST_STEP]->(:Step)-[:NEXT_STEP]->(:Step)...   the record starts the steps graph; builds hang off it
      (SHOWS, STARTS, BUILDS, ATTACHES) and steps link back with DEPENDS_ON {via}, ALIGNS_WITH, CHECK_NEEDS
  (:Lesson)-[:NEEDS {count, colour, value, instances}]->(:Part)     the record's parts list, one link per row
  (:Step)-[:PLACES|PROGRAMS]->(:Instance)        what a step puts in; a booklet lesson's instances are made from its
      parts list, one per copy (r<row>.<n>, with its colour), and given to the steps that place them, in order
  (:Step)-[:GATHERS {count, colour}]->(:Part)    an Arduino gather step's list
  (:Instance)-[:JOINED|CONTACT|ELECTRICAL {u_port, v_port, method, made_in}]->(:Instance)   the physical graph
  (:Instance)-[:IS_A]->(:Part {part_type_id})-[:HAS_PORT]->(:Port)                         the parts catalogue
Nodes of a lesson are keyed by `uid` = "<lesson_id>/<id>" (ids like b1 or step-1 are in many lessons); a part by its
part_type_id (old ids resolved through redirects.json first), a port by "<part_type_id>:<port id>".
Neo4j properties are numbers, strings, booleans or flat lists of them: anything nested is stored as JSON text
under the same name.

Needs NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD (and NEO4J_DATABASE) in .env.
Run: ./pinpoint db load [lesson ids...]     everything (parts, then all lessons), or only the lessons named
     ./pinpoint db check                    counts, and every lesson and part read back, against the JSON files
     ./pinpoint db stats                    what is in the database
"""
import json
import os
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
STEP_KINDS = {"step", "gather", "build", "upload", "overview"}
BUILD_KINDS = {"product", "subassembly"}
LINK_KINDS = {"joined": "JOINED", "contact": "CONTACT", "electrical": "ELECTRICAL"}
RELATION = re.compile(r"^[A-Z][A-Z_]*$")  # a relationship type is put into the query text: only these are allowed
BATCH = 500


# ---- connection ---------------------------------------------------------------------------------------------------
def settings():
    env = dict(os.environ)
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip().startswith("NEO4J_") and k.strip() not in os.environ:
                env[k.strip()] = v.strip().strip("\"'")
    missing = [k for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not env.get(k)]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} not set (add them to .env)")
    return env


def driver():
    from neo4j import GraphDatabase
    env = settings()
    d = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USERNAME"], env["NEO4J_PASSWORD"]),
                             notifications_min_severity="OFF")  # e.g. "property src_lost does not exist": fine
    d.database = env.get("NEO4J_DATABASE") or "neo4j"
    return d


def run(d, query, **params):
    records, _, _ = d.execute_query(query, params, database_=d.database)
    return [r.data() for r in records]


# ---- JSON -> rows (no database: tested in code/tests/unit/test_db.py) ----------------------------------------------
def flat(props, drop=()):
    """Properties Neo4j can hold: scalars and flat lists of scalars as they are, anything else as JSON text."""
    out = {}
    for k, v in (props or {}).items():
        if k in drop or v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v) and \
                len({type(x) for x in v}) <= 1:
            out[k] = v
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out


_CAT = {}


def _resolve(t):
    """The catalogue part for a type, by the lesson store's own rule (lesson_store.definition: exact, renamed, a
    print's plain piece, a sized type's family): `resistor-220` on an Arduino parts list is the part `resistor`."""
    if not t:
        return t
    if not _CAT:
        from graph.parts import part_catalogue
        _CAT.update(part_catalogue.load())
    from graph import lesson_store
    card, _ = lesson_store.definition(_CAT, t)
    return card["part_type_id"] if card else t


def _value(t, part):
    """What a sized type says about its copy: resistor-220 -> "220" (empty when the type is the part itself)."""
    return t[len(part) + 1:] if t and part and t != part and t.startswith(part + "-") else None


def part_rows(parts):
    """Part and Port nodes and HAS_PORT links from the catalogue (parts.json)."""
    nodes, ports = [], []
    for t, e in parts.items():
        meta = e.get("metadata") or {}
        props = flat(e, drop=("ports", "metadata"))
        props.update(flat({"description": meta.get("description"), "status": meta.get("status"),
                           "domain": meta.get("domain")}))
        props["metadata"] = json.dumps(meta, ensure_ascii=False)
        props["name"] = e.get("display_name") or t  # the caption the database browser shows
        props["src"] = json.dumps(e, ensure_ascii=False)  # the entry exactly, so the catalogue can be read back
        nodes.append({"key": t, "props": props})
        for p in e.get("ports") or []:
            ports.append({"part": t, "key": f"{t}:{p['id']}", "props": {**flat(p), "name": p["id"]}})
    return nodes, ports


SPECIAL = {"gather": "Gather parts", "upload": "Upload code", "overview": "Overview"}


def caption(n):
    """A step's name as the lesson says it: "Gather parts", "Step 2" (step-2), "Step 1 · red crab body" (a booklet
    step; its numbering starts again in every build); a build's own name."""
    if n.get("kind") in SPECIAL:
        return SPECIAL[n["kind"]]
    if n.get("kind") in BUILD_KINDS:
        return n.get("name") or n["id"]
    m = re.fullmatch(r"step-(\d+)", n["id"])
    if m:
        return f"Step {m.group(1)}"
    m = re.fullmatch(r"(.+?)-(\d+(?:\.\d+)*)", n["id"])  # a booklet step, or a sub-build step inside one (5.1)
    if m:
        return f"Step {n.get('number') or m.group(2)} · {m.group(1).replace('-', ' ')}"
    return n["id"]


def lesson_rows(lesson_id, store=None):
    """Everything one lesson puts in the database, in the shape of the plan (Pinpoint Lesson Data §1: record, steps,
    physical, parts, joined through the parts): {"lesson": props, "nodes": {label: [...]}, "links": [...]}.
    A link is (type, from key, to key, props, from label, to label)."""
    d = pathlib.Path(store or ROOT / "data/lessons/store") / lesson_id
    rec = json.loads((d / "lesson.json").read_text())
    ins = json.loads((d / "instruction.json").read_text()) if (d / "instruction.json").exists() else {"nodes": [], "edges": []}
    phys = json.loads((d / "physical.json").read_text()) if (d / "physical.json").exists() else {"nodes": [], "edges": []}
    uid = lambda i: f"{lesson_id}/{i}"  # noqa: E731
    src = rec.get("source") or {}
    lesson = flat({"lesson_id": lesson_id, "name": rec.get("name"), "lesson_type": rec.get("lesson_type"),
                   "kind": src.get("kind"), "link": rec.get("link"), "set": src.get("set"),
                   "result": rec.get("result"), "stats": rec.get("stats")})
    # the originals, so the lesson can be read back exactly (read_lesson): the record, each graph's own fields,
    # and on every node and link the element it came from and its place in its file
    index = json.loads((d.parent / "catalogue.json").read_text()) if (d.parent / "catalogue.json").exists() else {}
    rows_ = index.get("lessons", [])
    pos = next((k for k, r in enumerate(rows_) if r["lesson_id"] == lesson_id), None)
    row = rows_[pos] if pos is not None else None
    lesson.update(flat({"src": json.dumps(rec, ensure_ascii=False), "src_row": json.dumps(row) if row else None,
                        "row_seq": pos,
                        "src_instruction": json.dumps({k: v for k, v in ins.items() if k not in ("nodes", "edges")})
                        if (d / "instruction.json").exists() else None,
                        "src_physical": json.dumps({k: v for k, v in phys.items() if k not in ("nodes", "edges")})
                        if (d / "physical.json").exists() else None}))
    lost = []  # instruction edges with no place in the graph (none so far), kept on the lesson
    nodes = {"Step": [], "Build": [], "Instance": []}
    links = []
    labels = {}
    # the steps graph: the record points at the first step only; the rest hang off NEXT_STEP, STARTS, SHOWS, BUILDS
    for n in ins["nodes"]:
        label = "Build" if n.get("kind") in BUILD_KINDS else "Step"
        props = flat(n, drop=("source",))
        s = n.get("source") or {}
        props.update(flat({"picture": s.get("picture"), "page": s.get("page"), "booklet_label": s.get("booklet_label")}))
        if s:
            props["source"] = json.dumps(s, ensure_ascii=False)
        props["name"] = caption(n)  # what the database browser shows on the node
        props.update({"src": json.dumps(n, ensure_ascii=False), "nseq": len(labels)})
        nodes[label].append({"key": uid(n["id"]), "props": {**props, "lesson_id": lesson_id}})
        labels[n["id"]] = label
    entered = {e["v"] for e in ins["edges"] if e["type"] in ("NEXT_STEP", "STARTS", "SHOWS")}
    roots = [n["id"] for n in ins["nodes"] if n["id"] not in entered and n.get("kind") in STEP_KINDS]
    for r in roots[:1]:
        links.append(("FIRST_STEP", lesson_id, uid(r), {}, "Lesson", "Step"))
    # the record's parts list: the lesson NEEDS each part, one link per row (count, colour, value); the instances a
    # row stands for are kept on the link by id
    rows = (rec.get("parts_list") or {}).get("parts", [])
    copies = {}  # row -> the ids of its copies, when the instances come from the parts list (a booklet lesson)
    derived = not phys["nodes"]
    if derived:
        phys = {"nodes": [], "edges": []}
        for i, r in enumerate(rows):
            if not r.get("part"):
                continue
            copies[i] = [f"r{i}.{c + 1}" for c in range(r.get("count") or 1)]
            for x in copies[i]:
                phys["nodes"].append({"id": x, "type": r["part"], "label": r.get("name"),
                                      "props": {k: r[k] for k in ("colour", "print") if r.get(k)}})
            r = {**r, "instances": copies[i]}
            rows[i] = r
    in_physical = {n["id"] for n in phys["nodes"]}
    row_props = {}
    for i, r in enumerate(rows):
        if not r.get("part"):
            continue
        part = _resolve(r["part"])
        props = flat({"row": i, "count": r.get("count") or len(r.get("instances") or []) or None,
                      "colour": r.get("colour"), "print": r.get("print"), "value": _value(r["part"], part),
                      "name": r.get("name"), "listed_as": r["part"], "from": r.get("from"),
                      "instances": [x for x in r.get("instances") or [] if x in in_physical] or None})
        row_props[i] = (part, props)
        links.append(("NEEDS", lesson_id, part, props, "Lesson", "Part"))
    # the physical graph: instances, each pointing at its catalogue part; joins are links between instances
    for k, n in enumerate(phys["nodes"]):
        props = flat({"id": n["id"], "label": n.get("label"), "type": _resolve(n.get("type")), **(n.get("props") or {})})
        props.update({"derived": True} if derived else {"src": json.dumps(n, ensure_ascii=False), "nseq": k})
        props["name"] = " ".join(x for x in ((n.get("props") or {}).get("colour") or "", n.get("label") or n["id"],
                                             f"({n['id']})") if x)  # the caption: "Yellow Plate 2 x 6 (b11)"
        nodes["Instance"].append({"key": uid(n["id"]), "props": {**props, "lesson_id": lesson_id}})
        labels[n["id"]] = "Instance"
        if n.get("type"):
            links.append(("IS_A", uid(n["id"]), _resolve(n["type"]), {}, "Instance", "Part"))
    made_in = {e["v"]: (e["u"], i, e) for i, e in enumerate(ins["edges"]) if e["type"] == "MAKES"}
    for k, e in enumerate(phys["edges"]):
        jid = e.get("id") or f"link{k}"
        mk = made_in.pop(jid, None)
        links.append((LINK_KINDS.get(e["type"], e["type"].upper()), uid(e["u"]), uid(e["v"]),
                      flat({**{f: v for f, v in e.items() if f not in ("u", "v", "type")}, "id": jid,
                            "made_in": mk[0] if mk else None, "src": json.dumps(e, ensure_ascii=False), "pseq": k,
                            "src_makes": json.dumps(mk[2]) if mk else None, "seq_makes": mk[1] if mk else None}),
                      "Instance", "Instance"))
    lost += [[i, e] for _, i, e in made_in.values()]  # a step that makes a join the physical graph does not have
    # the steps' own links; a step that gathers or places points at the instances, or at the parts-list item
    for i, e in enumerate(ins["edges"]):
        t, u, v = e["type"], e["u"], e["v"]
        if t == "MAKES":
            continue  # kept on the join itself (made_in): a join is a link, and a link cannot be pointed at
        props = flat(e, drop=("type", "u", "v"))
        before = len(links)
        ref = re.match(r"lesson:parts_list/(\d+)$", str(v))
        if ref and int(ref.group(1)) in copies:  # a booklet step: the next copies of that row, in step order
            row = int(ref.group(1))
            take = copies[row][:e.get("count") or 1]
            copies[row] = copies[row][len(take):]
            links += [(t, uid(u), uid(x), flat({"where": e.get("where")}), labels.get(u, "Step"), "Instance") for x in take]
        elif ref and int(ref.group(1)) in row_props:  # a part on the list with no copies to place: the part itself
            part, rp = row_props[int(ref.group(1))]
            links.append((t, uid(u), part, {**flat({k: rp.get(k) for k in ("row", "colour", "print", "value")}), **props},
                          labels.get(u, "Step"), "Part"))
        elif v == "lesson:parts_list":  # an Arduino gather step: every part on the list, with its count
            links += [(t, uid(u), part, {**flat({k: rp.get(k) for k in ("row", "count", "colour", "value")}), **props},
                       labels.get(u, "Step"), "Part") for part, rp in row_props.values()]
        elif u in labels and v in labels:
            links.append((t, uid(u), uid(v), props, labels[u], labels[v]))
        if len(links) > before:  # the edge itself, on the first link made from it
            t0, a0, b0, p0, la0, lb0 = links[before]
            links[before] = (t0, a0, b0, {**p0, "src": json.dumps(e, ensure_ascii=False), "iseq": i}, la0, lb0)
        else:
            lost.append([i, e])
    if lost:
        lesson["src_lost"] = json.dumps(lost, ensure_ascii=False)
    return {"lesson": lesson, "nodes": nodes, "links": links}


# ---- loading ------------------------------------------------------------------------------------------------------
KEY = {"Lesson": "lesson_id", "Part": "part_type_id", "Port": "uid", "Step": "uid", "Build": "uid", "Instance": "uid"}


def setup(d):
    for label, key in KEY.items():
        run(d, f"CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
    for label in ("Step", "Build", "Instance"):
        run(d, f"CREATE INDEX {label.lower()}_lesson IF NOT EXISTS FOR (n:{label}) ON (n.lesson_id)")
    for old in ("join", "item"):  # joins and parts-list items were nodes in the first loads of 4 Nov 2026; now links
        run(d, f"DROP CONSTRAINT {old}_key IF EXISTS")
        run(d, f"DROP INDEX {old}_lesson IF EXISTS")


def _chunks(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def load_parts(d, parts=None):
    from graph.parts import part_catalogue
    nodes, ports = part_rows(parts or part_catalogue.load())
    for chunk in _chunks(nodes):
        run(d, "UNWIND $rows AS r MERGE (p:Part {part_type_id: r.key}) SET p = r.props, p.part_type_id = r.key",
            rows=chunk)
    for chunk in _chunks(ports):
        run(d, "UNWIND $rows AS r MATCH (p:Part {part_type_id: r.part}) MERGE (o:Port {uid: r.key}) "
               "SET o = r.props, o.uid = r.key, o.part_type_id = r.part MERGE (p)-[:HAS_PORT]->(o)", rows=chunk)
    return len(nodes), len(ports)


def load_lesson(d, lesson_id, store=None):
    """One lesson, replaced whole: its old nodes are removed first, so nothing it no longer has stays behind."""
    rows = lesson_rows(lesson_id, store)
    run(d, "MATCH (n) WHERE n.lesson_id = $id AND NOT n:Lesson AND NOT n:Part DETACH DELETE n", id=lesson_id)
    run(d, "MATCH (l:Lesson {lesson_id: $id}) DETACH DELETE l", id=lesson_id)
    run(d, "CREATE (l:Lesson) SET l = $props", props=rows["lesson"])
    for label, nodes in rows["nodes"].items():
        for chunk in _chunks(nodes):
            run(d, f"UNWIND $rows AS r CREATE (n:{label}) SET n = r.props, n.uid = r.key", rows=chunk)
    groups = {}
    for t, a, b, props, la, lb in rows["links"]:
        if not RELATION.match(t):
            raise ValueError(f"{lesson_id}: relationship type {t!r} is not allowed")
        groups.setdefault((t, la, lb), []).append({"a": a, "b": b, "props": props})
    missing = 0
    for (t, la, lb), items in groups.items():
        for chunk in _chunks(items):
            res = run(d, f"UNWIND $rows AS r MATCH (a:{la} {{{KEY[la]}: r.a}}) MATCH (b:{lb} {{{KEY[lb]}: r.b}}) "
                         f"CREATE (a)-[x:{t}]->(b) SET x = r.props RETURN count(x) AS made", rows=chunk)
            missing += len(chunk) - res[0]["made"]
    return {"nodes": 1 + sum(len(v) for v in rows["nodes"].values()), "links": len(rows["links"]) - missing,
            "not_linked": missing}


def lesson_ids(store=None):
    s = pathlib.Path(store or ROOT / "data/lessons/store")
    return sorted(p.name for p in s.iterdir() if (p / "lesson.json").exists())


def stats(d):
    labels = run(d, "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY n DESC")
    rels = run(d, "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY n DESC")
    return labels, rels


def check(d, store=None):
    """Per lesson: steps, builds, parts-list links, instances and joins in the database against the JSON files."""
    bad = []
    got = {}
    for label, name in (("Step", "steps"), ("Build", "builds"), ("Instance", "instances")):
        for r in run(d, f"MATCH (n:{label}) RETURN n.lesson_id AS id, count(n) AS n"):
            got.setdefault(r["id"], {})[name] = r["n"]
    for r in run(d, "MATCH (a:Instance)-[j:JOINED|CONTACT|ELECTRICAL]->(:Instance) RETURN a.lesson_id AS id, count(j) AS n"):
        got.setdefault(r["id"], {})["joins"] = r["n"]
    for r in run(d, "MATCH (l:Lesson)-[n:NEEDS]->(:Part) RETURN l.lesson_id AS id, count(n) AS n"):
        got.setdefault(r["id"], {})["needs"] = r["n"]
    for lid in lesson_ids(store):
        rows = lesson_rows(lid, store)
        want = {"steps": len(rows["nodes"]["Step"]), "builds": len(rows["nodes"]["Build"]),
                "needs": sum(t == "NEEDS" for t, *_ in rows["links"]), "instances": len(rows["nodes"]["Instance"]),
                "joins": sum(t in ("JOINED", "CONTACT", "ELECTRICAL") for t, *_ in rows["links"])}
        have = {k: (got.get(lid) or {}).get(k, 0) for k in want}
        if have != want:
            bad.append((lid, want, have))
    return bad


# ---- reading back (the database as the store) ---------------------------------------------------------------------
def read_lessons(d, ids=None):
    """{lesson_id: {"row", "lesson", "instruction", "physical"}} as the files hold them, put back together from the
    originals on the lessons' nodes and links: the lessons named, or all, in three queries."""
    where = "WHERE l.lesson_id IN $ids" if ids is not None else ""
    heads = run(d, f"MATCH (l:Lesson) {where} RETURN l.lesson_id AS id, l.src AS src, l.src_row AS row, "
                   "l.src_instruction AS si, l.src_physical AS sp, l.src_lost AS lost", ids=list(ids or []))
    heads = [h for h in heads if h["src"]]
    if not heads:
        return {}
    want = [h["id"] for h in heads]
    nodes = run(d, "MATCH (n) WHERE n.lesson_id IN $ids AND n.src IS NOT NULL AND (n:Step OR n:Build OR n:Instance) "
                   "RETURN n.lesson_id AS id, labels(n)[0] AS label, n.src AS src, n.nseq AS seq", ids=want)
    rels = run(d, "MATCH (a)-[r]->() WHERE a.lesson_id IN $ids AND (r.iseq IS NOT NULL OR r.pseq IS NOT NULL) "
                  "RETURN a.lesson_id AS id, r.src AS src, r.iseq AS iseq, r.pseq AS pseq, r.src_makes AS mk, "
                  "r.seq_makes AS mseq", ids=want)
    by_n, by_r = {}, {}
    for n in nodes:
        by_n.setdefault(n["id"], []).append(n)
    for r in rels:
        by_r.setdefault(r["id"], []).append(r)
    out = {}
    for g in heads:
        ns, rs = by_n.get(g["id"], []), by_r.get(g["id"], [])
        ins_edges = [(r["iseq"], r["src"]) for r in rs if r["iseq"] is not None] + \
                    [(r["mseq"], r["mk"]) for r in rs if r["mk"]] + \
                    [(i, json.dumps(e)) for i, e in json.loads(g["lost"] or "[]")]
        one = {"row": json.loads(g["row"]) if g["row"] else None, "lesson": json.loads(g["src"]),
               "instruction": None, "physical": None}
        if g["si"] is not None:
            one["instruction"] = {**json.loads(g["si"]),
                                  "nodes": [json.loads(n["src"]) for n in sorted(
                                      (n for n in ns if n["label"] != "Instance"), key=lambda n: n["seq"])],
                                  "edges": [json.loads(e) for _, e in sorted(ins_edges, key=lambda x: x[0])]}
        if g["sp"] is not None:
            one["physical"] = {**json.loads(g["sp"]),
                               "nodes": [json.loads(n["src"]) for n in sorted(
                                   (n for n in ns if n["label"] == "Instance"), key=lambda n: n["seq"])],
                               "edges": [json.loads(r["src"]) for r in sorted(
                                   (r for r in rs if r["pseq"] is not None), key=lambda r: r["pseq"])]}
        out[g["id"]] = one
    return out


def read_lesson(d, lesson_id):
    """One lesson as the files hold it (see read_lessons); None if it is not there."""
    return read_lessons(d, [lesson_id]).get(lesson_id)


def read_parts(d):
    """The parts catalogue (parts.json) as it is, from the parts' originals."""
    return {r["t"]: json.loads(r["src"]) for r in run(d, "MATCH (p:Part) WHERE p.src IS NOT NULL "
                                                        "RETURN p.part_type_id AS t, p.src AS src")}


def read_index(d):
    """The lesson index (catalogue.json's rows), in the order lessons were saved."""
    return [json.loads(r["row"]) for r in run(d, "MATCH (l:Lesson) WHERE l.src_row IS NOT NULL "
                                                 "RETURN l.src_row AS row ORDER BY l.row_seq")]


def sync_parts(d, parts, removed=()):
    """Some parts written again (and removed ones taken out), as a catalogue save leaves them."""
    if parts:
        load_parts(d, parts)
        run(d, "UNWIND $ids AS t MATCH (p:Part {part_type_id: t})-[:HAS_PORT]->(o:Port) "
               "WHERE NOT o.uid IN [x IN $ports WHERE x STARTS WITH t + ':'] DETACH DELETE o",
            ids=list(parts), ports=[f"{t}:{p['id']}" for t, e in parts.items() for p in e.get("ports") or []])
    if removed:
        run(d, "UNWIND $ids AS t MATCH (p:Part {part_type_id: t}) OPTIONAL MATCH (p)-[:HAS_PORT]->(o:Port) "
               "DETACH DELETE p, o", ids=list(removed))


# ---- the switch: the database when it is set up, the files otherwise -----------------------------------------------
_STATE = {"driver": None, "off": None, "parts": None, "lessons": {}, "index": None}


def enabled():
    """Read and write the database? Yes when .env has it, unless PINPOINT_DATA=files (the tests) or it failed once
    in this process (then the files are used, with one warning)."""
    if os.environ.get("PINPOINT_DATA", "db") == "files" or _STATE["off"]:
        return False
    try:
        settings()
    except RuntimeError:
        return False
    return True


def _driver():
    if _STATE["driver"] is None:
        _STATE["driver"] = driver()
    return _STATE["driver"]


def _safely(what, fn):
    try:
        return fn(_driver())
    except Exception as e:  # paused, offline, wrong password: the files, from here on in this process
        _STATE["off"] = f"{type(e).__name__}: {str(e)[:120]}"
        print(f"database: could not {what} ({_STATE['off']}); using the files", file=sys.stderr)
        return None


def parts_text():
    """The catalogue from the database as JSON text (cached for this process), or None to use the file."""
    if _STATE["parts"] is None and enabled():
        got = _safely("read the parts", read_parts)
        if got:
            _STATE["parts"] = json.dumps(got)
    return _STATE["parts"]


def lesson(lesson_id):
    """A lesson from the database (cached for this process), or None to use the files."""
    if lesson_id not in _STATE["lessons"] and enabled():
        got = _safely(f"read {lesson_id}", lambda d: read_lesson(d, lesson_id))
        if got is None:
            return None
        _STATE["lessons"][lesson_id] = json.dumps(got)
    raw = _STATE["lessons"].get(lesson_id)
    return json.loads(raw) if raw else None


def prefetch():
    """Every lesson into this process's cache (the validator, the parts lab and other whole-store runs): only the
    ones not cached yet, in three queries. Returns how many were fetched (0 once everything is cached)."""
    if not enabled():
        return 0
    rows = index() or []
    missing = [r["lesson_id"] for r in rows if r["lesson_id"] not in _STATE["lessons"]]
    if not missing and rows:
        return 0
    got = _safely("read the lessons", lambda d: read_lessons(d, missing or None)) or {}
    for lid, one in got.items():
        _STATE["lessons"][lid] = json.dumps(one)
    return len(got)


def index():
    """The lesson index from the database, or None to use the file."""
    if _STATE["index"] is None and enabled():
        _STATE["index"] = _safely("read the lesson index", read_index)
    return _STATE["index"]


def forget(lesson_id=None, parts=False):
    """Drop what this process has cached, after a save."""
    if lesson_id:
        _STATE["lessons"].pop(lesson_id, None)
        _STATE["index"] = None
    if parts:
        _STATE["parts"] = None


def save_parts(new, old):
    """After the catalogue file is written: the parts that changed, into the database."""
    if not enabled():
        return None
    changed = {t: e for t, e in new.items() if old.get(t) != e}
    removed = [t for t in old if t not in new]
    if not changed and not removed:
        return 0
    done = _safely("save the parts", lambda d: sync_parts(d, changed, removed) or True)
    _STATE["parts"] = json.dumps(new) if done else None
    return len(changed) + len(removed)


def save_lesson(lesson_id, store=None):
    """After a lesson is written to the files: the lesson into the database."""
    if not enabled():
        return None
    forget(lesson_id)
    return _safely(f"save {lesson_id}", lambda d: load_lesson(d, lesson_id, store))


def roundtrip(d, store=None):
    """Every lesson and the catalogue read back from the database against the files: [(what, difference)]."""
    bad = []
    s = pathlib.Path(store or ROOT / "data/lessons/store")
    every = read_lessons(d)  # all of them in three queries
    for lid in lesson_ids(store):
        got = every.get(lid) or {}
        for kind in ("lesson", "instruction", "physical"):
            f = s / lid / f"{kind}.json"
            want = json.loads(f.read_text()) if f.exists() else None
            if got.get(kind) != want:
                bad.append((lid, kind))
    from graph.parts import part_catalogue
    want = json.loads(part_catalogue.PATH.read_text())
    got = read_parts(d)
    bad += [("parts", t) for t in sorted(set(want) | set(got)) if want.get(t) != got.get(t)][:20]
    return bad


def main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:])
    cmd = a.pop(0) if a else "stats"
    if cmd == "load":
        os.environ["PINPOINT_DATA"] = "files"  # the load reads the files and writes the database
    with driver() as d:
        d.verify_connectivity()
        if cmd == "load":
            t0 = time.perf_counter()
            setup(d)
            if not a:
                n, p = load_parts(d)
                print(f"parts: {n} parts, {p} ports")
            total = {"nodes": 0, "links": 0, "not_linked": 0}
            for lid in a or lesson_ids():
                r = load_lesson(d, lid)
                for k in total:
                    total[k] += r[k]
                if r["not_linked"]:
                    print(f"  {lid}: {r['not_linked']} links whose ends are not in the database")
            print(f"lessons: {len(a or lesson_ids())}, {total['nodes']} nodes, {total['links']} links"
                  f" ({total['not_linked']} not linked) in {time.perf_counter() - t0:.0f} s")
        elif cmd == "check":
            bad = check(d)
            print("counts: every lesson matches the JSON" if not bad else f"{len(bad)} lessons differ:")
            for lid, want, have in bad[:20]:
                print(f"  {lid}: files {want}, database {have}")
            bad = roundtrip(d)
            print("read back: every lesson and part is exactly as in the files" if not bad else
                  f"read back: {len(bad)} differ: {bad[:10]}")
        elif cmd == "stats":
            labels, rels = stats(d)
            print("nodes:", ", ".join(f"{r['label']} {r['n']}" for r in labels) or "none")
            print("links:", ", ".join(f"{r['type']} {r['n']}" for r in rels) or "none")
        else:
            raise SystemExit("use: load [lesson ids] | check | stats")


if __name__ == "__main__":
    main()
