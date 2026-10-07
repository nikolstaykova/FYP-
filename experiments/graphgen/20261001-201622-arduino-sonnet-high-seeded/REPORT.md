# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 2 manuals succeeded, 0 failed · wall time 61 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 57.3 | 58.9 | 58.9 | 115 |
| Input tokens | 19180 | 19516 | 19516 | 38360 |
| Output tokens | 8710 | 9282 | 9282 | 17419 |
| Cost (USD) | 0.122 | 0.1264 | 0.1264 | 0.24 |

Estimated cost for 100 manuals at this rate: **$12.2**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 2 (50%) |
| Mean net precision | 0.785 |
| Mean net recall | 0.834 |
| Parts list correct (V1) | 1 / 2 |

### Check and repair loop

Build → check → repair → final check. **0/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 57.3 | 0.122 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 2/2 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 1/2; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 1 | 1 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| switch-case-serial | 55.7 | 0.1264 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-keyboard | 58.9 | 0.1176 | 18 | 64 | 1 | 0 | nets 4/6  |
