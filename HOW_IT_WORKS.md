# How Pinpoint makes building lessons: in plain words

Pinpoint turns a LEGO set or an Arduino tutorial into a step-by-step lesson a beginner can follow.

```
python -m graph.lessons lego 42124-1
python -m graph.lessons arduino https://docs.arduino.cc/built-in-examples/basics/Blink/
```

**The guiding idea:** code does what must be exact, Claude does what needs judgement, and code checks Claude's work.

## The two shared pipelines

Everything runs through **two pipelines, reused for every domain**. LEGO and Arduino only plug in a *recipe*: their
own sources, prompt and rules. The stages and their order never change.

### Pipeline 1: the graph (`pipeline.run_case`)

The graph is the build's map: every part, and for each pair that meets, how they join.

1. **Parts:** collect the parts list and each part's facts (its connection points, pins, size).
2. **Build:** make the graph, by code from an exact source, or by Claude reading the instructions.
3. **Check:** code tests the graph against the domain's laws (physical or electrical).
4. **Repair:** problems go back to Claude, in the same conversation, to fix.
5. **Save:** the graph, with its time, cost and checks.

### Pipeline 2: the steps, i.e. the lesson (`lessons.make`)

1. **Source:** load the graph and what the lesson is made from.
2. **Suggest:** code makes a first plan straight from the graph.
3. **Plan:** Claude starts from the suggestion, chooses the order and grouping, and writes the instructions.
4. **Check:** code tests the plan against every rule.
5. **Repair:** the problems go back to Claude, up to 3 rounds.
6. **Finish:** last fixes by code, a final check, then saved with its stats.

Every Claude turn is timed and costed, and progress is logged as it happens.

| | Graph pipeline | Steps pipeline |
|---|---|---|
| **LEGO** | Built by code from LEGO's 3D model (exact); by Claude only when there is just the PDF booklet | Code suggests from LEGO's own steps; physical rules |
| **Arduino** | Built by Claude from the tutorial link; code checks with electrical rules and fills in what pages leave out | Code suggests each part and wire; circuit rules; the sketch is compiled at the end |

The sections below say only **how each domain differs** at each stage. Section 5 lists every place code and AI
(Claude) are used: what the code does, and for the AI, its prompt, input and output.

---

## 1. LEGO: graph

### Case A: the set has an official 3D model (1,306 sets; all lessons use this case)

- **Parts:** the set's 3D model file (LDraw) gives every piece's shape, exact place and direction.
- **Build:** **code only, no Claude.**
  - **Marked joins:** code finds the connection points LEGO's 3D library marks (studs, sockets, pin holes, pins,
    axles) and matches them: a stud in a socket, a pin along a hole.
  - **Unmarked joins, by name rules:**
    - a clip on a bar, and a bar pushed into a hole or round plate;
    - a ball in a socket, a tyre on a rim, a wheel on a car base's pin;
    - hinges, turntables, figure parts.
  - **Odd shapes, by fallbacks:** arches, brackets, plates with clips or handles, round tiles on a centre stud,
    parts with a stud hole.
  - **LEGO's structure:** code reads LEGO's own steps, its sub-builds, and which model is the main one when a set
    holds several.
- **Check / repair:** not needed, since the source is exact. Testing finds joins code still misses, and each
  becomes a new generic rule.

### Case B: no 3D model, a booklet PDF with step numbers

- **Build:**
  1. Code finds each step in the PDF, cuts out its picture, and boxes the new pieces in red by comparing it with
     the step before.
  2. **Claude places each new piece** (a few steps at a time, with the parts list and any written guide for blind
     builders found online).
  3. Code works out the joins from the real part shapes at those places.
- **Check:** no two pieces in the same space, nothing held up by nothing, one stud in one socket.
- **Repair:** as in the shared pipeline.

### Case C: no 3D model, no step numbers in the PDF

- As case B, but Claude reads the whole booklet at once.

Claude reads exact places from pictures correctly only about a quarter of the time, so lessons use case A for now.

---

## 2. LEGO: steps

- **Source:** the graph from case A, plus each piece's colour, place, what it sits on and clicks onto, and LEGO's
  official step.
- **Suggest:** code turns **LEGO's own instruction steps** into the plan:
  - steps over 8 pieces are split, in an order that can be built;
  - LEGO's sub-builds become sub-assemblies, attached where LEGO does (nested ones into their parent);
  - the biggest model is the main one, and other models (a street lamp, cones) are set beside it;
  - code also lists what the checks find wrong with this plan.
- **Plan:** Claude merges, splits or reorders steps, and follows the **physical rules**:

