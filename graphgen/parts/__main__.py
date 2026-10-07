"""Parts pipeline from the command line.

  .venv-research/bin/python -m graphgen.parts lego-cards                 card every piece of the 100 test sets (one-off)
  .venv-research/bin/python -m graphgen.parts electronics-prefill        card every part the tutorials name (one-off)
  .venv-research/bin/python -m graphgen.parts find "HC-SR04" ultrasonic-hc-sr04   one part through the site registry
"""
import argparse
import json
import pathlib
import time

from .. import v3
from . import cards as pc
from . import lego as pl


def prefill_electronics():
    """Fill graphgen/data/cards_electronics.json before any run: read every tutorial's parts list, find each part in
    the store by free-text search, and look up only the unknown ones on the registry's shops (top result per shop,
    at most 3 checks each). Each card is stored once and reused by every later tutorial (RESEARCH.md R22, v5)."""
    import concurrent.futures
    from .. import catalogue as cat
    from ..run import arduino_manual
    from . import ingest, tutorial
    root = pathlib.Path(__file__).resolve().parents[2]
    cases = (json.loads((root / "research" / "data" / "arduino_dataset.json").read_text())
             + json.loads((root / "research" / "data" / "pi_dataset.json").read_text()))

    def manual(c):
        if c.get("manual_file"):
            return (root / c["manual_file"]).read_text()
        for attempt in range(3):  # GitHub sometimes times out
            try:
                return arduino_manual(c["path"], False)[0]
            except OSError:
                time.sleep(5)
        return ""

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        manuals = list(pool.map(manual, cases))
    store = pc.CardStore(root / "graphgen" / "data" / "cards_electronics.json", seed=cat.arduino_seed())
    wanted, matched, skipped = {}, 0, 0
    for c, md in zip(cases, manuals):
        for item in tutorial.hardware_list(md):
            card, name = tutorial.match(item, store)
            if card == "skip":
                skipped += 1
            elif card:
                matched += 1
            elif name:
                wanted.setdefault(name.lower(), (name, c["id"]))
    print(f"{len(cases)} tutorials read in {time.monotonic() - t0:.0f} s: {matched} items in the store, {skipped} not "
          f"parts, {len(wanted)} distinct parts to look up")
    found, cost, rows = 0, 0.0, []
    for i, (name, case) in enumerate(wanted.values(), 1):
        card, st, trail = ingest.ingest_part(name, "electronics", store, label=name, max_llm_calls=3)
        found += bool(card)
        cost += st.get("cost_usd", 0)
        rows.append({"part": name, "first_tutorial": case, "card": card and card["type"], "seconds": st["seconds"],
                     "trail": trail})
        print(f"  [{i}/{len(wanted)}] {name[:45]:45s} -> {card['type'] if card else 'not found'} ({st['seconds']} s)", flush=True)
    stats = {"tutorials": len(cases), "items_in_store": matched, "items_not_parts": skipped, "looked_up": len(wanted),
             "found": found, "cost_usd": round(cost, 4), "seconds": round(time.monotonic() - t0, 1), "parts": rows}
    (root / "graphgen" / "data" / "cards_electronics_prefill.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: v for k, v in stats.items() if k != "parts"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lc = sub.add_parser("lego-cards")
    lc.add_argument("--workers", type=int, default=4)
    lc.add_argument("--batch", type=int, default=40)
    sub.add_parser("electronics-prefill")
    f = sub.add_parser("find")
    f.add_argument("query")
    f.add_argument("type")
    f.add_argument("--store", type=pathlib.Path, default=pathlib.Path("/tmp/cards_try.json"))
    a = ap.parse_args()

    if a.cmd == "lego-cards":
        root = pathlib.Path(__file__).resolve().parents[2]
        sets = json.loads((root / "research" / "data" / "lego_dataset.json").read_text())
        t0 = time.monotonic()
        designs = {}
        for s in sets:
            designs.update(pl.designs(pl.RebrickableDump.set_parts(s["set"])))
        print(f"{len(designs)} distinct pieces in {len(sets)} sets ({time.monotonic() - t0:.1f} s to read the dump)")
        store = pc.CardStore(v3.LEGO_STORE)
        stats = pc.lego_cards(store, designs, batch_size=a.batch, workers=a.workers)
        stats["read_dump_seconds"] = round(time.monotonic() - t0 - stats["seconds"], 1)
        (v3.LEGO_STORE.parent / "cards_lego_stats.json").write_text(json.dumps(stats, indent=1))
        print(json.dumps(stats, indent=1))
    elif a.cmd == "electronics-prefill":
        prefill_electronics()
    else:
        store = pc.CardStore(a.store)
        card, stats, trail = pc.ingest(store, a.type, a.query, a.query)
        for step in trail:
            print("  ", *step)
        print(json.dumps(stats), "\n", json.dumps(card, indent=1)[:2000] if card else "not found")


if __name__ == "__main__":
    main()
