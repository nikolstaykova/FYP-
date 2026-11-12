# The checker: what the learner has, from photos

**Status:** 5 November 2026. Built and in Parts Quest for Arduino (whole parts list) and LEGO (one gather card at a
time). This file: how the checker works, what a check costs and how to make it cheaper (section 3), and how easily
its models can be swapped (section 4). Choosing the model is in `RECOGNITION.md`.

---

## 1. What is in it

| File | What it does |
|---|---|
| `code/checker/gather.py` (electronics part: `check`) | The rules: match what was seen to the lesson's parts, compare (values, counts), substitutes (a resistor in a range, a board that can stand in), parts the catalogue does not know |
| `code/checker/gather_flow.py` | The Arduino check as the learner gets it: Haiku's first look, close-ups for what it could not settle, Opus once only when Haiku still cannot tell |
| `code/graph/lego_gather.py` (not the checker: part of making a lesson) | Splits a LEGO lesson into gather cards when the lesson is made, stored in the lesson and Neo4j (COVERS): by numbered bag, else about 10 pieces and at most 8 kinds per card, never splitting a sub-build |
| `code/checker/gather.py` (LEGO part: `card_items`, `card_look`, `card_closeup`, `card_result`) | The LEGO card check, in the same module as the electronics check: each of the card's ~10 pieces goes to Haiku with its kind and size ("plate 2x2", "wheel", "minifigure head"); it says there / other colour / wrong piece (and what it is instead) / unsure / not there; close-ups, Opus once for what Haiku still cannot tell; the electronics result shape |
| `code/checker/gather_vlm.py` | The one Claude call the checker uses (photos + text → JSON), with prices |

The flow is the same for both: **first look (Haiku) → questions → close-ups (Haiku) → Opus only for a close-up Haiku
still cannot read.** Both return the same result shape, so the page and Pip use one result screen.

## 2. How the photos go in today

1. The page (camera or upload) scales each photo to **at most 1600 px on the long edge** and saves it as JPEG at
   quality 0.88 (`canvasToPhoto` in `research/recognition/lab/game.html`): a phone photo becomes about 140 KB.
2. **The first look** (electronics `gather_flow.first_look`, LEGO cards `gather.card_look`) is sent at **768 px on the
   long edge, JPEG quality 35** (`gather_vlm.shrink`, `FIRST_EDGE` / `FIRST_QUALITY`; since 12 November 2026, from
   the test in 3.7, see 3.8). **Close-ups and Opus's second look** get the photo unchanged (`gather_vlm.ask`).
3. Claude prices an image by its pixels, not its file size: **⌈width/28⌉ × ⌈height/28⌉ tokens**. Haiku 5.5 is in
   the high-resolution tier (up to 2576 px on the long edge and 4784 tokens per image; anything larger is scaled down
   by the API). A 1600×1200 photo is 58 × 43 = **2,494 tokens**; a 768×576 photo is 28 × 21 = 588.
4. **JPEG quality does not change the price.** It changes only how many bytes are uploaded (speed on a slow phone
   connection), and heavy compression adds artefacts that can hurt the answer.

Prices (per million tokens, read 3 November 2026): Haiku 5.5 $0.10 in / $0.50 out; Opus 5.5 $4 / $20.

## 3. What a check costs, and what changes it (5 November 2026)

### 3.1 The test

`research/recognition/res_test.py` runs the production first look (Haiku through `gather_flow.first_look`, then the
rules) on two sets, at every input setting:

- **Kit photos:** the 10 labelled cases of `kit_test.py` (web photos of whole kits, 600–1280 px; 50 answers with the
  accepted verdicts). Measures **% right**.
- **Your photos:** the distinct big photos taken in Parts Quest (`runs/lab`, 1600 px; 25 part verdicts, no labels).
  Measures **% of verdicts that stay the same as at full size**.
