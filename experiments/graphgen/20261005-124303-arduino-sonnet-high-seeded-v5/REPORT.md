# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 2 manuals succeeded, 0 failed · wall time 122 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 72.5 | 118.8 | 118.8 | 145 |
| Input tokens | 42225 | 43058 | 43058 | 84450 |
| Output tokens | 12049 | 21080 | 21080 | 24098 |
| Cost (USD) | 0.134 | 0.2283 | 0.2283 | 0.27 |

Estimated cost for 100 manuals at this rate: **$13.43**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 2 (50%) |
| Mean net precision | 0.84 |
| Mean net recall | 0.84 |
| Parts list correct (V1) | 2 / 2 |

### Check and repair loop

Build → check → repair → final check. **0/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 56.65 | 0.109 | 0.01 |
| parts | 2 | 15.85 | 0.025 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 2/2 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/2; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| tone-melody | 26.2 | 0.0403 | 5 | 12 | 0 | 0 | nets 2/2 ✅ |
| row-column-scanning | 118.8 | 0.2283 | 45 | 140 | 0 | 0 | nets 19/28  |
