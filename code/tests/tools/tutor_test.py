"""Can an agent with the lesson data (tutor_mcp.py) lead a learner through a lesson and answer free-text questions?

Each case is one learner message to a fresh Claude session that sees the data only through the tools. Code grades
the answer: every `must` group needs one of its phrases in the answer (case-insensitive), no `must_not` phrase may
appear, and each of the `tools` it should have used (a name, or a list of names any of which will do) must be among
the tools it called. Time and cost per case are kept.

  .venv-research/bin/python -m graph.tutor_test [--model sonnet]
Writes tests/experiments/tutor_test/results.json.
"""

import sys as _sys  # run as a script: the product (code/) and the research versions are importable
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[2]), str(_Path(__file__).resolve().parents[1] / "research"),
                 str(_Path(__file__).resolve().parents[1] / "tools")]
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "tests" / "experiments" / "tutor_test"
NEW = "docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver"

SYSTEM = """You are a patient tutor for hands-on build lessons (Arduino circuits, LEGO sets). The learner is building
right now. Answer from the lesson data, which you can read only through your tools: look facts up, do not guess
pins, columns, parts or values. Keep answers short and practical, in plain words, and say exactly where things go
(pin numbers, breadboard columns). When the learner tells you what they have wired, check it with the progress tool
before you answer. If the data does not say something, say so."""

CASES = [
    {"id": "lead-start", "lesson": "blink", "ask": "I'm starting the Blink lesson. What do I need, and what is the very first thing I build?",
     "must": [["resistor"], ["led"], ["column 10", "10t"], ["column 14", "14t"]], "tools": ["lesson"]},
    {"id": "lead-next", "lesson": "blink", "ask": "In Blink I've put the resistor in. What's the next step, exactly?",
     "must": [["long leg", "anode"], ["14"], ["15"]], "tools": [["step", "lesson"]]},  # both hold the step text
    {"id": "progress-moved", "lesson": "blink",
     "ask": "Blink: I put the resistor in columns 12 and 16 instead (r1:1 -> bb1:12t.a, r1:2 -> bb1:16t.a), then the orange "
            "wire from pin 13 into column 10 (wire1:a -> uno:13, wire1:b -> bb1:10t.e). Is that OK?",
     "must": [["12"], ["wrong", "move", "not in", "must go", "should go", "needs to"]], "must_not": [["that's correct", "all good"]],
     "tools": ["progress"]},
    {"id": "pin-swap-ok", "lesson": "blink", "ask": "Blink: can I use pin 7 instead of pin 13 for the LED? What else changes?",
     "must": [["yes", "can"], ["code", "sketch", "led_builtin"]], "tools": ["substitutions"]},
    {"id": "pin-swap-pwm", "lesson": "fade", "ask": "Fade: can I wire the LED to pin 8 instead of 9?",
     "must": [["no", "can't", "cannot", "won't"], ["pwm", "~"], ["3", "5", "6", "10", "11"]], "tools": ["substitutions"]},
    {"id": "why-resistor", "lesson": "blink", "ask": "Why do I even need the resistor in Blink?",
     "must": [["current"], ["led"]], "tools": []},
    {"id": "resistor-orientation", "lesson": "blink", "ask": "Does it matter which way round the resistor goes?",
     "must": [["no", "doesn't", "does not", "either way"]], "must_not": [["yes, it matters"]], "tools": []},
    {"id": "led-dark", "lesson": "blink", "ask": "My Blink LED never lights up. What should I check first?",
     "must": [["wrong way", "backwards", "long leg", "swap"]], "tools": []},
    {"id": "servo-swap", "lesson": None, "ask": "What happens if I plug a servo's power and ground the wrong way round?",
     "must": [["damage", "destroy", "break", "fry"]], "tools": ["part"]},
    {"id": "lego-first", "lesson": "4017-1", "ask": "I'm building the LEGO Sea Helicopter. What do I do in the first step?",
     "must": [["plate"], ["1 x 8", "1x8", "2 x 4", "2x4"]], "tools": ["lesson"]},
    {"id": "lego-propeller", "lesson": "4017-1", "ask": "Sea Helicopter: when does the propeller go on, and what does it sit on?",
     "must": [["propeller"], ["tile", "pin", "2460", "b12"]], "tools": [["lesson", "step", "instance"]]},
    {"id": "lego-colour", "lesson": "4017-1", "ask": "Sea Helicopter: I don't have a trans-neon-green 2x2 slope, only a red one. Can I use it?",
     "must": [["yes", "can"], ["colour", "color"]], "tools": [["part", "substitutions", "lesson", "instance"]]},
    {"id": "new-lesson-parts", "lesson": NEW, "ask": "For the Uno WiFi Rev2 web server lesson, which parts do I need?",
     "must": [["uno wifi rev2", "wifi rev2"], ["breadboard"], ["led"], ["220"], ["wire"]], "tools": ["lesson"]},
]


