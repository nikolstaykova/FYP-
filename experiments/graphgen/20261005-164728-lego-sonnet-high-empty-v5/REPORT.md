# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 49 manuals succeeded, 4 failed · wall time 3307 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 364.733 | 259.9 | 740.1 | 17872 |
| Input tokens | 1845530 | 932334 | 5080386 | 90430971 |
| Output tokens | 47077 | 31418 | 95675 | 2306776 |
| Cost (USD) | 1.094 | 0.7292 | 2.6915 | 53.6 |

Estimated cost for 100 manuals at this rate: **$109.39**.

### Accuracy

**3 PDF(s) contained no building instructions** (e.g. advent-calendar covers); Claude returned an empty graph instead of inventing parts. Left out of the accuracy below: `40396-1`, `3316-1`, `30300-1`.

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.004 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.019 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.977 | 0.986 |
| Inventory recall, by design (set pieces found) | 0.981 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.358 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 7 | |
| Contact recall | 0.63 | 0.667 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 31 | 210.5 | 0.523 | 0.981 | 0.552 |
| 100-249 | 12 | 633.892 | 2.069 | 0.989 | 0.79 |
| 250+ | 3 | 1164.367 | 4.007 | 0.948 | 0.689 |

### Check and repair loop

Build → check → repair → final check. **44/46** manuals had check failures after the first build; **4** of those were fully fixed by the repair. Issues in total: 567 → 376.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 46 | 326.167 | 1.018 | 0.02 |
| parts | 46 | 0.663 | 0.0 | 0.0 |
| repair1 | 39 | 55.146 | 0.107 | 0.012 |
| repair2 | 25 | 17.556 | 0.081 | 0.017 |

**Accuracy before → after repair** (43 booklets repaired): inventory recall 0.801 → 0.98; contact recall 0.496 → 0.602; contact precision 0.395 → 0.351.

### Spec rules and structure

- Manuals with **no rule problems**: 9/49 (18%).
- Problems by rule: V4 ×177, V3 ×143, V2 ×9, refs ×6 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 7/49; overrides used in 6.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 46 | 0 | 0 |

### Failures

