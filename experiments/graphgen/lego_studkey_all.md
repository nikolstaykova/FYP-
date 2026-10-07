**100 sets finished by every version**; scored on 97 (left out: 0 built from their LDraw model in v4, 3 with an empty graph). 1944 checkable brick contacts.

### Parts: does it find every piece exactly?

| Measure | v2 | v3 | v5 |
|---|---:|---:|---:|
| Sets with exactly the right number of pieces | 26 / 97 (27%) | 97 / 97 (100%) | 63 / 97 (65%) |
| Pieces built ÷ pieces in the sets | 1.00 | 1.00 | 1.02 |
| Pieces right by design (recall, pooled) | 0.86 | 1.00 | 0.98 |
| Pieces that are real (precision, pooled) | 0.86 | 1.00 | 0.97 |
| Right design AND colour (recall, pooled) | 0.83 | 1.00 | 0.97 |
| Most often MISSING | Plate 1 x 2 ×62; Plate Special 1 x 2 with 1 Stud without Groove (Jumper) ×52; Brick Curved 4 x 1 No Studs [Stud Holder with Asymmetric Ridges] ×51; Brick Sloped 30° 1 x 1 x 2/3 (Cheese Slope) ×38 | Technic Brick 1 x 2 with Axle Hole Type 2 [X Opening] ×1; Technic Axle 5.5 with Stop [Rounded Short End] ×1 | Plate 1 x 1 ×23; Plate Round 1 x 1 with Solid Stud ×13; Tile 1 x 2 with Groove ×13; Plate 2 x 2 ×8 |
| Most often EXTRA | Plate Special 1 x 2 with 1 Stud with Groove (Jumper) ×43; Tyre 21 x 12 with Offset Tread Small Wide and Beveled Tread Edge ×42; Plate 2 x 2 ×33; Plate Round 1 x 1 with Solid Stud ×30 | Technic Brick 1 x 2 with Axle Hole Type 1 [+ Opening] and Bottom Pin ×1; Technic Axle 5.5 with Stop [Flat Short End] ×1 | Plate Round 1 x 1 with Solid Stud ×39; Plate 1 x 2 ×15; Plate 2 x 4 ×14; Tile 1 x 1 with Groove ×12 |

From v3 on Claude is given the official inventory, so these rows show whether it used the list, not whether it can read pieces from pictures (v1 and v2 had to).

### Graph: does it connect the pieces exactly?

| Measure | v2 | v3 | v5 |
|---|---:|---:|---:|
| Brick contacts found (recall, pooled) | 0.55 | 0.64 | 0.70 |
| Joins that are real (precision, pooled) | 0.49 | 0.46 | 0.36 |
| Contacts found, more pieces scored (recall) | 0.50 | 0.59 | 0.62 |
| Joins real, more pieces scored (precision) | 0.39 | 0.38 | 0.31 |
| **Stud key (v7): connections found / real, all sets** | 0.47 / 0.52 | 0.58 / 0.53 | 0.61 / 0.46 |
| **Stud key: found / real, trusted sets only** | 0.49 / 0.56 | 0.62 / 0.57 | 0.64 / 0.45 |
| Joins written per piece | 1.05 | 1.15 | 1.36 |
| Most often MISSED contacts | Plate 1 x 2 + Plate 1 x 2 ×43; Plate 3 x 3 + Plate 1 x 2 ×27; Plate 1 x 6 + Plate 1 x 6 ×19 | Plate 3 x 3 + Plate 1 x 2 ×30; Plate 1 x 2 + Plate 1 x 2 ×23; Plate 1 x 6 + Plate 1 x 6 ×18 | Plate 1 x 2 + Plate 1 x 2 ×32; Plate 1 x 1 + Plate 1 x 1 ×26; Plate 1 x 6 + Plate 1 x 6 ×18 |
| Most often INVENTED contacts | Plate 1 x 2 + Plate 1 x 1 ×34; Plate 1 x 2 + Plate 1 x 3 ×30; Plate 2 x 4 + Plate 1 x 2 ×28 | Plate 2 x 4 + Plate 1 x 2 ×42; Plate 1 x 2 + Plate 1 x 1 ×35; Plate 1 x 2 + Plate 2 x 6 ×33 | Plate 2 x 4 + Plate 1 x 2 ×58; Plate 1 x 8 + Tile 1 x 8 with Groove ×57; Plate 1 x 6 + Plate 2 x 6 ×55 |

Contacts are checked among plain bricks, plates and tiles, matched by design pair; the *more pieces* rows also score slopes and round/special/modified bricks, plates and tiles (about twice the contacts). A real build has more than one contact per piece; a join count near 1.0 per piece means the model records a chain (each piece attached to one other), not every piece it touches. The **stud key** (v7, stud_key.py) scores every kind of piece by the library's stud, hole and pin geometry (clutch and pin joins); trusted sets are those whose model has the set's piece count and passes the physical laws.
