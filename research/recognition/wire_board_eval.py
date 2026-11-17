"""Where are the wire ends? Scored on photos of a bare breadboard, labelled by clicking (scratchpad label page).

Labels: data/wires/board/labels.json, {photo: {"ends": [{"x", "y", "column", "half": "t"|"b"|"rail", "row"}], "skip"}}
(x, y: where the end is in the photo, 0-1). Photos: data/wires/_inbox/<photo>.HEIC (or .jpg).
Column numbers are as printed on that half (on some boards the bottom half counts from the other side).

The same steps as the step check (validator/arduino.py): Haiku finds the board, it is cut from the full-size photo
and enlarged, and the model reads it with the step check's own breadboard explanation (arduino.LOOK), so what is
tuned here carries over.

    python research/recognition/wire_board_eval.py                 # tune set
    python research/recognition/wire_board_eval.py --set test
    python research/recognition/wire_board_eval.py --model claude-haiku-5-5
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
DIR = ROOT / "data" / "wires"
LABELS = DIR / "board" / "labels.json"
RUNS = ROOT / "research" / "recognition" / "runs" / "wires_board"

ASK = """{how}
Find EVERY jumper-wire end that is pushed into a hole of this breadboard (ends lying loose on the table don't count).
The first image is a close-up of the board, the second the whole photo.
For each end give: the wire's colour, the half ("top" or "bottom", or "rail" for the long + / - rows), the column
number as printed on THAT half's own number row (read the number row of the half the end is in; on some boards the
two halves are numbered from opposite ends), and the row letter. Count holes from the nearest printed number.
Answer ONLY with JSON: {{"ends": [{{"colour": "", "half": "top", "column": 0, "row": "", "sure": true, "why": ""}}]}}
("why": at most 12 words, how you counted.)"""


def split(name):
    return "test" if int(hashlib.md5(name.encode()).hexdigest(), 16) % 10 < 3 else "tune"


def jpeg(name):
    """The photo as a full-size JPEG (HEIC converted once with macOS sips)."""
    out = DIR / "board" / f"{name}.jpg"
    if not out.exists():
        src = next((DIR / "_inbox").glob(f"{name}.*"))
        if src.suffix.lower() == ".heic":
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92", str(src), "--out", str(out)],
                           check=True, capture_output=True)
        else:
            out.write_bytes(src.read_bytes())
    return out


def truth(lab):
    return sorted(f"rail" if e["half"] == "rail" else f"c{e['column']}{e['half']}" for e in lab["ends"]
                  if e.get("column") is not None or e["half"] == "rail")


RAW = """Where is each jumper-wire end that is plugged into this breadboard? For each, give the column number and
whether it is in the top or bottom half.
Answer ONLY with JSON: {"ends": [{"colour": "", "half": "top", "column": 0, "row": "", "why": ""}]}"""


def read_raw(photo, model):
    """The model as it is: the photo (sized as the API takes it) and a plain question. No crop, no explanation."""
    from gather import gather_vlm as vlm
    out, st, _ = vlm.ask(model, [vlm.shrink(str(photo), 1600, 85)], RAW, max_tokens=4000, effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        ends = json.loads(out[i:j + 1])["ends"]
    except Exception:
        ends = []
    return ends, st.get("cost_usd") or 0, None


HYBRID = """The first image is a breadboard that code has straightened. Code has also written the number of every
column in yellow boxes: the row of yellow numbers ABOVE the upper half belongs to the upper half, the row BELOW the
lower half belongs to the lower half. These yellow numbers are exact: do not count holes, read the yellow number.
The second image is the whole photo, for context.

