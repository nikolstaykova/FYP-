"""Offline tests for graphgen: no API calls. A hand-written graph in the exact
shape Claude must return goes through expansion, the rule checks, the logical
view and scoring."""
import pathlib

from graph.parts import part_catalogue
from graph.arduino import circuit_graph
from graph import lego_model


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
    flat = circuit_graph.expand(for_loop_graph())
    assert sum(1 for n in flat["nodes"] if n["type"] == "led") == 6
    assert {n["id"] for n in flat["nodes"]} >= {"ledblock1.led", "ledblock6.r"}
    pins = sorted(e["v_port"] for e in flat["edges"] if e["type"] == "electrical" and e["u"].endswith(".r") and e["u_port"] == "1")
    assert pins == ["2", "3", "4", "5", "6", "7"]


def test_rules_catch_bad_graphs():
    catalogue = part_catalogue.Catalogue(part_catalogue.arduino_seed())
    g = {"title": "x", "source_id": "x", "new_part_types": [], "notes": [], "repeats": [],
         "parts": [part("uno", "arduino-uno"), part("led1", "led"), part("led2", "led"), part("bb1", "breadboard")],
         "edges": [*wire_edges("led1", "Z", "uno", "13"), *wire_edges("led1", "A", "bb1", "3b.c"),
                   *wire_edges("led1", "C", "bb1", "3b.c")]}
    rules = {r for r, _ in circuit_graph.validate(circuit_graph.expand(g), catalogue)}
    assert {"V2", "V4"} <= rules  # led2 unused; port Z missing; hole 3b.c used twice


def test_store_on_demand_adds_only_new_types():
    catalogue = part_catalogue.Catalogue({})
    draft = {"type": "photoresistor", "name": "LDR", "category": "sensor", "ports": [{"name": "1", "kind": "lead"}, {"name": "2", "kind": "lead"}],
             "conducts": [], "through": [["1", "2"]], "symmetric": [["1", "2"]], "polarized": False, "connector": False,
             "mirror_of": None, "rotation_symmetry": "none"}
    assert catalogue.add_drafts([draft]) == ["photoresistor"]
    assert catalogue.add_drafts([draft]) == []  # second manual reuses it
    assert catalogue.get("photoresistor")["status"] == "unverified"



def test_lego_card_from_code_and_site_ranking():
    from graph.parts import cards
    from graph.parts import ingest
    card = cards.lego_card_code("3001", "Brick 2 x 4")
    assert sum(p["kind"] == "stud" for p in card["ports"]) == 8 and card["source"]["made_by"] == "code"
    assert cards.lego_card_code("3040", "Slope 45 2 x 1") is None  # not plain: goes to Claude
    ranked = ingest.rank("micro servo", [("Servo - Micro", "u1"), ("LED strip", "u2"), ("Micro Servo SG92R", "u3")])
    assert [u for _, u in ranked] == ["u1", "u3"]
    product, text = ingest.clean('<script type="application/ld+json">{"@type": "Product", "name": "Photo cell"}</script>'
                                  '<nav>menu</nav><p>Light sensor &amp; more</p>')
    assert product == {"name": "Photo cell"} and text == "Light sensor & more"


def test_parts_count_law_flags_only_missing_parts():
    flat = {"nodes": [{"id": "l1", "type": "led", "props": {}}, {"id": "l2", "type": "led", "props": {}},
                      {"id": "r1", "type": "resistor", "props": {"value": "10k"}},
                      {"id": "r2", "type": "resistor", "props": {"value": "220"}}], "edges": []}
    found = circuit_graph.parts_count(flat, [("led", 3, None), ("resistor", 1, circuit_graph.ohms("10k")), ("jumper-wire", 10, None)])
    assert [r for r, _ in found] == ["E6"] and "led" in found[0][1]  # 2 LEDs < 3 listed; the extra 220 ohm is allowed
    assert circuit_graph.parts_count(flat, [("resistor", 1, circuit_graph.ohms("4k7"))])  # a listed value the graph does not have


def test_pin_law_reads_board_pins_only():
    pins = circuit_graph.named_pins("MIDI jack pin 5 goes to digital pin 1. Pin 4 to 5V. Sensor on analog input 2. "
                             "The built-in LED on digital pin 13 blinks.")
    assert pins["digital"] == {"1"} and pins["analog"] == {"A2"}


def test_electrical_laws():
    catalogue = part_catalogue.Catalogue({"arduino-uno": {**part_catalogue.arduino_seed()["arduino-uno"], "electrical": {"logic_v": 5}},
                               "led": {**part_catalogue.arduino_seed()["led"], "electrical": {"needs_series_resistor": True}},
                               "rfid": part_catalogue._entry("rfid", "RFID", "module", [("3.3V", "header-pin"), ("SDA", "header-pin")],
                                                  electrical={"supply_v_max": 3.6, "logic_v": 3.3, "five_v_tolerant": False,
                                                              "power_pins": ["3.3V"]})})
    g = {"title": "", "source_id": "", "new_part_types": [], "notes": [], "repeats": [],
         "parts": [part("uno", "arduino-uno"), part("led1", "led"), part("rf", "rfid")],
         "edges": wire_edges("uno", "9", "led1", "A") + wire_edges("led1", "C", "uno", "GND.1")
                  + wire_edges("rf", "3.3V", "uno", "5V") + wire_edges("rf", "SDA", "uno", "10")}
    rules = sorted(r for r, _ in circuit_graph.electrical(circuit_graph.expand(g), catalogue))
    assert rules == ["E10", "E8", "E9"]


def test_consensus_keeps_agreement_and_drops_disputed():
    import consensus
    catalogue = part_catalogue.Catalogue(part_catalogue.arduino_seed())
    g = for_loop_graph()
    _, report = consensus.agree(g, g, catalogue)
    assert report["agreed"] == report["relations_a"] > 0  # a graph agrees with itself completely
    other = for_loop_graph()
    other["repeats"][0]["overrides"] = [o for o in other["repeats"][0]["overrides"] if o["copy_number"] != 6]
    kept, report = consensus.agree(g, other, catalogue)
    assert report["agreed"] < report["relations_a"]  # copy 6 sits on another pin in the second build
    assert len(kept["edges"]) < len(circuit_graph.expand(g)["edges"])



def test_sizes_are_not_quantities():
    from graph.parts.arduino import tutorial
    assert tutorial.quantity("8 x 8 LED Matrix") is None
    assert tutorial.clean("8 x 8 LED Matrix")[0] == "8 x 8 LED Matrix"
    assert tutorial.quantity("8x 1k ohm resistors") == 8 and tutorial.quantity("2 x 220 ohm resistors") == 2


def test_too_many_parts_law():
    text = ("## Circuit\nConnect an LED to digital pin 9 with a 220 ohm current limiting resistor in series. Connect a "
            "photoresistor to 5V and then to analog pin 0 with a 10K ohm resistor to ground.\n## Code\n")
    assert circuit_graph.text_mentions(circuit_graph.circuit_text(text), "resistor") == 2  # pin numbers and values are not counts
    three = {"nodes": [{"id": f"r{i}", "type": "resistor"} for i in range(3)], "edges": []}
    listed = [("led", 1), ("resistor", 1), ("resistor", 1)]
    assert [r for r, _ in circuit_graph.parts_extra(three, text, listed)] == ["E6"]
    assert circuit_graph.parts_extra(three, text, [("led", 1), ("resistor", None)]) == []  # "resistors": no limit


def test_parts_embedded_in_a_model_file_are_one_piece():
    text = ("0 FILE main.ldr\n0 !LDRAW_ORG Model\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 custom.dat\n"
            "0 FILE custom.dat\n0 !LDRAW_ORG Unofficial_Part\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 stud.dat\n"
            "1 16 0 0 0 1 0 0 0 1 0 0 0 1 box5.dat\n")
    assert [p[0] for p in lego_model.flatten_mpd(text)] == ["custom.dat"]


def test_model_and_parts_list_name_pieces_the_same_way():
    import collections
    d = lambda **c: dict(lego_model.designs(collections.Counter(c)))
    assert d(**{"3711a": 2}) == d(**{"14696": 2}) == d(**{"3711": 2}) == {"3711": 2}  # one chain link, three names
    assert d(**{"2580c01": 1}) == {"2579": 1, "2580": 1}  # a library assembly split into its parts
    # a minifigure: the model builds torso + arms + hands, hips + legs; Rebrickable lists two assemblies
    assert d(**{"973p01": 1, "3818": 1, "3819": 1, "3820": 2, "3815": 1, "3816": 1, "3817": 1, "3626b": 1}) == \
        d(**{"973c27h01": 1, "970c00": 1, "3626c": 1}) == {"minifig-torso": 1, "minifig-legs": 1, "minifig-head": 1}
    assert d(**{"2867": 1}) == d(**{"74747": 1})  # "~Moved to" followed to the current part, then compared alike


def test_segmented_hoses_and_custom_parts_are_one_piece():
    seg = "1 0 0 {} 0 1 0 0 0 1 0 0 0 1 {}\n"
    text = ("0 FILE main.ldr\n0 !LDRAW_ORG Model\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            + seg.format(-24, "755.dat") + "".join(seg.format(-24 - i, "756.dat") for i in range(20))
            + seg.format(-50, "755.dat") + "1 4 40 0 0 1 0 0 0 1 0 0 0 1 3003.dat\n"
            "1 1 0 -60 0 1 0 0 0 1 0 0 0 1 sign.ldr\n"
            "0 FILE sign.ldr\n0 sign\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 4-4cyli.dat\n3 16 0 0 0 1 0 0 0 0 1\n")
    pieces = [p[0] for p in lego_model.flatten_mpd(text)]
    assert len(pieces) == 4 and pieces[0] == "3001.dat" and pieces[2] == "3003.dat"  # brick, hose, brick, custom sign
    assert pieces[1].startswith("main.ldr#lsynth") and pieces[3] == "sign.ldr"


def _lesson_store(tmp_path):
    """A two-step toy lesson in a temporary store: a plate on a brick (LEGO card ids from the shared catalogue)."""
    from graph import lesson_store as lg
    physical = {"lesson_id": "toy", "part_catalogue": lg.PART_CATALOGUES["lego"],
                "nodes": [{"id": "b1", "type": "lego-3004", "props": {"ldraw": "3004.dat"}},
                          {"id": "b2", "type": "lego-3023", "props": {"ldraw": "3023.dat"}},
                          {"id": "b3", "type": "lego-3023", "props": {"ldraw": "3023.dat"}}],
                "edges": [{"id": "e1", "type": "joined", "u": "b1", "u_port": "stud.1", "v": "b2", "v_port": "anti"},
                          {"id": "e2", "type": "joined", "u": "b2", "u_port": "stud.1", "v": "b3", "v_port": "anti"}]}
    acts = {"step-1": ["b1", "b2", "e1"], "step-2": ["b3", "e2"]}
    inst = {"lesson_id": "toy", "nodes": [{"id": s, "kind": "step", "n": n, "text": s} for n, s in enumerate(acts, 1)],
            "edges": lg._chain(list(acts)) + lg._acts(acts, physical)
                     + lg._depends(acts, {"b1": "step-1", "b2": "step-1", "b3": "step-2"}, physical)}
    record = {"lesson_id": "toy", "kind": "lesson", "lesson_type": "lego", "name": "Toy", "source": {}}
    lg.register({"lesson_id": "toy", "title": "Toy", "lesson_type": "lego"},
                {"lesson": record, "instruction": inst, "physical": physical, "document": None}, store=tmp_path)
    return lg, inst


