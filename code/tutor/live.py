"""The voice tutor: a lesson from the store (the database when it is set up), taught step by step by voice.

The learner talks to a speech-to-speech model (Gemini Live: it hears and speaks, and stops the moment the learner
talks over it). It knows the lesson from `brief()`: the session plan (hello and the learner's name, gather the
parts, the parts check with photos and close-ups, then the steps), every step with its words, goal, hints and parts,
and the rules for talking. Its tools (`tools()`) drive the screen and the parts check: remember_name,
show_parts_list, open_camera, take_photo, check_parts and take_closeup (non-blocking: it can keep talking while the
check runs), skip_question, start_building, show_step, finish_lesson. LEGO lessons check each gather card instead.

The browser connects to Gemini itself (lowest delay for audio), with a short-lived token from `session()`, so the
API key stays on the server. Without a voice service, `reply()` is the free fallback: Haiku writes the tutor's next
words as text, and the browser's own voices speak them.

Cost: every Live turn reports its tokens (usageMetadata); `cost_usd()` prices them with PRICES, and the page stops
the voice at CAP_USD (a lesson must stay under 4 euro, even an hour long).
"""
import datetime
import json
import os
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL = "gemini-3.8-live"
VOICE = "Kore"
WS = ("wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService."
      "BidiGenerateContentConstrained?access_token=")
# USD per 1M tokens, on the high side of the published figures (Nov 2026), so the cap is reached early rather than late
PRICES = {"text_in": 0.75, "audio_in": 3.00, "text_out": 4.50, "audio_out": 12.00}
CAP_USD = 4.00  # about 3.70 euro: the page stops the voice here
WARN_USD = 3.00

RULES = """RESPOND IN ENGLISH. YOU MUST RESPOND UNMISTAKABLY IN ENGLISH, whatever language you think you hear.

You are Pip, a warm, funny tutor who teaches a hands-on build by voice, like a good friend sitting next to the
learner. They have their hands full, so you speak everything; the screen only shows what you are talking about.

Your personality:
- Relaxed, playful and human. Joke now and then (a light one, not every turn), react to what they say, and
  celebrate the small wins ("There it is!"). Never robotic, never a lecture.
- If they are taking ages, you may gently roast them, like a friend would ("Take your time, the LED's not going
  anywhere. Well, it's not going to blink by itself either."). Keep it kind: tease the situation, never the
  person, and offer help right after. Messages like "(It has been 2 minutes since they said anything)" tell you
  how long it has been.

How you talk:
- Always speak English. If what you hear sounds like another language or makes no sense, it is probably English
  misheard: answer in English, and if you could not follow, just say so like a person would ("Sorry, I didn't
  catch that, could you say it again?"). Never mention languages.
- Short, natural spoken sentences, one or two at a time. No lists, no headings, no markdown, no ids or codes
  (never say "step-3", "b11", "r1", "led1:A" or a question key).
- Call parts the short, everyday way: "the resistor", "the LED", "the black wire", "the Arduino". Say a value
  ("220 ohm") only once, while they gather the parts (so they pick the right one out of the box); while building,
  never, unless the lesson has two of that kind to tell apart (a 10k and a 220). A colour only when two look alike. Do not repeat what you have just said, and do not re-list parts they already have.
- Sound like a person, not a manual: "Grab the resistor and pop one leg in column 10, the other in 14. Either way
  round is fine." rather than "Place the resistor with one leg in column 10 and the other leg in column 14".
- Never narrate what you are doing or waiting for ("Waiting for the user to place the LED"): just stop talking
  and listen.
- Do not agree just to be nice. If they guess something ("the long leg is the straight one?"), tell them honestly
  how to be sure (the longer leg; the flat edge on the LED's rim is on the short leg's side).
- Use their name now and then, not in every sentence.
- One thing at a time, then let them do it: end with a short check such as "Tell me when it's in."
- Only move on when they clearly say they have done it ("done", "it's in", "next", "okay, what now?"). A question,
  a worry, something you could not follow, or "I'm still on the last bit" means you stay where you are: answer it,
  then ask again. If you are not sure whether they are done, ask ("Is the LED in?"). Never skip ahead.
- If they interrupt you, stop and listen; answer what they said, not what you were about to say.
- When they ask a question, answer briefly, then come back to where you were.
- Tool results come back as JSON: never read JSON aloud; say what it means.

What you know. Two kinds of knowledge:
- This lesson's facts (which parts, which values, which column or pin, what goes where, what joins to what): only
  from the lesson. Below is its outline; the lookup tools give you everything else in it, so use them instead of
  guessing.
- Know-how, which you already have and SHOULD use, like any good tutor: how to recognise a part (a resistor's colour
  bands, an LED's long leg and flat edge, a capacitor's code, a LEGO plate against a brick, counting studs), how a
  breadboard works, how to hold or press things, safety, and why things work. When they ask "how do I find / tell /
  recognise / know which one", explain exactly how, concretely: the colours, the shape, the markings. Never brush a
  question off ("just pick the right one", "it's in your kit"): that is never an answer.
Side questions are part of teaching. Answer them properly, briefly, then come back to where you were. Hands-on
know-how you should give without looking anything up:
- A leg into the breadboard: push it straight down, firmly, until it holds by itself, about 5 to 8 mm (most of the
  bare leg; it should not wobble or pop up). Won't go in? The leg is bent or kinked (straighten it with a
  fingernail), the leg is too thick or not lined up with the hole (wiggle it gently while pushing), or the hole is
  damaged (move along to the next free hole in the same column, since only the column matters). Never force it
  sideways. Long legs can be bent down flat or trimmed, as long as two bare legs never touch.
- Jumper wires: push the pin in fully; a wire that sits loose gives a flickering or dead circuit.
- The Arduino's header pins: the wire goes in the black strip, all the way down; the numbers are printed beside it.
- LEGO: press until it clicks and sits flat with no gap; studs line up exactly. Stuck pieces come apart with a brick
  separator or by twisting gently, never with teeth.
- "Does this match / is this right?": if you can tell from what they say, answer; if you need to see it, ask them to
  hold it up to the camera and use look.
Their versions: when the check shows they have a different colour wire, or a stand-in part (a check result lists
"their_versions"), or they tell you they are using another colour or part, call use_instead (once per thing) and
from then on always call it THEIR way ("the blue wire", not "the orange wire"), in every step. Colour and length of
a jumper wire never change the circuit, so say yes to any colour.
The lookup tools: step_info (any card in full: why, hints, which piece goes where, what joins to what, what
may change, the code), part_info (a part by any words: what it is, how to recognise it (a resistor's exact colour
bands, worked out for its value: say those, not your own), tips, how many, which cards use it, what can stand in
for it), lesson_info (how it works, troubleshooting, what to try next, the expected result, every card,
every part). Look up before you answer a question about a part, a step that is not on the screen, "why", "what if",
"what can I use instead", or "it doesn't work". You can look up while you talk ("let me check").
Never invent parts, pins or connections that are not in the lesson. If the lesson does not cover something, answer
from your know-how and say so if you are not sure ("usually..."); then offer a way to be certain (a close-up photo,
a multimeter, the label on the bag)."""

