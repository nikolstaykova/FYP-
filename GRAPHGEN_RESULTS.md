# Graph generation: results

> Can Claude turn a real manual into one build graph that follows [GRAPH_SPEC.md](./GRAPH_SPEC.md)? How accurate, how fast, how expensive?
> Method and test sets: [RESEARCH.md](./RESEARCH.md) R21. Code: [`graphgen/`](./graphgen/). Raw results: `experiments/graphgen/`.

---

## Price and performance at a glance

**Model:** Claude Sonnet (`sonnet` → `claude-sonnet-5-5`), effort `high`, run on the Claude subscription through headless Claude Code. **Cost** is Claude Code's estimate at **API list prices**: what the same calls would cost with an API key, not what the subscription charges.

| | Electronics (Arduino + Raspberry Pi) | LEGO (official PDF manuals) |
|---|---:|---:|
| **Pilot** | 9 tutorials | 10 manuals (all < 100 pieces) |
| Mean time per manual | **38 s** (median 37, 90th pct 69) | **88 s** (median 71, 90th pct 175) |
| Mean cost per manual | **$0.089** | **$0.198** |
| Cost per 100 manuals | **≈ $9** | **≈ $20** |
| Input / output tokens (mean) | ≈ 16k / 5.6k | ≈ 24k / 12.8k |
| **Full run** | **117 tutorials** (116 ok, 1 safety false positive) | 100 manuals: *running* |
| Mean time per manual | **41 s** (median 35, 90th pct 79) | *pending* |
| Mean cost per manual | **$0.104** (median $0.10, 90th pct $0.16) | *pending* |
| Cost per 100 manuals | **≈ $10.45** (whole run: $12.12) | *pending* |
| Input / output tokens (mean) | ≈ 19.7k / 5.9k | *pending* |
| **v1 full run (build only)** | see above | **34 booklets** before it was stopped: 221 s, $0.55 mean (median 180 s); big sets up to 650 s / $1.40 |
| **v2 (check + repair)** | **117/117, 44 s, $0.122** per tutorial (see below) | **in progress** (10 of 100 so far): 136 s, $0.41 mean |

*The LEGO full-run rows are filled in when that run finishes.*

---

## Latest: re-run with the new logic (v2)

**v2 = improved catalogue** (pushbutton explanation, missing pinouts) **+ allowed port kinds in the prompt + build → check → up to 2 repair rounds → final check.** Same 117 electronics tutorials, same model (Sonnet, effort high, subscription route). Compared with v1 (build only, old catalogue):

| Measure | v1: build only | **v2: build + check + repair** |
|---|---:|---:|
| Succeeded | 116 / 117 | **117 / 117** (2 safety-filter false positives passed on a retry) |
| Mean seconds per tutorial | 40.8 | 44.3 |
| Median seconds per tutorial | 34.8 | 35.0 |
| Mean cost per tutorial | $0.104 | **$0.122** |
| Cost per 100 tutorials | $10.45 | **$12.21** |
| Tutorials with rule problems | 30 | **0** |
| Rule problems in total | 210 | **0** |
| Answer-key tutorials, every net identical (strict) | 23 / 47 | **27 / 47** |
| Mean net precision / recall | 0.65 / 0.62 | **0.72 / 0.70** |
| Other tutorials: listed parts present | 0.97 | 0.96 |
| Needed a repair round | – | 22 / 115 |
| Check issues: first build → final | – | **67 → 2** |

**Phases in v2:**

| Phase | Runs | Mean time | Mean cost |
|---|---:|---:|---:|
| Build | 115 | 38.9 s | $0.103 |
| Repair round 1 | 22 | 25.7 s | $0.091 |
| Repair round 2 | 3 | 17.7 s | $0.048 |
| Checks (code) | every phase | < 0.01 s | free |

**What changed in accuracy:** Button, DigitalReadSerial, KeyboardMessage and toneMelody went from wrong to **exactly right**; nothing that was right became wrong. The 20 tutorials that still differ from the answer key were read by hand (the 4 whose graph changed were re-checked against the official tutorial):

