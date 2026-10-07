# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 95 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 75.8 | 80.4 | 92.4 | 227 |
| Input tokens | 59534 | 47217 | 94638 | 178602 |
| Output tokens | 10628 | 7766 | 16638 | 31885 |
| Cost (USD) | 0.162 | 0.1133 | 0.261 | 0.49 |

Estimated cost for 100 manuals at this rate: **$16.22**.

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

Build → check → repair → final check. **1/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 1 → 1.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 37.8 | 0.069 | 0.003 |
| parts | 3 | 23.5 | 0.044 | 0.0 |
| repair1 | 1 | 21.8 | 0.076 | 0.0 |
| repair2 | 1 | 21.7 | 0.07 | 0.0 |

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
| button | 54.6 | 0.1122 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| docs-mkr-mkr-zero-weather-data-logger | 80.4 | 0.1133 | 10 | 30 | 1 | 0 | listed parts 1.0 |
| calibration | 92.4 | 0.261 | 13 | 44 | 0 | 0 | nets 2/7  |
