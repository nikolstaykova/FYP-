# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 60 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 43.467 | 39.2 | 58.8 | 130 |
| Input tokens | 29883 | 30986 | 41422 | 89648 |
| Output tokens | 5562 | 4923 | 7494 | 16685 |
| Cost (USD) | 0.13 | 0.1308 | 0.1409 | 0.39 |

Estimated cost for 100 manuals at this rate: **$13.0**.

### Accuracy

**1 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 1 (100%) |
| Mean net precision | 1.0 |
| Mean net recall | 1.0 |
| Parts list correct (V1) | 1 / 1 |

**2 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.75.

### Check and repair loop

Build → check → repair → final check. **0/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 43.467 | 0.13 | 0.003 |

### Spec rules and structure

- Manuals with **no rule problems**: 3/3 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| button | 32.4 | 0.1182 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| docs-nano-33-iot-i2c | 39.2 | 0.1308 | 13 | 34 | 0 | 0 | listed parts 1.0 |
| pi-gpio-music-box | 58.8 | 0.1409 | 15 | 68 | 0 | 0 | listed parts 0.5 (missing buzzer) |