| Rule | Meaning |
|---|---|
| The way in | Each piece moves into place along one straight way; nothing built may be in that way; room for fingers |
| Nothing floats | A piece goes on only once what it sits on or clicks onto is there |
| Nothing under what is on top | Pieces under an overhang go on before it |
| One way at a time | A piece joining two things must reach both the same way |
| Base first | The piece others go onto first; a big part (a motor) last |
| What spans comes after | A beam over two pins goes on after both |
| Locking pieces last | A long axle through several pieces goes in after them ("hold … lined up, then push through") |
| Stop end | An axle or pin with a stop goes in free end first |
| On an axle end | Gears, wheels and bushes go on after the axle |
| One push | A sub-assembly goes on in one push; axles from the other side go in after |
| Things that move | Hinges and swivels may go on in turns; an arm on one pin can swing aside |
| See what you do | Every new piece visible; "turn the model over" |
| Beside, not on | Separate models stand beside the main one |
| Plain names | Never code names ("block 42"); say what it looks like |

- **Check:** rules S1–S13 and W1–W3.

| Rule | Checks |
|---|---|
| S1 | Every piece used once |
| S2 | Nothing floats |
| S3 | Sub-assemblies are fastened on, or stand beside the model |
| S5 | Step size |
| S6 | The way in: code slides each piece in along its way, as small cubes, and looks for anything in the way |
| S7 | LEGO's order |
| S8 | Finger room |
| S9 | LEGO's sub-builds built separately |
| S10–S13 | One part and one area per step, twins together, every new piece visible |
| W1–W3 | The words match the 3D page; no code names |

- **Finish:**
  - **Order fixes by code:** a piece on an axle end goes into the axle's step; axles that wait for a sub-assembly go
    into its attach step; a sub-build's pieces go back into the sub-build.
  - **Words against the 3D page:** what is held, when the model turns over, which piece comes first. Steps that
    differ are reworded by Claude.
  - **Extra output:** a **3D page** that plays every step. Pieces fly in along their real way, arms swing aside,
    and the camera turns with the model.

---

## 3. Arduino: graph

- **Parts:** a catalogue of known parts with their pins, voltages and which way round they go.
- **Build:** **Claude reads the tutorial** from its link (text, parts list, circuit pictures) and returns every
  part and connection: which leg in which breadboard hole, which wire to which board pin.
- **Check:** electrical laws.

| Rule | Checks |
|---|---|
| E1–E5 | Nothing shorted, legs in real holes |
| E6 | Part counts match the page |
| E7 | Pins the page names are wired |
| E8–E10 | Parts within their voltage |
| E11 | **Every pin the program reads is wired** |

- **Repair:** as in the shared pipeline. The repair message quotes the program's own lines.

**Arduino-only additions, by case:**

- **A shield stacked on the board:** code adds its connections to the board's pins underneath, from a datasheet
  table (pages never list these).
- **Finding the program ("sketch"):** Arduino's official example of the same name; the page's code (a sketch shown
  in pieces is joined); a linked sketch file; or a sketch embedded from Arduino's online editor.
- **The page and its sketch disagree** (the text says pin 6, the program reads pin 2): the graph follows the
  sketch, because the lesson must run. A pin the sketch only drives, and the circuit does not use, is just a note.
- **No sketch at all** (cloud, MATLAB and PLC tutorials): Claude writes one for the circuit, using only wired pins.
  Code checks it, and it is marked "written for this lesson".

---

## 4. Arduino: steps

- **Source:** the graph and the sketch.
- **Suggest:** every part and wire with its exact holes and pins and the connections it makes. Each part comes
  before the wires to it, and power goes last.
- **Plan:** Claude orders the steps, as the tutorial does or as is easiest. It groups up to 3 that belong together
  (a resistor and its wire). For each step it writes an instruction, a goal and two hints, and adds **optional
  extras**, shown only on request: why, how it works, a code walkthrough, things to try, troubleshooting.
- **Check:**

| Rule | Checks |
|---|---|
| W1 | Every suggested step used once |
| O1 | Nothing wired before its part is in |
| W2 | No internal names |
| W3 | Which way round, for parts with a right way |
| W4 | Columns, never rows |
| C1–C3 | The circuit is exactly the graph, parts before their wires, every pin the sketch reads is wired |

- **Finish:** the sketch is **compiled for the lesson's own board**.
  - Libraries are installed, the page's helper files are saved with the lesson, and a Wi-Fi details file is written
    as a template.
  - A real bug in the tutorial's own code (a typo) gets the smallest fix that compiles, recorded with the lesson.
    The original is kept.

---

## 5. Where code is used and where AI is used

All AI calls go to Claude (Sonnet) through one shared session class. Each call has a **prompt** (the instructions),
an **input** (the facts for this case) and a **structured output** (a fixed JSON form that code can check).

### 5.1 LEGO: graph

**Code: from the 3D model, no AI (`lego_model.py`, `assembly.py`, `lesson.placed`)**
- **Reads the 3D model file:** every piece's part number, colour, position and rotation, from the main model and
  all its sub-model files.
