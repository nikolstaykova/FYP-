"""The voice tutor: a lesson from the store (the database when it is set up), taught step by step by voice.

The learner talks to a speech-to-speech model (Gemini Live: it hears and speaks, and stops the moment the learner
talks over it). It knows the lesson from `brief()`: every step with its words, goal, hints and parts, and the rules
for teaching it. Two tools keep the screen in step with what it says: `show_step(n)` and `finish_lesson()`.

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

RULES = """You are Pip, a warm, patient tutor who teaches a hands-on build by voice. The learner has the parts in front of
them and is building while you talk, so they cannot read long instructions: you speak them.

How you talk:
- Short, natural spoken sentences, one or two at a time, like a friend sitting next to them. No lists, no
  headings, no markdown, no ids or codes (never say "step-3", "b11", "e4" or "r1"; say "the resistor").
- One step at a time. Say what to do, then let them do it: end with a short check such as "Tell me when it's in."
- When they say they are done, or ask to go on, move to the next step. When they seem stuck, give the step's hints,
  one at a time. When they ask a question, answer it briefly, then come back to where you were.
- If they interrupt you, stop and listen; answer what they said, not what you were about to say.
- Be encouraging, never fussy. Celebrate the end.

What you know:
- Only this lesson (below). Never invent parts, colours, columns, pins or connections that are not in it. If they
  ask something the lesson does not cover, say so honestly and give general, safe advice.
- Every step's parts are listed with it: use their names, colours and values ("the red LED", "the 220 ohm
  resistor", "two black 2 by 4 plates").

The screen:
- Before you start talking about a step, call show_step with its number, so the learner sees it.
- When the last step is done, call finish_lesson, then say a short well done.

Start by greeting them in one sentence, saying what they will build, and asking if they are ready."""

TOOLS = [{"functionDeclarations": [
    {"name": "show_step", "description": "Show a step of the lesson on the learner's screen. Call it before you talk "
                                         "about that step.",
     "parameters": {"type": "OBJECT", "properties": {"n": {"type": "INTEGER", "description": "the step number, from 1"}},
                    "required": ["n"]}},
    {"name": "finish_lesson", "description": "The learner has finished the last step.",
     "parameters": {"type": "OBJECT", "properties": {}}},
]}]


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


def brief(lesson_id):
    """The tutor's instructions: how to teach, then the whole lesson, step by step."""
    les = steps(lesson_id)
    lines = [RULES, "", f'The lesson: "{les["name"]}" ({les["lesson_type"]}), {len(les["steps"])} steps.', ""]
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


def session(lesson_id, resume=None, speakers=False):
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
             "systemInstruction": {"parts": [{"text": brief(lesson_id)}]},
             "tools": TOOLS,
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
FALLBACK = """Answer as Pip would SAY it out loud, following the rules above. Reply ONLY with JSON:
{"say": "what you say, one to three short spoken sentences", "show_step": <the step number to show, or null>,
 "finished": <true when the learner has finished the last step>}"""


def reply(lesson_id, history, text, step=None):
    """The tutor's next words, from Haiku (the free-voices mode). history: [{"who": "learner"|"tutor", "text"}]."""
    from checker import gather_vlm
    convo = "\n".join(f'{h["who"].capitalize()}: {h["text"]}' for h in history[-20:])
    prompt = (brief(lesson_id) + "\n\n" + (f"The screen shows step {step}.\n" if step else "")
              + "The conversation so far:\n" + (convo or "(none yet)") + f"\nLearner: {text or '(the lesson starts)'}\n\n"
              + FALLBACK)
    r = gather_vlm.client().messages.create(model="claude-haiku-5-5", max_tokens=600, output_config={"effort": "low"},
                                            messages=[{"role": "user", "content": prompt}])
    out = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        got = json.loads(m.group(0)) if m else {}
    except ValueError:
        got = {}
    pin, pout = gather_vlm.PRICES["claude-haiku-5-5"]
    return {"say": got.get("say") or out.strip()[:400], "show_step": got.get("show_step"),
            "finished": bool(got.get("finished")),
            "cost_usd": round((r.usage.input_tokens * pin + r.usage.output_tokens * pout) / 1e6, 6)}
