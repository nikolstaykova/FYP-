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
import functools
import re
import sys

from catalogue import CQ, brick_dims

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


LSYNTH = re.compile(r"(?:^|/| - )ls(\d+)\.dat$")
LSYNTH_KIND = {"40": "32580", "41": "32580", "50": "75c24", "51": "75c24"}  # segment type -> the piece it draws
LSYNTH_WORDS = [("flexible axle", "32580"), ("flex-system", "75c24"), ("flex system", "75c24"),
                ("ribbon cable", "lsynth-ribbon-cable"), ("hose flexible", "lsynth-flexible-hose"),
                ("ribbed hose", "lsynth-ribbed-hose"), ("pneumatic", "lsynth-pneumatic-tube"),
                ("rubber band", "lsynth-rubber-band"), ("string", "lsynth-string"), ("cable", "lsynth-cable"),
                ("chain", "lsynth-chain"), ("tread", "lsynth-tread")]
LSYNTH_DESIGN = {}  # bendable piece (file name) -> design number of the piece LSynth drew as segments


def _primitives():
    """Names of the LDraw library's primitives (the p/ folder: cylinders, discs, studs, edges)."""
    if not _PRIMS:
        import ldraw_geometry as geo
        geo._zip()
        _PRIMS.update(k for k, v in geo._NAMES.items() if isinstance(v, str) and v.lower().startswith("ldraw/p/"))
    return _PRIMS


_PRIMS = set()


def _refs(lines):
    return [ldraw_key(" ".join(b[14:])) for b in (l.split() for l in lines) if b[:1] == ["1"] and len(b) >= 15]


@functools.lru_cache(maxsize=None)
def library_title(ref):
    """The first line's title of a library part ('~Hose Flexible Segment Center Section'), '' if not in the library."""
    import ldraw_geometry as geo
    t = geo.text_of(ref if ref.endswith(".dat") else ref + ".dat")
    return (t.splitlines()[0][2:].strip() if t else "")


def resolve(ref):
    """A library part under its current name: '~Moved to X' and '=X' alias files point to the real part."""
    for _ in range(5):
        title = library_title(ref)
        m = re.match(r"^~Moved to (\S+)", title)
        if m:
            ref = ldraw_key(m.group(1)) + ".dat"
            continue
        if title.startswith("="):
            import ldraw_geometry as geo
            refs = _refs((geo.text_of(ref) or "").splitlines())
            if len(refs) == 1:
                ref = refs[0]
                continue
        break
    return ref


def is_segment(ref):
    """A piece some tool chains to draw ONE bendable piece: LSynth segments (ls40 ...), hose, tube and ribbon-cable
    segments of the library ('~... Segment', '~... End Section')."""
    if LSYNTH.search(ref):
        return True
    title = library_title(resolve(ref)).lower()
    return (title.startswith("~") and ("segment" in title or "end section" in title or "tube end" in title)) \
        or bool(re.search(r"cable\s+\d+\s*ldu", title))  # fixed-length cable bits that draw one cable


def is_primitive(ref):
    """A drawing primitive of the library (cylinder, disc, axle-hole outline ...), never a LEGO piece."""
    return ref in _primitives() or ref.rsplit("/", 1)[-1] in _primitives()


def _lsynth_design(files, refs):
    """What a run of LSynth segments draws: from the segment parts' own descriptions (the library does not carry
    LSynth parts; model files do), else from the segment number."""
    for r in refs:
        head = (" ".join(files.get(r, [""])[:2]) + " " + library_title(resolve(r))).lower()
        for word, design in LSYNTH_WORDS:
            if word in head:
                return design
    kinds = sorted({LSYNTH.search(r).group(1) for r in refs if LSYNTH.search(r)})
    return LSYNTH_KIND.get(kinds[0], f"lsynth-{kinds[0]}") if kinds else "segmented-" + resolve(refs[0]).rsplit(".", 1)[0]


