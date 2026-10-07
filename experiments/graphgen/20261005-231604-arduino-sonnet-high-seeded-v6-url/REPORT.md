# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 1 manuals succeeded, 1 failed · wall time 31 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 29.0 | 29.0 | 29.0 | 29 |
| Input tokens | 71310 | 71310 | 71310 | 71310 |
| Output tokens | 2944 | 2944 | 2944 | 2944 |
| Cost (USD) | 0.14 | 0.1395 | 0.1395 | 0.14 |

Estimated cost for 100 manuals at this rate: **$13.95**.

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
| build | 1 | 13.0 | 0.03 | 0.01 |
| parts | 1 | 16.0 | 0.11 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 1/1 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Failures

- `button`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:20am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| blink | 29.0 | 0.1395 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
