# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 61 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 43.867 | 39.2 | 58.1 | 132 |
| Input tokens | 29104 | 23311 | 43867 | 87311 |
| Output tokens | 6952 | 5380 | 10274 | 20855 |
| Cost (USD) | 0.146 | 0.1261 | 0.2012 | 0.44 |

Estimated cost for 100 manuals at this rate: **$14.63**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 2 (50%) |
| Mean net precision | 0.7 |
| Mean net recall | 0.643 |
| Parts list correct (V1) | 1 / 2 |

**1 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 1.0.

### Check and repair loop

Build → check → repair → final check. **1/3** manuals had check failures after the first build; **1** of those were fully fixed by the repair. Issues in total: 1 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 36.5 | 0.117 | 0.0 |
| repair1 | 1 | 22.1 | 0.087 | 0.0 |

**Accuracy before → after repair** (1 tutorials with an answer key that were repaired): all nets correct 0 → 0; mean net recall 0.286 → 0.286.

### Spec rules and structure

- Manuals with **no rule problems**: 3/3 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 1 | 1 |
| 3 | 0 | 1 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| button | 39.2 | 0.1116 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| docs-nano-33-iot-i2c | 34.3 | 0.1261 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| calibration | 58.1 | 0.2012 | 13 | 44 | 0 | 0 | nets 2/7  |
