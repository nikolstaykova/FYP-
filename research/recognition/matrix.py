"""The checker's price and quality as one matrix: photo setting (size, JPEG quality) x first-look model.
Reads runs/model_cost/results.json (6 models x 4 sizes, JPEG 85) and runs/res_test/results.json (Haiku: 384 px and
JPEG 35 / 15). Prints markdown tables for CHECKER.md.
Run: .venv-research/bin/python research/recognition/matrix.py
"""
import json
import statistics as S
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from kit_test import CASES  # noqa: E402

MODELS = [("claude-haiku-5-5", "Haiku 5.5"), ("claude-sonnet-5-5", "Sonnet 5.5"), ("claude-opus-5-5", "Opus 5.5"),
          ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"), ("gemini-3.8-flash", "Gemini 3.8 Flash"),
          ("nvidia/nemotron-3.5-super-vl-120b-a12b", "Nemotron 3.5 VL")]
ROWS = [("full", 85, "1600 px (full), JPEG 85"), ("1024", 85, "1024 px, JPEG 85"), ("768", 85, "768 px, JPEG 85"),
        ("512", 85, "512 px, JPEG 85"), ("384", 85, "384 px, JPEG 85"), ("full", 35, "1600 px, JPEG 35"),
        ("full", 15, "1600 px, JPEG 15")]
RES_NAME = {("384", 85): "384", ("full", 35): "full-q35", ("full", 15): "full-q15"}


def kit_pct(rs, key):
    kit = [r for r in rs if r["set"] == "kit"]
    right = sum(st in ok for r in kit for t, ok in CASES[r["case"]][2].items() for st in r[key].get(t, ["(none)"]))
    of = sum(len(r[key].get(t, ["(none)"])) for r in kit for t in CASES[r["case"]][2])
    return 100 * right / of if of else None


def cells():
    mc = [r for r in json.loads((HERE / "runs/model_cost/results.json").read_text()) if "error" not in r]
    rt = [r for r in json.loads((HERE / "runs/res_test/results.json").read_text()) if "verdicts" in r]
    out = {}
    for m, _ in MODELS:
        for size, q, _ in ROWS:
            if q == 85 and size != "384":
                rs = [r for r in mc if r["model"] == m and r["size"] == size]
                if rs:
                    c = {"first": 100 * S.mean(r["first_usd"] for r in rs), "kit": kit_pct(rs, "first_verdicts"),
                         "n": len(rs), "out": S.mean(r["tokens_out"] or 0 for r in rs), "s": S.mean(r["first_s"] or 0 for r in rs)}
                    if rs[0]["with_fallback"] and m != "claude-opus-5-5":
                        c["avg"] = c["first"] + 100 * S.mean(r["fallback_usd"] for r in rs)
                        c["kit2"] = kit_pct(rs, "final_verdicts")
                        c["rate"] = 100 * sum(r["fallback_ran"] for r in rs) / len(rs)
                    out[(m, size, q)] = c
            elif m == "claude-haiku-5-5":
                rs = [r for r in rt if r["variant"] == RES_NAME[(size, q)]]
                for r in rs:
                    r["first_verdicts"] = r["verdicts"]
                out[(m, size, q)] = {"first": 100 * S.mean(r["cost_usd"] for r in rs), "kit": kit_pct(rs, "first_verdicts"),
                                     "n": len(rs), "out": S.mean(r["tokens_out"] for r in rs), "s": S.mean(r["seconds"] for r in rs),
                                     "other_run": True}
    return out


def table(out, fmt, title):
    print(f"\n**{title}**\n")
    print("| Photo setting | " + " | ".join(n for _, n in MODELS) + " |")
    print("|---|" + "---|" * len(MODELS))
    for size, q, label in ROWS:
        row = []
        for m, _ in MODELS:
            c = out.get((m, size, q))
            row.append(fmt(c, m) if c else "not run")
        print(f"| {label} | " + " | ".join(row) + " |")


def main():
    out = cells()
    part = lambda c: f" ({c['n']}/14)" if c["n"] < 14 else ""
    table(out, lambda c, m: ("free" if m.startswith("nvidia") else f"{c['first']:.2f}¢") + part(c) +
          ("†" if c.get("other_run") else ""), "First look: price per check (US cents)")
    table(out, lambda c, m: f"{c['kit']:.0f}%" + part(c) + ("†" if c.get("other_run") else ""),
          "First look: kit photos right")
    table(out, lambda c, m: (f"{c['avg']:.2f}¢ · {c['kit2']:.0f}% · Opus in {c['rate']:.0f}%" + part(c)) if "avg" in c else
          ("no fallback (it is Opus)" if m == "claude-opus-5-5" else "–"),
          "With the Opus fallback (worst case): average price · kit right · how often Opus was called")
    table(out, lambda c, m: f"{c['out']:.0f}", "Answer length (output tokens, the main cost)")
    table(out, lambda c, m: f"{c['s']:.0f} s", "Seconds per first look")


if __name__ == "__main__":
    main()
