"""Turn experiment results into one Markdown report.

  write_report(run_dir, results, failures, config)   called by run.py, writes <run>/REPORT.md
  .venv-research/bin/python -m graphgen.report <run_dir> [<run_dir> ...] -o GRAPHGEN_RESULTS.md
"""
import argparse
import collections
import json
import pathlib
import statistics


def _pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "–"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def _q(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def section(results, failures, config):
    n = len(results)
    if not n:
        return "No successful runs.\n"
    secs = [r["stats"]["seconds"] for r in results]
    cost = [r["stats"]["cost_usd"] for r in results]
    tin = [r["stats"]["input_tokens"] for r in results]
    tout = [r["stats"]["output_tokens"] for r in results]
    domain = results[0]["domain"]
    lines = [f"**Model:** `{config.get('model')}` · effort `{config.get('effort')}` · catalogue `{config.get('catalogue')}` · "
             f"{n} manuals succeeded, {len(failures)} failed · wall time {config.get('wall_seconds', '–')} s with "
             f"{config.get('workers')} in parallel", "",
             "### Time and cost", "",
             "| | Mean | Median | 90th pct | Total |", "|---|---:|---:|---:|---:|",
             f"| Seconds per manual | {_mean(secs)} | {_q(secs, .5)} | {_q(secs, .9)} | {round(sum(secs))} |",
             f"| Input tokens | {round(_mean(tin))} | {_q(tin, .5)} | {_q(tin, .9)} | {sum(tin)} |",
             f"| Output tokens | {round(_mean(tout))} | {_q(tout, .5)} | {_q(tout, .9)} | {sum(tout)} |",
             f"| Cost (USD) | {_mean(cost)} | {_q(cost, .5)} | {_q(cost, .9)} | {round(sum(cost), 2)} |", "",
             f"Estimated cost for 100 manuals at this rate: **${round(100 * sum(cost) / n, 2)}**.", ""]

    lines += ["### Accuracy", ""]
    if domain == "arduino":
        keyed = [r for r in results if "nets_expected" in r["score"]]
        free = [r for r in results if "hardware_recall" in r["score"]]
        if keyed:
            lines += [f"**{len(keyed)} tutorials with an answer key** (CircuitQuest's verified circuit):", "",
                      "| Measure | Result |", "|---|---:|",
                      f"| All electrical connections correct | {sum(r['score']['all_nets_correct'] for r in keyed)} / {len(keyed)} ({_pct(sum(r['score']['all_nets_correct'] for r in keyed), len(keyed))}) |",
                      f"| Mean net precision | {_mean(r['score']['net_precision'] for r in keyed)} |",
                      f"| Mean net recall | {_mean(r['score']['net_recall'] for r in keyed)} |",
                      f"| Parts list correct (V1) | {sum(r['score']['inventory_correct'] for r in keyed)} / {len(keyed)} |", ""]
        if free:
            lines += [f"**{len(free)} tutorials without an answer key** (scored on the parts the tutorial lists): "
                      f"mean share of listed part families present = {_mean(r['score']['hardware_recall'] for r in free)}.", ""]
        drafts = [d for r in results for d in r.get("drafts", []) if d.get("checked")]
        if drafts:
            lines += [f"**First-time part creation:** {len(drafts)} drafted types could be checked against verified cards: "
                      f"polarity right {sum(d['polarized_ok'] for d in drafts)}/{len(drafts)}, "
                      f"symmetry right {sum(d['symmetric_ok'] for d in drafts)}/{len(drafts)}, "
                      f"port count right {sum(d['port_count_ok'] for d in drafts)}/{len(drafts)}.", ""]
    else:
        empty = [r for r in results if r["parts"] == 0]
        if empty:
            lines += [f"**{len(empty)} PDF(s) contained no building instructions** (e.g. advent-calendar covers); Claude returned an "
                      f"empty graph instead of inventing parts. Left out of the accuracy below: "
                      + ", ".join(f"`{r['case']}`" for r in empty) + ".", ""]
        results = [r for r in results if r["parts"] > 0]
        sc = [r["score"] for r in results]
        lines += ["| Measure | Mean | Median |", "|---|---:|---:|",
                  f"| Pieces built ÷ pieces in the set | {_mean(s['pieces_built'] / s['pieces_expected'] for s in sc)} | {_q([s['pieces_built'] / s['pieces_expected'] for s in sc], .5):.2f} |",
                  f"| Exact pieces (part + colour, needs an inventory page) | {_mean(s.get('exact_recall') for s in sc)} | {_q([s.get('exact_recall') for s in sc], .5)} |",
                  f"| Inventory precision, by design (pieces that are in the set) | {_mean(s['inventory_precision'] for s in sc)} | {_q([s['inventory_precision'] for s in sc], .5)} |",
                  f"| Inventory recall, by design (set pieces found) | {_mean(s['inventory_recall'] for s in sc)} | {_q([s['inventory_recall'] for s in sc], .5)} |",
                  f"| Contact precision (brick/plate/tile pairs) | {_mean(s['contact_precision'] for s in sc)} | {_q([s['contact_precision'] for s in sc], .5)} |",
                  f"| Booklets with no checkable contacts (no plain bricks/plates/tiles) | {sum(1 for s in sc if s['contact_recall'] is None)} | |",
                  f"| Contact recall | {_mean(s['contact_recall'] for s in sc)} | {_q([s['contact_recall'] for s in sc], .5)} |", "",
                  "*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, "
                  "because the model reads pictures and cannot give LDraw positions.*", ""]
        buckets = collections.defaultdict(list)
        for r in results:
            p = r["score"]["pieces_expected"]
            buckets["<100" if p < 100 else "100-249" if p < 250 else "250+"].append(r)
        lines += ["**By set size:**", "", "| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |",
                  "|---|---:|---:|---:|---:|---:|"]
        for b in ("<100", "100-249", "250+"):
            rs = buckets.get(b, [])
            if rs:
                lines.append(f"| {b} | {len(rs)} | {_mean(r['stats']['seconds'] for r in rs)} | {_mean(r['stats']['cost_usd'] for r in rs)} | "
                             f"{_mean(r['score']['inventory_recall'] for r in rs)} | {_mean(r['score']['contact_recall'] for r in rs)} |")
        lines.append("")

    if any(r.get("issues_first") is not None for r in results):
        rr = [r for r in results if r.get("issues_first") is not None]
        needed = [r for r in rr if r["issues_first"]]
        fixed = [r for r in needed if not r["issues_final"]]
        phase = collections.defaultdict(list)
        for r in rr:
            for p in r["phases"]:
                phase[p["phase"]].append(p)
        lines += ["### Check and repair loop", "",
                  f"Build → check → repair → final check. **{len(needed)}/{len(rr)}** manuals had check failures after the first build; "
                  f"**{len(fixed)}** of those were fully fixed by the repair. Issues in total: "
                  f"{sum(r['issues_first'] for r in rr)} → {sum(r['issues_final'] for r in rr)}.", "",
                  "| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |", "|---|---:|---:|---:|---:|"]
        for name, ps in sorted(phase.items()):
            lines.append(f"| {name} | {len(ps)} | {_mean(p['seconds'] for p in ps)} | {_mean(p['cost_usd'] for p in ps)} | "
                         f"{_mean(p.get('check_seconds') for p in ps)} |")
        both = [r for r in rr if "score_initial" in r]
        if both and domain == "arduino":
            keyed = [r for r in both if "nets_expected" in r["score"]]
            if keyed:
                lines += ["", f"**Accuracy before → after repair** ({len(keyed)} tutorials with an answer key that were repaired): "
                          f"all nets correct {sum(r['score_initial']['all_nets_correct'] for r in keyed)} → "
                          f"{sum(r['score']['all_nets_correct'] for r in keyed)}; mean net recall "
                          f"{_mean(r['score_initial']['net_recall'] for r in keyed)} → {_mean(r['score']['net_recall'] for r in keyed)}."]
        elif both:
            lines += ["", f"**Accuracy before → after repair** ({len(both)} booklets repaired): inventory recall "
                      f"{_mean(r['score_initial']['inventory_recall'] for r in both)} → {_mean(r['score']['inventory_recall'] for r in both)}; "
                      f"contact recall {_mean(r['score_initial']['contact_recall'] for r in both)} → {_mean(r['score']['contact_recall'] for r in both)}; "
                      f"contact precision {_mean(r['score_initial']['contact_precision'] for r in both)} → {_mean(r['score']['contact_precision'] for r in both)}."]
        lines.append("")
    rules = collections.Counter(p[0] for r in results for p in r["problems"])
    clean = sum(1 for r in results if not r["problems"])
    reps = [r for r in results if r["repeats"]]
    lines += ["### Spec rules and structure", "",
              f"- Manuals with **no rule problems**: {clean}/{n} ({_pct(clean, n)}).",
              f"- Problems by rule: " + (", ".join(f"{k} ×{v}" for k, v in rules.most_common()) or "none") +
              " (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).",
              f"- Manuals using **repeats**: {len(reps)}/{n}; overrides used in {sum(1 for r in reps if any(x['overrides'] for x in r['repeats']))}.", ""]
    growth = []
    total = 0
    for i, r in enumerate(results, 1):
        total += r["new_types_added"]
        growth.append((i, r["new_types_added"], total))
    marks = sorted({1, 2, 5, 10, 25, 50, 75, n} & set(range(1, n + 1)))
    lines += ["### Store on demand (catalogue growth)", "",
              "| After manual | New types in that manual | Catalogue additions so far |", "|---:|---:|---:|"]
    lines += [f"| {i} | {g[1]} | {g[2]} |" for i in marks for g in [growth[i - 1]]]
    lines.append("")
    if failures:
        lines += ["### Failures", "", *[f"- `{f['case']}`: {f['error'][:200]}" for f in failures], ""]
    lines += ["### Per manual", "", "| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in results:
        s = r["score"]
        if "nets_expected" in s:
            q = f"nets {s['nets_matched']}/{s['nets_expected']} {'✅' if s['all_nets_correct'] else ''}"
        elif "hardware_recall" in s:
            q = f"listed parts {s['hardware_recall']}" + (f" (missing {', '.join(s['families_missing'])})" if s["families_missing"] else "")
        else:
            q = (f"pieces {s['pieces_built']}/{s['pieces_expected']}, inv R {s['inventory_recall']}, "
                 f"contacts {s['contacts_correct']}/{s['contacts_expected']}")
        lines.append(f"| {r['case']} | {r['stats']['seconds']} | {r['stats']['cost_usd']} | {r['parts']} | {r['edges']} | "
                     f"{r['new_types_added']} | {len(r['problems'])} | {q} |")
    return "\n".join(lines) + "\n"


def write_report(run_dir, results, failures, config):
    run_dir = pathlib.Path(run_dir)
    (run_dir / "config.json").write_text(json.dumps(config, indent=1, default=str))
    text = f"# Graph generation: {config.get('domain')}\n\n{section(results, failures, config)}"
    path = run_dir / "REPORT.md"
    path.write_text(text)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=pathlib.Path)
    ap.add_argument("-o", "--output", type=pathlib.Path, required=True)
    a = ap.parse_args()
    parts = ["# Graph generation results\n",
             "Claude builds one graph per manual from the spec in [GRAPH_SPEC.md](./GRAPH_SPEC.md); code then checks the rules, "
             "computes the logical view and scores it against an answer key. Method and test sets: RESEARCH.md R21.\n"]
    for run in a.runs:
        results = [json.loads(l) for l in (run / "results.jsonl").read_text().splitlines() if l.strip()]
        failures = json.loads((run / "failures.json").read_text()) if (run / "failures.json").exists() else []
        config = json.loads((run / "config.json").read_text())
        parts.append(f"## {config['domain'].upper()}: {run.name}\n\n" + section(results, failures, config))
    a.output.write_text("\n".join(parts))
    print("wrote", a.output)


if __name__ == "__main__":
    main()
