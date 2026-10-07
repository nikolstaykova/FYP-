"""Electronics parts first, by code: read a tutorial's parts list and match each item to a Layer 0 card.

  hardware_list(manual)        the items under "Hardware Required" / "Hardware & Software Needed" / "Hardware"
  match(item, store)           (card id or None, cleaned name): free-text search over the cards (search.py), other
                               names from aliases.json
Items that are not circuit parts (USB cable, computer, IDE, SD card) are dropped. Unmatched items go to the
ingestion pipeline (shops) before the build.
"""
import re

HEADING = re.compile(r"^#+\s*(hardware[^\n]*|components[^\n]*|parts[^\n]*|what you will need[^\n]*|you will need[^\n]*)$", re.I | re.M)
NOT_PARTS = re.compile(r"\b(usb|cable|computer|laptop|pc\b|ide|software|sd ?card|micro ?sd|keyboard|mouse|monitor|"
                       r"screen|tv|internet|wi-?fi|account|app\b|python|scratch|raspberry pi os|power supply|charger|"
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
    from .search import tokens
    name, _ = clean(item)
    if not name or NOT_PARTS.search(name):
        return "skip", name
    query = re.sub(r"(\d+)\s*[x×]\s*(\d+)", r"\1x\2", VALUE.sub(" ", name))  # "8 x 8" is written 8x8 on cards
    if set(re.findall(r"[a-z0-9]+", query.lower())) <= GENERIC:
        return "skip", name  # "2 analog sensors": a description, not a part; the build decides from the circuit
    hits = store.search(query)
    if not hits:
        return None, name
    best = hits[0]
    card = store.cards[best.id]
    card_terms = set(tokens(" ".join([best.id.replace("-", " "), best.id, card["display_name"], *card.get("aliases", [])])))
    models = {t for t in tokens(re.sub(r"\b\d+\s+(axis|pin|pins|way|channels?|digits?|keys?|segments?)\b", r"\1", query))
              if re.search(r"\d", t)}  # "2 axis", "3 pin": a description, not a model number
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    if any(set(re.findall(r"[a-z0-9]+", al.lower())) == query_words for al in card.get("aliases", [])):
        return best.id, name  # the item is exactly one of the card's other names
    variant_clash = (set(re.findall(r"[a-z0-9]+", f"{best.id} {card['display_name']}".lower())) & VARIANTS) - query_words
    return (best.id if best.coverage >= 0.67 and models <= card_terms and not variant_clash else None), name
