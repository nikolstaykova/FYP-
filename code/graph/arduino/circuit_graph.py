"""A tutorial's circuit as a graph: the parts and every connection, read by Claude and checked by code.

What it is   the one way a circuit is extracted (build, save): Claude opens the tutorial's link and lists the parts
             (with the lookup_part tool), then gives every connection in the same conversation; code checks the
             graph and sends problems back once; part types Claude still had to draft are carded (upkeep). Also, in
             this file: the graph's structured form Claude returns (ExtractedGraph), the spec rules (validate),
             electrical nets (nets: breadboard strips and wires folded away), repeated groups expanded (expand) and
             the electronics checks (run and the laws E6-E12, B1/B2).
Used for     the circuit an Arduino lesson is made from (GRAPH_SPEC.md).
Where        arduino/circuit_lesson.py (extract); extract.py (ExtractedGraph, the answer's form);
             arduino/circuit_lesson.py (nets). The research versions it replaced (v1-v8) are in code/tests/research.

  1. parts     Claude reads the page (it opens the link itself, in a real browser) and lists every physical part,
               calling lookup_part (the card store, then the approved shops) for any part the catalogue lacks
  2. build     in the same conversation, the complete graph: the same parts and every connection
  3. check     code's laws (below); every problem goes back to Claude once, for the complete corrected graph
  4. upkeep    each part type Claude still had to draft is looked up on the shops and carded for later lessons;
               if that brings electrical facts, the electrical laws run again and one more repair follows
The laws: the spec rules (validate) and the electronics checks (run), the parts list's counts (E6) and nothing it does
not list, board pins the page names are wired (E7), the sketch's pins are wired, electrical facts (E8-E10), breadboard
placement (B1/B2), pin tables (E11), matrix resistors (E12).
"""
import collections
import json
import re
import subprocess
import time

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from graph.parts import part_catalogue
from graph.parts import cards as pc

ROOT = part_catalogue.pathlib.Path(__file__).resolve().parents[3]
CARDS = ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json"  # the card store; grows with every lesson
HINT = "arduino-v6"   # the builder's instructions (extract.HINTS)
REPAIRS = 1           # repair rounds after the first check
PARTS_TURN = ("STEP 1 OF 2, PARTS ONLY. List every physical part the tutorial uses, wires and breadboard included, "
              "as the `parts` of the graph: one node per physical part, its type from the catalogue, its value or "
              "colour in props. For any part the catalogue does not list, call lookup_part first and use the type it "
              "returns. Leave `edges` and `repeats` empty in this step; the connections come in step 2.")
BUILD_TURN = ("STEP 2 OF 2, CONNECTIONS. Now return the COMPLETE graph: the same parts as in step 1 (add or drop one "
              "only if step 1 was wrong, and say why in notes) and every connection the tutorial requires.")


class PartsThenBuild:
    """One conversation: turn 1 lists the parts (with lookup_part for parts the catalogue lacks), turn 2 adds the
    connections. The tutorial is read once; turn 2 reuses it. A repair turn returns the complete corrected graph."""

    def __init__(self, manual, catalogue_text, model, effort, web_domain, parts_tool_store):
        from graph.extract import SubscriptionSession
        self.session = SubscriptionSession(manual + "\n\n" + PARTS_TURN, catalogue_text, HINT, images=[], model=model,
                                           effort=effort, timeout=600, parts_tool_store=parts_tool_store,
                                           web_domain=web_domain)
        self.parts_graph, self.parts_stats = None, None

    def start(self):
        self.parts_graph, self.parts_stats = self.session.first()
        return self.session.send([{"type": "text", "text": BUILD_TURN}])

    def repair(self, message):
        return self.session.repair(message)

    def close(self):
        self.session.close()


def tutorial_items(manual, store):
    """Every parts-list item matched to a card, by code: [(card type, count)], an item with no count being 1.
    For the too-many-parts law only."""
    from graph.parts.arduino import tutorial
    out = []
    for item in tutorial.hardware_list(manual):
        for alt in re.split(r"\s+or\s+", item):  # "LED bar graph display or 10 LEDs": either one is allowed
            card, name = tutorial.match(alt, store)
            if card and card != "skip":
                q = tutorial.quantity(alt)
                plural = bool(re.search(r"s\b", name.split()[-1])) if name else False
                out.append((card, q if q else (None if plural else 1)))  # "Resistors": some, no upper limit
    return out


