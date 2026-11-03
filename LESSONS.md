# Lessons: how Pinpoint makes step-by-step lessons, what changed, and what is left

**Status:** 14 October 2026. Phase one (graph → lesson) is close to done. The test runs comparing the old and new
ways are still running; their results go in section 5 when they finish.
**Code:** `code/graph/lessons.py` (the one lesson loop), `code/graph/lego_3d/lesson.py` (LEGO recipe), `code/graph/arduino/circuit_lesson.py`
(Arduino recipe), `code/graph/lego_3d/assembly.py` (LEGO physics), `code/graph/lego_3d/assembly.py` (3D hint page),
`code/tests/tools/compare_cq.py` (comparison with CircuitQuest), `code/tests/tools/lesson_batch.py` (the full LEGO run).
**Research write-up:** [`RESEARCH.md`](./RESEARCH.md) R24.

---

## 1. One pipeline for every domain

There is **one function for graphs** and **one function for lessons**. Each domain plugs in a *recipe*: the prompt,
the rules and how to load and save. The flow itself is the same.

| Stage | One function | LEGO recipe | Arduino recipe |
|---|---|---|---|
| Graph | `pipeline.run_case` | Built by code from the set's 3D model (LDraw): studs, pins, clips, wheels, figures | Claude reads the tutorial link; code checks it with laws E1–E11 and asks for repairs |
| Lesson | `lessons.make(recipe, case)` | `LegoLessons` | `CircuitLessons` |

```
python -m graph.lessons lego 42124-1
python -m graph.lessons arduino https://docs.arduino.cc/built-in-examples/basics/Blink/
```

`lessons.make()` always runs the same steps:

1. **Source:** the graph and what the lesson is made from.
2. **Suggest (code):** a plan from the graph.
3. **Plan (Claude):** Claude orders, groups and writes, starting from the suggestion.
4. **Check (code):** every rule, with problems sent back to Claude for up to 3 repair rounds.
5. **Finish (code):** final fixes, then save.

Every Claude turn is timed and costed.

## 2. The new logic: code suggests, Claude plans and writes, code checks

| | Old way | New way |
|---|---|---|
| **Arduino** | Code fixed the order (one part or wire per step); Claude only wrote the words | Code **suggests** the steps (each part and wire with its exact holes and connections); Claude chooses the **order** and **grouping** (up to 3 suggested steps in one, e.g. a resistor and the wire to it) and writes the words |
| **LEGO** | Claude planned from the list of pieces alone | Code **suggests a whole plan** from LEGO's own steps (big steps split in a buildable order, sub-builds attached), with the problems the checks find in it; Claude starts from it, merges, splits, fixes and writes. Claude also gets the **physical rules** (section 3) |

In both, code's checks have the last word: anything wrong goes back to Claude.

## 3. The rules

### 3.1 LEGO: physical rules given to Claude (generic, for every set)

Every step must be possible with two hands on the real model.

1. **The way in:** each piece moves into place along one straight way. Nothing built may be in that way, and there
   must be room for the fingers. If something would be in the way, the piece goes on first.
2. **Nothing floats:** a piece goes on only once what it sits on, clicks onto or slides onto is there.
3. **Nothing goes under what is already on top:** pieces under an overhang, roof or plate go on before it.
4. **One way at a time:** a piece joining two things must reach both along the same way.
5. **Base first:** within a step, the piece others go onto comes first. A group starts from the piece the others
   connect through. A big part (a motor, a frame) goes on last if it would block the small pieces.
