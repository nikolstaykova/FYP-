"""An Arduino lesson from a tutorial's link.

What it is   the Arduino recipe of the lesson loop (lessons.py: CircuitLessons), in CircuitQuest's lesson format
             (lesson.json, diagram.json, code.ino). Parts first (part_review.parts_first); the circuit graph
             (circuit_graph.py); the page's sketch, copied as written (browser.render), or one written for the
             circuit when the page has none; steps suggested by code from the graph, with where everything goes on
             the breadboard (every hole's position in millimetres, which hole each leg goes in, left to right:
             placements, hole_mm, strip); Claude chooses the order and grouping and writes the words and extras;
             code checks them.
Used for     a lesson for any Arduino tutorial page, from its link alone. A page with no circuit to build is
             refused.
Where        python -m graph.lessons electronics <link>, then python -m graph.lesson_store build arduino <id>;
             writes data/lessons/arduino/<id>/. arduino/graphs.py reads its corrections (a person's note where a
             tutorial is wrong).

  source   the tutorial's circuit graph (circuit_graph.py: Claude opens the page itself, code checks and repairs it);
           the tutorial page through browser.render, for its sketch, copied as written (never rewritten)
  steps    SUGGESTED by code, from the graph: each part with its legs and holes, then the wires; a part goes in
           before any wire to it, signal wires as soon as both their ends have something to meet, power and ground
           wires last; a board that sits in the breadboard has its own step. Each suggested step's expected nets
           are the connections it makes (breadboard strips and wires folded away, as CircuitQuest's checker compares
           them); a part that joins nothing yet is a landing
  plan     Claude: from the suggested steps, the tutorial and its sketch, the lesson's ORDER and GROUPING (up to three
           suggested steps in one lesson step) and the words: a clip, a goal and hints per step, and the EXTRAS (how
           it works, a code walkthrough, try it / troubleshooting, a "why" per step), shown only when the learner asks
  checks   W1 every suggested step used exactly once (at most three a step), every step has its words; O1 nothing
           is wired before the parts it connects are in; W2 no internal ids in the words; W3 polarised parts say which
           leg is which; W4 connections are said as columns, never rows; W5 a circuit with no breadboard never has
           its words say one (parts twisted onto each other and onto the wires' ends). Code facts are reported, not repaired: C1 the
           steps' nets are exactly the graph's nets, C2 every part is placed before it is wired, C3 every pin the
           sketch reads is wired (C4 a note for pins it only drives)
"""
import collections
import json
import pathlib
import re
from typing import List

from pydantic import BaseModel, Field

from graph.arduino.circuit_graph import READS, code_pins
from graph.arduino import circuit_graph
from graph.parts import part_catalogue
from graph.lessons import Recipe, log

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "lessons" / "arduino"
WOKWI = json.loads((ROOT / "code" / "graph" / "parts" / "arduino" / "wokwi_types.json").read_text())  # copied from CircuitQuest's cards
EXTRACTED = ROOT / "data" / "graph_runs" / "20261006-112727-arduino-sonnet-high-seeded-v6-url"  # 48 links, v6


class StepWords(BaseModel):
    uses: List[str] = Field(description="The ids of the SUGGESTED steps this lesson step does, in the order done "
                                        "(one, or up to three that belong together)")
    clip: str = Field(description="Beginner mode: one or two short plain sentences: what to do with which part, which "
                                  "leg, where")
    goal: str = Field(description="Advanced mode, shown instead of the clip: only what to achieve")
    hints: List[str] = Field(description="Two short hints for a learner who is stuck")
    why: str = Field(description="EXTRA, only when asked: one or two sentences on why this part or wire is there")


class CodePart(BaseModel):
    lines: str = Field(description="The lines of the sketch this explains, copied exactly")
    says: str = Field(description="What they do, in plain words, tied to the parts just wired (pin 13 = the LED)")


class Extras(BaseModel):
    how_it_works: str = Field(description="EXTRA: a short plain explanation of the circuit and the idea it teaches")
    code_walkthrough: List[CodePart] = Field(description="EXTRA: the sketch explained block by block, in order")
    try_it: List[str] = Field(description="EXTRA: what the learner should see, then one or two small changes to try")
    troubleshooting: List[str] = Field(description="EXTRA: common mistakes for THIS circuit and how to spot them")


class CircuitWords(BaseModel):
    title: str
    description: str = Field(description="One sentence: what the learner builds and what it does")
    gather_clip: str = Field(description="What to collect, in one or two sentences")
    steps: List[StepWords]
    upload_clip: str = Field(description="Upload the code, and what the learner should then see")
    extras: Extras


