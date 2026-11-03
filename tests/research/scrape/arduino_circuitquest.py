"""Summarise Arduino connections from CircuitQuest's lessons and part library.

CircuitQuest (~/Desktop/CirquitQuest) holds Wokwi diagrams for lessons based on
official Arduino tutorials (docs.arduino.cc) plus a part library with
connection facts. Writes research/data/arduino_connections.json.

Run: .venv-research/bin/python research/scrape/arduino_circuitquest.py
"""
import collections
import glob
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CQ = pathlib.Path.home() / "Desktop" / "CirquitQuest"
OUT = ROOT / "research" / "data" / "arduino_connections.json"
BOARDS = ("arduino", "pi-pico", "esp32", "stm32", "nano", "mega", "leonardo")


def endpoint(pin, parts):
    t = parts.get(pin.split(":")[0], "?")
    if "breadboard" in t:
        return "breadboard-hole"
    if any(b in t for b in BOARDS):
        return "board-pin"
    return "component-pin"


def main():
    pairs, part_types, sources = collections.Counter(), collections.Counter(), set()
    diagrams = sorted(glob.glob(str(CQ / "lessons" / "*" / "diagram.json")))
    for path in diagrams:
        d = json.loads(pathlib.Path(path).read_text())
        parts = {p["id"]: p["type"] for p in d["parts"]}
        part_types.update(parts.values())
        for c in d["connections"]:
            pairs[" ↔ ".join(sorted([endpoint(c[0], parts), endpoint(c[1], parts)]))] += 1
        lesson = pathlib.Path(path).with_name("lesson.json")
        if lesson.exists():
            src = json.loads(lesson.read_text()).get("source", {}).get("url")
            if src:
                sources.add(src)
    # Repeated blocks: several LEDs (each with its own resistor) or buttons in
    # one lesson. Do the copies differ (LED colour, resistor value)?
    repeats = []
    for path in diagrams:
        d = json.loads(pathlib.Path(path).read_text())
        leds = [p for p in d["parts"] if p["type"] == "wokwi-led"]
        if len(leds) < 2:
            continue
        repeats.append({
            "lesson": pathlib.Path(path).parent.name,
            "copies": len(leds),
            "led_colours": sorted({l.get("attrs", {}).get("color", "red") for l in leds}),
            "resistor_values": sorted({p.get("attrs", {}).get("value") for p in d["parts"] if p["type"] == "wokwi-resistor"}),
        })
    cards = [json.loads(pathlib.Path(f).read_text()) for f in glob.glob(str(CQ / "library" / "parts" / "*.json"))]
    fields = collections.Counter(k for c in cards for k in c)
    result = {
        "lessons": len(diagrams),
        "official_sources": sorted(s for s in sources if "arduino.cc" in s),
        "connection_endpoints": pairs.most_common(),
        "part_types": part_types.most_common(),
        "card_fields": {k: fields[k] for k in (
            "pins", "leads", "symmetric_pins", "polarized", "pin_aliases", "legs_placed_together",
            "straddles_center_gap", "pin_domains", "protocol_pins", "protocol_legs", "connector_only")},
        "lead_kinds": collections.Counter(c.get("leads") for c in cards if c.get("leads")).most_common(),
        "repeated_led_blocks": repeats,
        "connector_parts": sorted(c["id"] for c in cards if c["id"] in (
            "jumper-wire", "jumper-wire-mf", "alligator-clip-wire", "solder", "heat-shrink", "usb-cable", "breadboard")),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in result.items() if k not in ("part_types", "official_sources")}, indent=1, ensure_ascii=False))
    print(len(result["official_sources"]), "lessons based on docs.arduino.cc")


if __name__ == "__main__":
    main()
