"""Average price against average performance, Haiku and Gemini Flash-Lite, every photo setting (repeat_matrix.py).
Error bars: 95% confidence interval of the mean over the runs.

Run: .venv-research/bin/python research/recognition/repeat_plot.py
Writes research/recognition/figures/checker_repeats.png and prints the table for CHECKER.md.
"""
import json
import math
import statistics as S
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from kit_test import CASES  # noqa: E402

OUT = HERE / "figures" / "checker_repeats.png"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COLOUR = {"claude-haiku-5-5": "#2a78d6", "gemini-3.5-flash-lite": "#eb6834"}
NAME = {"claude-haiku-5-5": "Haiku 5.5", "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite"}
MARK = {85: "o", 35: "s", 15: "^"}


def stats():
    rows = [r for r in json.loads((HERE / "runs/repeat_matrix/results.json").read_text()) if "error" not in r]
    ref = {r["case"]: r["first_verdicts"] for r in json.loads((HERE / "runs/model_cost/results.json").read_text())
           if r["model"] == "claude-opus-5-5" and r["size"] == "full" and "error" not in r}
    out = {}
    for key in sorted({(r["model"], r["size"], r["q"]) for r in rows}):
        rs = [r for r in rows if (r["model"], r["size"], r["q"]) == key]
        kits, labs = [], []
        for run in sorted({r["run"] for r in rs}):
            rr = [r for r in rs if r["run"] == run]
            kit = [r for r in rr if r["set"] == "kit"]
            of = sum(len(r["verdicts"].get(t, ["(none)"])) for r in kit for t in CASES[r["case"]][2])
            if of:
                kits.append(100 * sum(st in ok for r in kit for t, ok in CASES[r["case"]][2].items()
                                      for st in r["verdicts"].get(t, ["(none)"])) / of)
            lab = [r for r in rr if r["set"] == "lab" and r["case"] in ref]
            tot = sum(len(ref[r["case"]]) for r in lab)
            if tot:
                labs.append(100 * sum(sorted(r["verdicts"].get(t, [])) == sorted(v) for r in lab
                                      for t, v in ref[r["case"]].items()) / tot)
        ci = lambda xs: 1.96 * S.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0
        out[key] = {"price": 100 * S.mean(r["usd"] for r in rs), "kit": S.mean(kits) if kits else None,
                    "kit_ci": ci(kits), "lab": S.mean(labs) if labs else None, "lab_ci": ci(labs),
                    "both": S.mean([(k + l) / 2 for k, l in zip(kits, labs)]) if kits and labs else None,
                    "runs": len({r["run"] for r in rs}), "checks": len(rs), "s": S.mean(r["s"] or 0 for r in rs),
                    "out": S.mean(r["out"] or 0 for r in rs)}
    return out


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def main():
    d = stats()
    settings = [(size, q) for size in ("1024", "768", "512") for q in (85, 35, 15)]
    models = list(NAME)
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.4), sharey=True, gridspec_kw={"width_ratios": [1, 1.2, 1.2]})
    fig.patch.set_facecolor(SURFACE)
    ys = {st: len(settings) - 1 - i for i, st in enumerate(settings)}
    off = {models[0]: 0.15, models[1]: -0.15}
    panels = (("price", None, "Average price per check (¢)", "{:.2f}¢"),
              ("kit", "kit_ci", "Kit photos: % right", "{:.0f}%"),
              ("lab", "lab_ci", "Your photos: % same as Opus", "{:.0f}%"))
    for ax, (key, ci, title, fmt) in zip(axes, panels):
        style(ax)
        ax.grid(axis="y", visible=False)
        for k in range(1, 3):  # a line between the sizes
            ax.axhline(len(settings) - 3 * k - 0.5, color=GRID, linewidth=1)
        for m in models:
            for st in settings:
                v = d.get((m, *st))
                if not v or v[key] is None:
                    continue
                y = ys[st] + off[m]
                ax.errorbar(v[key], y, xerr=v[ci] if ci else None, fmt="o", ms=7, color=COLOUR[m], mec=SURFACE,
                            mew=1.5, ecolor=COLOUR[m], elinewidth=1.2, capsize=2, zorder=3)
                ax.annotate(fmt.format(v[key]), (v[key], y), xytext=(0, 7) if m == models[0] else (0, -12),
                            textcoords="offset points", ha="center", fontsize=7.5, color=INK2)
        ax.set_title(title, loc="left", color=INK, fontsize=11.5, fontweight="bold")
    axes[0].set_xlim(0, 0.65)
    for ax in axes[1:]:
        ax.set_xlim(70, 101)
    axes[0].set_yticks([ys[st] for st in settings], [f"{size} px · JPEG {q}" for size, q in settings])
    axes[0].set_ylim(-0.7, len(settings) - 0.3)
    for m in models:
        runs = sorted({v["runs"] for (mm, *_), v in d.items() if mm == m})
        axes[1].plot([], [], "o", ms=7, color=COLOUR[m], label=f"{NAME[m]} ({runs[-1]} runs)")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), frameon=False, fontsize=9, labelcolor=INK2, ncols=2)
    fig.text(0.01, 0.01, "Each dot: the average over the runs (each run = 14 photo sets); bars = 95% confidence interval. "
             "First look only, no Opus fallback. Gemini stopped at 4 runs: Google's quota on our key ran out.",
             fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor=SURFACE)
    print(OUT)
    print("| Model | Size | JPEG | Runs | Price per check | Kit right (± 95% CI) | Your photos same as Opus (± 95% CI) | Answer tokens | Seconds |")
    print("|---|---|---|---|---|---|---|---|---|")
    f = lambda x, c: "–" if x is None else f"{x:.0f}% ± {c:.0f}"
    for (m, size, q), v in sorted(d.items(), key=lambda kv: (kv[0][0], -int(kv[0][1]), -kv[0][2])):
        print(f"| {NAME[m]} | {size} px | {q} | {v['runs']} | {v['price']:.3f}¢ | {f(v['kit'], v['kit_ci'])} | "
              f"{f(v['lab'], v['lab_ci'])} | {v['out']:.0f} | {v['s']:.0f} |")


if __name__ == "__main__":
    main()
