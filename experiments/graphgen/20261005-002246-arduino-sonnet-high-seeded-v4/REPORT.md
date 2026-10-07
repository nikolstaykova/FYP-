# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 101 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 35.433 | 44.3 | 47.0 | 106 |
| Input tokens | 18292 | 18696 | 19474 | 54877 |
| Output tokens | 5130 | 5700 | 7971 | 15389 |
| Cost (USD) | 0.089 | 0.0895 | 0.1256 | 0.27 |

Estimated cost for 100 manuals at this rate: **$8.93**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 2 / 2 (100%) |
| Mean net precision | 1.0 |
| Mean net recall | 1.0 |
| Parts list correct (V1) | 2 / 2 |

**1 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.5.

### Check and repair loop

Build → check → repair → final check. **0/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 35.433 | 0.089 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 3/3 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 1 | 1 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| blink | 15.0 | 0.0528 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 44.3 | 0.0895 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| pi-gpio-music-box | 47.0 | 0.1256 | 15 | 68 | 1 | 0 | listed parts 0.5 (missing buzzer) |
