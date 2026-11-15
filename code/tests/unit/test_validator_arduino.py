"""The Arduino step check (validator.arduino): the verdict from what the model read, on Blink's steps.
No model is called: the readings are written here as the model would answer."""
from validator import arduino as A

STEP_RESISTOR, STEP_LED, STEP_SIGNAL_WIRE = 2, 3, 4  # Blink: gather, resistor, LED, signal wire, ground wire
AS_LESSON = {"where": {"10t": "10t", "14t": "14t"}}  # the resistor checked in the lesson's columns


def leg(key, **kw):
    return {"key": key, "sure": True, **kw}


def test_in_the_lessons_places_passes():
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=True, column=14, half="top"), "L2": leg("L2", column=15, half="top")}, AS_LESSON)
    assert res["verdict"] == "pass" and res["columns"] == {}


def test_another_free_column_is_accepted_and_kept():
    """We want column 15; they used 16: fine, and from now on the lesson's 15 is their 16."""
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=True), "L2": leg("L2", column=16, half="top")}, AS_LESSON)
    assert res["verdict"] == "moved"
    assert res["state"]["where"]["15t"] == "16t" and res["columns"] == {"15": "16"}
    # the next step asks about their column: the ground wire must share the LED's short leg, now in 16
    nxt = A.plan("blink", 5)
    assert "column 16 (top half)" in A.prompt(nxt, res["state"])


def test_the_whole_resistor_somewhere_else():
    p = A.plan("blink", STEP_RESISTOR)
    res = A.judge(p, {"L1": leg("L1", column=3, half="top"), "L2": leg("L2", column=7, half="top")}, {})
    assert res["verdict"] == "moved" and res["columns"] == {"10": "3", "14": "7"}
    led = A.plan("blink", STEP_LED)  # the LED's long leg must now go in their 7
    assert "column 7 (top half)" in A.prompt(led, res["state"])


def test_a_leg_not_sharing_its_column_is_wrong():
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=False, column=13, half="top"), "L2": leg("L2", column=15, half="top")}, AS_LESSON)
    assert res["verdict"] == "wrong"
    assert "same column as the 220 ohm resistor's other leg" in A._asks(res)[0]["message"]


def test_a_column_that_is_taken_would_join_two_things():
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=True), "L2": leg("L2", column=10, half="top")}, AS_LESSON)
    assert res["verdict"] == "wrong" and "already has something else" in res["legs"][1]["words"]


def test_an_led_the_wrong_way_round():
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=False, column=15, half="top"), "L2": leg("L2", column=14, half="top")}, AS_LESSON)
    assert res["verdict"] == "wrong" and res["reversed"] == ["led1"]
    assert "wrong way round" in res["legs"][0]["words"]


def test_a_wire_turned_round_is_harmless():
    """The model read the 'one end' in the breadboard and the 'other end' in the pin: a wire has no ends."""
    p = A.plan("blink", STEP_SIGNAL_WIRE)
    res = A.judge(p, {"L1": leg("L1", same=True, column=10, half="top"), "L2": leg("L2", pin="13")}, AS_LESSON)
    assert res["verdict"] == "harmless" and res["turned_round"] == ["wire1"]


def test_pins_that_can_and_cannot_stand_in():
    p = A.plan("blink", STEP_SIGNAL_WIRE)
    ok = A.judge(p, {"L1": leg("L1", pin="~9"), "L2": leg("L2", same=True)}, AS_LESSON)
    assert ok["verdict"] == "moved" and ok["state"]["where"]["uno:13"] == "uno:9"
    bad = A.judge(p, {"L1": leg("L1", pin="0"), "L2": leg("L2", same=True)}, AS_LESSON)
    assert bad["verdict"] == "wrong" and "USB" in bad["legs"][0]["words"]


def test_what_cannot_be_seen_is_asked_about():
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", same=True), "L2": {"key": "L2", "sure": False, "why": "hidden behind the LED"}}, AS_LESSON)
    assert res["verdict"] == "unsure"
    assert A._asks(res)[0]["kind"] == "tell"  # when the photo cannot show it, the learner says where it is


def test_a_steps_own_words_go_into_the_prompt():
    p = dict(A.plan("blink", STEP_LED), note="The LED is small: look closely at which leg is longer.")
    assert "About this step: The LED is small" in A.prompt(p)


def test_one_column_off_is_caught():
    """The LED's long leg in 13 when it must share the resistor's 14: the model counts one column off."""
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", offset=-1, column=13, half="top"), "L2": leg("L2", column=15, half="top")}, AS_LESSON)
    assert res["verdict"] == "wrong" and "column 14" in res["legs"][0]["words"]
    only_count = A.judge(p, {"L1": leg("L1", offset=-1), "L2": leg("L2", column=15, half="top")}, AS_LESSON)
    assert only_count["verdict"] == "wrong" and "1 column off" in only_count["legs"][0]["words"]


def test_a_model_that_contradicts_itself_is_not_trusted():
    """It says 'same column' (offset 0) but reads column 13 where the resistor is in 14: unsure, not a pass."""
    p = A.plan("blink", STEP_LED)
    res = A.judge(p, {"L1": leg("L1", offset=0, column=13, half="top"), "L2": leg("L2", column=15, half="top")}, AS_LESSON)
    assert res["legs"][0]["status"] == "unsure" and res["verdict"] == "unsure"


def test_the_question_does_not_lead_the_model():
    q = A.prompt(A.plan("blink", STEP_LED), AS_LESSON)
    assert "must be in the SAME column" not in q and '"offset"' in q


def test_what_the_learner_says_is_judged_like_a_photo():
    """The photo could not show the LED's short leg; they say "column 18": accepted, and kept for later steps."""
    readings = {"L1": leg("L1", offset=0, column=14, half="top"), "L2": {"key": "L2", "sure": False}}
    res = A.told("blink", STEP_LED, AS_LESSON, readings, {"L2": {"column": 18, "half": "top"}})
    assert res["verdict"] == "moved" and res["state"]["where"]["15t"] == "18t"
    taken = A.told("blink", STEP_LED, AS_LESSON, readings, {"L2": {"column": 10, "half": "top"}})
    assert taken["verdict"] == "wrong"  # column 10 already holds the resistor's other leg
