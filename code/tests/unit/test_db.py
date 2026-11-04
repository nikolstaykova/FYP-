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
    assert "HAS_STEP" not in types and "HAS_INSTANCE" not in types
    # the parts list: items that account for instances, which are their catalogue parts
    assert ("ACCOUNTS_FOR", "blink/parts_list/0") in {(t, a) for t, a, *_ in links}
    assert ("IS_A", "blink/uno", "arduino-uno") in {(t, a, b) for t, a, b, *_ in links}
    # joins are links between instances, with ports and the step that makes them
    j = next(p for t, a, b, p, *_ in links if t == "JOINED" and p["id"] == "e1")
    assert j["u_port"] == "a" and j["v_port"] == "13" and j["made_in"]
    assert "Join" not in rows["nodes"] and "MAKES" not in types
    # the gather step gathers every item on the list
    assert sum(t == "GATHERS" for t, *_ in links) == len(rows["nodes"]["Item"])


def test_a_booklet_lesson_starts_at_its_overview_and_steps_place_parts_list_items():
    rows = db.lesson_rows("7268-1-pdf")
    links = rows["links"]
    assert [b for t, a, b, *_ in links if t == "FIRST_STEP"] == ["7268-1-pdf/overview"]
    places = [(a, b, p) for t, a, b, p, la, lb in links if t == "PLACES"]
    assert places and all(lb == "Item" for t, a, b, p, la, lb in links if t == "PLACES")
    items = {n["key"]: n["props"] for n in rows["nodes"]["Item"]}
    assert all(items[b]["part"].startswith("lego-") and "count" in p for a, b, p in places)
    assert all(t == "IS_A" for t, a, *_ in links if a in items and t != "LISTS")  # no 3D model: item -> part
    step = next(n for n in rows["nodes"]["Step"] if n["props"]["id"] == "red-crab-body-1")
    assert step["props"]["picture"].endswith("step1.png")


def test_a_sized_type_on_a_parts_list_is_its_family_with_the_value_kept():
    items = [n["props"] for n in db.lesson_rows("fade")["nodes"]["Item"] if n["props"]["listed_as"].startswith("resistor")]
    assert [(i["part"], i["value"], i["listed_as"]) for i in items] == [("resistor", "220", "resistor-220")]


def test_every_node_has_a_readable_name_for_the_browser():
    blink = db.lesson_rows("blink")
    assert [n["props"]["name"] for n in blink["nodes"]["Step"]] == \
        ["Gather parts", "Step 1", "Step 2", "Step 3", "Step 4", "Upload code"]
    assert "2× Jumper wire" in [n["props"]["name"] for n in blink["nodes"]["Item"]]
    assert db.caption({"id": "red-crab-body-3", "kind": "step", "number": "3"}) == "Step 3 · red crab body"
    parts, ports = db.part_rows({"led": {"display_name": "LED", "ports": [{"id": "A", "kind": "lead"}]}})
    assert parts[0]["props"]["name"] == "LED" and ports[0]["props"]["name"] == "A"