- **Settings:** long edge 1600 (full) / 1280 / 1024 / 768 / 512 / 384 px at JPEG quality 85, and full size at JPEG
  quality 35 and 15. **Full size is run twice**: the difference between the two runs is the model's own noise.

126 checks, about 25¢ in total. Chart: `research/recognition/res_plot.py`.

![Price against quality for every input setting, and where the money goes](research/recognition/figures/checker_cost.png)

| Setting | Image tokens per photo | KB per photo | Cost per check | Kit: % right | Your photos: % same as full |
|---|---|---|---|---|---|
| full size | 1,494 (yours) / 1,219 (kit) | 140 / 221 | 0.210¢ | 98% | 100% (the reference) |
| full size, run 2 | same | same | 0.211¢ | 100% | 92% |
| 1280 px | 1,050 / 1,219 | 106 / 221 | 0.216¢ | 88% | 100% |
| 1024 px | 763 / 1,167 | 85 / 213 | 0.200¢ | 94% | 92% |
| **768 px** | 528 / 667 | 68 / 130 | **0.177¢** | **98%** | **96%** |
| 512 px | 283 / 306 | 46 / 64 | 0.165¢ | 100% | 88% |
| 384 px | 159 / 171 | 28 / 38 | 0.144¢ | 84% | 80% |
| full, JPEG q35 | as full | 54 / 92 | 0.210¢ | 86% | 96% |
| full, JPEG q15 | as full | 35 / 56 | 0.210¢ | 88% | 84% |

(The kit photos are at most 1280 px, so for them "full" and "1280" are the same image.)

### 3.2 What it shows

1. **The answer is the bill.** The model's written answer (the JSON list of every object it sees, about 3,600 output
   tokens) is **86–91% of the cost of a check**. The photo is 9% at full size; the instructions 5%. Making photos
   smaller can never save more than about a tenth.
2. **The model's own noise is large.** The same photos, checked again, scored anywhere from 88% to 100% (full,
   full run 2 and 1280 px are the same kit images). Differences inside that band are not real: 1280 px "losing" to
   768 px is noise.
3. **768 px is as good as full size here and 16% cheaper per check** (0.177¢ against 0.210¢; the image tokens drop
   from about 1,500 to about 530). 512 px still scores well on the kit photos but drifts more on yours (88%).
   **384 px is clearly worse** on both sets: below the noise band.
4. **JPEG compression saves bytes, not money.** q15 cuts the upload from 140 KB to 35 KB at exactly the same price,
   and the answers got worse (84% on your photos). Quality 0.8–0.9 is right.
5. **Per lesson, the checker is cheap either way.** A first look (0.21¢) plus two Haiku close-ups (about 0.05¢
   each) is about 0.3¢; an Opus close-up, when needed, about 1¢. Far inside the €4 lesson limit, whose real cost is the voice tutor.

### 3.3 What to do (in order of savings)

1. **Shorten the answer (the big lever, not yet done).** The first look writes 8 fields for every object on the
   table, the ones the lesson does not need included. Options: drop the fields the rules never use, list objects
   that are not in the lesson by name only, cap the list. Halving the answer would cut a check by about 40%,
   four times more than any image setting.
2. **Send the first look at 768 px on the long edge.** Done 12 November 2026 (3.8), after the ten-run test (3.7).
3. **Keep close-ups at full size.** A close-up exists to read small things (resistor bands, a board's name, how many
   studs). It was not tested at lower sizes and should not be shrunk without a test.
4. **JPEG quality saves no money**, only upload bytes. The first look now uses 35 (3.8); close-ups keep the page's 0.88.

### 3.4 Still to test

- ~~**Repeats**~~: done, ten runs (3.7).
- **Gemini's last 6 runs** when Google's quota allows (3.7 has 4 of 10); it will not change the price ranking.
- **768 px / JPEG 35 in the app**: check a few weeks of real checks (cost log) against the 0.19¢ and 94% expected.
- **The real flow's average price**: first look, Haiku close-ups, Opus only on unreadable close-ups, on photo sets
  with their close-ups, so the price is measured instead of bounded.