def tutorial_counts(manual, store):
    """Counts the tutorial's parts list states, by code, for the parts-count law only (no part is chosen or looked
    up from it): [(card type, count, resistor value or None)]."""
    from graph.parts.arduino import tutorial
    out = []
    for item in tutorial.hardware_list(manual):
        card, name = tutorial.match(item, store)
        q = tutorial.quantity(item)
        if card and card != "skip" and q:
            v = tutorial.VALUE.search(item)
            out.append((card, q, ohms(v.group(0)) if v and "resistor" in card else None))
    return out


def upkeep(graph, store):
    """Card every part type Claude had to add, through the shops; stored for later lessons.
    Returns (report, {type: engine card} for the cards found)."""
    from graph.parts import ingest
    store.refresh()  # cards the builder's lookup_part already stored
    t0, rows, cards, cost = time.monotonic(), [], {}, 0.0
    for d in graph["new_part_types"]:
        card, st, trail = ingest.ingest_part(d["name"], "electronics", store, wanted_id=d["type"], label=d["name"],
                                             max_llm_calls=3)
        cost += st.get("cost_usd", 0)
        rows.append({"type": d["type"], "found": bool(card), "trail": trail})
        if card:
            cards[d["type"]] = card
    return {"seconds": round(time.monotonic() - t0, 1), "cost_usd": round(cost, 4), "types": rows}, cards


def prompt(case):
    """What Claude is told: the link (it reads the page itself), and what a person or an earlier phase settled."""
    manual = (f"The tutorial is the web page {case['url']}. Open it with the open_page tool and read it, including "
              f"its circuit section, parts list and circuit images, before answering.")
    if case.get("correction"):  # a person's correction where the page is wrong or unclear: it overrules the page
        manual += f"\n\nCORRECTION from a person who checked this tutorial (follow it over the page): {case['correction']}"
    if case.get("sketch"):
        manual += f"\n\nTHE SKETCH this circuit runs:\n{case['sketch']}"
    if case.get("parts_note"):  # the parts, settled before this build (part_review.parts_first)
        manual += case["parts_note"]
    return manual


