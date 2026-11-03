"""Making the card of a part the catalogue does not have.

What it is   the one ingestion pipeline for every domain: the card store first; else the part's site (a URL goes to
             its site's adapter, a name is searched on the registry's sites in order, a LEGO number goes to
             Rebrickable); the page checked to be a real product page; a card by code where the site allows (a plain
             LEGO brick), else drafted by Claude from the page; every card through the gate (parts/cards.py) before
             it is stored. ingest_many does a LEGO set's pieces at once (code first, the rest batched).
             Also the sites themselves: the base every site adapter is built on (SiteAdapter: search, fetch_data,
             deterministic, the site's prompt rules), the shared web helpers (a cached fetch, a page cleaned to its
             text and product data, results ranked by the words they share with the query), the registry's sites
             in order (adapters) and the router (route). The adapters: parts/arduino/shops.py, parts/lego/sites.py.
Used for     a part a lesson needs that has no card yet.
Where        parts/cards.py (ingest, lego_cards), parts/mcp_server.py (the lookup_part tool),
             arduino/circuit_graph.py (upkeep), arduino/circuit_lesson.py and part_review.py,
             parts/lego/lego_ids.py.

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
import hashlib
import html
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request
from typing import List, Optional

from pydantic import BaseModel, Field

from graph.parts import cards
from graph.parts.cards import CardPort, Electrical, Geometry, IntrinsicBehaviour


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
- modules and sensors: the maker's model or chip first, no category word in front (dht11, mpu6050, hc-sr04)
- one id per part: no -headers, -pins or -wifi copies of a board (arduino-mkr1000, not arduino-mkr1000-headers)
- basic components: <category> (resistor, led, capacitor); the value or colour is an instance property
When a wanted id is given, use exactly that id."""
SYSTEM += NAMING


def prompt_engine(items, domain, model="sonnet", effort="low"):
    """items: [{target, wanted_id, label, content, instructions}] -> ([(item, EngineCard dict)], stats)."""
    from graph.extract import claude_json
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


def same_source(have, new):
    """The new card is the stored card read again from the same page (an update), not another product."""
    a, b = have.get("source") or {}, new.get("source") or {}
    if a.get("made_by") == "verified":
        return False  # a verified card is only changed by hand
    return bool(a.get("url")) and a.get("url") == b.get("url")


def _store(store, card, quarantine_reason=None):
    """Schema gate, then the naming rules (graph/parts/naming.py), then store or quarantine: every new card passes here,
    from a shop or drafted by Claude, so none enters the catalogue with an id that breaks the rules or is a part we
    have already. Electronics: N1-N6; LEGO (Rebrickable's own number): the id rules only. Returns the stored card or
    None."""
    ok, err = cards.gate(card)
    if ok and not quarantine_reason:
        have = store.cards.get(ok.get("part_type_id") or "") if hasattr(store, "cards") else None
        if have and not same_source(have, ok):
            # a card we have is never replaced by one from another page: a search for "panel-mount push button"
            # once came back as `pushbutton` and replaced the verified card with a SparkFun one (3 Nov 2026)
            return have
    if ok and not quarantine_reason:
        from graph.parts import naming
        t = ok.get("part_type_id") or ""
        if not (store.get(t) if hasattr(store, "get") else None):  # a card we have is updated, not named again
            found = naming._rules_only(t) if t.startswith("lego-") else \
                naming.check([{"type": t, "name": ok.get("display_name") or "", **ok}], store)
            if found:
                quarantine_reason = "naming: " + "; ".join(f"{r} {m}" for r, m in found)
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
            a = route(target)
            plan = [(a, [(target, target)])] if a else []
        else:
            plan = [(a, None) for a in adapters("lego" if domain == "lego" else "electronics")]
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
                if not content or (domain != "lego" and not looks_like_product(content)):
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
                    return cards.to_engine(stored), {**total, "seconds": round(time.monotonic() - t0, 1)}, trail
    return None, {**total, "seconds": round(time.monotonic() - t0, 1)}, trail


def ldraw_current(num):
    """The LDraw part a number is now ('6014' -> '6014a', '50746' -> '54200': moved and alias files), or None."""
    from graph import lego_model
    ref = lego_model.resolve(f"{num}.dat")
    cur = ref[:-4] if ref and ref.endswith(".dat") else None
    return cur if cur and cur != num and lego_model.library_title(cur) else None


def ldraw_card(num):
    """A LEGO card by code from the LDraw library alone, for a part Rebrickable has no page for under this number (a
    3D model names parts by their LDraw file): its title, and the studs and anti-studs its shape has (ldraw_studs:
    top studs as the joins name them, an anti-stud under every cell of its stud grid). None if LDraw has no shape."""
    from graph import lego_model
    cur = ldraw_current(num) or num
    title = re.sub(r"^[~=_|]+", "", lego_model.library_title(cur) or "").strip()
    if not title or title.lower().startswith("moved to"):
        return None
    try:
        studs, g = lego_model.stud_ports(cur + ".dat"), lego_model.grid(cur + ".dat")
    except Exception:  # a shape the stud code cannot read: the name only, no ports
        studs, g = [], None
    anti = []
    if g:
        (_, nx), (_, nz), occ = g
        anti = sorted({f"anti.{iz + 1}.{ix + 1}" if nz <= nx else f"anti.{ix + 1}.{iz + 1}" for ix, iz in occ})
    port = lambda i, k: {"id": i, "kind": k, "gender": None, "voltage_rating": None, "aliases": []}  # noqa: E731
    return {"part_type_id": f"lego-{num}", "domain": "lego", "display_name": re.sub(r"\s+", " ", title),
            "aliases": [cur] if cur != num else [], "category": re.sub(r"[^a-z]", "", title.split()[0].lower()) or "part",
            "ports": [port(s, "stud") for s in studs] + [port(a, "anti-stud") for a in anti],
            "source": {"platform": "ldraw", "url": f"https://library.ldraw.org/parts/list?s={cur}", "external_id": cur,
                       "made_by": "code"},
            "note": "Made by code from the LDraw library (Rebrickable has no part under this number): ports from its shape."}


