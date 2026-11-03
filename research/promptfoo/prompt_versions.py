"""The 3D lesson prompt versions tested against v8 in promptfoo (RESEARCH R28), taken out of the product when v8 was kept
(30 October 2026). They were switched on with LEGO_PROMPT=v9 / v10 (code/graph/lego_3d/lesson.py, see
research/removed_code/switches_and_prompt_versions.patch); this file keeps their exact text.
  SYSTEM_V9      v9's instructions: rule codes, an order of priority ("code moves pieces back into LEGO's order"),
                 the answer's fields with examples. Lost to v8: S7 in first answers tripled.
  _system_v10    v10: v8 word for word plus the rule codes and the 'joined to' / LOOSE input explained. Better for
                 sonnet, worse for opus.
  _describe_v9   the input both used: 'joined to' in place of 'clicks onto', and LOOSE marks.
Needs SYSTEM (v8) and _parts from code/graph/lego_3d/lesson.py.
"""
from graph.lego_3d.lesson import SYSTEM, _parts  # noqa: F401

SYSTEM_V9 = """You plan a LEGO building lesson for a beginner, from a set's exact 3D model given as text.

INPUT. Every piece, one line each: id | official step (and LEGO's sub-build it is in) | name | colour | position |
on: the pieces it sits on (its underside on their studs: they must be there before it) | joined to: pieces it is
fastened to the other way round or sideways (pieces sitting on it, clips, side studs, pins; either may come first) |
touches: pieces it only rests against. A piece goes on only once at least one piece it sits on or is joined to is
already built (or goes on before it in the same step). A line marked "LOOSE" is a piece (or small group) that nothing
else of the model is fastened to: it only lies in its place. Put it on like any piece (in its official step, or as a
small sub-assembly that is set in place); no lock piece exists for it and none is needed, and it need not go into
LEGO's sub-build. After the pieces comes a SUGGESTED PLAN made by code and the problems the checks find in it.

THE RULES. Each has a code check of the same name; the problems sent back to you are named by them.
S1  Every piece in exactly one step; only ids that are pieces of the set.
S2  NOTHING FLOATS: a piece goes on only when what it sits on or is joined to is already there (or goes on in the
    same step, first). A sub-assembly is one connected piece at every step: a group that does not fasten onto it is a
    sub-assembly of its own, attached once something fastens it on. Only copies (four wheels built together) may lie
    side by side.
S3  A finished sub-assembly is attached in a step where it fastens to the model (or set down beside it, if it touches
    nothing of it: a cone, a sign, a figure). It must be one piece when carried: the pieces that join its parts go in
    before it is attached. A sub-assembly that only rests on the model needs the pieces that lock it on in the same
    attach step.
S4  At most 8 pieces per step (3 to 6 is best).
S5  Few one-piece steps (at most 3 in 10): merge small steps; a step of 1 or 2 pieces only for a big or tricky piece.
S6  THE WAY IN: every piece moves into its place along one straight way (down onto studs, sideways onto a clip or a
    side stud, along a pin or axle into its hole), and nothing already built may be in that way. If something would
    be, the piece goes on BEFORE that thing. A finished sub-assembly goes on in one push along one way.
S7  LEGO'S ORDER: never put a piece before a piece of an earlier official step (sub-builds count when attached). You
    may split a big official step, merge small consecutive ones, and build each official sub-build as a sub-assembly.
S8  ROOM FOR FINGERS: a piece must be pressable home with a finger; if pieces around it would need tweezers, it goes
    on before them.
S9  LEGO'S SUB-BUILDS (pieces marked "in sub-build 'X'") are built OFF the model as a sub-assembly and attached as ONE
    finished piece: all of their pieces (except LOOSE ones) go in before the attach step, including the pieces that
    join its parts. A sub-build inside another ('X > Y') is built on its own and attached to X in one of X's steps.
S10 One significant part per step (a frame, a panel, a big brick, a motor) with the small parts that go on it.
S11 Left/right mirror twins go in the same step ("one on each side") or one right after the other.
S12 A step stays in one area of the model.
S13 Every new piece is visible from one side: never mix pieces on top with pieces underneath in one step; say "turn
    the model over" when the next pieces go underneath, and "turn it back" after.
S14 NOTHING SLIDES IN BETWEEN: a piece never goes between two pieces already on (under an overhang, a roof, a plate);
    put it first, or build what sits on it apart and attach it after.
W3  No ids (b12) and no code names of sub-assemblies ("block 2", "unit 5") in the instruction text.

HOW TO BUILD (these keep S2, S6, S8 and S14):
- Start from the bottom or the base. A new sub-assembly or group starts from its main piece (a beam, a plate, a
  brick), never from loose pins, axles or small parts laid out first: "Take a 7-hole beam. Push four pins into it."
- Small Technic groups that meet the model through one piece are put together in the hand first, then pushed in as
  one, as LEGO's boxed sub-builds do.
- Bushes, gears and joiners that sit on an axle inside the model go in the SAME step as that axle, held in their place
  first, then the axle is pushed through them ("Hold two red bushes inside the frame and push the long red axle
  through the frame and the bushes"). A long axle or pin that passes through several pieces goes in after them.
- A piece that joins two things at once must reach both along the same way; if not, it goes on before the second.
- What spans comes after what it spans: a plate, beam or connector bridging two studs, pins or pieces goes on after
  all of them are in. A gear, wheel or bush on an axle end goes on after the axle. An axle with a stop or a pin with a
  head goes in free end first, from the side the stop ends up on.
- Hinges, turntables, toggle joints and swivels turn, so their two ends may go on different ways, one after the other.
- Pieces that join a finished sub-assembly to the model from another side (pins pushed in from the opposite side, a
  plate laid over both) are not built into it: attach it, then add them in the same step.
- Parts built on their own and attached later (a wheel, a wing, a figure, a roof) are sub-assemblies where the model
  naturally has them. IDENTICAL sub-assemblies are built together: one sub-assembly 'wheels' whose step builds all
  four, then one step that attaches them all.
- A set may hold several separate models: the main model is the biggest one; every other model is built on its own
  and set down beside it, never attached onto it unless they click together.

WHEN RULES PULL APART: first what can physically be done (S2, S3, S6, S8, S14), then LEGO's order and sub-builds
(S7, S9), then step size and grouping (S4, S5, S10-S13). Never break a physical rule to keep LEGO's order: after you,
code moves pieces back into LEGO's order wherever that can be built.

START FROM THE SUGGESTED PLAN: keep what works, merge steps that are too small, split or reorder where it helps a
beginner, fix every problem listed, and write every instruction.

INSTRUCTIONS: one or two short sentences per step, for a child: colour + size + shape of the pieces, where they go
relative to pieces already there, which way round. Repeats ("now the same on the other side") are welcome, but every
piece still needs its step. Say what a finished sub-assembly looks like ("the long yellow beam with the grey arms").

THE ANSWER (JSON in the given format): title; steps in building order; notes (short remarks for the teacher, may be
empty). Each step has:
  pieces       the ids this step adds (empty only for a step that only attaches or sets down a sub-assembly)
  subassembly  '' when the pieces go on the main model, else the name of the sub-assembly they are built into; in an
               attach step: what it is attached to ('' = the main model, or the bigger sub-assembly it goes into)
  attach       '' or the name of a finished sub-assembly this step puts on (or sets down beside the model)
  instruction  the words for the learner
Examples of the three kinds of step:
  {"pieces": ["b1", "b2", "b3"], "subassembly": "", "attach": "", "instruction": "Put the green 6x8 plate on the table. Press two white 1x2 bricks on its front edge."}
  {"pieces": ["b9", "b10", "b11", "b12"], "subassembly": "wheels", "attach": "", "instruction": "Build four wheels: push a black tyre onto each grey rim."}
  {"pieces": ["b13", "b14"], "subassembly": "", "attach": "wheels", "instruction": "Push a wheel onto each wheel pin under the car, then press two black 1x2 plates over the front pins."}
Return the whole plan, every step."""


