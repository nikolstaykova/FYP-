# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 41 manuals succeeded, 3 failed · wall time 3110 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 274.388 | 209.2 | 607.5 | 11250 |
| Input tokens | 148641 | 125129 | 386112 | 6094293 |
| Output tokens | 39142 | 32726 | 94150 | 1604837 |
| Cost (USD) | 0.687 | 0.6585 | 1.6976 | 28.18 |

Estimated cost for 100 manuals at this rate: **$68.74**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.408 | 0.383 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 6 | |
| Contact recall | 0.616 | 0.667 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 27 | 166.467 | 0.378 | 1.0 | 0.577 |
| 100-249 | 12 | 436.333 | 1.175 | 1.0 | 0.682 |
| 250+ | 2 | 759.65 | 1.936 | 1.0 | 0.683 |

### Check and repair loop

Build → check → repair → final check. **27/41** manuals had check failures after the first build; **5** of those were fully fixed by the repair. Issues in total: 121 → 64.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 41 | 235.341 | 0.482 | 0.023 |
| parts | 41 | 0.437 | 0.0 | 0.0 |
| repair1 | 23 | 44.426 | 0.278 | 0.01 |
| repair2 | 14 | 40.036 | 0.145 | 0.009 |

**Accuracy before → after repair** (37 booklets repaired): inventory recall 1.0 → 1.0; contact recall 0.638 → 0.638; contact precision 0.418 → 0.416.

### Spec rules and structure

- Manuals with **no rule problems**: 34/41 (83%).
- Problems by rule: V2 ×36 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/41; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 41 | 0 | 0 |

### Failures

- `5981-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:20pm (Europe/Dublin)
- `30300-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:20pm (Europe/Dublin)
- `40413-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:20pm (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 7268-1 | 62.3 | 0.1124 | 32 | 36 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 4991-1 | 49.8 | 0.0956 | 26 | 30 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 1/1 |
| 30103-1 | 69.0 | 0.1185 | 28 | 33 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7736-1 | 40.5 | 0.1739 | 28 | 29 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4641-1 | 124.0 | 0.3352 | 29 | 35 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 7603-1 | 84.9 | 0.1476 | 33 | 38 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7246-1 | 46.6 | 0.0933 | 33 | 35 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 30161-1 | 87.7 | 0.1504 | 45 | 51 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 3/4 |
| 41502-1 | 187.5 | 0.2517 | 45 | 46 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 5969-1 | 161.3 | 0.4487 | 33 | 41 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 30313-1 | 84.3 | 0.1486 | 44 | 48 | 0 | 0 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 40396-1 | 335.8 | 0.4638 | 53 | 60 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 21003-1 | 110.5 | 0.3034 | 57 | 94 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 15/16 |
| 7902-1 | 339.6 | 0.7934 | 62 | 73 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 41181-1 | 155.5 | 0.6411 | 63 | 78 | 0 | 0 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 7634-1 | 441.6 | 1.0522 | 74 | 109 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 0/3 |
| 60054-1 | 320.3 | 0.9475 | 91 | 102 | 0 | 1 | pieces 91/91, inv R 1.0, contacts 0/4 |
| 41589-1 | 398.5 | 0.6937 | 79 | 108 | 0 | 0 | pieces 79/79, inv R 1.0, contacts 13/15 |
| 40148-1 | 207.6 | 0.6693 | 100 | 116 | 0 | 1 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 4778-1 | 393.4 | 0.707 | 104 | 126 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
| 70127-1 | 340.1 | 0.6585 | 105 | 129 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 40181-1 | 302.4 | 0.8586 | 139 | 167 | 0 | 0 | pieces 139/139, inv R 1.0, contacts 32/36 |
| 40386-1 | 317.3 | 0.9719 | 115 | 187 | 0 | 0 | pieces 115/115, inv R 1.0, contacts 0/0 |
| 7936-1 | 494.4 | 1.299 | 138 | 182 | 0 | 0 | pieces 138/138, inv R 1.0, contacts 12/14 |
| 21026-1 | 311.4 | 1.4352 | 212 | 275 | 0 | 0 | pieces 212/212, inv R 1.0, contacts 18/23 |
| 3316-1 | 288.6 | 0.7302 | 206 | 153 | 0 | 26 | pieces 206/206, inv R 1.0, contacts 0/11 |
| 40335-1 | 553.2 | 1.4299 | 150 | 180 | 0 | 0 | pieces 150/150, inv R 1.0, contacts 12/17 |
| 7992-1 | 744.8 | 1.915 | 214 | 247 | 0 | 0 | pieces 214/214, inv R 1.0, contacts 23/43 |
| 8159-1 | 675.3 | 1.7271 | 228 | 265 | 0 | 0 | pieces 228/228, inv R 1.0, contacts 22/46 |
| 21113-1 | 607.5 | 1.6976 | 243 | 282 | 0 | 2 | pieces 243/243, inv R 1.0, contacts 94/102 |
| 40199-1 | 624.6 | 1.7016 | 286 | 325 | 0 | 0 | pieces 286/286, inv R 1.0, contacts 104/134 |
| 8658-1 | 103.6 | 0.1667 | 32 | 39 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 3/5 |
| 10170-1 | 894.7 | 2.1695 | 366 | 482 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 59/100 |
| 7306-1 | 296.8 | 0.6935 | 57 | 64 | 0 | 4 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 30311-1 | 143.1 | 0.3178 | 46 | 53 | 0 | 0 | pieces 46/46, inv R 1.0, contacts 4/4 |
| 60001-1 | 209.2 | 0.6879 | 72 | 89 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 6/8 |
| 7808-1 | 45.8 | 0.0924 | 34 | 38 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 0/1 |
| 4904-1 | 129.5 | 0.184 | 34 | 37 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 6/11 |
| 30312-1 | 99.2 | 0.2246 | 36 | 37 | 0 | 0 | pieces 36/36, inv R 1.0, contacts 0/1 |
| 6966-1 | 90.9 | 0.1551 | 38 | 48 | 0 | 0 | pieces 38/38, inv R 1.0, contacts 0/0 |
| 9469-1 | 276.8 | 0.7199 | 73 | 92 | 0 | 0 | pieces 73/73, inv R 1.0, contacts 2/6 |
