"""Domain recipes for the one pipeline (pipeline.py). A domain changes only data and policies, never the code
path (RESEARCH.md R22): where its parts and models come from (registry sections), which builder is tried first,
which prompt hint the builder uses, which laws check the graph, and which issues trigger a repair.
"""
from dataclasses import dataclass, replace
from typing import Optional, Tuple


@dataclass(frozen=True)
class Recipe:
    name: str
    parts_list: Optional[str]          # where a manual's parts list comes from first: "lego_sets" (Rebrickable),
                                       # "tutorial" (the tutorial's hardware section, by code), None (the build finds them)
    part_cards: str                    # registry section new part types are ingested from
    builders: Tuple[str, ...]          # tried in order: "ldraw" (model file by code), "pages" (booklet, joins),
                                       # "pieces" (booklet, each piece names what it rests on), "one-shot"
    hint: str                          # prompt hint key in extract.HINTS for the model-based builder
    catalogue: str                     # "full": every card in the prompt; "parts": only this manual's cards
    repair: str                        # "all": every issue the laws find; "real": REAL_RULES only
    repair_rounds: int = 2
    pages_per_turn: int = 1            # "pages" builder: one page (one to four steps) per turn
    ingest_new_types: bool = False     # after the build: card the types the model drafted, through the registry
    parts_count_law: bool = False      # E6: counts stated in the tutorial's parts list must match the graph
    store_catalogue: bool = False      # build prompt from the Layer 0 store (with card_notes.json), not the seed only
    consensus: int = 1                 # 2 = build twice independently, keep what both agree on (consensus.py)
    pins_law: bool = False             # E7: board pins the circuit text names must be wired
    electrical_laws: bool = False      # E8-E10 from the cards' electrical facts
    electrical_prompt: bool = False    # show the cards' electrical facts to the builder
    card_store: Optional[str] = None   # Layer 0 store (the parts database), relative to the repo; grows with every run
    recheck_after_upkeep: bool = False # after upkeep brings new cards: rerun the electrical laws, repair once
    lookup_tool: bool = False          # the builder can call lookup_part (database, then approved sites) while building
    geometry_law: bool = False         # L5: LEGO stacking checked against the cards' stud grids
    placement_law: bool = False        # B1/B2: breadboard placement from CircuitQuest's card facts (v6)
    table_laws: bool = False           # E11 pin tables in the tutorial, E12 matrix resistors on one side (v6)
    piece_laws: bool = False           # L6-L10 on the v7 piece list: ids, step order, tiles, capacity, positions
    text_guides: bool = False          # v8: written instructions for blind builders (registry lego_text_guides), if any
    notes: str = ""


DOMAINS = {
    "electronics": Recipe(
        name="electronics", parts_list="tutorial", part_cards="electronics", builders=("one-shot",), hint="arduino",
        catalogue="full", repair="all", ingest_new_types=True,
        notes="Parts first by code: the tutorial's hardware list is matched to the catalogue; only unmatched parts are "
              "looked up on the registry's shops (top result per shop, at most 3 prompt-engine checks each) before the build. Then the graph "
              "as in v2 (tutorial + images + catalogue, every issue repaired). A type the model still had to draft is "
              "carded afterwards for later tutorials."),
    "lego": Recipe(
        name="lego", parts_list="lego_sets", part_cards="lego", builders=("ldraw", "pages"), hint="lego-pages",
        catalogue="parts", repair="real",
        notes="Parts first from Rebrickable (booklet fallback). Path A: the set's LDraw model by code. Path B: the "
              "booklet one page at a time with the parts list; repair only real errors."),
}

REAL_RULES = frozenset({"E1", "E2", "E3", "E4", "E5", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12",
                        "L13", "L14"})


