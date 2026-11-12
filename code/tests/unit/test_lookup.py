"""The tutor's lookups (tutor.lookup): it can travel the whole lesson by card, part or topic."""
from tutor import live, lookup


def test_lesson_topics():
    o = lookup.lesson_info("blink", "overview")
    assert o["build_steps"] == 5 and "troubleshooting" in o["topics_you_can_look_up"]
    assert lookup.lesson_info("blink", "troubleshooting")["troubleshooting"]
    assert len(lookup.lesson_info("4431-1", "cards")["cards"]) == len(live.steps("4431-1")["steps"])


def test_step_in_full_with_joins_in_words():
    s = lookup.step_info("blink", 3)
    assert s["why"] and any("column 14" in j for j in s["joins"]) and s["pieces"][0]["tip"]
    assert lookup.step_info("7268-1-pdf", 2)["picture_shows"]
    assert "error" in lookup.step_info("blink", 99)


def test_part_by_any_words_with_stand_ins():
    r = lookup.part_info("blink", "resistor")["found"][0]
    assert r["can_swap"]["value_ohms_range"] == [150, 600] and r["on_cards"]
    hand = lookup.part_info("4431-1", "yellow hand")["found"][0]
    assert hand["count"] == 6 and "colour" in hand["can_swap"]["free"]
    plate = lookup.part_info("7268-1-pdf", "4x4 plate")["found"][0]
    assert plate["count"] == 1 and plate["what_it_is"]
    assert lookup.part_info("blink", "propeller")["found"] == []


def test_tools_are_offered():
    names = [d["name"] for d in live.tools("lego")[0]["functionDeclarations"]]
    assert {"lesson_info", "step_info", "part_info"} <= set(names)
    assert "step_info" in live.brief("blink")


def test_resistor_colour_bands():
    from tutor.lookup import ohms, resistor_bands
    assert resistor_bands(220) == (["red", "red", "brown", "gold"], ["red", "red", "black", "black", "brown"])
    assert resistor_bands(10000)[0] == ["brown", "black", "orange", "gold"]
    assert resistor_bands(4.7)[0] == ["yellow", "violet", "gold", "gold"]
    assert [ohms(x) for x in ("Resistor 220", "10k", "4k7", "1M", "Resistor 4.7k")] == [220, 10000, 4700, 1000000, 4700]


def test_how_to_recognise_a_part():
    from tutor.lookup import recognise
    assert "red, red, brown" in recognise("Resistor 220", "resistor", None)["how_to_recognise"]
    assert "longer leg" in recognise("LED", "led", None)["how_to_recognise"]
    assert recognise("Black Brick 1 x 2", "lego-3004", "Bricks") == {}
