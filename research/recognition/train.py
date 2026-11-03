"""Transfer learning for the open world: fine-tune YOLO11 (COCO-pretrained) on ElectroCom61 with 17 classes:
our 16 lesson parts + "other part" (every other ElectroCom61 kind, merged).

The HELD_OUT kinds (classes.HELD_OUT) have their boxes REMOVED from the training and validation labels: the model
never sees them labelled, as with a learner's part nobody has catalogued. The test labels are untouched, so
score.py shows whether it still boxes them as "other part" or calls them one of our parts.

Writes the dataset to data/sources/electrocom61/open17/ (images are links), trains into runs/train/<name>.
Run: ~/.venvs/pinpoint-vision/bin/python train.py yolo11n [--epochs 60] [--prepare-only]
Then: bench.py yolo:runs/train/<name>/weights/best.pt --tag ft-<name>   (val and test)
"""
import json
import os
import sys
from pathlib import Path

from classes import HELD_OUT, NAMES, PARTS, part_of

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'data/sources/electrocom61'
OUT = SRC / 'open17'
CLASSES = PARTS + ['other part']


def new_class(c):
    """17-class id for an ElectroCom61 class id, or None when its boxes are removed (held out)."""
    if NAMES[c] in HELD_OUT:
        return None
    p = part_of(c)
    return PARTS.index(p) if p else len(PARTS)


def prepare():
    counts = {}
    for split in ('train', 'val', 'test'):
        ims = [Path(l) for l in (SRC / 'split' / f'{split}.txt').read_text().split('\n') if l]
        (OUT / split / 'images').mkdir(parents=True, exist_ok=True)
        (OUT / split / 'labels').mkdir(parents=True, exist_ok=True)
        removed = 0
        for im in ims:
            link = OUT / split / 'images' / im.name
            if not link.exists():
                os.symlink(im, link)
            lines = []
            for line in open(str(im).replace('/images/', '/labels/')[:-4] + '.txt'):
                f = line.split()
                if not f:
                    continue
                c = new_class(int(f[0]))
                # the test labels keep held-out boxes (as "other part") so the scorer can see them
                if c is None and split != 'test':
                    removed += 1
                    continue
                lines.append(' '.join([str(len(PARTS) if c is None else c)] + f[1:5]))
            (OUT / split / 'labels' / (im.stem + '.txt')).write_text('\n'.join(lines) + ('\n' if lines else ''))
        counts[split] = {'photos': len(ims), 'held_out_boxes_removed': removed}
    (OUT / 'data.yaml').write_text(f"path: {OUT}\ntrain: train/images\nval: val/images\ntest: test/images\n"
                                   f"nc: {len(CLASSES)}\nnames: {json.dumps(CLASSES)}\n")
    print(json.dumps(counts))


def main():
    a = sys.argv[1:]
    model = a[0] if a and not a[0].startswith('--') else 'yolo11n'
    epochs = int(a[a.index('--epochs') + 1]) if '--epochs' in a else 60
    prepare()
    if '--prepare-only' in a:
        return
    from ultralytics import YOLO
    YOLO(f'{model}.pt').train(data=str(OUT / 'data.yaml'), epochs=epochs, imgsz=640, batch=16, device='mps',
                              project=str(HERE / 'runs/train'), name=model, exist_ok=True, patience=15,
                              workers=4, seed=0, plots=True)


if __name__ == '__main__':
    main()
