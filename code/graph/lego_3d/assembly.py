"""Can a piece really be put on, and the 3D viewer that shows it.

What it is   for a piece added to what is built: the way it goes on (onto a stud, along a pin or axle), whether its
             real shape can travel that way without passing through a built piece, room for a finger, the pieces
             built in the hand first, and how much of each new piece each of the 8 views shows. And the 3D hint
             viewer: every piece as its real LDraw shape at its exact place, written for a web page (three.js,
             lesson_viewer.html beside this file) that shows the model built so far and lifts the step's new pieces
             into place on Hint; substeps plays each step as physical actions (a piece held in place while an axle
             is pushed through it, or put on in turn).
Used for     the 3D route's checks S6 (a way in), S8 (finger room) and S13 (one view shows every new piece); the
             check that a step's words say what the 3D page shows (lesson.words_vs_3d); showing a learner where a
             step's pieces go.
Where        lego_3d/lesson.py (of, Sightlines, VIEWS, clip_joins, in_hand, substeps), lego_3d/graphs.py
             (clip_joins); the viewer on its own: python -m graph.lego_3d.assembly 31040-1 ->
             data/lessons/lego3d/<set>/viewer/{index.html, lesson.json}.

For a piece added to what is already built:
  approach(nid, built)   the direction it goes on, and what it fastens to: onto a stud it comes from beyond the stud's
                         tip; its own stud into another piece, along that stud; a pin or axle slides along the hole's
                         axis, from the piece's own side; a piece that fastens to nothing it touches comes down
  clear(nid, d, built)   whether it can get to its place along d: its real shape (LDraw triangles as 4-LDU cubes),
                         slid back along its path a cube at a time, must not pass through a piece already built.
                         Pieces that touch share some cubes in their final places, so a piece blocks only when the
                         path crosses clearly more of it than the final place does. Returns the first blocker.
Coordinates are LDraw's (-Y up); directions point from where the piece starts to where it ends.
"""
import functools
import json
import math
import pathlib
import re
import struct
import sys

from graph import lego_model

VOX = 4.0
BAR = r"\bbar\b|lightsaber|\btap\b|handle|antenna|whip|\brod\b|pole|\bhose\b|harpoon|\bwand\b|\bstaff\b|telescope"
CLIP = r"\bclips?\b|\bholder\b"  # (a plate "with 2 Clips" too)
FLEX = r"\btyre\b|\btire\b|rubber|\bhose\b|\bcable\b|\bstring\b|\bflex|_subpart"  # bend out of the way (tyres stretch)


def clip_joins(where, touch):
    """Clip-and-bar fits the LDraw parts do not mark (studs and pin holes are marked; clips and bars are not): a
    bar-like piece (bar, blade, tap, handlebars, antenna ...) touching or inside a piece with a clip clips into it.
    Returns {frozenset(bar, clip): ('clip', clip, 'clip', bar, 'bar')}."""
    import re
    name = {nid: lego_model.library_title(lego_model.resolve(w[1])).lower().lstrip("~_=| ") for nid, w in where.items()}
    out = {}
    for k in touch:
        if len(k) != 2:
            continue
        a, b = tuple(k)
        for bar, clip in ((a, b), (b, a)):
            if re.search(BAR, name[bar]) and re.search(CLIP, name[clip]) and not re.search(CLIP, name[bar]):
                out[frozenset(k)] = ("clip", clip, "clip", bar, "bar")
    return out


BALL = r"ball|towball"
SOCKET = r"socket|\bcup\b|steering link|shock absorber|\blink\b"
TYRE, RIM = r"\btyre|\btire", r"wheel|\brim\b|\bhub\b"
WHEEL_PIN = r"car base|wheels? holder|holder.*wheel|with (wheel )?pins?\b|\baxle\b|wheel bearing"  # built-in pins
SWIVEL = r"toggle joint|\bhinge\b|swivel"  # parts that turn, so a block's ends can go on different ways
# minifigure parts click together on pegs LDraw does not mark: (piece, what it goes onto), by name
FIG = [(r"^minifig leg\b", r"^minifig hips"), (r"^minifig torso", r"^minifig (hips|legs)"),
       (r"^minifig arm", r"^minifig torso"), (r"^minifig hand", r"^minifig arm"),
       (r"^minifig head\b(?!dress|gear)", r"^minifig torso"),
       (r"^minifig (lifevest|life vest|airtanks|air tanks|armou?r|cape|neck)", r"^minifig torso"),
       (r"^minifig (?!.*visor)(helmet|hat|cap|hair|headdress|headgear|hood|crown|bandana)", r"^minifig head\b(?!dress|gear)"),
       (r"visor", r"^minifig helmet")]


def soft_joins(where, touch):
    """Fits the LDraw parts mark nowhere: a ball (towball, ball joint) pressed into a socket of a piece it touches,
    a tyre pushed onto its rim, a flexible hose's ends on what they touch. {frozenset: (how, a, port, b, port)}."""
    import re
    name = {nid: lego_model.library_title(lego_model.resolve(w[1])).lower().lstrip("~_=| ") for nid, w in where.items()}
    out = {}
    for k in touch:
        if len(k) != 2:
            continue
        a, b = tuple(k)
        for x, y in ((a, b), (b, a)):
            if re.search(BALL, name[x]) and re.search(SOCKET, name[y]) and not re.search(BALL, name[y]):
                out[frozenset(k)] = ("ball", y, "socket", x, "ball")
            elif re.search(TYRE, name[x]) and re.search(RIM, name[y]) and not re.search(TYRE, name[y]):
                out[frozenset(k)] = ("tyre", y, "rim", x, "tyre")
            elif re.search(BAR, name[x]) and not re.search(CLIP, name[y]) and touch[k] == "insert" and re.search(
                    r"\bhole\b|axlehole|\bholder\b|pinhole|with hole|\bround\b|\bcone\b", name[y]) \
                    and not re.search(BAR, name[y]):  # (round plates, bricks and cones: the bar goes through the
                    # open stud)
                out[frozenset(k)] = ("bar", y, "hole", x, "bar")  # a bar or antenna pushed into a hole
            elif re.search(r"\bhinge\b", name[x]) and re.search(r"\bhinge\b", name[y]) and touch[k] == "insert" \
                    and x < y:  # two hinge halves pressed together (click-lock hinges, finger hinges): LDraw marks
                out[frozenset(k)] = ("hinge", y, "hinge", x, "hinge")  # no studs or pins there
            elif re.search(r"\bturntable\b", name[y]) and touch[k] == "insert" and not re.search(r"\bturntable\b", name[x]):
                out[frozenset(k)] = ("turn", y, "top", x, "turn")  # a turntable's top on its base: LDraw marks no studs there
            elif re.search(RIM, name[x]) and not re.search(TYRE, name[x]) and touch[k] == "insert" and re.search(
                    WHEEL_PIN, name[y]) and not re.search(RIM, name[y]):  # a wheel pushed onto a pin no file marks
                out[frozenset(k)] = ("wheel", y, "pin", x, "wheel")
            elif any(re.search(c, name[x]) and re.search(q, name[y]) for c, q in FIG):
                out[frozenset(k)] = ("fig", y, "peg", x, "fig")
            elif re.search(r"\bhose\b|flex-system|\bflex\b", name[x]) and not re.search(r"hose|flex", name[y]):
                out.setdefault(frozenset(k), ("hose", y, "end", x, "hose"))
    return out


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _sweep(cubes, d):
    """The piece's cubes moved s cubes back along its way in (-d), made once per s: path(s)."""
    memo = {}

    def path(s):
        if s not in memo:
            sh = [round(-d[i] * s) for i in range(3)]
            memo[s] = {(v[0] + sh[0], v[1] + sh[1], v[2] + sh[2]) for v in cubes}
        return memo[s]
    return path


