# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 1 manuals succeeded, 0 failed · wall time 33 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 30.9 | 30.9 | 30.9 | 31 |
| Input tokens | 90484 | 90484 | 90484 | 90484 |
| Output tokens | 3418 | 3418 | 3418 | 3418 |
| Cost (USD) | 0.144 | 0.1439 | 0.1439 | 0.14 |

Estimated cost for 100 manuals at this rate: **$14.39**.

### Accuracy

**1 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 1 (100%) |
| Mean net precision | 1.0 |
| Mean net recall | 1.0 |
| Parts list correct (V1) | 1 / 1 |

### Check and repair loop

Build → check → repair → final check. **0/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 13.3 | 0.031 | 0.0 |
| parts | 1 | 17.6 | 0.113 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 1/1 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| blink | 30.9 | 0.1439 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
