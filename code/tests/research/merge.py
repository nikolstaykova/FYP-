"""One part under two ids, made one.

What it is   merge(keep, drop): the kept id gets the fullest port list, the richer electrical facts and the matching
             metadata; each dropped id becomes a redirect in redirects.json, so earlier lessons still find their
             part. resolve(type_id) follows the redirects.
Used for     cleaning the catalogue when the store's validator (P7) finds two cards for one part (one shop page, or one model
             number).
Where        resolve: parts/cards.py (CardStore.get), lesson_store.py (definition), parts/naming.py; merge on its
             own: python -m graph.parts.merge arduino-mkr1000 arduino-mkr1000-headers.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
REDIRECTS_PATH = HERE / "redirects.json"
ROOT = HERE.parents[2]
CARDS = ROOT / "code" / "graph" / "parts" / "arduino" / "cards_electronics.json"


def redirects():
    if not REDIRECTS_PATH.exists():
        return {}
    return {k: v for k, v in json.loads(REDIRECTS_PATH.read_text()).items() if not k.startswith("_")}


REDIRECTS = redirects()


def resolve(type_id, table=None):
    table = REDIRECTS if table is None else table
    seen = set()
    while type_id in table and type_id not in seen:
        seen.add(type_id)
        type_id = table[type_id]
    return type_id


def _norm(port_id):
    return re.sub(r"[^A-Z0-9]", "", port_id.upper())  # A.1 and A1, BAT_1 and BAT1


def merge(keep, drop, cards_path=CARDS, name=None, log=print):
    """Merge the cards `drop` into `keep` (which may be one of them, or an id none of them has yet). Returns the
    kept card. Writes the card store, parts.json's metadata and redirects.json; part_catalogue.build() is the caller's."""
    from graph.parts import part_catalogue
    cards = json.loads(cards_path.read_text())
    group = [t for t in [keep, *drop] if t in cards]
    richest = max(group, key=lambda t: (len(cards[t]["ports"]), t == keep))
    card = json.loads(json.dumps(cards[richest]))
    have = {_norm(p["id"]) for p in card["ports"]} | {_norm(a) for p in card["ports"] for a in p.get("aliases", [])}
    for t in group:  # a port only a dropped card had (a graph may name it): kept, as an alias where it is one
        for p in cards[t]["ports"]:
            if _norm(p["id"]) in have:
                continue
            twin = next((q for q in card["ports"] if _norm(q["id"]).rstrip("T") == _norm(p["id"]).rstrip("T")), None)
            if twin:  # BAT and BATT
                twin.setdefault("aliases", []).append(p["id"])
                log(f"  {t}:{p['id']} -> alias of {twin['id']}")
            else:
                card["ports"].append(p)
                log(f"  {t}:{p['id']} added")
            have.add(_norm(p["id"]))
    elec = {}
    for t in sorted(group, key=lambda t: len(json.dumps(cards[t].get("electrical") or {}))):
        elec.update({k: v for k, v in (cards[t].get("electrical") or {}).items() if v not in (None, [])})
    card["electrical"] = elec or card.get("electrical")
    card["aliases"] = sorted({a for t in group for a in cards[t].get("aliases", [])})
    card["part_type_id"] = keep
    if name:
        card["display_name"] = name
    parts = part_catalogue.load()
    meta = (parts.get(richest) or {}).get("metadata") or (parts.get(keep) or {}).get("metadata")
    for t in group:
        cards.pop(t, None)
        if t != keep:
            parts.pop(t, None)
    cards[keep] = card
    if meta:
        parts[keep] = {**card, "metadata": {**meta, "status": "drafted"}}  # rechecked against the merged card
    cards_path.write_text(json.dumps(dict(sorted(cards.items())), indent=1))
    part_catalogue.save(parts)
    table = json.loads(REDIRECTS_PATH.read_text()) if REDIRECTS_PATH.exists() else {
        "_doc": "Ids a card no longer has -> the id it is now (graph/parts/merge.py). Graphs from earlier runs "
                "keep the old id; CardStore.get, lesson_store.definition and the naming rules follow these."}
    for t in drop:
        if t != keep:
            table[t] = keep
    for k, v in list(table.items()):  # no chains: an id merged twice points at the last one
        if not k.startswith("_"):
            table[k] = resolve(v, {a: b for a, b in table.items() if not a.startswith("_")})
    REDIRECTS_PATH.write_text(json.dumps(table, indent=1))
    REDIRECTS.clear()
    REDIRECTS.update(redirects())
    log(f"{keep}: {len(card['ports'])} ports from {richest}; redirects {[t for t in drop if t != keep]}")
    return card


if __name__ == "__main__":
    merge(sys.argv[1], sys.argv[2:])
