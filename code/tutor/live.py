"""The voice tutor: a lesson from the store (the database when it is set up), taught step by step by voice.

The learner talks to a speech-to-speech model (Gemini Live: it hears and speaks, and stops the moment the learner
talks over it). It knows the lesson from `brief()`: the session plan (hello and the learner's name, gather the
parts, the parts check with photos and close-ups, then the steps), every step with its words, goal, hints and parts,
and the rules for talking. Its tools (`tools()`) drive the screen and the parts check: remember_name,
show_parts_list, open_camera, take_photo, check_parts and take_closeup (non-blocking: it can keep talking while the
check runs), skip_question, start_building, show_step, finish_lesson. LEGO lessons have no parts check.

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

RULES = """You are Pip, a warm, patient tutor who teaches a hands-on build by voice, like a friend sitting next to the
learner. They have their hands full, so you speak everything; the screen only shows what you are talking about.

How you talk:
- Always speak English, unless the learner speaks to you in another language; then answer in theirs.
- Short, natural spoken sentences, one or two at a time. No lists, no headings, no markdown, no ids or codes (never
  say "step-3", "b11", "r1" or a question key; say "the resistor").
- Use their name now and then, not in every sentence.
- One thing at a time, then let them do it: end with a short check such as "Tell me when it's in."
- If they interrupt you, stop and listen; answer what they said, not what you were about to say.
- When they ask a question, answer briefly, then come back to where you were.
- Be encouraging, never fussy. Celebrate the end.
- Tool results come back as JSON: never read JSON aloud; say what it means.

