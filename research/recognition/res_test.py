"""What image size and JPEG quality the parts check needs: cost (image tokens, bytes) against how right it is.

Two sets, both through the production first look (checker.gather_flow.first_look, Haiku) and the rules
(checker.gather.check):
- kit:  the labelled kit photos (kit_test.CASES: 10 cases, accepted answers per lesson part) -> % right.
- lab:  the learner's own phone photos from Parts Quest (runs/lab, up to 1600 px, no labels) -> how many part
        verdicts stay the same as at full size. Full size is run twice: the model's own run-to-run change is the
        floor any smaller size is measured against.
Variants: long edge 1600 / 1280 / 1024 / 768 / 512 / 384 px at JPEG quality 85, and full size at quality 35 / 15.
Image tokens are counted with the API's rule: ceil(w/28) * ceil(h/28) per image (Haiku 5.5 is in the high-resolution
tier: up to 2576 px and 4784 tokens; larger images are scaled down by the API).

Run: PYTHONPATH=code .venv-research/bin/python research/recognition/res_test.py [kit] [lab]
Writes research/recognition/runs/res_test/{results.json, summary.md}.
"""
import hashlib
import io
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / 'runs/res_test'
IMG = OUT / 'images'
LAB = HERE / 'runs/lab'

VARIANTS = [('full', None, 85), ('full-again', None, 85), ('1280', 1280, 85), ('1024', 1024, 85), ('768', 768, 85),
            ('512', 512, 85), ('384', 384, 85), ('full-q35', None, 35), ('full-q15', None, 15)]


def tokens(w, h):
    s = min(1, 2576 / max(w, h))  # the API's high-resolution tier scales larger images down first
    w, h = w * s, h * s
    if math.ceil(w / 28) * math.ceil(h / 28) > 4784:
        s2 = math.sqrt(4784 / (math.ceil(w / 28) * math.ceil(h / 28)))
        w, h = w * s2, h * s2
    return math.ceil(w / 28) * math.ceil(h / 28)


def variant(src, edge, q):
    """The photo at that long edge (never enlarged) and JPEG quality: (path, w, h, bytes)."""
    im = Image.open(src).convert('RGB')
    if edge and max(im.size) > edge:
        s = edge / max(im.size)
        im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=q)
    key = hashlib.sha1(Path(src).read_bytes()).hexdigest()[:10]
    p = IMG / f'{key}-{edge or "full"}-q{q}.jpg'
    p.write_bytes(buf.getvalue())
    return p, im.size[0], im.size[1], len(buf.getvalue())


def cases():
    from kit_test import CASES, KIT
    out = [{'set': 'kit', 'name': n, 'lesson': les, 'photos': [KIT / p for p in ph], 'want': want}
           for n, (ph, les, want) in CASES.items()]
    seen = set()
    for d in sorted(LAB.glob('*/')):  # the learner's photos: each distinct photo set once, the big ones
        st = d / 'flow_state.json'
        if not st.exists() or 'card' in json.loads(st.read_text()):
            continue
        ph = sorted(d.glob('photo_*.jpg'))
        if not ph or max(max(Image.open(p).size) for p in ph) < 1500:
            continue
        key = tuple(hashlib.sha1(p.read_bytes()).hexdigest() for p in ph)
        if key in seen:
            continue
        seen.add(key)
        out.append({'set': 'lab', 'name': d.name, 'lesson': json.loads(st.read_text())['lesson'], 'photos': ph, 'want': None})
    return out


def one(case, var):
    from checker import gather, gather_flow
    name, edge, q = var
    made = [variant(p, edge, q) for p in case['photos']]
    rec, _ = gather.lesson(case['lesson'])
    t0 = time.perf_counter()
    try:
        seen, stats = gather_flow.first_look([str(m[0]) for m in made], rec, small=False)
        res = gather.check(case['lesson'], [str(m[0]) for m in made], research=False, seen=seen)
    except Exception as e:
        return {'case': case['name'], 'set': case['set'], 'variant': name, 'error': repr(e)[:200]}
    got = {}
    for r in res['parts']:
        got.setdefault(r['type'], []).append(r['status'])
    row = {'case': case['name'], 'set': case['set'], 'variant': name, 'verdicts': got,
           'sizes': [f'{w}x{h}' for _, w, h, _ in made], 'image_tokens': sum(tokens(w, h) for _, w, h, _ in made),
           'bytes': sum(b for *_, b in made), 'tokens_in': stats.get('tokens_in'), 'tokens_out': stats.get('tokens_out'),
           'cost_usd': stats.get('cost_usd'), 'seconds': round(time.perf_counter() - t0, 1)}
    if case['want']:
        rows = [(t, st in ok) for t, ok in case['want'].items() for st in got.get(t, ['(none)'])]
        row['right'], row['of'] = sum(r for _, r in rows), len(rows)
    return row


def main():
    sets = [a for a in sys.argv[1:] if a in ('kit', 'lab')] or ['kit', 'lab']
    IMG.mkdir(parents=True, exist_ok=True)
    todo = [(c, v) for c in cases() if c['set'] in sets for v in VARIANTS]
    print(f'{len(todo)} looks', flush=True)
    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lambda cv: one(*cv), todo))
    (OUT / 'results.json').write_text(json.dumps(rows, indent=1))
    lines = ['| variant | set | right (kit) / same as full (lab) | image tokens per photo | KB per photo | input tokens | cost per look | seconds |',
             '|---|---|---|---|---|---|---|---|']
    full = {r['case']: r['verdicts'] for r in rows if r['variant'] == 'full' and 'verdicts' in r}
    for name, *_ in VARIANTS:
        for s in sets:
            rs = [r for r in rows if r['variant'] == name and r['set'] == s and 'verdicts' in r]
            if not rs:
                continue
            nph = sum(len(r['sizes']) for r in rs)
            if s == 'kit':
                score = f"{sum(r['right'] for r in rs)}/{sum(r['of'] for r in rs)}"
            else:
                same = tot = 0
                for r in rs:
                    for t, v in full.get(r['case'], {}).items():
                        tot += 1
                        same += sorted(r['verdicts'].get(t, [])) == sorted(v)
                score = f'{same}/{tot}'
            lines.append(f"| {name} | {s} | {score} | {sum(r['image_tokens'] for r in rs) / nph:.0f} | "
                         f"{sum(r['bytes'] for r in rs) / nph / 1024:.0f} | {sum(r['tokens_in'] or 0 for r in rs) / len(rs):.0f} | "
                         f"${sum(r['cost_usd'] or 0 for r in rs) / len(rs):.5f} | {sum(r['seconds'] for r in rs) / len(rs):.1f} |")
    errs = [r for r in rows if 'error' in r]
    (OUT / 'summary.md').write_text('\n'.join(lines) + (f'\n\nerrors: {errs}' if errs else '') + '\n')
    print('\n'.join(lines))
    if errs:
        print('errors:', errs)


if __name__ == '__main__':
    main()
