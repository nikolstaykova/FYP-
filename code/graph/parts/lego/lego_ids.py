"""When a LEGO inventory row and a piece of the 3D model are the same part.

What it is   Rebrickable numbers the inventory, LDraw numbers the 3D model, and the two disagree in known ways; each
             rule below names the evidence it used (colour spelling, prints, moulds, names, LDraw aliases,
             assemblies and minifigures, LDraw shortcuts like a wheel with its tyre).
Used for     matching a set's parts list to its 3D model's pieces (the 3D route's parts list, the booklet route's
             score and sizes).
Where        lesson_store.py (match), lego_booklet/pdf_lesson.py and booklet_size.py; scoring tools in
             code/tests/tools.

Rebrickable numbers the inventory; LDraw numbers the 3D model; the two disagree in known ways. Each rule names the
evidence it used, and they are tried in this order:
  colour     colour names spelt differently: "Trans-Neon Green" (Rebrickable) is "Trans Neon Green"
  print      a printed piece is its base design: 3003pe2 and 3003pr0053 are 3003 (the `pr`/`p` suffix, Rebrickable P)
  mould      a mould variant is the same shape: 3747a and 3747b, 4222 and 4222a (a letter suffix, Rebrickable M or A)
  name       the same name in both catalogues: LDraw 30039 "Tile 1 x 1 with Groove" is Rebrickable 3070b
  ldraw      LDraw moved or aliased the number: the model's 50746 is the library's 54200 (Rebrickable's number)
  assembly   an inventory row that is several pieces in the model: Rebrickable's sub-parts (B: the lever 298c02 is
             the base 4592 and the stick 4593), or a minifigure's legs (970c..: hips 3815, legs 3816 and 3817) and
             torso (973c..: torso 973, arms 3818 and 3819, two hands 3820); its pieces may be other colours
A part that matches only in another colour is matched as `colour differs` (the AR check accepts a colour swap), and
anything else stays a problem.
"""
import collections
import functools
import gzip
import csv
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[4]
DUMP = ROOT / "data" / "sources" / "rebrickable"


def colour_key(c):
    """A colour name compared across catalogues: spaces and hyphens, gray/grey, a material word (Rubber Black is
    Black) left out."""
    c = re.sub(r"\bgray\b", "grey", str(c or "").lower())
    c = re.sub(r"\b(rubber)\b", "", c)
    return re.sub(r"[^a-z0-9]", "", c)


def _num(t):
    return t[len("lego-"):] if t.startswith("lego-") else t


def base(t):
    """The design under prints and mould letters: 3003pr0053 -> 3003, 3747b -> 3747, 3626bp85 -> 3626, 30039 -> 30039."""
    n = _num(t)
    n = re.sub(r"(?<=\d)([a-z]?)(pr\d+|pe?\d+|p[a-z0-9]+)$", r"\1", n)  # 3626bp85 and 3626bpr0387: 3626b
    n = re.sub(r"(?<=\d)[a-z]$", "", n)
    return n


# A print on the end of a part number: 3626cpr0914 (a face), 3069bpw2, 4150ps4, 3003pe2, 3960p07; also on an
# assembly, 973c28h01pr1470. The mould letter (the c of 3626c) and an assembly's code (c28h01) stay.
PRINT = re.compile(r"(?<=[0-9a-z])(pr\d+[a-z]?|pe\d+|p[a-z]{0,2}\d+[a-z]?)$")


def unprinted(t):
    """A printed piece is its plain piece with a print: lego-3626cpr0914 -> ("lego-3626c", "pr0914"). The print is
    a property of the copy, like its colour, so the catalogue keeps one card per design (one minifig head, whatever
    its face). Not printed: (t, "")."""
    t = str(t or "")
    if not t.startswith("lego-"):
        return t, ""
    m = PRINT.search(t)
    if not m or not re.search(r"\d", t[len("lego-"):m.start()]):
        return t, ""
    return t[:m.start()], m.group(1)


