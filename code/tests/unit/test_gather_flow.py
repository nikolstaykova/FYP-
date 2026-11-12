"""The two-step parts check (gather.gather_flow) with given answers: no photos, no model calls."""
from gather import gather_flow as c


def S(name, lesson_part="none", value="", count=1, unsure="", might_replace="", replace_note=""):
    return dict(name=name, lesson_part=lesson_part, value=value, count=count, photos=[1], unsure=unsure,
                might_replace=might_replace, replace_note=replace_note)


KIT = [S("Arduino Uno R3", "arduino-uno"), S("breadboard", "breadboard", "half"), S("red LED", "led", "red"),
       S("resistor", "resistor", "220"), S("jumper wire", "jumper-wire", "", 3)]


def status(out, which="final"):
    return {r["type"]: r["status"] for r in out[which]["parts"]}


def test_nothing_to_settle_skips_the_second_look():
    # answers=None would call Opus if anything were flagged; with the exact kit nothing is, so no call is made
    out = c.check("blink", [], research=False, seen=KIT, answers=None)
    assert out["stages"] == [] and out["changes"] == []
    assert set(status(out).values()) == {"have"}


def test_unsure_and_unidentified_objects_are_flagged():
    from gather import gather
    seen = KIT[:3] + [S("resistor", "resistor", "", unsure="bands too small"),
                      S("small black component with three legs"), S("USB cable"),
                      S("blue microcontroller board", might_replace="arduino-uno")]
    res = gather.check("blink", [], research=False, seen=seen)
    objects, parts = c.flags(res, {r["type"] for r in res["parts"]})
    flagged = {res["seen"][i]["name"] for i, _ in objects}
    assert flagged == {"resistor", "small black component with three legs", "blue microcontroller board"}
    assert "USB cable" not in flagged  # identified, just not needed: no second look
    assert {r["type"] for r, _ in parts} >= {"resistor", "jumper-wire"}


def test_opus_answer_replaces_the_unsure_one():
    seen = KIT[:3] + [S("resistor", "resistor", "", unsure="bands too small"), S("jumper wire", "jumper-wire", "", 3)]
    out = c.check("blink", [], research=False, seen=seen,
                  answers=[{"ref": 3, "name": "resistor", "lesson_part": "resistor", "value": "220"}])
    assert status(out, "first")["resistor"] == "check"
    assert status(out)["resistor"] == "have"
    assert out["changes"] == [{"was": "resistor", "now": "resistor (220)"}]


def test_opus_finds_a_part_the_first_look_missed():
    seen = [x for x in KIT if x["lesson_part"] != "led"]
    out = c.check("blink", [], research=False, seen=seen,
                  answers=[{"ref": "new", "name": "red 5 mm LED", "lesson_part": "led", "value": "red"}])
    assert status(out, "first")["led"] == "missing"
    assert status(out)["led"] == "have"


def test_gone_removes_and_unasked_refs_are_ignored():
    seen = KIT + [S("blue microcontroller board", might_replace="arduino-uno")]
    objects = [(5, "not identified")]
    merged, changes = c.merge(seen, objects, [{"ref": 5, "gone": True}, {"ref": 0, "name": "Arduino Mega 2560"}])
    assert [s["name"] for s in merged] == [s["name"] for s in KIT]  # ref 0 was not asked about: Uno kept
    assert changes == [{"was": "blue microcontroller board", "now": "not there"}]


def test_a_board_opus_names_exactly_gets_the_pin_check():
    seen = KIT[1:] + [S("blue microcontroller board", might_replace="arduino-uno")]
    out = c.check("blink", [], research=False, seen=seen,
                  answers=[{"ref": 4, "name": "Arduino Nano", "lesson_part": "none", "value": "Nano"}])
    assert status(out)["arduino-uno"] == "use instead"


def _first(seen, lesson="blink"):
    from gather import gather
    res = gather.check(lesson, [], research=False, seen=seen)
    objects, parts = c.flags(res, {r["type"] for r in res["parts"]})
    return res, c.asks(res, objects, parts)


