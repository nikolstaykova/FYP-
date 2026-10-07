"""Accuracy of several versions on the same manuals, split into PARTS and GRAPH, with where the mistakes are.

  .venv-research/bin/python -m graphgen.evaluate --domain arduino v1=<run> v2=<run> v3=<run> v4=<run> [-o out.md]
  .venv-research/bin/python -m graphgen.evaluate --domain lego    v1=<run> v2=<run> ...

Only manuals every given run finished are compared (the count is printed), so versions are judged on the
same inputs.

Electronics (answer key: CircuitQuest's verified circuit, 47 tutorials; the rest: the tutorial's own parts list)
  PARTS  part families (board, led, resistor, ...; wires and breadboard excluded) vs the answer key: tutorials
         with every part exactly right, pooled precision/recall, most often missing / extra families
  GRAPH  electrical nets (wires and breadboard folded away) vs the answer key: tutorials with every net exactly
         right, pooled precision/recall, the same among tutorials whose parts were right (graph errors that are
         not parts errors), most often missed / invented connections
LEGO (answer key: Rebrickable inventory for parts, LDraw geometry for which plain bricks/plates/tiles clutch)
  PARTS  piece count, pieces right by design and by design+colour, most often missing / extra designs
  GRAPH  brick contacts: pooled recall/precision, joins written per piece, most often missed / invented pairs
  Caveats printed with the table: from v3 on, Claude is GIVEN the Rebrickable inventory, so LEGO parts scores
  measure only whether it used the list; v4 Path A sets (built from the LDraw model) are left out of LEGO
  accuracy because the LDraw model is also the answer key.
"""
import argparse
import collections
import csv
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(run):
    rows = [json.loads(l) for l in (pathlib.Path(run) / "results.jsonl").read_text().splitlines() if l.strip()]
    return {r["case"]: r for r in rows}


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "–"


def ratio(a, b):
    return f"{a / b:.2f}" if b else "–"


def top(counter, n=6, fmt=str):
    return "; ".join(f"{fmt(k)} ×{v}" for k, v in counter.most_common(n)) or "none"


# --- Electronics -------------------------------------------------------------------------------
def net_label(sig):
    """A net signature (list of [family, role]) as short text: 'board:13 + resistor'."""
    return " + ".join(f"{f}:{r}" if r not in ("x", "") else f for f, r in sig)


CASES = {c["id"]: c for c in json.loads((ROOT / "research" / "data" / "arduino_dataset.json").read_text())
         + json.loads((ROOT / "research" / "data" / "pi_dataset.json").read_text())}
LESSONS = {k: c["cq_lesson"] for k, c in CASES.items() if c.get("cq_lesson")}
REVIEW = {k: v for k, v in json.loads((ROOT / "research" / "data" / "answer_key_review.json").read_text()).items()
          if not k.startswith("_")}


MANUALS = ROOT / "research" / "raw" / "arduino_md"


def manual_text(case):
    """The tutorial's text (cached on disk; the official tutorials come from GitHub)."""
    from .run import arduino_manual
    MANUALS.mkdir(parents=True, exist_ok=True)
    path = MANUALS / f"{case}.md"
    if path.exists():
        return path.read_text()
    c = CASES[case]
    text = (ROOT / c["manual_file"]).read_text() if c.get("manual_file") else arduino_manual(c["path"], False)[0]
    path.write_text(text)
    return text


def _substitute(res, case):
    """Pin-substitute score (CircuitQuest's rule) and whether any circuit-law error is left."""
    from . import catalogue as cat
    from . import logical, score, truth
    from .run import DROP
    flat = json.loads((pathlib.Path(res["_run"]) / case / "graph.json").read_text())
    resp = json.loads((pathlib.Path(res["_run"]) / case / "response.json").read_text())
    c = cat.Catalogue(cat.arduino_seed())
    for t, card in (resp.get("cards") or {}).items():
        c.entries.setdefault(t, card)
    c.add_drafts(resp["graph"].get("new_part_types", []))
    lesson = LESSONS[case]
    sub = score.score_substitute(flat, logical.nets(flat, c), truth.arduino_truth(lesson), DROP.get(lesson, ()),
                                 manual_text(case))
    laws_ok = not any(i[0].startswith("E") for i in resp.get("final_issue_list", []))
    return sub["sub_all_correct"] and laws_ok


