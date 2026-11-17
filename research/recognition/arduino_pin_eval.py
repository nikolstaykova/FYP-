"""Score the step check's Arduino pin reading on labelled photos.

Photos in data/arduino_pins/<label>/, the folder is the pin the wire is really in: pin11, pin13, pinGND ...
Each photo goes through the real step check (validator.arduino.check) of the blink step that wires that pin
(GND: step 4, the ground wire; any other: step 3, the signal wire) and the pin it reads is compared with the label.

    python research/recognition/arduino_pin_eval.py
Writes research/recognition/runs/arduino_pins/<time>/: results.json and each photo's Arduino close-up.
"""
import concurrent.futures as cf
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
PHOTOS = ROOT / "data" / "arduino_pins"
OUT = ROOT / "research" / "recognition" / "runs" / "arduino_pins" / time.strftime("%Y%m%d-%H%M%S")


def norm(pin):
    p = str(pin or "").upper().replace("PIN", "").replace("~", "").replace("D", "").strip()
    return "GND" if p.startswith("GN") else p


def one(path, want):
    from validator import arduino
    keep = OUT / f"{path.parent.name}__{path.stem}"
    keep.mkdir(parents=True, exist_ok=True)
    step = "step-4" if want == "GND" else "step-3"
    r = arduino.check("blink", step, [str(path)], keep=keep)
    pin = next((v.get("pin") for v in (r.get("readings") or {}).values() if v.get("pin")), None)
    why = next((v.get("why") for v in (r.get("readings") or {}).values() if v.get("pin")), "")
    return {"photo": f"{path.parent.name}/{path.name}", "want": want, "read": norm(pin), "right": norm(pin) == want,
            "why": why, "cost_usd": r.get("cost_usd")}


def main():
    todo = [(p, d.name[3:].upper()) for d in sorted(PHOTOS.iterdir()) if d.is_dir() and d.name.startswith("pin")
            for p in sorted(d.glob("*.jpg"))]
    OUT.mkdir(parents=True)
    with cf.ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(lambda x: one(*x), todo))
    for r in rows:
        print(f"{'ok ' if r['right'] else 'BAD'} {r['photo']:28} want {r['want']:4} read {r['read']:4}  {r['why']}")
    n = sum(r["right"] for r in rows)
    cost = sum(r["cost_usd"] or 0 for r in rows)
    print(f"pins right {n}/{len(rows)}  ${cost:.2f}  {OUT}")
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
