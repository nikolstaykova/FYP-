"""Claude vision as a recogniser: one photo in, every object seen out (plain name, catalogue kind or "unknown", box), via the project's
subscription call (graph.extract.claude_json, timed and costed). Writes runs/claude-<model>/preds.jsonl.

Run with the research environment (it has pydantic and the claude CLI route):
  PYTHONPATH=code .venv-research/bin/python research/recognition/claude_bench.py sonnet [--every 4] [--effort low]
--every N takes every Nth test photo (4 -> about 106 photos), so the sample spreads over the whole test set.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from graph.extract import _image_block, claude_json

from classes import ASK, PARTS

HERE = Path(__file__).resolve().parent
SPLIT = HERE.parents[1] / 'data/sources/electrocom61/split'

SYSTEM = ASK


class Found(BaseModel):
    name: str = Field(description='what it is, in plain words')
    part: Literal[tuple(PARTS) + ('unknown',)]
    box: list[int] = Field(description='x1, y1, x2, y2 in thousandths of width/height')


class Answer(BaseModel):
    objects: list[Found]


def one(path, model, effort):
    content = [_image_block(Path(path).read_bytes(), 'image/jpeg'), {'type': 'text', 'text': 'List every object.'}]
    t0 = time.perf_counter()
    ans, stats = claude_json(SYSTEM, content, Answer, model=model, effort=effort, timeout=300)
    dets = [{'part': o['part'], 'name': o['name'], 'conf': 1.0, 'box': [min(max(v / 1000, 0), 1) for v in o['box'][:4]]}
            for o in ans['objects'] if len(o['box']) >= 4]
    return {'image': path, 'dets': dets, 'seconds': round(time.perf_counter() - t0, 2),
            'cost_usd': stats.get('cost_usd', 0), 'tokens_in': stats.get('input_tokens'),
            'tokens_out': stats.get('output_tokens')}


def main():
    a = sys.argv[1:]
    model = a[0]
    every = int(a[a.index('--every') + 1]) if '--every' in a else 4
    effort = a[a.index('--effort') + 1] if '--effort' in a else 'low'
    ims = [l for l in (SPLIT / 'test.txt').read_text().split('\n') if l][::every]
    out = HERE / 'runs' / f'claude-{model}'
    out.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)['image'] for l in open(out / 'preds.jsonl')} if (out / 'preds.jsonl').exists() else set()
    todo = [p for p in ims if p not in done]
    print(f'{len(todo)} photos to do ({len(done)} done)', flush=True)
    with open(out / 'preds.jsonl', 'a') as f, ThreadPoolExecutor(4) as pool:
        for i, row in enumerate(pool.map(lambda p: one(p, model, effort), todo)):
            f.write(json.dumps(row) + '\n')
            f.flush()
            if i % 10 == 0:
                print(f'{i}/{len(todo)} ${row["cost_usd"]} {row["seconds"]}s', flush=True)
    (out / 'config.json').write_text(json.dumps({'model': model, 'effort': effort, 'every': every,
                                                 'photos': len(ims), 'system': SYSTEM}, indent=1))


if __name__ == '__main__':
    main()
