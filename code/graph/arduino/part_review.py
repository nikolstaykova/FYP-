"""A second look at a new lesson's parts, before the lesson is built.

What it is   a separate Claude reviews every part's type with the catalogue in reach; code checks what it proposes
             (R1-R4 below). parts_first does this for the tutorial's parts list before the circuit is read
             (DATA_STRUCTURE.md §4.4).
Used for     making sure every part of an Arduino lesson is the right catalogue part (not a look-alike, not a new id
             for a part we have), since a lesson is made once.
Where        arduino/circuit_lesson.py (parts_first); on its own: python -m graph.arduino.part_review <lesson>
             [--apply]; writes data/part_review/<lesson>.json.

  1. code     each instance: the lesson's own name for it (the label), its assigned type, the ports it uses, the step
              that places it, and what the lesson says about it
  2. Claude   a fresh session with read-only tools over the catalogue (tutor_mcp: search_parts, part) and the
              lesson; for every instance: confirm the type, change it to an existing type, or say the part is new
  3. code     every answer is checked before it counts:
                R1  the type exists in the catalogue (a new one passes the naming rules and is not a catalogue part)
                R2  the type has every port the lesson's joins use on that instance
                R3  the model numbers in the lesson's own name are in the type's names, aliases or model
                R4  a plain part ('8 x LED, green') is the catalogue's plain part ('led'), not a product with that word
                R4  where the reviewer and the assigned type disagree, each side is checked the same way, and the
                    disagreement is reported with both results; nothing is changed without --apply
Output: data/part_review/<lesson>.json

  .venv-research/bin/python -m graph.arduino.part_review docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver [--apply]
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from typing import List, Literal

from pydantic import BaseModel, Field

from graph import lesson_store
from graph.parts import naming

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "part_review"


class Verdict(BaseModel):
    instance: str
    verdict: Literal["confirm", "change", "new"]
    type_id: str = Field(description="the type it should have: the assigned one (confirm), an existing catalogue type "
                                     "(change), or a new id by the naming rules (new)")
    evidence: str = Field(description="what in the catalogue or its metadata settles it (a model, chip, alias, ports)")
    confidence: float = Field(ge=0, le=1)


class Review(BaseModel):
    verdicts: List[Verdict]


SYSTEM = """You review the parts of a new build lesson before it is published. For every part instance you get the
lesson's own name for it, the type the lesson builder gave it, and the ports the lesson's connections use on it.
Check each one against the parts catalogue with your tools (search_parts, part): is the assigned type really this
part? Look at what tells similar parts apart (maker, model, chip, ports). Then answer for every instance:
- confirm: the assigned type is right
- change: a different type already in the catalogue is right (give its type id)
- new: the catalogue has no such part (give an id by the naming rules below)
Prefer a catalogue type whenever one is this part. A part the lesson names only generically ("resistor", "a motor")
is never new: it is the catalogue's part of that kind (search for it), with any value in its props. Say what
settles it in `evidence`.

