"""Which Arduino pin is the wire in? Scored on clicked labels (data/arduino_pins/board/labels.json).

The step check's own steps for an Arduino pin, without a lesson: Haiku finds the Arduino's header (arduino.zoom), it
is cut from the full-size photo and enlarged, and the model is asked which pin socket each wire is in, with the old
question (--rule none) or the step check's rule for pins (--rule new: arduino.PIN_HOW, count the header's openings).

    python research/recognition/arduino_pin_eval2.py --rule none
    python research/recognition/arduino_pin_eval2.py --rule new [--model claude-haiku-5-5]
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
DIR = ROOT / "data" / "arduino_pins" / "board"
RUNS = ROOT / "research" / "recognition" / "runs" / "arduino_pins2"

ASK = """The images: 1) a close-up of an Arduino's pin header, 2) the whole photo.
How the Arduino shows its pins: every pin socket in the header has its label printed beside it on the board (AREF,
GND, 13, 12, ~11 ... 0, 5V, 3V3, A0 ...).
Find every jumper wire plugged into the Arduino's header (not the breadboard) and say which pin socket it is in.
{rule}
Answer ONLY with JSON: {{"wires": [{{"colour": "", "pin": "", "why": ""}}]}} ("pin": the label as printed; "why": at
most 12 words)."""


def norm(p):
    p = str(p or "").upper().replace("PIN", "").replace("~", "").replace("D", "", 1 if str(p).upper().startswith("D") else 0).strip()
    return {"3.3V": "3V3", "3.3": "3V3", "GROUND": "GND"}.get(p, "GND" if p.startswith("GN") else p)


def one(name, lab, model, rule):
    from gather import gather_vlm as vlm
    from validator import arduino
    photo = DIR / f"{name}.jpg"
    plan_ = {"legs": [{"who": "the wire's ends", "kind": "pin"}]}
    t = time.time()
    zoomed, zcost = arduino.zoom(str(photo), plan_)
    imgs = ([zoomed["arduino"]] if zoomed.get("arduino") else []) + [vlm.shrink(str(photo), 1600, 85)]
    out, st, _ = vlm.ask(model, imgs, ASK.format(rule=arduino.PIN_HOW if rule == "new" else ""), max_tokens=3000,
                         effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        wires = json.loads(out[i:j + 1])["wires"]
    except Exception:
        wires = []
    got = [norm(w.get("pin")) for w in wires]
    want = [norm(e["pin"]) for e in lab["ends"] if e.get("pin")]
    hits = sum(1 for w in want if w in got)
    return {"photo": name, "want": want, "read": got, "right": hits, "n": len(want), "crop": bool(zoomed.get("arduino")),
            "why": [w.get("why") for w in wires], "cost_usd": round((st.get("cost_usd") or 0) + zcost, 5),
            "seconds": round(time.time() - t, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", default="new", choices=["none", "new"])
    ap.add_argument("--model", default="claude-opus-5-5")
    a = ap.parse_args()
    labels = {k: v for k, v in json.loads((DIR / "labels.json").read_text()).items() if not v.get("skip")}
    out = RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{a.rule}-{a.model.split('-')[1]}"
    out.mkdir(parents=True)
    with cf.ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(lambda kv: one(*kv, a.model, a.rule), sorted(labels.items())))
    n, right = sum(r["n"] for r in rows), sum(r["right"] for r in rows)
    order = ["AREF", "GND", "13", "12", "11", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1", "0"]
    off = {}
    for r in rows:
        for w in r["want"]:
            if w not in r["read"] and r["read"] and w in order and r["read"][0] in order:
                d = order.index(r["read"][0]) - order.index(w)
                off[d] = off.get(d, 0) + 1
    print(f"{a.model} rule={a.rule}: {right}/{n} pins right · off by (sockets, + = towards 0): {off} · "
          f"no close-up {sum(not r['crop'] for r in rows)} · ${sum(r['cost_usd'] for r in rows):.2f}")
    for r in rows:
        if r["right"] < r["n"]:
            print(f"  {r['photo']} want {r['want']} read {r['read']}  {r['why']}")
    (out / "results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
