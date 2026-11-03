"""Code's check of every stored lesson and every part.

What it is   the level 1 validator: does every lesson in the store and every part in the catalogue follow the data
             structure's own rules? Code only, no Claude.
Used for     finding a lesson or part that breaks the structure after a change (a new rule, a batch of new lessons),
             before it reaches a learner.
Where        the command line: python -m graph.validate_store (report: data/validation/report.json and .md).
             Reads data/lessons/store (lesson_store.py) and parts/parts.json (parts/part_catalogue.py).

Lessons (every row of the lesson catalogue)
  L1  the record has its required fields, and every graph it lists is there
  L2  the assembler's checks: every link resolves, every fact once, every piece of the parts list placed, the code's
      pins wired
  L3  the order (lesson_store._order) reaches every step exactly once
  L4  step ids follow the naming: `step-3`, `gather`, `upload-code`; a booklet's `flower-stand-7`, `flower-stand-7.1`
  L5  only known node kinds and edge types, with the fields an edge type needs
  L6  every part the lesson uses has a card and metadata
Parts (every part of the catalogue, parts.json)
  P1  only known metadata fields (part_metadata.FIELDS)
  P2  every code field holds codes of the vocabulary (the vocabulary in parts/part_metadata.py): material, reverse_power, basis, joins, specs,
      interchangeable, connect_by, takes, status
  P3  the card's port kinds are known (part_metadata.PORT_KINDS)
  P4  a described part has every drafted field it needs (description, polarized, reverse_power, specs, basis, joins)
  P5  an electronics part with ports has what code works out (fits, connect_by or takes, interchangeable)
  P6  its id follows the naming pattern: lowercase words and numbers with hyphens; LEGO parts `lego-<number>`
  P8  an electronics part (not a consumable, cable or tool) has pins
  P7  no two electronics cards are the same part under two ids (naming N7: one shop page, or one model number)

  .venv-research/bin/python -m graph.validate_store        # report: data/validation/report.{json,md}
"""
import collections
import json
import pathlib
import re
import time

from graph import lesson_store
from graph.parts import part_metadata
from graph.parts import part_catalogue

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "validation"

RECORD_FIELDS = ("lesson_id", "name", "lesson_type", "source", "graphs")
NODE_KINDS = set(lesson_store.STEP_KINDS) | {"product", "subassembly", "lesson", "part", "board"}
INSTRUCTION_EDGES = {  # edge type -> the fields it must carry
    "NEXT_STEP": (), "PLACES": (), "MAKES": (), "DEPENDS_ON": (), "ALIGNS_WITH": (), "CHECK_NEEDS": (),
    "GATHERS": (), "PROGRAMS": (), "BUILDS": (), "ATTACHES": (), "FIRST_STEP": (), "USES": (),
    "SHOWS": ("order",), "STARTS": ()}
PHYSICAL_EDGES = {"joined": ("u_port", "v_port"), "contact": (), "electrical": ("u_port", "v_port")}
STEP_ID = re.compile(r"^(step-\d+|gather|upload-code|overview|[a-z0-9]+(-[a-z0-9]+)*-\d+(\.\d+)?)$")
PART_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LEGO_ID = re.compile(r"^lego-[0-9a-z]+$")


def _codes(field, values, allowed, out, where=""):
    bad = [v for v in (values if isinstance(values, list) else [values]) if v is not None and v not in allowed]
    if bad:
        out.append(("P2", f"{where}{field}: {', '.join(map(str, bad))} not in the vocabulary"))