def build(case, out, sketch="", model="sonnet", effort="high"):
    """Parts, build, check, repair and upkeep for one tutorial. Returns what was saved: {graph, graph_initial, stats,
    phases, issues_first, issues_final, final_issue_list, upkeep}."""
    store = pc.store("electronics", out, CARDS)
    entries = {**part_catalogue.arduino_seed(), **{t: store.get(t) for t in store.cards}}  # the cards carry card_notes.json
    manual = prompt(case)
    counts, items = tutorial_counts(manual, store), tutorial_items(manual, store)
    catalogue_text = part_catalogue.Catalogue(entries).prompt_text(electrical=True, placement=True)
    web_domain = re.sub(r"^www\.", "", case["url"].split("/")[2])

    def check(graph):
        t0 = time.monotonic()
        tmp = part_catalogue.Catalogue(entries)
        tmp.add_drafts(graph["new_part_types"])
        flat = expand(graph)
        found = run(flat, tmp, "arduino", manual, frozenset(), None)
        if counts:
            found += parts_count(flat, counts)
        found += parts_extra(flat, manual, items)
        found += pins_wired(flat, manual)
        if sketch:  # the tutorial's own sketch, when the lesson found it
            found += sketch_pins(flat, sketch)
        found += electrical(flat, tmp) + placement(flat, tmp)
        found += pin_table_law(flat, tmp, manual) + matrix_resistors(flat, tmp)
        return found, round(time.monotonic() - t0, 2)

    def phase(name, st, issues, secs, **extra):
        return {"phase": name, **st, "check_seconds": secs, "issues": len(issues),
                "issue_rules": dict(collections.Counter(i[0] for i in issues)), **extra}

    extra = {}
    for attempt in range(2):  # a stalled session or a safety-filter false positive: tried once more from the start
        b = PartsThenBuild(manual, catalogue_text, model, effort, web_domain, store.path)
        phases = []
        try:
            graph, st = b.start()
            graph_initial = graph
            listed = collections.Counter(p["type"] for p in expand(b.parts_graph)["nodes"])
            built = collections.Counter(p["type"] for p in expand(graph)["nodes"])
            phases.append({"phase": "parts", "builder": "claude turn 1", **b.parts_stats, "check_seconds": 0.0,
                           "parts_listed": sum(listed.values()),
                           "changed_in_build": sum(((listed - built) + (built - listed)).values()),
                           "looked_up": sorted({t for t in listed if t not in entries})})
            issues, secs = check(graph)
            phases.append(phase("build", st, issues, secs, builder="parts-then-build"))
            issues_first = len(issues)
            for n in range(REPAIRS):
                if not issues:
                    break
                graph, st = b.repair(repair_message(issues))
                issues, secs = check(graph)
                phases.append(phase(f"repair{n + 1}", st, issues, secs))
            if graph["new_part_types"]:  # upkeep while the session is open: new cards' facts may need a repair
                try:
                    extra["upkeep"], new_cards = upkeep(graph, store)
                except Exception as e:  # a shop or model failure while carding must not lose the graph
                    extra["upkeep"], new_cards = {"error": f"{type(e).__name__}: {str(e)[:200]}"}, {}
                if new_cards:
                    entries = {**entries, **new_cards}
                    tmp = part_catalogue.Catalogue(entries)
                    tmp.add_drafts(graph["new_part_types"])
                    found = electrical(expand(graph), tmp)
                    if found:
                        graph, st = b.repair(repair_message(found))
                        issues, secs = check(graph)
                        phases.append(phase("repair-after-upkeep", st, issues, secs))
            break
        except subprocess.TimeoutExpired as e:
            with open(out / "stalls.log", "a") as f:
                f.write(f"{case['id']} attempt {attempt + 1}: no result after {e.timeout}s; last events {e.output}\n")
            if attempt:
                raise
        except RuntimeError as e:
            if attempt or "safeguards" not in str(e):
                raise
        finally:
            b.close()
    first = next(p for p in phases if p["phase"] == "build")
    total = {"model": first.get("model"), "effort": effort, "route": first.get("route"), "version": "v6",
             "builder": "parts-then-build",
             "seconds": round(sum(p["seconds"] + p.get("check_seconds", 0) for p in phases), 1),
             "input_tokens": sum(p.get("input_tokens", 0) for p in phases),
             "output_tokens": sum(p.get("output_tokens", 0) for p in phases),
             "cost_usd": round(sum(p.get("cost_usd", 0) for p in phases), 4),
             "repair_rounds_used": sum(1 for p in phases if p["phase"].startswith("repair"))}
    return {"graph": graph, "graph_initial": graph_initial, "stats": total, "phases": phases,
            "issues_first": issues_first, "issues_final": len(issues), "final_issue_list": [list(i) for i in issues],
            **extra}


def save(case, saved, out):
    """The flat graph (repeats expanded) with the spec rules' problems: <out>/<case>/graph.json, result.json,
    response.json. Returns the flat graph and its catalogue (the seed and the parts Claude drafted)."""
    catalogue = part_catalogue.Catalogue(part_catalogue.arduino_seed())
    catalogue.add_drafts(saved["graph"]["new_part_types"])
    flat = expand(saved["graph"])
    d = out / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "response.json").write_text(json.dumps(saved, indent=1))
    (d / "graph.json").write_text(json.dumps(flat, indent=1))
    (d / "result.json").write_text(json.dumps(
        {"case": case["id"], "stats": saved["stats"], "phases": saved["phases"], "parts": len(flat["nodes"]),
         "edges": len(flat["edges"]), "problems": [list(p) for p in validate(flat, catalogue)],
         "notes": saved["graph"]["notes"], "issues_first": saved["issues_first"],
         "issues_final": saved["issues_final"]}, indent=1))
    return flat, catalogue


# ---- the graph Claude returns (its structured form) ----------------------------------------------------------
EdgeType = Literal["joined", "contact", "electrical", "blocks", "anchored"]


OverrideKind = Literal["replace", "props", "mirror", "add", "remove", "attach"]