| Category | Tutorials | Count |
|---|---|---:|
| Answer key differs from the official tutorial; Claude follows the tutorial | ADXL3xx, ifStatement, Debounce, StateChangeDetection, Knock, toneMultiple, Midi, Ping, InputPullupSerial | 9 |
| Valid alternative / electrically equivalent | Calibration, LED bar graph, PitchFollower, SerialCallResponse ×2, VirtualColorMixer, WhileLoop | 7 |
| **Real error** | RowColumnScanning (LED-matrix pins on the wrong rows) | 1 |
| Ambiguous | JoystickMouseControl (X/Y axes possibly swapped; the tutorial is unclear) | 1 |
| Not verified | ArduinoISP, ArduinoToBreadboard | 2 |

**Adjusted accuracy v2: ≈ 43 / 47 (≈ 91%) correct or valid**, against ≈ 80% in v1. **The price: +$0.018 and +3.6 s per tutorial on average**; 81% of tutorials need no repair at all.

### LEGO v2 (in progress: 10 of 100 booklets so far)

*Updated 1 October 2026 while the run continues; the full table replaces this when it finishes.*

**v1 baseline (build only, 34 booklets before it was stopped):** mean 221 s and $0.55 per booklet (median 180 s; the 200+-piece sets took 8–11 min and $1.2–1.5). Piece count 98% right; inventory by design: recall 0.73, precision 0.72; brick contacts: recall 0.53, precision 0.44. Larger booklets did better on inventory because they have a parts page with Element IDs.

**Same 10 booklets, v1 vs v2:**

| Measure | v1: build only | v2: build + check + repair |
|---|---:|---:|
| Mean seconds per booklet | 92 | 136 |
| Mean cost per booklet | $0.19 | **$0.41** |
| Booklets with rule problems | 10 / 10 | **0 / 10** |
| Rule problems in total | 102 | **0** |
| Needed a repair round | – | 10 / 10 |
| Check issues: first build → final | – | 110 → 7 |
| Pieces built ÷ pieces in set | 0.96 | 0.98 |
| Inventory recall / precision (by design) | 0.44 / 0.41 | 0.41 / 0.37 |
| Contact recall / precision | 0.25 / 0.29 | 0.17 / 0.08 |

**What this means:**
- **The repair fixes form, not content.** First-build issues were port names (V3 ×31, V4 ×50) and invented part numbers (L2 ×27); repair cleared 110 → 7. But **contacts were identical before and after repair** in every booklet, so the repair neither helped nor hurt accuracy.
- **The accuracy difference between v1 and v2 is noise.** It comes from the first build (Claude does not give the same answer twice) and the samples are tiny: 0–11 checkable contacts per booklet, and 4 of these 10 have none.
- **The cost doubles** because every LEGO booklet needs a repair round, while 81% of electronics tutorials need none.
- **Conclusion so far:** for LEGO the check-and-repair loop is worth it only for clean, valid output (real part numbers, valid ports), not for accuracy. Accuracy needs a better input: **the official parts list for the set**, which would also remove most part-number issues before they happen.



---

## Pilot: what the scores say

| | Electronics | LEGO |
|---|---|---|
| Fully correct | **4 of 7** tutorials with an answer key have every electrical connection right | — |
| Mean accuracy | net precision 0.76, recall 0.72 | piece count ≈ 99% right; correct pieces by design 53% found (49% precision); brick contacts 56% found (48% precision) |
| Repeats | 2 of 2 multi-LED tutorials used `repeats` + `attach` overrides, and both expanded to **6 correct copies** | 7 of 10 booklets used repeats (e.g. 4 wheels) |
| New part types | Raspberry Pi board, speaker created on first use | 2–31 new piece types per booklet (catalogue starts empty) |

---

## Manual sanity check (read by hand)

The automatic score depends on the answer key. Every pilot graph was also read by hand with `python -m graphgen.inspect <run>/<manual>`, to see whether the **logic** holds.

### Electronics