def part(t, v):
    """[(rule, message)] for one part of the catalogue."""
    out = []
    m = v.get("metadata") or {}
    unknown = sorted(set(m) - set(part_metadata.FIELDS))
    if unknown:
        out.append(("P1", f"metadata fields not in the structure: {', '.join(unknown)}"))
    for f, allowed in part_metadata.CODES.items():
        if f in m:
            _codes(f, m[f], allowed, out)
    if m.get("size_studs") is not None and not (isinstance(m["size_studs"], list) and len(m["size_studs"]) == 2
                                                and all(isinstance(x, int) for x in m["size_studs"])):
        out.append(("P2", f"size_studs is {m['size_studs']!r}, not [w, l] studs"))
    for k, b in (m.get("basis") or {}).items():
        _codes("basis", b, part_metadata.BASIS_CODES, out, f"{k} ")
    sp = m.get("specs") or {}
    _codes("specs.interface", sp.get("interface") or [], part_metadata.INTERFACES, out)
    _codes("specs.wireless", sp.get("wireless") or [], part_metadata.WIRELESS, out)
    for i, j in enumerate(m.get("joins") or []):
        if "mates_with" in j:
            out.append(("P2", f"joins[{i}] has free text mates_with, not mates codes"))
        _codes("port_kind", j.get("port_kind"), part_metadata.PORT_KINDS, out, f"joins[{i}].")
        _codes("mates", j.get("mates") or [], part_metadata.MATES_CODES, out, f"joins[{i}].")
        _codes("method", j.get("method"), part_metadata.JOIN_METHODS, out, f"joins[{i}].")
        _codes("holds_by", j.get("holds_by"), part_metadata.HOLDS_BY_CODES, out, f"joins[{i}].")
        _codes("reversible", j.get("reversible"), part_metadata.REVERSIBLE_CODES, out, f"joins[{i}].")
    for k, rows in (m.get("fits") or {}).items():
        _codes("fits", k, part_metadata.PORT_KINDS, out)
        for r in rows:
            _codes("fits.with", r.get("with"), part_metadata.PORT_KINDS, out, f"{k} ")
            _codes("fits.method", r.get("method"), part_metadata.JOIN_METHODS, out, f"{k} ")
            _codes("fits.holds_by", r.get("holds_by"), part_metadata.HOLDS_BY_CODES, out, f"{k} ")
            _codes("fits.reversible", r.get("reversible"), part_metadata.REVERSIBLE_CODES, out, f"{k} ")
    for g in m.get("interchangeable") or []:
        _codes("interchangeable.kind", g.get("kind"), part_metadata.SWAP_KINDS, out)
    for w in m.get("connect_by") or []:
        _codes("connect_by.way", w.get("way"), part_metadata.CONNECT_WAYS, out)
        _codes("connect_by.tool", w.get("tool"), part_metadata.TOOLS, out)
    for w in m.get("takes") or []:
        _codes("takes.what", w.get("what"), part_metadata.TAKES, out)
    for c in m.get("checks_failed") or []:
        if not isinstance(c, dict):
            out.append(("P2", f"checks_failed holds text, not {{rule, message}}: {str(c)[:60]}"))
    _codes("port kinds", sorted({p["kind"] for p in v.get("ports") or [] if "<" not in p.get("id", "")} |
                                {p["kind"] for p in v.get("ports") or [] if "<" in p.get("id", "")}),
           part_metadata.PORT_KINDS, out)
    if out and out[-1][1].startswith("port kinds"):
        out[-1] = ("P3", out[-1][1])
    if m.get("description"):
        need = [f for f in ("polarized", "reverse_power", "specs", "basis", "joins", "material") if f not in m]
        if need:
            out.append(("P4", f"described, but without {', '.join(need)}"))
    if m.get("domain") == "arduino" and v.get("ports"):
        need = [f for f in ("fits", "interchangeable") if f not in m]
        if not (m.get("connect_by") or m.get("takes")) and m.get("fits"):
            need.append("connect_by or takes")
        if need:
            out.append(("P5", f"electronics part without {', '.join(need)}"))
    if not PART_ID.match(t) or (m.get("domain") == "lego" and not LEGO_ID.match(t)):
        out.append(("P6", f"id {t!r} does not follow the naming pattern"))
    if m.get("domain") == "arduino" and not v.get("ports") and not v.get("port_rule") and \
            str(v.get("category") or "").lower() not in ("consumable", "cable", "tool", "tools"):
        out.append(("P8", "an electronics part with no pins: no lesson can say which leg goes where (graph/parts/arduino/pinouts.py)"))
    return out


def lesson(lid, row):
    """[(rule, message)] for one lesson of the store."""
    out = []
    try:
        info, g = lesson_store._load(lid)
    except Exception as e:
        return [("L1", f"cannot be loaded: {e}")]
    rec, inst, phys = g.get("lesson") or {}, g.get("instruction"), g.get("physical")
    miss = [f for f in RECORD_FIELDS if not rec.get(f)]
    if miss:
        out.append(("L1", f"the record lacks {', '.join(miss)}"))
    for k, p in (rec.get("graphs") or {}).items():
        if p and not (lesson_store.STORE / p).exists():
            out.append(("L1", f"the {k} graph {p} is missing"))
    try:
        checks = lesson_store.assemble(lid)["checks"]
        out += [("L2", p) for p in checks["problems"]]
    except Exception as e:
        out.append(("L2", f"the assembler fails: {e}"))
    if inst:
        steps = [n["id"] for n in inst["nodes"] if n["kind"] in lesson_store.STEP_KINDS]
        order = lesson_store._order(inst)
        if sorted(order) != sorted(steps) or len(order) != len(set(order)):
            lost = sorted(set(steps) - set(order))
            out.append(("L3", f"the order reaches {len(set(order))} of {len(steps)} steps"
                              + (f" (not: {', '.join(lost[:6])})" if lost else "")))
        bad = [s for s in steps if not STEP_ID.match(s)]
        if bad:
            out.append(("L4", f"step ids not in the naming: {', '.join(bad[:6])}"))
        kinds = {n["kind"] for n in inst["nodes"]} - NODE_KINDS
        if kinds:
            out.append(("L5", f"node kinds not in the structure: {', '.join(sorted(kinds))}"))
        for e in inst["edges"]:
            if e["type"] not in INSTRUCTION_EDGES:
                out.append(("L5", f"edge type {e['type']} is not in the structure"))
            elif [f for f in INSTRUCTION_EDGES[e["type"]] if f not in e]:
                out.append(("L5", f"{e['type']} {e['u']} -> {e['v']} lacks {INSTRUCTION_EDGES[e['type']]}"))
    if phys:
        for e in phys["edges"]:
            if e["type"] not in PHYSICAL_EDGES:
                out.append(("L5", f"physical edge type {e['type']} is not in the structure"))
    cards = lesson_store._cards(lesson_store.PARTS)
    parts = part_catalogue.load()
    types = {n["type"] for n in (phys or {}).get("nodes", [])}
    types |= {r["part"] for r in (rec.get("parts_list") or {}).get("parts", []) if r.get("part")}
    nocard, nometa = [], []
    for t in sorted(types):
        c, _ = lesson_store.definition(cards, t)
        if not c:
            nocard.append(t)
        elif not ((parts.get(c["part_type_id"]) or {}).get("metadata") or {}).get("description"):
            nometa.append(c["part_type_id"])
    if nocard:
        out.append(("L6", f"parts with no card: {', '.join(nocard[:8])}"))
    if nometa:
        out.append(("L6", f"parts with no metadata: {', '.join(sorted(set(nometa))[:8])}"
                          + (f" (+{len(set(nometa)) - 8})" if len(set(nometa)) > 8 else "")))
    return out


