# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 97 manuals succeeded, 3 failed · wall time 1187 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 447.49 | 410.3 | 857.6 | 43406 |
| Input tokens | 415509 | 353635 | 728845 | 40304401 |
| Output tokens | 76434 | 66812 | 149370 | 7414130 |
| Cost (USD) | 1.441 | 1.33 | 2.7503 | 139.8 |

Estimated cost for 100 manuals at this rate: **$144.12**.

### Accuracy

**1 PDF(s) contained no building instructions** (e.g. advent-calendar covers); Claude returned an empty graph instead of inventing parts. Left out of the accuracy below: `3316-1`.

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.001 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.722 | 0.942 |
| Inventory precision, by design (pieces that are in the set) | 0.749 | 0.873 |
| Inventory recall, by design (set pieces found) | 0.762 | 0.942 |
| Contact precision (brick/plate/tile pairs) | 0.386 | 0.341 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 16 | |
| Contact recall | 0.445 | 0.5 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 57 | 265.644 | 0.872 | 0.673 | 0.351 |
| 100-249 | 30 | 610.583 | 1.962 | 0.897 | 0.588 |
| 250+ | 9 | 1103.878 | 3.455 | 0.877 | 0.499 |

### Check and repair loop

Build → check → repair → final check. **95/96** manuals had check failures after the first build; **41** of those were fully fixed by the repair. Issues in total: 2165 → 123.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 96 | 266.227 | 0.805 | 0.02 |
| repair1 | 95 | 119.331 | 0.417 | 0.02 |
| repair2 | 65 | 99.912 | 0.35 | 0.021 |

**Accuracy before → after repair** (96 booklets repaired): inventory recall 0.754 → 0.762; contact recall 0.441 → 0.445; contact precision 0.381 → 0.386.

### Spec rules and structure

- Manuals with **no rule problems**: 86/97 (89%).
- Problems by rule: V3 ×27, V4 ×2, V2 ×2 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 71/97; overrides used in 69.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 27 | 27 |
| 2 | 14 | 41 |
| 5 | 33 | 94 |
| 10 | 13 | 163 |
| 25 | 61 | 685 |
| 50 | 37 | 1314 |
| 75 | 107 | 1999 |
| 96 | 26 | 2366 |

### Failures