def run(case, model, effort):
    cfg = {"mcpServers": {"lessons": {"command": sys.executable, "args": ["-m", "graph.tutor_mcp"],
                                      "env": {"PYTHONPATH": str(ROOT)}, "cwd": str(ROOT)}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(json.dumps(cfg))
        mcp = f.name
    ask = case["ask"] + (f"\n(lesson id: {case['lesson']})" if case["lesson"] else "")
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                                                            "CLAUDE_CODE_CHILD_SESSION")}
    cmd = ["claude", "-p", ask, "--output-format", "stream-json", "--verbose", "--model", model, "--effort", effort,
           "--no-session-persistence", "--tools", "", "--mcp-config", mcp, "--strict-mcp-config",
           "--allowedTools", "mcp__lessons__*", "--system-prompt", SYSTEM]
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600, cwd=str(ROOT))
    os.unlink(mcp)
    tools, answer, cost = [], "", None
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "tool_use":
                    tools.append(c["name"].split("__")[-1])
        if ev.get("type") == "result":
            answer, cost = ev.get("result") or "", ev.get("total_cost_usd")
    low = answer.lower()
    missing = [g for g in case["must"] if not any(p.lower() in low for p in g)]
    bad = [p for g in case.get("must_not", []) for p in g if p.lower() in low]
    tools_missing = [t for t in case["tools"] if not any(x in tools for x in ([t] if isinstance(t, str) else t))]
    return {"id": case["id"], "ask": case["ask"], "answer": answer, "tools_used": tools,
            "pass": not missing and not bad and not tools_missing, "missing": missing, "said_wrongly": bad,
            "tools_missing": tools_missing, "seconds": round(time.monotonic() - t0, 1), "cost_usd": cost,
            "error": None if answer else (proc.stderr[-300:] or "no answer")}


# Conversations: one session, the learner moves through the lesson, then asks things that are not about the current
# step. Each turn is graded like a case.
CONVERSATIONS = [
    {"id": "blink-step4-indirect", "lesson": "blink", "turns": [
        {"say": "Lead me through the Blink lesson (lesson id: blink), one step at a time. Start.", "must": [["collect", "gather", "need"]]},
        {"say": "Done. Next.", "must": [["resistor"]]},
        {"say": "Done. Next.", "must": [["led"]]},
        {"say": "Done. Next.", "must": [["orange", "pin 13"]]},
        {"say": "Done. Next.", "must": [["black", "gnd"]]},
        {"say": "Hold on, before I do this one: what is this whole lesson actually about?",
         "must": [["blink"], ["led"], ["13", "pin"]]},
        {"say": "And list every part in the lesson, with how many of each.",
         "must": [["uno", "arduino"], ["breadboard"], ["220", "resistor"], ["led"], ["2", "two"], ["wire"]]},
        {"say": "Which step put the resistor in, and where do both ends of the black wire go?",
         "must": [["step 1", "step-1", "first build step"], ["gnd"], ["15"]]},
        {"say": "Which things end up electrically connected to pin 13?",
         "must": [["resistor", "r1"]], "must_not": [["led1:c", "ground"]]},
        {"say": "What did I do two steps ago?", "must": [["led"]]},
    ]},
    {"id": "lego-step3-indirect", "lesson": "4017-1", "turns": [
        {"say": "Take me through the LEGO Sea Helicopter (lesson id: 4017-1). What's step 1?", "must": [["1x8", "1 x 8"]]},
        {"say": "Done. Next.", "must": [["underside", "over", "under"]]},
        {"say": "Done. Next.", "must": [["2x2", "2 x 2"]]},
        {"say": "What is this set, and how many pieces does it have altogether?", "must": [["sea helicopter", "helicopter"], ["13"]]},
        {"say": "Which pieces haven't I used yet?", "must": [["propeller"], ["tile", "pin"]]},
    ]},
]