def _readable(net):
    return " + ".join(sorted(net))


def judge(res, case):
    """The one rule every version is scored by: CircuitQuest's checker (pass, harmless symmetric swap, substitute
    pin), and also correct if connected in an electrically equivalent way (resistors/LEDs in another series order;
    polarity still counts). Returns (correct, how, explanation of what is wrong)."""
    from . import catalogue as cat
    from . import cq_score, logical, score, truth
    from .run import DROP
    flat = json.loads((pathlib.Path(res["_run"]) / case / "graph.json").read_text())
    resp = json.loads((pathlib.Path(res["_run"]) / case / "response.json").read_text())
    c = cat.Catalogue(cat.arduino_seed())
    for t, card in (resp.get("cards") or {}).items():
        c.entries.setdefault(t, card)
    c.add_drafts(resp["graph"].get("new_part_types", []))
    lesson = LESSONS[case]
    try:
        d = cq_score.verdict(flat, c, lesson, DROP.get(lesson, ()), detail=True)  # one search: verdict and why
    except Exception as e:
        d = {"verdict": "wrong", "missing": [[f"(CircuitQuest could not read the graph: {type(e).__name__})"]]}
    if d["verdict"] in ("pass", "harmless", "substituted"):
        return True, d["verdict"], ""
    nets = logical.nets(flat, c)
    if score.score_equivalent(flat, nets, truth.arduino_truth(lesson), DROP.get(lesson, ()), unpolar=False)["eq_all_correct"]:
        return True, "equivalent", ""
    missing = [_readable(m) for m in d.get("missing", [])][:3]
    have = sorted({_readable(v) for v in (d.get("conflicts") or {}).values()})[:3]
    return False, "wrong", ("missing: " + "; ".join(missing) + (" | the graph has instead: " + "; ".join(have) if have else ""))


def _circuitquest(res, case):
    """CircuitQuest's own verdict on the graph (graphgen/cq_score.py): pass, harmless, substituted or wrong."""
    from . import catalogue as cat
    from . import cq_score
    from .run import DROP
    flat = json.loads((pathlib.Path(res["_run"]) / case / "graph.json").read_text())
    resp = json.loads((pathlib.Path(res["_run"]) / case / "response.json").read_text())
    c = cat.Catalogue(cat.arduino_seed())
    for t, card in (resp.get("cards") or {}).items():
        c.entries.setdefault(t, card)
    c.add_drafts(resp["graph"].get("new_part_types", []))
    lesson = LESSONS[case]
    try:
        return cq_score.verdict(flat, c, lesson, DROP.get(lesson, ()))
    except Exception as e:  # a graph CircuitQuest cannot read counts as wrong, and says why
        return f"wrong ({type(e).__name__})"


def _equivalent(res, case):
    """Series-equivalent score for one finished tutorial (rebuilt from its saved graph)."""
    from . import catalogue as cat
    from . import logical, score, truth
    from .run import DROP
    flat = json.loads((pathlib.Path(res["_run"]) / case / "graph.json").read_text())
    resp = json.loads((pathlib.Path(res["_run"]) / case / "response.json").read_text())
    c = cat.Catalogue(cat.arduino_seed())  # the catalogue the run scored with: seed + its cards + its drafts
    for t, card in (resp.get("cards") or {}).items():
        c.entries.setdefault(t, card)
    c.add_drafts(resp["graph"].get("new_part_types", []))
    lesson = LESSONS[case]
    return score.score_equivalent(flat, logical.nets(flat, c), truth.arduino_truth(lesson), DROP.get(lesson, ()))


