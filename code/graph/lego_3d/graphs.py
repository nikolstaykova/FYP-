"""A 3D-model lesson as the stored graphs: its physical graph and steps graph, and its parts list.

What it is   lego(set_id): the set's 3D model (lego_model) as the physical graph (every piece, every stud, pin and
             clip join, with ports) and the 3D lesson's plan (lego_3d/lesson.py) as the steps graph (each step
             PLACES its pieces and MAKES the joins between them and what is built; an attach step makes the joins
             between the sub-assembly and the model, whose pieces from then on count as the model's); the lesson
             record with the set's parts list matched to the model's pieces (parts/lego/lego_ids). export_lego: the
             lesson back in the form it was made in (lesson_store.audit checks nothing is lost).
Used for     storing a 3D-model lesson (DATA_STRUCTURE.md §3.3).
Where        lesson_store.py (build lego, audit).
"""
import collections
import json
import pathlib
import re

from graph.lesson_store import (PARTS, PART_CATALOGUES, _acts, _cards, _chain, _depends, _load, _order, _read,
                                   _rebrickable, _rel, definition, describe)


def lego(set_id, lessons_dir=None):
    """1 LEGO lesson: the physical graph from the set's 3D model, the instruction graph from its planned lesson.
    Every field of the saved lesson is carried over (audit() checks): a piece's placement for AR (`anchor`), its
    official step and sub-build as properties; sub-assemblies as nodes the steps BUILD and ATTACH; a piece's
    sits_on / holds / fastens are not stored again, they are the physical edges (audit() checks they agree)."""
    from graph.lego_3d import assembly, lesson as lego_lesson
    from graph import lego_model
    lessons_dir = pathlib.Path(lessons_dir or lego_lesson.OUT)
    saved = json.loads((lessons_dir / set_id / "lesson.json").read_text())
    plan, pieces = saved["lesson"], {p["id"]: p for p in saved["pieces"]}
    rows = lego_lesson.placed(set_id)
    real = [(nid, ref, pos, rot) for nid, ref, c, pos, rot in rows]
    assert [r[0] for r in rows] == list(pieces), "the 3D model and the lesson disagree on the pieces"
    joins = lego_model.connections(real)
    touch = lego_model.touching(real)
    for k, v in assembly.clip_joins({r[0]: r for r in real}, touch).items():
        joins.setdefault(k, v)

    nodes = []
    for nid, ref, c, pos, rot in rows:
        pc = pieces[nid]
        nodes.append({"id": nid, "type": f"lego-{pc['part_num']}", "label": pc["name"],
                      "props": {"colour": pc["colour"], "ldraw": ref, "ldraw_pos": [round(x, 2) for x in pos],
                                "ldraw_rot": [[round(x, 4) for x in r] for r in rot],
                                "anchor": {k: pc[k] for k in ("column", "row", "layer", "turn", "tilt", "roll") if k in pc},
                                "official_step": pc.get("official_step"), "official_sub": pc.get("official_sub")}})
    cards = _cards(PARTS)
    card_of = lambda i: definition(cards, f"lego-{pieces[i]['part_num']}")[0]  # noqa: E731
    edges = []
    for k, (kind, a, ap, b, bp) in sorted(joins.items(), key=lambda kv: sorted(kv[0])):
        if kind == "clip":  # u goes in: the bar goes into the clip
            a, ap, b, bp = b, bp, a, ap
        e = {"type": "joined", "u": a, "u_port": ap, "v": b, "v_port": bp,
             "method": None, "holds_by": None, "freedom": None, "reversible": None}
        describe(e, card_of)  # the same table as every domain's joins (the join table below, GRAPH_SPEC §5.2)
        edges.append(e)
    # pieces that touch without a stud, pin or clip join: contact; method rest when one rests on the other
    for k, v in sorted(((tuple(sorted(k)), v) for k, v in touch.items() if frozenset(k) not in joins)):
        edges.append({"type": "contact", "u": k[0], "u_port": None, "v": k[1], "v_port": None,
                      "method": "rest" if v == "rest" else None})
    for n, e in enumerate(edges, 1):
        e["id"] = f"e{n}"
    physical = {"lesson_id": set_id, "part_catalogue": PART_CATALOGUES["lego"], "nodes": nodes, "edges": edges,
                "made_by": "code, from the set's LDraw 3D model (exact)",
                "frames": {"ldraw_pos": "LDraw units (1 LDU = 0.4 mm), model stood upright",
                           "anchor": "the lesson's anchor frame for AR (lesson.model_of): studs and plates"}}

    # instruction graph: each step adds its pieces and makes every join between them and what is already built
    # (in the model or sub-assembly it belongs to); an attach step makes the joins between the sub-assembly and the rest
    stats = _read(lessons_dir / set_id / "stats.json", {})
    title = stats.get("name") or plan.get("title", set_id).strip()  # the record takes Rebrickable's name
    steps, acts, added_by, built, sub_of, extra = [], {}, {}, set(), {}, []
    subs = sorted({st["subassembly"] for st in plan["steps"] if st["subassembly"]} |
                  {st["attach"] for st in plan["steps"] if st.get("attach")})
    for name in subs:
        extra.append({"id": f"sub:{name}", "kind": "subassembly", "name": name})
    for n, st in enumerate(plan["steps"], 1):
        sid = f"step-{n}"
        new = list(st["pieces"])
        for p in new:
            added_by[p] = sid
            sub_of[p] = st["subassembly"] or ""
        now = built | set(new)
        made = [e["id"] for e in edges if e["type"] == "joined" and ({e["u"], e["v"]} & set(new))
                and {e["u"], e["v"]} <= now and sub_of.get(e["u"]) == sub_of.get(e["v"])]
        if st.get("attach"):  # and the joins between the sub-assembly and the rest, with any pieces this step adds
            mine = {p for p, s in sub_of.items() if s == st["attach"]}
            made += [e["id"] for e in edges if e["type"] == "joined" and ((e["u"] in mine) != (e["v"] in mine))
                     and {e["u"], e["v"]} <= now | mine and e["id"] not in made]
            for p in mine:  # attached, its pieces are part of what it went onto: a later piece joins them there
                sub_of[p] = st["subassembly"] or ""
        built |= set(new)
        acts[sid] = new + made
        steps.append({"id": sid, "kind": "step", "n": n, "text": st["instruction"], "bag": st.get("bag")})
        if st.get("attach"):
            extra_edges = {"type": "ATTACHES", "u": sid, "v": f"sub:{st['attach']}"}
            if st["subassembly"]:
                extra_edges["into"] = f"sub:{st['subassembly']}"
            acts.setdefault("_rel", []).append(extra_edges)
        elif st["subassembly"]:
            acts.setdefault("_rel", []).append({"type": "BUILDS", "u": sid, "v": f"sub:{st['subassembly']}"})
    rel = acts.pop("_rel", [])
    inst = {"lesson_id": set_id, "nodes": steps + extra,
            "edges": _chain([s["id"] for s in steps]) + rel + _acts(acts, physical) + _depends(acts, added_by, physical)}
    name, inventory = _rebrickable(set_id)
    figs = _minifig_parts(set_id)  # (part, colour id): a part of the set's minifigures
    listed = [{"part": f"lego-{r['part_num']}", "count": r["quantity"], "colour": r["color"], "name": r["name"],
               **({"from": "minifigure"} if (r["part_num"], r["color_id"]) in figs else {}),
               **({"category": r["category"]} if r.get("category") else {})}
              for r in inventory or [] if r.get("category") != "Stickers"]  # a sticker sheet is nothing to build
    record = {"lesson_id": set_id, "kind": "lesson", "lesson_type": "lego", "name": name or title,
              "link": f"https://rebrickable.com/sets/{set_id}/",
              "source": {"kind": "ldraw-model", "set": set_id, "file": f"data/sources/lego/{set_id}.mpd"},
              "plan_title": plan.get("title"), "notes": plan.get("notes", []),
              "parts_list": _lego_parts_list(listed, physical, inventory),
              "substitutions": {"pins": {}, "parts": {  # what each piece may differ in, as for every domain
                  n["id"]: (definition(cards, n["type"])[0] or {}).get("metadata", {}).get("substitutes")
                  for n in physical["nodes"] if (definition(cards, n["type"])[0] or {}).get("metadata", {}).get("substitutes")}},
              "stats": stats,
              "derived_from": _rel(lessons_dir / set_id / "lesson.json")}
    entry = {"lesson_id": set_id, "title": record["name"], "lesson_type": "lego", "source": record["source"],
             "derived_from": record["derived_from"]}
    return entry, {"lesson": record, "instruction": inst, "physical": physical, "document": None}


