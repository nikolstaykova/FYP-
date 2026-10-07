# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 3 manuals succeeded, 0 failed · wall time 356 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 160.633 | 74.9 | 354.3 | 482 |
| Input tokens | 24217 | 14254 | 44282 | 72652 |
| Output tokens | 21397 | 9512 | 47401 | 64190 |
| Cost (USD) | 0.29 | 0.1312 | 0.6302 | 0.87 |

Estimated cost for 100 manuals at this rate: **$28.99**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.25 | 0.25 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 1 | |
| Contact recall | 0.25 | 0.5 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 3 | 160.633 | 0.29 | 1.0 | 0.25 |

### Check and repair loop

Build → check → repair → final check. **2/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 6 → 6.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 158.233 | 0.29 | 0.0 |
| parts | 3 | 2.4 | 0.0 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 1/3 (33%).
- Problems by rule: V3 ×3, V4 ×2 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 2/3; overrides used in 2.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 52.7 | 0.1083 | 26 | 28 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 0/1 |
| 7246-1 | 74.9 | 0.1312 | 33 | 33 | 0 | 2 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 41502-1 | 354.3 | 0.6302 | 45 | 72 | 0 | 3 | pieces 45/45, inv R 1.0, contacts 1/2 |
