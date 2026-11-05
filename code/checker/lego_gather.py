"""LEGO gathering in groups: the learner finds the pieces for the next few steps, shows them to the camera, builds
them, then gathers again.

A LEGO learner has the set, so there is no whole-set check, and finding pieces before every single step is too slow
on a big set. So the steps are split into groups, and a gather card goes before each group. Each card is checked
from one photo of the pieces laid out (checker.lego_check), so a card must stay small enough for a model to see
every piece: about PIECES pieces and at most KINDS different kinds.
- A numbered bag (from the booklet) always starts a new group: "Open bag 2 and find these pieces".
- A group holds at most MAX_STEPS steps. Sizes are balanced, so the last group is not a leftover, and a group with
  very few pieces joins a neighbour when the two still fit on one card.
- A booklet sub-build (7.1, 7.2, then 7 where it goes on) is gathered in one go, unless it is too big: then it is
  split at its sub-steps.
- A single step with more pieces than a card holds gets several cards in a row ("part 1 of 2").

groups(steps) works on the tutor's step list (tutor.live.steps), where each step has `number`, `bag`, `times` and
`parts` ([{what, count, ...}]); it returns [{first, last, bag, open_bag, pieces, parts, part, of}] with first/last
as step indexes (part/of number the cards of one group that had to be split).
"""
import math

PIECES = 10  # pieces per card, about
KINDS = 8  # different pieces per card, at most
MAX_STEPS = 8  # never more steps than this between two gather cards
TINY = 0.5  # a group under this share of the target joins a neighbour (when the two still fit)


def _pieces(step):
    """How many pieces the step uses (a sub-build made 4 times needs its pieces 4 times)."""
    return sum(p["count"] for p in step.get("parts") or []) * max(1, int(step.get("times") or 1))


def _kinds(steps, idx):
    return {p["what"] for i in idx for p in steps[i].get("parts") or []}


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


def _fits(steps, idx, limit):
    return sum(_pieces(steps[i]) for i in idx) <= limit * 1.25 and len(_kinds(steps, idx)) <= KINDS


def _split(steps, units):
    """Units into groups of about PIECES pieces (balanced), at most KINDS kinds and MAX_STEPS steps."""
    units = [x for u in units for x in ([[i] for i in u] if not _fits(steps, u, PIECES) else [u])]
    flat = [i for u in units for i in u]
    total = sum(_pieces(steps[i]) for i in flat)
    if _fits(steps, flat, PIECES) and len(flat) <= MAX_STEPS:
        return [units]
    target = total / max(1, math.ceil(total / PIECES))
    groups, cur = [], []
    for u in units:
        idx = [i for g in cur for i in g]
        got = sum(_pieces(steps[i]) for i in idx)
        n = sum(_pieces(steps[i]) for i in u)
        if cur and (got >= target or got + n > target * 1.25 or len(idx) + len(u) > MAX_STEPS
                    or len(_kinds(steps, idx + u)) > KINDS):
            groups.append(cur)
            cur = []
        cur.append(u)
    if cur:
        groups.append(cur)
    return _merge_tiny(steps, groups, target)


def _merge_tiny(steps, groups, target):
    """A group with only a few pieces (or none: a step that attaches what was built) joins its smaller neighbour,
    when the two still fit on one card (an empty group always joins)."""
    def size(g):
        return sum(_pieces(steps[i]) for u in g for i in u)
    while len(groups) > 1:
        order = sorted(range(len(groups)), key=lambda j: size(groups[j]))
        for k in order:
            if size(groups[k]) >= target * TINY:
                return groups
            for j in sorted({k - 1, k + 1} & set(range(len(groups))), key=lambda j: size(groups[j])):
                a, b = sorted((j, k))
                idx = [i for g in groups[a] + groups[b] for i in g]
                if size(groups[k]) == 0 or _fits(steps, idx, PIECES):
                    groups[a:b + 1] = [groups[a] + groups[b]]
                    break
            else:
                continue
            break
        else:
            return groups
    return groups


def _parts(steps, idx):
    """The pieces of these steps, added up, in the order they are first used (each keeps its other fields)."""
    got = {}
    for i in idx:
        times = max(1, int(steps[i].get("times") or 1))
        for p in steps[i].get("parts") or []:
            if p["what"] in got:
                got[p["what"]]["count"] += p["count"] * times
            else:
                got[p["what"]] = {**p, "count": p["count"] * times}
    return list(got.values())


def _chunks(parts):
    """A list too long for one card, in cards of about PIECES pieces and at most KINDS kinds (a row is never split)."""
    total = sum(p["count"] for p in parts)
    n = max(math.ceil(total / (PIECES * 1.25)), math.ceil(len(parts) / KINDS))
    target = total / n
    out, cur = [], []
    for p in parts:
        got = sum(x["count"] for x in cur)
        if cur and (got >= target or got + p["count"] > target * 1.25 or len(cur) >= KINDS):
            out.append(cur)
            cur = []
        cur.append(p)
    return out + ([cur] if cur else [])


def groups(steps):
    """The gather cards of a LEGO lesson's steps (see the module doc)."""
    if not steps:
        return []
    out = []
    for bag, units in _segments(steps, _units(steps)):
        for k, g in enumerate(_split(steps, units)):
            idx = [i for u in g for i in u]
            parts = _parts(steps, idx)
            cards = [parts] if not parts or (sum(p["count"] for p in parts) <= PIECES * 1.25
                                             and len(parts) <= KINDS) else _chunks(parts)
            for c, chunk in enumerate(cards):
                out.append({"first": idx[0], "last": idx[-1], "bag": bag, "open_bag": bag is not None and k == 0 and c == 0,
                            "pieces": sum(p["count"] for p in chunk), "parts": chunk, "part": c + 1, "of": len(cards)})
    return out
