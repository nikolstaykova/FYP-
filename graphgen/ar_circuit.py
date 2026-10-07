"""AR support for electronics (v6 graphs): the circuit as steps an AR app can play and check.

  python -m graphgen.ar_circuit <run dir> [...]   writes <case>/ar_steps.json for every tutorial and AR_REPORT.md

1. Anchor. The breadboard (else the board): hole '12t.c' is column 12, row c, and every hole has a position in
   millimetres from the breadboard's top-left hole (0.1 inch pitch, the centre channel 0.3 inch, rails above and
   below). The board's header pins have positions on the Arduino Uno R3 shield layout. The app finds the breadboard
   in the camera image; from then on every hole is a fixed offset.
2. Steps, by code (no model call): the board and the breadboard; then one step per component, left to right on
   the breadboard, each leg with its hole (and which leg is + on polarised parts); then the wires, signal wires
   first and power and ground wires last (so nothing is powered half-built), each end with its hole or pin and the
   wire's colour. The tutorial's own circuit pictures go with the export.
3. Live check (`check_step`). Holes of one 5-hole strip, one power rail, or the board's GND pins are the same
   electrically: a leg one hole along the strip is RIGHT (equivalent), not wrong. Each expected leg or wire end is
   right, equivalent, wrong (where it went instead) or missing; `check_circuit` compares the whole circuit's nets.
"""
import collections
import json
import pathlib
import re
import sys

from . import catalogue as cat
from . import logical

ROOT = pathlib.Path(__file__).resolve().parents[1]
PITCH = 2.54  # mm
HOLE = re.compile(r"^(\d+)([tb])\.([a-j])$")
RAIL = re.compile(r"^([tb])([pn])\.(\d+)$")
POWER = re.compile(r"^(5V|3\.3V|3V3|VIN|GND(\.\d+)?|IOREF)$", re.I)

# Arduino Uno R3 header pins, inches from the board's lower-left corner (the shield template)
UNO_PINS = {**{str(d): (2.6 - 0.1 * d, 2.0) for d in range(8)},
            **{str(d): (1.74 - 0.1 * (d - 8), 2.0) for d in range(8, 14)},
            "GND.3": (1.14, 2.0), "AREF": (1.04, 2.0),
            "IOREF": (1.1, 0.1), "RESET": (1.2, 0.1), "3.3V": (1.3, 0.1), "5V": (1.4, 0.1), "GND.1": (1.5, 0.1),
            "GND.2": (1.6, 0.1), "VIN": (1.7, 0.1),
            **{f"A{a}": (1.9 + 0.1 * a, 0.1) for a in range(6)}}


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


def pin_mm(pin):
    p = UNO_PINS.get(str(pin).upper().replace("3V3", "3.3V")) or UNO_PINS.get(str(pin))
    return [round(p[0] * 25.4, 2), round(p[1] * 25.4, 2)] if p else None


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


def _at(kind, where):
    part, port = where
    return {"part": part, "port": port,
            "mm": hole_mm(port) if kind.get(part) == "breadboard" else pin_mm(port) if kind.get(part) == "board" else None}


def export(case_id, flat, catalogue, images=()):
    kind = _kinds(flat)
    nodes = {n["id"]: n for n in flat["nodes"]}
    where = placements(flat)
    anchor = next((i for i, k in kind.items() if k == "breadboard"), None) or next((i for i, k in kind.items() if k == "board"), None)
    steps = [{"step": 1, "say": "Put the board and the breadboard in front of you.",
              "add": [{"id": i, "type": nodes[i]["type"], "label": nodes[i].get("label")} for i, k in kind.items()
                      if k in ("board", "breadboard")]}]

    def leftmost(i):
        xs = [m[0] for p in where.get(i, {}).values() if (m := hole_mm(p[1]))]
        return min(xs) if xs else 1e9
    comps = sorted((i for i, k in kind.items() if k == "component"), key=lambda i: (leftmost(i), i))
    for i in comps:
        card = catalogue.get(nodes[i]["type"]) or {}
        legs = [{"leg": port, **_at(kind, w)} for port, w in sorted(where.get(i, {}).items())]
        steps.append({"step": len(steps) + 1, "add": [{"id": i, "type": nodes[i]["type"], "label": nodes[i].get("label"),
                                                        "props": nodes[i].get("props"), "polarised": bool(card.get("polarized")),
                                                        "legs": legs}]})
    wires = [i for i, k in kind.items() if k == "wire"]
    power = lambda i: any(POWER.match(str(w[1])) or RAIL.match(str(w[1]) or "") for w in where.get(i, {}).values())
    for i in sorted(wires, key=lambda i: (power(i), leftmost(i), i)):
        ends = [_at(kind, w) for _, w in sorted(where.get(i, {}).items())]
        steps.append({"step": len(steps) + 1, "power": power(i),
                      "add": [{"id": i, "type": nodes[i]["type"], "colour": (nodes[i].get("props") or {}).get("colour"),
                               "label": nodes[i].get("label"), "ends": ends}]})
    placed = sum(1 for s in steps for a in s["add"] for x in a.get("legs", []) + a.get("ends", []) if x["mm"])
    total = sum(1 for s in steps for a in s["add"] for x in a.get("legs", []) + a.get("ends", []))
    return {"tutorial": case_id, "anchor": {"id": anchor, "type": nodes[anchor]["type"] if anchor else None,
                                            "how": "lock onto the breadboard: hole 1t.a is (0, 0) mm, x along the "
                                                   "columns, y down the rows (the board's pins: Uno R3 shield layout)"},
            "reference_images": list(images), "legs_and_ends": total, "with_position": placed, "steps": steps}


