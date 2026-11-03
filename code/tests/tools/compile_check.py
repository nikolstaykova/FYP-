"""Compile every Arduino lesson's sketch for its board, as the Arduino IDE would (arduino-cli), so a lesson's "upload
the code" step is known to work. Libraries a sketch includes are installed from Arduino's library index first.

  ok         compiles for the lesson's board
  library    a library it includes is not in Arduino's index (named in the result)
  file       it includes a file of its own that the tutorial page does not give; files the page shows as their own
             code blocks (a Due's Waveforms.h) are taken from the page and saved with the lesson, a tone sketch's
             pitches.h from Arduino's examples, and arduino_secrets.h is written as a template the learner fills in
  cloud      it needs Arduino Cloud's thingProperties.h, made for each user's own Thing: not on any page
  --fix      a sketch with a real error gets the smallest fix that compiles, by Claude, recorded with the lesson
             (code_original.ino keeps the page's)
  error      the compiler's first error (a real problem in the sketch)
  no board   the lesson's board has no compiler package here
  toolchain  the compiler cannot run on this machine (Arduino's tools are Intel builds: Apple Silicon needs Rosetta)

  python -m graph.compile_check [lesson ids]     -> data/lessons/arduino/compile.json (and stats.json "compile")
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "lessons" / "arduino"

# a board's card type -> the compiler target (FQBN) the Arduino IDE uses for it
FQBN = {
    "arduino-uno": "arduino:avr:uno", "arduino-leonardo": "arduino:avr:leonardo", "arduino-mega": "arduino:avr:mega",
    "arduino-nano": "arduino:avr:nano", "arduino-yun-headers": "arduino:avr:yun",
    "arduino-mkr1000": "arduino:samd:mkr1000",
    "arduino-mkr-zero": "arduino:samd:mkrzero", "arduino-mkr-wifi-1010": "arduino:samd:mkrwifi1010",
    "arduino-mkr-wan-1310": "arduino:samd:mkrwan1310", "arduino-mkr-wan-1300": "arduino:samd:mkrwan1300",
    "arduino-mkr-gsm-1400": "arduino:samd:mkrgsm1400", "arduino-mkr-vidor-4000": "arduino:samd:mkrvidor4000",
    "arduino-nano-33-iot": "arduino:samd:nano_33_iot", "arduino-zero": "arduino:samd:arduino_zero_native",
    "arduino-due-r3": "arduino:sam:arduino_due_x", "arduino-nano-every": "arduino:megaavr:nona4809",
    "arduino-uno-wifi-rev2": "arduino:megaavr:uno2018", "arduino-nano-33-ble": "arduino:mbed_nano:nano33ble",
    "arduino-nano-rp2040-connect": "arduino:mbed_nano:nanorp2040connect",
    "arduino-uno-r4-minima": "arduino:renesas_uno:minima", "arduino-uno-r4-wifi": "arduino:renesas_uno:unor4wifi",
    "arduino-opta": "arduino:mbed_opta:opta", "arduino-nano-matter": "SiliconLabs:silabs:nano_matter",
}
# an #include -> the library to install, where the header's name is not the library's
LIBS = {
    "WiFiNINA.h": "WiFiNINA", "ArduinoBLE.h": "ArduinoBLE", "LoRa.h": "LoRa", "WiFi101.h": "WiFi101",
    "Servo.h": "Servo", "Adafruit_NeoPixel.h": "Adafruit NeoPixel", "AudioFrequencyMeter.h": "AudioFrequencyMeter",
    "MIDIUSB.h": "MIDIUSB", "DHT.h": "DHT sensor library", "Ethernet.h": "Ethernet", "Bridge.h": "Bridge",
    "BridgeClient.h": "Bridge", "BridgeServer.h": "Bridge", "Process.h": "Bridge",
    "ArduinoMotorCarrier.h": "ArduinoMotorCarrier", "Adafruit_Sensor.h": "Adafruit Unified Sensor",
    "Adafruit_BME280.h": "Adafruit BME280 Library", "RTClib.h": "RTClib", "U8x8lib.h": "U8g2",
    "ArduinoSound.h": "ArduinoSound", "ArduinoModbus.h": "ArduinoModbus", "Arduino_MKRIoTCarrier.h":
    "Arduino_MKRIoTCarrier", "Arduino_OplaUI.h": "Arduino_MKRIoTCarrier", "MKRGSM.h": "MKRGSM",
    "RTCZero.h": "RTCZero", "SD.h": "SD", "Arduino_MKRENV.h": "Arduino_MKRENV", "IRremote.h": "IRremote",
    "Keyboard.h": "Keyboard", "Mouse.h": "Mouse", "Arduino_HTS221.h": "Arduino_HTS221",
    "grove_two_rgb_led_matrix.h": "Grove - RGB LED Matrix w/Driver", "Adafruit_GFX.h": "Adafruit GFX Library",
    "Adafruit_SSD1306.h": "Adafruit SSD1306", "VidorPeripherals.h": "VidorPeripherals", "LiquidCrystal.h": "LiquidCrystal", "Stepper.h": "Stepper",
}
# files of a sketch's own folder that Arduino's examples hold (tone sketches)
OWN = {"pitches.h": "https://raw.githubusercontent.com/arduino/arduino-examples/main/examples/02.Digital/toneMelody/pitches.h"}
CLOUD = {"thingProperties.h", "arduino_secrets.h"}  # made by Arduino Cloud for each user: not on any page


def cli(*args, timeout=600):
    r = subprocess.run(["arduino-cli", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def board_of(d):
    import ar_circuit
    g = json.loads((d / "graph.json").read_text())
    kinds = ar_circuit._kinds(g)
    from merge import resolve  # a board id from an earlier run, merged since (arduino-mkr1000-headers)
    types = [resolve(n["type"]) for n in g["nodes"] if kinds.get(n["id"]) == "board"]
    return next((t for t in types if t in FQBN), types[0] if types else None)


_installed = set()


def install(lib):
    if lib in _installed:
        return True
    code, out = cli("lib", "install", lib)
    ok = code == 0 or "already installed" in out.lower()
    if ok:
        _installed.add(lib)
    return ok


def page_files(d, names):
    """Files of the sketch's own folder that the tutorial page shows as code blocks of their own (a Due waveform
    table 'Waveforms.h'): the block that guards or names the file. Saved next to the lesson's code.ino."""
    from graph.arduino import browser
    url = json.loads((d / "lesson.json").read_text())["source"]["url"]
    blocks = browser.github_markdown_code(url) or (browser.render(url).get("code") or [])
    got = {}
    for name in names:
        stem = re.sub(r"\W", "", name.rsplit(".", 1)[0]).lower()
        hit = next((b for b in blocks if "setup" not in b and re.search(r"#(ifndef|define|pragma)", b)
                    and stem in re.sub(r"\W", "", b).lower()), None)
        if hit:
            (d / name).write_text(hit if hit.endswith("\n") else hit + "\n")
            got[name] = "from the tutorial page"
    return got