BREADBOARD = """What matters on the breadboard, and what does not:
- Column numbers in the steps are only suggestions. Each column on one half of the breadboard is one strip: the
  holes in that column (on that half) are joined, and the two halves are separate. So any column works, as long as
  the same legs share a column as in the lesson, and the two legs of one part are in different columns.
- If the learner uses other columns, that is completely fine: say so, and from then on talk in their columns
  ("then the LED's long leg goes in your column 12, next to the resistor"). Never insist on the lesson's numbers.
- Whenever you give them a column that differs from the lesson's, call use_column first with the lesson's number
  and theirs (for example lesson 14, theirs 11), once for every column that changes, also later ones (if the
  LED's short leg moves from the lesson's 15 to their 12, call use_column for 15 too), so the step cards on the
  screen show their columns. Keep the
  mapping consistent: a lesson column always becomes the same column of theirs.
- What must share a column in this lesson (any column, as long as these are together):
{strips}
- What can change: {free}"""

FLOW_HELLO_NEW = """1. Hello. Introduce yourself in one sentence ("Hi, I'm Pip, I'll be your tutor today") and ask their name.
   Then wait for their answer: call no tool and start nothing else until they have told you. When they tell you,
   call remember_name with exactly the name they said (never guess one), and greet them by name. Then ask, in a
   friendly way, how much they have built before ("Have you done any electronics before, or is this your first
   time?") and call remember_level with beginner, some, or advanced from what they say."""
FLOW_HELLO_KNOWN = """1. Hello. Greet {name} by name, warmly, in one sentence (you have met before).{level_q}"""

