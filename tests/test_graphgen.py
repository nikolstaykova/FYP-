"""Offline tests for graphgen: no API calls. A hand-written graph in the exact
shape Claude must return goes through expansion, the rule checks, the logical
view and scoring."""
from graphgen import catalogue as cat
from graphgen import expand, logical, score, truth, validate


def part(id_, type_, **props):
    return {"id": id_, "type": type_, "label": None, "props": [{"key": k, "value": v} for k, v in props.items()]}


def wire_edges(u, up, v, vp):
    """A physical electrical connection: joined + electrical, as the spec requires."""
    base = {"u": u, "u_port": up, "v": v, "v_port": vp, "method": "insert", "freedom": "rigid", "reversible": "hand"}
    return [{**base, "type": "joined"}, {**base, "type": "electrical"}]


def for_loop_graph():
    """Six LED + resistor blocks on pins 2-7: one repeat, five `attach` overrides."""
    block_edges = (wire_edges("r", "1", "uno", "2") + wire_edges("r", "2", "led", "A")
                   + wire_edges("led", "C", "bb1", "bn.1"))
    return {
        "title": "For Loop Iteration", "source_id": "ForLoopIteration", "new_part_types": [],
        "parts": [part("uno", "arduino-uno"), part("bb1", "breadboard"), part("wire1", "jumper-wire")],
        "edges": wire_edges("wire1", "a", "bb1", "bn.30") + wire_edges("wire1", "b", "uno", "GND.1"), "notes": [],
        "repeats": [{
            "group": "ledblock", "times": 6,
            "parts": [part("r", "resistor", value="220"), part("led", "led")],
            "edges": block_edges,
            "overrides": [o for n in range(2, 7) for o in (
                {"copy_number": n, "kind": "attach", "target": "uno:2", "value": f"uno:{n + 1}"},
                {"copy_number": n, "kind": "attach", "target": "bb1:bn.1", "value": f"bb1:bn.{n}"})],
        }],
    }


def test_repeat_expands_to_six_real_copies():
    flat = expand.expand(for_loop_graph())
    assert sum(1 for n in flat["nodes"] if n["type"] == "led") == 6
    assert {n["id"] for n in flat["nodes"]} >= {"ledblock1.led", "ledblock6.r"}
    pins = sorted(e["v_port"] for e in flat["edges"] if e["type"] == "electrical" and e["u"].endswith(".r") and e["u_port"] == "1")
    assert pins == ["2", "3", "4", "5", "6", "7"]


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


def test_rules_catch_bad_graphs():
    catalogue = cat.Catalogue(cat.arduino_seed())
    g = {"title": "x", "source_id": "x", "new_part_types": [], "notes": [], "repeats": [],
         "parts": [part("uno", "arduino-uno"), part("led1", "led"), part("led2", "led"), part("bb1", "breadboard")],
         "edges": [*wire_edges("led1", "Z", "uno", "13"), *wire_edges("led1", "A", "bb1", "3b.c"),
                   *wire_edges("led1", "C", "bb1", "3b.c")]}
    rules = {r for r, _ in validate.validate(expand.expand(g), catalogue)}
    assert {"V2", "V4"} <= rules  # led2 unused; port Z missing; hole 3b.c used twice


def test_store_on_demand_adds_only_new_types():
    catalogue = cat.Catalogue({})
    draft = {"type": "photoresistor", "name": "LDR", "category": "sensor", "ports": [{"name": "1", "kind": "lead"}, {"name": "2", "kind": "lead"}],
             "conducts": [], "through": [["1", "2"]], "symmetric": [["1", "2"]], "polarized": False, "connector": False,
             "mirror_of": None, "rotation_symmetry": "none"}
    assert catalogue.add_drafts([draft]) == ["photoresistor"]
    assert catalogue.add_drafts([draft]) == []  # second manual reuses it
    assert catalogue.get("photoresistor")["status"] == "unverified"


