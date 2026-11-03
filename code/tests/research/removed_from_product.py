"""Definitions taken out of the product because nothing used them (kept for the record; not
maintained, may not run). Each section names the file it came from."""


# ==== from graph/extract.py =================================================================================
def extract_claude_code(manual_text, catalogue_text, domain, images=(), pdf=None, model="sonnet", effort="high",
                        timeout=900):
    """Same request through `claude -p` (subscription login instead of an API key).

    Structured output via --json-schema; PDF and images as content blocks over stream-json input.
    No tools, Claude Code's default system prompt replaced by ours. `cost_usd` is Claude Code's
    estimate at API list prices: what the call would cost on the API, not what the subscription charges."""
    import json
    import os
    import subprocess
    import tempfile

    catalogue_block = ("CATALOGUE (part types that already exist; anything else is new):\n" + catalogue_text
                       if catalogue_text else "CATALOGUE: empty. Every part type you use is new and must be in new_part_types.")
    system = SPEC + "\n\n" + HINTS[domain] + "\n\n" + catalogue_block
    content = [*([_pdf_block(pdf)] if pdf else []), *(_image_block(b, m) for b, m in images),
               {"type": "text", "text": "MANUAL:\n" + manual_text}]
    schema = json.dumps(ExtractedGraph.model_json_schema())
    env = {k: v for k, v in os.environ.items() if k not in CLAUDE_CODE_ENV_DROP}
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
        msg_path = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(system)
        sys_path = f.name
    cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--model", model, "--effort", effort, "--no-session-persistence", "--tools", "",
           "--system-prompt-file", sys_path, "--json-schema", schema]
    t0 = time.monotonic()
    try:
        with open(msg_path) as stdin:
            proc = subprocess.run(cmd, stdin=stdin, capture_output=True, text=True, env=env, timeout=timeout, cwd=tempfile.gettempdir())
    finally:
        os.unlink(msg_path)
        os.unlink(sys_path)
    seconds = time.monotonic() - t0
    result = None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            result = event
    if not result or result.get("is_error") or not result.get("structured_output"):
        detail = (result or {}).get("result") or proc.stderr[-500:] or proc.stdout[-500:]
        raise RuntimeError(f"claude -p failed: {str(detail)[:300]}")
    parsed = ExtractedGraph.model_validate(result["structured_output"])
    return parsed.model_dump(), _usage_stats(result, model, effort, seconds)


class ApiSession:
    """Same two-turn flow on the Anthropic API (needs ANTHROPIC_API_KEY)."""

    def __init__(self, manual_text, catalogue_text, domain, images=(), pdf=None, model=MODEL, effort="high", max_tokens=64000,
                 schema=ExtractedGraph):
        self.client = anthropic.Anthropic()
        system, content = _system_and_content(manual_text, catalogue_text, domain, images, pdf)
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.messages = [{"role": "user", "content": content}]
        self.model, self.effort, self.max_tokens, self.schema = model, effort, max_tokens, schema

    def _turn(self):
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if self.model in FALLBACK_MODELS else {}
        t0 = time.monotonic()
        with self.client.beta.messages.stream(model=self.model, max_tokens=self.max_tokens, **extra,
                                              thinking={"type": "adaptive"}, output_config={"effort": self.effort},
                                              output_format=self.schema, system=self.system, messages=self.messages) as s:
            final = s.get_final_message()
        if final.stop_reason in ("refusal", "max_tokens"):
            raise RuntimeError(f"stopped: {final.stop_reason}")
        text = next(b.text for b in final.content if b.type == "text")
        self.messages.append({"role": "assistant", "content": [{"type": "text", "text": text}]})
        u = final.usage
        pin, pout = PRICE.get(final.model, PRICE.get(self.model, (0, 0)))
        cr, cw = getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0
        stats = {"model": final.model, "effort": self.effort, "route": "api", "seconds": round(time.monotonic() - t0, 1),
                 "input_tokens": u.input_tokens + cr + cw, "cache_read_tokens": cr, "output_tokens": u.output_tokens,
                 "cost_usd": round((u.input_tokens * pin + cw * pin * 1.25 + cr * pin * 0.1 + u.output_tokens * pout) / 1e6, 4)}
        return self.schema.model_validate_json(text).model_dump(), stats

    def first(self):
        return self._turn()

    def repair(self, message):
        self.messages.append({"role": "user", "content": message})
        return self._turn()

    def send(self, content):
        self.messages.append({"role": "user", "content": content})
        return self._turn()

    def close(self):
        pass


