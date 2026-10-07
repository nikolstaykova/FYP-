"""The one pipeline (v4), the same code for every domain; domains.py says what differs (RESEARCH.md R22).

  1. parts      the manual's parts list from the recipe's source (LEGO: Rebrickable, booklet fallback), every
                part carded through the ingestion pipeline (parts/ingest.py)                     [Layer 0]
  2. build      the recipe's builders in order: "ldraw" (a 3D model file, by code), "pages" (the booklet a page
                at a time), "one-shot" (the whole manual in one turn)                            [Layers 1-2]
  3. check      logical view + the domain's laws and the spec rules                              [Layers 3, 5]
  4. repair     issues allowed by the recipe's policy go back to the builder, up to N rounds
  5. upkeep     part types the model had to draft are carded through the registry for later manuals
Every stage is a timed, costed phase. Builders share one interface: start(), repair(message), close().
"""
import base64
import collections
import json
import subprocess
import time

from . import catalogue as cat
from . import checks, expand
from .domains import REAL_RULES, VERSIONS

ROOT = cat.pathlib.Path(__file__).resolve().parents[1]


# --- Builders --------------------------------------------------------------------------------
class OneShot:
    """The whole manual in one turn; a repair turn returns the complete corrected graph."""
    name, repairable = "one-shot", True

    def __init__(self, Session, manual, images, catalogue_text, hint, cfg, parts_tool_store=None):
        kw = {"timeout": 600} if cfg.route == "subscription" else {}
        if parts_tool_store and cfg.route == "subscription":
            kw["parts_tool_store"] = parts_tool_store
        if getattr(cfg, "manual_url", False) and cfg.route == "subscription":
            kw["web_domain"] = "docs.arduino.cc"
        self.session = Session(manual, catalogue_text, hint, images=images, model=cfg.model, effort=cfg.effort, **kw)

    def start(self):
        return self.session.first()

    def repair(self, message):
        return self.session.repair(message)

    def close(self):
        self.session.close()


PARTS_TURN = ("STEP 1 OF 2, PARTS ONLY. List every physical part the tutorial uses, wires and breadboard included, "
              "as the `parts` of the graph: one node per physical part, its type from the catalogue, its value or "
              "colour in props. For any part the catalogue does not list, call lookup_part first and use the type it "
              "returns. Leave `edges` and `repeats` empty in this step; the connections come in step 2.")
BUILD_TURN = ("STEP 2 OF 2, CONNECTIONS. Now return the COMPLETE graph: the same parts as in step 1 (add or drop one "
              "only if step 1 was wrong, and say why in notes) and every connection the tutorial requires.")


class PartsThenBuild(OneShot):
    """Parts first, in the same conversation: turn 1 lists the parts (Layer 1, with lookup_part for parts the
    catalogue lacks), turn 2 adds the connections (Layer 2). The tutorial is read once; turn 2 reuses it."""
    name = "parts-then-build"

    def __init__(self, Session, manual, images, catalogue_text, hint, cfg, parts_tool_store=None):
        super().__init__(Session, manual + "\n\n" + PARTS_TURN, images, catalogue_text, hint, cfg, parts_tool_store)
        self.parts_graph, self.parts_stats = None, None

    def start(self):
        self.parts_graph, self.parts_stats = self.session.first()
        return self.session.send([{"type": "text", "text": BUILD_TURN}])


class LDrawBuild:
    """Path A: the build graph from the set's LDraw model, by code. Exact, so nothing to repair."""
    name, repairable = "ldraw", False

    def __init__(self, mpd_text, title, source_id, studs=False):
        self.args, self.steps, self.studs = (mpd_text, title, source_id), {}, studs
        self.name = "ldraw-studs" if studs else "ldraw"

    def start(self):
        from . import ldraw_graph
        graph, stats, self.steps = ldraw_graph.build(*self.args, studs=self.studs)
        return graph, stats

    def close(self):
        pass