| Tutorial | Does the logic hold? | Finding |
|---|---|---|
| ForLoop, Arrays | ✅ Yes | 6 LED + resistor copies on pins 7…2 (one repeat, `attach` overrides per copy), all cathodes to one GND rail. 13/13 nets. |
| Blink, Fade | ✅ Yes | LED + resistor on pin 13 / 9 to GND. |
| ifStatement | ✅ Yes (answer key differs) | Claude used the **built-in** LED, as the official tutorial says; CircuitQuest's lesson adds an external one, so the score is lower than it should be. |
| ADXL3xx (earlier test) | ✅ Yes (answer key differs) | Claude followed the **official** wiring (sensor in A0–A5, code drives A4/A5 as GND/power); CircuitQuest wires it to GND/3.3V instead. |
| Pi traffic lights | ✅ Yes | LEDs on GPIO 25/8/7 through resistors, button on 21, buzzer on 15. Claude noted that the text and the diagram disagree and followed the diagram. |
| **Button, DigitalReadSerial** | ❌ **No** | The pull-down resistor went on the button's **5V leg** instead of the pin-2 leg: the pin floats and the resistor sits across 5V–GND. Both tutorials share one image; the model misread which button legs are joined. A real error, correctly scored as wrong. |
| Pi music box | ⚠️ Unclear | The catalogue had **no ports** for the male-female jumper wire, so Claude invented `pin`/`socket`; nets cannot be folded. **Our catalogue's fault**, now fixed. |

### LEGO

| Booklet | Does the logic hold? | Finding |
|---|---|---|
| 30103 Car | ✅ Mostly | Plates stacked on two base plates; one `wheel ×4` repeat attached to the wheel pins with `attach` overrides. Piece count 25 vs 28. |
| All 10 | ⚠️ | **Small booklets have no inventory page** (many are 2 pages), so there are no Element IDs; Claude names pieces by **design number** (`lego-3023` = Plate 1×2) from its own knowledge. Colours come from the pictures. |
| All 10 | ⚠️ | Without a list of allowed **port kinds**, Claude invented its own (`socket`, `wheel-pin`), causing most rule warnings (V3/V4). The allowed kinds are now in the prompt. |

### What was fixed after the pilot

| Problem found | Fix |
|---|---|
| Answer key used `cq-adxl335`, catalogue `adxl335` | Type names normalised before scoring |
| Male-female jumper wire and alligator lead had no ports | Added (`a`, `b`, conducting) |
| Potentiometer pins in a breadboard flagged incompatible | `lug ↔ breadboard-hole` allowed |
| First, incomplete draft of a new type (Raspberry Pi with 8 pins) blocked later, fuller drafts | **Unverified** entries now **merge** ports from later manuals |
| LEGO pieces named by design number scored as 0 | Scored by design number as well as Element ID |
| Model invented port kinds | Allowed port kinds and compatible pairs added to the prompt |

---

## Full electronics run (117 tutorials)

| | Result |
|---|---|
| Succeeded | 116 / 117 (one safety-filter false positive on `tone-keyboard`) |
| Tutorials with an answer key | 47 |
| **Strict score:** every net identical to CircuitQuest | 23 / 47 (49%) |
| Tutorials without an answer key | 69: 96.7% of the part families each tutorial lists are in its graph |
| Rule warnings | 178, mostly **our catalogue**: CircuitQuest's cards for Leonardo, Mega, Zero, HC-SR04, servo, OLED, DHT22 have no pin list, so every pin used on them was "unknown" |

**Read by hand, the 24 "wrong" tutorials split into:**

| Category | Tutorials | Count |
|---|---|---:|
| Answer key differs from the **official** tutorial; Claude followed the tutorial | ADXL3xx, ifStatement, Debounce, StateChangeDetection, Knock (answer key adds an LED), toneMultiple (tutorial: speakers + 100 Ω), Midi (tutorial: two 220 Ω), Ping (same part, different name) | 8 |
| Valid alternative or electrically equivalent | VirtualColorMixer, SerialCallResponse ×2 ("any analog sensor + 10k"), LED bar graph, Calibration, WhileLoop, PitchFollower (resistor on the other side of the LED) | 7 |
| **Real model errors** | Button, DigitalReadSerial, KeyboardMessage, InputPullupSerial (**4 × pushbutton legs**), JoystickMouseControl, RowColumnScanning (partly) | 6 |
| Not verified | ArduinoISP, ArduinoToBreadboard, toneMelody | 3 |

**Adjusted accuracy: ≈ 38 / 47 (≈ 80%) correct or valid; ≈ 13% real errors.**

---

## Check and repair loop

**Flow:** Claude builds the graph → code checks it → if anything fails, the exact problems go back to Claude **in the same conversation** (the manual is not resent) → Claude returns a corrected graph → final check. Every phase is timed and costed separately; the score is kept for both the first and the final graph.

