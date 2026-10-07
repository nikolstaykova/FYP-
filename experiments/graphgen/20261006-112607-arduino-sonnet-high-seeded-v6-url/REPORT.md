# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 2 manuals succeeded, 0 failed · wall time 58 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 46.05 | 55.3 | 55.3 | 92 |
| Input tokens | 71078 | 71316 | 71316 | 142156 |
| Output tokens | 4598 | 6033 | 6033 | 9196 |
| Cost (USD) | 0.156 | 0.1708 | 0.1708 | 0.31 |

Estimated cost for 100 manuals at this rate: **$15.63**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 2 / 2 (100%) |
| Mean net precision | 1.0 |
| Mean net recall | 1.0 |
| Parts list correct (V1) | 2 / 2 |

### Check and repair loop

Build → check → repair → final check. **0/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 20.95 | 0.044 | 0.01 |
| parts | 2 | 25.1 | 0.112 | 0.0 |

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
| blink | 36.8 | 0.1418 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 55.3 | 0.1708 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
