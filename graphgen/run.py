"""Run the graph-building experiment on the LEGO and Arduino test sets.

For each manual: send it to Claude with the spec and catalogue, add any new part
types to the catalogue (store on demand), expand repeats, check the spec rules,
compute the logical view, score it, and time it. Results go to
experiments/graphgen/<run>/ (one folder per manual, results.jsonl, REPORT.md).

  .venv-research/bin/python -m graphgen.run --domain arduino --limit 10
  .venv-research/bin/python -m graphgen.run --domain lego --limit 10 --workers 4
  .venv-research/bin/python -m graphgen.run --domain lego --replay experiments/graphgen/<run>   # re-score only

Test sets (built by research/scrape/):
  research/data/lego_dataset.json     official lego.com PDFs + LDraw + Rebrickable answer keys
  research/data/arduino_dataset.json  official Arduino tutorials (+ CircuitQuest answer keys where they exist)

Catalogue: Arduino starts from the verified CircuitQuest catalogue (`--catalogue empty` to start
from nothing); LEGO starts empty, so every piece type is created the first time a manual uses it
and later manuals reuse it. Manuals run in waves of `--workers`; the catalogue grows between waves.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import re
import sys
import time
import traceback
import urllib.request

from . import catalogue as cat
from . import expand, logical, score, truth, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DOCS = "https://raw.githubusercontent.com/arduino/docs-content/main/"
MEDIA = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
# CircuitQuest lessons with parts the official tutorial does not have.
DROP = {"button": ("led1", "r2")}


def load_env():
    """Read ANTHROPIC_API_KEY from a git-ignored .env file in the repo root, if present."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def arduino_manual(path, with_images=True):
    md = _get(RAW_DOCS + path).decode("utf-8")
    md = re.sub(r"^---.*?---\s*", "", md, flags=re.S)
    images = []
    if with_images:
        section = re.split(r"#+\s*Code", md)[0]
        for name in re.findall(r"!\[[^\]]*\]\(([^)\s]+\.(?:png|jpe?g|gif|webp))\)", section, re.I)[:2]:
            try:
                images.append((_get(RAW_DOCS + path.rsplit("/", 1)[0] + "/" + name), MEDIA[name.rsplit(".", 1)[1].lower()]))
            except OSError:
                pass
    return md, images


def process(case, graph, stats, catalogue, out):
    """Everything after the model call: catalogue, expansion, rules, scoring."""
    t0 = time.monotonic()
    before = set(catalogue.entries)
    new_drafts = [d for d in graph["new_part_types"] if d["type"] not in before]
    added = catalogue.add_drafts(graph["new_part_types"])
    flat = expand.expand(graph)
    problems = validate.validate(flat, catalogue)
    r = {"case": case["id"], "domain": case["domain"], "stats": stats, "parts": len(flat["nodes"]),
         "edges": len(flat["edges"]), "repeats": [{"group": x["group"], "times": x["times"], "overrides": len(x["overrides"])}
                                                  for x in graph["repeats"]],
         "new_types_declared": len(graph["new_part_types"]), "new_types_added": len(added),
         "problems": [list(p) for p in problems], "notes": graph["notes"]}
    if case["domain"] == "arduino":
        if case.get("cq_lesson"):
            r["score"] = score.score_arduino(flat, logical.nets(flat, catalogue), truth.arduino_truth(case["cq_lesson"]),
                                             DROP.get(case["cq_lesson"], ()))
        else:
            r["score"] = score.score_hardware(flat, case.get("hardware", []))
        r["drafts"] = score.score_drafts(new_drafts, cat.arduino_seed())
    else:
        r["score"] = score.score_lego_pdf(flat, case["truth"], case["elements"], case["part_nums"])
    r["postprocess_ms"] = round((time.monotonic() - t0) * 1000, 1)
    d = out / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.json").write_text(json.dumps(flat, indent=1))
    (d / "result.json").write_text(json.dumps(r, indent=1))
    return r


def call(case, catalogue_text, cfg, out):
    from .extract import extract as api_extract
    from .extract import extract_claude_code

    def extract(*args, model, effort, max_tokens=None, **kw):
        if cfg.route == "subscription":
            return extract_claude_code(*args, model=model, effort=effort, **kw)
        return api_extract(*args, model=model, effort=effort, **({"max_tokens": max_tokens} if max_tokens else {}), **kw)

    d = out / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    if cfg.replay and (cfg.replay / case["id"] / "response.json").exists():
        saved = json.loads((cfg.replay / case["id"] / "response.json").read_text())
        graph, stats = saved["graph"], saved["stats"]
    elif case["domain"] == "arduino" and case.get("manual_file"):  # Raspberry Pi projects, saved locally
        manual = (ROOT / case["manual_file"]).read_text()
        images = [] if cfg.no_images else [((ROOT / i["file"]).read_bytes(), i["media"]) for i in case["images"]]
        graph, stats = extract(manual, catalogue_text, "arduino", images=images, model=cfg.model, effort=cfg.effort)
    elif case["domain"] == "arduino":
        manual, images = arduino_manual(case["path"], not cfg.no_images)
        graph, stats = extract(manual, catalogue_text, "arduino", images=images, model=cfg.model, effort=cfg.effort)
    else:
        pdf = (ROOT / "research" / "raw" / "lego_pdf" / f"{case['id']}.pdf").read_bytes()
        graph, stats = extract(f"LEGO set {case['id']}: {case['name']} (official instructions attached).", catalogue_text,
                               "lego-pdf", pdf=pdf, model=cfg.model, effort=cfg.effort, max_tokens=128000)
    (d / "response.json").write_text(json.dumps({"graph": graph, "stats": stats}, indent=1))
    return graph, stats


