# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 100 manuals succeeded, 0 failed · wall time 87 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 3.379 | 3.3 | 3.5 | 338 |
| Input tokens | 0 | 0 | 0 | 0 |
| Output tokens | 0 | 0 | 0 | 0 |
| Cost (USD) | 0.0 | 0.0 | 0.0 | 0.0 |

Estimated cost for 100 manuals at this rate: **$0.0**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.619 | 1.08 |
| Exact pieces (part + colour, needs an inventory page) | 0.0 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.745 | 0.807 |
| Inventory recall, by design (set pieces found) | 0.863 | 0.889 |
| Contact precision (brick/plate/tile pairs) | 1.0 | 1.0 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 16 | |
| Contact recall | 0.992 | 1.0 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 58 | 3.403 | 0.0 | 0.832 | 1.0 |
| 100-249 | 32 | 3.331 | 0.0 | 0.897 | 0.976 |
| 250+ | 10 | 3.39 | 0.0 | 0.937 | 1.0 |

### Check and repair loop

Build → check → repair → final check. **100/100** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 18582 → 18582.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 100 | 3.27 | 0.0 | 0.012 |
| parts | 100 | 0.1 | 0.0 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 0/100 (0%).
- Problems by rule: V2 ×14914 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/100; overrides used in 0.

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
| 7268-1 | 5.5 | 0.0 | 34 | 2 | 0 | 31 | pieces 34/32, inv R 0.5, contacts 2/2 |
| 4991-1 | 5.5 | 0.0 | 37 | 1 | 0 | 35 | pieces 37/26, inv R 0.923, contacts 1/1 |
| 7603-1 | 5.7 | 0.0 | 33 | 11 | 0 | 23 | pieces 33/33, inv R 0.879, contacts 11/11 |
| 30103-1 | 5.8 | 0.0 | 35 | 0 | 0 | 35 | pieces 35/28, inv R 1.0, contacts 0/0 |
| 7736-1 | 3.1 | 0.0 | 39 | 0 | 0 | 39 | pieces 39/28, inv R 0.857, contacts 0/0 |
| 4641-1 | 3.0 | 0.0 | 41 | 0 | 0 | 41 | pieces 41/29, inv R 0.828, contacts 0/0 |
| 7246-1 | 3.1 | 0.0 | 43 | 0 | 0 | 43 | pieces 43/33, inv R 0.848, contacts 0/0 |
| 5969-1 | 3.3 | 0.0 | 31 | 1 | 0 | 29 | pieces 31/33, inv R 0.848, contacts 1/1 |
| 41502-1 | 3.1 | 0.0 | 186 | 2 | 0 | 183 | pieces 186/45, inv R 0.689, contacts 2/2 |
| 30161-1 | 3.2 | 0.0 | 44 | 4 | 0 | 39 | pieces 44/45, inv R 0.733, contacts 4/4 |
| 30313-1 | 3.1 | 0.0 | 68 | 4 | 0 | 64 | pieces 68/44, inv R 0.841, contacts 4/4 |
| 40396-1 | 3.1 | 0.0 | 53 | 8 | 0 | 44 | pieces 53/53, inv R 0.962, contacts 8/8 |
| 7902-1 | 3.1 | 0.0 | 71 | 3 | 0 | 66 | pieces 71/62, inv R 0.694, contacts 3/3 |
| 21003-1 | 3.3 | 0.0 | 2028 | 16 | 0 | 2017 | pieces 2028/57, inv R 0.895, contacts 16/16 |
| 41181-1 | 3.4 | 0.0 | 157 | 1 | 0 | 155 | pieces 157/63, inv R 0.889, contacts 1/1 |
| 7634-1 | 3.4 | 0.0 | 83 | 3 | 0 | 79 | pieces 83/74, inv R 0.986, contacts 3/3 |
| 41589-1 | 3.2 | 0.0 | 85 | 15 | 0 | 65 | pieces 85/79, inv R 0.886, contacts 15/15 |
| 60054-1 | 3.3 | 0.0 | 98 | 4 | 0 | 92 | pieces 98/91, inv R 0.835, contacts 4/4 |
| 40148-1 | 3.2 | 0.0 | 99 | 6 | 0 | 89 | pieces 99/100, inv R 0.92, contacts 6/6 |
| 4778-1 | 3.3 | 0.0 | 215 | 4 | 0 | 209 | pieces 215/104, inv R 0.962, contacts 4/4 |
| 70127-1 | 3.3 | 0.0 | 429 | 3 | 0 | 423 | pieces 429/105, inv R 0.829, contacts 3/3 |
| 40386-1 | 3.3 | 0.0 | 115 | 0 | 0 | 115 | pieces 115/115, inv R 0.93, contacts 0/0 |
| 40181-1 | 3.3 | 0.0 | 139 | 36 | 0 | 96 | pieces 139/139, inv R 0.993, contacts 36/36 |
| 7936-1 | 3.4 | 0.0 | 147 | 14 | 0 | 134 | pieces 147/138, inv R 0.87, contacts 14/14 |
| 40335-1 | 3.4 | 0.0 | 158 | 17 | 0 | 137 | pieces 158/150, inv R 0.893, contacts 17/17 |
| 21026-1 | 3.1 | 0.0 | 210 | 23 | 0 | 176 | pieces 210/212, inv R 0.835, contacts 23/23 |
| 3316-1 | 3.2 | 0.0 | 219 | 11 | 0 | 204 | pieces 219/206, inv R 0.806, contacts 11/11 |
| 7992-1 | 3.4 | 0.0 | 223 | 43 | 0 | 187 | pieces 223/214, inv R 0.921, contacts 43/43 |
| 8159-1 | 3.3 | 0.0 | 290 | 46 | 0 | 231 | pieces 290/228, inv R 0.93, contacts 46/46 |
| 21113-1 | 3.2 | 0.0 | 258 | 102 | 0 | 150 | pieces 258/243, inv R 0.955, contacts 102/102 |
| 40199-1 | 3.4 | 0.0 | 286 | 134 | 0 | 169 | pieces 286/286, inv R 0.983, contacts 134/134 |
| 10170-1 | 3.4 | 0.0 | 365 | 100 | 0 | 272 | pieces 365/366, inv R 0.959, contacts 100/100 |
| 8658-1 | 3.2 | 0.0 | 31 | 5 | 0 | 25 | pieces 31/32, inv R 0.969, contacts 5/5 |
| 40413-1 | 3.3 | 0.0 | 366 | 46 | 0 | 332 | pieces 366/366, inv R 0.954, contacts 46/46 |
| 7306-1 | 3.3 | 0.0 | 83 | 3 | 0 | 79 | pieces 83/57, inv R 0.684, contacts 3/3 |
| 60001-1 | 3.2 | 0.0 | 89 | 8 | 0 | 78 | pieces 89/72, inv R 0.75, contacts 8/8 |
| 4904-1 | 3.1 | 0.0 | 32 | 11 | 0 | 17 | pieces 32/34, inv R 0.941, contacts 11/11 |
| 30311-1 | 3.2 | 0.0 | 59 | 4 | 0 | 55 | pieces 59/46, inv R 0.891, contacts 4/4 |
| 7808-1 | 3.2 | 0.0 | 34 | 1 | 0 | 32 | pieces 34/34, inv R 0.529, contacts 1/1 |
| 9469-1 | 3.2 | 0.0 | 92 | 6 | 0 | 84 | pieces 92/73, inv R 0.918, contacts 6/6 |
| 30312-1 | 3.2 | 0.0 | 55 | 1 | 0 | 53 | pieces 55/36, inv R 0.722, contacts 1/1 |
| 6966-1 | 3.4 | 0.0 | 39 | 0 | 0 | 39 | pieces 39/38, inv R 0.895, contacts 0/0 |
| 5981-1 | 3.2 | 0.0 | 57 | 2 | 0 | 54 | pieces 57/60, inv R 0.767, contacts 2/2 |
| 30300-1 | 3.4 | 0.0 | 57 | 3 | 0 | 52 | pieces 57/57, inv R 0.965, contacts 3/3 |
| 41504-1 | 3.1 | 0.0 | 154 | 0 | 0 | 154 | pieces 154/50, inv R 0.72, contacts 0/0 |
| 7242-1 | 3.1 | 0.0 | 125 | 6 | 0 | 116 | pieces 125/60, inv R 0.8, contacts 6/6 |
| 40138-1 | 3.4 | 0.0 | 227 | 65 | 0 | 172 | pieces 227/233, inv R 0.901, contacts 65/65 |
| 21000-1 | 3.3 | 0.0 | 69 | 62 | 0 | 28 | pieces 69/69, inv R 0.87, contacts 62/62 |
| 41071-1 | 3.1 | 0.0 | 119 | 16 | 0 | 100 | pieces 119/94, inv R 0.862, contacts 16/16 |
| 4431-1 | 3.3 | 0.0 | 212 | 34 | 0 | 177 | pieces 212/187, inv R 0.802, contacts 34/34 |
| 7635-1 | 3.4 | 0.0 | 186 | 2 | 0 | 182 | pieces 186/168, inv R 0.815, contacts 2/2 |
| 41488-1 | 3.4 | 0.0 | 89 | 15 | 0 | 70 | pieces 89/89, inv R 0.933, contacts 15/15 |
| 60059-1 | 3.1 | 0.0 | 238 | 25 | 0 | 207 | pieces 238/219, inv R 0.877, contacts 25/25 |
| 40456-1 | 3.3 | 0.0 | 118 | 0 | 0 | 118 | pieces 118/118, inv R 0.932, contacts 0/0 |
| 40180-1 | 3.2 | 0.0 | 164 | 33 | 0 | 119 | pieces 164/164, inv R 0.994, contacts 33/33 |
| 7997-1 | 3.3 | 0.0 | 415 | 76 | 0 | 338 | pieces 415/367, inv R 0.932, contacts 76/76 |
| 40448-1 | 3.3 | 0.0 | 200 | 9 | 0 | 189 | pieces 200/181, inv R 0.994, contacts 9/9 |
| 21027-1 | 3.3 | 0.0 | 289 | 32 | 0 | 259 | pieces 289/289, inv R 0.917, contacts 32/32 |
| 8158-1 | 3.4 | 0.0 | 297 | 57 | 0 | 239 | pieces 297/234, inv R 0.902, contacts 57/57 |
| 7325-1 | 3.4 | 0.0 | 233 | 8 | 0 | 220 | pieces 233/201, inv R 0.836, contacts 8/8 |
| 7942-1 | 3.2 | 0.0 | 135 | 8 | 0 | 125 | pieces 135/127, inv R 0.874, contacts 8/8 |
| 60065-1 | 3.3 | 0.0 | 71 | 0 | 0 | 71 | pieces 71/50, inv R 0.84, contacts 0/0 |
| 30105-1 | 3.4 | 0.0 | 41 | 1 | 0 | 39 | pieces 41/37, inv R 0.865, contacts 1/1 |
| 7803-1 | 3.3 | 0.0 | 38 | 10 | 0 | 27 | pieces 38/38, inv R 0.763, contacts 10/10 |
| 9470-1 | 3.3 | 0.0 | 242 | 8 | 0 | 233 | pieces 242/214, inv R 0.734, contacts 8/8 |
| 4200-1 | 3.3 | 0.0 | 103 | 5 | 0 | 97 | pieces 103/97, inv R 0.763, contacts 5/5 |
| 5970-1 | 3.3 | 0.0 | 66 | 0 | 0 | 66 | pieces 66/70, inv R 0.929, contacts 0/0 |
| 41505-1 | 3.3 | 0.0 | 167 | 2 | 0 | 164 | pieces 167/51, inv R 0.765, contacts 2/2 |
| 7731-1 | 3.3 | 0.0 | 71 | 2 | 0 | 68 | pieces 71/62, inv R 0.806, contacts 2/2 |
| 31028-1 | 3.2 | 0.0 | 53 | 2 | 0 | 50 | pieces 53/53, inv R 0.943, contacts 2/2 |
| 21000-2 | 3.3 | 0.0 | 69 | 62 | 0 | 28 | pieces 69/69, inv R 0.986, contacts 62/62 |
| 7903-1 | 3.5 | 0.0 | 265 | 25 | 0 | 235 | pieces 265/235, inv R 0.928, contacts 25/25 |
| 40377-1 | 3.4 | 0.0 | 90 | 13 | 0 | 70 | pieces 90/90, inv R 0.956, contacts 13/13 |
| 40457-1 | 3.3 | 0.0 | 142 | 0 | 0 | 142 | pieces 142/140, inv R 0.943, contacts 0/0 |
| 40144-1 | 3.5 | 0.0 | 164 | 61 | 0 | 90 | pieces 164/165, inv R 0.982, contacts 61/61 |
| 21302-1 | 3.4 | 0.0 | 454 | 82 | 0 | 350 | pieces 454/470, inv R 0.928, contacts 82/82 |
| 7893-1 | 3.4 | 0.0 | 803 | 17 | 0 | 777 | pieces 803/387, inv R 0.868, contacts 17/17 |
| 75878-1 | 3.5 | 0.0 | 277 | 10 | 0 | 263 | pieces 277/183, inv R 0.945, contacts 10/10 |
| 21032-1 | 3.4 | 0.0 | 361 | 82 | 0 | 274 | pieces 361/361, inv R 0.97, contacts 82/82 |
| 8160-1 | 3.4 | 0.0 | 415 | 77 | 0 | 331 | pieces 415/353, inv R 0.881, contacts 77/77 |
| 7236-1 | 3.5 | 0.0 | 63 | 2 | 0 | 59 | pieces 63/56, inv R 0.821, contacts 2/2 |
| 3931-1 | 3.2 | 0.0 | 46 | 4 | 0 | 40 | pieces 46/39, inv R 0.974, contacts 4/4 |
| 7269-1 | 3.4 | 0.0 | 37 | 10 | 0 | 28 | pieces 37/37, inv R 0.459, contacts 10/10 |
| 7875-1 | 3.5 | 0.0 | 41 | 2 | 0 | 38 | pieces 41/39, inv R 0.872, contacts 2/2 |
| 9471-1 | 3.3 | 0.0 | 281 | 15 | 0 | 259 | pieces 281/229, inv R 0.878, contacts 15/15 |
| 7630-1 | 3.4 | 0.0 | 113 | 27 | 0 | 82 | pieces 113/104, inv R 0.962, contacts 27/27 |
| 30055-1 | 3.4 | 0.0 | 42 | 0 | 0 | 42 | pieces 42/42, inv R 1.0, contacts 0/0 |
| 41500-1 | 3.4 | 0.0 | 142 | 0 | 0 | 142 | pieces 142/58, inv R 0.724, contacts 0/0 |
| 7732-1 | 3.2 | 0.0 | 93 | 0 | 0 | 93 | pieces 93/84, inv R 0.952, contacts 0/0 |
| 5761-1 | 3.5 | 0.0 | 53 | 1 | 0 | 51 | pieces 53/57, inv R 0.825, contacts 1/1 |
| 21001-1 | 3.4 | 0.0 | 69 | 42 | 0 | 32 | pieces 69/69, inv R 0.667, contacts 42/42 |
| 41485-1 | 3.4 | 0.0 | 99 | 12 | 0 | 84 | pieces 99/91, inv R 0.912, contacts 12/12 |
| 40391-1 | 3.5 | 0.0 | 153 | 0 | 0 | 153 | pieces 153/151, inv R 0.934, contacts 0/0 |
| 40182-1 | 3.4 | 0.0 | 175 | 69 | 0 | 96 | pieces 175/175, inv R 0.954, contacts 69/69 |
| 75892-1 | 3.5 | 0.0 | 461 | 18 | 0 | 443 | pieces 461/217, inv R 0.668, contacts 6/18 |
| 21033-1 | 3.6 | 0.0 | 443 | 140 | 0 | 316 | pieces 443/444, inv R 0.982, contacts 140/140 |
| 7613-1 | 3.4 | 0.0 | 34 | 3 | 0 | 30 | pieces 34/34, inv R 0.794, contacts 3/3 |
| 60066-1 | 3.3 | 0.0 | 96 | 0 | 0 | 96 | pieces 96/60, inv R 0.783, contacts 0/0 |
| 3930-1 | 2.9 | 0.0 | 48 | 2 | 0 | 45 | pieces 48/41, inv R 0.902, contacts 2/2 |
| 4905-1 | 2.0 | 0.0 | 40 | 8 | 0 | 25 | pieces 40/39, inv R 0.641, contacts 8/8 |
