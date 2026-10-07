"""v4 Path A: the build graph straight from an LDraw model (.mpd/.ldr), by code, no model call.

Every part line is a node (type `lego-<LDraw part number>`, LDraw colour in props); which pieces rest on which
comes from each piece's real shape in the parts library (ldraw_geometry.py), for every kind of piece; the `0 STEP`
lines of the model and its sub-models give the build order.
Pieces resting on pieces and pieces inside pieces (pins, axles) become `joined` edges; pieces side by side become
`contact` edges (GRAPH_SPEC: touching, not fastened). Limit: a clip on a bar or a hinge whose boxes only touch at a
point is not found.
"""
import re
import sys
import time

from . import truth


def steps_of(mpd_text):
    """Step number for each part, in the same order as truth.flatten_mpd lists them."""
    files, embedded = truth.mpd_sections(mpd_text)
    out = []

    def walk(name, step, depth=0):
        for line in files[name]:
            b = line.split()
            if b[:2] in (["0", "STEP"], ["0", "ROTSTEP"]):  # sub-models are built in their own steps first
                step[0] += 1
            if len(b) < 15 or b[0] != "1":
                continue
            ref = truth.ldraw_key(" ".join(b[14:]))
            if ref in files and ref not in embedded and depth < 10:
                walk(ref, step, depth + 1)
            else:
                out.append(step[0] + 1)

    walk(next(iter(files)), [0])
    return out


_INDEX = []


def _index(lego_ldraw):
    """The LDraw parts-library index, read once per process (it is the same for every set)."""
    if not _INDEX:
        _INDEX.append(lego_ldraw.library_index())
    return _INDEX[0]


def build(mpd_text, title, source_id, studs=False):
    """Returns (graph in ExtractedGraph form, stats, steps {node id: step})."""
    sys.path.insert(0, str(truth.pathlib.Path(__file__).resolve().parents[1] / "research" / "scrape"))
    import lego_ldraw
    t0 = time.monotonic()
    from . import ldraw_geometry
    index = _index(lego_ldraw)
    ldraw_geometry.register(mpd_text)  # parts the model file carries itself
    placed = truth.flatten_mpd(mpd_text, index)
    order = steps_of(mpd_text)
    nodes = [{"id": f"b{i}", "part": ref, "desc": lego_ldraw.describe(ref, index), "colour": colour}
             for i, (ref, colour, pos, rot) in enumerate(placed, 1)]
    parts = [{"id": n["id"], "type": "lego-" + re.sub(r"\.dat$", "", n["part"]), "label": n["desc"],
              "props": [{"key": "ldraw_colour", "value": n["colour"]}]} for n in nodes]
    # every piece's real box from the library: a piece joins each piece it rests on, whatever its shape
    where = [(f"b{i}", ref, pos, rot) for i, (ref, colour, pos, rot) in enumerate(placed, 1)]
    touching = ldraw_geometry.touching(where)
    if studs:  # v6: joins from the library's stud, hole and pin primitives, with ports; boxes only for contacts
        from . import ldraw_studs
        found = ldraw_studs.connections(where)
        edges = [{"type": "joined", "u": a, "u_port": ap, "v": b, "v_port": bp, "method": "clutch" if how == "clutch" else "insert",
                  "freedom": "rigid" if how == "clutch" else "revolute", "reversible": "hand"}
                 for how, a, ap, b, bp in sorted(found.values())]
        joined = set(found)
        edges += [{"type": "contact", "u": a, "u_port": None, "v": b, "v_port": None, "method": None, "freedom": None,
                   "reversible": None} for (a, b) in sorted(tuple(sorted(k)) for k, how in touching.items() if k not in joined)]
    else:
        edges = [{"type": "contact" if how == "contact" else "joined", "u": a, "u_port": None, "v": b, "v_port": None,
                  "method": None if how == "contact" else how, "freedom": "rigid", "reversible": "hand"}
                 for (a, b), how in sorted((tuple(sorted(k)), v) for k, v in touching.items())]
    geo = {"nodes": nodes}
    graph = {"title": title, "source_id": source_id, "new_part_types": [], "parts": parts, "edges": edges,
             "repeats": [], "notes": ["Built by code from the LDraw model (no model call)."]}
    steps = {n["id"]: s for n, s in zip(geo["nodes"], order)} if len(order) == len(geo["nodes"]) else {}
    stats = {"model": "code", "route": "ldraw", "seconds": round(time.monotonic() - t0, 3), "input_tokens": 0,
             "output_tokens": 0, "cost_usd": 0.0}
    return graph, stats, steps
