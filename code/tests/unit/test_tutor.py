"""The voice tutor's lesson brief, steps and cost (code/tutor/live.py), without calling any model."""
from tutor import live


def test_steps_are_numbered_from_one_with_their_parts_and_booklet_pictures():
    blink = live.steps("blink")
    assert [s["n"] for s in blink["steps"]] == list(range(1, len(blink["steps"]) + 1))
    assert blink["steps"][0]["title"] == "Gather the parts" and blink["steps"][-1]["title"] == "Upload the code"
    crab = live.steps("7268-1-pdf")
    first = next(s for s in crab["steps"] if s["kind"] != "gather")  # a LEGO lesson opens with a gather card
    assert first["title"] == "Step 1" and first["picture"].endswith("step1.png")
    assert any(p["what"] == "Black Plate 4 x 4" for p in first["parts"])
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
    assert {"open_camera", "take_photo", "check_parts", "take_closeup", "use_column"} <= set(arduino)
    assert {"open_camera", "check_parts", "take_closeup"} <= set(lego) and "start_building" in lego
    assert not {"show_parts_list", "use_column"} & set(lego)
    assert "no parts check" in live.brief("7268-1-pdf")


def test_the_tutor_knows_columns_do_not_matter_only_what_shares_one():
    b = live.breadboard("blink")
    assert "Never insist on the lesson's numbers" in b
    assert "resistor's other leg and the LED's long leg (+)" in b  # the column they must share, any column
    assert "never 0 or 1" in b  # the pin can move, but not to the serial pins
    brief = live.brief("blink")
    assert brief.startswith("RESPOND IN ENGLISH") and "roast" in brief and "the short, everyday way" in brief
    assert "call use_column first" in brief


def test_every_lesson_gets_a_tutor_brief():
    # Capacitance Meter and 10 other lessons once failed: their pin data is "13", not "uno:13"
    from graph import lesson_store
    failed = []
    for row in lesson_store.catalogue()["lessons"]:
        try:
            assert "Step 1 (" in live.brief(row["lesson_id"])
        except Exception as e:  # noqa: BLE001
            failed.append((row["lesson_id"], repr(e)[:80]))
    assert failed == []


def test_the_upload_step_carries_its_sketch_and_pip_knows_it_is_on_screen():
    up = [s for s in live.steps("capacitance-meter")["steps"] if s["kind"] == "upload"][0]
    assert up["code"].startswith("/*  RCTiming_capacitance_meter") and "\n\n\n" not in up["code"]
    b = live.brief("capacitance-meter")
    assert "ON THE SCREEN" in b and "Never say the lesson has no code" in b and "RCTiming" in b


def test_pip_asks_the_level_and_paces_itself_by_it():
    new = live.brief("blink")
    assert "remember_level" in new and "beginner's pace" in new
    assert "Their level: BEGINNER" in live.brief("blink", "Nicole", "beginner")
    assert "Their level: ADVANCED" in live.brief("blink", "Nicole", "advanced")
    assert "Never skip ahead" in new and "Never narrate" in new and "Do not agree just to be nice" in new
    assert "remember_level" in [d["name"] for d in live.tools("lego")[0]["functionDeclarations"]]
