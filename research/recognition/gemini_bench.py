"""Google Gemini VLMs through the Gemini API: the same photos (every 4th test photo) and words (classes.ASK) as the
Claude, NVIDIA and local runs. Writes runs/<model>/preds.jsonl for score.py. `ask()` is also the look step of
kit_test.py and swap_test.py for models named gemini-*.

Models tested (3 Nov 2026): gemini-3.5-flash-lite, gemini-3.8-flash, gemini-pro-latest, gemini-robotics-er-2-preview.
Cost is worked out from the token counts the API returns and PRICES (paid tier per 1M tokens, aistudio.google.com/
docs/pricing, read 3 Nov 2026; output includes thinking). Needs GEMINI_API_KEY in .env (aistudio.google.com).
Run: python3 gemini_bench.py gemini-3.8-flash [--every 4] [--limit N]
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from classes import JSON_ASK, parse_json_list

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPLIT = ROOT / 'data/sources/electrocom61/split'
URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
PRICES = {'gemini-3.5-flash-lite': (0.30, 2.50), 'gemini-3.8-flash': (0.75, 3.75),
          'gemini-robotics-er-2-preview': (1.00, 5.00), 'gemini-pro-latest': (2.00, 12.00),
          'gemini-3.1-pro-preview': (2.00, 12.00)}


def key():
    k = os.environ.get('GEMINI_API_KEY')
    if not k and (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('GEMINI_API_KEY='):
                k = line.split('=', 1)[1].strip().strip('"\'')
    if not k:
        raise SystemExit('GEMINI_API_KEY is not set (add it to .env)')
    return k


def _call(model, body, timeout=600):
    req = urllib.request.Request(URL.format(model=model), data=json.dumps(body).encode(),
                                 headers={'x-goog-api-key': key(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ask(model, images, text, max_tokens=8192, tries=4, json_out=True):
    """One call with images (bytes, media type) and text; returns (answer text, usage, seconds). Thinking is kept
    low (the list needs looking, not long reasoning); a model that refuses that setting is called without it."""
    parts = [{'inline_data': {'mime_type': mt, 'data': base64.b64encode(b).decode()}} for b, mt in images]
    parts.append({'text': text})
    gen = {'temperature': 0, 'maxOutputTokens': max_tokens, 'thinkingConfig': {'thinkingLevel': 'low'}}
    if json_out:
        gen['responseMimeType'] = 'application/json'
    for attempt in range(tries):
        t0 = time.perf_counter()
        try:
            d = _call(model, {'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': gen})
        except urllib.error.HTTPError as e:
            msg = e.read()[:400]
            if e.code == 400 and b'thinking' in msg.lower() and 'thinkingConfig' in gen:
                gen.pop('thinkingConfig')  # this model has no thinking level: call it plainly
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(20 * (attempt + 1))  # rate limit (free tier) or busy: wait and try again
                continue
            raise RuntimeError(f'{model}: HTTP {e.code} {msg!r}')
        secs = time.perf_counter() - t0
        cand = (d.get('candidates') or [{}])[0]
        out = ''.join(p.get('text', '') for p in (cand.get('content') or {}).get('parts', []) if not p.get('thought'))
        u = d.get('usageMetadata', {})
        tin, tout = u.get('promptTokenCount', 0), u.get('candidatesTokenCount', 0) + u.get('thoughtsTokenCount', 0)
        pin, pout = PRICES.get(model, (0, 0))
        usage = {'prompt_tokens': tin, 'completion_tokens': tout, 'thinking_tokens': u.get('thoughtsTokenCount', 0),
                 'cost_usd': round((tin * pin + tout * pout) / 1e6, 6), 'model_version': d.get('modelVersion')}
        return out, usage, secs
    raise RuntimeError(f'{model}: no answer after {tries} tries')


def one(path, model):
    text, usage, secs = ask(model, [(Path(path).read_bytes(), 'image/jpeg')], JSON_ASK)
    return {'image': path, 'dets': parse_json_list(text), 'seconds': round(secs, 2), 'cost_usd': usage['cost_usd'],
            'tokens_in': usage['prompt_tokens'], 'tokens_out': usage['completion_tokens'],
            'model_version': usage['model_version'], 'raw': text[:3000]}


def main():
    a = sys.argv[1:]
    model = a[0]
    every = int(a[a.index('--every') + 1]) if '--every' in a else 4
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    ims = [l for l in (SPLIT / 'test.txt').read_text().split('\n') if l][::every][:limit]
    out = HERE / 'runs' / model
    out.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)['image'] for l in open(out / 'preds.jsonl')} if (out / 'preds.jsonl').exists() else set()
    todo = [p for p in ims if p not in done]
    print(f'{model}: {len(todo)} photos to do ({len(done)} done)', flush=True)
    with open(out / 'preds.jsonl', 'a') as f, ThreadPoolExecutor(2) as pool:
        for i, row in enumerate(pool.map(lambda p: one(p, model), todo)):
            f.write(json.dumps(row) + '\n')
            f.flush()
            if i % 10 == 0:
                print(f'{i}/{len(todo)} {row["seconds"]}s {len(row["dets"])} objects ${row["cost_usd"]}', flush=True)
    (out / 'config.json').write_text(json.dumps({'model': model, 'route': 'Gemini API', 'every': every,
                                                 'photos': len(ims), 'prices_per_1M': PRICES.get(model),
                                                 'prompt': JSON_ASK}, indent=1))


if __name__ == '__main__':
    main()