class PageBuild:
    """Path B: the booklet as page images, `per_turn` pages a turn, in one conversation (earlier pieces stay in
    context). Each turn returns only what its pages add; the graph is the union. Repairs return additions too."""
    name, repairable = "pages", True

    def __init__(self, Session, pdf, intro, catalogue_text, hint, cfg, per_turn=1, timeout=600):
        self.pages = render_pages(pdf)
        self.batches = [self.pages[i:i + per_turn] for i in range(0, len(self.pages), per_turn)]
        self.graph = {"title": "", "source_id": "", "new_part_types": [], "parts": [], "edges": [], "repeats": [], "notes": []}
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        first = [(b, "image/png") for _, b in self.batches[0]] if self.batches else []
        self.session = Session(intro, catalogue_text, hint, images=first, model=cfg.model, effort=cfg.effort, **kw)
        self.turns = []

    def _merge(self, delta):
        ids = {p["id"] for p in self.graph["parts"]} | {r["group"] for r in self.graph["repeats"]}
        self.graph["parts"] += [p for p in delta["parts"] if p["id"] not in ids]  # an id is never redefined
        seen = {(e["type"], *sorted((e["u"], e["v"]))) for e in self.graph["edges"]}
        self.graph["edges"] += [e for e in delta["edges"] if (e["type"], *sorted((e["u"], e["v"]))) not in seen]
        self.graph["repeats"] += [r for r in delta["repeats"] if r["group"] not in ids]
        self.graph["notes"] += delta["notes"]
        self.graph["title"] = self.graph["title"] or delta["title"]
        self.graph["source_id"] = self.graph["source_id"] or delta["source_id"]

    def start(self):
        total, last = collections.Counter(), {}
        for i, batch in enumerate(self.batches):
            label = f"page {batch[0][0]}" + (f"-{batch[-1][0]}" if len(batch) > 1 else "") + f" of {self.pages[-1][0]}"
            if i == 0:
                delta, last = self.session.first()
            else:
                images = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                       "data": base64.standard_b64encode(b).decode()}} for _, b in batch]
                delta, last = self.session.send(images + [{"type": "text", "text": self.turn_text(label)}])
            self._merge(delta)
            self.turns.append({"pages": label, "seconds": last["seconds"], "cost_usd": last["cost_usd"],
                               "new_parts": len(delta["parts"]), "new_edges": len(delta["edges"])})
            for k in ("seconds", "input_tokens", "output_tokens", "cost_usd"):
                total[k] += last[k]
        return json.loads(json.dumps(self.graph)), {**last, **{k: round(v, 4) for k, v in total.items()}, "turns": len(self.turns)}

    def turn_text(self, label):
        return f"Next: {label}. Return only what it adds."

    def repair(self, message):
        delta, st = self.session.send([{"type": "text", "text": message + "\n\nReturn ONLY additions (new pieces, new "
                                                                          "edges); everything already given stays."}])
        self._merge(delta)
        return json.loads(json.dumps(self.graph)), st

    def close(self):
        self.session.close()


class PieceBuild(PageBuild):
    """v5 Path B: page by page like PageBuild, but each piece names every piece it rests on (`rests_on`), and
    code turns that into joins."""

    def __init__(self, Session, pdf, intro, catalogue_text, hint, cfg, per_turn=1, timeout=600, parts=None):
        from .model import LegoPiecesDelta
        self.parts = parts or []  # the official parts list: what is left to place is fed with every page
        self.pages = render_pages(pdf)
        self.batches = [self.pages[i:i + per_turn] for i in range(0, len(self.pages), per_turn)]
        self.pieces, self.others, self.notes, self.title = {}, [], [], ""
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        first = [(b, "image/png") for _, b in self.batches[0]] if self.batches else []
        self.session = Session(intro, catalogue_text, hint, images=first, model=cfg.model, effort=cfg.effort,
                               schema=LegoPiecesDelta, **kw)
        self.turns = []

    def _merge(self, delta):
        for p in delta["pieces"]:
            have = self.pieces.get(p["id"])
            if have:  # named again (a repair adding supports): keep the type, add the supports
                have["rests_on"] = list(dict.fromkeys(have["rests_on"] + p["rests_on"]))
            else:
                self.pieces[p["id"]] = dict(p)
        self.others += delta["other_joins"]
        self.notes += delta["notes"]
        self.title = self.title or delta["title"]
        delta["parts"], delta["edges"] = delta["pieces"], delta["other_joins"]  # for the per-turn counts
        self.graph = self.to_graph()

    def turn_text(self, label):
        """The next page, plus the pieces of the parts list not placed yet: Claude picks from what is left, so a
        Plate 1x2 is not taken for a Plate 1x3 that is already used up."""
        placed = collections.Counter(p["type"] for p in self.pieces.values())
        left = []
        for p in self.parts:
            t = f"lego-{p['part_num']}"
            n = p["quantity"] - placed[t]
            placed[t] = max(0, placed[t] - p["quantity"])
            if n > 0:
                left.append(f"{n}x {t} | {p['name']} | {p['color']}")
        rest = (f"\nPieces of the parts list NOT placed yet ({len(left)} lines):\n" + "\n".join(left[:80])
                + ("\n..." if len(left) > 80 else "")) if left else "\nEvery piece of the parts list is placed."
        return f"Next: {label}. Return only what it adds.{rest}"

    def to_graph(self):
        parts = [{"id": p["id"], "type": p["type"], "label": None, "props": [{"key": "colour", "value": p["colour"]}]}
                 for p in self.pieces.values()]
        edges, seen = [], set()
        for p in self.pieces.values():
            for below in p["rests_on"]:
                key = ("joined", *sorted((p["id"], below)))
                if below in self.pieces and below != p["id"] and key not in seen:
                    seen.add(key)
                    edges.append({"type": "joined", "u": p["id"], "u_port": None, "v": below, "v_port": None,
                                  "method": "stack", "freedom": "rigid", "reversible": "hand"})
        for j in self.others:
            key = ("joined", *sorted((j["u"], j["v"])))
            if key not in seen and j["u"] in self.pieces and j["v"] in self.pieces:
                seen.add(key)
                edges.append({"type": "joined", "u": j["u"], "u_port": None, "v": j["v"], "v_port": None,
                              "method": j["method"], "freedom": j["freedom"], "reversible": "hand"})
        return {"title": self.title, "source_id": "", "new_part_types": [], "parts": parts, "edges": edges,
                "repeats": [], "notes": self.notes}


