"""A LEGO lesson from the set's 3D model: Claude plans the steps, code checks they can be built.

What it is   the LEGO recipe of the lesson loop (lessons.py: LegoLessons). The 3D model gives the exact answer
             (every piece, where it sits, what it holds on to), so Claude is shown it as text and asked only for the
             order and the words, starting from a plan code made from LEGO's own steps; code checks the plan
             (S1-S14, W1-W3 below), sends problems back, then puts back LEGO's order and the ways in (fix_order) and
             rewords the steps that changed. A big set is planned bag by bag: Claude reads the booklet only for its
             numbered bags (which steps each bag has, how many of each part from the call-outs), code checks the
             answer (every part in bags as often as the set has it; bags 1, 2, 3 with consecutive steps) and puts
             every piece of the model into a bag (sections, read, assign).
Used for     a lesson for any LEGO set with an LDraw 3D model.
Where        python -m graph.lessons lego <set> (or python -m graph.lego_3d.lesson <set> [--fix-only]), then
             python -m graph.lesson_store build lego <set>; writes data/lessons/lego3d/<set>/ (bags.json beside
             the lesson). Its model_of and placed are also read by lego_booklet/pdf_lesson.py, lego_3d/assembly.py
             and lego_3d/graphs.py.

The checks:
  S1  every piece of the set in exactly one step
  S2  every new piece holds on to something already built (in the main model, or in the sub-assembly it belongs to),
      or to another new piece of the same step that does; the first step of the main model and of each
      sub-assembly may start anywhere
  S3  every sub-assembly is attached to the main model by some step (or into a bigger sub-assembly), as ONE piece:
      a sub-assembly that is still in loose parts cannot be carried (copies, like four wheels, excepted)
  S4  no step has more than MAX_STEP pieces
  S5  steps are not too small: at most SMALL_SHARE of the steps add a single piece
  S7  LEGO's own order (official steps from the 3D model): no piece before a piece of an earlier official step
  S9  LEGO's own sub-builds (sub-models, boxed hand blocks) are built off the model and attached as one, never
      put straight onto the main model; in a sub-assembly no second, separate group is laid beside it (S2)
  W1  the words say what the 3D page shows (what is held, what is pushed through); steps that do not are reworded
      from the page's own actions, after the order fix
  S10 one significant part per step; S11 left/right twins together; S12 a step in one area; S13 one view shows every
      new piece (how people build and read instructions: Agrawala et al. 2003; LEGO's booklets); pieces of one LEGO
      official step always pass
  S8  a finger can press every piece home: no pieces already on crowd the face it is pressed on (no tweezers)
  S6  every piece can really get to its place: slid in along the way it goes on (onto a stud, along an axle), its
      real shape does not pass through a piece built in an earlier step (assembly.py); pieces of one step are put
      on in whatever order lets each in
  S14 nothing is slid in between pieces already on: a piece that sits on another goes on after it, unless it is
      built apart and attached once that one is on (LEGO's own order passes: a support its booklet puts in later)
  W3  no code names in the words ('block 2', 'unit 5', piece ids): say what the thing looks like
Problems go back to Claude (complete corrected plan), up to REPAIRS rounds. Positions for AR come from the model,
never from Claude.

  python -m graph.lego_3d.lesson 31040-1 42031-1 21034-1 [--model sonnet]
Writes data/lessons/lego3d/<set>/lesson.json, lesson.md and stats.json.
"""
import argparse
import collections
import functools
import itertools
import json
import os
import math
import re
import pathlib
import time
from typing import List

from pydantic import BaseModel, Field

from graph import lego_model
from graph.lego_3d.assembly import VIEWS, Sightlines

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(os.environ["LESSON_OUT"]) if os.environ.get("LESSON_OUT") else ROOT / "data" / "lessons" / "lego3d"
MAX_STEP = 8        # S4: the most pieces one step may add
SMALL_SHARE = 0.3   # S5: at most this share of the steps may add a single piece
REPAIRS = 3         # (the lesson loop in lessons.py uses its own REPAIRS)
CHUNK = 150  # sets with more pieces are planned one part of the model at a time


# The answer Claude must return (the schema of every planning and repair turn): code reads it without guessing
class LessonStep(BaseModel):
    pieces: List[str] = Field(description="Ids of the pieces this step adds (b1, b2 ...); may be empty only for a step "
                                          "that attaches a finished sub-assembly")
    subassembly: str = Field(description="'' when the pieces go on the main model; else the name of the sub-assembly "
                                         "they are built into (built on its own, attached later), e.g. 'left wheel'")
    attach: str = Field(description="Name of a finished sub-assembly this step attaches to the main model, else ''")
    instruction: str = Field(description="One or two plain sentences for a child or beginner: which pieces (colour, "
                                         "size, shape), where they go, which way round")


class Lesson(BaseModel):
    title: str
    steps: List[LessonStep]
    notes: List[str]


# Claude's instructions for planning a section and for every repair. Each rule here has a code check in check():
# Claude is told the rule, and code makes sure it was kept
SYSTEM = """You plan a LEGO building lesson for a beginner, from a set's exact 3D model given as text.
You are given every piece (id, name, colour, size, where it sits) and which pieces hold on to which. Plan the steps:
- START FROM THE SUGGESTED PLAN given after the pieces: code made it from LEGO's own steps and lists what the checks
  find wrong with it. Keep what works, merge steps that are too small, split or reorder where it helps a beginner,
  fix the listed problems, and write every instruction.
- FOLLOW LEGO'S OWN ORDER: every piece has its official step. Never put a piece before a piece of an earlier official
  step. You may split a big official step into several steps, merge small consecutive official steps, and build each
  official sub-build as a sub-assembly (its name, then an attach step where the official order places it).
- Every piece in exactly one step. Steps of 3 to 6 pieces, like an official LEGO booklet (never more than 8; a step
  of 1 or 2 pieces only when the piece is big or tricky). Same pieces placed the same way share a step.
- Build so it could really be done by hand: start from the bottom or the base; a new piece must hold on to something
  already built (or to another piece of the same step that does).
- A new sub-assembly or group starts from its main piece, the one the others go into or onto (a beam, a plate, a
  brick), never from loose pins, axles or small parts laid out first: "Take a 7-hole beam. Push four pins into it."
- Small Technic groups that meet the model through one piece (a pin with a cross hole and the pin through it) are put
  together in the hand first, then pushed in as one ("Push a long pin through the side hole of a grey pin, put a
  second grey pin on its other end, then push the block into the beam"), as LEGO's boxed sub-builds do.
- Never ask for a piece to be slid onto an axle that is already through a frame: bushes, gears and joiners that sit on
  an axle inside the model go in the SAME step as that axle, held in their place first, then the axle is pushed
  through them ("Hold two red bushes inside the frame and push the long red axle through the frame and the bushes").
- A piece that would have to go onto two things at once from different sides (an angle connector onto an axle end
  and onto a pin already in a beam) goes on before the second of those things.
- Parts that are built on their own and attached later (a wheel, a wing, a figure, a roof) are SUB-ASSEMBLIES: give
  their steps that sub-assembly's name, then add a step that attaches it (attach = its name). Use them where the
  model naturally has them; otherwise build on the main model. IDENTICAL sub-assemblies are built together: one
  sub-assembly 'wheels' whose step builds all four wheels ("build four wheels: push a tyre onto each rim"), then one
  step that attaches them all; an attach step may also add a few pieces.
- Group a step the way people read instructions: one significant part per step (a frame, a panel, a big brick, a
  motor) with the small parts that go on it; a step stays in one area of the model; left/right twins go in the same
  step ("one on each side") or one right after the other; every new piece must be visible from one side, so a step
  never mixes pieces on top with pieces underneath (say "turn the model over" when the next pieces go underneath).
- LEGO's sub-builds (pieces marked "in sub-build 'X'") are built OFF the model as a sub-assembly and attached as ONE
  finished piece: every piece of that sub-build goes in before its attach step, including the pieces that join its
  parts together. Never put a sub-build's pieces straight onto the main model, and never attach a sub-assembly that
  is still in loose parts (it could not be carried). A sub-build inside another ('X > Y') is built on its own too,
  then attached to X in one of X's steps (that step: subassembly = X, attach = Y).
- A SET MAY HOLD SEVERAL SEPARATE MODELS (a truck, a street lamp, cones, a figure): the main model is the biggest
  one (its pieces go on the main model, '' as sub-assembly); every other model is built on its own and set down
  beside it, never attached onto it unless they click together. Never build a small model as the main one and
  attach the big one onto it.
- Things that stand BESIDE the model and touch nothing of it (a traffic cone, a sign, a second small vehicle, a
  figure) are built on their own as a sub-assembly and set down beside it ("Stand the cone next to the truck"):
  never attached onto the model.
- A sub-assembly is one connected piece at every step: a group that does not click onto it (it would only rest
  beside it) is a sub-assembly of its own, attached once something fastens it on. Only copies (several identical
  wheels built together) may lie side by side.
- PHYSICAL RULES: every step must be possible with two hands on the real model. They hold for every set:
  * THE WAY IN: every piece moves into its place along one straight way (down onto studs, sideways onto a clip or a
    side stud, along a pin or axle into its hole). Nothing already built may be in that way, and there must be room
    for the fingers that press it home. If something would be in the way, the piece goes on BEFORE that thing.
  * NOTHING FLOATS: a piece goes on only when what it sits on, clicks onto or slides onto is already there (or goes
    on in the same step, first).
  * NOTHING GOES UNDER WHAT IS ALREADY ON TOP: a piece pressed onto studs needs those studs free and reachable from
    above; a piece that goes underneath an overhang, a roof or a plate goes on before that overhang.
  * ONE WAY AT A TIME: a piece that joins two things at once (two pins, two studs on different pieces, a pin and an
    axle) must reach both along the same way; if not, it goes on before the second of them.
  * BASE FIRST, THEN WHAT GOES ON IT: within a step, the piece others go into or onto comes first; a new group starts
    from the piece the others connect through, and the biggest part (a motor, a large frame) goes on last if the
    small pieces around it would then be out of reach.
  * WHAT SPANS COMES AFTER WHAT IT SPANS: a plate, beam or connector that bridges two or more studs, pins or pieces
    goes on after all of them are in.
  * LOCKING PIECES GO IN LAST: a long axle or long pin that passes through several pieces goes in after the pieces it
    passes through (held lined up, or already on the model). Never expect a piece to be slid onto an axle or pin end
    it cannot reach any more. Pieces held in place while an axle goes through them are said that way: "hold the ...
    lined up with the holes, then push the axle through".
  * PARTS WITH A STOP go in FREE END FIRST: an axle with a stop, a pin with a head or bush end goes in by its plain
    end, from the side the stop ends up on.
  * ON AN AXLE END: a gear, wheel, hub or bush that goes onto the end of an axle sticking out goes on after the axle.
  * SUB-ASSEMBLIES GO ON IN ONE PUSH: a finished sub-assembly moves into place along one way. Pieces that join it to
    the model from another side (pins or axles pushed in from the opposite side, a plate laid over both) are not
    built into it: attach it, then add them in the same step.
  * THINGS THAT MOVE: hinges, turntables, toggle joints and swivels turn, so their two ends may go on different ways,
    one after the other; a beam or arm hanging on one pin can turn aside to make room and turn back after.
  * SEE WHAT YOU DO: every new piece must be visible from one side; say "turn the model over" when the next pieces go
    underneath and "turn it back" after.
- Repeats ("now build the same on the other side") are welcome in the wording, but every piece still needs its step.
- Instructions: one or two short sentences per step, colour + size + shape of the pieces, where they go relative to
  pieces already there, which way round. No ids in the instruction text, and never a sub-assembly's code name
  ("block 2", "unit 5"): say what the finished part looks like ("the long yellow beam with the grey arms").
Return the whole plan in the given JSON format."""


def old_system():
    """The instructions before code's suggested plan and the physical rules (for comparing the two ways)."""
    out = re.sub(r"- START FROM THE SUGGESTED PLAN.*?(?=- FOLLOW LEGO'S OWN ORDER)", "", SYSTEM, flags=re.S)
    return re.sub(r"- PHYSICAL RULES:.*?(?=- Repeats)", "", out, flags=re.S)


@functools.lru_cache(maxsize=None)
def _colour_names():
    """LDraw colour codes -> names ('4' -> 'Red'), from the LDraw library's LDConfig.ldr."""
    out = {}
    for line in lego_model._zip().read("ldraw/LDConfig.ldr").decode("utf-8", "replace").splitlines():
        b = line.split()
        if len(b) > 4 and b[:2] == ["0", "!COLOUR"] and "CODE" in b:
            out[b[b.index("CODE") + 1]] = b[2].replace("_", " ")
    return out


