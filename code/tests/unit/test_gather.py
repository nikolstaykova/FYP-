"""The parts check (checker.gather) from given sightings: no photos, no Claude calls."""
from checker import gather as g


def S(name, lesson_part, value="", count=1, unsure="", might_replace="", replace_note=""):
    return dict(name=name, lesson_part=lesson_part, value=value, count=count, photos=[1], unsure=unsure,
                might_replace=might_replace, replace_note=replace_note)


def status(seen, lesson="blink"):
    res = g.check(lesson, [], research=False, seen=seen)
    return {r["type"]: r["status"] for r in res["parts"]}, res


def test_exact_kit_has_everything():
    st, _ = status([S("Arduino Uno R3", "arduino-uno"), S("breadboard", "breadboard", "half"),
                    S("red LED", "led", "red"), S("resistor", "resistor", "220"), S("jumper wire", "jumper-wire", "", 3)])
    assert set(st.values()) == {"have"}


def test_mega_stands_in_with_same_pins():
    st, res = status([S("Arduino Mega 2560", "none", "Mega 2560")])
    assert st["arduino-uno"] == "use instead"
    use = res["parts"][0]["use_instead"][0]
    assert use["ok"] is True and use["pin_moves"] == {}


def test_esp32_renames_pin_and_uses_its_voltage_for_the_resistor():
    st, res = status([S("ESP32 DevKit V1", "none", "ESP32-WROOM-32"), S("resistor", "resistor", "150"),
                      S("resistor", "resistor", "470")])
    board = next(r for r in res["parts"] if r["type"] == "arduino-uno")["use_instead"][0]
    assert board["pin_moves"] == {"13": "D13"}
    r = next(r for r in res["parts"] if r["type"] == "resistor")
    assert r["have"][0]["value"] == "150" and "65-260" in r["have"][0]["why"]  # 3.3 V range, not 5 V


def test_resistor_out_of_range_is_refused_unless_unsure():
    st, _ = status([S("resistor", "resistor", "1k")])
    assert st["resistor"] == "missing"
    st, _ = status([S("resistor", "resistor", "possibly 1k")])
    assert st["resistor"] == "check"


def test_unreadable_values_ask_for_a_closer_photo():
    st, _ = status([S("breadboard", "breadboard", ""), S("resistor", "resistor", "", unsure="bands too small")])
    assert st["breadboard"] == "check" and st["resistor"] == "check"


def test_chip_is_not_a_board():
    st, res = status([S("28-pin DIP chip (ATmega328P)", "none", "", might_replace="arduino-uno")])
    assert st["arduino-uno"] == "missing"


def test_unknown_clone_is_offered_to_check():
    st, _ = status([S("Seeeduino", "none", "", might_replace="arduino-uno", replace_note="Uno-compatible clone")])
    assert st["arduino-uno"] == "check"


def test_value_alone_does_not_match_a_part():
    # "white" alone once matched the catalogue's white LED
    _, res = status([S("fader knob cap", "none", "white")])
    assert all(o["type"] != "led" for o in res["seen"])


def test_hedged_board_names_still_match():
    # "clone", "-compatible", "(mini-USB)" once made the catalogue search miss the Nano
    for name in ("Arduino Nano clone (mini-USB)", "Arduino Nano-compatible board (blue PCB)",
                 "Arduino Nano-style board (blue, ATmega328-type)"):
        _, res = status([S(name, "none")])
        assert res["seen"][0]["type"] == "arduino-nano", name


def test_board_known_only_to_the_wider_store_is_offered_to_check():
    # "Seeeduino" matched seeeduino-lotus, a store part with no catalogue card, and was once refused as "not a board"
    st, res = status([S("Seeeduino microcontroller board", "none", "Seeeduino", might_replace="arduino-uno")])
    assert st["arduino-uno"] == "check", res["parts"][0]["use_instead"]
