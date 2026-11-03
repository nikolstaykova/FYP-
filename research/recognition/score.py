"""Score a recognition run against the ElectroCom61 test split.

Known parts are our 16 lesson parts; the other 40 ElectroCom61 classes stand in for parts not in the catalogue
yet ("unknown"). Three measures:
- box AP@50 per part and its mean (mAP@50): how well the boxes are found, over every confidence threshold;
- gather counts: what step 0 needs. Per photo and part, the number found (confidence >= threshold) against the
  number there. Recall = found and there / there; precision = found and there / found; "photo right" = every
  part's count right in that photo. The threshold is the one with the best F1 on the validation run when given
  (--val), else 0.25.
- open world: every labelled object (all 61 classes) matched one-to-one to a box (IoU >= 0.5; and a loose
  'centre' match: the box's centre inside the object, for models that see the right thing but box it loosely). Found = has a box.
  Known objects: named right, called "unknown", or called another part. Unknown objects: called "unknown" (right),
  or called one of our parts (the worst mistake: the learner is told a wrong part is there). Plain names given to
  unknown objects are written to names.json for judge.py.

A run is preds.jsonl: one line per photo {"image": path, "dets": [{"part" (or "unknown"), "name" (optional),
"conf", "box": [x1,y1,x2,y2] 0-1}],
"seconds", "cost_usd"}. Run: python score.py runs/<name> [--val runs/<name>-val] [--same runs/<other>]  (--same: only that run's photos)
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

from classes import HELD_OUT, PARTS, name_of, part_of

HELD = {h.replace('-', ' ').lower() for h in HELD_OUT}


def truth(image):
    lab = Path(image.replace('/images/', '/labels/')).with_suffix('.txt')
    out = []
    for line in open(lab):
        f = line.split()
        if not f:
            continue
        p = part_of(int(f[0]))
        if p:
            x, y, w, h = map(float, f[1:5])
            out.append((p, [x - w / 2, y - h / 2, x + w / 2, y + h / 2]))
    return out


def truth_all(image):
    """Every labelled object: (ElectroCom61 name, our part or None, box)."""
    lab = Path(image.replace('/images/', '/labels/')).with_suffix('.txt')
    out = []
    for line in open(lab):
        f = line.split()
        if f:
            c = int(f[0])
            x, y, w, h = map(float, f[1:5])
            out.append((name_of(c), part_of(c), [x - w / 2, y - h / 2, x + w / 2, y + h / 2]))
    return out


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def load(run):
    return [json.loads(l) for l in open(Path(run) / 'preds.jsonl') if l.strip()]


def ap50(rows):
    """All-point AP at IoU 0.5 per part (VOC/COCO style)."""
    out = {}
    for p in PARTS:
        n_true = 0
        scored = []
        for r in rows:
            gts = [b for q, b in truth(r['image']) if q == p]
            n_true += len(gts)
            used = [False] * len(gts)
            for d in sorted((d for d in r['dets'] if d['part'] == p and d.get('box')), key=lambda d: -d['conf']):
                best, j = 0.0, -1
                for k, g in enumerate(gts):
                    v = iou(d['box'], g)
                    if v > best and not used[k]:
                        best, j = v, k
                hit = best >= 0.5
                if hit:
                    used[j] = True
                scored.append((d['conf'], hit))
        if n_true == 0:
            continue
        scored.sort(key=lambda s: -s[0])
        tp = np.cumsum([h for _, h in scored]) if scored else np.array([0])
        fp = np.cumsum([not h for _, h in scored]) if scored else np.array([0])
        rec = tp / n_true
        prec = tp / np.maximum(tp + fp, 1)
        mrec = np.concatenate([[0], rec, [1]])
        mpre = np.concatenate([[1], prec, [0]])
        mpre = np.maximum.accumulate(mpre[::-1])[::-1]
        idx = np.where(mrec[1:] != mrec[:-1])[0]
        out[p] = float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1])) if scored else 0.0
    return out


def counts(rows, thr):
    per = collections.defaultdict(lambda: [0, 0, 0])   # part -> [hit, found, there]
    right = 0
    for r in rows:
        there = collections.Counter(p for p, _ in truth(r['image']))
        found = collections.Counter(d['part'] for d in r['dets'] if d['conf'] >= thr and d['part'] in PARTS)
        ok = True
        for p in set(there) | set(found):
            hit = min(there[p], found[p])
            per[p][0] += hit
            per[p][1] += found[p]
            per[p][2] += there[p]
            ok &= there[p] == found[p]
        right += ok
    hit, found, there = (sum(v[i] for v in per.values()) for i in range(3))
    return {'recall': hit / max(there, 1), 'precision': hit / max(found, 1),
            'f1': 2 * hit / max(found + there, 1), 'photos_right': right / max(len(rows), 1),
            'per_part': {p: {'recall': v[0] / max(v[2], 1), 'precision': v[0] / max(v[1], 1), 'there': v[2]}
                         for p, v in sorted(per.items())}}


def center_in(d, g):
    """1 when the box's centre lies inside the labelled box (a loose match: 'it pointed at the right thing')."""
    cx, cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
    return float(g[0] <= cx <= g[2] and g[1] <= cy <= g[3])


