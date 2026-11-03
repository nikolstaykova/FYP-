"""promptfoo assertions on provider.py's summary, scored by the product's own checks (S1-S14, W3).

final_clean  pass only if the finished lesson has no issues (what the product needs); score 1 / (1 + issues)
first_shot   the planning prompt's first answer, before any repair: always passes, score 1 / (1 + issues), so the
             prompt itself can be compared across models (named score 'first_shot')
"""
import collections
import json


def _summary(output):
    return json.loads(output) if isinstance(output, str) else output


def final_clean(output, context):
    s = _summary(output)
    n = len(s["issues_final"])
    rules = dict(collections.Counter(r for r, _ in s["issues_final"]))
    return {"pass": n == 0, "score": 1 / (1 + n),
            "reason": "no issues" if not n else f"{n} issues {rules}: " + "; ".join(
                f"{r}: {m[:120]}" for r, m in s["issues_final"][:3])}


def first_shot(output, context):
    s = _summary(output)
    n = s["issues_first"]
    return {"pass": True, "score": 1 / (1 + n),
            "reason": f"first answer: {n} issues; {s['repairs']} repairs; {s['steps']} steps; "
                      f"{s['seconds']} s; ${s['cost_usd']}"}
