"""Does cropping and zooming the board photo help the step check read the columns? (16 Nov 2026)

Plain: the photo as the app sends it today (long edge 1600 px). Crop: a quick first look (Haiku) gives the box around
this step's parts and the printed column numbers nearest them; the code cuts that box from the FULL-size photo (a
margin added), enlarges it to 1600 px and sharpens it a little; the same question is asked on the crop.
Labelled photos (runs/lab/step-*, read by hand from the full-size photos), Blink:
  a072, 4ed0  step 2 (resistor): columns 10 and 15
  9d61        step 2 (resistor): columns 10 and 13   (the "13 instead of 14" photo; the board is small in it)
  c48b, 4acd  step 3 (LED), resistor in 10 and 15: long leg 15 (shares), short leg 18

Run: PYTHONPATH=code .venv-research/bin/python research/recognition/step_crop.py
"""
import io
import json
import statistics as S
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

HERE = Path(__file__).resolve().parent
LAB = HERE / "runs/lab"
OUT = HERE / "runs/step_crop"
CASES = [
    ("step-20261115-210417-a072", 2, {}, {"set": {"10t", "15t"}}),
    ("step-20261115-210418-4ed0", 2, {}, {"set": {"10t", "15t"}}),
    ("step-20261115-213655-9d61", 2, {}, {"set": {"10t", "13t"}}),
    ("step-20261115-210547-c48b", 3, {"where": {"10t": "10t", "14t": "15t"}}, {"L1": "15t", "L2": "18t"}),
    ("step-20261115-210629-4acd", 3, {"where": {"10t": "10t", "14t": "15t"}}, {"L1": "15t", "L2": "18t"}),
]
MODELS = ["claude-haiku-5-5", "claude-opus-5-5"]
RUNS = 2

LOCATE = """This photo shows a breadboard. In this step the learner put in: {parts}.
Find where those legs go into the board. Give ONE box that contains all those legs where they enter the holes, the
printed column numbers nearest to them (the numbers along the edge of that half), and a margin of a few columns on
each side. Coordinates from 0 to 1000 across the image (x, left to right) and down it (y, top to bottom).
Answer ONLY with JSON: {{"box": [x0, y0, x1, y1]}}"""


def full(photo):
    return ImageOps.exif_transpose(Image.open(photo)).convert("RGB")


def jpeg(im, q=90):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return b.getvalue(), "image/jpeg"


def locate(photo, plan_):
    """The box around this step's legs, in the full-size photo's pixels (or None)."""
    from gather import gather_vlm as vlm
    parts = sorted({x["who"].split("'s ")[0].replace("the ", "") for x in plan_["legs"]})
    out, st, _ = vlm.ask("claude-haiku-5-5", [vlm.shrink(str(photo), 1600, 85)], LOCATE.format(parts=", ".join(parts)),
                         max_tokens=2500, effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        x0, y0, x1, y1 = [float(v) for v in json.loads(out[i:j + 1])["box"]]
    except Exception:
        return None, st.get("cost_usd") or 0
    im = full(photo)
    W, H = im.size
    return (x0 / 1000 * W, y0 / 1000 * H, x1 / 1000 * W, y1 / 1000 * H), st.get("cost_usd") or 0


def crop_zoom(photo, box, edge=1600):
    im = full(photo)
    W, H = im.size
    x0, y0, x1, y1 = box
    mx, my = 0.15 * (x1 - x0) + 0.02 * W, 0.15 * (y1 - y0) + 0.02 * H  # a margin: the box is only roughly right
    x0, y0, x1, y1 = max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)
    c = im.crop((int(x0), int(y0), int(x1), int(y1)))
    s = edge / max(c.size)
    if s > 1:
        c = c.resize((round(c.width * s), round(c.height * s)), Image.LANCZOS)
    return c.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))


def score(plan_, readings, truth):
    from validator import arduino as A
    got = {x["key"]: A.reading_place(x, readings.get(x["key"])) for x in plan_["legs"]}
    if "set" in truth:
        right = [g in truth["set"] for g in got.values()]
        return sum(right) if len(set(got.values())) == len(got) else 0, len(got), got
    out = []
    for x in plan_["legs"]:
        r = readings.get(x["key"]) or {}
        want = truth[x["key"]]
        off = A._offset(r)
        ok = got[x["key"]] == want if got[x["key"]] else (x["shares"] and off == 0 and want == "15t")
        out.append(bool(ok))
    return sum(out), len(out), got


def one(case, model, mode, run):
    from gather import gather_vlm as vlm
    from validator import arduino as A
    name, step, state, truth = case
    p = A.plan("blink", step)
    photo = LAB / name / "photo_1.jpg"
    q = A.prompt(p, state)
    cost = 0
    if mode == "plain":
        img = vlm.shrink(str(photo), 1600, 85)
    else:
        box, c = locate(photo, p)
        cost += c
        if not box:
            return {"case": name, "model": model, "mode": mode, "run": run, "right": 0, "of": len(p["legs"]), "error": "no box"}
        crop = crop_zoom(photo, box)
        crop.save(OUT / f"{name}-{run}.jpg", quality=85)
        img = jpeg(crop)
        q = q.replace("You check one step", "This is a zoomed-in crop of the board around this step's parts. You check one step")
    out, st, secs = vlm.ask(model, [img], q, max_tokens=3000, effort="low")
    readings, _ = A._answer(out)
    right, of, got = score(p, readings, truth)
    return {"case": name, "model": model, "mode": mode, "run": run, "right": right, "of": of, "read": got,
            "cost": cost + (st.get("cost_usd") or 0), "secs": round(secs, 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(c, m, mode, r) for c in CASES for m in MODELS for mode in ("plain", "crop") for r in range(RUNS)]
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(lambda t: one(*t), jobs))
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    print("| Model | Plain photo | Cropped and zoomed | Cost per check (crop) |")
    print("|---|---|---|---|")
    for m in MODELS:
        cell = {}
        for mode in ("plain", "crop"):
            rs = [r for r in rows if r["model"] == m and r["mode"] == mode]
            cell[mode] = f"{100 * sum(r['right'] for r in rs) / max(1, sum(r['of'] for r in rs)):.0f}% ({sum(r['right'] for r in rs)}/{sum(r['of'] for r in rs)})"
        cost = S.mean([r.get("cost", 0) for r in rows if r["model"] == m and r["mode"] == "crop"]) * 100
        print(f"| {m} | {cell['plain']} | {cell['crop']} | {cost:.2f}¢ |")
    for r in rows:
        print(r["case"][-4:], r["model"][7:12], r["mode"], f"{r['right']}/{r['of']}", r.get("read"), r.get("error", ""))


if __name__ == "__main__":
    main()