def unprint_graphs(graphs):
    """A lesson's graphs with every printed LEGO piece as its plain piece and the print on the copy: nodes get
    `type` plain and props.print; parts-list rows get `part` plain and `print`. Changes `graphs` in place; returns
    how many were changed."""
    n = 0
    for kind, g in graphs.items():
        if not g:
            continue
        for node in g.get("nodes", []):
            plain, pr = unprinted(node.get("type"))
            if pr:
                node["type"] = plain
                node.setdefault("props", {})["print"] = pr
                n += 1
        rows = (g.get("parts_list") or {}) if kind == "lesson" else {}
        for r in (rows.get("parts", []) if isinstance(rows, dict) else rows):
            plain, pr = unprinted(r.get("part") or r.get("type"))
            if pr:
                r["part" if "part" in r else "type"] = plain
                r["print"] = pr
                n += 1
    return n


@functools.lru_cache(maxsize=1)
def _relations():
    """Rebrickable's print (P), mould (M) and alternate (A) links as groups of the same part: {part: group id}."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    f = DUMP / "part_relationships.csv.gz"
    if f.exists():
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh):
                if r["rel_type"] in ("P", "M", "A"):
                    parent[find(r["child_part_num"])] = find(r["parent_part_num"])
    return {k: find(k) for k in parent}


@functools.lru_cache(maxsize=1)
def _sub_parts():
    """Rebrickable's assemblies (B): {assembly: [its parts]}."""
    out = collections.defaultdict(list)
    f = DUMP / "part_relationships.csv.gz"
    if f.exists():
        with gzip.open(f, "rt") as fh:
            for r in csv.DictReader(fh):
                if r["rel_type"] == "B":
                    out[r["parent_part_num"]].append(r["child_part_num"])
    return dict(out)


MINIFIG = ((re.compile(r"^970c"), ("3815", "3816", "3817")),                    # legs: hips, right leg, left leg
           (re.compile(r"^973c"), ("973", "3818", "3819", "3820", "3820")),     # torso, arms, two hands
           (re.compile(r"^92456c01"), ("92241", "92244", "92245")),             # minidoll torso: torso, two arms
           (re.compile(r"^928(1[5-9]|2\d)c01"), ("92248", "~friends legs")))   # minidoll legs: hips, the legs


@functools.lru_cache(maxsize=1)
def _assemblies():
    f = ROOT / "data" / "reference" / "lego_assemblies.json"
    return {k: v for k, v in json.loads(f.read_text()).items() if not k.startswith("_")} if f.exists() else {}


def components(part):
    """The pieces an assembly row is in a 3D model, or None (not an assembly)."""
    n = _num(part)
    figure = next((parts for rx, parts in MINIFIG if rx.match(n)), None)
    if n in _sub_parts():
        comps = tuple(_sub_parts()[n])
        # a minifigure part Rebrickable lists short (a printed torso with no arms or hands, 973c05h01pr1163 -> 973pdd):
        # the figure is still built of all its pieces, as the minifigure rule says
        return figure if figure and len(comps) < len(figure) else comps
    if n in _assemblies():
        return tuple(_assemblies()[n])
    return figure


@functools.lru_cache(maxsize=None)
def shortcut_parts(part):
    """The parts an LDraw shortcut is made of (6014bc02, a wheel rim with its tyre: 6014b, 87697), or None: a 3D model
    may hold as one piece what the set's inventory lists as its parts."""
    try:
        from graph import lego_model
        ref = lego_model.resolve(f"{_num(part)}.dat")
        text = lego_model.text_of(ref) or ""
    except Exception:  # no LDraw library here
        return None
    if not re.search(r"(?m)^0 !LDRAW_ORG\s+(Unofficial_)?Shortcut\b", text):
        return None
    refs = [r[:-4] for r in lego_model._refs(text.splitlines()) if r.endswith(".dat")]
    return tuple(refs) if len(refs) >= 2 else None


def _ldraw(n):
    try:
        from graph.parts.ingest import ldraw_current
        return ldraw_current(n)
    except Exception:  # no LDraw library here: the rule does not apply
        return None


