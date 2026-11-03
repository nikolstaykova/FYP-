"""LEGO parts and models as LDraw draws them: each part's real shape, its studs and pins, how pieces join.

What it is   everything the project knows about LEGO pieces from the LDraw library, for every LEGO route (not
             only the 3D one). Parts: each part's real shape and box, its studs, anti-studs, pins and holes (grid,
             features), how two pieces join, as LEGO CAD tools find it (connections), which pieces touch, renamed
             and alias part numbers followed to the current one (resolve, library_title), drawing a part (mesh,
             view, colour). Models: a model file opened into its pieces (flatten_mpd), which build in a file is the
             set's (best_root), LDraw numbers against the set's inventory (reconcile, design, canon), the model stood
             upright, the anchor frame each piece is measured from (studs and plates from the first big piece) and
             the builds a booklet's steps belong to (booklet_builds). The rotation maths for both.
Used for     the 3D route: a set's pieces, joins and the checks that each step can be built. The booklet route:
             each part's shape, to measure how much new part a step shows. The parts: a LEGO card's ports and stud
             grid, its size check and the picture its metadata is drafted from. The lesson store: a 3D lesson's
             physical graph.
Where        lego_3d/ (lesson, assembly), lego_booklet/ (booklet_size, step_diff),
             parts/ (cards, ingest, part_metadata, lego/lego_ids), lesson_store.py. Its data: the LDraw library
             (data/sources/lego/complete.zip) and the sets' models (data/sources/lego/<set>.mpd).
"""

import collections
import csv
import functools
import gzip
import math
import pathlib
import re
import zipfile


# ---- reading LDraw files: pieces, renamed parts, rotations ---------------------------------------------------
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
        _zip()
        _PRIMS.update(k for k, v in _NAMES.items() if isinstance(v, str) and v.lower().startswith("ldraw/p/"))
    return _PRIMS


_PRIMS = set()


def _refs(lines):
    return [ldraw_key(" ".join(b[14:])) for b in (l.split() for l in lines) if b[:1] == ["1"] and len(b) >= 15]


@functools.lru_cache(maxsize=None)
def library_title(ref):
    """The first line's title of a library part ('~Hose Flexible Segment Center Section'), '' if not in the library."""
    t = text_of(ref if ref.endswith(".dat") else ref + ".dat")
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
            refs = _refs((text_of(ref) or "").splitlines())
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


# ---- piece shapes: boxes, what touches what ------------------------------------------------------------------
_ZIP = pathlib.Path(__file__).resolve().parents[2] / "data" / "sources" / "lego" / "complete.zip"


_NAMES = {}


def _zip():
    if not _NAMES:
        z = zipfile.ZipFile(_ZIP)
        for name in z.namelist():
            low = name.lower()
            if low.endswith(".dat") and low.startswith(("ldraw/parts/", "ldraw/p/")):
                key = low.split("ldraw/parts/", 1)[-1] if low.startswith("ldraw/parts/") else low.split("ldraw/p/", 1)[-1]
                _NAMES.setdefault(key, name)
        _NAMES["__zip__"] = z
    return _NAMES["__zip__"]


TOP_STUD = re.compile(r"^(?:\d+-\d+)?stud(?!3|4|12)", re.I)  # studs on top; stud3/stud4/stud12 are tubes underneath


EMBEDDED = {}  # parts a model file carries itself (embedded_parts), by name; looked up before the library


def register(text):
    """Make the parts embedded in a model file readable here (call before box/features on that model)."""
    EMBEDDED.update(embedded_parts(text))


def text_of(part):
    """A part file's text: embedded in a model, else from the library zip; None if unknown."""
    key = ldraw_key(part)
    if key in EMBEDDED:
        return EMBEDDED[key]
    z = _zip()
    name = _NAMES.get(key)
    return z.read(name).decode("utf-8", "replace") if name else None


@functools.lru_cache(maxsize=None)
def box(part):
    """Local bounding box (minx, miny, minz, maxx, maxy, maxz) of a library file, top studs left out; None if unknown."""
    text = text_of(part)
    if text is None:
        return None
    pts = []
    for line in text.splitlines():
        b = line.split()
        if not b:
            continue
        if b[0] in ("2", "3", "4", "5") and len(b) >= 8:
            nums = [float(x) for x in b[2:2 + 3 * int(b[0] if b[0] != "5" else 2)]]
            pts += [nums[i:i + 3] for i in range(0, len(nums), 3)]
        elif b[0] == "1" and len(b) >= 15:
            ref = " ".join(b[14:]).lower().replace("\\", "/")
            if TOP_STUD.match(ref.rsplit("/", 1)[-1]):
                continue
            sub = box(ref)
            if sub is None:
                continue
            pos = [float(x) for x in b[2:5]]
            rot = _mat([float(x) for x in b[5:14]])
            pts += [[pos[i] + _apply(rot, c)[i] for i in range(3)] for c in _corners(sub)]
    if not pts:
        return None
    return tuple(min(p[i] for p in pts) for i in range(3)) + tuple(max(p[i] for p in pts) for i in range(3))


def _corners(b):
    return [[x, y, z] for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]


