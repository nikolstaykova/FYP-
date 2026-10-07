# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 140 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 76.2 | 90.6 | 93.1 | 229 |
| Input tokens | 36818 | 45663 | 45978 | 110454 |
| Output tokens | 7277 | 7843 | 7886 | 21831 |
| Cost (USD) | 0.138 | 0.1489 | 0.1705 | 0.41 |

Estimated cost for 100 manuals at this rate: **$13.78**.

### Accuracy

**1 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 1 (100%) |
| Mean net precision | 1.0 |
| Mean net recall | 1.0 |
| Parts list correct (V1) | 1 / 1 |

**2 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.834.

### Check and repair loop

Build → check → repair → final check. **0/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 39.6 | 0.098 | 0.0 |
| parts | 3 | 36.6 | 0.04 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 3/3 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 3 | 3 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| button | 44.9 | 0.094 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| docs-nano-33-iot-i2c | 93.1 | 0.1705 | 13 | 36 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 90.6 | 0.1489 | 14 | 40 | 3 | 0 | listed parts 0.667 (missing sensor) |
