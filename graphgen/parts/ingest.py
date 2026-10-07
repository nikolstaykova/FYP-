"""The one ingestion pipeline for parts in every domain (RESEARCH.md R22).

  ingest_part(target, domain, store)      one part: a URL, a part number, or a name to search for
  ingest_many(targets, domain, store)     many parts at once (a LEGO set's pieces): code first, the rest batched

Order, the same for every domain:
  1. local Layer 0 check: a card already in the store is returned, nothing is fetched
  2. route: a URL goes to the adapter of its site; a name is searched on the registry's sources in order;
     a LEGO part number goes to Rebrickable
  3. fetch + existence check (no tokens spent on pages that are not real product pages)
  4. card by code when the adapter can (plain LEGO bricks), else the universal prompt engine (Claude +
     schema + the site's instructions from the registry)
  5. schema gate: a valid card is stored, an invalid one goes to quarantine
"""
import json
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from . import schema, sources
from .schema import CardPort, Electrical, Geometry, IntrinsicBehaviour


class EngineCard(BaseModel):
    """What the prompt engine returns per item: a Layer 0 card without its source (the pipeline adds that)."""
    target: str = Field(description="The item's target, copied from the request")
    matches: bool = Field(description="True only if the content really describes the part asked for")
    reason: str
    part_type_id: str
    display_name: str
    category: str
    ports: List[CardPort] = Field(description="Every port except LEGO studs/anti-studs (those come from the grids)")
    stud_grid: Optional[List[int]] = Field(description="LEGO: [rows, cols] of studs on top, else null")
    anti_stud_grid: Optional[List[int]] = Field(description="LEGO: [rows, cols] of receptacles underneath, else null")
    intrinsic_behaviour: IntrinsicBehaviour
    physical_geometry: Optional[Geometry]
    electrical: Optional[Electrical] = Field(description="Supply range, logic level, currents, power pins: from the "
                                                         "content's specifications; null for what it does not state")


class EngineOut(BaseModel):
    cards: List[EngineCard]


SYSTEM = """You are a part-catalogue ingestion engine. For each item you get raw content about one part (a shop
page, an API record, a parts database row) and you return ONE reusable Layer 0 part card: the part TYPE, never
how a particular tutorial or set uses it. Ports are where other parts connect, with standard kinds; behaviour says
what is joined inside the part, what is interchangeable, what is polarised. If a value is not in the content and
is not a standard fact about this exact part, leave it null. If the content is not the part asked for, set
matches=false.

"""

NAMING = """NAMING (part_type_id, lowercase, words joined by '-'):
- LEGO: lego-<part number>
- boards: arduino-<model> (arduino-uno, arduino-nano-33-ble), rpi-<model> (rpi-4b, rpi-pico-w)
- modules and sensors: <what>-<chip or model> (temp-dht11, imu-mpu6050, display-oled-128x64-i2c)
- basic components: <category> (resistor, led, capacitor); the value or colour is an instance property
When a wanted id is given, use exactly that id."""
SYSTEM += NAMING


def prompt_engine(items, domain, model="sonnet", effort="low"):
    """items: [{target, wanted_id, label, content, instructions}] -> ([(item, EngineCard dict)], stats)."""
    from ..extract import claude_json
    blocks = []
    for i, it in enumerate(items, 1):
        blocks.append(f"ITEM {i}\ntarget: {it['target']}\nwanted id: {it.get('wanted_id') or '(choose by the naming rules)'}\n"
                      f"part asked for: {it.get('label') or it['target']}\nsite rules: {it.get('instructions') or '-'}\n"
                      f"content: {json.dumps(it['content'])[:7000]}")
    out, stats = claude_json(SYSTEM + f"\n\nDomain: {domain}.", [{"type": "text", "text": "\n\n".join(blocks)}], EngineOut,
                             model=model, effort=effort)
    by_target = {c["target"]: c for c in out["cards"]}
    return [(it, by_target.get(it["target"])) for it in items], stats


def _grid(prefix, kind, grid):
    if not grid or len(grid) != 2:
        return []
    return [{"id": f"{prefix}.{i}.{j}", "kind": kind} for i in range(1, grid[0] + 1) for j in range(1, grid[1] + 1)]


def to_layer0(engine_card, domain, source):
    c = dict(engine_card)
    ports = _grid("stud", "stud", c.pop("stud_grid", None)) + _grid("anti", "anti-stud", c.pop("anti_stud_grid", None))
    for k in ("target", "matches", "reason"):
        c.pop(k, None)
    c["ports"] = ports + [p for p in c["ports"] if p["id"] not in {q["id"] for q in ports}]
    return {**c, "domain": domain, "source": source}


def _store(store, card, quarantine_reason=None):
    """Schema gate, then store or quarantine. Returns the stored card or None."""
    ok, err = schema.gate(card)
    if ok and not quarantine_reason:
        store.put_layer0([ok])
        return ok
    store.quarantine(card, err or quarantine_reason)
    return None