def load_cases(cfg):
    if cfg.domain == "arduino":
        cases = json.loads((ROOT / "research" / "data" / "arduino_dataset.json").read_text())
        pi = ROOT / "research" / "data" / "pi_dataset.json"
        if pi.exists() and not cfg.arduino_only:
            cases += json.loads(pi.read_text())
        for c in cases:
            c["domain"] = "arduino"
        return cases
    sys.path.insert(0, str(ROOT / "research" / "scrape"))
    import lego_ldraw
    index, elements, part_nums = lego_ldraw.library_index(), truth.element_map(), truth.part_numbers()
    cases = []
    for c in json.loads((ROOT / "research" / "data" / "lego_dataset.json").read_text()):
        mpd = (ROOT / "research" / "raw" / "lego" / f"{c['set']}.mpd").read_text(errors="replace")
        cases.append({**c, "id": c["set"], "domain": "lego", "elements": elements, "part_nums": part_nums,
                      "truth": truth.lego_pdf_truth(c, mpd, index, lego_ldraw.describe)})
    return cases


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["arduino", "lego"], required=True)
    ap.add_argument("--catalogue", choices=["seeded", "empty"], default=None)
    ap.add_argument("--route", choices=["api", "subscription"], default="api",
                    help="api: Anthropic API key (.env). subscription: headless Claude Code on your Claude plan")
    ap.add_argument("--model", default=None, help="Default: claude-sonnet-5 (api) / sonnet (subscription)")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--limit", type=int, help="First N manuals of the test set")
    ap.add_argument("--cases", nargs="*", help="Only these manual ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--arduino-only", action="store_true", help="Electronics: leave out the Raspberry Pi projects")
    ap.add_argument("--replay", type=pathlib.Path)
    cfg = ap.parse_args()
    cfg.model = cfg.model or ("sonnet" if cfg.route == "subscription" else "claude-sonnet-5")
    cfg.catalogue = cfg.catalogue or ("seeded" if cfg.domain == "arduino" else "empty")

    cases = load_cases(cfg)
    if cfg.cases:
        cases = [c for c in cases if c["id"] in cfg.cases]
    cases = cases[: cfg.limit]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "experiments" / "graphgen" / f"{stamp}-{cfg.domain}-{cfg.model}-{cfg.effort}-{cfg.catalogue}"
    out.mkdir(parents=True, exist_ok=True)
    catalogue = cat.Catalogue(cat.arduino_seed() if cfg.domain == "arduino" and cfg.catalogue == "seeded" else {})
    results, failures, t_run = [], [], time.monotonic()

    for start in range(0, len(cases), cfg.workers):
        wave = cases[start:start + cfg.workers]
        text = catalogue.prompt_text() if catalogue.entries else ""
        with concurrent.futures.ThreadPoolExecutor(cfg.workers) as pool:
            futures = {pool.submit(call, c, text, cfg, out): c for c in wave}
            for fut in concurrent.futures.as_completed(futures):
                c = futures[fut]
                try:
                    graph, stats = fut.result()
                    r = process(c, graph, stats, catalogue, out)
                    results.append(r)
                    with open(out / "results.jsonl", "a") as f:
                        f.write(json.dumps(r) + "\n")
                    print(f"[{len(results) + len(failures):3d}/{len(cases)}] {c['id']:28s} {stats['seconds']:6.1f}s "
                          f"${stats['cost_usd']:.3f}  parts {r['parts']:4d}  new types {r['new_types_added']:3d}  "
                          f"problems {len(r['problems']):3d}", flush=True)
                except Exception as e:
                    failures.append({"case": c["id"], "error": f"{type(e).__name__}: {e}"})
                    (out / "failures.json").write_text(json.dumps(failures, indent=1))
                    print(f"[{len(results) + len(failures):3d}/{len(cases)}] {c['id']:28s} FAILED {type(e).__name__}: {str(e)[:120]}",
                          flush=True)
                    traceback.print_exc(limit=1)

    (out / "catalogue_after.json").write_text(json.dumps(catalogue.to_json(), indent=1))
    from .report import write_report
    path = write_report(out, results, failures, {**vars(cfg), "replay": str(cfg.replay), "wall_seconds": round(time.monotonic() - t_run)})
    print("\nreport:", path)


if __name__ == "__main__":
    main()