def _name_key(name):
    n = str(name or "").lower().replace("~", "")
    n = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def same_part(row_part, row_name, piece_type, piece_name):
    """The rule by which an inventory row's part is this model piece's part, or None."""
    a, b = _num(row_part), _num(piece_type)
    if a == b:
        return "exact"
    if a.startswith("~"):  # an assembly's piece known by its name only ('~friends legs')
        return "by name" if all(w in _name_key(piece_name) for w in a[1:].split()) else None
    rel = _relations()
    if base(a) == base(b) or (a in rel and rel.get(a) == rel.get(b)) or rel.get(a, a) == rel.get(base(b), base(b)):
        return "print or mould of the same design"
    if row_name and piece_name and _name_key(row_name) == _name_key(piece_name):
        return "the same name in both catalogues"
    cur = _ldraw(b)
    if cur and (cur == a or base(cur) == base(a)):
        return f"LDraw's {b} is {cur}"
    return None


def match(rows, pieces):
    """Each inventory row -> the model pieces it accounts for (in place: row["instances"], row["matched_by"]).
    rows: [{part, count, colour, name}]; pieces: [{id, type, label, props: {colour}}]. Returns [problem]."""
    free = list(pieces)
    problems, notes = [], []
    parts_of = {}  # an assembly row -> one row per piece it is in the model, any colour
    for row in rows:
        comps = components(row["part"])
        if comps and not any(_num(n["type"]) == _num(row["part"]) for n in pieces):  # the model may have it whole
            parts_of[id(row)] = [{"part": c if c.startswith("~") else f"lego-{c}", "count": row["count"], "colour": None,
                                  "of": row["part"]} for c in comps]
    work = [x for row in rows for x in parts_of.get(id(row), [row])]
    for colour_must in (True, False):  # same colour first, then the same part in another colour
        for row in work:
            got = row.setdefault("instances", [])
            need = (row["count"] or 0) - len(got)
            if need <= 0:
                continue
            for n in list(free):
                if need <= 0:
                    break
                rule = same_part(row["part"], row.get("name"), n["type"], n.get("label"))
                if not rule:
                    continue
                same_colour = colour_key(row.get("colour")) == colour_key((n.get("props") or {}).get("colour"))
                if colour_must and not same_colour and not row.get("of"):
                    continue
                got.append(n["id"])
                free.remove(n)
                need -= 1
                why = rule if same_colour else f"{rule}; colour differs ({n['props'].get('colour')} in the model)"
                if row.get("of"):
                    why = f"part of the assembly {row['of']}"
                row.setdefault("matched_by", {})[n["id"]] = why
                if not same_colour and not row.get("of"):
                    notes.append(f"{n['id']}: {row['part']} is {row.get('colour')} in the inventory, "
                                 f"{n['props'].get('colour')} in the model")
    for n in list(free):  # a model piece that is a shortcut (rim with tyre) for rows the list has apart
        comps = shortcut_parts(n["type"]) or ()
        took = False
        for c in comps:
            row = next((r for r in work if (r["count"] or 0) > len(r.get("instances", []))
                        and same_part(r["part"], r.get("name"), f"lego-{c}", None)), None)
            if row:
                row["instances"].append(n["id"])
                row.setdefault("matched_by", {})[n["id"]] = f"part of the model's {_num(n['type'])} (LDraw shortcut)"
                took = True
        if took:
            free.remove(n)
    for row in rows:  # an assembly row holds the pieces it was found as
        for x in parts_of.get(id(row), []):
            row.setdefault("instances", []).extend(x.get("instances", []))
            row.setdefault("matched_by", {}).update(x.get("matched_by", {}))
    for row in rows:
        short = [x for x in parts_of.get(id(row), []) if len(x.get("instances", [])) < (x["count"] or 0)]
        if parts_of.get(id(row)):
            if short:
                problems.append(f"{row['part']} {row.get('colour', '')}: the assembly's "
                                f"{', '.join(x['part'] for x in short)} not all in the model")
            continue
        if len(row.get("instances", [])) < (row["count"] or 0):
            problems.append(f"{row['part']} {row.get('colour', '')}: the list says {row['count']}, "
                            f"the model has {len(row['instances'])}")
    problems += [f"{n['id']} ({n['type']}, {n.get('label', '')}) is in the model but not on the inventory" for n in free]
    return problems, notes
