"""Labelled resistor photos from Wikimedia Commons ("Category:Resistors by value": one category per value).

Saves data/resistors_web/<value>/commons_<n>.jpg (originals shrunk to 1600 px) and data/resistors_web/credits.json (file page, author,
licence: Commons files are free licences but most need the author credited if shown in the report).
Score them with: python research/recognition/resistor_eval.py --root data/resistors_web --set all
"""
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "resistors_web"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "fyp-resistor-research/0.1 (student project; one-off download)"}


def get(params):
    q = urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=30) as r:
        return json.load(r)


def small(data, dest, edge=1600):
    """Originals (thumbnails stall on Commons), shrunk here."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((edge, edge))
    im.save(dest, quality=92)


def tag(title):
    m = re.match(r"Category:([\d.]+)\s*(k|kilo|m|mega)?\s*-?ohm", title, re.I)
    if not m or float(m.group(1)) == 0:
        return None
    unit = (m.group(2) or "").lower()
    return f"{float(m.group(1)):g}" + ("k" if unit.startswith("k") else "M" if unit.startswith("m") else "")


def main():
    cats = get({"action": "query", "list": "categorymembers", "cmtitle": "Category:Resistors by value",
                "cmtype": "subcat", "cmlimit": 500})["query"]["categorymembers"]
    credits = {}
    for c in cats:
        v = tag(c["title"])
        if not v:
            continue
        files = get({"action": "query", "list": "categorymembers", "cmtitle": c["title"], "cmtype": "file",
                     "cmlimit": 100})["query"]["categorymembers"]
        for f in files:  # one file per request: asking for a whole category's image info stalls on Commons
            try:
                d = get({"action": "query", "titles": f["title"], "prop": "imageinfo", "iiprop": "url|mime|extmetadata"})
            except OSError as e:
                print("  skipped", f["title"], e)
                continue
            p = next(iter(d["query"]["pages"].values()))
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
                continue  # SVG drawings, PDFs
            name = f"commons_{p['pageid']}.jpg"
            dest = OUT / v / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                for tries in range(3):  # upload.wikimedia.org sometimes stalls
                    try:
                        with urllib.request.urlopen(urllib.request.Request(ii["url"], headers=UA), timeout=60) as r:
                            small(r.read(), dest)
                        break
                    except OSError as e:
                        print("  retry", p["title"], e)
                        time.sleep(3)
                time.sleep(0.3)  # gentle on Commons
            meta = ii.get("extmetadata") or {}
            credits[f"{v}/{name}"] = {"page": ii.get("descriptionurl"), "title": p["title"],
                                      "author": re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip(),
                                      "licence": (meta.get("LicenseShortName") or {}).get("value")}
        print(f"{c['title']:40} → {v}")
    (OUT / "credits.json").write_text(json.dumps(credits, indent=1, ensure_ascii=False))
    print(f"{len(credits)} photos in {OUT}")


if __name__ == "__main__":
    main()
