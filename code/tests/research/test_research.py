"""Tests of the research versions kept in code/tests/research (not part of the product)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "unit"))
import catalogue as cat  # noqa: E402
import expand, logical, score, validate  # noqa: E402,E401 (the research copies)
from test_graphgen import for_loop_graph, part, wire_edges  # noqa: E402,F401 (shared helpers)
import ldraw_studs  # noqa: E402
import truth  # noqa: E402

TURN = "0 0 1 0 1 0 -1 0 0"  # 90 degrees about the vertical axis
FLAT = "1 0 0 0 1 0 0 0 1"


def _joins(*lines):
    text = "0 FILE test.ldr\n0 !LDRAW_ORG Model\n" + "\n".join(f"1 4 {l}" for l in lines)
    placed = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(truth.flatten_mpd(text), 1)]
    found = ldraw_studs.connections(placed)
    return {tuple(sorted(k)): v[0] for k, v in found.items()}, ldraw_studs.validate(placed, found)


def placement_round_trip(set_id):
    import placement
    return placement.round_trip((pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "lego"
                                 / f"{set_id}.mpd").read_text(errors="replace"))


def test_v3_parts_check_flags_only_real_differences():
    import v3
    parts = [{"part_num": "3001", "quantity": 40}, {"part_num": "3023", "quantity": 20}]
    flat = {"nodes": [{"id": f"b{i}", "type": "lego-3001"} for i in range(40)]
                     + [{"id": f"p{i}", "type": "lego-3023"} for i in range(19)], "edges": []}
    assert v3.parts_check(flat, parts) == []  # one piece off in 60 is a slip, not worth a repair
    flat["nodes"] = flat["nodes"][:45]
    assert [r for r, _ in v3.parts_check(flat, parts)] == ["L4"]


def test_rests_on_becomes_one_join_per_support():
    from pipeline import PieceBuild
    b = PieceBuild.__new__(PieceBuild)
    b.pieces, b.others, b.notes, b.title = {}, [], [], ""
    b._merge({"title": "t", "source_id": "", "notes": [], "other_joins": [],
              "pieces": [{"id": "b1", "type": "lego-3001", "colour": "Red", "rests_on": [], "position": None},
                         {"id": "b2", "type": "lego-3001", "colour": "Red", "rests_on": [], "position": None},
                         {"id": "b3", "type": "lego-3001", "colour": "Blue", "rests_on": ["b1", "b2"], "position": None}]})
    assert sorted((e["u"], e["v"]) for e in b.graph["edges"]) == [("b3", "b1"), ("b3", "b2")]


def test_for_loop_scores_perfectly_against_circuitquest():
    catalogue = cat.Catalogue(cat.arduino_seed())
    flat = expand.expand(for_loop_graph())
    assert validate.validate(flat, catalogue) == []
    result = score.score_arduino(flat, logical.nets(flat, catalogue), truth.arduino_truth("for-loop"))
    assert result["all_nets_correct"], result
    assert result["inventory_correct"], result


def test_breadboard_and_wires_fold_away():
    """Same Blink circuit built through a breadboard and jumper wires gives the same nets."""
    g = {"title": "Blink", "source_id": "Blink", "new_part_types": [], "notes": [], "repeats": [],
         "parts": [part("uno", "arduino-uno"), part("bb1", "breadboard"), part("r1", "resistor", value="220"),
                   part("led1", "led"), part("wire1", "jumper-wire"), part("wire2", "jumper-wire")],
         "edges": (wire_edges("wire1", "a", "uno", "13") + wire_edges("wire1", "b", "bb1", "3b.g")
                   + wire_edges("r1", "1", "bb1", "3b.h") + wire_edges("r1", "2", "bb1", "6b.h")
                   + wire_edges("led1", "A", "bb1", "6b.i") + wire_edges("led1", "C", "bb1", "8b.i")
                   + wire_edges("wire2", "a", "bb1", "8b.g") + wire_edges("wire2", "b", "uno", "GND.2"))}
    catalogue = cat.Catalogue(cat.arduino_seed())
    flat = expand.expand(g)
    assert validate.validate(flat, catalogue) == []
    assert score.score_arduino(flat, logical.nets(flat, catalogue), truth.arduino_truth("blink"))["all_nets_correct"]


def test_stud_key_on_hand_built_models():
    base = f"0 0 0 {FLAT} 3001.dat"  # Brick 2 x 4
    assert _joins(base, f"0 -24 0 {FLAT} 3001.dat")[0] == {("b1", "b2"): "clutch"}            # stacked, aligned
    assert _joins(base, f"20 -24 0 {FLAT} 3001.dat")[0] == {("b1", "b2"): "clutch"}           # one stud along
    assert _joins(base, f"0 -24 0 {TURN} 3001.dat")[0] == {("b1", "b2"): "clutch"}            # crossed at 90 degrees
    assert _joins(base, f"80 0 0 {FLAT} 3001.dat")[0] == {}                                    # side by side
    assert _joins(base, f"0 -28 0 {FLAT} 3001.dat")[0] == {}                                   # floating above
    assert _joins(base, f"10 -24 0 {FLAT} 3001.dat")[0] == {}                                  # half a stud off the grid
    bridge = _joins(f"-20 0 0 {FLAT} 3003.dat", f"20 0 0 {FLAT} 3003.dat", f"0 -8 0 {FLAT} 3020.dat")[0]
    assert bridge == {("b1", "b3"): "clutch", ("b2", "b3"): "clutch"}                         # plate on two 2x2 bricks
    assert _joins(f"0 0 0 {FLAT} 3003.dat", f"0 -8 0 {FLAT} 3068b.dat")[0] == {("b1", "b2"): "clutch"}  # tile on a brick
    assert _joins(f"0 0 0 {FLAT} 3068b.dat", f"0 -24 0 {FLAT} 3003.dat")[0] == {}              # nothing holds on a tile
    tower, laws = _joins(*(f"0 {-24 * i} 0 {FLAT} 3005.dat" for i in range(4)))                # four 1x1 bricks
    assert sorted(tower) == [("b1", "b2"), ("b2", "b3"), ("b3", "b4")] and laws == []


def test_v8_placements_give_joins():
    import placement
    for t in [(0, 0, 0), (90, 0, 0), (37, 0, 0), (0, 90, 0), (270, 0, 90), (45, 30, 60)]:
        assert placement.angles(placement.rotation(*t)) == tuple(float(x) for x in t)  # angles invert rotation
    assert placement.size("3001.dat") == (4.0, 2.0, 3.0)
    assert placement.ldraw_file("3069bpr0100") == "3069b.dat" and placement.ldraw_file("4079b") == "4079.dat"
    pl = lambda c, r, layer, turn=0, free=False: placement.snapped(
        {"column": c, "row": r, "layer": layer, "turn": turn, "tilt": 0, "roll": 0, "free_angle": free})
    pairs = lambda **p: sorted(sorted(k) for k in placement.joins(p)[0])
    assert pairs(a=("3001.dat", pl(0, 0, 0)), b=("3001.dat", pl(1, 0, 3))) == [["a", "b"]]            # one stud along
    assert pairs(a=("3001.dat", pl(0, 0, 0)), b=("3001.dat", pl(1.1, -0.9, 3.2, 92))) == [["a", "b"]]  # rough reading
    assert pairs(a=("3001.dat", pl(0, 0, 0)), b=("3001.dat", pl(4, 0, 0))) == []                       # side by side
    assert pairs(a=("3001.dat", pl(0, 0, 0)), b=("3001.dat", pl(0, 0, 4))) == []                       # a plate too high
    assert pairs(a=("3068b.dat", pl(0, 0, 0)), b=("3003.dat", pl(0, 0, 1))) == []                      # nothing holds a tile
    found, placed = placement.joins({"a": ("3001.dat", pl(0, 0, 0)), "b": ("3001.dat", pl(1, 0, 0))})
    assert [r for r, _ in placement.laws(placed, found, {}, {})] == ["L11"]                           # same space


def test_v8_round_trip_on_a_real_model():
    """True placements of a real set, read back and snapped, give the set's own joins."""
    r = placement_round_trip("4991-1")
    assert r["joins_correct"] == r["joins_true"] == r["joins_found"]


