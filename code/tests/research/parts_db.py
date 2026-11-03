"""The one parts catalogue: LEGO and Arduino parts together in code/graph/parts/parts.json (DATA_STRUCTURE.md §3.4).

One entry per part TYPE, keyed by its id (`lego-3021`, `led`). An entry is the part's card (ports, inside behaviour,
polarity, electrical values) plus a `metadata` block:
  domain             lego · arduino: which kind of part it is
  source_catalogue   the card store it came from (cards_lego.json, cards_electronics.json)
  card_made_by       who made the card (code from LDraw, CircuitQuest's verified library, Claude)
  description, material, specifications, joins (holds_by, reversible), learner_tips, ...
                     drafted by Claude and checked by code (part_metadata.py), with `status` and `checks_failed`
Lessons' physical graphs type their instances by these ids; there is no other catalogue for them to look in.

The graph-building pipeline (v3.py, parts/) still adds new cards to its two card stores while it runs; `build`
merges them in, keeping every metadata block already here.

  python -m graph.parts.parts_db build      (merge the card stores in; safe to run again)
  python -m graph.parts.parts_db stats
"""
import argparse
import collections
import json
import pathlib

from graph.arduino import pins

ROOT = pathlib.Path(__file__).resolve().parents[3]
PATH = ROOT / "code" / "graph" / "parts" / "parts.json"
STORES = {"lego": "code/graph/parts/lego/cards_lego.json", "arduino": "code/graph/parts/arduino/cards_electronics.json"}
OLD_METADATA = ROOT / "code" / "graph" / "data" / "part_metadata.json"  # before parts.json: metadata in its own file

# Part-level substitutes: what a copy may differ in and still be right (instance properties, not other parts).
# A resistor's allowed values depend on what it does in the circuit, so the lesson works them out (substitutes.py)
SUBSTITUTES = {
    "led": {"free": ["colour"], "why": "any colour lights the same way (forward voltage differs a little)"},
    "jumper-wire": {"free": ["colour", "length"], "why": "a wire's colour and length do not change the circuit"},
    "resistor": {"value": "by role", "why": "worked out per lesson: a resistor in series with an LED may take any "
                                            "value that keeps its current between about 5 and 20 mA"},
    "lego": {"free": ["colour"], "why": "a colour swap builds the same shape (AR check accepts it)"},
}


def load(path=PATH):
    return json.loads(path.read_text()) if path.exists() else {}


def save(parts, path=PATH):
    path.write_text(json.dumps(dict(sorted(parts.items())), indent=1))


def of_domain(parts, domain):
    return {k: v for k, v in parts.items() if v["metadata"]["domain"] == domain}


def fits(card, examples):
    """Every port kind of the part -> what it can go into or onto (joins.FITS, by code, not drafted): the other port's
    kind, how they join, what holds them, how it is undone, and up to four catalogue parts that have that port."""
    from graph import lesson_store
    out = {}
    for k in sorted({p["kind"] for p in card.get("ports", [])}):
        rows = [{"with": o, "method": m, "holds_by": h, "reversible": r,
                 "examples": [x for x in examples.get(o, []) if o != "wire-end" or  # a leg pushes into a female end
                              any(w in x for w in ("alligator", "female", "clip"))][:4]}
                for o, m, h, r in lesson_store.fits_into(k)]
        if rows:
            out[k] = rows
    return out


WAYS = {"breadboard-hole": ("breadboard", "on a breadboard (no solder)"),
        "header-socket": ("header-socket", "into a header socket (on a board)"),
        "wire-end": ("female-jumper", "with a female jumper wire or a clip"),
        "header-pin": ("onto-header-pin", "pushed onto a header pin"),
        "screw": ("screw-terminal", "in a screw terminal (with a screwdriver)"),
        "pad": ("solder", "soldered (to a pad, a perfboard or a wire)")}
TAKES = {"lead": "a part's leg (resistor, LED…)", "pin": "a module's pin", "header-pin": "a header pin",
         "wire-end": "a male jumper wire", "lug": "a lug"}