class Port(BaseModel):
    name: str = Field(description="Port name, e.g. 'A', '1', '13', 'GND', 'stud.1.1'")
    kind: str = Field(description="Port kind, e.g. lead, header-pin, header-socket, breadboard-hole, stud, anti-stud, pin-hole")


class PartTypeDraft(BaseModel):
    """A catalogue entry for a part type the catalogue does not have yet."""
    type: str = Field(description="New part type id, GRAPH_SPEC §3, e.g. 'photoresistor', 'lego-3001'")
    name: str
    category: str = Field(description="e.g. resistor, led, board, sensor, connector, brick, plate")
    ports: List[Port]
    conducts: List[List[str]] = Field(description="Groups of this part's ports that are one electrical node (a wire's two ends). Empty if none")
    through: List[List[str]] = Field(description="Port pairs joined THROUGH the component, not one node; ordered from->to when directional (LED: ['A','C'])")
    symmetric: List[List[str]] = Field(description="Groups of interchangeable ports (resistor legs). Empty if none")
    polarized: bool
    connector: bool = Field(description="True if the part's only job is to join other parts (wire, breadboard, Technic pin)")
    mirror_of: Optional[str] = Field(description="Part type id of its mirror twin, or null")
    rotation_symmetry: Literal["none", "180", "90", "any"]


class KeyValue(BaseModel):
    key: str
    value: str


class PartRef(BaseModel):
    id: str = Field(description="Instance id, GRAPH_SPEC §3, e.g. r1, led1, uno, wire3, b12")
    type: str = Field(description="Catalogue part type, or a type from new_part_types")
    label: Optional[str] = Field(description="The manual's own name for it, or null")
    props: List[KeyValue] = Field(description="Instance properties: colour, value. Empty if none")


class EdgeOut(BaseModel):
    type: EdgeType
    u: str = Field(description="Part id")
    u_port: Optional[str] = Field(description="Port on u, or null if not port-specific")
    v: str = Field(description="Part id")
    v_port: Optional[str]
    method: Optional[str] = Field(description="insert, push-on, screw, slide, snap, solder, clip, rest ... or null")
    freedom: Optional[str] = Field(description="rigid, revolute, slider, cylindrical, ball, flexible, or null")
    reversible: Optional[str] = Field(description="hand, tool, damaging, permanent, or null")


class Override(BaseModel):
    copy_number: int = Field(description="Which copy (1-based) this override applies to")
    kind: OverrideKind
    target: str = Field(description="replace/props/remove: local part id. attach: the external endpoint 'part:port' as written in the template. mirror: ''. add: new local part id")
    value: str = Field(description="replace/add: part type. props: 'key=value'. attach: the endpoint 'part:port' to use for this copy. mirror/remove: ''")


class Repeat(BaseModel):
    """A sub-assembly built `times` times. Written once; code expands it."""
    group: str = Field(description="Group name; copies become <group><n>.<local id>, e.g. ledblock2.r")
    times: int
    parts: List[PartRef] = Field(description="Parts of ONE copy, with local ids")
    edges: List[EdgeOut] = Field(description="Edges of one copy. Endpoints that are not local part ids refer to parts outside the repeat")
    overrides: List[Override]


class ExtractedGraph(BaseModel):
    title: str
    source_id: str = Field(description="Official id: tutorial URL, LEGO set number, Sauder model number")
    new_part_types: List[PartTypeDraft] = Field(description="Only part types NOT in the provided catalogue")
    parts: List[PartRef] = Field(description="Every physical part outside repeats, including wires, connectors and the board")
    edges: List[EdgeOut]
    repeats: List[Repeat]
    notes: List[str] = Field(description="Assumptions or ambiguities in the manual. Empty if none")


# ---- the spec rules on a flat graph --------------------------------------------------------------------------
# Pairs of port kinds that may join (GRAPH_SPEC §5.2), plus electrical pairings.
COMPATIBLE = {
    frozenset(["stud", "anti-stud"]), frozenset(["pin", "pin-hole"]), frozenset(["axle", "axle-hole"]),
    frozenset(["lead", "breadboard-hole"]), frozenset(["wire-end", "breadboard-hole"]),
    frozenset(["wire-end", "header-socket"]), frozenset(["header-pin", "header-socket"]),
    frozenset(["header-pin", "breadboard-hole"]), frozenset(["lead", "header-socket"]),
    frozenset(["wire-end", "lead"]), frozenset(["wire-end", "header-pin"]), frozenset(["lug", "wire-end"]),
    frozenset(["lug", "breadboard-hole"]),  # breadboard potentiometers have pins, though the card says lug
    frozenset(["lead"]),  # legs twisted, clipped or soldered together (CircuitQuest build_methods)
    frozenset(["wire-end"]),
    frozenset(["axle", "pin-hole"]), frozenset(["clip", "bar"]), frozenset(["ball", "socket"]), frozenset(["hinge"]),
}