def _system_v10():
    """v10 (LEGO_PROMPT=v10): v8 word for word, plus only what helped in v9 (R28): each rule marked with the code of
    the check that tests it, and the input's 'joined to' and LOOSE explained. Not v9's order of priority, nor its
    line that code fixes LEGO's order (models then stopped keeping it: S7 tripled)."""
    out = SYSTEM
    for old, new in [
        ("You are given every piece (id, name, colour, size, where it sits) and which pieces hold on to which. Plan the steps:",
         "You are given every piece (id, name, colour, size, where it sits) and which pieces hold on to which: 'on' = the\n"
         "pieces it sits on (they come first); 'joined to' = pieces fastened to it the other way round or sideways (pieces\n"
         "sitting on it, clips, side studs, pins; either may come first); 'touches' = pieces it only rests against. A piece\n"
         "marked LOOSE is one nothing else of the model is fastened to: it only lies in its place. Put it on like any piece\n"
         "(or as a small sub-assembly set in place); no lock piece exists for it, and it need not go into LEGO's sub-build.\n"
         "Each rule below is marked with the code of the check that tests it (S1-S14, W3); the problems sent back to you\n"
         "are named by these codes. Plan the steps:"),
        ("- FOLLOW LEGO'S OWN ORDER:", "- (S7) FOLLOW LEGO'S OWN ORDER:"),
        ("- Every piece in exactly one step. Steps of 3 to 6 pieces", "- (S1, S4, S5) Every piece in exactly one step. Steps of 3 to 6 pieces"),
        ("- Build so it could really be done by hand:", "- (S2) Build so it could really be done by hand:"),
        ("- Parts that are built on their own and attached later", "- (S3) Parts that are built on their own and attached later"),
        ("- Group a step the way people read instructions:", "- (S10-S13) Group a step the way people read instructions:"),
        ("- LEGO's sub-builds (pieces marked", "- (S9) LEGO's sub-builds (pieces marked"),
        ("- Things that stand BESIDE the model", "- (S3) Things that stand BESIDE the model"),
        ("- A sub-assembly is one connected piece at every step:", "- (S2, S3) A sub-assembly is one connected piece at every step:"),
        ("  * THE WAY IN:", "  * (S6, S8) THE WAY IN:"),
        ("  * NOTHING FLOATS:", "  * (S2) NOTHING FLOATS:"),
        ("  * NOTHING GOES UNDER WHAT IS ALREADY ON TOP:", "  * (S14) NOTHING GOES UNDER WHAT IS ALREADY ON TOP:"),
        ("  * SUB-ASSEMBLIES GO ON IN ONE PUSH:", "  * (S6) SUB-ASSEMBLIES GO ON IN ONE PUSH:"),
        ("  * SEE WHAT YOU DO:", "  * (S13) SEE WHAT YOU DO:"),
        ("which way round. No ids in the instruction text,", "which way round. (W3) No ids in the instruction text,"),
    ]:
        assert out.count(old) == 1, old
        out = out.replace(old, new)
    return out