# ==== from graph/lego_booklet/step_diff.py ==================================================================
def step_images(pdf_bytes, grid=False, tight=False, dpi=DPI, top=0.22):
    """[{step, page, crop, png, boxes, zooms}] for a booklet with step numbers as text, step 1 first: each step's
    picture as PNG, with the regions it adds boxed in red (boxes None when it does not align with the previous step).
    grid: False, "v1" (grey labelled grid) or "v2" (magenta grid, every cell labelled, plus a high-resolution
    close-up of each of the largest boxes in `zooms`). tight: trim each cut to its step (tighten). [] for a scanned
    booklet. dpi: the pictures' resolution (the booklets' own pictures are 300 DPI)."""
    import cv2
    import pymupdf
    grid = "v1" if grid is True else grid
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    where = lego_model.booklet_steps(doc)
    if tight:  # each cut trimmed to its step (no panel or advert beside or below the last step on a page)
        where = [(page, tighten(doc[page - 1], crop)) for page, crop in where]
    out, prev = [], None
    for n, (page, crop) in enumerate(where, 1):
        cur = _bgr(doc[page - 1], crop, dpi)
        boxes = (changed_regions(prev, cur, top=top, corner=number_corner(dpi)) if not top else
                 changed_regions(prev, cur)) if prev is not None else None
        marked = cur.copy()
        for x, y, w, h in boxes or ():
            cv2.rectangle(marked, (x, y), (x + w, y + h), (0, 0, 255), max(4, round(4 * dpi / DPI)))
        if grid:
            marked = draw_grid(marked, style=grid)
        out.append({"step": n, "page": page, "crop": crop, "boxes": boxes,
                    "png": cv2.imencode(".png", marked)[1].tobytes(),
                    "zooms": close_ups(doc[page - 1], crop, boxes) if grid == "v2" else []})
        prev = cur
    return out


def summary(images):
    c = collections.Counter("first" if i["step"] == 1 else "boxed" if i["boxes"] else "no-align" if i["boxes"] is None
                            else "no-change" for i in images)
    return dict(c)


# ==== from graph/parts/cards.py =============================================================================
def add_shape_studs(store, ids=None, log=print):
    """LEGO cards that list fewer top studs than the part's real shape has get the missing ones, by code
    (ldraw_studs.stud_ports, named as the joins name them). Only on building pieces (a propeller's hub or a hair
    piece's stud-like shapes are not top studs), and never removing a port: a card that claims more than the shape
    shows stays as it is, for review. Returns {part: [studs added]}."""
    import json as _json
    from graph import lego_model
    cards = _json.loads(store.path.read_text())
    added = {}
    for t in sorted(ids or cards):
        c = cards.get(t)
        if not c or not t.startswith("lego-") or not any(w in (c.get("category") or "").lower() for w in BUILDING):
            continue
        try:
            shape = lego_model.stud_ports(t[len("lego-"):] + ".dat")
        except Exception:
            continue
        have = {p["id"] for p in c.get("ports") or [] if p.get("kind") == "stud"}
        if shape and len(have) < len(shape):
            new = [s for s in shape if s not in have]
            c["ports"] = (c.get("ports") or []) + [{"id": s, "kind": "stud", "gender": None, "voltage_rating": None,
                                                     "aliases": []} for s in new]
            c["note"] = ((c.get("note") or "") + " Top studs added from the LDraw shape by code.").strip()
            added[t] = new
    if added:
        store.path.write_text(_json.dumps(cards, indent=1))
        log(f"  studs added from the shape: {added}")
    return added


# --- Electronics: the tutorial's parts list, matched to the store ---------------------------
class PartLine(BaseModel):
    label: str = Field(description="The part as the tutorial names it")
    quantity: int
    catalogue_type: Optional[str] = Field(description="Catalogue type id that is this part, or null if none fits")
    new_type: Optional[str] = Field(description="If catalogue_type is null: the type id this part should get, by the naming rules")
    search_query: Optional[str] = Field(description="If catalogue_type is null: a short shop search query (product name, chip)")
    category: str


class PartsList(BaseModel):
    parts: List[PartLine] = Field(description="Every physical part the tutorial uses, wires and breadboard included")


