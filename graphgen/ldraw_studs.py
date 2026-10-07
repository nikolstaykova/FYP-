"""v6 Path A: connections from the LDraw library's connection primitives, the way LEGO CAD tools find them.

Every piece's file is walked down to its primitives, and each connection point is kept with its exact position and
axis in the finished model:
  stud   studs on top (stud.dat, stud2.dat, studa.dat, logo and truncated variants); axis = the way the stud points
  hole   Technic pin holes (peghole, connhole, beamhole, npeghol*) and axle holes (axlehole, axl*hol*)
  pin    Technic pins and axles (connect*, confric*, axle.dat)
Matching:
  clutch   a stud of piece A goes into one of piece B's receptacle cells: in B's own coordinates the stud base lies
           on B's bottom face and on its underside grid (a cell every 20 LDU), pointing up into B
           (any orientation in the model, so a stud on the side of a brick into a sideways piece counts too)
  pin      a pin or axle of piece A runs along the axis of a hole of piece B, through or close to its centre
Pieces that only touch (side by side, or resting without a stud) are `contact`, from their boxes (ldraw_geometry).
"""
import functools
import math
import re

from . import ldraw_geometry as geo
from . import truth

STUD = re.compile(r"^(?:\d+-\d+)?stud(?!3|4|12)[\w-]*\.dat$")
HOLE = re.compile(r"^(peghole|connhol|beamhol|npeghol|axlehol|axl\dho)[\w-]*\.dat$")
PIN = re.compile(r"^(connect|confric|axle)\d*[a-z]?\.dat$")


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


@functools.lru_cache(maxsize=None)
def features(part):
    """Connection points of a library file, in its own coordinates: ((kind, point, axis), ...).
    A primitive's axis is its local -Y (studs point that way; holes and pins run along Y)."""
    text = geo.text_of(part)
    if text is None:
        return ()
    out = []
    for line in text.splitlines():
        b = line.split()
        if len(b) < 15 or b[0] != "1":
            continue
        ref = " ".join(b[14:]).lower().replace("\\", "/")
        pos = [float(x) for x in b[2:5]]
        rot = truth._mat([float(x) for x in b[5:14]])
        kind = _kind(ref)
        if kind:
            out.append((kind, tuple(pos), tuple(_norm(truth._apply(rot, [0.0, -1.0, 0.0])))))
            continue
        for k, p, a in features(ref):
            out.append((k, tuple(pos[i] + truth._apply(rot, list(p))[i] for i in range(3)),
                        tuple(_norm(truth._apply(rot, list(a))))))
    return tuple(out)


def _world(placed):
    """[(id, part, pos, rot)] -> {id: [(kind, point, axis)]} in model coordinates."""
    out = {}
    for nid, part, pos, rot in placed:
        out[nid] = [(k, [pos[i] + truth._apply(rot, list(p))[i] for i in range(3)], _norm(truth._apply(rot, list(a))))
                    for k, p, a in features(part)]
    return out


def _inside(pt, b, tol=0.5):
    return all(b[i] - tol <= pt[i] <= b[i + 3] + tol for i in range(3))


def _local(pt, pos, rot):
    """A model point in a placed piece's own coordinates (rotation matrices are orthonormal: inverse = transpose)."""
    d = [pt[i] - pos[i] for i in range(3)]
    return [sum(rot[r][c] * d[r] for r in range(3)) for c in range(3)]


def receives(stud_point, stud_axis, part, pos, rot, tol=1.5):
    """True if a stud based at `stud_point`, pointing along `stud_axis`, goes into one of `part`'s receptacle cells:
    in the part's own coordinates the stud base is on its bottom face (local +Y side, LDraw down) and on its
    underside grid (one cell every 20 LDU, 10 LDU in from the edges), pointing up into it."""
    b = geo.box(part)
    if b is None:
        return False
    local = _local(stud_point, pos, rot)
    axis = [sum(rot[r][c] * stud_axis[r] for r in range(3)) for c in range(3)]
    if axis[1] > -0.95 or abs(local[1] - b[4]) > tol:  # must point up (-Y) into the part's bottom face
        return False
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
    found = [b for b, bb in boxes.items() if b != a and bb and _inside(inner, bb, 1.0) and receives(p, ax, *where[b])]
    if len(found) > 1:
        found = [b for b in found if _solid(p, *where[b])] or found
    return found


