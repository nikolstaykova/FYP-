"""The model comparison chart for CHECKER.md: average price per check (first look + the Opus fallback when it ran)
against how often the check is right, per model; and where the money goes. Reads runs/model_cost/results.json
(model_cost_test.py).

Run: .venv-research/bin/python research/recognition/model_cost_plot.py
Writes research/recognition/figures/checker_models.png and prints the table for CHECKER.md.
"""
import json
import statistics as S
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures" / "checker_models.png"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
PROVIDER = {"claude": BLUE, "gemini": ORANGE, "nvidia": AQUA}
NAME = {"claude-haiku-5-5": "Haiku 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5-5": "Opus 5.5",
        "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite", "gemini-3.8-flash": "Gemini 3.8 Flash",
        "nvidia/nemotron-3.5-super-vl-120b-a12b": "Nemotron 3.5 VL (free credits)"}
OPUS = "claude-opus-5-5"


def provider(m):
    return "claude" if m.startswith("claude") else "gemini" if m.startswith("gemini") else "nvidia"


def load():
    rows = [r for r in json.loads((HERE / "runs/model_cost/results.json").read_text()) if "error" not in r]
    from kit_test import CASES
    ref = {r["case"]: r["first_verdicts"] for r in rows if r["model"] == OPUS and r["size"] == "full"}

    def score(rs, key):
        kit = [r for r in rs if r["set"] == "kit"]
        right = sum(st in ok for r in kit for t, ok in CASES[r["case"]][2].items() for st in r[key].get(t, ["(none)"]))
        of = sum(len(r[key].get(t, ["(none)"])) for r in kit for t in CASES[r["case"]][2])
        lab = [r for r in rs if r["set"] == "lab" and r["case"] in ref]
        same = sum(sorted(r[key].get(t, [])) == sorted(v) for r in lab for t, v in ref[r["case"]].items())
        tot = sum(len(ref[r["case"]]) for r in lab)
        return (100 * right / of if of else None), (100 * same / tot if tot else None), len(kit), len(lab)
    out = {}
    for m in NAME:
        for size in ("full", "1024", "768", "512"):
            rs = [r for r in rows if r["model"] == m and r["size"] == size]
            if not rs:
                continue
            kit1, lab1, nk, nl = score(rs, "first_verdicts")
            kit2, lab2, *_ = score(rs, "final_verdicts")
            first = S.mean(r["first_usd"] for r in rs) * 100
            fb = S.mean(r["fallback_usd"] for r in rs) * 100
            out[(m, size)] = {"first": first, "fallback": fb, "total": first + fb, "with_fallback": rs[0]["with_fallback"],
                              "rate": 100 * sum(r["fallback_ran"] for r in rs) / len(rs), "kit1": kit1, "kit2": kit2,
                              "lab1": lab1, "lab2": lab2, "n": len(rs), "nk": nk, "nl": nl,
                              "seconds": S.mean(r["seconds"] for r in rs)}
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