def test_ar_export_check_and_pictures():
    import ar, ldraw_geometry
    pieces, found = ar.from_ldraw("4991-1")  # Plan A: the set's own model
    out = ar.export("4991-1", pieces, found, "ldraw")
    first = out["steps"][0]["add"]
    anchor = next(p for p in first if p["id"] == out["anchor"]["id"])
    assert (anchor["column"], anchor["row"], anchor["layer"]) == (0, 0, 0)  # the anchor's corner is the origin
    import ar, ldraw_geometry
    b = ldraw_geometry.world_box(anchor["ldraw"], anchor["pos_ldu"], anchor["rot"])
    assert b[3] - b[0] >= b[5] - b[2]  # and its long side runs along the columns
    step = next(s for s in out["steps"] if s["step"] > 1 and s["add"])
    seen = [{"part": p["ldraw"][:-4], **{k: p[k] for k in ("column", "row", "layer", "turn", "tilt", "roll")}}
            for p in step["add"]]
    exact = ar.check_step(out, step["step"], seen)
    assert len(exact["right"]) == len(step["add"]) and not exact["misplaced"] + exact["missing"] + exact["extra"]
    rough = [{**o, "column": o["column"] + 0.2, "layer": o["layer"] + 0.3} for o in seen]  # a camera's rough reading
    assert len(ar.check_step(out, step["step"], rough)["right"]) == len(step["add"])
    off = [{**seen[0], "column": seen[0]["column"] + 2}] + seen[1:]  # one piece two studs off
    assert [m["off_studs"] for m in ar.check_step(out, step["step"], off)["misplaced"]] == [2.0]
    pages = ar.booklet_steps(ar.ROOT / "data" / "sources" / "lego_pdf" / "30103-1.pdf")
    assert len(pages) == 8 and pages[0][1][0] < pages[2][1][0]  # step 1 left column, step 3 right column


