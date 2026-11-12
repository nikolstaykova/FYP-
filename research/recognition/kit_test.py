"""Test the parts check (code/gather/gather.py) on photos of whole parts sets taken from the web.

Photos: data/sources/kit_photos/ (sources.json has each photo's page, author and licence; CC photos from Wikimedia
Commons and Openverse, one ELEGOO product photo for internal testing only). Each case is a set of photos, a lesson,
and the answers accepted for each lesson part (by eye, from the photos). Also checked: parts seen in several photos
are counted once (`once`).
Run: PYTHONPATH=code .venv-research/bin/python research/recognition/kit_test.py [case ...] [--model opus]
     --model nvidia/<id> does the look with an NVIDIA VLM (nvidia_bench.ask; needs NVIDIA_API_KEY), same checks after.
Writes research/recognition/runs/kit_test/<case>.json and summary.json.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1] / 'data/sources/kit_photos'
OUT = HERE / 'runs/kit_test'

HAVE, CHECK, SWAP, MISSING = 'have', 'check', 'use instead', 'missing'
ELEGOO = ['elegoo-uno-most-complete-starter-kit.jpg']
STANDALONE = ['openverse-a35c87d1.jpg', 'openverse-c04df4b4.jpg', 'openverse-a4a49548.jpg']

CASES = {
    # the whole kit in one crowded product photo
    'elegoo-blink': (ELEGOO, 'blink', {
        'arduino-uno': {HAVE}, 'breadboard': {HAVE}, 'jumper-wire': {HAVE}, 'led': {HAVE},
        'resistor': {HAVE, CHECK}}),
    'elegoo-pot': (ELEGOO, 'potentiometer-basics', {
        'arduino-uno': {HAVE}, 'breadboard': {HAVE}, 'jumper-wire': {HAVE}, 'led': {HAVE},
        'potentiometer-10k': {HAVE, CHECK}, 'resistor': {HAVE, CHECK}}),
    'elegoo-servo': (ELEGOO, 'servo-motors', {
        'arduino-uno': {HAVE}, 'breadboard': {HAVE}, 'jumper-wire': {HAVE}, 'servo': {HAVE},
        'potentiometer-10k': {HAVE, CHECK}, 'capacitor-100nf': {HAVE, CHECK, SWAP},
        'dc-power-supply': {HAVE, CHECK, SWAP}}),
    'elegoo-switches': (ELEGOO, 'two-switches-one-pin', {
        'arduino-uno': {HAVE}, 'breadboard': {HAVE}, 'jumper-wire': {HAVE}, 'pushbutton': {HAVE},
        'resistor': {HAVE, CHECK}}),
    # an Uno-compatible clone the catalogue does not know: research, then offer it
    'seeeduino-blink': (['parts-organised-neatly.jpg'], 'blink', {
        'arduino-uno': {SWAP, CHECK}, 'breadboard': {HAVE, CHECK}, 'jumper-wire': {HAVE},
        'led': {MISSING}, 'resistor': {MISSING}}),
    # a small lab in a tin: no board
    'tin-blink': (['tin-electronics-lab-everything-out.jpg'], 'blink', {
        'arduino-uno': {MISSING}, 'breadboard': {HAVE, CHECK}, 'jumper-wire': {HAVE}, 'led': {HAVE},
        'resistor': {HAVE, CHECK}}),
    # one set from three angles: count once; a bare ATmega328 chip is not an Arduino board
    'standalone-switches': (STANDALONE, 'two-switches-one-pin', {
        'arduino-uno': {MISSING}, 'breadboard': {MISSING}, 'jumper-wire': {HAVE},
        'pushbutton': {'missing 1'}, 'resistor': {HAVE, CHECK}}),
    # an Arduino logo is not a board
    'logo-blink': (['openverse-9b1e57cf.jpg'], 'blink', {
        'arduino-uno': {MISSING}, 'breadboard': {MISSING}, 'jumper-wire': {MISSING}, 'led': {HAVE},
        'resistor': {HAVE, CHECK}}),
    # drawings of parts on a box are not parts
    'boxart-blink': (['openverse-4da414b9.jpg'], 'blink', {
        'arduino-uno': {MISSING}, 'breadboard': {MISSING}, 'jumper-wire': {MISSING}, 'led': {MISSING},
        'resistor': {MISSING}}),
}
ONCE = {'standalone-switches': {'led': 1, 'pushbutton': 1, 'crystal': 1}}


def look_nvidia(photos, lesson_id, model):
    """The look step with an NVIDIA or Gemini VLM: the same instruction as Claude gets, answer as JSON, same fields."""
    from gather import gather
    if model.startswith('gemini'):
        from gemini_bench import ask
    elif model.startswith('claude-'):
        from anthropic_bench import ask
    else:
        from nvidia_bench import ask
    rec, _ = gather.lesson(lesson_id)
    parts = "\n".join(f"- {p['type']}: {p['name']} x{p['count']}" for p in rec["parts_list"])
    text = (gather.LOOK + f"\n\nThe photos are numbered in the order given (1, 2, ...). The lesson is "
            f"\"{rec['name']}\". Its parts list:\n{parts}\nList every object in the photos. Answer ONLY with JSON: "
            '{"objects": [{"name": "", "lesson_part": "", "value": "", "count": 1, "photos": [1], '
            '"might_replace": "", "replace_note": "", "unsure": ""}]}')
    t0 = time.perf_counter()
    out, usage, secs = ask(model, [(Path(p).read_bytes(), 'image/jpeg') for p in photos], text, max_tokens=8192)
    i, j = out.find('{'), out.rfind('}')
    try:
        objs = json.loads(out[i:j + 1])['objects']
    except (ValueError, KeyError):
        objs = []
    keys = gather.Seen.model_fields
    seen = []
    for o in objs:
        if isinstance(o, dict) and o.get('name'):
            try:
                seen.append(gather.Seen(**{k: v for k, v in o.items() if k in keys}).model_dump())
            except Exception:
                pass
    return seen, {'seconds': round(time.perf_counter() - t0, 1), 'cost_usd': usage.get('cost_usd', 0.0), 'model': model,
                  'tokens_in': usage.get('prompt_tokens'), 'tokens_out': usage.get('completion_tokens'),
                  'parsed': len(seen), 'raw': out[:4000]}


def run(name, model):
    from gather import gather
    photos, lesson_id, want = CASES[name]
    t0 = time.monotonic()
    if model.startswith(('nvidia/', 'gemini', 'claude-')):
        seen, stats = look_nvidia([KIT / p for p in photos], lesson_id, model)
        res = gather.check(lesson_id, [KIT / p for p in photos], seen=seen)
        res['look'] = stats
    else:
        res = gather.check(lesson_id, [KIT / p for p in photos], model=model)
    res['seconds_total'] = round(time.monotonic() - t0, 1)
    got = {}
    for r in res['parts']:
        got.setdefault(r['type'], []).append(r['status'])
    rows = []
    for t, ok in want.items():
        for st in got.get(t, ['(not in lesson)']):
            rows.append({'part': t, 'got': st, 'accepted': sorted(ok), 'right': st in ok})
    once = []
    for word, n in ONCE.get(name, {}).items():
        c = sum(o['count'] for o in res['seen'] if word in o['name'].lower() or o.get('type') == word)
        once.append({'part': word, 'counted': c, 'there': n, 'right': c == n})
    res['test'] = {'rows': rows, 'once': once}
    out = OUT if model == 'opus' else OUT / model.split('/')[-1]
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{name}.json').write_text(json.dumps(res, indent=1, default=str))
    return res


def main():
    a = sys.argv[1:]
    model = a.pop(a.index('--model') + 1) if '--model' in a else 'opus'
    a = [x for x in a if x != '--model']
    names = a or list(CASES)
    summary = {}
    for n in names:
        res = run(n, model)
        t = res['test']
        right = sum(r['right'] for r in t['rows'])
        summary[n] = {'right': right, 'of': len(t['rows']), 'once': t['once'],
                      'look_s': res['look'].get('seconds'), 'look_usd': res['look'].get('cost_usd'),
                      'total_s': res['seconds_total'],
                      'wrong': [f"{r['part']}: got {r['got']}, want {'/'.join(r['accepted'])}" for r in t['rows']
                                if not r['right']]}
        print(f"{n}: {right}/{len(t['rows'])} right, look {res['look'].get('seconds')} s "
              f"${res['look'].get('cost_usd')}, total {res['seconds_total']} s", flush=True)
        for w in summary[n]['wrong']:
            print('   wrong:', w)
        for o in t['once']:
            print(f"   counted {o['part']}: {o['counted']} (there {o['there']})")
    out = OUT if model == 'opus' else OUT / model.split('/')[-1]
    prev = json.loads((out / 'summary.json').read_text()) if (out / 'summary.json').exists() else {}
    (out / 'summary.json').write_text(json.dumps(prev | summary, indent=1))


if __name__ == '__main__':
    main()
