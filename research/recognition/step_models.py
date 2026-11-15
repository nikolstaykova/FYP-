"""Which model reads a breadboard build and a resistor best? The validator's step check (code/validator/arduino.py)
and the resistor bands, asked of Claude, Gemini and NVIDIA models on the learner's own photos (15 Nov 2026).

Board photos (runs/lab/step-*), labelled by hand from the full-size photos: Blink on a 60-column board.
  a072, 4ed0  step 2 (the resistor): its legs are in columns 10 and 15, top half
  c48b, 4acd  step 3 (the LED), the resistor in 10 and 15: the LED's long leg in 15 (it shares the resistor's
              column), its short leg in 18
  cd20        step 3 on a product photo with nothing built: the only right answer is "cannot see it"
Resistor close-ups (runs/lab/*/closeup_*): the learner's resistor is red, violet, brown, gold = 270 ohm.
Each model: the app's exact step-check question (validator.arduino.prompt), scored leg by leg; and a neutral
"read this resistor" question, scored on the value. REPEATS runs each (Robotics-ER: 2, its free tier is 20 a day).

Run: PYTHONPATH=code .venv-research/bin/python research/recognition/step_models.py
Writes runs/step_models/results.json (resumable) and prints the table.
"""
import json
import statistics as S
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LAB = HERE / "runs/lab"
OUT = HERE / "runs/step_models"
REPEATS = 3
MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "gemini-3.5-flash-lite", "gemini-3.8-flash",
          "gemini-3.1-pro-preview", "gemini-robotics-er-2-preview", "nvidia/nemotron-3.5-super-vl-120b-a12b"]
FEWER = {"gemini-robotics-er-2-preview": 2}

BOARD = [  # (photo, step, state before it, truth: {leg key: place or "same" or None = cannot be seen})
    ("step-20261115-210417-a072", 2, {}, {"set": {"10t", "15t"}}),
    ("step-20261115-210418-4ed0", 2, {}, {"set": {"10t", "15t"}}),
    ("step-20261115-210547-c48b", 3, {"where": {"10t": "10t", "14t": "15t"}}, {"L1": "15t", "L2": "18t"}),
    ("step-20261115-210629-4acd", 3, {"where": {"10t": "10t", "14t": "15t"}}, {"L1": "15t", "L2": "18t"}),
    ("step-20261115-202656-cd20", 3, {"where": {"10t": "10t", "14t": "14t"}}, {"L1": None, "L2": None}),
]
RESISTOR = [("20261115-210100-be1d", "closeup_2.jpg"), ("20261115-205008-8f53", "closeup_1.jpg"),
            ("20261112-032650-2dc8", "closeup_1.jpg")]
RESISTOR_TRUTH = 270
RESISTOR_ASK = """This photo shows a resistor (it may be small in the photo). Read its colour bands in order, starting
from the end away from the gold or silver tolerance band, and give its value in ohms. If you cannot read the bands,
say so. Answer ONLY with JSON: {"bands": ["red", "..."], "ohms": 0, "sure": true}"""
LOCK = threading.Lock()


def ask(model, images, text):
    """(answer text, cost in dollars, seconds) from any of the models."""
    if model.startswith("claude-"):
        from gather import gather_vlm
        out, st, secs = gather_vlm.ask(model, images, text, max_tokens=3000, effort="low")
        return out, st.get("cost_usd") or 0, secs
    if model.startswith("gemini"):
        from gemini_bench import ask as g
        out, u, secs = g(model, images, text, max_tokens=6000)
        return out, u.get("cost_usd") or 0, secs
    from nvidia_bench import ask as n
    out, u, secs = n(model, images, text, max_tokens=3000)
    return out, (u or {}).get("cost_usd") or 0, secs


def board_case(model, case, run):
    from gather import gather_vlm
    from validator import arduino as A
    name, step, state, truth = case
    p = A.plan("blink", step)
    photo = LAB / name / "photo_1.jpg"
    out, cost, secs = ask(model, [gather_vlm.shrink(str(photo), 1600, 85)], A.prompt(p, state))
    readings, _ = A._answer(out)
    got = {x["key"]: A.reading_place(x, readings.get(x["key"])) for x in p["legs"]}
    same = {x["key"]: (readings.get(x["key"]) or {}).get("same") for x in p["legs"]}
    if "set" in truth:  # either leg of the resistor in either column
        right = [g in truth["set"] for g in got.values()]
        if len(set(got.values())) < len(got):
            right = [False] * len(got)
    else:
        right = []
        for k, want in truth.items():
            if want is None:  # nothing built: only "cannot see it" is right
                right.append(got[k] is None and same[k] is not True)
            else:
                right.append(got[k] == want or (k == "L1" and same[k] is True and got[k] in (None, want)))
    verdict = A.judge(p, readings, state)["verdict"]
    return {"case": name, "kind": "board", "model": model, "run": run, "right": sum(right), "of": len(right),
            "read": got, "verdict": verdict, "cost": cost, "secs": round(secs, 1), "raw": out[:1500]}


