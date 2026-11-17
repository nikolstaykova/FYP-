# Reading the build from photos: what went wrong, and tuning it on labelled photos

*Started 17 November 2026.* This file covers the photo checks in the app: where a wire end is on the breadboard
(the step check, `code/validator/arduino.py`) and a resistor's value (`code/gather/resistor.py`). It records every
problem we have had with real photos so far, the labelled photo set we built to measure them, the first scores
(the model as it is against our pipeline) and what to change next. See CHECKER.md for the parts check's costs.

---

## 1. The problems with photos so far (12–17 November)

What the learner saw, why it happened, and what was done. Ordered by when it came up.

| # | What happened | Why | What we did |
|---|---|---|---|
| 1 | The step check read a leg **one column off with confidence** (Haiku) | Counting tiny holes in a whole-room photo | Opus first for step checks while testing (15 Nov) |
| 2 | Whole photo too small to read the holes | The board is a small part of a 12 MP photo, then shrunk for the model | **Crop and zoom**: Haiku finds a box, code cuts it from the *full-size* photo, enlarges and sharpens it. Legs right: Haiku 60→80%, Opus 50→90% (16 Nov, `step_crop.py`) |
| 3 | Blurry, too far, too slanted photos were sent anyway | No check before the model | **Free quality gate** (`validator/board.py`, OpenCV): no board / too far / slanted / blurry → "take it again, and how" (17 Nov) |
| 4 | Read **column 9, the wire was in 10**; the learner said so and it **didn't correct** | Printed numbers sit a little off their columns in a tilted photo; the correction only worked for "unsure" legs | The learner can correct **any** reading (Pip's `tell_places` for every verdict; "Not right? Tell me where" in the app, pre-filled) |
| 5 | Hard to line the board up in the camera | No guide; the phone's own camera app | The app's own camera **full screen** with an **outline** of the board (rails, middle gap), full/half board |
| 6 | Outline too small; **Arduino and board didn't both fit** | One outline for every step | Bigger outline; the Arduino's place drawn beside the board when the step wires to it |
| 7 | **Auto line-up caught the Arduino but not the board, or the other way round** ("Move right" for ever) | The live check wanted the *board centred*, impossible with the Arduino beside it; it couldn't see the Arduino at all; the hole grid placed only ~60 of ~1000 holes on real photos | Live check rewritten: holes found by spacing (no grid), the **Arduino found by its blue board** (HSV, shape checks; not fooled by jeans), centring only when there is no Arduino, a "soft" OK after 4 frames |
| 8 | Arduino close-up: "Arduino not visible in this cropped photo" | One crop for the board only | **One photo, split**: Haiku gives a board box *and* an Arduino-header box; the model gets board close-up + Arduino close-up + whole photo; the close-ups are kept with each check |
| 9 | Read **pin 11 / column 11; the wire was in 13** | The wire's **black plastic connector covers the hole**; the model places the connector, not the metal pin | Not fixed yet: measured below (§4.2), next steps in §5 |
| 10 | Resistor value wrong (720 for 270, 2.7k) | Models misread band order and the multiplier | **Code finds the bands**, the model only names numbered colours, code works out the value: 5/7 right, 0 wrong (before 3/6 right, rest wrong). Needs **white paper**: on wood or yellow it can't find the body |
| 11 | (Found today) **The board's numbers start at 0**, and the **bottom half is numbered backwards** (60→0) | This board's print; our prompt says "1, 5, 10, 15…" | Measured below; prompt fix is step 1 in §5 |
| 12 | (Found today) **Close-up came out sideways** (IMG_2641) | iPhone photos taken **looking straight down** get an unreliable rotation tag: 7 of 21 say "turned 90°", 5 say "upside down". The model is shown the board on its side | Next: turn the board upright with code before the model (§5) |
| 13 | (Found today) "Top half / bottom half" is ambiguous when the **board is upside down** | Top in the photo is the board's bottom half | Score the column first, the half separately; the row letters (a–e vs f–j) say which half |

---

## 2. The labelled photo set