class WholePieces(PieceBuild):
    """v6 Path B: the whole booklet in one turn (as v3, which kept every piece exact), answered in the rests_on
    format (as v5): every piece names all the pieces it sits on, and code makes the joins. A repair returns the
    complete corrected list, so an extra piece can be removed (a page-by-page repair could only add)."""
    name, repairable = "whole-pieces", True

    def __init__(self, Session, pdf, intro, catalogue_text, hint, cfg, parts=None, timeout=1800):
        from .model import LegoPiecesDelta
        self.parts = parts or []
        self.pieces, self.others, self.notes, self.title, self.turns = {}, [], [], "", []
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        self.session = Session(intro, catalogue_text, hint, pdf=pdf, model=cfg.model, effort=cfg.effort,
                               schema=LegoPiecesDelta, **kw)

    def _replace(self, answer):
        """The answer is the whole set: it replaces what was there."""
        self.pieces, self.others, self.notes = {}, [], []
        self._merge(answer)

    def start(self):
        answer, st = self.session.first()
        self._replace(answer)
        return json.loads(json.dumps(self.graph)), st

    def repair(self, message):
        answer, st = self.session.repair(message + "\n\nReturn the COMPLETE corrected list of pieces (every piece, "
                                                   "with all of its rests_on), not only the changes.")
        self._replace(answer)
        return json.loads(json.dumps(self.graph)), st


class WholePiecesV7(WholePieces):
    """v7 Path B: as v6 (whole booklet, one turn), but every copy of a piece has its own id from the parts list
    (p1..pN fixes its type and colour, so identical pieces cannot be confused or invented), and each piece gives
    its step and its position on the stud grid as well as `rests_on`. Laws L6-L10 (checks.lego_pieces) check the
    answer; code also computes the joins from the positions alone (`position_graph`, scored separately)."""
    name = "whole-pieces-v7"

    def __init__(self, Session, pdf, intro, catalogue_text, hint, cfg, parts=None, timeout=1800):
        from .model import LegoPiecesV7
        self.parts = parts or []
        self.info, n = {}, 0
        for p in self.parts:
            for _ in range(p["quantity"]):
                n += 1
                self.info[f"p{n}"] = {"type": f"lego-{p['part_num']}", "name": p["name"], "colour": p["color"],
                                      "shape": checks.piece_shape(p["name"])}
        listing = "\n".join(f"{i} | {v['type']} | {v['name']} | {v['colour']}" for i, v in self.info.items())
        intro += f"\n\nPIECE LIST ({len(self.info)} pieces; one id per physical piece):\n{listing}"
        self.pieces, self.others, self.notes, self.title, self.turns, self.duplicates = {}, [], [], "", [], []
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        self.session = Session(intro, catalogue_text, hint, pdf=pdf, model=cfg.model, effort=cfg.effort,
                               schema=LegoPiecesV7, **kw)

    def _merge(self, answer):
        self.duplicates = []
        for p in answer["pieces"]:
            if p["id"] in self.pieces:
                self.duplicates.append(p["id"])
                continue
            known = self.info.get(p["id"], {})
            self.pieces[p["id"]] = {"id": p["id"], "type": known.get("type", "lego-unknown"),
                                    "colour": known.get("colour", ""), "step": p["step"],
                                    "rests_on": list(dict.fromkeys(p["rests_on"])), "position": p["position"]}
        self.others += answer["other_joins"]
        self.notes += answer["notes"]
        self.title = self.title or answer["title"]
        self.graph = self.to_graph()

    def laws(self):
        return checks.lego_pieces(self.pieces, self.info, self.duplicates)

    def position_graph(self):
        """The same pieces, joined by what their positions say (code), plus rests_on for pieces with no usable
        position (not on the grid, or not a plain block) and the other joins."""
        computed = checks.position_joins(self.pieces, self.info)
        gridded = {u for u, p in self.pieces.items() if p.get("position") and (self.info.get(u) or {}).get("shape")}
        pairs = {tuple(sorted(x)) for x in computed}
        for u, p in self.pieces.items():
            for v in p["rests_on"]:
                if v in self.pieces and v != u and not (u in gridded and v in gridded):
                    pairs.add(tuple(sorted((u, v))))
        g = json.loads(json.dumps(self.graph))
        g["edges"] = [{"type": "joined", "u": a, "u_port": None, "v": b, "v_port": None, "method": "stack",
                       "freedom": "rigid", "reversible": "hand"} for a, b in sorted(pairs)]
        seen = set(pairs)
        for j in self.others:
            k = tuple(sorted((j["u"], j["v"])))
            if k not in seen and j["u"] in self.pieces and j["v"] in self.pieces:
                seen.add(k)
                g["edges"].append({"type": "joined", "u": j["u"], "u_port": None, "v": j["v"], "v_port": None,
                                   "method": j["method"], "freedom": j["freedom"], "reversible": "hand"})
        return g