SINGLE_USE = {"stud", "anti-stud", "breadboard-hole", "header-socket", "pin-hole"}


def port_kind(catalogue, node_type, port):
    entry = catalogue.get(node_type)
    if not entry or port is None:
        return None
    if entry.get("port_rule") and entry["ports"]:
        return entry["ports"][0]["kind"]  # pattern-named ports (breadboard holes)
    for p in entry["ports"]:
        if p["name"] == port:
            return p["kind"]
    return "missing"


def validate(flat, catalogue):
    """Returns a list of problems: (rule, message)."""
    problems = []
    nodes = {n["id"]: n for n in flat["nodes"]}
    if len(nodes) != len(flat["nodes"]):
        dup = [k for k, c in collections.Counter(n["id"] for n in flat["nodes"]).items() if c > 1]
        problems.append(("ids", f"duplicate node ids: {dup[:5]}"))
    used = collections.Counter()
    touched = set()
    for e in flat["edges"]:
        for side in ("u", "v"):
            if e[side] not in nodes:
                problems.append(("refs", f"{e['id']}: unknown part '{e[side]}'"))
        if e["u"] not in nodes or e["v"] not in nodes:
            continue
        touched.update([e["u"], e["v"]])
        for side in ("u", "v"):  # V5: a join names the port on each side (a chip's pin, an LCD's pad), or no step
            entry = catalogue.get(nodes[e[side]]["type"])  # can place the part and no check can follow its pins
            if e["type"] == "joined" and e.get(side + "_port") is None and len((entry or {}).get("ports") or [0, 0]) > 1:
                problems.append(("V5", f"{e['id']}: the join to {e[side]} ({nodes[e[side]]['type']}) names no port: "
                                       f"say which of its pins it is"))
        ku = port_kind(catalogue, nodes[e["u"]]["type"], e.get("u_port"))
        kv = port_kind(catalogue, nodes[e["v"]]["type"], e.get("v_port"))
        for side, k in (("u", ku), ("v", kv)):
            if k == "missing":
                problems.append(("V4", f"{e['id']}: port '{e.get(side + '_port')}' not on {nodes[e[side]]['type']}"))
        if e["type"] == "joined" and ku and kv and "missing" not in (ku, kv):
            if frozenset([ku, kv]) not in COMPATIBLE:
                problems.append(("V3", f"{e['id']}: {ku} ↔ {kv} is not a compatible pair"))
        if e["type"] == "joined":
            for side, k in (("u", ku), ("v", kv)):
                if k in SINGLE_USE:
                    used[(e[side], e.get(side + "_port"))] += 1
    for (node, port), c in used.items():
        if c > 1:
            problems.append(("V4", f"single-use port {node}:{port} used {c} times"))
    for nid, n in nodes.items():
        if nid not in touched:
            problems.append(("V2", f"part {nid} ({n['type']}) has no connection"))
    return problems


# ---- electrical nets (connectors folded away) ----------------------------------------------------------------
class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def canonical_port(entry, port):
    rule = (entry or {}).get("alias")
    if not rule or port is None:
        return port
    if rule["mode"] == "strip":
        return port.split(".", 1)[0]
    if rule["mode"] == "prefix":
        for prefix in rule["prefixes"]:
            if port.startswith(prefix):
                return prefix
    return port