def test_lesson_store_assembles_and_links(tmp_path):
    lg, _ = _lesson_store(tmp_path)
    row = lg.catalogue(tmp_path)["lessons"][0]
    assert set(row) == {"lesson_id", "name", "lesson_type", "lesson"}  # the index points to the record only
    assert lg._load("toy", tmp_path)[0]["representations"]["document"] is None  # a lesson lists only what it has
    view = lg.assemble("toy", store=tmp_path)
    assert view["checks"]["problems"] == []
    assert [p["count"] for p in view["parts_list"]] == [1, 2]  # one definition, two instances
    assert view["steps"][1]["depends_on"] == [{"step": "step-1", "via": ["e2"]}]


def test_lesson_store_catches_broken_links(tmp_path):
    import json
    lg, inst = _lesson_store(tmp_path)
    inst["edges"] = [e for e in inst["edges"] if (e["u"], e["v"]) != ("step-2", "e2")]  # a join no step makes
    inst["edges"].append({"type": "PLACES", "u": "step-2", "v": "b9"})                  # a piece that is not there
    (tmp_path / "toy" / "instruction.json").write_text(json.dumps(inst))
    problems = lg.assemble("toy", store=tmp_path)["checks"]["problems"]
    assert any("b9" in p for p in problems) and any("e2" in p and "never made" in p for p in problems)


def test_lesson_store_definitions():
    from graph import lesson_store as lg
    cards = {"lego-3003": {"ports": []}, "resistor": {"ports": []}}
    assert lg.definition(cards, "lego-3003pe2")[1].startswith("base design")
    assert lg.definition(cards, "resistor-220")[1].startswith("family")
    assert lg.definition(cards, "lego-9999")[0] is None
    assert lg.port_match({"ports": [{"id": "<column><bank>.<row>"}]}, "14t.c") == "pattern"


def test_stud_grid_names_card_cells():
    """Clutch ports name the same grid cells as the part cards; a handle sticking out is not a cell."""
    assert lego_model.grid("3021.dat")[:2] == ((-30.0, 3), (-20.0, 2))  # Plate 2 x 3
    assert lego_model.grid("3839b.dat")[1][1] == 1                      # Plate 1 x 2 with Handles: one row
    eye = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    assert lego_model.cell([20, 8, 10], "3021.dat", [0, 0, 0], eye) == (2, 3)


def test_part_metadata_checks_offline(tmp_path):
    """Claude's metadata is checked against the cards and the real shapes (a fake call: no model is run)."""
    from graph.parts import part_metadata as pm
    lg, _ = _lesson_store(tmp_path)

    def fake(system, content, schema):
        base = {"material": ["abs"], "specs": {"maker": "LEGO", "stud_count": 2}, "basis": {"maker": "card", "stud_count": "image"},
                "learner_tips": [], "card_issues": [], "confidence": 0.9,
                "polarized": False, "description": "x", "reverse_power": "n/a"}  # Claude answers in codes
        parts = [{**base, "part_type_id": "lego-3004", "size_studs": [1, 2], "dimensions_mm": [8, 16, 9.6],
                  "joins": [{"port_kind": "stud", "mates": ["anti-stud"], "method": "clutch", "holds_by": "friction",
                             "reversible": "hand"}]},
                 {**base, "part_type_id": "lego-3023", "size_studs": [2, 2], "dimensions_mm": [8, 16, 3.2],
                  "polarized": True,  # wrong twice: size and polarity
                  "joins": [{"port_kind": "anti-stud", "mates": ["stud"], "method": "clutch", "holds_by": "spring",
                             "reversible": "hand"}]}]
        return schema.model_validate({"parts": parts}).model_dump(), {"model": "fake", "seconds": 0, "cost_usd": 0}

    entries, stats, issues = pm.enrich("toy", store=tmp_path, call=fake, redo=True)
    rules = {(r, t) for r, t, _ in issues}
    assert ("M4", "lego-3023") in rules and ("M3", "lego-3023") in rules
    assert not {r for r, t in rules if t == "lego-3004"}
    assert entries["lego-3004"]["specs"]["stud_count"] == 2 and entries["lego-3004"]["schema_version"] == 2
    j = entries["lego-3023"]["joins"][0]  # GRAPH_SPEC rules a LEGO clutch: the rule wins, Claude's word is kept
    assert j["holds_by"] == "friction" and j["overridden"] == {"holds_by": "spring"} and stats["images"] == 2


def test_lesson_network_is_lossless(tmp_path):
    """An Arduino lesson's files (lesson, circuit graph, Wokwi diagram, sketch, stats) rebuild exactly from the
    network alone; a field the network drops is reported."""
    from graph.arduino import graphs as ag
    import json
    from graph import lesson_store as lg
    src = tmp_path / "src" / "toy"
    src.mkdir(parents=True)
    graph = {"nodes": [{"id": "uno", "type": "arduino-uno", "label": "Uno", "props": {}},
                       {"id": "led1", "type": "led", "label": "LED", "props": {"colour": "red"}}],
             "edges": [{"type": "joined", "u": "led1", "u_port": "A", "v": "uno", "v_port": "13", "method": "insert",
                        "freedom": "rigid", "reversible": "hand", "id": "e1"},
                       {"type": "electrical", "u": "led1", "u_port": "A", "v": "uno", "v_port": "13", "method": None,
                        "freedom": None, "reversible": None, "id": "e2"}]}
    lesson = {"id": "toy", "title": "Toy", "source": {"url": "u", "title": "t"}, "difficulty": "beginner",
              "board": "arduino-uno", "code": "code.ino", "wokwi_diagram": "diagram.json", "tools_used": [],
              "parts_used": ["arduino-uno", "led"], "generated": True, "made_from": "graph", "sketch_from": "x",
              "steps": [{"id": "gather", "phase": "gather", "clip": "Get parts.", "items": ["arduino-uno", "led"]},
                        {"id": "step-1", "phase": "build", "clip": "LED in 13.", "strict": False, "goal": "g",
                         "hints": ["h"], "extras": {"why": "w"}, "suggested": ["step-1"], "at": {"A": "uno:13"},
                         "expected_landing": ["led1:A"]},
                        {"id": "upload-code", "phase": "upload", "clip": "Upload.", "code": "code.ino"}],
              "final_check": {"expected_nets": [["led1:A", "uno:13"]]},
              "extras": {"how_it_works": "hw", "try_it": ["t"], "troubleshooting": ["x"],
                         "code_walkthrough": [{"lines": "void setup() {}", "says": "s"}]}}
    diagram = {"version": 1, "author": "a", "editor": "wokwi", "dependencies": {},
               "parts": [{"type": "wokwi-arduino-uno", "id": "uno", "top": 0, "left": 0, "attrs": {}},
                         {"type": "wokwi-led", "id": "led1", "top": 0, "left": 0, "attrs": {"color": "red"}}],
               "connections": [["led1:A", "uno:13", "green", []]]}
    for name, v in (("graph.json", graph), ("lesson.json", lesson), ("diagram.json", diagram),
                    ("stats.json", {"seconds": 1.0, "cost_usd": 0.01, "phases": [{"phase": "plan"}]})):
        (src / name).write_text(json.dumps(v))
    (src / "code.ino").write_text("void setup() {}\nvoid loop() {}\n")
    store = tmp_path / "store"
    entry, graphs = ag.arduino("toy", lessons_dir=src.parent)
    lg.register(entry, graphs, store=store)
    assert all(not d for d in lg.audit("toy", store=store).values())
    view = lg.assemble("toy", store=store)
    assert view["checks"]["problems"] == [] and view["steps"][0]["gathers"] == ["uno", "led1"]
    lesson["steps"][0]["items"] = ["arduino-uno"]  # the gather step forgets the LED: caught
    (src / "lesson.json").write_text(json.dumps(lesson))
    lg.register(*ag.arduino("toy", lessons_dir=src.parent), store=store)
    assert any("led1 (led) is in the build but not on the parts list" in p
               for p in lg.assemble("toy", store=store)["checks"]["problems"])  # said once, by the parts list
    lesson["steps"][0]["items"] = ["arduino-uno", "led"]
    lesson["steps"][1]["new_field"] = 1  # a field the network does not know about is caught
    (src / "lesson.json").write_text(json.dumps(lesson))
    assert any(p.endswith("new_field") for p, _, _ in lg.audit("toy", store=store)["lesson.json"])


def test_parts_db_one_catalogue(tmp_path, monkeypatch):
    """LEGO and Arduino cards in one catalogue, each with metadata saying which it is; drafted metadata survives a
    rebuild, and a part id in both stores is refused."""
    import json
    import pytest
    (tmp_path / "l.json").write_text(json.dumps({"lego-3001": {"part_type_id": "lego-3001", "domain": "lego",
                                                               "ports": [], "source": {"made_by": "code"}}}))
    (tmp_path / "e.json").write_text(json.dumps({"led": {"part_type_id": "led", "domain": "electronics", "ports": []}}))
    monkeypatch.setattr(part_catalogue, "ROOT", tmp_path)
    monkeypatch.setattr(part_catalogue, "STORES", {"lego": "l.json", "arduino": "e.json"})
    out = tmp_path / "parts.json"
    assert part_catalogue.build(out) == {"lego": 1, "arduino": 1}
    parts = part_catalogue.load(out)
    assert parts["led"]["metadata"]["domain"] == "arduino" and "domain" not in parts["led"]
    assert {k: v for k, v in parts["lego-3001"]["metadata"].items() if k != "substitutes"} == \
        {"domain": "lego", "source_catalogue": "l.json", "card_made_by": "code"}
    assert parts["lego-3001"]["metadata"]["substitutes"]["free"] == ["colour"]  # a colour swap is still right
    parts["led"]["metadata"]["description"] = "drafted"
    part_catalogue.save(parts, out)
    part_catalogue.build(out)
    assert part_catalogue.load(out)["led"]["metadata"]["description"] == "drafted"
    (tmp_path / "e.json").write_text(json.dumps({"lego-3001": {"part_type_id": "lego-3001", "ports": []}}))
    with pytest.raises(ValueError):
        part_catalogue.build(out)


def test_pins_and_code_links():
    """A board's pins say what they can do; the sketch's pins are linked to the circuit; a swap is allowed only to a
    pin that can do what the code needs, and the code is rewritten at exactly the linked places."""
    from graph.arduino import pins
    uno = {"part_type_id": "arduino-uno", "ports": [{"id": str(i), "kind": "header-socket"} for i in range(14)] +
           [{"id": f"A{i}", "kind": "header-socket"} for i in range(6)] + [{"id": "GND.1"}, {"id": "GND.2"}]}
    cq = {"pin_domains": {"digital": [str(i) for i in range(2, 14)], "analog": [f"A{i}" for i in range(6)]},
          "protocol_pins": {"A4": {"protocol": "I2C", "role": "SDA"}}, "led_builtin": "13",
          "pin_aliases": {"mode": "prefix", "prefixes": ["GND"]}}
    pins.annotate(uno, cq)
    port = {p["id"]: p for p in uno["ports"]}
    assert "pwm" in port["9"]["can"] and "pwm" not in port["8"]["can"] and port["13"]["builtin"] == "LED_BUILTIN"
    assert port["0"]["reserved"] and port["GND.2"]["same_as"] == "GND"
    ok, why = pins.stand_ins(uno, "9", ["digital", "pwm"], used={"10"})
    assert ok == ["3", "5", "6", "11"] and why["8"] == "cannot do pwm" and why["10"].startswith("already used")
    fade = "/* fade on pin 9 */\nint led = 9;\nvoid setup() {\n  // declare pin 9 to be an output:\n  pinMode(led, OUTPUT);\n}\n" \
           "void loop() { analogWrite(led, 5); delay(1000); }\n"
    links = pins.links(fade, "uno", uno)
    code = [l for l in links if l["kind"] == "code"]
    assert len(code) == 1 and code[0]["port"] == "uno:9" and code[0]["needs"] == ["digital", "pwm"]
    assert [l["line"] for l in links if l["kind"] == "comment"] == [4]  # the header comment is left alone
    out = pins.rewrite(fade, links, {"uno:9": "uno:5"})
    assert "int led = 5;" in out and "declare pin 5" in out and "fade on pin 9" in out and "delay(1000)" in out
    blink = "void setup() { pinMode(LED_BUILTIN, OUTPUT); }\nvoid loop() { digitalWrite(LED_BUILTIN, HIGH); }\n"
    assert pins.rewrite(blink, pins.links(blink, "uno", uno), {"uno:13": "uno:12"}).count("(12,") == 2
    assert [l["kind"] for l in pins.links("void loop() { digitalWrite(pins[i], HIGH); }", "uno", uno)] == ["unresolved"]


