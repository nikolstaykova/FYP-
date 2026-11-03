"""How a new part type is named, so one part has one id.

What it is   the naming rules (N1-N7 below): RULES is the text every builder prompt carries; check() is what code
             does with each new part type before it is stored (a name that hides a part we have is sent back with
             the id to use); audit() runs the rules over the whole catalogue.
Used for     keeping the catalogue free of duplicate ids, so a new lesson with one new part adds one card and reuses
             the rest (GRAPH_SPEC §3).
Where        extract.py (RULES in the prompt), arduino/part_review.py, parts/ingest.py, parts/arduino/tutorial.py,
             lesson_store.py (P7).

One part type has one id, whatever lesson first uses it, so a new lesson with one new part adds one card and
reuses the rest. RULES is the text every builder prompt carries; check() is what code does with each entry in a
graph's new_part_types before it is stored, and audit() runs the same rules over the whole catalogue.

  N1  format: lowercase letters, digits and hyphens: dht11, hc-sr04, arduino-nano-33-iot
  N2  no instance properties in the id: colour, a resistor's or capacitor's value, a length or size (those go in
      the instance's props: led1 {colour: red}, r1 {value: 220})
  N3  the maker's model or family first, no category word in front of it: dht11, not temp-dht11 or sensor-dht11
  N4  not a part the catalogue already has under another id or alias: use that card's id. The part metadata can veto
      a lookalike (a different chip, interface, logic voltage, or what a power swap does)
  N6  a generic name (no model number: 'resistor', 'a DC motor') is never a new part: it reuses the catalogue's part
      of that kind the lessons use most (generic_default), with any value in the instance's props
  N5  (review) the metadata says it may be a part the catalogue has although the names do not show it: same
      category, polarity, ports and model number, most name words shared (rpi-3b and raspberry-pi-3)
Failures go back to Claude as repair messages, with the id to use where one exists.
"""
import pathlib
import collections
import re

RULES = """PART TYPE NAMES (strict; a part type has ONE id in every lesson)
- First use a catalogue type: if the part is in the catalogue under any name or alias, use that type id, even when
  the tutorial calls it something else ("red LED", "5mm LED" and "light emitting diode" are all `led`).
- A part named only generically ("a resistor", "a capacitor", "a motor") is never a new type: use the catalogue's
  type for that kind of part, with any value the lesson gives in the instance's props (r1 {"value": "220"}).
- Only a part the catalogue does not have gets a new type, named by these rules:
  1. lowercase letters, digits and hyphens only: dht11, hc-sr04, 74hc595, arduino-nano-33-iot
  2. the maker's model number, or the part's common name when it has none: dht11, ssd1306, potentiometer
  3. the maker or board family first, then the model: arduino-mkr-zero, raspberry-pi-5, grove-relay, adafruit-<model>
  4. no category word in front of a model: dht11, not temp-dht11 or sensor-dht11
  5. nothing that varies between copies of the same part: no colour, no resistor or capacitor value, no wire
     length, no LED size (3mm/5mm). Those are props of the instance: led1 {"colour": "red"}, r1 {"value": "220"}
  6. a different part only when its ports or behaviour differ (a 12 V pump is a different part from a 5 V pump,
     an electrolytic capacitor from a ceramic one; a red LED is not a different part from a green one)
  7. no packaging in the id: a board with or without soldered headers is the same part. A revision is part of
     the name when it is other hardware (arduino-uno-wifi-rev2 is not arduino-uno-r4-wifi)
- Instance ids are a short name and a number: r1, led2, wire3, uno, bb1."""

COLOURS = {"red", "green", "blue", "yellow", "white", "black", "orange", "purple", "violet", "pink", "brown", "grey",
           "gray", "amber", "warm", "cool"}
