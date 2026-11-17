"""Score the step check's wire readings (code/validator/arduino.py) on labelled photos of the blink lesson.

Photos go in data/wires/<setup>/; the folder name is the label: the step, then where every end really is:
    step3_pin13_c10t      step 3 (orange wire): one end in pin 13, the other in column 10, top half
    step3_pin11_c9t       the same wire moved: pin 11, column 9
    step4_pinGND_c18t     step 4 (black wire): a GND pin and column 18, top half
    step1_c10t_c14t       step 1 (resistor): legs in columns 10 and 14 (b = bottom half)
Ends are compared as a set, so the order in the name doesn't matter. Each setup should also have the earlier
steps' parts on the board as the lesson has them (the check reads the new step's ends).

    python research/recognition/wire_eval.py                  # tune set (about 70%, fixed by file name)
    python research/recognition/wire_eval.py --set test
    python research/recognition/wire_eval.py --model claude-haiku-5-5 --second claude-opus-5-5   # another model, same photos
Writes research/recognition/runs/wires/<time>/ with results.json and index.html (photo, close-ups, read vs true).
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
PHOTOS = ROOT / "data" / "wires"
RUNS = ROOT / "research" / "recognition" / "runs" / "wires"
EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
STEPS = {1: "step-1", 2: "step-2", 3: "step-3", 4: "step-4"}


def parse(name):
    """'step3_pin13_c10t' → ('step-3', ['pin 13', 'c10t'])."""
    parts = name.lower().split("_")
    m = re.fullmatch(r"step(\d+)", parts[0])
    if not m or int(m.group(1)) not in STEPS:
        raise ValueError(name)
    ends = []
    for p in parts[1:]:
        if p.startswith("pin"):
            ends.append("pin " + p[3:].upper())
        elif re.fullmatch(r"c\d+[tb]", p):
            ends.append(p)
        else:
            raise ValueError(f"{name}: '{p}' is not pinX or c<column><t|b>")
    return STEPS[int(m.group(1))], sorted(ends)


def place(r):
    if r.get("pin"):
        p = str(r["pin"]).upper()
        return "pin GND" if "GND" in p else f"pin {p}"
    if r.get("column"):
        return f"c{r['column']}{'b' if str(r.get('half', '')).startswith('b') else 't'}"
    if r.get("rail"):
        return f"rail {r['rail']}"
    return "?"


def split(path):
    return "test" if int(hashlib.md5(path.name.encode()).hexdigest(), 16) % 10 < 3 else "tune"


def photos(which):
    out = []
    for d in sorted(p for p in PHOTOS.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        try:
            step, truth = parse(d.name)
        except ValueError as e:
            print(f"skipping folder {d.name}: {e}")
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXT and (which == "all" or split(p) == which):
                out.append((p, step, truth))
    return out


def one(path, step, truth, out_dir):
    sys.path.insert(0, str(ROOT / "research" / "recognition"))
    from resistor_eval import jpeg
    from validator import arduino
    keep = out_dir / "shots" / f"{path.parent.name}__{path.stem}"
    keep.mkdir(parents=True, exist_ok=True)
    t = time.time()
    try:
        r = arduino.check("blink", step, [str(jpeg(path))], keep=keep)
    except Exception as e:
        r = {"verdict": "error", "why": str(e), "readings": {}}
    read = sorted(place(x) for x in (r.get("readings") or {}).values())
    hits = sum(min(read.count(p), truth.count(p)) for p in set(truth))
    return {"photo": str(path.relative_to(PHOTOS)), "step": step, "truth": truth, "read": read,
            "ends_right": hits, "ends": len(truth), "all_right": hits == len(truth), "verdict": r.get("verdict"),
            "why": {k: x.get("why") for k, x in (r.get("readings") or {}).items()}, "cost_usd": r.get("cost_usd"),
            "seconds": round(time.time() - t, 1), "shots": [str((keep / f).relative_to(out_dir)) for f in
                                                              ("board.jpg", "arduino.jpg") if (keep / f).exists()]}


def page(rows, out_dir, title):
    rows = sorted(rows, key=lambda r: (r["all_right"], r["photo"]))
    cells = []
    for r in rows:
        imgs = f'<img src="{(PHOTOS / r["photo"]).as_uri()}">' + "".join(f'<img src="{s}">' for s in r["shots"])
        cells.append(f'<div class="c {"ok" if r["all_right"] else "bad"}"><b>{"right" if r["all_right"] else "WRONG"}</b>'
                     f' true {html.escape(" · ".join(r["truth"]))}<br>read {html.escape(" · ".join(r["read"]))} '
                     f'({html.escape(str(r["verdict"]))})<br>{imgs}<small>{html.escape(r["photo"])}<br>'
                     f'{html.escape(json.dumps(r["why"]))}</small></div>')
    (out_dir / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title><style>body{{font:14px system-ui;margin:16px}}"
        ".g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}.c{{border:2px solid #ccc;"
        "padding:8px;border-radius:8px}}.bad{{border-color:#d33}}.ok{{border-color:#3a3}}.c img{{width:100%;margin-top:6px}}"
        f"small{{color:#666}}</style><h2>{html.escape(title)}</h2><div class=g>{''.join(cells)}</div>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="tune", choices=["tune", "test", "all"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", help="the model that reads the step (default: validator FIRST)")
    ap.add_argument("--second", help="the model for legs the first cannot read (default: same as --model)")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.model:
        from validator import arduino
        arduino.FIRST, arduino.SECOND = a.model, a.second or a.model
    todo = photos(a.set)[:a.limit]
    if not todo:
        sys.exit(f"no photos in {PHOTOS}/<setup>/ for set '{a.set}'")
    out_dir = RUNS / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    print(f"{len(todo)} photos ({a.set}) → {out_dir}")
    with cf.ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda x: one(*x, out_dir), todo))
    ends = sum(r["ends"] for r in rows)
    good = sum(r["ends_right"] for r in rows)
    cost = sum(r.get("cost_usd") or 0 for r in rows)
    summary = {"set": a.set, "photos": len(rows), "photos_all_right": sum(r["all_right"] for r in rows),
               "ends": ends, "ends_right": good, "cost_usd": round(cost, 3)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))
    title = f"Wires · {a.set} · {summary['photos_all_right']}/{len(rows)} photos right, {good}/{ends} ends"
    page(rows, out_dir, title)
    print(title, f"· ${cost:.2f}")
    print(f"page: {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
