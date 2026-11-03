"""Run a detector over the ElectroCom61 test (or val) photos and write runs/<name>/preds.jsonl for score.py.

Models:
  yoloworld-s, yoloworld-m, yoloworld-l   YOLO-World v2, open vocabulary: asked for our part names (classes.PROMPTS)
                                          plus generic words (classes.GENERIC) whose boxes count as "unknown"
  owlv2                                   OWLv2 base (Google), open vocabulary, same words
  yolo:<weights.pt>                       a YOLO we trained; classes that are not lesson parts count as "unknown"
Run with the vision environment: ~/.venvs/pinpoint-vision/bin/python bench.py yoloworld-l [--split val] [--limit N]
"""
import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image

from classes import GENERIC, PARTS, PROMPTS, part_of

HERE = Path(__file__).resolve().parent
SPLIT = HERE.parents[1] / 'data/sources/electrocom61/split'
# the 16 part names, then generic words; a box with a generic word is "unknown"
WORDS = [PROMPTS[p] for p in PARTS] + GENERIC
LABELS = PARTS + ['unknown'] * len(GENERIC)
DEVICE = 'mps' if torch.backends.mps.is_available() else 'cpu'


def images(split, limit=None):
    ims = [l for l in (SPLIT / f'{split}.txt').read_text().split('\n') if l]
    return ims[:limit] if limit else ims


class YoloWorld:
    def __init__(self, size):
        from ultralytics import YOLOWorld
        self.m = YOLOWorld(f'yolov8{size}-worldv2.pt')
        self.m.set_classes(WORDS)

    def __call__(self, path):
        r = self.m.predict(path, conf=0.01, device=DEVICE, verbose=False, max_det=100)[0]
        return [{'part': LABELS[int(c)], 'name': WORDS[int(c)], 'conf': float(s), 'box': b.tolist()}
                for b, s, c in zip(r.boxes.xyxyn, r.boxes.conf, r.boxes.cls)]


class Yolo:
    def __init__(self, weights):
        from ultralytics import YOLO
        self.m = YOLO(weights)

    def __call__(self, path):
        r = self.m.predict(path, conf=0.01, device=DEVICE, verbose=False, max_det=100)[0]
        return [{'part': part_of(int(c)) or 'unknown', 'name': self.m.names[int(c)], 'conf': float(s),
                 'box': b.tolist()} for b, s, c in zip(r.boxes.xyxyn, r.boxes.conf, r.boxes.cls)]


class Owlv2:
    NAME = 'google/owlv2-base-patch16-ensemble'

    def __init__(self):
        from transformers import Owlv2ForObjectDetection, Owlv2Processor
        self.proc = Owlv2Processor.from_pretrained(self.NAME)
        self.m = Owlv2ForObjectDetection.from_pretrained(self.NAME).to(DEVICE).eval()
        self.text = [[f'a photo of a {w}' for w in WORDS]]

    @torch.no_grad()
    def __call__(self, path):
        im = Image.open(path).convert('RGB')
        w, h = im.size
        inp = self.proc(text=self.text, images=im, return_tensors='pt').to(DEVICE)
        out = self.m(**inp)
        # OWLv2 pads the photo to a square; ours are already square (640x640)
        side = max(w, h)
        r = self.proc.post_process_object_detection(out, threshold=0.01, target_sizes=torch.tensor([[side, side]]))[0]
        keep = r['scores'].argsort(descending=True)[:100]
        return [{'part': LABELS[int(r['labels'][i])], 'name': WORDS[int(r['labels'][i])], 'conf': float(r['scores'][i]),
                 'box': [float(v) for v in (r['boxes'][i].cpu() / torch.tensor([w, h, w, h])).clamp(0, 1)]}
                for i in keep]


def model(name):
    if name.startswith('yoloworld-'):
        return YoloWorld(name.split('-')[1])
    if name.startswith('yolo:'):
        return Yolo(name[5:])
    if name == 'owlv2':
        return Owlv2()
    raise SystemExit(f'unknown model {name}')


def main():
    a = sys.argv[1:]
    name = a[0]
    split = a[a.index('--split') + 1] if '--split' in a else 'test'
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    tag = a[a.index('--tag') + 1] if '--tag' in a else name.replace('yolo:', 'yolo-').replace('/', '_')
    out = HERE / 'runs' / (tag + ('' if split == 'test' else f'-{split}'))
    out.mkdir(parents=True, exist_ok=True)
    m = model(name)
    ims = images(split, limit)
    m(ims[0])  # warm-up, not timed
    with open(out / 'preds.jsonl', 'w') as f:
        for i, path in enumerate(ims):
            t0 = time.perf_counter()
            dets = m(path)
            f.write(json.dumps({'image': path, 'dets': dets, 'seconds': round(time.perf_counter() - t0, 4)}) + '\n')
            if i % 50 == 0:
                print(f'{name} {split} {i}/{len(ims)}', flush=True)
    (out / 'config.json').write_text(json.dumps({'model': name, 'split': split, 'device': DEVICE,
                                                 'photos': len(ims), 'prompts': PROMPTS}, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()
