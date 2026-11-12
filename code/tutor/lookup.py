"""What the tutor can look up in a lesson while it teaches: anything the lesson's graphs hold, by card, part or topic.

The brief (live.brief) gives the tutor the lesson's outline; these lookups let it travel the rest on demand, so it
answers from the lesson instead of guessing:
  lesson_info(topic)  overview, how_it_works, troubleshooting, try_next, expected_result, cards (every card with
                      what it covers), parts (every part with how many and on which cards)
  step_info(n)        one card in full: the words, goal, why, hints, what changed, its pieces (with where they go),
                      what joins to what (in words), what can be swapped, the bag, the code
  part_info(name)     a part by any words ("red brick", "resistor", "2x4 plate"): what it is, tips, how many, the
                      cards that use it, what can stand in for it, and its pieces in this lesson
Everything comes from lesson_store.assemble (the database, else the files) and live.steps (the cards); index() is
cached per lesson.
"""
import functools
import re

TOPICS = ("overview", "how_it_works", "troubleshooting", "try_next", "expected_result", "cards", "parts")


def _clean(name):
    return re.sub(r"\s*\[.*?\]", "", name or "").strip()


def _label(p):
    """A piece the way a person says it: "red Brick 2 x 4", "220 ohm Resistor"."""
    props = p.get("props") or {}
    bits = [str(props[k]) for k in ("colour", "value") if props.get(k)]
    return " ".join(bits + [_clean(p.get("name") or p.get("type") or "part")])


def _port(port):
    port = str(port or "")
    m = re.match(r"(stud|anti)\.(\d+)\.(\d+)", port)
    if m:
        return f"{'stud' if m.group(1) == 'stud' else 'underside'} {m.group(2)},{m.group(3)}"
    return {"A": "long leg (+)", "C": "short leg (-)", "1": "one leg", "2": "other leg"}.get(port, port)


@functools.lru_cache(maxsize=16)
def index(lesson_id):
    """The lesson as lookups: cards, parts (by type), pieces (by instance), lesson notes, swaps."""
    from graph import lesson_store
    from tutor import live
    view = lesson_store.assemble(lesson_id)
    les = view.get("lesson") or {}
    cards = live.steps(lesson_id)["steps"]
    card_of = {c["id"]: c["n"] for c in cards}
    title_of = {c["n"]: c["title"] for c in cards}
    swaps = (les.get("substitutions") or {}).get("parts") or {}
    pins = (les.get("substitutions") or {}).get("pins") or {}

    pieces, parts, step_raw = {}, {}, {}
    for s in view["steps"]:
        step_raw[s["id"]] = s
        for p in s.get("parts") or []:
            inst = p.get("instance")
            if inst and not re.match(r"^\d+\s*x", str(inst)):
                pieces.setdefault(inst, {"label": _label(p), "type": p.get("type"), "card": card_of.get(s["id"])})
            row = parts.setdefault(p.get("type") or _label(p), {
                "name": _clean(p.get("name")), "type": p.get("type"), "colours": set(), "cards": [], "pieces": [],
                "about": p.get("about") or {}, "category": p.get("category"), "called": 0})
            m = re.match(r"^\s*(\d+)\s*x", str(inst or ""))  # a booklet call-out: "2 x"
            row["called"] += (int(m.group(1)) if m else 1) * max(1, int(s.get("times") or 1) if str(s.get("times") or 1).isdigit() else 1)
            if (p.get("props") or {}).get("colour"):
                row["colours"].add(p["props"]["colour"])
            n = card_of.get(s["id"])
            if n and n not in row["cards"]:
                row["cards"].append(n)
            if inst and pieces.get(inst):
                row["pieces"].append(inst)
            if not row["about"] and p.get("about"):
                row["about"] = p["about"]
    for r in view.get("parts_list") or []:  # counts and descriptions from the parts list
        if not isinstance(r, dict):
            continue
        row = parts.setdefault(r.get("type"), {"name": _clean(r.get("name")), "type": r.get("type"), "colours": set(),
                                               "cards": [], "pieces": [], "about": {}, "category": None})
        row["count"] = r.get("count")
        row["about"] = row["about"] or r.get("about") or {}
        for i in r.get("instances") or []:
            if i not in row["pieces"]:
                row["pieces"].append(i)
    cat = None
    for row in parts.values():
        row.setdefault("count", len(row["pieces"]) or row.get("called") or None)
        if not row["about"] and row["type"]:  # a booklet piece: its card from the parts catalogue
            try:
                if cat is None:
                    from graph.parts import part_catalogue
                    cat = part_catalogue.load()
                    cat = cat.get("parts", cat) if isinstance(cat, dict) else {}
                    cat = cat if isinstance(cat, dict) else {c.get("part_type_id"): c for c in cat}
                card, _ = lesson_store.definition(cat, row["type"])
                meta = (card or {}).get("metadata") or {}
                row["about"] = {"description": card.get("description") or meta.get("description"),
                                "tips": meta.get("tips") or card.get("tips") or []} if card else {}
            except Exception:
                row["about"] = {}
        why = {swaps[i].get("why") for i in row["pieces"] if i in swaps and swaps[i].get("why")}
        free = sorted({f for i in row["pieces"] if i in swaps for f in swaps[i].get("free") or []})
        vals = [swaps[i].get("value_ohms") for i in row["pieces"] if i in swaps and swaps[i].get("value_ohms")]
        row["can_swap"] = ({"free": free, "why": sorted(why)} if free or why else {}) | (
            {"value_ohms_range": vals[0]} if vals else {})
    return {"lesson_id": lesson_id, "name": les.get("name") or view.get("title") or lesson_id,
            "type": view.get("lesson_type"), "lesson": les, "cards": cards, "card_of": card_of, "title_of": title_of,
            "steps": step_raw, "parts": parts, "pieces": pieces, "pins": pins}