def test_learner_is_asked_for_a_closeup_of_the_unsure_resistor_and_for_the_missing_led():
    seen = [KIT[0], KIT[1], S("resistor", "resistor", "", unsure="the bands are too small to read: a close-up"),
            KIT[4]]
    res, qs = _first(seen)
    by_kind = {q["kind"]: q for q in qs}
    assert by_kind["closeup"]["message"].startswith("I can see a resistor, but")
    assert by_kind["find"]["type"] == "led" and "can't see an LED" in by_kind["find"]["message"]
    assert not any(q.get("type") == "resistor" for q in qs)  # the resistor row is covered by its object's question


def test_closeup_answer_settles_it_and_is_not_asked_again():
    from gather import gather
    seen = KIT[:3] + [S("resistor", "resistor", "", unsure="bands too small"), KIT[4]]
    res, qs = _first(seen)
    q = next(q for q in qs if q["kind"] == "closeup")
    seen2 = c.apply_closeup(seen, q, [dict(S("resistor", "resistor", "220"), by="closeup")])
    res2 = gather.check("blink", [], research=False, seen=seen2)
    assert {r["type"]: r["status"] for r in res2["parts"]}["resistor"] == "have"
    objects, parts = c.flags(res2, {r["type"] for r in res2["parts"]}, done=("closeup",))
    assert c.asks(res2, objects, parts) == []


def test_i_dont_have_it_is_not_asked_again():
    seen = [x for x in KIT if x["lesson_part"] != "led"]
    res, qs = _first(seen)
    assert [q["key"] for q in qs] == ["p:led"]
    objects, parts = c.flags(res, {r["type"] for r in res["parts"]})
    assert c.asks(res, objects, parts, dismissed={"p:led"}) == []


def test_the_models_own_question_is_used_and_unneeded_parts_are_not_asked_about():
    seen = KIT[:3] + [dict(S("resistor", "resistor", "", unsure="bands too small"),
                           ask="I can see some resistors, but I can't read their colour bands. Can you take a close-up?"),
                      KIT[4], S("DIP IC", unsure="part number too small"), S("electrolytic capacitor", unsure="value")]
    res, qs = _first(seen)
    assert [q["message"] for q in qs] == ["I can see some resistors, but I can't read their colour bands. "
                                          "Can you take a close-up?"]


def test_other_things_in_a_closeup_are_not_counted_twice():
    seen = KIT[:3] + [S("resistor", "resistor", "", unsure="bands too small"), KIT[4]]
    res, qs = _first(seen)
    q = next(q for q in qs if q["kind"] == "closeup")
    got = [dict(S("breadboard", "breadboard", "half"), by="closeup"), dict(S("resistor", "resistor", "220"), by="closeup")]
    merged = c.apply_closeup(seen, q, got)
    assert [m["lesson_part"] for m in merged].count("breadboard") == 1
    assert any(m["value"] == "220" for m in merged)


def test_a_photo_for_a_missing_part_adds_only_that_part():
    seen = [x for x in KIT if x["lesson_part"] != "led"]
    res, qs = _first(seen)
    merged = c.apply_closeup(seen, qs[0], [S("red LED", "led", "red"), S("USB cable")])
    assert [m["name"] for m in merged][-1] == "red LED" and len(merged) == len(seen) + 1


def test_opus_is_needed_only_when_the_closeup_did_not_settle_it():
    assert c.still_open([])  # nothing about the part in the close-up
    assert c.still_open([S("resistor", "resistor", "", unsure="still blurred")])
    assert not c.still_open([S("resistor", "resistor", "220")])


def test_one_photo_answers_several_questions_without_mixing_them_up():
    seen = [S("blue microcontroller board", might_replace="arduino-uno"), KIT[1],
            S("resistor", "resistor", "", unsure="bands too small"), KIT[4]]
    q_board = {"kind": "closeup", "ref": 0, "key": "o:board"}
    q_res = {"kind": "closeup", "ref": 2, "key": "o:res"}
    q_led = {"kind": "find", "type": "led", "key": "p:led"}
    merged = c.apply_many(seen, [
        (q_board, [S("Arduino Nano", "none", "Nano", might_replace="arduino-uno")]),
        (q_res, [S("resistor", "resistor", "220"), S("resistor", "resistor", "10k")]),  # one object becomes two
        (q_led, [S("red LED", "led", "red")])])
    names = [(m["name"], m["value"]) for m in merged]
    assert names == [("Arduino Nano", "Nano"), ("breadboard", "half"), ("resistor", "220"), ("resistor", "10k"),
                     ("jumper wire", ""), ("red LED", "red")]