def secrets_template(code):
    """arduino_secrets.h, which the learner fills in (Wi-Fi name, password ...): one empty entry per SECRET_ name."""
    names = sorted(set(re.findall(r"\bSECRET_\w+", code)))
    return "// Fill in your own details here (this file stays on your computer)\n" + "".join(
        f'#define {n} ""\n' for n in names)


def compile_dir(d, code, board):
    """Compile `code` with the lesson's own extra files. Returns (rc, output)."""
    with tempfile.TemporaryDirectory() as tmp:
        sk = pathlib.Path(tmp) / "sketch"
        sk.mkdir()
        (sk / "sketch.ino").write_text(code)
        for f in d.iterdir():
            if f.suffix in (".h", ".cpp") and f.name != "code.ino":
                (sk / f.name).write_text(f.read_text())
        for h in re.findall(r'#include\s*[<"]([^>"]+)[>"]', code):
            if h in OWN and not (sk / h).exists():
                (sk / h).write_text(urllib.request.urlopen(OWN[h], timeout=30).read().decode())
        return cli("compile", "--fqbn", FQBN[board], str(sk))


def check(d):
    code = (d / "code.ino").read_text()
    board = board_of(d)
    if not code.strip():
        return {"result": "no sketch"}
    if board not in FQBN:
        return {"result": "no board", "board": board}
    includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', code)
    if "arduino_secrets.h" in includes and not (d / "arduino_secrets.h").exists():
        (d / "arduino_secrets.h").write_text(secrets_template(code))  # the learner's own details go here
    local = [h for h in re.findall(r'#include\s*"([^"]+)"', code)
             if h not in CLOUD and h not in OWN and h not in LIBS and not (d / h).exists() and h != "arduino_secrets.h"]
    added = page_files(d, local) if local else {}
    if CLOUD & set(includes) - {"arduino_secrets.h"}:
        return {"result": "cloud", "board": board, "missing": sorted(CLOUD & set(includes) - {"arduino_secrets.h"}),
                "why": "made by Arduino Cloud for each user's own Thing"}
    for h in includes:
        if h in LIBS and not install(LIBS[h]):
            return {"result": "library", "board": board, "missing": [LIBS[h]]}
    rc, out = compile_dir(d, code, board)
    if rc == 0:
        return {"result": "ok", "board": board, "fqbn": FQBN[board], **({"files": added} if added else {})}
    if re.search(r"bad CPU type|fork/exec", out):  # the compiler itself cannot run here (Intel tools, no Rosetta)
        return {"result": "toolchain", "board": board, "error": "the compiler cannot run on this machine (install Rosetta)"}
    first = next((ln.strip() for ln in out.splitlines() if "error" in ln.lower()), out.strip()[:300])
    m = re.search(r"fatal error: ([\w./]+): No such file", out)
    if m:  # a header nobody installed: a library, or a file of the sketch's own
        return {"result": "library" if m.group(1) not in OWN else "file", "board": board, "missing": [m.group(1)],
                "error": first[:300]}
    return {"result": "error", "board": board, "fqbn": FQBN[board], "error": re.sub(r"/[^ :]*/sketch/", "", first)[:300]}


