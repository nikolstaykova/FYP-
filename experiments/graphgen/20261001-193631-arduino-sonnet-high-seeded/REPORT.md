# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 2 manuals succeeded, 0 failed · wall time 44 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 39.05 | 40.2 | 40.2 | 78 |
| Input tokens | 18674 | 18958 | 18958 | 37347 |
| Output tokens | 5556 | 5609 | 5609 | 11111 |
| Cost (USD) | 0.11 | 0.1103 | 0.1103 | 0.22 |

Estimated cost for 100 manuals at this rate: **$10.97**.

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
| build | 2 | 39.05 | 0.11 | 0.0 |

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
| digital-read-serial | 37.9 | 0.1103 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| button | 40.2 | 0.1091 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
