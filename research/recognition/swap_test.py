"""The "one part is a different model" test: Blink needs an Arduino Uno; each photo holds one board (an Uno as the
control, or a Mega, a Nano or an ESP32) among other parts. A model passes a photo when it reads the exact board
(the code matches it to the right catalogue part) and the parts check gives the right verdict for the Uno:
Uno -> have; Mega, Nano -> use instead (same pins); ESP32 -> use instead (pin 13 is D13, 3.3 V).

Photos: ElectroCom61 test and validation photos with exactly one board (never used for training anything).
Run: PYTHONPATH=code:research/recognition .venv-research/bin/python research/recognition/swap_test.py opus|haiku|
     sonnet|nvidia/<id>
Writes runs/swap_test/<model>.json.
"""
import collections
import glob
import json
import sys
import time
from pathlib import Path

from classes import NAMES

HERE = Path(__file__).resolve().parent
EC = HERE.parents[1] / 'data/sources/electrocom61/ec61'
BOARDS = {'Arduino-Uno': ('arduino-uno', {'have'}), 'Arduino-Mega': ('arduino-mega', {'use instead'}),
          'Arduino-Nano': ('arduino-nano', {'use instead'}), 'ESP32': ('esp32', {'use instead', 'check'})}
PER_BOARD = 4


def photos():
    found = collections.defaultdict(list)
    for f in sorted(glob.glob(str(EC / 'test/labels/*.txt'))) + sorted(glob.glob(str(EC / 'valid/labels/*.txt'))):
        boards = [NAMES[int(l.split()[0])] for l in open(f) if l.strip() and NAMES[int(l.split()[0])] in BOARDS]
        if len(boards) == 1:
            found[boards[0]].append(f.replace('/labels/', '/images/')[:-4] + '.jpg')
    # spread the picks over each board's photos (not neighbours from one burst)
    return [(b, ims[i * len(ims) // min(PER_BOARD, len(ims))]) for b, ims in sorted(found.items())
            for i in range(min(PER_BOARD, len(ims)))]


def main():
    from checker import gather
    model = sys.argv[1]
    rows, t0 = [], time.monotonic()
    for board, path in photos():
        want_type, want_status = BOARDS[board]
        if model.startswith(('nvidia/', 'gemini', 'claude-')):
            from kit_test import look_nvidia
            seen, stats = look_nvidia([path], 'blink', model)
            res = gather.check('blink', [path], seen=seen)
            res['look'] = stats
        else:
            res = gather.check('blink', [path], model=model)
        uno = next(r for r in res['parts'] if r['type'] == 'arduino-uno')
        boards = [o for o in res['seen'] if o.get('type') and gather.is_board(gather.catalogue(), o['type'])]
        read = any(str(o['type']).startswith(want_type) for o in boards)
        rows.append({'board': board, 'photo': Path(path).name, 'read_right': read,
                     'read_as': [f"{o['name']} -> {o['type']}" for o in res['seen']
                                 if o.get('type') and gather.is_board(gather.catalogue(), o['type'])
                                 or 'board' in o['name'].lower() or 'arduino' in o['name'].lower()],
                     'status': uno['status'], 'verdict_right': uno['status'] in want_status and read,
                     'why': [u['why'] for u in uno['use_instead']][:1],
                     'seconds': res['look'].get('seconds'), 'cost_usd': res['look'].get('cost_usd')})
        r = rows[-1]
        print(f"{board:13} read {'ok ' if r['read_right'] else 'NO '} verdict {'ok ' if r['verdict_right'] else 'NO '}"
              f"{r['status']:12} {r['read_as'][:2]}", flush=True)
    n = len(rows)
    summary = {'model': model, 'photos': n, 'read_right': sum(r['read_right'] for r in rows),
               'verdict_right': sum(r['verdict_right'] for r in rows),
               'median_s': sorted(r['seconds'] or 0 for r in rows)[n // 2],
               'cost_usd': round(sum(r['cost_usd'] or 0 for r in rows), 3), 'minutes': round((time.monotonic() - t0) / 60, 1)}
    print(json.dumps(summary))
    out = HERE / 'runs/swap_test'
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{model.split('/')[-1]}.json").write_text(json.dumps({'summary': summary, 'rows': rows}, indent=1))


if __name__ == '__main__':
    main()
