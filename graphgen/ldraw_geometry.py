"""Real piece shapes from the LDraw parts library, for Path A (v5): every piece's box, and which pieces rest on which.

The answer key (truth.py) only knows plain bricks, plates and tiles by their names. Here every piece's box comes from
its own geometry in the library (lines, triangles and quads of the part and its sub-parts and primitives), so slopes,
round pieces, special bricks and Technic bricks stack too. Studs on top are left out of the box, so its top is the
surface the next piece clutches. A piece joins every piece whose top its bottom sits on (within 1 LDU) with at least
half a stud (10 x 10 LDU) of overlap. Side connections (pins in holes, hinges, clips) are not found this way.
"""
import functools
import re
import zipfile

from . import truth

_ZIP = truth.pathlib.Path(__file__).resolve().parents[1] / "research" / "raw" / "lego" / "complete.zip"
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
EMBEDDED = {}  # parts a model file carries itself (truth.embedded_parts), by name; looked up before the library


def register(text):
    """Make the parts embedded in a model file readable here (call before box/features on that model)."""
    EMBEDDED.update(truth.embedded_parts(text))


def text_of(part):
    """A part file's text: embedded in a model, else from the library zip; None if unknown."""
    key = truth.ldraw_key(part)
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
            rot = truth._mat([float(x) for x in b[5:14]])
            pts += [[pos[i] + truth._apply(rot, c)[i] for i in range(3)] for c in _corners(sub)]
    if not pts:
        return None
    return tuple(min(p[i] for p in pts) for i in range(3)) + tuple(max(p[i] for p in pts) for i in range(3))


def _corners(b):
    return [[x, y, z] for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]


def world_box(part, pos, rot):
    b = box(part)
    if b is None:
        return None
    pts = [[pos[i] + truth._apply(rot, c)[i] for i in range(3)] for c in _corners(b)]
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
