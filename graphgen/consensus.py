"""Two independent builds, keep what they agree on (v5; any domain: LEGO, electronics, furniture later).

Two builders work on the same manual without seeing each other. Their graphs cannot be compared edge by edge:
ids differ (r1 vs r2, b7 vs b9) and physical routes differ (another breadboard hole, another wire). So both are
compared on their LOGICAL view (Layer 3), which every domain has:
  - electrical relations: two component ports in the same net (wires and breadboard folded away)
  - mechanical relations: two components joined directly (a brick on a brick, a pin in a hole)
Steps:
  1. align components of B to A: same type, then neighbourhood labels refined three times (Weisfeiler-Lehman
     style), then greedily by already-aligned neighbours
  2. a relation is AGREED when the aligned version is also in B
  3. the result is A's graph with every component B does not have, and every connection that supports a
     relation B does not share, removed. Wires and breadboards stay; what they carry is decided by the nets.
"""
import collections
import itertools

from . import logical
from .expand import expand


def _components(flat, catalogue):
    return {n["id"]: n["type"] for n in flat["nodes"] if not (catalogue.get(n["type"]) or {}).get("connector")}


def relations(flat, catalogue):
    """{("e", a_key, b_key)} electrical port pairs in one net and {("j", a, b)} direct joins between components."""
    comps = _components(flat, catalogue)
    rel = set()
    for net in logical.nets(flat, catalogue):
        keys = sorted(k for k in net if k.split(":", 1)[0] in comps)
        rel.update(("e", a, b) for a, b in itertools.combinations(keys, 2))
    for e in flat["edges"]:
        if e["type"] in ("joined", "contact") and e["u"] in comps and e["v"] in comps and e["u"] != e["v"]:
            rel.add(("j", *sorted((e["u"], e["v"]))))
    return rel, comps


def _neighbours(rel):
    nb = collections.defaultdict(list)
    for kind, a, b in rel:
        pa, pb = a.split(":", 1)[0], b.split(":", 1)[0]
        nb[pa].append((kind, a.split(":", 1)[1] if ":" in a else "", pb, b.split(":", 1)[1] if ":" in b else ""))
        nb[pb].append((kind, b.split(":", 1)[1] if ":" in b else "", pa, a.split(":", 1)[1] if ":" in a else ""))
    return nb


def _labels(comps, nb, rounds=3):
    lab = dict(comps)
    for _ in range(rounds):
        lab = {n: hash((lab[n], tuple(sorted((k, mp, lab.get(o, ""), op) for k, mp, o, op in nb.get(n, []))))) for n in comps}
    return lab


def align(comps_a, rel_a, comps_b, rel_b):
    """{b_id: a_id}: components of B mapped onto components of A."""
    nb_a, nb_b = _neighbours(rel_a), _neighbours(rel_b)
    la, lb = _labels(comps_a, nb_a), _labels(comps_b, nb_b)
    mapping, used = {}, set()
    groups_a = collections.defaultdict(list)
    for n in sorted(comps_a):
        groups_a[la[n]].append(n)
    for n in sorted(comps_b):  # 1. identical neighbourhood labels
        cand = [a for a in groups_a.get(lb[n], []) if a not in used]
        if cand:
            mapping[n] = cand[0]
            used.add(cand[0])
    changed = True
    while changed:  # 2. same type, most neighbours already aligned
        changed = False
        for n in sorted(comps_b):
            if n in mapping:
                continue
            mine = {mapping.get(o) for _, _, o, _ in nb_b.get(n, [])} - {None}
            best, score = None, -1
            for a in sorted(comps_a):
                if a in used or comps_a[a] != comps_b[n]:
                    continue
                s = len(mine & {o for _, _, o, _ in nb_a.get(a, [])})
                if s > score:
                    best, score = a, s
            if best:
                mapping[n] = best
                used.add(best)
                changed = True
    return mapping


def _map_key(key, mapping):
    part, _, port = key.partition(":")
    return f"{mapping[part]}:{port}" if port else mapping[part]


def agree(graph_a, graph_b, catalogue):
    """Returns (graph = A restricted to what B agrees with, report)."""
    flat_a, flat_b = expand(graph_a), expand(graph_b)
    rel_a, comps_a = relations(flat_a, catalogue)
    rel_b, comps_b = relations(flat_b, catalogue)
    mapping = align(comps_a, rel_a, comps_b, rel_b)
    rel_b_in_a = set()
    for kind, a, b in rel_b:
        pa, pb = a.split(":", 1)[0], b.split(":", 1)[0]
        if pa in mapping and pb in mapping:
            x, y = sorted((_map_key(a, mapping), _map_key(b, mapping)))
            rel_b_in_a.add((kind, x, y))
    agreed = rel_a & rel_b_in_a
    matched = set(mapping.values())
    disputed_ports = {k for kind, a, b in rel_a - agreed if kind == "e" for k in (a, b)}
    disputed_joins = {(a, b) for kind, a, b in rel_a - agreed if kind == "j"}

    def keep_edge(e):
        for side in ("u", "v"):
            part = e[side]
            if part in comps_a and part not in matched:
                return False
            if part in comps_a and e.get(side + "_port") is not None:
                key = f"{part}:{logical.canonical_port(catalogue.get(comps_a[part]), e[side + '_port'])}"
                if key in disputed_ports:
                    return False
        if e["type"] in ("joined", "contact") and tuple(sorted((e["u"], e["v"]))) in disputed_joins:
            return False
        return True

    nodes = [n for n in flat_a["nodes"] if n["id"] not in comps_a or n["id"] in matched]
    edges = [e for e in flat_a["edges"] if keep_edge(e)]
    graph = {"title": graph_a.get("title", ""), "source_id": graph_a.get("source_id", ""),
             "new_part_types": graph_a.get("new_part_types", []),
             "parts": [{"id": n["id"], "type": n["type"], "label": n.get("label"),
                        "props": [{"key": k, "value": v} for k, v in (n.get("props") or {}).items()]} for n in nodes],
             "edges": [{k: v for k, v in e.items() if k not in ("id", "group", "copy")} for e in edges],
             "repeats": [], "notes": graph_a.get("notes", []) + [f"Consensus of two independent builds: kept "
                                                                   f"{len(agreed)} of {len(rel_a)} relations."]}
    report = {"components_a": len(comps_a), "components_b": len(comps_b), "aligned": len(mapping),
              "relations_a": len(rel_a), "relations_b": len(rel_b), "agreed": len(agreed),
              "edges_a": len(flat_a["edges"]), "edges_kept": len(edges),
              "components_dropped": len(comps_a) - len(matched)}
    return graph, report
