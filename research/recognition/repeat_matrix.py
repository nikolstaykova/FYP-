"""Haiku against Gemini Flash-Lite, 10 runs of every photo setting, so averages are past the run-to-run noise.

Settings: long edge 1024 / 768 / 512 px x JPEG quality 85 / 35 / 15; first look only (no fallback); the 14 photo
sets of res_test.cases (10 labelled kit cases, 4 of your Parts Quest photo sets). Scores per run: kit % right
(kit_test labels) and your photos % of verdicts the same as Opus at full size (runs/model_cost). Resumable: rows are
saved as they come, a rerun only does what is missing (Google's 503 / 429 are retried with a pause).

Run: PYTHONPATH=code .venv-research/bin/python research/recognition/repeat_matrix.py [runs]
Writes runs/repeat_matrix/results.json; repeat_plot.py draws the chart.
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "runs/repeat_matrix"
MODELS = {"claude-haiku-5-5": 8, "gemini-3.5-flash-lite": 3}  # model: parallel calls
SIZES = [("1024", 1024), ("768", 768), ("512", 512)]
QUALITIES = [85, 35, 15]
LOCK = threading.Lock()


def one(case, model, size, q, run):
    from checker import gather
    from model_cost_test import first, _verdicts
    from res_test import variant
    name, edge = size
    photos = [str(variant(p, edge, q)[0]) for p in case["photos"]]
    rec, _ = gather.lesson(case["lesson"])
    row = {"case": case["name"], "set": case["set"], "model": model, "size": name, "q": q, "run": run}
    for attempt in range(6):
        try:
            seen, st = first(model, photos, rec, case["lesson"])
            res = gather.check(case["lesson"], photos, research=False, seen=seen)
            row.update(usd=st.get("cost_usd") or 0.0, s=st.get("seconds"), out=st.get("tokens_out"),
                       verdicts=_verdicts(res))
            row.pop("error", None)
            return row
        except Exception as e:
            row["error"] = repr(e)[:200]
            busy = any(x in row["error"] for x in ("503", "429", "Connection", "URLError", "overloaded", "529"))
            if not busy:
                return row
            time.sleep(20 * (attempt + 1))
    return row


def main():
    from res_test import cases, IMG
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    IMG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "results.json"
    rows = [r for r in json.loads(f.read_text()) if "error" not in r] if f.exists() else []
    have = {(r["case"], r["model"], r["size"], r["q"], r["run"]) for r in rows}
    cs = cases()

    def save(r):
        with LOCK:
            rows.append(r)
            if len(rows) % 20 == 0 or "error" in r:
                f.write_text(json.dumps(rows))
            done = sum(1 for x in rows if x["model"] == r["model"] and "error" not in x)
            if done % 50 == 0 or "error" in r:
                print(f"{r['model']}: {done} done" + (f"  error {r['error'][:90]}" if "error" in r else ""), flush=True)

    def run_model(model, threads):
        todo = [(c, model, s, q, k) for k in range(runs) for s in SIZES for q in QUALITIES for c in cs
                if (c["name"], model, s[0], q, k) not in have]
        print(f"{model}: {len(todo)} to run", flush=True)
        with ThreadPoolExecutor(threads) as pool:
            for r in pool.map(lambda t: one(*t), todo):
                save(r)

    ts = [threading.Thread(target=run_model, args=(m, n)) for m, n in MODELS.items()]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    f.write_text(json.dumps(rows))
    ok = [r for r in rows if "error" not in r]
    print(f"done: {len(ok)} rows, {len(rows) - len(ok)} errors, spent ${sum(r.get('usd') or 0 for r in ok):.2f}")


if __name__ == "__main__":
    main()
