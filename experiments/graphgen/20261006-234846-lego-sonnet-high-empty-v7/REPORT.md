# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 2 manuals succeeded, 0 failed · wall time 232 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 176.35 | 230.5 | 230.5 | 353 |
| Input tokens | 49950 | 90060 | 90060 | 99900 |
| Output tokens | 23146 | 31292 | 31292 | 46293 |
| Cost (USD) | 0.339 | 0.4877 | 0.4877 | 0.68 |

Estimated cost for 100 manuals at this rate: **$33.86**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.243 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 0.6 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 2 | 176.35 | 0.339 | 1.0 | 0.6 |

### Check and repair loop

Build → check → repair → final check. **1/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 5 → 1.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 147.95 | 0.226 | 0.085 |
| parts | 2 | 2.5 | 0.0 | 0.0 |
| repair1 | 1 | 35.4 | 0.164 | 0.0 |
| repair2 | 1 | 16.2 | 0.062 | 0.0 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 1.0 → 1.0; contact recall 1.0 → 1.0; contact precision 0.5 → 0.333.

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
| 7803-1 | 122.2 | 0.1894 | 38 | 44 | 0 | 0 | pieces 38/38, inv R 1.0, contacts 2/10 |
| 30105-1 | 230.5 | 0.4877 | 37 | 40 | 0 | 0 | pieces 37/37, inv R 1.0, contacts 1/1 |