TOOL = {"screw-terminal": "screwdriver", "solder": "soldering iron"}


def connect_by(fits_):
    """From `fits`, as data: how the part connects (its legs, pins or wire ends go into or onto something; a leg or
    pin can always be soldered too) and what its sockets, holes or terminals take.
    {"connect_by": [{way, tool, text}], "takes": [{what, text}]}, from no tools to tools."""
    from graph import lesson_store
    by, takes = {}, {}
    for kind_, rows in fits_.items():
        if kind_ in lesson_store.FITS:  # this port goes into or onto something
            for r in rows:
                if r["with"] in WAYS:
                    by.setdefault(r["with"], WAYS[r["with"]])
            by.setdefault("pad", WAYS["pad"])
        else:  # things go into this port
            for r in rows:
                if r["with"] in TAKES:
                    takes.setdefault(r["with"], TAKES[r["with"]])
    order = list(WAYS)
    return {"connect_by": [{"way": WAYS[k][0], "tool": TOOL.get(WAYS[k][0]), "text": WAYS[k][1]}
                           for k in sorted(by, key=order.index)],
            "takes": [{"what": k, "text": v} for k, v in takes.items()]}


def strips(card):
    """A breadboard's swap groups, written out: each column-bank's 5 holes ('12t.a'…'12t.e', '12b.f'…'12b.j') and
    each power rail ('tp.1'…'tp.63'). Columns and rail holes run 1-63 (a full breadboard, as the lessons use)."""
    out = []
    for c in range(1, 64):
        out.append({"kind": "strip", "name": f"{c}t", "ports": [f"{c}t.{r}" for r in "abcde"],
                    "why": "one metal strip: the same connection"})
        out.append({"kind": "strip", "name": f"{c}b", "ports": [f"{c}b.{r}" for r in "fghij"],
                    "why": "one metal strip: the same connection"})
    for rail, name in (("tp", "top +"), ("tn", "top −"), ("bp", "bottom +"), ("bn", "bottom −")):
        out.append({"kind": "rail", "name": rail, "ports": [f"{rail}.{n}" for n in range(1, 64)],
                    "why": f"the {name} power rail: one connection"})
    return out


def interchangeable(card):
    """Ports that can stand in for each other, written out as groups [{kind, ports, why}], by code:
      not-polarized   the two legs of a part that is not polarized (a resistor's 1 and 2)
      card-symmetric  groups the card marks as interchangeable (a pushbutton's sides)
      same-pin        pins marked the same (the Uno's GND.1, GND.2, GND.3)
      joined-inside   ports joined inside the part (a wire's two ends)
      strip, rail     a breadboard's 5-hole strips and its power rails"""
    ports = card.get("ports", [])
    ib = card.get("intrinsic_behaviour") or {}
    out = []
    legs = [p["id"] for p in ports if p["kind"] in ("lead", "pin")]
    if len(legs) == 2 and not ib.get("is_polarized"):
        out.append({"kind": "not-polarized", "ports": legs, "why": "not polarized: either leg in either place"})
    for g in ib.get("symmetric_port_groups") or []:
        if sorted(g) != sorted(legs):
            out.append({"kind": "card-symmetric", "ports": list(g), "why": "the card marks them as interchangeable"})
    same = {}
    for p in ports:
        if p.get("same_as"):
            same.setdefault(p["same_as"], []).append(p["id"])
    for name, ids in same.items():
        if len(ids) > 1:
            out.append({"kind": "same-pin", "name": name, "ports": ids, "why": f"all {name}: any one can be used"})
    for g in ib.get("internal_conducts") or []:
        if len(g) > 1:
            out.append({"kind": "joined-inside", "ports": list(g), "why": "joined inside the part: either one either way"})
    if any("<" in p["id"] for p in ports) and "strip" in (card.get("port_rule") or ""):
        out += strips(card)
    return out


SAME = ("strip", "rail", "same-pin")                         # groups that are one connection: any port in it will do
EITHER_WAY = ("not-polarized", "card-symmetric", "joined-inside")  # groups whose ports swap: either way round