# The 8 three-quarter views a booklet draws a model from: the camera far away along (sx, sy, sz) (LDraw axes, -y up,
# so sy = -1 looks from above)
VIEWS = [(sx, sy, sz) for sy in (-1, 1) for sx in (-1, 1) for sz in (-1, 1)]


class Sightlines:
    """What can be seen of a model as it grows, from each of the 8 views (Agrawala et al. 2003: "all the new parts
    added in each step must be visible"). A voxel is hidden from a view when a built voxel lies on its line toward the
    camera. Along a diagonal line (sx, sy, sz) the values x*sx - y*sy and x*sx - z*sz stay the same and x*sx grows
    toward the camera, so each view keeps, per line, the voxel nearest the camera: adding a piece and asking what is
    hidden are both one pass over its voxels."""

    def __init__(self, asm):
        self.asm, self.front = asm, {v: {} for v in VIEWS}

    def add(self, nid):
        for v, front in self.front.items():
            sx, sy, sz = v
            for x, y, z in self.asm.voxels(nid):
                k, t = (x * sx - y * sy, x * sx - z * sz), x * sx
                if front.get(k, -10 ** 9) < t:
                    front[k] = t

    def seen(self, nid, v):
        """Share of the piece that can be seen from view v, with what is built so far."""
        vox = self.asm.voxels(nid)
        if not vox:
            return 1.0
        sx, sy, sz = v
        front = self.front[v]
        return sum(1 for x, y, z in vox if front.get((x * sx - y * sy, x * sx - z * sz), -10 ** 9) <= x * sx) / len(vox)


def _idkey(i):
    """Piece ids (b12, b123) in number order."""
    return (len(str(i)), str(i))


def _axis(v):
    """The main axis nearest to v (a guessed direction is shown straight in, not at an angle)."""
    k = max(range(3), key=lambda i: abs(v[i]))
    if not v[k]:
        return [0.0, 1.0, 0.0]
    return [math.copysign(1.0, v[k]) if i == k else 0.0 for i in range(3)]