def run():
    t0 = time.monotonic()
    lessons = {}
    for row in json.loads((lesson_store.STORE / "catalogue.json").read_text())["lessons"]:
        lessons[row["lesson_id"]] = {"type": row.get("lesson_type"), "issues": lesson(row["lesson_id"], row)}
    parts = {}
    for t, v in part_catalogue.load().items():
        found = part(t, v)
        if found:
            parts[t] = found
    from graph.parts import naming  # P7: a card that is another card by its model number (a part under two ids), for review
    from graph.parts.cards import CardStore
    store = CardStore(ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json")
    for t, card in sorted(store.cards.items()):
        hit = naming._same_model(t, card.get("display_name"), store)
        page = naming.same_page(t, card, store)
        if hit:
            parts.setdefault(t, []).append(("P7", f"is '{hit[0]}' by its model {hit[1]} (a part under two ids?)"))
        elif page:
            parts.setdefault(t, []).append(("P7", f"is made from the shop page of '{page}' (a part under two ids?)"))
    rules = collections.Counter(r for x in lessons.values() for r, _ in x["issues"])
    rules.update(r for x in parts.values() for r, _ in x)
    report = {"date": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.monotonic() - t0, 1),
              "lessons": {"checked": len(lessons), "valid": sum(1 for x in lessons.values() if not x["issues"])},
              "parts": {"checked": len(part_catalogue.load()), "valid": len(part_catalogue.load()) - len(parts)},
              "by_rule": dict(sorted(rules.items())), "lesson_issues": {k: v for k, v in lessons.items() if v["issues"]},
              "part_issues": parts}
    return report


def validation_md(r):
    lines = [f"# Level 1 validation ({r['date']})", "",
             f"Lessons: **{r['lessons']['valid']}/{r['lessons']['checked']}** valid · parts: "
             f"**{r['parts']['valid']}/{r['parts']['checked']}** valid · {r['seconds']} s", "",
             "| rule | issues |", "|---|---|"] + [f"| {k} | {n} |" for k, n in r["by_rule"].items()] + ["", "## Lessons", ""]
    for lid, x in r["lesson_issues"].items():
        lines.append(f"- **{lid}** ({x['type']}): " + "; ".join(f"{a} {b}" for a, b in x["issues"]))
    lines += ["", "## Parts", ""]
    for t, xs in sorted(r["part_issues"].items()):
        lines.append(f"- `{t}`: " + "; ".join(f"{a} {b}" for a, b in xs))
    return "\n".join(lines) + "\n"


def validate_main():
    r = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(r, indent=1))
    (OUT / "report.md").write_text(validation_md(r))
    print(f"lessons {r['lessons']['valid']}/{r['lessons']['checked']} valid · parts {r['parts']['valid']}/"
          f"{r['parts']['checked']} valid · {r['seconds']} s · by rule {r['by_rule']}")
    for lid, x in r["lesson_issues"].items():
        print(f"  {lid}: " + "; ".join(f"{a} {b}"[:150] for a, b in x["issues"][:4]))
    shown = collections.Counter()
    for t, xs in r["part_issues"].items():
        for a, b in xs:
            shown[(a, re.sub(r"\[\d+\]", "[i]", b)[:90])] += 1
    for (a, b), n in shown.most_common(20):
        print(f"  {n:4} × {a} {b}")
