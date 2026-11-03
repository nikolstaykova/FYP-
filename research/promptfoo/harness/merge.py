"""Merge promptfoo evals run on the same tests into one, so every prompt and model sits side by side in the viewer.

  python merge.py <out.json> "<description>" <results.json> [<results.json> ...]
  then: promptfoo import --new-id <out.json>

Each input's columns (prompt x provider) keep their rows; columns are ordered by ORDER (v8 then v10 for each model,
opus, sonnet, haiku), any other label after them. The tests must be the same in every input (checked).
"""
import json
import sys
import time
import uuid

ORDER = ["v8-opus", "v10-opus", "v8-sonnet", "v10-sonnet", "v8-haiku", "v10-haiku"]

out_path, description, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
evals = [json.load(open(p)) for p in paths]
tests = [[t["vars"] for t in e["config"]["tests"]] for e in evals]
assert all(t == tests[0] for t in tests), "the evals do not run the same tests"

cols = []  # (label, prompt entry, provider config, rows)
for e in evals:
    r = e["results"]
    for i, p in enumerate(r["prompts"]):
        rows = [x for x in r["results"] if x["promptIdx"] == i]
        prov = next(c for c in e["config"]["providers"] if c.get("label") == p["provider"])
        cols.append((p["provider"], p, prov, rows))
labels = [c[0] for c in cols]
assert len(set(labels)) == len(labels), f"a column appears twice: {labels}"
cols.sort(key=lambda c: (ORDER.index(c[0]) if c[0] in ORDER else len(ORDER), c[0]))

base = evals[0]
results, prompts, providers = [], [], []
for k, (label, p, prov, rows) in enumerate(cols):
    prompts.append(p)
    providers.append(prov)
    for x in rows:
        results.append({**x, "promptIdx": k, "id": str(uuid.uuid4())})
stats = dict(base["results"]["stats"])
stats.update({"successes": sum(1 for x in results if x.get("success")),
              "failures": sum(1 for x in results if not x.get("success") and not x.get("error")),
              "errors": sum(1 for x in results if x.get("error")),
              "durationMs": sum(e["results"]["stats"].get("durationMs", 0) for e in evals)})
merged = {**base, "evalId": f"eval-merged-{time.strftime('%Y-%m-%dT%H:%M:%S')}",
          "config": {**base["config"], "description": description, "providers": providers},
          "results": {**base["results"], "prompts": prompts, "results": results, "stats": stats,
                      "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}}
json.dump(merged, open(out_path, "w"), indent=1)
print(f"{out_path}: {len(prompts)} columns {[c[0] for c in cols]}, {len(results)} rows, "
      f"{stats['successes']} passed, {stats['failures']} failed, {stats['errors']} errors")