class WholePiecesV8(WholePiecesV7):
    """v8 Path B: as v7, but each piece gets a full placement (column, row in half studs, layer in plates,
    turn/tilt/roll in degrees, free_angle) and the PIECE LIST gives each piece's size at turn 0. Code places every
    piece's LDraw part there and finds the joins with the answer key's stud and pin matching (placement.py): that is
    the graph. rests_on is kept for pieces code cannot place and as a cross-check (L13); the rests_on-only graph is
    saved too (graph_rests), so both can be scored."""
    name = "whole-pieces-v8"

    def __init__(self, Session, pdf, intro, catalogue_text, hint, cfg, parts=None, timeout=1800):
        from . import placement
        from .model import LegoPiecesV8
        self.parts = parts or []
        self.info = placement.piece_list(self.parts)
        fmt = lambda s: f"{s[0]:g} x {s[1]:g} studs x {s[2]:g} plates" if s else "size unknown"
        listing = "\n".join(f"{i} | {v['type']} | {v['name']} | {v['colour']} | SIZE {fmt(v['size'])}"
                            for i, v in self.info.items())
        intro += f"\n\nPIECE LIST ({len(self.info)} pieces; one id per physical piece):\n{listing}"
        self.pieces, self.others, self.notes, self.title, self.turns, self.duplicates = {}, [], [], "", [], []
        self.found, self.placed = {}, []
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        self.session = Session(intro, catalogue_text, hint, pdf=pdf, model=cfg.model, effort=cfg.effort,
                               schema=LegoPiecesV8, **kw)

    def _merge(self, answer):
        from . import placement
        self.duplicates = []
        for p in answer["pieces"]:
            if p["id"] in self.pieces:
                self.duplicates.append(p["id"])
                continue
            known = self.info.get(p["id"], {})
            self.pieces[p["id"]] = {"id": p["id"], "type": known.get("type", "lego-unknown"),
                                    "colour": known.get("colour", ""), "step": p["step"],
                                    "rests_on": list(dict.fromkeys(p["rests_on"])), "position": None,
                                    "placement": p["placement"], "page": p.get("page")}
        self.others += answer["other_joins"]
        self.notes += answer["notes"]
        self.title = self.title or answer["title"]
        self.found, self.placed = placement.joins(
            {i: (self.info[i]["ldraw"], placement.snapped(p["placement"])) for i, p in self.pieces.items()
             if (self.info.get(i) or {}).get("ldraw")},
            {i: set(p["rests_on"]) for i, p in self.pieces.items()}, {i: p["step"] for i, p in self.pieces.items()})
        self.graph = self.to_graph()

    def _edges(self, pairs):
        return [{"type": "joined", "u": a, "u_port": None, "v": b, "v_port": None, "method": "stack",
                 "freedom": "rigid", "reversible": "hand"} for a, b in sorted(pairs)]

    def _others(self, edges, seen):
        for j in self.others:
            k = tuple(sorted((j["u"], j["v"])))
            if k not in seen and j["u"] in self.pieces and j["v"] in self.pieces:
                seen.add(k)
                edges.append({"type": "joined", "u": j["u"], "u_port": None, "v": j["v"], "v_port": None,
                              "method": j["method"], "freedom": j["freedom"], "reversible": "hand"})
        return edges

    def to_graph(self):
        """Joins from the placements; rests_on and other_joins only for pieces code could not place."""
        parts = [{"id": p["id"], "type": p["type"], "label": None, "props": [{"key": "colour", "value": p["colour"]}]}
                 for p in self.pieces.values()]
        placed = {nid for nid, *_ in self.placed}
        pairs = {tuple(sorted(k)) for k in self.found}
        for u, p in self.pieces.items():
            for v in p["rests_on"]:
                if v in self.pieces and v != u and not (u in placed and v in placed):
                    pairs.add(tuple(sorted((u, v))))
        edges, seen = self._edges(pairs), set(pairs)
        for j in self.others:  # a join Claude names between placed pieces is already decided by their shapes
            if j["u"] in placed and j["v"] in placed:
                seen.add(tuple(sorted((j["u"], j["v"]))))
        return {"title": self.title, "source_id": "", "new_part_types": [], "parts": parts,
                "edges": self._others(edges, seen), "repeats": [], "notes": self.notes}

    def rests_graph(self):
        """The same pieces joined by rests_on and other_joins alone (Claude's own statement, as v7 scored it)."""
        pairs = {tuple(sorted((u, v))) for u, p in self.pieces.items() for v in p["rests_on"] if v in self.pieces and v != u}
        g = json.loads(json.dumps(self.graph))
        g["edges"] = self._others(self._edges(pairs), set(pairs))
        return g

    def laws(self):
        from . import placement
        names = {i: v["name"] for i, v in self.info.items()}
        return checks.lego_pieces(self.pieces, self.info, self.duplicates) + placement.laws(
            self.placed, self.found, {i: p["rests_on"] for i, p in self.pieces.items()}, names)