- `60059-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 9:20pm (Europe/Dublin)
- `7635-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 9:20pm (Europe/Dublin)
- `4431-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 9:20pm (Europe/Dublin)
- `41488-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 9:20pm (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 7268-1 | 105.4 | 0.1497 | 32 | 35 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 1/2 |
| 30103-1 | 68.6 | 0.1211 | 28 | 35 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4991-1 | 72.7 | 0.1243 | 26 | 27 | 0 | 1 | pieces 26/26, inv R 0.885, contacts 0/1 |
| 7603-1 | 97.7 | 0.1764 | 33 | 36 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7736-1 | 155.9 | 0.3917 | 28 | 53 | 0 | 13 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 5969-1 | 277.8 | 0.5797 | 33 | 63 | 0 | 4 | pieces 33/33, inv R 0.97, contacts 0/1 |
| 7246-1 | 82.7 | 0.1481 | 33 | 33 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 4641-1 | 206.3 | 0.4341 | 31 | 40 | 0 | 2 | pieces 31/29, inv R 1.0, contacts 0/0 |
| 41502-1 | 268.0 | 0.5652 | 37 | 52 | 0 | 14 | pieces 37/45, inv R 0.822, contacts 0/2 |
| 30161-1 | 99.6 | 0.1898 | 45 | 47 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 7902-1 | 253.3 | 0.678 | 62 | 73 | 0 | 1 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 30313-1 | 131.9 | 0.2831 | 44 | 46 | 0 | 6 | pieces 44/44, inv R 1.0, contacts 1/4 |
| 21003-1 | 216.7 | 0.6236 | 57 | 82 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 14/16 |
| 41181-1 | 259.9 | 0.7666 | 63 | 74 | 0 | 1 | pieces 63/63, inv R 0.984, contacts 1/1 |
| 7634-1 | 372.1 | 0.9483 | 76 | 111 | 0 | 3 | pieces 76/74, inv R 1.0, contacts 2/3 |
| 60054-1 | 425.5 | 1.0317 | 91 | 105 | 0 | 3 | pieces 91/91, inv R 0.967, contacts 1/4 |
| 40148-1 | 538.7 | 1.3097 | 103 | 225 | 0 | 27 | pieces 103/100, inv R 1.0, contacts 5/6 |
| 41589-1 | 289.2 | 0.7292 | 79 | 116 | 0 | 1 | pieces 79/79, inv R 1.0, contacts 12/15 |
| 4778-1 | 416.6 | 1.1371 | 105 | 143 | 0 | 1 | pieces 105/104, inv R 1.0, contacts 3/4 |
| 70127-1 | 615.5 | 1.4032 | 118 | 155 | 0 | 2 | pieces 118/105, inv R 1.0, contacts 3/3 |
| 40181-1 | 452.9 | 1.0454 | 139 | 167 | 0 | 9 | pieces 139/139, inv R 1.0, contacts 33/36 |
| 40386-1 | 696.9 | 2.0487 | 115 | 212 | 0 | 0 | pieces 115/115, inv R 0.948, contacts 0/0 |
| 7936-1 | 574.5 | 2.2182 | 144 | 203 | 0 | 14 | pieces 144/138, inv R 1.0, contacts 13/14 |
| 40335-1 | 740.1 | 2.2046 | 149 | 290 | 0 | 39 | pieces 149/150, inv R 0.98, contacts 15/17 |
| 7992-1 | 738.0 | 2.6915 | 217 | 264 | 0 | 3 | pieces 217/214, inv R 1.0, contacts 25/43 |
| 21026-1 | 836.2 | 3.6222 | 212 | 285 | 0 | 50 | pieces 212/212, inv R 0.962, contacts 16/23 |
| 8159-1 | 667.9 | 2.4883 | 233 | 276 | 0 | 2 | pieces 233/228, inv R 1.0, contacts 28/46 |
| 21113-1 | 733.8 | 2.3153 | 242 | 264 | 0 | 2 | pieces 242/243, inv R 0.992, contacts 99/102 |
| 8658-1 | 95.2 | 0.2454 | 32 | 33 | 0 | 4 | pieces 32/32, inv R 1.0, contacts 3/5 |
| 40199-1 | 875.4 | 2.7299 | 286 | 333 | 0 | 0 | pieces 286/286, inv R 0.93, contacts 91/134 |
| 60001-1 | 275.6 | 0.8534 | 72 | 105 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 7/8 |
| 7306-1 | 380.3 | 0.9143 | 57 | 94 | 0 | 13 | pieces 57/57, inv R 0.982, contacts 2/3 |
| 30311-1 | 124.2 | 0.2615 | 46 | 52 | 0 | 4 | pieces 46/46, inv R 1.0, contacts 4/4 |
| 7808-1 | 84.4 | 0.1796 | 34 | 39 | 0 | 1 | pieces 34/34, inv R 1.0, contacts 1/1 |
| 4904-1 | 194.4 | 0.3908 | 34 | 79 | 0 | 2 | pieces 34/34, inv R 1.0, contacts 7/11 |
| 10170-1 | 1451.4 | 4.3642 | 366 | 1313 | 0 | 26 | pieces 366/366, inv R 1.0, contacts 78/100 |
| 30312-1 | 190.8 | 0.3613 | 36 | 37 | 0 | 2 | pieces 36/36, inv R 0.972, contacts 0/1 |
| 9469-1 | 275.9 | 0.7525 | 73 | 88 | 0 | 10 | pieces 73/73, inv R 0.986, contacts 5/6 |
| 40413-1 | 1166.3 | 4.9271 | 366 | 498 | 0 | 34 | pieces 366/366, inv R 0.913, contacts 28/46 |
| 6966-1 | 131.5 | 0.2946 | 39 | 47 | 0 | 4 | pieces 39/38, inv R 1.0, contacts 0/0 |
| 5981-1 | 238.7 | 0.9262 | 60 | 83 | 0 | 2 | pieces 60/60, inv R 1.0, contacts 1/2 |
| 41504-1 | 203.2 | 0.5301 | 50 | 54 | 0 | 2 | pieces 50/50, inv R 0.96, contacts 0/0 |
| 7242-1 | 250.0 | 0.7446 | 60 | 62 | 0 | 9 | pieces 60/60, inv R 0.983, contacts 2/6 |
| 21000-1 | 183.7 | 0.6084 | 69 | 95 | 0 | 0 | pieces 69/69, inv R 0.986, contacts 55/62 |
| 40138-1 | 595.6 | 2.347 | 233 | 285 | 0 | 16 | pieces 233/233, inv R 0.983, contacts 34/65 |
| 41071-1 | 514.3 | 1.2101 | 94 | 106 | 0 | 4 | pieces 94/94, inv R 0.904, contacts 8/16 |
