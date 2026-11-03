"""Why do the remaining OMR models not match their sets? Every MISMATCH set of research/data/omr_audit.json, read the
same way the audit reads it (stud_key.reconcile), with the full list of pieces the model has extra and the pieces it
is missing, by name, grouped by kind of piece.

  .venv-research/bin/python research/scrape/omr_mismatch.py
Writes research/data/omr_mismatch.json (per set) and research/data/omr_mismatch.md (summary).
"""
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from graphgen import stud_key, truth  # noqa: E402
from graphgen.parts import lego as pl  # noqa: E402

KINDS = [  # (kind, pattern on the piece's name), first match wins
    ("minifigure / accessory", r"minifig|^minifig-|hair|helmet|cap\b|hat\b|weapon|sword|gun|tool|cup|utensil|animal"),
    ("sticker", r"sticker"),
    ("bendable (hose, cable, string, chain, band)", r"hose|cable|string|chain|rubber band|lsynth|tube|track link|tread"),
    ("Technic pin / axle / connector", r"technic.*(pin|axle|connector|bush)|^pin\b|axle"),
    ("plant / flower / decoration", r"plant|flower|leaves|stem|grass|decorat"),
    ("tile", r"\btile\b"),
    ("plate", r"\bplate\b"),
    ("brick", r"\bbrick\b"),
    ("slope", r"\bslope\b"),
    ("wheel / tyre", r"wheel|tyre|tire|rim\b"),
]


def name_of(design):
    p = pl.RebrickableDump.tables()["parts"].get(design)
    if p:
        return p["name"]
    t = truth.library_title(design + ".dat")
    return t.lstrip("~=_ ") or design


def kind_of(name):
    low = name.lower()
    for kind, pat in KINDS:
        if re.search(pat, low):
            return kind
    return "other"


def main():
    rows = [r for r in json.loads((ROOT / "research" / "data" / "omr_audit.json").read_text()) if r["class"] == "MISMATCH"]
    out, extra_all, missing_all = [], collections.Counter(), collections.Counter()
    by_cause = collections.defaultdict(list)
    for r in rows:
        s = r["set"]
        text = (ROOT / "research" / "raw" / "lego" / f"{s}.mpd").read_text(errors="replace")
        want, model, how = stud_key.reconcile(s, text, r.get("root"))
        if want is None:
            continue
        extra, missing = model - want, want - model
        row = {"set": s, "name": r["rebrickable_name"], "cause": r["why"], "model": sum(model.values()),
               "set_pieces": sum(want.values()), "reading": how,
               "extra": [(d, n, name_of(d), kind_of(name_of(d))) for d, n in extra.most_common()],
               "missing": [(d, n, name_of(d), kind_of(name_of(d))) for d, n in missing.most_common()]}
        row["extra_by_kind"] = dict(collections.Counter({k: 0 for k in []}) + collections.Counter(
            {k: sum(n for _, n, _, kk in row["extra"] if kk == k) for k in {x[3] for x in row["extra"]}}))
        row["missing_by_kind"] = dict(collections.Counter(
            {k: sum(n for _, n, _, kk in row["missing"] if kk == k) for k in {x[3] for x in row["missing"]}}))
        out.append(row)
        by_cause[r["why"].split("(")[0].strip()].append(row)
        extra_all.update({(d, nm): n for d, n, nm, _ in row["extra"]})
        missing_all.update({(d, nm): n for d, n, nm, _ in row["missing"]})
        print(f"{s:9} {row['model']:5}/{row['set_pieces']:5} {r['why'][:40]}", flush=True)
    (ROOT / "research" / "data" / "omr_mismatch.json").write_text(json.dumps(out, indent=1))

    kind_extra, kind_missing = collections.Counter(), collections.Counter()
    for row in out:
        kind_extra.update(row["extra_by_kind"])
        kind_missing.update(row["missing_by_kind"])
    lines = ["# The 151 OMR models that still do not match their sets", "",
             "Each MISMATCH set of `omr_audit.json`, read the way the audit reads it (minifigures or not, assemblies "
             "whole or split, whichever agrees best), with every piece the model has that the set does not (*extra*) "
             "and every piece of the set the model lacks (*missing*). Per set: `omr_mismatch.json`. Script: "
             "`research/scrape/omr_mismatch.py`.", "",
             "## By kind of piece (all 151 sets)", "", "| Kind | Extra in the models | Missing from the models |",
             "|---|---:|---:|"]
    for k in sorted(set(kind_extra) | set(kind_missing), key=lambda k: -(kind_extra[k] + kind_missing[k])):
        lines.append(f"| {k} | {kind_extra[k]} | {kind_missing[k]} |")
    lines += ["", "## Pieces most often extra in the models", "", "| Design | Name | Pieces |", "|---|---|---:|"]
    lines += [f"| {d} | {nm} | {n} |" for (d, nm), n in extra_all.most_common(25)]
    lines += ["", "## Pieces most often missing from the models", "", "| Design | Name | Pieces |", "|---|---|---:|"]
    lines += [f"| {d} | {nm} | {n} |" for (d, nm), n in missing_all.most_common(25)]
    lines += ["", "## By cause", ""]
    for cause, rs in sorted(by_cause.items(), key=lambda t: -len(t[1])):
        lines += [f"### {cause} ({len(rs)} sets)", "", "| Set | Name | Model / set | Main extra | Main missing |",
                  "|---|---|---:|---|---|"]
        for row in sorted(rs, key=lambda x: x["set"]):
            ex = "; ".join(f"{n}× {nm}" for _, n, nm, _ in row["extra"][:3]) or "–"
            mi = "; ".join(f"{n}× {nm}" for _, n, nm, _ in row["missing"][:3]) or "–"
            lines.append(f"| {row['set']} | {row['name'][:30]} | {row['model']} / {row['set_pieces']} | {ex} | {mi} |")
        lines.append("")
    (ROOT / "research" / "data" / "omr_mismatch.md").write_text("\n".join(lines) + "\n")
    print("wrote research/data/omr_mismatch.md", flush=True)


if __name__ == "__main__":
    main()
