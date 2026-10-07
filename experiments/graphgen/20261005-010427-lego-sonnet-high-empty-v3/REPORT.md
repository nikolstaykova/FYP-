# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 65 manuals succeeded, 4 failed · wall time 3824 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 334.398 | 285.3 | 597.8 | 21736 |
| Input tokens | 163453 | 99694 | 362074 | 10624443 |
| Output tokens | 51624 | 45044 | 93427 | 3355552 |
| Cost (USD) | 0.85 | 0.7395 | 1.7909 | 55.26 |

Estimated cost for 100 manuals at this rate: **$85.02**.

### Accuracy

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.0 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.014 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.999 | 1.0 |
| Inventory recall, by design (set pieces found) | 0.999 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.364 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 10 | |
| Contact recall | 0.589 | 0.636 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 39 | 201.085 | 0.468 | 0.998 | 0.587 |
| 100-249 | 22 | 478.286 | 1.29 | 1.0 | 0.599 |
| 250+ | 4 | 842.825 | 2.157 | 1.0 | 0.557 |

### Check and repair loop

Build → check → repair → final check. **57/65** manuals had check failures after the first build; **2** of those were fully fixed by the repair. Issues in total: 530 → 493.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 65 | 272.758 | 0.604 | 0.011 |
| parts | 65 | 0.268 | 0.0 | 0.0 |
| repair1 | 30 | 75.937 | 0.354 | 0.019 |
| repair2 | 23 | 74.357 | 0.235 | 0.015 |

**Accuracy before → after repair** (56 booklets repaired): inventory recall 0.999 → 0.999; contact recall 0.597 → 0.597; contact precision 0.349 → 0.349.

### Spec rules and structure

- Manuals with **no rule problems**: 20/65 (31%).
- Problems by rule: V2 ×213, V3 ×210, V4 ×19 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 31/65; overrides used in 26.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 0 | 0 |
| 65 | 0 | 0 |

### Failures

