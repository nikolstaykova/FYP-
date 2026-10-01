"""Run the graph-building experiment.

For each case: fetch the official manual, ask Claude for the graph, add any
new part types to the catalogue (store on demand), expand repeats, check the
spec rules, compute the logical view, and score it against ground truth.
Everything is written to experiments/graphgen/<run>/.

  .venv-research/bin/python -m graphgen.run --domain arduino --catalogue seeded
  .venv-research/bin/python -m graphgen.run --domain lego --catalogue empty
  .venv-research/bin/python -m graphgen.run --replay experiments/graphgen/<run>   # re-score, no API calls

Catalogue modes: `seeded` gives Claude the verified/imported catalogue;
`empty` starts with nothing, so every part type is created on first use and
later cases reuse what earlier cases created.
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
import time
import urllib.request

from . import catalogue as cat
from . import expand, logical, score, truth, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = "https://raw.githubusercontent.com/arduino/docs-content/main/content/built-in-examples/"

# (CircuitQuest lesson, official tutorial path, CircuitQuest parts the tutorial does not have)
ARDUINO_CASES = [
    ("blink", "01.basics/Blink/Blink.md", ()),
    ("fade", "01.basics/Fade/Fade.md", ()),
    ("analog-read-serial", "01.basics/AnalogReadSerial/AnalogReadSerial.md", ()),
    ("digital-read-serial", "01.basics/DigitalReadSerial/DigitalReadSerial.md", ()),
    ("button", "02.digital/Button/Button.md", ("led1", "r2")),
    ("if-statement", "05.control-structures/ifStatementConditional/ifStatementConditional.md", ()),
    ("for-loop", "05.control-structures/ForLoopIteration/ForLoopIteration.md", ()),
    ("arrays", "05.control-structures/Arrays/Arrays.md", ()),
]
LEGO_CASES = ["6524-1", "6365-1"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def arduino_manual(path, with_images=True):
    md = _get(DOCS + path).decode("utf-8")
    md = re.sub(r"^---.*?---\s*", "", md, flags=re.S)  # front matter
    images = []
    if with_images:
        section = md.split("### Code")[0]
        for name in re.findall(r"!\[[^\]]*\]\((assets/[^)]+\.png)\)", section)[:2]:
            images.append(_get(DOCS + path.rsplit("/", 1)[0] + "/" + name))
    return md, images


def lego_inputs():
    sys.path.insert(0, str(ROOT / "research" / "scrape"))
    import lego_ldraw  # LDraw library index, built from the downloaded parts library
    return lego_ldraw, lego_ldraw.library_index()


def lego_manual(t):
    lines = ["id | part type | description | colour | position x,y,z | rotation rows"]
    for n in t["nodes"]:
        num = n["part"][:-4] if n["part"].endswith(".dat") else n["part"]
        rot = " / ".join(",".join(f"{v:g}" for v in row) for row in n["rot"])
        lines.append(f"{n['id']} | lego-{num} | {n['desc']} | {n['colour']} | {','.join(f'{v:g}' for v in n['pos'])} | {rot}")
    return "\n".join(lines)


def run_case(name, domain, manual, images, catalogue, prompt_types, cfg, out, replay, truth_data, drop=()):
    from .extract import extract

    case_dir = out / name
    case_dir.mkdir(parents=True, exist_ok=True)
    raw_path = case_dir / "response.json"
    before = set(catalogue.entries)
    if replay and (replay / name / "response.json").exists():
        saved = json.loads((replay / name / "response.json").read_text())
        graph, stats = saved["graph"], saved["stats"]
    else:
        text = catalogue.prompt_text(prompt_types) if prompt_types else ""
        graph, stats = extract(manual, text, domain, images=images, model=cfg.model, effort=cfg.effort)
    raw_path.write_text(json.dumps({"graph": graph, "stats": stats}, indent=1))

    t0 = time.monotonic()
    new_drafts = [d for d in graph["new_part_types"] if d["type"] not in before]
    added = catalogue.add_drafts(graph["new_part_types"])
    flat = expand.expand(graph)
    problems = validate.validate(flat, catalogue)
    result = {"case": name, "domain": domain, "catalogue_mode": cfg.catalogue, "stats": stats,
              "parts": len(flat["nodes"]), "edges": len(flat["edges"]),
              "repeats": [{"group": r["group"], "times": r["times"], "overrides": len(r["overrides"])} for r in graph["repeats"]],
              "new_types_declared": len(graph["new_part_types"]), "new_types_added": added,
              "problems": [list(p) for p in problems], "notes": graph["notes"]}
    if domain == "arduino":
        result["score"] = score.score_arduino(flat, logical.nets(flat, catalogue), truth_data, drop)
        result["drafts"] = score.score_drafts(new_drafts, cat.arduino_seed())
    else:
        result["score"] = score.score_lego(flat, truth_data)
        result["drafts"] = score.score_lego_drafts(
            new_drafts, lambda t: cat.brick_dims(truth_data["desc_by_type"].get(t, "")))
    result["postprocess_ms"] = round((time.monotonic() - t0) * 1000, 1)
    (case_dir / "graph.json").write_text(json.dumps(flat, indent=1))
    (case_dir / "result.json").write_text(json.dumps(result, indent=1))
    return result


def summary_table(results):
    rows = ["| Case | Mode | Time (s) | Tokens in / out | Cost ($) | Parts / edges | New types | Rule problems | Score |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in results:
        s, sc = r["stats"], r["score"]
        if r["domain"] == "arduino":
            q = f"nets {sc['nets_matched']}/{sc['nets_expected']} (P {sc['net_precision']}, R {sc['net_recall']}), inventory {'✅' if sc['inventory_correct'] else '❌'}"
        else:
            q = f"contacts {sc['contacts_correct']}/{sc['contacts_expected']} (P {sc['contact_precision']}, R {sc['contact_recall']})"
        rows.append(f"| {r['case']} | {r['catalogue_mode']} | {s['seconds']} | {s['input_tokens']} / {s['output_tokens']} | "
                    f"{s['cost_usd']} | {r['parts']} / {r['edges']} | {len(r['new_types_added'])} | {len(r['problems'])} | {q} |")
    return "\n".join(rows)


def load_env():
    """Read ANTHROPIC_API_KEY from a git-ignored .env file in the repo root, if present."""
    import os
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["arduino", "lego"], required=True)
    ap.add_argument("--catalogue", choices=["seeded", "empty"], default="seeded")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--cases", nargs="*", help="Subset of case names")
    ap.add_argument("--no-images", action="store_true", help="Arduino: text only")
    ap.add_argument("--replay", type=pathlib.Path, help="Re-score saved responses (no API calls)")
    cfg = ap.parse_args()

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "experiments" / "graphgen" / f"{stamp}-{cfg.domain}-{cfg.catalogue}-{cfg.model}-{cfg.effort}"
    out.mkdir(parents=True, exist_ok=True)
    results = []

    if cfg.domain == "arduino":
        catalogue = cat.Catalogue(cat.arduino_seed() if cfg.catalogue == "seeded" else {})
        for lesson, path, drop in ARDUINO_CASES:
            if cfg.cases and lesson not in cfg.cases:
                continue
            manual, images = arduino_manual(path, not cfg.no_images)
            prompt_types = None if cfg.catalogue == "seeded" else list(catalogue.entries)
            r = run_case(lesson, "arduino", manual, images, catalogue, prompt_types, cfg, out, cfg.replay,
                         truth.arduino_truth(lesson), drop)
            results.append(r)
            print(f"{lesson:22s} {r['stats']['seconds']:6.1f}s  nets {r['score']['nets_matched']}/{r['score']['nets_expected']}"
                  f"  new types {len(r['new_types_added'])}  problems {len(r['problems'])}", flush=True)
    else:
        lego_ldraw, index = lego_inputs()
        catalogue = cat.Catalogue({})
        for setnum in LEGO_CASES:
            if cfg.cases and setnum not in cfg.cases:
                continue
            mpd = (ROOT / "research" / "raw" / "lego" / f"{setnum}.mpd").read_text(errors="replace")
            t = truth.lego_truth(mpd, index, lego_ldraw.describe)
            t["desc_by_type"] = {f"lego-{n['part'][:-4]}": n["desc"] for n in t["nodes"]}
            prompt_types = None
            if cfg.catalogue == "seeded":  # import on demand: only the parts this model uses
                for n in t["nodes"]:
                    e = cat.lego_entry(n["part"], n["desc"])
                    catalogue.entries.setdefault(e["type"], e)
                prompt_types = sorted({f"lego-{n['part'][:-4]}" for n in t["nodes"]})
            elif catalogue.entries:
                prompt_types = list(catalogue.entries)
            r = run_case(setnum, "lego", lego_manual(t), [], catalogue, prompt_types, cfg, out, cfg.replay, t)
            results.append(r)
            print(f"{setnum:10s} {r['stats']['seconds']:6.1f}s  contacts {r['score']['contacts_correct']}/{r['score']['contacts_expected']}"
                  f" (P {r['score']['contact_precision']})  new types {len(r['new_types_added'])}  problems {len(r['problems'])}", flush=True)

    (out / "catalogue_after.json").write_text(json.dumps(catalogue.to_json(), indent=1))
    (out / "summary.md").write_text(f"# {out.name}\n\n" + summary_table(results) + "\n")
    print("\n" + summary_table(results))
    print("\nwritten to", out)


if __name__ == "__main__":
    main()