def mpd_sections(text):
    """{name: lines} of a model file, and the names that are PARTS (one piece each, never expanded) rather than
    sub-models of pieces:
      - files marked Part/Subpart/Primitive/Shortcut (custom or unofficial pieces the file carries)
      - files that draw shapes themselves (lines, triangles, quads) or refer only to library primitives and other
        such files: unmarked custom pieces (until v9 their cylinders and edges were counted as pieces)
      - bendable pieces LSynth drew as many short segments (ls40, ls41, ls50 ...): a file made only of segments, or
        each run of consecutive segments inside a file, is ONE piece (a flexible axle, a hose, a cable)"""
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
    # LSynth: a run of consecutive segments becomes one virtual piece file
    for n in list(files):
        lines, out, run = files[n], [], []

        def close():
            if not run:
                return
            refs = _refs(run)
            if len(refs) == len(_refs(lines)):
                parts.add(n)  # the whole file is the bendable piece
                LSYNTH_DESIGN[n] = _lsynth_design(files, refs)
                out.extend(run)
            else:
                v = f"{n}#lsynth{len(LSYNTH_DESIGN) + 1}"
                files[v] = list(run)
                parts.add(v)
                LSYNTH_DESIGN[v] = _lsynth_design(files, refs)
                out.append(f"1 {run[0].split()[1]} 0 0 0 1 0 0 0 1 0 0 0 1 {v}")
            run.clear()
        prim_run = []

        def close_prims():
            # primitives drawn straight into a model file, among real parts: one custom piece per run
            if prim_run and any(l.split()[:1] == ["1"] for l in prim_run):
                v = f"{n}#custom{len(files)}"
                files[v] = list(prim_run)
                parts.add(v)
                out.append(f"1 16 0 0 0 1 0 0 0 1 0 0 0 1 {v}")
            else:
                out.extend(prim_run)
            prim_run.clear()
        mixed = any(l.split()[:1] == ["1"] and len(l.split()) >= 15 and not is_primitive(ldraw_key(" ".join(l.split()[14:])))
                    and not LSYNTH.search(ldraw_key(" ".join(l.split()[14:]))) for l in lines)
        for line in lines:
            b = line.split()
            ref = ldraw_key(" ".join(b[14:])) if b[:1] == ["1"] and len(b) >= 15 else None
            if ref and is_segment(ref):
                close_prims()
                run.append(line)
            elif mixed and n not in parts and ((ref and is_primitive(ref)) or b[:1] in (["2"], ["3"], ["4"], ["5"])):
                close()
                prim_run.append(line)
            elif b[:1] == ["1"]:
                close()
                close_prims()
                out.append(line)
            else:
                (prim_run if prim_run else out).append(line) if b[:1] != ["0"] else out.append(line)
        close()
        close_prims()
        files[n] = out
    # unmarked custom pieces: draw shapes themselves, or refer only to primitives and to such files
    prims = _primitives()
    draws = lambda lines: any(l.split()[:1] in (["2"], ["3"], ["4"], ["5"]) for l in lines)
    # draws shapes and refers to nothing but primitives (a real sub-model refers to library parts)
    shapes = {n for n, lines in files.items() if draws(lines) and all(r in prims for r in _refs(lines))}
    changed = True
    while changed:
        changed = False
        for n, lines in files.items():
            if n in shapes or n in parts:
                continue
            refs = _refs(lines)
            if refs and all(r in prims or r in shapes for r in refs) and (draws(lines) or any(r in shapes for r in refs)
                                                                        or all(r in prims for r in refs)):
                shapes.add(n)
                changed = True
    main = next(iter(files))
    parts |= shapes - {main}
    return files, parts


def embedded_parts(text):
    """{name: file text} of the parts a model file carries itself (the library does not have them)."""
    files, parts = mpd_sections(text)
    return {n: "\n".join(files[n]) for n in parts}


def roots(text):
    """The top-level builds of a model file: sub-models no other file refers to (the main model first)."""
    files, parts = mpd_sections(text)
    used = {r for n, lines in files.items() for r in _refs(lines)}
    main = next(iter(files))
    return [main] + [n for n in files if n != main and n not in used and n not in parts and _refs(files[n])]


def flatten_mpd(text, index=None, root=None):
    """[(part_file, colour, pos, rot)] for every real piece, sub-models expanded. Parts embedded in the file are
    pieces too (until v7 they were expanded into their primitives: discs, edges, cylinders counted as pieces).
    root: the build to flatten (default the file's main model; see roots())."""
    files, embedded = mpd_sections(text)
    main = root if root in files else next(iter(files))
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
    path = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "rebrickable" / "parts.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return {r["part_num"] for r in csv.DictReader(f)}


def element_map():
    """Rebrickable element ID -> (part number, colour id), from its public database dump."""
    import csv
    import gzip
    path = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "rebrickable" / "elements.csv.gz"
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
