"""How well a booklet lesson reads its steps, measured against the set's 3D model (never used to build it).

The LDraw model of a set is drawn step by step as LEGO's booklet is (each piece's `official_step`), so it says which
pieces each booklet step really adds. The booklet lesson's steps, in their order, are lined up with the model's
steps in theirs (a monotone alignment that matches the most pieces: the two count sub-build steps differently), and
each piece the lesson places is scored:

  exact    in the step the model has it in
  shifted  one step early or late (the reader saw it in the wrong picture)
  wrong    a piece the model's step does not have nearby (misread, or counted twice)
  missed   a model piece no lesson step places
Minifigure pieces are left out on both sides (a booklet shows the figure whole, a model in its pieces).

  .venv-research/bin/python tests/tools/booklet_eval.py 40396-1 30312-1
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]


def _key(part, colour):
    from graph.parts.lego import lego_ids
    return lego_ids.base(part), lego_ids.colour_key(colour)


def _figure(part):
    """A minifigure's piece (torso, legs, head, arms, hands...): left out of the score. A booklet shows a figure whole
    and a 3D model in its pieces, and the figure is not what the lesson's steps are judged on."""
    from graph.parts.lego import lego_ids
    n = lego_ids._num(part)
    return lego_ids.components(part) is not None and any(rx.match(n) for rx, _ in lego_ids.MINIFIG) or \
        n in {c for _, cs in lego_ids.MINIFIG for c in cs} or n.startswith(("3626", "973", "970"))


def truth(set_id):
    """The model's steps in order: [Counter{(design, colour): n}], each model piece named as the set's inventory
    names it where lego_ids matches the two (LDraw and Rebrickable number some parts differently)."""
    from graph.parts.lego import lego_ids
    import lesson_graphs as lg
    from graph.lego_3d.lesson import model_of
    _, inv = lg._rebrickable(set_id)
    rows = [(f"lego-{r['part_num']}", r["name"], lego_ids.colour_key(r["color"])) for r in inv or []]
    by = collections.defaultdict(collections.Counter)
    for p in model_of(set_id):
        if p.get("official_step") is None or _figure(f"lego-{p['part_num']}"):
            continue
        c = lego_ids.colour_key(p["colour"])
        mine = f"lego-{p['part_num']}"
        row = next((r for r in rows if r[2] == c and lego_ids.same_part(r[0], r[1], mine, p.get("name"))), None) or \
            next((r for r in rows if lego_ids.same_part(r[0], r[1], mine, p.get("name"))), None)  # a model in another
        if not row:  # the set lists it as an assembly the model has in pieces (lever 298c02: 4592 and 4593): the
            asm = next((r for r in rows if (lego_ids.components(r[0]) or ())[:1] and any(  # assembly counts once,
                lego_ids.same_part(f"lego-{x}", None, mine, None) for x in lego_ids.components(r[0]))), None)  # at
            if asm:                                                                         # its first piece
                if not lego_ids.same_part(f"lego-{lego_ids.components(asm[0])[0]}", None, mine, None):
                    continue
                row = asm
        by[p["official_step"]][(_key(row[0], "")[0], row[2]) if row else _key(mine, p["colour"])] += 1  # colour
        # (an older model's 'Light Grey' for the set's 'Light Bluish Gray'): the set's own colour
    return [by[k] for k in sorted(by)]


def lesson_steps(set_id):
    """The booklet lesson's steps in order: [(label, Counter)], from its reads (times included)."""
    d = ROOT / "data" / "lessons" / "booklet" / set_id
    for prev in ("redo6_prev", "redo5_prev", "redo4_prev"):
        if not (d / "reads.json").exists() and (d / prev / "reads.json").exists():
            d = d / prev  # being redone: the previous run meanwhile
    steps = json.loads((d / "steps.json").read_text())
    reads = {r["step"]: r for r in json.loads((d / "reads.json").read_text())["reads"]}
    out = []
    for s in steps:
        r = reads.get(s["step"], {"adds": []})
        c = collections.Counter()
        for a in r["adds"]:
            if _figure(a["part"]):
                continue
            c[_key(a["part"], a["colour"])] += a["count"] * r.get("times", s.get("times", 1))
        out.append((s["label"], c))
    return out


def align(lesson, model):
    """Each lesson step -> a run of consecutive model steps [lo, hi) (a model may have one step per piece, or the
    booklet's own steps), in order, covering the model, matching the most pieces (dynamic programming over where
    each run ends). Returns [(lo, hi)] per lesson step (an empty run is (k, k))."""
    n, m = len(lesson), len(model)
    pref = [collections.Counter()]
    for c in model:
        pref.append(pref[-1] + c)
    gain = lambda i, lo, hi: sum((lesson[i][1] & (pref[hi] - pref[lo])).values())  # noqa: E731
    NEG = float("-inf")
    best = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0
    for i in range(n):
        for lo in range(m + 1):
            if best[i][lo] == NEG:
                continue
            for hi in range(lo, m + 1):
                v = best[i][lo] + gain(i, lo, hi)
                if v > best[i + 1][hi]:
                    best[i + 1][hi], back[i + 1][hi] = v, lo
    hi = max(range(m + 1), key=lambda h: (best[n][h], h))
    runs = []
    for i in range(n, 0, -1):
        lo = back[i][hi]
        runs.append((lo, hi))
        hi = lo
    return runs[::-1]


def score(set_id):
    model, lesson = truth(set_id), lesson_steps(set_id)
    if not model:
        return None
    runs = align(lesson, model)
    pool = lambda lo, hi: sum((model[j] for j in range(lo, hi)), collections.Counter())  # noqa: E731
    left = [pool(*r) for r in runs]  # each lesson step's share of the model, not yet accounted for
    exact = shifted = wrong = 0
    rows = []
    for i, ((label, got), r) in enumerate(zip(lesson, runs)):
        for k, n in got.items():
            for _ in range(n):
                if left[i][k] > 0:
                    left[i][k] -= 1
                    exact += 1
                    continue
                near = [x for x in (i - 1, i + 1) if 0 <= x < len(left) and left[x][k] > 0]
                if near:
                    left[near[0]][k] -= 1
                    shifted += 1
                    rows.append((label, k, f"one step off (belongs with step {lesson[near[0]][0]})"))
                else:
                    wrong += 1
                    rows.append((label, k, "wrong (not in this part of the model)"))
    covered = sum(sum(pool(*r).values()) for r in runs)
    total = sum(sum(c.values()) for c in model)
    missed = sum(sum(c.values()) for c in left) + (total - covered)
    mains = sum(1 for label, _ in lesson if "sub" not in str(label))
    return {"set": set_id, "model_pieces": total, "exact": exact, "shifted": shifted, "wrong": wrong, "missed": missed,
            "model_steps": len(model), "booklet_steps": mains,  # a model with far fewer steps than the booklet was
            "model_follows_booklet": len(model) >= 0.8 * mains,  # not drawn to it: its score is a lower bound
            "exact_share": round(exact / total, 3) if total else None, "details": rows}


def main(argv):
    for s in argv:
        r = score(s)
        if not r:
            print(s, "no 3D model steps")
            continue
        print(f"{s}: {r['exact']}/{r['model_pieces']} exact ({r['exact_share']}), {r['shifted']} one step off, "
              f"{r['wrong']} wrong, {r['missed']} missed")
        for label, k, how in r["details"][:12]:
            print(f"   step {label}: {k[0]} {k[1]} {how}")


if __name__ == "__main__":
    main(sys.argv[1:])