- `40413-1`: TimeoutExpired: Command 'claude -p' timed out after 1464 seconds
- `4200-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `9470-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `7731-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 49.4 | 0.0985 | 28 | 30 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 7603-1 | 83.5 | 0.14 | 33 | 34 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 4991-1 | 63.6 | 0.0912 | 26 | 30 | 0 | 1 | pieces 26/26, inv R 0.923, contacts 1/1 |
| 7268-1 | 96.7 | 0.1594 | 32 | 32 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 0/2 |
| 4641-1 | 94.8 | 0.3041 | 29 | 30 | 0 | 0 | pieces 29/29, inv R 1.0, contacts 0/0 |
| 7246-1 | 77.2 | 0.1144 | 33 | 33 | 0 | 1 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 5969-1 | 285.3 | 0.7473 | 33 | 69 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 1/1 |
| 7736-1 | 60.0 | 0.2069 | 28 | 47 | 0 | 5 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 30161-1 | 226.9 | 0.3713 | 45 | 94 | 0 | 2 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 41502-1 | 333.7 | 0.4606 | 45 | 76 | 0 | 3 | pieces 45/45, inv R 1.0, contacts 2/2 |
| 40396-1 | 307.9 | 0.4762 | 53 | 87 | 0 | 0 | pieces 53/53, inv R 1.0, contacts 5/8 |
| 30313-1 | 113.2 | 0.2054 | 44 | 71 | 0 | 5 | pieces 44/44, inv R 1.0, contacts 2/4 |
| 21003-1 | 91.1 | 0.2925 | 57 | 69 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 14/16 |
| 7902-1 | 363.2 | 0.9333 | 62 | 76 | 0 | 0 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 7634-1 | 362.2 | 0.9812 | 74 | 94 | 0 | 1 | pieces 74/74, inv R 1.0, contacts 2/3 |
| 41181-1 | 195.4 | 0.7358 | 63 | 65 | 0 | 3 | pieces 63/63, inv R 1.0, contacts 1/1 |
| 60054-1 | 307.2 | 1.03 | 91 | 103 | 0 | 3 | pieces 91/91, inv R 1.0, contacts 2/4 |
| 41589-1 | 189.3 | 0.4848 | 79 | 99 | 0 | 1 | pieces 79/79, inv R 1.0, contacts 12/15 |
| 40148-1 | 344.3 | 0.9435 | 100 | 113 | 0 | 3 | pieces 100/100, inv R 1.0, contacts 5/6 |
| 4778-1 | 352.4 | 0.7158 | 104 | 114 | 0 | 0 | pieces 104/104, inv R 1.0, contacts 2/4 |
| 70127-1 | 375.1 | 1.0016 | 105 | 136 | 0 | 0 | pieces 105/105, inv R 1.0, contacts 3/3 |
| 40386-1 | 315.1 | 0.8628 | 115 | 176 | 0 | 0 | pieces 115/115, inv R 1.0, contacts 0/0 |
| 40181-1 | 486.5 | 1.2669 | 139 | 149 | 0 | 8 | pieces 139/139, inv R 1.0, contacts 30/36 |
| 7936-1 | 479.7 | 1.3277 | 138 | 168 | 0 | 10 | pieces 138/138, inv R 1.0, contacts 10/14 |
| 40335-1 | 533.1 | 1.4796 | 150 | 170 | 0 | 10 | pieces 150/150, inv R 1.0, contacts 14/17 |
| 21026-1 | 354.6 | 1.3051 | 212 | 255 | 0 | 10 | pieces 212/212, inv R 1.0, contacts 17/23 |
| 3316-1 | 164.2 | 0.4984 | 206 | 0 | 0 | 206 | pieces 206/206, inv R 1.0, contacts 0/11 |
| 7992-1 | 747.5 | 2.0844 | 214 | 233 | 0 | 3 | pieces 214/214, inv R 1.0, contacts 26/43 |
| 8159-1 | 408.7 | 0.894 | 228 | 252 | 0 | 0 | pieces 228/228, inv R 1.0, contacts 10/46 |
| 21113-1 | 857.7 | 2.163 | 243 | 280 | 0 | 2 | pieces 243/243, inv R 1.0, contacts 93/102 |
| 40199-1 | 603.7 | 1.3105 | 286 | 306 | 0 | 5 | pieces 286/286, inv R 1.0, contacts 98/134 |
| 10170-1 | 664.5 | 1.6724 | 366 | 430 | 0 | 0 | pieces 366/366, inv R 1.0, contacts 54/100 |
| 8658-1 | 154.8 | 0.2618 | 32 | 83 | 0 | 4 | pieces 32/32, inv R 1.0, contacts 4/5 |
| 7306-1 | 419.6 | 1.0839 | 57 | 61 | 0 | 2 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 30311-1 | 170.3 | 0.2604 | 46 | 55 | 0 | 3 | pieces 46/46, inv R 1.0, contacts 2/4 |
| 60001-1 | 259.1 | 0.8234 | 72 | 77 | 0 | 0 | pieces 72/72, inv R 1.0, contacts 4/8 |
| 4904-1 | 213.4 | 0.3313 | 34 | 73 | 0 | 0 | pieces 34/34, inv R 1.0, contacts 7/11 |
| 7808-1 | 42.5 | 0.0958 | 34 | 35 | 0 | 1 | pieces 34/34, inv R 1.0, contacts 1/1 |
| 9469-1 | 360.1 | 0.9273 | 73 | 90 | 0 | 10 | pieces 73/73, inv R 1.0, contacts 4/6 |
| 30312-1 | 132.7 | 0.2238 | 36 | 53 | 0 | 0 | pieces 36/36, inv R 1.0, contacts 0/1 |
| 6966-1 | 135.8 | 0.2183 | 38 | 39 | 0 | 3 | pieces 38/38, inv R 1.0, contacts 0/0 |
| 30300-1 | 255.3 | 0.3942 | 57 | 66 | 0 | 1 | pieces 57/57, inv R 1.0, contacts 2/3 |
| 41504-1 | 183.8 | 0.407 | 50 | 55 | 0 | 0 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 7242-1 | 105.0 | 0.3006 | 60 | 61 | 0 | 4 | pieces 60/60, inv R 1.0, contacts 2/6 |
| 5981-1 | 279.1 | 0.6392 | 60 | 83 | 0 | 7 | pieces 60/60, inv R 1.0, contacts 0/2 |
| 21000-1 | 175.2 | 0.3754 | 69 | 100 | 0 | 0 | pieces 69/69, inv R 1.0, contacts 58/62 |
| 40138-1 | 557.4 | 1.9533 | 233 | 243 | 0 | 15 | pieces 233/233, inv R 1.0, contacts 35/65 |
| 41071-1 | 394.0 | 1.1282 | 94 | 100 | 0 | 7 | pieces 94/94, inv R 1.0, contacts 13/16 |
| 4431-1 | 774.0 | 2.1499 | 187 | 204 | 0 | 8 | pieces 187/187, inv R 1.0, contacts 18/34 |
| 41488-1 | 217.3 | 0.3223 | 89 | 106 | 0 | 0 | pieces 89/89, inv R 1.0, contacts 12/15 |
| 60059-1 | 590.0 | 1.7909 | 219 | 279 | 0 | 18 | pieces 219/219, inv R 1.0, contacts 11/25 |
| 40456-1 | 279.0 | 0.734 | 118 | 148 | 0 | 0 | pieces 118/118, inv R 1.0, contacts 0/0 |
| 7635-1 | 597.8 | 1.3024 | 168 | 186 | 0 | 8 | pieces 168/168, inv R 1.0, contacts 0/2 |
| 40180-1 | 528.6 | 1.4789 | 164 | 174 | 0 | 0 | pieces 164/164, inv R 1.0, contacts 27/33 |
| 40448-1 | 460.9 | 1.0678 | 181 | 206 | 0 | 4 | pieces 181/181, inv R 1.0, contacts 8/9 |
| 21027-1 | 589.9 | 1.7967 | 289 | 338 | 0 | 11 | pieces 289/289, inv R 1.0, contacts 21/32 |
| 8158-1 | 461.0 | 0.9809 | 234 | 309 | 0 | 0 | pieces 234/234, inv R 1.0, contacts 26/57 |
| 7942-1 | 391.0 | 0.9792 | 127 | 145 | 0 | 10 | pieces 127/127, inv R 1.0, contacts 4/8 |
| 60065-1 | 258.3 | 0.7722 | 50 | 78 | 0 | 4 | pieces 50/50, inv R 1.0, contacts 0/0 |
| 7325-1 | 463.7 | 1.4047 | 201 | 238 | 0 | 4 | pieces 201/201, inv R 1.0, contacts 5/8 |
| 7997-1 | 1513.2 | 3.85 | 367 | 379 | 0 | 8 | pieces 367/367, inv R 1.0, contacts 23/76 |
| 7803-1 | 99.2 | 0.1717 | 38 | 40 | 0 | 4 | pieces 38/38, inv R 1.0, contacts 3/10 |
| 30105-1 | 199.2 | 0.4727 | 37 | 57 | 0 | 0 | pieces 37/37, inv R 1.0, contacts 0/1 |
| 5970-1 | 255.0 | 0.7395 | 70 | 67 | 0 | 13 | pieces 70/70, inv R 1.0, contacts 0/0 |
| 41505-1 | 232.0 | 0.4648 | 51 | 59 | 0 | 2 | pieces 51/51, inv R 1.0, contacts 0/2 |