FLOW_ARDUINO = """2. Gather. In one go: say in one sentence what they will build, call show_parts_list, and name every part to
   put on the table, naturally and grouped ("an Arduino Uno, a breadboard, a red LED, a 220 ohm resistor and two
   jumper wires"). Then ask them to tell you when everything is on the table, and wait.
3. Check. When they are ready, call open_camera (always before the first photo) and ask them to spread the parts out on a plain surface in view of
   the camera, and to tell you when to take the picture. When they say so ("take it", "ready", "now"), call
   take_photo. One clear photo is enough: do not ask for more unless the check says it cannot see something. Then say "let me have a
   look" and call check_parts.
   In the phone's browser the learner takes the photo with their phone's own camera (take_photo and the close-up
   tools then say "waiting"): ask them to tap Take photo, then wait; you are told as soon as they have taken it.
   Some learners upload photos instead of using the camera (a message tells you, and the camera tools say so too):
   then never take a photo; call open_camera first (it shows the upload area), ask them to upload one to three
   photos and to tell you when they have, then call check_parts. A close-up can be uploaded too: its result comes to you as a message, so do not take it again.
   The result says, part by part, what they have, what can be used instead (and why), what you are not sure of, and
   what is missing, and it may have questions. Tell them like a person would: first what is good, then what can
   stand in (with the reason, briefly), then each question in your own words with their name ("Mark, I can see the
   resistors, but I can't read their colour bands. Can you hold one up close to the camera?"). Then stop and wait:
   never take the close-up in the same breath as asking for it. Only when they say they are holding it up (or say
   "take it", "ready"), call take_closeup with that question's key: it takes the photo, checks it and gives you the
   new result. When two or more parts need a closer look, offer to do them in one go: they hold them all up
   together (or upload one photo of them together), and you call take_closeup_all when they are ready. If they
   say they don't have a part, call skip_question with its key, and tell them what they can do
   instead (find one, or what could stand in).
   When everything is settled, say well done and ask if they are ready to start building; call start_building
   when they say yes (or right away if they ask to carry on anyway)."""
FLOW_LEGO = """2. Gather. They have the set, so there is no parts check. Say in one sentence what they will build, and that
   they will not hunt for every piece at once: before each few steps (or each numbered bag) a card shows the pieces
   to find first. Then call start_building."""
FLOW_BUILD = """{n}. Build. Before you talk about a step, call show_step with its number. If the lesson's first step is gathering
   the parts and they were already checked, do not repeat it: show it and go straight on. For each step, say which
   part to pick up (the short way), then what to do with it. When they say they are done, go on to the next
   step. When they seem stuck, give the step's hints, one at a time. After the last step, call finish_lesson and
   celebrate.{lego}"""
FLOW_BUILD_LEGO = """
   The LEGO lesson comes as cards: gather cards (kind gather: "Find the pieces", or "Bag 2: find the pieces") and
   build steps. show_step takes the card number. On a gather card: if it says to open a bag, tell them to open that
   bag first. Then say the pieces the short way (colour and shape: "two red 2 by 4 bricks, a black wheel"), a few
   at a time for a beginner, all in one go for advanced. If one is hard to find, help (colour, size, how many studs,
   what it looks like). When they say they have them, ask them to lay the pieces out flat on a plain table, a
   little apart, and call open_camera; when they say "ready" (or "take it"), call take_photo, say "let me have a
   look" and call check_parts: it checks the photo against this card. (In upload mode: ask them to upload the photo
   and tell you, then call check_parts.) Tell the result like for any parts check: what is there, what is in
   another colour (fine: the build just looks different), then each question in your own words, and wait; when
   they hold a piece up, call take_closeup with its key (or take_closeup_all for several at once); skip_question if
   they don't have it. When it is settled (or they want to carry on anyway, or they tick all the pieces on the
   card instead), call show_step with the next card.
   On a build step, say it by its title ("Step 4"), never by the card number.
   The screen helps them see it: {visual} Point them to it ("have a look at the picture: see where the red brick
   sits?"), and when they are stuck, ask them to look at it again before you explain more."""

VISUAL_BOOKLET = ("each build step shows the booklet's own picture of that step (they can tap it to make it big): the "
                  "pieces of the step and where they go.")
VISUAL_3D = ("each build step shows a 3D model of what is built so far, and plays the step's new pieces flying into "
             "place, one by one; they can turn it with a finger, zoom, and press \"Show me again\". A gather card "
             "shows the model so far.")

LEVELS = {
    "beginner": """Their level: BEGINNER (first time). Go slowly: one small action at a time ("first just the resistor").
   Say briefly why it matters, in plain words. After each part, check with them ("Is it in? Both legs pushed all
   the way down?") before going on. Explain any word they may not know (breadboard column, leg, pin) the first
   time. Be extra encouraging, and expect questions.""",
    "some": """Their level: SOME EXPERIENCE. Give each step as it is, with a short reason only when it is not obvious.
   Check that they are done before going on.""",
    "advanced": """Their level: ADVANCED. Be brief: give each step in a sentence, combine small steps when it makes sense,
   no explanations unless they ask, no hand-holding. Still wait until they say they are done.""",
}

