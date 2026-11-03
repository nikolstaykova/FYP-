"""DATASTRUCTURE.md: the shared page "Pinpoint Lesson Data" as Markdown, section by section, written from the stored
lessons so the two always say the same thing (the page: https://claude.ai/artifact/AHdcjWezQiNFKGDAc9v5Yt).

  0  how a lesson is made          who does what (code, Claude, a check), in the parts-first order
  1  the two pilot lessons         the lesson record, the steps graph, the physical graph, the part definitions
  2  the Arduino circuit up close  which ports share a net
  3  booklet lessons               three LEGO lessons from their booklet PDFs alone: builds, numbered steps with their
                                   sub-builds, what each step places, the parts list with each part's metadata
  4  the parts catalogue           the shared catalogue in numbers
  5  the polarity decision

  .venv-research/bin/python tests/tools/datastructure_md.py        # writes DATASTRUCTURE.md
The specification of the structure (names, rules, every field) is DATA_STRUCTURE.md; this file is the data as it is.
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import collections
import json
import pathlib


import lesson_graphs as lg
import parts_db
import lesson_record

ROOT = pathlib.Path(__file__).resolve().parents[3]
PAGE = "https://claude.ai/artifact/AHdcjWezQiNFKGDAc9v5Yt"
BOOKLETS = ("30105-1", "30055-1", "30103-1")


def cell(x, n=None):
    s = " ".join(str(x if x is not None else "").split()).replace("|", "\\|")
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


PROCESS = [
    ("1", "Match the parts list", "code", "Each item in the tutorial's parts list is matched to a catalogue part by "
     "name, aliases and model number; a generic name ('a capacitor') reuses the lessons' most-used one; a value goes on "
     "the copy (r1 {value: 220})", "", ""),
    ("2", "Review the matches (second opinion)", "Claude + check", "A separate session with the catalogue in reach: "
     "right part, another existing part, or really new", "R1 the part exists or a new id passes the naming rules; R3 "
     "the model numbers in the tutorial's name are the part's; a 'new' part is refused when the match already fits",
     "12.5 s · $0.04"),
    ("3", "Add the parts that are really new", "code, then Claude + check", "Approved shops first (Adafruit, "
     "SparkFun, Pololu…); if none has it, Claude drafts the card", "card format; naming rules N1–N6", "16 s · $0.04"),
    ("4", "Describe the new parts", "Claude + check", "Standard metadata, only for parts that have none (LEGO with a "
     "picture of the part)", "M1–M11: polarity, sizes against the 3D shape, values against the card, every value's "
     "source", "7 s · $0.02 a part"),
    ("5", "Build the circuit", "Claude + check", "From the tutorial page, with the parts settled in steps 1–4",
     "E1–E11 (no short, every LED has a resistor, every pin the sketch uses is wired…); V4 every pin it wires is on "
     "the part", "31 s · $0.05"),
    ("6", "Plan the steps", "code, then Claude + check", "Code suggests the steps with their exact holes; Claude "
     "orders, groups and writes the words, hints and troubleshooting", "lesson rules (every part placed once, holes "
     "match the circuit…)", "38 s · $0.09"),
    ("7", "Build the lesson network", "code", "The lesson record, the steps graph, the physical graph, the parts-list "
     "links, the code-to-pin links, the substitutions and the expected result", "every link resolves; every fact once",
     "5 s · free"),
    ("8", "Teach it", "Claude + code", "The tutor answers the learner through tools; the progress checker says where "
     "the learner is from what they have wired", "", ""),
]


def section0():
    return "\n\n".join([
        "## 0 · How a lesson is made: who does what",
        "Each stage is done by **code** (exact, free, repeatable), by **Claude** (reading and writing, where judgement "
        "is needed), or is a **check** by code on what Claude produced. Nothing Claude writes is stored until code has "
        "checked it. Times and costs are from the Blink and Uno WiFi Rev2 lessons.",
        table(["#", "Stage", "Who", "What", "Checked by code", "Time · cost"], PROCESS),
        "**Why the parts come first.** Everything from step 5 on is built on which part each thing is. Matched, "
        "reviewed, added and described before anything uses them, a wrong match is fixed while it is cheap and a "
        "duplicate part is never made. In the test, a \"220 ohm resistor\" given the type of a capacitor passed every "
        "code check (a capacitor also has two legs); the reviewer caught it from the tutorial's own words, and code "
        "confirmed the fix.",
        "**LEGO differs.** With a 3D model, the parts and joins come from the model by code. With only the booklet "
        "(section 3), the parts list comes from Rebrickable and Claude matches each step's new pieces to it.",
    ])


def _pilot(lid):
    view = lg.assemble(lid)
    row, g = lg._load(lid)
    rec, inst, phys = g["lesson"] or {}, g["instruction"], g["physical"]
    out = [f"### {view['title']} (`{lid}`, {view['lesson_type']})"]
    keys = [("name", rec.get("name")), ("link", rec.get("link")), ("about", rec.get("description")),
            ("how it works", rec.get("how_it_works")), ("expected result", (rec.get("expected_result") or {}).get("text")
                                                      or (rec.get("expected_result") or {}).get("summary")),
            ("troubleshooting", f"{len(rec.get('troubleshooting') or [])} entries"),
            ("graphs", ", ".join(f"{k}: {v or 'none'}" for k, v in (rec.get("graphs") or {}).items()))]
    out.append("**Lesson record** (`lesson.json`)\n\n" + table(["field", "value"], [(k, cell(v, 220)) for k, v in keys if v]))
    plist = (rec.get("parts_list") or {}).get("parts") or []
    if plist:
        out.append("**Parts list** (each row → the instances it accounts for)\n\n" + table(
            ["row", "count", "instances"], [(r.get("label") or r.get("name") or r.get("part"), r.get("count") or "",
                                             ", ".join(r.get("instances", []))) for r in plist]))
    by = collections.defaultdict(list)
    for e in inst["edges"]:
        by[e["u"]].append(e)
    rows = []
    for s in view["steps"]:
        es = by.get(s["id"], [])
        rows.append((s["id"], s["kind"], cell(s.get("text"), 140),
                     ", ".join(e["v"] for e in es if e["type"] == "PLACES"),
                     ", ".join(e["v"] for e in es if e["type"] == "MAKES"),
                     ", ".join(e["v"] for e in es if e["type"] == "DEPENDS_ON"),
                     ", ".join(e["v"] for e in es if e["type"] == "ALIGNS_WITH")))
    out.append("**Steps graph** (`instruction.json`; NEXT_STEP runs down the table)\n\n" + table(
        ["step", "kind", "text", "PLACES", "MAKES", "DEPENDS_ON", "ALIGNS_WITH"], rows))
    if phys:
        cards = lg._cards(phys["part_catalogue"])
        out.append("**Physical graph** (`physical.json`): part instances and their definitions\n\n" + table(
            ["instance", "type", "definition", "props"],
            [(n["id"], n["type"], (lg.definition(cards, n["type"])[0] or {}).get("part_type_id", "–"),
              json.dumps(n.get("props") or {})[:80]) for n in phys["nodes"]]))
        joins = [e for e in phys["edges"] if e["type"] == "joined"]
        out.append("**Joins** (one vocabulary for every domain)\n\n" + table(
            ["edge", "from", "to", "method", "holds by", "reversible"],
            [(e["id"], f"{e['u']}:{e['u_port']}", f"{e['v']}:{e['v_port']}", e.get("method"), e.get("holds_by"),
              e.get("reversible")) for e in joins[:40]]) + ("\n\n(first 40 of %d)" % len(joins) if len(joins) > 40 else ""))
    return "\n\n".join(out)


def section1():
    return "\n\n".join(["## 1 · The four subgraphs of a lesson: two pilot lessons",
                        "Each lesson is a **lesson record** that points to its graphs: the **steps**, the **physical** "
                        "part instances they gather and place, and through those the **parts catalogue**, which holds "
                        "LEGO and Arduino parts together (`metadata.domain` says which kind each is).",
                        _pilot("blink"), _pilot("2134-1")])


def section2():
    row, g = lg._load("blink")
    phys = g["physical"]
    cards = lg._cards(phys["part_catalogue"])
    nets = lesson_record.nets(phys, cards)
    return "\n\n".join(["## 2 · The Arduino circuit up close: what is connected to what",
                        "The electrical nets the joins make in Blink (breadboard strips and wires folded away, as "
                        "CircuitQuest's checker compares them).",
                        table(["net", "ports on it"], [(i + 1, ", ".join(n)) for i, n in enumerate(nets)])])


def _booklet(sid):
    lid = f"{sid}-pdf"
    row, g = lg._load(lid)
    rec, inst = g["lesson"], g["instruction"]
    checks = lg.assemble(lid)["checks"]
    reads = json.loads((ROOT / "data" / "lessons" / "booklet" / sid / "reads.json").read_text())
    key = reads.get("answer_key") or {}
    N = {n["id"]: n for n in inst["nodes"]}
    E = inst["edges"]
    rows = rec["parts_list"]["parts"]
    nxt = {e["u"]: e["v"] for e in E if e["type"] == "NEXT_STEP"}
    starts = collections.defaultdict(list)
    for e in E:
        if e["type"] == "STARTS":
            starts[e["u"]].append(e)

    def chain(first):
        out, c = [], first
        while c and c not in out:
            out.append(c)
            c = nxt.get(c)
        return out
    builds = [N[e["v"]] for e in sorted((e for e in E if e["type"] == "SHOWS"), key=lambda e: e["order"])]
    places = collections.defaultdict(list)
    for e in E:
        if e["type"] == "PLACES":
            places[e["u"]].append(e)
    steps = [n for n in inst["nodes"] if n["kind"] == "step"]
    subs = sum(1 for e in E if e["type"] == "STARTS" and N.get(e["u"], {}).get("kind") == "step")
    out = [f"### {rec['name']} (`{sid}`)",
           table(["", ""], [("ready", "yes: every piece of the parts list is placed" if checks["ready"] else
                             "no: " + "; ".join(checks["problems"][:3])),
                            ("builds", ", ".join(b["name"] for b in builds)), ("sub-builds", subs),
                            ("steps", len(steps)), ("parts list", f"{len(rows)} rows, {sum(r['count'] for r in rows)} pieces"),
                            ("order inside builds vs the set's 3D model (score only)", key.get("order_agreement")),
                            ("3D model pieces matched to a step", f"{key.get('matched_to_a_booklet_step')}/{key.get('model_pieces')}"),
                            ("made in", f"{round(rec['stats']['seconds'])} s, ${rec['stats']['cost_usd']:.2f}, "
                                        f"{rec['stats']['calls']} Claude calls"),
                            ("to review", "; ".join(checks["review"]) or "nothing")])]
    # the structure as a diagram: one kind of arrow per edge type, all solid
    m = ["```mermaid", "flowchart TD", '  ov["overview · the first step"]']
    for b in builds:
        bid = b["id"].replace(":", "_").replace("-", "_")
        m.append(f'  {bid}[["{b["name"]} ({b["role"]})"]]')
        m.append(f'  ov -->|SHOWS| {bid}')
        ms = chain((starts[b["id"]] or [{}])[0].get("v"))
        prev = bid
        for i, s in enumerate(ms):
            sid_ = s.replace(".", "_").replace("-", "_")
            m.append(f'  {sid_}["{s}"]')
            m.append(f'  {prev} -->|{"STARTS" if i == 0 else "NEXT_STEP"}| {sid_}')
            prev = sid_
            for st in starts.get(s, []):
                sc = chain(st["v"])
                label = st["name"] + (f" · {st['times']}x" if st.get("times", 1) > 1 else "")
                m.append(f'  subgraph sb_{sid_}["sub-build · {label}"]')
                for x in sc:
                    m.append(f'    {x.replace(".", "_").replace("-", "_")}["{x}"]')
                m.append("  end")
                m.append(f'  {sid_} -->|STARTS| {sc[0].replace(".", "_").replace("-", "_")}')
                for a, c in zip(sc, sc[1:]):
                    m.append(f'  {a.replace(".", "_").replace("-", "_")} -->|NEXT_STEP| {c.replace(".", "_").replace("-", "_")}')
    m.append("```")
    out.append("**Structure** (`instruction.json`): SHOWS, STARTS and NEXT_STEP; a sub-build's steps inside the main "
               "step that needs it\n\n" + "\n".join(m))

    def step_row(s, sub=None):
        n = N[s]
        pl = "; ".join(f"{e['count']}× #{int(e['v'].split('/')[-1]) + 1} {rows[int(e['v'].split('/')[-1])]['name']} "
                       f"({rows[int(e['v'].split('/')[-1])]['colour']})" for e in places[s]) or "—"
        flags = "; ".join((n.get("problems") or []) + [f"added by a repair: {x}" for x in n.get("added_by_repair") or []])
        return (f"`{s}`" + (f" ({sub})" if sub else ""), f"[picture]({n['source']['picture']})" +
                (f" · [overlay]({n['source']['overlay']})" if n["source"].get("overlay") else ""),
                cell(n["text"], 260), cell(n.get("what_changed"), 200), pl, flags or "—")
    for b in builds:
        ms = chain((starts[b["id"]] or [{}])[0].get("v"))
        trs = []
        for s in ms:
            for st in starts.get(s, []):
                label = st["name"] + (f", {st['times']}x" if st.get("times", 1) > 1 else "")
                trs += [step_row(x, f"sub-build {label}") for x in chain(st["v"])]
            trs.append(step_row(s))
        out.append(f"**{b['name']}** ({b['role']}; finished: {cell(b['result'].get('description'), 300)})\n\n" + table(
            ["step", "booklet", "instruction", "what changed", "places (PLACES → parts list)", "review"], trs))
    parts = parts_db.load()
    cards = lg._cards(lg.PARTS)
    prow = []
    for i, r in enumerate(rows):
        c, how = lg.definition(cards, r["part"])
        md = ((parts.get(c["part_type_id"]) if c else {}) or {}).get("metadata", {})
        sp = md.get("specs") or {}
        placed = sum(e["count"] for e in E if e["type"] == "PLACES" and e["v"] == f"lesson:parts_list/{i}")
        prow.append((f"#{i + 1}", r["part"], r["colour"], cell(r["name"], 60), r["count"], f"{placed}/{r['count']}",
                     ", ".join(f"`{x}`" for x in r["steps"]), c and c["part_type_id"], cell(md.get("description"), 160),
                     " × ".join(map(str, md.get("size_studs") or [])), f"{sp.get('stud_count', '')} / {sp.get('anti_stud_count', '')}",
                     "; ".join(c["rule"] for c in md.get("checks_failed") or []) or "passed"))
    out.append("**Parts list** (`lesson.json` → `parts.json`): each row, the steps that place it, and the part's card "
               "and metadata\n\n" + table(["#", "part", "colour", "name", "count", "placed", "placed by", "card",
                                           "description", "size", "studs / anti-studs", "metadata checks"], prow))
    return "\n\n".join(out)


def section3():
    return "\n\n".join([
        "## 3 · Booklet lessons: builds, sub-builds, steps and parts",
        "Three LEGO lessons made from their booklet PDFs alone (no 3D model used to build them). Each is a **lesson "
        "record** and a **steps graph**; there is no physical graph. Code cut the steps from the PDF (the booklet's "
        "layout: builds, main steps, boxed sub-builds and their \"2x\"), made an overlay of what changed in each, found "
        "the arrows, and measured the new area per colour; Claude read each step with its previous picture, the "
        "overlay and a numbered picture of every part; code checked every read, repaired leftovers, and checked that "
        "every piece of the parts list is placed.",
        "- `overview` (the first step) **SHOWS** each build, in the booklet's order.\n"
        "- Each build (`product` node: a model, or a figure built on its own) **STARTS** at its own step 1; "
        "**NEXT_STEP** runs only inside one build or one sub-build.\n"
        "- Steps are numbered as the booklet: `flower-stand-7`; a sub-build's steps are inside the main step that needs "
        "it: `flower-stand-7.1`. The main step **STARTS** its sub-build (the edge carries its name and \"2x\"), and "
        "the sub-build is done just before the step.\n"
        "- **PLACES** step → parts-list row, with a count (times the sub-build's 2x) and where it goes.\n"
        "- Which build a step is in, and the whole order, are worked out from these edges; nothing is stored twice.",
    ] + [_booklet(s) for s in BOOKLETS])


def section4():
    parts = parts_db.load()
    dom = collections.Counter(p["metadata"].get("domain") for p in parts.values())
    meta = collections.Counter(p["metadata"].get("domain") for p in parts.values() if p["metadata"].get("description"))
    pol = collections.Counter(p["metadata"].get("domain") for p in parts.values()
                              if (p.get("intrinsic_behaviour") or {}).get("is_polarized"))
    cats = collections.Counter((p["metadata"].get("domain"), p.get("category")) for p in parts.values())
    rows = [(d, dom[d], meta[d], pol[d]) for d in sorted(dom)]
    top = sorted(cats.items(), key=lambda kv: -kv[1])[:16]
    return "\n\n".join([
        "## 4 · The parts catalogue (`code/graph/parts/parts.json`)",
        f"One catalogue, {len(parts):,} parts, LEGO and Arduino together; each part's `metadata.domain` says which "
        "kind it is, and its drafted metadata (standard fields, every value's source named) sits beside its card.",
        table(["domain", "parts", "with drafted metadata", "polarized"], rows),
        "**Most common categories**\n\n" + table(["domain", "category", "parts"], [(d, c, n) for (d, c), n in top]),
        "**Substitutes: what can be swapped, and where it is stored**\n\n" + table(
            ["level", "stored in", "example"],
            [("a copy of a part: what it may differ in and still be right", "`parts.json` → the part's "
              "`metadata.substitutes` (from `SUBSTITUTES` in `graph/parts/parts_db.py`)",
              f"{sum(1 for v in parts.values() if v['metadata'].get('substitutes'))} parts; `led`: colour free; "
              "`jumper-wire`: colour and length; `resistor`: value by role; every LEGO part: colour free"),
             ("this lesson's instances (worked out for its circuit)", "the lesson's `lesson.json` → "
              "`substitutions.parts`", "Blink: `r1` 150-600 ohm, in series with the LED: (5 V - 2 V) / 5-20 mA"),
             ("pins the code's pin may move to", "the lesson's `lesson.json` → `substitutions.pins`, from the "
              "board card's pin facts in `parts.json` (`can`, `same_as`, `reserved`; `graph/arduino/pins.py`) and the sketch",
              "Blink: `uno:13` → 2-12, A0-A5; 0 and 1 refused (USB upload and Serial)"),
             ("what a port can go into or onto", "`parts.json` → the part's `metadata.fits` (by code, from "
              "`FITS` in `graph/joins.py`): each port kind → the other port's kind, method, what holds it, how it "
              "is undone, example parts", "`resistor` lead → breadboard hole, header socket, female jumper end or "
              "clip, screw terminal (tool), solder pad (tool)"),
             ("ports that stand in for each other", "`parts.json` → the part's `metadata.interchangeable` (by code: "
              "a part that is not polarized, pins marked the same, groups joined inside, a breadboard's strip rule)",
              "groups `{kind, ports, why}`: `resistor` not-polarized [1, 2]; `arduino-uno` same-pin [GND.1, GND.2, "
              "GND.3]; `breadboard` 126 strips such as [12t.a … 12t.e] and 4 rails [tp.1 … tp.63]; never an `led`'s "
              "legs (polarized). `parts_db.swaps('breadboard', '12t.c')` → 12t.a, 12t.b, 12t.d, 12t.e"),
             ("the same part under two names (identity, not a swap)", "`naming.SAME_PART` (packaging; revisions are "
              "other hardware), `lego_ids.same_part` (a print or mould of the same design)", "`lego-3003pr0053` is "
              "`lego-3003`")]) + "\n\nNot stored yet: a part for another part (two 1 x 2 plates for one 2 x 2), "
        "and lesson-level substitutions for booklet lessons (they use the part-level colour rule only)."])


FULL = ("resistor", "led", "arduino-uno", "breadboard", "lego-3069b")


def part_card(t, parts):
    """One part with every field it has: the card (identity, ports, behaviour, electrical) and its metadata."""
    v = parts[t]
    m = v.get("metadata") or {}
    ib = v.get("intrinsic_behaviour") or {}
    ports = v.get("ports") or []
    kinds = collections.Counter(p["kind"] for p in ports)
    sp = {k: x for k, x in (m.get("specs") or {}).items() if x not in (None, [], ["none"])}
    rows = [("id · name", f"`{t}` · {v.get('display_name')}"), ("domain · category", f"{m.get('domain')} · {v.get('category')}"),
            ("aliases", ", ".join(v.get("aliases") or []) or "–"),
            ("description", m.get("description")),
            ("material", " ".join(f"`{x}`" for x in m.get("material") or []) + (f" ({m['material_text']})" if m.get("material_text") else "")),
            ("size", " · ".join(x for x in (" × ".join(map(str, m.get("size_studs") or [])) + (" studs" if m.get("size_studs") else ""),
                                             " × ".join(map(str, m.get("dimensions_mm") or [])) + (" mm" if m.get("dimensions_mm") else "")) if x) or "–"),
            ("ports", f"{len(ports)}: " + ", ".join(f"{n} {k}" for k, n in kinds.items()) +
             ("" if len(ports) > 12 else " (" + ", ".join(p["id"] for p in ports) + ")")),
            ("port names", v.get("port_rule") or v.get("port_alias_rule") or "–"),
            ("polarized", "yes: say which way round" if ib.get("is_polarized") else "no: either way round"),
            ("if power is reversed", f"`{m.get('reverse_power')}`" if m.get("reverse_power") else "–"),
            ("rotation symmetry", f"{ib.get('rotation_symmetry_deg')}°" if ib.get("rotation_symmetry_deg") else "–"),
            ("connected inside", "; ".join("-".join(g) for g in ib.get("internal_conducts") or []) or "–"),
            ("electrical", json.dumps(v.get("electrical")) if v.get("electrical") else "–"),
            ("specifications", "; ".join(f"{k} {x}" + (f" ({m['basis'][k]})" if (m.get("basis") or {}).get(k) else "")
                                         for k, x in sp.items()) or "–"),
            ("connect by", "; ".join(f"`{w['way']}` {w['text']}" for w in m.get("connect_by") or []) or "–"),
            ("takes (into its sockets, holes, terminals)", "; ".join(f"`{w['what']}` {w['text']}" for w in m.get("takes") or []) or "–"),
            ("fits", "; ".join(f"{k} → " + ", ".join(f"{r['with']} ({r['method']}, {r['holds_by']}, undo by "
                                                     f"{r['reversible']})" for r in rows_)
                               for k, rows_ in (m.get("fits") or {}).items()) or "–"),
            ("joins (drafted, as codes)", "; ".join(f"`{j.get('port_kind')}` → " + ", ".join(f"`{x}`" for x in j.get("mates") or [])
                                                   + f" (`{j.get('method')}`, `{j.get('holds_by')}`, undo `{j.get('reversible')}`)"
                                                   for j in m.get("joins") or []) or "–"),
            ("interchangeable ports (groups)", (lambda gs: "; ".join(f"`{g['kind']}` " + ", ".join(g["ports"]) for g in gs[:6])
                                                 + (f"; … {len(gs)} groups in all (" + ", ".join(f"{n} {k}" for k, n in
                                                     collections.Counter(g['kind'] for g in gs).items()) + ")" if len(gs) > 6 else ""))
             (m.get("interchangeable") or []) or "–"),
            ("substitutes (a copy may differ in)", json.dumps(m.get("substitutes")) if m.get("substitutes") else "–"),
            ("tips for the learner", " · ".join(m.get("learner_tips") or []) or "–"),
            ("card made by · metadata", f"`{m.get('card_made_by')}` · `{m.get('status')}`"
                                        f"{', confidence ' + str(m['confidence']) if m.get('confidence') is not None else ''}"),
            ("metadata checks", "; ".join(f"{c['rule']}: {c['message']}" for c in m.get("checks_failed") or []) or "all passed")]
    return f"#### `{t}`\n\n" + table(["field", "value"], rows)


def section4b():
    parts = parts_db.load()
    return "\n\n".join(["### A part, in full",
                         "Every field one part carries: its card (identity, ports, behaviour, electrical values) and "
                         "its metadata (drafted by Claude in the standard fields, each value's source named, checked "
                         "by code), plus the fields code works out: what it fits, how a learner can connect it, which "
                         "ports can swap, and what a copy may differ in."] +
                        [part_card(t, parts) for t in FULL if t in parts])


def section5():
    d = json.loads((ROOT / "code" / "graph" / "parts" / "arduino" / "polarity_decision.json").read_text())
    return "\n\n".join([
        "## 5 · What \"polarized\" means (decided " + str(d.get("date")) + ")",
        "**Definition:** " + cell(d.get("definition")),
        "**Why:** " + cell(d.get("why")),
        f"Under this definition the cards that were already marked polarized were all kept, and {len(d['changed'])} "
        f"cards marked not polarized but able to be fitted backwards were changed: " +
        ", ".join(f"`{c}`" for c in d["changed"][:60]) + (" …" if len(d["changed"]) > 60 else "")])


def main():
    text = "\n\n".join([
        "# Pinpoint Lesson Data",
        f"The data behind Pinpoint's lessons, as it is stored, section by section as on the shared page: {PAGE} "
        "(private until shared from its Share menu). Written from the lesson store by "
        "`python tests/tools/datastructure_md.py`; the specification of the structure (names, rules, every field) is "
        "[`DATA_STRUCTURE.md`](./DATA_STRUCTURE.md), and the research behind it is "
        "[`RESEARCH.md`](./RESEARCH.md) (R25, R26).",
        "**Contents:** 0 how a lesson is made · 1 the four subgraphs of a lesson (Blink, LEGO 2134-1) · 2 the Arduino "
        "circuit up close · 3 booklet lessons (Stephanie and Mailbox, Vulture Droid, Car) · 4 the parts catalogue · 5 "
        "the polarity decision",
        section0(), section1(), section2(), section3(), section4(), section4b(), section5()])
    (ROOT / "DATASTRUCTURE.md").write_text(text + "\n")
    print(f"DATASTRUCTURE.md: {len(text.splitlines())} lines")


if __name__ == "__main__":
    main()