def _piece(ix, ref):
    """A port reference "b12:stud.1.1" / "r1:1" / "bb1:10t.b" in words."""
    inst, _, port = str(ref).partition(":")
    who = ix["pieces"].get(inst, {}).get("label") or inst
    if inst.startswith("bb"):
        m = re.match(r"(\d+)([a-z])", port)
        return f"breadboard column {m.group(1)}" if m else "the breadboard"
    if ix["type"] == "arduino" and (inst in ("uno", "arduino") or "uno" in (ix["pieces"].get(inst, {}).get("type") or "")):
        return f"Arduino pin {port}"
    return f"the {who} ({_port(port)})" if port else f"the {who}"


def lesson_info(lesson_id, topic="overview"):
    ix, les = index(lesson_id), index(lesson_id)["lesson"]
    topic = topic if topic in TOPICS else "overview"
    if topic == "cards":
        return {"cards": [{"n": c["n"], "title": c["title"], "kind": c["kind"],
                           "about": (c["text"] or "")[:90] + ("…" if len(c["text"] or "") > 90 else "")}
                          for c in ix["cards"]][:120]}
    if topic == "parts":
        return {"parts": [{"name": r["name"], "count": r.get("count"), "colours": sorted(r["colours"]),
                           "on_cards": r["cards"][:12]} for r in ix["parts"].values()][:120]}
    if topic == "overview":
        built = [c for c in ix["cards"] if c["kind"] != "gather"]
        return {"name": ix["name"], "type": ix["type"], "description": les.get("description") or les.get("notes"),
                "difficulty": les.get("difficulty"), "cards": len(ix["cards"]), "build_steps": len(built),
                "gather_cards": len(ix["cards"]) - len(built), "bags": sorted({c["bag"] for c in built if c.get("bag")}),
                "different_parts": len(ix["parts"]), "link": les.get("link"),
                "topics_you_can_look_up": [t for t in TOPICS if t != "overview" and (t in ("cards", "parts") or les.get(t))]}
    found = les.get(topic) or (les.get("result") if topic == "expected_result" else None)
    return {topic: found} if found else {topic: None, "note": "this lesson has nothing on that; say so, do not guess"}