def electronics(runs, common):
    out = []
    keyed = [c for c in common if all("nets_expected" in runs[v][c]["score"] for v in runs)]
    free = [c for c in common if all(runs[v][c]["score"].get("hardware_recall") is not None for v in runs)]
    out.append(f"**{len(common)} tutorials finished by every version**; {len(keyed)} have an answer key (CircuitQuest), "
               f"{len(free)} are scored on the tutorial's own parts list.\n")
    head = "| Measure | " + " | ".join(runs) + " |\n|---|" + "---:|" * len(runs)
    p_rows, g_rows, notes = collections.defaultdict(list), collections.defaultdict(list), []
    for v, res in runs.items():
        rows = [res[c]["score"] for c in keyed]
        want = sum((collections.Counter(s["inventory_expected"]) for s in rows), collections.Counter())
        got = sum((collections.Counter(s["inventory_built"]) for s in rows), collections.Counter())
        both = sum(min(collections.Counter(s["inventory_expected"])[k], collections.Counter(s["inventory_built"])[k])
                   for s in rows for k in s["inventory_expected"])
        missing = collections.Counter()
        extra = collections.Counter()
        for s in rows:
            w, g = collections.Counter(s["inventory_expected"]), collections.Counter(s["inventory_built"])
            missing.update(w - g)
            extra.update(g - w)
        parts_ok = [s for s in rows if s["inventory_correct"]]
        p_rows["Tutorials with every part exactly right"].append(f"{len(parts_ok)} / {len(rows)} ({pct(len(parts_ok), len(rows))})")
        p_rows["Part precision (pooled)"].append(ratio(both, sum(got.values())))
        p_rows["Part recall (pooled)"].append(ratio(both, sum(want.values())))
        p_rows["Other tutorials: listed part families present"].append(
            ratio(sum(res[c]["score"]["hardware_recall"] for c in free), len(free)))
        p_rows["Most often MISSING"].append(top(missing, 4))
        p_rows["Most often EXTRA"].append(top(extra, 4))

        exp = sum(s["nets_expected"] for s in rows)
        built = sum(s["nets_built"] for s in rows)
        match = sum(s["nets_matched"] for s in rows)
        nets_ok = sum(1 for s in rows if s["all_nets_correct"])
        given = [s for s in parts_ok]
        g_rows["Tutorials with every connection exactly right"].append(f"{nets_ok} / {len(rows)} ({pct(nets_ok, len(rows))})")
        g_rows["Net precision (pooled)"].append(ratio(match, built))
        g_rows["Net recall (pooled)"].append(ratio(match, exp))
        g_rows["…of tutorials with the parts right: every connection right"].append(
            f"{sum(1 for s in given if s['all_nets_correct'])} / {len(given)}")
        mn, xn = collections.Counter(), collections.Counter()
        for s in rows:
            mn.update(net_label(n) for n in s["missing_nets"])
            xn.update(net_label(n) for n in s["extra_nets"])
        clean = [c for c in keyed if c not in REVIEW]
        g_rows[f"Every connection right, reviewed answer key ({len(clean)} tutorials)"].append(
            f"{sum(1 for c in clean if res[c]['score']['all_nets_correct'])} / {len(clean)}")
        eq = dict(zip(keyed, _parallel(_equivalent, [res[c] for c in keyed], keyed)))
        g_rows["Every connection right, electrically equivalent accepted"].append(
            f"{sum(1 for c in keyed if eq[c]['eq_all_correct'])} / {len(keyed)}")
        g_rows["…equivalent AND reviewed answer key"].append(
            f"{sum(1 for c in clean if eq[c]['eq_all_correct'])} / {len(clean)}")
        cq = dict(zip(keyed, _parallel(_circuitquest, [res[c] for c in keyed], keyed)))
        right = lambda cs: sum(1 for c in cs if cq[c] in ("pass", "harmless", "substituted"))
        g_rows["**CircuitQuest says correct** (pass, harmless swap or substitute pin)"].append(
            f"**{right(keyed)} / {len(keyed)} ({pct(right(keyed), len(keyed))})**")
        g_rows["**…CircuitQuest correct, reviewed answer key**"].append(
            f"**{right(clean)} / {len(clean)} ({pct(right(clean), len(clean))})**")
        g_rows["…of which: exact pass / harmless swap / substitute pin"].append(
            "/".join(str(sum(1 for c in keyed if cq[c] == v)) for v in ("pass", "harmless", "substituted")))
        sub = dict(zip(keyed, _parallel(_substitute, [res[c] for c in keyed], keyed)))
        g_rows["Correct with substitute pins + laws hold"].append(
            f"{sum(1 for c in keyed if sub[c])} / {len(keyed)} ({pct(sum(1 for c in keyed if sub[c]), len(keyed))})")
        g_rows["**…substitute pins + laws hold, reviewed answer key**"].append(
            f"**{sum(1 for c in clean if sub[c])} / {len(clean)} ({pct(sum(1 for c in clean if sub[c]), len(clean))})**")
        g_rows["Most often MISSED connections"].append(top(mn, 3))
        g_rows["Most often INVENTED connections"].append(top(xn, 3))
        wrong = [c for c in keyed if not res[c]["score"]["all_nets_correct"]]
        notes.append(f"- **{v}** tutorials with a wrong connection: {', '.join(sorted(wrong)) or 'none'}")
    # --- time, cost, cleanliness, failure types, stability ---
    t_rows = collections.defaultdict(list)
    for v, res in runs.items():
        x = [res[c] for c in common]
        t_rows["Mean time per tutorial"].append(f"{sum(r['stats']['seconds'] for r in x) / len(x):.0f} s")
        t_rows["Mean cost per tutorial"].append(f"${sum(r['stats']['cost_usd'] for r in x) / len(x):.3f}")
        for ph in ("parts", "build", "repair1"):
            ps = [p for r in x for p in r.get("phases", []) if p["phase"] == ph]
            t_rows[f"Phase {ph}: runs, mean time"].append(f"{len(ps)}, {sum(p['seconds'] for p in ps) / len(ps):.0f} s" if ps else "–")
        t_rows["Tutorials repaired"].append(str(sum(1 for r in x if r["stats"].get("repair_rounds_used"))))
        left = collections.Counter()
        for r in x:
            left.update((r.get("phases") or [{}])[-1].get("issue_rules") or {})
        t_rows["Check issues left at the end"].append(f"{sum(left.values())}" + (f" ({top(left, 3)})" if left else ""))
        t_rows["Rule problems left (spec rules)"].append(str(sum(len(r["problems"]) for r in x)))
    kinds = collections.defaultdict(lambda: collections.Counter())
    wrong_in = collections.Counter()
    for v, res in runs.items():
        for c in keyed:
            sc = res[c]["score"]
            if sc["all_nets_correct"]:
                continue
            wrong_in[c] += 1
            kinds[v]["answer key differs (reviewed)" if c in REVIEW else
                     "parts differ from the answer key" if not sc["inventory_correct"] else
                     "parts right, wiring wrong"] += 1
    for v in runs:
        t_rows["Wrong tutorials, by cause"].append(top(kinds[v], 3))
    always = sorted(c for c, n in wrong_in.items() if n == len(runs))
    flaky = sorted(c for c, n in wrong_in.items() if 0 < n < len(runs))
    out += ["### Speed, cost and cleanliness", "", head,
            *[f"| {k} | " + " | ".join(vs) + " |" for k, vs in t_rows.items()], "",
            f"**Wrong in every version ({len(always)}):** {', '.join(always) or 'none'}  ",
            f"**Right in some versions, wrong in others ({len(flaky)}):** {', '.join(flaky) or 'none'}", ""]
    out += ["### Parts: does it find every part exactly?", "", head,
            *[f"| {k} | " + " | ".join(vs) + " |" for k, vs in p_rows.items()], "",
            "### Graph: are the connections exactly right?", "", head,
            *[f"| {k} | " + " | ".join(vs) + " |" for k, vs in g_rows.items()], "",
            "Connections are compared after wires and breadboard are folded away (`board:13 + resistor` = pin 13 "
            "joined to a resistor leg). Strict rows count an electrically equivalent circuit as different; the "
            "*equivalent* rows accept resistors and LEDs in any series order (LED direction still checked) and a buzzer "
            "or speaker either way round. *Substitute pins* (CircuitQuest's rule, core/engine.py "
            "_try_pin_substitution) also accept a part on another board pin of the same pool (digital for digital, "
            "analog for analog, PWM where the code uses analogWrite/tone; never bus, serial or power pins, nor any pin "
            "of a sketch that loops over pin numbers), provided no circuit-law error is left. The "
            "*reviewed answer key* rows leave out the tutorials where CircuitQuest's circuit differs from the official "
            "tutorial (research/data/answer_key_review.json: " + ", ".join(sorted(REVIEW)) + ").",
            "", "Where the connection mistakes are, per version:", *notes, ""]
    return "\n".join(out)


