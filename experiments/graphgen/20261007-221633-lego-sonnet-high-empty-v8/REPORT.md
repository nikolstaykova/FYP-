# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 1 manuals succeeded, 0 failed · wall time 319 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 317.2 | 317.2 | 317.2 | 317 |
| Input tokens | 74826 | 74826 | 74826 | 74826 |
| Output tokens | 42398 | 42398 | 42398 | 42398 |
| Cost (USD) | 0.588 | 0.5879 | 0.5879 | 0.59 |

Estimated cost for 100 manuals at this rate: **$58.79**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.0 | 0.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 1 | |
| Contact recall | None | None |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 1 | 317.2 | 0.588 | 1.0 | None |

### Check and repair loop

Build → check → repair → final check. **1/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 42 → 31.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 71.4 | 0.127 | 0.01 |
| parts | 1 | 2.5 | 0.0 | 0.0 |
| repair1 | 1 | 89.8 | 0.187 | 0.01 |
| repair2 | 1 | 153.5 | 0.274 | 0.01 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 1.0 → 1.0; contact recall None → None; contact precision 0.0 → 0.0.

### Spec rules and structure

- Manuals with **no rule problems**: 0/1 (0%).
- Problems by rule: V2 ×16 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 317.2 | 0.5879 | 28 | 10 | 0 | 16 | pieces 28/28, inv R 1.0, contacts 0/0 |
