"""Where a learner is in an Arduino lesson, from what they have actually wired.

What it is   from the joins a learner has made, in any order: which steps are done, which can come next (only
             DEPENDS_ON must come first), which column a part must share with another (ALIGNS_WITH), and whether a
             pin or part they swapped is allowed (DATA_STRUCTURE.md §4.1).
Used for     following a learner who does not build in the suggested order, and the steps graph's ALIGNS_WITH edges.
Where        lesson_store.py (plan, aligns, wires, join_ids), tutor_mcp.py (progress).

Order and position are different things:
  order      NEXT_STEP is only the suggested order. Only DEPENDS_ON must come first (a join goes onto a part another
             step puts out: the board, the breadboard). CHECK_NEEDS has no order: the check waits for the part.
  position   a wire has no place of its own: its end goes where the part it connects went, so that part's step
             comes first (a DEPENDS_ON like any other, via the two joins into the shared strip: step-3's wire goes
             in the column of the resistor's left leg). Two parts that share a column
             (ALIGNS_WITH: the LED's long leg and the resistor) may go in either order: the first fixes the column,
             the other must be in the same one. A wire's end never fixes a column: the part it goes with does. So the circuit is checked by its relations, not by fixed holes: a resistor in
             column 12 instead of 10 is right, and then the wire must go to column 12, not 10.

  progress(lesson_id, observed, moves) -> the learner's layout and each step's state
    observed  [(port, port)] as the camera or the bench reports them, with the lesson's instance ids
    moves     the learner's pin map {planned port: actual port} (lesson record: substitutions)
The layout maps each planned strip to the strip the learner used for it: the part that went in first fixes it (the
order of `observed`), and a later part planned for that strip must follow. It is wrong when a later part goes
elsewhere or ports planned for different strips
share one (`short`: two nets joined). A join to a board pin or another part's port must be that port (read
through the pin map; every GND pin is GND). A part with symmetric legs (a resistor) may go either way round.
Which holes are one strip, which pins are the same, and which legs may swap come from the parts catalogue
(`metadata.interchangeable`, parts_db.connection / either_way), the same facts the tutor and the page show.
A step is `done` (every join it makes is in and right), `partly done`, `not started`, `wrong` (a join is in but
breaks the layout) or `too early` (DEPENDS_ON is strict order: a step it depends on is not done, `blocked_by`);
`early` when it is done ahead of the suggested order but nothing it depends on is missing. ALIGNS_WITH sets no order:
it only checks that the two parts end up in the same column as each other, whichever column that is.
`targets` gives, for each join still to make, the hole it must go to now (the learner's strip where one is fixed).
Not for LEGO yet: there a piece can also block a later one (GRAPH_SPEC `blocks`).
"""
import collections
import itertools
import json

from graph import lesson_store


def _rules(cards, types):
    def rule(inst):
        return (lesson_store.definition(cards, types.get(inst, ""))[0] or {}).get("port_alias_rule") or {}
    return rule


def _where(cards, types, rule, inst, port):
    """A port as the check compares it: ('strip', 'bb1:12t') for a breadboard hole (any hole of the strip will do),
    ('port', 'uno:GND') for one of a group of the same pins, else ('port', 'uno:13'). From the part's stored groups in
    the catalogue (parts_db.connection: strips, rails, same pins); the card's old naming rule where it has none."""
    from graph.parts import part_catalogue
    found = part_catalogue.connection(lesson_store.definition(cards, types.get(inst, ""))[0], port)
    if found:
        kind, name = found
        return ("strip" if kind in ("strip", "rail") else "port"), f"{inst}:{name}"
    r = rule(inst)
    if r.get("mode") == "strip":
        return "strip", f"{inst}:{port.split('.', 1)[0]}"
    if r.get("mode") == "prefix":
        port = next((x for x in r.get("prefixes", []) if port.startswith(x)), port)
    return "port", f"{inst}:{port}"


def plan(inst, phys, cards):
    """Each step's joins: [(step, new part's port, kind, target)] with kind 'strip' (a breadboard strip) or
    'port' (a board pin or another part's port, GND pins as GND)."""
    types = {n["id"]: n["type"] for n in phys["nodes"]}
    rule = _rules(cards, types)
    edges = {e["id"]: e for e in phys["edges"]}
    out = []
    for e in inst["edges"]:
        if e["type"] != "MAKES":
            continue
        pe = edges.get(e["v"])
        if not pe or pe["type"] != "joined":
            continue
        p, (ti, tp) = f"{pe['u']}:{pe['u_port']}", (pe["v"], pe["v_port"])
        out.append((e["u"], p, *_where(cards, types, rule, ti, tp)))
    return out


def wires(phys, cards):
    """The wire instances of a circuit (jumper wires, cables): a wire has no place of its own."""
    return {n["id"] for n in phys["nodes"] if n["type"] == "jumper-wire" or
            (lesson_store.definition(cards, n["type"])[0] or {}).get("category") in ("wire", "cable")}


