"""Audit every LDraw Official Model Repository (OMR) model as an exact answer key / Plan A graph source.

For each set in research/raw/lego/omr_sets.json: download the model (cached in research/raw/lego/<set>.mpd), compare it
with the set as sold (Rebrickable dump: name, parts list without spares), compute the stud answer key
(graphgen.stud_key.key_for) and classify:
  USABLE                 piece count within 5% (at least one piece either way, for tiny sets), designs match >= 90%
                         both ways, stud key trusted
  USABLE-WITH-CAVEATS    piece count within 5%, but designs match 80-90% or the stud key is not trusted
  MISMATCH               piece count or designs off (cause guessed: minifigures, alternate/extra models, partial
                         model, LSynth, part naming)
  UNAVAILABLE            no model file, no Rebrickable parts list, or the model could not be read in time

  .venv-research/bin/python research/scrape/omr_audit.py [--download-only] [--workers 6] [--limit N]
Writes research/data/omr_audit.json and research/data/omr_audit.md.
"""
import argparse
import collections
import concurrent.futures as cf
import difflib
import json
import pathlib
import re
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
RAW = ROOT / "research" / "raw" / "lego"
OUT_JSON = ROOT / "research" / "data" / "omr_audit.json"
MINIFIGS = True  # compare with the set's parts AND its minifigures' parts (--no-minifigs: parts only, as the first audit)
OUT_MD = ROOT / "research" / "data" / "omr_audit.md"
UA = {"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"}
TIMEOUT_S = 150  # per set, for the stud key of a very large model
# minifigure parts (Rebrickable lists minifigures apart from the set's parts, LDraw models include them)
MINIFIG = re.compile(r"^(973|970|971|972|3626|3624|3833|3815|3816|3817|3818|3819|3820|30381|76382|87990|92081|62810|"
                     r"85974|11256|16175|93088|6132|2524|3844|3842|30126|30167|970c|973c)")


def download(sets):
    status = {}
    for n, s in enumerate(sets):
        f = RAW / f"{s}.mpd"
        if f.exists() and f.stat().st_size > 0:
            status[s] = "cached"
            continue
        try:
            r = requests.get(f"https://library.ldraw.org/library/omr/{s}.mpd", headers=UA, timeout=60)
            if r.status_code == 200 and r.text.lstrip().startswith("0"):
                f.write_text(r.text)
                status[s] = "downloaded"
            else:
                status[s] = f"http {r.status_code}"
        except requests.RequestException as e:
            status[s] = f"error {type(e).__name__}"
        time.sleep(0.3)
        if n % 100 == 0:
            print(f"download {n}/{len(sets)}", flush=True)
    return status


def _name_of(text):
    """The model's title: the first plain comment line of its main file ("0 London"), not its "0 Name:" file name."""
    for line in text.splitlines()[:8]:
        if line.startswith("0 ") and not re.match(r"^0 (FILE|Name:|Author:|!|BFC|//)", line):
            return line[2:].strip()
    return ""


