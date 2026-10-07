"""`lookup_part`: a tool the building Claude can call while it reads a manual (v5), served over MCP (stdio).

  python -m graphgen.parts.mcp_server            (started by `claude -p --mcp-config ...`, not by hand)

The tool runs the same parts pipeline as everything else (RESEARCH.md R22): the Layer 0 store first (free-text
search), then the registry's approved sites (code scraper, then the prompt engine), then the schema gate; a card
found on a site is stored for every later manual. It returns the card (type id, pins, behaviour, electrical facts,
source) so the builder uses real pins instead of guessing. The store is the file in $PARTS_STORE.

The protocol is MCP's stdio transport: one JSON-RPC 2.0 message per line on stdin/stdout. Only what a tool server
needs is implemented: initialize, tools/list, tools/call, ping.
"""
import json
import os
import pathlib
import sys

TOOL = {
    "name": "lookup_part",
    "description": "Find an electronics part in our parts database or, if it is not there, on our approved shop sites "
                   "(Adafruit, SparkFun, Pololu, Seeed). Returns its catalogue card: the type id to use, its pins, "
                   "what is joined inside it, polarity and electrical facts. Call it for every part the catalogue "
                   "does not already list, BEFORE adding a new part type.",
    "inputSchema": {"type": "object", "properties": {
        "name": {"type": "string", "description": "The part as the tutorial names it, e.g. 'DHT11 temperature sensor'"},
        "type_id": {"type": "string", "description": "The type id you would give it, e.g. 'temp-dht11' (optional)"}},
        "required": ["name"]},
}


OPEN_PAGE = {
    "name": "open_page",
    "description": "Open a tutorial web page in a real browser (its JavaScript runs, as for a person) and get what a "
                   "reader sees: the page's text and its circuit images. Use it to read the tutorial you are given a "
                   "link to.",
    "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "description": "The page's address"}},
                    "required": ["url"]},
}


def _allowed(url):
    import urllib.parse
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in os.environ.get("BROWSE_DOMAINS", "").split(",") if d)


def open_page(url):
    """MCP content blocks: the page text, then each circuit image."""
    import base64
    from ..browser import render
    if not _allowed(url):
        return [{"type": "text", "text": f"open_page only opens pages on: {os.environ.get('BROWSE_DOMAINS')}"}]
    page = render(url)
    blocks = [{"type": "text", "text": f"PAGE {url}\n\n{page['text']}"}]
    for data, alt in page["images"]:
        blocks.append({"type": "text", "text": f"Image: {alt or 'figure'}"})
        blocks.append({"type": "image", "data": base64.standard_b64encode(data).decode(), "mimeType": "image/png"})
    return blocks


def _store():
    from .. import catalogue as cat
    from .cards import CardStore
    return CardStore(pathlib.Path(os.environ.get("PARTS_STORE", "graphgen/data/cards_electronics.json")),
                     seed=cat.arduino_seed())


def lookup(name, type_id=None, store=None):
    """Database first, then the approved sites. Returns a dict for the tool result."""
    from . import ingest, tutorial
    store = store or _store()
    card_id, _ = tutorial.match(name, store)
    source = "parts database"
    card = store.get(card_id) if card_id and card_id != "skip" else None
    trail = []
    if card is None:
        card, stats, trail = ingest.ingest_part(name, "electronics", store, wanted_id=type_id, label=name, max_llm_calls=3)
        source = "approved site (added to the database)"
    if card is None:
        return {"found": False, "searched": [f"{site}: {what}" for site, what in trail],
                "advice": "Not in the database or on the approved sites: add it to new_part_types yourself."}
    return {"found": True, "from": source, "type": card["type"], "name": card["name"],
            "ports": [p["name"] for p in card["ports"]][:60], "port_rule": card.get("port_rule"),
            "conducts": card["conducts"], "through": card["through"], "symmetric": card["symmetric"],
            "polarized": card["polarized"], "electrical": card.get("electrical"), "note": card.get("note"),
            "source": (card.get("source") or {}).get("url")}


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:  # a notification (e.g. notifications/initialized): no reply
            continue
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "parts", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": [TOOL] + ([OPEN_PAGE] if os.environ.get("BROWSE_DOMAINS") else [])}
        elif method == "tools/call" and params.get("name") == "open_page":
            try:
                result = {"content": open_page((params.get("arguments") or {}).get("url", "")), "isError": False}
            except Exception as e:
                result = {"content": [{"type": "text", "text": f"could not open the page: {type(e).__name__}: {e}"}],
                          "isError": True}
        elif method == "tools/call" and params.get("name") == "lookup_part":
            args = params.get("arguments") or {}
            try:
                out = lookup(args.get("name", ""), args.get("type_id"))
                result = {"content": [{"type": "text", "text": json.dumps(out)}], "isError": False}
            except Exception as e:  # the builder must get an answer, never a hang
                result = {"content": [{"type": "text", "text": f"lookup failed: {type(e).__name__}: {e}"}], "isError": True}
        elif method == "ping":
            result = {}
        else:
            reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
            print(json.dumps(reply), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