def resistor_case(model, case, run):
    from gather import gather_vlm
    d, f = case
    out, cost, secs = ask(model, [gather_vlm.shrink(str(LAB / d / f), 2400, 90)], RESISTOR_ASK)
    i, j = out.find("{"), out.rfind("}")
    try:
        ans = json.loads(out[i:j + 1])
    except ValueError:
        ans = {}
    try:
        ohms = float(ans.get("ohms") or 0)
    except (TypeError, ValueError):
        ohms = 0
    return {"case": f"{d}/{f}", "kind": "resistor", "model": model, "run": run, "right": int(round(ohms) == RESISTOR_TRUTH),
            "of": 1, "read": {"bands": ans.get("bands"), "ohms": ohms, "sure": ans.get("sure")}, "cost": cost,
            "secs": round(secs, 1), "raw": out[:600]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "results.json"
    rows = [r for r in json.loads(f.read_text()) if "error" not in r] if f.exists() else []
    have = {(r["case"], r["model"], r["run"]) for r in rows}
    todo = []
    for m in MODELS:
        for run in range(FEWER.get(m, REPEATS)):
            todo += [(board_case, m, c, run) for c in BOARD if (c[0], m, run) not in have]
            todo += [(resistor_case, m, c, run) for c in RESISTOR if (f"{c[0]}/{c[1]}", m, run) not in have]
    print(f"{len(todo)} calls to make ({len(rows)} done)", flush=True)

    def one(t):
        fn, m, c, run = t
        try:
            r = fn(m, c, run)
        except Exception as e:
            r = {"case": c[0] if fn is board_case else f"{c[0]}/{c[1]}", "model": m, "run": run, "error": repr(e)[:300]}
        with LOCK:
            rows.append(r)
            f.write_text(json.dumps(rows, indent=1))
        print(f"{m:40} {r['case'][-30:]:30} " + (f"{r['right']}/{r['of']} {r['secs']}s ${r['cost']:.4f}" if "error" not in r
                                                  else r["error"][:90]), flush=True)
    by_provider = {}
    for t in todo:  # Google's quota is per minute: its calls one at a time; the others in parallel
        by_provider.setdefault("gemini" if t[1].startswith("gemini") else "other", []).append(t)
    threads = [threading.Thread(target=lambda ts=ts, n=n: list(ThreadPoolExecutor(n).map(one, ts)))
               for ts, n in ((by_provider.get("gemini", []), 4), (by_provider.get("other", []), 6))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    table(rows)


def table(rows):
    ok = [r for r in rows if "error" not in r]
    print("\n| Model | Board legs right | Empty board: said cannot see | Resistor value right | Seconds (median) | Cost per check |")
    print("|---|---|---|---|---|---|")
    for m in MODELS:
        b = [r for r in ok if r["model"] == m and r["kind"] == "board" and "cd20" not in r["case"]]
        e = [r for r in ok if r["model"] == m and r["kind"] == "board" and "cd20" in r["case"]]
        rr = [r for r in ok if r["model"] == m and r["kind"] == "resistor"]
        if not (b or rr):
            continue
        pct = lambda xs: f"{100 * sum(r['right'] for r in xs) / max(1, sum(r['of'] for r in xs)):.0f}% ({sum(r['right'] for r in xs)}/{sum(r['of'] for r in xs)})"  # noqa: E731
        secs = S.median([r["secs"] for r in b + rr]) if b + rr else 0
        cost = S.mean([r["cost"] for r in b]) * 100 if b else 0
        print(f"| {m} | {pct(b)} | {pct(e)} | {pct(rr)} | {secs:.0f} | {cost:.2f}¢ |")


if __name__ == "__main__":
    if sys.argv[1:] == ["table"]:
        table(json.loads((OUT / "results.json").read_text()))
    elif sys.argv[1:2] == ["only"]:  # only these models, once each: only gemini-3.1-pro-preview ...
        everyone = list(MODELS)
        MODELS[:] = [m for m in MODELS if m in sys.argv[2:]]
        REPEATS = 1
        FEWER.clear()
        main()
        MODELS[:] = everyone
        table(json.loads((OUT / "results.json").read_text()))
    else:
        main()