**Wires, bare breadboard** (17 Nov): 28 phone photos of one or two jumper wires, one end pushed in, the other loose.
6 skipped (couldn't tell) and deleted, **21 labelled**. Some photos have two wires and only one end labelled; only
labelled ends are scored.

- Labelling: a click-to-label page (click the end, type the column as printed on that half, pick the half; row letter
  optional). Labels in `data/wires/board/labels.json` with where each end is in the photo (x, y).
- Photos: `data/wires/_inbox/` (HEIC), JPEGs in `data/wires/board/`. `data/` is git-ignored: photos stay on this Mac.
- Mix: white paper and wood; sun and shade; straight and tilted; board upright, sideways (by tag) and upside down;
  columns from 1 to 60, both halves.
- Caveat: the labels were read from the photos by the person who placed the wires. A label can be wrong too; a
  disagreement is checked by eye before it counts as a model error.

**Resistors**: 23 photos of the learner's 220 Ω in `data/resistors/220/` (not scored yet). Other values from Wikimedia
Commons ("Resistors by value", free licences, credits kept) into `data/resistors_web/` (download is rate-limited,
slow).

**Lesson-step wires** (`data/wires/<step>_<places>/`, e.g. `step3_pin13_c10t`): the format is ready, no photos yet.

---

## 3. How it is measured

| Script | What it scores |
|---|---|
| `research/recognition/wire_board_eval.py` | Wire ends on a bare board against the clicked labels |
| `research/recognition/wire_eval.py` | The full step check (`arduino.check`) on lesson setups |
| `research/recognition/resistor_eval.py` | The resistor reader; `--free` runs only the code stages |

- **Raw** (`--raw`): the model as it is: the whole photo (sized as the API takes it, 1600 px) and a plain question
  ("Where is each jumper-wire end plugged into this breadboard? Column and half"). No crop, no explanation.
- **Pipeline** (default): what the app does: Haiku finds the board, code cuts it from the full-size photo, enlarges
  and sharpens it; the model gets the close-up + the whole photo, with the step check's own breadboard explanation
  (`arduino.LOOK`), and is told to read the number row of the half the end is in and count from the nearest number.
- Scores: **column right** (the main one), column **and** half right, **one column off**.
- Each run writes `research/recognition/runs/wires_board/<time>/`: `results.json` and a page with every photo, the
  close-up and the model's own reason.
- `--model` picks the model (any Claude model now; others need a small connector in `gather_vlm.ask`).
- Tune/test split fixed by file name (~70/30). The first runs below are on **all 21** (nothing tuned yet: the
  baseline). From here, changes are judged on the tune set and the test set is run once at the end.

---

## 4. First results (17 November, all 21 photos)

### 4.1 The model as it is against our pipeline

| Model | As it is (whole photo, plain question) | Our pipeline (close-up + explanation) |
|---|---|---|
| **Opus 5.5** | 14/21 columns right (67%), 7 one column off · $0.41 | **18/21 (86%)**, 3 one column off · $0.74 |
| **Haiku 5.5** | 12/21 (57%), 7 one column off (half wrong in 3 more) · $0.015 | 11/21 (52%), 6 one column off · $0.04 |

- With Opus, the pipeline takes it from 67% to **86%**. Every miss in either version is one column off: it never
  guesses wildly, it miscounts by one.
- With Haiku, the crop doesn't help: it is the reading, not the picture, that fails. Haiku first is not good enough
  for wire positions yet; keep Opus for step checks.

### 4.2 Why it misses: the model looks at the coloured connector, not the tip

Without the pipeline, Opus's own reasons show it places **the black plastic connector** (or the wire's colour),
not where the **metal pin** goes in:

> "The black connector housing of the grey wire sits in the upper terminal strip, just right of the '45' label …
> roughly column 46. The column could be off by one because the housing hides the exact hole." (true: 45)

> "The red wire's black connector sits in the top half, between the printed column labels 35 and 40 and slightly
> closer to 40, which is about column 38." (true: 37)

> "It appears tilted, so the pin is likely at column 1, though it could be column 0 or 2." (true: 2)