Find every jumper-wire end that is pushed into a hole of the board (ends lying loose on the table don't count).
A wire end has a black plastic connector, wider than a hole, which hides the hole it is in: the metal pin goes into
the board at the connector's end that touches the board, at its middle; follow the connector straight down/up to the
yellow number of that column. Ignore the wire's colour and where the wire itself runs.
For each end give: "half" ("upper" or "lower" in the straightened image), "column": the yellow number of its column,
"why": at most 12 words.
Answer ONLY with JSON: {"ends": [{"colour": "", "half": "upper", "column": 0, "why": ""}]}"""


def read_hybrid(photo, model):
    """Geometry + model: code straightens the board and numbers every column (wire_geometry.numbered); the model only
    finds the wire end and reads the yellow number. Falls back to the pipeline when no grid is found."""
    sys.path.insert(0, str(ROOT / "research" / "recognition"))
    import wire_geometry
    from gather import gather_vlm as vlm
    pic, info = wire_geometry.numbered(str(photo))
    if pic is None:
        ends, cost, board = read(photo, model)
        return ends, cost, board
    out, st, _ = vlm.ask(model, [(pic, "image/jpeg"), vlm.shrink(str(photo), 1200, 80)], HYBRID, max_tokens=4000,
                         effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        ends = json.loads(out[i:j + 1])["ends"]
    except Exception:
        ends = []
    flip = info.get("upside_down")
    for e in ends:  # upper/lower in the straightened image -> the board's top/bottom half
        upper = str(e.get("half", "")).lower().startswith("u")
        e["half"] = "bottom" if upper == bool(flip) else "top"
    return ends, st.get("cost_usd") or 0, (pic, "image/jpeg")


def read(photo, model):
    from gather import gather_vlm as vlm
    from validator import arduino
    plan_ = {"legs": [{"who": "the wire's ends", "kind": "strip"}]}
    zoomed, zcost = arduino.zoom(str(photo), plan_)
    how = arduino.LOOK.split("{earlier}")[0].split("\n", 2)[2].strip()  # the breadboard explanation only
    imgs = ([zoomed["board"]] if zoomed["board"] else []) + [vlm.shrink(str(photo), 1600, 85)]
    out, st, _ = vlm.ask(model, imgs, ASK.format(how=how), max_tokens=4000, effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        ends = json.loads(out[i:j + 1])["ends"]
    except Exception:
        ends = []
    return ends, (st.get("cost_usd") or 0) + zcost, zoomed["board"]


def place(e):
    h = str(e.get("half", "")).lower()
    if h.startswith("rail"):
        return "rail"
    return f"c{e.get('column')}{'b' if h.startswith('b') else 't'}"


def one(name, lab, model, out_dir, raw=False, hybrid=False):
    t = time.time()
    want = truth(lab)
    try:
        ends, cost, board = (read_raw if raw else read_hybrid if hybrid else read)(jpeg(name), model)
    except Exception as e:
        ends, cost, board = [], 0, None
        print(name, "error", e)
    got = sorted(place(e) for e in ends)
    col = lambda x: int(x[1:-1]) if x[1:-1].isdigit() else None
    # only the ends the learner labelled count (a photo may have more wires than were labelled); the column is the
    # main score, the half separately (an upside-down board makes "top"/"bottom" ambiguous)
    hits = sum(1 for w in want if w in got)
    col_hits = sum(1 for w in want if any(col(g) == col(w) for g in got))
    near = sum(1 for w in want if not any(col(g) == col(w) for g in got)
               and any(col(g) is not None and col(w) is not None and abs(col(g) - col(w)) == 1 for g in got))
    if board:
        (out_dir / f"{name}_board.jpg").write_bytes(board[0])
    return {"photo": name, "truth": want, "read": got, "right": hits, "column_right": col_hits, "ends": len(want), "one_off": near,
            "all_right": col_hits == len(want),
            "why": [e.get("why") for e in ends], "cost_usd": round(cost, 5), "seconds": round(time.time() - t, 1),
            "board": f"{name}_board.jpg" if board else None}


def page(rows, out_dir, title):
    cells = []
    for r in sorted(rows, key=lambda r: (r["all_right"], r["photo"])):
        b = f'<img src="{r["board"]}">' if r["board"] else ""
        cells.append(f'<div class="c {"ok" if r["all_right"] else "bad"}"><b>{"right" if r["all_right"] else "WRONG"}</b> '
                     f'true {html.escape(" ".join(r["truth"]))} · read {html.escape(" ".join(r["read"]))}<br>'
                     f'<img src="{(DIR / "board" / (r["photo"] + ".jpg")).as_uri()}">{b}<small>{r["photo"]} · '
                     f'{html.escape(json.dumps(r["why"]))}</small></div>')
    (out_dir / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title><style>body{{font:14px system-ui;margin:16px}}"
        ".g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px}}.c{{border:2px solid #ccc;"
        "padding:8px;border-radius:8px}}.bad{{border-color:#d33}}.ok{{border-color:#3a3}}.c img{{width:100%;margin-top:6px}}"
        f"small{{color:#666}}</style><h2>{html.escape(title)}</h2><div class=g>{''.join(cells)}</div>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="tune", choices=["tune", "test", "all"])
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--hybrid", action="store_true", help="geometry straightens and numbers the columns, the model reads")
    ap.add_argument("--raw", action="store_true", help="the model as it is: whole photo, plain question")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    labels = json.loads(LABELS.read_text())
    todo = [(n, l) for n, l in sorted(labels.items()) if not l.get("skip") and truth(l)
            and (a.set == "all" or split(n) == a.set)][:a.limit]
    out_dir = RUNS / (time.strftime("%Y%m%d-%H%M%S") + ("-raw" if a.raw else "-hybrid" if a.hybrid else "") + "-" + a.model.split("-")[1])
    out_dir.mkdir(parents=True)
    print(f"{len(todo)} photos ({a.set}, {a.model}) → {out_dir}")
    with cf.ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda nl: one(*nl, a.model, out_dir, a.raw, a.hybrid), todo))
    ends = sum(r["ends"] for r in rows)
    s = {"set": a.set, "model": a.model, "photos": len(rows), "photos_all_right": sum(r["all_right"] for r in rows),
         "ends": ends, "column_right": sum(r["column_right"] for r in rows),
         "column_and_half_right": sum(r["right"] for r in rows), "one_column_off": sum(r["one_off"] for r in rows), "cost_usd": round(sum(r["cost_usd"] for r in rows), 3)}
    (out_dir / "results.json").write_text(json.dumps({"summary": s, "rows": rows}, indent=1))
    title = (f"Wire ends · {a.set} · {a.model}{' · RAW' if a.raw else ' · HYBRID' if a.hybrid else ' · pipeline'} · column right {s['column_right']}/{ends} "
             f"(with the half too {s['column_and_half_right']}), one column off {s['one_column_off']}")
    page(rows, out_dir, title)
    print(title, f"· ${s['cost_usd']}")
    print(f"page: {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