class Assembly:
    def __init__(self, rows):
        """rows: [(id, LDraw part, colour, pos, rot)] (lesson.placed)."""
        self.where = {nid: (nid, ref, pos, rot) for nid, ref, c, pos, rot in rows}
        placed = list(self.where.values())
        self.feats = lego_model._world(placed)
        self.joins = lego_model.connections(placed)
        self.touch = lego_model.touching(placed)
        for k, v in clip_joins(self.where, self.touch).items():  # clips onto bars: not marked in the parts
            self.joins.setdefault(k, v)
        for k, v in soft_joins(self.where, self.touch).items():  # balls in sockets, tyres on rims, hose ends
            self.joins.setdefault(k, v)
        self.boxes = {nid: lego_model.world_box(w[1], w[2], w[3]) for nid, w in self.where.items()}
        self.centre = {nid: [(b[i] + b[i + 3]) / 2 for i in range(3)] for nid, b in self.boxes.items() if b}
        self.vox = {}
        self.figs = {x for k, v in self.joins.items() if v[0] == "fig" for x in k}  # minifigure parts
        self.figs |= {nid for nid, w in self.where.items()  # and other figures (Fabuland, Duplo, Scala), and what
                      if re.search(r"^(minifig|figure|fabuland|duplo figure|scala figure)\b",  # they carry
                                   lego_model.library_title(lego_model.resolve(w[1])).lower().lstrip("~_=| "))}
        self.fastens = {}
        self._near, self._memo, self._stop = {}, {}, {}
        for k in self.joins:
            for x in k:
                self.fastens.setdefault(x, set()).update(set(k) - {x})

    def approach(self, nid, built):
        d, partners = self._approach(nid, built)[:2]
        s = self.stop_way(nid)
        if s and partners and all(r == "into" for r, _ in partners) and abs(sum(d[k] * s[k] for k in range(3))) > 0.9:
            d = s  # pushed into holes along its axis: free end first (its stop is wider than the hole); put onto an
            # axle (the axle into its bush) it goes the other way, bush first
        return d, partners

    def stop_way(self, nid):
        """A part with a stop (an axle with stop, a long pin with stop bush): the stop is wider than any hole, so it
        goes in free end first (42124 booklet 66: the 5.5 axle from inside the frame, its stop staying inside). The
        way it moves, from its stop end toward its free end, from the part's own shape: the wider end is the stop."""
        if nid in self._stop:
            return self._stop[nid]
        _, ref, pos, rot = self.where[nid]
        title = (lego_model.library_title(lego_model.resolve(ref)) or "").lower()
        out = None
        axis = next((a for k, _, a in self.feats.get(nid, []) if k == "pin"), None)
        if "stop" in title and axis:
            pts = [[pos[i] + lego_model._apply(rot, list(v))[i] for i in range(3)]
                   for _, tri in lego_model.mesh_low(ref) for v in tri]
            if pts:
                c = [sum(q[i] for q in pts) / len(pts) for i in range(3)]
                t = [sum((q[i] - c[i]) * axis[i] for i in range(3)) for q in pts]
                lo, hi = min(t), max(t)
                r = [math.dist(q, [c[i] + x * axis[i] for i in range(3)]) for q, x in zip(pts, t)]
                k = max(range(len(r)), key=r.__getitem__)  # the widest point is the stop (not always at the very end)
                typical = sorted(r)[len(r) // 2]
                if r[k] - typical > 1 and abs(t[k] - (lo + hi) / 2) > (hi - lo) * 0.15:
                    sign = 1 if t[k] < (lo + hi) / 2 else -1  # move from the stop's side toward the free end
                    out = [sign * axis[i] for i in range(3)]
        self._stop[nid] = out
        return out

    def locked(self, nid, built):
        """True if the piece would have to go on two ways at once: its joins to pieces already built point along
        different axes (an angle connector onto an axle end AND onto a pin already in a beam)."""
        return self._approach(nid, built)[2]

    def _approach(self, nid, built):
        dirs, partners, free = [], [], set()
        for k, (how, a, ap, b, bp) in self.joins.items():
            other = (set(k) - {nid}).pop() if nid in k and len(k) == 2 else None
            if not other or other not in built:
                continue
            if how == "clutch":  # a's stud goes into b
                n = int(ap.split(".")[1]) - 1
                studs = [f for f in self.feats[a] if f[0] == "stud"]
                ax = studs[n][2] if n < len(studs) else [0, -1, 0]
                dirs.append([-x for x in ax] if b == nid else list(ax))
                rel = ("on" if ax[1] < -0.7 else "under" if ax[1] > 0.7 else "onto the side of") if b == nid else \
                      ("under" if ax[1] < -0.7 else "on" if ax[1] > 0.7 else "onto the side of")
            elif how in ("ball", "tyre", "hose", "fig"):  # pressed straight on, towards the other piece
                c0, c1 = self.centre.get(other, [0] * 3), self.centre.get(nid, [0] * 3)
                t = lego_model.library_title(lego_model.resolve(self.where[nid][1])).lower()
                if how == "fig" and re.search(r"torso|head|helmet|hat\b|cap\b|hair|vest|tank|armou?r|cape|neck|hood|"
                                              r"crown|bandana", t) and "visor" not in t:
                    dirs.append([0.0, 1.0, 0.0] if nid != a else [0.0, -1.0, 0.0])  # down over the neck / onto the hips
                elif how == "fig" and re.search(r"\bleg\b", t):
                    dirs.append([0.0, -1.0, 0.0] if nid != a else [0.0, 1.0, 0.0])  # up into the hips
                else:
                    dirs.append(_axis([c0[i] - c1[i] for i in range(3)]))
                rel = {"ball": "onto the ball of" if nid == a else "into the socket of", "tyre": "onto", "hose": "onto",
                       "fig": "onto" if nid != a else "under"}[how]
            elif how == "clip":  # a bar pushed into a clip: from the bar's side of the clip
                c0, c1 = self.centre.get(other, [0] * 3), self.centre.get(nid, [0] * 3)
                dirs.append(_axis([c0[i] - c1[i] for i in range(3)]))  # straight towards the other piece
                rel = "into the clip of" if nid != a else "onto"
            else:  # a pin or axle along a hole: slide along the axis, from the new piece's side
                pins = [f for f in self.feats[a] if f[0] == "pin"]
                ax = pins[0][2] if pins else [1, 0, 0]
                side = sum((self.centre.get(nid, [0] * 3)[i] - self.centre.get(other, [0] * 3)[i]) * ax[i] for i in range(3))
                dirs.append([-x for x in ax] if side > 0 else list(ax))
                rel = "onto the axle of" if a == other else "into"
                if a != other:  # it is the pin: it may pass through one hole into the next, so it never locks
                    free.add(len(dirs) - 1)
            partners.append((rel, other))
        touching = [(set(k) - {nid}).pop() for k in self.touch if nid in k and len(k) == 2
                    and (set(k) - {nid}).pop() in built]
        if not dirs:  # a tyre goes onto its rim along the rim's axle hole (tyres and rims are not marked as joined)
            title = lambda i: lego_model.library_title(lego_model.resolve(self.where[i][1])).lower()
            for other in touching:
                pair = (title(nid), title(other))
                if any(re.search(r"\btyre|\btire", a) and re.search(r"wheel|\brim\b|hub", b) for a, b in (pair, pair[::-1])):
                    rim = other if re.search(r"wheel|\brim\b|hub", pair[1]) else nid
                    holes = [f for f in self.feats.get(rim, []) if f[0] in ("hole", "pin")]
                    ax = holes[0][2] if holes else None
                    if ax is None:  # no hole marked: the rim's thinnest side is its axle
                        b = self.boxes[rim]
                        k = min(range(3), key=lambda i: b[i + 3] - b[i])
                        ax = [1.0 if i == k else 0.0 for i in range(3)]
                    c0, c1 = self.centre.get(other, [0] * 3), self.centre.get(nid, [0] * 3)
                    side = sum((c1[i] - c0[i]) * ax[i] for i in range(3))
                    dirs.append([-x for x in ax] if side > 0 else list(ax))
                    partners.append(("onto" if rim == other else "into", other))
                    break
        if not dirs:  # fastens to nothing it touches: it goes on towards what it rests against (down onto a piece
            # below it, sideways against a piece beside it), straight along the main axis
            partners = [("next to", touching[0])] if touching else []
            b = self.boxes.get(nid)
            over = lambda o: self.boxes.get(o) and all(min(b[i + 3], self.boxes[o][i + 3]) - max(b[i], self.boxes[o][i]) > 2
                                                         for i in (0, 2))
            if b and any(over(o) and abs(self.boxes[o][1] - b[4]) <= 4 for o in touching):
                return [0.0, 1.0, 0.0], partners, False  # sits on a piece below it: down onto it
            if b and any(over(o) and abs(self.boxes[o][4] - b[1]) <= 4 for o in touching):
                return [0.0, -1.0, 0.0], partners, False  # under a piece above it: up into it
            if touching:
                c = self.centre.get(nid, [0] * 3)
                v = [sum(self.centre.get(o, c)[i] for o in touching) / len(touching) - c[i] for i in range(3)]
                return _axis(v), partners, False
            return [0.0, 1.0, 0.0], partners, False
        # several joins: the way most of them go (a stud and a pin of one piece cannot both be pushed along the mean)
        best = max(dirs, key=lambda v: sum(1 for w in dirs if sum(v[i] * w[i] for i in range(3)) > 0.9))
        agree = [w for w in dirs if sum(best[i] * w[i] for i in range(3)) > 0.9]
        held = [v for k, v in enumerate(dirs) if k not in free]  # ways it is pushed onto what holds it
        split = any(sum(held[0][i] * w[i] for i in range(3)) < 0.9 for w in held[1:])
        return _unit([sum(v[i] for v in agree) for i in range(3)]), partners, split

    def voxels(self, nid):
        if nid not in self.vox:
            _, ref, pos, rot = self.where[nid]
            out = set()
            for code, tri in lego_model.mesh(ref):
                if code == "24":
                    continue
                w = [[pos[i] + lego_model._apply(rot, list(p))[i] for i in range(3)] for p in tri]
                n = max(1, int(max(math.dist(w[0], w[1]), math.dist(w[1], w[2]), math.dist(w[0], w[2])) / 2))
                for i in range(n + 1):
                    for j in range(n + 1 - i):
                        a, b = i / n, j / n
                        q = [w[0][k] + a * (w[1][k] - w[0][k]) + b * (w[2][k] - w[0][k]) for k in range(3)]
                        out.add((math.floor(q[0] / VOX), math.floor(q[1] / VOX), math.floor(q[2] / VOX)))
            self.vox[nid] = out
        return self.vox[nid]

    def near(self, nid, pad):
        """Pieces whose boxes come within pad LDU of this one's (fixed for the model; cached)."""
        key = (nid, pad)
        if key not in self._near:
            b = self.boxes.get(nid)
            self._near[key] = frozenset(o for o, ob in self.boxes.items() if b and ob and o != nid and all(
                min(b[i + 3] + pad, ob[i + 3]) - max(b[i] - pad, ob[i]) > 0 for i in range(3)))
        return self._near[key]

    def _cached(self, kind, nid, d, built, pad, fn):
        """fn's answer depends only on the built pieces near the piece: remember it per (piece, way, those pieces)."""
        key = (kind, nid, tuple(round(x, 3) for x in d), frozenset(self.near(nid, pad) & set(built)))
        if key not in self._memo:
            self._memo[key] = fn(nid, d, key[3])
        return self._memo[key]

    def flexible(self, nid):
        import re
        ref = self.where[nid][1]
        return bool(re.search(FLEX, (lego_model.library_title(lego_model.resolve(ref)) or ref).lower()))

    def reach(self, nid, built):
        """How far the piece travels to its place: its own size and a bit, or, threaded onto an axle already in
        (a bush, a gear), all the way from the axle's end."""
        b = self.boxes.get(nid)
        if not b:
            return 0
        far = max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) + 40
        for o in self.fastens.get(nid, set()) & set(built):
            how, a = self.joins.get(frozenset((nid, o)), ("", ""))[:2]
            if how == "pin" and a == o and self.long_axle(o):
                ob = self.boxes[o]
                far = max(far, max(ob[3] - ob[0], ob[4] - ob[1], ob[5] - ob[2]) + 40)
        return far

    def threads(self, nid, step):
        """The axles of this step the piece is threaded onto (a bush held in a frame while the axle is pushed in)."""
        return [o for o in self.fastens.get(nid, set()) & set(step)
                if self.joins.get(frozenset((nid, o)), ("", ""))[:2] == ("pin", o)
                and self.long_axle(o)]

    def way_in(self, nid, built):
        """approach(), but a pin or axle pushed through holes may go in from either end: the other end if that one
        is clear and the first is not."""
        d, partners = self.approach(nid, built)
        if partners and all(r == "into" for r, _ in partners) and not self.stop_way(nid) \
                and not self.clear(nid, d, built)[0]:
            back = [-x for x in d]
            if self.clear(nid, back, built)[0]:
                return back, partners
        return d, partners

    def long_axle(self, nid):
        """A plain axle (not an axle pin, joiner or connector): things can be threaded onto it."""
        t = lego_model.library_title(lego_model.resolve(self.where[nid][1])) or ""
        return lego_model.is_axle(self.where[nid][1]) and "pin" not in t.lower()

    def must_thread(self, nid, step, built):
        """The axles of this step the piece must be held in place for: once that axle is in, the piece cannot slide
        on any more (a bush inside a frame). A bush that can slide on after (on the axle's free end) is not one."""
        out = []
        for a in self.threads(nid, step):
            after = set(built) | {a}
            if not self.clear(nid, self.approach(nid, after)[0], after)[0]:
                out.append(a)
        return out

    def clear(self, nid, d, built):
        return self._cached("clear", nid, d, built, self.reach(nid, built), self._clear)

    def _clear(self, nid, d, built):
        """(True, None) if the piece can get to its place along d, else (False, the first piece in the way).
        Flexible pieces (tyres, hoses, cables) bend out of the way: they neither block nor get blocked. Pieces joined
        to each other are made to meet: they do not block each other."""
        b = self.boxes.get(nid)
        if not b or self.flexible(nid):
            return True, None
        reach = self.reach(nid, built)
        mine = self.voxels(nid)
        steps = max(1, int(reach / VOX))
        path = _sweep(mine, d)
        for o in sorted(built, key=_idkey):  # in a fixed order: the same blocker every run
            ob = self.boxes.get(o)
            if not ob or o == nid or o in self.fastens.get(nid, ()) or self.flexible(o) or (
                    nid in self.figs and o in self.figs) or not all(  # a figure's small parts: fingers find a way
                    min(b[i + 3] + reach, ob[i + 3]) - max(b[i] - reach, ob[i]) > 0 for i in range(3)):
                continue
            theirs = self.voxels(o)
            base = len(mine & theirs)
            for s in range(1, steps + 1):  # every cube along the path
                if len(path(s) & theirs) > base + 3:
                    return False, o
        return True, None

    FINGER, DEPTH = 6, 6  # cubes (4 LDU): a fingertip about 1.2 studs across, reaching 3 plates deep

    def finger_room(self, nid, d, built):
        return self._cached("finger", nid, d, built, 30, self._finger_room)

    def _finger_room(self, nid, d, built):
        """(True, None) if a fingertip can press the piece home: behind the face it is pressed on (opposite its way
        in) a fingertip-sized column, FINGER x FINGER cubes across and DEPTH deep, is free of pieces already built.
        Else (False, the built piece most in the way): it would need tweezers. Pieces joined to it do not count
        (it is pressed onto them)."""
        if self.flexible(nid) or not self.boxes.get(nid):
            return True, None
        d = _axis(d)
        k = max(range(3), key=lambda i: abs(d[i]))
        sgn = int(math.copysign(1, d[k]))
        mine = self.voxels(nid)
        back = [v for v in mine if (v[0] - (sgn if k == 0 else 0), v[1] - (sgn if k == 1 else 0),
                                    v[2] - (sgn if k == 2 else 0)) not in mine]  # the face pressed on
        if not back:
            return True, None
        b = self.boxes[nid]
        near = {}
        joined = self.fastens.get(nid, set())
        for o in sorted(built, key=_idkey):
            ob = self.boxes.get(o)
            if o == nid or o in joined or self.flexible(o) or not ob or not all(
                    min(b[i + 3] + 30, ob[i + 3]) - max(b[i] - 30, ob[i]) > 0 for i in range(3)):
                continue
            for v in self.voxels(o):
                near[v] = o
        if not near:
            return True, None
        u, w = [i for i in range(3) if i != k]
        cand = back[:: max(1, len(back) // 25)]
        worst = {}
        h = self.FINGER // 2
        for c in cand:
            hits = {}
            for depth in range(1, self.DEPTH + 1):
                for du in range(-h, h):
                    for dw in range(-h, h):
                        q = list(c)
                        q[k] -= sgn * depth
                        q[u] += du
                        q[w] += dw
                        o = near.get(tuple(q))
                        if o is not None:
                            hits[o] = hits.get(o, 0) + 1
            if not hits:
                return True, None
            o = max(hits, key=hits.get)
            worst[o] = worst.get(o, 0) + hits[o]
        return False, max(worst, key=worst.get)

    def clear_block(self, ids, d, built):
        """clear() for a finished block (a sub-assembly) pushed on as one along d."""
        ids = set(ids)
        bs = [self.boxes[i] for i in ids if self.boxes.get(i)]
        if not bs:
            return True, None
        b = [min(x[k] for x in bs) for k in range(3)] + [max(x[k + 3] for x in bs) for k in range(3)]
        reach = max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) + 40
        steps = max(1, int(reach / VOX))
        solid = [i for i in ids if not self.flexible(i)]
        whole = set().union(*(self.voxels(i) for i in solid))
        for o in sorted(built, key=_idkey):
            ob = self.boxes.get(o)
            if not ob or o in ids or self.flexible(o) or not all(
                    min(b[i + 3] + reach, ob[i + 3]) - max(b[i] - reach, ob[i]) > 0 for i in range(3)):
                continue
            # only the block's pieces joined to o may meet it (an axle goes through the frame, its bushes may not)
            met = [i for i in solid if o in self.fastens.get(i, ())]
            mine = whole if not met else set().union(*(self.voxels(i) for i in solid if i not in met))
            if not mine:
                continue
            theirs = self.voxels(o)
            base = len(mine & theirs)
            # the block moved s back along -d meets o as o moved s along +d meets the block: o is one piece, the
            # block many, so o is the one moved (the same counts, far fewer cubes made: 7635-1's check 96 s -> 10 s)
            for s in range(1, steps + 1):
                sh = [round(-d[i] * s) for i in range(3)]
                if sum((v[0] - sh[0], v[1] - sh[1], v[2] - sh[2]) in mine for v in theirs) > base + 3:
                    return False, o
        return True, None

    def order_step(self, pieces, built):
        """The step's pieces in an order that can be built: each time the first piece (in the given order) that can
        get to its place without shutting out another piece of the step. Returns [(id, direction, partners, blocker
        or None)] (blocker: no order lets it in)."""
        built, left, out = set(built), list(pieces), []
        if built:  # a group of this step that meets nothing built is a new start: its main piece first (base first)
            new, todo = set(), [i for i in left if not (self.fastens.get(i, set()) & built)]
            reach = {i for i in left if self.fastens.get(i, set()) & built}
            stack = list(reach)
            while stack:  # everything joined (within the step) to a piece that meets what is built
                x = stack.pop()
                for o in self.fastens.get(x, set()) & set(left) - reach:
                    reach.add(o)
                    stack.append(o)
            alone = [i for i in left if i not in reach]
            if len(alone) >= 2 and len(alone) < len(left) or (alone and not reach and len(alone) >= 2):
                for x in self.order_step(alone, set()):
                    out.append(x)
                built |= set(alone)
                left = [i for i in left if i not in alone]
        while left:
            pick, fallback, held = None, None, None
            from graph.lego_3d.lesson import _attach_order
            touch = {}
            for k in self.touch:
                for x in k:
                    touch.setdefault(x, set()).update(set(k) - {x})
            can = set(_attach_order(left, built, self.fastens, touch)[0][:1]) | {
                i for i in left if (self.fastens.get(i) or touch.get(i, set())) & built}
            can |= {i for i in left if built and touch.get(i, set()) & built
                    and self.must_thread(i, left, built)}  # held while the axle goes in
            if not built:  # a new group starts from its main piece: the one most of the others fasten to, then the biggest
                def size(i):
                    b = self.boxes.get(i)
                    return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2]) if b else 0
                import re
                small = lambda i: bool(re.search(r"\bpin\b|\baxle\b|\bbush\b", lego_model.library_title(self.where[i][1]).lower())
                                       and (self.fastens.get(i, set()) & set(left)))  # pins go into the main piece
                mid = [sum(self.centre.get(i, [0] * 3)[k] for i in left) / len(left) for k in range(3)]
                inner = lambda i: sum((self.centre.get(i, mid)[k] - mid[k]) ** 2 for k in range(3))
                # LEGO builds from the inside out: the piece the others connect through, the one nearest the middle
                # (42124 booklet 77-79: cross block, red pins, beam, and the big motor last)
                cands = sorted(left, key=lambda i: (self.flexible(i) or "_subpart" in self.where[i][1], small(i),
                                                    -len(self.fastens.get(i, set()) & set(left)), inner(i)))
            else:
                cands = left
            if not built and cands:  # a new group starts from its main piece, whatever comes after it
                nid = cands[0]
                d, partners = self.way_in(nid, built)
                left.remove(nid)
                c0 = self.centre.get(nid, [0] * 3)  # then outwards from it, nearest first (inside out)
                vols = sorted(size(i) for i in left)
                big = lambda i: len(left) > 1 and size(i) > 4 * vols[len(vols) // 2]  # a big part (a motor) goes
                # on last: the small pieces around it are put on while they can still be reached (42124 block 42)
                left.sort(key=lambda i: (big(i), sum((self.centre.get(i, c0)[k] - c0[k]) ** 2 for k in range(3))))
                built.add(nid)
                out.append((nid, d, partners, None))
                continue
            for nid in cands:  # a piece that can get in now, and does not shut out another piece of this step
                if built and nid not in can:
                    continue  # it would float: what it clicks onto is not on yet
                d, partners = self.way_in(nid, built)
                if built and not (self.fastens.get(nid, set()) & built) and self.must_thread(nid, left, built):
                    held = held or (nid, d, partners, None)  # held in place, its axle through it next: only once
                    continue                                 # the pieces that simply go on are on
                if built and any(nid in self.must_thread(o, left, built) for o in left
                                 if o != nid and not (self.fastens.get(o, set()) & built)):
                    continue  # an axle waits for the pieces threaded onto it
                ok, _ = self.clear(nid, d, built)
                if not ok or self.locked(nid, built):
                    continue
                after = built | {nid}
                reach = lambda o: nid in self.near(o, (lambda b: max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) + 40)(
                    self.boxes[o]) if self.boxes.get(o) else 0)  # only nearby pieces can be shut out
                shuts = [o for o in left if o != nid and reach(o) and self.clear(o, self.way_in(o, built)[0], built)[0]
                         and not self.clear(o, self.way_in(o, after)[0], after)[0]]
                # nor locks one in: it would then have to go on two ways at once
                shuts += [o for o in left if o != nid and nid in self.fastens.get(o, ()) and not self.locked(o, built)
                          and self.locked(o, after)]
                # nor takes away the room a finger needs to press another piece of this step home
                crowds = [] if shuts else [o for o in left if o != nid and nid in self.near(o, 30)
                                           and self.finger_room(o, self.way_in(o, built)[0], built)[0]
                                           and not self.finger_room(o, self.way_in(o, after)[0], after)[0]]
                room = self.finger_room(nid, d, built)[0]
                if not shuts and not crowds and room:
                    pick = (nid, d, partners, None)
                    break
                if not shuts and (fallback is None or fallback[4] > len(crowds) + (not room)):
                    fallback = (nid, d, partners, None, len(crowds) + (not room))
                fallback = fallback or (nid, d, partners, None, 99)
            onto = fallback and self.fastens.get(fallback[0], set()) & built  # it presses onto something already on
            pick = pick or (fallback[:4] if onto else None)
            if not pick and held:  # a held piece waits for every piece that presses onto what is built (its path test
                waits = {a for h in left if not (self.fastens.get(h, set()) & built)  # may be wrong: 42124 booklet 63-64)
                         for a in self.must_thread(h, left, built)}  # axles that held pieces are waiting for
                press = next((i for i in left if i != held[0] and self.fastens.get(i, set()) & built
                              and i not in waits), None)
                if press:
                    d, partners = self.way_in(press, built)
                    pick = (press, d, partners, self.clear(press, d, built)[1])
            pick = pick or held or (fallback[:4] if fallback else None)
            if pick is None:  # nothing fits cleanly: take the first piece that at least fastens to what is built
                nid = next((i for i in left if not built or not self.fastens.get(i) or self.fastens[i] & built), left[0])
                d, partners = self.way_in(nid, built)
                pick = (nid, d, partners, self.clear(nid, d, built)[1])
            if pick is None:
                nid = left[0]
                d, partners = self.way_in(nid, built)
                pick = (nid, d, partners, self.clear(nid, d, built)[1])
            left.remove(pick[0])
            built.add(pick[0])
            out.append(pick)
        return out


