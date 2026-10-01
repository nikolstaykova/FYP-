"""Repeated sub-assemblies -> one flat graph (GRAPH_SPEC §8, RESEARCH.md R19).

A repeat with times=N becomes N real copies: every local part id becomes
<group><n>.<id> and every edge is copied. Endpoints that are not local part
ids refer to parts outside the repeat and stay as they are, unless an
`attach` override for that copy redirects them.
"""


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
            ovs = [o for o in rep.get("overrides", []) if o["copy"] == n]
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