def test_v8_relative_placements_chain_without_drift():
    import placement
    rel = lambda ref, c, r, layer, turn=0: {"relative_to": ref, "column": c, "row": r, "layer": layer, "turn": turn,
                                            "tilt": 0, "roll": 0, "free_angle": False}
    pieces = {"a": ("3001.dat", rel("", 5, 7, 0)),                    # anywhere: the first piece
              "b": ("3001.dat", rel("a", 1.2, 0.1, 3.3)),             # on a, one stud along, read roughly
              "c": ("3003.dat", rel("b", 2, -0.2, 2.8)),              # on b's right half
              "d": ("3001.dat", rel("a", -4, 0, 0))}                  # left of a on the same layer: touches only
    supports = {"b": {"a"}, "c": {"b"}}
    found, placed = placement.joins(pieces, supports, {"a": 1, "b": 2, "c": 3, "d": 3})
    assert sorted(sorted(k) for k in found) == [["a", "b"], ["b", "c"]]
    pos = {nid: p for nid, _, p, _ in placed}
    assert pos["b"][0] - pos["a"][0] == 20 and pos["c"][1] - pos["a"][1] == -48  # snapped exactly: no drift


def test_lsynth_segments_are_one_bendable_piece():
    seg = "1 0 0 0 0 1 0 0 0 1 0 0 0 1 {}\n"
    text = ("0 FILE main.ldr\n0 !LDRAW_ORG Model\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            "1 0 0 -24 0 1 0 0 0 1 0 0 0 1 hose.ldr\n"
            "0 FILE hose.ldr\n0 !LDRAW_ORG Model\n" + seg.format("ls50.dat") + seg.format("ls51.dat") * 30
            + seg.format("ls50.dat"))
    import stud_key
    pieces = [p[0] for p in truth.flatten_mpd(text)]
    assert pieces == ["3001.dat", "hose.ldr"]  # 32 segments, one hose
    assert stud_key.design("hose.ldr") == "75c24"


def test_pair_by_name_only_across_numbering_schemes():
    import collections
    import stud_key
    want = collections.Counter({"3666": 2, "fabupn0024": 2})   # set: Plate 1 x 6; Fabuland, Equipment Paint Brush
    model = collections.Counter({"3023": 2, "u669": 2})        # model: Plate 1 x 2; Fabuland Paint Brush
    _, pairs = stud_key.pair_by_name(want, model)
    assert [(a, b) for a, b, _ in pairs] == [("fabupn0024", "u669")]  # the brush, never two different plates


