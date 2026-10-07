"""Ground truth to score the model against.

Arduino: CircuitQuest's hand-validated Wokwi diagram for the same official
tutorial; nets computed by CircuitQuest's own checker (breadboard folded).

LEGO: an LDraw model of an official set. Parts and positions come from the
file; which plain bricks/plates/tiles sit on which is computed from geometry
(top of the lower part = bottom of the upper part, footprints overlap).
"""
import collections
import json
import pathlib
import re
import sys

from .catalogue import CQ, brick_dims

LDU_HEIGHT = {"brick": 24, "plate": 8, "tile": 8, "slope": 24, "slope-low": 16}
NOTHING_ON_TOP = {"tile", "slope", "slope-low"}  # no studs to clutch (a slope's few top studs are ignored)


def extended_dims(description):
    """v5 scoring: also slopes and round/special/modified bricks, plates and tiles, by their footprint
    ('Slope 45 2 x 2', 'Plate Round 1 x 1 with Solid Stud', 'Brick Special 1 x 2 with Handle')."""
    import re as _re
    d = _re.sub(r"\s+", " ", description).strip()
    m = _re.match(r"^(Brick|Plate|Tile|Slope)\b.*?(\d+) x (\d+)( x (\d+(/\d+)?))?", d, _re.I)
    if not m:
        return None
    kind = m.group(1).lower()
    if kind == "slope" and m.group(5) == "2/3":
        kind = "slope-low"
    return kind, int(m.group(2)), int(m.group(3))


# --- Arduino ---------------------------------------------------------------------
def arduino_truth(lesson_id):
    sys.path.insert(0, str(CQ))
    from core import checker  # CircuitQuest
    from core.library import load_library

    lib = load_library()
    diagram = json.loads((CQ / "lessons" / lesson_id / "diagram.json").read_text())
    alias = checker.board_alias_map(diagram["parts"], lib)
    connectors = checker.connector_ids(diagram["parts"], lib)
    raw = checker.build_nets([[c[0], c[1]] for c in diagram["connections"]], alias)
    nets = [frozenset(p for p in n if p.split(":")[0] not in connectors) for n in raw]
    parts = collections.Counter(p["type"] for p in diagram["parts"])
    return {"nets": [n for n in nets if len(n) >= 2],
            "types": {p["id"]: p["type"] for p in diagram["parts"]},
            "inventory": dict(parts)}


