"""One Claude call: manual (+ catalogue) in, ExtractedGraph out, with timing and usage.

Uses structured outputs (the response must match model.ExtractedGraph),
adaptive thinking, streaming (graphs for larger sets are long), and
server-side refusal fallbacks.
"""
import base64
import time

import anthropic

from .model import ExtractedGraph

MODEL = "claude-sonnet-5"
FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1", "claude-fable-5"}  # server-side refusal fallbacks
PRICE = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0),
         "claude-opus-5-5": (4.0, 20.0), "claude-fable-5-1": (10.0, 50.0)}  # $ per 1M input / output tokens

SPEC = """You turn an assembly manual or tutorial into ONE build graph, following this specification.

GRAPH
- Nodes are EVERY physical part, including connectors: each jumper wire, the breadboard, the board, every brick.
- Edges are typed connections between two parts, optionally naming the port on each side.
  joined     held together (a leg pushed into a breadboard hole, a wire end in a header socket, a brick on studs)
  contact    touching but not fastened
  electrical current can flow between the two ports. A physical electrical connection gets BOTH a
             `joined` and an `electrical` edge between the same ports.
  blocks     not touching, but one part prevents the other being added later
  anchored   fixed to the world (wall, floor)
- What happens INSIDE a part (a wire conducts end to end, a breadboard strip joins its holes, a resistor
  does not join its legs) comes from the catalogue. Do not add edges inside a part.

NAMING
- Instance ids: short lowercase name + number: uno, bb1, r1, led1, btn1, pot1, wire1 ... ; LEGO: keep the ids given.
- Ports are named exactly as in the catalogue entry (e.g. led A/C, resistor 1/2, uno 13 / A0 / GND.1 / 5V,
  breadboard '12t.c'). For a part type you create, choose clear port names and list them.
- Use catalogue types where they exist. A resistor is type `resistor` with a `value` prop (e.g. value=220).

PORT KINDS (use only these for a port's kind)
- electronics: lead, header-pin, header-socket, breadboard-hole, wire-end, lug
- LEGO: stud, anti-stud, pin, pin-hole, axle, axle-hole, clip, bar, ball, socket, hinge
- furniture: hole, screw, dowel, cam, groove, edge
Compatible joins: stud/anti-stud, pin/pin-hole, axle/axle-hole, axle/pin-hole (turns), clip/bar, ball/socket,
hinge/hinge, lead or wire-end or header-pin into breadboard-hole or header-socket, lead/lead (twisted or soldered).

NEW PART TYPES
- If a part is not in the catalogue, add ONE entry to new_part_types (not one per copy) with its ports,
  inside behaviour (conducts / through), symmetry, polarity, connector flag, mirror twin and rotation symmetry.

REPEATS
- If the manual builds the same sub-assembly N times, put it in `repeats` once with times=N. Copies that
  differ get overrides: replace (other part type), props (e.g. colour=red), mirror, add/remove, or attach
  (a copy connects to a different external endpoint, e.g. template endpoint 'uno:2' -> 'uno:5' for copy 4).
- Parts and edges inside a repeat use local ids; endpoints that are not local ids refer to parts outside it.

Be complete: every part the manual uses appears, and every connection it requires is an edge. Put any
assumption you had to make in notes."""

ARDUINO_HINT = """This is an electronics tutorial (Arduino or Raspberry Pi). Build the circuit the tutorial describes,
including any optional external LED circuit it lists. A Raspberry Pi's GPIO header pins are ports on the board
(name them e.g. GPIO17, GND, 3V3, 5V); boards and modules not in the catalogue are new part types. Place parts on a breadboard when the tutorial uses one, and use jumper wires
for every wire. The circuit images, when given, are the authority on what connects where."""

LEGO_PDF_HINT = """This is an official LEGO building-instructions PDF. Steps are pictures: each step's parts box shows
the pieces added (with counts), and the last pages list every piece with its count and Element ID.
- Every physical piece is a node. Use type `lego-<Element ID>` from the inventory pages and put the colour in props.
  Ids: b1, b2, ... in build order.
- Give a `joined` edge for every pair of pieces that connect (studs into a piece above, a pin into a hole, an
  axle through, a clip on a bar, a hinge), with method and freedom. Ports may be null.
- Sub-assemblies built more than once (a "2x" or "4x" box) go in `repeats`.
- If the booklet contains several separate models, build all of them."""