@functools.lru_cache(maxsize=None)
def library_twin(ref):
    """A model's own copy of a library part ('42124 - 42924.dat', the same shape as 42924.dat) as the library part,
    so it has its name and its studs and pin holes. Only when the shapes' boxes agree."""
    import re
    if lego_model.library_title(ref):
        return ref
    m = re.search(r"(\w+)\.dat$", ref)
    twin = m and lego_model.resolve(m.group(1) + ".dat")
    if not twin or twin == ref or not lego_model.library_title(twin):
        return ref
    a, b = lego_model.box(ref), lego_model.box(twin)
    if a is None or b is None or any(abs(x - y) > 2 for x, y in zip(a, b)):
        return ref
    return twin


@functools.lru_cache(maxsize=None)
def placed(set_id):
    """The set's 3D model, stood upright: [(id b1.., LDraw part, LDraw colour code, pos, rot)] in build order. The
    lesson and the 3D hint viewer (assembly.py) both use these ids."""
    text = (ROOT / "data" / "sources" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    want, _, _ = lego_model.reconcile(set_id)  # the set's inventory, to pick which model in the file is the set's
    root = lego_model.best_root(text, want) if want else None
    lego_model.register(text)  # the file's own parts (not in the LDraw library) become known shapes
    flat = lego_model.flatten_mpd(text, root=root)  # sub-models opened up: one row per real piece, in the file's order
    real = [(f"b{i}", library_twin(ref), pos, rot) for i, (ref, _, pos, rot) in enumerate(flat, 1)]
    g = lego_model.upright(real)  # the turn that stands it upright
    return tuple((nid, ref, c, lego_model._apply(g, pos), lego_model._mul(g, rot))
                 for (nid, ref, pos, rot), (_, c, _, _) in zip(real, flat))


@functools.lru_cache(maxsize=None)
def official(set_id):
    """The official order, from the 3D model (its authors follow the booklet): for each piece (same order and ids as
    placed()) its official step and the sub-model it is built in ('' for the main model). A sub-model is built in its
    own steps before the step that places it, as in the booklet's boxed sub-builds."""
    text = (ROOT / "data" / "sources" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    want, _, _ = lego_model.reconcile(set_id)
    root = lego_model.best_root(text, want) if want else None
    files, parts = lego_model.mpd_sections(text)
    main = root if root in files else next(iter(files))
    # a main file that only wraps one sub-model (the whole model in it) is not a sub-build: start from the wrapped one
    for _ in range(5):
        refs = [lego_model.ldraw_key(" ".join(b[14:])) for b in (l.split() for l in files[main]) if b[:1] == ["1"] and len(b) >= 15]
        subs = [r for r in refs if r in files and r not in parts]
        if len(refs) == 1 and len(subs) == 1:
            main = subs[0]
        else:
            break
    out, step = [], [0]  # out: (official step, sub-model) per piece; step: a counter the nested walk can change

    # walk the main file in order, opening each sub-model where it is used: a STEP line ends an official step, and
    # each piece gets the step it is in and the name of the sub-model it is built in
    def walk(name, sub, depth=0):
        for line in files[name]:
            b = line.split()
            if b[:2] in (["0", "STEP"], ["0", "ROTSTEP"]):
                step[0] += 1
            if len(b) < 15 or b[0] != "1":
                continue
            ref = lego_model.ldraw_key(" ".join(b[14:]))
            if ref in files and ref not in parts and depth < 10:
                walk(ref, sub or re.sub(r"^\d+(-\d+)?\s*-\s*|\.ldr$|\.dat$", "", ref), depth + 1)
            else:
                out.append((step[0] + 1, sub))
    walk(main, "")
    # then the units LEGO builds off the model that the file builds in place, and the small blocks built in the hand
    if len({x[0] for x in out}) < max(2, len(out) / 40):  # (almost) no STEP lines: the file's own order is the order
        out, n = [], [0]

        def walk2(name, sub, depth=0):
            for line in files[name]:
                b = line.split()
                if len(b) < 15 or b[0] != "1":
                    continue
                ref = lego_model.ldraw_key(" ".join(b[14:]))
                if ref in files and ref not in parts and depth < 10:
                    walk2(ref, sub or re.sub(r"^\d+(-\d+)?\s*-\s*|\.ldr$|\.dat$", "", ref), depth + 1)
                else:
                    n[0] += 1
                    out.append((n[0], sub))
        walk2(main, "")
    return tuple(hand_blocks(set_id, side_builds(set_id, out)))


def side_builds(set_id, out):
    """Units LEGO builds off the model (a bumper, a steering block) that the 3D model's author built in place. In the
    official order, pieces that clip, stud or pin onto nothing of the model built so far start a separate unit; later
    pieces joined to it grow it; the step whose pieces join it to the model attaches it. Each unit of HAND_MIN or more
    pieces becomes an official sub-build ('unit <first step>'), built on its own and then attached."""
    from graph.lego_3d import assembly
    if len(out) != len(placed(set_id)):
        return out
    asm = assembly.of(set_id)
    out = list(out)
    parent = {}  # union-find: pieces fastened together so far share one root

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    order = sorted(range(len(out)), key=lambda i: out[i][0])
    steps = collections.defaultdict(list)
    for i in order:
        steps[out[i][0]].append(f"b{i + 1}")
    main, unit_of = None, {}  # main: the first piece (the model grows from it); unit_of: piece or root -> unit name
    for st in sorted(steps):  # official steps in order: join each new piece to what it fastens to
        new = steps[st]
        for nid in new:
            parent[nid] = nid
        for nid in new:
            for o in sorted(asm.fastens.get(nid, set()), key=_num):  # in a fixed order: the roots, and so the
                # units' names, must not change with Python's set order from run to run
                if o in parent:
                    parent[find(nid)] = find(o)
        if main is None:
            main = new[0]
        for nid in new:
            if out[int(nid[1:]) - 1][1]:
                continue  # already in the file's own sub-model
            if find(nid) != find(main):
                root = find(nid)
                unit_of.setdefault(root, f"unit {st}")
                unit_of[nid] = unit_of[root]
        # a unit that has just joined the model keeps its name for its pieces; new units re-key on their roots
        for nid in new:
            r = find(nid)
            if r != find(main) and nid in unit_of:
                unit_of.setdefault(r, unit_of[nid])
    groups = collections.defaultdict(list)  # each unit's pieces; a unit of HAND_MIN or more becomes a sub-build
    for nid, name in unit_of.items():
        if nid.startswith("b") and nid in parent:
            groups[name].append(nid)
    for name, ids in groups.items():
        ids = sorted(set(ids), key=lambda x: int(x[1:]))
        if len(ids) >= HAND_MIN:
            for nid in ids:
                out[int(nid[1:]) - 1] = (out[int(nid[1:]) - 1][0], name)
    return out


HAND_MIN = 3  # pieces: smaller hand blocks (a pin into a beam) stay inside a step (the 3D viewer shows them in the hand)


def hand_blocks(set_id, out):
    """LEGO's boxed sub-builds that the 3D model leaves in a main step: pieces of one official step pinned to each
    other that meet the model through one piece only are put together in the hand and pushed on as one block
    (42124-1 booklet step 17: two beams, pins and towballs, then onto the axle). They become official sub-builds
    ('block <step>'), so the lesson builds them on their own and attaches them, however its steps are split."""
    from graph.lego_3d import assembly
    if len(out) != len(placed(set_id)):
        return out
    asm = assembly.of(set_id)
    out = list(out)
    steps, every = collections.defaultdict(lambda: collections.defaultdict(list)), collections.defaultdict(set)
    for i, (st, sub) in enumerate(out):
        every[st].add(f"b{i + 1}")
        steps[st][sub].append(f"b{i + 1}")  # the main model and each sub-build (a block can sit inside one)
    built = set()
    for st in sorted(every):
        found = [g for sub, ids in steps[st].items() for g, link in assembly.in_hand(ids, built, asm)
                 if len(g) >= HAND_MIN]
        for n, g in enumerate(found):
            name = f"block {st}" + ("abcdefgh"[n] if len(found) > 1 else "")
            sub = out[int(g[0][1:]) - 1][1]
            if sub:  # a block built in the hand, then pushed into a bigger sub-build (that one is attached later)
                name = f"{sub} > {name}"
            for nid in g:
                out[int(nid[1:]) - 1] = (st, name)
        built |= every[st]  # everything of earlier steps, sub-builds included
    return out


def model_of(set_id):
    """The set's 3D model as a lesson source: pieces in the anchor frame, holds (who holds on to whom)."""
    rows = placed(set_id)
    # the pieces, and the joins between them: studs and pins (ldraw_studs), clips (assembly), and plain touching
    real = [(nid, ref, pos, rot) for nid, ref, c, pos, rot in rows]
    pieces = [{"id": nid, "part_num": lego_model.design(ref), "ldraw": ref, "colour": c, "name": "", "step": 1,
               "pos": pos, "rot": rot} for nid, ref, c, pos, rot in rows]
    frame = lego_model.anchor_frame(lego_model.anchor_of(pieces))
    joins = lego_model.connections(real)
    touch = lego_model.touching(real)
    from graph.lego_3d import assembly
    for k, v in assembly.clip_joins({nid: (nid, ref, pos, rot) for nid, ref, pos, rot in real}, touch).items():
        joins.setdefault(k, v)  # clips onto bars, which the parts do not mark
    holds = collections.defaultdict(set)  # joined or touching: what a piece could rest against
    for k in list(joins) + list(touch):
        a, b = sorted(k)
        holds[a].add(b)
        holds[b].add(a)
    fastens = collections.defaultdict(set)  # stud, clip or pin joins only (touching is not holding)
    for k in joins:
        a, b = sorted(k)
        fastens[a].add(b)
        fastens[b].add(a)
    on = collections.defaultdict(set)  # b sits on a: a's stud is in b
    for k, (how, a, _, b, _) in joins.items():
        if how == "clutch":
            on[b].add(a)
    out = []
    off = official(set_id)
    for k, p in enumerate(pieces):  # each piece as Claude and the checks see it: where it is, what it holds on to
        f = lego_model.to_frame(p, frame)  # its place in studs and plates from the anchor piece (as the AR view measures)
        title = lego_model.library_title(lego_model.resolve(p["ldraw"])) or p["ldraw"]
        out.append({"id": p["id"], "part_num": p["part_num"], "name": title.lstrip("~=_ "),
                    "colour": _colour_names().get(p["colour"], p["colour"]),
                    "column": f.get("column"), "row": f.get("row"), "layer": f.get("layer"), "turn": f.get("turn"),
                    "tilt": f.get("tilt"), "roll": f.get("roll"), "sits_on": sorted(on[p["id"]], key=_num),
                    "holds": sorted(holds[p["id"]], key=_num), "fastens": sorted(fastens[p["id"]], key=_num),
                    "official_step": off[k][0] if k < len(off) else None, "official_sub": off[k][1] if k < len(off) else ""})
    return out


def _attach_order(new, built, fastens, holds):
    """Which of a step's pieces can go on, given what is built, and which would float. A piece goes on when it clicks
    onto something already there (studs, clips, pins). Exceptions, because the model's joins miss some fits: a HUB,
    a piece whose clip-on partners all depend on it alone (a bracket with the tiles that fit only on it), may go on by
    resting against the model; with nothing built yet (the first step, or a sub-assembly of several copies) each
    separate group of the step starts from one of its pieces. Returns (order, floating)."""
    reach, todo, order = set(built), list(new), []  # reach: what is on so far; todo: the step's pieces still to go
    holder = lambda i: fastens.get(i) or holds.get(i, set())

    def hub(i):
        deps = fastens.get(i, set())
        return deps and all((fastens.get(d, set()) - {i}) <= deps for d in deps)
    def ready(i):
        if fastens.get(i):
            return bool(fastens[i] & reach)
        # no detected fastening: it goes on after the pieces it touches in this step, against one already there
        return not (holds.get(i, set()) & set(todo) - {i}) and (bool(holds.get(i, set()) & reach) or not holds.get(i))
    while todo:  # put on, one at a time, a piece that can go on now; what never can is left floating
        nxt = next((i for i in todo if ready(i)), None)
        if nxt is None:  # else a hub resting against the model
            nxt = next((i for i in todo if hub(i) and holds.get(i, set()) & reach), None)
        if nxt is None:  # pieces with no detected fastening, all waiting for each other: the one touching most built
            loose = [i for i in todo if not fastens.get(i) and holds.get(i, set()) & reach]
            nxt = max(loose, key=lambda i: len(holds[i] & reach)) if loose else None
        if nxt is None and not (reach & set().union(*(holder(i) for i in todo))):
            nxt = max(todo, key=lambda i: len(fastens.get(i, set()) & set(todo)))  # a new group starts here
        if nxt is None:
            break
        order.append(nxt)
        reach.add(nxt)
        todo.remove(nxt)
    return order, sorted(todo, key=_num)


BIG = 20       # a significant part: at least this many times the set's median piece size (frames, panels, motors)
NEAR = 120     # LDU (6 studs): pieces of one step closer than this (box to box) are one region


def _vol(asm, i):
    """A piece's size: the volume of its box (LDU cubed), 0 if it has none."""
    b = asm.boxes.get(i)
    return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2]) if b else 0