def audit_one(s, rb_name, rb_parts_n, minifigs=True):
    """Everything for one set (runs in a worker process)."""
    global MINIFIGS
    MINIFIGS = minifigs
    import signal
    from graphgen import stud_key, truth
    from graphgen.parts import lego as pl

    def stop(*_):
        raise TimeoutError(f"over {TIMEOUT_S} s")
    signal.signal(signal.SIGALRM, stop)
    signal.alarm(TIMEOUT_S)
    t0 = time.monotonic()
    text = (RAW / f"{s}.mpd").read_text(errors="replace")
    truth.LSYNTH_DESIGN.clear()
    files, embedded = truth.mpd_sections(text)
    lsynth = len(truth.LSYNTH_DESIGN)
    parts = pl.RebrickableDump.set_parts(s, minifigs=MINIFIGS)
    want, _, how = stud_key.reconcile(s) if parts else (None, None, {})
    root = stud_key.best_root(text, want) if want else None
    model = stud_key.model_designs(text, root)
    if parts and MINIFIGS:  # minifigures or not, assemblies whole or split on either side: the best agreement
        want, model, how = stud_key.reconcile(s, text, root)
        want, pairs = stud_key.pair_by_name(want, model)  # same piece, different numbering scheme
        how = {**how, "paired_by_name": pairs}
    row = {"set": s, "rebrickable_name": rb_name, "rebrickable_num_parts": rb_parts_n,
           "model_name": _name_of(text), "model_files": len(files), "embedded_parts": len(embedded - set(truth.LSYNTH_DESIGN)),
           "lsynth_pieces_drawn": lsynth, "model_pieces": sum(model.values())}
    a = re.sub(r"^\d+(-\d+)?\s*-?\s*|\.(ldr|mpd)$", "", row["model_name"].lower()).strip()
    row["name_match"] = round(difflib.SequenceMatcher(None, a, rb_name.lower()).ratio(), 2)
    if parts is None:
        row.update(parts_list_pieces=None, error="no Rebrickable parts list")
        return row
    inv = want
    row["root"], row["reconciled"] = root, how
    n_set, n_model = sum(inv.values()), sum(model.values())
    common = sum((inv & model).values())
    extra, missing = model - inv, inv - model
    row.update(parts_list_pieces=n_set, within_5pct=bool(n_set and abs(n_model - n_set) <= max(1, 0.05 * n_set)),
               set_found_in_model=round(common / n_set, 3) if n_set else 0, model_in_set=round(common / n_model, 3) if n_model else 0,
               minifig_parts_extra=sum(v for k, v in extra.items() if MINIFIG.match(k)),
               top_extra=extra.most_common(5), top_missing=missing.most_common(5))
    try:
        k = stud_key.key_for(s, n_set, parts_counter=inv)
        row.update(joins=k["joins"], laws=k["laws"], ambiguous=sum(k["ambiguous"].values()), trusted=k["trusted"])
    except TimeoutError:
        row.update(timeout=True, error=f"stud key over {TIMEOUT_S} s ({n_model} pieces)")
    except Exception as e:  # a model the geometry code cannot read
        row.update(error=f"stud key: {type(e).__name__}: {str(e)[:120]}")
    signal.alarm(0)
    row["seconds"] = round(time.monotonic() - t0, 1)
    return row


def classify(r):
    if r.get("download") not in ("cached", "downloaded"):
        return "UNAVAILABLE", f"model file: {r.get('download')}"
    if r.get("error") or r.get("timeout"):
        return "UNAVAILABLE", r.get("error") or "timed out"
    found, inset, within = r["set_found_in_model"], r["model_in_set"], r["within_5pct"]
    if within and found >= 0.9 and inset >= 0.9 and r.get("trusted"):
        return "USABLE", ""
    if within and found >= 0.8 and inset >= 0.8:
        return "USABLE-WITH-CAVEATS", "stud key not trusted (laws/ambiguity)" if not r.get("trusted") else "designs match 80-90%"
    return "MISMATCH", cause(r)


def cause(r):
    n_set, n_model = r["parts_list_pieces"] or 0, r["model_pieces"]
    ratio = n_model / n_set if n_set else 0
    extra_fig = r["minifig_parts_extra"]
    if r["lsynth_pieces_drawn"] and not r["within_5pct"]:
        return "LSynth (bendable parts)"
    if ratio > 1.05 and extra_fig >= 0.5 * (n_model - n_set):
        return "minifigures in the model (Rebrickable lists them apart)"
    if ratio >= 1.8:
        return "model has extra / alternate builds (about %.1fx the set)" % ratio
    if ratio < 0.7:
        return "partial model (%.0f%% of the set's pieces)" % (100 * ratio)
    if r["within_5pct"] and (r["set_found_in_model"] < 0.8 or r["model_in_set"] < 0.8):
        return "same count, different designs (part naming / mould variants)"
    if ratio > 1.05:
        return "model larger than the set (%.0f%%)" % (100 * ratio)
    if ratio < 0.95:
        return "model smaller than the set (%.0f%%)" % (100 * ratio)
    return "designs differ"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=pathlib.Path, default=OUT_JSON)
    ap.add_argument("--no-minifigs", action="store_true")
    cfg = ap.parse_args()
    global MINIFIGS
    MINIFIGS = not cfg.no_minifigs
    import csv
    import gzip
    sets = json.loads((RAW / "omr_sets.json").read_text())[: cfg.limit]
    status = download(sets)
    print("download:", collections.Counter(v.split()[0] for v in status.values()), flush=True)
    if cfg.download_only:
        return
    with gzip.open(ROOT / "research" / "raw" / "rebrickable" / "sets.csv.gz", "rt") as f:
        rb = {r["set_num"]: r for r in csv.DictReader(f)}
    rows = {}
    todo = []
    for s in sets:
        rows[s] = {"set": s, "download": status[s], "rebrickable_name": (rb.get(s) or {}).get("name", ""),
                   "rebrickable_num_parts": int((rb.get(s) or {}).get("num_parts") or 0)}
        if status[s] in ("cached", "downloaded"):
            todo.append(s)
    with cf.ProcessPoolExecutor(cfg.workers, max_tasks_per_child=1) as ex:
        futs = {ex.submit(audit_one, s, rows[s]["rebrickable_name"], rows[s]["rebrickable_num_parts"], MINIFIGS): s
                for s in todo}
        start = {f: time.monotonic() for f in futs}
        done_n = 0
        for f in cf.as_completed(futs):
            s = futs[f]
            try:
                rows[s].update(f.result())
            except Exception as e:
                rows[s].update(error=f"{type(e).__name__}: {str(e)[:120]}")
            done_n += 1
            if done_n % 50 == 0:
                print(f"audited {done_n}/{len(todo)}", flush=True)
    for r in rows.values():
        r["class"], r["why"] = classify(r)
    cfg.out.write_text(json.dumps(list(rows.values()), indent=1, default=list))
    print(collections.Counter(r["class"] for r in rows.values()))