VALUE = re.compile(r"^\d+(\.\d+)?(r|k|kohm|ohm|ohms|m|meg|uf|nf|pf|mm|cm)$|^\d+k\d+$|^\d+r\d+$")
CATEGORY_FIRST = re.compile(r"^(temp|temperature|sensor|module|cable|display|motor|chip|ic|board)-(?=.*\d)")
FILLER = {"generic", "small", "basic", "standard", "simple", "new", "my", "part", "component", "thing", "board"}
VALUE_PARTS = {"resistor", "capacitor", "potentiometer", "pot", "inductor", "trimpot", "trimmer"}  # a number after
# one of these is its value (resistor-330 is a resistor of 330 ohm)
MAKERS = {"arduino", "adafruit", "sparkfun", "seeed", "dfrobot", "elegoo", "keyestudio", "waveshare"}  # a maker word
# missing or added does not make another part (mkr1000-board is arduino-mkr1000)
FORMAT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _rules_only(type_id):
    """N1-N3 for one id: [(rule, message)]."""
    out = []
    if not FORMAT.match(type_id or ""):
        out.append(("N1", f"type id '{type_id}' must be lowercase letters, digits and hyphens (e.g. hc-sr04)"))
        return out
    words = type_id.split("-")
    props = [w for i, w in enumerate(words) if w in COLOURS or VALUE.match(w) or
             (re.fullmatch(r"\d+", w) and i and words[i - 1] in VALUE_PARTS)]
    if props:
        out.append(("N2", f"type id '{type_id}' carries {', '.join(props)}: that varies between copies, so it goes in the "
                          f"instance's props (colour, value), not in the type"))
    fillers = [w for w in words if w in FILLER]
    if fillers:
        out.append(("N2", f"type id '{type_id}' has filler words {', '.join(fillers)}: name the part by its model or common name"))
    if CATEGORY_FIRST.match(type_id):
        out.append(("N3", f"type id '{type_id}' starts with a category word: put the model first "
                          f"('{re.sub(CATEGORY_FIRST, '', type_id)}')"))
    return out


SAME_PART = re.compile(r"^(headers?|pins?|with|soldered|unsoldered|breakout|gpio)$")  # packaging only: a revision
# (r3, r4, rev2) is other hardware on Arduino boards (the Uno WiFi Rev2 is not the Uno R4 WiFi), so it counts


def _shape(card):
    """What makes two cards behave the same: polarity and category (a card's port list can be more or less complete
    for the same board, so ports are not compared)."""
    ib = card.get("intrinsic_behaviour") or {}
    return bool(ib.get("is_polarized", card.get("polarized"))), card.get("category")


def _existing(type_id, name, store, exclude=(), card=None):
    """An existing card this type is the same part as, or None. The two ids may differ only by words that do not
    make another part: packaging (headers, pins), or something that is a property of a copy
    (a colour, a value: capacitor-100nf is capacitor-22pf with another value). Any other word makes another part
    (led-strip is not led, arduino-nano-every is not arduino-nano, dht11 is not dht22, pump-5v is not pump-12v).
    The existing card must also come up in the free-text search for the new one (ids, names, aliases)."""
    from graph.parts.arduino import tutorial
    loose = lambda w: bool(SAME_PART.match(w) or VALUE.match(w) or w in COLOURS or w in MAKERS)  # noqa: E731
    ws = re.sub(CATEGORY_FIRST, "", type_id).split("-")  # temp-dht22 is matched as dht22
    mine = {w for i, w in enumerate(ws) if w not in FILLER and not (re.fullmatch(r"\d+", w) and i and ws[i - 1] in VALUE_PARTS)}
    query = tutorial.VALUE.sub(" ", (name or type_id.replace("-", " ")))
    for hit in store.search(query, limit=8):
        if hit.id == type_id or hit.id in exclude:
            continue
        theirs = {w for w in hit.id.split("-") if w not in FILLER}
        core_mine, core_theirs = {w for w in mine if not loose(w)}, {w for w in theirs if not loose(w)}
        if core_mine and core_mine == core_theirs:
            (pa, ca), (pb, cb) = _shape(card or {}), _shape(store.cards[hit.id])
            known = card is not None and ("polarized" in card or "intrinsic_behaviour" in card)
            if card is not None and ((known and pa != pb) or (ca and cb and ca != cb)):  # a draft may leave them out
                continue  # another polarity or kind: another part (an electrolytic is not a ceramic capacitor)
            if metadata_veto(metadata(type_id) or (card or {}).get("metadata") or {}, metadata(hit.id)):
                continue  # the metadata says they are different parts
            return hit.id
    return None