def main(size="768"):
    d = load()
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.2), gridspec_kw={"width_ratios": [1.2, 1]})
    fig.patch.set_facecolor(SURFACE)

    style(a)
    floor = 0.02  # a free first look (NVIDIA credits) is drawn at the left edge of the log axis
    for m in NAME:
        v = d.get((m, size))
        if not v:
            continue
        c = PROVIDER[provider(m)]
        x1, x2 = max(v["first"], floor), max(v["total"], floor)
        a.plot([x1, x2], [v["kit1"], v["kit2"]], color=c, linewidth=1.5, alpha=0.6, zorder=2)
        a.scatter([x1], [v["kit1"]], s=64, facecolor=SURFACE, edgecolor=c, linewidth=2, zorder=3)
        a.scatter([x2], [v["kit2"]], s=64, color=c, edgecolor=SURFACE, linewidth=2, zorder=4)
        label = NAME[m] + (f" (partial: {v['n']} of 14 photo sets)" if v["n"] < 14 else "")
        off = (7, -13) if m == "claude-sonnet-5-5" else (-62, 6) if m == "claude-haiku-5-5" else (7, 4)
        a.annotate(label, (x2, v["kit2"]), xytext=off, textcoords="offset points", fontsize=8.5, color=INK2)
    a.set_xscale("log")
    a.set_xticks([0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10], ["free", "0.05", "0.1", "0.2", "0.5", "1", "2", "5", "10"])
    a.set_xlabel("Average price per check, US cents (log scale)", color=INK2, fontsize=10)
    a.set_ylabel("Kit photos: % right", color=INK2, fontsize=10)
    a.set_title(f"Price against quality, photos at {size} px", loc="left", color=INK, fontsize=12, fontweight="bold")
    a.scatter([], [], s=64, facecolor=SURFACE, edgecolor=MUTED, linewidth=2, label="first look only")
    a.scatter([], [], s=64, color=MUTED, label="with the Opus fallback (average)")
    for p, c in PROVIDER.items():
        a.plot([], [], color=c, linewidth=6, label={"claude": "Claude", "gemini": "Google Gemini", "nvidia": "NVIDIA"}[p])
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.11), frameon=False, fontsize=8.5, labelcolor=INK2, ncols=3)

    style(b)
    b.grid(axis="y", visible=False)
    ms = [m for m in NAME if (m, size) in d]
    ys = list(range(len(ms)))[::-1]
    first = [d[(m, size)]["first"] for m in ms]
    fb = [d[(m, size)]["fallback"] for m in ms]
    b.barh(ys, first, color=INK2, edgecolor=SURFACE, linewidth=2, height=0.62, label="First look")
    b.barh(ys, fb, left=first, color="#e87ba4", edgecolor=SURFACE, linewidth=2, height=0.62, label="Opus fallback (average)")
    for y, m in zip(ys, ms):
        v = d[(m, size)]
        note = "no fallback (it is Opus)" if m == OPUS else f"fallback in {v['rate']:.0f}% of checks"
        b.text(v["total"] * 1.02 + 0.05, y, f"{v['total']:.2f}¢ · {note}", va="center", fontsize=8.5, color=INK2)
    b.set_yticks(ys, [NAME[m] + ("*" if d[(m, size)]["n"] < 14 else "") for m in ms])
    b.set_xlim(0, max(v["total"] for (m, s), v in d.items() if s == size) * 1.65)
    b.set_xlabel("Average price per check, US cents", color=INK2, fontsize=10)
    b.set_title("Where the money goes", loc="left", color=INK, fontsize=12, fontweight="bold")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False, fontsize=8.5, labelcolor=INK2, ncols=2)

    fig.text(0.01, 0.01, "Fallback = Opus looks again at the questions the learner would be asked (at most 3, lesson parts "
             "only), on the same photos: the worst case (in the app Haiku reads the close-up first).\n"
             "* partial: Google refused part of the run (busy / rate limit). Nemotron: free NVIDIA credits, no list price.",
             fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor=SURFACE)
    print(OUT)
    print("| Model | Size | First look | + Opus fallback | Average per check | Fallback ran | Kit right: first → with fallback | Your photos same as Opus: first → with fallback | Seconds |")
    print("|---|---|---|---|---|---|---|---|---|")
    f = lambda x: "–" if x is None else f"{x:.0f}%"
    for m in NAME:
        for s in ("full", "1024", "768", "512"):
            v = d.get((m, s))
            if not v:
                continue
            fbk = f"{v['fallback']:.2f}¢" if v["with_fallback"] and m != OPUS else "–"
            arrow = (lambda p, q: f"{f(p)} → {f(q)}" if v["with_fallback"] and m != OPUS else f(p))
            print(f"| {NAME[m]} | {s} | {v['first']:.2f}¢ | {fbk} | {v['total']:.2f}¢ | "
                  f"{(str(round(v['rate'])) + '%') if v['with_fallback'] and m != OPUS else '–'} | {arrow(v['kit1'], v['kit2'])} | "
                  f"{arrow(v['lab1'], v['lab2'])} | {v['seconds']:.0f} |")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    main(*(sys.argv[1:2] or ["768"]))
