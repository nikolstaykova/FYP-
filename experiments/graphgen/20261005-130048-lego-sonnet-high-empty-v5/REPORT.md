# Graph generation: lego

**Model:** `sonnet` · effort `high` · catalogue `empty` · 24 manuals succeeded, 4 failed · wall time 1940 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 258.921 | 253.3 | 538.7 | 6214 |
| Input tokens | 850465 | 681203 | 1784027 | 20411169 |
| Output tokens | 33452 | 31403 | 72067 | 802845 |
| Cost (USD) | 0.63 | 0.5797 | 1.3097 | 15.13 |

Estimated cost for 100 manuals at this rate: **$63.04**.

### Accuracy

**2 PDF(s) contained no building instructions** (e.g. advent-calendar covers); Claude returned an empty graph instead of inventing parts. Left out of the accuracy below: `40396-1`, `3316-1`.

| Measure | Mean | Median |
|---|---:|---:|
| Pieces built ÷ pieces in the set | 1.004 | 1.00 |
| Exact pieces (part + colour, needs an inventory page) | 0.039 | 0.0 |
| Inventory precision, by design (pieces that are in the set) | 0.978 | 1.0 |
| Inventory recall, by design (set pieces found) | 0.981 | 1.0 |
| Contact precision (brick/plate/tile pairs) | 0.338 | 0.333 |
| Booklets with no checkable contacts (no plain bricks/plates/tiles) | 5 | |
| Contact recall | 0.557 | 0.667 |

*Contacts are compared by design pair (e.g. 2×4 brick on 2×2 plate), only for plain bricks, plates and tiles, because the model reads pictures and cannot give LDraw positions.*

**By set size:**

| Pieces | Sets | Mean seconds | Mean cost | Mean inventory recall | Mean contact recall |
|---|---:|---:|---:|---:|---:|
| <100 | 17 | 199.018 | 0.467 | 0.978 | 0.459 |
| 100-249 | 5 | 544.12 | 1.389 | 0.99 | 0.875 |

### Check and repair loop

Build → check → repair → final check. **21/22** manuals had check failures after the first build; **4** of those were fully fixed by the repair. Issues in total: 189 → 109.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 22 | 224.464 | 0.559 | 0.009 |
| parts | 22 | 0.473 | 0.0 | 0.0 |
| repair1 | 18 | 49.728 | 0.095 | 0.004 |
| repair2 | 11 | 23.645 | 0.08 | 0.004 |

**Accuracy before → after repair** (18 booklets repaired): inventory recall 0.701 → 0.983; contact recall 0.385 → 0.578; contact precision 0.446 → 0.386.

### Spec rules and structure

- Manuals with **no rule problems**: 6/24 (25%).
- Problems by rule: V4 ×51, V3 ×39, V2 ×2 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 2/24; overrides used in 1.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 22 | 0 | 0 |

### Failures

- `7936-1`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:20pm (Europe/Dublin)
- `7992-1`: RuntimeError: claude -p failed: API Error: This request would exceed your account's rate limit. Please try again later.
- `40335-1`: RuntimeError: claude -p failed: API Error: This request would exceed your account's rate limit. Please try again later.
- `21026-1`: RuntimeError: claude -p failed: API Error: This request would exceed your account's rate limit. Please try again later.

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| 30103-1 | 68.6 | 0.1211 | 28 | 35 | 0 | 0 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4991-1 | 72.7 | 0.1243 | 26 | 27 | 0 | 1 | pieces 26/26, inv R 0.885, contacts 0/1 |
| 7603-1 | 97.7 | 0.1764 | 33 | 36 | 0 | 4 | pieces 33/33, inv R 1.0, contacts 5/11 |
| 7268-1 | 105.4 | 0.1497 | 32 | 35 | 0 | 0 | pieces 32/32, inv R 1.0, contacts 1/2 |
| 7246-1 | 82.7 | 0.1481 | 33 | 33 | 0 | 0 | pieces 33/33, inv R 1.0, contacts 0/0 |
| 7736-1 | 155.9 | 0.3917 | 28 | 53 | 0 | 13 | pieces 28/28, inv R 1.0, contacts 0/0 |
| 4641-1 | 206.3 | 0.4341 | 31 | 40 | 0 | 2 | pieces 31/29, inv R 1.0, contacts 0/0 |
| 30161-1 | 99.6 | 0.1898 | 45 | 47 | 0 | 0 | pieces 45/45, inv R 1.0, contacts 2/4 |
| 5969-1 | 277.8 | 0.5797 | 33 | 63 | 0 | 4 | pieces 33/33, inv R 0.97, contacts 0/1 |
| 30313-1 | 131.9 | 0.2831 | 44 | 46 | 0 | 6 | pieces 44/44, inv R 1.0, contacts 1/4 |
| 41502-1 | 268.0 | 0.5652 | 37 | 52 | 0 | 14 | pieces 37/45, inv R 0.822, contacts 0/2 |
| 21003-1 | 216.7 | 0.6236 | 57 | 82 | 0 | 0 | pieces 57/57, inv R 1.0, contacts 14/16 |
| 7902-1 | 253.3 | 0.678 | 62 | 73 | 0 | 1 | pieces 62/62, inv R 1.0, contacts 2/3 |
| 41181-1 | 259.9 | 0.7666 | 63 | 74 | 0 | 1 | pieces 63/63, inv R 0.984, contacts 1/1 |
| 7634-1 | 372.1 | 0.9483 | 76 | 111 | 0 | 3 | pieces 76/74, inv R 1.0, contacts 2/3 |
| 41589-1 | 289.2 | 0.7292 | 79 | 116 | 0 | 1 | pieces 79/79, inv R 1.0, contacts 12/15 |
| 60054-1 | 425.5 | 1.0317 | 91 | 105 | 0 | 3 | pieces 91/91, inv R 0.967, contacts 1/4 |
| 40148-1 | 538.7 | 1.3097 | 103 | 225 | 0 | 27 | pieces 103/100, inv R 1.0, contacts 5/6 |
| 4778-1 | 416.6 | 1.1371 | 105 | 143 | 0 | 1 | pieces 105/104, inv R 1.0, contacts 3/4 |
| 70127-1 | 615.5 | 1.4032 | 118 | 155 | 0 | 2 | pieces 118/105, inv R 1.0, contacts 3/3 |
| 40181-1 | 452.9 | 1.0454 | 139 | 167 | 0 | 9 | pieces 139/139, inv R 1.0, contacts 33/36 |
| 40386-1 | 696.9 | 2.0487 | 115 | 212 | 0 | 0 | pieces 115/115, inv R 0.948, contacts 0/0 |
