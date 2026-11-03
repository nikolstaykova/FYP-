"""Judge the plain names a model gave to UNKNOWN objects (not in our catalogue) against ElectroCom61's label.

Reads runs/<name>/names.json (written by score.py), asks Claude Haiku in batches whether each name is right
("right": same thing; "close": right family but not the specific kind, e.g. "transistor" for an IGBT; "wrong"),
writes runs/<name>/names_judged.json and adds the shares to metrics.json.
Run: PYTHONPATH=code .venv-research/bin/python research/recognition/judge.py research/recognition/runs/<name>
"""
import collections
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from graph.extract import claude_json

SYSTEM = """You check names given to electronic parts in photos. For each item you get the true label and the name
a model gave. Answer per item:
- right: the name means the same kind of part (synonyms and extra detail are fine: "HC-SR501 PIR sensor" for
  "motion sensor", "relay board" for "relay module")
- close: the right family but not the specific kind ("transistor" for "igbt", "capacitor" for "film capacitor",
  "sensor module" for "gas sensor")
- wrong: a different part, or too vague to help ("component", "electronic module", "object")"""


class Verdict(BaseModel):
    i: int
    verdict: Literal['right', 'close', 'wrong']


class Verdicts(BaseModel):
    items: list[Verdict]


def main():
    run = Path(sys.argv[1])
    names = json.loads((run / 'names.json').read_text())
    # judge each distinct (truth, said) pair once
    pairs = sorted({(n['truth'], n['said'].strip().lower()) for n in names})
    verdict, cost = {}, 0.0
    for start in range(0, len(pairs), 80):
        chunk = pairs[start:start + 80]
        text = '\n'.join(f'{i}. true: {t} | said: {s}' for i, (t, s) in enumerate(chunk))
        ans, stats = claude_json(SYSTEM, [{'type': 'text', 'text': text}], Verdicts, model='haiku', effort='low')
        cost += stats.get('cost_usd', 0)
        for v in ans['items']:
            if 0 <= v['i'] < len(chunk):
                verdict[chunk[v['i']]] = v['verdict']
    judged = [n | {'verdict': verdict.get((n['truth'], n['said'].strip().lower()), 'wrong')} for n in names]
    (run / 'names_judged.json').write_text(json.dumps(judged, indent=1))
    c = collections.Counter(j['verdict'] for j in judged)
    share = {k: round(c[k] / max(len(judged), 1), 3) for k in ('right', 'close', 'wrong')}
    m = json.loads((run / 'metrics.json').read_text())
    m['open_world']['unknown_names'] = share | {'n': len(judged), 'judge_cost_usd': round(cost, 4)}
    (run / 'metrics.json').write_text(json.dumps(m, indent=1))
    print(run.name, share, f'n={len(judged)}', f'${cost:.4f}')


if __name__ == '__main__':
    main()
