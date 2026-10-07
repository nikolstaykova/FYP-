"""v7 LEGO answer key from stud geometry: which pieces of a set really connect, from its LDraw model.

  python -m graphgen.stud_key            builds research/data/lego_stud_key.json for every set (about a minute)

The v1-v6 key (truth.lego_truth) compared box footprints of plain bricks, plates and tiles named in the parts list,
and expanded parts embedded in a model file into their primitives. This key uses the parts library's own connection
points (ldraw_studs.py): a stud of one piece inside a receptacle cell of another (clutch), or a pin/axle along a hole
(pin), for EVERY kind of piece. How we know it is right:
  1. hand-built test models with known answers (tests/test_graphgen.py: stacked, offset, crossed, side by side,
     floating, off-grid, bridging, tiles both ways, a tower)
  2. physical laws on every set's model (ldraw_studs.validate, G1-G4)
  3. agreement with the box method on pieces resting on pieces (ldraw_studs.cross_check)
A stud that two pieces seem to hold (G1; curved slopes and wing plates overlap their neighbours' boxes) makes those
joins AMBIGUOUS: not expected, and not counted wrong if a build names them. A set is TRUSTED when its model has the
set's piece count (within 5%), breaks no law G2/G3 and at most 2% of its joins are ambiguous; scores are given for
all sets and for trusted sets only.
"""
import collections
import functools
import json
import pathlib
import re
import time

from . import ldraw_geometry as geo
from . import ldraw_studs, truth

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "data" / "lego_stud_key.json"


ALIASES = {"50746": "54200"}  # same piece, named differently by LDraw and Rebrickable, and not in its relationships
VARIANT = re.compile(r"^(\d+)[a-z]?(?:pr\d+|p[0-9a-z]{2,4})?$")  # 3794a, 3794b, 3626bp01, 3069bpr0001 -> base number


@functools.lru_cache(maxsize=None)
def _classes():
    """Union of designs Rebrickable says are the same piece: mould variants (M), alternates (A), prints (P)."""
    import csv
    import gzip
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x
    path = ROOT / "research" / "raw" / "rebrickable" / "part_relationships.csv.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["rel_type"] in ("M", "A", "P"):
                    a, b = find(r["child_part_num"].lower()), find(r["parent_part_num"].lower())
                    if a != b:
                        parent[max(a, b)] = min(a, b)
    return {x: find(x) for x in list(parent)}


def canon(d):
    """One name per physical piece, so the parts list (Rebrickable) and the 3D model (LDraw) can be compared:
    Rebrickable's relationships, then letter variants and prints of one number, then a short alias list."""
    if not d:
        return d
    d = ALIASES.get(d.lower(), d.lower())
    d = _classes().get(d, d)
    m = VARIANT.match(d)
    return m.group(1) if m else d


def design(ref):
    """LDraw file -> design number as the parts list writes it ('3001.dat' -> '3001'; a part embedded in a model
    file is named '<set> - <design>.dat')."""
    name = ref.rsplit("/", 1)[-1]
    name = re.sub(r"\.dat$", "", name)
    return re.sub(r"^\d+(-\d+)? - ", "", name)


def key_for(set_id, pieces_in_set):
    t0 = time.monotonic()
    text = (ROOT / "research" / "raw" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    geo.register(text)
    placed = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(truth.flatten_mpd(text), 1)]
    found = ldraw_studs.connections(placed)
    issues = ldraw_studs.validate(placed, found)
    laws = collections.Counter(rule for rule, _ in issues)
    # a stud two pieces seem to hold (G1: curved slopes and wing plates overlap their neighbours' boxes): which one
    # holds it cannot be told, so those joins are AMBIGUOUS: not expected, and not wrong if a build names them
    ambiguous = set()
    for rule, msg in issues:
        if rule == "G1":
            stud_of = re.match(r"stud \d+ of (\S+) ", msg).group(1)
            ambiguous |= {frozenset((stud_of, h)) for h in re.findall(r"'([^']+)'", msg)}
    cross = ldraw_studs.cross_check(placed, found)
    des = {nid: canon(design(ref)) for nid, ref, _, _ in placed}
    pairs, unsure = collections.Counter(), collections.Counter()
    for k, v in found.items():
        a, b = sorted(des[x] for x in k)
        (unsure if k in ambiguous else pairs)[f"{a}|{b}|{v[0]}"] += 1
    n = len(placed)
    trusted = (abs(n - pieces_in_set) <= 0.05 * pieces_in_set and not (laws["G2"] or laws["G3"])
               and sum(unsure.values()) <= 0.02 * max(1, len(found)))
    return {"pieces_model": n, "pieces_set": pieces_in_set, "joins": len(found),
            "clutch": sum(1 for v in found.values() if v[0] == "clutch"),
            "pin": sum(1 for v in found.values() if v[0] == "pin"),
            "pairs": dict(pairs), "ambiguous": dict(unsure), "designs": sorted(set(des.values())),
            "laws": dict(laws), "boxes_only": len(cross["boxes_only"]), "studs_only": len(cross["studs_only"]),
            "trusted": trusted, "seconds": round(time.monotonic() - t0, 2)}


def load():
    """{set: key} with pairs as Counter[(design a, design b)] (clutch and pin together)."""
    raw = json.loads(OUT.read_text())
    out = {}
    for s, k in raw.items():
        pairs = collections.Counter()
        for p, n in k["pairs"].items():
            a, b, _ = p.split("|")
            pairs[(a, b)] += n
        unsure = collections.Counter()
        for p, n in k.get("ambiguous", {}).items():
            a, b, _ = p.split("|")
            unsure[(a, b)] += n
        out[s] = {**k, "pairs": pairs, "ambiguous": unsure, "designs": set(k["designs"])}
    return out


def main():
    sets = json.loads((ROOT / "research" / "data" / "lego_dataset.json").read_text())
    out = {}
    for c in sets:
        out[c["set"]] = key_for(c["set"], c["pieces"])
        k = out[c["set"]]
        print(f"{c['set']:9} model {k['pieces_model']:4} / set {k['pieces_set']:4}  joins {k['joins']:4} "
              f"(clutch {k['clutch']}, pin {k['pin']})  laws {k['laws'] or '-'}  boxes-only {k['boxes_only']} "
              f"studs-only {k['studs_only']}  {'TRUSTED' if k['trusted'] else 'not trusted'}", flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    t = [k for k in out.values() if k["trusted"]]
    print(f"\n{len(out)} sets, {len(t)} trusted; joins {sum(k['joins'] for k in out.values())} "
          f"({sum(k['joins'] for k in t)} in trusted sets); written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
