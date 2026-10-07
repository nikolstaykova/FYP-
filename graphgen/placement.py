"""v8 LEGO Path B: Claude places every piece, code finds the connections from the pieces' real shapes.

Claude gives each piece of the PIECE LIST a placement read off the booklet's pictures:
  column, row   its front-left corner on the stud grid (column to the right, row towards the back), in studs,
                half-stud steps (a jumper plate puts a piece between rows)
  layer         the height of its lowest point in plates above the lowest piece (a brick is 3 plates)
  turn          degrees clockwise seen from above, 0-360
  tilt          degrees its top tips towards the front (90 = studs face the front: bricks with studs on the side)
  roll          degrees its top tips towards the right (90 = studs face the right)
  free_angle    true only for a piece held at an angle that is not a quarter turn (turntable, hinge, clip)
Code snaps what the studs force (quarter turns, the half-stud grid, whole plates), puts each piece's LDraw part
there and finds the joins with the same stud-in-receptacle and pin-in-hole matching the answer key uses
(ldraw_studs.connections). If the placements are right, the joins are right for every kind of piece; `round_trip`
proves that on the sets' own LDraw models.

Coordinates are LDraw's: 1 stud = 20 LDU, 1 plate = 8 LDU, -Y is up, +Z is the back, so the turn-0 front of a
part (a slope's sloped face, a headlight brick's side stud) faces -Z, as the library draws it.
"""
import collections
import functools
import math
import re

from . import ldraw_geometry as geo
from . import ldraw_studs, truth

STUD, PLATE = 20.0, 8.0


@functools.lru_cache(maxsize=None)
def ldraw_file(part_num):
    """A Rebrickable part number -> the LDraw library file of that piece (98% are the same name), else None:
    the number itself, then without its print or pattern (3069bpr0100 -> 3069b), then its mould letters."""
    geo._zip()
    names = geo._NAMES
    p = part_num.lower()
    tries = [p, re.sub(r"(pr|pat|px)\d+[a-z]?$", "", p)]
    base = re.match(r"^(\d+)", p)
    if base:
        tries += [base.group(1)] + [base.group(1) + c for c in "abcd"]
    m = re.match(r"^(\d+)c(\d+)$", p)  # 298c02 assemblies: the first part number of the family
    if m:
        tries += [f"{m.group(1)}c01"]
    for t in tries:
        if f"{t}.dat" in names:
            return f"{t}.dat"
    return None


def piece_list(parts):
    """The v8 PIECE LIST from a set's parts list: {p1..pN: {type, name, colour, shape, ldraw, size}}, one id per
    physical piece, in parts-list order."""
    from . import checks
    info, n = {}, 0
    for p in parts:
        part = ldraw_file(p["part_num"])
        sz = size(part) if part else None
        for _ in range(p["quantity"]):
            n += 1
            info[f"p{n}"] = {"type": f"lego-{p['part_num']}", "name": p["name"], "colour": p["color"],
                             "shape": checks.piece_shape(p["name"]), "ldraw": part, "size": sz}
    return info


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
    m = truth._mul(truth._mul(_ry(r[0]), _rx(r[1])), _rz(r[2]))
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


def _snap(v, step):
    return round(v / step) * step


def snapped(pl):
    """Angles the studs force: quarter turns, unless the piece is held at a free angle (turntable, hinge, clip).
    Positions are snapped in place(), on the part's own stud grid."""
    q = (lambda a: _snap(a, 90.0) % 360) if not pl.get("free_angle") else (lambda a: a % 360)
    return {"column": pl["column"], "row": pl["row"], "layer": pl["layer"], "turn": q(pl.get("turn") or 0),
            "tilt": q(pl.get("tilt") or 0), "roll": q(pl.get("roll") or 0), "free_angle": bool(pl.get("free_angle")),
            **({"relative_to": pl["relative_to"]} if pl.get("relative_to") else {})}


