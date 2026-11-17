"""Score the resistor reader (code/gather/resistor.py) on labelled photos.

Photos go in data/resistors/<value>/, one folder per value, named as printed: 270, 4.7k, 10k, 1M.
The folder name is the label; file names don't matter. data/ is git-ignored, so photos stay on this Mac.

Each photo is put in "tune" or "test" by its file name (fixed, about 70/30). Change the reader using only
the tune results, then check test once at the end, so the score isn't fitted to the same photos.

    python research/recognition/resistor_eval.py                 # tune set
    python research/recognition/resistor_eval.py --set test      # test set
    python research/recognition/resistor_eval.py --set all --limit 20
    python research/recognition/resistor_eval.py --free          # code only: how often it finds the body and 3-6 bands (Haiku's crop cached)

Each run writes research/recognition/runs/resistors/<time>/: results.json, a page (index.html) with every
photo's numbered strip and outcome, and prints right / wrong / not sure / failed-at-stage counts and cost.
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import io
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
PHOTOS = ROOT / "data" / "resistors"
RUNS = ROOT / "research" / "recognition" / "runs" / "resistors"
EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def ohms(label):
    s = label.strip().lower().replace("ω", "").replace("ohm", "").replace("r", "")
    mult = {"k": 1e3, "m": 1e6}.get(s[-1:], 1)
    return round(float(s.rstrip("km")) * mult, 4)


def split(path):
    return "test" if int(hashlib.md5(path.name.encode()).hexdigest(), 16) % 10 < 3 else "tune"


def photos(which):
    out = []
    for d in sorted(p for p in PHOTOS.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        try:
            want = ohms(d.name)
        except ValueError:
            print(f"skipping folder {d.name}: not a value like 270, 4.7k, 1M")
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in EXT and (which == "all" or split(p) == which):
                out.append((p, want))
    return out


def jpeg(path):
    """HEIC (iPhone) → JPEG beside the run, so the reader and the page can open it."""
    if path.suffix.lower() != ".heic":
        return path
    from PIL import Image
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        sys.exit("HEIC photos need: pip install pillow-heif (or set the iPhone camera to 'Most Compatible')")
    out = path.with_suffix(".jpg")
    if not out.exists():
        Image.open(path).convert("RGB").save(out, quality=92)
    return out


def crop(path):
    """Haiku's box around the resistor, cut out once and kept in data/resistors/.crops (later runs reuse it)."""
    c = PHOTOS / ".crops" / f"{path.parent.name}__{path.stem}.jpg"
    if not c.exists():
        from gather import gather_vlm as vlm
        got, _ = vlm.zoom(str(path), what="the resistor's body (the small beige or blue part with coloured bands; "
                          "include all its bands, not the long legs)")
        if not got:
            return None
        c.parent.mkdir(exist_ok=True)
        c.write_bytes(got[0])
    return c


def free(path):
    """Code only: does it find the body and 3-6 bands in Haiku's crop (cached, so free after the first run)?"""
    import numpy as np
    from PIL import Image
    from gather import resistor
    c = crop(path)
    if c is None:
        return {"stage": "no resistor"}
    img = np.asarray(Image.open(c).convert("RGB"))
    strip, info = resistor.body(img)
    if strip is None:
        return {"stage": "body", "why": info}
    found = [b for b in resistor.bands(strip, info["background"]) if 0.03 < (b["from"] + b["to"]) / 2 < 0.97]
    return {"stage": "ok" if 3 <= len(found) <= 6 else "bands", "n": len(found), "code": [b["code"] for b in found],
            "white_background": info["white_background"]}


MODELS = {}