# --- LEGO --------------------------------------------------------------------------------------
def lego(runs, common):
    sys.path.insert(0, str(ROOT / "research" / "scrape"))
    import lego_ldraw

    from . import truth
    names = {}
    with gzip.open(ROOT / "research" / "raw" / "rebrickable" / "parts.csv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            names[r["part_num"]] = r["name"]
    data = {c["set"]: c for c in json.loads((ROOT / "research" / "data" / "lego_dataset.json").read_text())}
    elements, part_nums, index = truth.element_map(), truth.part_numbers(), lego_ldraw.library_index()
    path_a = {c for v, res in runs.items() for c in common if res[c]["stats"].get("builder") == "ldraw"}
    empty = {c for v, res in runs.items() for c in common if res[c]["parts"] == 0}
    cases = [c for c in common if c not in path_a and c not in empty]
    truths = {}
    for c in cases:
        mpd = (ROOT / "research" / "raw" / "lego" / f"{c}.mpd").read_text(errors="replace")
        truths[c] = truth.lego_pdf_truth(data[c], mpd, index, lego_ldraw.describe)
        truths[c]["ext"] = truth.lego_pdf_truth(data[c], mpd, index, lego_ldraw.describe, extended=True)

    with gzip.open(ROOT / "research" / "raw" / "rebrickable" / "colors.csv.gz", "rt", encoding="utf-8") as f:
        colour_id = {r["name"].lower(): r["id"] for r in csv.DictReader(f)}
    from . import stud_key
    studs = stud_key.load()  # v7 answer key: real connections from stud geometry (stud_key.py)

    def exact_of(node, design):
        """design/colour id: from the Element ID if the node names one, else from its colour property."""
        m = re.search(r"(\d{6,7})", node["type"] + " " + (node.get("label") or ""))
        if m and m.group(1) in elements:
            return "/".join(elements[m.group(1)])
        props = node.get("props") or {}  # expanded graphs keep props as a dict
        props = props if isinstance(props, dict) else {p["key"]: p["value"] for p in props}
        col = next((v for k, v in props.items() if k.lower() in ("colour", "color")), None)
        return f"{design}/{colour_id[col.lower()]}" if design and col and col.lower() in colour_id else None

    def design_of(node):
        m = re.search(r"(\d{6,7})", node["type"] + " " + (node.get("label") or ""))
        if m and m.group(1) in elements:
            return elements[m.group(1)][0]
        m = re.match(r"^lego-([0-9a-z]+)$", node["type"].lower())
        return m.group(1) if m and m.group(1) in part_nums else None

    nm = lambda d: f"{names.get(d, d)}"
    pair_nm = lambda p: f"{names.get(p[0], p[0])} + {names.get(p[1], p[1])}"
    head = "| Measure | " + " | ".join(runs) + " |\n|---|" + "---:|" * len(runs)
    p_rows, g_rows = collections.defaultdict(list), collections.defaultdict(list)
    for v, res in runs.items():
        exact_n = built_n = want_n = d_match = d_built = e_match = 0
        missing, extra = collections.Counter(), collections.Counter()
        exp = pred = correct = joins = pieces = 0
        sk = {"all": [0, 0, 0], "trusted": [0, 0, 0]}  # stud key: expected, predicted, correct
        x_exp = x_pred = x_correct = 0
        miss_p, extra_p = collections.Counter(), collections.Counter()
        for c in cases:
            graph = json.loads((pathlib.Path(res[c]["_run"]) / c / res[c].get("_graph", "graph.json")).read_text())
            t = truths[c]
            designs = {n["id"]: design_of(n) for n in graph["nodes"]}
            got = collections.Counter(d for d in designs.values() if d)
            exact = collections.Counter(x for n in graph["nodes"] if (x := exact_of(n, designs[n["id"]])))
            e_match += sum((collections.Counter(t["inventory"]) & exact).values())
            want = collections.Counter()
            for key, q in t["inventory"].items():
                want[key.split("/")[0]] += q
            built_n += len(graph["nodes"])
            want_n += t["pieces"]
            exact_n += len(graph["nodes"]) == t["pieces"]
            d_match += sum((want & got).values())
            d_built += len(graph["nodes"])
            missing.update(want - got)
            extra.update(got - want)
            pairs = collections.Counter()
            s = t["scoreable_designs"]
            for e in graph["edges"]:
                if e["type"] != "joined":
                    continue
                joins += 1
                a, b = designs.get(e["u"]), designs.get(e["v"])
                if a in s and b in s:
                    pairs[tuple(sorted((a, b)))] += 1
            exp += sum(t["pairs"].values())
            pred += sum(pairs.values())
            correct += sum((t["pairs"] & pairs).values())
            x_pairs = collections.Counter()
            for e in graph["edges"]:
                a, b = designs.get(e["u"]), designs.get(e["v"])
                if e["type"] == "joined" and a in t["ext"]["scoreable_designs"] and b in t["ext"]["scoreable_designs"]:
                    x_pairs[tuple(sorted((a, b)))] += 1
            x_exp += sum(t["ext"]["pairs"].values())
            x_pred += sum(x_pairs.values())
            x_correct += sum((t["ext"]["pairs"] & x_pairs).values())
            miss_p.update(t["pairs"] - pairs)
            extra_p.update(pairs - t["pairs"])
            pieces += len(graph["nodes"])
            k = studs.get(c)
            if k:
                s_pairs = collections.Counter()
                for e in graph["edges"]:  # designs compared under one name per physical piece (stud_key.canon)
                    a, b = stud_key.canon(designs.get(e["u"])), stud_key.canon(designs.get(e["v"]))
                    if e["type"] == "joined" and a in k["designs"] and b in k["designs"]:
                        s_pairs[tuple(sorted((a, b)))] += 1
                s_pairs = s_pairs - (k["ambiguous"] - k["pairs"])  # a join the key cannot decide is not counted
                for scope in ("all", "trusted") if k["trusted"] else ("all",):
                    sk[scope][0] += sum(k["pairs"].values())
                    sk[scope][1] += sum(s_pairs.values())
                    sk[scope][2] += sum((k["pairs"] & s_pairs).values())
        p_rows["Sets with exactly the right number of pieces"].append(f"{exact_n} / {len(cases)} ({pct(exact_n, len(cases))})")
        p_rows["Pieces built ÷ pieces in the sets"].append(ratio(built_n, want_n))
        p_rows["Pieces right by design (recall, pooled)"].append(ratio(d_match, want_n))
        p_rows["Pieces that are real (precision, pooled)"].append(ratio(d_match, d_built))
        p_rows["Right design AND colour (recall, pooled)"].append(ratio(e_match, want_n))
        p_rows["Most often MISSING"].append(top(missing, 4, nm))
        p_rows["Most often EXTRA"].append(top(extra, 4, nm))
        g_rows["Brick contacts found (recall, pooled)"].append(ratio(correct, exp))
        g_rows["Joins that are real (precision, pooled)"].append(ratio(correct, pred))
        g_rows["Contacts found, more pieces scored (recall)"].append(ratio(x_correct, x_exp))
        g_rows["Joins real, more pieces scored (precision)"].append(ratio(x_correct, x_pred))
        g_rows["**Stud key (v7): connections found / real, all sets**"].append(
            f"{ratio(sk['all'][2], sk['all'][0])} / {ratio(sk['all'][2], sk['all'][1])}")
        g_rows["**Stud key: found / real, trusted sets only**"].append(
            f"{ratio(sk['trusted'][2], sk['trusted'][0])} / {ratio(sk['trusted'][2], sk['trusted'][1])}")
        g_rows["Joins written per piece"].append(ratio(joins, pieces))
        g_rows["Most often MISSED contacts"].append(top(miss_p, 3, pair_nm))
        g_rows["Most often INVENTED contacts"].append(top(extra_p, 3, pair_nm))
    exp_total = sum(sum(truths[c]["pairs"].values()) for c in cases)
    out = [f"**{len(common)} sets finished by every version**; scored on {len(cases)} "
           f"(left out: {len(path_a)} built from their LDraw model in v4, {len(empty)} with an empty graph). "
           f"{exp_total} checkable brick contacts.\n",
           "### Parts: does it find every piece exactly?", "", head,
           *[f"| {k} | " + " | ".join(vs) + " |" for k, vs in p_rows.items()], "",
           "From v3 on Claude is given the official inventory, so these rows show whether it used the list, not "
           "whether it can read pieces from pictures (v1 and v2 had to).", "",
           "### Graph: does it connect the pieces exactly?", "", head,
           *[f"| {k} | " + " | ".join(vs) + " |" for k, vs in g_rows.items()], "",
           "Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows "
           "also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has "
           "more than one contact per piece; a join count near 1.0 per piece means the model records a chain "
           "(each piece attached to one other), not every piece it touches. The **stud key** (v7, stud_key.py) "
           "scores every kind of piece by the library's stud, hole and pin geometry (clutch and pin joins); trusted "
           "sets are those whose model has the set's piece count and passes the physical laws.", ""]
    return "\n".join(out)


def _parallel(fn, res_list, cases):
    """fn(res, case) for many tutorials at once, on all but one CPU core (each judgment is independent)."""
    import concurrent.futures
    import os
    with concurrent.futures.ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as pool:
        return list(pool.map(fn, res_list, cases))


def judged(runs, common):
    """Every version by the one rule (judge): the headline, and each wrong tutorial with what it gets wrong."""
    keyed = [c for c in common if all("nets_expected" in runs[v][c]["score"] for v in runs)]
    clean = [c for c in keyed if c not in REVIEW]
    import concurrent.futures
    import os
    jobs = [(v, c) for v in runs for c in keyed]
    with concurrent.futures.ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as pool:  # judgments are independent
        results = list(pool.map(judge, [runs[v][c] for v, c in jobs], [c for _, c in jobs]))
    verdicts = {v: {} for v in runs}
    for (v, c), r in zip(jobs, results):
        verdicts[v][c] = r
    head = "| | " + " | ".join(runs) + " |\n|---|" + "---:|" * len(runs)
    row = lambda name, cs: f"| {name} | " + " | ".join(
        f"{sum(verdicts[v][c][0] for c in cs)} / {len(cs)} ({pct(sum(verdicts[v][c][0] for c in cs), len(cs))})" for v in runs) + " |"
    how = lambda v: collections.Counter(verdicts[v][c][1] for c in keyed if verdicts[v][c][0])
    out = [f"**Rule:** CircuitQuest's checker (exact, harmless symmetric swap, substitute pin) or connected in an "
           f"electrically equivalent way (resistors/LEDs in another series order; polarity still counts). "
           f"{len(keyed)} tutorials have an answer key; {len(clean)} after leaving out the {len(keyed) - len(clean)} "
           f"where the answer key is not the only right answer.", "", head,
           row("**Correct, reviewed answer key**", clean), row("Correct, all with an answer key", keyed),
           "| …how they were correct | " + " | ".join(", ".join(f"{k} {n}" for k, n in sorted(how(v).items())) for v in runs) + " |",
           ""]
    for v in runs:
        wrong = [c for c in keyed if not verdicts[v][c][0]]
        out += [f"**{v}: {len(wrong)} wrong** ({sum(1 for c in wrong if c not in REVIEW)} real, "
                f"{sum(1 for c in wrong if c in REVIEW)} where the answer key differs)", "",
                "| Tutorial | Whose error | What it gets wrong |", "|---|---|---|"]
        for c in sorted(wrong, key=lambda c: (c in REVIEW, c)):
            who = f"answer key ({REVIEW[c]['kind']}): {REVIEW[c]['reason']}" if c in REVIEW else "**model**"
            out.append(f"| {c} | {who} | {verdicts[v][c][2].replace('|', '/')} |")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["arduino", "lego"], required=True)
    ap.add_argument("runs", nargs="+", help="label=run_dir (several dirs for one label: label=dir1,dir2; another graph file: label=dir#graph_positions.json)")
    ap.add_argument("-o", "--out", type=pathlib.Path)
    ap.add_argument("--judged", action="store_true", help="electronics: every version by the one rule, with what is wrong")
    a = ap.parse_args()
    runs = {}
    for spec in a.runs:
        label, dirs = spec.split("=", 1)
        dirs, _, graph_file = dirs.partition("#")  # label=dir#graph_positions.json scores another graph file (v7)
        merged = {}
        for d in dirs.split(","):
            for c, r in load(d).items():
                if not graph_file or (pathlib.Path(d) / c / graph_file).exists():
                    merged[c] = {**r, "_run": d, "_graph": graph_file or "graph.json"}
        runs[label] = merged
    common = sorted(set.intersection(*(set(r) for r in runs.values())))
    if a.judged:
        text = judged(runs, common)
    else:
        text = (electronics if a.domain == "arduino" else lego)(runs, common)
    if a.out:
        a.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