""" + naming.RULES


def _instances(lesson_id):
    row, g = lesson_store._load(lesson_id)
    phys, inst, rec = g["physical"], g["instruction"], g["lesson"] or {}
    steps = {n["id"]: n for n in inst["nodes"]}
    out = []
    for n in phys["nodes"]:
        used = sorted({e["u_port"] for e in phys["edges"] if e["u"] == n["id"] and e.get("u_port")} |
                      {e["v_port"] for e in phys["edges"] if e["v"] == n["id"] and e.get("v_port")})
        placer = next((e["u"] for e in inst["edges"] if e["type"] == "PLACES" and e["v"] == n["id"]), None)
        out.append({"instance": n["id"], "lesson_name": n.get("label"), "assigned_type": n["type"],
                    "props": {k: v for k, v in (n.get("props") or {}).items() if k in ("colour", "value")},
                    "ports_used": used[:40], "placed_by": placer,
                    "step_text": (steps.get(placer) or {}).get("text", "")[:300]})
    return rec, out


FILLER = {"x", "additional", "extra", "more", "another", "a", "an", "the", "of", "one", "two", "total", "each", "pcs",
          "red", "green", "blue", "yellow", "white", "orange", "black", "purple", "pink", "clear", "warm", "cool"}


def _core(name):
    """An item's own words, without counts, colours, brackets and filler ('8 x additional LED, green (Example 2)' ->
    ['led']): a single word left that is a catalogue id names a plain part (R4)."""
    name = re.sub(r"\([^)]*\)", " ", name.lower())
    return [w for w in re.findall(r"[a-z][a-z0-9-]*", name) if w not in FILLER]


def check_type(type_id, item, store):
    """R1-R3 for one type on one instance: [problem]."""
    cards = lesson_store._cards(lesson_store.PARTS)
    card, how = lesson_store.definition(cards, type_id)
    out = []
    if card is None:
        out += [f"R1 {type_id}: {m}" for r, m in naming.check([{"type": type_id, "name": item["lesson_name"]}], store)]
        if not out:
            return ["(new part: passes the naming rules)"]
        return out
    names = {p["id"] for p in card.get("ports", [])}
    missing = [p for p in item["ports_used"] if lesson_store.port_match(card, p) is None]
    if missing:
        out.append(f"R2 {type_id} has no port {', '.join(missing)} (the lesson uses them)")
    sp = (card.get("metadata") or {}).get("specs") or {}
    terms = " ".join([card["part_type_id"], card.get("display_name", ""), *card.get("aliases", []), str(sp.get("model") or ""),
                      str(sp.get("chip") or "")]).lower()
    value = str((item.get("props") or {}).get("value") or "")
    models = set() if card.get("category") in naming.VALUE_PARTS else {  # a resistor's 220 is its value, not a model
        w for w in re.findall(r"[a-z0-9]+", (item["lesson_name"] or "").lower())
        if re.search(r"\d", w) and re.search(r"[a-z]", w) and not naming.VALUE.match(w) and len(w) > 1 and w != value}
    # (a model number has letters and digits: dht11, 74hc595; a bare number is a count, '16 total')
    core = _core(item["lesson_name"] or "")
    if len(core) == 1 and core[0] in cards and type_id != core[0] and lesson_store.definition(cards, core[0])[0] is not card:
        out.append(f"R4 the lesson calls it a plain '{core[0]}' ({item['lesson_name']}): use the catalogue's "
                   f"'{core[0]}', with any colour or value as a property, not {type_id} ({card.get('display_name')})")
    absent = [m for m in models if m not in terms.replace("-", " ") and m not in terms]
    if absent and len(absent) < len(models) and re.search(r"\bor\b|/", (item["lesson_name"] or "").lower()):
        absent = []  # the lesson offers alternatives ('ATmega168 or ATmega328'): one of them is enough
    if absent:
        out.append(f"R3 the lesson calls it '{item['lesson_name']}', but {', '.join(absent)} is not in {type_id}'s names, "
                   f"model or chip")
    return out


def _ask(ask, system, schema, model="sonnet", effort="high"):
    """One reviewer session: claude -p with read-only catalogue tools (tutor_mcp search_parts, part).
    Returns (the result event with structured_output, [tool names used])."""
    cfg = {"mcpServers": {"lessons": {"command": sys.executable, "args": ["-m", "graph.tutor_mcp"],
                                      "env": {"PYTHONPATH": str(ROOT)}, "cwd": str(ROOT)}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(json.dumps(cfg))
        mcp = f.name
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                                                            "CLAUDE_CODE_CHILD_SESSION")}
    proc = subprocess.run(["claude", "-p", ask, "--output-format", "stream-json", "--verbose", "--model", model,
                           "--effort", effort, "--no-session-persistence", "--tools", "", "--mcp-config", mcp,
                           "--strict-mcp-config", "--allowedTools", "mcp__lessons__search_parts", "mcp__lessons__part",
                           "--system-prompt", system, "--json-schema", json.dumps(schema.model_json_schema())],
                          capture_output=True, text=True, env=env, timeout=900, cwd=str(ROOT))
    os.unlink(mcp)
    result, tools = None, []
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            tools += [c["name"].split("__")[-1] for c in ev["message"].get("content", []) if c.get("type") == "tool_use"]
        if ev.get("type") == "result":
            result = ev
    if not result or not result.get("structured_output"):
        raise RuntimeError(f"review failed: {(result or {}).get('result') or proc.stderr[-300:]}")
    return result, tools


def review(lesson_id, model="sonnet", effort="high"):
    from graph.parts.cards import CardStore
    store = CardStore(ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json")
    rec, items = _instances(lesson_id)
    ask = (f"Lesson {lesson_id}: {rec.get('name')} ({rec.get('link')}).\nINSTANCES:\n" +
           "\n".join(json.dumps(i) for i in items))
    t0 = time.monotonic()
    result, tools = _ask(ask, SYSTEM, Review, model, effort)
    verdicts = Review.model_validate(result["structured_output"]).model_dump()["verdicts"]
    by = {v["instance"]: v for v in verdicts}
    rows = []
    for item in items:
        v = by.get(item["instance"])
        assigned = check_type(item["assigned_type"], item, store)
        row = {**item, "assigned_checks": assigned}
        if not v:
            row["outcome"] = "the reviewer gave no verdict"
        else:
            row.update({"verdict": v["verdict"], "reviewer_type": v["type_id"], "evidence": v["evidence"],
                        "confidence": v["confidence"]})
            if v["verdict"] == "confirm" and v["type_id"] == item["assigned_type"]:
                row["outcome"] = "agreed" if not [x for x in assigned if not x.startswith("(")] else \
                    "agreed, but code finds problems with the type"
            else:
                proposed = check_type(v["type_id"], item, store)
                row["proposed_checks"] = proposed
                ok = not [x for x in proposed if not x.startswith("(")]
                row["outcome"] = (f"change to {v['type_id']}: code confirms it" if ok and v["verdict"] == "change" else
                                  f"new part {v['type_id']}: passes the naming rules" if ok else
                                  f"{v['verdict']} to {v['type_id']}: code does not confirm it")
        rows.append(row)
    stats = {"seconds": round(time.monotonic() - t0, 1), "cost_usd": result.get("total_cost_usd"), "tools_used": tools}
    return {"lesson_id": lesson_id, "instances": rows, "stats": stats}


def apply(result, store_dir=None):
    """Write the changes code confirmed into the stored lesson, and the review into its record. Returns the changes."""
    store_dir = store_dir or lesson_store.STORE
    lid = result["lesson_id"]
    row, g = lesson_store._load(lid, store_dir)
    changes = {r["instance"]: r["reviewer_type"] for r in result["instances"] if r["outcome"].endswith("code confirms it")}
    for n in g["physical"]["nodes"]:
        if n["id"] in changes:
            n.setdefault("props", {})["type_before_review"] = n["type"]
            n["type"] = changes[n["id"]]
    rec = g["lesson"]
    rec["part_review"] = {"changes": changes, "stats": result["stats"],
                          "verdicts": {r["instance"]: {k: r.get(k) for k in ("verdict", "reviewer_type", "evidence", "outcome")}
                                       for r in result["instances"]}}
    for k in ("physical", "lesson"):
        (store_dir / row["representations"][k]).write_text(json.dumps(g[k], indent=1))
    return changes


# ---------------------------------------------------------------- parts first (before the circuit is built)

class ItemVerdict(BaseModel):
    item: int = Field(description="the item's number in the list")
    verdict: Literal["confirm", "change", "new"]
    type_id: str = Field(description="the type it should have: the matched one (confirm), an existing catalogue type "
                                     "(change), or a new id by the naming rules (new)")
    name: str = Field(description="the part's full name, as a shop would list it (for looking a new part up)")
    evidence: str
    confidence: float = Field(ge=0, le=1)


class ListReview(BaseModel):
    verdicts: List[ItemVerdict]


LIST_SYSTEM = """You review a tutorial's parts list before a lesson is built from it. Code has matched each item to a
catalogue part type, or found none. Check every item against the parts catalogue with your tools (search_parts,
part): is the matched type really this part? Look at what tells similar parts apart (maker, model, chip). Answer:
- confirm: the matched type is right
- change: a different type already in the catalogue is right (give its type id)
- new: the catalogue has no such part (give an id by the naming rules below, and the part's full name)
Prefer a catalogue type whenever one is this part: a part named only generically ("resistor", "a motor") is never
new. Say what settles it in `evidence`.

""" + naming.RULES


class HardwareList(BaseModel):
    items: List[str] = Field(description="Each piece of hardware the tutorial's circuit is built from, as the page names "
                                         "it, one per item, with its count and value ('2 x 220 ohm resistor'); not "
                                         "software, not tools, not optional alternatives")


def hardware_by_claude(page_text, label, model="sonnet"):
    """The hardware list of a page that has no hardware section, from its text: [item text]."""
    from graph.extract import claude_json
    try:
        out, _ = claude_json("You read an electronics tutorial and list the hardware its circuit is built from.",
                             [{"type": "text", "text": f"Tutorial: {label}\n\n{page_text[:30000]}"}], HardwareList,
                             model=model, effort="low")
    except Exception:  # no list: the circuit builder finds the parts, as before
        return []
    return [i for i in (out or {}).get("items", []) if i.strip()]


def parts_first(page_text, label, model="sonnet", effort="high", call=None, store=None, add=True):
    """The lesson's parts settled before anything is built on them (DATA_STRUCTURE.md §4.2):
      1 match     code: each item of the tutorial's hardware list to a catalogue type (tutorial.match)
      2 review    Claude with the catalogue tools: confirm, change to an existing type, or new; code checks each
                  answer (R1 the type exists or a new id passes the naming rules, R3 the item's model numbers are the
                  type's); only what code confirms counts, so a "new" part that already exists never gets a card
      3 add       code: only the parts still new are looked up on the approved shops (ingest); a part no shop has is
                  left to the circuit builder, which drafts its card as before
      4 describe  Claude: standard metadata for the parts just added and only those (part_metadata, M1-M11)
    R2 (the type has every pin the circuit uses) needs the circuit: the circuit check V4 does it there.
    store: the card store (default the parts database's); add=False stops after the review (nothing is written).
    Returns {"rows", "note" (for the circuit builder), "new_types", "phase"}."""
    from graph.parts import part_metadata
    from graph.parts import part_catalogue
    from graph.parts import cards as pc
    from graph.parts import ingest
    from graph.parts.arduino import tutorial
    t0 = time.monotonic()
    store = store or pc.store("electronics", None, ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json")
    rows, listed_by = [], "code"
    items = tutorial.hardware_list(page_text)
    if not items and call is None:  # no hardware section on the page (an article, not a project): Claude lists it
        items, listed_by = hardware_by_claude(page_text, label, model), "claude"
    for text in items:
        card, name = tutorial.match(text, store)
        if card == "skip":
            continue
        value = tutorial.VALUE.search(text)
        rows.append({"item": len(rows) + 1, "text": text, "matched": card, "name": name,
                     "lesson_name": text, "ports_used": [], "props": {"value": value.group(0)} if value else {}})
    phase = {"phase": "parts first", "listed": len(rows), "listed_by": listed_by, "review_seconds": 0,
             "review_cost_usd": 0}
    if not rows:
        return {"rows": [], "note": "", "new_types": [], "phase": {**phase, "seconds": round(time.monotonic() - t0, 1)}}
    # 2 review
    ask = f"Tutorial: {label}.\nPARTS LIST (item | text | matched type, None = no match):\n" + "\n".join(
        f"{r['item']} | {r['text']} | {r['matched']}" for r in rows)
    result, tools = (call or _ask)(ask, LIST_SYSTEM, ListReview, model, effort)
    phase.update(review_seconds=round(time.monotonic() - t0, 1), review_cost_usd=result.get("total_cost_usd"),
                 tools_used=tools)
    by = {v["item"]: v for v in ListReview.model_validate(result["structured_output"]).model_dump()["verdicts"]}
    for r in rows:
        v = by.get(r["item"])
        r["type"] = r["matched"]
        if not v:
            r["outcome"] = "no verdict: the match stands" if r["matched"] else "no verdict and no match"
            continue
        r.update(verdict=v["verdict"], reviewer_type=v["type_id"], evidence=v["evidence"], confidence=v["confidence"])
        known, how = lesson_store.definition(lesson_store._cards(lesson_store.PARTS), v["type_id"])
        proposed = known["part_type_id"] if known else v["type_id"]  # resistor-220 is the catalogue's resistor
        if proposed != v["type_id"]:
            r["reviewer_type_means"] = f"{proposed} ({how})"
        if proposed == r["matched"]:
            r["outcome"] = "agreed"
            continue
        problems = [x for x in check_type(proposed, r, store) if not x.startswith("(")]
        r["checks"] = problems
        if problems:
            r["outcome"] = f"{v['verdict']} to {proposed}: code does not confirm it ({'; '.join(problems)})"
        elif known or store.get(proposed):
            r.update(type=proposed, outcome=f"change to {proposed}: code confirms it")
        elif r["matched"] and not [x for x in check_type(r["matched"], r, store) if not x.startswith("(")]:
            r["outcome"] = (f"new refused: the catalogue's {r['matched']} fits the item's name (R1, R3 pass), and a "
                            f"part the catalogue has is never added again")
        else:
            r.update(type=None, new_type=v["type_id"], new_name=v["name"],
                     outcome=f"new part {v['type_id']}: passes the naming rules")
    # 3 add only the parts still new
    added, cost = {}, 0.0
    for r in rows:
        if not add or r["type"] or not (r.get("new_type") or r["matched"] is None):
            continue
        card, st, trail = ingest.ingest_part(r.get("new_name") or r["name"] or r["text"], "electronics", store,
                                             wanted_id=r.get("new_type"), label=r["text"], max_llm_calls=3)
        cost += st.get("cost_usd", 0)
        r["looked_up"] = [list(t) for t in trail][:6]
        if card:
            r["type"] = card["type"]
            added[card["type"]] = card
        else:
            r["outcome"] += "; no approved shop has it: the circuit builder drafts its card"
    # 4 describe the new parts, and only them: the metadata rules every new part follows (part_metadata.describe_new)
    meta_stats = None
    if added:
        part_catalogue.build()
        meta_stats = part_metadata.describe_new(list(added), "arduino", model=model, label=label)
    note = "\n\nPARTS (the tutorial's list, matched to the catalogue and reviewed before this build; use these " \
           "types):\n" + "\n".join(f"- {r['text']} -> {r['type'] or 'not in the catalogue: add it as a new type'}"
                                   for r in rows)
    phase.update(seconds=round(time.monotonic() - t0, 1), lookup_cost_usd=round(cost, 4),
                 metadata=meta_stats and {k: meta_stats.get(k) for k in ("seconds", "cost_usd", "described", "checks_failed")},
                 changed=sum(1 for r in rows if r.get("outcome", "").startswith("change")),
                 new=sorted(added), cost_usd=round((phase["review_cost_usd"] or 0) + cost +
                                                   ((meta_stats or {}).get("cost_usd") or 0), 4))
    return {"rows": rows, "note": note, "new_types": sorted(added), "phase": phase}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lessons", nargs="+")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--apply", action="store_true", help="write the changes code confirmed into the stored lesson")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    for lid in a.lessons:
        r = review(lid, a.model)
        (OUT / f"{lid}.json").write_text(json.dumps(r, indent=1))
        print(f"{lid}: {r['stats']['seconds']}s ${r['stats']['cost_usd']}  tools: {', '.join(r['stats']['tools_used'])}")
        if a.apply:
            print(f"  applied: {apply(r) or 'nothing to change'}")
        for row in r["instances"]:
            print(f"  {row['instance']:6} {row['assigned_type']:28} {row.get('verdict', '-'):8} -> {row['outcome']}"
                  + (f"  [{'; '.join(x for x in row['assigned_checks'] if not x.startswith('('))}]"
                     if [x for x in row["assigned_checks"] if not x.startswith("(")] else ""))


if __name__ == "__main__":
    main()
