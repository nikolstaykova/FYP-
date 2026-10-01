"""One Claude call: manual (+ catalogue) in, ExtractedGraph out, with timing and usage.

Uses structured outputs (the response must match model.ExtractedGraph),
adaptive thinking, streaming (graphs for larger sets are long), and
server-side refusal fallbacks.
"""
import base64
import time

import anthropic

from .model import ExtractedGraph

MODEL = "claude-opus-5"
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

ARDUINO_HINT = """This is an Arduino tutorial. Build the circuit the tutorial describes, including any optional
external LED circuit it lists. Place parts on a breadboard when the tutorial uses one, and use jumper wires
for every wire. The circuit images, when given, are the authority on what connects where."""

LEGO_HINT = """This is a LEGO model given as its official parts with exact positions (LDraw units: 1 stud = 20 LDU
horizontally, a brick is 24 LDU tall, a plate 8; -Y is UP; a part's origin is the centre of its TOP surface
and it extends downward (+Y) by its height). Give a `joined` edge for every pair of parts that clutch each other
(studs of the lower part inside the upper part), with method `insert` and freedom `rigid`. Ports may be null.
Keep the given part ids."""


def _image_block(png_bytes):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(png_bytes).decode()}}


def extract(manual_text, catalogue_text, domain, images=(), model=MODEL, effort="high", client=None):
    """Returns (graph_dict, stats)."""
    client = client or anthropic.Anthropic()
    system = SPEC + "\n\n" + (ARDUINO_HINT if domain == "arduino" else LEGO_HINT)
    catalogue_block = ("CATALOGUE (part types that already exist; anything else is new):\n" + catalogue_text
                       if catalogue_text else "CATALOGUE: empty. Every part type you use is new and must be in new_part_types.")
    content = [*(_image_block(b) for b in images),
               {"type": "text", "text": catalogue_block + "\n\nMANUAL:\n" + manual_text}]
    t0 = time.monotonic()
    first = None
    with client.beta.messages.stream(
        model=model,
        max_tokens=64000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
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
    stats = {"model": final.model, "effort": effort, "seconds": round(seconds, 1),
             "first_token_seconds": round(first, 1) if first else None,
             "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "cost_usd": round((u.input_tokens * pin + u.output_tokens * pout) / 1e6, 4),
             "request_id": getattr(final, "_request_id", None)}
    return parsed.model_dump(), stats
