# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 95 manuals succeeded, 3 failed · wall time 5331 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 371.408 | 317.3 | 763.6 | 35284 |
| Input tokens | 206564 | 164748 | 486870 | 19623561 |
| Output tokens | 53616 | 44936 | 112298 | 5093548 |
| Cost (USD) | 0.954 | 0.7199 | 2.0052 | 90.65 |

Estimated cost for 100 manuals at this rate: **$95.42**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 1.0 | 1.0 |
| Inventory recall, by design (set pieces found) | 1.0 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.414 | 0.397 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 15 | |
| Contact recall | 0.641 | 0.733 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 55 | 195.3 | 0.444 | 1.0 | 0.623 |
| 100-249 | 31 | 511.042 | 1.38 | 1.0 | 0.658 |
| 250+ | 9 | 966.667 | 2.606 | 1.0 | 0.677 |

### Check and repair loop

Build → check → repair → final check. **74/95** manuals had check failures after the first build; **13** of those were fully fixed by the repair. Issues in total: 370 → 150.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 95 | 317.026 | 0.671 | 0.026 |
| parts | 95 | 0.349 | 0.0 | 0.0 |
| repair1 | 60 | 53.525 | 0.333 | 0.025 |
| repair2 | 40 | 47.94 | 0.175 | 0.018 |

**Accuracy before → after repair** (82 booklets repaired): inventory recall 1.0 → 1.0; contact recall 0.631 → 0.631; contact precision 0.411 → 0.409.

### Spec rules and structure

- Manuals with **no rule problems**: 80/95 (84%).
- Problems by rule: V2 ×66 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/95; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 0 | 0 |
| 75 | 0 | 0 |
| 95 | 0 | 0 |

### Failures

