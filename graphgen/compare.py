"""Side-by-side comparison of two runs of the same test set (e.g. before and after the check-and-repair logic).

  .venv-research/bin/python -m graphgen.compare <old_run> <new_run> [--label-old v1 --label-new v2]
Prints a Markdown table; only manuals present in both runs are compared.
"""
import argparse
import json
import pathlib
import statistics


def load(run):
    rows = [json.loads(l) for l in (pathlib.Path(run) / "results.jsonl").read_text().splitlines() if l.strip()]
    return {r["case"]: r for r in rows}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def metrics(rows):
    m = {"Manuals compared": len(rows),
         "Mean seconds per manual": mean(r["stats"]["seconds"] for r in rows),
         "Median seconds per manual": median(r["stats"]["seconds"] for r in rows),
         "Mean cost per manual ($)": mean(r["stats"]["cost_usd"] for r in rows),
         "Total cost ($)": round(sum(r["stats"]["cost_usd"] for r in rows), 2),
         "Manuals with rule problems": sum(1 for r in rows if r["problems"]),
         "Rule problems in total": sum(len(r["problems"]) for r in rows)}
    if rows and rows[0]["domain"] == "arduino":
        keyed = [r for r in rows if "nets_expected" in r["score"]]
        free = [r for r in rows if "hardware_recall" in r["score"]]
        m.update({"Answer-key tutorials: all nets correct": f"{sum(r['score']['all_nets_correct'] for r in keyed)} / {len(keyed)}",
                  "Answer-key tutorials: mean net precision": mean(r["score"]["net_precision"] for r in keyed),
                  "Answer-key tutorials: mean net recall": mean(r["score"]["net_recall"] for r in keyed),
                  "Answer-key tutorials: parts list correct": f"{sum(r['score']['inventory_correct'] for r in keyed)} / {len(keyed)}",
                  "Other tutorials: listed parts present": mean(r["score"]["hardware_recall"] for r in free)})
    else:
        rows = [r for r in rows if r["parts"] > 0]
        m.update({"Pieces built ÷ pieces in set": mean(r["score"]["pieces_built"] / r["score"]["pieces_expected"] for r in rows),
                  "Inventory recall (by design)": mean(r["score"]["inventory_recall"] for r in rows),
                  "Inventory precision (by design)": mean(r["score"]["inventory_precision"] for r in rows),
                  "Contact recall": mean(r["score"]["contact_recall"] for r in rows),
                  "Contact precision": mean(r["score"]["contact_precision"] for r in rows)})
    for ph in ("parts", "build", "repair1", "repair2"):
        runs = [p for r in rows for p in r.get("phases", []) if p["phase"] == ph]
        if runs:
            m[f"Phase {ph}: runs / mean s / mean $"] = (f"{len(runs)} / {mean(p['seconds'] for p in runs)} / "
                                                        f"{mean(p['cost_usd'] for p in runs)}")
    rep = [r for r in rows if r.get("issues_first") is not None]
    if rep:
        m.update({"Manuals with check failures after first build": sum(1 for r in rep if r["issues_first"]),
                  "Check issues: first build → final": f"{sum(r['issues_first'] for r in rep)} → {sum(r['issues_final'] for r in rep)}",
                  "Manuals that needed a repair round": sum(1 for r in rep if r["stats"].get("repair_rounds_used"))})
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--label-old", default="before")
    ap.add_argument("--label-new", default="after")
    a = ap.parse_args()
    old, new = load(a.old), load(a.new)
    common = sorted(set(old) & set(new))
    mo, mn = metrics([old[c] for c in common]), metrics([new[c] for c in common])
    print(f"| Measure | {a.label_old} | {a.label_new} |\n|---|---:|---:|")
    for k in dict.fromkeys([*mo, *mn]):
        print(f"| {k} | {mo.get(k, '–')} | {mn.get(k, '–')} |")


if __name__ == "__main__":
    main()
