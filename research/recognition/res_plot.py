"""The cost chart for CHECKER.md: what each input setting costs per check against how often the check is right, and
where the money goes (photo, instructions, answer). Reads runs/res_test/results.json (res_test.py).

Run: .venv-research/bin/python research/recognition/res_plot.py
Writes research/recognition/figures/checker_cost.png.
"""
import json
import statistics as S
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures" / "checker_cost.png"
P_IN, P_OUT = 0.10 / 1e6, 0.50 / 1e6  # Haiku 5.5, $ per token (in, out)
CENTS = 100

# palette: the dataviz default (slots 1-3), light surface, ink and grid
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

SIZES = ["full", "1280", "1024", "768", "512", "384"]
LABEL = {"full": "full size", "full-again": "full size, run 2", "1280": "1280 px", "1024": "1024 px", "768": "768 px",
         "512": "512 px", "384": "384 px", "full-q35": "full, JPEG q35", "full-q15": "full, JPEG q15"}


def load():
    rows = [r for r in json.loads((HERE / "runs/res_test/results.json").read_text()) if "verdicts" in r]
    full = {r["case"]: r["verdicts"] for r in rows if r["variant"] == "full"}
    out = {}
    for v in LABEL:
        rs = [r for r in rows if r["variant"] == v]
        kit = [r for r in rs if r["set"] == "kit"]
        lab = [r for r in rs if r["set"] == "lab"]
        same = sum(sorted(r["verdicts"].get(t, [])) == sorted(x) for r in lab for t, x in full[r["case"]].items())
        tot = sum(len(full[r["case"]]) for r in lab)
        img = S.mean(r["image_tokens"] for r in rs)
        txt = S.mean(r["tokens_in"] for r in rs) - img
        ans = S.mean(r["tokens_out"] for r in rs)
        out[v] = {"kit": 100 * sum(r["right"] for r in kit) / sum(r["of"] for r in kit), "lab": 100 * same / tot,
                  "photo": img * P_IN * CENTS, "text": txt * P_IN * CENTS, "answer": ans * P_OUT * CENTS}
        out[v]["cost"] = out[v]["photo"] + out[v]["text"] + out[v]["answer"]
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
    d = load()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.patch.set_facecolor(SURFACE)

    # 1. price against how often it is right
    style(a)
    a.axhspan(88, 100, color=GRID, alpha=0.5, linewidth=0)
    a.text(0.142, 101.4, "Grey band: the same photos checked again land anywhere in 88–100% (the model's own noise)",
           fontsize=8.5, color=INK2)
    for key, colour, name in (("kit", BLUE, "Kit photos: % right (50 answers)"),
                              ("lab", ORANGE, "Your photos: % same as full size (25 verdicts)")):
        xs = [d[v]["cost"] for v in LABEL]
        ys = [d[v][key] for v in LABEL]
        a.scatter(xs, ys, s=64, color=colour, edgecolor=SURFACE, linewidth=2, zorder=3, label=name)
    for v in ("full", "768", "512", "384", "full-q15"):
        a.annotate(LABEL[v], (d[v]["cost"], d[v]["kit"]), xytext=(8, -12) if v == "512" else (6, 6), textcoords="offset points",
                   fontsize=8.5, color=INK2)
    a.set_xlabel("Cost per check (US cents, Haiku 5.5)", color=INK2, fontsize=10)
    a.set_ylabel("How often the check is right (%)", color=INK2, fontsize=10)
    a.set_ylim(70, 103.5)
    a.set_title("Price against quality: every input setting", loc="left", color=INK, fontsize=12, fontweight="bold")
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False, fontsize=8.5, labelcolor=INK2, ncols=2)

    # 2. where the money goes
    style(b)
    b.grid(axis="y", visible=False)
    ys = range(len(SIZES))[::-1]
    left = [0] * len(SIZES)
    for part, colour, name in (("photo", BLUE, "Photo"), ("text", AQUA, "Instructions"), ("answer", ORANGE, "Answer")):
        w = [d[v][part] for v in SIZES]
        b.barh(list(ys), w, left=left, color=colour, edgecolor=SURFACE, linewidth=2, height=0.62, label=name)
        left = [l + x for l, x in zip(left, w)]
    for y, v in zip(ys, SIZES):
        share = 100 * d[v]["answer"] / d[v]["cost"]
        b.text(d[v]["cost"] + 0.003, y, f"{d[v]['cost']:.3f}¢  ·  answer {share:.0f}%", va="center", fontsize=8.5,
               color=INK2)
    b.set_yticks(list(ys), [LABEL[v] for v in SIZES])
    b.set_xlim(0, 0.29)
    b.set_xlabel("Cost per check (US cents)", color=INK2, fontsize=10)
    b.set_title("Where the money goes (long edge of the photo)", loc="left", color=INK, fontsize=12, fontweight="bold")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False, fontsize=8.5, labelcolor=INK2, ncols=3)

    fig.text(0.01, 0.01, "JPEG quality changes the file size only, never the price: Claude counts an image by its pixels "
             "(⌈w/28⌉ × ⌈h/28⌉ tokens). 126 checks, 5 Nov 2026, about 25¢ in total.", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor=SURFACE)
    print(OUT)
    for v in LABEL:
        print(f"{v:11} cost {d[v]['cost']:.4f}c kit {d[v]['kit']:.0f}% lab {d[v]['lab']:.0f}% "
              f"photo {d[v]['photo']:.4f} text {d[v]['text']:.4f} answer {d[v]['answer']:.4f}")


if __name__ == "__main__":
    main()
