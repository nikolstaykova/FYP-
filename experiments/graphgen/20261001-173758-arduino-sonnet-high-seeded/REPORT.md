# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 1 manuals succeeded, 0 failed · wall time 31 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 29.4 | 29.4 | 29.4 | 29 |
| Input tokens | 18552 | 18552 | 18552 | 18552 |
| Output tokens | 4322 | 4322 | 4322 | 4322 |
| Cost (USD) | 0.117 | 0.1174 | 0.1174 | 0.12 |

Estimated cost for 100 manuals at this rate: **$11.74**.

### Accuracy

**1 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 0 / 1 (0%) |
| Mean net precision | 0.0 |
| Mean net recall | 0.0 |
| Parts list correct (V1) | 0 / 1 |

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
| adxl3xx | 29.4 | 0.1174 | 9 | 36 | 0 | 0 | nets 0/5  |
