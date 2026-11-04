"""The lesson store as database rows (graph.db), without a database."""
import json

from graph import db


def test_flat_keeps_what_neo4j_can_hold_and_writes_the_rest_as_json():
    out = db.flat({"a": 1, "b": "x", "c": [1, 2], "d": {"k": 1}, "e": [[1, 2]], "f": None, "g": [1, "x"]})
    assert out["a"] == 1 and out["b"] == "x" and out["c"] == [1, 2]
    assert json.loads(out["d"]) == {"k": 1} and json.loads(out["e"]) == [[1, 2]] and json.loads(out["g"]) == [1, "x"]
    assert "f" not in out


def test_an_arduino_lesson_is_record_steps_physical_and_parts_joined_through_the_parts():
    rows = db.lesson_rows("blink")
    links = rows["links"]
    types = {t for t, *_ in links}
    assert rows["lesson"]["lesson_id"] == "blink" and rows["lesson"]["lesson_type"] == "arduino"
    # the record points at its first step only; the steps follow on
    assert [(a, b) for t, a, b, *_ in links if t == "FIRST_STEP"] == [("blink", "blink/gather")]
    assert not types & {"HAS_STEP", "HAS_INSTANCE", "LISTS", "ACCOUNTS_FOR"} and "Item" not in rows["nodes"]
    # the parts list is the lesson NEEDing parts, with the instances each row stands for kept on the link
    wires = next(p for t, a, b, p, *_ in links if t == "NEEDS" and b == "jumper-wire")
    assert wires["count"] == 2 and wires["instances"] == ["wire1", "wire2"]
    # steps place instances; an instance is a part
    assert ("PLACES", "blink/led1") in {(t, b) for t, a, b, *_ in links}
    assert ("IS_A", "blink/uno", "arduino-uno") in {(t, a, b) for t, a, b, *_ in links}
    # joins are links between instances, with ports and the step that makes them
    j = next(p for t, a, b, p, *_ in links if t == "JOINED" and p["id"] == "e1")
    assert j["u_port"] == "a" and j["v_port"] == "13" and j["made_in"]
    assert "MAKES" not in types
    # the gather step gathers every part on the list, with its count
    gathers = [(b, p) for t, a, b, p, *_ in links if t == "GATHERS"]
    assert len(gathers) == sum(t == "NEEDS" for t, *_ in links) and ("jumper-wire", 2) in {(b, p["count"]) for b, p in gathers}


def test_a_booklet_lesson_has_one_instance_per_copy_placed_by_its_steps():
    rows = db.lesson_rows("7268-1-pdf")
    links = rows["links"]
    assert [b for t, a, b, *_ in links if t == "FIRST_STEP"] == ["7268-1-pdf/overview"]
    inst = {n["key"]: n["props"] for n in rows["nodes"]["Instance"]}
    needs = [p for t, a, b, p, *_ in links if t == "NEEDS"]
    assert len(inst) == sum(p["count"] for p in needs)  # one instance per copy on the parts list
    placed = [b for t, a, b, p, la, lb in links if t == "PLACES"]
    assert all(lb == "Instance" for t, a, b, p, la, lb in links if t == "PLACES")
    assert sorted(placed) == sorted(inst)  # every copy placed once, by its step
    # the part is stored once; the colour is on the copy
    is_a = {a: b for t, a, b, *_ in links if t == "IS_A"}
    plate = next(k for k, v in inst.items() if v.get("label") == "Plate 4 x 4")
    assert is_a[plate] == "lego-3031" and inst[plate]["colour"] == "Black"
    step = next(n for n in rows["nodes"]["Step"] if n["props"]["id"] == "red-crab-body-1")
    assert step["props"]["picture"].endswith("step1.png")


def test_a_sized_type_on_a_parts_list_is_its_family_with_the_value_kept():
    needs = [(b, p) for t, a, b, p, *_ in db.lesson_rows("fade")["links"] if t == "NEEDS" and p["listed_as"].startswith("resistor")]
    assert [(b, p["value"], p["listed_as"]) for b, p in needs] == [("resistor", "220", "resistor-220")]


def test_every_node_has_a_readable_name_for_the_browser():
    blink = db.lesson_rows("blink")
    assert [n["props"]["name"] for n in blink["nodes"]["Step"]] == \
        ["Gather parts", "Step 1", "Step 2", "Step 3", "Step 4", "Upload code"]
    assert db.caption({"id": "red-crab-body-3", "kind": "step", "number": "3"}) == "Step 3 · red crab body"
    parts, ports = db.part_rows({"led": {"display_name": "LED", "ports": [{"id": "A", "kind": "lead"}]}})
    assert parts[0]["props"]["name"] == "LED" and ports[0]["props"]["name"] == "A"
