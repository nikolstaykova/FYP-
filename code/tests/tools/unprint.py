"""One card per LEGO design: printed pieces merged into their plain piece (3 Nov 2026).

A printed piece (a minifig head with a face, a printed tile) had a card of its own (lego-3626cpr0914), so the same
head was in the catalogue once per face. Now the print is a property of the copy, like its colour
(lego_ids.unprinted, applied by lesson_store.register to every lesson saved). This tool brings what was saved before
in line:
  1. cards: every printed card merged into its plain piece (cards.merge: ports kept, old id -> new id in
     redirects.json, so older graphs still resolve); a plain piece with no card yet takes Rebrickable's name;
  2. lessons: every saved lesson's graphs rewritten (type plain, props.print / row print) and its assembled view
     rebuilt; then parts.json rebuilt from the cards.
No model calls. Run: ./pinpoint tool unprint [--dry-run]
"""
import collections
import csv
import gzip
import json
import re
import sys

from graph import lesson_store
from graph.parts import cards as cards_mod, part_catalogue
from graph.parts.lego.lego_ids import DUMP, unprinted, unprint_graphs

LEGO_CARDS = cards_mod.LEGO_STORE


def plain_name(plain, printed_names):
    """Rebrickable's name for the plain piece ("Minifig Head [Hollow Stud]"), else a printed name without its print."""
    names = {r["part_num"]: r["name"] for r in csv.DictReader(gzip.open(DUMP / "parts.csv.gz", "rt"))}
    n = names.get(plain[len("lego-"):])
    if n:
        return re.sub(r"\s*\[Plain\]", "", n).strip()
    n = printed_names[0] if printed_names else plain
    return re.sub(r"\s+with\b.*\b(print|pattern)\b.*$|,[^,]*\b(print|pattern)\b.*$", "", n, flags=re.I).strip()


def merge_cards(dry):
    cards = json.loads(LEGO_CARDS.read_text())
    groups = collections.defaultdict(list)
    for t in cards:
        plain, pr = unprinted(t)
        if pr:
            groups[plain].append(t)
    for plain, printed in sorted(groups.items()):
        name = None if plain in cards else plain_name(plain, [cards[t].get("display_name") for t in printed])
        print(f"{plain}{'' if plain in cards else ' (new: ' + name + ')'} <- {', '.join(sorted(printed))}")
        if not dry:
            cards_mod.merge(plain, sorted(printed), cards_path=LEGO_CARDS, name=name, log=lambda m: None)
    return sum(len(v) for v in groups.values()), len(groups)


def migrate_lessons(dry):
    changed = {}
    for d in sorted(lesson_store.STORE.iterdir()):
        if not (d / "lesson.json").exists():
            continue
        graphs = {k: json.loads((d / f"{k}.json").read_text()) for k in lesson_store.KINDS if (d / f"{k}.json").exists()}
        n = unprint_graphs(graphs)
        if not n:
            continue
        changed[d.name] = n
        if not dry:
            for k, g in graphs.items():
                (d / f"{k}.json").write_text(json.dumps(g, indent=1))
            if (d / "assembled.json").exists():
                view = lesson_store.assemble(d.name)
                (d / "assembled.json").write_text(json.dumps(view, indent=1))
                (d / "assembled.md").write_text(lesson_store.to_md(view))
    return changed


def main():
    dry = "--dry-run" in sys.argv
    n, k = merge_cards(dry)
    print(f"cards: {n} printed cards {'would merge' if dry else 'merged'} into {k} plain pieces")
    changed = migrate_lessons(dry)
    print(f"lessons: {sum(changed.values())} printed pieces in {len(changed)} lessons "
          f"{'would be' if dry else 'were'} rewritten: {changed}")
    if not dry:
        print("parts.json:", part_catalogue.build())


if __name__ == "__main__":
    main()