if __name__ == "__main__" and "--summary" not in sys.argv:
    main()


def summary():
    """research/data/omr_audit.md from omr_audit.json: counts, causes with examples, usable sets with a written guide."""
    from graphgen.parts import sources
    rows = json.loads(OUT_JSON.read_text())
    sources.text_guides("0-1")  # loads both guide indexes (set number -> guide url)
    guides = {**{k: "LEGO Audio & Braille" for k in sources.LegoAudioBraille._index or {}},
              **{k: "Bricks for the Blind" for k in sources.BricksForTheBlind._index or {}}}
    by = collections.defaultdict(list)
    for r in rows:
        by[r["class"]].append(r)
    causes = collections.defaultdict(list)
    for r in by["MISMATCH"] + by["UNAVAILABLE"]:
        causes[re.sub(r"\(.*\)|\d+", "", r["why"]).strip()].append(r)
    lines = ["# LDraw OMR models as answer keys: audit", "",
             f"{len(rows)} sets in the Official Model Repository, each compared with the set as sold (Rebrickable parts "
             "list without spares) and checked with the stud answer key (`graphgen/stud_key.py`). Script: "
             "`research/scrape/omr_audit.py`; per-set results: `omr_audit.json`.", "",
             "| Class | Sets | Meaning |", "|---|---:|---|",
             f"| USABLE | {len(by['USABLE'])} | piece count within 5%, designs match ≥90% both ways, stud key trusted |",
             f"| USABLE-WITH-CAVEATS | {len(by['USABLE-WITH-CAVEATS'])} | within 5%, but designs match 80–90% or the stud key is not trusted |",
             f"| MISMATCH | {len(by['MISMATCH'])} | piece count or designs off |",
             f"| UNAVAILABLE | {len(by['UNAVAILABLE'])} | no model file, no parts list, or too large to check in time |", "",
             "## Why sets do not match", "", "| Cause | Sets | Examples |", "|---|---:|---|"]
    for c, rs in sorted(causes.items(), key=lambda kv: -len(kv[1])):
        ex = ", ".join(f"{r['set']} ({r.get('model_pieces', '?')} vs {r.get('parts_list_pieces', '?')})" for r in rs[:4])
        lines.append(f"| {c} | {len(rs)} | {ex} |")
    ok = [r for r in by["USABLE"] if r["set"].split("-")[0] in guides]
    lines += ["", f"## Usable sets that also have a written guide ({len(ok)})", "",
              "| Set | Name | Pieces | Guide |", "|---|---|---:|---|"]
    lines += [f"| {r['set']} | {r['rebrickable_name']} | {r['parts_list_pieces']} | {guides[r['set'].split('-')[0]]} |"
              for r in sorted(ok, key=lambda r: r["parts_list_pieces"] or 0)]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(OUT_MD)


if __name__ == "__main__" and "--summary" in sys.argv:
    summary()