def test_parts_list_points_to_instances():
    """Each parts-list row points to the instances it accounts for, by base design and colour; a gap is named."""
    from graph.arduino import graphs as ag
    from graph import lesson_store as lg
    cards = {"lego-3003": {"part_type_id": "lego-3003"}, "lego-3004": {"part_type_id": "lego-3004"}}
    phys = {"nodes": [{"id": "b1", "type": "lego-3004", "props": {"colour": "Black"}},
                      {"id": "b2", "type": "lego-3004", "props": {"colour": "Black"}},
                      {"id": "b3", "type": "lego-3003pe2", "props": {"colour": "Red"}},
                      {"id": "b4", "type": "lego-3004", "props": {"colour": "White"}}]}
    rows = [{"part": "lego-3004", "count": 2, "colour": "Black"}, {"part": "lego-3003pr0053", "count": 1, "colour": "Red"}]
    problems = ag.match_parts(rows, phys, cards, lg.definition)
    assert rows[0]["instances"] == ["b1", "b2"] and rows[1]["instances"] == ["b3"]  # two prints, one base design
    assert problems == ["b4 (lego-3004) is in the build but not on the parts list"]


def test_steps_name_both_neighbours(tmp_path):
    """The step order is stored once, as NEXT_STEP; each step's previous step is its reverse, worked out on reading."""
    lg, inst = _lesson_store(tmp_path)
    assert not any(e["type"] == "PREVIOUS_STEP" for e in inst["edges"])
    steps = lg.assemble("toy", store=tmp_path)["steps"]
    assert (steps[0]["previous"], steps[0]["next"], steps[1]["previous"], steps[1]["next"]) == (None, "step-2", "step-1", None)


def test_progress_any_order(tmp_path):
    """An Arduino step done early is accepted (its check waits for the part it names); the circuit is compared by
    net: another hole of the same strip, another GND pin, a resistor either way round all count; a join the
    lesson does not plan is reported."""
    from graph.arduino import graphs as ag
    import json
    from graph import lesson_store as lg
    from graph.arduino import graphs
    src = tmp_path / "src" / "toy"
    src.mkdir(parents=True)
    def j(i, u, up, v, vp):
        return [{"type": t, "u": u, "u_port": up, "v": v, "v_port": vp, "id": f"e{i}{t[0]}", "method": "insert" if t == "joined" else None,
                 "reversible": "hand" if t == "joined" else None} for t in ("joined", "electrical")]
    graph = {"nodes": [{"id": "uno", "type": "arduino-uno", "label": "Uno", "props": {}},
                       {"id": "bb1", "type": "breadboard", "label": "bb", "props": {}},
                       {"id": "r1", "type": "resistor", "label": "R", "props": {"value": "220"}},
                       {"id": "wire1", "type": "jumper-wire", "label": "w", "props": {}}],
             "edges": j(1, "r1", "1", "bb1", "10t.a") + j(2, "r1", "2", "bb1", "14t.a") +
                      j(3, "wire1", "a", "uno", "GND.1") + j(4, "wire1", "b", "bb1", "14t.b")}
    lesson = {"id": "toy", "title": "Toy", "source": {"url": "u"}, "steps": [
        {"id": "gather", "phase": "gather", "clip": "Get.", "items": ["arduino-uno", "breadboard", "resistor", "jumper-wire"]},
        {"id": "step-1", "phase": "build", "clip": "R.", "at": {"1": "bb1:10t.a", "2": "bb1:14t.a"}},
        {"id": "step-2", "phase": "build", "clip": "W.", "at": {"a": "uno:GND.1", "b": "bb1:14t.b"},
         "expected_nets": [["r1:2", "uno:GND"]]}]}
    (src / "graph.json").write_text(json.dumps(graph))
    (src / "lesson.json").write_text(json.dumps(lesson))
    store = tmp_path / "store"
    lg.register(*ag.arduino("toy", lessons_dir=src.parent), store=store)
    es = json.loads((store / "toy" / "instruction.json").read_text())["edges"]

    # its check names r1, but the position dependency below already links the two steps: no second edge
    assert not any(e["type"] == "CHECK_NEEDS" and e["u"] == "step-2" and e["v"] == "step-1" for e in es)
    r = graphs.progress("toy", [("wire1:a", "uno:GND.2"), ("wire1:b", "bb1:14t.e")], store=store)
    assert r["steps"]["step-2"]["status"] == "too early" and r["steps"]["step-2"]["blocked_by"] == ["step-1"]
    assert r["next"] == "step-1"  # DEPENDS_ON is strict: the wire's column comes from the resistor
    r = graphs.progress("toy", [("r1:2", "bb1:10t.c"), ("r1:1", "bb1:14t.c")], store=store)  # the resistor turned round
    assert r["steps"]["step-1"]["status"] == "done" and r["unexpected"] == []
    # the wire has no place of its own: its end goes where the resistor's leg went
    assert {"type": "DEPENDS_ON", "u": "step-2", "v": "step-1", "via": ["e2j", "e4j"]} in es  # its join and r1's, strip 14
    # position, not fixed holes: the resistor in columns 20/24 is right, and then the wire must follow it to 24
    moved = [("r1:1", "bb1:20t.a"), ("r1:2", "bb1:24t.a")]
    r = graphs.progress("toy", moved, store=store)
    assert r["steps"]["step-1"]["status"] == "done" and r["layout"] == {"10t": "20t", "14t": "24t"}
    assert r["steps"]["step-2"]["targets"]["wire1:b"].startswith("24t")
    r = graphs.progress("toy", moved + [("wire1:a", "uno:GND.1"), ("wire1:b", "bb1:24t.c")], store=store)
    assert r["done"] == ["step-1", "step-2"] and r["errors"] == []
    r = graphs.progress("toy", moved + [("wire1:a", "uno:GND.1"), ("wire1:b", "bb1:14t.c")], store=store)  # the old column
    assert r["steps"]["step-2"]["status"] == "wrong" and r["to_fix"] == ["step-2"] and "column 24t" in r["errors"][0]
    r = graphs.progress("toy", [("r1:1", "bb1:20t.a"), ("r1:2", "bb1:20t.b")], store=store)  # both legs in one column
    assert r["steps"]["step-1"]["status"] == "wrong" and "different columns" in r["errors"][0]
    r = graphs.progress("toy", [("led9:A", "bb1:3t.a")], store=store)
    assert r["unexpected"] == [("led9:A", "bb1:3t.a")]


def test_part_metadata_only_new_parts(tmp_path):
    """A lesson's parts that already have metadata are not sent again: one new part, one part asked for."""
    from graph.parts import part_metadata as pm
    lg, _ = _lesson_store(tmp_path)  # the toy uses lego-3004 and lego-3023
    parts = tmp_path / "parts.json"
    part_catalogue.save({"lego-3004": {"part_type_id": "lego-3004", "ports": [], "metadata": {"domain": "lego", "description": "had"}},
                   "lego-3023": {"part_type_id": "lego-3023", "ports": [], "metadata": {"domain": "lego"}}}, parts)
    asked = []

    def fake(system, content, schema):
        asked.extend(c["text"].split("\n")[0] for c in content if c["type"] == "text" and c["text"].startswith("PART"))
        return {"parts": []}, {"model": "fake", "seconds": 0, "cost_usd": 0}

    _, stats, _ = pm.enrich("toy", store=tmp_path, call=fake, path=parts)
    assert asked == ["PART lego-3023"] and stats["skipped"] == 1
    asked.clear()
    pm.enrich("toy", store=tmp_path, call=fake, path=parts, redo=True)
    assert asked == ["PART lego-3004", "PART lego-3023"]


def test_naming_rules():
    """A new part type gets one id by fixed rules; a name that hides an existing part is sent back with the id to
    use; a genuinely new part passes."""
    import pathlib
    from graph.parts import naming
    from graph.parts.cards import CardStore
    store = CardStore(pathlib.Path(__file__).resolve().parents[2] / "graph" / "parts" / "arduino" / "cards_electronics.json")
    use = lambda d: next((m.split("use '")[1].split("'")[0] for r, m in naming.check([d], store) if r in ("N4", "N6")), None)  # noqa: E731
    assert use({"type": "red-led", "name": "Red LED", "polarized": True}) == "led"
    assert use({"type": "resistor-330", "name": "330 ohm resistor"}) == "resistor"
    assert use({"type": "mkr1000-board", "name": "Arduino MKR1000"}) == "arduino-mkr1000"
    assert {r for r, _ in naming.check([{"type": "temp-dht22", "name": "DHT22"}], store)} == {"N3", "N4"}
    assert use({"type": "capacitor-ceramic", "name": "a capacitor"}) == "capacitor-100nf"  # generic: the most used
    assert [r for r, _ in naming.check([{"type": "LED_Red"}], store)] == ["N1", "N6"]  # bad format, and it is an LED
    for new in ("arduino-nano-matter", "led-strip", "dht11"):  # new parts, or a catalogue type: no complaint
        assert naming.check([{"type": new, "name": new.replace("-", " ")}], store) == [], new
    src = (pathlib.Path(__file__).resolve().parents[2] / "graph" / "extract.py").read_text()  # the builder's prompt carries the rules
    assert '_naming.RULES' in src and "temp-dht11" not in src


def test_every_fact_once():
    """The pilot lessons state no fact twice: no stored reverse, no electrical twin made by a step, no copied port or
    pin, no check that a dependency already implies."""
    import json, pathlib
    from graph import lesson_store as lg
    for lid in ("blink", "fade", "2134-1"):
        d = pathlib.Path("data/lessons/store") / lid
        if not (d / "instruction.json").exists():
            continue
        g = {k: json.loads((d / f"{k}.json").read_text()) for k in ("lesson", "instruction", "physical")}
        assert lg.single_facts(g["instruction"], g["physical"], g["lesson"]) == [], lid


def test_tutor_tools_read_the_store():
    """The tutoring agent's tools answer from the stored lesson data (no model call): steps with their neighbours
    and joins, a learner's wiring checked, pin stand-ins, a part's facts."""
    import pathlib
    from graph import tutor_mcp as t
    if not pathlib.Path("data/lessons/store/blink/lesson.json").exists():
        return
    s = t.step("blink", "step-3")
    assert (s["previous"], s["next"]) == ("step-2", "step-4") and "wire1:b -> bb1:10t.a" in s["makes"]
    assert {"step": "step-1", "via": ["wire1:b -> bb1:10t.a", "r1:1 -> bb1:10t.b"]} in s["depends_on"]
    r = t.progress("blink", ["r1:1 -> bb1:12t.a", "r1:2 -> bb1:16t.a", "wire1:a -> uno:13", "wire1:b -> bb1:10t.e"])
    assert r["errors"] == ["wire1:b (step-3) must go in column 12t, with r1:1 (step-1)"]
    assert t.substitutions("fade")["pins"]["uno:9"]["stand_ins"] == ["3", "5", "6", "10", "11"]
    assert t.part("servo")["reverse_power"] == "damage" and "error" in t.part("no-such-part")


