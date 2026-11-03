"""Re-split ElectroCom61 so test photos are new scenes, and every lesson part is in the test set.

Why: the published split leaves LED, buzzer and push switch out of test and validation entirely, and many photos
were shot seconds apart (near copies of one scene), so a random split would test on scenes seen in training.
How: consecutive photos are grouped into bursts (taken within 10 s, or looking alike: near copies of one scene);
whole bursts go to one split.
Limit: the photographer re-arranged the same few parts between shots for hours, so every split still shares the
same physical objects; scores on this test set will be higher than on a new kit. Bursts are handed out greedily to the split whose share of the burst's lesson parts is
furthest below its target (train 70%, val 10%, test 20%).

Writes data/sources/electrocom61/split/{train,val,test}.txt (image paths) and data.yaml (for Ultralytics).
Run: python research/recognition/make_split.py
"""
import collections
import datetime as dt
import json
import random
import re
from pathlib import Path

import cv2
import numpy as np

from classes import NAMES, part_of

ROOT = Path(__file__).resolve().parents[2] / 'data/sources/electrocom61'
SRC = ROOT / 'ec61'
OUT = ROOT / 'split'
TARGET = {'train': 0.7, 'val': 0.1, 'test': 0.2}
GAP_S = 10
SIM_MIN = 0.8   # correlation of 24x24 grey thumbnails; ~15% of consecutive iPhone photos are above it


def stamp(name):
    """(kind, number) used to order and group photos: seconds for camera timestamps, sequence for IMG_1234."""
    base = name.split('.rf.')[0]
    m = re.match(r'IMG_?(\d{8})_?(\d{6})', base)
    if m:
        t = dt.datetime.strptime(m[1] + m[2], '%Y%m%d%H%M%S')
        return 'time', t.timestamp()
    m = re.match(r'IMG_(\d{4})_JPG', base)
    return 'seq', int(m[1])


def thumb(path):
    a = cv2.resize(cv2.imread(str(path), 0), (24, 24), interpolation=cv2.INTER_AREA).astype(float).ravel()
    a -= a.mean()
    return a / (np.linalg.norm(a) or 1)


def bursts(images):
    """Consecutive photos join one burst when taken within GAP_S seconds or when they look alike (SIM_MIN).
    The iPhone photos (IMG_1234) have no time, so only looks count for them."""
    by_kind = collections.defaultdict(list)
    for im in images:
        k, v = stamp(im.name)
        by_kind[k].append((v, im))
    groups = []
    for kind, items in by_kind.items():
        items.sort()
        cur, last = [], None
        for v, im in items:
            t = thumb(im)
            if last is not None:
                close = kind == 'time' and v - last[0] <= GAP_S
                if not close and float(t @ last[1]) < SIM_MIN:
                    groups.append(cur)
                    cur = []
            cur.append(im)
            last = (v, t)
        groups.append(cur)
    return groups


def parts_in(im):
    lab = Path(str(im).replace('/images/', '/labels/')).with_suffix('.txt')
    c = collections.Counter()
    for line in open(lab):
        if line.strip():
            p = part_of(int(line.split()[0]))
            if p:
                c[p] += 1
    return c


def main():
    images = sorted(SRC.glob('*/images/*.jpg'))
    groups = bursts(images)
    random.Random(0).shuffle(groups)
    # place bursts with rare parts first so they spread across splits
    total = collections.Counter()
    gparts = []
    for g in groups:
        c = collections.Counter()
        for im in g:
            c += parts_in(im)
        gparts.append(c)
        total += c
    order = sorted(range(len(groups)), key=lambda i: min([total[p] for p in gparts[i]] or [10**9]))
    have = {s: collections.Counter() for s in TARGET}
    n_img = collections.Counter()
    split_of = {}
    for i in order:
        c = gparts[i]

        def need(s):
            if c:
                return sum(TARGET[s] - have[s][p] / total[p] for p in c) / len(c)
            return TARGET[s] - n_img[s] / len(images)
        s = max(TARGET, key=need)
        split_of[i] = s
        have[s] += c
        n_img[s] += len(groups[i])
    OUT.mkdir(exist_ok=True)
    for s in TARGET:
        ims = sorted(str(im) for i, g in enumerate(groups) if split_of[i] == s for im in g)
        (OUT / f'{s}.txt').write_text('\n'.join(ims) + '\n')
    (OUT / 'data.yaml').write_text(
        f"path: {OUT}\ntrain: train.txt\nval: val.txt\ntest: test.txt\nnc: {len(NAMES)}\nnames: {json.dumps(NAMES)}\n")
    report = {'bursts': len(groups), 'images': dict(n_img),
              'parts': {p: {s: have[s][p] for s in TARGET} for p in sorted(total)}}
    (OUT / 'split_report.json').write_text(json.dumps(report, indent=1))
    print(f"{len(images)} images in {len(groups)} bursts -> {dict(n_img)}")
    print(f"{'part':15} " + ' '.join(f'{s:>6}' for s in TARGET))
    for p in sorted(total):
        print(f"{p:15} " + ' '.join(f'{have[s][p]:6}' for s in TARGET))


if __name__ == '__main__':
    main()
