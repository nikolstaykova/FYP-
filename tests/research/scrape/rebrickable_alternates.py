"""Alternate builds of LEGO sets (3-in-1 B and C models, fan MOCs) from Rebrickable, and whether a 3D file exists.

A 3-in-1 booklet holds several builds, but the LDraw repository models only the main one. Rebrickable lists each
set's alternate builds (GET /api/v3/lego/sets/<set>/alternates/), the official LEGO ones among them, and many come
with a digital file (LDraw .ldr/.mpd, Stud.io .io, LDD .lxf) on the build's page.

  .venv-research/bin/python research/scrape/rebrickable_alternates.py 31040-1 [more sets]  (or --all-usable)
Needs REBRICKABLE_API_KEY in the environment or .env. Writes research/data/rebrickable_alternates.json.
"""
import json
import os
import pathlib
import re
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "data" / "rebrickable_alternates.json"
API = "https://rebrickable.com/api/v3/lego"


def key():
    k = os.environ.get("REBRICKABLE_API_KEY")
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("REBRICKABLE_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("'\"")
    if not k:
        sys.exit("REBRICKABLE_API_KEY is not set (add it to .env)")
    return k


def get(url, k):
    for attempt in range(3):
        r = requests.get(url, headers={"Authorization": f"key {k}", "Accept": "application/json"}, timeout=30)
        if r.status_code == 429:  # rate limit: about 1 request a second
            time.sleep(2 + attempt * 2)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def alternates(set_num, k):
    out, url = [], f"{API}/sets/{set_num}/alternates/?page_size=100"
    while url:
        data = get(url, k)
        out += data.get("results", [])
        url = data.get("next")
        time.sleep(1.1)
    return out


def file_check(moc_url):
    """What the build's public page says about digital files (no login): which formats are mentioned."""
    try:
        html = requests.get(moc_url, headers={"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"}, timeout=30).text
    except requests.RequestException as e:
        return {"error": str(e)[:80]}
    formats = sorted({f for f in ("ldr", "mpd", "io", "lxf", "lxfml") if re.search(rf"\.{f}\b", html, re.I)})
    return {"formats_mentioned": formats, "free": bool(re.search(r"\bfree\b", html, re.I)),
            "login_needed": bool(re.search(r"log ?in to download|sign in to download", html, re.I))}


def main(argv):
    k = key()
    sets = argv
    if "--all-usable" in argv:
        audit = json.loads((ROOT / "research" / "data" / "omr_audit.json").read_text())
        sets = [r["set"] for r in audit if r["class"].startswith("USABLE")]
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for s in sets:
        if s in results:
            continue
        alts = alternates(s, k)
        rows = []
        for a in alts:
            official = (a.get("designer_name") or "").strip().upper() == "LEGO"
            row = {"moc": a.get("set_num"), "name": a.get("name"), "pieces": a.get("num_parts"),
                   "designer": a.get("designer_name"), "official": official, "url": a.get("moc_url")}
            if official and a.get("moc_url"):
                row.update(file_check(a["moc_url"]))
                time.sleep(1.1)
            rows.append(row)
        results[s] = rows
        off = [r for r in rows if r["official"]]
        print(f"{s:9} {len(rows):3} alternate builds, {len(off)} official: "
              + "; ".join(f"{r['moc']} {r['name'][:30]} files {r.get('formats_mentioned')}" for r in off), flush=True)
        OUT.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
