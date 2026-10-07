# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 9 manuals succeeded, 0 failed · wall time 1 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 37.644 | 36.7 | 69.3 | 339 |
| Input tokens | 16329 | 16905 | 17538 | 146959 |
| Output tokens | 5577 | 5356 | 10658 | 50195 |
| Cost (USD) | 0.089 | 0.0866 | 0.1321 | 0.81 |

Estimated cost for 100 manuals at this rate: **$8.95**.

### Accuracy

**7 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 4 / 7 (57%) |
| Mean net precision | 0.762 |
| Mean net recall | 0.724 |
| Parts list correct (V1) | 6 / 7 |

**2 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 1.0.

### Spec rules and structure

- Manuals with **no rule problems**: 8/9 (89%).
- Problems by rule: V4 ×20, V3 ×1 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 2/9; overrides used in 2.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 9 | 1 | 2 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| button | 36.7 | 0.085 | 9 | 32 | 0 | 0 | nets 1/3  |
| arrays | 43.6 | 0.0973 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| blink | 17.0 | 0.0568 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| digital-read-serial | 35.0 | 0.0838 | 9 | 32 | 0 | 0 | nets 1/3  |
| for-loop | 45.0 | 0.0993 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| fade | 18.9 | 0.0574 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 23.9 | 0.0866 | 6 | 18 | 0 | 0 | nets 2/5  |
| pi-interactive-traffic-lights-python | 69.3 | 0.1321 | 17 | 64 | 1 | 0 | listed parts 1.0 |
| pi-gpio-music-box | 49.4 | 0.1068 | 16 | 70 | 1 | 21 | listed parts 1.0 |