def _gap(asm, a, b):
    """Distance between two pieces' boxes (0 when they overlap)."""
    A, B = asm.boxes.get(a), asm.boxes.get(b)
    if not A or not B:
        return 0
    return math.sqrt(sum(max(0, max(A[k], B[k]) - min(A[k + 3], B[k + 3])) ** 2 for k in range(3)))


def mirror_pairs(asm, pieces):
    """Left/right twins: the same part (or its Left/Right version) at mirrored places across the model's middle,
    along the axis where most such twins are found. [(a, b)]"""
    if getattr(asm, "_mirrors", None) is not None:
        return asm._mirrors
    by = {p["id"]: p for p in pieces}
    key = lambda i: re.sub(r"\b(left|right)\b", "", by[i]["name"].lower()) + "|" + str(by[i]["colour"])
    groups = collections.defaultdict(list)
    vols = sorted(_vol(asm, i) for i in by if _vol(asm, i))
    med = vols[len(vols) // 2] if vols else 0
    for i in by:  # real parts only: pins, axles and bushes sit symmetrically everywhere without being twins
        if i in asm.centre and _vol(asm, i) >= med and not re.search(r"\b(pin|axle|bush)\b", by[i]["name"].lower()):
            groups[key(i)].append(i)
    xs = [b for b in asm.boxes.values() if b]
    best = []
    for ax in range(3):  # try each axis as the mirror: a pair is twins if one mirrored across the middle is the other
        mid = (min(b[ax] for b in xs) + max(b[ax + 3] for b in xs)) / 2
        found = []
        for g in groups.values():
            for a, b in itertools.combinations(g, 2):
                ca, cb = asm.centre[a], asm.centre[b]
                m = list(ca)
                m[ax] = 2 * mid - ca[ax]
                if abs(ca[ax] - cb[ax]) > 10 and math.dist(m, cb) < 6:
                    found.append((a, b))
        if len(found) > len(best):
            best = found
    asm._mirrors = best
    return best


def grouping(lesson, pieces, asm, ids, limit=12):
    """How LEGO groups a step (Agrawala et al. 2003, from how people build; LEGO's own booklets):
      S10 one significant part per step (copies of one part count once), with the small parts that go on it
      S11 left/right twins in the same step or the next one
      S12 one region: a step's pieces are together, not in places far apart (copies and twins apart)
      S13 visible: one view (of the 8 three-quarter views) shows every new piece of the step
    None of them asks for what LEGO's own official step does: pieces of one official step pass."""
    issues = []
    off = {p["id"]: p.get("official_step") for p in pieces}
    kind = {p["id"]: (p.get("part_num"), p.get("colour")) for p in pieces}
    name = {p["id"]: f"{p['colour'].lower()} {re.sub(r' +', ' ', p['name'])}" for p in pieces}
    vols = sorted(_vol(asm, i) for i in ids if _vol(asm, i))
    med = vols[len(vols) // 2] if vols else 0
    big = {i for i in ids if med and _vol(asm, i) >= BIG * med}
    twins = [(a, b) for a, b in mirror_pairs(asm, pieces) if a in ids and b in ids]
    twin = {x: y for a, b in twins for x, y in ((a, b), (b, a))}
    lego = lambda g: len({off.get(i) for i in g}) == 1  # LEGO adds them in one official step itself
    seen = collections.defaultdict(lambda: Sightlines(asm))
    step_of, shown = {}, collections.Counter()
    for n, st in enumerate(lesson["steps"], 1):  # S10, S12, S13 step by step; S11 after, over the whole plan
        new = [i for i in st["pieces"] if i in ids]
        sec = st["subassembly"] or ""
        if st["attach"] and st["attach"] in seen:  # an attached sub-assembly is now part of what it joins
            for i in [x for s2 in lesson["steps"][:n - 1] if s2["subassembly"] == st["attach"] for x in s2["pieces"]]:
                seen[sec].add(i)
        kinds = {kind[i] for i in new if i in big}
        if len(kinds) > 1 and not lego([i for i in new if i in big]) and shown["S10"] < limit:
            names = sorted({name[i] for i in new if i in big})
            issues.append(("S10", f"step {n} adds {len(kinds)} significant parts ({'; '.join(names[:4])}). Like a "
                                  f"LEGO booklet, add one significant part per step, with the small parts that go "
                                  f"on it: split the step."))
            shown["S10"] += 1
        # S12: regions of the step (single linkage on box gaps); copies and twins of a region count with it
        left, regions = list(new), []
        while left:
            g, todo = set(), [left[0]]
            while todo:
                i = todo.pop()
                if i in g:
                    continue
                g.add(i)
                todo += [j for j in left if j not in g and (_gap(asm, i, j) < NEAR or twin.get(i) == j)]
            left = [i for i in left if i not in g]
            regions.append(g)
        sigs = {tuple(sorted(map(str, (kind[i] for i in g)))) for g in regions}
        if len(regions) > 1 and len(sigs) > 1 and not lego(new) and shown["S12"] < limit:
            issues.append(("S12", f"step {n} puts pieces in {len(regions)} places far apart "
                                  f"({' / '.join(' '.join(sorted(g, key=_num)[:4]) for g in regions[:3])}). Keep a "
                                  f"step to one area of the model: split it by area."))
            shown["S12"] += 1
        # S13: one of the 8 views shows every new piece
        sl = seen[sec]
        if new and shown["S13"] < limit:
            ok = [v for v in VIEWS if all(sl.seen(i, v) >= 0.15 for i in new)]
            if not ok and not lego(new):
                hidden = [i for i in new if max(sl.seen(i, v) for v in VIEWS) < 0.15]
                issues.append(("S13", f"step {n}: no single view shows all its new pieces"
                                      + (f" ({', '.join(name[i] + ' (' + i + ')' for i in hidden[:3])} hidden from every side)"
                                         if hidden else "") + ". Every new piece must be visible when it is added: "
                                      "split the step so each part can be seen from one side."))
                shown["S13"] += 1
        for i in new:
            sl.add(i)
            step_of[i] = n
    for a, b in twins:  # S11
        if a in step_of and b in step_of and abs(step_of[a] - step_of[b]) > 1 and \
                abs((off.get(a) or 0) - (off.get(b) or 0)) <= 1 and shown["S11"] < limit:
            issues.append(("S11", f"the {name[a]} ({a}, step {step_of[a]}) and its mirror twin ({b}, step "
                                  f"{step_of[b]}) are far apart in the lesson. Put left/right twins in the same step "
                                  f"(\"one on each side\") or one right after the other."))
            shown["S11"] += 1
    return issues



def _parts(ids, fz):
    """The separate pieces a set of pieces makes: groups joined by what really fastens (not by resting)."""
    left, out = set(ids), []
    while left:
        g, todo = set(), [min(left, key=_num)]
        while todo:
            i = todo.pop()
            if i in g:
                continue
            g.add(i)
            todo += [j for j in fz.get(i, set()) if j in left and j not in g]
        left -= g
        out.append(g)
    return out


def _sig(g, kind):
    """What a group is made of (parts and colours, not where): copies of one build share it."""
    return tuple(sorted(map(str, (kind.get(i) for i in g))))


def _mark_built(line, built):
    """'... | on: b1 b7 | touches: b9' with pieces of earlier parts marked [built]."""
    head, _, tail = line.partition(" | on: ")
    return head + " | on: " + " ".join(f"{w}[built]" if w in built else w for w in tail.split(" ") if w)


def _num(i):
    """b12 -> 12: sorts piece ids in the model's order."""
    return int(i[1:]) if i[1:].isdigit() else 0


def parts_of_model(set_id, pieces):
    """The model's own parts, in its author's build order: each sub-model the main build uses directly is one part,
    the pieces placed straight in the main build another; parts are merged until each has at least CHUNK // 4
    pieces. Returns [[piece ids]] in the order the flattened model lists them."""
    text = (ROOT / "data" / "sources" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    files, parts = lego_model.mpd_sections(text)
    want, _, _ = lego_model.reconcile(set_id)
    root = lego_model.best_root(text, want) if want else None
    main = root if root in files else next(iter(files))
    groups, order = collections.OrderedDict(), []

    def count(name, depth=0):
        n = 0
        for b in (l.split() for l in files[name]):
            if b[:1] == ["1"] and len(b) >= 15:
                ref = lego_model.ldraw_key(" ".join(b[14:]))
                n += count(ref, depth + 1) if ref in files and ref not in parts and depth < 10 else 1
        return n
    for b in (l.split() for l in files[main]):
        if b[:1] == ["1"] and len(b) >= 15:
            ref = lego_model.ldraw_key(" ".join(b[14:]))
            key = ref if ref in files and ref not in parts else "(main)"
            order.append((key, count(ref) if key != "(main)" else 1))
    ids = [p["id"] for p in pieces]
    out, i = [], 0  # one run of piece ids per sub-model (or per run of pieces placed straight in the main file)
    for key, n in order:  # the flattened model lists pieces in exactly this order
        if out and out[-1][0] == key:
            out[-1][1].extend(ids[i:i + n])
        else:
            out.append([key, ids[i:i + n]])
        i += n
    merged = []  # small runs merged with their neighbours, never past CHUNK pieces
    for key, g in out:
        if merged and (len(merged[-1]) < CHUNK // 4 or len(g) < CHUNK // 4) and len(merged[-1]) + len(g) <= CHUNK:
            merged[-1].extend(g)
        else:
            merged.append(list(g))
    return merged


def describe(pieces):
    """The pieces as text for Claude: one line each with its official step, name, colour, place, and what it sits on,
    clicks onto and touches."""
    lines = [f"PIECES ({len(pieces)}). Position: column/row in studs, layer in plates (brick = 3), turn in degrees, "
             f"in the frame of the first big piece. 'official step' = the step of LEGO's own instructions that adds it (sub-builds "
             f"are built on their own, then attached). 'on' = the pieces it sits on (studs); 'clicks onto' = other pieces it "
             f"fastens to (side studs, clips, pins); 'touches' = pieces it only rests against. A piece can only be put on "
             f"once something it sits on or clicks onto is already there."]
    for p in pieces:
        pos = f"col {p['column']:g} row {p['row']:g} layer {p['layer']:g} turn {p['turn']:g}" if p["column"] is not None else "?"
        if p["tilt"] or p["roll"]:
            pos += f" tilt {p['tilt']:g} roll {p['roll']:g}"
        clicks = [h for h in p.get("fastens", []) if h not in p["sits_on"]]
        other = [h for h in p["holds"] if h not in p["sits_on"] and h not in clicks]
        offi = f"official step {p['official_step']}" + (f" in sub-build '{p['official_sub']}'" if p.get("official_sub") else "")
        lines.append(f"{p['id']} | {offi} | {p['name']} | {p['colour']} | {pos} | on: {' '.join(p['sits_on']) or '-'} | "
                     f"clicks onto: {' '.join(clicks) or '-'} | touches: {' '.join(other) or '-'}")
    return "\n".join(lines)


def names_in_words(lesson):
    """W3: the instructions never use code's names for sub-builds ('block 2', 'unit 5', 'drivemotor > block 42') or
    piece ids: a learner does not know them. Say what the thing is ('the long yellow beam with the grey arms')."""
    # LEGO's file names for its sub-builds ('drivemotor', 'roofrear', 'chassisbottom1', 'substep_step-32'): one word
    # that is no plain English (a digit, an underscore, or two words run together, long)
    files = {w for st in lesson["steps"] for x in (st["subassembly"], st["attach"]) for w in re.split(r" > |: ", x)
             if w and " " not in w and (re.search(r"\d|_", w) or len(w) >= 9)}
    out = []
    for n, st in enumerate(lesson["steps"], 1):
        hit = re.findall(r"\b(?:block|unit) \d+[a-z]?\b|\bb\d+\b|\S+ > \S+", st["instruction"], re.I)
        hit += [w for w in files if re.search(rf"\b{re.escape(w)}\b", st["instruction"], re.I)]
        if hit:
            out.append(("W3", f"step {n}: the instruction says {', '.join(sorted(set(hit)))}, a name the learner does "
                              f"not know; say what it is (its colour and shape, what it looks like)"))
    return out


def main_file(pieces):
    """The set's main model: the biggest of LEGO's top-level model files (a set may hold several models: a truck, a
    street lamp, cones, a figure; LEGO's file may list a small one first)."""
    import collections
    top = collections.Counter((p.get("official_sub") or "").split(" > ")[0] for p in pieces)
    return max(top, key=lambda k: (top[k], k == (pieces[0].get("official_sub") or "") if pieces else 0)) if top else ""


def separate_models(pieces, asm, main):
    """Top-level model files other than the main one that touch nothing of it: separate models, set beside it."""
    top = lambda p: (p.get("official_sub") or "").split(" > ")[0]
    ids = {}
    for p in pieces:
        ids.setdefault(top(p), set()).add(p["id"])
    return {name for name, g in ids.items() if name != main and asm is not None and not any(
        frozenset((a, b)) in asm.touch for a in g for b in ids.get(main, ()))}


def suggested(pieces, asm, main_sub=None, size=6):
    """A plan by code, from LEGO's own instructions: its official steps in order (a step of more than 8 pieces split,
    in an order that can be built), each official sub-build as a sub-assembly, attached right after its last step
    (a nested one 'X > Y' into X). Claude starts from it. Returns {"steps": [...]} in the lesson's format."""
    order = sorted(pieces, key=lambda p: (p.get("official_step") or 0, _num(p["id"])))  # LEGO's order
    if main_sub is None:
        main_sub = main_file(pieces)
    apart = separate_models(pieces, asm, main_sub)
    sub = lambda p: "" if (p.get("official_sub") or "") == main_sub else (p.get("official_sub") or "")
    groups = []  # one group per official step of the main model or of one sub-build
    for p in order:
        key = (sub(p), p.get("official_step"))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(p["id"])
        else:
            groups.append((key, [p["id"]]))
    steps, built = [], {}  # built: what each sub-assembly (or the main model, '') has so far
    for n, ((name, _), ids) in enumerate(groups):
        if len(ids) > 8:  # too big for one step: in an order that can be built, a few at a time
            have = built.setdefault(name, set())
            ids = [x[0] for x in asm.order_step(ids, have)] if asm is not None else ids
        for k in range(0, len(ids), size if len(ids) > 8 else len(ids)):
            chunk = ids[k:k + (size if len(ids) > 8 else len(ids))]
            steps.append({"pieces": chunk, "subassembly": name, "attach": "", "instruction": ""})
            built.setdefault(name, set()).update(chunk)
        later = {g[0][0] for g in groups[n + 1:]}  # sub-builds that still have steps to come
        if name and name not in later and name in apart:  # a separate model: set down beside the main one
            steps.append({"pieces": [], "subassembly": "", "attach": name, "instruction": "", "beside": True})
        elif name and name not in later:  # its last step: attached now, into the sub-build it is part of
            parent = name.rsplit(" > ", 1)[0] if " > " in name else ""
            steps.append({"pieces": [], "subassembly": parent if parent != main_sub else "", "attach": name,
                          "instruction": ""})
    return {"title": "", "steps": steps, "notes": []}


def check(lesson, pieces, built=(), all_holds=None, asm=None, limit=12):
    """S1-S14 on a plan for `pieces` (a whole set, or one part of it with `built` = the ids already built).
    Returns [(rule, message)]."""
    ids = {p["id"] for p in pieces}
    holds = all_holds or {p["id"]: set(p["holds"]) for p in pieces}
    fastens = {p["id"]: set(p.get("fastens", [])) for p in pieces}
    issues, seen = [], collections.Counter()
    # S1: every piece in exactly one step, and no id that is not a piece
    for st in lesson["steps"]:
        seen.update(st["pieces"])
    missing = sorted(ids - set(seen), key=_num)
    if missing:
        issues.append(("S1", f"{len(missing)} pieces are in no step: {' '.join(missing[:40])}"))
    twice = sorted((i for i, n in seen.items() if n > 1), key=_num)
    if twice:
        issues.append(("S1", f"pieces in more than one step: {' '.join(twice[:40])}"))
    unknown = sorted(set(seen) - ids)
    if unknown:
        issues.append(("S1", f"ids that are not pieces of the set: {' '.join(unknown[:20])}"))
    # S4, S3, S2: the plan played step by step. main: what is on the main model; subs: what each sub-assembly has;
    # attached: the sub-assemblies put on so far
    start = set(built)
    main, subs, attached = set(built), collections.defaultdict(set), set()
    kind = {p["id"]: (p.get("part_num"), p.get("colour")) for p in pieces}
    placed_in, step_no = {}, {}
    fz = asm.fastens if asm is not None else fastens  # what really fastens (balls, tyres, figure pegs included)
    for n, st in enumerate(lesson["steps"], 1):
        new = [i for i in st["pieces"] if i in ids]
        if len(new) > MAX_STEP:
            issues.append(("S4", f"step {n} adds {len(new)} pieces; split it (at most {MAX_STEP}, ideally 1-6)"))
        built = subs[st["subassembly"]] if st["subassembly"] else main  # what this step builds on (the same set)
        if st["attach"]:  # S3: a finished sub-assembly goes on as one piece
            sub = subs.get(st["attach"])
            whole = main
            main = built  # the attach target: the main model, or the bigger sub-assembly this step builds
            # a part that clicks onto nothing it is attached to would only be carried along (several wheels pushed
            # on in one step are fine: each goes on by itself)
            real = {i for i in sub or set() if fz.get(i)}  # hoses, cables, bands: no detected join, they come along
            parts = [g for g in _parts(real, fz) if not any(fz.get(i, set()) & (main | set(new)) for i in g)]
            copies = len({_sig(g, kind) for g in _parts(real, fz)}) == 1  # identical models built together (two
            if sub and parts and len(_parts(real, fz)) > 1 and not copies:  # cones, four wheels): fine apart
                parts = sorted(_parts(real, fz), key=lambda g: -len(g))
                # carried as one, it would fall apart: what joins its parts must go in while it is off the model
                join = sorted({i for i in fz if i not in sub and sum(bool(fz[i] & g) for g in parts) > 1}, key=_num)
                issues.append(("S3", f"step {n} attaches '{st['attach']}', but it is still {len(parts)} loose parts "
                                     f"that nothing joins yet ({'; '.join(' '.join(sorted(g, key=_num)[:5]) for g in parts[:4])}"
                                     f"). It cannot be carried as one. Put the pieces that join them"
                                     + (f" ({', '.join(join[:8])})" if join else "") + f" into '{st['attach']}' before "
                                     f"it is attached, or build each part as its own sub-assembly."))
            figure = bool(sub) and asm is not None and len(sub & asm.figs) * 2 >= len(sub)
            if not sub:
                issues.append(("S3", f"step {n} attaches '{st['attach']}', but no step builds a sub-assembly of that name"))
            elif figure or (asm is not None and not any(frozenset((i, o)) in asm.touch for i in sub for o in main)) \
                    or not any(fz.get(i, set()) - sub for i in sub):
                # a minifigure stands on, sits in or stands beside the model: nothing clicks it on; a thing that
                # touches nothing of the model stands beside it (a traffic cone, a sign): it is only set down there;
                # and what no piece of the whole model fastens to is only set in its place, so no lock can be asked
                # for (30161-1: the 3D model's rear 1 x 4 plate and its lights lie beside the base, joined to nothing)
                main |= sub
                attached.add(st["attach"])
            elif main and not any(holds[i] & main for i in sub):
                issues.append(("S3", f"step {n} attaches '{st['attach']}', but none of its pieces holds on to the main model"))
            elif main and not any(fz.get(i, set()) & main for i in sub) and not any(
                    fz.get(i, set()) & sub and fz.get(i, set()) & main for i in new):
                # it only rests there: the pieces that lock it on (an axle through both) belong in this step
                lock = sorted({i for i in fz if i not in main and i not in sub and fz[i] & sub and fz[i] & main}, key=_num)
                issues.append(("S3", f"step {n} attaches '{st['attach']}', but nothing fastens it to the model: it only "
                                     f"rests there. Put the pieces that lock it on in this same step"
                                     + (f" ({', '.join(lock[:6])})" if lock else "") + "."))
                main |= sub
                attached.add(st["attach"])
            else:
                main |= sub
                attached.add(st["attach"])
            main = whole
        if new:  # S2: no piece floats (attaches, tiles_on and starts: see _attach_order)
            for i in _attach_order(new, built, fastens, holds)[1]:
                issues.append(("S2", f"step {n}: {i} would float: it clicks onto "
                                     f"{', '.join(sorted(fastens.get(i) or holds[i], key=_num)[:4])}, none of which is on yet "
                                     f"({'sub-assembly ' + repr(st['subassembly']) if st['subassembly'] else 'main model'}). "
                                     f"Put what it clicks onto first."))
            if st["subassembly"] and built:  # S2: a sub-assembly is one piece: no second build laid beside it
                old = _parts(built, fz)
                for g in _parts(built | set(new), fz):
                    if g & built or len(g) < 2 or any(_sig(g, kind) == _sig(o, kind) for o in old) or any(
                            fz.get(i, set()) - g - built for i in g):
                        continue  # joined on, a single piece, one more copy (four wheels built together), or it
                        # clicks onto the model by itself when the sub-assembly is attached
                    issues.append(("S2", f"step {n}: {' '.join(sorted(g, key=_num))} make a separate group that does "
                                         f"not click onto the rest of '{st['subassembly']}' (at most it rests against "
                                         f"it). Build it as its own sub-assembly and attach it in the step where "
                                         f"something fastens it on."))
        for i in new:
            placed_in[i], step_no[i] = st["subassembly"], n
        built |= set(new)
    for name, sub in subs.items():  # S3: built but never attached (a minifigure, or a thing beside the model, may be)
        if name not in attached and sub and any(holds[i] - sub for i in sub) and not (
                asm is not None and not any(frozenset((i, o)) in asm.touch for i in sub for o in set(ids) - sub)) and not (
                asm is not None and len(sub & asm.figs) * 2 >= len(sub)):  # a minifigure may stand apart
            issues.append(("S3", f"sub-assembly '{name}' is never attached to the main model"))
    # S9: LEGO's own sub-builds are built off the model and attached as one finished piece
    lego_subs = collections.defaultdict(list)
    first = next((i for st in lesson["steps"] if not st["subassembly"] for i in st["pieces"] if i in ids), None)
    mainf = main_file(pieces)
    figs = asm.figs if asm is not None else set()
    for p in pieces:  # each of LEGO's sub-builds and its pieces
        name = p.get("official_sub") or ""
        while name:  # a block inside a bigger sub-build is part of that one too
            lego_subs[name].append(p["id"])
            name = name.rsplit(" > ", 1)[0] if " > " in name else ""
    shown9 = 0
    flagged = set()
    comp = {i: n for n, g in enumerate(_parts({i for i in ids if fz.get(i)}, fz)) for i in g}  # joined groups
    for name, members in sorted(lego_subs.items(), key=lambda x: (x[0].count(" > "), min(_num(i) for i in x[1]))):
        if name.rsplit(" > ", 1)[0] in flagged and " > " in name:
            continue  # its bigger sub-build is already reported
        members = [i for i in members if fz.get(i) and i in placed_in]  # a motor's cable stub fastens to nothing
        # pieces of it that nothing joins to the rest of it, even through other pieces, cannot be built into it: the
        # 1 x 4 plate of 30161-1's 'unit 1' only lies beside the base, joined to nothing (it would be a loose group)
        hub = collections.Counter(comp.get(i) for i in members)
        members = [i for i in members if not hub or comp.get(i) == hub.most_common(1)[0][0]]
        if (first in members or name == mainf) and " > " not in name or members and set(members) <= figs:
            continue  # the model itself (a set's main build kept in its own file), or a minifigure
        onto = sorted((i for i in members if placed_in[i] == ""), key=_num)
        # put in at the very step that attaches the sub-build, into it: axles that go through it into the model
        # from both sides cannot be in it before (42124 drive motor unit)
        att = {n: st["attach"] for n, st in enumerate(lesson["steps"], 1) if st["attach"]}
        onto = [i for i in onto if not (att.get(step_no[i]) and (att[step_no[i]] == name or name.startswith(
            att[step_no[i]] + " > ") or att[step_no[i]].endswith(name.split(" > ")[0])))]
        if not onto:
            continue
        # all of it in one step of the model: put together in the hand in that step, then pushed on (the 3D page
        # shows it so); spread over steps, its first pieces go onto the model and the rest cannot get in
        if len(onto) == len(members) and len({step_no[i] for i in members}) == 1:
            continue
        if len(members) >= HAND_MIN and onto and shown9 < limit:
            shown9 += 1
            flagged.add(name)
            inside = name.rsplit(" > ", 1)[0] if " > " in name else ""
            issues.append(("S9", f"LEGO builds {' '.join(sorted(members, key=_num)[:12])} off the model as its "
                                 f"sub-build '{name}', then attaches it as one finished piece, but this plan puts "
                                 f"{' '.join(onto[:12])} straight onto the main model. Build all of them as a "
                                 f"sub-assembly (the pieces that join its parts included), then attach it"
                                 + (f" into the sub-assembly of '{inside}'" if inside else "") + "."))
    off = {p["id"]: p.get("official_step") for p in pieces if p.get("official_step") is not None}
    osub = {p["id"]: p.get("official_sub", "") for p in pieces}
    overruled = []  # S6 reports LEGO's own order contradicts (kept for the audit, not sent back)
    if asm is not None:  # S6: can each piece get to its place past what is already built?
        name = {p["id"]: f"{p['colour'].lower()} {re.sub(r'[ ]+', ' ', p['name'])}" for p in pieces}
        # model: what is on the main model; side: what each sub-assembly built off to the side has
        step_of, model, side, shown = {}, set(start), collections.defaultdict(set), 0
        n_fingers = [0]

        def vol(i):
            b = asm.boxes.get(i)
            return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2]) if b else 0
        for n, st in enumerate(lesson["steps"], 1):
            new = [i for i in st["pieces"] if i in ids]
            if st["attach"] in side:  # a finished sub-assembly joins the model: it must get there as one block
                block = side.pop(st["attach"])
                into = side[st["subassembly"]] if st["subassembly"] else model
                way = {i: asm.approach(i, into)[0] for i in sorted(block, key=_num) if asm.fastens.get(i, set()) & into}
                # axles or pins of the block going into the model from opposite sides (two axles pushed in towards
                # each other): the block cannot be pushed on with them in; they go in after, through it (42124 drive
                # motor unit: an axle with stop through each side into the 15-hole beams)
                stick = [i for i in way if asm.long_axle(i) or re.search(r"\b(axle|pin)\b", name.get(i, ""))]
                against = sorted({i for a in stick for b in stick if a != b
                                  and sum(way[a][k] * way[b][k] for k in range(3)) < -0.5 for i in (a, b)}, key=_num)
                if against and shown < limit:
                    outs = sorted({o for i in against for o in asm.fastens.get(i, set()) & into}, key=_num)
                    issues.append(("S6", f"step {n}: the finished '{st['attach']}' cannot be pushed on with "
                                         f"{', '.join(name.get(i, i) + ' (' + i + ')' for i in against)} already in: "
                                         f"they go into the {', '.join(name.get(o, o) + ' (' + o + ')' for o in outs)} "
                                         f"from opposite sides. Leave them out of '{st['attach']}': put them in step {n}, "
                                         f"after it is in place."))
                    shown += 1
                dirs = [w for i, w in way.items() if i not in against]
                if dirs:
                    best = max(dirs, key=lambda v: sum(1 for w in dirs if sum(v[k] * w[k] for k in range(3)) > 0.9))
                    ok, blocker = asm.clear_block(block - set(against), best, into)
                    lego_first = blocker is not None and off.get(blocker) is not None and any(
                        off.get(i) is not None and off[i] > off[blocker] for i in block)
                    lego_first = lego_first or len({osub.get(i, "") for i in block} - {""}) == 1 and all(
                        osub.get(i) for i in block)  # LEGO itself pushes this very sub-build on as one
                    threaded = {i for i in block if asm.threads(i, block)}  # bushes, joiners on the block's axle
                    if not ok and threaded and asm.clear_block(block - threaded, best, into)[0] and shown < limit:
                        # they cannot go through the model with the axle (42124 booklet 97)
                        issues.append(("S6", f"step {n}: the finished '{st['attach']}' cannot be pushed on: "
                                             f"{', '.join(name.get(i, i) + ' (' + i + ')' for i in sorted(threaded, key=_num))} "
                                             f"on its axle cannot pass through the {name.get(blocker, blocker)} "
                                             f"({blocker}). Do not build them onto the axle first: in the step that "
                                             f"pushes the axle in, hold them inside the model, then push the axle "
                                             f"through them."))
                        shown += 1
                    elif not ok and not lego_first and shown < limit:
                        when = f"step {step_of[blocker]}" if blocker in step_of else "an earlier part"
                        issues.append(("S6", f"step {n}: the finished '{st['attach']}' cannot be pushed on: the "
                                             f"{name.get(blocker, blocker)} ({blocker}, {when}) is in its way. Attach "
                                             f"'{st['attach']}' before {blocker} goes on, or build its pieces straight "
                                             f"onto the model in LEGO's order."))
                        shown += 1
                into |= block
            done = side[st["subassembly"]] if st["subassembly"] else model  # built off to the side: meets only itself
            # each new piece in an order that can be built: d is the way it goes in, blocker what is in that way
            for nid, d, partners, blocker in asm.order_step(new, done):
                if blocker is not None and off.get(nid) is not None and off.get(blocker) is not None \
                        and off[blocker] < off[nid] and not any(  # LEGO itself puts the blocker on first: the
                            off.get(a, 0) >= off[nid] for a in asm.threads(nid, done)):  # path test is wrong, unless
                    # the piece slides onto an axle LEGO puts in with it (it should be held there before the axle)
                    overruled.append((nid, blocker))
                    blocker = None
                if blocker is not None and off.get(nid) is not None and off.get(nid) == off.get(blocker) \
                        and vol(blocker) >= 2 * vol(nid):
                    overruled.append((nid, blocker))  # same LEGO step: the base goes on before what sits in it
                    blocker = None
                if blocker is not None and shown < limit:
                    when = f"step {step_of[blocker]}" if blocker in step_of else "an earlier part"
                    lego = (f" LEGO puts {nid} on in its official step {off[nid]}, before {blocker} (official step "
                            f"{off[blocker]}): move {nid} EARLIER, to its official step; do not move {blocker} later."
                            if off.get(nid) is not None and off.get(blocker) is not None else "")
                    axles = sorted(a for a in asm.fastens.get(nid, set()) if asm.long_axle(a))
                    hand = (f" Or, as LEGO does: put it onto the {name.get(axles[0], axles[0])} ({axles[0]}) in the hand "
                            f"first, with what sits on that end of the axle, and push the axle in with it (free end "
                            f"first); the pieces for the axle's far end go on after." if axles else "")
                    issues.append(("S6", f"step {n}: the {name.get(nid, nid)} ({nid}) cannot get to its place: the "
                                         f"{name.get(blocker, blocker)} ({blocker}, {when}) is in its way. Put {nid} on "
                                         f"before {blocker}.{lego}{hand}"))
                    shown += 1
                if blocker is None and n_fingers[0] < limit:  # S8: room for a finger to press it home?
                    ok, crowd = asm.finger_room(nid, d, done)
                    lego = off.get(crowd) is not None and off.get(nid) is not None and (
                        off[crowd] < off[nid] or (off[crowd] == off[nid] and vol(crowd) >= 2 * vol(nid)))
                    if not ok and not lego:
                        when = f"step {step_of[crowd]}" if crowd in step_of else "an earlier part"
                        issues.append(("S8", f"step {n}: no room for a finger to press the {name.get(nid, nid)} ({nid}) "
                                             f"home: the {name.get(crowd, crowd)} ({crowd}, {when}) is around it, so it "
                                             f"would need tweezers. Put {nid} on before {crowd}."))
                        n_fingers[0] += 1
                done.add(nid)
                step_of[nid] = n
    if off:  # S7: LEGO's own order: no piece before a piece of an earlier official step (sub-builds apart)
        sub = {p["id"]: p.get("official_sub", "") for p in pieces}
        latest, shown = {}, 0
        # a piece of a sub-assembly joins the model (or the sub-assembly it goes into) when that sub-assembly is
        # attached, not when it is built in the hand: that is when its place in LEGO's order counts
        events, pending = [], collections.defaultdict(list)
        for n, st in enumerate(lesson["steps"], 1):
            if st["attach"] and st["attach"] in pending:
                moved = pending.pop(st["attach"])
                (pending[st["subassembly"]] if st["subassembly"] else events).extend((n, i) for _, i in moved)
            for i in st["pieces"]:
                (pending[st["subassembly"]] if st["subassembly"] else events).append((n, i))
        for rest in pending.values():  # never attached: counted where they were built
            events += rest
        # official steps must never go backwards within the main model or one sub-build
        for n, st in [(n, {"pieces": [i]}) for n, i in events]:
            for i in st["pieces"]:
                if i not in off:
                    continue
                key = sub.get(i, "")
                prev = latest.get(key)
                if prev and off[i] < prev[0] and shown < limit:
                    issues.append(("S7", f"step {n}: {i} is from official step {off[i]}, but step {prev[1]} already "
                                         f"added {prev[2]} from the later official step {prev[0]}. Keep LEGO's order: move {i} earlier "
                                         f"(or {prev[2]} later), so official steps never go backwards."))
                    shown += 1
                if not prev or off[i] > prev[0]:
                    latest[key] = (off[i], n, i)
    # S14: nothing is slid in between pieces already on. A piece may be pushed up into the underside of what is built
    # (a dish under a hull), but not into a gap: when A sits on B and B comes later, B must not also sit on something
    # already there (it would go in between the two); built apart, A's sub-assembly is attached after B is on
    attach_at = {st["attach"]: n for n, st in enumerate(lesson["steps"], 1) if st.get("attach")}
    on_model = lambda i: step_no[i] if placed_in.get(i, "") == "" else attach_at.get(placed_in[i], step_no[i])  # noqa: E731
    shown14 = 0
    sits = {p["id"]: set(p.get("sits_on") or []) for p in pieces}
    for p in pieces:
        a = p["id"]
        for b in p.get("sits_on") or []:
            if a not in step_no or b not in step_no or shown14 >= limit:
                continue
            same = placed_in.get(a, "") == placed_in.get(b, "")
            late = step_no[b] > step_no[a] if same else on_model(b) > on_model(a)
            below = [c for c in sits.get(b, ()) if c in step_no and c != a and
                     (step_no[c] < step_no[b] if placed_in.get(c, "") == placed_in.get(b, "") else on_model(c) < on_model(b))]
            lego = off.get(a) is not None and off.get(b) is not None and off[b] > off[a]  # LEGO's own booklet puts
            if late and below and not lego:                                                # the support in later too
                issues.append(("S14", f"step {step_no[a]}: {a} sits on {b}, which only comes in step {step_no[b]}: "
                                      f"{b} would have to slide in between it and {', '.join(sorted(below, key=_num)[:3])}. Put {b} first, or build {a} apart as a "
                                      f"sub-assembly and attach it after {b} is on."))
                shown14 += 1
    if asm is not None:  # S10-S13: how a step is grouped
        issues += grouping(lesson, pieces, asm, ids, limit)
    # S5: not too many one-piece steps (only checked from 6 steps up)
    adding = [len(st["pieces"]) for st in lesson["steps"] if st["pieces"]]
    singles = sum(1 for n in adding if n == 1)
    if len(adding) >= 6 and singles > SMALL_SHARE * len(adding):
        issues.append(("S5", f"{singles} of {len(adding)} steps add a single piece; merge small steps so most steps add "
                             f"3 to 6 pieces, and build identical sub-assemblies together"))
    check.overruled = overruled  # read by the audit: where S6's path test lost to LEGO's own order
    return issues


def write_md(set_id, name, lesson, stats, path):
    """lesson.md: the lesson to read, a heading with its size, time, cost and final check, then each step."""
    secs = (stats.get("bags") or {}).get("sections") or []
    alt = (stats.get("bags") or {}).get("alternate_builds") or 0
    lines = [f"# {set_id} {name}: lesson", "", "*Main build" + (f"; the booklet also has {alt} alternate build"
             f"{'s' if alt > 1 else ''}, not covered (no 3D model)*" if alt else "*") + "", "",
             f"{len(lesson['steps'])} steps · {stats['pieces']} pieces · "
             f"{stats['seconds']:.0f} s · ${stats['cost_usd']:.2f} · repairs {stats['repairs']} · "
             f"final check: {'passed' if not stats['issues_final'] else str(len(stats['issues_final'])) + ' issues'}", ""]
    for n, st in enumerate(lesson["steps"], 1):
        where = f" *(sub-assembly: {st['subassembly']})*" if st["subassembly"] else ""
        att = f" *(attach {st['attach']})*" if st["attach"] else ""
        if not st["pieces"] and st["instruction"].startswith("Open bag"):
            lines += [f"### {st['instruction'].rstrip('.')}", ""]
            continue
        lines.append(f"**Step {n}.**{where}{att} {st['instruction']}  ")
        lines.append(f"<sub>pieces: {' '.join(st['pieces']) or '—'}</sub>")
        lines.append("")
    path.write_text("\n".join(lines))


def sections(set_id, pieces, use_bags=True, model="sonnet"):
    """The lesson's sections: numbered bags read from the booklet when it has them (read, below), else the model's parts
    (large sets) or one section. Returns ([(bag number or None, [piece ids])], bag stats or None)."""
    pdf = ROOT / "data" / "sources" / "lego_pdf" / f"{set_id}.pdf"
    out, bstats = None, None
    if use_bags and pdf.exists():  # the booklet's numbered bags (read by Claude), each piece given its bag
        plan, parts, bstats = read(set_id, pdf.read_bytes(), model=model)
        (OUT / set_id).mkdir(parents=True, exist_ok=True)
        (OUT / set_id / "bags.json").write_text(json.dumps({"plan": plan, "stats": bstats}, indent=1))
        if plan["numbered_bags"] and len(plan["bags"]) > 1:
            bag_of = assign(plan, parts, pieces)
            out = []
            for b in [x["bag"] for x in plan["bags"]]:
                ids = [p["id"] for p in pieces if bag_of[p["id"]] == b]
                for i in range(0, len(ids), CHUNK):  # a very large bag is planned in pieces of CHUNK
                    out.append((b if i == 0 else None, ids[i:i + CHUNK]))
            out = [(b, g) for b, g in out if g]
    if out is None:  # no bags: a big set by its model's own parts, a small one in one section
        groups = parts_of_model(set_id, pieces) if len(pieces) > CHUNK else [[p["id"] for p in pieces]]
        out = [(None, g) for g in groups]
    return out, bstats


from graph.lessons import Recipe, log as _log


class LegoLessons(Recipe):
    """The LEGO recipe of the lesson stage (lessons.py): the set's 3D model is the source; Claude plans the order and
    the words of each bag (or part of a big model); check() is the rule set; LEGO's own order is restored by code."""
    name, schema, system, hint = "lego", Lesson, SYSTEM, "lego-v8"
    default_model = "opus"  # R28: with prompt v8, the fewest issues and repairs of the three models

    def __init__(self, use_bags=True, model=None, suggest=None):
        import os
        self.use_bags, self.model = use_bags, model or self.default_model
        # suggest: code's suggested plan in the prompt and the physical rules in the instructions (the new way); off,
        # Claude plans from the pieces alone (the old way, kept for comparing: LEGO_SUGGEST=0)
        self.suggest = os.environ.get("LEGO_SUGGEST", "1") != "0" if suggest is None else suggest
        if not self.suggest:
            self.system = old_system()

    def source(self, set_id):
        """The set's name, its pieces as model_of() gives them, and its geometry (assembly.of: boxes, ways in, views)."""
        from graph.lego_3d import assembly
        sets = {c["set"]: c for f in ("lego_dataset.json", "lego_guides_dataset.json", "lego_bags_dataset.json")
                if (ROOT / "data" / "reference" / f).exists()
                for c in json.loads((ROOT / "data" / "reference" / f).read_text())}
        pieces = model_of(set_id)
        return {"id": set_id, "name": (sets.get(set_id) or {}).get("name", ""), "pieces": pieces,
                "by_id": {p["id"]: p for p in pieces}, "holds": {p["id"]: set(p["holds"]) for p in pieces},
                "asm": assembly.of(set_id)}

    def sections(self, src):
        """Each section as ((bag or None, its number), [piece ids]); reading the bags is the first phase."""
        _log(src["id"], f"{len(src['pieces'])} pieces; reading bags/sections")
        secs, bstats = sections(src["id"], src["pieces"], self.use_bags, self.model)
        src["bags"], src["n_sections"] = bstats, len(secs)
        phases = [{"phase": "bags", "seconds": bstats["seconds"], "cost_usd": bstats["cost_usd"],
                   "issues": len(bstats["issues_final"]), "rules": {}}] if bstats else []
        return [((bag, k), g) for k, (bag, g) in enumerate(secs, 1)], phases

    def prompt(self, src, section, built):
        """What Claude plans a section from: the set, the section's pieces (those already on marked [built]) and code's
        suggested plan with what the checks find wrong with it."""
        (bag, k), g = section
        n = src["n_sections"]
        what = f"BAG {bag}" if bag is not None else f"PART {k} OF {n}"
        head = f"LEGO set {src['id']} {src['name']}." + (
            f" {what}: plan only the pieces below (the learner has just opened this bag; do not add an 'open the bag' "
            f"step, that is done). Pieces marked [built] are already on the model from earlier; build on them, or "
            f"build this section as a sub-assembly and attach it." if n > 1 else "")
        listing = describe([src["by_id"][i] for i in g])
        if built:
            listing = "\n".join(
                line if not line.startswith("b") else _mark_built(line, built) for line in listing.splitlines())
        if not self.suggest:
            return head + "\n\n" + listing
        # code's suggested plan: LEGO's own steps, split where too big, sub-builds attached; and what the checks find
        # wrong with it. Claude starts from it: merges, splits, reorders, and writes the words
        sec = [src["by_id"][i] for i in g]
        main_sub = main_file(src["pieces"])
        plan = suggested(sec, src["asm"], main_sub)
        found = check(plan, sec, built, src["holds"], src["asm"], limit=20)
        lines = [f"s{n} | " + (f"set '{st['attach']}' down beside the main model (a separate model)" if st.get("beside")
                               else f"attach '{st['attach']}'" + (f" into '{st['subassembly']}'" if st["subassembly"] else "")
                               if st["attach"] else (f"sub-assembly '{st['subassembly']}' | " if st["subassembly"] else
                                                     "main model | ") + " ".join(st["pieces"]))
                 for n, st in enumerate(plan["steps"], 1)]
        sugg = ("SUGGESTED PLAN (by code, from LEGO's own steps in order; a step of more than 8 pieces split in an "
                "order that can be built; LEGO's sub-builds as sub-assemblies, attached after their last step). Start "
                "from it: merge steps that are too small, split or reorder where it helps, fix the problems listed, and "
                "write every instruction.\n" + "\n".join(lines) +
                ("\nPROBLEMS THE CHECKS FIND IN IT:\n" + "\n".join(f"- {r}: {m}" for r, m in found) if found else
                 "\nThe checks find no problem in it."))
        return head + "\n\n" + listing + "\n\n" + sugg

    def check(self, src, part, section, built):
        """The rules on one section's plan (S1-S14), and no code names in its words (W3)."""
        pieces = [src["by_id"][i] for i in section[1]] if section else src["pieces"]
        return check(part, pieces, built, src["holds"], src["asm"]) + names_in_words(part)

    def final_check(self, src, lesson):
        return check(lesson, src["pieces"], asm=src["asm"]) + names_in_words(lesson)

    def join(self, src, done):
        """The sections' plans as one lesson: an 'Open bag N' step before each bag, and each section's sub-assembly
        names prefixed with it ('bag 2: wheels') so two sections' names never clash."""
        steps, notes = [], []
        for ((bag, k), g), lesson in done:
            if bag is not None:  # each bag's section starts by opening it
                steps.append({"pieces": [], "subassembly": "", "attach": "", "instruction": f"Open bag {bag}.", "bag": bag})
            prefix = (f"bag {bag}: " if bag is not None else f"part {k}: ") if len(done) > 1 else ""
            cur_bag = bag if bag is not None else (steps[-1].get("bag") if steps else None)
            for x in lesson["steps"]:
                steps.append({**x, "subassembly": prefix + x["subassembly"] if x["subassembly"] else "",
                              "attach": prefix + x["attach"] if x["attach"] else "", "bag": cur_bag})
            notes += lesson["notes"]
        return {"title": f"{src['id']} {src['name']}", "steps": steps, "notes": notes}

    def finish(self, src, lesson, phases):
        """Code's fixes after Claude: LEGO's order and the ways in (fix_order), then the steps whose words no longer fit
        (moved pieces, what the 3D page shows, code names) reworded by Claude in one call."""
        lesson, moved = fix_order(lesson, src["pieces"], src["asm"])
        _log(src["id"], f"order fix moved {len(moved)}")
        if moved:
            phases.append({"phase": "order fix (code)", "seconds": 0, "cost_usd": 0, "moved": moved})
        t0 = time.monotonic()
        off = words_vs_3d(lesson, src["id"], src["pieces"])
        for n, acts in off:
            lesson["steps"][n - 1]["_reword"], lesson["steps"][n - 1]["_how"] = True, acts
        _log(src["id"], f"words vs 3D: {len(off)} step(s) say otherwise {[n for n, _ in off]}")
        named = sorted({int(re.match(r"step (\d+)", m).group(1)) for _, m in names_in_words(lesson)})
        for n in named:  # code's names left in the words (block 42): said as what the thing is
            lesson["steps"][n - 1]["_reword"] = True
        if named:
            _log(src["id"], f"internal names in the words: steps {named} reworded")
        phases.append({"phase": "words vs 3D (code)", "seconds": round(time.monotonic() - t0, 1), "cost_usd": 0,
                       "steps": [n for n, _ in off]})
        if any(st.get("_reword") for st in lesson["steps"]):
            _log(src["id"], "rewording changed steps")
            rw = reword(lesson, src["pieces"], self.model)
            if rw:
                phases.append(rw)
        return lesson

    def save(self, src, lesson, stats):
        """lesson.json (the plan and the pieces), stats.json and lesson.md in data/lessons/lego3d/<set>/."""
        sizes = [len(x["pieces"]) for x in lesson["steps"]]
        stats.update({"set": src["id"], "name": src["name"], "pieces": len(src["pieces"]),
                      "step_sizes": dict(collections.Counter(sizes)),
                      "subassemblies": len({x["subassembly"] for x in lesson["steps"]} - {""}),
                      "parts_planned": src["n_sections"], "bags": src["bags"]})
        d = OUT / src["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "lesson.json").write_text(json.dumps({"lesson": lesson, "pieces": src["pieces"]}, indent=1))
        (d / "stats.json").write_text(json.dumps(stats, indent=1))
        write_md(src["id"], src["name"], lesson, stats, d / "lesson.md")
        return d


def make(set_id, model=None, effort="high", use_bags=True):
    """One set's lesson through the shared lesson loop (lessons.make); the model is LegoLessons.default_model if none."""
    from graph import lessons
    recipe = LegoLessons(use_bags, model)
    return lessons.make(recipe, set_id, recipe.model, effort)


def fix_order(lesson, pieces, asm, rounds=20, budget=300):
    """What Claude's repairs left out of LEGO's order (S7), moved by code: a piece put too early that makes many pieces
    after it look late goes later, to its own official step's pieces; each late piece goes into the latest earlier
    step (same sub-assembly) whose pieces are from its own official step or before, and its text says so. A move is
    kept only if it leaves fewer problems; after `budget` seconds no more moves are tried (a big set's checks are
    slow: 7635-1 took 100 min without it). Returns (lesson, moved ids)."""
    import copy
    import time
    stop = time.monotonic() + budget

    def cost(trial):  # a trial's problem count; past the budget none is tried (counts as no better)
        return len(check(trial, pieces, asm=asm, limit=10 ** 6)) if time.monotonic() < stop else float("inf")
    by = {p["id"]: p for p in pieces}
    off = {i: p.get("official_step") for i, p in by.items()}
    best = copy.deepcopy(lesson)
    score = len(check(best, pieces, asm=asm, limit=10 ** 6))  # how many problems the plan has: lower is better
    moved = []
    # each round tries the kinds of move below in turn, on a copy; the first that leaves fewer problems is kept,
    # and the round starts again. It stops when no move helps (or after `rounds`)
    for _ in range(rounds):
        if time.monotonic() >= stop:
            break
        found = check(best, pieces, asm=asm, limit=10 ** 6)
        late = [(int(m.group(1)), m.group(2)) for r, msg in found if r == "S7"
                for m in [re.match(r"step (\d+): (b\d+) is from", msg)] if m]
        improved = False
        # S9: pieces of one of LEGO's sub-builds put straight on the model: they go into that sub-assembly's first
        # step, so it is built whole and attached as one (42072: the bonnet's two lime plates hang from its 3x4 plate)
        for r, msg in found:
            m = re.match(r"LEGO builds .*? sub-build '(.+?)', .*? this plan puts ((?:b\d+ ?)+) straight onto", msg)
            if r != "S9" or not m:
                continue
            name, ids = m.group(1), m.group(2).split()
            k = next((j for j, st in enumerate(best["steps"]) if st["subassembly"] and
                      (st["subassembly"] == name or st["subassembly"].endswith(": " + name))), None)
            if k is None:
                continue
            trial = copy.deepcopy(best)
            for i in ids:
                for st in trial["steps"]:
                    if i in st["pieces"]:
                        st["pieces"].remove(i)
                        st["_reword"] = True
            trial["steps"][k]["pieces"] = ids + trial["steps"][k]["pieces"]
            trial["steps"][k]["_reword"] = True
            trial["steps"] = [x for x in trial["steps"] if x["pieces"] or x["attach"] or x["instruction"].startswith("Open bag")]
            sc = cost(trial)
            if sc < score:
                best, score, improved = trial, sc, True
                moved += ids
                break
        if improved:
            continue
        # S6 on axles a sub-assembly cannot be pushed on with: they leave it, and go in at its attach step
        for r, msg in found:
            m = re.match(r"step (\d+): the finished '.*?' cannot be pushed on with (.*?) already in:", msg)
            if r != "S6" or not m:
                continue
            n, outs = int(m.group(1)), re.findall(r"\((b\d+)\)", m.group(2))
            outs += sorted({o for i in outs for o in asm.fastens.get(i, set()) if o not in outs
                            and asm.fastens.get(o, set()) <= set(outs)}, key=_num)  # a bush on its end goes with it
            trial = copy.deepcopy(best)
            for i in outs:
                k = next(j for j, st in enumerate(trial["steps"]) if i in st["pieces"])
                trial["steps"][k]["pieces"].remove(i)
                trial["steps"][k]["_reword"] = True
            names = list(dict.fromkeys(f"{by[i]['colour'].lower()} {re.sub(r' +', ' ', by[i]['name'])}" for i in outs))
            trial["steps"][n - 1]["pieces"] += outs
            trial["steps"][n - 1]["_reword"] = True
            trial["steps"][n - 1]["instruction"] += (f" Once it is in place, push in the {' and the '.join(names)} "
                                                     f"from each side.")
            trial["steps"] = [s for s in trial["steps"] if s["pieces"] or s["attach"] or s["instruction"].startswith("Open bag")]
            sc = cost(trial)
            if sc < score:
                best, score, improved = trial, sc, True
                moved += outs
                break
        if improved:
            continue
        # S6 within one official step: the blocked piece joins its blocker's step (the step's own order then puts it first)
        for r, msg in found:
            m = re.match(r"step (\d+): .*?\((b\d+)\) cannot get to its place: .*?\((b\d+), step (\d+)\)", msg)
            if r != "S6" or not m:
                continue
            n, i, blk, k = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
            src, dst = best["steps"][n - 1], best["steps"][k - 1]
            if k >= n or src["subassembly"] != dst["subassembly"]:
                continue
            trial = copy.deepcopy(best)
            if i not in trial["steps"][n - 1]["pieces"]:  # the message named a piece of another step
                continue
            trial["steps"][n - 1]["pieces"].remove(i)
            trial["steps"][k - 1]["pieces"].insert(0, i)  # it goes on first
            p = by[i]
            trial["steps"][k - 1]["_reword"] = trial["steps"][n - 1]["_reword"] = True
            trial["steps"][k - 1]["instruction"] = (f"First add the {p['colour'].lower()} {re.sub(r' +', ' ', p['name'])}. "
                                                    + trial["steps"][k - 1]["instruction"])
            sc = cost(trial)
            if sc < score:
                best, score, improved = trial, sc, True
                moved.append(i)
                break
        if improved:
            continue
        # S6 on a piece that sits on an axle: it joins the step that puts the axle in (its in-hand block, if the axle
        # is built in the hand), so it goes in with the axle, free end first (42124 booklet 37: both long pins on the
        # 5-long axle in the hand, the far yellow beam last)
        for r, msg in found:
            m = re.match(r"step (\d+): .*?\((b\d+)\) cannot get to its place: .*in the hand first.*?\((b\d+)\) in the hand", msg) or \
                re.match(r"step (\d+): .*?\((b\d+)\) cannot get to its place: .*put it onto the .*?\((b\d+)\) in the hand", msg)
            if r != "S6" or not m:
                continue
            n, i, axle = int(m.group(1)), m.group(2), m.group(3)
            k = next((j for j, st in enumerate(best["steps"], 1) if axle in st["pieces"]), None)
            if k is None or k == n:
                continue
            trial = copy.deepcopy(best)
            if i not in trial["steps"][n - 1]["pieces"]:  # the message named a piece of another step
                continue
            trial["steps"][n - 1]["pieces"].remove(i)
            trial["steps"][k - 1]["pieces"].append(i)
            p = by[i]
            trial["steps"][k - 1]["_reword"] = trial["steps"][n - 1]["_reword"] = True
            trial["steps"][k - 1]["instruction"] += (f" Also put the {p['colour'].lower()} {re.sub(r' +', ' ', p['name'])} "
                                                     f"onto the axle here.")
            trial["steps"] = [s for s in trial["steps"] if s["pieces"] or s["attach"] or s["instruction"].startswith("Open bag")
                              or s is trial["steps"][k - 1]]
            sc = cost(trial)
            if sc < score:
                best, score, improved = trial, sc, True
                moved.append(i)
                break
        if improved:
            continue
        # S7: one piece put too EARLY makes every piece after it look late (4431-1: b148 from official step 28 in
        # step 34, and 27 pieces of official steps 22-27 after it). Moving that one piece LATER clears them all: to
        # the step that adds its own official step's pieces, else the first later step whose pieces are all from its
        # official step or after (the same sub-assembly)
        early = collections.Counter(m.group(1) for r, msg in found if r == "S7"
                                    for m in [re.search(r"already added (b\d+) from the later official step", msg)] if m)
        for e, n_late in early.most_common():
            if n_late < 2:
                break
            k0 = next((k for k, st in enumerate(best["steps"]) if e in st["pieces"]), None)
            if k0 is None or off.get(e) is None:
                continue
            sub = best["steps"][k0]["subassembly"]
            later = [k for k in range(k0 + 1, len(best["steps"])) if best["steps"][k]["subassembly"] == sub
                     and best["steps"][k]["pieces"]]
            offs = lambda k: [off[j] for j in best["steps"][k]["pieces"] if off.get(j) is not None]  # noqa: E731
            mates = [k for k in later if off[e] in offs(k)]
            after = [k for k in later if offs(k) and min(offs(k)) >= off[e]]
            for k in list(dict.fromkeys(mates + after))[:4]:
                trial = copy.deepcopy(best)
                trial["steps"][k0]["pieces"].remove(e)
                trial["steps"][k]["pieces"].append(e)
                p = by[e]
                trial["steps"][k]["_reword"] = trial["steps"][k0]["_reword"] = True
                trial["steps"][k]["instruction"] += f" Also add the {p['colour'].lower()} {re.sub(r' +', ' ', p['name'])}."
                keep = trial["steps"][k]
                trial["steps"] = [s for s in trial["steps"] if s["pieces"] or s["attach"] or
                                  s["instruction"].startswith("Open bag") or s is keep]
                sc = cost(trial)
                if sc < score:
                    best, score, improved = trial, sc, True
                    moved.append(e)
                    break
            if improved:
                break
        if improved:
            continue
        # S14: a piece sits on one that only comes later (it would have to slide in between): the support goes first,
        # into the step of what sits on it; else the piece waits for its support (the same sub-assembly)
        for r, msg in found:
            m = re.match(r"step (\d+): (b\d+) sits on (b\d+), which only comes in step (\d+)", msg)
            if r != "S14" or not m:
                continue
            n, a, b, k = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
            for what, frm, to, front in ((b, k, n, True), (a, n, k, False)):
                if best["steps"][frm - 1]["subassembly"] != best["steps"][to - 1]["subassembly"] or \
                        what not in best["steps"][frm - 1]["pieces"]:
                    continue
                trial = copy.deepcopy(best)
                trial["steps"][frm - 1]["pieces"].remove(what)
                (trial["steps"][to - 1]["pieces"].insert(0, what) if front else trial["steps"][to - 1]["pieces"].append(what))
                p = by[what]
                trial["steps"][to - 1]["_reword"] = trial["steps"][frm - 1]["_reword"] = True
                keep = trial["steps"][to - 1]
                trial["steps"] = [s for s in trial["steps"] if s["pieces"] or s["attach"] or
                                  s["instruction"].startswith("Open bag") or s is keep]
                sc = cost(trial)
                if sc < score:
                    best, score, improved = trial, sc, True
                    moved.append(what)
                    break
            if improved:
                break
        if improved:
            continue
        # S6 inside one step: the piece in the way goes on in the next step (the same sub-assembly), after the one it
        # blocked
        for r, msg in found:
            m = re.match(r"step (\d+): .*?\((b\d+)\) cannot get to its place: .*?\((b\d+), step (\d+)\)", msg)
            if r != "S6" or not m or int(m.group(1)) != int(m.group(4)):
                continue
            n, blk = int(m.group(1)), m.group(3)
            nxt = next((k for k in range(n, len(best["steps"])) if best["steps"][k]["subassembly"] ==
                        best["steps"][n - 1]["subassembly"] and best["steps"][k]["pieces"]), None)
            if blk not in best["steps"][n - 1]["pieces"]:
                continue
            trial = copy.deepcopy(best)
            trial["steps"][n - 1]["pieces"].remove(blk)
            if nxt is None:  # the last step of its part: the piece in the way gets a step of its own, right after
                p = by[blk]
                trial["steps"].insert(n, {"pieces": [blk], "subassembly": best["steps"][n - 1]["subassembly"],
                                          "attach": "", "bag": best["steps"][n - 1].get("bag"), "_reword": True,
                                          "instruction": f"Add the {p['colour'].lower()} {re.sub(r' +', ' ', p['name'])}."})
                nxt = n
            else:
                trial["steps"][nxt]["pieces"].insert(0, blk)
            trial["steps"][nxt]["_reword"] = trial["steps"][n - 1]["_reword"] = True
            sc = cost(trial)
            if sc < score:
                best, score, improved = trial, sc, True
                moved.append(blk)
                break
        if improved:
            continue
        # S7: a piece later than LEGO's order goes back into the latest earlier step it fits
        for n, i in late:
            src = best["steps"][n - 1]
            for k in range(n - 2, -1, -1):  # the latest earlier step that fits its official step
                dst = best["steps"][k]
                offs = [off[j] for j in dst["pieces"] if off.get(j) is not None]
                if dst["subassembly"] != src["subassembly"] or not offs or max(offs) > off[i]:
                    continue
                trial = copy.deepcopy(best)
                if i not in trial["steps"][n - 1]["pieces"]:  # the message named a piece of another step
                    continue
                trial["steps"][n - 1]["pieces"].remove(i)
                trial["steps"][k]["pieces"].append(i)
                p = by[i]
                trial["steps"][k]["_reword"] = trial["steps"][n - 1]["_reword"] = True
                trial["steps"][k]["instruction"] += f" Also add the {p['colour'].lower()} {re.sub(r' +', ' ', p['name'])}."
                trial["steps"] = [s for s in trial["steps"] if s["pieces"] or s["attach"] or s["instruction"].startswith("Open bag")
                                  or s is trial["steps"][k]]
                sc = cost(trial)
                if sc < score:
                    best, score, improved = trial, sc, True
                    moved.append(i)
                break
            if improved:
                break
        if not improved:
            break
    return best, moved


# Claude's answer when rewording: the new text of each step it was given
class Reworded(BaseModel):
    step: int
    instruction: str


class Rewording(BaseModel):
    steps: List[Reworded]


REWORD = """You fix the wording of a few steps of a LEGO building lesson. Code moved pieces between steps so the build
works with real hands (a big base piece goes on before the small pieces that sit in it or are pushed through it). The
old texts below no longer match their pieces. For each step listed, write a new instruction (1-3 sentences, the same
style as the old one: colours, simple names, where it goes) that describes EXACTLY the pieces listed for that step, in
the order listed (that is the build order: the base or frame first, then what is pushed into or onto it). Never mention pieces of other steps as
being added here, never say a piece 'goes first because' anything. When a step lists what the 3D page shows,
follow those actions in that order exactly: hold only what is held there, push in what is pushed. Return every
listed step. Never use code's names for sub-assemblies ("block 42", "unit 5"): say what the
finished part looks like (colours, the main pieces)."""


def words_vs_3d(lesson, set_id, pieces):
    """The words must say what the 3D page shows. The page plays each step as physical actions (assembly.substeps): a piece
    HELD in its place while an axle is pushed through it, or put on in turn. A step whose text holds something the
    page does not (or the page holds something the text does not) is reworded from the page's actions (42124 step 68:
    the text held the differential while the page, as the booklet, puts the axle in first). Returns [(step, actions)]."""
    from graph.lego_3d import assembly
    subs = assembly.substeps(lesson["steps"], placed(set_id), pieces)
    by = {p["id"]: p for p in pieces}
    out = []
    for n, (st, s) in enumerate(zip(lesson["steps"], subs), 1):
        acts = [x for x in s["subs"] if not x.get("copy")]
        held = any(x["text"].startswith("Hold the") for x in acts)
        says = bool(re.search(r"\bhold\b(?:[^.]|\.\d)*\b(push|slide|thread)\w*\b(?:[^.]|\.\d)*\bthrough\b",
                              st["instruction"], re.I))  # (a "." inside a number like 5.5 does not end the sentence)
        how = [x["text"] for x in acts]
        turned = s.get("turn") and not re.search(r"\b(turn|flip|upside|underside|over)\b", st["instruction"], re.I)
        if turned:  # W2: the page turns the model over here; the words must say so
            how = ["Turn the model over (this step is built on the other side)."] + how
        # the page starts a new group from one piece and puts the big part on last: the words must not start from
        # the part the page puts on last (42124 step 94: the text took the motor first, the page puts it on last)
        backwards = False
        if len(acts) > 2 and acts[0]["text"].endswith("down to start."):
            first = re.split(r"(?<!\d)\.(?!\d)", st["instruction"])[0].lower()
            key = lambda i: next((w for w in KEYS if w in (by.get(i, {}).get("name", "").lower())), None)
            k0, k1 = key(acts[0]["piece"]), key(acts[-1]["piece"])
            backwards = bool(k1 and k0 and k1 != k0 and re.search(rf"\b{k1}", first) and not re.search(rf"\b{k0}", first))
        if acts and (held != says or turned or backwards):
            out.append((n, how))
    return out


KEYS = ("motor", "frame", "panel", "fairing", "beam", "liftarm", "plate", "brick", "tile", "gear", "wheel", "axle",
        "connector", "block", "pin")  # what a piece is, as the words name it


def reword(lesson, pieces, model="sonnet"):
    """Claude rewrites only the steps fix_order changed (their texts were patched by code). Returns stats or None."""
    todo = [(n, st) for n, st in enumerate(lesson["steps"], 1) if st.pop("_reword", False)]
    if not todo:
        return None
    from graph.extract import SubscriptionSession
    by = {p["id"]: p for p in pieces}
    # for each step: the step before, the old text, the pieces it has now, and what the 3D page shows
    desc = lambda i: f"{by[i]['colour'].lower()} {re.sub(r' +', ' ', by[i]['name'])} ({i})" if i in by else i
    text = "\n\n".join(
        f"STEP {n}{' (sub-assembly: ' + st['subassembly'] + ')' if st['subassembly'] else ''}\n"
        f"before it: {lesson['steps'][n - 2]['instruction'] if n > 1 else '-'}\n"
        f"old text: {st['instruction']}\n"
        + (f"FIRST this step attaches the finished sub-assembly '{st['attach']}' (say where it goes, as the old text "
           f"does); the pieces come after it\n" if st.get("attach") else "")
        + "pieces now: " + ", ".join(desc(i) for i in st["pieces"])
        + ("\nthe 3D page shows, in this order (the new text must follow it): " + " | ".join(st.pop("_how"))
           if st.get("_how") else "")
        for n, st in todo)
    s = SubscriptionSession(text, "", "lego-v8", model=model, effort="medium", timeout=600, schema=Rewording,
                            system=REWORD)
    try:
        out, st = s.first()
    finally:
        s.close()
    new = {x["step"]: x["instruction"] for x in out["steps"]}
    for n, step in todo:
        if new.get(n):
            step["instruction"] = new[n]
    return {"phase": "reword (moved steps)", **st, "steps": [n for n, _ in todo]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--model", default=None, help="default: LegoLessons.default_model (opus)")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--no-bags", action="store_true", help="do not read the booklet's numbered bags")
    ap.add_argument("--fix-only", action="store_true", help="only run the code order fix on the saved lesson")
    cfg = ap.parse_args()
    if cfg.fix_only:  # the saved lesson again with code's order fix only (no new plan): after a fix to the rules
        from graph.lego_3d import assembly
        for s in cfg.sets:
            d = OUT / s
            saved = json.loads((d / "lesson.json").read_text())
            pieces, asm = model_of(s), assembly.of(s)
            fixed, moved = fix_order(saved["lesson"], pieces, asm)
            reword(fixed, pieces)
            issues = check(fixed, pieces, asm=asm)
            st = json.loads((d / "stats.json").read_text())
            st["issues_final"], st["order_fix_moved"] = [list(i) for i in issues], moved
            st["steps"] = len(fixed["steps"])
            (d / "lesson.json").write_text(json.dumps({"lesson": fixed, "pieces": saved["pieces"]}, indent=1))
            (d / "stats.json").write_text(json.dumps(st, indent=1))
            write_md(s, st["name"], fixed, st, d / "lesson.md")
            print(f"{s}: moved {moved}; issues left {len(issues)} {collections.Counter(r for r, _ in issues)}", flush=True)
        return
    for s in cfg.sets:  # each set made in full, with a one-line summary
        st = make(s, cfg.model, cfg.effort, use_bags=not cfg.no_bags)
        print(f"{s:9} {st['pieces']:4} pieces  {st['steps']:3} steps  sizes {st['step_sizes']}  sub-assemblies "
              f"{st['subassemblies']}  issues {st['issues_first']} -> {len(st['issues_final'])}  repairs {st['repairs']}  "
              f"{st['seconds']:.0f} s  ${st['cost_usd']:.2f}", flush=True)


# ---- numbered bags: which pieces are in bag 1, bag 2 (read from the booklet, checked by code) ----------------
BAG_REPAIRS = 2


class BagLine(BaseModel):
    line: int = Field(description="Number of the parts-list line (L1, L2 ... -> 1, 2 ...)")
    count: int = Field(description="How many of that line this bag's steps use")


class Bag(BaseModel):
    bag: int = Field(description="The number printed on the bag in the booklet (1, 2, 3 ...)")
    first_step: int
    last_step: int
    parts: List[BagLine]


class Section(BaseModel):
    kind: str = Field(description="'main' (part of the set's main model, the one on the box front), 'minifigure' "
                                  "(a figure or small accessory built on its own), or 'alternate' (a DIFFERENT model "
                                  "built from the same pieces: a 3-in-1 B or C model, a B model)")
    name: str = Field(description="What the section builds, in a few words (e.g. 'red jeep', 'dune buggy', 'pilot')")
    first_page: int
    last_page: int


class BagPlan(BaseModel):
    sections: List[Section] = Field(description="The booklet's building sections in page order")
    numbered_bags: bool = Field(description="False if the booklet shows no numbered bags (then one bag: all parts)")
    bags: List[Bag] = Field(description="Bags of the MAIN model only")
    notes: List[str]


BAGS_SYSTEM = """You read an official LEGO instruction booklet (attached) for two things only: its SECTIONS and its numbered BAGS.
SECTIONS: a booklet can hold more than the main model. Step numbers start again at 1 for each section. Say what each
section is: part of the MAIN model (the box-front model: its chapters, sub-models built separately and attached,
later bags), a MINIFIGURE or small accessory built on its own, or an ALTERNATE build (a different, complete model from
the same pieces, as in 3-in-1 sets: it ends with its own finished model). Give each section's first and last page.
BAGS (main model only). LEGO marks numbered bags in one or both of these ways: an OVERVIEW page near the start that
shows bag icons with big numbers (1, 2, 3 ...) next to pictures of the model at each stage; and/or a bag icon with a
big number where each bag's section starts. If either appears, the booklet HAS numbered bags. Use the overview's
pictures and the section starts to find where each bag's steps begin.
Sections of a booklet start with a picture of a bag with a big number: open bag 1, build steps ..., open bag 2, ...
For each bag give its number, the first and last booklet step built from it, and how many of each line of the
PARTS LIST below its steps use (read the parts call-out box of every step in the bag's section and add them up).
Every part the MAIN model uses must end up in exactly one bag, as many times as it uses it (an alternate build reuses
the same pieces, so do not count its call-outs again). Pieces not shown in any
call-out (spares are not listed) go in the bag whose steps use them. If the booklet has no numbered bags, return
numbered_bags = false and one bag (number 1) with every part."""


def parts_list(set_id):
    from graph.parts.lego import inventory as pl
    return pl.RebrickableDump.set_parts(set_id, minifigs=True) or []


def check_bags(plan, parts, restarts=()):
    issues = []
    secs = plan.get("sections") or []
    if secs and not any(x["kind"] == "main" for x in secs):
        issues.append(("B3", "no section is the main model"))
    for a, b in zip(secs, secs[1:]):
        if b["first_page"] <= a["last_page"]:
            issues.append(("B3", f"sections overlap or are out of page order: '{a['name']}' pages {a['first_page']}-"
                                 f"{a['last_page']}, '{b['name']}' pages {b['first_page']}-{b['last_page']}"))
    starts = {x["first_page"] for x in secs}
    missed = [p for p in restarts if not any(abs(p - q) <= 1 for q in starts)]
    if secs and missed:
        issues.append(("B3", f"step numbers start again on page(s) {missed}, but no section starts there"))
    want = {i: p["quantity"] for i, p in enumerate(parts, 1)}
    got = collections.Counter()
    for b in plan["bags"]:
        for x in b["parts"]:
            got[x["line"]] += x["count"]
    wrong = [(i, want.get(i, 0), got.get(i, 0)) for i in sorted(set(want) | set(got)) if want.get(i, 0) != got.get(i, 0)]
    if wrong:
        issues.append(("B1", "bag counts differ from the parts list: " + ", ".join(
            f"L{i} ({parts[i - 1]['name'][:30] if 0 < i <= len(parts) else '?'}): list {w}, bags {g}" for i, w, g in wrong[:40])))
    nums = [b["bag"] for b in plan["bags"]]
    if nums != list(range(1, len(nums) + 1)):
        issues.append(("B2", f"bags should be numbered 1, 2, 3 ... in booklet order; got {nums}"))
    steps = [(b["first_step"], b["last_step"]) for b in plan["bags"]]
    for (a1, b1), (a2, b2) in zip(steps, steps[1:]):
        if a2 <= b1:
            issues.append(("B2", f"bag steps overlap or go backwards: {a1}-{b1} then {a2}-{b2}"))
    return issues


def read(set_id, pdf_bytes, model="sonnet", effort="high"):
    """Claude reads the booklet's bags. Returns (plan, parts, stats)."""
    from graph.extract import SubscriptionSession
    parts = parts_list(set_id)
    listing = "\n".join(f"L{i} | {p['part_num']} | {p['name']} | {p['color']} | x{p['quantity']}"
                        for i, p in enumerate(parts, 1))
    import pymupdf
    builds = lego_model.booklet_builds(pymupdf.open(stream=pdf_bytes, filetype="pdf"))
    restarts = [b[0][0] for b in builds[1:]]
    hint = (f"\n\nSTEP NUMBERS START AGAIN on page(s) {restarts} (found in the booklet's text): each of those starts a "
            f"section." if restarts else "")
    text = f"LEGO set {set_id}. PARTS LIST ({len(parts)} lines, minifigures included):\n{listing}{hint}"
    s = SubscriptionSession(text, "", "lego-v8", pdf=pdf_bytes, model=model, effort=effort, timeout=1800,
                            schema=BagPlan, system=BAGS_SYSTEM)
    phases = []
    try:
        plan, st = s.first()
        issues = check_bags(plan, parts, restarts)
        phases.append({"phase": "bags", **st, "issues": len(issues)})
        for n in range(BAG_REPAIRS):
            if not issues:
                break
            plan, st = s.repair("The bags have problems:\n" + "\n".join(f"- {r}: {m}" for r, m in issues) +
                                "\n\nReturn the COMPLETE corrected bags.")
            issues = check_bags(plan, parts, restarts)
            phases.append({"phase": f"repair{n + 1}", **st, "issues": len(issues)})
    finally:
        s.close()
    secs = plan.get("sections") or []
    stats = {"bags": len(plan["bags"]), "numbered": plan["numbered_bags"],
             "sections": [f"{x['kind']}: {x['name']} (pages {x['first_page']}-{x['last_page']})" for x in secs],
             "alternate_builds": sum(1 for x in secs if x["kind"] == "alternate"), "issues_final": [list(i) for i in issues],
             "seconds": round(sum(p["seconds"] for p in phases), 1),
             "cost_usd": round(sum(p["cost_usd"] for p in phases), 4), "repairs": len(phases) - 1}
    return plan, parts, stats


def _colour_key(name):
    return re.sub(r"[^a-z]", "", (name or "").lower().replace("grey", "gray"))


def assign(plan, parts, pieces):
    """{piece id: bag number} for the 3D model's pieces (in build order): each piece to the earliest bag that still
    has one of its design, preferring one of its colour. Pieces with no match go to the bag of the piece before."""
    left = collections.defaultdict(collections.Counter)  # bag -> Counter[(design, colour)]
    for b in plan["bags"]:
        for x in b["parts"]:
            if 0 < x["line"] <= len(parts):
                p = parts[x["line"] - 1]
                left[b["bag"]][(lego_model.canon(p["part_num"]), _colour_key(p["color"]))] += x["count"]
    order = [b["bag"] for b in plan["bags"]]
    out, last = {}, order[0] if order else 1
    for p in pieces:
        d, c = lego_model.canon(p["part_num"]), _colour_key(p["colour"])
        bag = next((b for b in order if left[b][(d, c)] > 0), None)
        if bag is None:
            bag = next((b for b in order if any(k[0] == d and v > 0 for k, v in left[b].items())), None)
            if bag is not None:
                k = next(k for k, v in left[bag].items() if k[0] == d and v > 0)
                left[bag][k] -= 1
        else:
            left[bag][(d, c)] -= 1
        out[p["id"]] = bag if bag is not None else last
        last = out[p["id"]]
    return out


if __name__ == "__main__":
    main()
