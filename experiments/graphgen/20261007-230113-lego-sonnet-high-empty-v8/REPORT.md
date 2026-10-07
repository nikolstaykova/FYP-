# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 6 manuals succeeded, 0 failed · wall time 1620 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 573.033 | 537.9 | 1004.9 | 3438 |
| Input tokens | 131234 | 128931 | 160244 | 787404 |
| Output tokens | 75632 | 73079 | 131854 | 453795 |
| Cost (USD) | 1.042 | 0.9943 | 1.7137 | 6.25 |

Estimated cost for 100 manuals at this rate: **$104.2**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.106 | 0.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 3 | |
| Contact recall | 0.288 | 0.364 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 6 | 573.033 | 1.042 | 1.0 | 0.288 |

### Check and repair loop

Build → check → repair → final check. **6/6** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 222 → 114.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 6 | 182.267 | 0.299 | 0.01 |
| parts | 6 | 1.25 | 0.0 | 0.0 |
| repair1 | 6 | 183.65 | 0.355 | 0.01 |
| repair2 | 6 | 205.867 | 0.388 | 0.01 |

**Accuracy before → after repair** (6 booklets repaired): inventory recall 1.0 → 1.0; contact recall 0.455 → 0.288; contact precision 0.188 → 0.106.

### Spec rules and structure

- Manuals with **no rule problems**: 0/6 (0%).
- Problems by rule: V2 ×59 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/6; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 388.2 | 0.7854 | 26 | 15 | 0 | 6 | pieces 26/26, inv R 1.0, contacts 0/1 |
| 30103-1 | 491.2 | 0.8604 | 28 | 16 | 0 | 11 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7268-1 | 612.0 | 1.0466 | 32 | 25 | 0 | 8 | pieces 32/32, inv R 1.0, contacts 1/2 |
| 7736-1 | 404.0 | 0.8517 | 28 | 14 | 0 | 13 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7603-1 | 537.9 | 0.9943 | 33 | 24 | 0 | 8 | pieces 33/33, inv R 1.0, contacts 4/11 |
| 7246-1 | 1004.9 | 1.7137 | 33 | 14 | 0 | 13 | pieces 33/33, inv R 1.0, contacts 0/0 |