def nets(flat, catalogue):
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    uf = UnionFind()

    def key(part, port):
        return f"{part}:{canonical_port(catalogue.get(types.get(part)), port)}"

    for e in flat["edges"]:
        if e["type"] == "electrical" and e["u"] in types and e["v"] in types:
            uf.union(key(e["u"], e.get("u_port")), key(e["v"], e.get("v_port")))
    for part, t in types.items():
        for group in (catalogue.get(t) or {}).get("conducts", []):
            for a, b in zip(group, group[1:]):
                uf.union(key(part, a), key(part, b))
    groups = {}
    for k in list(uf.parent):
        part = k.split(":", 1)[0]
        entry = catalogue.get(types.get(part)) or {}
        if entry.get("connector"):
            continue
        groups.setdefault(uf.find(k), set()).add(k)
    return [frozenset(g) for g in groups.values() if len(g) >= 2]


# ---- repeated groups expanded into one flat graph ------------------------------------------------------------
def _props(prop_list):
    return {p["key"]: p["value"] for p in prop_list}


def expand(graph):
    """graph: ExtractedGraph as a dict. Returns {"nodes": [...], "edges": [...]}."""
    nodes = [{"id": p["id"], "type": p["type"], "label": p.get("label"), "props": _props(p.get("props", []))}
             for p in graph["parts"]]
    edges = [dict(e) for e in graph["edges"]]

    for rep in graph.get("repeats", []):
        local = {p["id"] for p in rep["parts"]}
        for n in range(1, rep["times"] + 1):
            ovs = [o for o in rep.get("overrides", []) if o["copy_number"] == n]
            prefix = f"{rep['group']}{n}."
            types = {p["id"]: p["type"] for p in rep["parts"]}
            props = {p["id"]: _props(p.get("props", [])) for p in rep["parts"]}
            removed, mirrored, attach = set(), False, {}
            for o in ovs:
                if o["kind"] == "replace":
                    types[o["target"]] = o["value"]
                elif o["kind"] == "props" and "=" in o["value"]:
                    k, v = o["value"].split("=", 1)
                    props.setdefault(o["target"], {})[k.strip()] = v.strip()
                elif o["kind"] == "remove":
                    removed.add(o["target"])
                elif o["kind"] == "add":
                    types[o["target"]] = o["value"]
                    local.add(o["target"])
                elif o["kind"] == "mirror":
                    mirrored = True
                elif o["kind"] == "attach":
                    attach[o["target"]] = o["value"]
            for pid, ptype in types.items():
                if pid in removed:
                    continue
                node = {"id": prefix + pid, "type": ptype, "label": None, "props": dict(props.get(pid, {})),
                        "group": rep["group"], "copy": n}
                if mirrored:
                    node["props"]["mirror"] = "true"
                nodes.append(node)

            def endpoint(part, port):
                if part in local:
                    return (None, None) if part in removed else (prefix + part, port)
                key = f"{part}:{port}" if port else part
                if key in attach:
                    new = attach[key]
                    return tuple(new.split(":", 1)) if ":" in new else (new, port)
                return part, port

            for e in rep["edges"]:
                u, up = endpoint(e["u"], e.get("u_port"))
                v, vp = endpoint(e["v"], e.get("v_port"))
                if u is None or v is None:
                    continue
                edges.append({**e, "u": u, "u_port": up, "v": v, "v_port": vp, "group": rep["group"], "copy": n})

    for i, e in enumerate(edges, 1):
        e["id"] = f"e{i}"
    return {"nodes": nodes, "edges": edges}


# ---- the electronics checks (laws) on a graph ----------------------------------------------------------------
SUPPLY = {"5V", "3V3", "VIN"}


TWO_LEGGED = {"led", "resistor", "button", "buzzer"}


def _board_role(key, types):
    part, port = key.split(":", 1)
    return role("board", port) if family(types.get(part)) == "board" else None


_NAMES = {}


def _card_name(type_id):
    """A part's name from the card store (a shop card the builder looked up is not in the check's catalogue)."""
    if not _NAMES:
        import json
        import pathlib
        f = pathlib.Path(__file__).resolve().parents[1] / "parts" / "arduino" / "cards_electronics.json"
        _NAMES.update({t: c.get("display_name") for t, c in json.loads(f.read_text()).items()} if f.exists() else {})
    return _NAMES.get(type_id)


