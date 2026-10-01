"""Logical view (GRAPH_SPEC §7): electrical nets, with connectors folded away.

Ports are expanded to nodes; `electrical` edges join them; inside a part,
alias rules (breadboard strips, the board's GND pins) and `conducts` groups
(a wire's two ends) join them too. A net is reported as the set of ports on
non-connector parts.
"""


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
