# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 100 manuals succeeded, 0 failed · wall time 3700 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 357.82 | 307.2 | 710.5 | 35782 |
| Input tokens | 179002 | 139327 | 416767 | 17900240 |
| Output tokens | 56215 | 45178 | 115504 | 5621539 |
| Cost (USD) | 0.938 | 0.7395 | 1.9533 | 93.78 |

Estimated cost for 100 manuals at this rate: **$93.78**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.009 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.999 | 1.0 |
| Inventory recall, by design (set pieces found) | 0.999 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.381 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 16 | |
| Contact recall | 0.605 | 0.643 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 58 | 205.817 | 0.488 | 0.999 | 0.616 |
| 100-249 | 32 | 479.678 | 1.335 | 1.0 | 0.589 |
| 250+ | 10 | 849.49 | 2.278 | 1.0 | 0.598 |

### Check and repair loop

Build → check → repair → final check. **87/100** manuals had check failures after the first build; **2** of those were fully fixed by the repair. Issues in total: 748 → 656.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 100 | 289.54 | 0.66 | 0.016 |
| parts | 100 | 0.282 | 0.0 | 0.0 |
| repair1 | 49 | 82.057 | 0.38 | 0.021 |
| repair2 | 37 | 75.046 | 0.247 | 0.019 |

**Accuracy before → after repair** (84 booklets repaired): inventory recall 0.999 → 0.999; contact recall 0.59 → 0.59; contact precision 0.373 → 0.373.

### Spec rules and structure