The connector is about 2.5 mm wide and sits over the hole and its neighbour; seen at an angle it covers the next
column. The model also **snaps to a printed number** ("directly above the '50' column marking": true 49; "right above
the partly hidden '45' label": true 44).

The pipeline's explanation ("count holes from the nearest printed number") fixes most of these with Opus. The three
it still misses:

| Photo | True | Read | Why |
|---|---|---|---|
| IMG_2641 | column 7 | 6 | **Close-up sideways** (rotation tag, problem 12) |
| IMG_2645 | column 1 | 2 | Next to the "0": our prompt says numbers start at 1 (problem 11) |
| IMG_2651 | column 12 | 11 | Connector covering the hole; counted "one right of 10" |

### 4.3 Other findings

- **Half (top/bottom)**: Opus as it is gets the half right whenever it gets the column; with the pipeline it puts one
  end in the wrong half (IMG_2646, column 60 at the very end of the board). Haiku as it is puts 3 ends in the wrong
  half (the upside-down boards). The row letter (a–e / f–j) is the reliable way to tell the half.
- **Cost per photo**: Opus pipeline ≈ 3.5¢ (the close-up adds an image), Opus as it is ≈ 2¢, Haiku < 0.2¢.

---

## 5. What to change next (one at a time, each measured on the tune set)

1. **Board numbering**: the explanation says numbers start at 1 and run the same way on both halves. Say instead: the
   first column may be labelled 0 or 1, and the two halves may be numbered from opposite ends; read the number row of
   that half. (Targets IMG_2645-type misses.)
2. **Look for the pin, not the connector**: tell the model the black plastic connector is wider than the hole and
   hides it; the pin is at the connector's centre where it meets the board, and the wire leaves from its top. Ask for
   the columns on both sides of the connector before choosing. (Targets the connector misses.)
3. **Upright before reading**: ignore the phone's rotation tag for top-down photos; turn the image with code so the
   board's long side is horizontal (the hole grid gives the angle) and the numbers read upright (the + / − rail
   colours tell which way up). The close-up then always looks the same. (Targets IMG_2641; also the half confusion.)
4. **Mark the end, then count**: code finds the connector (dark blob at the end of a coloured wire) and the hole grid,
   draws numbered ticks on the columns near it in the close-up, so the model reads a tick number instead of counting
   holes. The same idea that worked for resistor bands.
5. **More photos**: 21 is a start. Aim for ~150: both wire colours, connectors at many angles, the lesson setups
   (`data/wires/step3_…`) with the Arduino in the photo.
6. Re-run Haiku after each change: if it reaches Opus's score, step checks go back to Haiku first (cheaper, faster).
7. Then the test set, once, for the numbers in the report.

The same photos can later score other models (`--model`; an open model such as Kimi, Llama or Gemma through a
connector): the photos, labels, crop and rules carry over; only prompt wording may need re-checking.

---

## 6. How to run

```bash
# wire ends on a bare board
python research/recognition/wire_board_eval.py --raw --model claude-opus-5-5   # the model as it is
python research/recognition/wire_board_eval.py --model claude-opus-5-5         # our pipeline (tune set by default)
python research/recognition/wire_board_eval.py --set test                      # once, at the end

# resistors
python research/recognition/resistor_eval.py --free                            # code stages only, free
python research/recognition/resistor_eval.py                                   # with the models
```

Use `.venv-research/bin/python`. Results: `research/recognition/runs/…/index.html`.

---

## 7. Geometry: code counts the columns (17 November, later)

The holes form an exact grid, so code can do the counting the models get wrong. `validator/board.py` already finds
the holes, works out the grid and fits a homography (the board warped flat). New in
`research/recognition/wire_geometry.py`:

- **The two halves** are the two 5-row blocks with the most holes (the printed numbers' row is left out).
- **The board's end**: the board has 65 hole columns; the 65 with the most holes are the board (stray blobs on the
  paper past the ends are left out).
- **This board's numbers**: printed number = hole column from the end − 3 (top half, left to right; bottom half,
  right to left). In the straightened image the upper half always counts up left to right and the lower half right
  to left, *whichever way up the photo was taken*, so the column number needs no "which way up" at all.
- **Which way up** (only for top/bottom half): on an upright board each rail has its blue line above its red one.
- Fixed in `board.py` on the way: a board standing upright in the photo found "up" and "down" as its two grid
  directions (angles compared mod 360 instead of mod 180); a grid could come out mirrored (a photo never is).
  All 173 tests pass.

### 7.1 Geometry alone (no model, free, ~1 s a photo)

Where the learner clicked the wire end, put through the grid: **18/21 columns right**. The 3 misses are clicks
between two holes (0.3–0.5 of a column off a hole) and one sideways photo.

### 7.2 Geometry + model ("hybrid")

