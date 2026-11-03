"""Lessons for every usable 3D model (data/reference/omr_audit.json), smallest first, several at a time; sets that
already have a lesson are skipped, so the run can be stopped and started again.
  python -m graph.lesson_batch [--workers 4] [--limit N]    run
  python -m graph.lesson_batch --summary                     data/lessons/lego3d/BATCH.md from every stats.json
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "lessons" / "lego3d"
LOGS = ROOT / "tests" / "tests" / "experiments" / "graphgen" / "logs" / "lessons_batch"


def usable():
    audit = json.loads((ROOT / "data" / "reference" / "omr_audit.json").read_text())
    rows = [r for r in audit if r["class"].startswith("USABLE")]
    return [r["set"] for r in sorted(rows, key=lambda r: r.get("model_pieces") or 0)]


def one(s):
    if (OUT / s / "stats.json").exists():
        return s, "skipped"
    LOGS.mkdir(parents=True, exist_ok=True)
    for attempt in range(30):  # the subscription's session limit: wait for the reset and try again
        with open(LOGS / f"{s}.log", "w") as log:
            try:
                r = subprocess.run([sys.executable, "-m", "graph.lego_3d.lesson", s], cwd=ROOT, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=5400)
            except subprocess.TimeoutExpired:
                return s, "timed out"
        if r.returncode == 0:
            return s, "ok"
        text = (LOGS / f"{s}.log").read_text(errors="replace")
        if not re.search(r"session limit|usage limit|weekly limit|rate limit|hit your|authenticate|reach the API|ENOTFOUND|ECONNRESET|"
                         r"Request timed out|overloaded", text):
            return s, f"failed ({r.returncode})"
        # not the lesson's fault: the usage limit, a lapsed login, the network down. Wait and try again
        print(f"{s}: {'usage limit' if 'limit' in text else 'login or network'}, waiting 15 min", flush=True)
        time.sleep(900)
    return s, "failed (limit)"


def summary():
    rows, fails = [], []
    for s in usable():
        f = OUT / s / "stats.json"
        if f.exists():
            rows.append(json.loads(f.read_text()))
        elif (LOGS / f"{s}.log").exists():
            fails.append(s)
    by = collections.Counter()
    clean = 0
    for r in rows:
        rules = collections.Counter(i[0] for i in r["issues_final"])
        by.update({k: 1 for k in rules})
        clean += not r["issues_final"]
    n = len(rows)
    pct = lambda x: f"{100 * x / max(1, n):.0f}%"
    md = ["# Lessons for every usable 3D model", "",
          f"{n} lessons made, {len(fails)} failed, timed out or still running, {len(usable()) - n - len(fails)} not run yet.", "",
          "| | Sets |", "|---|---:|", f"| No problems left | {clean} ({pct(clean)}) |"]
    names = {"S1": "piece missing or used twice", "S2": "piece in the air", "S3": "sub-assembly not attached",
             "S4": "step too big", "S5": "too many one-piece steps", "S6": "path blocked", "S7": "out of LEGO's order"}
    md += [f"| With '{names.get(k, k)}' ({k}) | {v} ({pct(v)}) |" for k, v in sorted(by.items())]
    if rows:
        md += ["", f"Time per set: median {sorted(r['seconds'] for r in rows)[n // 2]:.0f} s; cost per set: median "
                   f"${sorted(r['cost_usd'] for r in rows)[n // 2]:.2f}, total ${sum(r['cost_usd'] for r in rows):.0f}."]
    md += ["", "| Set | Name | Pieces | Steps | Problems left |", "|---|---|---:|---:|---|"]
    md += [f"| {r['set']} | {r['name']} | {r['pieces']} | {r['steps']} | "
           f"{dict(collections.Counter(i[0] for i in r['issues_final'])) or '–'} |" for r in rows]
    if fails:
        md += ["", "Failed or timed out: " + ", ".join(fails)]
    (OUT / "BATCH.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:14]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--summary", action="store_true")
    cfg = ap.parse_args()
    if cfg.summary:
        return summary()
    sets = usable()[:cfg.limit] if cfg.limit else usable()
    done = 0
    with ThreadPoolExecutor(cfg.workers) as ex:
        for s, how in ex.map(one, sets):
            done += 1
            if how != "skipped":
                print(f"{done}/{len(sets)} {s} {how}", flush=True)
            if done % 20 == 0:
                summary()
    summary()


if __name__ == "__main__":
    main()
