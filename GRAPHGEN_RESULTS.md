# Graph generation: results

*Updated 15 October 2026.*

How each version turns a manual into one build graph ([GRAPH_SPEC.md](./GRAPH_SPEC.md)), which one we chose, and
why. Full tables and every version in detail:
[`tests/experiments/graphgen/GRAPHGEN_RESULTS_full.md`](./experiments/graphgen/GRAPHGEN_RESULTS_full.md). Plain-language
walk-through: [`HOW_IT_WORKS.md`](./HOW_IT_WORKS.md).

**The pipeline is the same for every version and domain** (`pipeline.run_case`): parts → build → check → repair →
save. Versions differ in how each step is done.

**The setup for every version:**
- **Model:** Claude Sonnet.
- **Cost:** Claude Code's estimate at API list prices.
- **Test sets:** 117 electronics tutorials and 100 LEGO booklets.

---

## Arduino

**How it is judged:** the circuit is compared with CircuitQuest's verified lessons, using CircuitQuest's own
checker. There are 28 tutorials where its answer is the only right one.

| Version | The big change | Circuit correct (28) | Real wiring mistakes | Time / cost per tutorial |
|---|---|---:|---:|---|
| v1 | Claude reads the tutorial and writes the graph in one go | 82% | 5 | 41 s / $0.10 |
| v2 | **Code checks the circuit's laws; Claude repairs** | 96% | 1 | 44 s / $0.12 |
| v3 | Claude lists the parts first, then wires them | 93% | 2 | 100 s / $0.19 |
| v5 | Parts with electrical facts (voltages); a part-lookup tool | 96% | 1 | 70 s / $0.16 |
| v6 | **Breadboard sense** (legs placed as they fit, chips across the gap) and **pin tables** followed row by row | **100%** | **0** | 67 s / $0.18 |
| v6 from a link | Claude opens the tutorial's web page itself | **100%** | **0** | 49 s / $0.11 |
| **+ program and shields** (current) | **The program is checked against the circuit** (every pin it reads must be wired; it wins over the page's text). Stacked shields are joined by code from a datasheet table | 100% | 0, plus 2 page errors fixed | about the same |

**Chosen: v6 from a link, with the program and shield checks.**
- **Why:**
  - it is the only version with no wiring mistakes;
  - it needs only the tutorial's link;
  - the program caught 2 errors no other check could (a page naming the wrong pin; status LEDs missing).
- **It works because the checks are code:** each jump in accuracy came from a law plus repair (v2, v6, the program
  check), not from a better prompt alone.

**Limitations found:**
- **Only 47 of 117 tutorials can be judged at all.** Of those, 19 have more than one right answer: CircuitQuest
  sometimes changes the tutorial's circuit (an added LED, a buzzer for a speaker), and we follow the tutorial.
- **Pages can be wrong or incomplete:** they contradict their own program, leave out a shield's connections, or have
  no program at all (5 tutorials, which now get one written for their circuit).
- **New shields** need a line added to the datasheet table.
- **Strict port names** cause extra repairs that fix names, not circuits.

---

## LEGO

**How it is judged:** against the set's official inventory (the right pieces) and its 3D model, which says which
pieces really connect (the "stud key").

| Version | The big change | Right pieces | Connections found / real | Time / cost per set |
|---|---|---:|---|---|
| v1–v2 | Claude reads the booklet pictures and writes pieces and joins (v2 adds checks and repair) | 25–27% | 0.50 / 0.57 | 221–452 s / $0.55–1.47 |
| v3 | **Parts first:** Claude gets the official inventory | **100%** | 0.58 / 0.53 | 362 s / $0.95 |
| v5 | Page by page, each piece says what it rests on | 65% | 0.61 / 0.46 | 432 s / $1.71 |
| v7 | One id per piece, positions, laws against impossible answers | 100% | 0.53 / 0.49 (2 sets) | – |
| v8 | **Claude places each piece; code finds the joins from the real shapes** | 100% | 0.46 / 0.59; **25% of pieces in the right place** | 130 min / $14 for 6 sets |
| v8 + written guides, v9 render and compare | Guides for blind builders; drawing the placements to match the picture | 100% | in place 9% → 13% with guides; v9 no better | – |
| **Path A** (current) | **No reading: the graph comes straight from the set's official 3D model, by code** | exact | **exact**: every piece in place; joins from the real shapes | seconds, free |
| **Path A + join rules** (current) | Joins the 3D library does not mark, found while building lessons: clips "with 2 Clips", arches, brackets, round tiles, stud holes, hinges, turntables, bars into holes, connectors with an axle end, separate models in one set | exact | **+20% real stud joins** on 60 sample sets, no false ones added | seconds, free |

**How good is Path A's join finding?**
- **Given true positions:** the join engine finds 99.9% of real connections with 99.98% precision.
- **Coverage:** 1,306 of 1,421 downloadable 3D models match their set and can be used.

**Chosen: Path A (the official 3D model), with the join rules.**
- **Why:**
  - every piece is in exactly the right place, and the joins come from the real shapes;
  - it is free and takes seconds;
  - it covers 1,306 sets.
- **Why not the booklet:** reading the booklet never got past about 25% of pieces in the right place, even with
  written guides, Opus, zoomed close-ups or render-and-compare. Vision models are weak at exact positions in
  drawings. That is not enough for a lesson or an AR overlay.
- **Use of the booklet now:** it is read only for what reading does well: the numbered bags.

**Limitations found:**
- **Only sets with a 3D model:** sets without one have no reliable graph yet.
- **Joins no rule can see:** a part only wedged in place, and cardboard with no holes in the 3D file. Rare.
- **Unusual parts:** some joins are found by part name (clips, hinges), so they can be missed. Building lessons over
  the full run keeps finding them; each becomes a generic rule.
- **Sub-builds only the booklet shows** (the Buggy's bumper is built in place in the 3D model).
- **The 3D models are fan-made:** 115 of 1,421 do not match the set as sold and are not used.

---

## Overall

- **Exact sources beat reading pictures:** use the 3D model for LEGO and the program for Arduino. Reading is for
  what Claude does well: tutorial text, bag numbers and plain words.
- **Code checks make Claude reliable.** Every gain came from a law plus repair.
- **One pipeline for both domains:** every fix is a generic rule.
