"""The lesson store and parts catalogue in Neo4j (DATA_STRUCTURE.md §10).

The JSON files stay the source: this loads them into the database, the same way every time, so it can be re-run
whenever a lesson or the catalogue changes (a lesson is replaced whole; parts are merged).

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
     ./pinpoint db check                    counts in the database against the JSON files
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
    d = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USERNAME"], env["NEO4J_PASSWORD"]))
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
    m = re.fullmatch(r"(.+?)-(\d+)", n["id"])
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
    if not phys["nodes"]:
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
    for n in phys["nodes"]:
        props = flat({"id": n["id"], "label": n.get("label"), "type": _resolve(n.get("type")), **(n.get("props") or {})})
        props["name"] = " ".join(x for x in ((n.get("props") or {}).get("colour") or "", n.get("label") or n["id"],
                                             f"({n['id']})") if x)  # the caption: "Yellow Plate 2 x 6 (b11)"
        nodes["Instance"].append({"key": uid(n["id"]), "props": {**props, "lesson_id": lesson_id}})
        labels[n["id"]] = "Instance"
        if n.get("type"):
            links.append(("IS_A", uid(n["id"]), _resolve(n["type"]), {}, "Instance", "Part"))
    made_in = {e["v"]: e["u"] for e in ins["edges"] if e["type"] == "MAKES"}
    for k, e in enumerate(phys["edges"]):
        jid = e.get("id") or f"link{k}"
        links.append((LINK_KINDS.get(e["type"], e["type"].upper()), uid(e["u"]), uid(e["v"]),
                      flat({**{f: v for f, v in e.items() if f not in ("u", "v", "type")}, "id": jid,
                            "made_in": made_in.get(jid)}), "Instance", "Instance"))
    # the steps' own links; a step that gathers or places points at the instances, or at the parts-list item
    for e in ins["edges"]:
        t, u, v = e["type"], e["u"], e["v"]
        if t == "MAKES":
            continue  # kept on the join itself (made_in): a join is a link, and a link cannot be pointed at
        props = flat(e, drop=("type", "u", "v"))
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


def main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:])
    cmd = a.pop(0) if a else "stats"
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
            print("every lesson matches the JSON" if not bad else f"{len(bad)} lessons differ:")
            for lid, want, have in bad[:20]:
                print(f"  {lid}: files {want}, database {have}")
        elif cmd == "stats":
            labels, rels = stats(d)
            print("nodes:", ", ".join(f"{r['label']} {r['n']}" for r in labels) or "none")
            print("links:", ", ".join(f"{r['type']} {r['n']}" for r in rels) or "none")
        else:
            raise SystemExit("use: load [lesson ids] | check | stats")


if __name__ == "__main__":
    main()
