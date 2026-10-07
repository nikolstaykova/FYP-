# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 1 manuals succeeded, 0 failed · wall time 71 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 69.1 | 69.1 | 69.1 | 69 |
| Input tokens | 19818 | 19818 | 19818 | 19818 |
| Output tokens | 10024 | 10024 | 10024 | 10024 |
| Cost (USD) | 0.136 | 0.1362 | 0.1362 | 0.14 |

Estimated cost for 100 manuals at this rate: **$13.62**.

### Accuracy

**1 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 0 / 1 (0%) |
| Mean net precision | 0.679 |
| Mean net recall | 0.679 |
| Parts list correct (V1) | 1 / 1 |

### Check and repair loop

Build → check → repair → final check. **0/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 69.1 | 0.136 | 0.01 |
| parts | 1 | 0.0 | 0.0 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 1/1 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 1/1; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| row-column-scanning | 69.1 | 0.1362 | 37 | 124 | 0 | 0 | nets 19/28  |
