**87 sets finished by every version**; scored on 86 (left out: 0 built from their LDraw model in v4, 1 with an empty graph). 1645 checkable brick contacts.

### Parts: does it find every piece exactly?

| Measure | v2 | v3 |
|---|---:|---:|
| Sets with exactly the right number of pieces | 22 / 86 (26%) | 86 / 86 (100%) |
| Pieces built ÷ pieces in the sets | 0.98 | 1.00 |
| Pieces right by design (recall, pooled) | 0.84 | 1.00 |
| Pieces that are real (precision, pooled) | 0.86 | 1.00 |
| Right design AND colour (recall, pooled) | 0.81 | 1.00 |
| Most often MISSING | Plate 1 x 2 ×65; Brick Curved 4 x 1 No Studs [Stud Holder with Asymmetric Ridges] ×51; Brick Sloped 30° 1 x 1 x 2/3 (Cheese Slope) ×41; Plate Round 1 x 1 with Solid Stud ×36 | Technic Brick 1 x 2 with Axle Hole Type 2 [X Opening] ×1; Technic Axle 5.5 with Stop [Rounded Short End] ×1 |
| Most often EXTRA | Tyre 21 x 12 with Offset Tread Small Wide and Beveled Tread Edge ×30; Plate 2 x 2 ×29; Tile 1 x 8 with Groove ×25; Panel 1 x 2 x 1 [Square Corners] ×23 | Technic Brick 1 x 2 with Axle Hole Type 1 [+ Opening] and Bottom Pin ×1; Technic Axle 5.5 with Stop [Flat Short End] ×1 |

From v3 on Claude is given the official inventory, so these rows show whether it used the list, not whether it can read pieces from pictures (v1 and v2 had to).

### Graph: does it connect the pieces exactly?

| Measure | v2 | v3 |
|---|---:|---:|
| Brick contacts found (recall, pooled) | 0.53 | 0.62 |
| Joins that are real (precision, pooled) | 0.47 | 0.45 |
| Contacts found, more pieces scored (recall) | 0.49 | 0.59 |
| Joins real, more pieces scored (precision) | 0.38 | 0.37 |
| Joins written per piece | 1.05 | 1.14 |
| Most often MISSED contacts | Plate 1 x 2 + Plate 1 x 2 ×34; Plate 1 x 6 + Plate 1 x 6 ×19; Plate 2 x 4 + Plate 1 x 4 ×18 | Plate 1 x 2 + Plate 1 x 2 ×19; Plate 1 x 6 + Plate 1 x 6 ×18; Brick 1 x 2 + Plate 1 x 6 ×17 |
| Most often INVENTED contacts | Plate 1 x 2 + Plate 1 x 1 ×28; Plate 2 x 4 + Plate 1 x 2 ×22; Plate 1 x 2 + Plate 1 x 3 ×22 | Plate 2 x 4 + Plate 1 x 2 ×31; Plate 1 x 2 + Plate 2 x 6 ×30; Plate 1 x 1 + Plate 1 x 4 ×23 |

Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has more than one contact per piece; a join count near 1.0 per piece means the model records a chain (each piece attached to one other), not every piece it touches.