def converse(conv, model, effort):
    """One session, turn after turn (stream-json in and out)."""
    cfg = {"mcpServers": {"lessons": {"command": sys.executable, "args": ["-m", "graph.tutor_mcp"],
                                      "env": {"PYTHONPATH": str(ROOT)}, "cwd": str(ROOT)}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(json.dumps(cfg))
        mcp = f.name
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                                                            "CLAUDE_CODE_CHILD_SESSION")}
    proc = subprocess.Popen(["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                             "--model", model, "--effort", effort, "--no-session-persistence", "--tools", "",
                             "--mcp-config", mcp, "--strict-mcp-config", "--allowedTools", "mcp__lessons__*",
                             "--system-prompt", SYSTEM], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env, cwd=str(ROOT), bufsize=1)
    out, prev_cost = [], 0.0
    for k, turn in enumerate(conv["turns"], 1):
        t0 = time.monotonic()
        proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": turn["say"]}}) + "\n")
        proc.stdin.flush()
        tools, answer, cost = [], "", None
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "assistant":
                tools += [c["name"].split("__")[-1] for c in ev["message"].get("content", []) if c.get("type") == "tool_use"]
            if ev.get("type") == "result":
                answer, cost = ev.get("result") or "", ev.get("total_cost_usd") or 0.0
                break
        low = answer.lower()
        missing = [g for g in turn["must"] if not any(p.lower() in low for p in g)]
        bad = [p for g in turn.get("must_not", []) for p in g if p.lower() in low]
        out.append({"conversation": conv["id"], "turn": k, "say": turn["say"], "answer": answer, "tools_used": tools,
                    "pass": not missing and not bad, "missing": missing, "said_wrongly": bad,
                    "seconds": round(time.monotonic() - t0, 1), "cost_usd": round(cost - prev_cost, 4)})
        prev_cost = cost
    proc.stdin.close()
    proc.wait(timeout=60)
    os.unlink(mcp)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--only", nargs="*", help="case ids to run")
    ap.add_argument("--conversations", action="store_true", help="run the multi-turn conversations instead")
    a = ap.parse_args(argv)
    if a.conversations:
        OUT.mkdir(parents=True, exist_ok=True)
        with cf.ThreadPoolExecutor(2) as pool:
            turns = [t for c in pool.map(lambda c: converse(c, a.model, a.effort), CONVERSATIONS) for t in c]
        (OUT / "conversations.json").write_text(json.dumps(turns, indent=1))
        for t in turns:
            print(f"{'PASS' if t['pass'] else 'FAIL'} {t['conversation']:22} turn {t['turn']:2} {t['seconds']:5}s  "
                  f"tools: {', '.join(t['tools_used']) or '-'}  | {t['say'][:60]}"
                  + (f"  missing {t['missing']}" if t["missing"] else "") + (f"  said {t['said_wrongly']}" if t["said_wrongly"] else ""))
        print(f"{sum(t['pass'] for t in turns)}/{len(turns)} turns passed; {sum(t['seconds'] for t in turns):.0f}s, "
              f"${sum(t['cost_usd'] for t in turns):.3f}")
        return
    cases = [c for c in CASES if not a.only or c["id"] in a.only]
    OUT.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda c: run(c, a.model, a.effort), cases))
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    for r in results:
        print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']:22} {r['seconds']:6}s ${r['cost_usd']}  tools: {', '.join(r['tools_used'])}"
              + (f"  missing {r['missing']}" if r["missing"] else "") + (f"  said {r['said_wrongly']}" if r["said_wrongly"] else "")
              + (f"  no {r['tools_missing']}" if r["tools_missing"] else "") + (f"  ERROR {r['error']}" if r["error"] else ""))
    n = sum(r["pass"] for r in results)
    print(f"{n}/{len(results)} passed; {sum(r['seconds'] for r in results):.0f}s total, "
          f"${sum(r['cost_usd'] or 0 for r in results):.3f}")


if __name__ == "__main__":
    main()