TOOL_DEFS = {
    "remember_name": {"description": "Remember the learner's name for this and later lessons.",
                      "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}},
    "remember_level": {"description": "Remember how much they have built before, to set your pace: beginner (first "
                                      "time), some (has built a few things), advanced (knows what they are doing).",
                       "parameters": {"type": "OBJECT", "properties": {"level": {"type": "STRING",
                                      "enum": ["beginner", "some", "advanced"]}}, "required": ["level"]}},
    "show_parts_list": {"description": "Show the lesson's parts list on the screen as a checklist.",
                        "parameters": {"type": "OBJECT", "properties": {}}},
    "open_camera": {"description": "Open the photo panel on the screen: the camera, or the upload area if the learner "
                                   "uploads photos. Always call it before asking for photos or a close-up.",
                    "parameters": {"type": "OBJECT", "properties": {}}},
    "use_column": {"description": "The learner uses a different breadboard column from the lesson's: from now on the "
                                  "screen shows their column wherever the steps say the lesson's.",
                   "parameters": {"type": "OBJECT", "properties": {
                       "lesson": {"type": "INTEGER", "description": "the column number the lesson's steps use"},
                       "theirs": {"type": "INTEGER", "description": "the column the learner uses instead"}},
                       "required": ["lesson", "theirs"]}},
    "take_photo": {"description": "Take a photo of the parts with the camera now. Returns how many photos there are.",
                   "parameters": {"type": "OBJECT", "properties": {}}},
    "check_parts": {"description": "Check the photos against the lesson's parts list (takes 5 to 15 seconds). Returns "
                                   "what they have, what can be used instead, what is not sure, what is missing, and "
                                   "questions (each with a key).",
                    "behavior": "NON_BLOCKING", "parameters": {"type": "OBJECT", "properties": {}}},
    "take_closeup": {"description": "Take a close-up photo now for one question and check it (takes 5 to 15 seconds). "
                                    "Returns the new result.",
                     "behavior": "NON_BLOCKING",
                     "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING", "description": "the question's key"}},
                                    "required": ["key"]}},
    "take_closeup_all": {"description": "When there are two or more questions: take ONE close-up photo of all those parts "
                                        "held together, and check it for every question at once (takes 5 to 15 seconds). "
                                        "Returns the new result.",
                         "behavior": "NON_BLOCKING", "parameters": {"type": "OBJECT", "properties": {}}},
    "skip_question": {"description": "The learner does not have that part, or wants to skip the question. Returns the "
                                     "new result.",
                      "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}}, "required": ["key"]}},
    "use_instead": {"description": "The learner uses their own version of something in the lesson: a different "
                                   "colour wire (\"orange wire\" -> \"blue wire\"), brick colour, or a stand-in part. "
                                   "From now on the step cards show theirs, and you must call it theirs too.",
                    "parameters": {"type": "OBJECT", "properties": {
                        "lesson": {"type": "STRING", "description": "the words the lesson uses, e.g. \"orange wire\""},
                        "theirs": {"type": "STRING", "description": "what they use instead, e.g. \"blue wire\""}},
                        "required": ["lesson", "theirs"]}},
    "look": {"description": "Look through the camera to answer a question you cannot answer without seeing "
                            "(\"does this colour match?\", \"is this the right resistor?\", \"is it in the right "
                            "hole?\", \"what is this piece?\"). First ask them to hold it up to the camera; call it when "
                            "they say it is there. Takes about 5 seconds. Returns what was seen, as the answer to your question.",
             "behavior": "NON_BLOCKING",
             "parameters": {"type": "OBJECT", "properties": {"question": {"type": "STRING",
                            "description": "exactly what to find out, with what the lesson expects (\"Is this resistor "
                                           "220 ohm: red, red, brown, gold?\")"}}, "required": ["question"]}},
    "start_building": {"description": "Go to the building steps on the screen (step 1).",
                       "parameters": {"type": "OBJECT", "properties": {}}},
    "show_step": {"description": "Show a step of the lesson on the screen. Call it before you talk about that step.",
                  "parameters": {"type": "OBJECT", "properties": {"n": {"type": "INTEGER", "description": "the step number, from 1 (in a LEGO lesson: the card number, gather cards counted)"}},
                                 "required": ["n"]}},
    "finish_lesson": {"description": "The learner has finished the last step.", "parameters": {"type": "OBJECT", "properties": {}}},
    "lesson_info": {"description": "Look up the lesson as a whole: overview, how_it_works, troubleshooting, try_next, "
                                   "expected_result, cards (every card and what it covers), parts (every part, how "
                                   "many, on which cards).",
                    "parameters": {"type": "OBJECT", "properties": {"topic": {"type": "STRING", "enum": [
                        "overview", "how_it_works", "troubleshooting", "try_next", "expected_result", "cards", "parts"]}},
                        "required": ["topic"]}},
    "step_info": {"description": "Look up one card in full (it does not change the screen): its words, goal, why, "
                                 "hints, each piece and where it goes, what joins to what, what may change, the code.",
                  "parameters": {"type": "OBJECT", "properties": {"n": {"type": "INTEGER", "description": "the card number, from 1"}},
                                 "required": ["n"]}},
    "part_info": {"description": "Look up a part of this lesson by any words (\"resistor\", \"red 2x4 brick\", \"hinge\"): "
                                 "what it is, tips, how many, which cards use it, what can stand in for it.",
                  "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}},
}
CHECK_TOOLS = ("show_parts_list", "open_camera", "take_photo", "check_parts", "take_closeup", "take_closeup_all",
               "skip_question", "use_column")


LEGO_SKIP = ("show_parts_list", "use_column")  # a LEGO lesson checks each gather card, not a parts list or columns


def tools(lesson_type):
    """The tools for this lesson: electronics has the parts check and breadboard columns; LEGO checks each gather
    card with the same photo tools."""
    names = [t for t in TOOL_DEFS if lesson_type == "arduino" or t not in LEGO_SKIP]
    return [{"functionDeclarations": [{"name": n, **TOOL_DEFS[n]} for n in names]}]


def _part_words(p):
    props = p.get("props") or {}
    bits = [str(props.get(k)) for k in ("colour", "value") if props.get(k)]
    return " ".join(bits + [p.get("name") or p.get("type") or "part"]) + (f" ({p['where']})" if p.get("where") else "")


def _count(p):
    """How many of this piece: a booklet call-out says "2 x"; elsewhere each entry is one piece."""
    m = re.match(r"\s*(\d+)\s*x\b", str(p.get("instance") or ""))
    return int(m.group(1)) if m else 1


def steps(lesson_id):
    """The lesson's steps as the learner sees them and the tutor teaches them, in order, numbered from 1. A LEGO lesson
    has its gather cards (stored with the lesson, graph/lego_gather.py): each card's pieces are those of the steps it
    covers."""
    from graph import lesson_store
    view = lesson_store.assemble(lesson_id)
    lego = view.get("lesson_type") == "lego"
    out = []
    for s in view["steps"]:
        if s.get("kind") == "overview":
            continue
        if lego and s.get("kind") == "gather":  # a stored gather card: its pieces are the steps' it covers (below)
            out.append({"n": len(out) + 1, "id": s["id"], "kind": "gather", "title": s.get("title") or "Find the pieces",
                        "text": s.get("text") or "", "goal": None, "hints": [], "why": None, "what_changed": None,
                        "parts": [], "picture": None, "code": None, "code_file": None, "expected": None, "number": "",
                        "bag": s.get("bag"), "times": 1, "covers": s.get("covers") or []})
            continue
        if lego and not s.get("parts") and re.match(r"open bag \d+\.?$", (s.get("text") or "").strip(), re.I):
            continue  # the bag's gather card says to open it
        counted, meta = {}, {}
        for p in s.get("parts") or []:
            w = _part_words({k: v for k, v in p.items() if k != "where"})
            counted[w] = counted.get(w, 0) + _count(p)
            meta.setdefault(w, {"type": p.get("type"), "colour": (p.get("props") or {}).get("colour"),
                                "about": ((p.get("about") or {}).get("description") or "")[:200]})
        picture = ((s.get("source") or {}).get("picture") or "")
        prog = s.get("program") if isinstance(s.get("program"), dict) else {}
        code = prog.get("text") or ""
        if code.count("\n\n") > 0.4 * max(1, code.count("\n")):  # some sketches were saved double-spaced
            code = code.replace("\n\n", "\n")
        times = int(s.get("times") or 1) if str(s.get("times") or 1).isdigit() else 1
        text = s.get("text") or ""
        if times > 1 and str(times) not in text:
            text += f" (Build this {times} times.)"
        out.append({"n": len(out) + 1, "id": s["id"], "kind": s.get("kind"),
                    "title": {"gather": "Gather the parts", "upload": "Upload the code"}.get(s.get("kind"))
                    or f"Step {sum(1 for x in out if x['kind'] != 'gather' or not lego) + 1}",  # LEGO cards are not steps
                    "text": text, "goal": s.get("goal"), "hints": s.get("hints") or [],
                    "why": s.get("why"), "what_changed": s.get("what_changed"),
                    "parts": [{"what": w, "count": c, **(meta[w] if lego else {})} for w, c in counted.items()],
                    "picture": picture if picture.startswith("data/lessons/booklet/") else None,
                    "code": code or None, "code_file": prog.get("file") if code else None,
                    "expected": s.get("expected"),
                    "number": str(s.get("number") or s.get("n") or ""), "bag": s.get("bag"), "times": times})
    if lego:
        _fill_cards(out)
    return {"lesson_id": lesson_id, "name": (view.get("lesson") or {}).get("name") or view.get("title") or lesson_id,
            "lesson_type": view.get("lesson_type"), "steps": out}


def _fill_cards(steps):
    """The stored gather cards' pieces: those of the steps each covers (a split card: only the pieces it lists)."""
    by_id = {s["id"]: s for s in steps}
    build_no = {s["id"]: k for k, s in enumerate((x for x in steps if x["kind"] != "gather"), 1)}  # "steps 1 to 3"
    for i, card in enumerate(steps):
        if card["kind"] != "gather":
            continue
        got, nums = {}, []
        for c in card.pop("covers", []):
            st = by_id.get(c["step"])
            if not st:
                continue
            nums.append(build_no[st["id"]])
            want = {(x.get("type"), x.get("colour")): x["count"] for x in c.get("pieces") or []}
            for p in st["parts"]:
                k = (p.get("type"), p.get("colour"))
                count = want.get(k) if want else p["count"] * max(1, st.get("times") or 1)
                if not count:
                    continue
                if p["what"] in got:
                    got[p["what"]]["count"] += count
                else:
                    got[p["what"]] = {**p, "count": count}
        card["parts"] = list(got.values())
        if nums:
            card["covers"] = [min(nums), max(nums)]


LEG = {"A": "long leg (+)", "C": "short leg (-)", "1": "one leg", "2": "other leg", "a": "one end", "b": "other end"}


def _who(node, port):
    """A port the way a person says it: "the LED's long leg (+)", "the orange wire's other end", "the Arduino's pin 13"."""
    label = re.sub(r"\s*\(.*?\)", "", node.get("label") or node["id"]).strip()
    kind = (node.get("type") or "").split("-")[0]
    if kind in ("arduino", "esp32") or "uno" in (node.get("type") or ""):
        return f"the Arduino's {'GND' if port.upper().startswith('GND') else 'pin ' + port}"
    return f"the {label}'s {LEG.get(port, port)}"


def breadboard(lesson_id):
    """The breadboard facts for the tutor: which legs share a column (any column will do), and what can change."""
    from graph import lesson_store
    _, g = lesson_store._load(lesson_id)
    phys, rec = g.get("physical") or {"nodes": [], "edges": []}, g.get("lesson") or {}
    nodes = {n["id"]: n for n in phys["nodes"]}
    strips = {}
    for e in phys["edges"]:
        if e.get("type") != "joined":
            continue
        for a, pa, b, pb in ((e["u"], e.get("u_port"), e["v"], e.get("v_port")), (e["v"], e.get("v_port"), e["u"], e.get("u_port"))):
            m = re.match(r"(\d+)([tb])\.", str(pb or ""))
            if a in nodes and b in nodes and (nodes[b].get("type") or "").startswith("breadboard") and m:
                strips.setdefault((m.group(1), m.group(2)), []).append(_who(nodes[a], str(pa)))
    lines = [f"  - {' and '.join(sorted(set(v)))} (the lesson uses column {c} on the {'top' if h == 't' else 'bottom'} half)"
             for (c, h), v in sorted(strips.items(), key=lambda kv: int(kv[0][0])) if len(set(v)) > 1]
    sub = rec.get("substitutions") or {}
    free = []
    for pin, v in (sub.get("pins") or {}).items():
        if not isinstance(v, dict):
            continue
        never = " or ".join(v.get("refused") or {})
        free.append(f"the Arduino's pin {str(pin).split(':')[-1]} can be any of {', '.join(map(str, (v.get('stand_ins') or [])[:8]))}... "
                    f"(then the sketch must use that pin too)" + (f", but never {never}" if never else ""))
    for inst, v in (sub.get("parts") or {}).items():
        n = nodes.get(inst)
        if n:
            what = ", ".join(v.get("free") or []) or ("value" if v.get("value") else "")
            free.append(f"the {re.sub(r'[(].*?[)]', '', n.get('label') or inst).strip()}'s {what} ({v.get('why', '')})")
    return BREADBOARD.format(strips="\n".join(lines) or "  - (no breadboard in this lesson)", free="; ".join(free) or "nothing")


def brief(lesson_id, name=None, level=None):
    """The tutor's instructions: how to talk, how the session goes (hello, gather, check, build), then the lesson.
    `level` (beginner, some, advanced) sets the pace; unknown, Pip asks."""
    les = steps(lesson_id)
    arduino = les["lesson_type"] == "arduino"
    level = level if level in LEVELS else None
    ask_level = ("" if level else " Then ask how much they have built before and call remember_level with "
                 "beginner, some, or advanced.")
    flow = [FLOW_HELLO_KNOWN.format(name=name, level_q=ask_level) if name else FLOW_HELLO_NEW,
            FLOW_ARDUINO if arduino else FLOW_LEGO, FLOW_BUILD.format(n=4 if arduino else 3, lego="" if arduino else FLOW_BUILD_LEGO.format(
                visual=VISUAL_BOOKLET if les["lesson_id"].endswith("-pdf") else VISUAL_3D))]
    lines = [RULES, "", LEVELS[level] if level else "Their level: not known yet (you will ask). Until then, go at a "
             "beginner's pace.", "", "How the session goes:", *flow, "",
             f'The lesson: "{les["name"]}" ({les["lesson_type"]}), {len(les["steps"])} steps.']
    if arduino:
        from checker import gather
        rec, phys = gather.lesson(lesson_id)
        lines.append("The parts to gather: " + "; ".join(
            f'{r["count"]}x {r["name"]}' + (f' ({", ".join(sorted({str(v) for v in r["values"] if v}))})'
                                             if any(r["values"]) else "") for r in gather.needs(rec, phys)))
    if arduino:
        try:
            lines += ["", breadboard(lesson_id)]
        except Exception:  # a lesson whose data has an unexpected shape still gets a tutor
            lines += ["", BREADBOARD.split("- What must share")[0].rstrip()]
    lines.append("")
    for s in les["steps"]:
        lines.append(f'Step {s["n"]} ({s["kind"]}): {s["text"]}' if arduino else
                     f'Card {s["n"]}, {s["title"]} ({s["kind"]}): {s["text"]}')
        if s["goal"]:
            lines.append(f'  Goal: {s["goal"]}')
        if s["parts"]:
            lines.append("  Parts: " + "; ".join(f'{p["count"]}x {p["what"]}' if p["count"] > 1 else p["what"]
                                                  for p in s["parts"]))
        for h in s["hints"][:3]:
            lines.append(f"  Hint: {h}")
        if s["why"]:
            lines.append(f'  Why: {s["why"]}')
        if s.get("code"):
            lines.append("  The sketch for this step is ON THE SCREEN, with Copy and Download buttons: tell them to open "
                         "the Arduino IDE, paste it in (or open the downloaded file), choose the board (Tools > Board) and "
                         "the port (Tools > Port), and press Upload. Never say the lesson has no code. The sketch, so you "
                         "can explain any line they ask about:")
            lines.append("  " + s["code"][:6000].replace("\n", "\n  "))
            if s.get("expected"):
                lines.append(f'  What should happen: {s["expected"] if isinstance(s["expected"], str) else json.dumps(s["expected"])[:400]}')
    return "\n".join(lines)


def _gemini_key():
    k = os.environ.get("GEMINI_API_KEY")
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    return k


def session(lesson_id, resume=None, speakers=False, name=None, level=None):
    """What the browser needs to open a Live session: a single-use token (30 minutes, a new session must start
    within 1), the socket address, and the setup message with the tutor's instructions. `resume`: the handle of a
    session to carry on (sessions end after about 10-15 minutes; the page reconnects with it). `speakers`: the
    learner is not on headphones, so the start of speech must be clearer before it counts as an interruption (the
    tutor's own voice from the speakers is less likely to cut it off)."""
    key = _gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (add it to .env)")
    now = datetime.datetime.now(datetime.timezone.utc)
    iso = lambda d: (now + d).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/auth_tokens",
                                 data=json.dumps({"uses": 1, "expireTime": iso(datetime.timedelta(minutes=30)),
                                                  "newSessionExpireTime": iso(datetime.timedelta(minutes=1))}).encode(),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    token = json.loads(urllib.request.urlopen(req, timeout=30).read())["name"]
    setup = {"model": f"models/{MODEL}",
             "generationConfig": {"responseModalities": ["AUDIO"],
                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}},
             "systemInstruction": {"parts": [{"text": brief(lesson_id, name, level)}]},
             "tools": tools(steps(lesson_id)["lesson_type"]),
             "inputAudioTranscription": {}, "outputAudioTranscription": {},
             "realtimeInputConfig": {"automaticActivityDetection": {
                 "silenceDurationMs": 700, **({"startOfSpeechSensitivity": "START_SENSITIVITY_LOW"} if speakers else {})}},
             "contextWindowCompression": {"slidingWindow": {}},
             "sessionResumption": {"handle": resume} if resume else {}}
    return {"ws": WS + token, "setup": {"setup": setup}, "prices": PRICES, "cap_usd": CAP_USD, "warn_usd": WARN_USD,
            "model": MODEL}


