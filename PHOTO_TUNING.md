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

---

## 9. Geometry first, the model where geometry is not sure — now in the app (17 November, later)

**Rule** (the learner's: "keep geometry; the model is to fine-tune it when geometry is not sure"): code finds every
connector and is **sure** of one when it is connector-sized (at least one hole cell) and three estimates of the pin
give the same column: the black blob's middle, its end away from the wire, and its **base**. The base uses the
connector's radius: a connector stands up, so in a photo from above its top leans away from the point under the
camera; the pin is at the blob's end nearest the photo's centre, moved in by half the blob's width (the radius).
Where code is sure, its column stands; elsewhere the model reads (numbered board + crop + photo, pin rule).

| `wire_board_eval.py --geometry-first` | Columns right | Settled by geometry alone | Cost (21 photos) |
|---|---|---|---|
| Opus 5.5 | **21/21** | 7 (all right) | $0.42 |
| Haiku 5.5 | 18/21 | 7 (all right) | $0.02 |

Caveat: these 21 photos were also used to find the rules (the board's numbering, the size check), so this is a
tuning score, not a test score. New photos are needed for the honest number (§5.7).

Fixes on the way: the RANSAC fit is seeded (the same photo always gives the same grid; one run had placed a shadow as
a "sure" connector); the straightened image was one row lower than the code assumed (columns unaffected; the code-only
base estimate went from 13 to 15/21 once fixed).

**In the app** (`code/validator/geometry.py`, used by `validator/arduino.check`):
1. `geometry.analyse(photo)`: straighten, number every column, check the numbers against the printed ones, find the
   connectors. **Trusted** only when the board has this board's 65 columns and its printed numbers are where ours say
   (at most one out, corrected); otherwise nothing from geometry is used and the check runs as before.
2. The model gets the numbered board first ("these numbers are exact: read them instead of counting"), then the board
   and Arduino close-ups and the whole photo; the breadboard explanation now has the pin rule.
3. After the model: a wire end within one column of a connector code is sure of takes code's column (the offset moves
   with it); when they agree, the reading counts as sure. Resistor and LED legs are never moved (no connector).
4. Each check records the geometry step (used or why not, connectors found, legs set by geometry).
On the learner's step photo b2c4 (blink step 3): geometry sure of column 13; with their earlier columns the board end
passes (it had been misread as 11 before any of this).

---

## 10. First real step checks with geometry, and fixes (17 November, late)

The learner's two step checks (blink steps 1 and 2, board held upright in the photo):

| Problem seen | Why | Fix |
|---|---|---|
| The close-up showed empty columns 25–45; the parts were at 10–20 ("LED not visible") | Haiku's box was wrong on an upright board | **Geometry makes the close-up**: on the straightened board, the columns where something sits (much more coloured or darker than the board's usual column) ±4, cut from the full-size photo at 56 px a column, with the yellow numbers. Haiku is only asked when the step wires to the Arduino |
| The resistor was read as "bottom half" | Which way up came from the rails' colours, but this board's rails clip on either way round (red above blue in one photo, blue above red in another), and the board itself is printed the same both ways | **The half with the parts is the top half**: the straightened board is turned round so that half is on top (blink builds in one half) |
| A frame that is blurry means "take it again" | One photo per check | **A few frames**: the app keeps the frames taken while lining up where the board was found; with the photo that takes itself go the 2 sharpest others. The server reads the sharpest one geometry knows the board on, sends one more as a second view, and asks for a retake only if none will do |

Re-run on the same two photos: step 1 resistor in the top half, column 13 (one bent leg unsure), cost 3.5¢ (was
6.5¢: no Haiku); step 2 LED in the top half, its legs hidden under its body from straight above: unsure (honest),
the learner is asked. Also: the live outline (board and Arduino found by their corners) now has to have found the
board before the photo takes itself.

---

## 11. The Arduino's pins (17 November, late)

The learner's check of blink step 3 read **pin 12; the wire was in 11**. A labelled set started from the checks'
own photos: `data/arduino_pins/<pin>/` (pin11: 3 frames, pinGND: 6), scored by
`research/recognition/arduino_pin_eval.py` (the real step check, the pin it reads against the folder).

**Why it is off by one:** the labels and their little gold dots are printed on the board, but the black header and
the wire's connector stand 1–2 cm above it. In a photo from above (the Arduino away from the photo's middle) the tall
parts shift against the print (parallax): on the close-up the socket openings sit about half a socket past their
dots, the connector's top a whole socket. "The label next to the connector" is then one off, always towards the
edge of the photo (AREF here).

| Prompt for an Arduino pin | Right (of 9) |
|---|---|
| Before ("which pin socket is it in?") | 4 (11 read as 12 ×3, GND as AREF, 1 not read) |
| + "the connector leans away from the photo's middle; its socket is under its other end" | 4 |
| "Don't take the label next to it: **count the header's own openings** from its end (AREF, GND, 13 …)" | 6 |
| Both: count the openings, and the opening is under the connector's end that meets the header | **8** |

