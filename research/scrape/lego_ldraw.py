"""Survey LEGO connection types from LDraw files of official sets.

Downloads models of official LEGO sets from the LDraw Official Model
Repository (OMR, community-made; allowed as an extension, RESEARCH.md R13),
reads every part they use, looks up each part's description in the LDraw
parts library, and groups parts by how they connect (studs, Technic pins,
axles, hinges, clips, ...).

MPD files go to research/raw/lego/ (git-ignored). Writes
research/data/lego_connections.json.

Run: .venv-research/bin/python research/scrape/lego_ldraw.py
"""
import collections
import json
import pathlib
import re

import zipfile

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "raw" / "lego"
OUT = ROOT / "research" / "data" / "lego_connections.json"
OMR = "https://library.ldraw.org/library/omr/{}-1.mpd"
LIBRARY_ZIP = "https://library.ldraw.org/library/updates/complete.zip"  # one download, then offline
UA = {"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"}

# A spread of themes and eras: Classic/Creator/City (studs), Technic (pins, axles).
CANDIDATES = [
    "10001", "6390", "6399", "6086", "6542", "6597", "6687", "6699", "4954", "7905", "7939",
    "8043", "8052", "8063", "8070", "8081", "8109", "8258", "8265", "8275", "8285", "8297",
    "8421", "8448", "8455", "8480", "8865", "8880", "42000", "42008", "42009", "42030",
    "31001", "31013", "31024", "31038", "4888", "5767", "5771", "5891", "6753", "6753",
    "6346", "6349", "6351", "6356", "6365", "6375", "6394", "6441", "6455", "6461", "6493",
    "1489", "1496", "6524", "6526", "6537", "6551", "6581", "6600", "6614",
]
TARGET = 30

# Description keyword -> connection family. First match wins, so order matters.
FAMILIES = [
    (r"^Sticker|Sticker\b", "sticker (adhesive)"),
    (r"Technic.*Pin|^Pin\b", "technic-pin"),
    (r"Technic.*Axle(?! Joiner)|^Axle", "technic-axle"),
    (r"Axle Joiner|Connector|Bush", "technic-connector/bush"),
    (r"Gear|Rack|Worm|Turntable|Differential", "gear/turntable (moves)"),
    (r"Technic.*(Beam|Liftarm|Brick)|Liftarm", "technic-beam (pin holes)"),
    (r"Hinge", "hinge (rotates)"),
    (r"Clip|Bar\b|Bar Holder|Lightsaber|Antenna|Flag", "clip/bar"),
    (r"Ball|Socket|Tow", "ball/socket (rotates)"),
    (r"Wheel|Tyre|Tire|Rim", "wheel/tyre"),
    (r"String|Hose|Chain|Rope|Rubber Band|Tube", "flexible"),
    (r"Minifig|Figure", "minifigure"),
    (r"Door|Window|Glass|Shutter", "door/window (often hinged)"),
    (r"Tile", "tile (no top studs)"),
    (r"Plate|Brick|Slope|Wedge|Panel|Cone|Cylinder|Round|Arch|Bracket|Baseplate|Roof", "stud (brick/plate)"),
]


def get(url):
    r = requests.get(url, headers=UA, timeout=60)
    return r.text if r.status_code == 200 else None


def model_parts(text):
    """Every part referenced by type-1 lines, excluding the file's own submodels."""
    submodels = {m.lower() for m in re.findall(r"^0 FILE (.+?)\s*$", text, re.M)}
    parts = collections.Counter()
    for line in text.splitlines():
        bits = line.split()
        if len(bits) >= 15 and bits[0] == "1":
            name = " ".join(bits[14:]).strip().lower().replace("\\", "/")
            if name not in submodels:
                parts[name] += 1
    return parts


def library_index():
    """{part filename: description} from the LDraw parts library, following
    "Moved to X" aliases. The zip is downloaded once (146 MB) to avoid
    hammering the site with one request per part (it rate-limits at ~300)."""
    path = RAW / "complete.zip"
    if not path.exists():
        with requests.get(LIBRARY_ZIP, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    index = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            low = name.lower()
            if low.startswith("ldraw/parts/") and low.endswith(".dat") and "/s/" not in low:
                with z.open(name) as f:
                    first = f.readline().decode("utf-8", "replace")
                # "~" marks sub-parts, "=" aliases, "_" physical colour variants, "|" mirror-only.
                index[low.rsplit("/", 1)[1]] = re.sub(r"^0\s+[~=_|]*", "", first).strip()
    return index


def describe(part, index, depth=0):
    desc = index.get(part, "?")
    moved = re.match(r"Moved to (\S+)", desc)
    if moved and depth < 3:
        return describe(moved.group(1).lower() + ".dat", index, depth + 1)
    return desc


def family(desc):
    for pattern, fam in FAMILIES:
        if re.search(pattern, desc, re.I):
            return fam
    return "other"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    index = library_index()
    sets, totals, fam_parts = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for num in dict.fromkeys(CANDIDATES):
        if len(sets) >= TARGET:
            break
        path = RAW / f"{num}-1.mpd"
        if not path.exists():
            text = get(OMR.format(num))
            if not text:
                continue
            path.write_text(text)
        text = path.read_text()
        title = (re.search(r"^0 (?!FILE|Name|Author|!)(.+)$", text, re.M) or [None, "?"])[1].strip()
        parts = model_parts(text)
        fams = collections.Counter()
        for part, n in parts.items():
            fam = family(describe(part, index))
            fams[fam] += n
            fam_parts[fam][describe(part, index)] += n
        totals.update(fams)
        sets.append({"set": f"{num}-1", "title": title, "pieces": sum(parts.values()), "families": fams.most_common()})
        print(f"{num}-1  {sum(parts.values()):4d} pcs  {title[:40]:40s}", fams.most_common(4))
    result = {
        "sets": sets,
        "total_pieces": sum(totals.values()),
        "families": totals.most_common(),
        "examples": {f: [d for d, _ in c.most_common(6)] for f, c in fam_parts.items()},
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print("\nTOTAL", result["total_pieces"], "pieces in", len(sets), "sets")
    for f, n in totals.most_common():
        print(f"  {n:6d}  {f:32s}", result["examples"][f][:3])


if __name__ == "__main__":
    main()