@functools.lru_cache(maxsize=None)
def anchor(part):
    """A point of the part that lies on the half-stud grid and a plate line when the part is placed right: a top
    stud's base (else the part's origin, which the library puts on the grid). The box corner Claude reads may not be
    on the grid (a clip, a wheel holder or a pin sticks out), so the snap is done on this point instead."""
    for k, p, a in ldraw_studs.features(part):
        if k == "stud" and a[1] < -0.95:
            return tuple(p)
    return (0.0, 0.0, 0.0)


@functools.lru_cache(maxsize=None)
def size(part):
    """(width in studs, depth in studs, height in plates) of a library part at turn 0, top studs left out."""
    b = geo.box(part)
    if b is None:
        return None
    return tuple(round((b[i + 3] - b[i]) / u, 2) for i, u in ((0, STUD), (2, STUD), (1, PLATE)))


def place(part, pl):
    """(pos, rot) in LDraw coordinates for a placement (angles already snapped): the part's box, turned, has its
    front-left corner at (column, row) and its lowest point at `layer`; then the part's anchor is snapped to the
    half-stud grid and the plate lines (upright), or a fifth of a stud / half a plate (on its side). A piece at a
    free angle is placed as given."""
    rot = rotation(pl["turn"], pl["tilt"], pl["roll"])
    b = geo.world_box(part, [0.0, 0.0, 0.0], rot)
    if b is None:
        return None
    pos = [pl["column"] * STUD - b[0], -pl["layer"] * PLATE - b[4], pl["row"] * STUD - b[2]]
    if not pl.get("free_angle") and _has_top_studs(part):
        upright = pl["tilt"] == 0 and pl["roll"] == 0
        across, up = (STUD / 2, PLATE) if upright else (4.0, 4.0)
        a = truth._apply(rot, list(anchor(part)))
        world = [pos[i] + a[i] for i in range(3)]
        pos = [pos[0] + _snap(world[0], across) - world[0], pos[1] + _snap(world[1], up) - world[1],
               pos[2] + _snap(world[2], across) - world[2]]
    return [round(v, 4) for v in pos], rot


def placement_of(part, pos, rot):
    """The placement a correct answer gives for a piece of a real model (round trip): column/row of the turned box's
    front-left corner, layer of its lowest point. Not snapped and not shifted to the model's origin."""
    a = angles(rot)
    b = geo.world_box(part, pos, rot)
    if a is None or b is None:
        return None
    return {"column": b[0] / STUD, "row": b[2] / STUD, "layer": -b[4] / PLATE, "turn": a[0], "tilt": a[1], "roll": a[2]}


def _has_top_studs(part):
    return any(k == "stud" and a[1] < -0.95 for k, _, a in ldraw_studs.features(part))


def snap_pins(placed, reach=12.0):
    """A piece with no studs on top (a Technic pin, an axle, a wheel, a beam) is not on the plate lines: slide it
    so its pin or axle runs along the nearest hole of another piece (or its hole along another piece's pin), as a
    CAD tool does, if that hole is within `reach` LDU (about half a stud) across the axis."""
    feats = ldraw_studs._world(placed)
    out = []
    for nid, part, pos, rot in placed:
        if _has_top_studs(part):
            out.append((nid, part, pos, rot))
            continue
        best = None
        for k, p, ax in feats[nid]:
            want = {"pin": "hole", "hole": "pin"}.get(k)
            if not want:
                continue
            for other, fs in feats.items():
                if other == nid:
                    continue
                for k2, p2, ax2 in fs:
                    if k2 != want or abs(sum(ax[i] * ax2[i] for i in range(3))) < 0.95:
                        continue
                    d = [p2[i] - p[i] for i in range(3)]
                    along = sum(d[i] * ax2[i] for i in range(3))
                    perp = [d[i] - along * ax2[i] for i in range(3)]
                    n = math.sqrt(sum(v * v for v in perp))
                    if n <= reach and abs(along) <= 40 and (best is None or n < best[0]):
                        best = (n, perp)
        if best and best[0] > 1e-6:
            pos = [pos[i] + best[1][i] for i in range(3)]
            feats[nid] = [(k, [p[i] + best[1][i] for i in range(3)], ax) for k, p, ax in feats[nid]]
        out.append((nid, part, pos, rot))
    return out


