"""Each Arduino board's geometry reference in the database, under its part: what the step check overlays a photo of
the board on to put every pin's name at its opening (validator/uno_overlay.py, PHOTO_TUNING.md section 14).

    (:Part {part_type_id})-[:HAS_GEOMETRY]->(:BoardGeometry {part_type_id, photo, kept, source, made, status,
                                                              layouts, rows, updated})
  rows      JSON: [{"layout", "from", "pins": {pin: [x, y] in the reference photo}, "fit"}] per header row
  layouts   the rows' layouts, e.g. ["uno-r3", "power-analog-8"] (validator.uno_overlay.LAYOUTS)
  photo     the reference photo's file name; kept: "repo" (code/graph/parts/arduino/refs, openly licensed) or
            "local" (data/board_refs/local_refs: licence unknown or the learner's own photo, never in git). The photo
            stays a file: the database says which one and where it came from (source, licence).
  made      "clicks" (from clicked photos), "openings" (row ends read once, the comb fits the openings),
            "layout" (no photo: the layout as numbers only)
  status    "checked" (looked at by a person), "standard" (numbers from the shield standard)
  form, rows_mils   the layout as numbers (validator/board_layout.py): the board's form ("uno") and each row's
            openings in mils from the board's edges (the shield standard), for every Uno-shaped board, photo or not.
            26 Nov: from the outline alone they land 1-2 openings off in a photo (the outline is not exact enough to
            name a pin), so the photo overlay is what places the pins; the numbers are the layout itself.

The files are the backup and what git keeps, as for the rest of the catalogue: `./pinpoint db load` puts them all in,
`save(board)` one after it is made or changed, `read()` gives them back for the overlay (None: use the files).
"""
import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
REFS = ROOT / "code" / "graph" / "parts" / "arduino" / "refs"
LOCAL_REFS = ROOT / "data" / "board_refs" / "local_refs"


def on_disk():
    """Every reference in the files: {board: (meta, kept)}; a local one replaces the repo's of the same board."""
    out = {}
    for kept, d in (("repo", REFS), ("local", LOCAL_REFS)):
        for j in sorted(d.glob("*.json")):
            try:
                out[j.stem] = (json.loads(j.read_text()), kept)
            except ValueError:
                continue
    return out


def _rows(meta):
    from validator.uno_overlay import rows_of
    return rows_of(meta)


def _layout(board):
    """The board's layout as numbers (validator/board_layout.py: the shield standard): {"form", "rows_mils"} or {}."""
    try:
        from validator import board_layout
    except Exception:
        return {}
    f = board_layout.form_of(board)
    m = board_layout.mils(board)
    if not f or not m:
        return {}
    return {"form": f[0], "rows_mils": json.dumps({r: {p: list(xy) for p, xy in pins.items()} for r, pins in m.items()})}


def layout_only():
    """The Uno-shaped boards with no reference photo: their layout as numbers only (rows from the standard)."""
    from validator import board_layout
    have = on_disk()
    return [{"key": b, "props": {"photo": "", "kept": "none", "source": "the Arduino shield standard (no photo)",
                                 "made": "layout", "status": "standard", "layouts": rows, "rows": "[]",
                                 "updated": "", "name": f"{b} geometry", **_layout(b)}}
            for b, (_, rows) in sorted(board_layout.BOARDS.items()) if b not in have]


def row(board, meta, kept):
    """One reference as a database row: {"key", "props"} (flat properties; the rows as JSON text)."""
    rows = _rows(meta)
    made = meta.get("made") or ("clicks" if any(r.get("from") == "connectors" for r in rows) else "openings")
    mtime = None
    for d in (LOCAL_REFS, REFS) if kept == "local" else (REFS,):
        if (d / f"{board}.json").exists():
            mtime = datetime.datetime.fromtimestamp((d / f"{board}.json").stat().st_mtime).strftime("%Y-%m-%d")
            break
    return {"key": board, "props": {
        "photo": meta.get("photo") or "", "kept": kept, "source": meta.get("source") or (
            "the learner's own photos (clicked)" if made == "clicks" else ""),
        "made": made, "status": meta.get("status") or ("auto" if made == "auto" else "checked"),
        "layouts": [r["layout"] for r in rows], "rows": json.dumps(rows), "updated": mtime or "",
        "name": f"{board} geometry", **_layout(board)}}


def load(d, only=None):
    """The references into the database (all, or `only` these boards). Returns (made, linked to a part)."""
    from graph.db import run
    rows = [row(b, m, k) for b, (m, k) in on_disk().items() if not only or b in only]
    rows += [r for r in layout_only() if not only or r["key"] in only]
    run(d, "CREATE CONSTRAINT boardgeometry_key IF NOT EXISTS FOR (n:BoardGeometry) REQUIRE n.part_type_id IS UNIQUE")
    run(d, "UNWIND $rows AS r MERGE (g:BoardGeometry {part_type_id: r.key}) SET g = r.props, g.part_type_id = r.key",
        rows=rows)
    linked = run(d, "UNWIND $rows AS r MATCH (p:Part {part_type_id: r.key}), (g:BoardGeometry {part_type_id: r.key}) "
                    "MERGE (p)-[:HAS_GEOMETRY]->(g) RETURN count(*) AS n", rows=rows)
    return len(rows), (linked[0]["n"] if linked else 0)


def read_db(d):
    """{board: meta} from the database, in the files' form (rows parsed)."""
    from graph.db import run
    got = run(d, "MATCH (g:BoardGeometry) RETURN g")
    out = {}
    for r in got:
        g = dict(r["g"])
        try:
            rows = json.loads(g.get("rows") or "[]")
        except ValueError:
            continue
        if g.get("kept") == "none":  # the layout as numbers only: nothing to overlay on
            continue
        out[g["part_type_id"]] = {"photo": g.get("photo"), "source": g.get("source"), "made": g.get("made"),
                                  "status": g.get("status"), "kept": g.get("kept"), "rows": rows}
    return out


def read():
    """The references from the database ({board: meta}), or None when it is not in use or cannot be reached."""
    from graph import db
    if not db.enabled():
        return None
    return db._safely("read the board geometry", read_db)


def save(board):
    """One board's reference (just made or changed in the files) into the database; None when it is not in use."""
    from graph import db
    if not db.enabled():
        return None
    return db._safely(f"save the geometry of {board}", lambda d: load(d, only={board}))


def check(d):
    """Each reference in the files against the database: [(board, what differs)]."""
    have = read_db(d)
    bad = []
    for b, (m, k) in on_disk().items():
        g = have.get(b)
        if not g:
            bad.append((b, "not in the database"))
        elif g["rows"] != _rows(m) or g["kept"] != k:
            bad.append((b, "differs"))
    return bad
