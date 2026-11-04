"""The lesson store and parts catalogue in Neo4j (DATA_STRUCTURE.md §10).

The JSON files stay the source: this loads them into the database, the same way every time, so it can be re-run
whenever a lesson or the catalogue changes (a lesson is replaced whole; parts are merged).

The graph:
  (:Lesson {lesson_id})-[:HAS_STEP]->(:Step)        steps of every kind (gather, build, step, upload, overview)
  (:Lesson)-[:HAS_BUILD]->(:Build)                  a booklet build or a 3D model's sub-assembly
  (:Lesson)-[:HAS_INSTANCE]->(:Instance)-[:IS_A]->(:Part {part_type_id})-[:HAS_PORT]->(:Port)
  (:Join {kind: joined|contact|electrical})-[:END {side, port}]->(:Instance), plus a shortcut
      (:Instance)-[:JOINED|CONTACT|ELECTRICAL {join, u_port, v_port}]->(:Instance)
  (:Lesson)-[:NEEDS {count, colour, print, row}]->(:Part)       the lesson's parts list
  the instruction graph's own links as they are: NEXT_STEP, DEPENDS_ON {via}, PLACES {count, where}, MAKES (-> Join),
      GATHERS, PROGRAMS, ALIGNS_WITH, SHOWS, STARTS, BUILDS, ATTACHES, CHECK_NEEDS
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
        nodes.append({"key": t, "props": props})
        for p in e.get("ports") or []:
            ports.append({"part": t, "key": f"{t}:{p['id']}", "props": flat(p)})
    return nodes, ports


def lesson_rows(lesson_id, store=None):
    """Everything one lesson puts in the database: {"lesson": props, "nodes": {label: [...]}, "links": [...]}.
    A link is (type, from uid or part, to uid or part, props, from label, to label)."""
    d = pathlib.Path(store or ROOT / "data/lessons/store") / lesson_id
    rec = json.loads((d / "lesson.json").read_text())
    ins = json.loads((d / "instruction.json").read_text()) if (d / "instruction.json").exists() else {"nodes": [], "edges": []}
    phys = json.loads((d / "physical.json").read_text()) if (d / "physical.json").exists() else {"nodes": [], "edges": []}
    uid = lambda i: f"{lesson_id}/{i}"  # noqa: E731
    src = rec.get("source") or {}
    lesson = flat({"lesson_id": lesson_id, "name": rec.get("name"), "lesson_type": rec.get("lesson_type"),
                   "kind": src.get("kind"), "link": rec.get("link"), "set": src.get("set"),
                   "result": rec.get("result"), "stats": rec.get("stats")})
    nodes = {"Step": [], "Build": [], "Instance": [], "Join": []}
    links = []
    labels = {}
    for n in ins["nodes"]:
        label = "Build" if n.get("kind") in BUILD_KINDS else "Step"
        props = flat(n, drop=("source",))
        s = n.get("source") or {}
        props.update(flat({"picture": s.get("picture"), "page": s.get("page"), "booklet_label": s.get("booklet_label")}))
        if s:
            props["source"] = json.dumps(s, ensure_ascii=False)
        nodes[label].append({"key": uid(n["id"]), "props": {**props, "lesson_id": lesson_id}})
        labels[n["id"]] = label
        links.append(("HAS_STEP" if label == "Step" else "HAS_BUILD", lesson_id, uid(n["id"]), {}, "Lesson", label))
    for n in phys["nodes"]:
        props = flat({"id": n["id"], "label": n.get("label"), "type": _resolve(n.get("type")), **(n.get("props") or {})})
        nodes["Instance"].append({"key": uid(n["id"]), "props": {**props, "lesson_id": lesson_id}})
        labels[n["id"]] = "Instance"
        links.append(("HAS_INSTANCE", lesson_id, uid(n["id"]), {}, "Lesson", "Instance"))
        if n.get("type"):
            links.append(("IS_A", uid(n["id"]), _resolve(n["type"]), {}, "Instance", "Part"))
    for k, e in enumerate(phys["edges"]):
        jid = e.get("id") or f"link{k}"
        kind = e["type"]
        nodes["Join"].append({"key": uid(jid), "props": {**flat(e, drop=("u", "v", "type")), "id": jid, "kind": kind,
                                                          "lesson_id": lesson_id}})
        labels[jid] = "Join"
        links.append(("END", uid(jid), uid(e["u"]), flat({"side": "u", "port": e.get("u_port")}), "Join", "Instance"))
        links.append(("END", uid(jid), uid(e["v"]), flat({"side": "v", "port": e.get("v_port")}), "Join", "Instance"))
        links.append((LINK_KINDS.get(kind, kind.upper()), uid(e["u"]), uid(e["v"]),
                      flat({"join": jid, "u_port": e.get("u_port"), "v_port": e.get("v_port"), "method": e.get("method")}),
                      "Instance", "Instance"))
    rows = (rec.get("parts_list") or {}).get("parts", [])
    for i, r in enumerate(rows):
        if r.get("part"):
            part = _resolve(r["part"])
            links.append(("NEEDS", lesson_id, part,
                          flat({"row": i, "count": r.get("count") or len(r.get("instances") or []) or None,
                                "colour": r.get("colour"), "print": r.get("print"), "value": _value(r["part"], part),
                                "name": r.get("name"), "from": r.get("from"), "listed_as": r["part"]}), "Lesson", "Part"))
    for e in ins["edges"]:
        t, u, v = e["type"], e["u"], e["v"]
        props = flat(e, drop=("type", "u", "v"))
        ref = re.match(r"lesson:parts_list/(\d+)$", str(v))
        if ref and int(ref.group(1)) < len(rows):  # a booklet step's part: the parts-list row's part
            r = rows[int(ref.group(1))]
            props.update(flat({"row": int(ref.group(1)), "colour": r.get("colour"), "print": r.get("print")}))
            links.append((t, uid(u), _resolve(r["part"]), props, labels.get(u, "Step"), "Part"))
        elif u in labels and v in labels:
            links.append((t, uid(u), uid(v), props, labels[u], labels[v]))
        elif u in labels and str(v).startswith("lesson"):
            links.append((t, uid(u), lesson_id, props, labels[u], "Lesson"))
    return {"lesson": lesson, "nodes": nodes, "links": links}


# ---- loading ------------------------------------------------------------------------------------------------------
KEY = {"Lesson": "lesson_id", "Part": "part_type_id", "Port": "uid", "Step": "uid", "Build": "uid", "Instance": "uid",
       "Join": "uid"}


def setup(d):
    for label, key in KEY.items():
        run(d, f"CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
    for label in ("Step", "Build", "Instance", "Join"):
        run(d, f"CREATE INDEX {label.lower()}_lesson IF NOT EXISTS FOR (n:{label}) ON (n.lesson_id)")


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
    """Per lesson: steps, builds, instances and joins in the database against the JSON files."""
    bad = []
    got = {r["id"]: r for r in run(d, """
        MATCH (l:Lesson) OPTIONAL MATCH (l)-[:HAS_STEP]->(s) WITH l, count(s) AS steps
        OPTIONAL MATCH (l)-[:HAS_BUILD]->(b) WITH l, steps, count(b) AS builds
        OPTIONAL MATCH (l)-[:HAS_INSTANCE]->(i) WITH l, steps, builds, count(i) AS instances
        OPTIONAL MATCH (j:Join {lesson_id: l.lesson_id}) RETURN l.lesson_id AS id, steps, builds, instances, count(j) AS joins""")}
    for lid in lesson_ids(store):
        rows = lesson_rows(lid, store)
        want = {"steps": len(rows["nodes"]["Step"]), "builds": len(rows["nodes"]["Build"]),
                "instances": len(rows["nodes"]["Instance"]), "joins": len(rows["nodes"]["Join"])}
        have = {k: (got.get(lid) or {}).get(k) for k in want}
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
