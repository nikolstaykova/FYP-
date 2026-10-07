# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 1 manuals succeeded, 3 failed · wall time 678 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 583.4 | 583.4 | 583.4 | 583 |
| Input tokens | 139513 | 139513 | 139513 | 139513 |
| Output tokens | 75587 | 75587 | 75587 | 75587 |
| Cost (USD) | 1.079 | 1.0793 | 1.0793 | 1.08 |

Estimated cost for 100 manuals at this rate: **$107.93**.

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
| <100 | 1 | 583.4 | 1.079 | 1.0 | None |

### Check and repair loop

Build → check → repair → final check. **1/1** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 41 → 26.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 1 | 73.3 | 0.179 | 0.01 |
| parts | 1 | 2.7 | 0.0 | 0.0 |
| repair1 | 1 | 365.2 | 0.504 | 0.01 |
| repair2 | 1 | 142.2 | 0.397 | 0.01 |

**Accuracy before → after repair** (1 booklets repaired): inventory recall 1.0 → 1.0; contact recall None → None; contact precision 0.0 → 0.0.

### Spec rules and structure

- Manuals with **no rule problems**: 0/1 (0%).
- Problems by rule: V2 ×10 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/1; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |

### Failures

- `41504-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:50am (Europe/Dublin)
- `30161-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:50am (Europe/Dublin)
- `41589-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:50am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 583.4 | 1.0793 | 28 | 16 | 0 | 10 | pieces 28/28, inv R 1.0, contacts 0/0 |
