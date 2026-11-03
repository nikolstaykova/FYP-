"""Small open VLMs as recognisers, run locally on the Mac (free): the same photos as the Claude runs (every 4th
test photo) and, where the model takes instructions, the same words (classes.ASK). Writes runs/<name>/preds.jsonl.

Models:
  qwen3vl-2b, qwen3vl-4b   Qwen3-VL Instruct (Oct 2025): answers JSON with boxes in thousandths, like Claude
  cosmos-reason2-2b        NVIDIA Cosmos-Reason2 2B (Dec 2025, physical-world reasoning, built on Qwen3-VL)
  florence2-large          Florence-2 large (0.77 B): phrase grounding with all part names + generic words
  moondream2               Moondream2 (1.9 B): its detect() asked once per part name and generic word
Florence-2 and Moondream2 cannot name what they find, so their "unknown" boxes carry only the generic word.
VLMs give no confidence, so every box has conf 1.0 (score.py then counts every box).
Run: ~/.venvs/pinpoint-vision/bin/python vlm_bench.py qwen3vl-2b [--every 4] [--limit N]
"""
import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image

from classes import GENERIC, JSON_ASK, PARTS, PROMPTS, parse_json_list

HERE = Path(__file__).resolve().parent
SPLIT = HERE.parents[1] / 'data/sources/electrocom61/split'
DEVICE = 'mps' if torch.backends.mps.is_available() else 'cpu'
class Qwen3VL:
    def __init__(self, size, name=None):
        from transformers import AutoModelForImageTextToText, AutoProcessor
        name = name or f'Qwen/Qwen3-VL-{size.upper()}-Instruct'
        self.proc = AutoProcessor.from_pretrained(name)
        self.m = AutoModelForImageTextToText.from_pretrained(name, dtype=torch.bfloat16).to(DEVICE).eval()

    @torch.no_grad()
    def __call__(self, path):
        msgs = [{'role': 'user', 'content': [{'type': 'image', 'image': str(path)}, {'type': 'text', 'text': JSON_ASK}]}]
        inp = self.proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True,
                                            return_tensors='pt').to(DEVICE)
        gen = self.m.generate(**inp, max_new_tokens=2048, do_sample=False)
        text = self.proc.batch_decode(gen[:, inp['input_ids'].shape[1]:], skip_special_tokens=True)[0]
        return parse_json_list(text), text


class Florence2:
    NAME = 'florence-community/Florence-2-large'
    TASK = '<CAPTION_TO_PHRASE_GROUNDING>'

    def __init__(self):
        from transformers import AutoProcessor, Florence2ForConditionalGeneration
        self.proc = AutoProcessor.from_pretrained(self.NAME)
        self.m = Florence2ForConditionalGeneration.from_pretrained(self.NAME, dtype=torch.float16).to(DEVICE).eval()
        self.by_phrase = {PROMPTS[p].lower(): p for p in PARTS} | {g: 'unknown' for g in GENERIC}

    def part(self, phrase):
        phrase = phrase.lower().strip()
        if phrase in self.by_phrase:
            return self.by_phrase[phrase]
        hits = [p for k, p in self.by_phrase.items() if k in phrase or phrase in k]
        return hits[0] if len(hits) == 1 else None

    @torch.no_grad()
    def __call__(self, path):
        im = Image.open(path).convert('RGB')
        w, h = im.size
        text = self.TASK + ', '.join([PROMPTS[p] for p in PARTS] + GENERIC)
        inp = self.proc(text=text, images=im, return_tensors='pt').to(DEVICE, torch.float16)
        gen = self.m.generate(input_ids=inp['input_ids'], pixel_values=inp['pixel_values'], max_new_tokens=1024,
                              num_beams=3, do_sample=False)
        raw = self.proc.batch_decode(gen, skip_special_tokens=False)[0]
        res = self.proc.post_process_generation(raw, task=self.TASK, image_size=(w, h))[self.TASK]
        out = []
        for box, label in zip(res['bboxes'], res['labels']):
            p = self.part(label)
            if p:
                out.append({'part': p, 'name': label, 'conf': 1.0,
                            'box': [box[0] / w, box[1] / h, box[2] / w, box[3] / h]})
        return out, raw


class Moondream2:
    def __init__(self):
        from transformers import AutoModelForCausalLM
        self.m = AutoModelForCausalLM.from_pretrained('vikhyatk/moondream2', revision='2025-06-21',
                                                      trust_remote_code=True, device_map={'': DEVICE})

    def __call__(self, path):
        im = Image.open(path).convert('RGB')
        out = []
        for p, word in [(p, PROMPTS[p]) for p in PARTS] + [('unknown', g) for g in GENERIC]:
            for o in self.m.detect(im, word)['objects']:
                out.append({'part': p, 'name': word, 'conf': 1.0,
                            'box': [o['x_min'], o['y_min'], o['x_max'], o['y_max']]})
        return out, ''


def model(name):
    if name.startswith('qwen3vl-'):
        return Qwen3VL(name.split('-')[1])
    if name == 'cosmos-reason2-2b':  # NVIDIA, built on Qwen3-VL: same loader
        return Qwen3VL('2b', 'nvidia/Cosmos-Reason2-2B')
    if name == 'florence2-large':
        return Florence2()
    if name == 'moondream2':
        return Moondream2()
    raise SystemExit(f'unknown model {name}')


def main():
    a = sys.argv[1:]
    name = a[0]
    every = int(a[a.index('--every') + 1]) if '--every' in a else 4
    limit = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    ims = [l for l in (SPLIT / 'test.txt').read_text().split('\n') if l][::every][:limit]
    out = HERE / 'runs' / name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    m = model(name)
    load_s = time.perf_counter() - t0
    m(ims[0])  # warm-up, not timed
    with open(out / 'preds.jsonl', 'w') as f:
        for i, path in enumerate(ims):
            t0 = time.perf_counter()
            dets, raw = m(path)
            f.write(json.dumps({'image': path, 'dets': dets, 'seconds': round(time.perf_counter() - t0, 3),
                                'raw': raw[:3000]}) + '\n')
            f.flush()
            if i % 10 == 0:
                print(f'{name} {i}/{len(ims)} {len(dets)} boxes', flush=True)
    (out / 'config.json').write_text(json.dumps({'model': name, 'device': DEVICE, 'every': every,
                                                 'photos': len(ims), 'load_seconds': round(load_s, 1),
                                                 'prompt': JSON_ASK}, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()
