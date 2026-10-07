# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 4 manuals succeeded, 0 failed · wall time 6 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 5.35 | 5.4 | 5.4 | 21 |
| Input tokens | 0 | 0 | 0 | 0 |
| Output tokens | 0 | 0 | 0 | 0 |
| Cost (USD) | 0.0 | 0.0 | 0.0 | 0.0 |

Estimated cost for 100 manuals at this rate: **$0.0**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 2.157 | 2.07 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.554 | 0.649 |
| Inventory recall, by design (set pieces found) | 0.865 | 0.923 |
| Contact precision (brick/plate/tile pairs) | 1.0 | 1.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 1.0 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 2 | 5.35 | 0.0 | 0.806 | 1.0 |
| 250+ | 2 | 5.35 | 0.0 | 0.925 | 1.0 |

### Check and repair loop

Build → check → repair → final check. **4/4** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 1442 → 1442.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 4 | 2.868 | 0.0 | 0.0 |
| parts | 4 | 2.5 | 0.0 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 0/4 (0%).
- Problems by rule: V2 ×1311 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/4; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 4 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 21033-1 | 5.3 | 0.0 | 443 | 140 | 0 | 316 | pieces 443/444, inv R 0.982, contacts 140/140 |
| 41502-1 | 5.3 | 0.0 | 186 | 2 | 0 | 183 | pieces 186/45, inv R 0.689, contacts 2/2 |
| 7893-1 | 5.4 | 0.0 | 803 | 17 | 0 | 777 | pieces 803/387, inv R 0.868, contacts 17/17 |
| 4991-1 | 5.4 | 0.0 | 37 | 1 | 0 | 35 | pieces 37/26, inv R 0.923, contacts 1/1 |