def _stats():
    return {"seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}


def _add(total, st):
    for k in ("input_tokens", "output_tokens", "cost_usd"):
        total[k] = round(total[k] + (st.get(k) or 0), 4)
    total["calls"] += 1


def ingest_part(target, domain, store, wanted_id=None, label=None, max_llm_calls=None):
    """One part. Returns (card in engine form or None, stats, trail). `max_llm_calls` caps the prompt-engine
    checks across all sites (a part no shop sells should not cost a call per site)."""
    t0, total, trail = time.monotonic(), _stats(), []
    with store.lock:  # two manuals asking for the same new part: the second reuses the card
        if wanted_id and store.get(wanted_id):  # 1. local Layer 0 check
            return store.get(wanted_id), total, [("cache", wanted_id)]
        if target.startswith("http"):  # 2. route
            a = sources.route(target)
            plan = [(a, [(target, target)])] if a else []
        else:
            plan = [(a, None) for a in sources.adapters("lego" if domain == "lego" else "electronics")]
        for adapter, hits in plan:
            if not adapter.available():
                trail.append((adapter.name, "skipped: needs " + ", ".join(adapter.row.get("needs", []))))
                continue
            if hits is None:
                try:
                    hits = [(target, target)] if domain == "lego" else adapter.search(target)[:1]  # the top result only
                except Exception as e:  # a site being down must not stop the pipeline
                    trail.append((adapter.name, f"search failed: {type(e).__name__}"))
                    continue
            if not hits:
                trail.append((adapter.name, "no search result"))
            for title, url in hits:
                content = adapter.fetch_data(url)  # 3. fetch + existence check
                if not content or (domain != "lego" and not sources.looks_like_product(content)):
                    trail.append((adapter.name, f"no usable page: {url}"))
                    continue
                card = adapter.deterministic(content)  # 4. code first
                if card is None and max_llm_calls is not None and total["calls"] >= max_llm_calls:
                    trail.append(("budget", f"stopped after {total['calls']} checks"))
                    return None, {**total, "seconds": round(time.monotonic() - t0, 1)}, trail
                if card is None:
                    [(it, out)], st = prompt_engine([{"target": url, "wanted_id": wanted_id, "label": label or target,
                                                      "content": content, "instructions": adapter.get_prompt_instructions()}],
                                                    domain)
                    _add(total, st)
                    if not out or not out["matches"]:
                        trail.append((adapter.name, f"did not match: {url} ({(out or {}).get('reason', '')[:80]})"))
                        continue
                    card = to_layer0(out, domain, {"platform": adapter.name, "url": content["url"],
                                                   "external_id": content.get("part_num"), "made_by": "claude"})
                    if wanted_id:
                        card["part_type_id"] = wanted_id
                stored = _store(store, card)  # 5. gate
                trail.append((adapter.name, f"card from {url}" if stored else f"quarantined: {url}"))
                if stored:
                    return schema.to_engine(stored), {**total, "seconds": round(time.monotonic() - t0, 1)}, trail
    return None, {**total, "seconds": round(time.monotonic() - t0, 1)}, trail


def ingest_many(targets, domain, store, batch_size=40, workers=4, log=None):
    """Many parts by number (LEGO): cache, then code, then the prompt engine in parallel batches.
    targets: [part number]. Returns stats."""
    import concurrent.futures
    t0 = time.monotonic()
    total = {**_stats(), "cached": 0, "made_by_code": 0, "made_by_claude": 0, "quarantined": 0, "not_found": 0}
    adapter = sources.adapters(domain)[0]
    todo = []
    for num in targets:
        if store.get(f"lego-{num}"):
            total["cached"] += 1
            continue
        content = adapter.fetch_data(num)
        if not content:
            total["not_found"] += 1
            continue
        card = adapter.deterministic(content)
        if card:
            total["made_by_code"] += 1 if _store(store, card) else 0
        else:
            todo.append({"target": num, "wanted_id": f"lego-{num}", "label": content["name"], "content": content,
                         "instructions": adapter.get_prompt_instructions(), "url": content["url"]})
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max(1, workers)) as pool:
        for n, (pairs, st) in enumerate(pool.map(lambda b: prompt_engine(b, domain), batches), 1):
            _add(total, st)
            for it, out in pairs:
                if not out or not out["matches"]:
                    store.quarantine({"target": it["target"]}, "prompt engine gave no matching card")
                    total["quarantined"] += 1
                    continue
                card = to_layer0({**out, "part_type_id": it["wanted_id"]}, domain,
                                 {"platform": adapter.name, "url": it["url"], "external_id": it["target"], "made_by": "claude"})
                if _store(store, card):
                    total["made_by_claude"] += 1
                else:
                    total["quarantined"] += 1
            if log:
                log(f"  batch {n}/{len(batches)}: {st['seconds']} s, ${st['cost_usd']}")
    total["seconds"] = round(time.monotonic() - t0, 1)
    return total
