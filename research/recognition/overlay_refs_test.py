"""Which board does the Arduino overlay pick? Each reference turned into 6 synthetic phone photos (tilted, turned
0-290 degrees, blurred, darkened) must come back as itself, and the learner's real photos (data/arduino_pins, a
Duemilanove) must never be taken for another board.

    python research/recognition/overlay_refs_test.py
"""
import collections
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from validator import board as b, uno_overlay as u  # noqa: E402

rng = np.random.default_rng(0)


def fake(im, i):
    h, w = im.shape[:2]
    bg = np.full((int(h * 1.6), int(w * 1.6), 3), rng.integers(60, 200, 3), np.uint8)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-0.08, 0.08, (4, 2)) * [w, h] + [w * 0.3, h * 0.3]
    out = cv2.warpPerspective(im, cv2.getPerspectiveTransform(src, dst.astype(np.float32)), bg.shape[1::-1], dst=bg,
                              borderMode=cv2.BORDER_TRANSPARENT)
    R = cv2.getRotationMatrix2D((out.shape[1] / 2, out.shape[0] / 2), [0, 35, 90, 170, 200, 290][i], 1)
    out = cv2.warpAffine(out, R, out.shape[1::-1], borderValue=tuple(int(x) for x in bg[0, 0]))
    out = cv2.GaussianBlur(out, (5, 5), 1.2)
    return cv2.convertScaleAbs(out, alpha=rng.uniform(0.6, 1.1), beta=rng.uniform(-20, 20))


def main():
    for ref in u._load_refs():
        got = []
        for i in range(6):
            r = u.overlay(u.crop(fake(ref["image"], i))[0])
            got.append(r[0]["board"] if r else None)
        print(f"{ref['board']:22} {sum(g == ref['board'] for g in got)}/6  {dict(collections.Counter(got))}")
    photos = sorted((ROOT / "data" / "arduino_pins").glob("*/*.jpg"))
    picks = collections.Counter()
    for p in photos:
        r = u.overlay(u.crop(b.load(str(p)))[0])
        picks[r[0]["board"] if r else None] += 1
    print(f"learner's Duemilanove photos: {len(photos)}  {dict(picks)}")


if __name__ == "__main__":
    main()
