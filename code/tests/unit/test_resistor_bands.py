"""gather.resistor: the value from band colours (no photos, no model)."""
from gather import resistor as r


def test_either_way_round():
    for seq in (["red", "violet", "brown", "gold"], ["gold", "brown", "violet", "red"]):
        v = r.value(seq)
        assert v["text"] == "270 Ω" and v["sure"] and v["bands"][0] == "red"


def test_five_bands_and_multipliers():
    assert r.value(["brown", "black", "black", "red", "brown"])["text"] == "10k Ω"
    assert r.value(["yellow", "violet", "gold", "gold"])["text"] == "4.7 Ω"


def test_unlikely_values_are_not_sure():
    assert not r.value(["grey", "black", "violet", "red", "brown"])["sure"]  # 80.7 kΩ: not a standard value
    assert not r.value(["red", "red", "violet", "gold"])["sure"]  # 220 MΩ: not in a kit
    assert r.value(["gold", "gold", "gold"]) is None
