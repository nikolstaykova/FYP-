**72 sets finished by every version**; scored on 69 (left out: 0 built from their LDraw model in v4, 3 with an empty graph). 1235 checkable brick contacts.

### Parts: does it find every piece exactly?

| Measure | v3 | v5 | v6 |
|---|---:|---:|---:|
| Sets with exactly the right number of pieces | 69 / 69 (100%) | 48 / 69 (70%) | 69 / 69 (100%) |
| Pieces built ÷ pieces in the sets | 1.00 | 1.02 | 1.00 |
| Pieces right by design (recall, pooled) | 1.00 | 0.98 | 1.00 |
| Pieces that are real (precision, pooled) | 1.00 | 0.97 | 1.00 |
| Right design AND colour (recall, pooled) | 1.00 | 0.97 | 1.00 |
| Most often MISSING | Technic Brick 1 x 2 with Axle Hole Type 2 [X Opening] ×1; Technic Axle 5.5 with Stop [Rounded Short End] ×1 | Plate 1 x 1 ×17; Plate Round 1 x 1 with Solid Stud ×11; Tile 1 x 4 with Groove ×7; Tile 1 x 2 with Groove ×5 | none |
| Most often EXTRA | Technic Brick 1 x 2 with Axle Hole Type 1 [+ Opening] and Bottom Pin ×1; Technic Axle 5.5 with Stop [Flat Short End] ×1 | Plate Round 1 x 1 with Solid Stud ×32; Plate 2 x 4 ×10; Hinge Plate 1 x 2 Locking with 1 Finger On End, with Groove ×8; Plate Special 1 x 2 with 1 Stud with Groove and Inside Stud Holder (Jumper) ×7 | none |

From v3 on Claude is given the official inventory, so these rows show whether it used the list, not whether it can read pieces from pictures (v1 and v2 had to).

### Graph: does it connect the pieces exactly?

| Measure | v3 | v5 | v6 |
|---|---:|---:|---:|
| Brick contacts found (recall, pooled) | 0.64 | 0.69 | 0.69 |
| Joins that are real (precision, pooled) | 0.48 | 0.33 | 0.49 |
| Contacts found, more pieces scored (recall) | 0.60 | 0.61 | 0.66 |
| Joins real, more pieces scored (precision) | 0.39 | 0.30 | 0.40 |
| Joins written per piece | 1.16 | 1.41 | 1.22 |
| Most often MISSED contacts | Brick 1 x 2 + Plate 1 x 6 ×17; Plate 1 x 6 + Plate 1 x 6 ×15; Plate 1 x 2 + Plate 1 x 4 ×12 | Plate 1 x 2 + Plate 1 x 2 ×23; Plate 1 x 6 + Plate 1 x 6 ×15; Plate 1 x 1 + Plate 1 x 1 ×13 | Plate 1 x 6 + Plate 1 x 6 ×15; Plate 1 x 2 + Plate 1 x 2 ×11; Plate 2 x 4 + Plate 1 x 2 ×9 |
| Most often INVENTED contacts | Plate 1 x 2 + Plate 2 x 6 ×30; Plate 2 x 4 + Plate 1 x 2 ×28; Plate 2 x 4 + Plate 2 x 6 ×19 | Plate 1 x 8 + Tile 1 x 8 with Groove ×57; Plate 4 x 6 + Plate 1 x 6 ×54; Plate 4 x 8 + Plate 2 x 6 ×49 | Plate 1 x 2 + Plate 2 x 6 ×34; Plate 2 x 4 + Plate 1 x 2 ×30; Plate 1 x 2 + Plate 1 x 1 ×21 |

Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has more than one contact per piece; a join count near 1.0 per piece means the model records a chain (each piece attached to one other), not every piece it touches.
