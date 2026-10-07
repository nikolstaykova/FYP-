"""v3: parts first, then the graph.

Phase "parts" (timed and costed like every other phase), before Claude builds anything:
  LEGO         set inventory from Rebrickable (code) -> cards from the card store (prebuilt with
               `python -m graphgen.parts lego-cards`; any missing piece is carded on demand).
               Fallback when the set is hidden or unknown: the booklet's parts page (code), else Claude
               reads the parts boxes.
  Electronics  Claude lists the tutorial's parts and matches them to the catalogue by the naming rules;
               a part the catalogue lacks goes through the site registry (Adafruit, SparkFun, Pololu,
               Seeed, Mouser, DigiKey) and becomes a card.
The build prompt then carries only the cards this manual needs, plus (LEGO) the exact parts list.
Repair runs only for real errors (REAL_RULES), not for naming or port-form issues.
"""
import pathlib
import time

from . import catalogue as cat
from .parts import cards as pc
from .parts import lego as pl

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEGO_STORE = ROOT / "graphgen" / "data" / "cards_lego.json"
from .domains import REAL_RULES  # noqa: E402  (shared with the v4 recipes)
ALWAYS = ("breadboard", "jumper-wire", "jumper-wire-mf")  # wiring parts every circuit may use

_stores = {}


def store(domain, run_dir=None, path=None):
    """One card store per domain per process. Electronics starts from the verified seed; ingested cards are
    written to the run folder unless `path` points at an earlier store (reuse = warm catalogue)."""
    if domain not in _stores:
        if domain == "lego":
            _stores[domain] = pc.CardStore(path or LEGO_STORE)
        else:
            _stores[domain] = pc.CardStore(path or (run_dir / "cards_electronics.json"), seed=cat.arduino_seed())
    return _stores[domain]


def _phase(seconds, stats=None, **extra):
    stats = stats or {}
    return {"phase": "parts", "seconds": round(seconds, 1), "input_tokens": stats.get("input_tokens", 0),
            "output_tokens": stats.get("output_tokens", 0), "cost_usd": round(stats.get("cost_usd", 0.0), 4),
            "check_seconds": 0.0, **extra}


def prepare_lego(case, pdf, cfg, run_dir):
    t0 = time.monotonic()
    s = store("lego", run_dir, cfg.cards)
    parts, stats, method = None, {}, "rebrickable dump"
    if case["id"] not in (cfg.hide_parts or ()):
        parts = pl.RebrickableDump.set_parts(case["id"])
    if parts is None:
        parts, stats, method = pl.booklet_parts(pdf)
    missing = {p: v for p, v in pl.designs(parts).items() if not s.get(f"lego-{p}")}
    made = pc.lego_cards(s, missing, log=None) if missing else {}
    if made:
        stats = {k: stats.get(k, 0) + made.get(k, 0) for k in ("input_tokens", "output_tokens", "cost_usd")}
    types = sorted({f"lego-{p['part_num']}" for p in parts})
    cards = {t: s.get(t) for t in types if s.get(t)}
    return {"parts": parts, "cards": cards, "catalogue_text": _cards_text(cards),
            "manual_extra": "\n\n" + pl.prompt_text(parts),
            "phase": _phase(time.monotonic() - t0, stats, method=method, cards_made=len(missing),
                            pieces=sum(p["quantity"] for p in parts))}


def prepare_electronics(case, manual, cfg, run_dir):
    t0 = time.monotonic()
    s = store("electronics", run_dir, cfg.cards)
    lines, stats = pc.match_parts(manual, s)
    total = dict(stats)
    trails, used = [], set(ALWAYS)
    for line in lines:
        t = line["catalogue_type"]
        if t and s.get(t):
            used.add(t)
            continue
        wanted = line["new_type"] or line["catalogue_type"]
        if not wanted:
            continue
        card, st, trail = pc.ingest(s, wanted, line["label"], line["search_query"] or line["label"])
        trails.append({"part": line["label"], "type": wanted, "found": bool(card), "trail": trail, "seconds": st.get("seconds")})
        for k in ("input_tokens", "output_tokens", "cost_usd"):
            total[k] = total.get(k, 0) + st.get(k, 0)
        if card:
            used.add(wanted)
    cards = {t: s.get(t) for t in sorted(used) if s.get(t)}
    listing = "\n".join(f"- {l['quantity']}x {l['label']} -> {l['catalogue_type'] or l['new_type']}" for l in lines)
    return {"parts": lines, "cards": cards, "catalogue_text": _cards_text(cards),
            "manual_extra": "\n\nPARTS (matched to the catalogue before this build):\n" + listing,
            "phase": _phase(time.monotonic() - t0, total, matched=sum(1 for l in lines if l["catalogue_type"]),
                            listed=len(lines), ingested=sum(1 for x in trails if x["found"]), ingest=trails)}


def _cards_text(cards):
    return cat.Catalogue(cards).prompt_text()


def parts_check(flat, parts):
    """L4: the graph's pieces differ from the parts list it was given (only when the difference is more than
    a slip: over 2 pieces and over 5% of the set)."""
    import collections
    want = collections.Counter()
    for p in parts:
        want[f"lego-{p['part_num']}"] += p["quantity"]
    got = collections.Counter(n["type"] for n in flat["nodes"])
    missing, extra = want - got, got - want
    off = sum(missing.values()) + sum(extra.values())
    if off > max(2, 0.05 * sum(want.values())):
        return [("L4", "pieces differ from the parts list: missing " + ", ".join(f"{t} ×{q}" for t, q in list(missing.items())[:15])
                 + "; not in the list " + ", ".join(f"{t} ×{q}" for t, q in list(extra.items())[:15]))]
    return []
