"""Build the LEGO test set: official lego.com manuals with an answer key.

For each candidate set:
  - the official building-instructions PDF from lego.com (the input Claude reads);
  - the LDraw model from the Official Model Repository (answer key for connections);
  - the official inventory from Rebrickable's public database (answer key for parts),
    and Rebrickable's element -> part number table to map manual element IDs to LDraw parts.

Only sets with exactly one instructions PDF, 30-500 pieces and year >= 2005 are kept, spread
over themes. Downloads go to research/raw/ (git-ignored); the list of chosen sets goes to
research/data/lego_dataset.json.

Run: .venv-research/bin/python research/scrape/lego_official.py [--target 100]
"""
import argparse
import csv
import gzip
import json
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "raw"
RB = RAW / "rebrickable"
OUT = ROOT / "research" / "data" / "lego_dataset.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
PDF = re.compile(r"https://www\.lego\.com/cdn/product-assets/product\.bi\.core\.pdf/\d+\.pdf")


def omr_sets():
    cache = RAW / "lego" / "omr_sets.json"
    if cache.exists():
        return json.loads(cache.read_text())
    found, page = [], 1
    while True:
        html = requests.get(f"https://library.ldraw.org/omr/sets?page={page}", headers=UA, timeout=60).text
        nums = re.findall(r">\s*(\d{3,7}-\d)\s*<", html)
        new = [n for n in dict.fromkeys(nums) if n not in found]
        if not new:
            break
        found += new
        page += 1
        time.sleep(0.5)
    cache.write_text(json.dumps(found))
    return found


def rebrickable(name):
    with gzip.open(RB / f"{name}.csv.gz", "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def lego_pdfs(setnum):
    num = setnum.split("-")[0]
    html = requests.get(f"https://www.lego.com/en-us/service/building-instructions/{num}", headers=UA, timeout=60).text
    return list(dict.fromkeys(PDF.findall(html)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=100)
    cfg = ap.parse_args()

    omr = set(omr_sets())
    print(len(omr), "sets in the LDraw OMR")
    themes = {t["id"]: t["name"] for t in rebrickable("themes")}
    sets = {s["set_num"]: s for s in rebrickable("sets")}
    cands = [s for n, s in sets.items() if n in omr and int(s["year"]) >= 2005 and 30 <= int(s["num_parts"]) <= 500]
    # Spread over themes: round-robin by theme, smaller sets first within a theme.
    by_theme = {}
    for s in sorted(cands, key=lambda s: int(s["num_parts"])):
        by_theme.setdefault(s["theme_id"], []).append(s)
    order = []
    while any(by_theme.values()):
        for t in list(by_theme):
            if by_theme[t]:
                order.append(by_theme[t].pop(0))
    print(len(cands), "candidates (OMR ∩ Rebrickable, 2005+, 30-500 pieces) over", len(by_theme), "themes")

    inv_ids = {}
    for row in rebrickable("inventories"):
        if row["version"] == "1":
            inv_ids[row["set_num"]] = row["id"]

    chosen = []
    for s in order:
        if len(chosen) >= cfg.target:
            break
        try:
            pdfs = lego_pdfs(s["set_num"])
        except requests.RequestException:
            continue
        time.sleep(0.4)
        if len(pdfs) != 1:
            continue
        mpd = RAW / "lego" / f"{s['set_num']}.mpd"
        pdf_path = RAW / "lego_pdf" / f"{s['set_num']}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:  # a slow or failed download skips the set; files already saved are reused on a rerun
            if not mpd.exists():
                r = requests.get(f"https://library.ldraw.org/library/omr/{s['set_num']}.mpd", headers=UA, timeout=60)
                if r.status_code != 200:
                    continue
                mpd.write_text(r.text)
            if not pdf_path.exists():
                r = requests.get(pdfs[0], headers=UA, timeout=180)
                if r.status_code != 200 or len(r.content) > 20_000_000:
                    continue
                pdf_path.write_bytes(r.content)
        except requests.RequestException:
            continue
        chosen.append({"set": s["set_num"], "name": s["name"], "year": int(s["year"]), "theme": themes.get(s["theme_id"]),
                       "pieces": int(s["num_parts"]), "pdf": pdfs[0], "pdf_mb": round(pdf_path.stat().st_size / 1e6, 1),
                       "inventory_id": inv_ids.get(s["set_num"])})
        print(f"{len(chosen):3d} {s['set_num']:9s} {int(s['num_parts']):4d} pcs  {themes.get(s['theme_id'], '?')[:20]:20s} {s['name'][:40]}", flush=True)

    # Official inventories (non-spare parts) for the chosen sets.
    wanted = {c["inventory_id"]: c for c in chosen if c["inventory_id"]}
    for c in chosen:
        c["inventory"] = {}
    for row in rebrickable("inventory_parts"):
        c = wanted.get(row["inventory_id"])
        if c and row["is_spare"] == "False":
            key = f"{row['part_num']}/{row['color_id']}"
            c["inventory"][key] = c["inventory"].get(key, 0) + int(row["quantity"])
    OUT.write_text(json.dumps(chosen, indent=1))
    print("wrote", OUT, len(chosen), "sets")


if __name__ == "__main__":
    main()