# ---------------------------------------------------------------- the part metadata as evidence (parts.json)
IDENTITY = ("chip", "model", "interface", "logic_v", "wireless")  # standard fields that say which part it is
ABBREV = {"rpi": "raspberry pi"}


def _metadata():
    import json
    f = pathlib.Path(__file__).resolve().parents[3] / "code" / "graph" / "parts" / "parts.json"
    return {t: v.get("metadata") or {} for t, v in json.loads(f.read_text()).items()} if f.exists() else {}


_META = []


def metadata(type_id):
    if not _META:
        _META.append(_metadata())
    return _META[0].get(type_id) or {}


def _specs(meta):
    norm = lambda v: ",".join(sorted(map(str, v))) if isinstance(v, list) else str(v)  # noqa: E731
    return {k: re.sub(r"[^a-z0-9.,]", "", norm(v).lower()) for k, v in (meta.get("specs") or {}).items()
            if v not in (None, [], "")}


def metadata_veto(a_meta, b_meta):
    """Why two parts are not the same by their metadata (an identity specification both give, differently), or None."""
    from graph.parts.part_metadata import normalize  # both as codes: a draft in words and a stored entry compare the same
    a_meta, b_meta = normalize(a_meta), normalize(b_meta)
    sa, sb = _specs(a_meta), _specs(b_meta)
    for k in IDENTITY:
        if k in sa and k in sb and sa[k] != sb[k]:
            return f"their {k} differs ({sa[k]} / {sb[k]})"
    ra, rb = a_meta.get("reverse_power"), b_meta.get("reverse_power")
    if ra and rb and ra != rb:
        return "a power swap does different things to them"
    return None


