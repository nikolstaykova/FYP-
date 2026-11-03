"""promptfoo provider: a 3D LEGO lesson for the test's `set`, made by the product's whole flow (run_one.py) with the
model and effort from this provider's config. Each call is its own process with its own output folder
(runs/<model>-<effort>/<set>/<time>-<id>/), so calls can run side by side. The output is a JSON summary that
checks.py scores with the product's own checks (issues_first: the prompt's first answer; issues_final: the lesson).
"""
import json
import pathlib
import subprocess
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
PY = HERE.parents[2] / ".venv-research" / "bin" / "python"


def call_api(prompt, options, context):
    cfg = options.get("config") or {}
    s = context["vars"]["set"]
    model, effort = cfg.get("model", "opus"), cfg.get("effort", "high")
    out = HERE / "runs" / f"{model}-{effort}" / s / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    out.mkdir(parents=True)
    t0 = time.monotonic()
    # caffeinate: the Mac must not sleep in the middle of a call (it broke a run before)
    proc = subprocess.run(["caffeinate", "-ims", str(PY), str(HERE / "run_one.py"), s, model, effort, str(out)],
                          capture_output=True, text=True, timeout=cfg.get("timeout_s", 5400))
    (out / "log.txt").write_text(proc.stdout + "\n--- stderr\n" + proc.stderr)
    line = next((l for l in reversed(proc.stdout.splitlines()) if l.startswith("STATS ")), None)
    if proc.returncode or not line:
        return {"error": f"{s} with {model}: exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"}
    st = json.loads(line[6:])
    summary = {"set": s, "model": model, "effort": effort, "issues_first": st["issues_first"],
               "issues_final": st["issues_final"], "steps": st["steps"], "repairs": st["repairs"],
               "seconds": st["seconds"], "wall_seconds": round(time.monotonic() - t0, 1), "cost_usd": st["cost_usd"],
               "dir": str(out.relative_to(HERE))}
    calls = [p for p in st["phases"] if "input_tokens" in p]  # every Claude turn (plan, repairs, reword, bags)
    tokens = {"prompt": sum(p["input_tokens"] + p.get("cache_read_tokens", 0) for p in calls),
              "completion": sum(p.get("output_tokens", 0) for p in calls), "cached": sum(p.get("cache_read_tokens", 0) for p in calls)}
    tokens["total"] = tokens["prompt"] + tokens["completion"]
    return {"output": json.dumps(summary), "cost": st["cost_usd"], "tokenUsage": tokens}