class StepPiecesV8(WholePiecesV8):
    """v8 Path B, step by step: for a booklet with step numbers as text, each step's picture with what it adds boxed
    in red (step_diff.py: the picture compared with the previous step's), `per_turn` steps a turn in one
    conversation. Each turn returns only the pieces its steps add, in the grid of the pieces already placed (listed
    with their placements); a repair returns only the pieces to correct. Joins, laws and graphs as WholePiecesV8."""
    name = "step-pieces-v8"

    def __init__(self, Session, images, intro, catalogue_text, hint, cfg, parts=None, per_turn=4, timeout=900):
        from . import placement
        from .model import LegoPiecesV8
        self.parts = parts or []
        self.info = placement.piece_list(self.parts)
        listing = "\n".join(f"{i} | {v['type']} | {v['name']} | {v['colour']} | SIZE "
                            + (f"{v['size'][0]:g} x {v['size'][1]:g} studs x {v['size'][2]:g} plates" if v["size"] else "size unknown")
                            for i, v in self.info.items())
        self.batches = [images[i:i + per_turn] for i in range(0, len(images), per_turn)]
        self.last_step = images[-1]["step"] if images else 0
        self.pieces, self.others, self.notes, self.title, self.turns, self.duplicates = {}, [], [], "", [], []
        intro += f"\n\nPIECE LIST ({len(self.info)} pieces; one id per physical piece):\n{listing}\n\n" + self.turn_text(0)
        self.found, self.placed = {}, []
        kw = {"timeout": timeout} if cfg.route == "subscription" else {}
        first = [(i["png"], "image/png") for i in self.batches[0]] if self.batches else []
        self.session = Session(intro, catalogue_text, hint, images=first, model=cfg.model, effort=cfg.effort,
                               schema=LegoPiecesV8, **kw)

    def turn_text(self, n):
        batch = self.batches[n]
        steps = f"{batch[0]['step']}-{batch[-1]['step']}" if len(batch) > 1 else f"{batch[0]['step']}"
        boxed = ", ".join(f"step {i['step']}: " + ("first step" if i["step"] == 1 else f"{len(i['boxes'])} red box(es)"
                                                    if i["boxes"] else "no boxes (the view changed)") for i in batch)
        placed = "\n".join(f"{i} {p['type'][5:]} step {p['step']} col {p['placement']['column']:g} row "
                           f"{p['placement']['row']:g} layer {p['placement']['layer']:g} turn {p['placement']['turn']:g}"
                           + (f" tilt {p['placement']['tilt']:g}" if p["placement"]["tilt"] else "")
                           + (f" roll {p['placement']['roll']:g}" if p["placement"]["roll"] else "")
                           for i, p in self.pieces.items())
        left = [i for i in self.info if i not in self.pieces]
        return (f"STEPS {steps} of {self.last_step} (pictures attached, in order; {boxed}). Return only the pieces "
                f"these steps add.\nPieces placed so far ({len(self.pieces)}):\n{placed or '(none)'}\n"
                f"Ids not placed yet ({len(left)}): {', '.join(left)}")

    def _add(self, answer):
        """Add (or, for an id given again, correct) pieces; then joins and graph for everything placed so far."""
        from . import placement
        for p in answer["pieces"]:
            known = self.info.get(p["id"], {})
            self.pieces[p["id"]] = {"id": p["id"], "type": known.get("type", "lego-unknown"), "colour": known.get("colour", ""),
                                    "step": p["step"], "rests_on": list(dict.fromkeys(p["rests_on"])), "position": None,
                                    "placement": p["placement"], "page": p.get("page")}
        self.others += answer["other_joins"]
        self.notes += answer["notes"]
        self.title = self.title or answer["title"]
        self.duplicates = []
        self.found, self.placed = placement.joins(
            {i: (self.info[i]["ldraw"], placement.snapped(p["placement"])) for i, p in self.pieces.items()
             if (self.info.get(i) or {}).get("ldraw")},
            {i: set(p["rests_on"]) for i, p in self.pieces.items()}, {i: p["step"] for i, p in self.pieces.items()})
        self.graph = self.to_graph()

    def start(self):
        total = collections.Counter()
        for n, batch in enumerate(self.batches):
            if n == 0:
                answer, st = self.session.first()
            else:
                images = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                       "data": base64.standard_b64encode(i["png"]).decode()}} for i in batch]
                answer, st = self.session.send(images + [{"type": "text", "text": self.turn_text(n)}])
            self._add(answer)
            self.turns.append({"steps": [i["step"] for i in batch], "seconds": st["seconds"], "cost_usd": st["cost_usd"],
                               "new_pieces": len(answer["pieces"])})
            for k in ("seconds", "input_tokens", "output_tokens", "cost_usd"):
                total[k] += st[k]
        return json.loads(json.dumps(self.graph)), {**st, **{k: round(v, 4) for k, v in total.items()}, "turns": len(self.turns)}

    def repair(self, message):
        answer, st = self.session.repair(message + "\n\nReturn ONLY the pieces to add or correct (an id given again "
                                                   "replaces its step, rests_on and placement); every other piece stays.")
        self._add(answer)
        return json.loads(json.dumps(self.graph)), st


