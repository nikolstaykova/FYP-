# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 43 manuals succeeded, 2 failed · wall time 3463 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 286.398 | 259.1 | 533.1 | 12315 |
| Input tokens | 125373 | 58051 | 265483 | 5391037 |
| Output tokens | 43831 | 41715 | 82012 | 1884714 |
| Cost (USD) | 0.707 | 0.4984 | 1.3277 | 30.39 |

Estimated cost for 100 manuals at this rate: **$70.66**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.021 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.998 | 1.0 |
| Inventory recall, by design (set pieces found) | 0.998 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.368 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 7 | |
| Contact recall | 0.652 | 0.667 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 29 | 194.069 | 0.443 | 0.997 | 0.653 |
| 100-249 | 12 | 451.575 | 1.212 | 1.0 | 0.652 |
| 250+ | 2 | 634.1 | 1.491 | 1.0 | 0.635 |

### Check and repair loop

Build → check → repair → final check. **37/43** manuals had check failures after the first build; **2** of those were fully fixed by the repair. Issues in total: 367 → 343.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 43 | 240.486 | 0.512 | 0.008 |
| parts | 43 | 0.223 | 0.0 | 0.0 |
| repair1 | 17 | 68.518 | 0.336 | 0.018 |
| repair2 | 13 | 61.5 | 0.204 | 0.011 |

**Accuracy before → after repair** (17 booklets repaired): inventory recall 1.0 → 1.0; contact recall 0.702 → 0.702; contact precision 0.466 → 0.466.

### Spec rules and structure

- Manuals with **no rule problems**: 14/43 (33%).
- Problems by rule: V2 ×211, V3 ×88, V4 ×16 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 21/43; overrides used in 20.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 43 | 0 | 0 |

### Failures

- `40413-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:10am (Europe/Dublin)
- `5981-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:10am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 49.4 | 0.0985 | 28 | 30 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4991-1 | 63.6 | 0.0912 | 26 | 30 | 0 | 1 | pieces 26/26, inv R 0.923, contacts 1/1 |
| 7603-1 | 83.5 | 0.14 | 33 | 34 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7268-1 | 96.7 | 0.1594 | 32 | 32 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 7736-1 | 60.0 | 0.2069 | 28 | 47 | 0 | 5 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4641-1 | 94.8 | 0.3041 | 29 | 30 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 7246-1 | 77.2 | 0.1144 | 33 | 33 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 30313-1 | 113.2 | 0.2054 | 44 | 71 | 0 | 5 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 30161-1 | 226.9 | 0.3713 | 45 | 94 | 0 | 2 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 5969-1 | 285.3 | 0.7473 | 33 | 69 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 21003-1 | 91.1 | 0.2925 | 57 | 69 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 14/16 |
| 41502-1 | 333.7 | 0.4606 | 45 | 76 | 0 | 3 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 40396-1 | 307.9 | 0.4762 | 53 | 87 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 41181-1 | 195.4 | 0.7358 | 63 | 65 | 0 | 3 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 7902-1 | 363.2 | 0.9333 | 62 | 76 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 41589-1 | 189.3 | 0.4848 | 79 | 99 | 0 | 1 | pieces 79/79, inv R 1.0, contacts 12/15 |
| 7634-1 | 362.2 | 0.9812 | 74 | 94 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 2/3 |
| 60054-1 | 307.2 | 1.03 | 91 | 103 | 0 | 3 | pieces 91/91, inv R 1.0, contacts 2/4 |
| 40148-1 | 344.3 | 0.9435 | 100 | 113 | 0 | 3 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 4778-1 | 352.4 | 0.7158 | 104 | 114 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
| 70127-1 | 375.1 | 1.0016 | 105 | 136 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 40386-1 | 315.1 | 0.8628 | 115 | 176 | 0 | 0 | pieces 115/115, inv R 1.0, contacts 0/0 |
| 40181-1 | 486.5 | 1.2669 | 139 | 149 | 0 | 8 | pieces 139/139, inv R 1.0, contacts 30/36 |
| 21026-1 | 354.6 | 1.3051 | 212 | 255 | 0 | 10 | pieces 212/212, inv R 1.0, contacts 17/23 |
| 7936-1 | 479.7 | 1.3277 | 138 | 168 | 0 | 10 | pieces 138/138, inv R 1.0, contacts 10/14 |
| 3316-1 | 164.2 | 0.4984 | 206 | 0 | 0 | 206 | pieces 206/206, inv R 1.0, contacts 0/11 |
| 40335-1 | 533.1 | 1.4796 | 150 | 170 | 0 | 10 | pieces 150/150, inv R 1.0, contacts 14/17 |
| 8159-1 | 408.7 | 0.894 | 228 | 252 | 0 | 0 | pieces 228/228, inv R 1.0, contacts 10/46 |
| 7992-1 | 747.5 | 2.0844 | 214 | 233 | 0 | 3 | pieces 214/214, inv R 1.0, contacts 26/43 |
| 40199-1 | 603.7 | 1.3105 | 286 | 306 | 0 | 5 | pieces 286/286, inv R 1.0, contacts 98/134 |
| 8658-1 | 154.8 | 0.2618 | 32 | 83 | 0 | 4 | pieces 32/32, inv R 1.0, contacts 4/5 |
| 21113-1 | 857.7 | 2.163 | 243 | 280 | 0 | 2 | pieces 243/243, inv R 1.0, contacts 93/102 |
| 10170-1 | 664.5 | 1.6724 | 366 | 430 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 54/100 |
| 30311-1 | 170.3 | 0.2604 | 46 | 55 | 0 | 3 | pieces 46/46, inv R 1.0, contacts 2/4 |
| 60001-1 | 259.1 | 0.8234 | 72 | 77 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 4/8 |
| 7808-1 | 42.5 | 0.0958 | 34 | 35 | 0 | 1 | pieces 34/34, inv R 1.0, contacts 1/1 |
| 7306-1 | 419.6 | 1.0839 | 57 | 61 | 0 | 2 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 4904-1 | 213.4 | 0.3313 | 34 | 73 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 7/11 |
| 30312-1 | 132.7 | 0.2238 | 36 | 53 | 0 | 0 | pieces 36/36, inv R 1.0, contacts 0/1 |
| 6966-1 | 135.8 | 0.2183 | 38 | 39 | 0 | 3 | pieces 38/38, inv R 1.0, contacts 0/0 |
| 9469-1 | 360.1 | 0.9273 | 73 | 90 | 0 | 10 | pieces 73/73, inv R 1.0, contacts 4/6 |
| 41504-1 | 183.8 | 0.407 | 50 | 55 | 0 | 0 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 30300-1 | 255.3 | 0.3942 | 57 | 66 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 2/3 |
