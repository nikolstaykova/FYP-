"""NVIDIA VLMs through NVIDIA's hosted API (build.nvidia.com, OpenAI-compatible): the same photos (every 4th test
photo) and the same words (classes.ASK) as the Claude and local runs. Writes runs/<model>/preds.jsonl for score.py.

Models tested (3 Nov 2026): nvidia/cosmos-reason2-8b (physical-world reasoning), nvidia/nemotron-3-nano-omni-30b-a3b-
reasoning (small, 3B active), nvidia/nemotron-3.5-super-vl-120b-a12b (the flagship).
Needs NVIDIA_API_KEY in .env (an NVIDIA account's key from build.nvidia.com; free credits).
Run: ~/.venvs/pinpoint-vision/bin/python nvidia_bench.py nvidia/cosmos-reason2-8b [--every 4] [--limit N]
"""
import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from classes import JSON_ASK, parse_json_list

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPLIT = ROOT / 'data/sources/electrocom61/split'
URL = 'https://integrate.api.nvidia.com/v1/chat/completions'


def key():
    k = os.environ.get('NVIDIA_API_KEY')
    if not k and (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('NVIDIA_API_KEY='):
                k = line.split('=', 1)[1].strip().strip('"\'')
    if not k:
        raise SystemExit('NVIDIA_API_KEY is not set (add it to .env)')
    return k


def ask(model, images, text, max_tokens=4096, tries=4):
    """One chat call with images (bytes, media type) and text; returns (answer text, usage, seconds)."""
    content = [{'type': 'image_url', 'image_url': {'url': f'data:{mt};base64,{base64.b64encode(b).decode()}'}}
               for b, mt in images] + [{'type': 'text', 'text': text}]
    # Nemotron models think before answering unless told not to; the list is all we need
    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
                       'max_tokens': max_tokens, 'chat_template_kwargs': {'enable_thinking': False}}).encode()
    for attempt in range(tries):
        t0 = time.perf_counter()
        req = urllib.request.Request(URL, data=body, headers={'Authorization': f'Bearer {key()}',
                                                              'Content-Type': 'application/json',
                                                              'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.loads(r.read())
            msg = d['choices'][0]['message']
            # a model that still thinks may put its answer only in the reasoning text
            return (msg.get('content') or msg.get('reasoning_content') or ''), d.get('usage', {}), \
                time.perf_counter() - t0
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(20 * (attempt + 1))  # rate limit or a busy model: wait and try again
                continue
            raise RuntimeError(f'{model}: HTTP {e.code} {e.read()[:300]!r}')


def one(path, model):
    text, usage, secs = ask(model, [(Path(path).read_bytes(), 'image/jpeg')], JSON_ASK)
    return {'image': path, 'dets': parse_json_list(text), 'seconds': round(secs, 2), 'cost_usd': 0.0,
            'tokens_in': usage.get('prompt_tokens'), 'tokens_out': usage.get('completion_tokens'), 'raw': text[:3000]}


def main():
    a = sys.argv[1:]
    model = a[0]
    every = int(a[a.index('--every') + 1]) if '--every' in a else 4
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    ims = [l for l in (SPLIT / 'test.txt').read_text().split('\n') if l][::every][:limit]
    out = HERE / 'runs' / model.split('/')[-1]
    out.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)['image'] for l in open(out / 'preds.jsonl')} if (out / 'preds.jsonl').exists() else set()
    todo = [p for p in ims if p not in done]
    print(f'{model}: {len(todo)} photos to do ({len(done)} done)', flush=True)
    with open(out / 'preds.jsonl', 'a') as f, ThreadPoolExecutor(2) as pool:
        for i, row in enumerate(pool.map(lambda p: one(p, model), todo)):
            f.write(json.dumps(row) + '\n')
            f.flush()
            if i % 10 == 0:
                print(f'{i}/{len(todo)} {row["seconds"]}s {len(row["dets"])} objects', flush=True)
    (out / 'config.json').write_text(json.dumps({'model': model, 'route': 'NVIDIA API (build.nvidia.com)',
                                                 'every': every, 'photos': len(ims), 'prompt': JSON_ASK}, indent=1))


if __name__ == '__main__':
    main()
