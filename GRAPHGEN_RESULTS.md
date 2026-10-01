# Graph generation: results

> Can Claude turn a real manual into one build graph that follows [GRAPH_SPEC.md](./GRAPH_SPEC.md)? How accurate, how fast, how expensive?
> Method and test sets: [RESEARCH.md](./RESEARCH.md) R21. Code: [`graphgen/`](./graphgen/). Raw results: `experiments/graphgen/`.

---

## Price and performance at a glance

**Model:** Claude Sonnet (`sonnet` → `claude-sonnet-5-5`), effort `high`, run on the Claude subscription through headless Claude Code. **Cost** is Claude Code's estimate at **API list prices**: what the same calls would cost with an API key, not what the subscription charges.

| | Electronics (Arduino + Raspberry Pi) | LEGO (official PDF manuals) |
|---|---:|---:|
| **Pilot** | 9 tutorials | 10 manuals (all < 100 pieces) |
| Mean time per manual | **38 s** (median 37, 90th pct 69) | **88 s** (median 71, 90th pct 175) |
| Mean cost per manual | **$0.089** | **$0.198** |
| Cost per 100 manuals | **≈ $9** | **≈ $20** |
| Input / output tokens (mean) | ≈ 16k / 5.6k | ≈ 24k / 12.8k |
| **Full run** | 117 tutorials: *running* | 100 manuals: *queued* |

*The full-run row is filled in when the run finishes.*

---

## Pilot: what the scores say

| | Electronics | LEGO |
|---|---|---|
| Fully correct | **4 of 7** tutorials with an answer key have every electrical connection right | — |
| Mean accuracy | net precision 0.76, recall 0.72 | piece count ≈ 99% right; correct pieces by design 53% found (49% precision); brick contacts 56% found (48% precision) |
| Repeats | 2 of 2 multi-LED tutorials used `repeats` + `attach` overrides, and both expanded to **6 correct copies** | 7 of 10 booklets used repeats (e.g. 4 wheels) |
| New part types | Raspberry Pi board, speaker created on first use | 2–31 new piece types per booklet (catalogue starts empty) |

---

## Manual sanity check (read by hand)

The automatic score depends on the answer key. Every pilot graph was also read by hand with `python -m graphgen.inspect <run>/<manual>`, to see whether the **logic** holds.

### Electronics

| Tutorial | Does the logic hold? | Finding |
|---|---|---|
| ForLoop, Arrays | ✅ Yes | 6 LED + resistor copies on pins 7…2 (one repeat, `attach` overrides per copy), all cathodes to one GND rail. 13/13 nets. |
| Blink, Fade | ✅ Yes | LED + resistor on pin 13 / 9 to GND. |
| ifStatement | ✅ Yes (answer key differs) | Claude used the **built-in** LED, as the official tutorial says; CircuitQuest's lesson adds an external one, so the score is lower than it should be. |
| ADXL3xx (earlier test) | ✅ Yes (answer key differs) | Claude followed the **official** wiring (sensor in A0–A5, code drives A4/A5 as GND/power); CircuitQuest wires it to GND/3.3V instead. |
| Pi traffic lights | ✅ Yes | LEDs on GPIO 25/8/7 through resistors, button on 21, buzzer on 15. Claude noted that the text and the diagram disagree and followed the diagram. |
| **Button, DigitalReadSerial** | ❌ **No** | The pull-down resistor went on the button's **5V leg** instead of the pin-2 leg: the pin floats and the resistor sits across 5V–GND. Both tutorials share one image; the model misread which button legs are joined. A real error, correctly scored as wrong. |
| Pi music box | ⚠️ Unclear | The catalogue had **no ports** for the male-female jumper wire, so Claude invented `pin`/`socket`; nets cannot be folded. **Our catalogue's fault**, now fixed. |

### LEGO

| Booklet | Does the logic hold? | Finding |
|---|---|---|
| 30103 Car | ✅ Mostly | Plates stacked on two base plates; one `wheel ×4` repeat attached to the wheel pins with `attach` overrides. Piece count 25 vs 28. |
| All 10 | ⚠️ | **Small booklets have no inventory page** (many are 2 pages), so there are no Element IDs; Claude names pieces by **design number** (`lego-3023` = Plate 1×2) from its own knowledge. Colours come from the pictures. |
| All 10 | ⚠️ | Without a list of allowed **port kinds**, Claude invented its own (`socket`, `wheel-pin`), causing most rule warnings (V3/V4). The allowed kinds are now in the prompt. |

### What was fixed after the pilot

| Problem found | Fix |
|---|---|
| Answer key used `cq-adxl335`, catalogue `adxl335` | Type names normalised before scoring |
| Male-female jumper wire and alligator lead had no ports | Added (`a`, `b`, conducting) |
| Potentiometer pins in a breadboard flagged incompatible | `lug ↔ breadboard-hole` allowed |
| First, incomplete draft of a new type (Raspberry Pi with 8 pins) blocked later, fuller drafts | **Unverified** entries now **merge** ports from later manuals |
| LEGO pieces named by design number scored as 0 | Scored by design number as well as Element ID |
| Model invented port kinds | Allowed port kinds and compatible pairs added to the prompt |

---

## Limits of this experiment

- **Answer-key noise (electronics):** CircuitQuest's circuits sometimes differ from the official tutorial (ifStatement, ADXL3xx, Button's extra LED). Only Button's difference is excluded automatically.
- **LEGO contacts** are checked only by design pair among plain bricks, plates and tiles; slopes, Technic, minifigures and wheels are not checked, and 4 of 10 pilot booklets had nothing checkable.
- **Strict nets:** an electrically equivalent circuit (resistor on the other side of an LED) counts as wrong.
- **Cost** is an API-price estimate; the run itself used the Claude subscription.