def test_v3_parts_check_flags_only_real_differences():
    from graphgen import v3
    parts = [{"part_num": "3001", "quantity": 40}, {"part_num": "3023", "quantity": 20}]
    flat = {"nodes": [{"id": f"b{i}", "type": "lego-3001"} for i in range(40)]
                     + [{"id": f"p{i}", "type": "lego-3023"} for i in range(19)], "edges": []}
    assert v3.parts_check(flat, parts) == []  # one piece off in 60 is a slip, not worth a repair
    flat["nodes"] = flat["nodes"][:45]
    assert [r for r, _ in v3.parts_check(flat, parts)] == ["L4"]


def test_lego_card_from_code_and_site_ranking():
    from graphgen.parts import cards, sources
    card = cards.lego_card_code("3001", "Brick 2 x 4")
    assert sum(p["kind"] == "stud" for p in card["ports"]) == 8 and card["source"]["made_by"] == "code"
    assert cards.lego_card_code("3040", "Slope 45 2 x 1") is None  # not plain: goes to Claude
    ranked = sources.rank("micro servo", [("Servo - Micro", "u1"), ("LED strip", "u2"), ("Micro Servo SG92R", "u3")])
    assert [u for _, u in ranked] == ["u1", "u3"]
    product, text = sources.clean('<script type="application/ld+json">{"@type": "Product", "name": "Photo cell"}</script>'
                                  '<nav>menu</nav><p>Light sensor &amp; more</p>')
    assert product == {"name": "Photo cell"} and text == "Light sensor & more"


def test_series_order_is_equivalent_but_led_direction_is_not():
    types = {"uno": "arduino-uno", "r1": "resistor", "l1": "led"}
    a = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND"})]
    swapped = [frozenset({"uno:13", "l1:A"}), frozenset({"l1:C", "r1:1"}), frozenset({"r1:2", "uno:GND"})]
    reversed_led = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:C"}), frozenset({"l1:A", "uno:GND"})]
    flat = {"nodes": [{"id": k, "type": v} for k, v in types.items()]}
    truth_ = {"nets": a, "types": types}
    assert score.score_equivalent(flat, swapped, truth_)["eq_all_correct"]
    assert not score.score_equivalent(flat, reversed_led, truth_)["eq_all_correct"]


def test_parts_count_law_flags_only_missing_parts():
    from graphgen import checks
    flat = {"nodes": [{"id": "l1", "type": "led", "props": {}}, {"id": "l2", "type": "led", "props": {}},
                      {"id": "r1", "type": "resistor", "props": {"value": "10k"}},
                      {"id": "r2", "type": "resistor", "props": {"value": "220"}}], "edges": []}
    found = checks.parts_count(flat, [("led", 3, None), ("resistor", 1, checks.ohms("10k")), ("jumper-wire", 10, None)])
    assert [r for r, _ in found] == ["E6"] and "led" in found[0][1]  # 2 LEDs < 3 listed; the extra 220 ohm is allowed
    assert checks.parts_count(flat, [("resistor", 1, checks.ohms("4k7"))])  # a listed value the graph does not have


def test_pin_law_reads_board_pins_only():
    from graphgen import checks
    pins = checks.named_pins("MIDI jack pin 5 goes to digital pin 1. Pin 4 to 5V. Sensor on analog input 2. "
                             "The built-in LED on digital pin 13 blinks.")
    assert pins["digital"] == {"1"} and pins["analog"] == {"A2"}


