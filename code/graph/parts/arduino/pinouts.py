"""The pins of the Arduino parts whose cards have none.

What it is   for a card with no pins (a 74HC595, an LCD, a stepper motor): the Wokwi element's own pin list when it
             is fixed, else a datasheet pinout drafted by Claude and checked by code (unique names, as many as the
             package has, power and ground among them); written to parts/arduino/pinouts.json and onto the cards.
Used for     letting a lesson say which leg goes where, and its checks follow the signals, for parts CircuitQuest
             listed without pins.
Where        arduino/circuit_lesson.py (build, before a lesson's circuit is read), parts/part_catalogue.py (the
             seed); on its own: python -m graph.parts.arduino.pinouts.
"""
import json
import pathlib
import re
import urllib.request
from typing import List, Literal

from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[4]
PATH = ROOT / "code" / "graph" / "parts" / "arduino" / "pinouts.json"
CARDS = ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json"
WOKWI = "https://unpkg.com/@wokwi/elements@1.9.1/dist/esm/{}-element.js"
NO_PINS = ("consumable", "cable", "tool")  # solder, heat-shrink, a USB cable: nothing to wire by pin


def load():
    return {k: v for k, v in json.loads(PATH.read_text()).items() if not k.startswith("_")} if PATH.exists() else {}


def from_wokwi(wokwi_type):
    """The element's fixed pin list, in order, or None (no element, or pins made in a loop)."""
    try:
        js = urllib.request.urlopen(WOKWI.format(wokwi_type.replace("wokwi-", "")), timeout=20).read().decode()
    except Exception:  # no such element file
        return None
    m = re.search(r"get pinInfo\(\)\s*\{(.*?)\n    \}", js, re.S)
    if not m or re.search(r"for\s*\(|\.map\(|`", m.group(1)):
        return None
    names = list(dict.fromkeys(re.findall(r"name:\s*['\"]([^'\"]+)['\"]", m.group(1))))
    return names if len(names) >= 2 else None


class Pinout(BaseModel):
    pins: List[str] = Field(description="Every pin's name as printed on the part or in its datasheet, each once; a "
                                        "chip's in pin-number order (pin 1 first)")
    kind: Literal["lead", "header-pin", "pin", "screw", "wire-end"] = Field(
        description="How its pins connect: lead (a chip's or component's legs into a breadboard), header-pin (a "
                    "module's male pin header), pin, screw (screw terminals), wire-end (bare wires)")
    package_pins: int = Field(description="How many pins the part has")
    power: List[str] = Field(description="Its supply pins (VCC, VDD, 5V...), names from `pins`; [] if none")
    ground: List[str] = Field(description="Its ground pins, names from `pins`; [] if none")
    basis: str = Field(description="Where the pinout is from: the datasheet or the module's printing")


def check(p):
    """The pinout's problems: []."""
    out = []
    if len(set(p["pins"])) != len(p["pins"]):
        out.append("a pin name is listed twice: each pin once (number duplicates: GND1, GND2)")
    if len(p["pins"]) != p["package_pins"]:
        out.append(f"{len(p['pins'])} pins listed but the part has {p['package_pins']}")
    for k in ("power", "ground"):
        if any(x not in p["pins"] for x in p[k]):
            out.append(f"{k} names a pin that is not in pins")
    if p["kind"] != "wire-end" and not (p["power"] or p["ground"]):
        out.append("no power or ground pin: name them")
    return out


SYSTEM = """You give the standard pinout of an electronics part used in Arduino tutorials (a chip, a module, a
display, a motor), as in its datasheet or as printed on the module. Use the common names (74HC595: Q1..Q7, GND,
Q7S, MR, SHCP, STCP, OE, DS, Q0, VCC in pin order). For a module, the pins of its header as the module is sold
for breadboards (the common Arduino version)."""


def draft(type_id, name, call=None):
    from graph.extract import claude_json
    ask = f"Part: {name} (catalogue id {type_id}). Give its pinout."
    for _ in range(2):
        ans, st = (call or claude_json)(SYSTEM, [{"type": "text", "text": ask}], Pinout, model="sonnet", effort="medium")
        bad = check(ans)
        if not bad:
            return ans, st, []
        ask += "\nYour last answer had these problems, fix them: " + "; ".join(bad)
    return None, st, bad


def build(types=None, call=None, log=print):
    """Pins for every card with none (or `types`); writes pinouts.json and the cards. Returns {type: source}."""
    from graph.parts import part_catalogue
    from graph.filelock import locked
    wok = json.loads((ROOT / "code" / "graph" / "parts" / "arduino" / "wokwi_types.json").read_text())
    seed = part_catalogue.Catalogue(part_catalogue.arduino_seed()).entries
    have = load()
    todo = types or [t for t, e in seed.items() if not e.get("ports") and t not in have
                     and (wok.get(t) or {}).get("subtype") not in NO_PINS]
    out, cost = {}, 0.0
    for t in todo:
        name = (wok.get(t) or {}).get("name") or (seed.get(t) or {}).get("name") or t
        pins = from_wokwi((wok.get(t) or {}).get("wokwi_type") or "")
        if pins:
            have[t] = {"pins": pins, "kind": "pin", "source": f"wokwi element {(wok.get(t) or {}).get('wokwi_type')}"}
        else:
            ans, st, bad = draft(t, name, call)
            cost += st.get("cost_usd") or 0
            if not ans:
                log(f"  {t}: no pinout ({'; '.join(bad)})")
                continue
            have[t] = {"pins": ans["pins"], "kind": ans["kind"], "power": ans["power"], "ground": ans["ground"],
                       "source": f"drafted by Claude, checked by code ({ans['basis']})"}
        out[t] = have[t]["source"]
        log(f"  {t}: {len(have[t]['pins'])} pins ({have[t]['source'][:40]})")
    PATH.write_text(json.dumps({"_doc": "Pins of the parts whose CircuitQuest card lists none (graph/parts/arduino/pinouts.py)",
                                **dict(sorted(have.items()))}, indent=1))
    with locked(CARDS):  # onto the cards that have no ports
        cards = json.loads(CARDS.read_text())
        for t, p in have.items():
            if t in cards and not cards[t].get("ports"):
                cards[t]["ports"] = [{"id": n, "kind": p["kind"], "gender": None, "voltage_rating": None, "aliases": []}
                                     for n in p["pins"]]
        CARDS.write_text(json.dumps(cards, indent=1))
    part_catalogue.build()
    log(f"pinouts: {len(out)} parts, ${round(cost, 4)}")
    return out


if __name__ == "__main__":
    build()
