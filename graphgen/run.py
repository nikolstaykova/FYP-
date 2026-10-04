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
and later manuals reuse it. `--workers` manuals are always in flight; each new call sees the catalogue as it stands.
"""
import argparse
import collections
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


def score_graph(case, flat, catalogue):
    if case["domain"] == "arduino":
        if case.get("cq_lesson"):
            return score.score_arduino(flat, logical.nets(flat, catalogue), truth.arduino_truth(case["cq_lesson"]),
                                       DROP.get(case["cq_lesson"], ()))
        return score.score_hardware(flat, case.get("hardware", []))
    return score.score_lego_pdf(flat, case["truth"], case["elements"], case["part_nums"])


def process(case, saved, catalogue, out):
    """Everything after the model: catalogue, expansion, rules, scoring (final graph, and the first
    draft before repair so the repair's effect can be measured)."""
    graph, stats = saved["graph"], saved["stats"]
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
         "problems": [list(p) for p in problems], "notes": graph["notes"],
         "phases": saved.get("phases", [{"phase": "build", **stats}]),
         "issues_first": saved.get("issues_first"), "issues_final": saved.get("issues_final")}
    r["score"] = score_graph(case, flat, catalogue)
    if saved.get("graph_initial") is not None and saved["graph_initial"] is not graph:
        tmp = cat.Catalogue(catalogue.entries)
        tmp.add_drafts(saved["graph_initial"]["new_part_types"])
        r["score_initial"] = score_graph(case, expand.expand(saved["graph_initial"]), tmp)
    if case["domain"] == "arduino":
        r["drafts"] = score.score_drafts(new_drafts, cat.arduino_seed())
    r["postprocess_ms"] = round((time.monotonic() - t0) * 1000, 1)
    d = out / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.json").write_text(json.dumps(flat, indent=1))
    (d / "result.json").write_text(json.dumps(r, indent=1))
    return r


