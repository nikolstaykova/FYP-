"""Check the whole-flow provider before a full eval: one case per route on one model, side by side.
  python smoke.py <model>   -> prints each route's summary, its clear verdict and the models its calls used
"""
import concurrent.futures
import json
import sys

import checks
import provider

CASES = [("booklet", "7603-1"), ("lego3d", "7603-1"), ("arduino", "https://docs.arduino.cc/tutorials/generic/knight-rider/")]
model = sys.argv[1] if len(sys.argv) > 1 else "haiku"


def one(rc):
    route, case = rc
    r = provider.call_api("", {"config": {"model": model}}, {"vars": {"route": route, "case": case}})
    return route, r


with concurrent.futures.ThreadPoolExecutor(3) as ex:
    for route, r in ex.map(one, CASES):
        s = json.loads(r["output"])
        print(route, json.dumps({k: s.get(k) for k in ("clear", "rc", "issues", "note", "cost_usd", "wall_seconds", "dir")}))
        print("  ", checks.clear(r["output"], {})["reason"][:200])
        print("  ", checks.one_model(r["output"], {})["reason"])
