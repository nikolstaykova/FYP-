# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 19 manuals succeeded, 3 failed · wall time 2459 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 308.005 | 258.0 | 643.3 | 5852 |
| Input tokens | 147624 | 82568 | 324093 | 2804849 |
| Output tokens | 41395 | 35238 | 88838 | 786502 |
| Cost (USD) | 0.692 | 0.5224 | 1.4835 | 13.14 |

Estimated cost for 100 manuals at this rate: **$69.18**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.001 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.464 | 0.4 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 4 | |
| Contact recall | 0.582 | 0.5 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 18 | 289.378 | 0.654 | 1.0 | 0.564 |
| 100-249 | 1 | 643.3 | 1.371 | 1.0 | 0.833 |

### Check and repair loop

Build → check → repair → final check. **17/19** manuals had check failures after the first build; **7** of those were fully fixed by the repair. Issues in total: 123 → 26.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 19 | 252.521 | 0.45 | 0.005 |
| parts | 19 | 0.411 | 0.0 | 0.0 |
| repair1 | 15 | 42.287 | 0.222 | 0.004 |
| repair2 | 11 | 37.464 | 0.115 | 0.005 |

**Accuracy before → after repair** (15 booklets repaired): inventory recall 0.997 → 1.0; contact recall 0.552 → 0.566; contact precision 0.48 → 0.445.

### Spec rules and structure

- Manuals with **no rule problems**: 16/19 (84%).
- Problems by rule: V2 ×3 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/19; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 19 | 0 | 0 |

### Failures

- `40386-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)
- `4778-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)
- `70127-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 95.8 | 0.151 | 28 | 31 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4991-1 | 109.1 | 0.2444 | 26 | 25 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 0/1 |
| 7268-1 | 112.1 | 0.2531 | 32 | 45 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 2/2 |
| 7603-1 | 111.4 | 0.2676 | 33 | 34 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7736-1 | 127.1 | 0.3731 | 28 | 29 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4641-1 | 293.5 | 0.7429 | 29 | 29 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 7246-1 | 255.5 | 0.5063 | 33 | 32 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 5969-1 | 299.3 | 0.7098 | 33 | 40 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 0/1 |
| 30161-1 | 258.0 | 0.5224 | 45 | 52 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 30313-1 | 157.2 | 0.3266 | 44 | 47 | 0 | 0 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 21003-1 | 92.3 | 0.2811 | 57 | 74 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 15/16 |
| 40396-1 | 142.2 | 0.228 | 53 | 58 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 4/8 |
| 41502-1 | 374.2 | 0.6201 | 45 | 48 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 1/2 |
| 41181-1 | 386.1 | 1.073 | 63 | 71 | 0 | 0 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 7902-1 | 462.7 | 1.0538 | 62 | 65 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 7634-1 | 696.8 | 1.4835 | 74 | 101 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 1/3 |
| 41589-1 | 597.0 | 1.392 | 79 | 100 | 0 | 0 | pieces 79/79, inv R 1.0, contacts 15/15 |
| 60054-1 | 638.5 | 1.545 | 91 | 103 | 0 | 0 | pieces 91/91, inv R 1.0, contacts 2/4 |
| 40148-1 | 643.3 | 1.3712 | 100 | 118 | 0 | 1 | pieces 100/100, inv R 1.0, contacts 5/6 |
