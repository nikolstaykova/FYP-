"""ElectroCom61 classes mapped to our parts catalogue (code/graph/parts/parts.json).

Only parts our Arduino lessons use are scored ("lesson classes"); the other ElectroCom61 classes stay in the
training data but are not part of the gather step. Several ElectroCom61 classes can map to one of our parts
(both potentiometer kinds -> potentiometer). PROMPTS are the words open-vocabulary models and Claude are given.
"""
import json
import re

NAMES = ['1-5-Volt-Battery', '3-3-Volt-Battery', '7-Segment-Display', '9-Volt-Battery', 'Arduino-Mega',
         'Arduino-Nano', 'Arduino-Uno', 'BJT-Transistor', 'Bluetooth-Module', 'Breadboard', 'Bridge-Rectifier',
         'Buck-Converter', 'Buzzer', 'Capacitor-10mf', 'Capacitor-470mf', 'DC-Motor', 'Diode', 'ESP32', 'ESP32-CAM',
         'FT-232-USB-Serial-Module', 'Film-Capacitor', 'Fuse', 'Fuse-Base', 'GSM-Module', 'Gas-Sensor', 'Heat-Sink',
         'High-Voltage-Ceramic-Capacitor', 'Humidity-Sensor', 'IC-Base-14-Pin', 'IC-Base-28-Pin', 'IC-Chip', 'IGBT',
         'IR-Sensor', 'Inductor', 'Keypad', 'LCD-Display', 'LDR-Sensor', 'LED-Light', 'Low-Voltage-Ceramic-Capacitor',
         'MLC-Capacitor', 'MOSFET', 'Motion-Sensor', 'Motor-Driver', 'NTC-Thermistor', 'OLED-Display', 'Pin-Header',
         'Push-Switch', 'RFID-Scanner', 'Raindrops-Module', 'Relay-Module', 'Resistor', 'Rocker-Switch',
         'Servo-Motor', 'Soil-Moisture-Sensor', 'Sonar-Sensor', 'TCRT5000', 'Tact-Switch', 'Taper-Potentiometer',
         'Trimmer-Potentiometer', 'Water-Sensor', 'Zener-Diode']

# ElectroCom61 class -> our part id (only parts used in our Arduino lessons)
TO_PART = {
    'Arduino-Uno': 'arduino-uno',
    'Arduino-Mega': 'arduino-mega',
    'Arduino-Nano': 'arduino-nano',
    'Breadboard': 'breadboard',
    'Resistor': 'resistor',
    'LED-Light': 'led',
    'Push-Switch': 'pushbutton',
    'Tact-Switch': 'pushbutton',
    'Taper-Potentiometer': 'potentiometer',
    'Trimmer-Potentiometer': 'potentiometer',
    'Capacitor-10mf': 'capacitor',
    'Capacitor-470mf': 'capacitor',
    'Low-Voltage-Ceramic-Capacitor': 'capacitor',
    'High-Voltage-Ceramic-Capacitor': 'capacitor',
    'Film-Capacitor': 'capacitor',
    'MLC-Capacitor': 'capacitor',
    'LDR-Sensor': 'photoresistor',
    'DC-Motor': 'dc-motor',
    'Buzzer': 'buzzer',
    'Servo-Motor': 'servo',
    'Diode': 'diode',
    'MOSFET': 'mosfet-n',
    'Sonar-Sensor': 'ping-sensor',
}

PARTS = sorted(set(TO_PART.values()))

# unknown kinds the trained detector never sees labelled (their boxes are removed from its training labels), to
# test whether it finds kinds it was never taught. A spread of shapes: modules, boards, small parts, big parts.
HELD_OUT = ['Relay-Module', 'ESP32-CAM', 'Keypad', 'Gas-Sensor', 'Inductor', 'IGBT', 'Rocker-Switch',
            'Heat-Sink', 'Fuse', '7-Segment-Display']

# what an open-vocabulary detector or Claude is asked to find, per part
PROMPTS = {
    'arduino-uno': 'Arduino Uno board',
    'arduino-mega': 'Arduino Mega board',
    'arduino-nano': 'Arduino Nano board',
    'breadboard': 'solderless breadboard',
    'resistor': 'resistor',
    'led': 'LED',
    'pushbutton': 'push button switch',
    'potentiometer': 'potentiometer',
    'capacitor': 'capacitor',
    'photoresistor': 'photoresistor (LDR)',
    'dc-motor': 'DC motor',
    'buzzer': 'buzzer',
    'servo': 'servo motor',
    'diode': 'diode',
    'mosfet-n': 'MOSFET transistor',
    'ping-sensor': 'ultrasonic distance sensor',
}


# the instruction every VLM gets (Claude and the local ones), so they are compared on the same words.
# Open world: list EVERY object, name it in plain words, and give a catalogue kind only when it is one.
ASK = f"""You find the objects on a table in a photo, for a learner gathering parts for an electronics lesson.
List EVERY object you can see (electronic parts, modules, boards, tools, anything), each as its own entry
(three resistors = three entries), with:
- name: what it is, as specifically as you can tell (e.g. "USB cable", "multimeter", "Raspberry Pi
  board", "soldering iron"); never leave it out because it is unusual
- part: one of these catalogue kinds if, and only if, it is that kind; otherwise "unknown":
{chr(10).join(f'    {p}: {PROMPTS[p]}' for p in PARTS)}
- box: x1, y1, x2, y2 as thousandths of the photo's width and height (0 = left/top, 1000 = right/bottom).
A module that carries one of these parts on a board (e.g. a sensor module) is "unknown" unless it is listed above.
Do not force an object into a catalogue kind: "unknown" with a good name is right for anything not listed."""

# words open-vocabulary detectors get for objects outside the catalogue; a box with one of these is "unknown"
GENERIC = ['electronic component', 'electronic module', 'circuit board']


JSON_ASK = ASK + ('\nAnswer ONLY with JSON: [{"name": "<what it is>", "part": "<kind or unknown>", '
                  '"box": [x1, y1, x2, y2]}, ...]; [] when none.')


def parse_json_list(text):
    m = re.search(r'\[.*\]', text, re.S)
    if not m:
        return []
    try:
        items = json.loads(m[0])
    except ValueError:
        # cut a truncated answer back to its last whole object
        cut = m[0][:m[0].rfind('}') + 1] + ']'
        try:
            items = json.loads(cut)
        except ValueError:
            return []
    out = []
    for o in items if isinstance(items, list) else []:
        if not isinstance(o, dict):
            continue
        part, box = o.get('part') or o.get('label'), o.get('box') or o.get('bbox_2d')
        part = part if part in PARTS else 'unknown'
        if isinstance(box, list) and len(box) >= 4:
            try:
                out.append({'part': part, 'name': str(o.get('name') or o.get('label') or ''), 'conf': 1.0,
                            'box': [min(max(float(v) / 1000, 0), 1) for v in box[:4]]})
            except (TypeError, ValueError):
                pass
    return out


def name_of(class_id: int):
    """ElectroCom61's own name, in plain words ('Relay-Module' -> 'relay module')."""
    return NAMES[class_id].replace('-', ' ').lower()


def part_of(class_id: int):
    """Our part id for an ElectroCom61 class id, or None when the class is not a lesson part."""
    return TO_PART.get(NAMES[class_id])