SYSTEM = """You plan and write a step-by-step Arduino lesson for a complete beginner. Code has worked out the circuit
from the tutorial and SUGGESTS build steps: for each, its id, the part or wire, every leg or wire end with its
breadboard hole or board pin, and what it connects. The holes, pins and connections are exact; never change them.
You choose the ORDER and the GROUPING:
- order the steps the way the tutorial builds it, or else the way that is easiest to follow for a beginner (a part,
  then the wires to it; the signal path in the order it flows; power last, so nothing is live while building)
- a lesson step may do up to three suggested steps that belong together (a part and the short wire to it; two
  identical wires side by side); list them in `uses` in the order done. Most steps do one.
- every suggested step is used exactly once
- a wire can only go in once the parts it connects to are in place (the board and breadboard are there from the
  start): put a part before, or in the same step as, every wire that connects to it

Breadboard holes are written <column><half>.<row>: '12t.c' is column 12, top half, row c; 't' = top half (rows a-e),
'b' = bottom half (rows f-j). The five holes of one column-half are one connection; the centre gap separates the halves.
Rails: 'tp.3' / 'tn.3' top plus / minus rail, 'bp' / 'bn' bottom. Board pins: '13', 'A0', '5V', 'GND.1' ...

Each lesson step has three texts, covering everything it does:
- clip (beginner mode): one or two short, plain sentences saying exactly what to do with which part, which leg and
  where: "Put the LED's long leg in column 14 on the top half, in the same column as the resistor's other leg, and its
  short leg in column 15." Name legs by what a beginner can see (long / short leg, middle leg, "either leg"), never by
  internal names ("group 1", "anode" alone, "contact pair"). Say breadboard places as numbered columns and the middle
  gap; never say "row" for a connection. Say the wire's colour.
- goal (advanced mode, shown INSTEAD of the clip): only what to achieve: "Connect the LED's long leg to the free end
  of the resistor."
- hints: two short hints: what to look for, and the usual mistake ("Any hole in that column works: the five holes are
  joined." "The long leg is the + side.").
Never write part ids (r1, led1, wire2, bb1, uno) in any text: say "the resistor", "the red wire", "the Arduino".

EXTRAS are shown only when the learner asks for them (a button now, a spoken keyword in AR later), never in the
main flow, so keep the clips short and put explanations here:
- why (per step): why this part or wire is there.
- how_it_works: the circuit and the idea it teaches, in a few plain sentences.
- code_walkthrough: the given sketch block by block, in order, each block's exact lines and what they do, tied to
  the pins just wired. Explain the sketch as given; never change it.
- try_it: what the learner should see, then one or two small changes to try.
- troubleshooting: the common mistakes for THIS circuit and how to spot them.
Return everything in the given JSON format."""


def ohms(value):
    """'220', '10k', '4.7k', '1M', '10000 ohm' -> ohms (int), else None."""
    m = re.match(r"\s*([\d.]+)\s*([kKmM]?)", str(value or ""))
    if not m:
        return None
    return round(float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)])


def library_id(node):
    """The part's card id in CircuitQuest's library: resistors by value (resistor-220), others by type."""
    t = node["type"]
    if t == "resistor":
        r = ohms((node.get("props") or {}).get("value"))
        hit = next((k for k, v in WOKWI.items() if v["subtype"] == "resistor" and v["value"] and int(v["value"]) == r), None)
        return hit or (f"resistor-{r}" if r else "resistor")
    return t


def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").rsplit("/", 1)[-1].lower()).strip("-") or "tutorial"


def extract(case, out, code=""):
    """The tutorial's graph (circuit_graph.py: Claude reads the link, code checks); the tutorial's sketch, when found,
    is checked against it (its pins must be wired). Returns (flat graph, its catalogue, stats)."""
    saved = circuit_graph.build(case, out, sketch=code)
    flat, catalogue = circuit_graph.save(case, saved, out)
    return flat, catalogue, saved["stats"]