def world_box(part, pos, rot):
    b = box(part)
    if b is None:
        return None
    pts = [[pos[i] + _apply(rot, c)[i] for i in range(3)] for c in _corners(b)]
    return tuple(min(p[i] for p in pts) for i in range(3)) + tuple(max(p[i] for p in pts) for i in range(3))


def touching(placed):
    """{frozenset(a, b): edge type} for every pair of pieces that touch:
      joined (rest)   one rests on the other (bottom on top, at least half a stud of overlap)
      joined (insert) their boxes overlap by more than 2 LDU in all three directions (a pin in a hole, an axle
                      through a wheel; also non-box shapes that interlock, so some of these only touch)
                      (a pin in a hole, an axle through a wheel, a piece clipped inside another)
      contact         side by side: faces touching, overlapping at least 4 LDU along both other directions
    LDraw: -Y is up, so a piece's top is its min Y and its bottom its max Y."""
    boxes = [(nid, world_box(part, pos, rot)) for nid, part, pos, rot in placed]
    boxes = [(nid, b) for nid, b in boxes if b]
    found = {}
    over = lambda a, b, i: min(a[i + 3], b[i + 3]) - max(a[i], b[i])
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            ox, oy, oz = over(ba, bb, 0), over(ba, bb, 1), over(ba, bb, 2)
            key = frozenset((a, b))
            stacked = any(abs(up[4] - lo[1]) <= 1.0 for lo, up in ((ba, bb), (bb, ba)))
            if stacked and ox >= 10 and oz >= 10:
                found[key] = "rest"  # touching from above; not necessarily clutching (a slope over a tile)
            elif ox > 2 and oy > 2 and oz > 2:
                found[key] = "insert"  # boxes overlap: a pin in a hole, an axle through a wheel (or shapes interlocking)
            elif (abs(ox) <= 1 and oy >= 4 and oz >= 4) or (abs(oz) <= 1 and oy >= 4 and ox >= 4):
                found[key] = "contact"
    return found


# ---- joins: studs, anti-studs, pins and holes ----------------------------------------------------------------
STUD = re.compile(r"^(?:\d+-\d+)?stud(?!3|4|12)[\w-]*\.dat$")


HOLE = re.compile(r"^(peghole|connhol|beamhol|npeghol|axlehol|axl\dho)[\w-]*\.dat$")


PIN = re.compile(r"^(?:(?:connect|confric)(?:collar|rib)?|axle)\d*[a-z]?\.dat$")  # incl. newer pins drawn with collars and friction ribs


def _kind(ref):
    name = ref.rsplit("/", 1)[-1]
    if STUD.match(name):
        return "stud"
    if HOLE.match(name):
        return "hole"
    if PIN.match(name):
        return "pin"
    return None


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


WITH_AXLE = re.compile(r"\bwith (\d+(\.\d+)?L? )?(axle|pin)\b", re.I)


AXLE = re.compile(r"^Technic Axle(?! and Pin Connector| Joiner| Connector)\b", re.I)


def is_axle(part):
    return bool(AXLE.match(library_title(resolve(part)) or ""))


@functools.lru_cache(maxsize=None)
def features(part):
    """Connection points of a part, in its own coordinates: ((kind, point, axis), ...). An axle's body is drawn with the
    axle-hole primitives (axlehol8 ...): on an axle they are its pin, not holes."""
    out = _features(part)
    if is_axle(part):
        out = tuple(("pin" if k == "hole" else k, p, a) for k, p, a in out)
    return out


@functools.lru_cache(maxsize=None)
def _features(part):
    """Connection points of a library file, in its own coordinates: ((kind, point, axis), ...).
    A primitive's axis is its local -Y (studs point that way; holes and pins run along Y)."""
    text = text_of(part)
    if text is None:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if len(b) < 15 or b[0] != "1":
            continue
        ref = " ".join(b[14:]).lower().replace("\\", "/")
        pos = [float(x) for x in b[2:5]]
        rot = _mat([float(x) for x in b[5:14]])
        kind = _kind(ref)
        if kind:
            out.append((kind, tuple(pos), tuple(_norm(_apply(rot, [0.0, -1.0, 0.0])))))
            continue
        for k, p, a in _features(ref):
            out.append((k, tuple(pos[i] + _apply(rot, list(p))[i] for i in range(3)),
                        tuple(_norm(_apply(rot, list(a))))))
    return tuple(out)


def _world(placed):
    """[(id, part, pos, rot)] -> {id: [(kind, point, axis)]} in model coordinates."""
    out = {}
    for nid, part, pos, rot in placed:
        out[nid] = [(k, [pos[i] + _apply(rot, list(p))[i] for i in range(3)], _norm(_apply(rot, list(a))))
                    for k, p, a in features(part)]
    return out


def _inside(pt, b, tol=0.5):
    return all(b[i] - tol <= pt[i] <= b[i + 3] + tol for i in range(3))


def _local(pt, pos, rot):
    """A model point in a placed piece's own coordinates (rotation matrices are orthonormal: inverse = transpose)."""
    d = [pt[i] - pos[i] for i in range(3)]
    return [sum(rot[r][c] * d[r] for r in range(3)) for c in range(3)]