def step_info(lesson_id, n):
    ix = index(lesson_id)
    cards = ix["cards"]
    try:
        c = cards[int(n) - 1]
    except (ValueError, IndexError, TypeError):
        return {"error": f"there are cards 1 to {len(cards)}"}
    out = {"card": c["n"], "title": c["title"], "kind": c["kind"], "text": c["text"]}
    for k in ("goal", "why", "what_changed", "expected", "bag"):
        if c.get(k):
            out[k] = c[k]
    if c.get("hints"):
        out["hints"] = c["hints"]
    if c["kind"] == "gather":
        out["covers_steps"] = c.get("covers")
        out["pieces"] = [f'{p["count"]}x {p["what"]}' if p["count"] > 1 else p["what"] for p in c["parts"]]
        return out
    raw = ix["steps"].get(c["id"]) or {}
    if raw.get("description"):
        out["picture_shows"] = raw["description"]
    pieces = []
    for p in raw.get("parts") or []:
        d = {"piece": _label(p)}
        if p.get("where"):
            d["where"] = p["where"]
        tips = (p.get("about") or {}).get("tips")
        if tips:
            d["tip"] = tips[0]
        pieces.append(d)
    if pieces:
        out["pieces"] = pieces[:12]
    joins = [f'{_piece(ix, e["from"])} → {_piece(ix, e["to"])}' + (f' ({e["method"]})' if e.get("method") else "")
             for e in raw.get("connections") or [] if e.get("type") in ("joined", "electrical", "contact")]
    if joins:
        out["joins"] = joins[:14]
    for k in ("builds", "attaches"):
        if raw.get(k):
            out[k] = raw[k][:6]
    if c.get("times", 1) > 1:
        out["build_times"] = c["times"]
    if c.get("code"):
        out["code_on_screen"] = True
        out["code"] = c["code"][:3000]
    swaps = sorted({f'{ix["pieces"].get(p.get("instance"), {}).get("label") or _label(p)}: '
                    + ", ".join((ix["lesson"].get("substitutions") or {}).get("parts", {}).get(p.get("instance"), {}).get("free") or [])
                    for p in raw.get("parts") or []
                    if (ix["lesson"].get("substitutions") or {}).get("parts", {}).get(p.get("instance"), {}).get("free")})
    if swaps:
        out["free_to_change"] = swaps[:8]
    out["cards"] = len(cards)
    return out


def _words(t):
    t = (t or "").lower().replace("×", "x")
    t = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", t)
    return set(re.findall(r"[a-z]+|\d+x\d+|\d+", t)) - {"the", "a", "an", "of", "with", "and", "piece", "part"}


BANDS = ["black", "brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white"]