def connections(placed):
    """{frozenset(a, b): (how, port on a, port on b)} with how = 'clutch' or 'pin'; ports as 'stud.<n>', 'hole.<n>'."""
    feats = _world(placed)
    boxes = {nid: geo.world_box(part, pos, rot) for nid, part, pos, rot in placed}
    where = {nid: (part, pos, rot) for nid, part, pos, rot in placed}
    found = {}
    # clutch: a stud of A points into B, and B's surface is at the stud's base
    for a, fs in feats.items():
        studs = [(i, p, ax) for i, (k, p, ax) in enumerate(f for f in fs if f[0] == "stud")]
        for n, p, ax in studs:
            for b in _holders(a, p, ax, boxes, where):
                found.setdefault(frozenset((a, b)), ("clutch", a, f"stud.{n + 1}", b, "anti"))
    # pin: a pin/axle of A along the axis of a hole of B
    holes = [(b, i, p, ax) for b, fs in feats.items() for i, (k, p, ax) in enumerate(f for f in fs if f[0] == "hole")]
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
                if perp <= 2.5 and abs(along) <= 30:
                    found[frozenset((a, b))] = ("pin", a, "pin", b, f"hole.{n + 1}")
    return found


# --- Checks that the geometry is right (v6): physical laws, and agreement with the box method -----------------
def validate(placed, found):
    """Physical laws every correct model obeys; a violation flags the model instead of trusting it.
      G1  a stud sits inside two or more pieces (a stud fits one receptacle)
      G2  a piece is clutched to itself
      G3  more clutches than the model has studs
      G4  a piece has no join or contact at all, and is not the lowest piece of its model
    Returns [(rule, message)]."""
    issues = []
    feats = _world(placed)
    boxes = {nid: geo.world_box(part, pos, rot) for nid, part, pos, rot in placed}
    where = {nid: (part, pos, rot) for nid, part, pos, rot in placed}
    for a, fs in feats.items():
        for n, (k, p, ax) in enumerate(f for f in fs if f[0] == "stud"):
            holders = _holders(a, p, ax, boxes, where)
            if len(holders) > 1:
                issues.append(("G1", f"stud {n + 1} of {a} is inside {len(holders)} pieces: {holders}"))
    for key, (how, a, _, b, _) in found.items():
        if a == b:
            issues.append(("G2", f"{a} is clutched to itself"))
    studs = sum(1 for fs in feats.values() for f in fs if f[0] == "stud")
    clutches = sum(1 for v in found.values() if v[0] == "clutch")
    if clutches > studs:
        issues.append(("G3", f"{clutches} clutches but only {studs} studs"))
    touched = {x for k in found for x in k} | {x for k in geo.touching(placed) for x in k}
    lowest = max((bb[4] for bb in boxes.values() if bb), default=0)  # -Y is up: the lowest piece has the largest Y
    for nid, bb in boxes.items():
        if nid not in touched and bb and abs(bb[4] - lowest) > 1:
            issues.append(("G4", f"{nid} touches nothing and is not at the bottom of the model"))
    return issues


def cross_check(placed, found):
    """Pairs where the box method and the stud method disagree about pieces resting on pieces: what one sees and
    the other does not. Flagged for review, not trusted either way."""
    rest = {k for k, how in geo.touching(placed).items() if how == "rest"}
    clutch = {k for k, v in found.items() if v[0] == "clutch"}
    return {"boxes_only": sorted(tuple(sorted(k)) for k in rest - clutch),
            "studs_only": sorted(tuple(sorted(k)) for k in clutch - rest)}
