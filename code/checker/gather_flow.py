"""The parts check with a cheap first look, then close-ups the learner takes, then (only if asked) a stronger model.

1. Haiku lists every object in the photos (gather.LOOK), and the code checks them against the lesson (gather.check).
2. The code picks what Haiku could not settle (`flags`):
   - objects it was unsure of (its `unsure` note, or a value like "possibly 1k");
   - objects it could not identify: a vague name ("red circuit board"), or a guess that it might replace a lesson part;
   - lesson parts that came out missing or "check" (Haiku may have overlooked or misread them).
3. The learner is asked, one question each (`asks`), only about what can change a verdict for this lesson: "I can
   see some resistors, but I can't read their bands. Can you take a close-up?" / "I can't see an LED. If you have
   one, take a photo of it." Haiku looks at each close-up with that one question (`closeup_look`, ~0.05 cents) and
   its answer replaces the first one (`apply_closeup`).
4. Only when Haiku still cannot tell from the close-up (`still_open`), Opus looks at that one close-up (~1 cent),
   once per question. Still open after that: the learner can retake it or skip.
`check()` runs the first look and an Opus look at all photos without a learner (benchmarks, the command line).

Run: ./pinpoint checker.gather_flow blink p1.jpg p2.jpg [--no-research]
"""
import json
import pathlib
import re
import sys
import time

from checker import gather, gather_vlm as vlm

FIRST = "claude-haiku-5-5"
SECOND = "claude-opus-5-5"

# names that say "I can see something but cannot tell what it is"
VAGUE = re.compile(r"\b(unknown|unidentified|unclear|some|something|object|item|thing|component|device|part|"
                   r"circuit board|pcb|board with|module with|(?:microcontroller|development|dev|controller|interface) board|"
                   r"chip|ic|small black|small blue)\b", re.I)
HEDGED = re.compile(r"possibl|probabl|likely|maybe|\?", re.I)

ANSWER = ('Answer ONLY with JSON: {"objects": [{"name": "", "lesson_part": "", "value": "", "count": 1, '
          '"photos": [1], "might_replace": "", "replace_note": "", "unsure": ""}]}')


def lesson_text(rec):
    parts = "\n".join(f"- {p['type']}: {p['name']} x{p['count']}" for p in rec["parts_list"])
    return f"The lesson is \"{rec['name']}\". Its parts list:\n{parts}"


def to_seen(objs, extra=()):
    """Model answers -> Seen dicts (unknown keys dropped, bad rows skipped); `extra` keys are kept as given."""
    keys = gather.Seen.model_fields
    out = []
    for o in objs:
        if not o.get("name"):
            continue
        try:
            s = gather.Seen(**{k: v for k, v in o.items() if k in keys}).model_dump()
        except Exception:
            continue
        out.append({**s, **{k: o[k] for k in extra if k in o}})
    return out


ASK_FIELD = ('- ask: only when `unsure` is not empty: one short, friendly question to the learner asking for the photo '
             'that would settle it, as if talking to them ("I can see some resistors, but I can\'t read their colour '
             'bands. Can you take a close-up of them?"). Otherwise "".')


def first_look(photos, rec, model=FIRST):
    images = [(pathlib.Path(p).read_bytes(), vlm.media_type(p)) for p in photos]
    text = (gather.LOOK + "\n" + ASK_FIELD + "\n\nThe photos are numbered in the order given (Photo 1, Photo 2, ...). "
            + lesson_text(rec) + "\nList every object in the photos. " + ANSWER.replace('"unsure": ""', '"unsure": "", "ask": ""'))
    out, stats, _ = vlm.ask(model, images, text, effort="low")
    stats["raw"] = out[:6000]
    return to_seen(vlm.json_objects(out), extra=("ask",)), stats