def test_electrical_laws():
    from graphgen import checks
    catalogue = cat.Catalogue({"arduino-uno": {**cat.arduino_seed()["arduino-uno"], "electrical": {"logic_v": 5}},
                               "led": {**cat.arduino_seed()["led"], "electrical": {"needs_series_resistor": True}},
                               "rfid": cat._entry("rfid", "RFID", "module", [("3.3V", "header-pin"), ("SDA", "header-pin")],
                                                  electrical={"supply_v_max": 3.6, "logic_v": 3.3, "five_v_tolerant": False,
                                                              "power_pins": ["3.3V"]})})
    g = {"title": "", "source_id": "", "new_part_types": [], "notes": [], "repeats": [],
         "parts": [part("uno", "arduino-uno"), part("led1", "led"), part("rf", "rfid")],
         "edges": wire_edges("uno", "9", "led1", "A") + wire_edges("led1", "C", "uno", "GND.1")
                  + wire_edges("rf", "3.3V", "uno", "5V") + wire_edges("rf", "SDA", "uno", "10")}
    rules = sorted(r for r, _ in checks.electrical(expand.expand(g), catalogue))
    assert rules == ["E10", "E8", "E9"]


def test_consensus_keeps_agreement_and_drops_disputed():
    from graphgen import consensus
    catalogue = cat.Catalogue(cat.arduino_seed())
    g = for_loop_graph()
    _, report = consensus.agree(g, g, catalogue)
    assert report["agreed"] == report["relations_a"] > 0  # a graph agrees with itself completely
    other = for_loop_graph()
    other["repeats"][0]["overrides"] = [o for o in other["repeats"][0]["overrides"] if o["copy_number"] != 6]
    kept, report = consensus.agree(g, other, catalogue)
    assert report["agreed"] < report["relations_a"]  # copy 6 sits on another pin in the second build
    assert len(kept["edges"]) < len(expand.expand(g)["edges"])


def test_rests_on_becomes_one_join_per_support():
    from graphgen.pipeline import PieceBuild
    b = PieceBuild.__new__(PieceBuild)
    b.pieces, b.others, b.notes, b.title = {}, [], [], ""
    b._merge({"title": "t", "source_id": "", "notes": [], "other_joins": [],
              "pieces": [{"id": "b1", "type": "lego-3001", "colour": "Red", "rests_on": [], "position": None},
                         {"id": "b2", "type": "lego-3001", "colour": "Red", "rests_on": [], "position": None},
                         {"id": "b3", "type": "lego-3001", "colour": "Blue", "rests_on": ["b1", "b2"], "position": None}]})
    assert sorted((e["u"], e["v"]) for e in b.graph["edges"]) == [("b3", "b1"), ("b3", "b2")]


def test_sizes_are_not_quantities():
    from graphgen.parts import tutorial
    assert tutorial.quantity("8 x 8 LED Matrix") is None
    assert tutorial.clean("8 x 8 LED Matrix")[0] == "8 x 8 LED Matrix"
    assert tutorial.quantity("8x 1k ohm resistors") == 8 and tutorial.quantity("2 x 220 ohm resistors") == 2


def test_too_many_parts_law():
    from graphgen import checks
    text = ("## Circuit\nConnect an LED to digital pin 9 with a 220 ohm current limiting resistor in series. Connect a "
            "photoresistor to 5V and then to analog pin 0 with a 10K ohm resistor to ground.\n## Code\n")
    assert checks.text_mentions(checks.circuit_text(text), "resistor") == 2  # pin numbers and values are not counts
    three = {"nodes": [{"id": f"r{i}", "type": "resistor"} for i in range(3)], "edges": []}
    listed = [("led", 1), ("resistor", 1), ("resistor", 1)]
    assert [r for r, _ in checks.parts_extra(three, text, listed)] == ["E6"]
    assert checks.parts_extra(three, text, [("led", 1), ("resistor", None)]) == []  # "resistors": no limit