def receives(stud_point, stud_axis, part, pos, rot, tol=1.5, by_studs=False):
    """True if a stud based at `stud_point`, pointing along `stud_axis`, goes into one of `part`'s receptacle cells:
    in the part's own coordinates the stud base is on its bottom face (local +Y side, LDraw down) and on its
    underside grid (one cell every 20 LDU, 10 LDU in from the edges), pointing up into it."""
    b = box(part)
    if b is None:
        return False
    local = _local(stud_point, pos, rot)
    axis = [sum(rot[r][c] * stud_axis[r] for r in range(3)) for c in range(3)]
    if axis[1] > -0.95 or abs(local[1] - b[4]) > tol:  # must point up (-Y) into the part's bottom face
        return False
    tops = [q for k, q, a in features(part) if k == "stud" and a[1] < -0.95] if by_studs else []
    if tops:  # its cells sit under its own top studs: the box would put them wrong on a part with a clip, a handle
        # or another bit sticking out (Plate 1 x 1 with Clip Light, Plate 1 x 2 with Handles)
        xs, zs = sorted({round(q[0]) for q in tops}), sorted({round(q[2]) for q in tops})
        step = lambda v: min((y - x for x, y in zip(v, v[1:]) if y - x > 1), default=20)
        on = lambda v, x: v[0] - 10 - tol <= x <= v[-1] + 10 + tol and min(
            abs((x - v[0]) % step(v)), step(v) - abs((x - v[0]) % step(v))) <= tol
        if on(xs, local[0]) and on(zs, local[2]):
            return True
    for i in (0, 2):
        if not (b[i] + 10 - tol <= local[i] <= b[i + 3] - 10 + tol):
            return False
        off = (local[i] - (b[i] + 10)) % 20
        if min(off, 20 - off) > tol:
            return False
    return True


def _solid(stud_point, part, pos, rot, tol=1.5):
    """True if the part has material over this stud's cell: a top stud right above it (corner bricks and plates,
    round and wedge pieces have empty corners inside their box). A part with no top studs (a tile) counts as solid."""
    local = _local(stud_point, pos, rot)
    tops = [p for k, p, a in features(part) if k == "stud" and a[1] < -0.95]
    return not tops or any(abs(p[0] - local[0]) <= tol and abs(p[2] - local[2]) <= tol for p in tops)


def _holders(a, p, ax, boxes, where):
    """The pieces a stud of `a` goes into. Usually one; when the boxes of several pieces take it (one of them only
    looks solid there), the pieces with material over the stud's cell are kept."""
    inner = [p[i] + 2.0 * ax[i] for i in range(3)]  # 2 LDU up the stud: inside whatever holds it
    near = [b for b, bb in boxes.items() if b != a and bb and _inside(inner, bb, 1.0)]
    found = [b for b in near if receives(p, ax, *where[b])]
    if not found:  # cells under the part's own top studs: a part with a clip or handle sticking out, whose box puts
        found = [b for b in near if receives(p, ax, *where[b], by_studs=True)]  # its cells wrong (only if none else)
    if not found:  # a part whose sockets are not at the bottom of its outline (an arch, a curved or inverted piece):
        # a top stud of it right above this stud, and the stud's base inside its body, below its top plate
        def under_top(b):
            bb = box(where[b][0])
            local = _local(p, where[b][1], where[b][2])
            axis = [sum(where[b][2][r][c] * ax[r] for r in range(3)) for c in range(3)]
            tops = [q for k, q, a2 in features(where[b][0]) if k == "stud" and a2[1] < -0.95]
            return bool(bb and tops and axis[1] <= -0.95 and bb[1] + 8 - 1.5 <= local[1] <= bb[4] + 1.5 and any(
                abs(q[0] - local[0]) <= 1.5 and abs(q[2] - local[2]) <= 1.5 for q in tops))
        hits = [b for b in near if under_top(b)]
        found = hits if len(hits) == 1 else found
    if not found:  # a round part's centre socket (a 2 x 2 round tile or plate on a single stud: its corners are not
        # where the stud is)
        def centre(b):
            bb = box(where[b][0])
            if not bb or not re.search(r"\bround\b|\bdish\b", library_title(resolve(where[b][0])) or "", re.I):
                return False
            local = _local(p, where[b][1], where[b][2])
            axis = [sum(where[b][2][r][c] * ax[r] for r in range(3)) for c in range(3)]
            return axis[1] <= -0.95 and abs(local[1] - bb[4]) <= 1.5 and all(
                abs(local[i] - (bb[i] + bb[i + 3]) / 2) <= 1.5 for i in (0, 2))
        hits = [b for b in near if centre(b)]
        found = hits if len(hits) == 1 else found
    # a part "with Stud Hole" the stud passes through on its way into the piece above: clamped, so held too
    for b in near:
        if b not in found and re.search(r"stud hole", library_title(resolve(where[b][0])) or "", re.I):
            bb = box(where[b][0])
            local = _local(p, where[b][1], where[b][2])
            if bb and abs(local[1] - bb[4]) <= 1.5 and all(bb[i] - 1.5 <= local[i] <= bb[i + 3] + 1.5 for i in (0, 2)):
                found = found + [b]
    if not found and len(near) == 1:  # one piece only over the stud, its underside right at the stud's base: a
        b = near[0]                   # bracket or other odd shape whose cells neither grid finds
        bb = box(where[b][0])
        local = _local(p, where[b][1], where[b][2])
        axis = [sum(where[b][2][r][c] * ax[r] for r in range(3)) for c in range(3)]
        odd = bb and any(min((bb[i + 3] - bb[i]) % 20, 20 - (bb[i + 3] - bb[i]) % 20) > 2 for i in (0, 2))
        if odd and axis[1] <= -0.95 and abs(local[1] - bb[4]) <= 1.5:  # only where no grid can be trusted: a
            found = [b]                                                  # regular brick off the grid stays unjoined
    if len(found) > 1:
        found = [b for b in found if _solid(p, *where[b])] or found
    return found