- **The answer trim** (3.3.1): same test, shorter output, check that the verdicts hold.
- **Close-ups at lower sizes**, on resistor bands and board names.
- **LEGO cards:** small pieces (1×1 plates, studs) may need more pixels than electronics; same test on gather-card
  photos once there are labelled ones.

### 3.5 Across models, with the Opus fallback paid for (5 November 2026)

`research/recognition/model_cost_test.py`: six models as the first look (Haiku, Sonnet and Opus 5.5; Gemini 3.5
Flash-Lite and 3.8 Flash; NVIDIA Nemotron 3.5 VL) at 1600 / 1024 / 768 / 512 px, on the same 14 photo sets (10
labelled kit cases, 4 of your Parts Quest photo sets). At full size and 768 px the **fallback** is paid for too:
Opus looks again, on the same photos, at the questions the learner would be asked (at most 3, lesson parts only).
That is the worst case: in the app the learner's close-up goes to Haiku first and Opus only when Haiku still cannot
read it. "Your photos" are scored against Opus at full size (no labels). About $6.20 in total. Chart:
`research/recognition/model_cost_plot.py`.

![Price against quality per model with the Opus fallback, and where the money goes](research/recognition/figures/checker_models.png)

| Model | Size | First look | + Opus fallback | Average per check | Fallback ran | Kit right: first → with fallback | Your photos same as Opus: first → with fallback | Seconds |
|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | full | 0.22¢ | 1.88¢ | 2.10¢ | 79% | 88% → 88% | 92% → 92% | 22 |
| Haiku 5.5 | 1024 | 0.21¢ | – | 0.21¢ | – | 84% | 96% | 15 |
| Haiku 5.5 | 768 | 0.20¢ | 1.69¢ | 1.89¢ | 79% | 80% → 90% | 96% → 96% | 20 |
| Haiku 5.5 | 512 | 0.16¢ | – | 0.16¢ | – | 90% | 88% | 12 |
| Sonnet 5.5 | full | 2.58¢ | 2.21¢ | 4.80¢ | 100% | 98% → 100% | 92% → 96% | 18 |
| Sonnet 5.5 | 1024 | 2.45¢ | – | 2.45¢ | – | 86% | 96% | 12 |
| Sonnet 5.5 | 768 | 2.21¢ | 1.82¢ | 4.03¢ | 93% | 84% → 90% | 88% → 92% | 17 |
| Sonnet 5.5 | 512 | 2.09¢ | – | 2.09¢ | – | 86% | 84% | 11 |
| Opus 5.5 | full | 5.43¢ | – | 5.43¢ | – | 100% | 100% | 16 |
| Opus 5.5 | 1024 | 5.11¢ | – | 5.11¢ | – | 98% | 96% | 16 |
| Opus 5.5 | 768 | 5.11¢ | – | 5.11¢ | – | 100% | 92% | 17 |
| Opus 5.5 | 512 | 4.63¢ | – | 4.63¢ | – | 98% | 100% | 16 |
| Gemini 3.5 Flash-Lite | full | 0.16¢ | 1.43¢ | 1.60¢ | 67% | 94% → 94% | 100% → 93% | 41 |
| Gemini 3.5 Flash-Lite | 1024 | 0.16¢ | – | 0.16¢ | – | 88% | 70% | 40 |
| Gemini 3.5 Flash-Lite | 768 | 0.12¢ | 1.22¢ | 1.34¢ | 80% | 93% → 93% | 90% → 80% | 83 |
| Gemini 3.5 Flash-Lite | 512 | 0.18¢ | – | 0.18¢ | – | 100% | 80% | 41 |
| Gemini 3.8 Flash | full | 0.73¢ | 2.58¢ | 3.31¢ | 100% | 91% → 95% | 60% → 80% | 110 |
| Nemotron 3.5 VL (free credits) | full | 0.00¢ | 2.13¢ | 2.13¢ | 79% | 38% → 62% | 72% → 76% | 40 |
| Nemotron 3.5 VL (free credits) | 1024 | 0.00¢ | – | 0.00¢ | – | 56% | 72% | 34 |
| Nemotron 3.5 VL (free credits) | 768 | 0.00¢ | 1.74¢ | 1.74¢ | 79% | 44% → 66% | 84% → 84% | 31 |
| Nemotron 3.5 VL (free credits) | 512 | 0.00¢ | – | 0.00¢ | – | 42% | 76% | 29 |

