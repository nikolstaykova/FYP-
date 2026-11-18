"""Make the overlay reference for a board (validator/uno_overlay.py) from the clicked Arduino pin photos.

    python research/recognition/uno_reference.py arduino-duemilanove IMG_2733
(reference photo from data/arduino_pins/board/, the clicks from its labels.json)
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from validator import uno_overlay  # noqa: E402

DIR = ROOT / "data" / "arduino_pins" / "board"

if __name__ == "__main__":
    board_id, ref = sys.argv[1], sys.argv[2]
    labels = json.loads((DIR / "labels.json").read_text())
    clicked = [(str(DIR / f"{n}.jpg"), e["pin"], (e["x"], e["y"])) for n, v in labels.items() if not v.get("skip")
               for e in v["ends"] if e.get("pin")]
    meta = uno_overlay.build(board_id, str(DIR / f"{ref}.jpg"), clicked)
    print(f"{board_id}: fitted from {meta['fitted_from']} photos; AREF {meta['pins']['AREF']}, 0 {meta['pins']['0']}")
