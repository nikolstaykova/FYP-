"""Our Arduino lessons (data/lessons/arduino) against the CircuitQuest lessons made for the same tutorials, read
from the files of both (same lesson format; no CircuitQuest code is run).

  parts    the gather list (usb cable and jumper wires left out), as library ids
  circuit  the nets the build steps make, each pin named by its part's Wokwi type and port (board GND.1 = GND, D13 = 13),
           so part ids may differ; scored as matching nets (F1)
  steps    build steps; sketch: similarity of the code, comments and blank lines left out
  words    words per clip, hints per step; extras only we have

  python -m graph.compare_cq [CirquitQuest lessons dir]
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import difflib
import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OURS = ROOT / "data" / "lessons" / "arduino"
CQ = pathlib.Path.home() / "Desktop" / "CirquitQuest" / "lessons"
SKIP = {"usb-cable", "jumper-wire", "jumper-wire-mf"}


def _pin(pin, types):
    part, _, port = pin.partition(":")
    t = types.get(part, part)
    port = re.sub(r"^(\d)\.[lr]$", r"\1", port)  # a pushbutton's two legs on one side are one pin (1.l = 1.r = 1)
    if re.search(r"resistor|pushbutton|crystal|capacitor-ceramic|speaker|photoresistor|fsr", t) and re.fullmatch(r"\d", port):
        port = "leg"  # either way round: which leg is 1 is no difference in the circuit
    if t.startswith("wokwi-arduino") or "arduino" in t:
        t = "board"
        port = re.sub(r"^(GND|5V|3V3|VIN)\.\d+$", r"\1", port)
        port = re.sub(r"^D(\d+)$", r"\1", port)
    return f"{t}:{port}"


def nets(lesson, diagram):
    """The circuit the build steps make: pairs joined into nets, pins named by part type."""
    types = {p["id"]: p["type"] for p in diagram.get("parts", [])}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x
    for s in lesson["steps"]:  # joined by the pins themselves, named by type after
        for pair in s.get("expected_nets") or []:
            a, *rest = pair
            for b in rest:
                parent[find(b)] = find(a)
    groups = {}
    for x in parent:
        groups.setdefault(find(x), set()).add(_pin(x, types))
    return {frozenset(g) for g in groups.values() if len(g) > 1}


def sketch_text(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return [ln.strip() for ln in code.splitlines() if ln.strip()]


def one(case, cq_dir):
    ours, theirs = OURS / case, cq_dir / case
    a, b = json.loads((ours / "lesson.json").read_text()), json.loads((theirs / "lesson.json").read_text())
    da = json.loads((ours / "diagram.json").read_text()) if (ours / "diagram.json").exists() else {}
    db = json.loads((theirs / "diagram.json").read_text()) if (theirs / "diagram.json").exists() else {}
    items = lambda L: {i for s in L["steps"] if s.get("phase") == "gather" for i in s.get("items", [])} - SKIP
    pa, pb = items(a), items(b)
    na, nb = nets(a, da), nets(b, db)
    # a net matches when it joins the same board pins and part pins; partial credit is not given
    hit = len(na & nb)
    f1 = 2 * hit / (len(na) + len(nb)) if na or nb else 1.0
    ca = sketch_text((ours / "code.ino").read_text()) if (ours / "code.ino").exists() else []
    cb = sketch_text((theirs / "code.ino").read_text()) if (theirs / "code.ino").exists() else []
    build = lambda L: [s for s in L["steps"] if s.get("phase") == "build"]
    words = lambda L: statistics.mean([len(s.get("clip", "").split()) for s in build(L)] or [0])
    hints = lambda L: statistics.mean([len(s.get("hints", [])) for s in build(L)] or [0])
    stats = json.loads((ours / "stats.json").read_text())
    return {"case": case, "parts_ours": sorted(pa), "parts_cq": sorted(pb), "parts_same": pa == pb,
            "only_ours": sorted(pa - pb), "only_cq": sorted(pb - pa),
            "nets_ours": len(na), "nets_cq": len(nb), "nets_f1": round(f1, 3),
            "nets_only_ours": [sorted(n) for n in na - nb], "nets_only_cq": [sorted(n) for n in nb - na],
            "steps_ours": len(build(a)), "steps_cq": len(build(b)),
            "sketch_sim": round(difflib.SequenceMatcher(None, ca, cb).ratio(), 3) if ca or cb else 1.0,
            "sketch_ours": bool(ca), "sketch_cq": bool(cb),
            "words_ours": round(words(a), 1), "words_cq": round(words(b), 1),
            "hints_ours": round(hints(a), 1), "hints_cq": round(hints(b), 1),
            "extras_ours": bool(a.get("extras")), "issues_ours": [i[0] for i in stats.get("issues_final", [])],
            "cost_ours": stats.get("cost_usd"), "seconds_ours": stats.get("seconds")}


def main(argv):
    cq_dir = pathlib.Path(argv[0]) if argv else CQ
    cases = sorted(d.name for d in cq_dir.iterdir() if (d / "lesson.json").exists() and (OURS / d.name / "lesson.json").exists())
    rows = [one(c, cq_dir) for c in cases]
    n = len(rows)
    mean = lambda k: round(statistics.mean(r[k] for r in rows), 2)
    summary = {"lessons": n, "parts_same": sum(r["parts_same"] for r in rows),
               "nets_exact": sum(r["nets_f1"] == 1.0 for r in rows), "nets_f1_mean": mean("nets_f1"),
               "steps_ours_mean": mean("steps_ours"), "steps_cq_mean": mean("steps_cq"),
               "sketch_same": sum(r["sketch_sim"] >= 0.95 for r in rows), "sketch_sim_mean": mean("sketch_sim"),
               "words_ours_mean": mean("words_ours"), "words_cq_mean": mean("words_cq"),
               "hints_ours_mean": mean("hints_ours"), "hints_cq_mean": mean("hints_cq")}
    (OURS / "cq_compare.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))
    for r in rows:
        print(f"{r['case']:28} nets F1 {r['nets_f1']:.2f} ({r['nets_ours']}/{r['nets_cq']})  steps {r['steps_ours']}/"
              f"{r['steps_cq']}  sketch {r['sketch_sim']:.2f}  parts {'=' if r['parts_same'] else '+' + ','.join(r['only_ours']) + ' -' + ','.join(r['only_cq'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