FIX = """You fix an Arduino sketch that does not compile, so a beginner's lesson can be uploaded. Make the SMALLEST
change that fixes the compiler's errors (a typo, a missing declaration or #define, a missing include of a standard
library, a name the library spells differently). Never change what the sketch does, its pins or its comments beyond
the fix. Return the whole fixed sketch and one short line per change."""


def fix(d, result, rounds=2):
    """Claude repairs a sketch that does not compile (the compiler's errors in, the smallest fix out), up to `rounds`
    times; kept only if it then compiles. The changes are recorded with the lesson (code.ino keeps the fixed sketch,
    code_original.ino the page's)."""
    from pydantic import BaseModel
    from typing import List
    from graph.extract import SubscriptionSession

    class Fixed(BaseModel):
        sketch: str
        changes: List[str]
    code = (d / "code.ino").read_text()
    board = result["board"]
    rc, out = compile_dir(d, code, board)
    errors = "\n".join(ln for ln in out.splitlines() if "error" in ln.lower())[:3000]
    s = SubscriptionSession(f"BOARD: {board} ({FQBN[board]})\n\nSKETCH:\n{code}\n\nCOMPILER ERRORS:\n{errors}", "",
                            "lego-v8", model="sonnet", effort="medium", timeout=600, schema=Fixed, system=FIX)
    try:
        ans, st = s.first()
        for n in range(rounds):
            rc, out = compile_dir(d, ans["sketch"], board)
            if rc == 0:
                if not (d / "code_original.ino").exists():
                    (d / "code_original.ino").write_text(code)
                (d / "code.ino").write_text(ans["sketch"])
                return {"result": "ok", "board": board, "fqbn": FQBN[board], "fixed": ans["changes"],
                        "fix_cost_usd": st.get("cost_usd")}
            if n + 1 < rounds:
                errors = "\n".join(ln for ln in out.splitlines() if "error" in ln.lower())[:3000]
                ans, st2 = s.repair(f"It still does not compile:\n{errors}\nReturn the whole fixed sketch.")
                st = {**st, "cost_usd": round(st.get("cost_usd", 0) + st2.get("cost_usd", 0), 4)}
    finally:
        s.close()
    return {**result, "fix_tried": ans.get("changes", []), "fix_cost_usd": st.get("cost_usd")}


def main(argv):
    fixing = "--fix" in argv
    argv = [a for a in argv if a != "--fix"]
    ids = argv or sorted(d.name for d in OUT.iterdir() if (d / "code.ino").exists() and (d / "graph.json").exists())
    path = OUT / "compile.json"
    results = json.loads(path.read_text()) if path.exists() and argv else {}
    for i in ids:
        d = OUT / i
        try:
            r = check(d)
            if fixing and r["result"] == "error":  # the page's own sketch has a bug: the smallest fix that compiles
                r = fix(d, r)
        except Exception as e:  # one lesson never stops the rest
            r = {"result": "check failed", "error": str(e)[:200]}
        results[i] = r
        stats = d / "stats.json"
        if stats.exists():
            st = json.loads(stats.read_text())
            st["compile"] = r
            stats.write_text(json.dumps(st, indent=1))
        print(f"{i}: {r['result']}" + (f" ({', '.join(r.get('missing', []))})" if r.get("missing") else "")
              + (f": {r['error'][:140]}" if r.get("error") else ""), flush=True)
    path.write_text(json.dumps(results, indent=1))
    from collections import Counter
    print(dict(Counter(r["result"] for r in results.values())))


if __name__ == "__main__":
    main(sys.argv[1:])