def test_lego_inventory_matching():
    """A Rebrickable row and an LDraw model piece are the same part despite colour spelling, prints, mould letters or
    different numbers with the same name; a really different piece, or a colour swap, is reported."""
    from graph.parts.lego import lego_ids as li
    assert li.same_part("lego-3298pr0017", None, "lego-3298p19", None)          # two print codes, one design
    assert li.same_part("lego-3747b", None, "lego-3747a", None)                 # mould variants
    assert li.same_part("lego-3070b", "Tile 1 x 1 with Groove", "lego-30039", "Tile  1 x  1 with Groove")  # names
    assert not li.same_part("lego-4286", "Slope 33 3 x 1", "lego-3298", "Slope Brick 33  3 x  2")   # another piece
    rows = [{"part": "lego-3039", "count": 1, "colour": "Trans-Neon Green"}, {"part": "lego-4740", "count": 1, "colour": "Trans-Clear"}]
    pieces = [{"id": "b1", "type": "lego-3039", "props": {"colour": "Trans Neon Green"}},
              {"id": "b2", "type": "lego-4740", "props": {"colour": "Sand Blue"}}]
    problems, notes = li.match(rows, pieces)
    assert problems == [] and rows[0]["instances"] == ["b1"] and notes == ["b2: lego-4740 is Trans-Clear in the inventory, Sand Blue in the model"]


def test_part_review_code_checks():
    """The reviewer's proposals are checked by code: a type must have the ports the lesson uses, and the model numbers
    in the lesson's own name; a resistor's value is not a model number."""
    import pathlib
    from graph.arduino import part_review as pr
    from graph.parts.cards import CardStore
    store = CardStore(pathlib.Path(__file__).resolve().parents[2] / "graph" / "parts" / "arduino" / "cards_electronics.json")
    board = {"lesson_name": "Arduino UNO WiFi Rev2", "ports_used": ["2", "GND.1"], "props": {}}
    assert pr.check_type("arduino-uno-wifi-rev2", board, store) == []
    assert pr.check_type("arduino-uno", board, store)[0].startswith("R3")              # the wrong board
    led = {"lesson_name": "LED", "ports_used": ["A", "C"], "props": {}}
    assert pr.check_type("rgb-led", led, store)[0].startswith("R2")                     # no legs A and C
    assert pr.check_type("resistor", {"lesson_name": "220 ohm resistor", "ports_used": ["1", "2"],
                                      "props": {"value": "220"}}, store) == []


def test_parts_first_review_is_checked_by_code():
    """Parts are settled before the circuit: the reviewer's answers count only when code confirms them, a value
    never makes a type, and a part the catalogue has is never added again (nothing is written with add=False)."""
    from graph.arduino import part_review as pr
    page = ("## Hardware Required\n- Arduino UNO R4 WiFi\n- 1 red LED\n- 220 ohm resistor\n- a capacitor\n"
            "- 1 x HC-SR04 ultrasonic sensor\n- USB cable\n")

    def fake(ask, system, schema, model, effort):
        v = [{"item": int(i), "verdict": "confirm", "type_id": m, "name": t, "evidence": "", "confidence": 0.9}
             for i, t, m in (map(str.strip, line.split("|")) for line in ask.splitlines()[2:])]
        v[0].update(verdict="change", type_id="arduino-uno")         # R3: the list says R4 WiFi
        v[2].update(verdict="new", type_id="resistor-220")           # the value is the copy's, not the type's
        v[4].update(verdict="new", type_id="ultrasonic-sensor-x")    # the catalogue has it
        return {"structured_output": {"verdicts": v}, "total_cost_usd": 0.0}, []
    r = pr.parts_first(page, "test", call=fake, add=False)
    got = {x["text"]: x["type"] for x in r["rows"]}
    assert "USB cable" not in got
    assert got == {"Arduino UNO R4 WiFi": "arduino-uno-r4-wifi", "1 red LED": "led", "220 ohm resistor": "resistor",
                   "a capacitor": "capacitor-100nf", "1 x HC-SR04 ultrasonic sensor": "hc-sr04"}
    assert r["new_types"] == [] and "-> hc-sr04" in r["note"]


def test_pdf_lesson_cuts_and_words():
    """A booklet's last step on a page is cut to the step (not the panel or advert beside and below it), and the
    words a child reads never name a part by its id."""
    import pathlib
    from graph.lego_booklet import pdf_lesson as pl
    pdf = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "lego_pdf" / "30103-1.pdf"
    if pdf.exists():
        import pymupdf
        from graph.lego_booklet import step_diff
        doc = pymupdf.open(pdf)
        x0, y0, x1, y1 = step_diff.tighten(doc[1], (72, 255, 641, 848))  # Car step 8: the page's bottom is an advert
        assert x1 < 330 and y1 < 440 and (x0, y0) == (72, 255)
        assert step_diff.tighten(doc[0], (357, 254, 641, 469))[2] == 641  # red arrow lines are not dividers
    assert pl.check_words({"instruction": "Press the pink 1 x 2 tile on.", "what_changed": "A tile was added."}) == []
    bad = pl.check_words({"instruction": "Take lego-3069b and the 92818c01pr0001 legs.", "description": "ok"})
    assert len(bad) == 1 and "lego-3069b" in bad[0] and "92818c01pr0001" in bad[0]


def test_pdf_lesson_every_part_placed_before_it_is_final(tmp_path):
    """A booklet-only lesson is ready only when its steps place every piece of the parts list; a piece still left is
    given a step at the end only where code finds support for it (a real step, within what is left, the step's own
    words name its colour), and is flagged on that step for review."""
    from graph.lego_booklet import pdf_lesson as pl
    from graph import lesson_store as lg
    inventory = [{"part": "lego-3001", "colour": "Red", "name": "Brick 2 x 4", "count": 2},
                 {"part": "lego-3069b", "colour": "Bright Pink", "name": "Tile 1 x 2", "count": 3}]
    steps = [{"step": n, "page": 1, "crop": [0, 0, 10, 10], "boxes": 1, "png": f"s{n}.png"} for n in (1, 2)]
    reads = [{"step": 1, "adds": [{"part": "lego-3001", "colour": "Red", "count": 2, "where": "on the table"}],
              "instruction": "Put two red bricks side by side.", "description": "Two red bricks.", "what_changed": "",
              "confidence": 0.9, "problems": []},
             {"step": 2, "adds": [{"part": "lego-3069b", "colour": "Bright Pink", "count": 1, "where": "on top"}],
              "instruction": "Lay a pink tile on top.", "description": "Two red bricks with pink tiles on top.",
              "what_changed": "Pink tiles were added.", "confidence": 0.6, "problems": []}]

    def register(rs):
        record, inst = pl.build("toy", rs, steps, inventory, [], [{"seconds": 1, "cost_usd": 0}])
        lg.register({"lesson_id": "toy-pdf", "title": "toy", "lesson_type": "lego"},
                    {"lesson": record, "instruction": inst, "physical": None, "document": None}, tmp_path)
    import unittest.mock as um
    with um.patch.object(lg, "_rebrickable", lambda s: ("Toy", [])):
        register(reads)
        c = lg.assemble("toy-pdf", tmp_path)["checks"]
        assert not c["ready"] and any("#2 lego-3069b" in p and "the steps place 1" in p for p in c["problems"])

        def fake(system, content, schema):
            return {"allocations": [
                {"part": "lego-3069b", "colour": "Bright Pink", "count": 2, "step": 1, "where": "", "evidence": ""},  # no pink in step 1's words
                {"part": "lego-3069b", "colour": "Bright Pink", "count": 5, "step": 2, "where": "", "evidence": ""},  # more than left
                {"part": "lego-3069b", "colour": "Bright Pink", "count": 2, "step": 2, "where": "on top", "evidence": "two flat pink tiles", "confidence": 0.8},
            ]}, {"seconds": 0, "cost_usd": 0}
        reads, still, ph = pl.allocate("toy", steps, reads, inventory, call=fake, images=False)
        assert still == [] and [x["step"] for x in ph["placed"]] == [2] and len(ph["problems"]) == 2
        register(reads)
        c = lg.assemble("toy-pdf", tmp_path)["checks"]
        assert c["ready"] and len(c["review"]) == 1 and "allocated here at the end" in c["review"][0]


def test_pdf_lesson_symmetry():
    """S11 on a booklet: the hidden twins of pieces put on one side go to the same step; a Left part and its Right
    twin far apart are flagged."""
    from graph.lego_booklet import pdf_lesson as pl
    inventory = [{"part": "lego-50951", "colour": "Black", "name": "Tyre 14 x 6", "count": 4},
                 {"part": "lego-3001", "colour": "Red", "name": "Brick 2 x 4", "count": 2},
                 {"part": "lego-43722", "colour": "White", "name": "Wedge Plate 2 x 3 Right", "count": 1},
                 {"part": "lego-43723", "colour": "White", "name": "Wedge Plate 2 x 3 Left", "count": 1}]
    steps = [{"step": n} for n in (1, 2, 3, 4)]
    reads = [{"step": 1, "adds": [{"part": "lego-3001", "colour": "Red", "count": 1, "where": "on the left"},
                                  {"part": "lego-43723", "colour": "White", "count": 1, "where": "at the back"}]},
             {"step": 2, "adds": [{"part": "lego-3001", "colour": "Red", "count": 1, "where": "on the right"}]},
             {"step": 3, "adds": [{"part": "lego-50951", "colour": "Black", "count": 2, "where": "on the near side, front and back"}]},
             {"step": 4, "adds": [{"part": "lego-43722", "colour": "White", "count": 1, "where": "at the back"}]}]
    reads, still, ph = pl.symmetry(steps, reads, inventory)
    assert still == [] and reads[2]["adds"][0]["count"] == 4 and ph["placed"][0]["by"] == "symmetry"
    assert "hidden twins" in reads[2]["problems"][0]
    assert len(ph["problems"]) == 1 and "left/right twins" in reads[3]["problems"][0]  # Left in 1, Right in 4


def test_booklet_size_finds_a_missed_piece():
    """Code's own evidence for counts: much more new area of a colour than the step's read pieces cover is asked
    about, and copies still left go to the one step whose unexplained area of their colour they fit."""
    import pytest
    from graph.lego_booklet import booklet_size as bs
    panel, tile = bs.silhouette("93095"), bs.silhouette("3069b")
    if not (panel and tile):
        pytest.skip("no LDraw library")
    inventory = [{"part": "lego-93095", "colour": "Bright Pink", "name": "Panel", "count": 1},
                 {"part": "lego-3069b", "colour": "Bright Pink", "name": "Tile 1 x 2", "count": 3}]
    seat = (panel + 2 * tile) * bs.CAL * 0.9  # what step 2 shows: the panel and two tiles, a little hidden
    areas = {2: {"Bright Pink": seat}, 3: {}, 7: {"Bright Pink": tile * bs.CAL}}
    reads = [{"step": 2, "adds": [{"part": "lego-93095", "colour": "Bright Pink", "count": 1, "where": "left"}]},
             {"step": 3, "adds": []},
             {"step": 7, "adds": [{"part": "lego-3069b", "colour": "Bright Pink", "count": 1, "where": "front"}]}]
    assert bs.check(reads[0], areas[2]) and "Bright Pink" in bs.check(reads[0], areas[2])[0]
    assert bs.check(reads[2], areas[7]) == []
    reads, still, ph = bs.fill(reads, inventory, areas)
    assert still == [] and ph["placed"][0]["step"] == 2 and ph["placed"][0]["count"] == 2
    assert "by size" in reads[0]["problems"][0]