# --- LEGO --------------------------------------------------------------------------
def _mat(vals):
    return [vals[0:3], vals[3:6], vals[6:9]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


PART_ORG = re.compile(r"(?m)^0 !LDRAW_ORG\s+(Unofficial_)?(Part|Subpart|Primitive|8_Primitive|48_Primitive|Shortcut)\b",
                      re.I)


def ldraw_key(name):
    """One spelling for a file name: references write `s\\x.dat` or `s/x.dat`, in any case."""
    return name.strip().lower().replace("\\", "/")


def mpd_sections(text):
    """{name: lines} of a model file, and the names that are PARTS embedded in it (custom or unofficial pieces,
    marked Part/Subpart/Primitive/Shortcut) rather than sub-models. A part is one piece: never expanded."""
    files, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^0 FILE (.+?)\s*$", line)
        if m:
            current = ldraw_key(m.group(1))
            files[current] = []
        elif current is not None:
            files[current].append(line)
    if not files:  # a single-model .ldr file without "0 FILE" sections
        files["main"] = text.splitlines()
    parts = {n for n, lines in files.items() if PART_ORG.search("\n".join(lines[:15]))}
    return files, parts


def embedded_parts(text):
    """{name: file text} of the parts a model file carries itself (the library does not have them)."""
    files, parts = mpd_sections(text)
    return {n: "\n".join(files[n]) for n in parts}


def flatten_mpd(text, index=None):
    """[(part_file, colour, pos, rot)] for every real piece, sub-models expanded. Parts embedded in the file are
    pieces too (until v7 they were expanded into their primitives: discs, edges, cylinders counted as pieces)."""
    files, embedded = mpd_sections(text)
    main = next(iter(files))
    out = []

    def walk(name, pos, rot, depth=0):
        for line in files[name]:
            b = line.split()
            if len(b) < 15 or b[0] != "1":
                continue
            ref = ldraw_key(" ".join(b[14:]))
            p = [float(x) for x in b[2:5]]
            r = _mat([float(x) for x in b[5:14]])
            abs_pos = [pos[i] + _apply(rot, p)[i] for i in range(3)]
            abs_rot = _mul(rot, r)
            if ref in files and ref not in embedded and depth < 10:
                walk(ref, abs_pos, abs_rot, depth + 1)
            else:
                out.append((ref, b[1], abs_pos, abs_rot))

    walk(main, [0.0, 0.0, 0.0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    return out


def _footprint(dims, pos, rot):
    """Axis-aligned x/z extent of a brick footprint (only 90° rotations about Y)."""
    _, w, l = dims
    hx, hz = w * 10.0, l * 10.0
    corners = [_apply(rot, [sx * hx, 0, sz * hz]) for sx in (-1, 1) for sz in (-1, 1)]
    xs = [pos[0] + c[0] for c in corners]
    zs = [pos[2] + c[2] for c in corners]
    return min(xs), max(xs), min(zs), max(zs)


def lego_truth(mpd_text, index, describe, extended=False):
    parts = flatten_mpd(mpd_text, index)
    nodes = []
    for i, (ref, colour, pos, rot) in enumerate(parts, 1):
        desc = describe(ref, index)
        nodes.append({"id": f"b{i}", "part": ref, "desc": desc, "colour": colour,
                      "pos": [round(x, 1) for x in pos], "rot": [[round(x, 3) for x in r] for r in rot],
                      "dims": brick_dims(desc) or (extended_dims(desc) if extended else None)})
    contacts = set()
    boxy = [n for n in nodes if n["dims"] and abs(n["rot"][1][1]) > 0.99]
    for a in boxy:
        ha = LDU_HEIGHT[a["dims"][0]]
        fa = _footprint(a["dims"], a["pos"], a["rot"])
        for b in boxy:
            if a is b or a["dims"][0] in NOTHING_ON_TOP:
                continue  # nothing clutches on top of a tile or a slope
            hb = LDU_HEIGHT[b["dims"][0]]
            # LDraw: -Y is up; a part's origin is its top surface, it extends +Y by its height.
            if abs((b["pos"][1] + hb) - a["pos"][1]) > 0.5:
                continue
            fb = _footprint(b["dims"], b["pos"], b["rot"])
            ox = min(fa[1], fb[1]) - max(fa[0], fb[0])
            oz = min(fa[3], fb[3]) - max(fa[2], fb[2])
            if ox >= 19 and oz >= 19:  # at least one 20-LDU stud cell overlaps
                contacts.add(frozenset([a["id"], b["id"]]))
    return {"nodes": nodes, "contacts": contacts, "scoreable": {n["id"] for n in boxy},
            "inventory": dict(collections.Counter(n["part"] for n in nodes))}


# --- LEGO from the official PDF ----------------------------------------------------
def part_numbers():
    """Every Rebrickable part number (design), to recognise `lego-<design>` types."""
    import csv
    import gzip
    path = pathlib.Path(__file__).resolve().parents[1] / "research" / "raw" / "rebrickable" / "parts.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return {r["part_num"] for r in csv.DictReader(f)}


def element_map():
    """Rebrickable element ID -> (part number, colour id), from its public database dump."""
    import csv
    import gzip
    path = pathlib.Path(__file__).resolve().parents[1] / "research" / "raw" / "rebrickable" / "elements.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return {r["element_id"]: (r["part_num"], r["color_id"]) for r in csv.DictReader(f)}


def lego_pdf_truth(entry, mpd_text, index, describe, extended=False):
    """Answer key for one official manual: Rebrickable inventory (parts) and LDraw geometry
    (which plain brick/plate/tile designs clutch which), compared at design level because the
    model sees pictures, not LDraw part ids."""
    geo = lego_truth(mpd_text, index, describe, extended)
    design = {n["id"]: n["part"][:-4] if n["part"].endswith(".dat") else n["part"] for n in geo["nodes"]}
    pairs = collections.Counter(tuple(sorted(design[x] for x in c)) for c in geo["contacts"])
    return {"inventory": entry["inventory"], "pieces": sum(entry["inventory"].values()),
            "pairs": pairs, "scoreable_designs": {design[i] for i in geo["scoreable"]},
            "ldraw_pieces": len(geo["nodes"])}
