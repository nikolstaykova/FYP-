# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 2 manuals succeeded, 0 failed · wall time 468 s with 2 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 456.95 | 466.7 | 466.7 | 914 |
| Input tokens | 181733 | 320932 | 320932 | 363466 |
| Output tokens | 60410 | 65657 | 65657 | 120820 |
| Cost (USD) | 0.967 | 1.2128 | 1.2128 | 1.93 |

Estimated cost for 100 manuals at this rate: **$96.73**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.005 | 0.01 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.548 | 0.667 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 1.0 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 1 | 447.2 | 0.722 | 1.0 | 1.0 |
| 100-249 | 1 | 466.7 | 1.213 | 1.0 | 1.0 |

### Check and repair loop

Build → check → repair → final check. **2/2** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 6 → 2.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 2 | 418.05 | 0.755 | 0.0 |
| parts | 2 | 2.6 | 0.0 | 0.0 |
| repair1 | 1 | 39.8 | 0.298 | 0.0 |
| repair2 | 1 | 32.8 | 0.126 | 0.0 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 1.0 → 1.0; contact recall 1.0 → 1.0; contact precision 0.429 → 0.429.

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
| 41502-1 | 447.2 | 0.7218 | 45 | 50 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 70127-1 | 466.7 | 1.2128 | 105 | 136 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
