"""A tutorial's parts list, read and matched by code.

What it is   hardware_list: the items under 'Hardware Required' (and similar headings); match: each item to a card
             by free-text search, with other names from parts/arduino/aliases.json; items that are not circuit parts
             (USB cable, computer, IDE) dropped; quantity and value read from the item.
Used for     the parts-first step of an Arduino lesson and the parts-count laws.
Where        arduino/circuit_graph.py (tutorial_counts, tutorial_items), arduino/part_review.py,
             parts/mcp_server.py, parts/naming.py.
"""
import re

HEADING = re.compile(r"^#+\s*(hardware[^\n]*|components[^\n]*|parts[^\n]*|what you will need[^\n]*|you will need[^\n]*)$", re.I | re.M)
NOT_PARTS = re.compile(r"\b(usb|cable|computer|laptop|pc\b|ide|software|sd ?card|micro ?sd|keyboard|mouse|monitor|"
                       r"(?:computer|laptop|pc|tv) screen|^screen$|tv\b|internet|wi-?fi (?:network|connection|router|access)|"
                       r"^wi-?fi$|account|app\b|python|scratch|raspberry pi os|power supply|charger|"  # a WiFi board is a part
                       r"headphones|optional|librar|package|licen[cs]e|installed|device|network|surface|oscilloscope|google|matlab|"
                       r"multimeter|soldering|account)", re.I)
VALUE = re.compile(r"\b\d+(\.\d+)?\s*(k|m|u|µ|n|p)?\s*(ohms?|Ω|f|farads?|v|volts?|mm|w)\b|\b\d+(\.\d+)?[kmunp]\d*\b", re.I)


def hardware_list(manual):
    """Bullet items of the tutorial's hardware section(s)."""
    items = []
    for m in HEADING.finditer(manual):
        if re.search(r"software", m.group(1), re.I) and not re.search(r"hardware", m.group(1), re.I):
            continue
        body = manual[m.end():]
        nxt = re.search(r"^#+\s", body, re.M)
        for line in body[: nxt.start() if nxt else len(body)].splitlines():
            b = re.match(r"^\s*[-*+]\s+(.+)$", line) or re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            if b:
                items.append(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", b.group(1)).strip())
    return items


SIZE = re.compile(r"^\s*\d+\s*[x×]\s*\d+(?![\d.]*\s*(k|m|ohms?|Ω|[munpµ]?f|v|w)\b|[\d.]*[kmΩ])", re.I)  # "8 x 8 matrix"


def quantity(item):
    """The count the list states ('2 x 220 ohm resistor' -> 2, '3 LEDs' -> 3), or None if it states none
    ('8 x 8 LED matrix' is a size, not a count)."""
    if SIZE.match(item):
        return None
    q = re.match(r"^\s*(\d+)\s*(x|×)\s*|^\s*(\d+)\s+(?!(ohms?|Ω|k|v|volts?|mm|[munp]f|w|x|×|axis|pin|pins|way|channels?|digits?|keys?|segments?|bits?|wire)\b)", item, re.I)
    return int(q.group(1) or q.group(3)) if q else None


def clean(item):
    """'2 x 10k ohm resistor (brown-black-orange)' -> ('10k ohm resistor', 2)."""
    q = None if SIZE.match(item) else re.match(r"^\s*(\d+)\s*(x|×)\s*|^\s*(\d+)\s+(?!(ohms?|Ω|k|v|volts?|mm|[munp]f|w|x|×|axis|pin|pins|way|channels?|digits?|keys?|segments?|bits?|wire)\b)", item, re.I)
    name = re.sub(r"\(.*?\)", "", item[q.end():] if q else item)
    name = re.split(r"\s+(or|e\.g\.)\s+", name)[0]
    return re.sub(r"\s+", " ", name).strip(" .,:;*"), int(q.group(1) or q.group(3)) if q else 1


GENERIC = {"analog", "digital", "sensor", "sensors", "input", "output", "device", "component", "components", "part",
           "parts", "module", "modules", "any", "other", "electronic", "electronics"}
VARIANTS = {"pico", "nano", "mega", "uno", "mini", "micro", "zero", "leonardo", "due", "every", "iot", "ble", "lite",
            "pro", "plus", "max", "c3", "c6", "s2", "s3", "zero2"}  # a board/module variant word must match


def match(item, store):
    """Card id for a parts-list item, or None if no card is this part, by free-text search over the cards
    (search.py). Component values (220 ohm, 100 nF, 4k7) are instance properties, so they are left out of the
    query. The best hit is accepted when it contains two thirds of the query's terms and every model number
    in it (dht11, sr04, 33)."""
    name, _ = clean(item)
    if not name or NOT_PARTS.search(name):
        return "skip", name
    query = re.sub(r"(\d+)\s*[x×]\s*(\d+)", r"\1x\2", VALUE.sub(" ", name))  # "8 x 8" is written 8x8 on cards
    if set(re.findall(r"[a-z0-9]+", query.lower())) <= GENERIC:
        return "skip", name  # "2 analog sensors": a description, not a part; the build decides from the circuit
    hits = store.search(query)
    if not hits:
        return None, name
    from graph.parts import naming  # a generic item ("capacitor", "a motor") reuses the lessons' most-used part of that kind
    v = VALUE.search(item)  # a value the item states picks the card that carries it, while values sit in some ids
    if v:                   # (capacitor-100nf, capacitor-22pf: GRAPH_SPEC would have them as one part with a value)
        want = re.sub(r"[^a-z0-9]", "", v.group(0).lower().replace("µ", "u"))
        for h in hits[:8]:
            c = store.cards[h.id]
            if want and want in re.sub(r"[^a-z0-9]", "", " ".join([h.id, c.get("display_name", "")]).lower().replace("µ", "u")):
                return h.id, name
    if naming.is_generic(name):  # the item as written: "10uF capacitor" names a value, so it is not generic
        g = naming.generic_default(query, store)
        if g:
            return g[0], name
    for best in hits[:5]:  # the best hit may be a sibling with another model number (Uno WiFi Rev2 for Uno R4 WiFi)
        found = _accept(best, store, query, name)
        if found:
            return found, name
    return None, name


def _accept(best, store, query, name):
    """The hit's id if it is this part: two thirds of the query's terms, every model number, no variant clash."""
    from graph.parts.cards import tokens
    card = store.cards[best.id]
    card_terms = set(tokens(" ".join([best.id.replace("-", " "), best.id, card["display_name"], *card.get("aliases", [])])))
    models = {t for t in tokens(re.sub(r"\b\d+\s+(axis|pin|pins|way|channels?|digits?|keys?|segments?)\b", r"\1", query))
              if re.search(r"\d", t)}  # "2 axis", "3 pin": a description, not a model number
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    if any(set(re.findall(r"[a-z0-9]+", al.lower())) == query_words for al in card.get("aliases", [])):
        return best.id  # the item is exactly one of the card's other names
    variant_clash = (set(re.findall(r"[a-z0-9]+", f"{best.id} {card['display_name']}".lower())) & VARIANTS) - query_words
    return best.id if best.coverage >= 0.67 and models <= card_terms and not variant_clash else None
