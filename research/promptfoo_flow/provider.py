"""promptfoo provider: one lesson through its route's whole flow (run_flow.sh) with every Claude call on the
provider's model, then judged as the repeat test judges it (tests/experiments/repeat_20261028/summary.py):
  booklet  exit 0, the last READY line is READY, and <set>-pdf valid in the store
  lego3d   no plan issues (stats.json), store build with 0 problems, valid in the store
  arduino  no issues, sketch compiles, store build with 0 problems, valid in the store; a page with no circuit is
           refused by design (that is the right answer)
Each call has its own folder runs/<model>/<route>-<case>/<time>-<id>/ (lessons, a private copy of the store, logs),
so calls can run side by side and the real lessons and store are never touched. The output is a JSON summary;
checks.py scores it.
"""
import glob
import json
import pathlib
import re
import subprocess
import sys
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "code")]


def _load(p):
    try:
        return json.loads(pathlib.Path(p).read_text())
    except (OSError, ValueError):
        return None


def _models(d):
    """Every model the flow's Claude calls report (stats phases, booklet reads): to show the flow used one model."""
    found = set()
    for f in glob.glob(str(d / "lessons" / "**" / "*.json"), recursive=True):
        text = pathlib.Path(f).read_text(errors="replace")
        found |= set(re.findall(r'"model": "(claude-[a-z0-9-]+)"', text))
    return sorted(found)


def judge(route, case, d):
    from graph.arduino.circuit_lesson import slug
    log = (d / "flow.log").read_text(errors="replace") if (d / "flow.log").exists() else ""
    rc = int((d / "rc").read_text().strip()) if (d / "rc").exists() else -1
    invalid = {}
    for line in ((d / "validate.txt").read_text(errors="replace") if (d / "validate.txt").exists() else "").splitlines():
        m = re.match(r"  (\S+): (L\d.*)", line)
        if m:
            invalid[m.group(1)] = m.group(2)[:150]
    store = re.findall(r"- problems: (\d+)", log)
    out = {"route": route, "case": case, "rc": rc, "issues": None, "note": ""}
    if route == "booklet":
        ready = [l.strip() for l in log.splitlines() if re.search(r"^\s*(NOT )?READY\b", l)]
        lid = f"{case}-pdf"
        out["clear"] = rc == 0 and bool(ready) and not ready[-1].startswith("NOT") and lid not in invalid
        out["note"] = (ready[-1] if ready else "no READY line (failed)") + (f" | store: {invalid[lid]}" if lid in invalid else "")
        cost = re.findall(r"^\S+: \d+ steps in \d+s, \$([\d.]+)", log, re.M)
        out["cost_usd"] = float(cost[-1]) if cost else 0.0
        secs = re.findall(r"^\S+: \d+ steps in (\d+)s", log, re.M)
        out["seconds"] = float(secs[-1]) if secs else None
        return out
    lid = case if route == "lego3d" else slug(case)
    if route == "arduino" and "no circuit to build" in log:
        out.update(clear=True, refused=True, note="refused: the page has no circuit (by design)", cost_usd=0.0)
        st = _load(d / "lessons" / lid / "stats.json")
        out["cost_usd"] = (st or {}).get("cost_usd", 0.0)
        return out
    st = _load(d / "lessons" / lid / "stats.json")
    issues = st["issues_final"] if st and rc == 0 else None
    comp = ((st or {}).get("compile") or {}).get("result")
    ok = issues == [] and bool(store) and store[-1] == "0" and lid not in invalid and comp != "error"
    out.update(clear=ok, issues=None if issues is None else len(issues), cost_usd=(st or {}).get("cost_usd", 0.0),
               seconds=(st or {}).get("seconds"), issues_first=(st or {}).get("issues_first"),
               repairs=(st or {}).get("repairs"), compile=comp,
               note=("failed (see flow.log)" if issues is None else "; ".join(f"{r}: {m[:90]}" for r, m in issues[:3]))
               + (f" | store problems {store[-1]}" if store and store[-1] != "0" else "")
               + (f" | compile {comp}" if comp == "error" else "") + (f" | store: {invalid[lid]}" if lid in invalid else ""))
    return out


def call_api(prompt, options, context):
    cfg = options.get("config") or {}
    route, case = context["vars"]["route"], context["vars"]["case"]
    model = cfg.get("model", "opus")
    name = re.sub(r"[^a-z0-9]+", "-", case.lower().rstrip("/").rsplit("/", 1)[-1])
    d = HERE / "runs" / model / f"{route}-{name}" / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True)
    t0 = time.monotonic()
    subprocess.run(["caffeinate", "-ims", str(HERE / "run_flow.sh"), route, case, model, str(d)],
                   capture_output=True, text=True, timeout=cfg.get("timeout_s", 7200))
    res = judge(route, case, d)
    res.update(model=model, wall_seconds=round(time.monotonic() - t0, 1), models_used=_models(d),
               dir=str(d.relative_to(HERE)))
    return {"output": json.dumps(res), "cost": res.get("cost_usd") or 0.0}