def electronics(flat, catalogue, manual_text=""):
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    circuit_nets = nets(flat, catalogue)
    net_of = {k: i for i, n in enumerate(circuit_nets) for k in n}
    pullup = "INPUT_PULLUP" in manual_text or "pull_up=True" in manual_text
    for net in circuit_nets:
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
    settled = set(re.findall(r"^- .+? -> ([a-z0-9][a-z0-9.-]*)\s*$", manual_text, re.M))  # the parts note (part_review)
    for n in flat["nodes"]:  # E7: a part the reviewed parts list settled is built as that type, not a look-alike
        if not settled or n["type"] in settled:
            continue
        name = str((catalogue.get(n["type"]) or {}).get("name") or _card_name(n["type"]) or n["type"]).lower()
        like = sorted(t for t in settled if re.search(rf"\b{re.escape(t)}s?\b", name))
        if like:
            issues.append(("E7", f"{n['id']} is {n['type']} ({name}), but the tutorial's reviewed parts list has "
                                 f"{like[0]}: use {like[0]} (its colour or value as a property), as the parts list says"))
    for n in flat["nodes"]:
        fam = family(n["type"])
        if fam not in TWO_LEGGED:
            continue
        entry = catalogue.get(n["type"]) or {}
        legs = sorted({canonical_port(entry, p["name"]) for p in entry.get("ports", [])})
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
    spec = [(r, m) for r, m in validate(flat, catalogue)]
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


READS = ("digitalRead", "analogRead")


def code_pins(code, funcs=None):
    """Board pins the sketch drives or reads (copied from CircuitQuest's sketch check): pin constants resolved.
    funcs: only pins used by these calls (READS: what the sketch reads)."""
    consts = dict(re.findall(r"(?:const\s+)?(?:unsigned\s+)?(?:int|byte|uint8_t|short|long)\s+(\w+)\s*=\s*(A?\d+)\s*;", code))
    for k, v in re.findall(r"#define\s+(\w+)\s+(A?\d+)", code):  # the first definition: later ones sit in
        consts.setdefault(k, v)                                     # #else branches for other boards
    consts["LED_BUILTIN"] = "13"  # the Uno's on-board LED pin
    used = set()
    # a pin read with nothing on it for its noise (a random seed) needs no wire
    code = re.sub(r"randomSeed\s*\(\s*analogRead\s*\([^)]*\)", "randomSeed(", code)
    code = re.sub(r"\b\w*random\w*\s*=\s*analogRead\s*\([^)]*\)", "", code, flags=re.I)
    for func, arg in re.findall(r"\b(pinMode|digitalWrite|digitalRead|analogWrite|analogRead|tone|noTone)\s*\(\s*(\w+)", code):
        pin = consts.get(arg, arg)
        if func == "analogRead" and re.fullmatch(r"\d", pin):  # analogRead(0) reads analog pin A0
            pin = f"A{pin}"
        if re.fullmatch(r"\d+", pin) and 14 <= int(pin) <= 19:  # on the Uno, digital 14-19 are A0-A5
            pin = f"A{int(pin) - 14}"
        if funcs and func not in funcs:
            continue
        if re.fullmatch(r"A?\d+", pin) and func != "pinMode":  # a pin only set up, never read or written,
            used.add(pin)                                      # does nothing (a leftover pinMode(11, OUTPUT))
    return used


def sketch_pins(flat, code):
    """E11: every board pin the tutorial's sketch reads or writes is wired to something (the sketch says what is on
    a pin even when the text does not: a TMP36 powered from A0 and A2, a second button on pin 3)."""
    boards = {n["id"] for n in flat["nodes"] if family(n["type"]) == "board"}
    if not boards or not code:
        return []
    used = {re.sub(r"^D(\d+)$", r"\1", str(e[side + "_port"])) for e in flat["edges"] for side in ("u", "v")
            if e[side] in boards and e.get(side + "_port")}
    lines = code.splitlines()
    out = []
    # pins the sketch READS: without them the program cannot work, so the sketch wins over the page's text. Pins it
    # only drives may be another way to do what the circuit does (a TMP36 powered from A0/A2): not a repair
    for pin in sorted(code_pins(code, READS) - used - {"13"}):
        names = [pin] + re.findall(rf"\b(\w+)\s*=\s*{pin}\s*;", code) + re.findall(rf"#define\s+(\w+)\s+{pin}\b", code)
        code_lines = [ln.strip() for ln in lines if not re.match(r"\s*(//|/?\*)", ln)]  # code, not comments
        named = [ln for ln in code_lines if any(re.search(rf"\b{n}\b", ln) for n in names)]
        said = [ln for ln in named if re.search(r"=\s*" + pin + r"\s*;|#define", ln)][:1] + \
               [ln for ln in named if re.search(r"digitalRead|analogRead", ln)][:1]  # where it is named, where read
        at = " ... ".join(x[:90] for x in said)
        out.append(("E11", f"the tutorial's sketch reads board pin {pin} ({at}), but nothing is wired to it, so "
                           f"the program cannot work: wire what the sketch reads there (its comments say what), even "
                           f"if the page's text names another pin; the sketch is what runs"))
    return out


