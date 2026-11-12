"""Which model and image size give the cheapest right check, once the Opus fallback is paid for.

For every model x photo size x photo set:
  1. first look by the model (the production prompt; Claude through checker.gather_flow.first_look, Gemini and NVIDIA
     through kit_test.look_nvidia, the same instruction and JSON);
  2. the rules (checker.gather.check) and the flags (checker.gather_flow.flags): what the first look could not settle;
  3. the fallback: Opus looks again at only the flagged objects and parts, on the same photos
     (gather_flow.second_look). In the app the learner's close-up goes to Haiku first and Opus only when Haiku still
     cannot tell, so this is the worst case: every question the learner would get (at most 3, lesson parts only,
     gather_flow.asks) goes to Opus. An Opus first look has no fallback.
Price per check = first look + fallback when it ran. Quality: kit photos (labelled, kit_test.CASES) % right, first
look alone and after the fallback; your photos (runs/lab, no labels) % of verdicts the same as Opus at full size.

Run: PYTHONPATH=code .venv-research/bin/python research/recognition/model_cost_test.py
Writes research/recognition/runs/model_cost/results.json (one row per check, resumable: done rows are kept).
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / 'runs/model_cost'

MODELS = ['claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5', 'gemini-3.5-flash-lite', 'gemini-3.8-flash',
          'nvidia/nemotron-3.5-super-vl-120b-a12b']
SIZES = [('full', None), ('1024', 1024), ('768', 768), ('512', 512)]
FALLBACK_AT = {'full', '768'}  # the Opus fallback is measured at these sizes
OPUS = 'claude-opus-5-5'


def first(model, photos, rec, lesson):
    from checker import gather_flow
    if model.startswith('claude-'):
        return gather_flow.first_look(photos, rec, model, small=False)  # the photos are already sized
    from kit_test import look_nvidia
    seen, st = look_nvidia(photos, lesson, model)
    return seen, {**st, 'model': model}


def one(case, model, size):
    from checker import gather, gather_flow
    from res_test import variant
    name, edge = size
    photos = [str(variant(p, edge, 85)[0]) for p in case['photos']]
    rec, _ = gather.lesson(case['lesson'])
    row = {'case': case['name'], 'set': case['set'], 'model': model, 'size': name}
    t0 = time.perf_counter()
    try:
        seen, st1 = first(model, photos, rec, case['lesson'])
        res1 = gather.check(case['lesson'], photos, research=False, seen=seen)
        objects, parts = gather_flow.flags(res1, {r['type'] for r in res1['parts']})
        qs = gather_flow.asks(res1, objects, parts)  # what the learner would be asked (at most 3, lesson parts only)
        why = dict(objects)
        objects = [(q['ref'], why.get(q['ref'], 'unsure')) for q in qs if q['kind'] == 'closeup']
        parts = [(r, w) for r, w in parts if f"p:{r['type']}" in {q['key'] for q in qs}]
        row.update(first_usd=st1.get('cost_usd') or 0.0, first_s=st1.get('seconds'), tokens_out=st1.get('tokens_out'),
                   parsed=len(seen), questions=len(qs))
        row['first_verdicts'] = _verdicts(res1)
        final = res1
        row['fallback_usd'] = 0.0
        row['fallback_ran'] = False
        if (objects or parts) and model != OPUS and name in FALLBACK_AT:
            answers, st2 = gather_flow.second_look(photos, rec, seen, objects, parts, OPUS)
            merged, _ = gather_flow.merge(seen, objects, answers)
            final = gather.check(case['lesson'], photos, research=False, seen=merged)
            row.update(fallback_usd=st2.get('cost_usd') or 0.0, fallback_s=st2.get('seconds'), fallback_ran=True)
        row['final_verdicts'] = _verdicts(final)
        row['with_fallback'] = model == OPUS or name in FALLBACK_AT
    except Exception as e:
        row['error'] = repr(e)[:300]
    row['seconds'] = round(time.perf_counter() - t0, 1)
    return row


def _verdicts(res):
    got = {}
    for r in res['parts']:
        got.setdefault(r['type'], []).append(r['status'])
    return got


def main():
    from res_test import cases, IMG
    IMG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / 'results.json'
    done = [r for r in json.loads(f.read_text())] if f.exists() else []
    have = {(r['case'], r['model'], r['size']) for r in done if 'error' not in r}
    cs = cases()
    todo = [(c, m, s) for m in MODELS for s in SIZES for c in cs if (c['name'], m, s[0]) not in have]
    print(f'{len(todo)} checks to run ({len(have)} done)', flush=True)
    rows = [r for r in done if 'error' not in r]

    def run(t):
        r = one(*t)
        print(f"{r['model']:42} {r['size']:5} {r['case']:22} first ${r.get('first_usd', 0):.4f} "
              f"fallback ${r.get('fallback_usd', 0):.4f} {r.get('error', '')[:80]}", flush=True)
        return r
    with ThreadPoolExecutor(8) as pool:
        for r in pool.map(run, todo):
            rows.append(r)
            f.write_text(json.dumps(rows, indent=1))
    print('total spent this run: $%.3f' % sum((r.get('first_usd') or 0) + (r.get('fallback_usd') or 0)
                                              for r in rows if (r['case'], r['model'], r['size']) not in have))


if __name__ == '__main__':
    main()
