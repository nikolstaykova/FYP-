"""Count joining actions and hardware across the scraped Sauder steps.

Reads research/data/sauder.json (from sauder.py) and writes
research/data/sauder_connections.json: verb counts, hardware counts, which
hardware each verb is used with, and example sentences.

Run: .venv-research/bin/python research/scrape/analyze_sauder.py
"""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "research" / "raw" / "sauder" / "sauder.json"
OUT = ROOT / "research" / "data" / "sauder_connections.json"

# Hardware words as they appear in capitals in the booklets -> one family name.
HARDWARE = {
    r"CAM DOWEL": "cam-dowel",
    r"HIDDEN CAM|CAM\b|CAMS\b": "cam-lock",
    r"SLIDE CAM": "slide-cam",
    r"WOOD DOWEL|DOWEL": "dowel",
    r"SCREW": "screw",
    r"NAIL": "nail",
    r"METAL PIN|\bPIN\b|PINS\b": "metal-pin",
    r"EXTENSION SLIDE|EXTENSION RAIL|\bSLIDES?\b|\bRAILS?\b": "drawer-slide",
    r"HINGE": "hinge",
    r"BRACKET": "bracket",
    r"GLIDE": "glide",
    r"HANDLE|KNOB|PULL": "handle",
    r"SAFETY STRAP|TIPPING RESTRAINT|STRAP": "anti-tip-strap",
    r"TRACK": "track",
    r"SHELF SUPPORT|SUPPORT PEG": "shelf-support",
    r"BOLT": "bolt",
    r"NUT\b": "nut",
    r"WASHER": "washer",
    r"APPLIQUE": "applique",
    r"MAGNET|CATCH": "catch",
    r"GLASS": "glass-panel",
    r"FELT|BUMPER|PAD": "bumper",
    r"BACK\b": "back-panel",
}
VERB = re.compile(r"^(?:NOTE:\s*)?(?:Then,?\s*)?([A-Z][a-z]+)")


def families(sentence):
    found = []
    for pattern, fam in HARDWARE.items():
        if re.search(pattern, sentence) and fam not in found:
            found.append(fam)
    # "CAM DOWEL" also matches "CAM" and "DOWEL"; keep the specific one.
    if "cam-dowel" in found:
        found = [f for f in found if f not in ("cam-lock", "dowel")]
    if "slide-cam" in found:
        found = [f for f in found if f not in ("cam-lock", "drawer-slide")]
    return found


def main():
    manuals = json.loads(SRC.read_text())
    verbs, hw, pairs = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    n_sentences = 0
    for m in manuals:
        for step in m["steps"]:
            if step["step"] == 0:
                continue
            for sentence in step["lines"]:
                n_sentences += 1
                v = VERB.match(sentence)
                verb = v.group(1) if v else "?"
                fams = families(sentence)
                verbs[verb] += 1
                for f in fams:
                    hw[f] += 1
                    pairs[verb][f] += 1
                key = (verb, tuple(fams[:1]))
                if len(examples[verb]) < 4 and not sentence.startswith("NOTE"):
                    examples[verb].append(f"[{m['model']}] {sentence}")
    result = {
        "manuals": len(manuals),
        "sentences": n_sentences,
        "verbs": verbs.most_common(),
        "hardware": hw.most_common(),
        "verb_hardware": {v: c.most_common() for v, c in pairs.items()},
        "examples": examples,
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"{len(manuals)} manuals, {n_sentences} sentences")
    print("VERBS:", verbs.most_common(25))
    print("HARDWARE:", hw.most_common())
    for v, _ in verbs.most_common(14):
        print(f"  {v:10s}", pairs[v].most_common(6))


if __name__ == "__main__":
    main()