def cost_usd(usage):
    """One turn's usageMetadata, priced (input by modality, output audio or text, thinking as text out)."""
    inp = {d.get("modality"): d.get("tokenCount", 0) for d in usage.get("promptTokensDetails") or []}
    out = {d.get("modality"): d.get("tokenCount", 0) for d in usage.get("responseTokensDetails") or []}
    return (inp.get("TEXT", 0) * PRICES["text_in"] + inp.get("AUDIO", 0) * PRICES["audio_in"]
            + out.get("AUDIO", 0) * PRICES["audio_out"] + out.get("TEXT", 0) * PRICES["text_out"]
            + usage.get("thoughtsTokenCount", 0) * PRICES["text_out"]) / 1e6


LOOK = """You are helping a learner with this lesson: {lesson}.
The parts it uses: {parts}.
The learner holds something up to the camera. Answer this question about the photo, in at most two short spoken
sentences, plainly and honestly (say if the photo does not show it clearly, and what would help): {question}"""


def look(lesson_id, photo, question):
    """Pip's look tool: one photo and one question, answered by Haiku (about 0.1 cents)."""
    from checker import gather_vlm
    st = steps(lesson_id)
    parts = sorted({p["what"] for s in st["steps"] for p in s.get("parts") or []})[:40]
    out, stats, _ = gather_vlm.ask("claude-haiku-5-5", [gather_vlm.shrink(photo, 1280, 80)],
                                   LOOK.format(lesson=st.get("name") or lesson_id, parts=", ".join(parts) or "see the lesson",
                                               question=question), max_tokens=600, effort="low")
    return {"answer": out.strip(), "cost_usd": stats.get("cost_usd")}


