# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 4 manuals succeeded, 0 failed · wall time 64 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 37.8 | 39.3 | 61.2 | 151 |
| Input tokens | 18701 | 18871 | 19077 | 74804 |
| Output tokens | 5617 | 5926 | 9707 | 22468 |
| Cost (USD) | 0.089 | 0.0917 | 0.1316 | 0.36 |

Estimated cost for 100 manuals at this rate: **$8.92**.

### Accuracy

**4 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 1 / 4 (25%) |
| Mean net precision | 0.616 |
| Mean net recall | 0.545 |
| Parts list correct (V1) | 2 / 4 |

### Check and repair loop

Build → check → repair → final check. **0/4** manuals had check failures after the first build; **0** of those were fully fixed by the repair. Issues in total: 0 → 0.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 4 | 37.8 | 0.089 | 0.0 |

### Spec rules and structure

- Manuals with **no rule problems**: 4/4 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 1/4; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 4 | 0 | 0 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| input-pullup-serial | 20.6 | 0.0606 | 5 | 16 | 0 | 0 | nets 1/4  |
| keyboard-message | 30.1 | 0.0729 | 8 | 28 | 0 | 0 | nets 3/3 ✅ |
| joystick-mouse-control | 39.3 | 0.0917 | 12 | 46 | 0 | 0 | nets 2/8  |
| row-column-scanning | 61.2 | 0.1316 | 45 | 140 | 0 | 0 | nets 19/28  |
