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
    for t, card in (saved.get("cards") or {}).items():  # v3: the cards this manual was built with
        catalogue.entries.setdefault(t, card)
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
    for k in ("graph_positions", "graph_rests"):  # v7: joins from positions; v8: joins from rests_on alone
        if saved.get(k):
            (d / f"{k}.json").write_text(json.dumps(expand.expand(saved[k]), indent=1))
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
    if cfg.manual_url and case.get("url"):  # experiment: only the tutorial's link; Claude reads the page itself
        manual, images = (f"The tutorial is the web page {case['url']}. Open it with the open_page tool and read "
                          f"it, including its circuit section, parts list and circuit images, before answering."), []
    if cfg.version in ("v4", "v5", "v6", "v7", "v8"):  # the generic pipeline (graphgen/pipeline.py), recipes in domains.py
        from . import pipeline
        saved = pipeline.run_case(case, entries, cfg, out, manual, images, pdf)
        (d / "response.json").write_text(json.dumps(saved, indent=1))
        return saved
    domain = case["domain"] if case["domain"] == "arduino" else "lego-pdf"
    text = cat.Catalogue(entries).prompt_text() if entries else ""
    Session = SubscriptionSession if cfg.route == "subscription" else ApiSession
    booklet = checks.booklet_inventory(pdf) if pdf else None
    prep = None
    if cfg.version == "v3":  # parts first: list and card every part before the graph is built
        from . import v3
        prep = v3.prepare_lego(case, pdf, cfg, out) if pdf else v3.prepare_electronics(case, manual, cfg, out)
        text, domain = prep["catalogue_text"], ("lego" if pdf else "arduino") + "-v3"
        entries = {**entries, **prep["cards"]}

    def check(graph):
        t0 = time.monotonic()
        tmp = cat.Catalogue(entries)
        tmp.add_drafts(graph["new_part_types"])
        flat = expand.expand(graph)
        found = checks.run(flat, tmp, case["domain"], manual, case.get("part_nums", frozenset()), booklet)
        if prep and pdf:
            found += v3.parts_check(flat, prep["parts"])
        return found, round(time.monotonic() - t0, 2)

    def to_repair(issues):  # v3 repairs real errors only; v2 repairs everything the checks find
        return [i for i in issues if i[0] in v3.REAL_RULES] if prep else issues

    import subprocess
    for attempt in range(2):  # a stalled session is retried once from the start
        # Per-turn limit: 10 min, plus ~4 s per piece for big LEGO booklets (a 216-piece set took 11 min); a stalled
        # turn is then retried from the start instead of waiting.
        limit = min(2400, max(600, 4 * case.get("pieces", 0))) if pdf else 600
        kw = {"timeout": limit} if cfg.route == "subscription" else {}
        session = Session(manual + (prep["manual_extra"] if prep else ""), text, domain, images=images, pdf=pdf,
                          model=cfg.model, effort=cfg.effort, **kw)
        try:
            graph, st = session.first()
            graph_initial, phases = graph, [*([prep["phase"]] if prep else []), {"phase": "build", **st}]
            issues, secs = check(graph)
            phases[-1].update(check_seconds=secs, issues=len(issues), issue_rules=dict(collections.Counter(i[0] for i in issues)))
            issues_first = len(issues)
            for n in range(cfg.repair_rounds):
                if not to_repair(issues):
                    break
                graph, st = session.repair(checks.repair_message(to_repair(issues)))
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
    build = next(p for p in phases if p["phase"] == "build")
    total = {"model": build["model"], "effort": cfg.effort, "route": build["route"], "version": cfg.version,
             "seconds": round(sum(p["seconds"] + p["check_seconds"] for p in phases), 1),
             "input_tokens": sum(p["input_tokens"] for p in phases), "output_tokens": sum(p["output_tokens"] for p in phases),
             "cost_usd": round(sum(p["cost_usd"] for p in phases), 4),
             "repair_rounds_used": sum(1 for p in phases if p["phase"].startswith("repair"))}
    saved = {"graph": graph, "graph_initial": graph_initial, "stats": total, "phases": phases,
             "issues_first": issues_first, "issues_final": len(issues), "final_issue_list": [list(i) for i in issues]}
    if prep:
        saved.update(cards=prep["cards"], parts_list=prep["parts"])
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
    ap.add_argument("--version", choices=["v2", "v3", "v4", "v5", "v6", "v7", "v8"], default="v2",
                    help="v3: parts first (graphgen/v3.py), repair real errors only. v4/v5: the generic pipeline, recipes in domains.py; "
                         "LEGO = LDraw file if there is one, else the booklet page by page (graphgen/pipeline.py)")
    ap.add_argument("--cards", type=pathlib.Path, help="v3: card store to start from (default: LEGO prebuilt store; "
                                                         "electronics a fresh store in the run folder)")
    ap.add_argument("--hide-parts", nargs="*", default=[], help="v3 LEGO: act as if Rebrickable lacks these sets (fallback)")
    ap.add_argument("--manual-url", action="store_true",
                    help="experiment (electronics): give Claude only the tutorial's URL; it reads the page itself")
    ap.add_argument("--whole-booklet", action="store_true",
                    help="v8 LEGO: read the whole booklet in one turn even when it has step numbers as text (no step diff)")
    ap.add_argument("--lego-path", choices=["auto", "ldraw", "pages"], default="auto",
                    help="v4 LEGO build: auto = LDraw model if the set has one, else the booklet page by page")
    cfg = ap.parse_args()
    cfg.model = cfg.model or ("sonnet" if cfg.route == "subscription" else "claude-sonnet-5")
    cfg.catalogue = cfg.catalogue or ("seeded" if cfg.domain == "arduino" else "empty")

    cases = load_cases(cfg)
    if cfg.cases:
        cases = [c for c in cases if c["id"] in cfg.cases]
    cases = cases[: cfg.limit]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "experiments" / "graphgen" / f"{stamp}-{cfg.domain}-{cfg.model}-{cfg.effort}-{cfg.catalogue}" \
        f"{'-' + cfg.version if cfg.version != 'v2' else ''}{'-url' if cfg.manual_url else ''}"
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
    if cfg.domain == "lego" and cfg.version == "v8":  # AR: steps with placements, anchor and booklet pictures
        from . import ar
        ar.main([str(out)])
        print("AR report:", out / "AR_REPORT.md")


if __name__ == "__main__":
    main()