def render_pages(pdf_bytes, dpi=110, max_side=1568):
    """[(page number, png)] for pages that can hold building steps: not the cover, not a parts page."""
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = []
    for i, page in enumerate(doc):
        if (i == 0 and len(doc) > 2) or checks.booklet_inventory_page(page):
            continue
        zoom = min(dpi / 72, max_side / max(page.rect.width, page.rect.height))
        out.append((i + 1, page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")))
    return out


def tutorial_parts(manual, store, recipe):
    """Electronics parts first: the hardware list by code, matched to the store; unmatched parts through the
    ingestion pipeline (shops). Returns the cards to add, a parts note for the builder, and the timed phase."""
    from .parts import ingest, tutorial
    t0, cost, rows, cards = time.monotonic(), {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}, [], {}
    looked = {}  # a part listed twice is looked up once
    for item in tutorial.hardware_list(manual):
        card_id, name = tutorial.match(item, store)
        row = {"item": item, "card": None if card_id == "skip" else card_id, "skipped": card_id == "skip"}
        if card_id is None and name and name.lower() in looked:
            row["card"] = looked[name.lower()]
        elif card_id is None and name:
            card, st, trail = ingest.ingest_part(name, recipe.part_cards, store, label=name, max_llm_calls=3)
            looked[name.lower()] = card and card["type"]
            for k in cost:
                cost[k] += st.get(k, 0)
            row.update(card=card and card["type"], looked_up=True, trail=trail, seconds=st["seconds"])
            if card:
                cards[card["type"]] = card
        rows.append(row)
    listing = "\n".join(f"- {r['item']} -> {r['card']}" for r in rows if not r["skipped"])
    counts = [(r["card"], q, checks.ohms(v.group(0)) if (v := tutorial.VALUE.search(r["item"])) and "resistor" in r["card"] else None)
              for r in rows if r["card"] and not r["skipped"] and (q := tutorial.quantity(r["item"]))]
    return {"cards": cards, "counts": counts,
            "manual_extra": ("\n\nPARTS (the tutorial's list, matched to the catalogue before this build; "
                             "'None' = not in the catalogue):\n" + listing) if listing else "",
            "phase": {"phase": "parts", "seconds": round(time.monotonic() - t0, 1), "check_seconds": 0.0,
                      **{k: round(v, 4) for k, v in cost.items()}, "listed": len(rows),
                      "matched": sum(1 for r in rows if r["card"] and not r.get("looked_up")),
                      "looked_up": sum(1 for r in rows if r.get("looked_up")),
                      "found": sum(1 for r in rows if r.get("looked_up") and r["card"]), "items": rows}}


def tutorial_items(manual, store):
    """Every parts-list item matched to a card, by code: [(card type, count)], an item with no count being 1.
    For the too-many-parts law only."""
    from .parts import tutorial
    import re
    out = []
    for item in tutorial.hardware_list(manual):
        for alt in re.split(r"\s+or\s+", item):  # "LED bar graph display or 10 LEDs": either one is allowed
            card, name = tutorial.match(alt, store)
            if card and card != "skip":
                q = tutorial.quantity(alt)
                plural = bool(re.search(r"s\b", name.split()[-1])) if name else False
                out.append((card, q if q else (None if plural else 1)))  # "Resistors": some, no upper limit
    return out


def tutorial_counts(manual, store):
    """Counts the tutorial's parts list states, by code, for the parts-count law only (no part is chosen or looked
    up from it): [(card type, count, resistor value or None)]."""
    from .parts import tutorial
    out = []
    for item in tutorial.hardware_list(manual):
        card, name = tutorial.match(item, store)
        q = tutorial.quantity(item)
        if card and card != "skip" and q:
            v = tutorial.VALUE.search(item)
            out.append((card, q, checks.ohms(v.group(0)) if v and "resistor" in card else None))
    return out


def upkeep(graph, recipe, cfg, out):
    """Card every part type the model had to add, through the registry's sites; stored for later manuals.
    Returns (report, {type: engine card} for the cards found)."""
    from . import v3
    from .parts import ingest
    store = v3.store("electronics", out, cfg.cards or (ROOT / recipe.card_store if recipe.card_store else None))
    store.refresh()  # cards the builder's lookup_part already stored
    t0, rows, cards, cost = time.monotonic(), [], {}, 0.0
    for d in graph["new_part_types"]:
        card, st, trail = ingest.ingest_part(d["name"], recipe.part_cards, store, wanted_id=d["type"], label=d["name"],
                                             max_llm_calls=3)
        cost += st.get("cost_usd", 0)
        rows.append({"type": d["type"], "found": bool(card), "trail": trail})
        if card:
            cards[d["type"]] = card
    return {"seconds": round(time.monotonic() - t0, 1), "cost_usd": round(cost, 4), "types": rows}, cards


def ldraw_matches(mpd_text, prep, tolerance=0.05):
    """Path A only when the LDraw model is the set as sold: its piece count within 5% of the parts list
    (only 23 of 100 test models match exactly; some hold extra minifigures or alternate models)."""
    from . import ldraw_graph
    if not prep:
        return True
    want = sum(p["quantity"] for p in prep["parts"])
    return want > 0 and abs(len(ldraw_graph.steps_of(mpd_text)) - want) <= tolerance * want


# --- The pipeline ------------------------------------------------------------------------------
def run_case(case, entries, cfg, out, manual, images, pdf):
    from . import v3
    from .extract import ApiSession, SubscriptionSession
    from .parts import ingest, sources
    recipe = VERSIONS[cfg.version]["lego" if case["domain"] == "lego" else "electronics"]
    Session = SubscriptionSession if cfg.route == "subscription" else ApiSession
    phases, prep, extra, listed, store = [], None, {}, None, None

    # 1. parts
    if recipe.parts_list == "lego_sets":
        prep = v3.prepare_lego(case, pdf, cfg, out)
        phases.append(prep["phase"])
        entries = {**entries, **prep["cards"]}
    elif recipe.parts_list == "tutorial":
        store = v3.store("electronics", out, cfg.cards or (ROOT / recipe.card_store if recipe.card_store else None))
        listed = tutorial_parts(manual, store, recipe)
        phases.append(listed["phase"])
        if recipe.store_catalogue:  # the store's cards carry card_notes.json (pin facts the seed lacked)
            entries = {**entries, **{t: store.get(t) for t in store.cards}}
        entries = {**entries, **listed["cards"]}
        manual = manual + listed["manual_extra"]
    elif not pdf and recipe.store_catalogue:  # v5: Claude decides the parts; the store is its catalogue
        store = v3.store("electronics", out, cfg.cards or (ROOT / recipe.card_store if recipe.card_store else None))
        entries = {**entries, **{t: store.get(t) for t in store.cards}}
    counts = listed["counts"] if listed else \
        (tutorial_counts(manual, store) if recipe.parts_count_law and not pdf and recipe.store_catalogue else [])
    items = tutorial_items(manual, store) if recipe.parts_count_law and not pdf and store else []
    catalogue_text = prep["catalogue_text"] if prep and recipe.catalogue == "parts" else \
        (cat.Catalogue(entries).prompt_text(electrical=recipe.electrical_prompt, placement=recipe.placement_law)
         if entries else "")
    booklet = checks.booklet_inventory(pdf) if pdf else None
    policy = (lambda issues: [i for i in issues if i[0] in REAL_RULES]) if recipe.repair == "real" else (lambda issues: issues)

    def check(graph):  # 3. check
        t0 = time.monotonic()
        tmp = cat.Catalogue(entries)
        tmp.add_drafts(graph["new_part_types"])
        flat = expand.expand(graph)
        found = checks.run(flat, tmp, case["domain"], manual, case.get("part_nums", frozenset()), booklet)
        if prep:
            found += v3.parts_check(flat, prep["parts"])
        if recipe.parts_count_law and counts:
            found += checks.parts_count(flat, counts)
        if recipe.parts_count_law and recipe.store_catalogue and not pdf:
            found += checks.parts_extra(flat, manual, items)
        if recipe.pins_law:
            found += checks.pins_wired(flat, manual)
        if recipe.electrical_laws:
            found += checks.electrical(flat, tmp)
        if recipe.geometry_law:
            found += checks.lego_geometry(flat, tmp)
        if recipe.placement_law:
            found += checks.placement(flat, tmp)
        if recipe.table_laws:
            found += checks.pin_table_law(flat, tmp, manual) + checks.matrix_resistors(flat, tmp)
        if recipe.piece_laws and hasattr(b, "laws"):  # v7: L6-L10 on the piece list the builder holds
            found += b.laws()
        return found, round(time.monotonic() - t0, 2)

    def guide_text():  # v8: both text-guide sites are checked; every written guide found goes with the booklet
        if not recipe.text_guides:
            return ""
        t0 = time.monotonic()
        guides = sources.text_guides(case["id"])
        extra["text_guides"] = {"seconds": round(time.monotonic() - t0, 1),
                                "found": [{"source": g["source"], "url": g["url"], "chars": len(g["text"])} for g in guides]}
        return "".join(f"\n\nWRITTEN INSTRUCTIONS for this set from {g['source']} ({g['url']}), written for blind "
                       f"builders:\n{g['text']}\nEND OF WRITTEN INSTRUCTIONS ({g['source']})" for g in guides)

    def builder():  # 2. build: the recipe's builders in order
        kinds = recipe.builders  # --lego-path ldraw / pages forces the recipe's model-file or Claude builder
        if pdf and cfg.lego_path != "auto":
            kinds = [k for k in recipe.builders if k.startswith("ldraw") == (cfg.lego_path == "ldraw")]
        for kind in kinds:
            if kind in ("ldraw", "ldraw-studs"):
                model = sources.adapters("lego_models")[0].fetch_data(case["id"])
                if model and (cfg.lego_path == "ldraw" or ldraw_matches(model["text"], prep)):
                    return LDrawBuild(model["text"], case.get("name", ""), case["id"], studs=kind == "ldraw-studs")
                extra["ldraw_skipped"] = "no model" if not model else "model differs from the set's parts list"
            elif kind == "step-pieces-v8":  # booklets with step numbers as text: a few steps a turn, new pieces boxed
                from . import step_diff
                images = step_diff.step_images(pdf) if pdf and not getattr(cfg, "whole_booklet", False) else []
                if not images:
                    extra["steps_skipped"] = "no step numbers in the booklet's text"
                    continue
                extra["step_diff"] = step_diff.summary(images)
                intro = f"LEGO set {case['id']}: {case.get('name', '')}." + guide_text()
                return StepPiecesV8(Session, images, intro, catalogue_text, "lego-v8-steps", cfg,
                                    parts=prep["parts"] if prep else None)
            elif kind in ("whole-pieces-v7", "whole-pieces-v8"):  # the piece list (one id per piece) replaces the parts list
                intro = f"LEGO set {case['id']}: {case.get('name', '')} (official instructions attached)."
                intro += guide_text()
                return (WholePiecesV8 if kind == "whole-pieces-v8" else WholePiecesV7)(Session, pdf, intro, catalogue_text, recipe.hint, cfg,
                                     parts=prep["parts"] if prep else None)
            elif kind == "whole-pieces":
                intro = f"LEGO set {case['id']}: {case.get('name', '')} (official instructions attached).{prep['manual_extra'] if prep else ''}"
                return WholePieces(Session, pdf, intro, catalogue_text, recipe.hint, cfg,
                                   parts=prep["parts"] if prep else None)
            elif kind == "pieces":
                intro = f"LEGO set {case['id']}: {case.get('name', '')}. First page attached.{prep['manual_extra'] if prep else ''}"
                return PieceBuild(Session, pdf, intro, catalogue_text, recipe.hint, cfg, per_turn=recipe.pages_per_turn,
                                  parts=prep["parts"] if prep else None)
            elif kind == "pages":
                intro = f"LEGO set {case['id']}: {case.get('name', '')}. First page attached.{prep['manual_extra'] if prep else ''}"
                return PageBuild(Session, pdf, intro, catalogue_text, recipe.hint, cfg, per_turn=recipe.pages_per_turn)
            elif kind in ("one-shot", "parts-then-build"):
                cls = PartsThenBuild if kind == "parts-then-build" else OneShot
                return cls(Session, manual, images, catalogue_text, recipe.hint, cfg,
                           parts_tool_store=store.path if recipe.lookup_tool and store else None)
        raise RuntimeError(f"no builder of {recipe.builders} could run for {case['id']}")

    for attempt in range(2):  # a stalled session or a safety-filter false positive: retry once from the start
        b = builder()
        run_phases = []
        try:
            graph, st = b.start()
            graph_initial = graph
            if getattr(b, "parts_stats", None):  # turn 1 of parts-then-build: the parts step, timed on its own
                listed_types = collections.Counter(p["type"] for p in expand.expand(b.parts_graph)["nodes"])
                built_types = collections.Counter(p["type"] for p in expand.expand(graph)["nodes"])
                run_phases.append({"phase": "parts", "builder": "claude turn 1", **b.parts_stats, "check_seconds": 0.0,
                                   "parts_listed": sum(listed_types.values()),
                                   "changed_in_build": sum(((listed_types - built_types) + (built_types - listed_types)).values()),
                                   "looked_up": sorted({t for t in listed_types if t not in entries})})
            issues, secs = check(graph)
            run_phases.append({"phase": "build", "builder": b.name, **st, "check_seconds": secs, "issues": len(issues),
                               "issue_rules": dict(collections.Counter(i[0] for i in issues)),
                               **({"page_turns": b.turns} if b.name == "pages" else {})})
            issues_first = len(issues)
            for n in range(min(cfg.repair_rounds, recipe.repair_rounds) if b.repairable else 0):  # 4. repair
                if not policy(issues):
                    break
                graph, st = b.repair(checks.repair_message(policy(issues)))
                issues, secs = check(graph)
                run_phases.append({"phase": f"repair{n + 1}", **st, "check_seconds": secs, "issues": len(issues),
                                   "issue_rules": dict(collections.Counter(i[0] for i in issues))})
            if b.name == "ldraw":
                extra["steps"] = b.steps
            if hasattr(b, "rests_graph"):  # v8: joins from rests_on alone, scored separately; placements kept
                extra["graph_rests"] = b.rests_graph()
                extra["placements"] = {i: {"step": p["step"], "page": p.get("page"), "rests_on": p["rests_on"], **p["placement"]}
                                       for i, p in b.pieces.items()}
            elif hasattr(b, "position_graph"):  # v7: joins computed from the positions alone, scored separately
                extra["graph_positions"] = b.position_graph()
            if recipe.recheck_after_upkeep and graph["new_part_types"]:  # 5. upkeep now, while the session is open
                try:
                    extra["upkeep"], new_cards = upkeep(graph, recipe, cfg, out)
                except Exception as e:  # a shop or model failure while carding must not lose the graph
                    extra["upkeep"], new_cards = {"error": f"{type(e).__name__}: {str(e)[:200]}"}, {}
                if new_cards:  # the new cards' electrical facts: check again, repair once
                    entries = {**entries, **new_cards}
                    tmp = cat.Catalogue(entries)
                    tmp.add_drafts(graph["new_part_types"])
                    found = checks.electrical(expand.expand(graph), tmp)
                    if found and b.repairable:
                        graph, st = b.repair(checks.repair_message(found))
                        issues, secs = check(graph)
                        run_phases.append({"phase": "repair-after-upkeep", **st, "check_seconds": secs,
                                           "issues": len(issues), "issue_rules": dict(collections.Counter(i[0] for i in issues))})
            break
        except subprocess.TimeoutExpired as e:
            with open(out / "stalls.log", "a") as f:
                f.write(f"{case['id']} attempt {attempt + 1}: no result after {e.timeout}s; last events {e.output}\n")
            if attempt:
                raise
        except RuntimeError as e:
            if attempt or "safeguards" not in str(e):
                raise
        finally:
            b.close()
    phases += run_phases

    # 5. upkeep: card the part types the model drafted (not part of this manual's build time)
    if recipe.ingest_new_types and graph["new_part_types"] and "upkeep" not in extra:
        try:
            extra["upkeep"], _ = upkeep(graph, recipe, cfg, out)
        except Exception as e:
            extra["upkeep"] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}

    build = next(p for p in phases if p["phase"] == "build")
    total = {"model": build.get("model"), "effort": cfg.effort, "route": build.get("route"), "version": cfg.version,
             "builder": build["builder"], "seconds": round(sum(p["seconds"] + p.get("check_seconds", 0) for p in phases), 1),
             "input_tokens": sum(p.get("input_tokens", 0) for p in phases),
             "output_tokens": sum(p.get("output_tokens", 0) for p in phases),
             "cost_usd": round(sum(p.get("cost_usd", 0) for p in phases), 4),
             "repair_rounds_used": sum(1 for p in phases if p["phase"].startswith("repair"))}
    saved = {"graph": graph, "graph_initial": graph_initial, "stats": total, "phases": phases, "issues_first": issues_first,
             "issues_final": len(issues), "final_issue_list": [list(i) for i in issues], **extra}
    if prep:
        saved.update(cards=prep["cards"], parts_list=prep["parts"])
    return saved
