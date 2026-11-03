"""The site a new LEGO part's card comes from.

What it is   the Rebrickable adapter (parts/ingest.py: SiteAdapter): the local copy of Rebrickable's daily dump
             first, the live API (REBRICKABLE_API_KEY) for a part missing from it. A plain brick, plate or tile
             becomes a card by code; any other part is drafted by Claude from this data.
Used for     the card of a LEGO piece the card store does not have.
Where        parts/ingest.py (adapters for the registry's "lego" section) for parts/ingest.py; parts/cards.py
             (lego_card_code).
"""
import json
import os
import re

from graph.parts.ingest import SiteAdapter, fetch


class Rebrickable(SiteAdapter):
    """LEGO parts: the local copy of Rebrickable's daily dump first; a part missing from it goes to the live API
    (needs REBRICKABLE_API_KEY). Plain bricks, plates and tiles become cards by code."""
    domain = "rebrickable.com"

    def part_number(self, target):
        m = re.search(r"rebrickable\.com/parts/([^/]+)", target)
        return m.group(1) if m else re.sub(r"^lego-", "", target)

    def fetch_data(self, target):
        from graph.parts.lego.inventory import RebrickableDump
        num = self.part_number(target)
        t = RebrickableDump.tables()
        part = t["parts"].get(num)
        if part is None and os.environ.get("REBRICKABLE_API_KEY"):
            raw = fetch(f"https://rebrickable.com/api/v3/lego/parts/{num}/",
                        headers={"Authorization": "key " + os.environ["REBRICKABLE_API_KEY"]})
            part = raw and json.loads(raw)
            part = part and {"part_num": part["part_num"], "name": part["name"], "part_cat_id": str(part["part_cat_id"])}
        if not part:
            return None
        return {"title": part["name"], "url": f"https://rebrickable.com/parts/{num}/", "jsonld": None,
                "text": json.dumps({"part_num": num, "name": part["name"],
                                    "category": t["cats"].get(part.get("part_cat_id"), "?")}),
                "part_num": num, "name": part["name"], "category": t["cats"].get(part.get("part_cat_id"), "?")}

    def deterministic(self, content):
        from graph.parts import part_catalogue
        from graph.parts import cards
        if not content or not part_catalogue.brick_dims(content["name"]):
            return None
        e = part_catalogue.lego_entry(content["part_num"], content["name"])
        return cards.from_engine(e, "lego", {"platform": "rebrickable", "url": content["url"],
                                              "external_id": content["part_num"], "made_by": "code"})