- **Opens each part's shape** in LEGO's 3D library and finds its connection points: studs, sockets, pin holes, pins
  and axles.
- **Joins:** a stud inside a socket is a stud join; a pin along a hole is a pin join.
- **Name rules** add the joins the library does not mark: clips and bars, balls, tyres and wheels, hinges,
  turntables, figures.
- **Fallbacks** cover odd shapes (arches, brackets, clips and handles sticking out, round tiles, stud holes).
- **Records LEGO's own structure:** the official step and sub-build of each piece, and which model is the main one.

**AI: placing pieces from a booklet PDF (only for sets with no 3D model)**

| | |
|---|---|
| **Prompt** | "You record an official LEGO set from its instruction booklet. Place every new piece (boxed in red) on its step: its type exactly as in the parts list, its colour, its place, and what it rests on." Plus rules: count against the parts list; "2x" boxes mean copies |
| **Input** | Step pictures cut from the PDF, new pieces boxed in red by code; the set's official parts list; any written guide for blind builders |
| **Output** | Pieces: id, part type, colour, place and turn, what it rests on, other joins (pins, clips) |
| **Then code** | Works out the joins from the real shapes at those places, checks them (no two pieces in one space, nothing floating) and sends problems back for repair |

**AI: reading the bags** (`bags.py`, for sets whose booklet uses numbered bags)

| | |
|---|---|
| **Prompt** | "Read the booklet for two things only: its sections and its numbered bags" |
| **Input** | The booklet PDF, shrunk to page images |
| **Output** | Each bag's number and the official steps it covers |
| **Then code** | Checks the counts and splits the lesson by bag |

### 5.2 LEGO: steps

**Code, before Claude (`lesson.suggested`, `describe`)**
- Writes each piece as a line of text: id, LEGO's step and sub-build, name, colour, position, what it sits on and
  what it clicks onto.
- Makes the **suggested plan** from LEGO's own steps (big steps split in a buildable order, sub-builds attached,
  separate models set beside the main one) and runs the checks on it.

**AI: planning and writing the lesson** (`lesson.SYSTEM`)

| | |
|---|---|
| **Prompt** | "You plan a LEGO building lesson for a beginner from a set's exact 3D model." Then: start from the suggested plan; follow LEGO's own order; every piece in exactly one step; 3–6 pieces a step; LEGO's sub-builds built separately; the **physical rules** (section 2); plain instructions without ids or code names |
| **Input** | The piece lines, the suggested plan, the problems the checks find in it, and (for sets with bags) which pieces are already built |
| **Output** | Title; steps, each with its pieces (ids), its sub-assembly name or "main", what it attaches, and the instruction text; notes |

**Code, after Claude (`lesson.check`, `fix_order`, `words_vs_3d`)**
- **Checks** every plan with S1–S13 and W1–W3.
  - **The way-in test:** each piece is turned into small cubes and slid in along its way, looking for anything
    already built in its path.
  - **Finger room:** room for a fingertip to press the piece home.
  - **The 8 views:** which corner views of the model show each new piece.
- **Repairs:** sends the problems back to Claude (the same conversation, up to 3 rounds).
- **Fixes what is left:** moves pieces between steps and keeps a move only if it leaves fewer problems.
- **Words against the 3D page:** works out what the 3D page will show for each step (held pieces, turns, which
  piece first) and marks steps whose words say otherwise.

**AI: rewording changed steps** (`lesson.REWORD`)

| | |
|---|---|
| **Prompt** | "Code moved pieces between steps; the old texts no longer match. Write a new instruction for each listed step that describes exactly its pieces, in the order the 3D page shows; never use code names" |
| **Input** | Each changed step: the step before it, its old text, its pieces now, and the 3D page's actions in order |
| **Output** | The step number and the new instruction, for each step |

### 5.3 Arduino: graph

**AI: reading the circuit from the tutorial** (`extract.ARDUINO_V6_HINT`, through `pipeline.run_case`)

