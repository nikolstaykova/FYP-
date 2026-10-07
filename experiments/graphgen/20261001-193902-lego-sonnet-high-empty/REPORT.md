# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 5 manuals succeeded, 0 failed · wall time 214 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 112.4 | 106.5 | 165.6 | 562 |
| Input tokens | 38392 | 32843 | 67192 | 191959 |
| Output tokens | 18811 | 16528 | 30367 | 94057 |
| Cost (USD) | 0.254 | 0.2044 | 0.4037 | 1.27 |

Estimated cost for 100 manuals at this rate: **$25.4**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 0.856 | 0.86 |
| Exact pieces (part + colour, needs an inventory page) | 0.169 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.342 | 0.308 |
| Inventory recall, by design (set pieces found) | 0.311 | 0.222 |
| Contact precision (brick/plate/tile pairs) | 0.5 | 0.5 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 2 | |
| Contact recall | 0.417 | 0.25 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 5 | 112.4 | 0.254 | 0.311 | 0.417 |

### Check and repair loop

Build → check → repair → final check. **5/5** manuals had check failures after the first build; **4** of those were fully fixed by the repair. Issues in total: 51 → 1.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 5 | 58.96 | 0.101 | 0.0 |
| repair1 | 5 | 45.12 | 0.125 | 0.0 |
| repair2 | 1 | 41.6 | 0.14 | 0.0 |

**Accuracy before → after repair** (5 booklets repaired): inventory recall 0.29 → 0.311; contact recall 0.417 → 0.417; contact precision 0.5 → 0.5.

### Spec rules and structure

- Manuals with **no rule problems**: 5/5 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 1/5; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 9 | 9 |
| 2 | 10 | 19 |
| 5 | 15 | 65 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 7268-1 | 98.9 | 0.2022 | 26 | 25 | 9 | 0 | pieces 26/32, inv R 0.25, contacts 0/2 |
| 30103-1 | 106.5 | 0.2044 | 24 | 24 | 10 | 0 | pieces 24/28, inv R 0.107, contacts 0/0 |
| 4991-1 | 165.6 | 0.4037 | 31 | 32 | 27 | 0 | pieces 31/26, inv R 0.885, contacts 1/1 |
| 30161-1 | 78.3 | 0.1922 | 23 | 23 | 4 | 0 | pieces 23/45, inv R 0.222, contacts 1/4 |
| 7246-1 | 112.7 | 0.2675 | 30 | 29 | 15 | 0 | pieces 30/33, inv R 0.091, contacts 0/0 |