def open_world(rows, thr, match='iou'):
    k = collections.Counter()
    false_known = collections.Counter()
    names = []
    for r in rows:
        gts = truth_all(r['image'])
        dets = [d for d in r['dets'] if d['conf'] >= thr and d.get('box')]
        sim = iou if match == 'iou' else lambda a, b: center_in(a, b) * (0.5 + iou(a, b))
        pairs = sorted(((sim(d['box'], g[2]), i, j) for i, d in enumerate(dets) for j, g in enumerate(gts)),
                       reverse=True)
        used_d, used_g = set(), {}
        for v, i, j in pairs:
            if v < 0.5:
                break
            if i not in used_d and j not in used_g:
                used_d.add(i)
                used_g[j] = dets[i]
        k['boxes'] += len(dets)
        k['boxes_on_object'] += len(used_d)
        for j, (name, part, _) in enumerate(gts):
            d = used_g.get(j)
            side = 'known' if part else 'unknown'
            k[side] += 1
            k['held_out'] += name in HELD
            if not d:
                continue
            k[side + '_found'] += 1
            if part:
                k['known_right' if d['part'] == part else
                  'known_said_unknown' if d['part'] == 'unknown' else 'known_wrong_part'] += 1
            else:
                if name in HELD:  # kinds the trained detector never saw labelled
                    k['held_out_found'] += 1
                    k['held_out_said_unknown'] += d['part'] == 'unknown'
                if d['part'] == 'unknown':
                    k['unknown_said_unknown'] += 1
                else:
                    k['unknown_said_known'] += 1
                    false_known[f"{name} -> {d['part']}"] += 1
                if d.get('name'):
                    names.append({'image': r['image'], 'truth': name, 'said': d['name']})
    f = lambda a, b: round(k[a] / max(k[b], 1), 3)
    return {'known_found': f('known_found', 'known'), 'known_right': f('known_right', 'known'),
            'known_said_unknown': f('known_said_unknown', 'known'),
            'known_wrong_part': f('known_wrong_part', 'known'),
            'unknown_found': f('unknown_found', 'unknown'),
            'unknown_said_unknown': f('unknown_said_unknown', 'unknown_found'),
            'unknown_said_known': f('unknown_said_known', 'unknown_found'),
            'held_out_found': f('held_out_found', 'held_out'),
            'held_out_said_unknown': f('held_out_said_unknown', 'held_out_found'),
            'boxes_on_a_labelled_object': f('boxes_on_object', 'boxes'),
            'counts': dict(k), 'false_known': dict(false_known.most_common(15))}, names


def best_threshold(rows):
    grid = [0.01, 0.02, 0.03] + [round(t, 2) for t in np.arange(0.05, 0.96, 0.05)]
    return max(grid, key=lambda t: counts(rows, t)['f1'])


def score(run, val=None, same=None):
    rows = load(run)
    if same:  # only the photos another run has (e.g. Claude's sample)
        keep = {r['image'] for r in load(same)}
        rows = [r for r in rows if r['image'] in keep]
    thr = best_threshold(load(val)) if val else (1.0 if all(d['conf'] == 1.0 for r in rows for d in r['dets'])
                                                  else 0.25)
    aps = ap50(rows)
    res = {'run': str(run), 'photos': len(rows), 'threshold': thr,
           'mAP50': sum(aps.values()) / len(aps) if aps else None, 'ap50': aps,
           'gather': counts(rows, thr),
           'seconds_per_photo': float(np.median([r.get('seconds', 0) for r in rows])),
           'cost_usd': round(sum(r.get('cost_usd', 0) for r in rows), 4)}
    res['open_world'], names = open_world(rows, thr)
    res['open_world_center'], _ = open_world(rows, thr, match='center')
    if same:
        res['same_as'] = str(same)
    if names and not same:
        (Path(run) / 'names.json').write_text(json.dumps(names, indent=1))
    name = 'metrics.json' if not same else f'metrics_on_{Path(same).name}.json'
    (Path(run) / name).write_text(json.dumps(res, indent=1))
    return res


def show(res):
    g = res['gather']
    print(f"{res['run']}: {res['photos']} photos, mAP50 {res['mAP50']:.3f}, threshold {res['threshold']}, "
          f"count recall {g['recall']:.2f} precision {g['precision']:.2f}, photos all right {g['photos_right']:.2f}, "
          f"{res['seconds_per_photo']:.2f} s/photo, ${res['cost_usd']}")
    o = res['open_world']
    print(f"  open world: known found {o['known_found']:.2f}, named right {o['known_right']:.2f}, "
          f"said unknown {o['known_said_unknown']:.2f}, wrong part {o['known_wrong_part']:.2f} | unknown found "
          f"{o['unknown_found']:.2f}, of those said unknown {o['unknown_said_unknown']:.2f}, "
          f"called a known part {o['unknown_said_known']:.2f} | held-out kinds found {o['held_out_found']:.2f}, "
          f"said unknown {o['held_out_said_unknown']:.2f} | boxes on a labelled object "
          f"{o['boxes_on_a_labelled_object']:.2f}")
    c = res['open_world_center']
    print(f"  centre match: known found {c['known_found']:.2f}, named right {c['known_right']:.2f} | unknown found "
          f"{c['unknown_found']:.2f}, said unknown {c['unknown_said_unknown']:.2f}, called known "
          f"{c['unknown_said_known']:.2f} | held-out found {c['held_out_found']:.2f} | boxes on an object "
          f"{c['boxes_on_a_labelled_object']:.2f}")
    if o['false_known']:
        print('  unknown called known:', ', '.join(f'{k} x{v}' for k, v in list(o['false_known'].items())[:8]))
    for p, v in g['per_part'].items():
        print(f"  {p:15} AP50 {res['ap50'].get(p, 0):.2f}  recall {v['recall']:.2f}  precision {v['precision']:.2f}"
              f"  (n={v['there']})")


if __name__ == '__main__':
    a = sys.argv[1:]
    val = a[a.index('--val') + 1] if '--val' in a else None
    same = a[a.index('--same') + 1] if '--same' in a else None
    show(score(a[0], val, same))