def ohms(text):
    """220 / "220 ohm" / "4.7k" / "10K" / "1M" / "4k7" in a part's name -> ohms, or None."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([kKmM]?)(\d*)\s*(?:ohms?|Ω|R\b)?", text or "")
    if not m:
        return None
    num = float(m.group(1).replace(",", "."))
    if m.group(3) and m.group(2):  # 4k7
        num = float(f"{m.group(1)}.{m.group(3)}")
    return round(num * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)])


def resistor_bands(value):
    """The colour bands of a resistor value: (4-band, 5-band), read from the end away from the gold/brown
    tolerance band. 220 -> red red brown gold / red red black black brown; 4.7 -> yellow violet gold gold."""
    if not value or value <= 0:
        return None
    mult = {-2: "silver", -1: "gold", **dict(enumerate(BANDS))}

    def bands(n):  # n significant digits, then the multiplier
        e = 0
        v = float(value)
        while v >= 10 ** n - 0.5:
            v /= 10
            e += 1
        while v < 10 ** (n - 1) - 1e-9:
            v *= 10
            e -= 1
        d = str(int(round(v))).zfill(n)[:n]
        return [BANDS[int(c)] for c in d] + [mult.get(e, "?")]

    return bands(2) + ["gold"], bands(3) + ["brown"]


def recognise(name, key, category):
    """How to pick this part out of a box: general knowledge, worked out here so Pip never guesses it."""
    words = f"{name} {key or ''} {category or ''}".lower()
    if "resistor" in words:
        v = ohms(name)
        b = resistor_bands(v) if v else None
        if b:
            return {"how_to_recognise": (
                f"A small tube with coloured stripes. {name.split()[-1]} ohm reads {', '.join(b[0][:3])} then a gold band "
                f"(4 stripes), or {', '.join(b[1][:4])} then a brown band (5 stripes, common in starter kits: the body "
                "is often blue). Read from the end away from the gold or brown band. Kit resistors often come on a "
                "paper strip labelled with the value. Not sure? A multimeter on ohms tells you for certain."),
                "bands_4": b[0], "bands_5": b[1]}
        return {"how_to_recognise": "A small tube with coloured stripes; the stripes give the value."}
    if "led" in words.split() or "led" in (key or "") or "light emitting" in words:
        return {"how_to_recognise": ("A small coloured dome with two legs. The longer leg is + (anode); the rim of the "
                                     "dome has a flat edge on the - side (short leg). A clear LED shows its colour "
                                     "only when lit.")}
    if "potentiometer" in words or "pot " in words:
        return {"how_to_recognise": ("A knob or dial with three legs. The value is printed on it as a code: 103 means "
                                     "10k ohm (10 then 3 zeros), 102 is 1k, 104 is 100k.")}
    if "capacitor" in words:
        return {"how_to_recognise": ("Ceramic: a small flat disc, value as a 3-digit code: 104 = 100 nF (10 then 4 "
                                     "zeros, in picofarads), 103 = 10 nF; either way round. Electrolytic: a little "
                                     "can with the value printed on it and a stripe down the side on the - leg "
                                     "(the shorter leg); it must go the right way round.")}
    if "diode" in words:
        return {"how_to_recognise": "A small black or glass tube; the stripe at one end marks the - side (cathode)."}
    if "button" in words or "switch" in words:
        return {"how_to_recognise": "A tactile button: a small square with a round plunger and four legs (two pairs "
                                    "are joined inside: the pins on the same side as the bent legs face)."}
    if "jumper" in words or "wire" in words:
        return {"how_to_recognise": "Short wires with pins on both ends; the colour does not change the circuit."}
    return {}


def part_info(lesson_id, name):
    ix = index(lesson_id)
    want = _words(name)
    if not want:
        return {"error": "say which part"}
    scored = []
    for key, r in ix["parts"].items():
        have = _words(" ".join([r["name"], key or "", " ".join(r["colours"]), r.get("category") or "",
                                " ".join((r["about"].get("specifications") or {}).get("aliases", []) if isinstance(r["about"].get("specifications"), dict) else [])]))
        hit = len(want & have)
        if hit:
            scored.append((hit / len(want), -len(have), key, r))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if not scored:
        return {"found": [], "note": "no part in this lesson matches those words; ask what it looks like, or look at the parts list (lesson_info parts)"}
    out = []
    for score, _, key, r in scored[:3]:
        if out and score < scored[0][0]:
            break
        a = r["about"] or {}
        d = {"name": r["name"], "count": r.get("count"), "colours": sorted(r["colours"]),
             "on_cards": [f"{n} ({ix['title_of'].get(n)})" for n in r["cards"][:10]]}
        if a.get("description"):
            d["what_it_is"] = a["description"]
        if a.get("tips"):
            d["tips"] = a["tips"][:3]
        if ix["type"] == "arduino":
            d.update(recognise(r["name"], key, r.get("category")))
        if r.get("can_swap"):
            d["can_swap"] = r["can_swap"]
        out.append(d)
    pins = ix["pins"]
    if ix["type"] == "arduino" and pins and any("arduino" in (x["name"] or "").lower() or "uno" in (x["name"] or "").lower() for x in out):
        out[0]["pins_that_can_change"] = {k.split(":")[-1]: {"could_use": v.get("stand_ins"), "never": v.get("refused")}
                                          for k, v in pins.items()}
    return {"found": out}