Code straightens the board and writes the true number on **every column** in yellow (upper half's numbers above it,
lower half's below); the model only finds the wire end and reads the yellow number (`wire_board_eval.py --hybrid`).

| Model | As it is | Pipeline (crop) | **Hybrid (geometry + model)** |
|---|---|---|---|
| Opus 5.5 | 14/21 · $0.41 | 18/21 · $0.74 | **17/21 · $0.38** |
| Haiku 5.5 | 12/21 | 11/21 | 11/21 · $0.015 |

- Hybrid Opus is as good as the pipeline (17 vs 18, within one photo) at **half the cost**: one straightened image
  instead of a close-up plus the whole photo, and no Haiku box.
- Haiku is still at ~half right whatever it is shown: it reads the label of the connector's *middle*.

### 7.3 What is still wrong (looked at by eye)

1. **The model reads the connector's middle, not the pin.** IMG_2660: connector over 12–13, wire leaves to the lower
   right, so the pin is at the upper-left end: 13 (label right, model 12). IMG_2659 the same (49, model 50).
   The pin is at the end of the connector **away from where the wire leaves it**.
2. **Anchoring off by one on some photos.** IMG_2640: the yellow 46 sits over the printed 45 in the top half (the
   bottom half lines up). Counting from the board's end is fragile when the end column is in shadow or the fit is
   slightly off; the printed numbers are a second anchor.
3. A few labels may be off by one themselves (clicks between holes); they were read from the photos.

### 7.4 Next

1. **Code finds the pin**: the connector is a dark, elongated blob in the straightened image; the wire (coloured)
   leaves one end; the pin is the other end. Its column comes straight from the grid. The model then only confirms
   ("is the connector at the yellow 13?") or handles what code can't find.
2. **Anchor to the printed numbers too**: check that yellow 5, 10, 15… sit under the printed 5, 10, 15 (one cheap
   Haiku look or template matching); shift by one when they don't.
3. Then the full pipeline in the app: geometry first, the model's crop as the fallback when no grid is found.

---

## 8. The pin rule, geometry + pipeline, and code finding the connector (17 November, later)

### 8.1 One sentence that helps every version: where the pin is

"The metal pin is at the connector's end **away from where the wire leaves it**, at that end's middle." Added to the
prompt (`--pin-rule`), all on the same 21 photos:

| Opus 5.5 | Without the rule | With the rule |
|---|---|---|
| Crop pipeline | 18/21 · $0.74 | **19/21** · $0.70 |
| Geometry + model (numbered board) | 17/21 · $0.38 | **19/21 · $0.39** |
| Geometry + pipeline in one look (numbered board + crop + photo) | — | **19/21** · $0.64 |

| Haiku 5.5 | Without the rule | With the rule |
|---|---|---|
| Crop pipeline | 11/21 | 16/21 · $0.04 |
| Geometry + model | 11/21 | 17/21 · $0.015 |
| Geometry + pipeline in one look | — | **18/21** · $0.036 |

- The rule is the biggest single gain (it is exactly the "looks at the connector, not the tip" problem).
- Geometry gives the same Opus score at half the price, and lifts Haiku most (11 → 17–18 of 21).
- Opus pipeline and Opus geometry make **different** mistakes: they agree on 16/21 (15 right), and where they
  disagree one of them is always right.

### 8.2 Code finds the connector (no model)

`wire_geometry.connectors`: on the straightened board, dark blobs bigger than a hole (gaps from the glossy top
closed first). Found on 18/21 photos. Which point of it is the pin?

| Point used | Columns right (of 21) |
|---|---|
| Middle of the black blob | 12 |
| End away from the wire | 12 |
| **Base** (camera geometry: the connector stands up, so its top leans away from the point under the camera; the base is the blob's end nearest the photo's centre, half a width in) | **13** |

On its own the code is not good enough (it misses 3 connectors, takes another dark blob once, and is one column out
on ~4). As a **second opinion** it is very useful:

| Model's answer and code's answer (base or middle) … | agree | of which right | disagree (ask the learner) |
|---|---|---|---|
| Opus, geometry + pipeline in one look | 15 | **15 (none wrong)** | 6 |
| Opus, crop pipeline + pin rule | 14 | **14 (none wrong)** | 7 |
| Opus, geometry + model + pin rule | 16 | 14 | 5 |
| Haiku, geometry + pipeline in one look | 15 | 13 | 6 |

So: accept when the model and the code agree, otherwise ask (the app already asks the learner to say where a leg is
when it is unsure). On these photos that never confirms a wrong column with Opus.

### 8.3 Our numbers against the printed numbers

`wire_geometry.printed_shift`: slides a strip over the 3 rows outside each half and keeps the line with ~13 marks
(the printed 0, 5 … 60; a line of holes has 65), then checks they sit over the columns our numbering gives them.
Found on 40 of 42 halves; our numbering matched the printed numbers on all of them (shift 0). When the printed line
can't be found it keeps the count from the board's end.