What you know: only this lesson (below). Never invent parts, colours, columns, pins or connections that are not in
it. If they ask something the lesson does not cover, say so honestly and give general, safe advice."""

FLOW_HELLO_NEW = """1. Hello. Introduce yourself in one sentence ("Hi, I'm Pip, I'll be your tutor today") and ask their name.
   Then wait for their answer: call no tool and start nothing else until they have told you. When they tell you,
   call remember_name with exactly the name they said (never guess one), then greet them by name."""
FLOW_HELLO_KNOWN = """1. Hello. Greet {name} by name, warmly, in one sentence (you have met before)."""

FLOW_ARDUINO = """2. Gather. In one go: say in one sentence what they will build, call show_parts_list, and name every part to
   put on the table, naturally and grouped ("an Arduino Uno, a breadboard, a red LED, a 220 ohm resistor and two
   jumper wires"). Then ask them to tell you when everything is on the table, and wait.
3. Check. When they are ready, call open_camera (always before the first photo) and ask them to spread the parts out on a plain surface in view of
   the camera, and to tell you when to take the picture. When they say so ("take it", "ready", "now"), call
   take_photo. With many small parts, offer one more photo from another angle (at most 3). Then say "let me have a
   look" and call check_parts.
   The result says, part by part, what they have, what can be used instead (and why), what you are not sure of, and
   what is missing, and it may have questions. Tell them like a person would: first what is good, then what can
   stand in (with the reason, briefly), then each question in your own words with their name ("Mark, I can see the
   resistors, but I can't read their colour bands. Can you hold one up close to the camera?"). Then stop and wait:
   never take the close-up in the same breath as asking for it. Only when they say they are holding it up (or say
   "take it", "ready"), call take_closeup with that question's key: it takes the photo, checks it and gives you the
   new result. If they say they don't have a part, call skip_question with its key, and tell them what they can do
   instead (find one, or what could stand in).
   When everything is settled, say well done and ask if they are ready to start building; call start_building
   when they say yes (or right away if they ask to carry on anyway)."""
FLOW_LEGO = """2. Gather. They have the set, so there is no parts check. Say in one sentence what they will build, and that
   for every step you will tell them which pieces to find first. Then call start_building."""
FLOW_BUILD = """{n}. Build. Before you talk about a step, call show_step with its number. For each step, first say which parts
   to pick up (from the step's parts), then what to do with them. When they say they are done, go on to the next
   step. When they seem stuck, give the step's hints, one at a time. After the last step, call finish_lesson and
   celebrate."""

TOOL_DEFS = {
    "remember_name": {"description": "Remember the learner's name for this and later lessons.",
                      "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}}, "required": ["name"]}},
    "show_parts_list": {"description": "Show the lesson's parts list on the screen as a checklist.",
                        "parameters": {"type": "OBJECT", "properties": {}}},
    "open_camera": {"description": "Open the camera on the screen so the learner can show their parts.",
                    "parameters": {"type": "OBJECT", "properties": {}}},
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
    "skip_question": {"description": "The learner does not have that part, or wants to skip the question. Returns the "
                                     "new result.",
                      "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}}, "required": ["key"]}},
    "start_building": {"description": "Go to the building steps on the screen (step 1).",
                       "parameters": {"type": "OBJECT", "properties": {}}},
    "show_step": {"description": "Show a step of the lesson on the screen. Call it before you talk about that step.",
                  "parameters": {"type": "OBJECT", "properties": {"n": {"type": "INTEGER", "description": "the step number, from 1"}},
                                 "required": ["n"]}},
    "finish_lesson": {"description": "The learner has finished the last step.", "parameters": {"type": "OBJECT", "properties": {}}},
}
CHECK_TOOLS = ("show_parts_list", "open_camera", "take_photo", "check_parts", "take_closeup", "skip_question")


def tools(lesson_type):
    """The tools for this lesson: the parts check only for electronics (a LEGO learner has the set)."""
    names = [t for t in TOOL_DEFS if lesson_type == "arduino" or t not in CHECK_TOOLS]
    return [{"functionDeclarations": [{"name": n, **TOOL_DEFS[n]} for n in names]}]


def _part_words(p):
    props = p.get("props") or {}
    bits = [str(props.get(k)) for k in ("colour", "value") if props.get(k)]
    return " ".join(bits + [p.get("name") or p.get("type") or "part"]) + (f" ({p['where']})" if p.get("where") else "")


def steps(lesson_id):
    """The lesson's steps as the learner sees them and the tutor teaches them, in order, numbered from 1."""
    from graph import lesson_store
    view = lesson_store.assemble(lesson_id)
    out = []
    for s in view["steps"]:
        if s.get("kind") == "overview":
            continue
        counted = {}
        for p in s.get("parts") or []:
            w = _part_words({k: v for k, v in p.items() if k != "where"})
            counted[w] = counted.get(w, 0) + 1
        picture = ((s.get("source") or {}).get("picture") or "")
        out.append({"n": len(out) + 1, "id": s["id"], "kind": s.get("kind"),
                    "title": {"gather": "Gather the parts", "upload": "Upload the code"}.get(s.get("kind"))
                    or f"Step {len(out) + 1}",
                    "text": s.get("text") or "", "goal": s.get("goal"), "hints": s.get("hints") or [],
                    "why": s.get("why"), "what_changed": s.get("what_changed"),
                    "parts": [{"what": w, "count": c} for w, c in counted.items()],
                    "picture": picture if picture.startswith("data/lessons/booklet/") else None})
    return {"lesson_id": lesson_id, "name": (view.get("lesson") or {}).get("name") or view.get("title") or lesson_id,
            "lesson_type": view.get("lesson_type"), "steps": out}


def brief(lesson_id, name=None):
    """The tutor's instructions: how to talk, how the session goes (hello, gather, check, build), then the lesson."""
    les = steps(lesson_id)
    arduino = les["lesson_type"] == "arduino"
    flow = [FLOW_HELLO_KNOWN.format(name=name) if name else FLOW_HELLO_NEW,
            FLOW_ARDUINO if arduino else FLOW_LEGO, FLOW_BUILD.format(n=4 if arduino else 3)]
    lines = [RULES, "", "How the session goes:", *flow, "",
             f'The lesson: "{les["name"]}" ({les["lesson_type"]}), {len(les["steps"])} steps.']
    if arduino:
        from checker import gather
        rec, phys = gather.lesson(lesson_id)
        lines.append("The parts to gather: " + "; ".join(
            f'{r["count"]}x {r["name"]}' + (f' ({", ".join(sorted({str(v) for v in r["values"] if v}))})'
                                             if any(r["values"]) else "") for r in gather.needs(rec, phys)))
    lines.append("")
    for s in les["steps"]:
        lines.append(f'Step {s["n"]} ({s["kind"]}): {s["text"]}')
        if s["goal"]:
            lines.append(f'  Goal: {s["goal"]}')
        if s["parts"]:
            lines.append("  Parts: " + "; ".join(f'{p["count"]}x {p["what"]}' if p["count"] > 1 else p["what"]
                                                  for p in s["parts"]))
        for h in s["hints"][:3]:
            lines.append(f"  Hint: {h}")
        if s["why"]:
            lines.append(f'  Why: {s["why"]}')
    return "\n".join(lines)


def _gemini_key():
    k = os.environ.get("GEMINI_API_KEY")
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    return k


def session(lesson_id, resume=None, speakers=False, name=None):
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
             "systemInstruction": {"parts": [{"text": brief(lesson_id, name)}]},
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


# ---- the free fallback: Haiku writes, the browser speaks ------------------------------------------------------------
FALLBACK = """Answer as Pip would SAY it out loud, following the rules above. You may use one tool, as the session plan
says (tools: {tools}). Reply ONLY with JSON:
{{"say": "what you say now, one to three short spoken sentences", "tool": {{"name": "<tool name>", "args": {{}}}} or null}}
A message in brackets such as "(result of check_parts: ...)" is what a tool gave back: tell the learner what it means."""


def reply(lesson_id, history, text, name=None):
    """The tutor's next words and its next tool, from Haiku (the free-voices mode). history: [{"who", "text"}]."""
    from checker import gather_vlm
    les_type = steps(lesson_id)["lesson_type"]
    names = ", ".join(f'{d["name"]}({", ".join(d.get("parameters", {}).get("properties", {}))})'
                      for d in tools(les_type)[0]["functionDeclarations"])
    convo = "\n".join(f'{h["who"].capitalize()}: {h["text"]}' for h in history[-24:])
    prompt = (brief(lesson_id, name) + "\n\nThe conversation so far:\n" + (convo or "(none yet: the session starts now)")
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