def test_booklet_arrows_and_balance():
    """Arrows are read from the PDF (head, and where the visible line starts: the piece it moves), and are never a
    change. A piece read a step early is found by the two steps' whole new area; code moves it alone when one kind
    fits, and asks only among its own candidates when several do."""
    import pathlib, pytest
    from graph.lego_booklet import booklet_size as bs, step_diff
    pdf = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "lego_pdf" / "30103-1.pdf"
    if pdf.exists():
        import pymupdf
        doc = pymupdf.open(pdf)
        a = step_diff.arrows(doc[1], (73, 56, 319, 260), 300)  # Car step 7: the pink tile pushed onto two pegs
        assert len(a) == 2 and all(x["tail"][0] < x["tip"][0] - 100 for x in a)
        assert step_diff.arrow_mask((851, 1025), a).sum() > 0
    if not (bs.silhouette("44674") and bs.silhouette("60212") and bs.silhouette("3622")):
        pytest.skip("no LDraw library")
    w = lambda p: {"part": p, "colour": "White", "count": 1, "where": ""}
    reads = [{"step": 4, "adds": [{**w("lego-3622"), "count": 2}, w("lego-60212"), w("lego-44674")]},
             {"step": 5, "adds": [{"part": "lego-3023", "colour": "Medium Lavender", "count": 2, "where": ""}]}]
    e4 = 2 * bs.silhouette("3622") + bs.silhouette("60212")
    e5 = 2 * bs.silhouette("3023") + bs.silhouette("44674")
    areas = {4: {"*": 0.7 * e4}, 5: {"*": 0.7 * e5}}  # what the pictures show: the headlight mudguard is in step 5
    asked = []
    pick = lambda src, dst, c: asked.append(sorted(x["part"] for x in c)) or next(x for x in c if x["part"] == "lego-44674")
    reads, ph = bs.balance(reads, areas, pick)
    assert [m["to"] for m in ph["placed"]] == [5] and any(a["part"] == "lego-44674" for a in reads[1]["adds"])
    assert asked and "lego-3023" not in asked[0] and reads[0]["reword"] and reads[1]["reword"]  # only step 4's pieces


def test_booklet_layout_builds_and_sub_builds():
    """The booklet's layout from the PDF: main steps by the largest digits, builds where the numbers start again,
    a boxed sub-build attached in the step it is part of (with its 2x), a figure's panel a build of its own."""
    import pathlib, pytest
    pdfs = pathlib.Path(__file__).resolve().parents[3] / "data" / "sources" / "lego_pdf"
    if not (pdfs / "30055-1.pdf").exists():
        pytest.skip("no booklets")
    import pymupdf
    from graph.lego_booklet import pdf_lesson as pl
    droid = pl._layout(pymupdf.open(pdfs / "30055-1.pdf"))
    mains = [s["label"] for s in droid if s["kind"] == "main"]
    assert mains == ["1", "2", "3", "4", "5", "6", "7"]
    wing = [s for s in droid if s.get("box") == "sub-3"]
    assert len(wing) == 5 and all(s["times"] == 2 for s in wing)
    assert next(s for s in droid if s["label"] == "7")["attaches"] == ["sub-3"]
    mail = pl._layout(pymupdf.open(pdfs / "30105-1.pdf"))
    builds = {}
    for s in mail:
        if s["kind"] == "main":
            builds.setdefault(s["build"], []).append(s["label"])
    assert sorted(builds.values(), key=len) == [["1", "2"], ["1", "2", "3"], ["1", "2", "3", "4", "5", "6", "7", "8"]]
    stand = {s["label"]: s for s in mail if s["kind"] == "main" and len(builds[s["build"]]) == 8}
    assert [len(stand[n]["attaches"]) for n in "5678"] == [1, 1, 1, 1]


def test_order_of_a_lesson_with_builds():
    """SHOWS / STARTS / NEXT_STEP: each build its own chain, a step's sub-build just before the step."""
    from graph import lesson_store as lg
    E = [{"type": "SHOWS", "u": "overview", "v": "build:a", "order": 1}, {"type": "SHOWS", "u": "overview", "v": "build:b", "order": 2},
         {"type": "STARTS", "u": "build:a", "v": "a-1"}, {"type": "NEXT_STEP", "u": "a-1", "v": "a-2"},
         {"type": "STARTS", "u": "a-2", "v": "a-2.1"}, {"type": "NEXT_STEP", "u": "a-2.1", "v": "a-2.2"},
         {"type": "STARTS", "u": "build:b", "v": "b-1"}]
    nodes = [{"id": i, "kind": "step"} for i in ("a-1", "a-2", "a-2.1", "a-2.2", "b-1")] + [{"id": "overview", "kind": "overview"}]
    assert lg._order({"nodes": nodes, "edges": E}) == ["overview", "a-1", "a-2.1", "a-2.2", "a-2", "b-1"]


def test_catalogue_fits_and_interchangeable_ports():
    """What a port can go into, and which ports can stand in for each other, are worked out by code for every
    electronics card: a resistor's lead fits a breadboard hole, a header socket, a female jumper end, a screw terminal
    or a solder pad, and its two legs swap; an LED's legs do not; the Uno's GND pins are one group."""
    p = part_catalogue.load()
    lead = {r["with"] for r in p["resistor"]["metadata"]["fits"]["lead"]}
    assert {"breadboard-hole", "header-socket", "wire-end", "screw", "pad"} <= lead
    assert p["resistor"]["metadata"]["interchangeable"][0] == {"kind": "not-polarized", "ports": ["1", "2"],
                                                                "why": "not polarized: either leg in either place"}
    assert not any(g.get("ports") == ["A", "C"] for g in p["led"]["metadata"]["interchangeable"])
    assert any(sorted(g.get("ports", [])) == ["GND.1", "GND.2", "GND.3"] for g in p["arduino-uno"]["metadata"]["interchangeable"])
    groups = p["breadboard"]["metadata"]["interchangeable"]  # written out: 126 strips of 5, 4 rails of 63
    assert sum(g["kind"] == "strip" for g in groups) == 126 and sum(g["kind"] == "rail" for g in groups) == 4
    assert part_catalogue.swaps("breadboard", "12t.c", p) == ["12t.a", "12t.b", "12t.d", "12t.e"]
    assert "12b.f" not in part_catalogue.swaps("breadboard", "12t.c", p)  # across the gap is another strip
    assert part_catalogue.swaps("arduino-uno", "GND.2", p) == ["GND.1", "GND.3"]
    ways = [w["way"] for w in p["resistor"]["metadata"]["connect_by"]]
    assert ways[0] == "breadboard" and "solder" in ways
    assert next(w for w in p["resistor"]["metadata"]["connect_by"] if w["way"] == "solder")["tool"] == "soldering iron"


def test_metadata_is_codes_not_free_text():
    """Everything but the description, the tips and the reasons is codes and numbers, so code can check and answer
    before Claude is asked; a second normalize changes nothing."""
    from graph.parts import part_metadata as pm
    draft = {"description": "A flat 1 x 2 tile.", "learner_tips": ["Smooth top."], "material": "Fibreglass PCB with metal pins",
             "size_studs": "2 x 1", "reverse_power": "no harm, does not work", "status": "drafted (claude)",
             "joins": [{"port_kind": "lead", "mates_with": "breadboard hole or female jumper wire", "method": "insert",
                        "holds_by": "spring", "reversible": "hand"}],
             "basis": {"maker": "general knowledge"}, "specs": {"interface": ["I2C", "none"]},
             "substitutes": {"value": "by role", "why": "per lesson"}, "checks_failed": ["M4: size off"]}
    m = pm.normalize(draft)
    assert m["description"] == draft["description"] and m["learner_tips"] == draft["learner_tips"]
    assert m["material"] == ["pcb", "metal"] and m["material_text"] == draft["material"]  # not glass: fibreglass
    assert m["size_studs"] == [1, 2] and m["reverse_power"] == "no-harm" and m["status"] == "drafted"
    assert m["joins"][0]["mates"] == ["breadboard-hole", "wire-end"] and "mates_with" not in m["joins"][0]
    assert m["basis"] == {"maker": "general-knowledge"} and m["specs"]["interface"] == ["i2c"]
    assert m["substitutes"]["value"] == "by-role" and m["checks_failed"] == [{"rule": "M4", "message": "size off"}]
    assert pm.normalize(m) == m


def test_new_part_drafted_in_words_is_stored_and_rechecked_as_codes():
    """Making a lesson with a new part: Claude drafts its metadata in words, code checks the draft, it is stored as
    codes, and a recheck on the stored codes (and the naming check against a draft) finds nothing new."""
    import copy
    from graph.parts import part_metadata as pm, naming
    cards = part_catalogue.load()
    draft = {"part_type_id": "dht11", "description": "A temperature and humidity sensor.", "material": "Plastic case with metal pins",
             "size_studs": None, "dimensions_mm": [15.5, 12, 5.5], "polarized": True, "reverse_power": "no harm, does not work",
             "joins": [{"port_kind": "pin", "mates_with": "breadboard hole", "method": "insert", "holds_by": "spring", "reversible": "hand"}],
             "learner_tips": ["Check which pin is VCC."], "card_issues": [], "confidence": 0.8,
             "specs": {"maker": "Aosong", "model": "DHT11", "interface": ["Single-wire"]},
             "basis": {"maker": "maker page", "model": "card", "interface": "general knowledge"}}
    fake = lambda system, content, schema: ({"parts": [copy.deepcopy(draft)]}, {"seconds": 0, "cost_usd": 0})
    entries, _, issues = pm.draft({"dht11": (cards["dht11"], None)}, "arduino", None, "test", fake)
    stored = pm.normalize(entries["dht11"])
    assert stored["basis"]["maker"] == "maker-page" and stored["reverse_power"] == "no-harm"
    m11 = lambda found: [x for x in found if x[0] == "M11"]
    assert m11(pm.check([{**stored, "part_type_id": "dht11"}], {"dht11": (cards["dht11"], None)}, "arduino", None)) == []
    assert naming.metadata_veto(draft, stored) is None  # the same part, one side in words, one in codes


def test_progress_reads_swaps_from_the_catalogue():
    """The progress check takes which holes are one strip, which pins are the same and which legs swap from the parts
    catalogue (metadata.interchangeable), not from rules of its own: with the card's old naming rule switched off it
    still reads a hole as its strip and GND.2 as GND."""
    from graph.arduino import graphs
    from graph import lesson_store as lg
    cards = lg._cards(lg.PARTS)
    types = {"bb1": "breadboard", "uno": "arduino-uno", "r1": "resistor"}
    no_rule = lambda inst: {}
    assert graphs._where(cards, types, no_rule, "bb1", "12t.c") == ("strip", "bb1:12t")
    assert graphs._where(cards, types, no_rule, "bb1", "tp.40") == ("strip", "bb1:tp")
    assert graphs._where(cards, types, no_rule, "uno", "GND.2") == ("port", "uno:GND")
    assert graphs._where(cards, types, no_rule, "uno", "13") == ("port", "uno:13")
    assert part_catalogue.either_way(lg.definition(cards, "resistor")[0]) == [["1", "2"]]
    assert part_catalogue.either_way(lg.definition(cards, "led")[0]) == []


