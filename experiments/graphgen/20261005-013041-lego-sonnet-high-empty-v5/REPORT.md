# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 1 manuals succeeded, 0 failed · wall time 84 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 82.9 | 82.9 | 82.9 | 83 |
| Input tokens | 27448 | 27448 | 27448 | 27448 |
| Output tokens | 9086 | 9086 | 9086 | 9086 |
| Cost (USD) | 0.17 | 0.1698 | 0.1698 | 0.17 |

Estimated cost for 100 manuals at this rate: **$16.98**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.0 | 0.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 0.0 | 0.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 1 | 82.9 | 0.17 | 1.0 | 0.0 |

### Check and repair loop

Build → check → repair → final check. **0/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 80.2 | 0.17 | 0.0 |
| parts | 1 | 2.7 | 0.0 | 0.0 |

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
| 4991-1 | 82.9 | 0.1698 | 26 | 28 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 0/1 |
