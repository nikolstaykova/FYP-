# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 3 manuals succeeded, 0 failed · wall time 75 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 48.5 | 46.0 | 74.3 | 146 |
| Input tokens | 30183 | 24104 | 43737 | 90550 |
| Output tokens | 6019 | 5568 | 9857 | 18056 |
| Cost (USD) | 0.152 | 0.1257 | 0.2294 | 0.46 |

Estimated cost for 100 manuals at this rate: **$15.23**.

### Accuracy

**2 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 2 (50%) |
| Mean net precision | 0.834 |
| Mean net recall | 0.834 |
| Parts list correct (V1) | 2 / 2 |

**1 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 1.0.

### Check and repair loop

Build → check → repair → final check. **0/3** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 3 | 33.0 | 0.103 | 0.0 |
| parts | 3 | 15.5 | 0.049 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 3/3 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/3; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| blink | 25.2 | 0.1019 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| button | 46.0 | 0.1257 | 9 | 28 | 0 | 0 | nets 2/3  |
| pi-gpio-music-box | 74.3 | 0.2294 | 16 | 69 | 0 | 0 | listed parts 1.0 |