def _lego_parts_list(listed, physical, inventory):
    """The set's inventory, each row pointing at the model pieces it accounts for, matched by lego_ids (colour
    spelling, prints, moulds, names), with the rule used for each piece."""
    if not inventory:
        return {"from": None, "parts": listed, "problems": ["no inventory for this set"], "notes": []}
    from graph.parts.lego import lego_ids
    problems, notes = lego_ids.match(listed, physical["nodes"])
    # a minifigure's piece the inventory does not account for is a note, never a problem: a figure is not what the
    # lesson is judged on (its torso, arms and hands are listed in different ways by Rebrickable and by LDraw)
    figure = lambda p: re.search(r"\((?:lego-)?\w+, Minifig\b", p) or any(  # noqa: E731
        f"(lego-{c}," in p for _, cs in lego_ids.MINIFIG for c in cs if not c.startswith("~"))
    fig_extra = [p for p in problems if "in the model but not on the inventory" in p and figure(p)]
    problems = [p for p in problems if p not in fig_extra]
    notes += [f"minifigure piece: {p}" for p in fig_extra]
    # what the 3D model leaves out is a gap in the model, not an error, as long as it is the same model: every
    # model piece is on the inventory, its minifigures may be missing, and only a few set pieces are left out
    extra = [p for p in problems if "in the model but not on the inventory" in p]
    short = [r for r in listed if len(r.get("instances", [])) < (r["count"] or 0)]
    loose = [r for r in short if r.get("from") != "minifigure"]
    pieces = sum(r["count"] or 0 for r in listed if r.get("from") != "minifigure")
    warnings = []
    if not extra and sum((r["count"] or 0) - len(r.get("instances", [])) for r in loose) <= max(2, 0.05 * pieces):
        names = {r["part"] for r in short}
        gap = [p for p in problems if p.split(" ", 1)[0] in names]
        problems = [p for p in problems if p not in gap]
        figs = sorted({r["part"] for r in short if r.get("from") == "minifigure"})
        if figs:
            warnings.append(f"the 3D model has no minifigures ({len(figs)} parts of them on the inventory)")
        warnings += [f"not in the 3D model: {r['part']} {r.get('colour', '')} ({r['count'] - len(r.get('instances', []))} "
                     f"of {r['count']}), left out by the model's author" for r in loose]
    return {"from": "Rebrickable inventory of the set (with its minifigures)", "parts": listed, "problems": problems,
            "warnings": warnings, "notes": notes}