LEGO_HINT = """This is a LEGO model given as its official parts with exact positions (LDraw units: 1 stud = 20 LDU
horizontally, a brick is 24 LDU tall, a plate 8; -Y is UP; a part's origin is the centre of its TOP surface
and it extends downward (+Y) by its height). Give a `joined` edge for every pair of parts that clutch each other
(studs of the lower part inside the upper part), with method `insert` and freedom `rigid`. Ports may be null.
Keep the given part ids."""


def _image_block(data, media_type="image/png"):
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(data).decode()}}


HINTS = {"arduino": ARDUINO_HINT, "lego": LEGO_HINT, "lego-pdf": LEGO_PDF_HINT}


def _pdf_block(pdf_bytes):
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.standard_b64encode(pdf_bytes).decode()}}


def extract(manual_text, catalogue_text, domain, images=(), pdf=None, model=MODEL, effort="high",
            max_tokens=64000, client=None):
    """Returns (graph_dict, stats). domain: arduino | lego | lego-pdf."""
    client = client or anthropic.Anthropic()
    catalogue_block = ("CATALOGUE (part types that already exist; anything else is new):\n" + catalogue_text
                       if catalogue_text else "CATALOGUE: empty. Every part type you use is new and must be in new_part_types.")
    # Spec + hint + catalogue are identical across manuals of one run: cache them.
    system = [{"type": "text", "text": SPEC + "\n\n" + HINTS[domain] + "\n\n" + catalogue_block,
               "cache_control": {"type": "ephemeral"}}]
    content = [*([_pdf_block(pdf)] if pdf else []), *(_image_block(b, m) for b, m in images),
               {"type": "text", "text": "MANUAL:\n" + manual_text}]
    t0 = time.monotonic()
    first = None
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        **extra,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=ExtractedGraph,
        system=system,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for event in stream:
            if first is None and event.type == "content_block_delta":
                first = time.monotonic() - t0
        final = stream.get_final_message()
    seconds = time.monotonic() - t0
    if final.stop_reason == "refusal":
        raise RuntimeError(f"refused: {final.stop_details}")
    if final.stop_reason == "max_tokens":
        raise RuntimeError("hit max_tokens before the graph was complete")
    parsed = getattr(final, "parsed_output", None)
    if parsed is None:
        text = next(b.text for b in final.content if b.type == "text")
        parsed = ExtractedGraph.model_validate_json(text)
    u = final.usage
    pin, pout = PRICE.get(final.model, PRICE.get(model, (0, 0)))
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
    cost = (u.input_tokens * pin + cache_write * pin * 1.25 + cache_read * pin * 0.1 + u.output_tokens * pout) / 1e6
    stats = {"model": final.model, "effort": effort, "seconds": round(seconds, 1),
             "first_token_seconds": round(first, 1) if first else None,
             "input_tokens": u.input_tokens + cache_read + cache_write, "cache_read_tokens": cache_read,
             "output_tokens": u.output_tokens, "cost_usd": round(cost, 4),
             "request_id": getattr(final, "_request_id", None)}
    return parsed.model_dump(), stats


# --- Route 2: headless Claude Code on the user's Claude subscription -------------------
CLAUDE_CODE_ENV_DROP = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION")


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
    u = result["usage"]
    used = next(iter(result.get("modelUsage") or {}), model)
    stats = {"model": used, "effort": effort, "route": "claude-code subscription", "seconds": round(seconds, 1),
             "api_seconds": round(result.get("duration_api_ms", 0) / 1000, 1),
             "first_token_seconds": round(result.get("ttft_ms", 0) / 1000, 1) or None,
             "input_tokens": u["input_tokens"] + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
             "cache_read_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u["output_tokens"],
             "cost_usd": round(result.get("total_cost_usd", 0.0), 4), "turns": result.get("num_turns")}
    return parsed.model_dump(), stats