def in_hand(pieces, built, asm):
    """Technic groups LEGO puts together in the hand (its boxed sub-builds): pieces of the step pinned to each other
    that meet the model in one push (through one piece, or several going on the same way). Returns [(group, the piece that goes into the model)]."""
    if not built:
        return []
    pinned = lambda a, b: asm.joins.get(frozenset((a, b)), ("",))[0] == "pin"

    def connected(g):
        seen, todo = set(), [next(iter(g))]
        while todo:
            x = todo.pop()
            seen.add(x)
            todo += [o for o in asm.fastens.get(x, set()) & g - seen if pinned(x, o)]
        return seen == g
    left, out = set(pieces), []
    while left:
        seed = min(left, key=pieces.index)
        g, todo = {seed}, [seed]
        while todo:
            x = todo.pop()
            for o in asm.fastens.get(x, set()) & left - g:
                if pinned(x, o):
                    g.add(o)
                    todo.append(o)
        left -= g
        links = [i for i in g if asm.fastens.get(i, set()) & built]
        ways = {i: asm.approach(i, built)[0] for i in links}  # several links are fine if one push sets them all
        same = lambda a, b: sum(ways[a][k] * ways[b][k] for k in range(3)) > 0.9
        best = None
        swivel = any(re.search(SWIVEL, lego_model.library_title(lego_model.resolve(asm.where[i][1])).lower()) for i in g)
        if swivel and len(links) > 1 and connected(g):  # a toggle joint or hinge in it: its ends find their ways one
            best = set(g)                               # after the other (42124 booklet 103)
        for i in ([] if best else links):  # links going on another way stay out of the block: they go on after it (42124 booklet 75)
            sub = g - {j for j in links if not same(i, j)}
            if len(sub) >= 2 and connected(sub) and (best is None or len(sub) > len(best)):
                best = sub
        while best and len(best) >= 2:  # nor may the block shut out the step's other pieces (42124 booklet 75-76)
            after = set(built) | best
            stuck = [b for o in set(pieces) - best for ok, b in [asm.clear(o, asm.approach(o, after)[0], after)]
                     if not ok and b in best and b not in links]
            # nor lock one in: a piece left that would then go onto the block and the model two ways at once
            stuck += [b for o in set(pieces) - best if asm.locked(o, after) and not asm.locked(o, built)
                      for b in sorted(asm.fastens.get(o, set()) & best - set(links), key=pieces.index)[:1]]
            if not stuck or not connected(best - {stuck[0]}):
                break
            best = best - {stuck[0]}
        while best and len(best) >= 2:  # pushed in as one, a piece on its axle must not hit the model (a bush that
            # sits inside a frame goes on after, held there: 42124 booklet 97); one on the axle's outer end is fine
            link = min((j for j in links if j in best), key=pieces.index)
            ok, hit = asm.clear_block(best, asm.approach(link, built)[0], built)
            on_axle = [i for i in best if i not in links and any(a in best for a in asm.threads(i, best))]
            if ok or not on_axle:
                break
            near = lambda i: min(sum((asm.centre[i][k] - asm.centre.get(hit, asm.centre[i])[k]) ** 2 for k in range(3))
                                 for _ in [0])
            drop = min(on_axle, key=near)
            if not connected(best - {drop}):
                break
            best = best - {drop}
        if best and any(asm.joins.get(frozenset((o, b)), ("", ""))[:2] == ("pin", o) and asm.fastens.get(o, set()) - best
                        for o in set(pieces) - best for b in asm.fastens.get(o, set()) & best):
            best = None  # a pin left over would be pushed through the block into the model: build it piece by piece,
            # pins first and what spans them last (42124: yellow 2-hole beam over the fairing pins)
        if best and len(best) >= 2:
            out.append((sorted(best, key=pieces.index), min((j for j in links if j in best), key=pieces.index)))
    return out


