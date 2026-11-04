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
