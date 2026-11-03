"""v7 LEGO answer key from stud geometry: which pieces of a set really connect, from its LDraw model.

  python -m graph.stud_key            builds data/reference/lego_stud_key.json for every set (about a minute)

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


import ldraw_geometry as geo

import ldraw_studs, truth

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "reference" / "lego_stud_key.json"


ALIASES = {"50746": "54200", "6143": "3941", "14696": "3711"}  # same piece, named differently by LDraw and Rebrickable,
# and not in its relationships (round brick 2x2; chain link)
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
    path = ROOT / "data" / "sources" / "rebrickable" / "part_relationships.csv.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["rel_type"] in ("M", "A", "P"):
                    a, b = find(r["child_part_num"].lower()), find(r["parent_part_num"].lower())
                    if a != b:
                        parent[max(a, b)] = min(a, b)
    return {x: find(x) for x in list(parent)}


@functools.lru_cache(maxsize=None)
def _subparts():
    """Assemblies and the parts they are made of (Rebrickable's 'B' relationships, e.g. 4033c01 -> 4033, 4034)."""
    import csv
    import gzip
    out = collections.defaultdict(list)
    path = ROOT / "data" / "sources" / "rebrickable" / "part_relationships.csv.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["rel_type"] == "B":
                    out[r["parent_part_num"].lower()].append(r["child_part_num"].lower())
    return dict(out)


def _minifig(d):
    """Minifigures compared as figures, not as their parts: a model builds a torso from torso, arms and hands and
    legs from hips and two legs; Rebrickable lists a torso assembly (973c..) and a legs assembly (970c..). Returns
    the token for a torso / legs / head, '' for a part that is inside one, None for anything else."""
    if d.startswith("fabfig"):  # Rebrickable: a Fabuland figure is one piece
        return "fabuland-figure"
    if re.match(r"^u9\d{3}", d) or d.startswith("fab"):
        title = truth.library_title(d + ".dat").lower()
        if title.startswith("figure fabuland torso"):
            return "fabuland-figure"  # the model builds the figure: its torso stands for it
        if title.startswith("figure fabuland"):
            return ""  # arms, legs, hips, head: inside the figure
    if re.match(r"^973", d):
        return "minifig-torso"
    if re.match(r"^(970|3815)", d):
        return "minifig-legs"
    if re.match(r"^(3626|28621)", d):
        return "minifig-head"
    if re.match(r"^(3818|3819|3820|981|982|983|975|976|977|3816|3817|971|972)([a-z]|$)", d):
        return ""
    return None


@functools.lru_cache(maxsize=None)
def _library_assembly(d):
    """The parts a library assembly ('... (Complete)' or a shortcut) is made of, [] if it is not one."""
    title = truth.library_title(d + ".dat")
    text = geo.text_of(d + ".dat") or ""
    if "(complete)" not in title.lower() and not re.search(r"!LDRAW_ORG\s+(Unofficial_)?Shortcut", text, re.I):
        return []
    kids = [r.rsplit("/", 1)[-1].rsplit(".", 1)[0] for r in truth._refs(text.splitlines())
            if not r.startswith(("s/", "p/")) and r.rsplit(".", 1)[0] not in truth._primitives() and r not in truth._primitives()]
    return [k for k in kids if truth.library_title(k + ".dat")]


def designs(counter, split=True):
    """Counter of design names -> the same pieces under one name per physical piece (canon), so a parts list and a 3D
    model that name pieces differently still compare: renamed and alias library parts followed to the real part,
    assemblies split into their parts (Rebrickable's sub-parts or the library's own assembly file), minifigures
    compared as torso / legs / head."""
    out = collections.Counter()
    for d, n in counter.items():
        d = str(d).lower()
        d = truth.resolve(d + ".dat").rsplit(".", 1)[0] if truth.library_title(d + ".dat") else d
        fig = _minifig(d)
        if fig is not None:
            if fig:
                out[fig] += n
            continue
        kids = (_subparts().get(d) or _library_assembly(d)) if split else None
        for k in (kids or [d]):
            out[canon(k)] += n
    return out


def model_designs(text, root=None, split=False):
    """The designs of a model file's pieces (its build `root`); split=True splits its assemblies into their parts."""
    return designs(collections.Counter(design(r) for r, _, _, _ in truth.flatten_mpd(text, root=root)), split=split)


def reconcile(set_id, text=None, root=None):
    """The set as sold and its 3D model, read the same way: the parts list with or without its minifigures (some models
    build the figures, some leave them out), and assemblies whole or split into their parts on either side (one side
    may list a flower stem or a wheel holder as one piece, the other as its parts). The reading under which the two
    agree best wins. Returns (set designs, model designs or None, {"minifigs", "split_set", "split_model"})."""
    from graph.parts.lego import inventory as pl
    models = {False: model_designs(text, root), True: model_designs(text, root, split=True)} if text else {False: None}
    best = None
    for figs in (True, False):
        parts = pl.RebrickableDump.set_parts(set_id, minifigs=figs)
        if not parts:
            return None, None, {}
        raw = collections.Counter()
        for p in parts:
            raw[p["part_num"]] += p["quantity"]
        for split_set in (True, False):
            want = designs(raw, split=split_set)
            for split_model, model in models.items():
                if model is None:
                    return want, None, {"minifigs": figs, "split_set": split_set}
                n, m = sum(want.values()), sum(model.values())
                score = (abs(m - n) <= 0.05 * n, sum((want & model).values()) - abs(n - m))  # within tolerance first
                if best is None or score > best[0]:
                    best = (score, want, model, {"minifigs": figs, "split_set": split_set, "split_model": split_model})
    return best[1], best[2], best[3]


def _name(d):
    from graph.parts.lego import inventory as pl
    p = pl.RebrickableDump.tables()["parts"].get(d)
    return (p["name"] if p else truth.library_title(d + ".dat")).lower()


def _words(name):
    stop = {"with", "and", "the", "of", "for", "x", "fabuland", "equipment", "piece", "complete"}
    return {w for w in re.findall(r"[a-z]+|\d+", name) if w not in stop and (len(w) > 1 or w.isdigit())}


UNOFFICIAL = re.compile(r"^(u\d|fab|upn|x\d|bb\d|fig)")  # numbering schemes outside the official part numbers


def pair_by_name(want, model, threshold=0.5):
    """Last step of reading a set and its model the same way: a piece left over on one side and a piece left over on
    the other, in equal number, whose names describe the same thing ('Fabuland Paint Brush' / 'Fabuland, Equipment
    Paint Brush': same words, different numbering schemes) are counted as one design. Returns the set's designs with
    those renamed to the model's names, and the pairs made."""
    extra, missing = model - want, want - model
    want, pairs = collections.Counter(want), []
    for m, n in sorted(missing.items(), key=lambda t: -t[1]):
        wm = _words(_name(m))
        best = None
        for e, k in extra.items():
            if k != n or not (UNOFFICIAL.match(m) or UNOFFICIAL.match(e)):
                continue
            we = _words(_name(e))
            score = len(wm & we) / max(1, len(wm | we))
            if score >= threshold and (best is None or score > best[0]):
                best = (score, e)
        if best:
            e = best[1]
            want[e] += n
            want[m] -= n
            if want[m] <= 0:
                del want[m]
            del extra[e]
            pairs.append((m, e, round(best[0], 2)))
    return want, pairs


def set_designs(set_id, model=None):
    """reconcile() for callers holding only the model's designs: (set designs, reading)."""
    want, _, how = reconcile(set_id)
    return want, how


def best_root(text, parts_counter):
    """The top-level build of a model file that matches the set best (a file can carry alternate models or extra
    builds): the root whose pieces share the most designs with the parts list."""
    roots = truth.roots(text)
    if len(roots) <= 1:
        return None
    score = lambda r: sum((designs(collections.Counter(design(p) for p, _, _, _ in truth.flatten_mpd(text, root=r)))
                           & parts_counter).values())
    return max(roots, key=score)


def canon(d):
    """One name per physical piece, so the parts list (Rebrickable) and the 3D model (LDraw) can be compared:
    Rebrickable's relationships, then letter variants and prints of one number, then a short alias list."""
    if not d:
        return d
    d = ALIASES.get(d.lower(), d.lower())
    d = _classes().get(d, d)
    m = VARIANT.match(d)
    d = m.group(1) if m else d
    for _ in range(3):  # the alias list again, after the relationships (3711a -> 14696 -> 3711): one fixed name
        d2 = _classes().get(ALIASES.get(d, d), ALIASES.get(d, d))
        m = VARIANT.match(d2)
        d2 = m.group(1) if m else d2
        if d2 == d:
            break
        d = d2
    return d


def design(ref):
    """LDraw file -> design number as the parts list writes it ('3001.dat' -> '3001'; a part embedded in a model
    file is named '<set> - <design>.dat')."""
    if truth.ldraw_key(ref) in truth.LSYNTH_DESIGN:  # a bendable piece LSynth drew as segments
        return truth.LSYNTH_DESIGN[truth.ldraw_key(ref)]
    name = ref.rsplit("/", 1)[-1]
    name = re.sub(r"\.dat$", "", name)
    return re.sub(r"^\d+(-\d+)? - ", "", name)


def key_for(set_id, pieces_in_set, parts_counter=None):
    """The answer key of one set. parts_counter (designs of the set, minifigures included): pick the model's build
    that matches it best and compare piece counts with it, not with pieces_in_set."""
    t0 = time.monotonic()
    text = (ROOT / "data" / "sources" / "lego" / f"{set_id}.mpd").read_text(errors="replace")
    geo.register(text)
    root = best_root(text, parts_counter) if parts_counter else None
    if parts_counter:
        pieces_in_set = sum(parts_counter.values())
    placed = [(f"b{i}", ref, pos, rot) for i, (ref, _, pos, rot) in enumerate(truth.flatten_mpd(text, root=root), 1)]
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
    sets = json.loads((ROOT / "data" / "reference" / "lego_dataset.json").read_text())
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