def ingest_many(targets, domain, store, batch_size=40, workers=4, log=None):
    """Many parts by number (LEGO): cache, then code, then the prompt engine in parallel batches.
    targets: [part number]. Returns stats."""
    import concurrent.futures
    t0 = time.monotonic()
    total = {**_stats(), "cached": 0, "made_by_code": 0, "made_by_claude": 0, "quarantined": 0, "not_found": 0}
    adapter = adapters(domain)[0]
    todo = []
    for num in targets:
        if store.get(f"lego-{num}"):
            total["cached"] += 1
            continue
        content = adapter.fetch_data(num)
        if not content and domain == "lego" and ldraw_current(num):  # LDraw moved or aliased it: its current number
            content = adapter.fetch_data(ldraw_current(num))
            if content:
                content = {**content, "part_num": num}
        if not content and domain == "lego":  # a 3D model's LDraw number Rebrickable does not have: the LDraw part
            card = ldraw_card(num)
            if card and _store(store, card):
                total["made_by_code"] += 1
                continue
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


# ---- the sites: the adapters' base, the shared web helpers, the registry and the router --------------
ROOT = pathlib.Path(__file__).resolve().parents[3]


CACHE = ROOT / "data" / "sources" / "parts"


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


REGISTRY = json.loads((pathlib.Path(__file__).parent / "registry.json").read_text())


def fetch(url, data=None, headers=None, timeout=30):
    """GET (or POST `data`), cached on disk by URL + body. Returns text or None on an HTTP error."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha1((url + (data or "")).encode()).hexdigest() + ".html")
    if path.exists():
        return path.read_text(errors="replace")
    req = urllib.request.Request(url, data=data.encode() if data else None,
                                 headers={"User-Agent": UA, "Accept-Language": "en", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    path.write_text(text)
    return text


def clean(raw, limit=6000):
    """HTML -> (JSON-LD Product dict or None, plain text without scripts, styles, header, nav, footer)."""
    product = None
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw, re.S | re.I):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "Product":
                product = {k: item.get(k) for k in ("name", "description", "sku", "mpn", "brand") if item.get(k)}
    body = re.sub(r"<(script|style|noscript|svg|header|nav|footer)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return product, text[:limit]


def words(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower())) - {"the", "a", "an", "with", "for", "and", "of", "x"}


def rank(query, candidates):
    """Candidates sorted by word overlap with the query; ones sharing no word are dropped."""
    q = words(query)
    unique = {u: t.strip() for t, u in candidates if u}  # one entry per page
    scored = [(len(q & words(t)) / (len(q) or 1), t, u) for u, t in unique.items()]
    return [(t, u) for s, t, u in sorted(scored, key=lambda x: -x[0]) if s > 0]


def looks_like_product(page):
    """Existence check before spending tokens: a real product page with specs."""
    if not page or len(page["text"]) < 300:
        return False
    if page.get("jsonld"):
        return True
    return any(k in page["text"].lower() for k in ("sku", "datasheet", "pinout", "technical details", "specifications", "in stock"))


class SiteAdapter:
    name = domain = ""
    row = {}

    def available(self):
        return all(os.environ.get(v) for v in self.row.get("needs", []))

    def search(self, query):
        return []

    def fetch_data(self, url):
        raw = fetch(url)
        if not raw:
            return None
        product, text = clean(raw)
        title = (product or {}).get("name") or (re.search(r"<title>(.*?)</title>", raw, re.S | re.I) or [None, ""])[1]
        return {"title": html.unescape(title).strip(), "url": url, "jsonld": product, "text": text}

    def deterministic(self, content):
        return None

    def get_prompt_instructions(self):
        return self.row.get("prompt_instructions", "")


def _classes():
    """Every adapter class by name (imported here, not at the top: the adapters import this module)."""
    from graph.parts.arduino import shops
    from graph.parts.lego import inventory
    return {c.__name__: c for c in (shops.Adafruit, shops.SparkFun, shops.Pololu, shops.Seeed, shops.Mouser,
                                    shops.DigiKey, inventory.Rebrickable)}


def adapters(domain):
    """Adapters for a registry section ("electronics", "lego"), in registry order, each carrying its registry row."""
    classes, out = _classes(), []
    for row in REGISTRY.get(domain, []):
        cls = classes.get(row["adapter"])
        if cls:
            a = cls()
            a.name, a.row = row["name"], row
            out.append(a)
    return out


def route(url):
    """Registry router: the adapter whose domain the URL belongs to, or None."""
    host = urllib.parse.urlparse(url).netloc.lower()
    for section in ("electronics", "lego"):
        for a in adapters(section):
            if a.domain and host.endswith(a.domain):
                return a
    return None
