"""One 3D lesson through the product's whole flow, for the promptfoo eval (provider.py runs it as its own process).

  python run_one.py <set> <model> <effort> <out dir>

lesson.make as `./pinpoint lessons lego` runs it: the planning prompt (lego-v8), up to 3 repairs, code's order fix and
rewording, the final check. LESSON_OUT is set to <out dir> before the product is imported, so the lesson, its stats
and bags.json are written there and never to data/lessons. Prints the stats as one JSON line at the end.
"""
import json
import os
import pathlib
import sys

s, model, effort, out = sys.argv[1:5]
os.environ["LESSON_OUT"] = out
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[3] / "code")]
from graph.lego_3d import lesson as L  # noqa: E402

assert L.OUT == pathlib.Path(out), L.OUT  # never the store
st = L.make(s, model, effort)
print("STATS " + json.dumps(st))