def test_series_order_is_equivalent_but_led_direction_is_not():
    import score
    types = {"uno": "arduino-uno", "r1": "resistor", "l1": "led"}
    a = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND"})]
    swapped = [frozenset({"uno:13", "l1:A"}), frozenset({"l1:C", "r1:1"}), frozenset({"r1:2", "uno:GND"})]
    reversed_led = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:C"}), frozenset({"l1:A", "uno:GND"})]
    flat = {"nodes": [{"id": k, "type": v} for k, v in types.items()]}
    truth_ = {"nets": a, "types": types}
    assert score.score_equivalent(flat, swapped, truth_)["eq_all_correct"]
    assert not score.score_equivalent(flat, reversed_led, truth_)["eq_all_correct"]


def test_substitute_pins_follow_circuitquest():
    import score
    types = {"uno": "arduino-uno", "r1": "resistor", "l1": "led"}
    key = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND"})]
    moved = [frozenset({"uno:12", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND.2"})]
    flat = {"nodes": [{"id": k, "type": v} for k, v in types.items()]}
    assert score.score_substitute(flat, moved, {"nets": key, "types": types}, manual="digitalWrite(13, HIGH);")["sub_all_correct"]
    assert not score.score_substitute(flat, moved, {"nets": key, "types": types},
                                      manual="for (int p = 2; p < 14; p++) { digitalWrite(p, HIGH); }")["sub_all_correct"]


def test_lego_stacking_law():
    import checks
    from graph.parts.cards import lego_card_code
    catalogue = cat.Catalogue({"lego-3001": lego_card_code("3001", "Brick 2 x 4"),
                               "lego-3070": lego_card_code("3070", "Tile 1 x 1"),
                               "lego-3005": lego_card_code("3005", "Brick 1 x 1")})
    stack = lambda u, v: {"type": "joined", "u": u, "v": v, "u_port": None, "v_port": None, "method": "stack"}
    flat = {"nodes": [{"id": "b1", "type": "lego-3001"}, {"id": "t1", "type": "lego-3070"}, {"id": "s1", "type": "lego-3005"},
                      {"id": "s2", "type": "lego-3005"}, {"id": "s3", "type": "lego-3005"}],
            "edges": [stack("s1", "t1"), stack("s2", "b1"), stack("s2", "s3"), stack("b1", "s2")]}
    rules = [m for r, m in checks.lego_geometry(flat, catalogue)]
    assert any("tile" in m for m in rules)            # s1 on a tile
    assert any("only 1 stud cells" in m for m in rules)  # a 1x1 brick on two pieces
    assert any("each rest on the other" in m for m in rules)


# --- v7: the stud answer key, checked on hand-built models whose right answer is known ----------------------
# LDraw: -Y is up, a brick is 24 LDU tall and a plate 8, one stud is 20 LDU, a part's origin is its top centre.


def test_v7_piece_laws_and_position_joins():
    import checks
    shape = checks.piece_shape
    assert shape("Brick 2 x 4") == {"w": 2, "l": 4, "h": 3, "smooth": False}
    assert shape("Brick 1 x 2 x 2")["h"] == 6 and shape("Slope 30 1 x 1 x 2/3")["h"] == 2
    assert shape("Tile 2 x 2")["smooth"] and not shape("Tile Special 1 x 2 with 1 Stud")["smooth"]
    assert shape("Technic Axle 4") is None
    info = {"p1": {"name": "Brick 2 x 4"}, "p2": {"name": "Brick 2 x 4"}, "p3": {"name": "Plate 1 x 2"},
            "p4": {"name": "Tile 2 x 2"}}
    for v in info.values():
        v["shape"] = shape(v["name"])
    pos = lambda x, y, layer, turned=False: {"x": x, "y": y, "layer": layer, "turned": turned}
    good = {"p1": {"step": 1, "rests_on": [], "position": pos(0, 0, 0)},
            "p2": {"step": 2, "rests_on": ["p1"], "position": pos(1, 0, 3)},         # one stud along, on top
            "p3": {"step": 3, "rests_on": ["p2"], "position": pos(4, 0, 6, True)},  # turned, over p2's last column
            "p4": {"step": 3, "rests_on": [], "position": pos(-1, 0, 3)}}           # on p1's free end, overhanging
    assert set(checks.position_joins(good, info)) == {("p2", "p1"), ("p3", "p2"), ("p4", "p1")}
    rules = [r for r, _ in checks.lego_pieces(good, info)]
    assert rules == ["L10"]  # p4 sits on p1 by position but does not say so
    good["p4"]["rests_on"] = ["p1"]
    assert checks.lego_pieces(good, info) == []
    bad = {"p1": {"step": 2, "rests_on": ["p4"], "position": None},                  # on a tile, tile added later?
           "p2": {"step": 1, "rests_on": ["p1"], "position": None},                  # rests on a later piece
           "p4": {"step": 1, "rests_on": [], "position": None},
           "p9": {"step": 1, "rests_on": [], "position": None}}                      # not in the list; p3 missing
    rules = sorted(r for r, _ in checks.lego_pieces(bad, info))
    assert rules == ["L6", "L6", "L7", "L8"]


def test_ar_circuit_steps_and_checks():
    import copy
    import ar_circuit
    from graph.parts import part_catalogue
    j = lambda u, up, v, vp: [{"type": t, "u": u, "u_port": up, "v": v, "v_port": vp} for t in ("joined", "electrical")]
    flat = {"nodes": [{"id": "uno", "type": "arduino-uno"}, {"id": "bb", "type": "breadboard"},
                      {"id": "r", "type": "resistor", "props": {"value": "220"}}, {"id": "led", "type": "led"},
                      {"id": "w1", "type": "jumper-wire", "props": {"colour": "orange"}},
                      {"id": "w2", "type": "jumper-wire", "props": {"colour": "black"}}],
            "edges": j("r", "1", "bb", "3b.h") + j("r", "2", "bb", "6b.h") + j("led", "A", "bb", "6b.i")
                     + j("led", "C", "bb", "8b.i") + j("w1", "1", "uno", "13") + j("w1", "2", "bb", "3b.g")
                     + j("w2", "1", "bb", "8b.g") + j("w2", "2", "uno", "GND.1")}
    c = part_catalogue.Catalogue(part_catalogue.arduino_seed())
    ar = ar_circuit.export("blink", flat, c)
    order = [a["id"] for s in ar["steps"] for a in s["add"]]
    assert order == ["uno", "bb", "r", "led", "w1", "w2"]  # board, breadboard, parts left to right, ground wire last
    assert ar_circuit.hole_mm("6b.h") == [12.7, 22.86] and ar_circuit.hole_mm("6t.e")[1] + 7.62 == ar_circuit.hole_mm("6b.f")[1]
    led_step = next(s["step"] for s in ar["steps"] if s["add"][0]["id"] == "led")
    seen = lambda a, c_: [{"id": "led", "leg": "A", "part": "bb", "port": a}, {"id": "led", "leg": "C", "part": "bb", "port": c_}]
    assert ar_circuit.check_step(ar, led_step, seen("6b.i", "8b.i"))["right"] == ["led.A", "led.C"]
    assert ar_circuit.check_step(ar, led_step, seen("6b.j", "8b.i"))["equivalent"] == ["led.A"]  # same strip: fine
    wrong = ar_circuit.check_step(ar, led_step, seen("7b.i", "8b.i"))["wrong"]
    assert wrong == [{"leg": "led.A", "want": "6b.i", "got": "7b.i"}]                                # next strip: wrong
    gnd = next(s["step"] for s in ar["steps"] if s["add"][0]["id"] == "w2")
    swapped = [{"id": "w2", "leg": "end1", "part": "uno", "port": "GND.2"}, {"id": "w2", "leg": "end2", "part": "bb", "port": "8b.f"}]
    assert ar_circuit.check_step(ar, gnd, swapped)["equivalent"] == ["w2"]  # ends swapped, other GND pin, same strip
    moved = copy.deepcopy(flat)
    for e in moved["edges"]:
        if e["u"] == "led" and e["u_port"] == "A":
            e["v_port"] = "6t.a"  # the anode into the other half of the board: not connected to the resistor
    assert ar_circuit.check_circuit(flat, flat, c)["same"] and not ar_circuit.check_circuit(flat, moved, c)["same"]
