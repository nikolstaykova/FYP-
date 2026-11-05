"""The photo check of a LEGO gather card: are the card's pieces on the table?

The card lists the pieces for the next few steps (checker.lego_gather, at most ~10 pieces and 8 kinds), so the
model does not identify LEGO from scratch: it ticks off a known list, which is much easier.
1. Haiku looks at the photos of the laid-out pieces with the list (`look`) and says, piece by piece: there (how
   many it can see), there in another colour, not sure (with a question for the learner), or not there.
2. The learner is asked about what is not settled (`result`: a close-up of an unsure piece, a photo of a piece
   that was not seen). Haiku looks at the close-up with that one question; only when it still cannot tell, Opus
   looks once (`closeup`).
Rules from the checker's tolerance: another colour is fine (the build works, it just looks different); any
minifigure face, hair or accessory is fine; many identical small pieces count as there when some are seen (a model
cannot count ten 1x1 studs reliably, so the learner is reminded how many).

result() gives the same shape as the electronics check (parts rows with status have / use / check / missing, and
asks), so the page and the tutor use one result screen for both.
"""
import pathlib

from checker import gather_vlm as vlm

FIRST = "claude-haiku-5-5"
SECOND = "claude-opus-5-5"
MANY = 3  # this many identical pieces or more: seeing some is enough

LOOK = """The learner is about to build a LEGO model and has laid out the pieces for the next few steps. Here is the
list of pieces they should have:
{items}

Look at the photos and, for EACH piece on the list (by its key), say whether it is there:
- "there": you can see it, in the right colour. `seen`: how many you can see.
- "other_colour": the same piece (same shape and size) is there, but in another colour. `colour_seen`: which.
- "unsure": something that could be it, but you cannot tell (too small, blurry, hidden, or a similar piece such as a
  2x3 plate vs a 2x4 plate). `why`: what you cannot tell. `ask`: one short, friendly question to the learner asking
  for the close-up that would settle it ("I can see a grey plate, but I can't count its studs. Can you hold it up
  close to the camera?").
- "not_there": you cannot see it at all. `ask`: "" (the learner is asked anyway).
Shape and size matter most: count studs when they show; a plate is thin, a brick three times as tall, a tile has no
studs on top. A minifigure part with another face, print, hair or accessory counts as "there". Each piece in the
photos can be only one item on the list. Do not guess: when two list items look alike and you cannot tell which is
which, say "unsure" for them.
Answer ONLY with JSON: {{"pieces": [{{"key": "p1", "status": "there", "seen": 1, "colour_seen": "", "why": "", "ask": ""}}],
"extra": ["short name of any piece on the table that is not on the list"]}}"""


def items(card):
    """The card's pieces with keys p1, p2... (`card` is a gather card from tutor.live.steps)."""
    return [{"key": f"p{i}", "what": p["what"], "count": p["count"], "colour": p.get("colour"),
             "about": p.get("about") or ""} for i, p in enumerate(card.get("parts") or [], 1)]


def _list(its):
    return "\n".join(f'- {x["key"]}: {x["count"]}x {x["what"]}' + (f' ({x["about"]})' if x["about"] else "")
                     for x in its)


def _answer(text):
    import json
    i, j = text.find("{"), text.rfind("}")
    try:
        d = json.loads(text[i:j + 1])
    except ValueError:
        return [], []
    pieces = [p for p in d.get("pieces") or [] if isinstance(p, dict) and p.get("key")]
    return pieces, [str(x) for x in d.get("extra") or [] if x][:8]


def _images(photos):
    return [(pathlib.Path(p).read_bytes(), vlm.media_type(p)) for p in photos]


def look(photos, its, model=FIRST, effort="low"):
    """One look at the photos with the list. Returns ({key: verdict}, extra pieces, stats)."""
    out, stats, _ = vlm.ask(model, _images(photos), LOOK.format(items=_list(its)), max_tokens=4000, effort=effort)
    pieces, extra = _answer(out)
    known = {x["key"] for x in its}
    got = {p["key"]: {"status": p.get("status") or "unsure", "seen": int(p.get("seen") or 0) if str(p.get("seen") or 0).isdigit() else 0,
                      "colour_seen": p.get("colour_seen") or "", "why": p.get("why") or "", "ask": p.get("ask") or "",
                      "by": model} for p in pieces if p["key"] in known}
    for x in its:  # a piece the model left out was not seen
        got.setdefault(x["key"], {"status": "not_there", "seen": 0, "colour_seen": "", "why": "", "ask": "", "by": model})
    return got, extra, {**stats, "raw": out[:3000]}


def closeup(photo, its, state_verdicts):
    """A close-up for one or more open pieces: Haiku first; the pieces it still cannot tell go to Opus once.
    Returns (new verdicts for those keys, steps for the cost log)."""
    got, _, st = look([photo], its, FIRST)
    steps = [{"what": "close-up", **{k: st.get(k) for k in ("model", "seconds", "cost_usd")}}]
    still = [x for x in its if got[x["key"]]["status"] == "unsure"
             and not any(v.get("by") == SECOND for k, v in state_verdicts.items() if k == x["key"])]
    if still:
        more, _, st2 = look([photo], still, SECOND, effort="medium")
        got.update(more)
        steps.append({"what": "close-up, second look", **{k: st2.get(k) for k in ("model", "seconds", "cost_usd")}})
    for k in got:
        got[k]["closeup"] = True
    return got, steps


def _short(what):
    return what if len(what) < 40 else what[:38].rsplit(" ", 1)[0] + "…"


def result(its, verdicts, dismissed=(), extra=()):
    """The verdicts in the electronics check's shape: {parts: [...], asks: [...], not_needed: [...]}."""
    parts, asks = [], []
    for x in its:
        v = verdicts.get(x["key"]) or {"status": "not_there", "seen": 0}
        st, need, seen = v["status"], x["count"], v.get("seen") or 0
        row = {"type": x["key"], "part": x["what"], "need": need, "have": [], "use_instead": []}
        if st == "there" and (seen >= need or (need >= MANY and seen >= 1) or seen == 0):
            row["status"] = "have"
            note = "" if seen >= need or seen == 0 else f"I can see {seen}; make sure you have {need}"
            row["have"] = [{"object": x["what"], "count": need, "why": note}]
        elif st == "there":  # fewer than needed of a piece that is easy to count
            row["status"] = "check"
            row["have"] = [{"object": x["what"], "count": seen, "why": f"I can see {seen} of the {need}"}]
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "find", "message": f"I can see {seen} of the {need} {_short(x['what'])}. "
                             "Can you find the rest and show me?"})
        elif st == "other_colour":
            row["status"] = "use another colour"
            c = v.get("colour_seen") or "another colour"
            row["use_instead"] = [{"object": f"{c} {x['what']}".strip(), "ok": True,
                                   "why": "only the colour is different, so the build still works"}]
        elif st == "unsure":
            row["status"] = "check"
            row["have"] = [{"object": x["what"], "count": seen, "why": v.get("why") or "needs a better look"}]
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "closeup", "message": v.get("ask") or
                             f"I'm not sure about the {_short(x['what'])}. Can you hold it up close to the camera?"})
        else:
            row["status"] = "skipped" if x["key"] in dismissed else "missing"
            if x["key"] not in dismissed:
                asks.append({"key": x["key"], "kind": "find", "message": f"I can't see the {_short(x['what'])}. "
                             "If you have it, show it to me."})
        parts.append(row)
    return {"parts": parts, "asks": asks[:4], "not_needed": [{"object": e} for e in extra]}
