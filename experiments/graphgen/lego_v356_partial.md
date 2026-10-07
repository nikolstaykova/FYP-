**41 sets finished by every version**; scored on 39 (left out: 0 built from their LDraw model in v4, 2 with an empty graph). 634 checkable brick contacts.

### Parts: does it find every piece exactly?

| Measure | v3 | v5 | v6 |
|---|---:|---:|---:|
| Sets with exactly the right number of pieces | 39 / 39 (100%) | 27 / 39 (69%) | 39 / 39 (100%) |
| Pieces built ÷ pieces in the sets | 1.00 | 1.01 | 1.00 |
| Pieces right by design (recall, pooled) | 1.00 | 0.98 | 1.00 |
| Pieces that are real (precision, pooled) | 1.00 | 0.98 | 1.00 |
| Right design AND colour (recall, pooled) | 1.00 | 0.97 | 1.00 |
| Most often MISSING | Technic Brick 1 x 2 with Axle Hole Type 2 [X Opening] ×1; Technic Axle 5.5 with Stop [Rounded Short End] ×1 | Plate 1 x 1 ×14; Tile 1 x 4 with Groove ×6; Brick Special 1 x 2 with 2 Studs on 1 Side ×3; Plate 1 x 3 ×3 | none |
| Most often EXTRA | Technic Brick 1 x 2 with Axle Hole Type 1 [+ Opening] and Bottom Pin ×1; Technic Axle 5.5 with Stop [Flat Short End] ×1 | Plate Round 1 x 1 with Solid Stud ×16; Tile 1 x 3 ×5; Plate 2 x 2 ×4; Tile 1 x 2 with Groove ×3 | none |

From v3 on Claude is given the official inventory, so these rows show whether it used the list, not whether it can read pieces from pictures (v1 and v2 had to).

### Graph: does it connect the pieces exactly?

| Measure | v3 | v5 | v6 |
|---|---:|---:|---:|
| Brick contacts found (recall, pooled) | 0.68 | 0.76 | 0.72 |
| Joins that are real (precision, pooled) | 0.48 | 0.31 | 0.50 |
| Contacts found, more pieces scored (recall) | 0.65 | 0.64 | 0.69 |
| Joins real, more pieces scored (precision) | 0.40 | 0.28 | 0.41 |
| Joins written per piece | 1.20 | 1.54 | 1.23 |
| Most often MISSED contacts | Brick 1 x 2 + Plate 1 x 6 ×14; Plate 1 x 6 + Plate 1 x 6 ×12; Plate 1 x 2 + Plate 1 x 2 ×9 | Plate 1 x 2 + Plate 1 x 2 ×17; Plate 1 x 6 + Plate 1 x 6 ×12; Plate 1 x 6 + Plate 1 x 4 ×8 | Plate 1 x 6 + Plate 1 x 6 ×12; Plate 1 x 2 + Plate 1 x 2 ×7; Brick 1 x 2 + Plate 1 x 6 ×6 |
| Most often INVENTED contacts | Plate 1 x 2 + Plate 2 x 6 ×24; Plate 2 x 4 + Plate 2 x 2 ×15; Plate 1 x 1 + Plate 1 x 6 ×14 | Plate 1 x 8 + Tile 1 x 8 with Groove ×56; Plate 4 x 6 + Plate 1 x 6 ×54; Plate 4 x 8 + Plate 2 x 6 ×49 | Plate 1 x 2 + Plate 2 x 6 ×28; Plate 1 x 2 + Plate 1 x 1 ×14; Plate 2 x 4 + Plate 1 x 2 ×12 |

Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has more than one contact per piece; a join count near 1.0 per piece means the model records a chain (each piece attached to one other), not every piece it touches.