def call(case, entries, cfg, out):
    """Build -> check -> repair (up to cfg.repair_rounds) -> final check, each phase timed and costed."""
    from . import checks
    from .extract import ApiSession, SubscriptionSession

    d = out / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    if cfg.replay and (cfg.replay / case["id"] / "response.json").exists():
        saved = json.loads((cfg.replay / case["id"] / "response.json").read_text())
        (d / "response.json").write_text(json.dumps(saved, indent=1))
        return saved

    pdf, images, manual = None, [], ""
    if case["domain"] == "arduino" and case.get("manual_file"):
        manual = (ROOT / case["manual_file"]).read_text()
        images = [] if cfg.no_images else [((ROOT / i["file"]).read_bytes(), i["media"]) for i in case["images"]]
    elif case["domain"] == "arduino":
        manual, images = arduino_manual(case["path"], not cfg.no_images)
    else:
        pdf = (ROOT / "research" / "raw" / "lego_pdf" / f"{case['id']}.pdf").read_bytes()
        manual = f"LEGO set {case['id']}: {case['name']} (official instructions attached)."
    domain = case["domain"] if case["domain"] == "arduino" else "lego-pdf"
    text = cat.Catalogue(entries).prompt_text() if entries else ""
    Session = SubscriptionSession if cfg.route == "subscription" else ApiSession
    booklet = checks.booklet_inventory(pdf) if pdf else None

    def check(graph):
        t0 = time.monotonic()
        tmp = cat.Catalogue(entries)
        tmp.add_drafts(graph["new_part_types"])
        found = checks.run(expand.expand(graph), tmp, case["domain"], manual, case.get("part_nums", frozenset()), booklet)
        return found, round(time.monotonic() - t0, 2)

    import subprocess
    for attempt in range(2):  # a stalled session is retried once from the start
        # Per-turn limit: 10 min, plus ~4 s per piece for big LEGO booklets (a 216-piece set took 11 min); a stalled
        # turn is then retried from the start instead of waiting.
        limit = min(2400, max(600, 4 * case.get("pieces", 0))) if pdf else 600
        kw = {"timeout": limit} if cfg.route == "subscription" else {}
        session = Session(manual, text, domain, images=images, pdf=pdf, model=cfg.model, effort=cfg.effort, **kw)
        try:
            graph, st = session.first()
            graph_initial, phases = graph, [{"phase": "build", **st}]
            issues, secs = check(graph)
            phases[-1].update(check_seconds=secs, issues=len(issues), issue_rules=dict(collections.Counter(i[0] for i in issues)))
            issues_first = len(issues)
            for n in range(cfg.repair_rounds):
                if not issues:
                    break
                graph, st = session.repair(checks.repair_message(issues))
                issues, secs = check(graph)
                phases.append({"phase": f"repair{n + 1}", **st, "check_seconds": secs, "issues": len(issues),
                               "issue_rules": dict(collections.Counter(i[0] for i in issues))})
            break
        except subprocess.TimeoutExpired as e:
            with open(out / "stalls.log", "a") as f:  # what the session was doing when it stalled
                f.write(f"{case['id']} attempt {attempt + 1}: no result after {e.timeout}s; last events {e.output}\n")
            if attempt:
                raise
        except RuntimeError as e:  # safety-filter false positives are random: retry once from the start
            if attempt or "safeguards" not in str(e):
                raise
        finally:
            session.close()
    total = {"model": phases[0]["model"], "effort": cfg.effort, "route": phases[0]["route"],
             "seconds": round(sum(p["seconds"] + p["check_seconds"] for p in phases), 1),
             "input_tokens": sum(p["input_tokens"] for p in phases), "output_tokens": sum(p["output_tokens"] for p in phases),
             "cost_usd": round(sum(p["cost_usd"] for p in phases), 4), "repair_rounds_used": len(phases) - 1}
    saved = {"graph": graph, "graph_initial": graph_initial, "stats": total, "phases": phases,
             "issues_first": issues_first, "issues_final": len(issues), "final_issue_list": [list(i) for i in issues]}
    (d / "response.json").write_text(json.dumps(saved, indent=1))
    return saved


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
    ap.add_argument("--repair-rounds", type=int, default=1, help="Check-and-repair rounds after the first build (0 = off)")
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

    # Keep `workers` calls in flight; each new call sees the catalogue as it is when it starts.
    pending, inflight = list(cases), {}
    with concurrent.futures.ThreadPoolExecutor(cfg.workers) as pool:
        while pending or inflight:
            while pending and len(inflight) < cfg.workers:
                c = pending.pop(0)
                inflight[pool.submit(call, c, json.loads(json.dumps(catalogue.entries)), cfg, out)] = c
            done, _ = concurrent.futures.wait(inflight, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                c = inflight.pop(fut)
                try:
                    saved = fut.result()
                    stats = saved["stats"]
                    r = process(c, saved, catalogue, out)
                    results.append(r)
                    with open(out / "results.jsonl", "a") as f:
                        f.write(json.dumps(r) + "\n")
                    print(f"[{len(results) + len(failures):3d}/{len(cases)}] {c['id']:28s} {stats['seconds']:6.1f}s "
                          f"${stats['cost_usd']:.3f}  parts {r['parts']:4d}  new types {r['new_types_added']:3d}  "
                          f"issues {r['issues_first']}->{r['issues_final']}  repairs {stats.get('repair_rounds_used', 0)}", flush=True)
                except Exception as e:
                    failures.append({"case": c["id"], "error": f"{type(e).__name__}: {e}"})
                    (out / "failures.json").write_text(json.dumps(failures, indent=1))
                    print(f"[{len(results) + len(failures):3d}/{len(cases)}] {c['id']:28s} FAILED {type(e).__name__}: {str(e)[:120]}",
                          flush=True)
                    traceback.print_exc(limit=1)
                    if pending and re.search(r"(session|usage|rate) limit", str(e), re.I):
                        # Out of subscription quota: every later call would fail too. Stop here; --replay <this run> resumes.
                        print(f"limit reached, {len(pending)} manuals not started; resume with --replay {out}", flush=True)
                        pending.clear()

    (out / "catalogue_after.json").write_text(json.dumps(catalogue.to_json(), indent=1))
    from .report import write_report
    path = write_report(out, results, failures, {**vars(cfg), "replay": str(cfg.replay), "wall_seconds": round(time.monotonic() - t_run)})
    print("\nreport:", path)


if __name__ == "__main__":
    main()
