**34 sets finished by every version**; scored on 32 (left out: 0 built from their LDraw model in v4, 2 with an empty graph). 603 checkable brick contacts.

### Parts: does it find every piece exactly?

| Measure | v1 | v2 | v3 | v5 |
|---|---:|---:|---:|---:|
| Sets with exactly the right number of pieces | 8 / 32 (25%) | 6 / 32 (19%) | 32 / 32 (100%) | 21 / 32 (66%) |
| Pieces built ÷ pieces in the sets | 0.98 | 0.98 | 1.00 | 1.01 |
| Pieces right by design (recall, pooled) | 0.81 | 0.80 | 1.00 | 0.98 |
| Pieces that are real (precision, pooled) | 0.83 | 0.82 | 1.00 | 0.98 |
| Right design AND colour (recall, pooled) | 0.74 | 0.74 | 1.00 | 0.97 |
| Most often MISSING | Plate 1 x 2 ×26; Tile 1 x 6 with Groove ×19; Plate Round 1 x 1 with Solid Stud ×19; Plate 1 x 3 ×18 | Plate 1 x 2 ×27; Tile 1 x 6 with Groove ×19; Plate Round 1 x 1 with Solid Stud ×17; Brick Special 1 x 1 with Handle ×16 | Technic Brick 1 x 2 with Axle Hole Type 2 [X Opening] ×1; Technic Axle 5.5 with Stop [Rounded Short End] ×1 | Plate 1 x 1 ×14; Tile 1 x 4 with Groove ×6; Brick Special 1 x 2 with 2 Studs on 1 Side ×3; Plate 1 x 3 ×3 |
| Most often EXTRA | Plate 2 x 4 ×16; Panel 1 x 2 x 1 [Square Corners] ×16; Brick Special 1 x 2 with Handle ×16; Plate 2 x 2 ×14 | Wheel 8 x 6 ×18; Plate 2 x 2 ×17; Tile 1 x 4 with Groove ×16; Panel 1 x 2 x 1 [Square Corners] ×16 | Technic Brick 1 x 2 with Axle Hole Type 1 [+ Opening] and Bottom Pin ×1; Technic Axle 5.5 with Stop [Flat Short End] ×1 | Plate Round 1 x 1 with Solid Stud ×16; Tile 1 x 3 ×5; Plate 2 x 2 ×4; Tile 1 x 2 with Groove ×3 |

From v3 on Claude is given the official inventory, so these rows show whether it used the list, not whether it can read pieces from pictures (v1 and v2 had to).

### Graph: does it connect the pieces exactly?

| Measure | v1 | v2 | v3 | v5 |
|---|---:|---:|---:|---:|
| Brick contacts found (recall, pooled) | 0.60 | 0.55 | 0.69 | 0.75 |
| Joins that are real (precision, pooled) | 0.49 | 0.54 | 0.51 | 0.31 |
| Contacts found, more pieces scored (recall) | 0.55 | 0.55 | 0.66 | 0.65 |
| Joins real, more pieces scored (precision) | 0.42 | 0.45 | 0.42 | 0.28 |
| **Stud key (v7): connections found / real, all sets** | 0.50 / 0.57 | 0.47 / 0.56 | 0.64 / 0.56 | 0.66 / 0.43 |
| **Stud key: found / real, trusted sets only** | 0.51 / 0.62 | 0.46 / 0.59 | 0.65 / 0.61 | 0.71 / 0.42 |
| Joins written per piece | 1.08 | 1.05 | 1.19 | 1.56 |
| Most often MISSED contacts | Plate 1 x 2 + Plate 1 x 2 ×21; Plate 1 x 6 + Plate 1 x 6 ×12; Brick 1 x 2 + Plate 1 x 6 ×8 | Plate 1 x 2 + Plate 1 x 2 ×17; Brick 1 x 2 + Plate 1 x 6 ×14; Plate 1 x 6 + Plate 1 x 6 ×12 | Brick 1 x 2 + Plate 1 x 6 ×14; Plate 1 x 6 + Plate 1 x 6 ×12; Plate 1 x 2 + Plate 1 x 2 ×9 | Plate 1 x 2 + Plate 1 x 2 ×17; Plate 1 x 6 + Plate 1 x 6 ×12; Plate 1 x 6 + Plate 1 x 4 ×8 |
| Most often INVENTED contacts | Plate 1 x 2 + Plate 1 x 1 ×23; Plate 2 x 2 + Plate 1 x 2 ×20; Plate 1 x 2 + Plate 2 x 6 ×16 | Plate 1 x 2 + Plate 1 x 3 ×12; Plate 1 x 2 + Plate 1 x 1 ×11; Plate 1 x 2 + Plate 2 x 6 ×9 | Plate 1 x 2 + Plate 2 x 6 ×20; Plate 1 x 1 + Plate 1 x 6 ×14; Plate 1 x 2 + Plate 1 x 1 ×13 | Plate 1 x 8 + Tile 1 x 8 with Groove ×56; Plate 4 x 6 + Plate 1 x 6 ×54; Plate 4 x 8 + Plate 2 x 6 ×49 |

Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has more than one contact per piece; a join count near 1.0 per piece means the model records a chain (each piece attached to one other), not every piece it touches. The **stud key** (v7, stud_key.py) scores every kind of piece by the library's stud, hole and pin geometry (clutch and pin joins); trusted sets are those whose model has the set's piece count and passes the physical laws.
