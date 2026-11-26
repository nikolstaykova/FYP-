import json

from graph.parts.arduino import board_geometry as G
from validator import board_layout as L


def test_every_reference_becomes_a_database_row_with_its_rows_and_layout_numbers():
    refs = G.on_disk()
    assert "arduino-duemilanove" in refs
    r = G.row("arduino-duemilanove", *refs["arduino-duemilanove"])
    assert r["key"] == "arduino-duemilanove" and r["props"]["layouts"] == ["duemilanove", "power-analog-6"]
    assert json.loads(r["props"]["rows"])[0]["pins"]["AREF"]  # where AREF's opening is on the reference photo
    assert r["props"]["form"] == "uno" and json.loads(r["props"]["rows_mils"])["duemilanove"]["0"] == [2600, 2000]


def test_uno_shaped_boards_without_a_photo_get_their_layout_as_numbers_only():
    only = {r["key"]: r["props"] for r in G.layout_only()}
    assert "arduino-zero" in only and only["arduino-zero"]["kept"] == "none"
    assert only["arduino-zero"]["layouts"] == ["uno-r3", "power-analog-8"]
    assert "arduino-duemilanove" not in only  # it has a photo


def test_the_shield_standard_spacing_and_gaps():
    m = L.mils("arduino-uno")
    d = m["uno-r3"]
    assert d["8"][0] - d["9"][0] == 100 and d["7"][0] - d["8"][0] == 160  # 0.1" apart, 0.16" between 8 and 7
    p = m["power-analog-8"]
    assert p["A0"][0] - p["VIN"][0] == 200  # 0.2" between VIN and A0
