# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 2 manuals succeeded, 0 failed · wall time 217 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 126.85 | 214.4 | 214.4 | 254 |
| Input tokens | 73517 | 127941 | 127941 | 147034 |
| Output tokens | 21615 | 37649 | 37649 | 43230 |
| Cost (USD) | 0.349 | 0.5863 | 0.5863 | 0.7 |

Estimated cost for 100 manuals at this rate: **$34.88**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 2 (50%) |
| Mean net precision | 0.84 |
| Mean net recall | 0.84 |
| Parts list correct (V1) | 2 / 2 |

### Check and repair loop

Build → check → repair → final check. **1/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 1 → 1.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 60.3 | 0.153 | 0.005 |
| parts | 2 | 13.8 | 0.028 | 0.0 |
| repair1 | 1 | 53.2 | 0.174 | 0.0 |
| repair2 | 1 | 52.3 | 0.162 | 0.0 |

**Accuracy before → after repair** (1 tutorials with an answer key that were repaired): all nets correct 0 → 0; mean net recall 0.679 → 0.679.

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
| button | 39.3 | 0.1113 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| row-column-scanning | 214.4 | 0.5863 | 37 | 124 | 0 | 0 | nets 19/28  |