The one left: a spare frame with the Arduino almost out of the picture (no reading: right to say so). Tuning score
on 9 photos; fresh photos needed. Also fixed: the live camera missed the learner's Duemilanove in warm light (its
dark blue reaches V 10–20; the range began at 25): found in 8/9 frames with it, 0 without.

### 11.1 Fair test on new photos (18 November)

43 new photos of the Arduino with a wire (15 different pins: 0–12, GND, AREF; the Arduino in different places in
the frame), labelled by clicking (`data/arduino_pins/board/labels.json`), none of them used to find the rule.
`research/recognition/arduino_pin_eval2.py`: the step check's Arduino close-up (Haiku box, cut from the full photo),
then the pin question with or without the rule (`arduino.PIN_HOW`).

| Model | Before (no rule) | With the rule (count the header's openings; the one under the connector's end at the header) |
|---|---|---|
| **Opus 5.5** | 39/43 (all 4 misses one socket towards 0) · $1.14 | **43/43** · $1.25 |
| Haiku 5.5 | 25/43 (12 one socket off; also "12" read as "2": the digits are printed stacked) · $0.07 | 35/43 · $0.08 |

The rule holds on photos it was not tuned on. Opus stays first for step checks; Haiku is not good enough for pins.

---

## 12. Resistors: the learner's photos (18 November)

The 23 photos in the "220" folder are **270 Ω** (red-violet-brown-gold: the second band is clearly violet; earlier
checks had found 270 too): moved to `data/resistors/270/`. `resistor_eval.py --set all` (HEIC converted with sips;
the converted copies no longer counted twice):

| Outcome (23 photos, mostly from about 30 cm, resistor small in the frame) | Photos |
|---|---|
| Right and sure | 6 |
| Right but marked not sure | 2 |
| Wrong and sure | **1** (brown multiplier read as black: 27 Ω) |
| Wrong, marked not sure (not used) | 3 |
| Bands or body not found (resistor too small, or end-on) → the app asks for a close-up on white paper | 10 |
| Colours make no value | 1 |

Safe (1 confident mistake in 23) but it reads only about a third of these far photos; close-ups (§ earlier: 5/7)
do much better. Other values are untested: the Wikimedia download was rate-limited after 5 photos.

---

## 13. Whole-flow test, 18 November: blur, the LED's hidden leg, the outline

From the learner's run (blink steps 1–4, 15 live frames, 7 checks):

| Seen | Why | Fix |
|---|---|---|
| Steps 3 and 4 "unsure" first ("pin header blurry"), right on the retake | The photo took itself when the **board** was sharp; nothing looked at the Arduino. Sharpness (Laplacian, 1200 px): unreadable photos board 302 / Arduino 1,083; readable ≥ ~800 / ≥ ~3,300 | The live check also measures the Arduino's box; the photo takes itself only with board ≥ 500 and Arduino ≥ 1,500 ("Hold still, tap the Arduino to focus"). Spare frames are ranked by the weaker of the two |
| LED short leg never read | From above the LED's body covers both legs | `_hidden_leg`: an LED leg read unsure one or two columns from its sure other leg, same half, is taken (its legs are one column apart). Re-run of step 2: the short leg worked out (column 35), step passes |
| The board/Arduino had to match the outline | — | The app sends where its outlines are; the live check only wants the board's holes inside the board outline (7% margin) and the Arduino's middle inside its outline; code finds the exact edges in the photo afterwards (geometry; the Arduino by its blue board) |
| — | — | When Haiku's header box finds no Arduino, code cuts the Arduino out by its blue board (Haiku's tight header crop stays first: it is what scored 43/43) |

Open: two step-3 photos taken 30 s apart read pin 12 and pin 11 (asked the learner which it was).

---

## 14. Geometry for the Arduino: overlay on a reference of the same board (18 November)

The model kept wavering on pins next to each other (the same photo read 11, 12 or 13; pin 11 was right). Code
couldn't count the header's openings in the raw photo (black in black, half covered), and the gold dots by the
labels were confused with other gold pads. The learner's idea: once the gather check knows the board, use what all
boards of that kind share, and overlay to find the board's rotation.

`code/validator/uno_overlay.py`:
1. **Overlay.** The Arduino in the photo (its blue board, or the whole photo) is matched to a reference photo of the
   same board by SIFT features of its print (text, chips, pads); RANSAC gives the homography: position, rotation, which
   way round, slant, in one go. Reference: `code/graph/parts/arduino/refs/arduino-duemilanove.jpg` (+ `.json`, made by
   `research/recognition/uno_reference.py` from the clicked photos).
2. **The openings.** In the straightened photo the header is a straight row; a comb of the header's known shape (16
   openings 2.54 mm apart, 1.6 spacings between 8 and 7) is slid along it until its teeth sit on the dark openings,
   the spaces between them on lighter plastic, and the spots past both ends and in the 8/7 gap on no opening.
3. **The names.** Each pin's name is written in yellow just outside the header with a line to its opening; the model
   gets this image first and reads the name at the connector.

| On the 43 clicked photos | |
|---|---|
| Overlaid on the reference | 40 (3: no blue board found) |
| Pin nearest the click, positions learned from the other photos | **40/40** |