def _minifig_parts(set_id):
    """{(part number, colour id)} of the set's minifigures (Rebrickable), or an empty set."""
    try:
        from graph.parts.lego import inventory as rb
        t = rb.RebrickableDump.tables()
        inv = t["inv"].get(set_id)
        return set(rb.RebrickableDump.minifig_parts().get(inv[0], {})) if inv else set()
    except (OSError, KeyError):
        return set()


def export_lego(lesson_id, store=None):
    """The saved LEGO lesson.json, rebuilt from the network alone. A piece's sits_on / holds / fastens come from the
    physical edges: fastens = its stud, pin and clip joins; holds = those and every touch; sits_on = the pieces whose
    stud is in it (as lesson.model_of)."""
    row, g = _load(lesson_id, store)
    inst, phys = g["instruction"], g["physical"]
    nodes = {n["id"]: n for n in inst["nodes"]}
    acts = collections.defaultdict(list)
    for e in inst["edges"]:
        if e["type"] == "PLACES":
            acts[e["u"]].append(e["v"])
    sub = {e["u"]: e["v"][len("sub:"):] for e in inst["edges"] if e["type"] == "BUILDS"}
    att = {e["u"]: (e["v"][len("sub:"):], (e.get("into") or "sub:")[len("sub:"):]) for e in inst["edges"]
           if e["type"] == "ATTACHES"}
    steps = []
    for sid in _order(inst):
        st = nodes[sid]
        a, into = att.get(sid, ("", ""))
        steps.append({"pieces": acts[sid], "subassembly": into if sid in att else sub.get(sid, ""), "attach": a,
                      "instruction": st["text"], "bag": st.get("bag")})
    les = g["lesson"]
    rel = {k: collections.defaultdict(set) for k in ("sits_on", "holds", "fastens")}
    for e in phys["edges"]:
        rel["holds"][e["u"]].add(e["v"])
        rel["holds"][e["v"]].add(e["u"])
        if e["type"] == "joined":
            rel["fastens"][e["u"]].add(e["v"])
            rel["fastens"][e["v"]].add(e["u"])
            if str(e.get("u_port")).startswith("stud") and str(e.get("v_port")).startswith("anti"):  # a stud in it
                rel["sits_on"][e["v"]].add(e["u"])
    num = lambda x: int(re.sub(r"\D", "", x) or 0)  # noqa: E731
    pieces = []
    for n in phys["nodes"]:
        pr = n["props"]
        pieces.append({"id": n["id"], "part_num": n["type"][len("lego-"):], "name": n["label"], "colour": pr["colour"],
                       **pr["anchor"], **{k: sorted(rel[k][n["id"]], key=num) for k in ("sits_on", "holds", "fastens")},
                       "official_step": pr["official_step"], "official_sub": pr["official_sub"]})
    return {"lesson.json": {"lesson": {"title": les.get("plan_title"), "steps": steps, "notes": les.get("notes", [])},
                            "pieces": pieces}, "stats.json": les.get("stats")}