**Checks** ([`graphgen/checks.py`](./graphgen/checks.py)):

| Electronics (circuit laws) | LEGO |
|---|---|
| E1 supply shorted to GND · E2 board pin wired straight to 5V/GND · E3 a two-legged part shorted out · E4 a leg connected to nothing · E5 input pin floating (only a button on it, no pull-up/down, unless the code uses `INPUT_PULLUP`) | L1 piece counts differ from the booklet's own parts page · L2 not a real LEGO part number · L3 the build falls apart into separate groups |
| + the spec rules (V2 unused part, V3 incompatible ports, V4 missing/over-used port) | + the same spec rules |

### Electronics

- **Do the checks catch real errors?** Run on the graphs from the full run: they flag **5 of the 6 real errors** (Button, DigitalReadSerial: E5 floating pin; KeyboardMessage, InputPullupSerial: E2 pin shorted; Joystick: E1 supply shorted) and **nothing** on correct graphs (Blink, Fade, ForLoop). The miss, RowColumnScanning, has pins on the wrong rows: no circuit law can see that.
- **Catalogue fixes first:** the pushbutton entry now says which legs are joined inside it, and the missing pinouts were added. Re-run on the 6 error tutorials:

| Tutorial | Before | After | Note |
|---|---|---|---|
| Button | 1/3 | **3/3 ✅** | fixed on the first build |
| DigitalReadSerial | 1/3 | **3/3 ✅** | fixed on the first build |
| KeyboardMessage | 1/3 | **3/3 ✅** | fixed on the first build |
| InputPullupSerial | 0/4 | 1/4, **correct** | internal pull-up, as the tutorial says; the answer key adds an LED |
| JoystickMouseControl | 2/8 | 2/8, mostly correct | only the X/Y axes may be swapped (the tutorial is ambiguous); the answer key adds 2 buttons |
| RowColumnScanning | 19/28 | 19/28 ❌ | pins on the wrong rows of the LED matrix |

  None of the six triggered a repair any more: every first build passed the checks. **The catalogue fix did more than the repair loop**; the loop stays as a safety net (it catches the error types we saw).

### LEGO (5 booklets, up to 2 repair rounds)

| Booklet | Issues build → final | Repair rounds | Build | Repair | Inventory recall | Contact recall |
|---|---|---:|---|---|---|---|
| 7268 Crab | 13 → **0** | 1 | 48 s, $0.08 | 51 s, $0.13 | 0.25 → 0.25 | 0.0 → 0.0 |
| 30103 Car | 13 → **0** | 1 | 71 s, $0.10 | 35 s, $0.11 | 0.11 → 0.11 | – |
| 4991 | 14 → 1 | 2 | 56 s, $0.10 | 68 + 42 s, $0.30 | 0.85 → **0.89** | 1.0 → 1.0 |
| 30161 | 3 → **0** | 1 | 53 s, $0.10 | 25 s, $0.09 | 0.16 → **0.22** | 0.25 → 0.25 |
| 7246 | 8 → **0** | 1 | 67 s, $0.13 | 46 s, $0.14 | 0.09 → 0.09 | – |

- **Issues: 51 → 1.** One repair round almost always clears them (invented part numbers, incompatible ports, missing ports).
- **Cost of repair:** about **+25–70 s and +$0.09–0.16 per round**, roughly doubling the cost of a small booklet.
- **Accuracy barely moves** (small gains on 2 of 5): the LEGO checks catch *impossible* graphs, not *plausible but wrong* pieces. These booklets have no parts page, so which piece is which is guessed from small pictures; **giving Claude the official parts list** (from the set number) is the bigger lever for LEGO.

---

## Limits of this experiment

- **Answer-key noise (electronics):** CircuitQuest's circuits sometimes differ from the official tutorial (ifStatement, ADXL3xx, Button's extra LED). Only Button's difference is excluded automatically.
- **LEGO contacts** are checked only by design pair among plain bricks, plates and tiles; slopes, Technic, minifigures and wheels are not checked, and 4 of 10 pilot booklets had nothing checkable.
- **Strict nets:** an electrically equivalent circuit (resistor on the other side of an LED) counts as wrong.
- **Cost** is an API-price estimate; the run itself used the Claude subscription.
