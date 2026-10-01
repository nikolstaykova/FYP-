"""Spec rules on a flat graph (GRAPH_SPEC §9). V1 (counts vs inventory) is in score.py,
because it needs the manual's parts list."""
import collections
import re

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
