"""Score an electronics graph with CircuitQuest's own checker (~/Desktop/CirquitQuest), so "electrically
equivalent" means exactly what CircuitQuest accepts.

  verdict(flat, catalogue, lesson_id, drop=()) -> "pass" | "harmless" | "substituted" | "wrong"

1. The graph's nets (wires and breadboard folded away) become CircuitQuest "detected pairs".
2. Its parts are aligned to the answer key's parts (consensus.align: same kind of part, then what they connect to),
   and renamed to the answer key's ids (r1, led1, uno ...), so CircuitQuest compares like with like.
3. core.checker.check(): pass, or harmless (a symmetric-leg swap: resistor legs, pot ends, button sides), after
   folding GND pins and breadboard strips (CircuitQuest's alias rules).
4. If wrong: core.engine._try_pin_substitution(), repeatedly: a part on another pin of the same pool (digital for
   digital, analog for analog; never bus pins, never in a lesson marked fixed_pins), as CircuitQuest's lessons accept.
"""
import itertools
import sys

from . import logical
from .catalogue import CQ
from .consensus import align
from .score import family, role


def _cq():
    sys.path.insert(0, str(CQ))
    from core import checker, engine
    from core.lesson import load_lesson
    from core.library import load_library
    return checker, engine, load_lesson, load_library()


def _pairs(nets):
    """Nets -> pairs chaining each net's pins (what CircuitQuest's build_nets turns back into nets)."""
    out = []
    for net in nets:
        pins = sorted(net)
        out += [[a, b] for a, b in zip(pins, pins[1:])]
    return out


def best_mapping(mapping, comps_b, check, limit=500):
    """Try re-pairing identical parts (same kind) among themselves; return the pairing with the fewest missing nets.
    Groups are permuted one at a time, up to `limit` checks in all."""
    best, best_missing = dict(mapping), check(mapping).get("missing", [])
    if not best_missing:
        return best
    groups = {}
    for ours, key in mapping.items():
        groups.setdefault(comps_b.get(ours), []).append(ours)
    tried = 0
    for kind, ours in groups.items():
        if len(ours) < 2:
            continue
        keys = [best[o] for o in ours]
        for perm in itertools.permutations(keys):
            tried += 1
            if tried > limit:
                return best
            trial = {**best, **dict(zip(ours, perm))}
            missing = check(trial).get("missing", [])
            if len(missing) < len(best_missing):
                best, best_missing = trial, missing
                if not missing:
                    return best
    return best


def verdict(flat, catalogue, lesson_id, drop=(), detail=False):
    checker, engine, load_lesson, library = _cq()
    lesson = load_lesson(lesson_id)
    diagram = lesson.diagram()
    parts = [p for p in diagram["parts"] if p["id"] not in drop]
    alias = checker.board_alias_map(parts, library)
    connectors = checker.connector_ids(parts, library)
    final = lesson.data.get("final_check", {}).get("expected_nets")
    if final:  # the lesson's own final check: what CircuitQuest tests a finished circuit against
        expected = [pair for pair in final if not any(p.split(":")[0] in drop for p in pair)]
    else:
        raw = checker.build_nets([[c[0], c[1]] for c in diagram["connections"]], alias)
        expected = _pairs([frozenset(p for p in n if p.split(":")[0] not in connectors | set(drop)) for n in raw])
    key_nets = [frozenset(n) for n in checker.build_nets(expected, alias)]
    key_nets = [frozenset(p for p in n if p.split(":")[0] not in connectors) for n in key_nets]
    key_nets = [n for n in key_nets if len(n) >= 2]

    # our nets, components only, then aligned and renamed to the answer key's ids
    our_nets = logical.nets(flat, catalogue)
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    comps_a = {p["id"]: family(p["type"]) for p in parts if p["id"] not in connectors}
    comps_b = {pid: family(t) for pid, t in types.items() if not (catalogue.get(t) or {}).get("connector")}
    def rel(nets, fam):
        """Relations for ALIGNMENT only, with legs named by role (a resistor's two legs are the same role), so a
        part wired the other way round still pairs with its counterpart. CircuitQuest itself sees the real legs."""
        keyed = lambda k: f"{k.split(':', 1)[0]}:{role(fam.get(k.split(':', 1)[0], ''), k.split(':', 1)[1])}"
        return {("e", *sorted((keyed(a), keyed(b)))) for n in nets for a, b in itertools.combinations(sorted(n), 2)}
    mapping = align(comps_a, rel(key_nets, comps_a), comps_b, rel(our_nets, comps_b))
    sym = {}
    for p in parts:
        for card in library.find_by_wokwi_type(p.get("type"), (p.get("attrs") or {}).get("value")):
            if card.get("symmetric_pins"):
                sym[p["id"]] = card["symmetric_pins"]

    def detected_for(m):
        rename = lambda k: f"{m.get(k.split(':', 1)[0], k.split(':', 1)[0] + '_extra')}:{k.split(':', 1)[1]}"
        return _pairs([frozenset(rename(k) for k in n) for n in our_nets])

    # Identical parts (six resistors) can be paired several ways; keep the pairing CircuitQuest finds closest,
    # so a scoring verdict never depends on which of two identical resistors got which id.
    mapping = best_mapping(mapping, comps_b, lambda m: checker.check(expected, detected_for(m), sym, alias, connectors))
    detected = detected_for(mapping)
    result = checker.check(expected, detected, sym, alias, connectors)
    explain = lambda v: {"verdict": v, "missing": result.get("missing", []), "conflicts": result.get("conflicts", []),
                         "mapping": mapping} if detail else v
    if result["verdict"] in ("pass", "harmless"):
        return explain(result["verdict"])
    boards = engine._board_component_ids(parts, library)
    token = engine._FIXED_PINS.set(bool(lesson.data.get("fixed_pins")))
    try:
        for _ in range(12):  # one substitution per call, as many as the circuit needs
            sub, original, actual = engine._try_pin_substitution(expected, detected, sym, alias, connectors,
                                                                 board_component_ids=boards, lesson=lesson,
                                                                 library=library)
            if sub is None:
                return explain("wrong")
            expected = [[actual if p == original else p for p in pair] for pair in expected]
            if checker.check(expected, detected, sym, alias, connectors)["verdict"] in ("pass", "harmless"):
                return explain("substituted")
    finally:
        engine._FIXED_PINS.reset(token)
    return explain("wrong")
