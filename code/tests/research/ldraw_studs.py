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


import ldraw_geometry as geo

import truth

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
    return bool(AXLE.match(truth.library_title(truth.resolve(part)) or ""))


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
        for k, p, a in _features(ref):
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


def receives(stud_point, stud_axis, part, pos, rot, tol=1.5, by_studs=False):
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
            bb = geo.box(where[b][0])
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
            bb = geo.box(where[b][0])
            if not bb or not re.search(r"\bround\b|\bdish\b", truth.library_title(truth.resolve(where[b][0])) or "", re.I):
                return False
            local = _local(p, where[b][1], where[b][2])
            axis = [sum(where[b][2][r][c] * ax[r] for r in range(3)) for c in range(3)]
            return axis[1] <= -0.95 and abs(local[1] - bb[4]) <= 1.5 and all(
                abs(local[i] - (bb[i] + bb[i + 3]) / 2) <= 1.5 for i in (0, 2))
        hits = [b for b in near if centre(b)]
        found = hits if len(hits) == 1 else found
    # a part "with Stud Hole" the stud passes through on its way into the piece above: clamped, so held too
    for b in near:
        if b not in found and re.search(r"stud hole", truth.library_title(truth.resolve(where[b][0])) or "", re.I):
            bb = geo.box(where[b][0])
            local = _local(p, where[b][1], where[b][2])
            if bb and abs(local[1] - bb[4]) <= 1.5 and all(bb[i] - 1.5 <= local[i] <= bb[i + 3] + 1.5 for i in (0, 2)):
                found = found + [b]
    if not found and len(near) == 1:  # one piece only over the stud, its underside right at the stud's base: a
        b = near[0]                   # bracket or other odd shape whose cells neither grid finds
        bb = geo.box(where[b][0])
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
    b = geo.box(part)
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
    import render
    tris = [t for c, t in render.mesh(part) if c != "24"]
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
    boxes = {nid: geo.world_box(part, pos, rot) for nid, part, pos, rot in placed}
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
        if WITH_AXLE.search(truth.library_title(truth.resolve(part)) or ""):
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
            holders = [h for h in _holders(a, p, ax, boxes, where)
                       if not re.search(r"stud hole", truth.library_title(truth.resolve(where[h][0])) or "", re.I)]
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
