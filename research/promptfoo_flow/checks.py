"""promptfoo assertions on provider.py's summary of one whole flow.

clear       pass only if the lesson came out right by the repeat test's rules (a page with no circuit refused counts
            as right); score 1 or 0
one_model   every Claude call of the flow reported the provider's model (always passes; the reason lists them), so a
            result cannot come from a call that quietly used another model
"""
import json


def _s(output):
    return json.loads(output) if isinstance(output, str) else output


def clear(output, context):
    s = _s(output)
    return {"pass": bool(s.get("clear")), "score": 1.0 if s.get("clear") else 0.0,
            "reason": f"{s['route']} {s['case']}: {'clear' if s.get('clear') else 'NOT clear'} - {s.get('note', '')}"
                      f" ({s.get('wall_seconds')} s, ${s.get('cost_usd')})"}


def one_model(output, context):
    s = _s(output)
    want = {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku"}.get(s["model"], s["model"])
    used = s.get("models_used") or []
    only = bool(used) and all(want in m for m in used)
    return {"pass": True, "score": 1.0 if only else 0.0,
            "reason": ("one model: " if only else "MIXED or none recorded: ") + ", ".join(used)}
