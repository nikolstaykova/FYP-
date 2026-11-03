"""Claude through the Anthropic API directly (not the `claude -p` subscription route), so its speed can be compared
fairly with Gemini and NVIDIA. `ask()` has the same shape as gemini_bench.ask and nvidia_bench.ask and is the look
step of kit_test.py, swap_test.py and the lab (lab/server.py) for models named claude-*.

Prices per 1M tokens (in / out), Anthropic API, read 3 Nov 2026. Needs ANTHROPIC_API_KEY in .env.
"""
import base64
import os
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[2]
PRICES = {'claude-haiku-5-5': (0.10, 0.50), 'claude-sonnet-5-5': (2.00, 10.00), 'claude-opus-5-5': (4.00, 20.00)}
_client = None


def key():
    k = os.environ.get('ANTHROPIC_API_KEY')
    if not k and (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('ANTHROPIC_API_KEY='):
                k = line.split('=', 1)[1].strip().strip('"\'')
    return k or None


def client():
    global _client
    if _client is None:
        if not key():
            raise RuntimeError('ANTHROPIC_API_KEY is not set (add it to .env)')
        _client = anthropic.Anthropic(api_key=key(), timeout=600, max_retries=3)
    return _client


def ask(model, images, text, max_tokens=16000, tries=3, json_out=True, effort='low'):
    """One call with images (bytes, media type) and text; returns (answer text, usage, seconds). Effort low: the list
    needs looking, not long reasoning (thinking cannot be switched off on the current models)."""
    content = [{'type': 'image', 'source': {'type': 'base64', 'media_type': mt, 'data': base64.b64encode(b).decode()}}
               for b, mt in images]
    content.append({'type': 'text', 'text': text})
    t0 = time.perf_counter()
    r = client().messages.create(model=model, max_tokens=max_tokens, output_config={'effort': effort},
                                 messages=[{'role': 'user', 'content': content}])
    secs = time.perf_counter() - t0
    out = ''.join(b.text for b in r.content if b.type == 'text')
    tin, tout = r.usage.input_tokens, r.usage.output_tokens
    pin, pout = PRICES.get(model, (0, 0))
    usage = {'prompt_tokens': tin, 'completion_tokens': tout, 'cost_usd': round((tin * pin + tout * pout) / 1e6, 6),
             'model_version': r.model, 'stop_reason': r.stop_reason}
    return out, usage, secs