def flags(res, lesson_types, done=()):
    """What the first look could not settle: (objects, parts). objects: [(index in seen, reason)], parts: [(row,
    reason)]. Indexes follow res["seen"], which keeps the order of the model's list. Objects whose answer came from
    a look in `done` ("closeup", "opus") are not flagged again unless still unsure."""
    objects = []
    for i, o in enumerate(res["seen"]):
        if o.get("by") in done and not o.get("unsure"):
            continue
        if o.get("unsure"):
            objects.append((i, f"unsure: {o['unsure']}"))
        elif HEDGED.search(o.get("value") or ""):
            objects.append((i, f"value not certain: {o['value']}"))
        elif o["type"] is None and o.get("might_replace") in lesson_types:
            objects.append((i, f"not identified exactly; might replace {o['might_replace']}"))
        elif VAGUE.search(o["name"]) and o.get("matched_by") != "lesson part":
            # a vague name is flagged even when the catalogue search found something: "blue microcontroller
            # board" once matched an MKR WiFi 1010
            objects.append((i, "not identified" if o["type"] is None else f"vague name, matched to {o['type']}"))
    parts = [(r, r["status"]) for r in res["parts"] if r["status"] == "check" or r["status"].startswith("missing")]
    return objects, parts


def _a(name):
    """ "a resistor", "an LED", "an ESP32": abbreviations go by how the first letter is said."""
    n = name.strip()
    if re.match(r"(?i)(a|an|the|some|\d)\b", n):
        return n
    first = n.split()[0] if n else ""
    vowel = first[:1] in "AEFHILMNORSX" if first.isupper() and len(first) > 1 else n[:1].lower() in "aeiou"
    return ("an " if vowel else "a ") + n


PROPER = re.compile(r"^(Arduino|Raspberry|ESP|Elegoo|Seeed|Seeeduino|Adafruit|SparkFun|Nano|Uno|Mega|Pico)", re.I)


def _thing(name):
    """ "a resistor", "an LED", "an Arduino Nano": the object's name, without the details in brackets."""
    n = re.sub(r"\s*\([^)]*\)", "", name).strip() or name
    if not PROPER.match(n) and n[1:2].islower():
        n = n[0].lower() + n[1:]
    return _a(n)


def asks(res, objects, parts, dismissed=(), limit=3):
    """Questions for the learner: only what can change a verdict for this lesson, boards first, at most `limit`.
    Per lesson part that is not settled (missing or "check"):
      - an object we saw for it, or one that might stand in, that the look was unsure of: a close-up of that object;
      - otherwise: "I cannot see an LED; take a photo of it, or tell me you don't have it".
    The question is the model's own (`ask`) when it wrote one. Each has a key that stays the same across re-checks."""
    seen = res["seen"]
    flagged = {i: why for i, why in objects}
    out, used = [], set()
    for r, why in parts:
        names = {h["object"] for h in r["have"]} | {u["object"] for u in r["use_instead"]}
        cands = [i for i in flagged if i not in used and (seen[i]["name"] in names or seen[i].get("might_replace") == r["type"]
                                                           or seen[i].get("lesson_part") == r["type"])]
        if cands:
            i = cands[0]
            used.add(i)
            o = seen[i]
            msg = o.get("ask") or (
                f"I can see {_thing(o['name'])}; it might work instead of the {r['part']}, but I can't tell which model "
                "it is. Can you take a close-up of the writing on it?" if o.get("might_replace") == r["type"] else
                f"I can see {_thing(o['name'])}, but I'm not sure about it. Can you take a close-up of it?")
            out.append({"key": f"o:{o['name']}|{o.get('value', '')}", "kind": "closeup", "ref": i, "object": o["name"],
                        "part": r["part"], "message": msg})
            continue
        if r["status"].startswith("missing"):
            parts_ = r["status"].split()
            have = r["need"] - int(parts_[1]) if len(parts_) > 1 else 0
            msg = (f"I can only see {have} of the {r['need']} {r['part']} the lesson needs." if have else
                   f"I can't see {_thing(r['part'])}, which the lesson needs.") + \
                " If you have one, take a photo of it; if not, tap \u201cI don't have it\u201d."
        else:
            msg = f"I'm not sure about the {r['part']}. Can you take a close-up of it?"
        out.append({"key": f"p:{r['type']}", "kind": "find", "part": r["part"], "type": r["type"], "message": msg})
    return [q for q in out if q["key"] not in dismissed][:limit]