Gemini was only partly measured: Google refused much of the run (HTTP 503 "high demand" and 429 rate limits on our
key), so Flash-Lite has 4–7 of 14 photo sets per size and 3.8 Flash only 5 at full size. One run per setting: the
noise from 3.2 (88–100% on the same photos) applies.

**What it shows**

1. **The fallback is the bill, not the first look.** With Haiku first, Opus was called in 79% of checks and the
   average price went from **0.2¢ to 1.9¢**: the fallback is about 90% of it. It bought little: kit answers 88% →
   88% at full size, 80% → 90% at 768 px.
2. **Most of that money was wasted.** About two-thirds of the questions sent to Opus were about parts that were
   simply not in the photo ("I can't see an LED"). No model can find a missing part in the same photo; only a new
   photo from the learner can.
3. **No first-look model is cheaper than Haiku.** Gemini 3.5 Flash-Lite looked about the same price here (0.1–0.2¢),
   but 10 runs in 3.7 put it at 0.46–0.56¢, about 2.5× Haiku. It was also slow (40–80 s against Haiku's 12–22 s) and Google refused
   a large part of the requests: not reliable enough for a learner waiting at the table. Sonnet costs 10× Haiku and
   was not better. Nemotron is free (NVIDIA credits) but got 38–56% right, so Opus would be needed almost every time.
4. **Opus alone is the most accurate (98–100%) at 4.6–5.4¢ a check.** That is 2.5× Haiku with the worst-case
   fallback, for clearly better answers. Still far inside the €4 lesson limit.
5. **Image size saves little for every model.** Opus 5.4¢ at full size against 4.6¢ at 512 px; Haiku 0.22¢ against
   0.16¢.

**What to do**

1. **Call Opus only for a close-up Haiku could not read, never for a missing part.** This is what the app already
   does (`server.flow`: a missing part asks the learner for a photo; Opus only after Haiku fails on a close-up),
   and it should stay that way: it turns the 1.9¢ worst case into roughly 0.2¢ + 0.05¢ per close-up + about 1¢ only
   on the rare unreadable close-up.
2. **Keep Haiku as the first look.** Revisit Gemini Flash-Lite when its service is stable (it is the only model at
   Haiku's price that matched it).
3. **Keep "Opus only" as an option** for when certainty matters more than a few cents (about 5¢ a check).
4. Then the answer trim from 3.3, which lowers every model's price.

### 3.6 The whole matrix: photo setting x model (9 November 2026)

Every measured cell of 3.1 and 3.5 in one place (`research/recognition/matrix.py`). JPEG 85 rows are from the model
test (3.5); † marks Haiku cells from the image test (3.1), a separate run. (n/14) = Gemini cells where Google
refused part of the run. "not run" cells were not measured. For Claude, the price of a JPEG 35 or 15 photo is the
same as JPEG 85 at that size (pixels, not bytes, are paid for), so only the quality would change.

**First look: price per check (US cents)**

| Photo setting | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Nemotron 3.5 VL |
|---|---|---|---|---|---|---|
| 1600 px (full), JPEG 85 | 0.22¢ | 2.58¢ | 5.43¢ | 0.16¢ (6/14) | 0.73¢ (5/14) | free |
| 1024 px, JPEG 85 | 0.21¢ | 2.45¢ | 5.11¢ | 0.16¢ (7/14) | not run | free |
| 768 px, JPEG 85 | 0.20¢ | 2.21¢ | 5.11¢ | 0.12¢ (5/14) | not run | free |
| 512 px, JPEG 85 | 0.16¢ | 2.09¢ | 4.63¢ | 0.18¢ (4/14) | not run | free |
| 384 px, JPEG 85 | 0.14¢† | not run | not run | not run | not run | not run |
| 1600 px, JPEG 35 | 0.21¢† | not run | not run | not run | not run | not run |
| 1600 px, JPEG 15 | 0.21¢† | not run | not run | not run | not run | not run |

**First look: kit photos right**

| Photo setting | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Nemotron 3.5 VL |
|---|---|---|---|---|---|---|
| 1600 px (full), JPEG 85 | 88% | 98% | 100% | 94% (6/14) | 91% (5/14) | 38% |
| 1024 px, JPEG 85 | 84% | 86% | 98% | 88% (7/14) | not run | 56% |
| 768 px, JPEG 85 | 80% | 84% | 100% | 93% (5/14) | not run | 44% |
| 512 px, JPEG 85 | 90% | 86% | 98% | 100% (4/14) | not run | 42% |
| 384 px, JPEG 85 | 84%† | not run | not run | not run | not run | not run |
| 1600 px, JPEG 35 | 86%† | not run | not run | not run | not run | not run |
| 1600 px, JPEG 15 | 88%† | not run | not run | not run | not run | not run |

**With the Opus fallback (worst case): average price · kit right · how often Opus was called**

| Photo setting | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Nemotron 3.5 VL |
|---|---|---|---|---|---|---|
| 1600 px (full), JPEG 85 | 2.10¢ · 88% · Opus in 79% | 4.80¢ · 100% · Opus in 100% | no fallback (it is Opus) | 1.60¢ · 94% · Opus in 67% (6/14) | 3.31¢ · 95% · Opus in 100% (5/14) | 2.13¢ · 62% · Opus in 79% |
| 1024 px, JPEG 85 | – | – | no fallback (it is Opus) | – | not run | – |
| 768 px, JPEG 85 | 1.89¢ · 90% · Opus in 79% | 4.03¢ · 90% · Opus in 93% | no fallback (it is Opus) | 1.34¢ · 93% · Opus in 80% (5/14) | not run | 1.74¢ · 66% · Opus in 79% |
| 512 px, JPEG 85 | – | – | no fallback (it is Opus) | – | not run | – |
| 384 px, JPEG 85 | – | not run | not run | not run | not run | not run |
| 1600 px, JPEG 35 | – | not run | not run | not run | not run | not run |
| 1600 px, JPEG 15 | – | not run | not run | not run | not run | not run |

**Answer length (output tokens, the main cost)**

| Photo setting | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Nemotron 3.5 VL |
|---|---|---|---|---|---|---|
| 1600 px (full), JPEG 85 | 3819 | 1997 | 2128 | 357 | 1473 | 3551 |
| 1024 px, JPEG 85 | 3798 | 1963 | 2068 | 377 | not run | 3294 |
| 768 px, JPEG 85 | 3650 | 1840 | 2182 | 253 | not run | 3122 |
| 512 px, JPEG 85 | 2944 | 1802 | 2026 | 479 | not run | 3342 |
| 384 px, JPEG 85 | 2638 | not run | not run | not run | not run | not run |
| 1600 px, JPEG 35 | 3607 | not run | not run | not run | not run | not run |
| 1600 px, JPEG 15 | 3618 | not run | not run | not run | not run | not run |

**Seconds per first look**

| Photo setting | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Nemotron 3.5 VL |
|---|---|---|---|---|---|---|
| 1600 px (full), JPEG 85 | 16 s | 12 s | 16 s | 36 s | 103 s | 32 s |
| 1024 px, JPEG 85 | 15 s | 11 s | 16 s | 40 s | not run | 33 s |
| 768 px, JPEG 85 | 15 s | 11 s | 17 s | 79 s | not run | 25 s |
| 512 px, JPEG 85 | 12 s | 11 s | 16 s | 41 s | not run | 29 s |
| 384 px, JPEG 85 | 11 s | not run | not run | not run | not run | not run |
| 1600 px, JPEG 35 | 15 s | not run | not run | not run | not run | not run |
| 1600 px, JPEG 15 | 15 s | not run | not run | not run | not run | not run |

**Is Gemini cheaper?** These one-run numbers said so (Flash-Lite 0.12–0.18¢, very short answers), but they came
from the few checks Google let through. **With full runs it is not: see 3.7** (Flash-Lite averaged 0.46–0.56¢,
about 2.5× Haiku).

### 3.7 Ten runs: Haiku against Gemini Flash-Lite, every size x JPEG quality (9–10 November 2026)

`research/recognition/repeat_matrix.py`: Haiku 5.5 and Gemini 3.5 Flash-Lite, photos at 1024 / 768 / 512 px x
JPEG 85 / 35 / 15, first look only, 14 photo sets per run. Haiku: all 10 runs (1,260 checks). Gemini: 4 runs (496
checks) before Google stopped it ("You exceeded your current quota", HTTP 429). About $4.90. Error bars and ± are
the 95% confidence interval of the mean over the runs. Chart: `research/recognition/repeat_plot.py`.

![Price, kit accuracy and your-photo accuracy for every size and JPEG quality, Haiku against Gemini](research/recognition/figures/checker_repeats.png)

| Model | Size | JPEG | Runs | Price per check | Kit right (± 95% CI) | Your photos same as Opus (± 95% CI) | Answer tokens | Seconds |
|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 1024 px | 85 | 10 | 0.205¢ | 94% ± 3 | 93% ± 3 | 3608 | 15 |
| Haiku 5.5 | 1024 px | 35 | 10 | 0.207¢ | 87% ± 2 | 93% ± 2 | 3648 | 15 |
| Haiku 5.5 | 1024 px | 15 | 10 | 0.203¢ | 87% ± 2 | 92% ± 3 | 3569 | 15 |
| Haiku 5.5 | 768 px | 85 | 10 | 0.197¢ | 87% ± 2 | 93% ± 5 | 3556 | 15 |
| Haiku 5.5 | 768 px | 35 | 10 | 0.189¢ | 93% ± 4 | 94% ± 4 | 3402 | 14 |
| Haiku 5.5 | 768 px | 15 | 10 | 0.186¢ | 92% ± 4 | 91% ± 2 | 3349 | 19 |
| Haiku 5.5 | 512 px | 85 | 10 | 0.164¢ | 93% ± 3 | 90% ± 3 | 2997 | 12 |
| Haiku 5.5 | 512 px | 35 | 10 | 0.160¢ | 96% ± 2 | 90% ± 2 | 2918 | 12 |
| Haiku 5.5 | 512 px | 15 | 10 | 0.158¢ | 96% ± 2 | 90% ± 2 | 2871 | 12 |
| Gemini 3.5 Flash-Lite | 1024 px | 85 | 4 | 0.537¢ | 86% ± 7 | 83% ± 8 | 1882 | 9 |
| Gemini 3.5 Flash-Lite | 1024 px | 35 | 4 | 0.547¢ | 98% ± 3 | 86% ± 10 | 1923 | 12 |
| Gemini 3.5 Flash-Lite | 1024 px | 15 | 4 | 0.491¢ | 86% ± 2 | 86% ± 4 | 1698 | 6 |
| Gemini 3.5 Flash-Lite | 768 px | 85 | 4 | 0.563¢ | 92% ± 4 | 92% ± 3 | 1987 | 13 |
| Gemini 3.5 Flash-Lite | 768 px | 35 | 4 | 0.548¢ | 92% ± 2 | 95% ± 2 | 1925 | 11 |
| Gemini 3.5 Flash-Lite | 768 px | 15 | 4 | 0.467¢ | 94% ± 2 | 88% ± 3 | 1603 | 14 |
| Gemini 3.5 Flash-Lite | 512 px | 85 | 4 | 0.464¢ | 90% ± 4 | 88% ± 8 | 1588 | 10 |
| Gemini 3.5 Flash-Lite | 512 px | 35 | 4 | 0.490¢ | 94% ± 3 | 83% ± 5 | 1692 | 9 |
| Gemini 3.5 Flash-Lite | 512 px | 15 | 4 | 0.468¢ | 94% ± 3 | 85% ± 13 | 1613 | 17 |

**What it shows**

1. **Haiku is the cheaper model: 0.16–0.21¢ a check against Gemini's 0.46–0.56¢.** Gemini's tokens cost more (3× in,
   5× out) and over full runs its answers were 1,600–2,000 tokens, not the 250–480 of the partial run. The earlier
   "Gemini is a little cheaper" (3.6) was wrong: it came from too few, unrepresentative checks.
2. **Gemini is not more accurate either.** On your photos Haiku is 90–94% at every setting with tight intervals;
   Gemini 83–95% with wide ones (it is less consistent from run to run).
3. **For Haiku, 512 px is the price winner: 0.16¢ (−20% on 1024 px) with 93–96% on the kit photos**, but 90% on
   your photos against 92–94% at 768 and 1024 px. 768 px is the balance: 0.19–0.20¢, 93–94% on your photos.
4. **JPEG quality hardly matters.** No consistent effect at any size, beyond the noise. It does not change the price
   either (pixels are paid for, not bytes). The app uses 35 for the smaller upload (3.8).
5. **Ten runs were needed.** Single runs had swung 10–18 points; with ten, the intervals are ±2–5 points.

**Choice:** Haiku, first look at **768 px** (best on your photos for 0.19¢), or **512 px** if the last 20% of the
first-look price matters more than 3 points on real phone photos. Close-ups stay at full size.

### 3.8 What the app does now, and why (12 November 2026)

**The first look sends every photo at 768 px on the long edge, JPEG quality 35, to Haiku 5.5.** Close-ups and the
Opus second look are unchanged (full photo).

| | Before | Now |
|---|---|---|
| Photo sent to the first look | page's photo, up to 1600 px, JPEG 0.88 | 768 px, JPEG 35 |
| Image tokens, 4:3 photo | 2,494 (1600×1200) | 588 (768×576) |
| Upload per photo (average, test photos) | about 140 KB | about 36 KB (87 KB at JPEG 85) |
| Price of a first look | 0.22¢ (1600 px, 3.6) | **0.19¢** (3.7) |
| Agreement with Opus on your photos (3.7) | not in the 10 runs (1024 px: 93% ± 3) | **94% ± 4** |
| Kit photos right (3.7) | not in the 10 runs (1024 px: 94% ± 3) | 93% ± 4 |

**Why this setting.** It scored best on your own phone photos, the ones the app will really see (94%, the highest
of the 9 Haiku settings), for about 8% less than 1024 px. 512 px is 15% cheaper again (0.16¢) and better on the
clean kit photos, but it is 4 points lower on your photos (90%); real photos are messier (lighting, clutter,
angles), so they decide. The gap between JPEG 35 and 85 at 768 px (94% vs 93%, 93% vs 87% kit) is inside the
noise, so quality 35 is not proven better; it is chosen because it is never worse and makes the upload about 2.4×
smaller than JPEG 85, which helps on a slow phone connection. JPEG 15 was not picked because at 768 px it dipped to
91% on your photos.

**What it changes, per check.** About 0.03¢ (≈ 14%) cheaper per first look than the 1600 px photo sent before, with
4× fewer image tokens. The answer (about 3,400 tokens) is still about 90% of the price, so the next
saving is shortening it (3.3.1).

**Where in the code.**

- `code/checker/gather_vlm.py`: `FIRST_EDGE = 768`, `FIRST_QUALITY = 35`, `shrink(path)` (rotates by EXIF, never
  enlarges, sends the file as it is if Pillow cannot read it).
- `code/checker/gather_flow.py`: `first_look(..., small=True)`. The cost tests pass `small=False` because they size
  the photos themselves (`res_test.py`, `model_cost_test.py`), so their results stay repeatable.
- `code/checker/gather.py`: `card_look(..., small=True)` for the gather card's first look; `card_closeup` passes
  `small=False`.
- Tests: `code/tests/unit/test_shrink.py`.

**Caveats.** The test's "your photos" are 4 photo sets of electronics; LEGO cards were not in it, and 1×1 plates or
studs may need more pixels (3.4). If LEGO first looks come back "unsure" more often than before, raise `FIRST_EDGE`
for LEGO only.

## 4. Can the models be swapped without breaking anything?

**Within Claude: yes, mostly.** **To another provider: not yet, apart from the research scripts.**

| Part | Where the model is set | Swap to another Claude model | Swap to another provider (Gemini, NVIDIA, local) |
|---|---|---|---|
| Arduino check (`gather_flow`) | `FIRST`, `SECOND` constants | Change the string | Not plug-in: `gather_vlm.ask` speaks only to Anthropic |
| LEGO card check (`gather.card_*`) | `FIRST`, `SECOND` constants | Change the string | Same as above |
| Opus "whole look" (`gather.look`, benchmarks, command line) | `model=` argument | Pass it | Through `graph/extract.py`, Anthropic only |
| Lesson building (`graph/…`) | `model=` arguments and defaults per stage | Pass it (aliases opus / sonnet / haiku) | Anthropic only |
| Voice tutor (`tutor/live.py`) | `MODEL = "gemini-3.8-live"`, `VOICE` | n/a | Another Gemini Live model: change the string. Another realtime provider: rewrite the transport (the browser speaks Gemini Live's WebSocket protocol) |
| Free-voice tutor (`live.reply`) | Hardcoded `"claude-haiku-5-5"` in the call | Edit the line | Anthropic only |
| Research benchmarks (`research/recognition/*_bench.py`) | `--model` | Yes | **Yes**: Anthropic, Gemini and NVIDIA behind the same `ask(model, images, text)` |

What is already right: the prompts ask for plain JSON and the code checks it, so any model that returns that JSON
works with the rules; the research scripts already prove the same prompt runs on three providers.

What breaks or goes wrong today when a model is swapped:

1. **Two separate Claude callers** (`checker/gather_vlm.py` and `graph/extract.py`) plus one inline call in
   `live.reply`: three places to change.
2. **Prices are looked up by exact model name.** A model missing from `PRICES` costs **$0 in the logs, silently**,
   so the cost tracking would be wrong without any error.
3. **Provider-specific options** are passed everywhere (`output_config.effort`): another provider has no such field.
4. **The voice tutor is tied to Gemini Live's protocol** (audio formats, tool-call messages, interruptions, session
   resumption).

The fix (not done yet): one small model registry, e.g. `code/models.py`, holding for each model its provider, its
prices and its image tier, and one `ask(role, images, text)` that routes to the right provider (moving the
research adapters in). Each part names a **role** ("check first look", "check close-up", "check second look",
"tutor fallback") and the registry maps roles to models, from one config file or environment variables. A test
then runs every role against a stub model, and an unknown model fails loudly instead of costing $0. The voice
tutor stays its own adapter: a realtime voice API is a different kind of thing from a photo check.