@functools.lru_cache(maxsize=8)
def of(set_id):
    from graph.lego_3d import lesson  # here: lesson imports this module
    return Assembly(lesson.placed(set_id))


# ---- the 3D hint viewer: the model so far, and the step's new pieces flying into place -----------------------
HTML = pathlib.Path(__file__).with_name("lesson_viewer.html")


def _short(name):
    return re.sub(r"\s+", " ", name).replace(" x ", "×").strip()


def copies(pieces, asm):
    """A step that builds the same thing several times (four wheels): its pieces split into groups joined among
    themselves, all with the same pieces (part and colour). Returns the groups (one group when there are no copies)."""
    left, groups = set(pieces), []
    near = lambda i: (asm.fastens.get(i, set()) | {(set(k) - {i}).pop() for k in asm.touch if i in k and len(k) == 2})
    while left:
        seed = min(left, key=lambda i: pieces.index(i))
        g, todo = {seed}, [seed]
        while todo:
            for o in near(todo.pop()) & left - g:
                g.add(o)
                todo.append(o)
        left -= g
        groups.append(sorted(g, key=pieces.index))
    sig = lambda g: sorted((asm.where[i][1], next(r[2] for r in ROWS[0] if r[0] == i)) for i in g)
    if len(groups) > 1 and all(sig(g) == sig(groups[0]) for g in groups):
        return groups
    return [list(pieces)]