def closeup_look(photo, question, rec, seen_item=None, model=FIRST, effort="low"):
    """One close-up, answering only the question it was asked (Haiku; Opus when Haiku still cannot tell).
    Returns (Seen dicts, stats)."""
    about = (f"Earlier you listed: {seen_item['name']}" + (f" ({seen_item['value']})" if seen_item.get("value") else "")
             + f", count {seen_item['count']}." if seen_item else "")
    text = (gather.LOOK + "\n" + ASK_FIELD + "\n\n" + lesson_text(rec) + "\n\nThe learner took this close-up because you "
            "asked: \"" + question + "\" " + about + " Answer ONLY for the part you asked about (one entry, or one per value "
            "if you can now see different values), not for anything else in the photo. `count` is how many there are in "
            "all (keep the earlier count unless the close-up shows otherwise). If you still cannot tell, say what in "
            "`unsure` and ask again in `ask`. " + ANSWER.replace('"unsure": ""', '"unsure": "", "ask": ""'))
    out, stats, _ = vlm.ask(model, [(pathlib.Path(photo).read_bytes(), vlm.media_type(photo))], text, effort=effort)
    stats["raw"] = out[:4000]
    got = to_seen(vlm.json_objects(out), extra=("ask",))
    for g in got:
        g["by"] = "closeup" if model == FIRST else "opus"
    return got, stats


def pick(seen, question, answers):
    """The close-up answers about the part asked about (same lesson part, or what it might replace), so other things
    in the close-up are not counted twice. For an object, when none says which part it is, the first answer is
    taken as the one asked about."""
    if question["kind"] == "closeup":
        old = seen[question["ref"]]
        want = {old.get("lesson_part"), old.get("might_replace")} - {"", "none", None}
        keep = [a for a in answers if a.get("lesson_part") in want or a.get("might_replace") in want] if want else []
        return keep or answers[:1]
    return [a for a in answers if a.get("lesson_part") == question.get("type")
            or a.get("might_replace") == question.get("type")]


def still_open(kept):
    """After a close-up: nothing useful about the part, or still unsure: the stronger model looks at it."""
    return not kept or any(k.get("unsure") for k in kept)


def apply_closeup(seen, question, answers):
    """The close-up's answers (see `pick`) in place of the object asked about, or added for a missing part."""
    keep = pick(seen, question, answers)
    if question["kind"] == "closeup":
        i = question["ref"]
        return seen[:i] + keep + seen[i + 1:] if keep else seen
    return seen + keep


def second_look(photos, rec, seen, objects, parts, model=SECOND):
    """Opus on the same photos, asked only about the flagged objects and parts."""
    if not objects and not parts:
        return [], {}
    images = [(pathlib.Path(p).read_bytes(), vlm.media_type(p)) for p in photos]
    listed = "\n".join(f"{i}. {s['name']}" + (f" ({s['value']})" if s["value"] else "") + f" x{s['count']}"
                       for i, s in enumerate(seen))
    ask_obj = "\n".join(f"- object {i} ({seen[i]['name']}): {why}" for i, why in objects) or "- none"
    ask_parts = "\n".join(f"- {r['type']}: {r['part']} x{r['need']} (first look: {why})" for r, why in parts) or "- none"
    text = (gather.LOOK + "\n\nThe photos are numbered in the order given. " + lesson_text(rec) + "\n\n"
            "A first, quicker look listed these objects (numbered):\n" + listed + "\n\n"
            "Look closely at these objects it was not sure of, and give your own answer for each, with `ref` set to "
            "its number. If it is not really there, give it with \"gone\": true. If it is really several different "
            "objects, give each with the same ref.\n" + ask_obj + "\n\n"
            "Also look for these lesson parts, which the first look did not find or could not confirm. If you can "
            "see one that is NOT already in the list above, add it with \"ref\": \"new\"; if it is in the list "
            "under another name, answer for that object's number instead.\n" + ask_parts + "\n\n"
            "Answer only for those objects and parts, not the others. Keep `unsure` for what you still cannot tell. "
            'Answer ONLY with JSON: {"objects": [{"ref": 0, "gone": false, "name": "", "lesson_part": "", '
            '"value": "", "count": 1, "photos": [1], "might_replace": "", "replace_note": "", "unsure": ""}]}')
    out, stats, _ = vlm.ask(model, images, text, effort="medium")
    stats["raw"] = out[:6000]
    return vlm.json_objects(out), stats