def _pinned(part):
    return any(k in ("pin", "hole") for k, _, _ in ldraw_studs.features(part))


def settle_one(part, pos, rot, near, reach=(10.0, 12.0)):
    """The position (moved by at most `reach` LDU across / along its up axis) where a piece's underside takes the
    most of the studs `near` [(point, axis)], in any orientation; unchanged if it already takes one or none can be
    reached."""
    b = geo.box(part)
    if b is None or not near or any(ldraw_studs.receives(p, ax, part, pos, rot) for p, ax in near):
        return pos

    def taken(at):
        return sum(1 for p, ax in near if ldraw_studs.receives(p, ax, part, at, rot))
    best, best_n, best_d = pos, 0, 0.0
    for p, ax in near:
        l = ldraw_studs._local(p, pos, rot)
        lax = [sum(rot[r][c] * ax[r] for r in range(3)) for c in range(3)]
        if lax[1] > -0.95 or abs(l[1] - b[4]) > reach[1]:
            continue
        if not (b[0] - reach[0] <= l[0] <= b[3] + reach[0] and b[2] - reach[0] <= l[2] <= b[5] + reach[0]):
            continue
        tx = min(max(b[0] + 10 + 20 * round((l[0] - b[0] - 10) / 20), b[0] + 10), b[3] - 10)
        tz = min(max(b[2] + 10 + 20 * round((l[2] - b[2] - 10) / 20), b[2] + 10), b[5] - 10)
        dl = [l[0] - tx, l[1] - b[4], l[2] - tz]
        if abs(dl[0]) > reach[0] or abs(dl[2]) > reach[0]:
            continue
        d = truth._apply(rot, dl)
        at = [pos[i] + d[i] for i in range(3)]
        n, size = taken(at), math.sqrt(sum(v * v for v in d))
        if n > best_n or (n == best_n and n and size < best_d):
            best, best_n, best_d = at, n, size
    return [round(v, 4) for v in best]


def _studs_of(w):
    return [(p, ax) for k, p, ax in ldraw_studs._world([w[:4]])[w[0]] if k == "stud"]


def settle(placed, supports, reach=(10.0, 12.0)):
    """A piece that does not clutch the pieces it says it rests on (`supports`: {id: ids}) is slid by at most
    `reach` LDU (across, along its up axis), lowest pieces first, so its underside takes the most studs of those
    pieces, in any orientation, as a CAD tool drops a piece onto studs. Only towards the pieces named, so a
    placement that is right (or a piece with nothing under it) is never moved; a piece at a free angle neither."""
    up_first = sorted(placed, key=lambda w: -(geo.world_box(w[1], w[2], w[3]) or (0, 0, 0, 0, 0, 0))[4])
    done, studs = {}, {}
    for nid, part, pos, rot, free in up_first:
        near = [x for o in supports.get(nid, ()) for x in studs.get(o, ())]
        if not free:
            pos = settle_one(part, pos, rot, near, reach)
        done[nid] = (nid, part, pos, rot)
        studs[nid] = _studs_of(done[nid])
    return [done[w[0]] for w in placed]


