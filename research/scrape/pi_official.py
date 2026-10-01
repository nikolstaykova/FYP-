"""Official Raspberry Pi electronics tutorials (Raspberry Pi Foundation, github.com/raspberrypilearning).

Each project is markdown steps (en/step_*.md, or en/*.md for short guides) plus images.
The steps are joined into one manual; up to two wiring images (file names mentioning
wiring/circuit/breadboard/led/button/...) are kept. Saved to research/raw/pi/ (git-ignored);
the list goes to research/data/pi_dataset.json. There is no answer key: these are scored on
the spec rules and on the part families the project lists.

Run: .venv-research/bin/python research/scrape/pi_official.py
"""
import json
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "raw" / "pi"
OUT = ROOT / "research" / "data" / "pi_dataset.json"
API = "https://api.github.com/repos/raspberrypilearning/{}"
RAWGH = "https://raw.githubusercontent.com/raspberrypilearning/{}/{}/{}"

REPOS = [
    "python-quick-reaction-game", "push-button-stop-motion", "gpio-music-box", "balloon-pi-tay-popper",
    "laser-tripwire", "camjam-kit-1", "pir-motion-sensors", "ultrasonic-theremin", "physical-computing",
    "rpi-gpio-wiring-a-button", "rpi-gpio-connect-pir", "rpi-python-piezoelectric-buzzer", "rpi-physical-connect-led",
    "build-a-buggy", "rpi-physical-connect-motor-controller", "generic-electronics-connect-ultrasonic-distance-sensor",
    "build-a-robot", "traffic-lights-python", "interactive-traffic-lights-python", "rpi-connect-led",
    "rpi-connect-buzzer", "reaction",
]
WIRING = re.compile(r"(wir|circuit|breadboard|led|button|buzzer|pir|gpio|sensor|motor|resistor|diagram|connect)", re.I)
MEDIA = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif"}


def step_key(path):
    m = re.search(r"step_(\d+)", path)
    return (0, int(m.group(1))) if m else (1, path)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    chosen = []
    for repo in REPOS:
        info = requests.get(API.format(repo), timeout=30).json()
        branch = info.get("default_branch", "master")
        tree = requests.get(API.format(repo) + f"/git/trees/{branch}?recursive=1", timeout=30).json().get("tree", [])
        time.sleep(1)
        md = sorted([t["path"] for t in tree if t["path"].startswith("en/") and t["path"].endswith(".md")
                     and "/resources/" not in t["path"]], key=step_key)
        if not md:
            md = [t["path"] for t in tree if t["path"].lower() in ("readme.md", "worksheet.md")]
        text = "\n\n".join(requests.get(RAWGH.format(repo, branch, p), timeout=30).text for p in md)
        meta = next((t["path"] for t in tree if t["path"] == "en/meta.yml"), None)
        hardware = []
        if meta:
            y = requests.get(RAWGH.format(repo, branch, meta), timeout=30).text
            block = re.search(r"hardware:\s*\n((?:\s+-.*\n?)+)", y)
            if block:
                hardware = [l.strip("- \t") for l in block.group(1).splitlines() if l.strip()]
        if not hardware:
            need = re.search(r"(?:You will need|What you will need|Hardware)[^\n]*\n((?:.*\n){1,20})", text, re.I)
            if need:
                hardware = [l.strip("-*• \t") for l in need.group(1).splitlines() if l.strip().startswith(("-", "*", "•"))]
        hardware = [h for h in hardware if re.search(r"[A-Za-z]{3}", h) and "collapse" not in h.lower()]
        imgs = [t["path"] for t in tree if t["path"].lower().rsplit(".", 1)[-1] in MEDIA and WIRING.search(t["path"].rsplit("/", 1)[-1])]
        saved = []
        for p in imgs[:2]:
            r = requests.get(RAWGH.format(repo, branch, p), timeout=30)
            if r.status_code == 200 and len(r.content) < 3_000_000:
                f = RAW / f"{repo}__{p.rsplit('/', 1)[-1]}"
                f.write_bytes(r.content)
                saved.append({"file": str(f.relative_to(ROOT)), "media": MEDIA[p.rsplit('.', 1)[-1].lower()]})
        if len(text) < 300:
            print("skip", repo, "(no readable steps)")
            continue
        (RAW / f"{repo}.md").write_text(text)
        chosen.append({"id": f"pi-{repo}", "source": "raspberrypi", "url": f"https://github.com/raspberrypilearning/{repo}",
                       "manual_file": str((RAW / f"{repo}.md").relative_to(ROOT)), "images": saved,
                       "hardware": hardware, "cq_lesson": None})
        print(f"{len(chosen):2d} {repo:55s} {len(text):6d} chars  {len(saved)} images  hardware: {hardware[:4]}", flush=True)
    OUT.write_text(json.dumps(chosen, indent=1))
    print("wrote", OUT, len(chosen))


if __name__ == "__main__":
    main()
