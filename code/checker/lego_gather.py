"""LEGO gathering in groups: the learner finds the pieces for the next few steps, builds them, then gathers again.

A LEGO learner has the set, so there is no whole-set check, and finding pieces before every single step is too slow
on a big set. So the steps are split into groups, and a gather card goes before each group:
- A numbered bag (from the booklet) always starts a new group: "Open bag 2 and find these pieces".
- Inside a bag, or in a lesson without bags, a group holds about PIECES pieces (more inside an open bag, where the
  pile is small) and at most MAX_STEPS steps. The sizes are balanced, so the last group is not a leftover.
- A booklet sub-build (7.1, 7.2, then 7 where it goes on) is gathered in one go, unless it is very big (over two
  groups' worth): then it is split at its sub-steps.
- A small lesson (up to SMALL pieces) has one gather card at the start.

groups(steps) works on the tutor's step list (tutor.live.steps), where each step has `number`, `bag`, `times` and
`parts` ([{what, count}]); it returns [{first, last, bag, open_bag, pieces, parts}] with first/last as indexes.
"""
import math

PIECES = 12  # pieces per group in a lesson without bags
PIECES_IN_BAG = 20  # inside an open bag the pile is small, so a group can hold more
MAX_STEPS = 8  # never more steps than this between two gather cards (a tiny group may be merged past it)
TINY = 0.5  # a group under this share of the target is merged into a neighbour
SMALL = 15  # a lesson this small is gathered once


def _pieces(step):
    """How many pieces the step uses (a sub-build made 4 times needs its pieces 4 times)."""
    return sum(p["count"] for p in step.get("parts") or []) * max(1, int(step.get("times") or 1))


def _units(steps):
    """The steps in runs that are gathered together: a booklet sub-build (7.1, 7.2 ... then 7) is one run."""
    out, run = [], []
    for i, s in enumerate(steps):
        run.append(i)
        if "." not in str(s.get("number") or ""):  # a main step closes the run
            out.append(run)
            run = []
    if run:
        out.append(run)
    return out


def _segments(steps, units):
    """The units by bag: a new bag starts a new segment. Returns [(bag or None, [units])]."""
    segs = []
    for u in units:
        bag = next((steps[i].get("bag") for i in u if steps[i].get("bag") is not None), None)
        if not segs or (bag is not None and bag != segs[-1][0]):
            segs.append((bag, []))
        segs[-1][1].append(u)
    return segs


def _split(steps, units, limit):
    """Units into groups of about `limit` pieces (balanced) and at most MAX_STEPS steps."""
    big = 2 * limit  # a sub-build this big is split at its sub-steps after all
    units = [x for u in units for x in
             ([[i] for i in u] if sum(_pieces(steps[i]) for i in u) > big else [u])]
    size = [sum(_pieces(steps[i]) for i in u) for u in units]
    total = sum(size)
    if total <= limit * 1.25:
        return [units] if sum(len(u) for u in units) <= MAX_STEPS * 2 else _by_steps(units)
    target = total / math.ceil(total / limit)
    groups, cur, got = [], [], 0
    for u, n in zip(units, size):
        if cur and (got >= target or got + n > target * 1.25 or sum(map(len, cur)) + len(u) > MAX_STEPS):
            groups.append(cur)
            cur, got = [], 0
        cur.append(u)
        got += n
    if cur:
        groups.append(cur)
    return _merge_tiny(groups, [sum(_pieces(steps[i]) for u in g for i in u) for g in groups], target)


def _merge_tiny(groups, size, target):
    """A group with only a few pieces (or none: a step that attaches what was built) joins its smaller neighbour."""
    while len(groups) > 1:
        k = min(range(len(groups)), key=lambda j: size[j])
        if size[k] >= target * TINY:
            break
        j = k - 1 if k == len(groups) - 1 or (k > 0 and size[k - 1] <= size[k + 1]) else k + 1
        a, b = sorted((j, k))
        groups[a:b + 1] = [groups[a] + groups[b]]
        size[a:b + 1] = [size[a] + size[b]]
    return groups


def _by_steps(units):
    groups, cur = [], []
    for u in units:
        if cur and sum(map(len, cur)) + len(u) > MAX_STEPS:
            groups.append(cur)
            cur = []
        cur.append(u)
    return groups + ([cur] if cur else [])


def _parts(steps, idx):
    """The pieces of these steps, added up, in the order they are first used."""
    got = {}
    for i in idx:
        times = max(1, int(steps[i].get("times") or 1))
        for p in steps[i].get("parts") or []:
            got[p["what"]] = got.get(p["what"], 0) + p["count"] * times
    return [{"what": w, "count": c} for w, c in got.items()]


def groups(steps):
    """The gather groups of a LEGO lesson's steps (see the module doc)."""
    if not steps:
        return []
    total = sum(_pieces(s) for s in steps)
    segs = _segments(steps, _units(steps))
    out = []
    for bag, units in segs:
        if total <= SMALL and len(segs) == 1:
            parts_groups = [units]
        else:
            parts_groups = _split(steps, units, PIECES_IN_BAG if bag is not None else PIECES)
        for k, g in enumerate(parts_groups):
            idx = [i for u in g for i in u]
            out.append({"first": idx[0], "last": idx[-1], "bag": bag, "open_bag": bag is not None and k == 0,
                        "pieces": sum(_pieces(steps[i]) for i in idx), "parts": _parts(steps, idx)})
    return out
