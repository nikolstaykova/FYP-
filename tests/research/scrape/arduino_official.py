"""Build the Arduino test set: 100 official tutorials from Arduino's docs repository.

1. Every CircuitQuest lesson whose source is an official docs.arduino.cc built-in
   example (these have a verified circuit, used as the answer key).
2. Topped up with other official tutorials from github.com/arduino/docs-content that
   describe a circuit (a Hardware list with real components, and a Circuit / Schematic / Wiring section).
   These have no answer key; they are scored on the spec rules and on the parts the
   tutorial lists.

Writes research/data/arduino_dataset.json.

Run: .venv-research/bin/python research/scrape/arduino_official.py [--target 100]
"""
import argparse
import json
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
CQ = pathlib.Path.home() / "Desktop" / "CirquitQuest"
OUT = ROOT / "research" / "data" / "arduino_dataset.json"
RAW = "https://raw.githubusercontent.com/arduino/docs-content/main/"
TREE = "https://api.github.com/repos/arduino/docs-content/git/trees/main?recursive=1"
COMPONENTS = re.compile(r"\b(LED|resistor|potentiometer|push ?button|pushbutton|servo|piezo|buzzer|photoresistor|"
                        r"thermistor|sensor|transistor|relay|motor|LCD|switch|capacitor|diode)\b", re.I)


def hardware_list(md):
    m = re.search(r"#+\s*(?:Hardware|Components)[^\n]*\n(.*?)(?=\n#+\s)", md, re.S | re.I)
    if not m:
        return []
    return [re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", l.strip("-*• \t")).strip()
            for l in m.group(1).splitlines() if l.strip().startswith(("-", "*", "•"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=100)
    cfg = ap.parse_args()
    tree = [x["path"] for x in requests.get(TREE, timeout=60).json()["tree"] if x["path"].endswith(".md")]

    chosen = []
    for lesson in sorted(p.name for p in (CQ / "lessons").iterdir() if (p / "lesson.json").exists()):
        url = json.loads((CQ / "lessons" / lesson / "lesson.json").read_text()).get("source", {}).get("url") or ""
        m = re.search(r"built-in-examples/[^/]+/([^/]+)/?$", url)
        if not m:
            continue
        name = m.group(1).lower()
        path = next((p for p in tree if p.startswith("content/built-in-examples/") and p.lower().endswith(f"/{name}/{name}.md")), None)
        if path:
            chosen.append({"id": lesson, "path": path, "url": url, "cq_lesson": lesson})
    print(len(chosen), "CircuitQuest lessons with an official tutorial")

    taken = {c["path"] for c in chosen}
    pool = [p for p in tree if p not in taken and (p.startswith("content/built-in-examples/") or "/tutorials/" in p)]
    pool.sort(key=lambda p: (not p.startswith("content/built-in-examples/"), "uno" not in p and "nano" not in p, p))
    for path in pool:
        if len(chosen) >= cfg.target:
            break
        try:
            md = requests.get(RAW + path, timeout=30).text
        except requests.RequestException:
            continue  # skip a slow file rather than stop the whole collection
        time.sleep(0.1)
        hw = hardware_list(md)
        has_circuit = re.search(r"#+\s*(Circuit|Schematic|Wiring|Connections?|Setting up the circuit)", md, re.I)
        if not hw or not has_circuit or len(COMPONENTS.findall(" ".join(hw))) < 1:
            continue
        parts = path.split("/")
        board = parts[parts.index("boards") + 1] if "boards" in parts else ""
        slug = re.sub(r"[^a-z0-9]+", "-", f"{board}-{parts[-2]}".lower()).strip("-")
        if any(c["id"] == f"docs-{slug}" for c in chosen):
            slug += f"-{len(chosen)}"
        chosen.append({"id": f"docs-{slug}", "path": path, "url": "https://github.com/arduino/docs-content/blob/main/" + path,
                       "cq_lesson": None, "hardware": hw})
        print(len(chosen), path, hw[:4], flush=True)
    OUT.write_text(json.dumps(chosen, indent=1))
    print("wrote", OUT, len(chosen))


if __name__ == "__main__":
    main()