| The step check on the 12 photos from the learner's checks (not used to make the reference) | Right | Sure and wrong | Cost |
|---|---|---|---|
| No overlay, one read | 8–10/12 (varied run to run) | 1–2 | $0.63 |
| No overlay, read twice (disagreement → ask) | 9/12 | 0–1 | $1.20 |
| **Overlay, one read** (run twice) | **11/12 both times** | **0** | $0.69 |

The one left is a frame with the Arduino almost out of the picture (no reading: right). The second read is off
again (`PINPOINT_PIN_TWICE=1` turns it on). Only the Duemilanove has a reference so far; another board needs one
reference photo and a few clicked photos (the check works as before without one).

### 14.1 More boards (18 November)

The database has 44 boards. By how a wire meets them: **Uno-shaped with female headers** (Uno R3, R4 Minima/WiFi,
Uno WiFi Rev2, Leonardo, Duemilanove, Zero, Due, Yún, Mega: this overlay); **plugged into the breadboard** (Nano
family, ESP32 DevKits, Pi Pico, MKR, Pro Mini, Blue Pill...: the wires go into breadboard columns, so the breadboard
geometry already covers them); **Raspberry Pi** (2x20 male pins: needs its own template); micro:bit and Opta (rare).

References from openly licensed top-down photos on Wikimedia Commons (`code/graph/parts/arduino/refs/CREDITS.md`),
made without clicked photos: the two ends of the header row read once off a pixel grid, then the comb finds the
openings (`uno_overlay.build_from_row`). Header layouts per board (`LAYOUTS`): Duemilanove 16 openings (AREF..8 |
7..0); Uno R3 and later 18 (SCL, SDA, AREF, GND, 13..8 | 7..0).

| Board | Reference | Recognised (synthetic phone photos: any rotation, scale, slant, blur, darker) | Labels at the openings |
|---|---|---|---|
| Duemilanove | learner's photos | all 11 of the learner's photos with the board in view picked it (none mistaken for another) | — |
| Due | Commons, Arduino SA | 6/6 | 6/6 |
| Leonardo | Commons | 6/6 | 6/6 |
| Uno R4 WiFi | Commons (slightly angled: faint openings) | 6/6 | 0/6 within 0.4 opening (about 0.4 off along the row) |

Not yet: the Uno R3 and the Mega 2560 (Commons has them only at an angle or as a clone); the R4 WiFi needs a straighter
photo. On the learner's Duemilanove, the step check scored 11/12, 11/12 and 9/12 on three runs: the labels were right on
the miss (the connector leans over the next opening and the model took that one). Next: code tells which opening the
connector covers (the plastic between openings it hides; its base is at the end away from the wire), as on the
breadboard.

### 14.2 The Mega, both header rows, and teal boards (18 November)

- **Mega 2560** (newer teal print): a reference from a straight-down product photo the learner found (licence unknown,
  so it is kept out of git: `data/board_refs/local_refs/`, loaded with the repo's references). Its main row is 26
  openings: SCL..8 | 7..0 | 14..21; the gap before 14 is 2.0 spacings (fitted: 2.0 put the row's ends on the header,
  1.6 slid it a whole opening). Turned 170 degrees in a synthetic phone photo: recognised, both rows labelled right.
- **Both header rows.** References now hold several rows: the digital header and the power + analog header
  (Duemilanove: RESET, 3V3, 5V, GND, GND, VIN | A0-A5; Uno R3 / Leonardo / R4: NC, IOREF, RESET, 3V3, 5V, GND, GND,
  VIN | A0-A5; Mega: ... | A0-A7 | A8-A15; Due: ... | A0-A7 | A8-A11, DAC0, DAC1, CANRX, CANTX). Checked by eye on each
  reference: right on the Due, Leonardo and Mega; the R4 WiFi's power block looks one opening off (its photo is
  angled).
- **Which way round:** the overlay finds the board at any rotation, upside down included.
- **Finding the board in the live camera:** the colour range now starts at hue 84 (teal boards, Mega Rev3: 89), the
  shape may be up to 2.4 : 1 (the Mega is 2.06 : 1), and a board must be "busy" (edge density at least 0.06: the
  learner's Arduinos 0.11-0.26, dark clothing that matched the colour 0.01-0.03). The 21 photos without an Arduino:
  none found; the 55 with one: 52 found.

### 14.3 Uno R3 and a straight Uno R4 WiFi (18 November)

- **Uno R3** (the most common board, card `arduino-uno`) and **Uno R4 WiFi**: references from straight-down product
  photos the learner pasted (licence unknown: kept out of git in `data/board_refs/local_refs/`). Both rows fitted
  with the tight comb (the loose one slid the Uno's digital row a whole opening, past pin 0); every pin checked by eye
  against the printed labels.
- A local reference **replaces** a repo reference of the same board: the R4 WiFi's angled Commons photo (whose power
  row was one opening off) is no longer used when the straight one is there.
- **Recognition:** six references, six synthetic phone photos each (tilted, turned 0-290 degrees, blurred,
  darkened): 36/36 recognised as the right board. The learner's 55 Duemilanove photos: 53 Duemilanove, 2 no board
  found (as before), never the Uno R3, although the two boards look alike.