# v5: one change per domain on top of v4, so each effect can be measured (RESEARCH.md R22, "v5").
DOMAINS_V5 = {
    "electronics": replace(DOMAINS["electronics"], parts_list=None, builders=("parts-then-build",), hint="arduino-v5",
                           parts_count_law=True,
                           store_catalogue=True, pins_law=True, electrical_laws=True, electrical_prompt=True,
                           recheck_after_upkeep=True, lookup_tool=True, card_store="graphgen/data/cards_electronics.json",
                           notes="Parts first, in one conversation: turn 1 Claude lists the tutorial's parts (electronics "
                                 "has no part numbers, so Claude reads them), matching each to the card store and calling "
                                 "lookup_part (database, then the approved sites) for any it lacks; turn 2 adds the "
                                 "connections. Cards carry electrical facts. Laws: parts "
                                 "count per value (E6, missing only), board pins named in the circuit text wired (E7), "
                                 "electrical (E8-E10). After the graph, every part type Claude had to add is looked up on "
                                 "the registry's sites and stored; if that brings electrical facts, E8-E10 run again and "
                                 "one repair follows if they fail."),
    "lego": replace(DOMAINS["lego"], builders=("ldraw", "pieces"), hint="lego-pieces", geometry_law=True,
                    notes="v4, but Path B asks each piece what it rests on (code makes the joins), feeds every page "
                          "the pieces not placed yet, and checks stacking against the cards' stud grids (L5)."),
}
# v6: the issues every version shared, as laws and card facts (RESEARCH.md R22, "v6").
DOMAINS_V6 = {
    "electronics": replace(DOMAINS_V5["electronics"], hint="arduino-v6", placement_law=True, table_laws=True,
                           notes="v5 + breadboard placement as CircuitQuest models it (legs together in pin order, "
                                 "parts across the centre gap: laws B1/B2 and prompt), the tutorial's pin tables (E11) "
                                 "and LED-matrix resistors all on one side (E12)."),
    "lego": replace(DOMAINS_V5["lego"], builders=("ldraw-studs", "whole-pieces"), hint="lego-whole-pieces",
                    notes="Path A finds joins from the LDraw library's stud, hole and pin primitives (ldraw_studs.py), "
                          "with ports. Path B reads the WHOLE booklet in one turn (v3 kept every piece exact) and "
                          "answers in v5's rests_on format; a repair returns the complete list, so extras can go."),
}
# v7: LEGO contacts (RESEARCH.md R22, "v7"): every v6 change, plus one id per piece, positions and laws for Path B.
DOMAINS_V7 = {
    "electronics": DOMAINS_V6["electronics"],
    "lego": replace(DOMAINS_V6["lego"], builders=("ldraw-studs", "whole-pieces-v7"), hint="lego-v7", piece_laws=True,
                    notes="v6, and Path B gets a PIECE LIST with one id per physical piece (copies of a piece are "
                          "told apart); each piece gives its step, rests_on and position on the stud grid. Laws "
                          "L6-L10: ids, step order, nothing on smooth tiles, stud capacity, positions agree with "
                          "rests_on. Code also computes the joins from the positions alone (scored separately)."),
}
# v8: LEGO placements (RESEARCH.md R22, "v8"): Claude places each piece, code finds the joins from real shapes.
DOMAINS_V8 = {
    "electronics": DOMAINS_V7["electronics"],
    "lego": replace(DOMAINS_V7["lego"], builders=("ldraw-studs", "step-pieces-v8", "whole-pieces-v8"), hint="lego-v8",
                    text_guides=True,
                    notes="v7, but each piece gets a full placement: column and row in half studs, layer in plates, "
                          "turn/tilt/roll in degrees (0-360) and free_angle. Code snaps what the studs force (quarter "
                          "turns, the piece's own studs onto the grid, pins onto holes), places each piece's LDraw "
                          "part and finds the joins with the answer key's own stud and pin matching "
                          "(placement.py). Laws L11-L14: no two pieces in one space, nothing held by nothing, "
                          "rests_on agrees with the placements, one stud in one piece. Every set is looked up on both text-guide "
                          "sites (LEGO Audio & Braille, Bricks for the Blind); each written guide found is given with "
                          "the booklet. Booklets with step numbers as text are read a few steps a turn, each step's new pieces "
                          "boxed in red by comparing its picture with the previous step's (step_diff.py); others whole."),
}
VERSIONS = {"v4": DOMAINS, "v5": DOMAINS_V5, "v6": DOMAINS_V6, "v7": DOMAINS_V7, "v8": DOMAINS_V8}