def test_new_parts_follow_the_metadata_rules(tmp_path):
    """Every way a lesson is made calls part_metadata.describe_new for its new parts: only a part with no metadata is
    drafted; the draft is checked, stored as codes, and the catalogue rebuilt so the computed fields are there."""
    import copy, json, shutil
    from graph.parts import part_metadata as pm
    path = tmp_path / "parts.json"
    shutil.copy(part_catalogue.PATH, path)
    parts = json.loads(path.read_text())
    keep = {k: parts["dht11"]["metadata"][k] for k in ("domain", "source_catalogue", "card_made_by")}
    parts["dht11"]["metadata"] = keep  # as if the part were new: a card, no metadata
    path.write_text(json.dumps(parts))
    calls = []
    draft = {"part_type_id": "dht11", "description": "A temperature and humidity sensor.", "material": "plastic case with metal pins",
             "size_studs": None, "dimensions_mm": [15.5, 12, 5.5], "polarized": True, "reverse_power": "damage",
             "joins": [{"port_kind": "pin", "mates_with": "breadboard hole", "method": "insert", "holds_by": "spring", "reversible": "hand"}],
             "learner_tips": ["Check which pin is VCC."], "card_issues": [], "confidence": 0.8,
             "specs": {"model": "DHT11", "interface": ["Single-wire"]}, "basis": {"model": "card", "interface": "general knowledge"}}

    def fake(system, content, schema):
        calls.append(content[0]["text"])
        return {"parts": [copy.deepcopy(draft)]}, {"seconds": 0, "cost_usd": 0}
    st = pm.describe_new(["dht11", "resistor"], "arduino", call=fake, path=path)
    assert st["described"] == 1 and st["already"] == 1 and len(calls) == 1  # the resistor has metadata: not asked
    m = part_catalogue.load(path)["dht11"]["metadata"]
    assert m["material"] == ["metal", "plastic"] and m["joins"][0]["mates"] == ["breadboard-hole"] and m["status"] == "drafted"
    assert m["fits"] and any(w["way"] == "breadboard" for w in m["connect_by"])  # computed by code after the save
    assert pm.describe_new(["dht11"], "arduino", call=fake, path=path)["described"] == 0 and len(calls) == 1


