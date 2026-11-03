"""Do repeated LEGO sub-assemblies ever differ between copies?

For every downloaded LDraw MPD (research/raw/lego/*.mpd, from lego_ldraw.py):
  1. Exact reuse: a submodel referenced N > 1 times. Do the references use
     different colours? (A reference's colour replaces colour 16, "main
     colour", inside the submodel, so one definition can appear in several
     colours.) Are any references mirrored (determinant of the 3x3 matrix < 0)?
  2. Near-copies: pairs of *different* submodels with the same parts but
     different colours, or the same parts except one or two, or names like
     left/right. These are "same as before, but ..." variations.

Writes research/data/lego_repeats.json.

Run: .venv-research/bin/python research/scrape/lego_repeats.py
"""
import collections
import glob
import itertools
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "raw" / "lego"
OUT = ROOT / "research" / "data" / "lego_repeats.json"


def split_files(text):
    files, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^0 FILE (.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            files[current] = []
        elif current:
            files[current].append(line)
    return files


def refs(lines):
    """(colour, part/submodel name, determinant) for each type-1 line."""
    out = []
    for line in lines:
        b = line.split()
        if len(b) >= 15 and b[0] == "1":
            a, bb, c, d, e, f, g, h, i = map(float, b[5:14])
            det = a * (e * i - f * h) - bb * (d * i - f * g) + c * (d * h - e * g)
            out.append((b[1], " ".join(b[14:]).strip().lower(), det))
    return out


def main():
    exact, near, totals = [], [], collections.Counter()
    for path in sorted(glob.glob(str(RAW / "*.mpd"))):
        setnum = pathlib.Path(path).stem
        files = split_files(pathlib.Path(path).read_text(errors="replace"))
        names = set(files)
        uses = collections.defaultdict(list)  # submodel -> [(colour, det)]
        for parent, lines in files.items():
            for colour, name, det in refs(lines):
                if name in names:
                    uses[name].append((colour, det))
        content = {n: collections.Counter((c, p) for c, p, _ in refs(ls) if p not in names) for n, ls in files.items()}
        shape = {n: collections.Counter(p for (_, p), k in content[n].items() for _ in range(k)) for n in files}

        for name, u in uses.items():
            if len(u) < 2:
                continue
            colours = sorted({c for c, _ in u})
            mirrored = sum(1 for _, det in u if det < 0)
            uses_16 = any(c == "16" for (c, _), _ in content[name].items())
            totals["reused submodels"] += 1
            if len(colours) > 1 and uses_16:
                totals["reused with different colours"] += 1
            if mirrored:
                totals["reused with a mirrored copy"] += 1
            exact.append({"set": setnum, "submodel": name, "copies": len(u), "ref_colours": colours,
                          "inherits_colour": uses_16, "mirrored_copies": mirrored})

        for a, b in itertools.combinations(sorted(n for n in files if sum(shape[n].values()) >= 3), 2):
            sa, sb = shape[a], shape[b]
            if sa == sb and content[a] != content[b]:
                kind = "same parts, different colours"
            elif sa != sb and sum(((sa - sb) + (sb - sa)).values()) <= 2 and sum(sa.values()) >= 4:
                kind = "same except 1-2 parts"
            elif re.sub(r"(left|right|_l\b|_r\b|\bl\b|\br\b)", "", a) == re.sub(r"(left|right|_l\b|_r\b|\bl\b|\br\b)", "", b) and a != b:
                kind = "left/right pair"
            else:
                continue
            diff = {"only_in_a": dict(sa - sb), "only_in_b": dict(sb - sa)} if kind == "same except 1-2 parts" else {}
            near.append({"set": setnum, "a": a, "b": b, "kind": kind, **diff})
            totals[kind] += 1
    result = {"totals": dict(totals), "exact_reuse": exact, "near_copies": near}
    OUT.write_text(json.dumps(result, indent=1))
    print(json.dumps(result["totals"], indent=1))
    for e in [e for e in exact if len(e["ref_colours"]) > 1 or e["mirrored_copies"]][:12]:
        print("  reuse:", e)
    for n in near[:25]:
        print("  near: ", n)


if __name__ == "__main__":
    main()