def _covers(tris, x, z):
    """True if a vertical line at (x, z) passes through any of the triangles (part coordinates)."""
    for t in tris:
        (ax, az), (bx, bz), (cx, cz) = ((p[0], p[2]) for p in t)
        d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(d) < 1e-9:
            continue
        u = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / d
        v = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / d
        if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
            return True
    return False


@functools.lru_cache(maxsize=None)
def grid(part):
    """The part's stud grid: ((lo_x, n_x), (lo_z, n_z), occupied cells {(ix, iz)} from 0). Cells every 20 LDU over its
    box (top studs left out); a box off the grid (handles, a clip sticking out) uses the span of its top studs; rows
    and columns at the edges with no material under their centre (the far side of a handle) are dropped. None if the
    part's shape is unknown."""
    b = box(part)
    if b is None:
        return None
    tops = [q for kind, q, a in features(part) if kind == "stud" and a[1] < -0.95]
    axes = []
    for k in (0, 2):  # x, z
        span = b[k + 3] - b[k]
        n, lo = max(1, round(span / 20)), (b[k] + b[k + 3]) / 2 - max(1, round(span / 20)) * 10
        if tops and abs(span - 20 * round(span / 20)) > 2:
            v = sorted({round(q[k]) for q in tops})
            n, lo = round((v[-1] - v[0]) / 20) + 1, v[0] - 10
        axes.append((lo, n))
    tris = [t for c, t in mesh(part) if c != "24"]
    occ = {(i, j) for i in range(axes[0][1]) for j in range(axes[1][1])
           if _covers(tris, axes[0][0] + 20 * i + 10, axes[1][0] + 20 * j + 10)}
    if not occ:
        return axes[0], axes[1], frozenset((i, j) for i in range(axes[0][1]) for j in range(axes[1][1]))
    xs, zs = [i for i, _ in occ], [j for _, j in occ]
    x0, z0 = min(xs), min(zs)
    return ((axes[0][0] + 20 * x0, max(xs) - x0 + 1), (axes[1][0] + 20 * z0, max(zs) - z0 + 1),
            frozenset((i - x0, j - z0) for i, j in occ))