| | |
|---|---|
| **Prompt** | "Record the circuit from this tutorial as a graph." Rules: use exactly the parts the tutorial says, no more and no fewer; where it offers alternatives, build what its circuit and images use; put each resistor where the image puts it; polarised parts go the right way round; power each part within its range; place parts on the breadboard the way they physically fit (a chip or button across the centre gap); follow any pin table row by row. For a part not in the catalogue, call the **lookup tool**, and only invent a new part type if that finds nothing |
| **Input** | The tutorial's link (Claude opens the page with a tool: text, parts list, circuit images); the parts catalogue (each part's pins, voltages, breadboard facts, which way round) |
| **Tools Claude can call** | `open_page` (reads the tutorial); `lookup_part` (searches our parts database and approved shop sites, returns the part's card) |
| **Output** | Parts (id, type, label, values such as a resistor's ohms), connections (which pin of which part to which hole or pin), any new part types, notes |

**Code, around the AI (`circuit_graph.py`, `circuit_lesson.py`, `browser.py`)**
- **Checks** the graph with E1–E11 and sends problems back. For E11, the repair message quotes the sketch's own lines.
- **Shields:** adds the connections of a shield stacked on the board, from the datasheet table.
- **Finds the sketch:** Arduino's official example, the page's code, a linked file, an online-editor sketch; it
  removes line numbers and joins pieces.
- **Compares the sketch with the graph:** reads which pins the sketch reads and drives. If the graph leaves a read
  pin unwired, it has the graph made again.

### 5.4 Arduino: steps

**Code, before Claude (`circuit_lesson.plan_steps`)**
- Works out every part and wire with its exact holes and pins, and the connections each makes.
- Puts them in a safe order (parts before their wires, power last). These are the suggested steps.

**AI: planning and writing the lesson** (`circuit_lesson.SYSTEM`, from CircuitQuest's writing rules)

| | |
|---|---|
| **Prompt** | "Plan and write a step-by-step Arduino lesson for a complete beginner. Code suggests the steps; never change their holes and pins. Choose the order and grouping (up to 3 suggested steps in one); a wire only once its parts are in." Writing rules: which leg goes where (long/short leg); columns, never rows; the wire's colour; never part ids. The extras are only shown on request |
| **Input** | Each suggested step (its id, part or wire, every leg or end with its hole or pin, what it connects, whether it is polarised); the sketch; the tutorial's text |
| **Output** | Title, description, what to gather; steps, each with the suggested steps it uses, a short instruction, a goal for advanced learners, 2 hints and a "why"; what to expect after uploading; extras: how it works, a code walkthrough (lines and what they do), things to try, troubleshooting |

**AI: writing a sketch when the page has none** (`circuit_lesson.WRITE_SKETCH`)

| | |
|---|---|
| **Prompt** | "The tutorial has no sketch the board can run. Write one that makes this circuit do what the tutorial is about, as a standalone program: only the wired pins, the standard Arduino core, short and commented, saying it was written for this lesson" |
| **Input** | The tutorial's link, its board, its parts, every connection, and its text |
| **Output** | The sketch, and one sentence on what it does |
| **Then code** | Checks it (setup and loop, balanced braces, only wired pins), asks for one fix if needed, then compiles it |

**Code, after Claude (`circuit_lesson.check`, `code_facts`, `compile_check.py`)**
- **Checks** W1–W4, O1 and C1–C3. For C1, it rebuilds the circuit from the steps' connections and compares it with
  the graph.
- **Compiles** the sketch for the lesson's own board with Arduino's compiler: installs libraries, saves the page's
  helper files with the lesson, and writes the Wi-Fi details template.

**AI: fixing a sketch that does not compile** (`compile_check.FIX`)

| | |
|---|---|
| **Prompt** | "Make the smallest change that fixes the compiler's errors (a typo, a missing declaration, a name the library spells differently). Never change what the sketch does or its pins" |
| **Input** | The board, the sketch and the compiler's error lines |
| **Output** | The fixed sketch and one line per change |
| **Then code** | Compiles it again and keeps it only if it compiles (up to 2 tries). The original is kept as `code_original.ino` |

## 6. What has been achieved (15 October 2026)

**Arduino:**
- **Lessons:** all 95 tutorials have a lesson that passes every check.
- **Compiling:** 90 sketches compile. The other 5 need Arduino Cloud or a library that doesn't support their board.
- **Against CircuitQuest (48 shared tutorials):** the same circuit in 27, the same sketch in 21. Most differences
  are where we follow the tutorial page and CircuitQuest changed the circuit.

**LEGO:**
- **The full run:** under way over all 1,306 sets with a 3D model; more than half are done.
- **Quality:** about 87% pass every check.
- **The new way against the old** (271 sets made both ways): lessons with no issues 60% → 92%, issues left −80%,
  cost −37%.
- **The Off-Road Buggy** (371 pieces), the main test model, passes every check, including every problem step found
  testing it by hand.

**Every rule is generic:** it came from one real mistake and now applies to every set and tutorial.

## 7. What is next

1. **Finish phase one:** the rest of the LEGO run, then fix the kinds of issues it leaves.
2. **Parts database:** what each part looks like, its legs and pins, its variants, and what counts as the same part.
3. **The checker:** when the learner says "done", compare what they built with what the step should give, and help
   them, adapting as CircuitQuest does.
4. **Later:** reading the build from a camera picture (a vision model), and AR.

More detail: [`LESSONS.md`](./LESSONS.md) (the rules and results), [`RESEARCH.md`](./RESEARCH.md) (R22–R24).