def _expected(ar, step):
    s = next(s for s in ar["steps"] if s["step"] == step)
    out = []
    for a in s["add"]:
        for x in a.get("legs", []):
            out.append((a["id"], x["leg"], (x["part"], x["port"])))
        for n, x in enumerate(a.get("ends", []), 1):
            out.append((a["id"], f"end{n}", (x["part"], x["port"])))
    return out


def check_step(ar, step, observed):
    """observed: [{id, leg (or end1/end2), part, port}] as the camera read them. Each expected leg or wire end is
    right (that hole), equivalent (same strip, rail or GND), wrong (somewhere else) or missing. A wire's two ends
    may be swapped."""
    want = _expected(ar, step)
    seen = {(o["id"], o.get("leg")): (o["part"], o["port"]) for o in observed}
    result = {"step": step, "right": [], "equivalent": [], "wrong": [], "missing": []}
    by_wire = collections.defaultdict(list)
    for i, leg, w in want:
        if leg.startswith("end"):
            by_wire[i].append(w)
            continue
        got = seen.get((i, leg))
        if got is None:
            result["missing"].append(f"{i}.{leg}")
        elif got == w:
            result["right"].append(f"{i}.{leg}")
        elif strip(got) == strip(w):
            result["equivalent"].append(f"{i}.{leg}")
        else:
            result["wrong"].append({"leg": f"{i}.{leg}", "want": w[1], "got": got[1]})
    for i, ends in by_wire.items():
        got = [w for (j, _), w in seen.items() if j == i]
        if len(got) < len(ends):
            result["missing"].append(i)
            continue
        same = lambda a, b: sorted(map(strip, a)) == sorted(map(strip, b))
        if sorted(got) == sorted(ends):
            result["right"].append(i)
        elif same(got, ends):
            result["equivalent"].append(i)
        else:
            result["wrong"].append({"leg": i, "want": [e[1] for e in ends], "got": [g[1] for g in got]})
    return result


def check_circuit(flat_expected, flat_built, catalogue):
    """The whole circuit: does the built one have the same nets (connections between component legs and board
    pins), whatever holes it uses?"""
    key = lambda f: {frozenset(net) for net in logical.nets(f, catalogue)}
    want, got = key(flat_expected), key(flat_built)
    return {"same": want == got, "missing_nets": [sorted(n) for n in want - got], "extra_nets": [sorted(n) for n in got - want]}


def _images(case):
    path = case.get("path") or ""
    raw = "https://raw.githubusercontent.com/arduino/docs-content/main/"
    try:
        from .run import RAW_DOCS
        raw = RAW_DOCS
    except ImportError:
        pass
    cache = ROOT / "research" / "raw" / "arduino_md" / (case["id"] + ".md")
    if not cache.exists():
        return []
    md = re.split(r"#+\s*Code", cache.read_text(errors="replace"))[0]
    return [raw + path.rsplit("/", 1)[0] + "/" + n for n in re.findall(r"!\[[^\]]*\]\(([^)\s]+\.(?:png|jpe?g|gif|webp))\)", md, re.I)]


def main(argv):
    cases = {c["id"]: c for c in json.loads((ROOT / "research" / "data" / "arduino_dataset.json").read_text())}
    for run in map(pathlib.Path, argv):
        rows = []
        for d in sorted(p for p in run.iterdir() if (p / "graph.json").exists()):
            flat = json.loads((d / "graph.json").read_text())
            resp = json.loads((d / "response.json").read_text()) if (d / "response.json").exists() else {}
            c = cat.Catalogue(cat.arduino_seed())
            for t, card in (resp.get("cards") or {}).items():
                c.entries.setdefault(t, card)
            out = export(d.name, flat, c, _images(cases.get(d.name, {"id": d.name})))
            (d / "ar_steps.json").write_text(json.dumps(out, indent=1))
            # self-check: the export, read back as a camera would, must pass its own check
            ok = all(not (r := check_step(out, s["step"], [
                {"id": a["id"], "leg": x.get("leg", f"end{n}"), "part": x["part"], "port": x["port"]}
                for a in s["add"] for n, x in enumerate(a.get("legs", []) + a.get("ends", []), 1)]))["wrong"]
                and not r["missing"] for s in out["steps"])
            rows.append({"tutorial": d.name, "steps": len(out["steps"]), "legs_and_ends": out["legs_and_ends"],
                         "with_position": out["with_position"], "breadboard": out["anchor"]["type"] == "breadboard",
                         "images": len(out["reference_images"]), "self_check": ok})
        n = sum(r["legs_and_ends"] for r in rows)
        lines = [f"# AR circuits: {run.name}", "",
                 f"{len(rows)} tutorials. {sum(r['breadboard'] for r in rows)} anchored on a breadboard, "
                 f"{len(rows) - sum(r['breadboard'] for r in rows)} on the board. "
                 f"{sum(r['with_position'] for r in rows)} of {n} legs and wire ends "
                 f"({sum(r['with_position'] for r in rows) / max(1, n):.0%}) have a position the overlay can point at. "
                 f"{sum(r['images'] > 0 for r in rows)} have the tutorial's circuit pictures. "
                 f"Self-check passed on {sum(r['self_check'] for r in rows)}.", "",
                 "| Tutorial | Steps | Legs + wire ends | With position | Anchor | Pictures |", "|---|---:|---:|---:|---|---:|"]
        lines += [f"| {r['tutorial']} | {r['steps']} | {r['legs_and_ends']} | {r['with_position']} | "
                  f"{'breadboard' if r['breadboard'] else 'board'} | {r['images']} |" for r in rows]
        (run / "AR_REPORT.md").write_text("\n".join(lines) + "\n")
        (run / "ar_summary.json").write_text(json.dumps(rows, indent=1))
        print(lines[2])


if __name__ == "__main__":
    main(sys.argv[1:])
