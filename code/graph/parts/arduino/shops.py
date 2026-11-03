"""The electronics shops a new Arduino part is looked up on.

What it is   one site adapter per shop (parts/ingest.py: SiteAdapter): Adafruit, SparkFun, Pololu and Seeed by their
             pages; Mouser and DigiKey through their official APIs (MOUSER_API_KEY, DIGIKEY_CLIENT_ID / _SECRET),
             since their pages are blocked to programs.
Used for     finding the shop page of a part no card has yet, so its card is made from the shop's own data.
Where        parts/ingest.py (adapters for the registry's "electronics" section), so parts/ingest.py and the
             lookup_part tool (parts/mcp_server.py) reach them.
"""
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

from graph.parts.ingest import SiteAdapter, fetch, rank


class Adafruit(SiteAdapter):
    domain = "adafruit.com"

    def search(self, query):
        raw = fetch("https://www.adafruit.com/search?q=" + urllib.parse.quote(query)) or ""
        found = re.findall(r'href="/product/(\d+)"[^>]*>\s*([^<]{3,120})<', raw)
        return rank(query, [(html.unescape(t), f"https://www.adafruit.com/product/{n}") for n, t in found])


class SparkFun(SiteAdapter):
    domain = "sparkfun.com"

    def search(self, query):
        raw = fetch("https://www.sparkfun.com/catalogsearch/result/?q=" + urllib.parse.quote(query)) or ""
        found = re.findall(r'class="product-item-link"\s+href="([^"]+)"[^>]*>\s*([^<]+)<', raw)
        return rank(query, [(html.unescape(t), u) for u, t in found])


class Pololu(SiteAdapter):
    domain = "pololu.com"

    def search(self, query):
        raw = fetch("https://www.pololu.com/search?query=" + urllib.parse.quote(query)) or ""
        found = re.findall(r'href="(/product/\d+)"[^>]*>Pololu item \d+:\s*(.*?)</a>', raw)  # query words are in <strong>
        return rank(query, [(html.unescape(re.sub(r"<[^>]+>", "", t)), "https://www.pololu.com" + u) for u, t in found])


class Seeed(SiteAdapter):
    """Seeed's search is rendered in the browser, so match the query against product URLs in its sitemap."""
    domain = "seeedstudio.com"

    def search(self, query):
        raw = fetch("https://www.seeedstudio.com/sitemap.xml") or ""
        urls = [u for u in re.findall(r"<loc>([^<]+\.html)</loc>", raw) if "-c-" not in u and "/category/" not in u]
        return rank(query, [(u.rsplit("/", 1)[1][:-5].replace("-", " "), u) for u in urls])


class Mouser(SiteAdapter):
    """Official Search API (MOUSER_API_KEY); plain page requests are bot-blocked."""
    domain = "mouser.com"

    def search(self, query):
        body = json.dumps({"SearchByKeywordRequest": {"keyword": query, "records": 5, "startingRecord": 0}})
        raw = fetch("https://api.mouser.com/api/v1/search/keyword?apiKey=" + os.environ["MOUSER_API_KEY"], body,
                    {"Content-Type": "application/json"})
        parts = (json.loads(raw or "{}").get("SearchResults") or {}).get("Parts") or []
        self._records = {p.get("ProductDetailUrl"): p for p in parts}
        return rank(query, [(p.get("Description", ""), p.get("ProductDetailUrl")) for p in parts])

    def fetch_data(self, url):
        p = getattr(self, "_records", {}).get(url)
        return p and {"title": p.get("Description"), "url": url, "jsonld": {"mpn": p.get("ManufacturerPartNumber")},
                      "text": json.dumps(p)[:6000]}


class DigiKey(SiteAdapter):
    """Official Product Search API v4 (DIGIKEY_CLIENT_ID / _SECRET); pages are bot-blocked."""
    domain = "digikey.com"
    _token = (None, 0)

    def _auth(self):
        token, expires = DigiKey._token
        if token and time.time() < expires:
            return token
        body = urllib.parse.urlencode({"client_id": os.environ["DIGIKEY_CLIENT_ID"], "grant_type": "client_credentials",
                                       "client_secret": os.environ["DIGIKEY_CLIENT_SECRET"]})
        with urllib.request.urlopen(urllib.request.Request("https://api.digikey.com/v1/oauth2/token", data=body.encode()),
                                    timeout=30) as r:
            data = json.loads(r.read())
        DigiKey._token = (data["access_token"], time.time() + int(data.get("expires_in", 600)) - 30)
        return DigiKey._token[0]

    def search(self, query):
        raw = fetch("https://api.digikey.com/products/v4/search/keyword", json.dumps({"Keywords": query, "Limit": 5}),
                    {"Content-Type": "application/json", "X-DIGIKEY-Client-Id": os.environ["DIGIKEY_CLIENT_ID"],
                     "Authorization": "Bearer " + self._auth()})
        products = json.loads(raw or "{}").get("Products") or []
        self._records = {p.get("ProductUrl"): p for p in products}
        return rank(query, [((p.get("Description") or {}).get("ProductDescription", ""), p.get("ProductUrl")) for p in products])

    def fetch_data(self, url):
        p = getattr(self, "_records", {}).get(url)
        return p and {"title": (p.get("Description") or {}).get("ProductDescription"), "url": url,
                      "jsonld": {"mpn": p.get("ManufacturerProductNumber")}, "text": json.dumps(p)[:6000]}