def resolve_relative(pieces, supports, steps=None):
    """v8 relative placements -> placed pieces [(id, part, pos, rot, free)]. pieces: {id: (LDraw part, placement)}
    where a placement may name `relative_to`, an id: then column/row/layer are counted from THAT piece's
    front-left-bottom corner (studs right / back, plates up) instead of from the model's. Pieces are placed one at a
    time, every piece after the one it is counted from, and each is settled onto the studs of the pieces it rests on
    before the next is placed, so a misreading is corrected where it happens and does not carry over. A piece with
    no (known) relative_to, or in a loop of them, is counted from the model's origin."""
    order, seen, stack = [], set(), set()
    key = lambda i: ((steps or {}).get(i, 0), len(i), i)

    def visit(i):
        if i in seen or i in stack:
            return
        stack.add(i)
        ref = pieces[i][1].get("relative_to")
        if ref in pieces and ref != i:
            visit(ref)
        stack.discard(i)
        seen.add(i)
        order.append(i)
    for i in sorted(pieces, key=key):
        visit(i)
    done, studs, out = {}, {}, {}
    for i in order:
        part, pl = pieces[i]
        ref = pl.get("relative_to")
        if ref in done and ref != i:
            rb = geo.world_box(done[ref][1], done[ref][2], done[ref][3])
            pl = {**pl, "column": rb[0] / STUD + pl["column"], "row": rb[2] / STUD + pl["row"],
                  "layer": -rb[4] / PLATE + pl["layer"]}
        where = place(part, snapped(pl))
        if not where:
            continue
        pos, rot = where
        free = bool(pl.get("free_angle"))
        if not free:
            near = [x for o in supports.get(i, ()) for x in studs.get(o, ())]
            pos = settle_one(part, pos, rot, near)
        done[i] = (i, part, pos, rot)
        studs[i] = _studs_of(done[i])
        out[i] = (i, part, pos, rot, free)
    return [out[i] for i in pieces if i in out]


def _move(w, turn, centre, d):
    """A placed piece (nid, part, pos, rot, free) turned `turn` degrees about the vertical through `centre`, then
    shifted by d."""
    nid, part, pos, rot, free = w
    r = _ry(math.radians(turn))
    p = truth._apply(r, [pos[i] - centre[i] for i in range(3)])
    return (nid, part, [round(p[i] + centre[i] + d[i], 4) for i in range(3)], truth._mul(r, rot), free)


def register_steps(placed, steps, supports):
    """Claude reads each booklet step on its own and its grid drifts from step to step (a step's pieces are right
    among themselves but shifted or turned against the model). Each step's new pieces are moved TOGETHER, by a
    quarter turn and a shift, so that as many as possible clutch the earlier pieces they say they rest on; a step
    that names no earlier support (the first, or a sub-assembly's start) stays where it is."""
    by_step = collections.defaultdict(list)
    for w in placed:
        by_step[steps.get(w[0], 0)].append(w)
    done = []
    for s in sorted(by_step):
        group = by_step[s]
        before = {w[0]: w for w in done}
        pairs = [(w, before[v]) for w in group for v in supports.get(w[0], ()) if v in before]
        if not pairs or any(w[4] for w in group):
            done += group
            continue

        def held(g):
            at = {w[0]: w for w in g}
            return sum(1 for w, sup in pairs
                       if any(ldraw_studs.receives(p, ax, at[w[0]][1], at[w[0]][2], at[w[0]][3])
                              for k, p, ax in ldraw_studs._world([sup[:4]])[sup[0]] if k == "stud"))
        best, best_n, best_cost = group, held(group), 0.0
        if best_n < len(pairs):
            centre = group[0][2]
            for turn in (0, 90, 180, 270):
                turned = [_move(w, turn, centre, (0, 0, 0)) for w in group]
                tw = {w[0]: w for w in turned}
                for w, sup in pairs[:6]:
                    nid, part, pos, rot, _ = tw[w[0]]
                    b = geo.box(part)
                    if b is None:
                        continue
                    for k, p, ax in ldraw_studs._world([sup[:4]])[sup[0]]:
                        if k != "stud":
                            continue
                        l = ldraw_studs._local(p, pos, rot)
                        tx = min(max(b[0] + 10 + 20 * round((l[0] - b[0] - 10) / 20), b[0] + 10), b[3] - 10)
                        tz = min(max(b[2] + 10 + 20 * round((l[2] - b[2] - 10) / 20), b[2] + 10), b[5] - 10)
                        d = truth._apply(rot, [l[0] - tx, l[1] - b[4], l[2] - tz])
                        moved = [_move(x, 0, centre, d) for x in turned]
                        n = held(moved)
                        cost = math.sqrt(sum(v * v for v in d)) + (0 if turn == 0 else 40)
                        if n > best_n or (n == best_n and n > held(group) and cost < best_cost):
                            best, best_n, best_cost = moved, n, cost
        done += best
    at = {w[0]: w for w in done}
    return [at[w[0]] for w in placed]


