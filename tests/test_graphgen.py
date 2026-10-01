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