def join_ids(inst, phys):
    """{new part's port: the joined edge it goes in by}, for the joins the steps make."""
    edges = {e["id"]: e for e in phys["edges"]}
    return {f"{edges[e['v']]['u']}:{edges[e['v']]['u_port']}": e["v"] for e in inst["edges"]
            if e["type"] == "MAKES" and e["v"] in edges}


def aligns(joins, is_wire=lambda port: False, ids=None):
    """Position edges, per breadboard strip, from the first step (suggested order) that puts a port in it:
      a wire's end next to a part's leg   DEPENDS_ON: a wire has no place of its own, its end goes where that part
                                          went, so that step comes first (step-3's wire goes in the column of the
                                          resistor's left leg). `via` the two joins into the strip, as for any
                                          DEPENDS_ON: the evidence, not a second kind of dependency
      part next to part (or the wire first)  ALIGNS_WITH: they share the column, either may go in first"""
    ids = ids or {}
    by_strip = collections.defaultdict(list)
    for step, port, kind, target in joins:
        if kind == "strip":
            by_strip[target].append((step, port))
    deps, al = {}, {}
    for strip, rows in by_strip.items():
        first_step, first_port = rows[0]
        for step, port in rows[1:]:
            if step == first_step:
                continue
            if is_wire(port) and not is_wire(first_port):
                deps.setdefault((step, first_step), set()).update(x for x in (ids.get(port), ids.get(first_port)) if x)
            else:
                al.setdefault((step, first_step), []).append([port, first_port, strip.split(":", 1)[1]])
    return ([{"type": "DEPENDS_ON", "u": a, "v": b, "via": sorted(v, key=lambda x: int(x[1:]) if x[1:].isdigit() else x)}
             for (a, b), v in deps.items()] +
            [{"type": "ALIGNS_WITH", "u": a, "v": b, "ports": v} for (a, b), v in al.items()])