def one(path, want, out_dir, is_free):
    keep = out_dir / "strips" / f"{path.parent.name}__{path.stem}"
    keep.mkdir(parents=True, exist_ok=True)
    t = time.time()
    try:
        src = jpeg(path)
        r = free(src) if is_free else __import__("gather.resistor", fromlist=["read"]).read(str(src), keep=keep, **MODELS)
    except Exception as e:  # one bad photo shouldn't stop the run
        r = {"value": None, "why": f"error: {e}"}
    r["seconds"] = round(time.time() - t, 1)
    v = r.get("value")
    if is_free:
        outcome = r.get("stage", "error")
    elif not v:
        why = r.get("why", "")
        outcome = ("no resistor" if "no resistor" in why else "bands" if "bands, not" in why
                   else "colours" if "colour" in why else "body")
    elif not v["sure"]:
        outcome = "not sure (right)" if abs(v["ohms"] - want) < 1e-6 else "not sure (wrong)"
    else:
        outcome = "right" if abs(v["ohms"] - want) < 1e-6 else "WRONG"
    return {"photo": str(path.relative_to(PHOTOS)), "want": want, "outcome": outcome,
            "read": v["text"] if v else None, "strip": str((keep / "resistor_strip.jpg").relative_to(out_dir))
            if (keep / "resistor_strip.jpg").exists() else None, **{k: r.get(k) for k in
            ("bands", "code", "model", "by", "why", "cost_usd", "seconds", "n", "stage")}}


def page(rows, out_dir, title):
    order = ["WRONG", "not sure (wrong)", "colours", "bands", "body", "no resistor", "not sure (right)", "right"]
    rows = sorted(rows, key=lambda r: (order.index(r["outcome"]) if r["outcome"] in order else 0, r["photo"]))
    cells = []
    for r in rows:
        src = PHOTOS / r["photo"]
        img = f'<img src="{html.escape(src.with_suffix(".jpg").as_uri() if src.suffix.lower() == ".heic" else src.as_uri())}">'
        strip = f'<img class=s src="{html.escape(r["strip"])}">' if r.get("strip") else ""
        cells.append(f'<div class="c {r["outcome"].split()[0].lower()}"><b>{html.escape(r["outcome"])}</b> '
                     f'want {r["want"]:g} · read {html.escape(str(r["read"]))}<br>{img}{strip}<small>'
                     f'{html.escape(r["photo"])}<br>bands {html.escape(str(r.get("bands")))} · '
                     f'{html.escape(str(r.get("why") or ""))}</small></div>')
    (out_dir / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title><style>body{{font:14px system-ui;"
        "margin:16px}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}"
        ".c{{border:2px solid #ccc;padding:8px;border-radius:8px}}.wrong{{border-color:#d33}}.right{{border-color:#3a3}}"
        ".c img{{width:100%;margin-top:6px}}.c img.s{{image-rendering:pixelated}}small{{color:#666}}</style>"
        f"<h2>{html.escape(title)}</h2><div class=g>{''.join(cells)}</div>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="tune", choices=["tune", "test", "all"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--free", action="store_true", help="code stages only, no colour naming")
    ap.add_argument("--root", help="another photo folder, e.g. data/resistors_web")
    ap.add_argument("--model", help="the model that names the colours (default Haiku)")
    ap.add_argument("--second", help="the model asked when the first is not sure (default Opus)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    global PHOTOS
    MODELS.update({k: v for k, v in (("first", a.model), ("second", a.second or a.model)) if v})
    PHOTOS = (ROOT / a.root) if a.root else PHOTOS
    todo = photos(a.set)[:a.limit]
    if not todo:
        sys.exit(f"no photos in {PHOTOS}/<value>/ for set '{a.set}'")
    out_dir = RUNS / ((PHOTOS.name + "-") + time.strftime("%Y%m%d-%H%M%S") + ("-code" if a.free else ""))
    out_dir.mkdir(parents=True)
    print(f"{len(todo)} photos ({a.set}) → {out_dir}")
    with cf.ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda pw: one(*pw, out_dir, a.free), todo))
    counts = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    cost = sum(r.get("cost_usd") or 0 for r in rows)
    summary = {"set": a.set, "photos": len(rows), "counts": counts, "cost_usd": round(cost, 4),
               "right_pct": round(100 * counts.get("right", 0) / len(rows), 1),
               "wrong_pct": round(100 * counts.get("WRONG", 0) / len(rows), 1)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))
    page(rows, out_dir, f"Resistors · {a.set} · {summary['right_pct']}% right, {summary['wrong_pct']}% wrong")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:18} {v}")
    print(f"right {summary['right_pct']}%  wrong {summary['wrong_pct']}%  cost ${cost:.3f}")
    print(f"page: {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