def store_drafts(case, out, log=None):
    """The parts the circuit builder drafted (a part neither the tutorial's list nor the shops gave us): each stored
    as a card through the same gate as every new card (schema, naming rules: ingest._store), then given metadata by
    the metadata rules (part_metadata.describe_new). Returns {stored, refused, metadata}."""
    from graph.parts import part_metadata
    from graph.parts import cards as pc
    from graph.parts import ingest
    from graph.parts import cards
    saved = json.loads((out / case["id"] / "response.json").read_text())
    drafts = (saved.get("graph") or {}).get("new_part_types") or []
    store = pc.store("electronics", None, ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json")
    stored, refused = [], []
    for d in drafts:
        if store.get(d["type"]):
            continue
        card = cards.from_engine({**d, "status": "unverified"}, "electronics",
                                  {"platform": "lesson-draft", "url": case.get("url"), "external_id": None,
                                   "made_by": "claude"})
        (stored if ingest._store(store, card) else refused).append(d["type"])
    if stored:
        part_catalogue.build()  # the new cards into the catalogue, so the metadata rules can find them
    meta = part_metadata.describe_new(stored, "arduino", label=case["id"]) if stored else {}
    if log and (stored or refused):
        log(case["id"], f"parts the builder drafted: stored {stored or 'none'}, refused {refused or 'none'}; "
                        f"metadata {meta.get('described', 0)} (${meta.get('cost_usd', 0)})")
    return {"stored": stored, "refused": refused, "metadata": meta}


def degutter(code):
    """A code viewer's line numbers read along with the code ('1\t/*', '2\t', ...): the numbered lines, numbers off."""
    lines = code.splitlines()
    numbered = [ln for ln in lines if re.match(r"^\d+\t", ln)]
    if len(numbered) < 3 or len(numbered) < len([ln for ln in lines if ln.strip()]) / 2:
        return code
    return "\n".join(re.sub(r"^\d+\t", "", ln) for ln in numbered) + "\n"


def sketch(code_blocks):
    """The tutorial's sketch: the longest code block with setup() and loop()."""
    code_blocks = [degutter(c) for c in code_blocks]
    full = [c for c in code_blocks if "setup" in c and "loop" in c]
    if full:
        return max(full, key=len)
    # shown a piece at a time, explained in between: the pieces in the page's order make the sketch
    parts = [c for c in code_blocks if re.search(r"[;{}]|#include", c)]
    whole = "\n\n".join(c.strip("\n") for c in parts)
    return whole if re.search(r"\bvoid\s+setup\s*\(", whole) and re.search(r"\bvoid\s+loop\s*\(", whole) else ""


def _pairs(before, after, boards=()):
    """The connections a step makes: nets after it that join pins (or groups) separate before it. A group is named
    by its board pin when it has one (led1:C with uno:GND, as the tutorial says it)."""
    out = []
    for net in after:
        groups = []
        for pin in sorted(net):
            g = next((n for n in before if pin in n), frozenset([pin]))
            if g not in groups:
                groups.append(g)
        if len(groups) > 1:
            reps = [min(g, key=lambda x: (x.split(":", 1)[0] not in boards, x)) for g in groups]
            out += [[reps[0], r] for r in reps[1:]]
    return out


STACK = json.loads((ROOT / "code" / "graph" / "parts" / "arduino" / "stack_pins.json").read_text())


def stacked(flat):
    """A shield or carrier stacked on a board joins its pins to the board's underneath, with no wire (data/stack_pins
    .json): those joins are added to the graph as electrical edges (a stacked motor shield's channel B on 8, 11, 13)."""
    nodes = {n["id"]: n for n in flat["nodes"]}
    kind = _kinds(flat)
    have = {(e["u"], e["u_port"], e["v"], e["v_port"]) for e in flat["edges"] if e["type"] == "electrical"}
    add = []
    for e in flat["edges"]:
        if e["type"] != "joined":
            continue
        for top, base in ((e["u"], e["v"]), (e["v"], e["u"])):
            pins = STACK.get(nodes.get(top, {}).get("type"))
            if not pins or kind.get(base) != "board" or base == top:
                continue
            ports = {x for f in flat["edges"] for x in ((f["u_port"],) if f["u"] == base else (f["v_port"],) if f["v"] == base else ())}
            dstyle = any(re.fullmatch(r"D\d+", str(p)) for p in ports)  # the board's pins as the graph names them
            for sp, bp in pins.items():
                bp = f"D{bp}" if dstyle and bp.isdigit() else bp
                if (top, sp, base, bp) not in have and (base, bp, top, sp) not in have:
                    add.append({"type": "electrical", "u": top, "u_port": sp, "v": base, "v_port": bp, "method": "stacked",
                                "freedom": None, "reversible": None, "id": f"stack-{top}-{sp}"})
                    have.add((top, sp, base, bp))
    return dict(flat, edges=flat["edges"] + add) if add else flat


def _named(key, step):
    """A step's `at` key that already names its part ('pb1.wf.a', a wire that came with the step's own part)."""
    return any(key.startswith(w + ".") for w in step.get("with", []))


def plan_steps(flat, catalogue):
    """The build order and what each step connects, by code from the graph."""
    kind = _kinds(flat)
    nodes = {n["id"]: n for n in flat["nodes"]}
    where = placements(flat)
    fixed = {i for i, k in kind.items() if k in ("board", "breadboard")}

    def nets(ids):
        keep = fixed | set(ids)
        sub = {"nodes": [n for n in flat["nodes"] if n["id"] in keep],
               "edges": [e for e in flat["edges"] if e["u"] in keep and e["v"] in keep]}
        return circuit_graph.nets(sub, catalogue)

    def leftmost(i):
        xs = [m[0] for p in where.get(i, {}).values() if (m := hole_mm(p[1]))]
        return min(xs) if xs else 1e9
    comps = sorted((i for i, k in kind.items() if k == "component"), key=lambda i: (leftmost(i), i))
    wires = [i for i, k in kind.items() if k == "wire"]
    power = lambda i: any(POWER.match(str(w[1])) or RAIL.match(str(w[1]) or "")
                          for w in where.get(i, {}).values())
    placed, steps = [], []
    # a wire end pushed straight onto a part's pin (a module's header: the wire lesson's BMP280) is in no hole, so
    # `where` lacks it; the step's `at` names it too, or two wires from one socket could not be told apart
    on_part = collections.defaultdict(dict)
    for e in flat["edges"]:
        for a, ap, b, bp in ((e["u"], e.get("u_port"), e["v"], e.get("v_port")), (e["v"], e.get("v_port"), e["u"], e.get("u_port"))):
            if e["type"] == "joined" and kind.get(a) in ("wire", "component") and kind.get(b) == "component" and ap:
                on_part[a][ap] = (b, bp)

    def ends(i):  # a wire's ends; a part's other ends join it at the step of the part they go into
        return sorted({**(on_part.get(i, {}) if kind[i] == "wire" else {}), **where.get(i, {})}.items())

    def strips_of(ids):
        return {strip(w) for i in ids for w in where.get(i, {}).values()}

    def ready(w):  # both ends meet something already there: a board pin, or a strip with a part's leg in it
        have = strips_of([i for i in placed if kind[i] == "component"])
        return all(kind.get(p) == "board" or p in placed and kind.get(p) == "component"  # or plugged into a part
                   or strip((p, port)) in have for p, port in where.get(w, {}).values())

    pending = []  # wires that join nothing yet (a rail fed before anything is on it): they go with the step that uses them

    def add(i):
        before = nets(placed)
        placed.append(i)
        boards = {x for x, k in kind.items() if k == "board"}
        made = _pairs(before, nets(placed), boards)
        if kind[i] == "wire" and not made:
            pending.append(i)
            return
        mine = {strip(w) for w in where.get(i, {}).values()}
        plugged = {e["u"] if e["v"] == i else e["v"] for e in flat["edges"] if i in (e["u"], e["v"])}
        with_it = [w for w in pending if {strip(e) for e in where.get(w, {}).values()} & mine
                   or w in plugged]  # or a cable plugged straight into it (Grove)
        for w in with_it:
            pending.remove(w)
        if with_it:  # the pairs this step really makes count the wires that came before it
            made = _pairs(nets([x for x in placed if x not in with_it and x != i]), nets(placed), boards)
        n = nodes[i]
        at = {port: f"{p}:{h}" for port, (p, h) in ends(i)}
        if kind[i] == "component":  # a part off the board: a cable already in (a Grove cable, itself a component)
            at.update({f"{w}.{port}": f"{p}:{h}" for w in placed  # joins it here; a wire names this end in its own step
                       if w != i and kind[w] == "component" for port, (p, h) in on_part.get(w, {}).items() if p == i})
        for w in with_it:
            at.update({f"{w}.{port}": f"{p}:{h}" for port, (p, h) in ends(w)})
        step = {"id": f"step-{len(steps) + 1}", "part": i, "with": with_it, "kind": kind[i], "type": n["type"],
                "label": (n.get("label") or n["type"]) + "".join(f" + {nodes[w].get('label') or w}" for w in with_it),
                "props": n.get("props") or {}, "at": at}
        if made:
            step["expected_nets"] = made
        else:
            step["expected_landing"] = [f"{i}:{port}" for port in sorted(where.get(i, {}))] or [i]
        steps.append(step)
    for b in sorted(i for i, k in kind.items() if k == "board"):  # a board that sits in a breadboard (a Nano): placed
        at = {e["u_port"] if e["u"] == b else e["v_port"]:                  # first, its pins in their holes
              f"{e['v'] if e['u'] == b else e['u']}:{e['v_port'] if e['u'] == b else e['u_port']}"
              for e in flat["edges"] if e["type"] == "joined" and b in (e["u"], e["v"])
              and kind.get(e["v"] if e["u"] == b else e["u"]) == "breadboard"}
        if at:
            n = nodes[b]
            steps.append({"id": f"step-{len(steps) + 1}", "part": b, "with": [], "kind": "board", "type": n["type"],
                          "label": n.get("label") or n["type"], "props": n.get("props") or {}, "at": dict(sorted(at.items())),
                          "expected_landing": [f"{b}:{p}" for p in sorted(at)]})
    for c in comps:
        add(c)
        for w in sorted(wires, key=lambda i: (leftmost(i), i)):
            if w not in placed and not power(w) and ready(w):
                add(w)
    for w in sorted((w for w in wires if w not in placed), key=lambda i: (power(i), leftmost(i), i)):
        add(w)
    for w in list(pending):  # still joining nothing at the end: a step of its own
        pending.remove(w)
        n = nodes[w]
        steps.append({"id": f"step-{len(steps) + 1}", "part": w, "with": [], "kind": "wire", "type": n["type"],
                      "label": n.get("label"), "props": n.get("props") or {}, "expected_nets": [],
                      "at": {port: f"{p}:{h}" for port, (p, h) in ends(w)}})
    return steps, nets(placed)


CORRECTIONS = ROOT / "data" / "reference" / "lesson_corrections.json"


def corrections():
    """A person's fixes for tutorials that are wrong or incomplete: {case id: {"hint": what the circuit really is,
    "sketch": a file or link with the sketch, "why": what was wrong}}. Kept, so every later run uses them."""
    return json.loads(CORRECTIONS.read_text()) if CORRECTIONS.exists() else {}


def correct(case_id, hint="", sketch_src="", why=""):
    """Record a correction (python -m graph.lessons arduino <id> --hint "..." [--sketch file|url])."""
    allc = corrections()
    entry = allc.get(case_id, {})
    entry.update({k: v for k, v in (("hint", hint), ("sketch", sketch_src), ("why", why)) if v})
    allc[case_id] = entry
    CORRECTIONS.write_text(json.dumps(allc, indent=1) + "\n")


def read_sketch(src):
    """A sketch from a local file, a GitHub file link (read raw) or any link to plain text."""
    import urllib.request
    p = pathlib.Path(src).expanduser()
    if p.exists():
        return p.read_text()
    src = re.sub(r"https://github\.com/([^/]+)/([^/]+)/blob/", r"https://raw.githubusercontent.com/\1/\2/", src)
    with urllib.request.urlopen(src, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


class WrittenSketch(BaseModel):
    sketch: str = Field(description="the complete Arduino sketch, with setup() and loop()")
    explains: str = Field(description="one sentence: what it does with this circuit")


WRITE_SKETCH = """You write the Arduino sketch for a lesson whose tutorial page has no sketch the board can run (the
page uses a cloud service, another program such as MATLAB, a PLC tool, or no code at all). Write a sketch that makes
THIS circuit do what the tutorial is about, as a standalone program on the board (no cloud account, no PC program):
- use only the board pins the circuit wires (listed); every input the program needs must be one of them
- the standard Arduino core, plus a library only if the tutorial names it
- short and commented for a beginner; start with a comment saying it was written for this lesson because the
  tutorial has none, and what it does
- Serial at 9600 if it prints"""


def write_sketch(src, model="sonnet"):
    """A page with no runnable sketch: Claude writes one for the extracted circuit, checked like the page's own
    (setup and loop, only wired pins, every pin it reads wired); one repair if not. Returns (code, phase)."""
    from graph.extract import SubscriptionSession
    kind = _kinds(src["flat"])
    boards = {i for i, k in kind.items() if k == "board"}
    nodes = {n["id"]: n for n in src["flat"]["nodes"]}
    lines = [f"TUTORIAL: {src['url']}",
             "BOARD: " + ", ".join(f"{nodes[b]['type']} ({b})" for b in sorted(boards)),
             "PARTS: " + ", ".join(f"{n['id']} {n['type']}" + (f" ({n['label']})" if n.get("label") else "")
                                   for n in src["flat"]["nodes"] if kind.get(n["id"]) in ("component", "board")),
             "CONNECTIONS (each line one net):"] + [" - " + ", ".join(sorted(n)) for n in src["nets"]]
    lines += ["", "TUTORIAL TEXT:", src["page_text"][:8000]]
    wired = {re.sub(r"^D(\d+)$", r"\1", pin.split(":", 1)[1]) for n in src["nets"] for pin in n
             if pin.split(":", 1)[0] in boards}

    def problems(code):
        out = []
        if not (re.search(r"\bvoid\s+setup\s*\(", code) and re.search(r"\bvoid\s+loop\s*\(", code)):
            out.append("it needs void setup() and void loop()")
        if code.count("{") != code.count("}"):
            out.append("its braces do not balance")
        bad = sorted(code_pins(code) - wired - {"13"})
        if bad:
            out.append(f"it uses board pins {', '.join(bad)}, which the circuit does not wire; use only {', '.join(sorted(wired))}")
        return out
    s = SubscriptionSession("\n".join(lines), "", "lego-v8", model=model, effort="medium", timeout=600,
                            schema=WrittenSketch, system=WRITE_SKETCH)
    try:
        ans, st = s.first()
        bad = problems(ans["sketch"])
        if bad:
            ans, st2 = s.repair("The sketch has problems:\n" + "\n".join("- " + b for b in bad) +
                                "\nReturn the complete corrected sketch.")
            st = {**st, "cost_usd": round(st.get("cost_usd", 0) + st2.get("cost_usd", 0), 4),
                  "seconds": round(st.get("seconds", 0) + st2.get("seconds", 0), 1)}
    finally:
        s.close()
    return ans["sketch"], {"phase": "write sketch (page has none)", **st, "problems_left": problems(ans["sketch"])}


class CircuitLessons(Recipe):
    name, schema, system, hint = "electronics", CircuitWords, SYSTEM, "lego-v8"
    timeout = 900

    def source(self, case):
        from graph.arduino import browser
        if case.startswith("http"):
            c = {"id": slug(case), "domain": "arduino", "url": case}
        else:
            c = dict(next(x for x in json.loads((ROOT / "data" / "reference" / "arduino_dataset.json").read_text())
                          if x["id"] == case), domain="arduino")
        log(c["id"], "reading the page for its sketch")  # first: the graph is checked against it (E11)
        page = browser.render(c["url"])
        code = sketch(page.get("code", []))
        fix = corrections().get(c["id"], {})
        if fix.get("sketch"):  # a sketch given by a person (a file or a link): the page has none, or the wrong one
            code = read_sketch(fix["sketch"])
            log(c["id"], f"sketch from the correction: {fix['sketch']}")
        c = dict(c, correction=fix.get("hint", ""), sketch=code if fix else "")
        flat = None
        if fix:
            log(c["id"], "corrected: extracting the graph again with the correction")
        elif not case.startswith("http") and (OUT / case / "extract" / case / "graph.json").exists():
            flat = json.loads((OUT / case / "extract" / case / "graph.json").read_text())  # this lesson's own, newer
            catalogue, gstats = part_catalogue.Catalogue(part_catalogue.arduino_seed()), json.loads(           # (extracted again for it)
                (OUT / case / "extract" / case / "result.json").read_text()).get("stats")
            if circuit_graph.sketch_pins(stacked(flat), code):
                log(c["id"], "the saved graph leaves pins the sketch reads unwired: extracting again")
                flat = None
        elif not case.startswith("http") and (EXTRACTED / case / "graph.json").exists():  # the link run's graph,
            flat = json.loads((EXTRACTED / case / "graph.json").read_text())             # unless the sketch uses
            catalogue, gstats = part_catalogue.Catalogue(part_catalogue.arduino_seed()), json.loads(           # pins it leaves unwired
                (EXTRACTED / case / "result.json").read_text()).get("stats")
            if circuit_graph.sketch_pins(stacked(flat), code):
                log(c["id"], "the saved graph leaves pins the sketch uses unwired: extracting again")
                flat = None
        first = None
        if flat is None:
            out = OUT / c["id"] / "extract"
            out.mkdir(parents=True, exist_ok=True)
            from graph.arduino import part_review  # parts first: matched, reviewed, added and described before the circuit
            log(c["id"], "parts first: match, review, add the new ones, describe them")
            first = part_review.parts_first(page.get("markdown") or page["text"], c["url"])
            (out / "parts_first.json").write_text(json.dumps(first, indent=1))
            log(c["id"], f"parts first: {first['phase']['listed']} listed, {first['phase'].get('changed', 0)} changed by "
                         f"the review, new: {first['new_types'] or 'none'} ({first['phase']['seconds']} s, "
                         f"${first['phase'].get('cost_usd', 0)})")
            c["parts_note"] = first["note"]
            seed = part_catalogue.Catalogue(part_catalogue.arduino_seed()).entries  # the settled parts' pins, before the circuit uses them
            no_pins = sorted({r.get("type") or r.get("matched") for r in first["rows"]
                              if (r.get("type") or r.get("matched")) in seed
                              and not seed[r.get("type") or r.get("matched")].get("ports")} - {None})
            if no_pins:
                from graph.parts.arduino import pinouts
                log(c["id"], f"pinouts for parts with none: {pinouts.build(no_pins, log=lambda *m: None)}")
            log(c["id"], "extracting the circuit graph (pipeline v6, link)")
            flat, catalogue, gstats = extract(c, out, code)
            (out / "drafted_parts.json").write_text(json.dumps(store_drafts(c, out, log), indent=1))
            seed_now = part_catalogue.Catalogue(part_catalogue.arduino_seed()).entries  # seed cards that list no pins (CircuitQuest's)
            no_pins = sorted({n["type"] for n in flat["nodes"]
                              if n["type"] in seed_now and not seed_now[n["type"]].get("ports")})
            if no_pins:  # a part whose card lists no pins: its pinout first (Wokwi, or drafted and checked), so
                from graph.parts.arduino import pinouts  # the next lesson with it can say which leg goes where
                got = pinouts.build(no_pins, log=lambda *m: None)
                if got:  # a part the builder brought: the next extraction uses them
                    log(c["id"], f"pinouts added for {sorted(got)} (a part the circuit builder brought)")
        flat = stacked(flat)
        steps, all_nets = plan_steps(flat, catalogue)
        if not any(s["kind"] in ("component", "wire") for s in steps):  # an article with no circuit to build (SPI
            raise ValueError(f"{c['id']}: the page has no circuit to build (no part or wire to place)")  # explained)
        log(c["id"], f"{len(steps)} build steps by code")
        written = None
        if not code:  # nothing on the page the board can run: a sketch written for this circuit, so the lesson runs
            log(c["id"], "no sketch on the page: writing one for the circuit")
            code, written = write_sketch({"url": c["url"], "flat": flat, "nets": all_nets, "page_text": page["text"]})
            log(c["id"], f"sketch written ({written.get('seconds')} s, ${written.get('cost_usd')}); "
                         f"problems left: {written['problems_left'] or 'none'}")
        return {"id": c["id"], "url": c["url"], "flat": flat, "catalogue": catalogue, "graph_stats": gstats,
                "page_title": page["text"][:120], "page_text": page["text"], "code": code,
                "steps": steps,
                "nets": all_nets, "sketch_written": written, "parts_first": first and first["phase"]}

    def sections(self, src):  # one section; writing a missing sketch is a phase of its own
        return [(None, None)], [x for x in (src.get("parts_first"), src.get("sketch_written")) if x]

    def prompt(self, src, section, built):
        lines = [f"TUTORIAL: {src['url']}", "",
                 "SUGGESTED BUILD STEPS (from code, in code's order; you choose the lesson's order and grouping):"]
        for s in src["steps"]:
            what = s["label"] or s["type"]
            extra = ", ".join(f"{k} {v}" for k, v in s["props"].items())
            at = "; ".join(f"{port} in {w}" for port, w in s["at"].items())
            conn = (" | connects: " + ", ".join(f"{a} with {b}" for a, b in s["expected_nets"])) if s.get("expected_nets") \
                else " | connects nothing yet (it is only put in place)"
            pol = " | polarised: say which leg goes where" if (src["catalogue"].get(s["type"]) or {}).get("polarized") else ""
            lines.append(f"{s['id']} | {s['kind']} {what}{' (' + extra + ')' if extra else ''} | {at}{conn}{pol}")
        head = ("SKETCH (written for this lesson because the tutorial has none: say so in the upload clip; explain "
                "it, never change it):") if src.get("sketch_written") else "SKETCH (the tutorial's own; explain it, never change it):"
        lines += ["", head, src["code"] or "(none found on the page)",
                  "", "TUTORIAL TEXT (for the explanations):", src["page_text"][:8000]]
        return "\n".join(lines)

    def check(self, src, words, section, built):
        issues, ids = [], [s["id"] for s in src["steps"]]
        by = {s["id"]: s for s in src["steps"]}
        used = [u for w in words["steps"] for u in w["uses"]]
        missing, twice = [i for i in ids if i not in used], sorted({u for u in used if used.count(u) > 1})
        unknown = sorted(set(used) - set(ids))
        if missing or twice or unknown:
            issues.append(("W1", f"every suggested step must be used exactly once: missing {', '.join(missing) or '-'}; "
                                 f"used twice {', '.join(twice) or '-'}; unknown {', '.join(unknown) or '-'}"))
        for n, w in enumerate(words["steps"], 1):
            if len(w["uses"]) > 3:
                issues.append(("W1", f"lesson step {n} does {len(w['uses'])} suggested steps; at most 3"))
        # O1: nothing is wired before the parts it connects are in (the board and breadboard are there from the start)
        fixed = {i for i, k in _kinds(src["flat"]).items() if k in ("board", "breadboard")}
        placed = set(fixed)
        for n, w in enumerate(words["steps"], 1):
            here = [by[u] for u in w["uses"] if u in by]
            now = placed | {x for st in here for x in [st["part"], *st.get("with", [])]}
            for st in here:
                for pair in st.get("expected_nets", []):
                    late = sorted({pin.split(":", 1)[0] for pin in pair} - now)
                    if late:
                        issues.append(("O1", f"lesson step {n} ({st['id']}) connects {' with '.join(pair)}, but "
                                             f"{', '.join(late)} is not in place yet: put the step that places it "
                                             f"({', '.join(x['id'] for x in src['steps'] if x['part'] in late)}) before or in this step"))
            placed = now
        part_ids = {n["id"] for n in src["flat"]["nodes"]}
        has_breadboard = any(k == "breadboard" for k in _kinds(src["flat"]).values())
        for n, w in enumerate(words["steps"], 1):
            if not w["clip"].strip() or not w["goal"].strip() or not w["hints"]:
                issues.append(("W1", f"lesson step {n}: needs a clip, a goal and hints"))
            text = " ".join([w["clip"], w["goal"], *w["hints"]])
            leaked = sorted(i for i in part_ids if re.search(rf"\b{re.escape(i)}\b", text) and not i.isdigit())
            if leaked:
                issues.append(("W2", f"lesson step {n}: the words name internal ids ({', '.join(leaked)}); say what the part is"))
            if any((src["catalogue"].get(by[u]["type"]) or {}).get("polarized") for u in w["uses"] if u in by) and not re.search(
                    r"\b(long|short|longer|shorter|plus|minus|positive|negative|flat|notch|dot|stripe|band|pin 1|"
                    r"marking|marked|signal|SIG|VCC|GND|anode|cathode)\b|[+−]|\(-\)", w["clip"], re.I):
                issues.append(("W3", f"lesson step {n}: a part has a right way round; the clip must say which leg goes "
                                     f"where (long / short leg, + / −)"))
            if re.search(r"\bsame row\b|\brow (is|are) (joined|connected)", text, re.I):
                issues.append(("W4", f"lesson step {n}: connections are columns, not rows; say the column"))
            if not has_breadboard and re.search(r"\bbreadboard\b|\b(column|row|rail)s?\b", text, re.I):
                issues.append(("W5", f"lesson step {n}: this circuit has no breadboard (its parts are joined to each "
                                     f"other and to the wires' ends directly); say how the legs and wire ends are "
                                     f"joined, never a breadboard, its columns, rows or rails"))
        return issues

    def join(self, src, done):
        (_, words), = done
        return words

    def final_check(self, src, words):
        found = self.check(src, words, None, set()) + code_facts(dict(src, steps=in_order(src, words)))
        # notes are not problems (a pin the sketch also drives, another way to wire the same thing): kept apart
        src["notes"] = [list(i) for i in found if i[0] == "C4"]
        return [i for i in found if i[0] != "C4"]


    def save(self, src, words, stats):
        d = OUT / src["id"]
        d.mkdir(parents=True, exist_ok=True)
        nodes = {n["id"]: n for n in src["flat"]["nodes"]}
        kind = _kinds(src["flat"])
        by = {s["id"]: s for s in src["steps"]}
        items = list(dict.fromkeys(library_id(n) for n in src["flat"]["nodes"]))
        steps = [{"id": "gather", "phase": "gather", "clip": words["gather_clip"], "items": items}]
        for n, w in enumerate(words["steps"], 1):
            here = [by[u] for u in w["uses"] if u in by]
            step = {"id": f"step-{n}", "phase": "build", "clip": w["clip"], "strict": False, "goal": w["goal"],
                    "hints": w["hints"], "extras": {"why": w.get("why", "")}, "suggested": w["uses"],
                    # the graph's holes and pins: where the AR overlay shows each leg
                    # each key names its part ('cable2.jumper.1'): two cables in the same sockets stay apart
                    "at": {(k if _named(k, st) or any(k.startswith(f"{i}.") for i in nodes) else f"{st['part']}.{k}"): v
                           for st in here for k, v in st["at"].items()}}
            nets = [p for st in here for p in st.get("expected_nets", [])]
            if nets:
                step["expected_nets"] = nets
            else:
                step["expected_landing"] = [x for st in here for x in st.get("expected_landing", [])]
            steps.append(step)
        steps.append({"id": "upload-code", "phase": "upload", "clip": words["upload_clip"], "code": "code.ino"})
        lesson = {"id": src["id"], "title": words["title"], "description": words["description"],
                  "source": {"url": src["url"], "title": src["page_title"][:80]}, "difficulty": "beginner",
                  "board": "arduino-uno", "code": "code.ino", "wokwi_diagram": "diagram.json", "tools_used": [],
                  "parts_used": items, "steps": steps,
                  "final_check": {"expected_nets": [p for s in src["steps"] for p in s.get("expected_nets", [])]},
                  "extras": words["extras"], "generated": True, "made_from": "graph",
                  "sketch_from": "written for this lesson (the tutorial has none)" if src.get("sketch_written") else "the tutorial"}
        (d / "lesson.json").write_text(json.dumps(lesson, indent=2, ensure_ascii=False) + "\n")
        (d / "diagram.json").write_text(json.dumps(diagram(src["flat"], kind, nodes), indent=2) + "\n")
        (d / "code.ino").write_text(src["code"] if src["code"].endswith("\n") else src["code"] + "\n")
        (d / "graph.json").write_text(json.dumps(src["flat"], indent=1))
        stats["graph"] = src["graph_stats"]
        stats["notes"] = src.get("notes", [])
        (d / "stats.json").write_text(json.dumps(stats, indent=1))
        (d / "lesson.md").write_text(markdown(lesson, src["code"]))
        return d


def in_order(src, words):
    """Code's suggested steps in the lesson's order (Claude's). Within one lesson step they go in together, so they
    keep code's own order there (parts before the wires to them, a part before the part that lands in its column)."""
    by = {s["id"]: s for s in src["steps"]}
    rank = {s["id"]: k for k, s in enumerate(src["steps"])}
    out = []
    for w in words["steps"]:
        here = [by[u] for u in w["uses"] if u in by]
        out += sorted(here, key=lambda st: rank[st["id"]])
    return out + [s for s in src["steps"] if s not in out]


def _boards(src):
    return {i for i, k in _kinds(src["flat"]).items() if k == "board"}


def _union(pairs):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x
    for p in pairs:
        a, *rest = sorted(p)
        for b in rest:
            parent[find(b)] = find(a)
    groups = {}
    for x in list(parent):
        groups.setdefault(find(x), set()).add(x)
    return {frozenset(g) for g in groups.values() if len(g) > 1}


def diagram(flat, kind, nodes):
    """Wokwi's diagram.json for the finished circuit: every leg in its hole, every wire between its two ends."""
    parts = []
    for i, n in nodes.items():
        lid = library_id(n)
        w = (WOKWI.get(lid) or {}).get("wokwi_type") or f"wokwi-{n['type']}"
        if kind[i] == "wire":
            continue
        if kind[i] == "breadboard":
            w = "wokwi-breadboard-half"
        attrs = {}
        if (WOKWI.get(lid) or {}).get("value"):
            attrs["value"] = WOKWI[lid]["value"]
        if (n.get("props") or {}).get("colour") and kind[i] == "component":
            attrs["color"] = n["props"]["colour"]
        parts.append({"type": w, "id": i, "top": 0, "left": 0, "attrs": attrs})
    conns = []
    where = placements(flat)
    for i, legs in where.items():
        if kind.get(i) == "component":
            conns += [[f"{i}:{port}", f"{p}:{h}", "green", []] for port, (p, h) in sorted(legs.items())]
        elif kind.get(i) == "wire" and len(legs) == 2:
            (_, (pa, ha)), (_, (pb, hb)) = sorted(legs.items())
            conns.append([f"{pa}:{ha}", f"{pb}:{hb}", (nodes[i].get("props") or {}).get("colour") or "green", []])
    return {"version": 1, "author": "Pinpoint FYP (from the tutorial's graph)", "editor": "wokwi", "parts": parts,
            "connections": conns, "dependencies": {}}


def markdown(lesson, code):
    out = [f"# {lesson['title']}", "", lesson["description"], "", f"Source: {lesson['source']['url']}", ""]
    for s in lesson["steps"]:
        out.append(f"**{s['id']}** ({s['phase']}): {s['clip']}")
        if s.get("goal"):
            out.append(f"  - goal: {s['goal']}")
        for h in s.get("hints", []):
            out.append(f"  - hint: {h}")
        if s.get("expected_nets") or s.get("expected_landing"):
            out.append(f"  - checks: {s.get('expected_nets') or s.get('expected_landing')}")
        if (s.get("extras") or {}).get("why"):
            out.append(f"  - [extra] why: {s['extras']['why']}")
    ex = lesson["extras"]
    out += ["", "## Extras (shown on request)", "", "**How it works.** " + ex["how_it_works"], "", "**Code walkthrough**"]
    out += [f"- `{c['lines'].strip()[:80]}`: {c['says']}" for c in ex["code_walkthrough"]]
    out += ["", "**Try it**"] + [f"- {t}" for t in ex["try_it"]] + ["", "**Troubleshooting**"] + \
           [f"- {t}" for t in ex["troubleshooting"]] + ["", "## Sketch", "", "```cpp", code, "```", ""]
    return "\n".join(out)


def code_facts(src):
    """C1-C3: facts about the graph, the steps and the sketch (not Claude's to repair), reported with the lesson."""
    issues = []
    made = {frozenset(p) for s in src["steps"] for p in s.get("expected_nets", [])}
    # what is joined before the first step: a shield stacked on its board (its pins are the board's)
    kind = _kinds(src["flat"])
    fixed = {i for i, k in kind.items() if k in ("board", "breadboard")}
    made |= {frozenset(x) for x in _pairs([], circuit_graph.nets(
        {"nodes": [n for n in src["flat"]["nodes"] if n["id"] in fixed],
         "edges": [e for e in src["flat"]["edges"] if e["u"] in fixed and e["v"] in fixed]}, src["catalogue"]),
        {x for x, k in kind.items() if k == "board"})}
    want = {frozenset(n) for n in src["nets"]}
    named = set().union(*want) if want else set()
    for n in src["flat"]["nodes"]:  # what a part joins inside itself (the board's GND pins) is no step's work
        for g in (src["catalogue"].get(n["type"]) or {}).get("conducts", []):  # (a wire's own two ends are in
            made |= {frozenset((f"{n['id']}:{a}", f"{n['id']}:{b}")) for a, b in zip(g, g[1:])  # no net)
                     if f"{n['id']}:{a}" in named and f"{n['id']}:{b}" in named}
    union = _union(made)
    if union != want:
        issues.append(("C1", f"the steps' connections differ from the graph's nets: {sorted(map(sorted, union ^ want))[:6]}"))
    first = {}
    for k, s in enumerate(src["steps"]):
        for p in [s["part"], *s.get("with", [])]:
            first.setdefault(p, k)
    for k, s in enumerate(src["steps"]):
        for pair in s.get("expected_nets", []):
            for pin in pair:
                p = pin.split(":", 1)[0]
                if p in first and first[p] > k:
                    issues.append(("C2", f"{s['id']} wires {pin} before that part is placed"))
    wired = {re.sub(r"^D(\d+)$", r"\1", pin.split(":", 1)[1]) for n in src["nets"] for pin in n
             if pin.split(":", 1)[0] in _boards(src)}  # D2 and 2 are one pin
    # pin 13 also drives the Uno's own LED, so a sketch may use it with nothing wired
    reads = code_pins(src["code"], READS) if src["code"] else set()
    for pin in sorted(code_pins(src["code"]) - wired - {"13"} if src["code"] else []):
        if pin in reads:  # the program cannot work without it
            issues.append(("C3", f"the sketch reads pin {pin}, but the circuit wires nothing to it"))
        else:  # only driven: often another way to do what the circuit does (a sensor powered from two pins)
            issues.append(("C4", f"note: the sketch also drives pin {pin}, which this circuit does not use"))
    if not src["code"]:
        issues.append(("C3", "no sketch with setup() and loop() was found on the tutorial page"))
    return issues


# ---- where everything goes on the breadboard: holes in millimetres, legs to holes, order ----------
PITCH = 2.54  # mm


HOLE = re.compile(r"^(\d+)([tb])\.([a-j])$")


RAIL = re.compile(r"^([tb])([pn])\.(\d+)$")


POWER = re.compile(r"^(5V|3\.3V|3V3|VIN|GND(\.\d+)?|IOREF)$", re.I)


def hole_mm(hole):
    """A breadboard hole's position in mm from the top-left hole (1t.a), x along the columns, y down the rows."""
    m = HOLE.match(hole or "")
    if m:
        col, bank, row = int(m.group(1)), m.group(2), "abcdefghij".index(m.group(3))
        return [round((col - 1) * PITCH, 2), round(row * PITCH + (3 * PITCH - PITCH if row >= 5 else 0), 2)]
    m = RAIL.match(hole or "")
    if m:  # rails: two rows above the top bank (tp, tn) and two below the bottom bank (bp, bn)
        bank, sign, n = m.group(1), m.group(2), int(m.group(3))
        y = {("t", "n"): -3 * PITCH, ("t", "p"): -2 * PITCH, ("b", "p"): 13 * PITCH, ("b", "n"): 14 * PITCH}[(bank, sign)]
        return [round((n - 1) * PITCH, 2), round(y, 2)]
    return None


def strip(where):
    """What a hole or pin is electrically the same as: a column-bank strip, a rail, the board's GND."""
    part, port = where
    m = HOLE.match(port or "")
    if m:
        return (part, f"{m.group(1)}{m.group(2)}")
    m = RAIL.match(port or "")
    if m:
        return (part, f"{m.group(1)}{m.group(2)}")
    if re.match(r"^GND(\.\d+)?$", port or "", re.I):
        return (part, "GND")
    return (part, port)


def _kinds(flat):
    kind = {}
    for n in flat["nodes"]:
        t = n["type"].lower()
        kind[n["id"]] = ("breadboard" if "breadboard" in t else "board" if t.startswith(("arduino", "raspberry", "pi-"))
                         else "wire" if "wire" in t or "jumper" in t else "component")
    return kind


def placements(flat):
    """{part id: {port: (other part, other port)}} from the joined edges to the breadboard and the board."""
    kind = _kinds(flat)
    out = collections.defaultdict(dict)
    for e in flat["edges"]:
        if e["type"] != "joined":
            continue
        for a, ap, b, bp in ((e["u"], e.get("u_port"), e["v"], e.get("v_port")), (e["v"], e.get("v_port"), e["u"], e.get("u_port"))):
            if kind.get(b) in ("breadboard", "board") and kind.get(a) in ("component", "wire"):
                out[a][ap or f"end{len(out[a]) + 1}"] = (b, bp)
    return out