def joins(pieces, supports=None, steps=None):
    """pieces: {id: (LDraw part, snapped placement)}, supports: {id: the ids it says it rests on}, steps: {id:
    booklet step} -> ({frozenset(a, b): (how, ...)} as ldraw_studs.connections, placed list). Pieces whose part is
    unknown are left out. With steps, each step is registered onto the earlier ones first (register_steps)."""
    pieces = {i: v for i, v in pieces.items() if v[0]}
    if any(pl.get("relative_to") for _, pl in pieces.values()):  # v8 relative placements: one piece at a time
        placed = snap_pins([w[:4] for w in resolve_relative(pieces, supports or {}, steps)])
        return ldraw_studs.connections(placed), placed
    placed = []
    for nid, (part, pl) in pieces.items():
        where = place(part, pl)
        if where:
            placed.append((nid, part, *where, bool(pl.get("free_angle"))))
    if steps:
        placed = register_steps(placed, steps, supports or {})
    placed = snap_pins(settle(placed, supports or {}))
    return ldraw_studs.connections(placed), placed


def laws(placed, found, stated, info, limit=60):
    """Physical laws on Claude's placements, worded for a repair. stated: {id: rests_on}; info: {id: name}.
      L11  two pieces fill the same space (their boxes overlap by more than a quarter stud in all three directions,
           and no pin or stud joins them)
      L12  a piece is held by nothing (no stud, no pin, no other piece touching it) and is not at the bottom
      L13  rests_on names a piece, but the placements do not put this piece's bottom on that piece's studs
      L14  a stud of one piece sits inside two pieces"""
    issues = []
    boxes = {nid: geo.world_box(part, pos, rot) for nid, part, pos, rot in placed}
    ids = sorted(boxes, key=lambda x: (len(x), x))
    over = lambda a, b, i: min(a[i + 3], b[i + 3]) - max(a[i], b[i])
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            ba, bb = boxes[a], boxes[b]
            if ba and bb and all(over(ba, bb, i) > 5 for i in range(3)) and frozenset((a, b)) not in found:
                issues.append(("L11", f"{a} ({info.get(a, '')}) and {b} ({info.get(b, '')}) fill the same space: "
                                      f"check their column, row, layer and turn"))
    for rule, msg in ldraw_studs.validate(placed, found):
        if rule == "G4":
            nid = msg.split()[0]
            issues.append(("L12", f"{nid} ({info.get(nid, '')}) is held by nothing at its placement (no stud below or "
                                  f"above it, no pin, not touching another piece): check its layer, column and row"))
        elif rule == "G1":
            issues.append(("L14", msg + ": two pieces cannot share one stud; one of them is misplaced"))
    for u, below in stated.items():
        for v in below:
            if u in boxes and v in boxes and frozenset((u, v)) not in found:
                bu, bv = boxes[u], boxes[v]
                why = (f"its bottom is at layer {-bu[4] / PLATE:g} but the top of {v} is at layer {-bv[1] / PLATE:g}"
                       if abs(bu[4] - bv[1]) > 1 else "they share no stud cell (check column, row and turn)")
                issues.append(("L13", f"{u} rests on {v}, but their placements do not join them: {why}"))
    return issues[:limit] + ([("L11", f"… and {len(issues) - limit} more problems of the same kinds")] if len(issues) > limit else [])


