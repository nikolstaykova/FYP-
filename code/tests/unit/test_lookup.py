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