# --- Build-then-repair sessions: the repair turn reuses the manual already in context ----------
def _system_and_content(manual_text, catalogue_text, domain, images, pdf):
    catalogue_block = ("CATALOGUE (part types that already exist; anything else is new):\n" + catalogue_text
                       if catalogue_text else "CATALOGUE: empty. Every part type you use is new and must be in new_part_types.")
    system = SPEC + "\n\n" + HINTS[domain] + "\n\n" + catalogue_block
    content = [*([_pdf_block(pdf)] if pdf else []), *(_image_block(b, m) for b, m in images),
               {"type": "text", "text": "MANUAL:\n" + manual_text}]
    return system, content


class SubscriptionSession:
    """One `claude -p` process kept open (stream-json in/out): turn 1 builds the graph, later turns repair it."""

    def __init__(self, manual_text, catalogue_text, domain, images=(), pdf=None, model="sonnet", effort="high", timeout=900):
        import json
        import os
        import queue
        import subprocess
        import tempfile
        import threading

        self.json, self.timeout, self.model, self.effort = json, timeout, model, effort
        system, self.first_content = _system_and_content(manual_text, catalogue_text, domain, images, pdf)
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        f.write(system)
        f.close()
        self.sys_path = f.name
        env = {k: v for k, v in os.environ.items() if k not in CLAUDE_CODE_ENV_DROP}
        self.proc = subprocess.Popen(
            ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
             "--model", model, "--effort", effort, "--no-session-persistence", "--tools", "",
             "--system-prompt-file", self.sys_path, "--json-schema", json.dumps(ExtractedGraph.model_json_schema())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            cwd=tempfile.gettempdir(), bufsize=1)
        self.lines = queue.Queue()
        threading.Thread(target=lambda: [self.lines.put(l) for l in self.proc.stdout] + [self.lines.put(None)],
                         daemon=True).start()
        self.prev_cost = 0.0

    def _turn(self, content):
        import queue
        import subprocess
        t0 = time.monotonic()
        self.proc.stdin.write(self.json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
        self.proc.stdin.flush()
        result = None
        while result is None:
            try:
                line = self.lines.get(timeout=self.timeout)
            except queue.Empty:
                self.close()
                raise subprocess.TimeoutExpired("claude -p", self.timeout)
            if line is None:
                raise RuntimeError("claude -p exited: " + self.proc.stderr.read()[-300:])
            try:
                event = self.json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                result = event
        if result.get("is_error") or not result.get("structured_output"):
            raise RuntimeError(f"claude -p failed: {str(result.get('result'))[:300]}")
        total = result.get("total_cost_usd", 0.0) or 0.0
        cost = total - self.prev_cost if total >= self.prev_cost else total  # cumulative per session
        self.prev_cost = max(total, self.prev_cost)
        u = result["usage"]
        stats = {"model": next(iter(result.get("modelUsage") or {}), self.model), "effort": self.effort,
                 "route": "claude-code subscription", "seconds": round(time.monotonic() - t0, 1),
                 "input_tokens": u["input_tokens"] + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                 "cache_read_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u["output_tokens"],
                 "cost_usd": round(cost, 4)}
        return ExtractedGraph.model_validate(result["structured_output"]).model_dump(), stats

    def first(self):
        return self._turn(self.first_content)

    def repair(self, message):
        return self._turn([{"type": "text", "text": message}])

    def close(self):
        import os
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        if os.path.exists(self.sys_path):
            os.unlink(self.sys_path)


class ApiSession:
    """Same two-turn flow on the Anthropic API (needs ANTHROPIC_API_KEY)."""

    def __init__(self, manual_text, catalogue_text, domain, images=(), pdf=None, model=MODEL, effort="high", max_tokens=64000):
        self.client = anthropic.Anthropic()
        system, content = _system_and_content(manual_text, catalogue_text, domain, images, pdf)
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.messages = [{"role": "user", "content": content}]
        self.model, self.effort, self.max_tokens = model, effort, max_tokens

    def _turn(self):
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if self.model in FALLBACK_MODELS else {}
        t0 = time.monotonic()
        with self.client.beta.messages.stream(model=self.model, max_tokens=self.max_tokens, **extra,
                                              thinking={"type": "adaptive"}, output_config={"effort": self.effort},
                                              output_format=ExtractedGraph, system=self.system, messages=self.messages) as s:
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
        return ExtractedGraph.model_validate_json(text).model_dump(), stats

    def first(self):
        return self._turn()

    def repair(self, message):
        self.messages.append({"role": "user", "content": message})
        return self._turn()

    def close(self):
        pass