def upright(placed):
    """The rotation that stands a model file upright: the commonest 'up' of its pieces becomes up (-Y), then the
    commonest turn left over (mod a quarter turn) is taken out."""
    import collections
    ups = collections.Counter(tuple(round(v, 2) for v in truth._apply(rot, [0.0, -1.0, 0.0])) for _, _, _, rot in placed)
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
        K2 = truth._mul(K, K)
        g = [[(1.0 if i == j else 0.0) + s * K[i][j] + (1 - c) * K2[i][j] for j in range(3)] for i in range(3)]
    turns = collections.Counter()
    for _, _, _, rot in placed:
        a = angles(truth._mul(g, rot))
        if a and abs(a[1] % 90) < 1 and abs(a[2] % 90) < 1:
            turns[round(a[0] % 90, 1)] += 1
    off = turns.most_common(1)[0][0] if turns else 0.0
    return truth._mul(_ry(math.radians(-off)), g) if off > 0.05 else g


def round_trip(mpd_text, reading=None):
    """Does a correct answer give the right joins? Every piece of a real model -> its placement (as Claude would
    read it) -> snapped -> placed again -> joins, compared with the joins of the model itself.
    Returns {pieces, off_grid (placement changed by snapping), unknown (no box / mirrored), joins_true,
    joins_found, joins_correct}."""
    geo.register(mpd_text)
    real = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(truth.flatten_mpd(mpd_text), 1)]
    truth_joins = set(ldraw_studs.connections(real))
    g = upright(real)  # some files store the whole model tilted (a mosaic on a stand); Claude reads it upright
    real = [(nid, ref, truth._apply(g, pos), truth._mul(g, rot)) for nid, ref, pos, rot in real]
    # Claude counts from the model's own grid; a model file's origin need not be on it: shift the model by the
    # commonest offset of the pieces' anchors from the half-stud grid and the plate lines
    import collections
    at = [[pos[i] + truth._apply(rot, list(anchor(ref)))[i] for i in range(3)] for _, ref, pos, rot in real]
    shift = [collections.Counter(round(p[i] % g, 2) for p in at).most_common(1)[0][0] if at else 0.0
             for i, g in ((0, STUD / 2), (1, PLATE), (2, STUD / 2))]
    real = [(nid, ref, [pos[i] - shift[i] for i in range(3)], rot) for nid, ref, pos, rot in real]
    pieces, off, unknown = {}, [], []
    for nid, ref, pos, rot in real:
        pl = placement_of(ref, pos, rot)
        if pl is None:
            unknown.append(nid)
            continue
        s = snapped(pl)
        got = place(ref, s)
        if not got or max(abs(got[0][i] - pos[i]) for i in range(3)) > 0.05:
            if _has_top_studs(ref) or any(abs(s[k] - pl[k]) % 360 > 0.01 and abs(abs(s[k] - pl[k]) - 360) > 0.01
                                          for k in ("turn", "tilt", "roll")):
                s = {**pl, "free_angle": True}  # a correct reader gives a piece off the grid as it is, free_angle
                off.append(nid)
        if reading:  # what a careful reader of pictures gives: rounded positions and angles
            s = {**s, **{k: round(s[k] / reading[k]) * reading[k] for k in ("column", "row", "layer")}}
            if s.get("free_angle"):
                s = {**s, **{k: round(s[k] / reading["angle"]) * reading["angle"] for k in ("turn", "tilt", "roll")}}
        pieces[nid] = (ref, s)
    supports = {}
    for k, (how, a, _, b, _) in ldraw_studs.connections(real).items():
        if how == "clutch":  # a's stud is in b: b rests on a, as a correct rests_on says
            supports.setdefault(b, set()).add(a)
    found = set(joins(pieces, supports)[0])
    return {"pieces": len(real), "off_grid": len(off), "unknown": len(unknown), "joins_true": len(truth_joins),
            "joins_found": len(found), "joins_correct": len(found & truth_joins),
            "missed": sorted(map(sorted, truth_joins - found))[:10], "extra": sorted(map(sorted, found - truth_joins))[:10]}


def pl_close(a, b, tol=1e-3):
    return all(abs(a[k] - b[k]) <= tol or abs(abs(a[k] - b[k]) - 360) <= tol for k in a)
