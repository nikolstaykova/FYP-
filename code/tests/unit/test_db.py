"""The lesson store as database rows (graph.db), without a database."""
import json

from graph import db


def test_flat_keeps_what_neo4j_can_hold_and_writes_the_rest_as_json():
    out = db.flat({"a": 1, "b": "x", "c": [1, 2], "d": {"k": 1}, "e": [[1, 2]], "f": None, "g": [1, "x"]})
    assert out["a"] == 1 and out["b"] == "x" and out["c"] == [1, 2]
    assert json.loads(out["d"]) == {"k": 1} and json.loads(out["e"]) == [[1, 2]] and json.loads(out["g"]) == [1, "x"]
    assert "f" not in out


def test_an_arduino_lesson_becomes_steps_instances_joins_and_parts():
    rows = db.lesson_rows("blink")
    assert rows["lesson"]["lesson_id"] == "blink" and rows["lesson"]["lesson_type"] == "arduino"
    assert {n["props"]["kind"] for n in rows["nodes"]["Step"]} >= {"gather", "build", "upload"}
    assert any(n["key"] == "blink/uno" for n in rows["nodes"]["Instance"])
    types = {t for t, *_ in rows["links"]}
    assert {"HAS_STEP", "IS_A", "END", "JOINED", "NEXT_STEP", "NEEDS"} <= types
    joins = {n["props"]["id"]: n["props"] for n in rows["nodes"]["Join"]}
    assert joins["e1"]["kind"] == "joined" and joins["e1"]["u_port"] == "a"


def test_a_booklet_step_points_at_the_part_with_its_count_and_colour():
    rows = db.lesson_rows("7268-1-pdf")
    places = [(a, b, p) for t, a, b, p, la, lb in rows["links"] if t == "PLACES" and lb == "Part"]
    assert places and all(b.startswith("lego-") and "count" in p for a, b, p in places)
    step = next(n for n in rows["nodes"]["Step"] if n["props"]["id"] == "red-crab-body-1")
    assert step["props"]["picture"].endswith("step1.png")
    assert {n["props"]["kind"] for n in rows["nodes"]["Build"]} == {"product"}


def test_a_sized_type_on_a_parts_list_is_its_family_with_the_value_kept():
    rows = db.lesson_rows("fade")
    needs = [(b, p) for t, a, b, p, la, lb in rows["links"] if t == "NEEDS" and p.get("listed_as", "").startswith("resistor")]
    assert needs == [("resistor", {**needs[0][1], "value": "220"})] and needs[0][1]["listed_as"] == "resistor-220"