ROWS = [()]


def choose_view(sight, new, last):
    """The view a step is shown from: the last one if it shows every new piece, else the one that shows them best
    (from above when it can). `turn` when it goes from above to below or back: the model is turned over."""
    from graph.lego_3d.assembly import VIEWS
    if not new:
        return last, False
    score = {v: min(sight.seen(i, v) for i in new) for v in VIEWS}
    ok = [v for v in VIEWS if score[v] >= 0.15]
    if last in ok:
        return last, False
    view = max(VIEWS, key=lambda v: (v in ok, v[1] < 0, score[v]))
    return view, bool(last and (last[1] < 0) != (view[1] < 0))


def swings(nid, built, asm, step=()):
    """Arms that can turn out of the way: built pieces touching nid that hang on one pin line only (one round pin,
    or pins on one axis), so a hand can swing them aside, put nid in, and swing them back (42124 booklet 64)."""
    out = []
    for n in sorted(built, key=lambda i: (len(i), i)):
        t = (lego_model.library_title(lego_model.resolve(asm.where[n][1])) or "").lower()
        if n in asm.figs or frozenset((n, nid)) not in asm.touch or n in asm.fastens.get(nid, set()):
            continue  # not a neighbour, or the piece goes into it (then it must stay where it is)
        if not re.search(r"beam|liftarm", t):  # only arms: beams and liftarms, not pins or connectors
            continue
        if not any(n in asm.fastens.get(x, set()) and nid in asm.fastens.get(x, set()) for x in step if x != nid):
            continue  # nothing in this step goes into both the arm and the piece: the arm need not move
        on = asm.fastens.get(n, set()) & built
        joins = [asm.joins.get(frozenset((n, o))) for o in on]
        if not on or any(j is None or j[0] != "pin" for j in joins):
            continue
        b = asm.boxes[n]
        inside = lambda p: all(b[k] - 2 <= p[k] <= b[k + 3] + 2 for k in range(3))
        pins = [(p, a) for o in on for kind, p, a in asm.feats.get(o, []) if kind == "pin" and inside(p)]
        axled = lambda o: asm.long_axle(o) or "axle" in (lego_model.library_title(lego_model.resolve(asm.where[o][1])) or "").lower()
        if not pins or any(axled(o) for o in on):  # on an axle (or an axle pin's cross end) it cannot turn
            continue
        p0, a0 = pins[0]
        line = all(abs(abs(sum(a[k] * a0[k] for k in range(3))) - 1) < 1e-3  # all on one axis line
                   and math.dist([p[k] - p0[k] for k in range(3)],
                                 [sum((p[j] - p0[j]) * a0[j] for j in range(3)) * a0[k] for k in range(3)]) < 2
                   for p, a in pins)
        if line:
            out.append({"piece": n, "at": [round(p0[0], 2), round(-p0[1], 2), round(p0[2], 2)],
                        "axis": [round(a0[0], 4), round(-a0[1], 4), round(a0[2], 4)]})
    return out