6. **What spans comes after what it spans:** a plate or beam over several studs or pins goes on after all of them.
7. **Locking pieces go in last:** a long axle or pin through several pieces goes in after them ("hold … lined up,
   then push the axle through").
8. **Parts with a stop go in free end first,** from the side the stop ends up on.
9. **On an axle end:** gears, wheels, hubs and bushes go on after the axle.
10. **Sub-assemblies go on in one push:** pieces joining from another side are added after attaching.
11. **Things that move:** hinges, toggles, swivels and turntables may have their ends go on different ways. Arms on
    one pin can turn aside to make room.
12. **See what you do:** every new piece visible; say "turn the model over" and "turn it back".

Also given to Claude:

- follow LEGO's own order;
- every piece in exactly one step;
- 3–6 pieces a step;
- LEGO's sub-builds built off the model and attached as one;
- identical sub-assemblies built together;
- one area and one significant part per step;
- left and right twins together.

### 3.2 LEGO: checks by code (S1–S13, W1–W2)

| Rule | Checks |
|---|---|
| S1 | Every piece in exactly one step |
| S2 | Nothing floats; a sub-assembly is one connected piece at every step |
| S3 | A sub-assembly is attached and fastened (figures may stand or sit) |
| S5 | Step size |
| S6 | The way in is clear (pieces as 4-LDU cubes slid along their way); a sub-assembly can be pushed on in one direction; axles going in from opposite sides are left out of it |
| S7 | LEGO's own order |
| S8 | Room for fingers |
| S9 | LEGO's sub-builds are built off the model and attached as one |
| S10–S13 | Grouping: one significant part a step, one area, twins together, visibility |
| W1 | The words match the 3D page (what is held, what is pushed) |
| W2 | "Turn it over" where the camera flips |

Code also fixes what is left after the repairs:

- **LEGO order:** leftover order problems are moved by code (`fix_order`).
- **Axles from opposite sides:** these leave the sub-build and go into its attach step.
- **Rewording:** steps that code changed are reworded.

### 3.3 LEGO: what the 3D model gives code

- **Joins:**
  - studs (clutch), Technic pins and axles;
  - clips on bars, balls in sockets, tyres on rims;
  - wheels on built-in pins (car bases, wheel holders);
  - minifigure and other figure parts.
- **Stud sockets:** for a part with a clip or handle sticking out, the sockets are taken from the part's own top
  studs when the outline gives none. This finds 9% more real stud joins.
- **Directions:** each piece's way in, with the "stop" side for axles and pins with a stop.
- **Blocking:** whether something already built blocks that way.
- **Official structure:** LEGO's steps, sub-builds (nested: "drive motor > block 42") and hand blocks.

### 3.4 Arduino: checks

| Rule | Checks |
|---|---|
| E7 | Graph: every pin the page's circuit text names is wired |
| **E11** | Graph: every pin the **sketch reads** is wired, so the program can work; the sketch wins over the page's text. The repair message quotes the sketch's own lines |
| W1 | Every suggested step used exactly once, at most 3 a lesson step; every step has its words |
| O1 | Nothing is wired before the parts it connects are in |
| W2 | No internal ids (r1, led1) in the words |
| W3 | Polarised parts say which way round (long/short leg, +/−, notch, stripe …) |
| W4 | Columns, never "rows", for breadboard connections |
| C1 | The steps' connections are exactly the graph's |
| C2 | Every part is placed before it is wired |
| C3 | Every pin the sketch reads is wired |
| C4 | Note: a pin the sketch only drives, which the circuit does not use |

**Arduino: how code makes the graph and the sketch right:**
- **Shields:** a shield or carrier stacked on a board joins its pins to the board's
  (`code/graph/parts/arduino/stack_pins.json`, from the datasheets).
- **Sketches found:**
  - the page's own code;
  - Arduino's examples repository for built-in examples;
  - linked `.ino` files;
  - sketches embedded from Arduino's online editor (through its public API);
  - sketches shown in pieces, joined.
- **No sketch on the page** (cloud projects, MATLAB, PLC): Claude **writes one for the circuit**. Code checks it
  (setup and loop, only wired pins) and it is marked "written for this lesson".
- **A graph that leaves read pins unwired** is extracted again.
- **Manual corrections:** `--hint` / `--sketch`, kept in `data/reference/lesson_corrections.json`.

## 4. What has been achieved

### 4.1 Off-Road Buggy (42124, 371 pieces): the test model

| Version | Steps | Issues: first plan → final | Cost |
|---|---:|---|---:|
| v17 | 142 | 0 left | — |
| v18b (stop rule) | 113 | 12 → 1 | $2.53 |
| v19 (S10–S13, views, turn-over, 1:1 lengths) | 143 | 21 → 0 | $2.95 |
| v19 + fixes | 142 | 0 | — |

The v19 fixes:

- **Motor block:** the motor goes on last.
- **Drive motor unit:** its two axles are pushed in from each side after it is attached.

The new way is being tested on the Buggy now (section 5).

**User-reported problems fixed by generic rules:**
- the swinging arms;
- the 2-hole beam block that could not get in;
- the yellow beam on the fairing;
- the motor unit floating in the air;
- the blocked azure beam;
- the long pins with the 5-long axle ("the long shall be last");
- the white cross block and half pin;
- the differential before its axle;
- the motor block pushed onto a beam at the end;
- the drive motor unit with its axles already in.

### 4.2 Arduino: 95 lessons from links

- **All 95 run.** 94 pass every check; 1 (Yún) has only a note.
- **Graphs that were wrong, fixed automatically:**
  - **Joystick:** the page says pin 6, but the sketch reads pin 2.
  - **ArduinoISP:** the status LEDs were missing.
- **Pages with no Arduino sketch (5), now with a sketch written for their circuit:**
  - [MATLAB PWM blink](https://github.com/arduino/docs-content/blob/main/content/hardware/uno/boards/uno-rev3/tutorials/matlab-pwm-blink/content.md)
  - [Arduino to Breadboard](https://docs.arduino.cc/built-in-examples/arduino-isp/ArduinoToBreadboard/)
  - [Opta Modbus TCP](https://github.com/arduino/docs-content/blob/main/content/hardware/opta/opta-family/opta/tutorials/10.opta-modbus-tcp-plc-ide/content.md)
  - [Alexa + IoT Cloud](https://github.com/arduino/docs-content/blob/main/content/tutorials/projects/arduino-iot-cloud-amazon-alexa-integration/arduino-iot-cloud-amazon-alexa-integration.md)
  - [TV control with Alexa](https://github.com/arduino/docs-content/blob/main/content/tutorials/projects/full-control-of-your-tv-using-alexa-and-arduino-iot-cloud/full-control-of-your-tv-using-alexa-and-arduino-iot-cloud.md)
- **Our own bugs found and fixed on the way:**
  - jumper-wire nets;
  - shield pins;
  - Grove cables;
  - line numbers read into sketches (20 lessons);
  - split sketches;
  - online-editor sketches;
  - pages that never finish loading.

**Against CircuitQuest (48 shared tutorials; `python -m graph.compare_cq`):**

| | Result |
|---|---|
| Same parts list | 30 of 48 |
| Circuit identical | 27 of 48 (mean match score 0.75) |
| Sketch identical | 21 of 48 (mean similarity 0.84) |
| Build steps per lesson | 9.9 (CQ 11.6) |

**Where the circuits differ, we follow the tutorial page and CircuitQuest changed the circuit:**
- the board's own LED, where CQ adds an LED;
- a speaker and a 100 Ω resistor, where CQ uses a buzzer;
- the ADXL3xx powered from A4 and A5;
- the MIDI resistor.

**Where CircuitQuest was better:** 3 lessons where our graph was missing parts (ArduinoISP, Arduino to Breadboard,
joystick).

**Compile check (`python -m graph.compile_check [--fix]`, arduino-cli, each lesson's own board):**

| Result | Count |
|---|---:|
| Compiles | **90 of 95** |
| Needs Arduino Cloud's `thingProperties.h` (made for each user's Thing) | 3 |
| Library problem on the Nano Matter | 2 |

- **The two library problems:**
  - the Grove RGB LED Matrix library is not in Arduino's index;
  - the DHT library does not build for the Silicon Labs core.
- **Fixed on the way:**
  - libraries installed;
  - a helper file the page shows as its own code block (the Due's `Waveforms.h`) is saved with the lesson;
  - `arduino_secrets.h` is written as a template for the learner's Wi-Fi details.
- **Tutorial bugs fixed by the smallest change that compiles** (Claude, from the compiler's errors; the page's sketch
  is kept as `code_original.ino`):
  - a typo, `Serial.prinln` (MKR Zero garden);
  - note names that did not match the MIDI library (`C3` → `pitchC3`; `A3` had silently meant the analog pin).
- **Lesson learned:** a compile failure is not always the sketch's fault. Three "fixes" were wrong because the
  compiler was given the wrong board (a card id named "mkr1000-wifi" is the MKR WiFi 1010). They were undone; the
  page's sketches compile unchanged on the right board.

### 4.3 LEGO: full run

- **The run:** all 1,306 sets with a usable 3D model, made the new way with every rule (`lessons-batch-14.log`).
- **Results so far (15 October):** 482 lessons, 85% passing every check, $137, sets up to 371 pieces.
- **Robustness:** the run waits and retries on usage, session and weekly limits, lapsed logins and network drops. A
  missed "weekly limit" message once marked 229 sets failed; that is fixed, and they are being made again.
- **Earlier runs, kept for comparison:**
  - old way: `tests/experiments/lessons_batch_v6_oldway/`;
  - older rules: `lessons_batch_v4_partial/` and `lessons_batch_v5_redo/`.

## 5. Old way against new way: summary

### 5.1 What "old" and "new" mean

| | Old way | New way |
|---|---|---|
| **LEGO** | Claude planned the lesson from the list of pieces alone; code checked and asked for repairs | **Code suggests a whole plan** from LEGO's own steps (big steps split, sub-builds attached, extra models set beside), with the problems the checks find in it. **Claude starts from it**, with **generic physical rules** in its instructions. Code checks and repairs as before, plus new finishing fixes |
| **Arduino** | **Code fixed the order:** one part or wire per step. Claude only wrote the words | **Code suggests** the steps (exact holes and connections). **Claude chooses the order and grouping** (up to 3 in one step) and writes the words. Code checks the order (nothing wired before its part) |

In both, code's checks have the last word. The old LEGO way can still be run with `LEGO_SUGGEST=0`.

### 5.2 What we tested

1. **8 small LEGO sets** (13–31 pieces): the new way against lessons the old way had made a few days before.
2. **8 bigger LEGO sets made both ways the same night**, under the same checks: 5 Technic (42044, 42101, 42102,
   42072, 42058; 112–146 pieces) and 3 System (60054, 4010, 6030; 83–95 pieces). Also **the Off-Road Buggy** (371
   pieces), checked step by step against the problems found by hand.
3. **271 sets made both ways:** old lessons against the new full run.
4. **All 95 Arduino lessons** made again the new way, against the code-order versions.

All lessons were judged by the same, latest checks, so old and new are compared fairly.

### 5.3 Results

| Test | Old way | New way |
|---|---|---|
| LEGO, 8 small sets | 16 repair rounds, $1.77 | **6 repair rounds, $0.66**; 0 issues left either way |
| LEGO, 8 bigger sets | $10.32 | **$9.39**; far fewer first-plan issues on Technic (42101: 14 → 4; 42102: 10 → 2); issues left the same kind both ways |
| LEGO Buggy | 142 steps, 0 issues, $2.95 | 137 steps, 0 issues, $3.35 |
| **LEGO, 271 sets** | 60% with no issues, 198 left, $60.78 | **92% with no issues, 39 left (−80%), $38.54 (−37%)** |
| **Arduino, 94 lessons** | 881 steps | **665 steps (−25%)**, about the same cost; all pass every check |

- **Per LEGO set** (271 sets): 101 better, 159 the same, 11 worse.
- **Fairest pair:** 84 lessons made one day apart under almost the same checks. Issues left 28 → 4; cost $15.30 →
  $7.09.

### 5.4 How the lessons themselves differ

**LEGO:**
- **First plans already follow the physical rules,** so fewer repairs are needed. In 42044, pins go in first and
  then the beam over them, and pieces held lined up get the axle pushed through them.
- **The Buggy's hand-found problems are all right:**
  - the drive motor unit fitted first, then its axles pushed in from both sides;
  - fairing pins before the beam over them;
  - the differential after its axle;
  - the motor block with the motor last.
- **Fuller steps** of 4–6 pieces, closer to a LEGO booklet; slightly fewer steps.
- **One new risk, now caught by code:** Claude copied code's names from the suggested plan ("block 42",
  "drivemotor"). Code now finds those and has the steps reworded.

**Arduino:**
- **Parts and their wires grouped together:** "Put one resistor's legs in column 1 and column 12. Then connect a wire
  from Arduino pin 2 to column 12."
- **Much shorter lessons:**
  - Analog Write Mega: 48 → 17 steps;
  - Digital Pot Control: 43 → 16;
  - LED Bar Graph: 35 → 18.

### 5.5 What the tests also found (now generic rules)

- **Sets with several separate models** (a truck, a street lamp, cones, a figure): the main model is the biggest
  one, and the others are set beside it.
- **Joins the 3D library does not mark:**
  - connectors with an axle end;
  - turntables, hinges;
  - bars into holes and through round plates;
  - plates "with 2 Clips";
  - stud holes;
  - round tiles on a centre stud;
  - arches and brackets.

  Together these add about 10% more real stud joins, with no false ones.
- **Words:** code names, and text that starts from the part the 3D page puts on last, are reworded.
- **Real limits, rare:** a part only wedged in place, and cardboard with no holes in the 3D file.
- **Re-running a lesson blindly does not help:** another roll of the dice made 3 of 4 worse. Re-run only where a
  fix applies, and keep the version with fewer issues.

### 5.6 Decision (15 October 2026)

**The new way, for both domains.** It gives the same or better lessons for less money, with far fewer repairs. The
full LEGO run uses it; all 95 Arduino lessons are already made with it.