def connection(card, port):
    """The connection a port is part of, from the card's stored groups: (kind, name) for a strip, a rail or a
    same-pin group ('strip', '12t'), or None when the port stands alone."""
    for g in ((card or {}).get("metadata") or {}).get("interchangeable") or []:
        if g.get("kind") in SAME and port in g.get("ports", []):
            return g["kind"], g.get("name") or g["ports"][0]
    return None


def either_way(card):
    """The card's groups of ports that may swap (a resistor's legs, a wire's ends): [[port, ...]]."""
    return [list(g["ports"]) for g in ((card or {}).get("metadata") or {}).get("interchangeable") or []
            if g.get("kind") in EITHER_WAY]


def swaps(part, port, parts=None):
    """The ports this one can stand in for (and that can stand in for it), from the part's stored groups:
    swaps("breadboard", "12t.c") -> ["12t.a", "12t.b", "12t.d", "12t.e"]. Worked out on read, not stored per port."""
    parts = parts or load()
    groups = ((parts.get(part) or {}).get("metadata") or {}).get("interchangeable") or []
    return sorted({x for g in groups if port in g.get("ports", []) for x in g["ports"] if x != port})


def build(path=PATH):
    """parts.json from the card stores: each card as it is (its own `domain` field moves into metadata), with the
    metadata block it already had here (or in the old part_metadata.json). Returns {domain: count}."""
    from graph.filelock import locked
    with locked(path):
        return _build(path)


def _build(path):
    parts = load(path)
    old = json.loads(OLD_METADATA.read_text()) if OLD_METADATA.exists() else {}
    examples = collections.defaultdict(list)  # a port kind -> the electronics parts that have it
    for t, card in sorted(json.loads((ROOT / STORES["arduino"]).read_text()).items()):
        for k in sorted({p["kind"] for p in card.get("ports", [])}):
            if t not in examples[k]:
                examples[k].append(t)
    out, counts = {}, collections.Counter()
    for domain, rel in STORES.items():
        for t, card in json.loads((ROOT / rel).read_text()).items():
            if t in out:
                raise ValueError(f"{t} is in two card stores")
            meta = dict((parts.get(t) or {}).get("metadata") or {})
            if not meta.get("description") and t in old:
                meta.update(old[t])
            meta.pop("part_type_id", None)
            meta.update({"domain": domain, "source_catalogue": rel,
                         "card_made_by": (card.get("source") or {}).get("made_by")})
            if t in SUBSTITUTES or domain == "lego":
                meta["substitutes"] = SUBSTITUTES.get(t) or SUBSTITUTES["lego"]
            entry = json.loads(json.dumps({**{k: v for k, v in card.items() if k != "domain"}, "metadata": meta}))
            from graph.parts.part_metadata import normalize  # codes, not free text (stored metadata from before is converted)
            entry["metadata"] = normalize(entry["metadata"])
            if domain == "arduino":  # a copy: the card store is not changed
                pins.annotate(entry, pins.cq_card(t))
                entry["metadata"]["fits"] = fits(entry, examples)  # by code, after the pin facts (same_as)
                entry["metadata"]["interchangeable"] = interchangeable(entry)
                entry["metadata"].update(connect_by(entry["metadata"]["fits"]))
            out[t] = entry
            counts[domain] += 1
    save(out, path)
    return dict(counts)


def stats(parts):
    rows = {}
    for domain in STORES:
        d = of_domain(parts, domain)
        drafted = [v for v in d.values() if v["metadata"].get("description")]
        rows[domain] = {"parts": len(d), "with_metadata": len(drafted),
                        "with_joins": sum(1 for v in drafted if v["metadata"].get("joins")),
                        "checks_failed": sum(1 for v in drafted if v["metadata"].get("checks_failed"))}
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "stats"])
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(f"{PATH.relative_to(ROOT)}: {build()}")
    for domain, row in stats(load()).items():
        print(f"  {domain:8} {row}")


if __name__ == "__main__":
    main()