def merge(seen, objects, answers):
    """Haiku's list with Opus's answers in place of the flagged objects; new parts added at the end. Returns
    (merged seen, changes). A flagged object Opus did not answer for stays as Haiku had it."""
    asked = {i for i, _ in objects}
    by_ref, new = {}, []
    for a in answers:
        ref = a.get("ref")
        if isinstance(ref, str) and ref.isdigit():
            ref = int(ref)
        if isinstance(ref, int) and ref in asked:
            by_ref.setdefault(ref, []).append(a)
        elif ref == "new" or ref is None:
            new.append(a)  # an answer for an object we did not ask about is ignored
    merged, changes = [], []
    for i, s in enumerate(seen):
        if i not in by_ref:
            merged.append(s)
            continue
        kept = [a for a in by_ref[i] if not a.get("gone")]
        now = to_seen(kept)
        for n in now:
            n["by"] = "opus"
        merged += now
        changes.append({"was": f"{s['name']}" + (f" ({s['value']})" if s["value"] else ""),
                        "now": "; ".join(n["name"] + (f" ({n['value']})" if n["value"] else "") for n in now)
                        or "not there"})
    for n in to_seen([a for a in new if not a.get("gone")]):
        n["by"] = "opus"
        merged.append(n)
        changes.append({"was": "not seen", "now": n["name"] + (f" ({n['value']})" if n["value"] else "")})
    return merged, changes


def check(lesson_id, photos, research=True, first=FIRST, second=SECOND, seen=None, answers=None):
    """The two-step check. `seen` / `answers` replace the model calls (tests and re-runs)."""
    rec, _ = gather.lesson(lesson_id)
    t0 = time.perf_counter()
    stats1 = {}
    if seen is None:
        seen, stats1 = first_look(photos, rec, first)
    res1 = gather.check(lesson_id, photos, research=False, seen=seen)
    types = {r["type"] for r in res1["parts"]}
    objects, parts = flags(res1, types)
    stats2 = {}
    if answers is None:
        answers, stats2 = second_look(photos, rec, seen, objects, parts, second)
    merged, changes = merge(seen, objects, answers) if (objects or parts) else (seen, [])
    final = gather.check(lesson_id, photos, research=research, seen=merged)
    stages = [s for s in (stats1, stats2) if s]
    final["look"] = {"seconds": round(sum(s["seconds"] for s in stages), 1),
                     "cost_usd": round(sum(s["cost_usd"] for s in stages), 6), "model": "+".join(s["model"] for s in stages)}
    return {"lesson": lesson_id, "first": res1, "final": final, "stages": stages, "changes": changes,
            "asked": {"objects": [{"object": seen[i]["name"], "why": why} for i, why in objects],
                      "parts": [{"part": r["part"], "why": why} for r, why in parts]},
            "seconds_total": round(time.perf_counter() - t0, 1)}


def text(out):
    lines = [gather.text(out["final"])]
    if out["changes"]:
        lines.append(f"Looked at again by {SECOND}: " + "; ".join(f"{c['was']} -> {c['now']}" for c in out["changes"]))
    lines.append("Steps: " + ", ".join(f"{s['model']} {s['seconds']} s ${s['cost_usd']}" for s in out["stages"]))
    return "\n".join(lines)


def main(argv=None):
    a = list(argv or sys.argv[1:])
    research = "--no-research" not in a
    a = [x for x in a if x != "--no-research"]
    out = check(a[0], a[1:], research=research)
    print(text(out))
    d = gather.ROOT / "data/parts_checks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{a[0]}-gather-flow-{time.strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps(out, indent=1, default=str))
    print(f"saved {f.relative_to(gather.ROOT)}")


if __name__ == "__main__":
    main()
