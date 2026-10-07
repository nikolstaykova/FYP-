# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 10 manuals succeeded, 0 failed · wall time 500 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 88.37 | 71.0 | 174.5 | 884 |
| Input tokens | 23782 | 14256 | 48374 | 237822 |
| Output tokens | 12796 | 10811 | 24564 | 127956 |
| Cost (USD) | 0.198 | 0.1348 | 0.4061 | 1.98 |

Estimated cost for 100 manuals at this rate: **$19.8**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 0.991 | 1.02 |
| Inventory precision (pieces that are in the set) | 0.408 | 0.562 |
| Inventory recall (set pieces found) | 0.438 | 0.643 |
| Contact precision (brick/plate/tile pairs) | 0.283 | 0.0 |
| Contact recall | 0.458 | 0.5 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 10 | 88.37 | 0.198 | 0.438 | 0.458 |

### Spec rules and structure

- Manuals with **no rule problems**: 0/10 (0%).
- Problems by rule: V4 ×88, V3 ×67 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 7/10; overrides used in 6.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 12 | 12 |
| 2 | 6 | 18 |
| 5 | 5 | 69 |
| 10 | 24 | 157 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 57.6 | 0.0965 | 25 | 26 | 12 | 14 | pieces 25/28, inv R 0.0, contacts 0/0 |
| 7268-1 | 58.2 | 0.1073 | 24 | 23 | 6 | 20 | pieces 24/32, inv R 0.0, contacts 0/2 |
| 4991-1 | 65.5 | 0.1315 | 31 | 32 | 27 | 11 | pieces 31/26, inv R 0.846, contacts 1/1 |
| 7736-1 | 71.0 | 0.2255 | 33 | 36 | 19 | 12 | pieces 33/28, inv R 0.643, contacts 0/0 |
| 7603-1 | 75.0 | 0.1348 | 26 | 29 | 5 | 19 | pieces 26/33, inv R 0.0, contacts 0/11 |
| 4641-1 | 111.4 | 0.322 | 34 | 33 | 24 | 10 | pieces 34/29, inv R 0.931, contacts 0/0 |
| 30161-1 | 58.8 | 0.1016 | 30 | 32 | 2 | 16 | pieces 30/45, inv R 0.089, contacts 1/4 |
| 7246-1 | 63.6 | 0.1279 | 33 | 32 | 7 | 17 | pieces 33/33, inv R 0.0, contacts 0/0 |
| 5969-1 | 148.1 | 0.3268 | 41 | 43 | 31 | 22 | pieces 41/33, inv R 0.939, contacts 1/1 |
| 41502-1 | 174.5 | 0.4061 | 46 | 45 | 24 | 14 | pieces 46/45, inv R 0.933, contacts 1/2 |
