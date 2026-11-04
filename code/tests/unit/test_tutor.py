"""The voice tutor's lesson brief, steps and cost (code/tutor/live.py), without calling any model."""
from tutor import live


def test_steps_are_numbered_from_one_with_their_parts_and_booklet_pictures():
    blink = live.steps("blink")
    assert [s["n"] for s in blink["steps"]] == list(range(1, len(blink["steps"]) + 1))
    assert blink["steps"][0]["title"] == "Gather the parts" and blink["steps"][-1]["title"] == "Upload the code"
    crab = live.steps("7268-1-pdf")
    assert crab["steps"][0]["picture"].endswith("step1.png")
    assert any(p["what"] == "Black Plate 4 x 4" for p in crab["steps"][0]["parts"])


def test_the_brief_holds_the_rules_and_every_step():
    b = live.brief("blink")
    assert "call show_step" in b and "Never invent parts" in b
    assert all(f"Step {s['n']} (" in b for s in live.steps("blink")["steps"])


def test_a_turn_is_priced_by_modality():
    usage = {"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000_000}],
             "responseTokensDetails": [{"modality": "AUDIO", "tokenCount": 1_000_000}], "thoughtsTokenCount": 0}
    assert live.cost_usd(usage) == live.PRICES["text_in"] + live.PRICES["audio_out"]
    assert live.CAP_USD <= 4.3  # under 4 euro


def test_the_session_starts_with_the_name_and_checks_parts_only_for_electronics():
    new = live.brief("blink")
    assert "ask their name" in new and "call no tool" in new and "remember_name" in new
    assert "Greet Mark by name" in live.brief("blink", "Mark")
    assert "take_closeup" in new and "never take the close-up in the same breath" in new
    arduino = [d["name"] for d in live.tools("arduino")[0]["functionDeclarations"]]
    lego = [d["name"] for d in live.tools("lego")[0]["functionDeclarations"]]
    assert {"open_camera", "take_photo", "check_parts", "take_closeup"} <= set(arduino)
    assert not {"open_camera", "check_parts"} & set(lego) and "start_building" in lego
    assert "no parts check" in live.brief("7268-1-pdf")


def test_the_tutor_knows_columns_do_not_matter_only_what_shares_one():
    b = live.breadboard("blink")
    assert "Never insist on the lesson's numbers" in b
    assert "resistor's other leg and the LED's long leg (+)" in b  # the column they must share, any column
    assert "never 0 or 1" in b  # the pin can move, but not to the serial pins
    brief = live.brief("blink")
    assert "Always speak English" in brief and "roast" in brief and "the short, everyday way" in brief