def substeps(steps, rows, pieces_info):
    """Each step piece by piece, in an order that can really be built (assembly.py): the direction each piece goes
    on, a one-line instruction from what it fastens to, and whether something already built is in its way."""
    from graph.lego_3d import assembly
    asm = assembly.Assembly(rows)
    ROWS[0] = rows
    info = {p["id"]: p for p in pieces_info}
    label = lambda i: f"{info[i]['colour'].lower()} {_short(info[i]['name'])}" if i in info else i
    import collections
    model, side, out, blocked = set(), collections.defaultdict(set), [], 0
    sight = collections.defaultdict(lambda: assembly.Sightlines(asm))  # what each section shows from the 8 views
    last_view = {}
    for st in steps:
        subs = []
        attach_dir = None
        if st.get("attach") in side:  # a finished sub-assembly joins the model, along the way its joins go
            block = side.pop(st["attach"])
            into = side[st["subassembly"]] if st.get("subassembly") else model  # or into a bigger sub-assembly
            dirs = [asm.approach(i, into)[0] for i in block if asm.fastens.get(i, set()) & into]
            if dirs:
                v = [sum(d[k] for d in dirs) for k in range(3)]
                n = math.sqrt(sum(x * x for x in v)) or 1.0
                attach_dir = [round(v[0] / n, 3), round(-v[1] / n, 3), round(v[2] / n, 3)]
            into |= block
            for i in block:
                sight[st.get("subassembly") or ""].add(i)
        built = side[st["subassembly"]] if st.get("subassembly") else model
        sec = st.get("subassembly") or ""
        view, turn = choose_view(sight[sec], [i for i in st["pieces"] if asm.voxels(i)], last_view.get(sec))  # built off to the side: meets only itself
        # pieces drawn apart but sold as one (a motor's cable: '..._subpart1.ldr') come with the piece they belong to
        extra = [i for i in st["pieces"] if "_subpart" in asm.where[i][1]]
        st = dict(st, pieces=[i for i in st["pieces"] if i not in extra])
        groups = copies(st["pieces"], asm)
        first = set(groups[0]) if len(groups) > 1 else set(st["pieces"])
        rest = list(st["pieces"])
        fresh = not built  # a new group: its pieces go on one by one, never as a block pushed into the lone start
        # piece at the end (42124 block 42: the motor with its pins and cross block, pushed into the 5-hole beam last)
        if not built and len(rest) > 2:  # a new group: its main piece down first, then blocks made in the hand go onto it
            plan = asm.order_step(rest, set())  # its start piece, then the rest inside out, a big part last
            nid, d, partners, _ = plan[0]
            rest = [x[0] for x in plan]
            subs.append({"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)],
                         "text": f"Put the {label(nid)} down to start.", "blocked": False, "copy": nid not in first})
            built.add(nid)
            rest.remove(nid)
        # a step that joins several official steps is played one official step at a time, in LEGO's order: blocks
        # made in the hand never mix them (42124 booklet: the cross block onto the axle pin, then its half pin)
        offi = {p["id"]: p.get("official_step") or 0 for p in pieces_info}
        for rest in [[i for i in rest if offi.get(i, 0) == o] for o in sorted({offi.get(i, 0) for i in rest})]:
            for g, link in ([] if fresh else assembly.in_hand(list(rest), built, asm)):  # put together in the hand, then pushed on as one block
                d0, partners0 = asm.approach(link, built)
                for nid, d, partners, blocker in asm.order_step(g, set()):
                    rel, other = partners[0] if partners else (None, None)
                    text = (f"In your hand: put the {label(nid)} {rel} the {label(other)}." if other
                            else f"In your hand: take the {label(nid)}.")
                    subs.append({"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)], "text": text,
                                 "blocked": False, "copy": nid not in first, "hand": [round(d0[0], 3), round(-d0[1], 3), round(d0[2], 3)]})
                rel, other = partners0[0] if partners0 else ("onto", None)
                subs.append({"piece": link, "group": g, "dir": [round(d0[0], 3), round(-d0[1], 3), round(d0[2], 3)],
                             "text": f"Push the block you made {rel} the {label(other)}." if other else "Put the block in place.",
                             "blocked": False, "copy": False})
                built |= set(g)
                rest = [i for i in rest if i not in g]
            for nid, d, partners, blocker in asm.order_step(rest, built):
                rel, other = partners[0] if partners else (None, None)
                text = f"Put the {label(nid)} {rel} the {label(other)}." if other else f"Put the {label(nid)} down to start."
                axle = [] if asm.fastens.get(nid, set()) & built else asm.must_thread(
                    nid, [i for i in rest if i not in built], built - {nid})  # held: only what has nothing to go onto yet
                if axle:  # threaded: held in its place, lined up with the holes the axle comes through (42124 booklet 64)
                    via = sorted(asm.fastens.get(axle[0], set()) & built - {nid}, key=lambda i: (len(i), i))
                    into = f"through the {label(via[0])} into it" if via else "into it"
                    text = (f"Hold the {label(nid)} in its place, lined up with the holes: next the "
                            f"{label(axle[0])} is pushed {into}.")
                sub = {"piece": nid, "dir": [round(d[0], 3), round(-d[1], 3), round(d[2], 3)], "text": text,
                       "blocked": blocker is not None, "copy": nid not in first}
                arms = swings(nid, built, asm, [i for i in rest if i not in built]) if axle or blocker is not None else []
                if arms:  # tight fit: turn the arms aside on their pin, put it in, turn them back
                    kinds = list(dict.fromkeys(label(a["piece"]) for a in arms))
                    names = " and ".join(kinds) if len(kinds) > 1 or len(arms) == 1 else f"two {kinds[0]}s"
                    pins = "its pin" if len(arms) == 1 else "their pins"
                    sub["swing"] = arms
                    sub["text"] = f"Turn the {names} out a little on {pins} to make room. " + text
                subs.append(sub)
                blocked += blocker is not None
                built.add(nid)
        for i in extra:  # with the piece of this step it belongs to (the one it touches, else the first)
            owner = next((x for x in subs if not x.get("group") and frozenset((i, x["piece"])) in asm.touch), subs[0] if subs else None)
            if owner is None:
                continue
            owner["group"] = (owner.get("group") or [owner["piece"]]) + [i]
            built.add(i)
        for i in st["pieces"]:
            sight[sec].add(i)
        last_view[sec] = view
        for x in subs:  # 1:1 lengths: how many studs long an axle or a beam is
            m = re.search(r"\b(?:axle|beam)\s+(\d+(?:\.\d+)?)\b", (info.get(x["piece"]) or {}).get("name", "").lower())
            if m and not x.get("group"):
                x["len"] = float(m.group(1))
        out.append({"subs": subs, "attach_dir": attach_dir, "copies": len(groups) if len(groups) > 1 else 1,
                    "view": [view[0], -view[1], view[2]] if view else None, "turn": turn})
    substeps.blocked = blocked
    return out