def electrical(flat, catalogue):
    """E8-E10, from the cards' electrical facts."""
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    facts = lambda pid: (catalogue.get(types.get(pid)) or {}).get("electrical") or {}
    circuit_nets = nets(flat, catalogue)
    board_logic = {pid: facts(pid).get("logic_v") for pid in types if family(types[pid]) == "board"}
    for net in circuit_nets:
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
    net_of = {k: i for i, n in enumerate(circuit_nets) for k in n}
    for pid, t in types.items():  # E9
        if not facts(pid).get("needs_series_resistor") or family(t) != "led":
            continue
        legs = [net_of.get(f"{pid}:{leg}") for leg in ("A", "C")]
        if None in legs:
            continue
        a_net, c_net = circuit_nets[legs[0]], circuit_nets[legs[1]]
        others = [k for k in a_net | c_net if not k.startswith(pid + ":")]
        drives = any(_board_role(k, types) not in (None, "GND") for k in a_net)
        grounded = any(_board_role(k, types) == "GND" for k in c_net)
        if drives and grounded and not any(family(types.get(k.split(":", 1)[0])) == "resistor" for k in others):
            issues.append(("E9", f"{pid} is wired from a board pin to ground with no series resistor"))
    return issues


def cells(shape, pos):
    """The stud cells a placed piece covers: unturned, its long side runs along x."""
    a, b = max(shape["w"], shape["l"]), min(shape["w"], shape["l"])
    dx, dy = (b, a) if pos["turned"] else (a, b)
    return {(pos["x"] + i, pos["y"] + j) for i in range(dx) for j in range(dy)}


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
    circuit_nets = nets(flat, catalogue)
    net_of = {k: i for i, net in enumerate(circuit_nets) for k in net}
    boards = [pid for pid, t in types.items() if family(t) == "board"]
    reach = {}  # net index -> circuit_nets reachable through one resistor
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
    circuit_nets = nets(flat, catalogue)
    for pid, t in types.items():
        ports = [p["name"] for p in (catalogue.get(t) or {}).get("ports", [])]
        rows = [p for p in ports if re.fullmatch(r"R\d+", p)]
        cols = [p for p in ports if re.fullmatch(r"C\d+", p)]
        if len(rows) < 2 or len(cols) < 2:
            continue
        with_res = lambda group: [p for p in group if any(f"{pid}:{p}" in n and any(
            family(types.get(k.split(":")[0])) == "resistor" for k in n) for n in circuit_nets)]
        on_rows, on_cols = with_res(rows), with_res(cols)
        if on_rows and on_cols:
            fewer, side = (on_rows, "rows") if len(on_rows) <= len(on_cols) else (on_cols, "columns")
            issues.append(("E12", f"{pid} ({t}) has resistors on both rows and columns: move the ones on {side} "
                                  f"({', '.join(fewer)}) to the other side, so every resistor is on the same side"))
    return issues


# ---- part families (for the checks) --------------------------------------------------------------------------
FAMILIES = [("board", r"arduino|uno"), ("breadboard", r"breadboard"), ("wire", r"wire|jumper|cable"),
            ("pot", r"potentiometer|\bpot\b|pot-|trimmer"),
            ("photoresistor", r"photo.?resistor|photocell|\bldr\b"), ("fsr", r"\bfsr\b|force.?sens"),
            ("led", r"\bled\b|led-|-led|^led"),
            ("resistor", r"resistor"), ("button", r"button|switch"),
            ("capacitor", r"capacitor"), ("crystal", r"crystal|xtal"), ("joystick", r"joystick")]


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
