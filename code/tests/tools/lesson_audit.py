"""Are the lessons realistic? Every saved lesson (data/lessons/lego3d/<set>/lesson.json) checked in full, uncapped:
  floating   S2: a piece put on before anything it clicks onto
  blocked    S6: a piece whose path in is blocked by a piece already built, and LEGO does not do it that way
  overruled  S6 reports LEGO's own order contradicts (LEGO puts the blocker on first, so the path test is wrong)
  out_of_order  S7: pieces before a piece of an earlier official step
  small_first   sub-assemblies whose first piece (3D hint order) is a pin, axle or bush while the step has the piece
                it goes into
  python -m graph.lesson_audit [sets]   writes data/lessons/lego3d/AUDIT.md
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import collections
import json
import pathlib
import re
import sys

from graph.lego_3d import assembly, lesson
import truth

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "lessons" / "lego3d"
SMALL = r"\bpin\b|\baxle\b|\bbush\b"


def audit(set_id):
    L = json.loads((DIR / set_id / "lesson.json").read_text())["lesson"]
    pieces = lesson.model_of(set_id)
    asm = assembly.of(set_id)
    issues = lesson.check(L, pieces, asm=asm, limit=10 ** 6)
    by = collections.Counter(r for r, _ in issues)
    off = {p["id"]: p.get("official_step") for p in pieces}
    sub = {p["id"]: p.get("official_sub", "") for p in pieces}
    latest, late = {}, 0
    for st in L["steps"]:
        for i in st["pieces"]:
            if off.get(i) is None:
                continue
            k = sub.get(i, "")
            if latest.get(k, 0) > off[i]:
                late += 1
            latest[k] = max(latest.get(k, 0), off[i])
    seen, small = set(), []
    for n, st in enumerate(L["steps"], 1):
        s = st["subassembly"]
        if s and s not in seen and st["pieces"]:
            seen.add(s)
            first = asm.order_step(st["pieces"], set())[0][0]
            name = truth.library_title(asm.where[first][1]).lower()
            if re.search(SMALL, name) and any(asm.fastens.get(first, set()) & set(st["pieces"]) - {first} for _ in [0]):
                small.append(f"step {n} '{s}': {name}")
    n = sum(len(st["pieces"]) for st in L["steps"])
    return {"set": set_id, "pieces": n, "steps": len(L["steps"]), "floating": by["S2"], "blocked": by["S6"],
            "overruled": len(lesson.check.overruled), "out_of_order": late,
            "out_of_order_pct": round(100 * late / max(1, n), 1), "small_first": small,
            "other": {k: v for k, v in by.items() if k not in ("S2", "S6", "S7")},
            "examples": [m for r, m in issues if r in ("S2", "S6")][:6]}


def main(sets):
    sets = sets or sorted(p.parent.name for p in DIR.glob("*/lesson.json"))
    rows = []
    for s in sets:
        r = audit(s)
        rows.append(r)
        print(f"{s:9} pieces {r['pieces']:4} steps {r['steps']:4} floating {r['floating']:3} blocked {r['blocked']:3} "
              f"(overruled by LEGO {r['overruled']:3}) out of LEGO order {r['out_of_order_pct']:5}%  small first "
              f"{len(r['small_first'])} other {r['other']}", flush=True)
    md = ["# Lesson realism audit", "", "| Set | Pieces | Steps | Floating | Blocked | Overruled by LEGO | Out of LEGO's order | Small piece first |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    md += [f"| {r['set']} | {r['pieces']} | {r['steps']} | {r['floating']} | {r['blocked']} | {r['overruled']} | "
           f"{r['out_of_order_pct']}% | {len(r['small_first'])} |" for r in rows]
    for r in rows:
        if r["examples"] or r["small_first"]:
            md += ["", f"## {r['set']}", ""] + [f"- {m}" for m in r["examples"] + r["small_first"]]
    (DIR / "AUDIT.md").write_text("\n".join(md) + "\n")
    (DIR / "audit.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
