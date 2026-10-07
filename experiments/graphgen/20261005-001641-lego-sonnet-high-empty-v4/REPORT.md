# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 3 manuals succeeded, 0 failed · wall time 289 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 175.933 | 189.4 | 287.3 | 528 |
| Input tokens | 467421 | 530512 | 839166 | 1402262 |
| Output tokens | 22288 | 22651 | 37106 | 66865 |
| Cost (USD) | 0.438 | 0.4605 | 0.7329 | 1.31 |

Estimated cost for 100 manuals at this rate: **$43.76**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.363 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.282 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.781 | 0.885 |
| Inventory recall, by design (set pieces found) | 0.954 | 0.978 |
| Contact precision (brick/plate/tile pairs) | 0.733 | 1.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 0 | |
| Contact recall | 0.833 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 3 | 175.933 | 0.438 | 0.954 | 0.833 |

### Check and repair loop

Build → check → repair → final check. **2/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 19 → 18.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 162.267 | 0.415 | 0.0 |
| parts | 3 | 2.5 | 0.0 | 0.0 |
| repair1 | 2 | 16.75 | 0.034 | 0.0 |

**Accuracy before → after repair** (2 booklets repaired): inventory recall 0.869 → 0.989; contact recall 0.5 → 0.75; contact precision 0.2 → 0.6.

### Spec rules and structure

- Manuals with **no rule problems**: 1/3 (33%).
- Problems by rule: V3 ×14 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 2/3; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 51.1 | 0.1194 | 26 | 30 | 0 | 0 | pieces 26/26, inv R 0.885, contacts 1/1 |
| 41502-1 | 189.4 | 0.4605 | 45 | 57 | 0 | 1 | pieces 45/45, inv R 0.978, contacts 1/2 |
| 5761-1 | 287.3 | 0.7329 | 119 | 124 | 0 | 13 | pieces 119/57, inv R 1.0, contacts 1/1 |