- `75892-1`: RuntimeError: claude -p failed: Request timed out
- `21033-1`: RuntimeError: claude -p failed: Request timed out
- `4905-1`: RuntimeError: claude -p failed: Request timed out

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 4991-1 | 159.5 | 0.3787 | 31 | 32 | 27 | 0 | pieces 31/26, inv R 0.846, contacts 1/1 |
| 7603-1 | 106.7 | 0.2415 | 32 | 31 | 14 | 0 | pieces 32/33, inv R 0.121, contacts 0/11 |
| 30103-1 | 133.5 | 0.3092 | 24 | 27 | 12 | 0 | pieces 24/28, inv R 0.143, contacts 0/0 |
| 7268-1 | 136.8 | 0.3247 | 26 | 25 | 8 | 0 | pieces 26/32, inv R 0.125, contacts 0/2 |
| 5969-1 | 149.7 | 0.67 | 40 | 40 | 33 | 0 | pieces 40/33, inv R 0.909, contacts 0/1 |
| 7246-1 | 104.3 | 0.2214 | 29 | 28 | 11 | 0 | pieces 29/33, inv R 0.091, contacts 0/0 |
| 4641-1 | 188.8 | 0.7003 | 34 | 35 | 25 | 0 | pieces 34/29, inv R 0.931, contacts 0/0 |
| 7736-1 | 176.0 | 0.5551 | 33 | 38 | 17 | 0 | pieces 33/28, inv R 0.643, contacts 0/0 |
| 30161-1 | 154.0 | 0.3144 | 24 | 25 | 3 | 0 | pieces 24/45, inv R 0.133, contacts 0/4 |
| 30313-1 | 54.2 | 0.3378 | 42 | 45 | 13 | 0 | pieces 42/44, inv R 0.136, contacts 0/4 |
| 40396-1 | 187.9 | 0.4606 | 53 | 56 | 20 | 0 | pieces 53/53, inv R 1.0, contacts 6/8 |
| 21003-1 | 184.0 | 0.5796 | 57 | 63 | 20 | 0 | pieces 57/57, inv R 0.842, contacts 10/16 |
| 41502-1 | 328.7 | 0.9555 | 46 | 50 | 23 | 0 | pieces 46/45, inv R 0.956, contacts 0/2 |
| 41181-1 | 321.7 | 1.106 | 67 | 66 | 50 | 0 | pieces 67/63, inv R 1.0, contacts 0/1 |
| 7902-1 | 374.8 | 1.0383 | 65 | 66 | 26 | 0 | pieces 65/62, inv R 0.952, contacts 2/3 |
| 7634-1 | 471.7 | 1.2955 | 75 | 85 | 37 | 0 | pieces 75/74, inv R 0.892, contacts 0/3 |
| 41589-1 | 614.5 | 1.4867 | 79 | 115 | 37 | 0 | pieces 79/79, inv R 1.0, contacts 13/15 |
| 40148-1 | 441.6 | 1.2086 | 99 | 103 | 33 | 0 | pieces 99/100, inv R 0.93, contacts 5/6 |
| 60054-1 | 476.0 | 1.3741 | 94 | 93 | 50 | 0 | pieces 94/91, inv R 0.956, contacts 0/4 |
| 70127-1 | 533.7 | 1.5741 | 109 | 125 | 29 | 0 | pieces 109/105, inv R 0.952, contacts 3/3 |
| 4778-1 | 378.2 | 1.1271 | 85 | 89 | 19 | 0 | pieces 85/104, inv R 0.212, contacts 2/4 |
| 40386-1 | 339.2 | 1.1315 | 115 | 131 | 48 | 0 | pieces 115/115, inv R 0.983, contacts 0/0 |
| 40181-1 | 527.2 | 1.5686 | 139 | 142 | 27 | 0 | pieces 139/139, inv R 0.993, contacts 29/36 |
| 7936-1 | 501.7 | 1.33 | 135 | 138 | 42 | 0 | pieces 135/138, inv R 0.913, contacts 11/14 |
| 40335-1 | 598.0 | 1.756 | 154 | 164 | 61 | 0 | pieces 154/150, inv R 0.993, contacts 12/17 |
| 21026-1 | 493.0 | 1.9664 | 212 | 227 | 38 | 0 | pieces 212/212, inv R 1.0, contacts 19/23 |
| 7992-1 | 749.6 | 2.2702 | 215 | 235 | 51 | 0 | pieces 215/214, inv R 0.939, contacts 11/43 |
| 8159-1 | 553.0 | 1.7328 | 183 | 197 | 11 | 0 | pieces 183/228, inv R 0.408, contacts 14/46 |
| 21113-1 | 818.6 | 2.2926 | 249 | 283 | 44 | 0 | pieces 249/243, inv R 0.996, contacts 81/102 |
| 40199-1 | 891.9 | 2.7503 | 286 | 295 | 30 | 0 | pieces 286/286, inv R 1.0, contacts 85/134 |
| 10170-1 | 693.6 | 1.9304 | 365 | 371 | 8 | 0 | pieces 365/366, inv R 0.653, contacts 31/100 |
| 40413-1 | 1969.1 | 5.8125 | 366 | 386 | 96 | 0 | pieces 366/366, inv R 0.986, contacts 21/46 |
| 7306-1 | 406.6 | 1.2907 | 70 | 76 | 38 | 0 | pieces 70/57, inv R 0.947, contacts 1/3 |
| 8658-1 | 82.2 | 0.3301 | 19 | 19 | 0 | 0 | pieces 19/32, inv R 0.25, contacts 2/5 |
| 30311-1 | 158.4 | 0.5087 | 42 | 44 | 0 | 0 | pieces 42/46, inv R 0.304, contacts 1/4 |
| 60001-1 | 376.5 | 1.0988 | 79 | 81 | 25 | 4 | pieces 79/72, inv R 0.889, contacts 4/8 |
| 4904-1 | 79.0 | 0.1862 | 24 | 23 | 0 | 0 | pieces 24/34, inv R 0.5, contacts 3/11 |
| 7808-1 | 76.7 | 0.1838 | 23 | 22 | 0 | 0 | pieces 23/34, inv R 0.147, contacts 0/1 |
| 9469-1 | 463.2 | 1.445 | 83 | 91 | 38 | 0 | pieces 83/73, inv R 0.945, contacts 2/6 |
| 30312-1 | 126.8 | 0.3215 | 33 | 32 | 0 | 0 | pieces 33/36, inv R 0.306, contacts 0/1 |
| 6966-1 | 110.9 | 0.4351 | 31 | 32 | 1 | 0 | pieces 31/38, inv R 0.0, contacts 0/0 |
| 5981-1 | 340.9 | 1.1822 | 68 | 72 | 34 | 0 | pieces 68/60, inv R 0.983, contacts 0/2 |
| 30300-1 | 104.4 | 0.2635 | 30 | 30 | 0 | 0 | pieces 30/57, inv R 0.228, contacts 0/3 |
| 41504-1 | 206.0 | 0.5797 | 50 | 49 | 12 | 0 | pieces 50/50, inv R 0.92, contacts 0/0 |
| 7242-1 | 288.8 | 1.0022 | 62 | 67 | 5 | 0 | pieces 62/60, inv R 0.317, contacts 4/6 |
| 40138-1 | 703.3 | 2.4463 | 233 | 237 | 58 | 0 | pieces 233/233, inv R 1.0, contacts 36/65 |
| 21000-1 | 223.0 | 0.7904 | 69 | 87 | 7 | 0 | pieces 69/69, inv R 0.87, contacts 52/62 |
| 4431-1 | 868.2 | 2.7343 | 205 | 209 | 59 | 0 | pieces 205/187, inv R 0.957, contacts 14/34 |
| 41071-1 | 516.1 | 1.672 | 98 | 109 | 37 | 0 | pieces 98/94, inv R 0.979, contacts 11/16 |
| 7635-1 | 673.6 | 2.0972 | 175 | 178 | 37 | 10 | pieces 175/168, inv R 0.887, contacts 0/2 |
| 41488-1 | 339.1 | 1.1705 | 89 | 99 | 23 | 0 | pieces 89/89, inv R 0.989, contacts 13/15 |
| 60059-1 | 854.6 | 2.8043 | 227 | 274 | 53 | 2 | pieces 227/219, inv R 0.991, contacts 7/25 |
| 40456-1 | 410.3 | 1.5439 | 118 | 136 | 19 | 0 | pieces 118/118, inv R 1.0, contacts 0/0 |
| 40180-1 | 564.8 | 1.7778 | 164 | 171 | 12 | 0 | pieces 164/164, inv R 1.0, contacts 28/33 |
| 7997-1 | 1193.7 | 3.3927 | 319 | 381 | 66 | 1 | pieces 319/367, inv R 0.728, contacts 25/76 |
| 40448-1 | 772.7 | 2.4324 | 188 | 199 | 48 | 0 | pieces 188/181, inv R 0.989, contacts 6/9 |
| 21027-1 | 972.3 | 3.5332 | 289 | 312 | 37 | 0 | pieces 289/289, inv R 0.979, contacts 20/32 |
| 8158-1 | 533.0 | 1.7377 | 157 | 170 | 0 | 0 | pieces 157/234, inv R 0.35, contacts 10/57 |
| 7325-1 | 695.4 | 2.3038 | 212 | 234 | 60 | 0 | pieces 212/201, inv R 0.96, contacts 4/8 |
| 7942-1 | 507.4 | 1.625 | 127 | 126 | 21 | 0 | pieces 127/127, inv R 0.874, contacts 4/8 |
| 60065-1 | 359.4 | 1.0305 | 59 | 56 | 27 | 0 | pieces 59/50, inv R 1.0, contacts 0/0 |
| 30105-1 | 158.8 | 0.6738 | 34 | 32 | 3 | 0 | pieces 34/37, inv R 0.243, contacts 0/1 |
| 7803-1 | 72.2 | 0.463 | 21 | 23 | 0 | 0 | pieces 21/38, inv R 0.342, contacts 0/10 |
| 9470-1 | 815.4 | 2.1105 | 228 | 235 | 50 | 0 | pieces 228/214, inv R 0.93, contacts 7/8 |
| 4200-1 | 486.1 | 1.6267 | 101 | 104 | 19 | 4 | pieces 101/97, inv R 0.856, contacts 1/5 |
| 5970-1 | 365.2 | 1.3606 | 79 | 81 | 18 | 0 | pieces 79/70, inv R 0.971, contacts 0/0 |
| 41505-1 | 202.7 | 0.8793 | 51 | 53 | 7 | 0 | pieces 51/51, inv R 1.0, contacts 0/2 |
| 7731-1 | 270.4 | 1.1008 | 65 | 68 | 16 | 1 | pieces 65/62, inv R 0.887, contacts 0/2 |
| 31028-1 | 715.5 | 2.1945 | 123 | 140 | 17 | 0 | pieces 123/53, inv R 1.0, contacts 2/2 |
| 21000-2 | 188.7 | 0.8373 | 69 | 77 | 0 | 0 | pieces 69/69, inv R 0.986, contacts 40/62 |
| 40377-1 | 466.8 | 1.3828 | 90 | 106 | 22 | 0 | pieces 90/90, inv R 1.0, contacts 10/13 |
| 7903-1 | 770.6 | 2.4366 | 212 | 220 | 44 | 2 | pieces 212/235, inv R 0.826, contacts 5/25 |
| 40144-1 | 529.9 | 1.9373 | 164 | 169 | 6 | 0 | pieces 164/165, inv R 0.982, contacts 39/61 |
| 40457-1 | 420.8 | 1.6147 | 140 | 161 | 10 | 0 | pieces 140/140, inv R 1.0, contacts 0/0 |
| 21302-1 | 1401.4 | 4.5543 | 479 | 497 | 107 | 0 | pieces 479/470, inv R 0.947, contacts 47/82 |
| 7893-1 | 890.4 | 2.7639 | 393 | 415 | 58 | 0 | pieces 393/387, inv R 0.907, contacts 11/17 |
| 75878-1 | 611.8 | 2.2032 | 183 | 197 | 37 | 0 | pieces 183/183, inv R 0.951, contacts 7/10 |
| 21032-1 | 857.6 | 3.0687 | 361 | 383 | 20 | 0 | pieces 361/361, inv R 1.0, contacts 59/82 |
| 8160-1 | 1064.9 | 3.2861 | 265 | 283 | 54 | 2 | pieces 265/353, inv R 0.691, contacts 15/77 |
| 7236-1 | 213.9 | 0.874 | 50 | 48 | 1 | 4 | pieces 50/56, inv R 0.429, contacts 1/2 |
| 3931-1 | 199.4 | 0.972 | 43 | 39 | 15 | 0 | pieces 43/39, inv R 1.0, contacts 3/4 |
| 7269-1 | 69.0 | 0.5267 | 23 | 24 | 0 | 0 | pieces 23/37, inv R 0.216, contacts 2/10 |
| 7875-1 | 122.7 | 0.6222 | 28 | 28 | 0 | 0 | pieces 28/39, inv R 0.154, contacts 0/2 |
| 9471-1 | 959.6 | 3.1575 | 258 | 281 | 55 | 0 | pieces 258/229, inv R 0.969, contacts 12/15 |
| 7630-1 | 548.5 | 1.7947 | 105 | 110 | 14 | 0 | pieces 105/104, inv R 0.942, contacts 13/27 |
| 30055-1 | 137.5 | 0.6714 | 31 | 30 | 0 | 0 | pieces 31/42, inv R 0.357, contacts 0/0 |
| 41500-1 | 265.2 | 0.8044 | 61 | 60 | 9 | 0 | pieces 61/58, inv R 0.966, contacts 0/0 |
| 7732-1 | 385.2 | 1.4373 | 87 | 87 | 21 | 1 | pieces 87/84, inv R 0.952, contacts 0/0 |
| 5761-1 | 461.4 | 1.6653 | 134 | 136 | 10 | 0 | pieces 134/57, inv R 0.93, contacts 0/1 |
| 21001-1 | 109.9 | 0.6574 | 69 | 71 | 1 | 0 | pieces 69/69, inv R 0.681, contacts 28/42 |
| 41485-1 | 502.8 | 1.5763 | 91 | 128 | 6 | 0 | pieces 91/91, inv R 1.0, contacts 12/12 |
| 40391-1 | 509.6 | 2.0397 | 151 | 160 | 15 | 0 | pieces 151/151, inv R 1.0, contacts 0/0 |
| 40182-1 | 634.2 | 2.1057 | 175 | 187 | 10 | 0 | pieces 175/175, inv R 0.994, contacts 58/69 |
| 7613-1 | 120.7 | 0.663 | 28 | 27 | 0 | 0 | pieces 28/34, inv R 0.235, contacts 0/3 |
| 3930-1 | 474.1 | 1.49 | 45 | 41 | 15 | 0 | pieces 45/41, inv R 0.951, contacts 2/2 |
| 60066-1 | 572.7 | 1.3899 | 78 | 86 | 26 | 0 | pieces 78/60, inv R 0.967, contacts 0/0 |
