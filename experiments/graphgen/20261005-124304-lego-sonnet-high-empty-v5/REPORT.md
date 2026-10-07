# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 1 manuals succeeded, 0 failed · wall time 289 s with 1 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 287.3 | 287.3 | 287.3 | 287 |
| Input tokens | 681983 | 681983 | 681983 | 681983 |
| Output tokens | 35910 | 35910 | 35910 | 35910 |
| Cost (USD) | 0.617 | 0.6165 | 0.6165 | 0.62 |

Estimated cost for 100 manuals at this rate: **$61.65**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.044 | 1.04 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.957 | 0.957 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.25 | 0.25 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 0.5 | 0.5 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 1 | 287.3 | 0.617 | 1.0 | 0.5 |

### Check and repair loop

Build → check → repair → final check. **1/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 13 → 18.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 218.1 | 0.483 | 0.0 |
| parts | 1 | 2.7 | 0.0 | 0.0 |
| repair1 | 1 | 52.1 | 0.085 | 0.0 |
| repair2 | 1 | 14.4 | 0.048 | 0.0 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 0.711 → 1.0; contact recall 0.0 → 0.5; contact precision None → 0.25.

### Spec rules and structure

- Manuals with **no rule problems**: 0/1 (0%).
- Problems by rule: V4 ×14, V3 ×3 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 41502-1 | 287.3 | 0.6165 | 47 | 73 | 0 | 17 | pieces 47/45, inv R 1.0, contacts 1/2 |
