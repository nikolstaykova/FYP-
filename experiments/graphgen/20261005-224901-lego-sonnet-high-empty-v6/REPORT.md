# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 21 manuals succeeded, 3 failed · wall time 1811 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 192.419 | 155.5 | 393.4 | 4041 |
| Input tokens | 91024 | 42534 | 254399 | 1911503 |
| Output tokens | 25891 | 21947 | 48269 | 543713 |
| Cost (USD) | 0.429 | 0.3352 | 0.7934 | 9.01 |

Estimated cost for 100 manuals at this rate: **$42.88**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.001 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.436 | 0.417 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 4 | |
| Contact recall | 0.655 | 0.75 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 18 | 172.206 | 0.387 | 1.0 | 0.629 |
| 100-249 | 3 | 313.7 | 0.678 | 1.0 | 0.778 |

### Check and repair loop

Build → check → repair → final check. **11/21** manuals had check failures after the first build; **1** of those were fully fixed by the repair. Issues in total: 24 → 16.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 21 | 174.543 | 0.339 | 0.01 |
| parts | 21 | 0.371 | 0.0 | 0.0 |
| repair1 | 7 | 30.429 | 0.192 | 0.004 |
| repair2 | 6 | 25.75 | 0.091 | 0.005 |

**Accuracy before → after repair** (7 booklets repaired): inventory recall 1.0 → 1.0; contact recall 0.643 → 0.643; contact precision 0.49 → 0.49.

### Spec rules and structure

- Manuals with **no rule problems**: 17/21 (81%).
- Problems by rule: V2 ×4 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/21; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 21 | 0 | 0 |

### Failures

- `7936-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:20am (Europe/Dublin)
- `40181-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:20am (Europe/Dublin)
- `40386-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 2:20am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 49.8 | 0.0956 | 26 | 30 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 1/1 |
| 7268-1 | 62.3 | 0.1124 | 32 | 36 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 30103-1 | 69.0 | 0.1185 | 28 | 33 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7736-1 | 40.5 | 0.1739 | 28 | 29 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7603-1 | 84.9 | 0.1476 | 33 | 38 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7246-1 | 46.6 | 0.0933 | 33 | 35 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 4641-1 | 124.0 | 0.3352 | 29 | 35 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 30161-1 | 87.7 | 0.1504 | 45 | 51 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 3/4 |
| 5969-1 | 161.3 | 0.4487 | 33 | 41 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 30313-1 | 84.3 | 0.1486 | 44 | 48 | 0 | 0 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 41502-1 | 187.5 | 0.2517 | 45 | 46 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 21003-1 | 110.5 | 0.3034 | 57 | 94 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 15/16 |
| 41181-1 | 155.5 | 0.6411 | 63 | 78 | 0 | 0 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 40396-1 | 335.8 | 0.4638 | 53 | 60 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 7902-1 | 339.6 | 0.7934 | 62 | 73 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 41589-1 | 398.5 | 0.6937 | 79 | 108 | 0 | 0 | pieces 79/79, inv R 1.0, contacts 13/15 |
| 7634-1 | 441.6 | 1.0522 | 74 | 109 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 0/3 |
| 60054-1 | 320.3 | 0.9475 | 91 | 102 | 0 | 1 | pieces 91/91, inv R 1.0, contacts 0/4 |
| 40148-1 | 207.6 | 0.6693 | 100 | 116 | 0 | 1 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 70127-1 | 340.1 | 0.6585 | 105 | 129 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 4778-1 | 393.4 | 0.707 | 104 | 126 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