def stud_ports(part):
    """The top studs of a part from its real shape, named as its card and the joins name them ('stud.2.2'): one per
    distinct up-facing stud (a shape can draw the same stud twice)."""
    pts = {tuple(round(c, 1) for c in pt) for k, pt, a in features(part) if k == "stud" and a[1] < -0.95}
    out = set()
    for pt in pts:
        c = cell(pt, part, [0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        if c:
            out.add(f"stud.{c[0]}.{c[1]}")
    return sorted(out)


def cell(point, part, pos, rot):
    """The stud-grid cell of a model point on a placed piece, named as the part cards name it (catalogue.lego_entry):
    (i, j) with i along the piece's shorter side, j along its longer one, from 1 (grid). None if the part's shape
    is unknown."""
    g = grid(part)
    if g is None:
        return None
    local = _local(point, pos, rot)
    (cx, nx), (cz, nz) = [(min(n, max(1, int((local[k] - lo) // 20) + 1)), n) for k, (lo, n) in zip((0, 2), g[:2])]
    return (cz, cx) if nz <= nx else (cx, cz)


def _cell_port(kind, point, part, pos, rot, fallback):
    c = cell(point, part, pos, rot)
    return f"{kind}.{c[0]}.{c[1]}" if c else fallback


def connections(placed):
    """{frozenset(a, b): (how, port on a, port on b)} with how = 'clutch' or 'pin'. A clutch names the grid cells
    as the part cards do: 'stud.<i>.<j>' on the piece below, 'anti.<i>.<j>' on the piece above; pins 'pin', 'hole.<n>'."""
    feats = _world(placed)
    boxes = {nid: world_box(part, pos, rot) for nid, part, pos, rot in placed}
    where = {nid: (part, pos, rot) for nid, part, pos, rot in placed}
    found = {}
    # clutch: a stud of A points into B, and B's surface is at the stud's base
    for a, fs in feats.items():
        studs = [(i, p, ax) for i, (k, p, ax) in enumerate(f for f in fs if f[0] == "stud")]
        for n, p, ax in studs:
            for b in _holders(a, p, ax, boxes, where):
                found.setdefault(frozenset((a, b)), ("clutch", a, _cell_port("stud", p, *where[a], f"stud.{n + 1}"),
                                                     b, _cell_port("anti", p, *where[b], "anti")))
    # pin: a pin/axle of A along the axis of a hole of B
    holes = [(b, i, p, ax) for b, fs in feats.items() for i, (k, p, ax) in enumerate(f for f in fs if f[0] == "hole")]
    # a part "... with Axle" / "... with Pin" (a connector with an axle end): its axle end is drawn with the hole
    # primitives, so those also count as its pins, into another piece's hole (42101: Connector with Axle 1.5 into
    # an angle connector)
    for a, (part, _, _) in where.items():
        if WITH_AXLE.search(library_title(resolve(part)) or ""):
            feats[a] = feats[a] + [("pin", p, ax) for k, p, ax in feats[a] if k == "hole"]
    long_pin = {a: is_axle(where[a][0]) for a in feats}  # an axle reaches holes all along its length
    for a, fs in feats.items():
        for k, p, ax in fs:
            if k != "pin":
                continue
            for b, n, hp, hax in holes:
                if b == a or frozenset((a, b)) in found:
                    continue
                if abs(sum(ax[i] * hax[i] for i in range(3))) < 0.95:
                    continue
                d = [hp[i] - p[i] for i in range(3)]
                along = sum(d[i] * ax[i] for i in range(3))
                perp = math.sqrt(max(0.0, sum(x * x for x in d) - along * along))
                ab = boxes.get(a)  # the hole must be on the pin itself, not beyond its end
                inside = not ab or all(ab[i] - 2 <= hp[i] <= ab[i + 3] + 2 for i in range(3))
                if perp <= 2.5 and inside and (abs(along) <= 30 or long_pin[a]):
                    found[frozenset((a, b))] = ("pin", a, "pin", b, f"hole.{n + 1}")
    return found


# ---- the set's own model, and LDraw numbers against its inventory --------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[2]


ALIASES = {"50746": "54200", "6143": "3941", "14696": "3711"}  # same piece, named differently by LDraw and Rebrickable,


# and not in its relationships (round brick 2x2; chain link)
VARIANT = re.compile(r"^(\d+)[a-z]?(?:pr\d+|p[0-9a-z]{2,4})?$")  # 3794a, 3794b, 3626bp01, 3069bpr0001 -> base number


@functools.lru_cache(maxsize=None)
def _classes():
    """Union of designs Rebrickable says are the same piece: mould variants (M), alternates (A), prints (P)."""
    import csv
    import gzip
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x
    path = ROOT / "data" / "sources" / "rebrickable" / "part_relationships.csv.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["rel_type"] in ("M", "A", "P"):
                    a, b = find(r["child_part_num"].lower()), find(r["parent_part_num"].lower())
                    if a != b:
                        parent[max(a, b)] = min(a, b)
    return {x: find(x) for x in list(parent)}


@functools.lru_cache(maxsize=None)
def _subparts():
    """Assemblies and the parts they are made of (Rebrickable's 'B' relationships, e.g. 4033c01 -> 4033, 4034)."""
    import csv
    import gzip
    out = collections.defaultdict(list)
    path = ROOT / "data" / "sources" / "rebrickable" / "part_relationships.csv.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["rel_type"] == "B":
                    out[r["parent_part_num"].lower()].append(r["child_part_num"].lower())
    return dict(out)


def _minifig(d):
    """Minifigures compared as figures, not as their parts: a model builds a torso from torso, arms and hands and
    legs from hips and two legs; Rebrickable lists a torso assembly (973c..) and a legs assembly (970c..). Returns
    the token for a torso / legs / head, '' for a part that is inside one, None for anything else."""
    if d.startswith("fabfig"):  # Rebrickable: a Fabuland figure is one piece
        return "fabuland-figure"
    if re.match(r"^u9\d{3}", d) or d.startswith("fab"):
        title = library_title(d + ".dat").lower()
        if title.startswith("figure fabuland torso"):
            return "fabuland-figure"  # the model builds the figure: its torso stands for it
        if title.startswith("figure fabuland"):
            return ""  # arms, legs, hips, head: inside the figure
    if re.match(r"^973", d):
        return "minifig-torso"
    if re.match(r"^(970|3815)", d):
        return "minifig-legs"
    if re.match(r"^(3626|28621)", d):
        return "minifig-head"
    if re.match(r"^(3818|3819|3820|981|982|983|975|976|977|3816|3817|971|972)([a-z]|$)", d):
        return ""
    return None


@functools.lru_cache(maxsize=None)
def _library_assembly(d):
    """The parts a library assembly ('... (Complete)' or a shortcut) is made of, [] if it is not one."""
    title = library_title(d + ".dat")
    text = text_of(d + ".dat") or ""
    if "(complete)" not in title.lower() and not re.search(r"!LDRAW_ORG\s+(Unofficial_)?Shortcut", text, re.I):
        return []
    kids = [r.rsplit("/", 1)[-1].rsplit(".", 1)[0] for r in _refs(text.splitlines())
            if not r.startswith(("s/", "p/")) and r.rsplit(".", 1)[0] not in _primitives() and r not in _primitives()]
    return [k for k in kids if library_title(k + ".dat")]


def designs(counter, split=True):
    """Counter of design names -> the same pieces under one name per physical piece (canon), so a parts list and a 3D
    model that name pieces differently still compare: renamed and alias library parts followed to the real part,
    assemblies split into their parts (Rebrickable's sub-parts or the library's own assembly file), minifigures
    compared as torso / legs / head."""
    out = collections.Counter()
    for d, n in counter.items():
        d = str(d).lower()
        d = resolve(d + ".dat").rsplit(".", 1)[0] if library_title(d + ".dat") else d
        fig = _minifig(d)
        if fig is not None:
            if fig:
                out[fig] += n
            continue
        kids = (_subparts().get(d) or _library_assembly(d)) if split else None
        for k in (kids or [d]):
            out[canon(k)] += n
    return out


def model_designs(text, root=None, split=False):
    """The designs of a model file's pieces (its build `root`); split=True splits its assemblies into their parts."""
    return designs(collections.Counter(design(r) for r, _, _, _ in flatten_mpd(text, root=root)), split=split)


def reconcile(set_id, text=None, root=None):
    """The set as sold and its 3D model, read the same way: the parts list with or without its minifigures (some models
    build the figures, some leave them out), and assemblies whole or split into their parts on either side (one side
    may list a flower stem or a wheel holder as one piece, the other as its parts). The reading under which the two
    agree best wins. Returns (set designs, model designs or None, {"minifigs", "split_set", "split_model"})."""
    from graph.parts.lego import inventory as pl
    models = {False: model_designs(text, root), True: model_designs(text, root, split=True)} if text else {False: None}
    best = None
    for figs in (True, False):
        parts = pl.RebrickableDump.set_parts(set_id, minifigs=figs)
        if not parts:
            return None, None, {}
        raw = collections.Counter()
        for p in parts:
            raw[p["part_num"]] += p["quantity"]
        for split_set in (True, False):
            want = designs(raw, split=split_set)
            for split_model, model in models.items():
                if model is None:
                    return want, None, {"minifigs": figs, "split_set": split_set}
                n, m = sum(want.values()), sum(model.values())
                score = (abs(m - n) <= 0.05 * n, sum((want & model).values()) - abs(n - m))  # within tolerance first
                if best is None or score > best[0]:
                    best = (score, want, model, {"minifigs": figs, "split_set": split_set, "split_model": split_model})
    return best[1], best[2], best[3]


def best_root(text, parts_counter):
    """The top-level build of a model file that matches the set best (a file can carry alternate models or extra
    builds): the root whose pieces share the most designs with the parts list."""
    builds = roots(text)
    if len(builds) <= 1:
        return None
    score = lambda r: sum((designs(collections.Counter(design(p) for p, _, _, _ in flatten_mpd(text, root=r)))
                           & parts_counter).values())
    return max(builds, key=score)


def canon(d):
    """One name per physical piece, so the parts list (Rebrickable) and the 3D model (LDraw) can be compared:
    Rebrickable's relationships, then letter variants and prints of one number, then a short alias list."""
    if not d:
        return d
    d = ALIASES.get(d.lower(), d.lower())
    d = _classes().get(d, d)
    m = VARIANT.match(d)
    d = m.group(1) if m else d
    for _ in range(3):  # the alias list again, after the relationships (3711a -> 14696 -> 3711): one fixed name
        d2 = _classes().get(ALIASES.get(d, d), ALIASES.get(d, d))
        m = VARIANT.match(d2)
        d2 = m.group(1) if m else d2
        if d2 == d:
            break
        d = d2
    return d


def design(ref):
    """LDraw file -> design number as the parts list writes it ('3001.dat' -> '3001'; a part embedded in a model
    file is named '<set> - <design>.dat')."""
    if ldraw_key(ref) in LSYNTH_DESIGN:  # a bendable piece LSynth drew as segments
        return LSYNTH_DESIGN[ldraw_key(ref)]
    name = ref.rsplit("/", 1)[-1]
    name = re.sub(r"\.dat$", "", name)
    return re.sub(r"^\d+(-\d+)? - ", "", name)


# ---- drawing a part ------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _rebrickable_rgb():
    with gzip.open(ROOT / "data" / "sources" / "rebrickable" / "colors.csv.gz", "rt") as f:
        return {r["name"].lower(): tuple(int(r["rgb"][i:i + 2], 16) for i in (0, 2, 4)) for r in csv.DictReader(f)}


@functools.lru_cache(maxsize=None)
def _ldraw_rgb():
    out = {}
    text = _zip().read("ldraw/LDConfig.ldr").decode("utf-8", "replace")
    for line in text.splitlines():
        b = line.split()
        if len(b) > 6 and b[:2] == ["0", "!COLOUR"] and "CODE" in b and "VALUE" in b:
            v = b[b.index("VALUE") + 1].lstrip("#")
            out[b[b.index("CODE") + 1]] = tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    return out


def rgb(colour):
    """An LDraw colour code ('15') or a Rebrickable colour name ('White') -> (r, g, b); grey if unknown."""
    c = str(colour)
    return _ldraw_rgb().get(c) or _rebrickable_rgb().get(c.lower()) or (160, 160, 160)


def view(az, el):
    """Rotation taking LDraw world coordinates to the view: x right, y down on the page, z away from the viewer."""
    a, e = math.radians(az), math.radians(el)
    ry = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    rx = [[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]]
    return _mul(rx, ry)


# --- real shapes (v9, second version) ------------------------------------------------------------------------
def _low(ref):
    """The library's low-detail version of a round primitive (8 segments for 16, 16 for 48), if there is one."""
    if ref.startswith("48/"):
        ref = ref[3:]
    if "/" not in ref and text_of("8/" + ref) is not None:
        return "8/" + ref
    return ref


@functools.lru_cache(maxsize=None)
def mesh_low(part, depth=0):
    """mesh() with round primitives at low detail: for the 3D viewer (smaller, faster on a phone)."""
    text = text_of(part)
    if text is None or depth > 12:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if not b:
            continue
        if b[0] == "3" and len(b) >= 11:
            v = [float(x) for x in b[2:11]]
            out.append((b[1], (tuple(v[0:3]), tuple(v[3:6]), tuple(v[6:9]))))
        elif b[0] == "4" and len(b) >= 14:
            v = [float(x) for x in b[2:14]]
            p = [tuple(v[i:i + 3]) for i in range(0, 12, 3)]
            out += [(b[1], (p[0], p[1], p[2])), (b[1], (p[0], p[2], p[3]))]
        elif b[0] == "1" and len(b) >= 15:
            ref = _low(ldraw_key(" ".join(b[14:])))
            pos = [float(x) for x in b[2:5]]
            rot = _mat([float(x) for x in b[5:14]])
            for c, tri in mesh_low(ref, depth + 1):
                cc = b[1] if c == "16" else c
                out.append((cc, tuple(tuple(pos[i] + _apply(rot, list(p))[i] for i in range(3)) for p in tri)))
    return tuple(out)


@functools.lru_cache(maxsize=None)
def mesh(part, depth=0):
    """A library part's triangles in its own coordinates: ((colour code, (p1, p2, p3)), ...); colour '16' means the
    piece's own colour. Sub-files and primitives are followed (studs, slopes, curves all included)."""
    text = text_of(part)
    if text is None or depth > 12:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if not b:
            continue
        if b[0] == "3" and len(b) >= 11:
            v = [float(x) for x in b[2:11]]
            out.append((b[1], (tuple(v[0:3]), tuple(v[3:6]), tuple(v[6:9]))))
        elif b[0] == "4" and len(b) >= 14:
            v = [float(x) for x in b[2:14]]
            p = [tuple(v[i:i + 3]) for i in range(0, 12, 3)]
            out += [(b[1], (p[0], p[1], p[2])), (b[1], (p[0], p[2], p[3]))]
        elif b[0] == "1" and len(b) >= 15:
            ref = ldraw_key(" ".join(b[14:]))
            pos = [float(x) for x in b[2:5]]
            rot = _mat([float(x) for x in b[5:14]])
            for c, tri in mesh(ref, depth + 1):
                cc = b[1] if c == "16" else c
                out.append((cc, tuple(tuple(pos[i] + _apply(rot, list(p))[i] for i in range(3)) for p in tri)))
    return tuple(out)


# ---- the anchor frame, and the booklet's steps from the model ------------------------------------------------
# --- 1. anchoring ---------------------------------------------------------------------------------------------
def anchor_of(pieces):
    """The anchor: among the first step's pieces, the one with the largest footprint."""
    first = min(p["step"] for p in pieces)

    def area(p):
        b = world_box(p["ldraw"], p["pos"], p["rot"])
        return (b[3] - b[0]) * (b[5] - b[2]) if b else 0
    return max((p for p in pieces if p["step"] == first), key=area)


def anchor_frame(anchor):
    """(rotation, origin) taking model coordinates into the anchor's frame: the anchor's turn (a quarter turn,
    whichever makes its long side run along the columns) is taken out, then its front-left-bottom corner is the
    origin."""
    turn = round((angles(anchor["rot"]) or (0, 0, 0))[0] / 90) * 90
    b0 = world_box(anchor["ldraw"], [0, 0, 0], rotation(0, 0, 0))
    if b0 and (b0[5] - b0[2]) > (b0[3] - b0[0]):  # a part drawn front-to-back: it lies along the columns at turn 90
        turn -= 90
    r = _ry(math.radians(-turn))
    b = world_box(anchor["ldraw"], _apply(r, anchor["pos"]), _mul(r, anchor["rot"]))
    return r, [b[0], b[4], b[2]]


def to_frame(p, frame):
    """A placed piece in the anchor frame: its LDraw pose and the placement an AR app reads."""
    r, o = frame
    pos = [v - o[i] for i, v in enumerate(_apply(r, p["pos"]))]
    rot = _mul(r, p["rot"])
    pl = placement_of(p["ldraw"], pos, rot) or {}
    return {**{k: round(v, 2) for k, v in pl.items()}, "pos_ldu": [round(v, 2) for v in pos],
            "rot": [[round(v, 4) for v in row] for row in rot]}


def booklet_builds(pdf_path):
    """The booklet's builds, each a list of its steps' (page, crop), in order: a new build starts where the step
    numbers start again (21 -> 1)."""
    import pymupdf
    doc = pdf_path if isinstance(pdf_path, pymupdf.Document) else pymupdf.open(pdf_path)
    words = [(i, w) for i, page in enumerate(doc) for w in page.get_text("words")
             if w[4].isdigit() and len(w[4]) <= 3 and (w[3] - w[1]) >= 18]
    if not words:
        return []
    size = collections.Counter(round(w[3] - w[1]) for _, w in words).most_common(1)[0][0]
    nums = [(i, w) for i, w in words if abs((w[3] - w[1]) - size) <= 0.15 * size]
    out = []
    for i in sorted({i for i, _ in nums}):
        rect = doc[i].rect
        here = sorted((w for j, w in nums if j == i), key=lambda w: (int(w[4]), w[1], w[0]))  # the digits ARE the steps
        for n, w in enumerate(here):
            # the next column of steps to the right ends this one; the next step below in this column ends it too
            right = min((v[0] for v in here if v[0] > w[0] + 50), default=rect.x1)
            below = min((v[1] for v in here if v[1] > w[1] + 40 and w[0] - 50 <= v[0] < right), default=rect.y1)
            out.append((int(w[4]), i + 1, (max(0, w[0] - 10), max(0, w[1] - 10), right - 5, below - 5)))
    builds, last = [], None
    for num, page, crop in out:
        if not builds or (last is not None and num < last and num <= 2):
            builds.append([])
        builds[-1].append((page, crop))
        last = num
    return builds


# ---- rotations, and standing a model upright -----------------------------------------------------------------
STUD_LDU, PLATE = 20.0, 8.0  # a stud and a plate, in LDraw units


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def rotation(turn, tilt, roll):
    """turn about the vertical, then tilt about the left-right axis, then roll about the front-back axis
    (applied to the part: roll first). Degrees."""
    r = [math.radians(x) for x in (turn, tilt, roll)]
    m = _mul(_mul(_ry(r[0]), _rx(r[1])), _rz(r[2]))
    return [[0.0 if abs(v) < 1e-9 else v for v in row] for row in m]


def angles(rot):
    """The inverse of rotation(): (turn, tilt, roll) in degrees for a rotation matrix; None for a mirrored one."""
    det = (rot[0][0] * (rot[1][1] * rot[2][2] - rot[1][2] * rot[2][1]) - rot[0][1] * (rot[1][0] * rot[2][2] - rot[1][2] * rot[2][0])
           + rot[0][2] * (rot[1][0] * rot[2][1] - rot[1][1] * rot[2][0]))
    if det < 0:
        return None
    sx = max(-1.0, min(1.0, -rot[1][2]))
    tilt = math.asin(sx)
    if abs(math.cos(tilt)) > 1e-6:
        roll = math.atan2(rot[1][0], rot[1][1])
        turn = math.atan2(rot[0][2], rot[2][2])
    else:  # top facing front or back: turn and roll are the same motion, all of it is turn
        roll = 0.0
        turn = math.atan2(-rot[2][0], rot[0][0])
    return tuple(round(math.degrees(a) % 360, 3) for a in (turn, tilt, roll))


def placement_of(part, pos, rot):
    """The placement a correct answer gives for a piece of a real model (round trip): column/row of the turned box's
    front-left corner, layer of its lowest point. Not snapped and not shifted to the model's origin."""
    a = angles(rot)
    b = world_box(part, pos, rot)
    if a is None or b is None:
        return None
    return {"column": b[0] / STUD_LDU, "row": b[2] / STUD_LDU, "layer": -b[4] / PLATE, "turn": a[0], "tilt": a[1], "roll": a[2]}


def upright(placed):
    """The rotation that stands a model file upright: the commonest 'up' of its pieces becomes up (-Y), then the
    commonest turn left over (mod a quarter turn) is taken out."""
    import collections
    ups = collections.Counter(tuple(round(v, 2) for v in _apply(rot, [0.0, -1.0, 0.0])) for _, _, _, rot in placed)
    u = ups.most_common(1)[0][0] if ups else (0.0, -1.0, 0.0)
    n = math.sqrt(sum(v * v for v in u)) or 1.0
    u = [v / n for v in u]
    # Rodrigues: rotate u onto (0, -1, 0)
    t = [0.0, -1.0, 0.0]
    axis = [u[1] * t[2] - u[2] * t[1], u[2] * t[0] - u[0] * t[2], u[0] * t[1] - u[1] * t[0]]
    s, c = math.sqrt(sum(v * v for v in axis)), sum(u[i] * t[i] for i in range(3))
    if s < 1e-9:
        g = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]] if c > 0 else [[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]
    else:
        k = [v / s for v in axis]
        K = [[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]
        K2 = _mul(K, K)
        g = [[(1.0 if i == j else 0.0) + s * K[i][j] + (1 - c) * K2[i][j] for j in range(3)] for i in range(3)]
    turns = collections.Counter()
    for _, _, _, rot in placed:
        a = angles(_mul(g, rot))
        if a and abs(a[1] % 90) < 1 and abs(a[2] % 90) < 1:
            turns[round(a[0] % 90, 1)] += 1
    off = turns.most_common(1)[0][0] if turns else 0.0
    return _mul(_ry(math.radians(-off)), g) if off > 0.05 else g

