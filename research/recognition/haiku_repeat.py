"""Haiku's first look three more times at 1024 / 768 / 512 px on the 14 photo sets, to see past the run-to-run noise.
Kit photos: % right (kit_test labels). Your photos: % of verdicts the same as Opus at full size (model_cost run).
Run: PYTHONPATH=code .venv-research/bin/python research/recognition/haiku_repeat.py
Writes runs/haiku_repeat/results.json and prints the table."""
import json
import statistics as S
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model_cost_test as M  # noqa: E402
from kit_test import CASES  # noqa: E402
from res_test import cases, IMG  # noqa: E402

OUT = HERE / "runs/haiku_repeat"
M.FALLBACK_AT = set()  # first look only
SIZES = [("1024", 1024), ("768", 768), ("512", 512)]
REPEATS = 3


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    cs = cases()
    todo = [(c, s, k) for k in range(REPEATS) for s in SIZES for c in cs]
    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lambda t: {**M.one(t[0], "claude-haiku-5-5", t[1]), "repeat": t[2]}, todo))
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    ref = {r["case"]: r["first_verdicts"] for r in json.loads((HERE / "runs/model_cost/results.json").read_text())
           if r["model"] == "claude-opus-5-5" and r["size"] == "full" and "error" not in r}
    print("| Haiku | kit right per run | mean | your photos same as Opus per run | mean | price |")
    print("|---|---|---|---|---|---|")
    for name, _ in SIZES:
        kits, labs, cost = [], [], []
        for k in range(REPEATS):
            rs = [r for r in rows if r["size"] == name and r["repeat"] == k and "error" not in r]
            kit = [r for r in rs if r["set"] == "kit"]
            right = sum(st in ok for r in kit for t, ok in CASES[r["case"]][2].items() for st in r["first_verdicts"].get(t, ["(none)"]))
            of = sum(len(r["first_verdicts"].get(t, ["(none)"])) for r in kit for t in CASES[r["case"]][2])
            lab = [r for r in rs if r["set"] == "lab" and r["case"] in ref]
            same = sum(sorted(r["first_verdicts"].get(t, [])) == sorted(v) for r in lab for t, v in ref[r["case"]].items())
            tot = sum(len(ref[r["case"]]) for r in lab)
            kits.append(100 * right / of)
            labs.append(100 * same / tot)
            cost += [r["first_usd"] for r in rs]
        print(f"| {name} px | {' / '.join(f'{x:.0f}%' for x in kits)} | {S.mean(kits):.0f}% | "
              f"{' / '.join(f'{x:.0f}%' for x in labs)} | {S.mean(labs):.0f}% | {100 * S.mean(cost):.3f}¢ |")
    print("errors:", sum("error" in r for r in rows), " spent: $%.3f" % sum(r.get("first_usd") or 0 for r in rows))


if __name__ == "__main__":
    main()
