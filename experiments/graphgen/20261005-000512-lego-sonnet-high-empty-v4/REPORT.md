# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 3 manuals succeeded, 0 failed · wall time 236 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 124.833 | 76.0 | 233.8 | 374 |
| Input tokens | 89893 | 15620 | 238834 | 269678 |
| Output tokens | 15909 | 10381 | 28507 | 47728 |
| Cost (USD) | 0.255 | 0.1454 | 0.4907 | 0.76 |

Estimated cost for 100 manuals at this rate: **$25.48**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.03 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.295 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.947 | 0.923 |
| Inventory recall, by design (set pieces found) | 0.974 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.333 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 1 | |
| Contact recall | 0.5 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 3 | 124.833 | 0.255 | 0.974 | 0.5 |

### Check and repair loop

Build → check → repair → final check. **2/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 8 → 15.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 97.633 | 0.211 | 0.0 |
| parts | 3 | 2.5 | 0.0 | 0.0 |
| repair1 | 1 | 49.6 | 0.068 | 0.0 |
| repair2 | 1 | 24.5 | 0.064 | 0.0 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 0.756 → 1.0; contact recall 0.0 → 0.0; contact precision None → None.

### Spec rules and structure

- Manuals with **no rule problems**: 1/3 (33%).
- Problems by rule: V3 ×6, V4 ×6, ids ×1 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 64.7 | 0.1284 | 26 | 28 | 0 | 1 | pieces 26/26, inv R 0.923, contacts 1/1 |
| 7246-1 | 76.0 | 0.1454 | 33 | 35 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 41502-1 | 233.8 | 0.4907 | 49 | 57 | 0 | 12 | pieces 49/45, inv R 1.0, contacts 0/2 |
