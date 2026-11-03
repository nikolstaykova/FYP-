# research/

Evaluation material that is not part of the product: kept for the record and for RESEARCH.md, never imported by
`code/`. Moved here on 30 October 2026 when the code was cleaned after R28.

| Folder | What it is |
|---|---|
| `promptfoo/harness/` | The promptfoo eval of the 3D lesson flow: `provider.py` runs the whole 3D flow for a set (`run_one.py`, lessons written under `runs/`, never the store), `checks.py` scores it with our checker (`final_clean`, `first_shot`), `merge.py` joins evals with the same tests into one for the viewer. Runs prompt v8 on any model. |
| `promptfoo/round1/` | 29 Oct: v8 on opus, sonnet, haiku; 10 sets × 2 (before fixes 1 and 2) |
| `promptfoo/round2/` | 30 Oct: v8 against v9, three models, 10 sets × 2 |
| `promptfoo/round3/` | 30 Oct: v8 against v10, sonnet and haiku, 5 sets × 2 |
| `promptfoo/round4/` | 30 Oct: v8 against v10, opus, 5 sets × 2 |
| `promptfoo/compare_v8_v10.json` | rounds 3 and 4 as one eval (`promptfoo import` it to see all six columns) |
| `promptfoo/prompt_versions.py` | the exact text of prompts v9 and v10 and their input format (`_describe_v9`), taken out of the product when v8 was kept |
| `promptfoo_flow/` | a whole-flow eval across all three routes (booklet, 3D, Arduino) with one model for every call; set up, never run (stopped) |
| `removed_code/switches_and_prompt_versions.patch` | the code taken out of `code/` with it: `LEGO_PROMPT` (v9/v10), `PINPOINT_MODEL` (one model for every call), `LESSON_OUT` for the booklet and Arduino routes, the Arduino recipe's model. `promptfoo_flow` needs it: apply with `git apply` first |
| `repeat_20261028_failed_runs/` | the two first attempts of the repeat test that were not valid runs (usage limit; the Mac asleep) |

Each round folder holds its `promptfooconfig.yaml`, `results.json`, `eval.log` and every lesson made (`runs/`).