def progress(lesson_id, observed, moves=None, store=None):
    row, g = lesson_store._load(lesson_id, store)
    rec, inst, phys = g["lesson"], g["instruction"], g["physical"]
    if rec.get("lesson_type") != "arduino":
        raise ValueError("progress works for Arduino lessons only (LEGO needs `blocks` edges first)")
    cards = lesson_store._cards(lesson_store.PARTS)
    types = {n["id"]: n["type"] for n in phys["nodes"]}
    rule = _rules(cards, types)
    back = {v: k for k, v in (moves or {}).items()}  # actual -> planned
    joins = plan(inst, phys, cards)
    order = lesson_store._order(inst)
    # a wire's end takes its column from the part it goes next to: it never fixes a column itself
    wire_ids = wires(phys, cards)
    follows = {p for _, p, k, _ in joins if k == "strip" and p.split(":")[0] in wire_ids}
    nodes = {n["id"]: n for n in inst["nodes"]}

    def norm(port):  # an observed port as the plan names it: through the pin map; GND pins as GND; holes as strips
        port = back.get(port, port)
        i, p = port.split(":", 1)
        return _where(cards, types, rule, i, p)

    planned_ports = {p for _, p, _, _ in joins}
    seen = collections.defaultdict(set)  # a new part's port -> what it is joined to, as (kind, target)
    when = {}  # a new part's port -> when it went in (the order of `observed`)
    unexpected = []
    for n_obs, (a, b) in enumerate(observed):
        ka, ta = norm(a)
        kb, tb = norm(b)
        pa, pb = back.get(a, a), back.get(b, b)
        if pa in planned_ports or pa.split(":")[0] in {p.split(":")[0] for p in planned_ports}:
            seen[pa].add((kb, tb))
            when.setdefault(pa, n_obs)
        elif pb in planned_ports or pb.split(":")[0] in {p.split(":")[0] for p in planned_ports}:
            seen[pb].add((ka, ta))
            when.setdefault(pb, n_obs)
        else:
            unexpected.append((a, b))
    # parts with symmetric legs: try each way round, keep the one that breaks the fewest relations
    sym = {}  # from the catalogue's either-way-round groups (parts_db.either_way); the card's own field where none
    from graph.parts import part_catalogue
    for i, t in types.items():
        card = lesson_store.definition(cards, t)[0] or {}
        groups = part_catalogue.either_way(card) or [list(g) for g in (card.get("intrinsic_behaviour") or {}).get(
            "symmetric_port_groups") or []]
        for gr in groups:
            if i in wire_ids:
                continue  # a wire's two ends: each end follows the part it goes with already
            sym.setdefault(i, []).append(list(gr))
    choices = [[]]
    for i, groups in sym.items():
        for gr in groups:
            choices = [c + [(i, gr, perm)] for c in choices for perm in itertools.permutations(gr)]

    def evaluate(choice):
        swap = {f"{i}:{a}": f"{i}:{b}" for i, gr, perm in choice for a, b in zip(gr, perm)}
        got, at = {}, {}  # planned port -> its observed (kind, target)s, and when it went in
        for port, targets in seen.items():
            got[swap.get(port, port)] = targets
            at[swap.get(port, port)] = when.get(port, 0)
        strips = collections.defaultdict(list)  # planned strip -> [(when, observed strip)]
        for step, port, kind, target in joins:
            for k, t in got.get(port, ()):
                if kind == "strip" and k == "strip":
                    strips[target].append((port in follows, at[port], t))
        layout, problems = {}, []
        for s, obs in strips.items():  # a part's leg fixes the strip (the first in), never a wire's end before it
            layout[s] = min(obs)[1]
            layout[s] = min(obs)[2]
            if len({t for *_, t in obs}) > 1:
                problems.append(("split", s, sorted({t for *_, t in obs})))
        users = collections.defaultdict(list)
        for s, o in layout.items():
            users[o].append(s)
        for o, ss in users.items():
            if len(ss) > 1:
                problems.append(("short", o, sorted(ss)))
        return got, layout, problems

    got, layout, problems = min((evaluate(c) for c in choices), key=lambda r: len(r[2]))
    shorted = {s for kind, o, ss in problems if kind == "short" for s in ss}
    who = {p: s for s, p, _, _ in joins}
    errors = []
    for kind, a, b in problems:
        ports = [p for _, p, k, t in joins if k == "strip" and t in ([a] if kind == "split" else b) and p in got]
        if kind == "split":
            fixed = layout[a]
            late = [p for p in ports if not any(k == "strip" and t == fixed for k, t in got[p])]
            first = [p for p in ports if p not in late]
            errors.append(f"{', '.join(f'{p} ({who[p]})' for p in late)} must go in column {fixed.split(':', 1)[1]}, "
                          f"with {', '.join(f'{p} ({who[p]})' for p in first)}")
        else:
            errors.append(f"{', '.join(f'{p} ({who[p]})' for p in ports)} are all in column {a.split(':', 1)[1]}: "
                          f"they belong in different columns, so this joins circuits that must stay apart")
    steps = {}
    for sid in order:
        mine = [(p, k, t) for s, p, k, t in joins if s == sid]
        made, missing, wrong, targets = [], [], [], {}
        for p, k, t in mine:
            obs = got.get(p)
            if not obs:
                missing.append(p)
                taken = set(layout.values())
                if k == "strip" and t in layout:
                    targets[p] = f"{layout[t].split(':', 1)[1]} (where that strip's other part already is)"
                elif k == "strip":
                    targets[p] = ("any free column, e.g. " + t.split(":", 1)[1]) if t not in taken else \
                        f"any free column ({t.split(':', 1)[1]} is taken)"
                else:
                    targets[p] = t.split(":", 1)[1]
                continue
            ok = any(kk == k and (tt == t if k == "port" else (t in layout and layout[t] == tt and t not in shorted))
                     for kk, tt in obs)
            (made if ok else wrong).append(p)
        status = ("not a wiring step" if not mine else "wrong" if wrong else "done" if not missing
                  else "partly done" if made else "not started")
        steps[sid] = {"status": status, "made": made, "missing": missing, "wrong": wrong, "targets": targets,
                      "text": nodes[sid]["text"]}
    first_open = None
    for k, sid in enumerate(order):
        st = steps[sid]
        if st["status"] in ("not started", "partly done", "wrong", "too early") and first_open is None:
            first_open = sid
        open_ = lambda d: steps[d["v"]]["status"] in ("not started", "partly done", "wrong", "too early")  # noqa: E731
        # DEPENDS_ON is strict order: a step done before a step it depends on is not credited (too early)
        st["blocked_by"] = [d["v"] for d in inst["edges"] if d["type"] == "DEPENDS_ON" and d["u"] == sid and open_(d)
                            and st["status"] in ("done", "partly done")]
        if st["blocked_by"]:
            st["status"] = "too early"
            st["why"] = [f"{d['v']} first (via {', '.join(d['via'])})"
                         for d in inst["edges"] if d["type"] == "DEPENDS_ON" and d["u"] == sid and d["v"] in st["blocked_by"]]
        st["check_waits_for"] = sorted({d["v"] for d in inst["edges"] if d["type"] in ("CHECK_NEEDS", "ALIGNS_WITH")
                                        and d["u"] == sid and open_(d)})  # a shared column: the check needs it too
        st["early"] = st["status"] in ("done", "partly done") and any(
            steps[o]["status"] in ("not started", "partly done", "wrong") for o in order[:k])
    return {"lesson_id": lesson_id, "steps": steps, "next": first_open, "errors": errors, "unexpected": unexpected,
            "to_fix": [s for s in order if steps[s]["status"] == "wrong"],
            "layout": {s.split(":", 1)[1]: o.split(":", 1)[1] for s, o in layout.items()},
            "done": [s for s in order if steps[s]["status"] == "done"]}


if __name__ == "__main__":
    import sys
    print(json.dumps(progress(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else []), indent=1))