def export(set_id, src=None):
    from graph.lego_3d import lesson  # here: lesson imports this module
    d = (src or lesson.OUT) / set_id
    data = json.loads((d / "lesson.json").read_text())
    steps = data["lesson"]["steps"]
    rows = lesson.placed(set_id)
    palette, pal_index, blob, pieces = [], {}, bytearray(), []
    for nid, ref, colour, pos, rot in rows:
        tris = []
        for code, tri in lego_model.mesh_low(ref):
            if code == "24":
                continue
            c = colour if code == "16" else code
            if c not in pal_index:
                pal_index[c] = len(palette)
                palette.append("#%02x%02x%02x" % lego_model.rgb(c))
            pts = [[pos[i] + lego_model._apply(rot, list(p))[i] for i in range(3)] for p in tri]
            tris.append((pal_index[c], pts))
        start = len(blob)
        for _, pts in tris:
            for p in pts:
                blob += struct.pack("<3h", *(max(-32768, min(32767, round(v * 2))) for v in p))
        colours_at = len(blob)
        blob += bytes(c for c, _ in tris)
        if len(blob) % 2:
            blob += b"\0"
        pieces.append({"id": nid, "tris": len(tris), "at": start, "colours_at": colours_at})
    name = data["lesson"].get("title", set_id)
    subs = substeps(steps, rows, data.get("pieces", []))
    out = {"set": set_id, "title": name, "palette": palette, "pieces": pieces,
           "steps": [{"pieces": s["pieces"], "instruction": s["instruction"], "subassembly": s.get("subassembly", ""),
                      "attach": s.get("attach", ""), "bag": s.get("bag"), "substeps": sub["subs"],
                      "attach_dir": sub["attach_dir"], "copies": sub["copies"], "view": sub["view"],
                      "turn": sub["turn"]} for s, sub in zip(steps, subs)]}
    v = d / "viewer"
    v.mkdir(parents=True, exist_ok=True)
    out["geometry"] = __import__("base64").b64encode(bytes(blob)).decode()  # artifacts serve text, not binary files
    (v / "lesson.json").write_text(json.dumps(out))
    page = HTML.read_text().replace("{{TITLE}}", name.split(" ", 1)[-1] or set_id)
    (v / "index.html").write_text(page)
    return v, len(blob)


if __name__ == "__main__":
    args = sys.argv[1:]
    src = pathlib.Path(args.pop(args.index("--from") + 1)) if "--from" in args else None
    if "--from" in args:
        args.remove("--from")
    for s in args:
        v, n = export(s, src)
        print(f"{s}: {v} ({n / 1e6:.1f} MB of geometry)")


if __name__ == "__main__":
    args = sys.argv[1:]
    src = pathlib.Path(args.pop(args.index("--from") + 1)) if "--from" in args else None
    if "--from" in args:
        args.remove("--from")
    for s in args:
        v, n = export(s, src)
        print(f"{s}: {v} ({n / 1e6:.1f} MB of geometry)")