def test_substitute_pins_follow_circuitquest():
    types = {"uno": "arduino-uno", "r1": "resistor", "l1": "led"}
    key = [frozenset({"uno:13", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND"})]
    moved = [frozenset({"uno:12", "r1:1"}), frozenset({"r1:2", "l1:A"}), frozenset({"l1:C", "uno:GND.2"})]
    flat = {"nodes": [{"id": k, "type": v} for k, v in types.items()]}
    assert score.score_substitute(flat, moved, {"nets": key, "types": types}, manual="digitalWrite(13, HIGH);")["sub_all_correct"]
    assert not score.score_substitute(flat, moved, {"nets": key, "types": types},
                                      manual="for (int p = 2; p < 14; p++) { digitalWrite(p, HIGH); }")["sub_all_correct"]


def test_lego_stacking_law():
    from graphgen import checks
    from graphgen.parts.cards import lego_card_code
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
TURN = "0 0 1 0 1 0 -1 0 0"  # 90 degrees about the vertical axis
FLAT = "1 0 0 0 1 0 0 0 1"


def _joins(*lines):
    from graphgen import ldraw_studs
    text = "0 FILE test.ldr\n0 !LDRAW_ORG Model\n" + "\n".join(f"1 4 {l}" for l in lines)
    placed = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(truth.flatten_mpd(text), 1)]
    found = ldraw_studs.connections(placed)
    return {tuple(sorted(k)): v[0] for k, v in found.items()}, ldraw_studs.validate(placed, found)


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


def test_parts_embedded_in_a_model_file_are_one_piece():
    text = ("0 FILE main.ldr\n0 !LDRAW_ORG Model\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 custom.dat\n"
            "0 FILE custom.dat\n0 !LDRAW_ORG Unofficial_Part\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 stud.dat\n"
            "1 16 0 0 0 1 0 0 0 1 0 0 0 1 box5.dat\n")
    assert [p[0] for p in truth.flatten_mpd(text)] == ["custom.dat"]


def test_v7_piece_laws_and_position_joins():
    from graphgen import checks
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


def test_v8_placements_give_joins():
    from graphgen import placement
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


def placement_round_trip(set_id):
    from graphgen import placement
    return placement.round_trip((truth.pathlib.Path(__file__).resolve().parents[1] / "research" / "raw" / "lego"
                                 / f"{set_id}.mpd").read_text(errors="replace"))


def test_ar_export_check_and_pictures():
    from graphgen import ar
    pieces, found = ar.from_ldraw("4991-1")  # Plan A: the set's own model
    out = ar.export("4991-1", pieces, found, "ldraw")
    first = out["steps"][0]["add"]
    anchor = next(p for p in first if p["id"] == out["anchor"]["id"])
    assert (anchor["column"], anchor["row"], anchor["layer"]) == (0, 0, 0)  # the anchor's corner is the origin
    from graphgen import ldraw_geometry as geo
    b = geo.world_box(anchor["ldraw"], anchor["pos_ldu"], anchor["rot"])
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
    pages = ar.booklet_steps(ar.ROOT / "research" / "raw" / "lego_pdf" / "30103-1.pdf")
    assert len(pages) == 8 and pages[0][1][0] < pages[2][1][0]  # step 1 left column, step 3 right column


def test_v8_relative_placements_chain_without_drift():
    from graphgen import placement
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


def test_ar_circuit_steps_and_checks():
    import copy
    from graphgen import ar_circuit, catalogue as cat
    j = lambda u, up, v, vp: [{"type": t, "u": u, "u_port": up, "v": v, "v_port": vp} for t in ("joined", "electrical")]
    flat = {"nodes": [{"id": "uno", "type": "arduino-uno"}, {"id": "bb", "type": "breadboard"},
                      {"id": "r", "type": "resistor", "props": {"value": "220"}}, {"id": "led", "type": "led"},
                      {"id": "w1", "type": "jumper-wire", "props": {"colour": "orange"}},
                      {"id": "w2", "type": "jumper-wire", "props": {"colour": "black"}}],
            "edges": j("r", "1", "bb", "3b.h") + j("r", "2", "bb", "6b.h") + j("led", "A", "bb", "6b.i")
                     + j("led", "C", "bb", "8b.i") + j("w1", "1", "uno", "13") + j("w1", "2", "bb", "3b.g")
                     + j("w2", "1", "bb", "8b.g") + j("w2", "2", "uno", "GND.1")}
    c = cat.Catalogue(cat.arduino_seed())
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