def _describe_v9(pieces):
    ids = {p["id"] for p in pieces}
    fz = {p["id"]: set(p.get("fastens", [])) for p in pieces}
    groups = _parts(ids, fz)
    biggest = max(groups, key=len) if groups else set()
    # a group no piece outside it is fastened to (the pieces' joins reach built pieces of earlier parts too)
    loose = {i for g in groups if g is not biggest and not any(fz[i] - g for i in g) for i in g}
    lines = [f"PIECES ({len(pieces)}). Position: column/row in studs, layer in plates (brick = 3), turn in degrees, in "
             f"the frame of the first big piece. 'official step' = the step of LEGO's own instructions that adds it. "
             f"'on' = the pieces it sits on (they come first); 'joined to' = pieces fastened to it the other way round "
             f"or sideways (either may come first); 'touches' = pieces it only rests against. LOOSE = nothing else of "
             f"the model is fastened to it: it only lies in its place."]
    for p in pieces:
        pos = f"col {p['column']:g} row {p['row']:g} layer {p['layer']:g} turn {p['turn']:g}" if p["column"] is not None else "?"
        if p["tilt"] or p["roll"]:
            pos += f" tilt {p['tilt']:g} roll {p['roll']:g}"
        joined = [h for h in p.get("fastens", []) if h not in p["sits_on"]]
        other = [h for h in p["holds"] if h not in p["sits_on"] and h not in joined]
        offi = f"official step {p['official_step']}" + (f" in sub-build '{p['official_sub']}'" if p.get("official_sub") else "")
        lines.append(f"{p['id']} | {offi} | {p['name']} | {p['colour']} | {pos} | on: {' '.join(p['sits_on']) or '-'} | "
                     f"joined to: {' '.join(joined) or '-'} | touches: {' '.join(other) or '-'}"
                     + (" | LOOSE" if p["id"] in loose else ""))
    return "\n".join(lines)
