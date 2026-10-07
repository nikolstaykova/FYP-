# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 48 manuals succeeded, 0 failed · wall time 828 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 48.998 | 44.1 | 75.6 | 2352 |
| Input tokens | 78496 | 72282 | 102851 | 3767786 |
| Output tokens | 6806 | 5835 | 12246 | 326673 |
| Cost (USD) | 0.106 | 0.0893 | 0.1661 | 5.08 |

Estimated cost for 100 manuals at this rate: **$10.59**.

### Accuracy

**48 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 28 / 48 (58%) |
| Mean net precision | 0.754 |
| Mean net recall | 0.727 |
| Parts list correct (V1) | 30 / 48 |

### Check and repair loop

Build → check → repair → final check. **6/48** manuals had check failures after the first build; **3** of those were fully fixed by the repair. Issues in total: 8 → 3.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 48 | 26.725 | 0.059 | 0.006 |
| parts | 48 | 19.152 | 0.037 | 0.0 |
| repair1 | 6 | 19.667 | 0.064 | 0.008 |
| repair2 | 3 | 10.6 | 0.034 | 0.0 |

**Accuracy before → after repair** (6 tutorials with an answer key that were repaired): all nets correct 3 → 3; mean net recall 0.75 → 0.75.

### Spec rules and structure

- Manuals with **no rule problems**: 48/48 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/48; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 48 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| analog-in-out-serial | 44.1 | 0.0814 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| adxl3xx | 53.7 | 0.0852 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-input | 58.4 | 0.0867 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-read-serial | 30.3 | 0.0618 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| arduino-isp | 40.9 | 0.0993 | 10 | 29 | 0 | 0 | nets 1/15  |
| arrays | 52.5 | 0.1171 | 21 | 76 | 0 | 0 | nets 13/13 ✅ |
| analog-write-mega | 102.1 | 0.2396 | 51 | 196 | 0 | 0 | nets 25/25 ✅ |
| arduino-to-breadboard | 93.8 | 0.1877 | 19 | 120 | 0 | 0 | nets 3/7  |
| blink | 30.7 | 0.0483 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| blink-without-delay | 29.7 | 0.0602 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 58.7 | 0.0888 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| calibration | 49.6 | 0.1002 | 13 | 44 | 0 | 0 | nets 4/7  |
| button-mouse-control | 72.5 | 0.161 | 25 | 109 | 0 | 0 | nets 7/7 ✅ |
| debounce | 49.8 | 0.0907 | 8 | 28 | 0 | 0 | nets 2/5  |
| digital-read-serial | 44.0 | 0.0891 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| dimmer | 28.1 | 0.0717 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fading | 27.7 | 0.0547 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fade | 32.4 | 0.0577 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 30.9 | 0.0619 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 29.6 | 0.06 | 6 | 18 | 0 | 0 | nets 2/5  |
| for-loop | 56.7 | 0.1169 | 21 | 76 | 0 | 0 | nets 13/13 ✅ |
| keyboard-logout | 50.4 | 0.1334 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| input-pullup-serial | 55.5 | 0.1332 | 5 | 16 | 0 | 0 | nets 1/4  |
| joystick-mouse-control | 71.5 | 0.1661 | 13 | 38 | 0 | 0 | nets 4/8  |
| keyboard-message | 36.1 | 0.0714 | 7 | 24 | 0 | 0 | nets 3/3 ✅ |
| knock | 26.7 | 0.0569 | 5 | 12 | 0 | 0 | nets 1/4  |
| keyboard-reprogram | 52.4 | 0.136 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-mouse-control | 75.6 | 0.1523 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| memsic2125 | 32.0 | 0.0732 | 7 | 28 | 0 | 0 | nets 4/4 ✅ |
| midi | 46.6 | 0.1039 | 9 | 20 | 0 | 0 | nets 3/4  |
| physical-pixel | 32.1 | 0.0831 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| ping | 28.1 | 0.0562 | 6 | 18 | 0 | 0 | nets 0/3  |
| led-bar-graph | 103.1 | 0.22 | 38 | 182 | 0 | 0 | nets 2/23  |
| pitch-follower | 41.1 | 0.0923 | 11 | 36 | 0 | 0 | nets 2/4  |
| read-analog-voltage | 26.2 | 0.0594 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| read-ascii-string | 34.8 | 0.0863 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| serial-call-response | 59.4 | 0.1507 | 14 | 52 | 0 | 0 | nets 1/5  |
| serial-call-response-ascii | 58.2 | 0.115 | 14 | 52 | 0 | 0 | nets 1/5  |
| smoothing | 29.3 | 0.0579 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| state-change-detection | 35.2 | 0.0725 | 7 | 24 | 0 | 0 | nets 2/5  |
| switch-case-sensor | 29.2 | 0.0613 | 7 | 20 | 0 | 0 | nets 3/3 ✅ |
| row-column-scanning | 142.6 | 0.3749 | 37 | 124 | 0 | 0 | nets 28/28 ✅ |
| tone-melody | 24.1 | 0.0613 | 5 | 12 | 0 | 0 | nets 2/2 ✅ |
| switch-case-serial | 51.7 | 0.1115 | 18 | 64 | 0 | 0 | nets 11/11 ✅ |
| tone-keyboard | 50.0 | 0.1137 | 16 | 56 | 0 | 0 | nets 4/6  |
| tone-multiple | 41.8 | 0.0893 | 12 | 40 | 0 | 0 | nets 0/4  |
| virtual-color-mixer | 42.4 | 0.1094 | 13 | 44 | 0 | 0 | nets 0/5  |
| while-loop | 59.6 | 0.1237 | 14 | 52 | 0 | 0 | nets 5/8  |
