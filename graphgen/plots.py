"""Figures comparing every version, from graphgen/data/results_summary.json -> figures/graphgen/*.png.

  /opt/homebrew/anaconda3/bin/python3 -m graphgen.plots      (needs matplotlib; the project venv does not have it)

One measure per chart (never two y-scales): versions on the x axis, values at the bar tips, a version not run yet is
left out and named under the chart. Colours: the reference categorical palette (dataviz skill), slot 1 for a single
series, slots 1-2 for a pair; text in text inks, never in the series colour.
"""
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "graphgen"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834"]


def style(ax, title, unit):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=12, fontweight="bold")
    ax.set_ylabel(unit, color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def bars(name, title, unit, versions, series, labels=None, fmt="{:g}", note=""):
    """series: one list of values, or several (then a legend and direct labels)."""
    series = series if isinstance(series[0], list) else [series]
    keep = [i for i, v in enumerate(versions) if any(s[i] is not None for s in series)]
    missing = [versions[i] for i in range(len(versions)) if i not in keep]
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    style(ax, title, unit)
    n, width = len(series), 0.34 if len(series) > 1 else 0.5
    for j, s in enumerate(series):
        xs = [k + (j - (n - 1) / 2) * (width + 0.04) for k in range(len(keep))]
        ys = [s[i] if s[i] is not None else 0 for i in keep]
        rects = ax.bar(xs, ys, width=width, color=SERIES[j], label=labels[j] if labels else None, zorder=2)
        for r, i in zip(rects, keep):
            if s[i] is not None:
                ax.annotate(fmt.format(s[i]), (r.get_x() + r.get_width() / 2, r.get_height()), xytext=(0, 3),
                            textcoords="offset points", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(keep)), [versions[i] for i in keep])
    top = max(v for s in series for v in s if v is not None)
    ax.set_ylim(0, top * 1.18)
    if labels:
        ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="upper left", ncol=len(labels))
    foot = "  ".join(x for x in (note, f"Not run yet: {', '.join(missing)}." if missing else "") if x)
    if foot:
        fig.text(0.01, 0.01, foot, fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04 if foot else 0, 1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", facecolor=SURFACE)
    plt.close(fig)


def main():
    d = json.loads((ROOT / "graphgen" / "data" / "results_summary.json").read_text())
    e, l = d["electronics"], d["lego"]
    bars("electronics_accuracy", "Electronics: circuits CircuitQuest accepts as correct", "% of tutorials",
         e["versions"], [e["circuitquest_correct_reviewed_pct"], e["circuitquest_correct_all_pct"]],
         ["reviewed answer key (28)", "all with an answer key (47)"], "{:g}%",
         "CircuitQuest's checker; electrically equivalent circuits count as correct.")
    bars("electronics_errors", "Electronics: real model errors (answer-key differences left out)", "tutorials",
         e["versions"], e["real_model_errors"], fmt="{:g}", note="Out of the 47 tutorials with an answer key.")
    bars("electronics_time", "Electronics: mean time per tutorial", "seconds", e["versions"], e["mean_seconds"],
         fmt="{:g} s", note="All 117 tutorials.")
    bars("electronics_cost", "Electronics: mean cost per tutorial", "US dollars (API prices)", e["versions"],
         e["mean_cost_usd"], fmt="${:.3f}")
    bars("lego_contacts", "LEGO: brick contacts", "share (0-1)", l["versions"], [l["contacts_found"], l["contacts_real"]],
         ["contacts found (recall)", "joins that are real (precision)"], "{:.2f}",
         "v1 on its 33 sets; v2 and v3 on the 86 sets both finished.")
    bars("lego_pieces", "LEGO: sets with exactly the right pieces", "% of sets", l["versions"], l["sets_exact_pieces_pct"],
         fmt="{:g}%", note="From v3 the official parts list is given to Claude.")
    bars("lego_time", "LEGO: mean time per set (the same 87 sets)", "seconds", l["versions"], l["mean_seconds_same_sets"],
         fmt="{:g} s")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
