"""The two LED photos straightened and numbered by geometry, the model reads where the legs go in.

    python research/recognition/led_pair_model.py [--side-only]
"""
import concurrent.futures as cf
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "code"))
from gather.gather_vlm import ask  # noqa: E402
from validator import geometry as G  # noqa: E402

D = ROOT / "data" / "leds" / "pairs"
Q = """{intro} The board has been straightened by code and every hole column carries its number in a yellow box, above
and below each half (they match the numbers printed on the board).
There is one LED on the board. Find where each of its two legs goes INTO a hole: follow each thin metal leg from the
LED down to the board, to the hole it disappears into, and read that hole's column number from the yellow box in line
with it. {side}
Answer ONLY with JSON: {{"columns": [a, b], "half": "top" or "bottom", "sure": true or false, "why": "a few words"}}"""


def one(v, side_only):
    imgs, intro = [], ""
    top_only = "--top-only" in sys.argv
    # where the LED is, from the photo from above (geometry), so both close-ups are centred on it
    import led_pair_eval as E
    tflat, tinfo, tshift = E.straight(D / "jpg" / f"{v['top']}.jpg")
    found = G.leds(tflat, tinfo, tshift)
    around = None
    if found:
        k = 0 if found[0]["half"] == "top" else 1
        xs = [x for x, _ in found[0]["outline"]]
        a, b = sorted(int(G.label(round(x / E.CELL - 1), k, tshift)) for x in (min(xs), max(xs)))
        around = list(range(a - 4, b + 5))
    s = G.analyse(str(D / "jpg" / f"{v['top' if top_only else 'side']}.jpg"), around=around)
    if top_only:
        intro, side = "The photo is a breadboard from above.", ""
    elif not side_only:
        t = G.analyse(str(D / "jpg" / f"{v['top']}.jpg"), around=around)
        imgs.append((t["closeup"], "image/jpeg"))
        intro = "Photo 1 is a breadboard from above, Photo 2 the same board, nothing moved, from low at the side."
        side = ("From above the LED's body hides the legs; Photo 2, from the side, shows them going in: read the "
                "columns there, and use Photo 1 to check it is the same place.")
    else:
        intro = "The photo is a breadboard from low at the side."
        side = ""
    imgs.append((s["closeup"], "image/jpeg"))
    return v, imgs, Q.format(intro=intro, side=side)


def read(job):
    v, imgs, q = job
    out, st, _ = ask("claude-opus-5-5", imgs, q, max_tokens=3000, effort="low")
    i, j = out.find("{"), out.rfind("}")
    try:
        a = json.loads(out[i:j + 1])
    except ValueError:
        a = {}
    got = sorted(int(c) for c in a.get("columns") or [])
    want = sorted([v["long"], v["short"]])
    return v, want, got, a, st["cost_usd"]


def main():
    side_only = "--side-only" in sys.argv
    lab = [v for v in json.loads((D / "labels.json").read_text()).values() if not v.get("not_pair") and v.get("long")]
    jobs = [one(v, side_only) for v in lab]  # geometry one photo at a time (it is not thread-safe)
    with cf.ThreadPoolExecutor(5) as ex:
        rows = list(ex.map(read, jobs))
    ok = 0
    for v, want, got, a, c in rows:
        ok += want == got
        print(f"{v['top']}+{v['side']}  want {want}  got {got} sure={a.get('sure')}  {'ok' if want == got else 'BAD'}  {a.get('why', '')}")
    print(f"both legs right {ok}/{len(rows)}  ${sum(r[4] for r in rows):.2f}")


if __name__ == "__main__":
    main()