def _models(text):
    """Model numbers in an id or name, digits split from letters (3b -> 3, b): values (10k, 100nf) left out."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", ABBREV.get(text, text).lower()):
        if re.search(r"\d", w) and not VALUE.match(w):
            out |= set(re.findall(r"\d+", w))
    return out


def _words_of(card):
    text = " ".join([card.get("part_type_id", "").replace("-", " "), card.get("display_name", ""), *card.get("aliases", [])])
    for a, b in ABBREV.items():
        text = re.sub(rf"\b{a}\b", b, text.lower())
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in FILLER and len(w) > 2}


def metadata_duplicate(card, store, exclude=()):
    """A card the metadata says may be this same part although the names do not show it (N5, for review): the same
    category, polarity and port count, the same model numbers, most of the name words shared, and no identity
    specification differing. Returns (id, why) or None."""
    me, my_meta = card, metadata(card.get("part_type_id")) or card.get("metadata") or {}
    my_models = _models(me.get("part_type_id", "").replace("-", " ") + " " + me.get("display_name", ""))
    my_words = _words_of(me)
    for t, other in store.cards.items():
        if t == me.get("part_type_id") or t in exclude:
            continue
        if other.get("category") != me.get("category") or len(other.get("ports") or []) != len(me.get("ports") or []):
            continue
        if bool((other.get("intrinsic_behaviour") or {}).get("is_polarized")) != bool((me.get("intrinsic_behaviour") or {}).get("is_polarized")):
            continue
        if _models(t.replace("-", " ") + " " + other.get("display_name", "")) != my_models or not my_models:
            continue
        theirs = _words_of(other)
        if not my_words or len(my_words & theirs) / len(my_words | theirs) < 0.6:
            continue
        if metadata_veto(my_meta, metadata(t)):
            continue
        return t, "same category, polarity, ports and model number, most name words shared, no metadata against it"
    return None


# ---------------------------------------------------------------- a generic name reuses a part we have
ARTICLES = {"a", "an", "the", "some", "one", "two", "three", "four", "x", "pcs", "pieces", "piece", "any", "basic",
            "generic", "standard", "small", "simple"}
_USE = []


def usage():
    """How many lessons use each part type (the lesson library: circuit graphs and the lesson store)."""
    if not _USE:
        import collections
        import glob
        import json
        root = pathlib.Path(__file__).resolve().parents[3]
        c = collections.Counter()
        for f in glob.glob(str(root / "data" / "lessons" / "arduino" / "*" / "graph.json")):
            c.update({n["type"] for n in json.loads(pathlib.Path(f).read_text())["nodes"]})
        _USE.append(c)
    return _USE[0]


def is_generic(name):
    """A name that picks out no particular part: at most three words once articles and colours are left out, with no
    model number, no maker and no board variant ('resistor', 'a DC motor', 'red LED'; not 'Arduino Uno', 'DHT11')."""
    from graph.parts.arduino.tutorial import VARIANTS
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in ARTICLES and w not in COLOURS]
    return (bool(words) and len(words) <= 3 and not any(re.search(r"\d", w) for w in words)
            and not any(w in MAKERS or w in VARIANTS for w in words))


def generic_default(name, store):
    """The catalogue part a generic name reuses: among the cards that are this kind of part (the search's best hit's
    category, the name's words in their names), the one the lessons use most; ties by search rank. Returns
    (type id, why, alternatives) or None."""
    words = {re.sub(r"s$", "", w) for w in re.findall(r"[a-z]+", name.lower()) if w not in ARTICLES and w not in COLOURS}
    hits = store.search(name, limit=8)
    if not hits or not words:
        return None
    cat = store.cards[hits[0].id].get("category")

    def fits(h):
        c = store.cards[h.id]
        text = " ".join([h.id, c.get("display_name", ""), *c.get("aliases", []), c.get("category", "")]).lower()
        return c.get("category") == cat and all(w in text for w in words)
    cands = [h.id for h in hits if fits(h)]
    if not cands:
        return None
    use = usage()
    best = max(cands, key=lambda t: (use[t], -cands.index(t)))
    others = [t for t in cands if t != best]
    why = (f"'{name}' names no particular part: reuse the lessons' most-used {cat} ({best}, in {use[best]} lessons)"
           if use[best] else f"'{name}' names no particular part: reuse the catalogue's {best}")
    return best, why, others


REVISION = re.compile(r"^(rev|r|v|gen|mk)\d+$")


def _grams(*texts):
    """Ids and names cut at spaces, hyphens and punctuation, joined in runs of one or two: 'HC-SR04 sensor' gives
    hc, sr04, hcsr04, … ; kept are those with a digit, four characters or more, not a value (220ohm) or a revision
    (rev2, r3, v2)."""
    out = set()
    for text in texts:
        chunks = [c for c in re.split(r"[^a-z0-9]+", str(text or "").lower()) if c]
        for n in (1, 2):
            for i in range(len(chunks) - n + 1):
                g = "".join(chunks[i:i + n])
                if len(g) >= 4 and re.search(r"\d", g) and not VALUE.match(g) and not REVISION.match(g) and \
                        not any(REVISION.match(c) for c in chunks[i:i + n]):
                    out.add(g)
    return out


_MODELS = {}


def _model_index(store):
    """(the cards whose short id is a model: 'dht11', 'hc-sr04', 'arduino-mkr1000'; the maker's model number of each
    card, for the models only one card has)."""
    key = id(store)
    if key not in _MODELS:
        by_id, by_model = {}, collections.defaultdict(set)
        for cid, card in getattr(store, "cards", {}).items():
            parts = [c for c in cid.split("-") if c]
            if len(parts) <= 2 and re.search(r"\d", cid) and not VALUE.match(parts[-1]):
                by_id[re.sub(r"[^a-z0-9]", "", cid)] = cid
            m = ((metadata(cid) or {}).get("specs") or {}).get("model")
            if m and len(re.sub(r"[^a-z0-9]", "", str(m).lower())) >= 4:
                by_model[re.sub(r"[^a-z0-9]", "", str(m).lower())].add(cid)
        _MODELS[key] = (by_id, {k: next(iter(v)) for k, v in by_model.items() if len(v) == 1})
    return _MODELS[key]


def _same_model(type_id, name, store, exclude=()):
    """N7: the existing card the new type is by its model number: (its id, the model), or None. A model counts when
    it IS a card's short id (dht11, hc-sr04), or it is the maker's model number of exactly one card (a chip or a
    family name several products share, ws2812, nano33, is not one part)."""
    by_id, by_model = _model_index(store)
    for g in sorted(_grams(type_id, name), key=len, reverse=True):
        for hit in (by_id.get(g), by_model.get(g)):
            if hit and hit != type_id and hit not in exclude:
                return hit, g
    return None


def page_key(url):
    """A shop page's address without its scheme, query and trailing slash, lowercased: one key per product page."""
    if not url:
        return None
    return re.sub(r"^https?://(www\.)?", "", url.split("?")[0].split("#")[0].rstrip("/").lower()) or None


def same_page(type_id, card, store):
    """N7 too: the existing card made from the same shop page as this card (one product is one part, whatever its
    packaging: arduino-mkr1000-headers was arduino-mkr1000), or None."""
    key = page_key((card.get("source") or {}).get("url"))
    if not key:
        return None
    return next((cid for cid, c in getattr(store, "cards", {}).items()
                 if cid != type_id and page_key((c.get("source") or {}).get("url")) == key), None)


def check(new_types, store):
    """N1-N4 for a graph's new_part_types ([{type, name, ...}]) against the card store: [(rule, message)]."""
    issues = []
    for d in new_types or []:
        t, name = d.get("type", ""), d.get("name") or ""
        issues += _rules_only(t)
        from graph.parts.cards import REDIRECTS
        if t in REDIRECTS:
            issues.append(("N4", f"'{t}' was merged into '{REDIRECTS[t]}' (the same part): use '{REDIRECTS[t]}'"))
            continue
        if store is not None and t in getattr(store, "cards", {}):
            continue  # it is a catalogue type already
        if store is not None and is_generic(name or t.replace("-", " ")):  # N6: a generic name is a part we have
            g = generic_default(name or t.replace("-", " "), store)
            if g:
                issues.append(("N6", f"new type '{t}' ({name}) is a generic name: use '{g[0]}' ({g[1]}); put any value "
                                     f"in the instance's props"))
                continue
        same = _existing(t, name, store, card=d) if store is not None else None
        page = None if same or store is None else same_page(t, d, store)
        if page:
            issues.append(("N7", f"new type '{t}' ({name}) is from the shop page the catalogue's '{page}' was made "
                                 f"from (the same product): use '{page}'"))
            continue
        model = None if same or store is None else _same_model(t, name, store)
        if model:
            issues.append(("N7", f"new type '{t}' ({name}) carries the model {model[1]}, which the catalogue's "
                                 f"'{model[0]}' already is: use '{model[0]}'"))
            continue
        if same:
            issues.append(("N4", f"new type '{t}' ({name}) looks like the catalogue's '{same}': use '{same}', with any "
                                 f"colour or value in the instance's props"))
    return issues


def audit(store):
    """The rules over the whole catalogue: {type id: [(rule, message)]}, N4 meaning another card looks like it."""
    out, pairs = {}, set()
    for t, card in sorted(store.cards.items()):
        found = _rules_only(t)
        same = _existing(t, card.get("display_name"), store, exclude=(t,), card=card)
        if same and frozenset((t, same)) not in pairs:  # each pair once
            pairs.add(frozenset((t, same)))
            found.append(("N4", f"is the same part as '{same}' ({store.cards[same].get('display_name')})"))
        elif not same:
            dup = metadata_duplicate(card, store)
            if dup and frozenset((t, dup[0])) not in pairs:
                pairs.add(frozenset((t, dup[0])))
                found.append(("N5", f"may be the same part as '{dup[0]}' ({store.cards[dup[0]].get('display_name')}): {dup[1]}"))
        if found:
            out[t] = found
    return out


if __name__ == "__main__":
    from graph.parts.cards import CardStore
    store = CardStore(pathlib.Path("code/graph/parts/arduino/cards_electronics.json"))
    found = audit(store)
    print(f"{len(found)} of {len(store.cards)} electronics types break a naming rule")
    for t, issues in found.items():
        for r, m in issues:
            print(f"  {r} {t}: {m}")