def match_parts(manual_text, store, model="sonnet", effort="low"):
    """Claude reads the tutorial's parts and matches each to a stored card. Returns (parts, stats)."""
    from graph.extract import claude_json
    system = ("You list the physical parts an electronics tutorial uses and match each to the part catalogue.\n"
              "Use a catalogue type whenever one is the same kind of part (any resistor value -> resistor, any LED colour "
              "-> led). Only propose a new type for a part the catalogue really lacks.\n\n" +
              ing.NAMING + "\n\nCATALOGUE:\n" + store.index_text())
    out, stats = claude_json(system, [{"type": "text", "text": "TUTORIAL:\n" + manual_text[:30000]}], PartsList,
                             model=model, effort=effort)
    return out["parts"], stats


# ==== from graph/parts/lego/inventory.py ====================================================================
def booklet_parts(pdf_bytes, model="sonnet", effort="low"):
    """Parts from the booklet. Returns (parts_list, stats, method)."""
    t = RebrickableDump.tables()
    page = booklet_inventory(pdf_bytes)  # {element_id: count} from the parts page, by code
    known = {el: q for el, q in page.items() if el in t["el_to_part"]}
    if known and sum(known.values()) >= 0.8 * sum(page.values()):
        out = [RebrickableDump.describe(*t["el_to_part"][el], q, element_id=el) for el, q in sorted(known.items())]
        return out, {"seconds": 0.0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}, "booklet parts page (code)"
    from graph.extract import _pdf_block, claude_json
    system = ("You read a LEGO building-instructions booklet and list every piece the model uses, with its total count: "
              "add up the parts boxes of all steps (a box inside a '2x' sub-assembly counts twice), or copy the parts page "
              "at the end if there is one. Give the LEGO design number when you know it.")
    res, stats = claude_json(system, [_pdf_block(pdf_bytes), {"type": "text", "text": "List the pieces."}], BookletParts,
                             model=model, effort=effort, timeout=1200)
    colour_id = {v.lower(): k for k, v in t["colors"].items()}
    merged = collections.Counter()
    for line in res["parts"]:
        part, color = None, colour_id.get(line["colour"].lower(), "-1")
        if line["element_id"] and line["element_id"] in t["el_to_part"]:
            part, color = t["el_to_part"][line["element_id"]]
        elif line["part_num"] and line["part_num"] in t["parts"]:
            part = line["part_num"]
        merged[(part or "x-" + "-".join(line["name"].lower().split())[:40], color, line["name"])] += line["quantity"]
    out = []
    for (part, color, name), q in sorted(merged.items()):
        d = RebrickableDump.describe(part, color, q)
        if d["name"] == "?":
            d.update(name=name, category="unknown")
        out.append(d)
    return out, stats, "Claude read the booklet"


# ==== from graph/parts/naming.py ============================================================================
def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in FILLER}