def test_new_cards_follow_the_naming_rules(tmp_path):
    """Every new card passes the naming rules before it is stored (ingest._store), from a shop or drafted by Claude:
    a colour or value in the id, a generic name, or a part we have under another id (N7: the same model) is
    quarantined with its reason; a really new part is stored."""
    import json, shutil
    from graph.parts import ingest
    from graph.parts.cards import CardStore
    from graph import lesson_store as lg
    path = tmp_path / "cards.json"
    shutil.copy(lg.ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json", path)
    store = CardStore(path)
    base = json.loads(path.read_text())["dht11"]
    for tid, name, stored in (("red-led", "red LED", False), ("resistor-220", "220 ohm resistor", False),
                              ("dht11-sensor", "DHT11 temperature and humidity sensor", False),
                              ("dht-11", "DHT11", False), ("lm35", "LM35 temperature sensor", True)):
        own = {**base["source"], "url": f"https://shop.example/{tid}"}  # its own shop page (one page, one part: N7)
        assert bool(ingest._store(store, {**base, "part_type_id": tid, "display_name": name, "source": own})) is stored, tid
    reasons = {q["card"]["part_type_id"]: q["reason"] for q in json.loads((tmp_path / "cards_quarantine.json").read_text())}
    assert "N2" in reasons["red-led"] and "N7" in reasons["dht11-sensor"] and "'dht11'" in reasons["dht-11"]


def test_one_part_one_id():
    """A part merged into another keeps working under its old id (graphs from earlier runs), and a new card from a
    shop page that already has a card is refused (naming N7), so packaging copies (-headers, -pins) stay out."""
    import collections
    from graph import lesson_store as lg
    from graph.parts import naming
    from graph.parts.cards import CardStore
    from graph.parts.cards import REDIRECTS, resolve
    store = CardStore(pathlib.Path(__file__).resolve().parents[2] / "graph" / "parts" / "arduino" / "cards_electronics.json")
    assert resolve("arduino-mkr1000-headers") == "arduino-mkr1000" and "arduino-mkr1000-headers" not in store.cards
    assert resolve("arduino-mkr1000-wifi") == "arduino-mkr-wifi-1010" and resolve("temp-dht11") == "dht11"
    assert store.get("temp-dht11") and len(store.cards["arduino-mkr1000"]["ports"]) == 30
    cards = {t: c for t, c in store.cards.items()}
    assert lg.definition(cards, "arduino-mkr1000-headers")[0]["part_type_id"] == "arduino-mkr1000"
    lego = CardStore(pathlib.Path(__file__).resolve().parents[2] / "graph" / "parts" / "lego" / "cards_lego.json")
    assert all(v in (lego.cards if v.startswith("lego-") else store.cards) for v in REDIRECTS.values())
    assert resolve("lego-98138pr0008") == "lego-98138"  # a printed tile is the plain tile (one card per design)
    assert "N4" in {r for r, _ in naming.check([{"type": "temp-dht11", "name": "DHT11"}], store)}
    copy = {"type": "samd21-wifi", "name": "SAMD21 WiFi",
            "source": {"url": "https://www.seeedstudio.com/ARDUINO-MKR1000-p-3167.html?x=1"}}
    found = naming.check([copy], store)
    assert any(r == "N7" and "'arduino-mkr1000'" in m for r, m in found), found
    by_page = collections.Counter(naming.page_key((c.get("source") or {}).get("url")) for c in store.cards.values())
    assert not [k for k, n in by_page.items() if k and n > 1]  # no two cards from one shop page


def test_inventory_rows_match_model_pieces():
    """A Rebrickable row and the 3D model's pieces are matched across the two catalogues' known differences: prints
    of a lettered design, LDraw's moved numbers, assemblies (Rebrickable sub-parts, minifigure and minidoll rules,
    the data table), and an assembly the model has whole stays whole."""
    from graph.parts.lego import lego_ids
    assert lego_ids.same_part("lego-3626bpr0387", "", "lego-3626bp85", "")
    assert lego_ids.same_part("lego-54200", "", "lego-50746", "")  # LDraw's 50746 is 54200
    piece = lambda i, t, label="": {"id": i, "type": t, "label": label, "props": {"colour": "Red"}}  # noqa: E731
    rows = [{"part": "lego-298c02", "count": 1, "colour": "Yellow"}, {"part": "lego-970c28", "count": 1, "colour": "Blue"},
            {"part": "lego-92818c01pr0002", "count": 1, "colour": "Magenta"}]
    pieces = [piece("a", "lego-4592"), piece("b", "lego-4593"), piece("c", "lego-3815"), piece("d", "lego-3816"),
              piece("e", "lego-3817"), piece("f", "lego-92248"), piece("g", "lego-92250p01", "Figure Friends Legs with Skirt")]
    problems, _ = lego_ids.match(rows, pieces)
    assert problems == [] and sorted(rows[0]["instances"]) == ["a", "b"] and "g" in rows[2]["instances"]
    whole = [{"part": "lego-3829c01", "count": 1, "colour": "Grey"}]
    assert lego_ids.match(whole, [piece("s", "lego-3829c01")])[0] == []


def test_grouped_arduino_steps_make_their_joins():
    """A lesson step that groups a part and its wires names each port with its part ('wire1.a', an id may hold a dot);
    bare ports are the step's own part; a wire placed by a step makes both its ends."""
    from graph.arduino import graphs as ag
    phys = {"nodes": [{"id": "pot1", "type": "potentiometer"}, {"id": "wire3", "type": "jumper-wire"},
                      {"id": "pb1.wf", "type": "jumper-wire"}, {"id": "bb1", "type": "breadboard"}, {"id": "uno", "type": "arduino-uno"}],
            "edges": [{"id": "e1", "type": "joined", "u": "pot1", "u_port": "SIG", "v": "bb1", "v_port": "2t.a"},
                      {"id": "e2", "type": "joined", "u": "wire3", "u_port": "a", "v": "uno", "v_port": "A3"},
                      {"id": "e3", "type": "joined", "u": "wire3", "u_port": "b", "v": "pot1", "v_port": "SIG"},
                      {"id": "e4", "type": "joined", "u": "pb1.wf", "u_port": "a", "v": "bb1", "v_port": "3t.d"}]}
    insts, made = ag._arduino_targets({"at": {"SIG": "bb1:2t.a", "wire3.a": "uno:A3", "pb1.wf.a": "bb1:3t.d"}}, phys)
    assert insts == ["pot1", "wire3", "pb1.wf"] and sorted(made) == ["e1", "e2", "e3", "e4"]


def test_ldraw_parts_get_cards_by_code():
    """A 3D model's LDraw number Rebrickable has no part for gets a card by code from the LDraw file: its name, the
    current number it was moved to, and the studs its shape has."""
    from graph.parts import ingest
    assert ingest.ldraw_current("50746") == "54200"
    c = ingest.ldraw_card("95820")
    assert c and c["source"]["made_by"] == "code" and {"stud.1.1", "stud.1.2"} <= {p["id"] for p in c["ports"]}


def test_two_sub_builds_of_one_step_have_their_own_ids():
    """A main step that two sub-builds are part of numbers their steps in one run (9.1-9.2, then 9.3)."""
    from graph.lego_booklet import pdf_lesson as pl
    base = {"page": 1, "crop": [0, 0, 10, 10], "png": "x.png", "boxes": [], "arrows": [], "build": 0, "times": 1}
    steps = [{**base, "step": 1, "kind": "main", "label": "8", "box": None, "attaches": [], "prev": None},
             {**base, "step": 2, "kind": "sub", "label": "sub-1 · 1", "box": "sub-1", "attaches": [], "prev": None},
             {**base, "step": 3, "kind": "sub", "label": "sub-1 · 2", "box": "sub-1", "attaches": [], "prev": 2},
             {**base, "step": 4, "kind": "sub", "label": "sub-2", "box": "sub-2", "attaches": [], "prev": None},
             {**base, "step": 5, "kind": "main", "label": "9", "box": None, "attaches": ["sub-1", "sub-2"], "prev": 1}]
    reads = [{"step": i, "instruction": "", "adds": [], "confidence": 1} for i in range(1, 6)]
    _, inst = pl.build("30311-1", reads, steps, [], [], [], None, {"build": {}, "box": {}})
    ids = [n["id"] for n in inst["nodes"] if n["kind"] == "step"]
    assert len(ids) == len(set(ids)) and {i.rsplit("-", 1)[1] for i in ids} == {"8", "9.1", "9.2", "9.3", "9"}


def test_nothing_goes_in_under_a_piece_already_on():
    """S14: nothing slides in between pieces already on (b1 between b0 below and b2 above); pushing a piece up into
    the underside of what is built is fine, and so is a sub-assembly attached after its support."""
    from graph.lego_3d import lesson as L
    P = [{"id": "b0", "part_num": "3001", "colour": "Red", "holds": ["b1"], "fastens": ["b1"], "sits_on": []},
         {"id": "b1", "part_num": "3001", "colour": "Red", "holds": ["b0", "b2"], "fastens": ["b0", "b2"], "sits_on": ["b0"]},
         {"id": "b2", "part_num": "3001", "colour": "Red", "holds": ["b1"], "fastens": ["b1"], "sits_on": ["b1"]}]
    step = lambda pieces, sub="", attach="": {"pieces": pieces, "subassembly": sub, "attach": attach,  # noqa: E731
                                              "instruction": "x"}
    late = {"steps": [step(["b0"]), step(["b2"]), step(["b1"])]}  # b1 into the gap between b0 and b2
    under = {"steps": [step(["b2"]), step(["b1"]), step(["b0"])]}  # each pushed up underneath: fine
    fine = {"steps": [step(["b0"]), step(["b2"], sub="top"), step(["b1"]), step([], attach="top")]}
    assert not any(r == "S14" for r, _ in L.check(under, P))
    assert any(r == "S14" for r, _ in L.check(late, P))
    assert not any(r == "S14" for r, _ in L.check(fine, P))


def test_a_plain_part_is_the_catalogue_plain_part():
    """R4: '8 x LED, green' is the catalogue's 'led' (colour a property), not a product with LED in its name; a bare
    number is a count, not a model number (R3)."""
    from graph.arduino import part_review as pr
    item = {"lesson_name": "8 x additional LED, green (Example 2, 16 total)", "ports_used": [], "props": {}}
    assert any(m.startswith("R4") for m in pr.check_type("adafruit-3433", item, None))
    assert pr.check_type("led", item, None) == []


def test_attach_step_does_not_count_the_sub_build_again():
    """A step that puts a finished sub-build on, and a read that counts one of its pieces again there: the extra
    comes off the attaching step when the set's count is passed."""
    from graph.lego_booklet import pdf_lesson as pl
    steps = [{"step": 1, "kind": "sub", "box": "sub-1", "attaches": []},
             {"step": 2, "kind": "main", "box": None, "attaches": ["sub-1"]}]
    reads = [{"step": 1, "times": 4, "adds": [{"part": "lego-4624", "colour": "Grey", "count": 1}]},
             {"step": 2, "times": 1, "adds": [{"part": "lego-4624", "colour": "Grey", "count": 1}]}]
    reads, ph = pl.attach_overcount(steps, reads, [{"part": "lego-4624", "colour": "Grey", "count": 4}])
    assert reads[1]["adds"] == [] and ph["removed"][0]["step"] == 2


def test_pinouts_are_checked_before_they_are_kept():
    """A drafted pinout is kept only with unique names, as many as the package has, and power or ground named."""
    from graph.parts.arduino import pinouts
    good = {"pins": ["VCC", "GND", "DT", "SCK"], "kind": "header-pin", "package_pins": 4, "power": ["VCC"],
            "ground": ["GND"], "basis": "module"}
    assert pinouts.check(good) == []
    assert pinouts.check({**good, "pins": ["VCC", "GND", "DT", "DT"]})
    assert pinouts.check({**good, "package_pins": 5})
    assert pinouts.check({**good, "power": [], "ground": []})


def test_never_more_of_a_piece_than_the_set_has():
    """The parts list is a hard limit: a piece read in more steps than the set has copies comes off the steps whose
    picture does not show it, then off the least sure, last first."""
    from graph.lego_booklet import pdf_lesson as pl
    steps = [{"step": 1, "times": 1}, {"step": 2, "times": 3}]
    reads = [{"step": 1, "times": 1, "confidence": 0.5, "adds": [{"part": "lego-3023", "colour": "White", "count": 1}]},
             {"step": 2, "times": 3, "confidence": 0.9, "adds": [{"part": "lego-3023", "colour": "White", "count": 1}]}]
    reads, ph = pl.enforce_inventory("x", steps, reads, [{"part": "lego-3023", "colour": "White", "count": 3,
                                                           "name": "Plate 1 x 2"}], call=False)
    assert reads[0]["adds"] == [] and reads[1]["adds"][0]["count"] == 1 and ph["removed"][0]["step"] == 1


def test_every_piece_of_the_set_is_used():
    """The parts list is used whole: a piece Claude only guesses a step for goes there (flagged), and one with no
    answer goes on the last step (flagged), so no piece is left out of the lesson."""
    from graph.lego_booklet import pdf_lesson as pl
    steps = [{"step": 1, "png": "x"}, {"step": 2, "png": "x"}]
    reads = [{"step": 1, "adds": []}, {"step": 2, "adds": []}]
    inv = [{"part": "lego-3069b", "colour": "Green", "count": 1, "name": "Tile"},
           {"part": "lego-30115", "colour": "Red", "count": 1, "name": "Hat"}]
    ans = {"allocations": [{"part": "lego-3069b", "colour": "Green", "count": 1, "step": 1, "where": "front",
                            "evidence": "maybe", "confidence": 0.3}]}
    reads, still, ph = pl.allocate("x", steps, reads, inv, call=lambda *a: (ans, {}), images=False)
    assert still == []
    assert reads[0]["adds"][0]["part"] == "lego-3069b" and "guess" in reads[0]["problems"][0]
    assert reads[1]["adds"][0]["part"] == "lego-30115" and "last step" in reads[1]["problems"][0]


def test_code_links_analog_number_and_builtin_led():
    """analogRead(0) is A0, not digital pin 0; pin 13 driven as an output is the board's built-in LED (no wire)."""
    from graph.arduino import pins
    card = {"ports": [{"id": "0"}, {"id": "13", "builtin": "LED_BUILTIN"}, {"id": "A0"}]}
    ls = pins.links("#define p 0\nint led = 13;\nvoid loop(){ analogRead(p); digitalWrite(led, 1); }",
                          "uno", card)
    ports = {l["port"]: l for l in ls if l["kind"] == "code"}
    assert "uno:A0" in ports and "uno:0" not in ports
    assert ports["uno:13"].get("builtin_led")


def test_model_shortcut_piece_covers_its_listed_parts():
    """A 3D model's wheel-with-tyre shortcut (6014bc02) accounts for the rim and the tyre the inventory lists apart."""
    from graph.parts.lego import lego_ids
    if not lego_ids.shortcut_parts("lego-6014c02"):
        return  # no LDraw library here
    rows = [{"part": "lego-6014b", "count": 1, "colour": "Light Bluish Gray", "name": "Wheel Rim"},
            {"part": "lego-87697", "count": 1, "colour": "Black", "name": "Tyre"}]
    pieces = [{"id": "b1", "type": "lego-6014c02", "label": "Wheel with Tyre", "props": {"colour": "Light Bluish Gray"}}]
    problems, _ = lego_ids.match(rows, pieces)
    assert problems == [] and rows[0]["instances"] == ["b1"] and rows[1]["instances"] == ["b1"]


def test_r3_one_of_the_offered_chips_is_enough():
    """'Arduino Board with an ATmega168 or ATmega328 chip': the Uno (ATmega328P) fits; a board with neither does not."""
    from graph.arduino import part_review as pr
    item = {"lesson_name": "Arduino Board with an ATmega168 or ATmega328 chip.", "ports_used": [], "props": {}}
    assert not any(m.startswith("R3") for m in pr.check_type("arduino-uno", item, None))
    assert any(m.startswith("R3") for m in pr.check_type("arduino-mega", item, None))


def test_builtin_led_from_the_pin_alias():
    from graph.arduino import pins
    card = {"ports": [{"id": "13", "aliases": ["D13", "LED_BUILTIN"]}]}
    assert pins.links("void setup(){ pinMode(13, OUTPUT); }", "m", card)[0].get("builtin_led")


def test_valued_parts_list_row_matches_a_part_of_that_value():
    """'resistor-220' on the parts list is the build's resistor with value 220 (and 200000 is 200k)."""
    from graph.arduino import graphs as ag
    phys = {"nodes": [{"id": "r1", "type": "resistor", "props": {"value": "220"}},
                      {"id": "r2", "type": "resistor", "props": {"value": "200k"}}]}
    rows = [{"part": "resistor-200000", "count": None}, {"part": "resistor-220", "count": None}]
    same = lambda c, t: ({"part_type_id": "resistor"},)  # noqa: E731  (every resistor-N is the resistor card)
    assert ag.match_parts(rows, phys, {}, same) == []
    assert rows[0]["instances"] == ["r2"] and rows[1]["instances"] == ["r1"]


def test_a_net_joins_two_parts():
    """A driver chip's unused input and output, joined only through the chip itself, are not a net of the circuit."""
    from graph.arduino import graphs as ag
    cards = {"uln": {"intrinsic_behaviour": {"internal_pass_through": [["1", "16"], ["7", "10"]]}}, "m": {}}
    phys = {"nodes": [{"id": "u", "type": "uln"}, {"id": "mo", "type": "m"}],
            "edges": [{"type": "electrical", "u": "u", "u_port": "16", "v": "mo", "v_port": "a"}]}
    assert ag.nets(phys, cards) == [["mo:a", "u:16"]]  # a chip input-output path is not a wire either


def test_combination_page_with_another_set():
    """A page naming this set and another set number ('8655 + 8658 =') builds a combination: not this set's steps."""
    from graph.lego_booklet import booklet_layout as bl

    class Page:
        rect = type("R", (), {"width": 100, "height": 100})()
        def __init__(self, text): self.text = text
        def get_text(self, *a): return self.text
    import unittest.mock as um
    with um.patch.object(bl, "scanned", lambda p: False):
        assert bl.other_set(Page("8655 + 8658 = ©2005 4271808"), "8658-1")
        assert not bl.other_set(Page("8658 Big Bling Wheelie ©2005"), "8658-1")


def test_three_in_one_booklet_is_model_a_only():
    """A 3-in-1 booklet's models B and C (numbers starting at 1 again, each from all the pieces) are not steps of
    model A; another set's second build starting at 1 (a second vehicle) is kept."""
    from graph.lego_booklet import pdf_lesson as pl
    steps = [{"step": i + 1, "kind": "main", "build": b, "label": str(n), "page": 1}
             for i, (b, n) in enumerate([(0, n) for n in range(1, 7)] + [(1, n) for n in range(1, 7)])]
    kept, alts = pl.first_model("x", steps, theme="672")
    assert len(kept) == 6 and alts[0]["steps"] == 6
    assert pl.first_model("x", steps, theme="494") == (steps, [])


def test_nets_through_cables_not_components():
    """A cable's wires join its ends; a resistor's two legs are two nets (Blink: three nets, not one)."""
    from graph.arduino import graphs as ag
    cards = {"res": {"category": "resistor", "intrinsic_behaviour": {"internal_pass_through": [["1", "2"]]}},
             "cab": {"category": "cable", "intrinsic_behaviour": {"internal_pass_through": [["a", "b"]]}}, "b": {}}
    phys = {"nodes": [{"id": "r", "type": "res"}, {"id": "c", "type": "cab"}, {"id": "u", "type": "b"}],
            "edges": [{"type": "electrical", "u": "u", "u_port": "13", "v": "r", "v_port": "1"},
                      {"type": "electrical", "u": "r", "u_port": "2", "v": "c", "v_port": "a"},
                      {"type": "electrical", "u": "c", "u_port": "b", "v": "u", "v_port": "GND"}]}
    assert ag.nets(phys, cards) == [["c:a", "c:b", "r:2", "u:GND"], ["r:1", "u:13"]]


def test_final_check_pairs_meet_at_a_connector_pin():
    """'header pin 15 to r1:1' and 'header pin 15 to lcd:A' name the net lcd:A, r1:1 (the pin is folded away)."""
    from graph.arduino import graphs as ag
    cards = {"hdr": {"intrinsic_behaviour": {"is_connector_only": True}}, "r": {}, "l": {}}
    types = {"hdr15": "hdr", "r1": "r", "lcd1": "l"}
    ok, why = ag.compare_check([["hdr15:pin", "r1:1"], ["hdr15:pin", "lcd1:A"]], [["lcd1:A", "r1:1"]], cards, types)
    assert ok, why


def test_words_never_name_a_breadboard_the_circuit_lacks():
    """W5: a circuit with no breadboard (parts twisted onto the wires' ends) must not be worded with one."""
    from graph.arduino.circuit_lesson import CircuitLessons
    flat = {"nodes": [{"id": "uno", "type": "arduino-uno"}, {"id": "r1", "type": "resistor"},
                      {"id": "wire1", "type": "jumper-wire"}], "edges": []}
    src = {"flat": flat, "catalogue": {}, "steps": [{"id": "s1", "part": "r1", "type": "resistor", "expected_nets": []}]}
    step = {"uses": ["s1"], "goal": "Join the resistor to the wire.", "hints": ["Twist the leads tightly."]}
    words = lambda clip: {"steps": [{**step, "clip": clip}]}  # noqa: E731
    found = CircuitLessons.check(CircuitLessons.__new__(CircuitLessons), src, words("Put the resistor in column 5 of the breadboard."), None, set())
    assert any(r == "W5" for r, _ in found)
    found = CircuitLessons.check(CircuitLessons.__new__(CircuitLessons), src, words("Twist one resistor lead round the wire's end."), None, set())
    assert not any(r == "W5" for r, _ in found)


def test_a_short_minifigure_breakdown_is_the_whole_figure():
    """Rebrickable lists some printed torsos as the torso print alone (973c05h01pr1163 -> 973pdd): the figure is
    still built of a torso, two arms and two hands, so the model's arms and hands are matched to it."""
    from graph.parts.lego import lego_ids
    assert lego_ids.components("lego-973c05h01pr1163") == ("973", "3818", "3819", "3820", "3820")
    rows = [{"part": "lego-973c05h01pr1163", "count": 1, "colour": "Dark Blue", "name": "Torso Plaid Shirt"}]
    pieces = [{"id": f"b{i}", "type": f"lego-{t}", "label": n, "props": {"colour": c}} for i, (t, n, c) in enumerate(
        [("973", "Minifig Torso", "Dark Blue"), ("3818", "Minifig Arm Right", "Dark Blue"),
         ("3819", "Minifig Arm Left", "Dark Blue"), ("3820", "Minifig Hand", "Yellow"), ("3820", "Minifig Hand", "Yellow")], 1)]
    problems, _ = lego_ids.match(rows, pieces)
    assert problems == [] and len(rows[0]["instances"]) == 5


def test_an_unmatched_minifigure_piece_is_a_note():
    """Minifigures do not decide whether a lesson is ready: a figure piece the inventory does not account for is
    noted, not a problem; any other unmatched piece still is."""
    from graph.lego_3d import graphs
    listed = [{"part": "lego-3001", "count": 1, "colour": "Red", "name": "Brick 2 x 4"}]
    phys = {"nodes": [{"id": "b1", "type": "lego-3001", "label": "Brick 2 x 4", "props": {"colour": "Red"}},
                      {"id": "b2", "type": "lego-3820", "label": "Minifig Hand", "props": {"colour": "Yellow"}}]}
    out = graphs._lego_parts_list(listed, phys, [{"part_num": "3001"}])
    assert out["problems"] == [] and any("minifigure piece" in n for n in out["notes"])
    phys["nodes"].append({"id": "b3", "type": "lego-3003", "label": "Brick 2 x 2", "props": {"colour": "Red"}})
    listed[0].pop("instances", None)
    out = graphs._lego_parts_list(listed, phys, [{"part_num": "3001"}])
    assert any("b3" in p for p in out["problems"])


def _plan_pieces(spec):
    """Pieces for an order test: (id, official step, fastens to)."""
    out = []
    for i, off, to in spec:
        out.append({"id": i, "part_num": "3001", "name": "Brick 2 x 4", "colour": "Red", "official_step": off,
                    "official_sub": "", "holds": list(to), "fastens": list(to), "sits_on": list(to)})
    for p in out:  # holding is both ways
        for q in out:
            if p["id"] in q["fastens"] and q["id"] not in p["fastens"]:
                p["holds"].append(q["id"]); p["fastens"].append(q["id"])
    return out


def test_one_piece_too_early_is_moved_later():
    """One piece put before its official step makes every piece after it look late (S7): the order fix moves that
    one piece later, to its own official step's pieces, instead of every other piece earlier."""
    from graph.lego_3d import lesson as L
    pieces = _plan_pieces([("b1", 1, []), ("b2", 1, ["b1"]), ("b3", 2, ["b1"]), ("b4", 3, ["b1"]), ("b5", 3, ["b1"])])
    st = lambda ids: {"pieces": ids, "subassembly": "", "attach": "", "instruction": "x"}  # noqa: E731
    plan = {"steps": [st(["b1", "b4"]), st(["b2"]), st(["b3"]), st(["b5"])], "notes": []}
    assert [r for r, _ in L.check(plan, pieces, limit=10 ** 6)].count("S7") == 2
    fixed, moved = L.fix_order(plan, pieces, None)
    assert moved == ["b4"] and not [r for r, _ in L.check(fixed, pieces, limit=10 ** 6) if r == "S7"]
    assert fixed["steps"][-1]["pieces"] == ["b5", "b4"]


def test_s14_passes_a_support_lego_puts_in_later():
    """A piece that sits on one which comes later would slide in between (S14), unless LEGO's own booklet puts the
    support in later too (pushed up into it from below)."""
    from graph.lego_3d import lesson as L
    pieces = _plan_pieces([("b1", 1, []), ("b2", 1, ["b1"]), ("b3", 2, ["b1"])])
    for p in pieces:
        p["sits_on"] = {"b1": [], "b2": ["b3"], "b3": ["b1"]}[p["id"]]
    st = lambda ids: {"pieces": ids, "subassembly": "", "attach": "", "instruction": "x"}  # noqa: E731
    plan = {"steps": [st(["b1", "b2"]), st(["b3"])], "notes": []}
    assert "S14" not in [r for r, _ in L.check(plan, pieces, limit=10 ** 6)]  # LEGO: b2 in step 1, b3 in step 2
    pieces[1]["official_step"] = 3  # the booklet puts b3 in first: then sliding it in between is a mistake
    assert "S14" in [r for r, _ in L.check(plan, pieces, limit=10 ** 6)]


def _wire_flat(edges, nodes):
    """A circuit graph from (u, u_port, v, v_port) joins: each a joined edge and its electrical twin."""
    out = []
    for k, (u, up, v, vp) in enumerate(edges):
        out += [{"id": f"j{k}", "type": "joined", "u": u, "u_port": up, "v": v, "v_port": vp, "method": "insert"},
                {"id": f"e{k}", "type": "electrical", "u": u, "u_port": up, "v": v, "v_port": vp}]
    return {"nodes": [{"id": i, "type": t} for i, t in nodes.items()], "edges": out}


def test_a_wire_end_on_a_module_pin_is_in_its_step():
    """The wire lesson: two wires leave the same socket (A4), one to the other Arduino, one onto the sensor's pin. The
    sensor end is in no hole, but the step names it, so the store can tell the two wires apart."""
    from graph.arduino import circuit_lesson as C
    flat = _wire_flat([("w1", "a", "uno1", "A4"), ("w1", "b", "uno2", "A4"), ("w2", "a", "uno1", "A4"), ("w2", "b", "bmp1", "SDI")],
                      {"uno1": "arduino-uno", "uno2": "arduino-uno", "bmp1": "adafruit-bmp280", "w1": "jumper-wire", "w2": "jumper-wire"})
    steps, _ = C.plan_steps(flat, part_catalogue.Catalogue(part_catalogue.arduino_seed()))
    at = {k: v for s in steps if s["part"] == "w2" for k, v in s["at"].items()}
    assert at == {"a": "uno1:A4", "b": "bmp1:SDI"}


def test_a_module_names_the_grove_cable_plugged_into_it():
    """A Grove cable (a component, not a wire) goes in by its jumper ends; the module's own step then joins its other
    end, and never claims those joins before the module is placed."""
    from graph.arduino import circuit_lesson as C
    flat = _wire_flat([("c1", f"jumper.{n}", "uno1", p) for n, p in enumerate(["A5", "A4", "5V", "GND"], 1)]
                      + [("c1", f"grove.{n}", "oled1", p) for n, p in enumerate(["SCL", "SDA", "VCC", "GND"], 1)],
                      {"uno1": "arduino-uno", "c1": "grove-cable-4pin", "oled1": "grove-oled-096"})
    steps, _ = C.plan_steps(flat, part_catalogue.Catalogue(part_catalogue.arduino_seed()))
    by = {s["part"]: s["at"] for s in steps}
    assert set(by["c1"]) == {"jumper.1", "jumper.2", "jumper.3", "jumper.4"}
    assert by["oled1"] == {f"c1.grove.{n}": f"oled1:{p}" for n, p in enumerate(["SCL", "SDA", "VCC", "GND"], 1)}


def test_the_lesson_loop_keeps_its_best_plan(monkeypatch):
    """A repair can make a plan worse: answers with 3, then 1, then 5 issues end with the 1-issue plan (and a tie
    keeps the later plan)."""
    from graph import extract, lessons
    answers = iter([3, 1, 5, 5])

    class Session:
        def __init__(self, *a, **k):
            pass

        def first(self):
            return {"n": next(answers), "steps": []}, {"seconds": 0, "cost_usd": 0}

        repair = lambda self, msg: self.first()  # noqa: E731

        def close(self):
            pass

    class R(lessons.Recipe):
        name = "test"

        def source(self, case):
            return {"id": case}

        def prompt(self, src, section, built):
            return ""

        def check(self, src, part, section, built):
            return [("X", f"issue {i}") for i in range(part["n"])]

        def join(self, src, done):
            return done[0][1]

        def finish(self, src, lesson, phases):
            return lesson

        def save(self, src, lesson, stats):
            self.saved = lesson
            return "-"
    monkeypatch.setattr(extract, "SubscriptionSession", Session)
    r = R()
    st = lessons.make(r, "case")
    assert r.saved["n"] == 1 and len(st["issues_final"]) == 1 and st["issues_first"] == 3


def test_a_print_is_a_property_of_the_copy():
    from graph.parts.lego.lego_ids import unprinted, unprint_graphs
    assert unprinted("lego-3626cpr0914") == ("lego-3626c", "pr0914")
    assert unprinted("lego-973c28h01pr1470") == ("lego-973c28h01", "pr1470")  # an assembly keeps its code
    assert unprinted("lego-3626c") == ("lego-3626c", "") and unprinted("lego-2412b") == ("lego-2412b", "")
    g = {"physical": {"nodes": [{"id": "h1", "type": "lego-3626cpr0914", "props": {"colour": "Yellow"}},
                                {"id": "h2", "type": "lego-3626cpr0498", "props": {"colour": "Yellow"}}]},
         "lesson": {"parts_list": {"parts": [{"part": "lego-3626cpr0914", "colour": "Yellow", "count": 1}]}}}
    assert unprint_graphs(g) == 3
    assert {n["type"] for n in g["physical"]["nodes"]} == {"lego-3626c"}
    assert [n["props"]["print"] for n in g["physical"]["nodes"]] == ["pr0914", "pr0498"]
    assert g["lesson"]["parts_list"]["parts"][0] == {"part": "lego-3626c", "colour": "Yellow", "count": 1, "print": "pr0914"}


def test_research_never_replaces_a_card_we_have(tmp_path):
    # a SparkFun "panel-mount button" came back as `pushbutton` and replaced the verified card (3 Nov 2026)
    import json as _json
    from graph.parts import ingest
    from graph.parts.cards import CardStore
    src = pathlib.Path(__file__).resolve().parents[2] / "graph" / "parts" / "arduino" / "cards_electronics.json"
    p = tmp_path / "cards.json"
    p.write_text(_json.dumps({"pushbutton": _json.loads(src.read_text())["pushbutton"]}))
    store = CardStore(p)
    other = {**store.cards["pushbutton"], "display_name": "Momentary Button - Panel Mount (Red)",
             "source": {"platform": "sparkfun", "url": "https://www.sparkfun.com/x.html", "external_id": None,
                        "made_by": "claude"}}
    kept = ingest._store(store, other)
    assert kept["display_name"] == "Pushbutton"
    assert _json.loads(p.read_text())["pushbutton"]["source"]["made_by"] == "verified"
