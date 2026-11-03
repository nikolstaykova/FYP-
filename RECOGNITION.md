# Part recognition: step 0 of the phone app

**Status:** 3 November 2026. Scenario fixed (section 1); the parts check is built (`code/checker/gather.py`)
and tested on whole sets from the web (6.5); Claude Opus chosen for the look (section 7); small local VLMs still
running.
**Code:** `research/recognition/` (the comparison). **Data:** `data/sources/electrocom61/`.

---

## 1. The scenario

The learner has a pile of parts and picks an Arduino lesson. They take **a few photos** with the phone and upload
them. The app answers:

1. **What is here?** Every object in the photos, each counted once even if it is in two photos, including parts the
   catalogue does not know yet.
2. **Is this what the lesson needs?** Against the lesson's parts list: have it, missing, or more than needed.
3. **If not, can what you have do the job?** A different board (a Mega or a Nano for an Uno), another resistor value,
   another LED colour, a half-size breadboard. If yes, say what changes (which pins; the sketch rewritten to match).
4. **A part we have no record of:** research it (maker and shop pages), add it to the catalogue, then answer 3 for it.

What this asks of the model:

| Need | Why |
|---|---|
| **Find anything, even parts we do not know yet** | the learner's pile holds parts that are not in the catalogue. The model must still find them, name them in plain words ("relay module", "ESP32 board") and never pass them off as a part it knows |
| **Read the details that decide a substitute** | resistor colour bands (value), the board's printed name, a breadboard's size, an LED's colour, markings on a chip or module |
| **Count once across photos** | the same Arduino in two photos is one Arduino |
| **Say when it cannot tell** | "the bands on this resistor are too small: take a closer photo" is better than a guess |
| Speed and cost | a few photos once per lesson: seconds and a few cents are fine. A live camera is **not** needed |

Because the photos are uploaded, not streamed, a cloud VLM is the natural fit, and a phone-sized detector is not
needed. The live-camera candidates below (open-vocabulary detectors, a fine-tuned YOLO) were dropped on 3 November
for this reason; what they showed is kept in section 6.

## 2. The parts check: how it works

```
photos ──► 1 LOOK (Claude, all photos in one call) ──► inventory: each object once, name, details, count, unsure?
                                                            │
             catalogue (parts.json) ◄── 2 MATCH (code: search + aliases; Claude picks when two fit)
                                                            │
             lesson parts list ──────► 3 COMPARE (code): have · missing · extra
                                                            │
             pins, specs, ranges ────► 4 SUBSTITUTE (code decides, Claude explains): yes + what changes · no + why
                                                            │
             maker / shop pages ─────► 5 RESEARCH unknown parts (ingest_part, part_review) → catalogue → back to 4
```

| Stage | Who | Built on |
|---|---|---|
| 1 Look | Claude (Opus or Sonnet; section 6) | the open-world prompt tested here, plus "read the details" and "count once across photos" |
| 2 Match | code, Claude only when ambiguous | `parts/cards.py` search index and aliases, `parts.json` |
| 3 Compare | code | the lesson's `parts_list` (type, count, value) in `data/lessons/store/<id>/assembled.json` |
| 4 Substitute | code | `metadata.substitutes` (LED any colour, wire any colour or length); the resistor range worked out per lesson; **boards:** every pin the sketch uses (`arduino/pins.links`) must exist on the other board with what the code needs from it (`pins.stand_ins`), then the sketch is rewritten at those places (`pins.rewrite`); logic voltage and libraries checked |
| 5 Research | Claude with web pages, checked by code | `parts/ingest.ingest_part` (card from maker and shop pages, gate checks), `arduino/part_review` |

Every answer says what it rests on (the catalogue card, a pin table, a researched page) so the learner and we can
check it.

## 2b. Choosing the model (the comparison below)

The comparison started for a live camera, so it also tested detectors. The question it answers now: which VLM
finds and names parts best, known and unknown, for the price.

## 3. The dataset: ElectroCom61