# ==== from graph/lego_booklet/step_diff.py ==================================================================
def close_ups(page, crop, boxes, scale=2, most=3):
    """High-resolution close-ups of the largest red boxes (the model sees a downscaled picture, so small studs blur):
    each box with a margin, rendered at `scale` times the step picture's resolution, with a fine v2 grid in
    lowercase. Returns [png]."""
    import cv2
    big = _bgr(page, crop, dpi=DPI * scale)
    out = []
    for n, (x, y, w, h) in enumerate((boxes or [])[:most], 1):  # boxes come most-changed first
        m = max(w, h) // 3
        x0, y0 = max(0, (x - m) * scale), max(0, (y - m) * scale)
        x1, y1 = min(big.shape[1], (x + w + m) * scale), min(big.shape[0], (y + h + m) * scale)
        zoom = big[y0:y1, x0:x1].copy()
        cv2.rectangle(zoom, ((x - x0 // scale) * scale, (y - y0 // scale) * scale),
                      ((x + w - x0 // scale) * scale, (y + h - y0 // scale) * scale), (0, 0, 255), 3)
        zoom = draw_grid(zoom, cell=max(36, min(zoom.shape[:2]) // 6), style="v2", lower=True)
        cv2.putText(zoom, f"close-up {n}", (6, zoom.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 4)
        cv2.putText(zoom, f"close-up {n}", (6, zoom.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 160), 2)
        out.append(cv2.imencode(".png", zoom)[1].tobytes())
    return out


# ==== from graph/lego_model.py ==============================================================================
# --- booklet pictures ----------------------------------------------------------------------------------------
def booklet_steps(pdf_path, build=None):
    """Where each step of one BUILD is in the booklet: [(page number, (x0, y0, x1, y1) in PDF points)], step 1 first.
    Step numbers are the booklet's large digits (page numbers are small); a page with several steps is split between
    them, side by side or one under another. A booklet can hold several builds (3-in-1 sets, B models): the step
    numbers start again at 1 for each; build=1 is the first one, None (default) all of them.
    [] for a scanned booklet (no text)."""
    builds = booklet_builds(pdf_path)
    if build is None:
        return [x for b in builds for x in b]
    return builds[build - 1] if 0 < build <= len(builds) else []


# ==== from graph/parts/lego/inventory.py ====================================================================
class BookletParts(BaseModel):
    parts: List[BookletLine]


def booklet_inventory(pdf_bytes):
    """Element ID -> count from a booklet's own parts page(s), if it has any (text like '4x' then '300401')."""
    if not pdf_bytes:
        return {}
    import pymupdf
    inv = collections.Counter()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        if not booklet_inventory_page(page):
            continue
        tokens = page.get_text().split()
        for a, b in zip(tokens, tokens[1:]):
            m = re.fullmatch(r"(\d{1,3})x", a)
            if m and re.fullmatch(r"\d{6,7}", b):
                inv[b] += int(m.group(1))
    return dict(inv)


# ==== from graph/lego_booklet/step_diff.py ==================================================================
def draw_grid(img, cell=None, style="v1", lower=False):
    """A labelled grid on the picture (the 'grid-augmented' prompt from the research: reading a label instead of
    judging a position). v1: grey lines, columns A, B, C ... and rows 1, 2, 3 ... on the edges. v2: magenta lines and
    every cell labelled inside its own top-left corner (C4), so no row or column has to be traced. lower: lowercase
    column letters (close-ups), so a close-up cell (c4) is never confused with a cell of the whole picture (C4)."""
    import cv2
    h, w = img.shape[:2]
    cell = cell or max(40, min(h, w) // 9)
    col = (lambda i: chr(97 + i % 26)) if lower else (lambda i: chr(65 + i) if i < 26 else "A" + chr(65 + i - 26))
    colour = MAGENTA if style == "v2" else (90, 90, 90)
    over = img.copy()
    for x in range(0, w, cell):
        cv2.line(over, (x, 0), (x, h), colour, 1)
    for y in range(0, h, cell):
        cv2.line(over, (0, y), (w, y), colour, 1)
    out = cv2.addWeighted(over, 0.6 if style == "v2" else 0.55, img, 0.4 if style == "v2" else 0.45, 0)
    font = cv2.FONT_HERSHEY_SIMPLEX
    if style == "v2":
        size = max(0.32, cell / 150)
        for i, x in enumerate(range(0, w, cell)):
            for j, y in enumerate(range(0, h, cell)):
                label, at = f"{col(i)}{j + 1}", (x + 2, y + int(11 * size / 0.35))
                cv2.putText(out, label, at, font, size, (255, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(out, label, at, font, size, (120, 0, 120), 1, cv2.LINE_AA)
        return out
    size = max(0.4, cell / 110)
    for i, x in enumerate(range(0, w, cell)):
        for y in (cell // 3, h - 6):
            cv2.putText(out, col(i), (x + cell // 2 - 6, y), font, size, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(out, col(i), (x + cell // 2 - 6, y), font, size, (20, 20, 20), 1, cv2.LINE_AA)
    for j, y in enumerate(range(0, h, cell)):
        for x in (3, w - cell // 3 - 4):
            cv2.putText(out, str(j + 1), (x, y + cell // 2 + 5), font, size, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(out, str(j + 1), (x, y + cell // 2 + 5), font, size, (20, 20, 20), 1, cv2.LINE_AA)
    return out


# ==== from graph/parts/lego/inventory.py ====================================================================
# --- Fallback: the set is not in Rebrickable --------------------------------------------
class BookletLine(BaseModel):
    element_id: Optional[str] = Field(description="Element ID printed next to the piece, or null")
    part_num: Optional[str] = Field(description="LEGO design number if you know it (e.g. 3001 for Brick 2 x 4), or null")
    name: str = Field(description="Piece name in Rebrickable style, e.g. 'Plate 1 x 2', 'Slope 45 2 x 2'")
    colour: str
    quantity: int


# ---- a booklet's own parts page -------------------------------------------------------------------
def booklet_inventory_page(page):
    """A parts page lists at least 5 Element IDs as text."""
    return sum(1 for t in page.get_text().split() if re.fullmatch(r"\d{6,7}", t)) >= 5