- Manuals with **no rule problems**: 31/100 (31%).
- Problems by rule: V3 ×321, V2 ×219, V4 ×30 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 47/100; overrides used in 41.

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
| 100 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 7268-1 | 96.7 | 0.1594 | 32 | 32 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 7603-1 | 83.5 | 0.14 | 33 | 34 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 4991-1 | 63.6 | 0.0912 | 26 | 30 | 0 | 1 | pieces 26/26, inv R 0.923, contacts 1/1 |
| 30103-1 | 49.4 | 0.0985 | 28 | 30 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7246-1 | 77.2 | 0.1144 | 33 | 33 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 4641-1 | 94.8 | 0.3041 | 29 | 30 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 7736-1 | 60.0 | 0.2069 | 28 | 47 | 0 | 5 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 5969-1 | 285.3 | 0.7473 | 33 | 69 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 30161-1 | 226.9 | 0.3713 | 45 | 94 | 0 | 2 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 30313-1 | 113.2 | 0.2054 | 44 | 71 | 0 | 5 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 41502-1 | 333.7 | 0.4606 | 45 | 76 | 0 | 3 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 40396-1 | 307.9 | 0.4762 | 53 | 87 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 21003-1 | 91.1 | 0.2925 | 57 | 69 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 14/16 |
| 7634-1 | 362.2 | 0.9812 | 74 | 94 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 2/3 |
| 7902-1 | 363.2 | 0.9333 | 62 | 76 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 41181-1 | 195.4 | 0.7358 | 63 | 65 | 0 | 3 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 41589-1 | 189.3 | 0.4848 | 79 | 99 | 0 | 1 | pieces 79/79, inv R 1.0, contacts 12/15 |
| 60054-1 | 307.2 | 1.03 | 91 | 103 | 0 | 3 | pieces 91/91, inv R 1.0, contacts 2/4 |
| 4778-1 | 352.4 | 0.7158 | 104 | 114 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
| 70127-1 | 375.1 | 1.0016 | 105 | 136 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 40148-1 | 344.3 | 0.9435 | 100 | 113 | 0 | 3 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 40386-1 | 315.1 | 0.8628 | 115 | 176 | 0 | 0 | pieces 115/115, inv R 1.0, contacts 0/0 |
| 40181-1 | 486.5 | 1.2669 | 139 | 149 | 0 | 8 | pieces 139/139, inv R 1.0, contacts 30/36 |
| 40335-1 | 533.1 | 1.4796 | 150 | 170 | 0 | 10 | pieces 150/150, inv R 1.0, contacts 14/17 |
| 7936-1 | 479.7 | 1.3277 | 138 | 168 | 0 | 10 | pieces 138/138, inv R 1.0, contacts 10/14 |
| 21026-1 | 354.6 | 1.3051 | 212 | 255 | 0 | 10 | pieces 212/212, inv R 1.0, contacts 17/23 |
| 3316-1 | 164.2 | 0.4984 | 206 | 0 | 0 | 206 | pieces 206/206, inv R 1.0, contacts 0/11 |
| 7992-1 | 747.5 | 2.0844 | 214 | 233 | 0 | 3 | pieces 214/214, inv R 1.0, contacts 26/43 |
| 8159-1 | 408.7 | 0.894 | 228 | 252 | 0 | 0 | pieces 228/228, inv R 1.0, contacts 10/46 |
| 21113-1 | 857.7 | 2.163 | 243 | 280 | 0 | 2 | pieces 243/243, inv R 1.0, contacts 93/102 |
| 10170-1 | 664.5 | 1.6724 | 366 | 430 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 54/100 |
| 40199-1 | 603.7 | 1.3105 | 286 | 306 | 0 | 5 | pieces 286/286, inv R 1.0, contacts 98/134 |
| 8658-1 | 154.8 | 0.2618 | 32 | 83 | 0 | 4 | pieces 32/32, inv R 1.0, contacts 4/5 |
| 60001-1 | 259.1 | 0.8234 | 72 | 77 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 4/8 |
| 7306-1 | 419.6 | 1.0839 | 57 | 61 | 0 | 2 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 30311-1 | 170.3 | 0.2604 | 46 | 55 | 0 | 3 | pieces 46/46, inv R 1.0, contacts 2/4 |
| 7808-1 | 42.5 | 0.0958 | 34 | 35 | 0 | 1 | pieces 34/34, inv R 1.0, contacts 1/1 |
| 4904-1 | 213.4 | 0.3313 | 34 | 73 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 7/11 |
| 9469-1 | 360.1 | 0.9273 | 73 | 90 | 0 | 10 | pieces 73/73, inv R 1.0, contacts 4/6 |
| 30312-1 | 132.7 | 0.2238 | 36 | 53 | 0 | 0 | pieces 36/36, inv R 1.0, contacts 0/1 |
| 6966-1 | 135.8 | 0.2183 | 38 | 39 | 0 | 3 | pieces 38/38, inv R 1.0, contacts 0/0 |
| 5981-1 | 279.1 | 0.6392 | 60 | 83 | 0 | 7 | pieces 60/60, inv R 1.0, contacts 0/2 |
| 30300-1 | 255.3 | 0.3942 | 57 | 66 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 41504-1 | 183.8 | 0.407 | 50 | 55 | 0 | 0 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 7242-1 | 105.0 | 0.3006 | 60 | 61 | 0 | 4 | pieces 60/60, inv R 1.0, contacts 2/6 |
| 40138-1 | 557.4 | 1.9533 | 233 | 243 | 0 | 15 | pieces 233/233, inv R 1.0, contacts 35/65 |
| 21000-1 | 175.2 | 0.3754 | 69 | 100 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 58/62 |
| 41071-1 | 394.0 | 1.1282 | 94 | 100 | 0 | 7 | pieces 94/94, inv R 1.0, contacts 13/16 |
| 4431-1 | 774.0 | 2.1499 | 187 | 204 | 0 | 8 | pieces 187/187, inv R 1.0, contacts 18/34 |
| 7635-1 | 597.8 | 1.3024 | 168 | 186 | 0 | 8 | pieces 168/168, inv R 1.0, contacts 0/2 |
| 60059-1 | 590.0 | 1.7909 | 219 | 279 | 0 | 18 | pieces 219/219, inv R 1.0, contacts 11/25 |
| 41488-1 | 217.3 | 0.3223 | 89 | 106 | 0 | 0 | pieces 89/89, inv R 1.0, contacts 12/15 |
| 40456-1 | 279.0 | 0.734 | 118 | 148 | 0 | 0 | pieces 118/118, inv R 1.0, contacts 0/0 |
| 7997-1 | 1513.2 | 3.85 | 367 | 379 | 0 | 8 | pieces 367/367, inv R 1.0, contacts 23/76 |
| 40180-1 | 528.6 | 1.4789 | 164 | 174 | 0 | 0 | pieces 164/164, inv R 1.0, contacts 27/33 |
| 40448-1 | 460.9 | 1.0678 | 181 | 206 | 0 | 4 | pieces 181/181, inv R 1.0, contacts 8/9 |
| 21027-1 | 589.9 | 1.7967 | 289 | 338 | 0 | 11 | pieces 289/289, inv R 1.0, contacts 21/32 |
| 8158-1 | 461.0 | 0.9809 | 234 | 309 | 0 | 0 | pieces 234/234, inv R 1.0, contacts 26/57 |
| 7325-1 | 463.7 | 1.4047 | 201 | 238 | 0 | 4 | pieces 201/201, inv R 1.0, contacts 5/8 |
| 60065-1 | 258.3 | 0.7722 | 50 | 78 | 0 | 4 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 7942-1 | 391.0 | 0.9792 | 127 | 145 | 0 | 10 | pieces 127/127, inv R 1.0, contacts 4/8 |
| 30105-1 | 199.2 | 0.4727 | 37 | 57 | 0 | 0 | pieces 37/37, inv R 1.0, contacts 0/1 |
| 7803-1 | 99.2 | 0.1717 | 38 | 40 | 0 | 4 | pieces 38/38, inv R 1.0, contacts 3/10 |
| 5970-1 | 255.0 | 0.7395 | 70 | 67 | 0 | 13 | pieces 70/70, inv R 1.0, contacts 0/0 |
| 41505-1 | 232.0 | 0.4648 | 51 | 59 | 0 | 2 | pieces 51/51, inv R 1.0, contacts 0/2 |
| 7731-1 | 248.8 | 0.7374 | 62 | 67 | 0 | 4 | pieces 62/62, inv R 1.0, contacts 1/2 |
| 4200-1 | 305.6 | 0.9251 | 97 | 100 | 0 | 1 | pieces 97/97, inv R 1.0, contacts 0/5 |
| 31028-1 | 209.1 | 0.689 | 53 | 61 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 0/2 |
| 21000-2 | 194.6 | 0.4066 | 69 | 85 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 48/62 |
| 9470-1 | 536.1 | 1.5936 | 214 | 218 | 0 | 11 | pieces 214/214, inv R 1.0, contacts 7/8 |
| 40377-1 | 256.0 | 0.6266 | 90 | 109 | 0 | 0 | pieces 90/90, inv R 1.0, contacts 11/13 |
| 40457-1 | 227.7 | 0.7231 | 140 | 165 | 0 | 0 | pieces 140/140, inv R 1.0, contacts 0/0 |
| 7903-1 | 633.1 | 1.7032 | 235 | 250 | 0 | 18 | pieces 235/235, inv R 1.0, contacts 8/25 |
| 40144-1 | 438.0 | 1.4092 | 165 | 184 | 0 | 8 | pieces 165/165, inv R 1.0, contacts 37/61 |
| 40413-1 | 1212.8 | 3.6528 | 366 | 384 | 0 | 2 | pieces 366/366, inv R 1.0, contacts 23/46 |
| 75878-1 | 480.2 | 1.5321 | 183 | 200 | 0 | 6 | pieces 183/183, inv R 1.0, contacts 6/10 |
| 21302-1 | 1004.3 | 3.1446 | 470 | 490 | 0 | 5 | pieces 470/470, inv R 1.0, contacts 52/82 |
| 7893-1 | 710.5 | 1.8623 | 387 | 408 | 0 | 10 | pieces 387/387, inv R 1.0, contacts 13/17 |
| 21032-1 | 607.4 | 1.8414 | 361 | 411 | 0 | 3 | pieces 361/361, inv R 1.0, contacts 63/82 |
| 7269-1 | 91.4 | 0.1499 | 37 | 36 | 0 | 0 | pieces 37/37, inv R 1.0, contacts 2/10 |
| 3931-1 | 132.1 | 0.4401 | 39 | 38 | 0 | 0 | pieces 39/39, inv R 1.0, contacts 4/4 |
| 7236-1 | 180.1 | 0.4613 | 56 | 62 | 0 | 3 | pieces 56/56, inv R 1.0, contacts 1/2 |
| 7875-1 | 151.0 | 0.2298 | 39 | 42 | 0 | 9 | pieces 39/39, inv R 1.0, contacts 2/2 |
| 30055-1 | 103.7 | 0.1637 | 42 | 45 | 0 | 3 | pieces 42/42, inv R 1.0, contacts 0/0 |
| 7630-1 | 359.5 | 0.6704 | 104 | 121 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 10/27 |
| 8160-1 | 766.3 | 1.5797 | 353 | 394 | 0 | 4 | pieces 353/353, inv R 1.0, contacts 34/77 |
| 41500-1 | 317.4 | 0.5864 | 58 | 86 | 0 | 2 | pieces 58/58, inv R 1.0, contacts 0/0 |
| 7732-1 | 307.4 | 0.8667 | 84 | 97 | 0 | 8 | pieces 84/84, inv R 1.0, contacts 0/0 |
| 21001-1 | 182.3 | 0.395 | 69 | 96 | 0 | 4 | pieces 69/69, inv R 1.0, contacts 40/42 |
| 9471-1 | 777.3 | 2.4012 | 229 | 252 | 0 | 13 | pieces 229/229, inv R 1.0, contacts 12/15 |
| 5761-1 | 361.6 | 0.895 | 57 | 62 | 0 | 4 | pieces 57/57, inv R 1.0, contacts 1/1 |
| 40391-1 | 201.2 | 0.7159 | 151 | 165 | 0 | 0 | pieces 151/151, inv R 1.0, contacts 0/0 |
| 41485-1 | 455.0 | 0.8852 | 91 | 265 | 0 | 1 | pieces 91/91, inv R 1.0, contacts 12/12 |
| 7613-1 | 133.3 | 0.2336 | 34 | 75 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 3/3 |
| 40182-1 | 546.5 | 1.5448 | 175 | 197 | 0 | 1 | pieces 175/175, inv R 1.0, contacts 61/69 |
| 3930-1 | 127.6 | 0.4187 | 41 | 39 | 0 | 1 | pieces 41/41, inv R 1.0, contacts 2/2 |
| 60066-1 | 186.5 | 0.6885 | 60 | 63 | 0 | 0 | pieces 60/60, inv R 1.0, contacts 0/0 |
| 75892-1 | 627.8 | 2.0359 | 217 | 258 | 0 | 6 | pieces 217/217, inv R 1.0, contacts 1/18 |
| 4905-1 | 151.6 | 0.24 | 39 | 44 | 0 | 0 | pieces 39/39, inv R 1.0, contacts 3/8 |
| 21033-1 | 822.3 | 2.0719 | 444 | 467 | 0 | 1 | pieces 444/444, inv R 1.0, contacts 90/140 |