[ElectroCom61](https://data.mendeley.com/datasets/6scy6h8sjz/2) ([paper, Data in Brief 2025](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11847280/)):
2,121 photos, 61 kinds of electronic part, boxes in YOLO format, CC BY 4.0. The photos are parts spread on lab
tables in different light, which is close to what the gather step will see.

**Our 16 lesson parts ("known").** 23 of its 61 classes are parts our 114 Arduino lessons use, merged into 16 of our part ids
(`research/recognition/classes.py`): both potentiometer kinds → `potentiometer`; six capacitor classes (electrolytic, ceramic, film, multilayer) → `capacitor`; push switch and tact switch → `pushbutton`; LDR → `photoresistor`; sonar → `ping-sensor`; plus
Arduino Uno, Mega and Nano, breadboard, resistor, LED, buzzer, servo, DC motor, diode, MOSFET. The other **38
classes stand in for parts not in the catalogue yet ("unknown")**: batteries, displays, relay and sensor modules,
ESP32 boards, keypads, inductors, IGBTs, bridge rectifiers, thermistors…

**Not in it:** jumper wires and USB cables, in 105 and 24 of our lessons. They need another source later.

**A new split.** The published split cannot be used as it is:
- LED, buzzer and push switch are in **no** test or validation photo, and Arduino Uno is in one.
- Many photos were taken seconds apart: near copies of one scene.

`make_split.py` groups consecutive photos into bursts (taken within 10 s, or looking alike by a grey-thumbnail
match) and hands whole bursts to train/val/test, so that each lesson part gets about 70/10/20 of its examples. Result:
1,431 train, 229 val, 461 test photos; every lesson part is in test, most with 25 or more examples (fewest:
photoresistor 8, resistor 17; most: capacitor 271).

**Limit, important:** the photographer re-arranged the same few physical parts on the table for hours. No split can
keep the *objects* apart, only the scenes. So a model trained on this data is tested on objects it has seen in
other positions, and **its score here will be higher than on a learner's own kit**. Open-vocabulary models and VLMs
(not trained on it) do not have this advantage. Testing on our own phone photos is the fix; left for later.

## 4. The candidates

| Kind | Model | Size / price | Where it runs | Gives |
|---|---|---|---|---|
| Open-vocabulary detector | YOLO-World v2 S, L | 13 M / 47 M parameters | on the phone (exportable) | boxes + confidence for any typed name |
| Open-vocabulary detector | OWLv2 base (Google) | 155 M | a server (heavy) | boxes + confidence for any typed name |
| Small VLM | Florence-2 large (Microsoft) | 0.77 B | phone possible, Mac | boxes for phrases in a caption |
| Small VLM | Moondream2 | 1.9 B | Mac, a strong phone | `detect()` per name |
| Small VLM | Qwen3-VL 2B, 4B Instruct | 2 B / 4 B | Mac; 2B on a phone with work | JSON list with boxes, follows our instructions |
| Cloud VLM, NVIDIA | Cosmos-Reason2 8B (physical-world reasoning), Nemotron 3 Nano Omni 30B-A3B, Nemotron 3.5 Super VL 120B-A12B | 8 B / 30 B (3 B active) / 120 B (12 B active) | NVIDIA's API (build.nvidia.com) | JSON list with boxes (`nvidia_bench.py`); also the kit test's look (`kit_test.py --model nvidia/<id>`) |
| Cloud VLM, cheap | Claude Haiku | per photo | cloud | JSON list with boxes |
| Cloud VLM, middle | Claude Sonnet | per photo | cloud | JSON list with boxes |
| Cloud VLM, expensive | Claude Opus | per photo | cloud | JSON list with boxes |
| Trained detector | YOLO11 n / s fine-tuned on ElectroCom61 | 2.6 M / 9.4 M | on the phone (Core ML, TFLite), real time | boxes + confidence, 61 classes |

Every VLM gets the same instruction (`classes.ASK`): list **every** object, each with a plain name, one of the 16
catalogue kinds **or "unknown"**, and a box in thousandths of the photo; never force an object into a catalogue kind.
The prompt's example names are things not in the dataset (USB cable, multimeter), so it gives no answers away. The
open-vocabulary detectors get the 16 plain names plus generic words ("electronic component", "electronic module",
"circuit board"); a box with a generic word counts as "unknown". Florence-2 and Moondream2 cannot name what they
find, so they can only say "unknown", not what it is.
Not tested: GPT and Gemini (no keys set up), Qwen3-VL 8B and larger (do not fit this 16 GB Mac), NVIDIA
Cosmos-Reason2 2B locally (gated on Hugging Face: needs an account that accepted NVIDIA's licence; its 8B sibling
is tested through the API instead).

## 5. How they are scored (`score.py`)

- **AP@50 per part and its mean (mAP@50):** the standard detection measure, over all confidence thresholds. VLMs give
  no confidence, so their AP is one point and lower than a detector's at the same quality; compare them on counts.
- **Open world** (every labelled object, all 61 classes, matched one-to-one to a box at IoU ≥ 0.5):
  - known parts: **found**, **named right**, said "unknown", or called **another part**;
  - unknown parts: **found**, then of those found: said **"unknown"** (right) or **called one of our parts** (the
    worst mistake: the learner is told a part is there that is not);
  - the plain names given to unknown parts, judged right / close / wrong by Claude Haiku (`judge.py`; "close" = the
    right family, e.g. "transistor" for an IGBT);
  - boxes on a labelled object: of all boxes, how many are on something labelled. Photos also show pens, staplers
    and tape that nobody labelled, so a VLM that lists everything loses points here without being wrong.
- **Gather counts** (what step 0 needs): per photo and part, the number found against the number there.
  **Recall** (of the parts there, how many found), **precision** (of the parts claimed, how many there) and
  **photos all right** (every part's count right in the photo). Detectors use the confidence threshold with the
  best F1 on the validation photos.
- **Time per photo** (median, after a warm-up) and **cost**.
- The cloud and local VLMs run on every 4th test photo (116 photos) to keep cost and time down; detectors run on all
  461, and are also scored on the same 116 (`score.py --same`) for a like-for-like table.

Run everything from `research/recognition/`: `bench.py` (detectors), `vlm_bench.py` (local VLMs), `claude_bench.py`
(Claude), `score.py` (scores; writes `runs/<name>/metrics.json`).

## 6. Results

### 6.1 First finding: a closed prompt forces unknown parts into known ones

The first Claude runs used a closed prompt ("report only these 16 kinds, ignore everything else"). Scored on the
open-world measures (82 photos Haiku, 63 Sonnet), **every unknown part Claude boxed was called one of our parts**,
never left out: inductor → capacitor (7 times), bridge rectifier → diode (6) or buzzer (4), IGBT → MOSFET (5),
TCRT5000 sensor → MOSFET (4), thermistor → photoresistor, IR sensor module → Arduino Nano. On a learner's table
that means "your capacitor is here" when it is an inductor. With the open prompt, Haiku on one photo named a
keypad, a soil-moisture probe, a rocker switch and a TO-92 transistor and marked each "unknown". These runs are kept
as `runs/old-claude-*` and are not used below.

### 6.2 Claude, three sizes, open-world prompt (116 test photos, 3 November)

| | Haiku (cheap) | Sonnet (middle) | Opus (expensive) |
|---|---:|---:|---:|
| **Gather counts, known parts:** recall / precision | 0.75 / 0.77 | 0.88 / 0.84 | **0.89 / 0.87** |
| Photos with every known part's count right | 53% | 59% | **64%** |
| Known parts pointed at (centre in box) / named right | **79%** / 58% | 57% / 40% | 77% / **65%** |
| Known parts boxed tightly (IoU ≥ 0.5) | **62%** | 36% | 54% |
| **Unknown parts** pointed at (centre) | **83%** | 63% | 81% |
| Unknown parts boxed: said "unknown" / called one of our parts | 95% / 4% | 96% / 4% | **98% / 2%** |
| Held-out kinds pointed at | **82%** | 64% | 76% |
| Names of unknown parts: right / close / wrong | 70 / 17 / 13% | 76 / 16 / 8% | **84 / 9 / 7%** |
| Box mAP@50, known parts (one confidence, so low by design) | 0.34 | 0.18 | 0.35 |
| Time per photo (median, subscription, 4 at a time) | 9.4 s | 6.3 s | 6.5 s |
| Cost for 116 photos (per photo) | **$0.09 (0.08¢)** | $0.89 (0.8¢) | $1.98 (1.7¢) |

What this shows:
- **The open prompt works.** Once "unknown" is allowed, Claude almost never passes an unknown part off as a known one
  (2–4%, against 100% with the closed prompt), and it names them well: Opus 84% right, 93% right or close. The
  mistakes left are near misses: zener diode → diode, IGBT → MOSFET.
- **Claude knows what is on the table better than where.** Counts are good, but its boxes are unreliable *per
  photo*: in most photos they sit on the parts, in some they scatter across the table (checked by drawing them).
  Sonnet scattered most often, which is why its boxes score lowest while its counts are good. For the gather step
  (counts) that is fine; to show the learner *which* object is which, boxes should come from a detector.
- **Opus is best at naming, Haiku is nearly as good at finding for a twentieth of the price.** Haiku finds as many
  objects as Opus but names fewer correctly (unknown parts 70% against 84%; known parts 58% against 65%).
- **Too slow for a live camera** (6–9 s a photo), fine for one "check my parts" photo.

### 6.3 Open-vocabulary detectors, untrained (all 461 test photos)

| | YOLO-World S | YOLO-World L |
|---|---:|---:|
| Box mAP@50, known parts | 0.020 | 0.014 |
| Known parts found (IoU) / named right | 33% / 6% | 36% / 4% |
| Unknown parts boxed that were called one of ours | 66% | 80% |
| Time per photo (M2 GPU) | 0.04 s | 0.11 s |

Fast enough for a live camera, but they do not know electronic parts: confidences never pass 0.21, and YOLO-World L
calls almost anything a "buzzer" (keypad, ESP32, Bluetooth module, 20+ times each). Untrained, they are no use
here. With the upload scenario they were dropped, together with OWLv2 and the fine-tuning (section 1).

### 6.4 Small local VLMs (free, on the Mac)

| | Florence-2 large (0.77 B) |
|---|---:|
| Objects found (centre in box): known / unknown / held-out kinds | 59% / 71% / 84% |
| Known parts named right | 16% |
| Unknown parts boxed that were called one of ours | 83% (keypad, motor driver, LCD → "Arduino Mega") |
| Time per photo (M2 GPU) | 4.0 s, free |

A good **finder** (boxes most objects, even kinds it was never asked for) and a poor **namer**: it can only pick
from the words it is given, so anything not in the list gets the nearest word. Qwen3-VL 2B and 4B and Moondream2
*running*.

### 6.5 The parts check on whole sets from the web (3 November)

The ElectroCom61 photos never show a whole kit, so 9 photos of whole parts sets were taken from the web
(`data/sources/kit_photos/`, `sources.json` gives each photo's page, author and licence: CC photos from Wikimedia
Commons and Openverse, and one ELEGOO product photo for internal testing only). Each case pairs photos with a lesson
and the answers accepted for each part (`research/recognition/kit_test.py`). Claude Opus does the look.

| Case | Photos | Lesson | What it tests | Right |
|---|---|---|---|---|
| ELEGOO kit | 1 crowded product photo, ~60 kinds | Blink, Potentiometer, Servo, Two switches | finding the lesson's parts in a full kit | 5/5, 6/6, 7/7, 6/6 |
| Seeeduino set | 1 | Blink | an Uno clone the catalogue does not know | 4/5 → 5/5 |
| Lab in a tin | 1 | Blink | no board at all | 5/5 |
| Standalone set | **3 photos of one set** | Two switches | counting once across photos; a bare ATmega328 chip | 5/6 → 6/6 |
| Arduino logo | 1 | Blink | a printed logo is not a board | 4/5 → 5/5 |
| Box art | 1 | Blink | drawings of parts are not parts | 5/5 |

**47 of 50 part verdicts right on the first run; 50 of 50 after three fixes** (made from these cases, so the second
figure is not an independent test). **Counted once across photos: right** (the LED, button and crystal in all three
photos of the standalone set were each counted once). The three fixes:
- a value alone ("white") was searched in the catalogue and matched the white LED: values are no longer searched alone;
- the bare ATmega328 chip was offered for the Uno as "maybe": a catalogue part that is not a board now cannot stand
  in for one ("it is a chip, not a board");
- a resistor read as "possibly 1.5k" was refused outright: a reading Claude is not sure of now gives "check, a
  close-up will tell".

What it did well without being told: it said which jumper wires were soldered to other parts and so not free to use,
read the Seeeduino as "an Uno-compatible clone, any version will do", called the 4-leg LED "probably RGB: works as
the lesson's LED using one colour", and asked for close-ups where bands or chip markings were too small.

Time and cost per check (Opus): 7–40 s for the look (the crowded kit photo is the
slowest), 2–14¢. Researching the Seeeduino took 18 s and found no maker page among the approved sites, so it is
offered as "may use, check" with Claude's reason, not checked pin by pin.

### 6.6 Example: one check, as the learner would see it

```
Parts check for blink:               (3 ElectroCom61 photos, Opus, 21 s, 7¢)
↔ Arduino Uno R3 x1: use instead
     can use Arduino Mega 2560 (clone): the same pins, so the sketch does not change; choose this board in the
     Arduino IDE when uploading
✓ Solderless breadboard x1: have
     have 1 half-size solderless breadboard: the lesson uses columns up to 15; a half board has 30
✗ Jumper wire x2: missing
✓ LED x1: have (clear 5 mm LED: the lesson's is red; any colour lights the same way)
? Resistor 220 x1: check
     its value could not be read: a close-up of its colour bands will tell
```

### 6.7 NVIDIA VLMs through NVIDIA's API (116 test photos, 3 November)

| | Claude Opus | Nemotron 3.5 Super VL 120B | Nemotron 3 Nano Omni 30B-A3B |
|---|---:|---:|---:|
| Gather counts, known parts: recall / precision | **0.89 / 0.87** | 0.49 / 0.40 | 0.51 / 0.06 |
| Objects pointed at (centre): known / unknown | 77% / 81% | **97% / 98%** | 93% / 92% |
| Known parts named right (centre) | **65%** | 46% | 43% |
| Unknown parts boxed that were called one of ours | **2%** | 19% | 34% |
| Names of unknown parts: right / close / wrong | **84 / 9 / 7%** | 26 / 22 / 52% | 19 / 29 / 53% |
| Time per photo (median) | 6.5 s | 6.1 s | 3.2 s |

Both had to be run with their "thinking" switched off (Super VL otherwise spent its whole answer budget thinking
and returned nothing). They **find** almost everything, better than Claude, but **name** poorly: inductor →
push button, Bluetooth module → Arduino Nano, IC → resistor; Nano Omni also lists parts that are not there
(precision 0.06). Cosmos-Reason2 8B is listed on the API but not open to a free account ("not found for
account"). Super VL's kit test (6.5) timed out on the first, crowded photo after 15 minutes and was stopped.

### 6.8 "One part is a different model" (the swap test, 14 photos)

The case that matters most: the learner has everything, but one part is a different model. Blink needs an Uno; each
photo holds one board, an Uno (the control) or a Mega, a Nano or an ESP32, among other parts (ElectroCom61 test and
validation photos; `swap_test.py`). Passing a photo = the exact board read (the code matches it to the right
catalogue part) **and** the right verdict (Uno → have; Mega, Nano → use instead, same pins; ESP32 → use instead, pin
13 is D13 and 3.3 V).

| Model | Board read and verdict right | Time per photo | Cost, 14 photos |
|---|---:|---:|---:|
| **Claude Opus** | **14/14** | 12.6 s | $0.52 |
| Claude Sonnet | 12/14 → **13/14** after the matching fix | 7.9 s | $0.22 |
| Claude Haiku | 10/14 → **12/14** after the matching fix | 11.6 s | $0.02 |
| Nemotron 3.5 Super VL | 7/14 | 21.5 s | free credits |
| Nemotron 3 Nano Omni | 5/14 | 6.1 s | free credits |

- **Matching fix:** three misses were ours, not the models': "Arduino Nano clone (mini-USB)", "Arduino Nano-compatible
  board" and "Arduino Nano-style board" were right but the catalogue search missed them. Hedges and looks
  ("clone", "-compatible", "(blue PCB)") are now dropped before searching (`gather.core_name`, unit test).
- **Left after the fix:** Sonnet and Haiku misread ESP32 boards (as an ESP8266, or not as a board).
- **Super VL's mistakes are the dangerous kind:** in 4 photos it called a Mega or a Nano an "Arduino Uno R3", so the
  check said "have" for a part the learner does not have. A model that is wrong *and sure* is worse than one that
  says "check". Nano Omni also called a Nano an Uno once, an ESP32 a Nano, and in 6 photos returned no usable list.

### 6.9 Google Gemini through the Gemini API (3 November)

Picked as the cheap option. Same photos, prompt and code as Claude (`gemini_bench.py`; kit and swap tests dispatch
`gemini-*` models), thinking set to "low", JSON answers. Cost from the token counts the API returns, at the paid
price ($0.30 / $2.50 per 1M tokens in / out for Flash-Lite); the runs themselves were on the free tier.

| | Claude Haiku | **Gemini 3.5 Flash-Lite** | Claude Opus |
|---|---:|---:|---:|
| Gather counts, known parts: recall / precision | 0.75 / 0.77 | 0.76 / 0.80 | **0.89 / 0.87** |
| Photos with every known part's count right | 53% | 52% | **64%** |
| Known parts pointed at (centre) / named right | **79%** / 58% | 57% / 44% | 77% / **65%** |
| Unknown parts boxed: said "unknown" / called one of ours | 95% / 4% | 95% / 4% | **98% / 2%** |
| Names of unknown parts: right / close / wrong | 70 / 17 / 13% | 67 / 17 / 17% | **84 / 9 / 7%** |
| Swap test (6.8): board read and verdict right | 12/14 | 12/14 | **14/14** |
| Kit test (6.5), 50 verdicts | not run | 44 → **47/50** after a fix | 47 → 50/50 |
| Time per photo (median) | 9.4 s | **2.3 s** | 6.5 s |
| Cost per photo (116 photos) | 0.08¢ | 0.12¢ | 1.7¢ |
| Cost per kit check (1–3 photos) | — | **0.1–1.3¢** | 2–14¢ |

- **Flash-Lite is about Haiku's level, three to four times faster.** It counts and names like Haiku, says "unknown"
  as reliably, and passes the same 12 of 14 swap photos. Both misses are ESP32 boards (read as "ESP8266 development
  board" and "USB interface board"); the verdicts were "check" and "missing", not a false "have". It never called a
  Mega or a Nano an Uno.
- **It points at fewer objects** (57% of known parts against 79% for Haiku) and its boxes are looser, so boxes for
  the learner still have to come from a detector.
- **Kit test misses:** jumper wire bundles counted as one wire (2 × "bundle" against 7 wires needed), and once a
  resistor offered as "use instead" instead of "check". The answers also changed between two runs at temperature 0
  (44 then 47), so a single run is a rough figure.
- **A bug of ours, found by this run:** "Seeeduino" matched `seeeduino-lotus` in the wider parts store, which has no
  catalogue card, and the check refused it as "not a board". A board is now refused only when the catalogue knows it
  is not one; otherwise it is "may use, check" (unit test added).
- **Not finished:** Gemini Robotics-ER 2 stopped after 20 photos (the free tier allows 20 requests a day for it) and
  Gemini 3.8 Flash returned "high demand" (503) errors and timeouts all run. Gemini Pro has no free tier.
- **For real users:** the free tier lets Google use the requests to improve its products; learners' photos should
  go through the paid tier, where they are not.

## 7. Decision (3 November, to confirm when the local VLMs finish)

- **The look: Claude Opus**, all photos in one call. Best at naming (84% of unknown parts named right), at reading
  details and at saying what it cannot tell; 2–14¢ and 7–40 s a check, fine for a few uploaded photos once per
  lesson. Haiku finds as much for a twentieth of the price but names less well: a fallback if cost matters.
- **The cheap option: Gemini 3.5 Flash-Lite** (6.9): Haiku's accuracy at 2–3 s a photo and 0.1–1.3¢ a check. The
  plan to test: Flash-Lite looks first, and only objects it is unsure of, or boards it cannot name exactly, go to
  Opus. Most checks would then cost about 1¢.
- **Everything after the look is code** (match, compare, substitute), so the verdicts rest on the catalogue, the pin
  tables and the lesson's own circuit, not on the model's opinion. `code/checker/gather.py`, 10 unit tests.
- **Not used:** untrained detectors (do not know electronic parts), Florence-2 (finds but cannot name), the NVIDIA
  VLMs (find well, name poorly; Super VL calls other boards an Uno, 7/14 on the swap test).
- **Swap test (6.8):** Opus read every board and gave every verdict right (14/14); Sonnet 13/14 and Haiku 12/14
  after the matching fix.

**Next:**
1. Our own photos of a real kit (phone, normal light) as an independent test.
2. Research that works for boards like the Seeeduino: allow maker sites (Seeed) and read a board's pin table into
   the catalogue, so a clone is checked pin by pin instead of "may use, check".
3. The phone side: upload screen, the report, and "retake" prompts that open the camera on the part named.
