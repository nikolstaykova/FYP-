"""Claude through the Anthropic API: one call with photos, answer as JSON. Used by the gather flow
(checker.gather_flow).

Needs ANTHROPIC_API_KEY in the environment or in .env at the project root.
Prices per 1M tokens (in / out), Anthropic API, read 3 Nov 2026.
"""
import base64
import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}
_client = None


def api_key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    return k or None


def client():
    global _client
    if _client is None:
        import anthropic
        if not api_key():
            raise RuntimeError("ANTHROPIC_API_KEY is not set (add it to .env)")
        _client = anthropic.Anthropic(api_key=api_key(), timeout=600, max_retries=3)
    return _client


def media_type(path):
    p = str(path).lower()
    return "image/png" if p.endswith(".png") else "image/webp" if p.endswith(".webp") else "image/jpeg"


def ask(model, images, text, max_tokens=16000, effort="low"):
    """images: (bytes, media type) pairs, numbered "Photo 1", "Photo 2"... in the order given.
    Returns (answer text, usage with cost, seconds)."""
    content = []
    for i, (b, mt) in enumerate(images, 1):
        content += [{"type": "text", "text": f"Photo {i}:"},
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(b).decode()}}]
    content.append({"type": "text", "text": text})
    t0 = time.perf_counter()
    r = client().messages.create(model=model, max_tokens=max_tokens, output_config={"effort": effort},
                                 messages=[{"role": "user", "content": content}])
    secs = time.perf_counter() - t0
    out = "".join(b.text for b in r.content if b.type == "text")
    tin, tout = r.usage.input_tokens, r.usage.output_tokens
    pin, pout = PRICES.get(model, (0, 0))
    return out, {"model": model, "tokens_in": tin, "tokens_out": tout, "stop_reason": r.stop_reason,
                 "cost_usd": round((tin * pin + tout * pout) / 1e6, 6), "seconds": round(secs, 1)}, secs


def json_objects(text):
    """The "objects" list from a JSON answer (tolerates text around the JSON); [] when there is none."""
    i, j = text.find("{"), text.rfind("}")
    try:
        objs = json.loads(text[i:j + 1]).get("objects", [])
    except (ValueError, AttributeError):
        return []
    return [o for o in objs if isinstance(o, dict)]
