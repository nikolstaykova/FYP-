# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 1 manuals succeeded, 4 failed · wall time 9 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 3.6 | 3.6 | 3.6 | 4 |
| Input tokens | 0 | 0 | 0 | 0 |
| Output tokens | 0 | 0 | 0 | 0 |
| Cost (USD) | 0.0 | 0.0 | 0.0 | 0.0 |

Estimated cost for 100 manuals at this rate: **$0.0**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.879 | 0.879 |
| Inventory recall, by design (set pieces found) | 0.879 | 0.879 |
| Contact precision (brick/plate/tile pairs) | 1.0 | 1.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 1.0 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 1 | 3.6 | 0.0 | 0.879 | 1.0 |

### Check and repair loop

Build → check → repair → final check. **1/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 29 → 29.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 1.135 | 0.0 | 0.0 |
| parts | 1 | 2.5 | 0.0 | 0.0 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 0.879 → 0.879; contact recall 1.0 → 1.0; contact precision 1.0 → 1.0.

### Spec rules and structure

- Manuals with **no rule problems**: 0/1 (0%).
- Problems by rule: V2 ×23 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Failures

- `30103-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `7736-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `7268-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `4991-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 7603-1 | 3.6 | 0.0 | 33 | 11 | 0 | 23 | pieces 33/33, inv R 0.879, contacts 11/11 |