# ---- the free fallback: Haiku writes, the browser speaks ------------------------------------------------------------
FALLBACK = """Answer as Pip would SAY it out loud, following the rules above. You may use one tool, as the session plan
says (tools: {tools}). Reply ONLY with JSON:
{{"say": "what you say now, one to three short spoken sentences", "tool": {{"name": "<tool name>", "args": {{}}}} or null}}
A message in brackets such as "(result of check_parts: ...)" is what a tool gave back: tell the learner what it means."""


def reply(lesson_id, history, text, name=None, level=None):
    """The tutor's next words and its next tool, from Haiku (the free-voices mode). history: [{"who", "text"}]."""
    from checker import gather_vlm
    les_type = steps(lesson_id)["lesson_type"]
    names = ", ".join(f'{d["name"]}({", ".join(d.get("parameters", {}).get("properties", {}))})'
                      for d in tools(les_type)[0]["functionDeclarations"])
    convo = "\n".join(f'{h["who"].capitalize()}: {h["text"]}' for h in history[-24:])
    prompt = (brief(lesson_id, name, level) + "\n\nThe conversation so far:\n" + (convo or "(none yet: the session starts now)")
              + (f"\nLearner: {text}" if text else "") + "\n\n" + FALLBACK.format(tools=names))
    r = gather_vlm.client().messages.create(model="claude-haiku-5-5", max_tokens=700, output_config={"effort": "low"},
                                            messages=[{"role": "user", "content": prompt}])
    out = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        got = json.loads(m.group(0)) if m else {}
    except ValueError:
        got = {}
    tool = got.get("tool") if isinstance(got.get("tool"), dict) and got["tool"].get("name") in TOOL_DEFS else None
    pin, pout = gather_vlm.PRICES["claude-haiku-5-5"]
    return {"say": got.get("say") or out.strip()[:400], "tool": tool,
            "cost_usd": round((r.usage.input_tokens * pin + r.usage.output_tokens * pout) / 1e6, 6)}