- `75892-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)
- `60066-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)
- `21033-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 69.0 | 0.1185 | 28 | 33 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4991-1 | 49.8 | 0.0956 | 26 | 30 | 0 | 0 | pieces 26/26, inv R 1.0, contacts 1/1 |
| 7268-1 | 62.3 | 0.1124 | 32 | 36 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 7736-1 | 40.5 | 0.1739 | 28 | 29 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7603-1 | 84.9 | 0.1476 | 33 | 38 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 4641-1 | 124.0 | 0.3352 | 29 | 35 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 5969-1 | 161.3 | 0.4487 | 33 | 41 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 7246-1 | 46.6 | 0.0933 | 33 | 35 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 30161-1 | 87.7 | 0.1504 | 45 | 51 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 3/4 |
| 41502-1 | 187.5 | 0.2517 | 45 | 46 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 30313-1 | 84.3 | 0.1486 | 44 | 48 | 0 | 0 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 40396-1 | 335.8 | 0.4638 | 53 | 60 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 7902-1 | 339.6 | 0.7934 | 62 | 73 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 21003-1 | 110.5 | 0.3034 | 57 | 94 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 15/16 |
| 41181-1 | 155.5 | 0.6411 | 63 | 78 | 0 | 0 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 7634-1 | 441.6 | 1.0522 | 74 | 109 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 0/3 |
| 41589-1 | 398.5 | 0.6937 | 79 | 108 | 0 | 0 | pieces 79/79, inv R 1.0, contacts 13/15 |
| 60054-1 | 320.3 | 0.9475 | 91 | 102 | 0 | 1 | pieces 91/91, inv R 1.0, contacts 0/4 |
| 40148-1 | 207.6 | 0.6693 | 100 | 116 | 0 | 1 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 4778-1 | 393.4 | 0.707 | 104 | 126 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
| 40386-1 | 317.3 | 0.9719 | 115 | 187 | 0 | 0 | pieces 115/115, inv R 1.0, contacts 0/0 |
| 70127-1 | 340.1 | 0.6585 | 105 | 129 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 40181-1 | 302.4 | 0.8586 | 139 | 167 | 0 | 0 | pieces 139/139, inv R 1.0, contacts 32/36 |
| 40335-1 | 553.2 | 1.4299 | 150 | 180 | 0 | 0 | pieces 150/150, inv R 1.0, contacts 12/17 |
| 7936-1 | 494.4 | 1.299 | 138 | 182 | 0 | 0 | pieces 138/138, inv R 1.0, contacts 12/14 |
| 21026-1 | 311.4 | 1.4352 | 212 | 275 | 0 | 0 | pieces 212/212, inv R 1.0, contacts 18/23 |
| 3316-1 | 288.6 | 0.7302 | 206 | 153 | 0 | 26 | pieces 206/206, inv R 1.0, contacts 0/11 |
| 7992-1 | 744.8 | 1.915 | 214 | 247 | 0 | 0 | pieces 214/214, inv R 1.0, contacts 23/43 |
| 8159-1 | 675.3 | 1.7271 | 228 | 265 | 0 | 0 | pieces 228/228, inv R 1.0, contacts 22/46 |
| 21113-1 | 607.5 | 1.6976 | 243 | 282 | 0 | 2 | pieces 243/243, inv R 1.0, contacts 94/102 |
| 40199-1 | 624.6 | 1.7016 | 286 | 325 | 0 | 0 | pieces 286/286, inv R 1.0, contacts 104/134 |
| 10170-1 | 894.7 | 2.1695 | 366 | 482 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 59/100 |
| 40413-1 | 1942.4 | 4.9418 | 366 | 415 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 34/46 |
| 8658-1 | 103.6 | 0.1667 | 32 | 39 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 3/5 |
| 7306-1 | 296.8 | 0.6935 | 57 | 64 | 0 | 4 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 60001-1 | 209.2 | 0.6879 | 72 | 89 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 6/8 |
| 30311-1 | 143.1 | 0.3178 | 46 | 53 | 0 | 0 | pieces 46/46, inv R 1.0, contacts 4/4 |
| 4904-1 | 129.5 | 0.184 | 34 | 37 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 6/11 |
| 7808-1 | 45.8 | 0.0924 | 34 | 38 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 0/1 |
| 9469-1 | 276.8 | 0.7199 | 73 | 92 | 0 | 0 | pieces 73/73, inv R 1.0, contacts 2/6 |
| 30312-1 | 99.2 | 0.2246 | 36 | 37 | 0 | 0 | pieces 36/36, inv R 1.0, contacts 0/1 |
| 6966-1 | 90.9 | 0.1551 | 38 | 48 | 0 | 0 | pieces 38/38, inv R 1.0, contacts 0/0 |
| 5981-1 | 194.6 | 0.6039 | 60 | 84 | 0 | 0 | pieces 60/60, inv R 1.0, contacts 0/2 |
| 30300-1 | 214.8 | 0.4672 | 57 | 66 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 41504-1 | 102.0 | 0.2888 | 50 | 68 | 0 | 0 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 7242-1 | 151.2 | 0.4519 | 60 | 67 | 0 | 0 | pieces 60/60, inv R 1.0, contacts 2/6 |
| 40138-1 | 564.4 | 1.7728 | 233 | 282 | 0 | 0 | pieces 233/233, inv R 1.0, contacts 44/65 |
| 21000-1 | 238.0 | 0.4522 | 69 | 90 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 48/62 |
| 4431-1 | 763.6 | 2.043 | 187 | 226 | 0 | 1 | pieces 187/187, inv R 1.0, contacts 16/34 |
| 41071-1 | 390.3 | 1.0635 | 94 | 106 | 0 | 2 | pieces 94/94, inv R 1.0, contacts 13/16 |
| 7635-1 | 622.2 | 1.648 | 168 | 201 | 0 | 0 | pieces 168/168, inv R 1.0, contacts 0/2 |
| 41488-1 | 319.4 | 0.6643 | 89 | 109 | 0 | 0 | pieces 89/89, inv R 1.0, contacts 12/15 |
| 60059-1 | 651.7 | 2.0052 | 219 | 289 | 0 | 3 | pieces 219/219, inv R 1.0, contacts 14/25 |
| 40180-1 | 392.5 | 1.074 | 164 | 195 | 0 | 0 | pieces 164/164, inv R 1.0, contacts 29/33 |
| 40456-1 | 300.0 | 0.7507 | 118 | 165 | 0 | 0 | pieces 118/118, inv R 1.0, contacts 0/0 |
| 7997-1 | 918.3 | 2.3883 | 367 | 453 | 0 | 0 | pieces 367/367, inv R 1.0, contacts 37/76 |
| 21027-1 | 790.2 | 2.4715 | 289 | 361 | 0 | 0 | pieces 289/289, inv R 1.0, contacts 26/32 |
| 40448-1 | 454.5 | 1.3367 | 181 | 227 | 0 | 0 | pieces 181/181, inv R 1.0, contacts 8/9 |
| 8158-1 | 674.5 | 1.606 | 234 | 297 | 0 | 0 | pieces 234/234, inv R 1.0, contacts 30/57 |
| 60065-1 | 199.2 | 0.562 | 50 | 51 | 0 | 0 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 30105-1 | 153.1 | 0.3422 | 37 | 39 | 0 | 1 | pieces 37/37, inv R 1.0, contacts 1/1 |
| 7803-1 | 81.0 | 0.1347 | 38 | 48 | 0 | 0 | pieces 38/38, inv R 1.0, contacts 1/10 |
| 7942-1 | 477.3 | 1.0682 | 127 | 148 | 0 | 0 | pieces 127/127, inv R 1.0, contacts 3/8 |
| 7325-1 | 534.1 | 1.5368 | 201 | 239 | 0 | 0 | pieces 201/201, inv R 1.0, contacts 6/8 |
| 4200-1 | 333.2 | 0.913 | 97 | 123 | 0 | 0 | pieces 97/97, inv R 1.0, contacts 1/5 |
| 5970-1 | 311.8 | 0.8207 | 70 | 68 | 0 | 0 | pieces 70/70, inv R 1.0, contacts 0/0 |
| 7731-1 | 152.3 | 0.4913 | 62 | 72 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/2 |
| 41505-1 | 230.5 | 0.4476 | 51 | 59 | 0 | 0 | pieces 51/51, inv R 1.0, contacts 1/2 |
| 21000-2 | 121.5 | 0.275 | 69 | 99 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 56/62 |
| 9470-1 | 766.0 | 1.9952 | 214 | 248 | 0 | 5 | pieces 214/214, inv R 1.0, contacts 6/8 |
| 31028-1 | 400.0 | 0.7794 | 53 | 62 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 0/2 |
| 40377-1 | 430.3 | 0.787 | 90 | 121 | 0 | 0 | pieces 90/90, inv R 1.0, contacts 10/13 |
| 40457-1 | 423.5 | 1.1591 | 140 | 190 | 0 | 0 | pieces 140/140, inv R 1.0, contacts 0/0 |
| 40144-1 | 352.3 | 1.089 | 165 | 194 | 0 | 0 | pieces 165/165, inv R 1.0, contacts 51/61 |
| 7903-1 | 832.2 | 2.1098 | 235 | 295 | 0 | 0 | pieces 235/235, inv R 1.0, contacts 9/25 |
| 75878-1 | 503.6 | 1.4618 | 183 | 215 | 0 | 0 | pieces 183/183, inv R 1.0, contacts 9/10 |
| 7893-1 | 964.5 | 2.4618 | 387 | 448 | 0 | 1 | pieces 387/387, inv R 1.0, contacts 14/17 |
| 21302-1 | 1135.0 | 3.3436 | 470 | 514 | 0 | 16 | pieces 470/470, inv R 1.0, contacts 58/82 |
| 7236-1 | 166.4 | 0.3937 | 56 | 63 | 0 | 1 | pieces 56/56, inv R 1.0, contacts 1/2 |
| 3931-1 | 113.3 | 0.3635 | 39 | 48 | 0 | 0 | pieces 39/39, inv R 1.0, contacts 4/4 |
| 21032-1 | 760.5 | 1.9982 | 361 | 465 | 0 | 0 | pieces 361/361, inv R 1.0, contacts 60/82 |
| 7269-1 | 78.6 | 0.1361 | 37 | 47 | 0 | 0 | pieces 37/37, inv R 1.0, contacts 5/10 |
| 7875-1 | 129.4 | 0.1997 | 39 | 49 | 0 | 0 | pieces 39/39, inv R 1.0, contacts 2/2 |
| 8160-1 | 669.8 | 1.9787 | 353 | 401 | 0 | 0 | pieces 353/353, inv R 1.0, contacts 33/77 |
| 30055-1 | 131.3 | 0.2842 | 42 | 41 | 0 | 0 | pieces 42/42, inv R 1.0, contacts 0/0 |
| 7630-1 | 534.1 | 1.2406 | 104 | 138 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 17/27 |
| 41500-1 | 240.3 | 0.4859 | 58 | 61 | 0 | 0 | pieces 58/58, inv R 1.0, contacts 0/0 |
| 9471-1 | 796.0 | 2.2172 | 229 | 284 | 0 | 0 | pieces 229/229, inv R 1.0, contacts 11/15 |
| 21001-1 | 155.8 | 0.3284 | 69 | 97 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 40/42 |
| 7732-1 | 363.3 | 0.9462 | 84 | 100 | 0 | 0 | pieces 84/84, inv R 1.0, contacts 0/0 |
| 5761-1 | 345.8 | 0.6177 | 57 | 61 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 1/1 |
| 41485-1 | 387.4 | 0.7298 | 91 | 124 | 0 | 0 | pieces 91/91, inv R 1.0, contacts 11/12 |
| 40391-1 | 446.1 | 1.2273 | 151 | 216 | 0 | 0 | pieces 151/151, inv R 1.0, contacts 0/0 |
| 40182-1 | 517.7 | 1.332 | 175 | 210 | 0 | 0 | pieces 175/175, inv R 1.0, contacts 64/69 |
| 7613-1 | 112.1 | 0.1818 | 34 | 36 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 3/3 |
