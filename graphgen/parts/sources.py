"""Site adapters (the ingestion layer of RESEARCH.md R22). Each adapter only knows how to reach one source:

  domain                    host the router matches a URL against
  search(query)             -> [(title, url)] candidate pages, best first
  fetch_data(target)        -> {title, url, jsonld, text} cleaned content, or None
  deterministic(content)    -> a Layer 0 card made by code, or None (then the prompt engine is used)
  get_prompt_instructions() -> the site's extra rules for the prompt engine (from registry.json)

Everything else (where to look, in what order, what the prompt says) is data in registry.json. Fetched pages
are cached under research/raw/parts/ (git-ignored).
"""
import hashlib
import html
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "research" / "raw" / "parts"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
REGISTRY = json.loads((pathlib.Path(__file__).parent / "registry.json").read_text())


def fetch(url, data=None, headers=None, timeout=30):
    """GET (or POST `data`), cached on disk by URL + body. Returns text or None on an HTTP error."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha1((url + (data or "")).encode()).hexdigest() + ".html")
    if path.exists():
        return path.read_text(errors="replace")
    req = urllib.request.Request(url, data=data.encode() if data else None,
                                 headers={"User-Agent": UA, "Accept-Language": "en", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    path.write_text(text)
    return text


def clean(raw, limit=6000):
    """HTML -> (JSON-LD Product dict or None, plain text without scripts, styles, header, nav, footer)."""
    product = None
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw, re.S | re.I):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "Product":
                product = {k: item.get(k) for k in ("name", "description", "sku", "mpn", "brand") if item.get(k)}
    body = re.sub(r"<(script|style|noscript|svg|header|nav|footer)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
    return product, text[:limit]


def words(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower())) - {"the", "a", "an", "with", "for", "and", "of", "x"}


def rank(query, candidates):
    """Candidates sorted by word overlap with the query; ones sharing no word are dropped."""
    q = words(query)
    unique = {u: t.strip() for t, u in candidates if u}  # one entry per page
    scored = [(len(q & words(t)) / (len(q) or 1), t, u) for u, t in unique.items()]
    return [(t, u) for s, t, u in sorted(scored, key=lambda x: -x[0]) if s > 0]


def looks_like_product(page):
    """Existence check before spending tokens: a real product page with specs."""
    if not page or len(page["text"]) < 300:
        return False
    if page.get("jsonld"):
        return True
    return any(k in page["text"].lower() for k in ("sku", "datasheet", "pinout", "technical details", "specifications", "in stock"))


class SiteAdapter:
    name = domain = ""
    row = {}

    def available(self):
        return all(os.environ.get(v) for v in self.row.get("needs", []))

    def search(self, query):
        return []

    def fetch_data(self, url):
        raw = fetch(url)
        if not raw:
            return None
        product, text = clean(raw)
        title = (product or {}).get("name") or (re.search(r"<title>(.*?)</title>", raw, re.S | re.I) or [None, ""])[1]
        return {"title": html.unescape(title).strip(), "url": url, "jsonld": product, "text": text}

    def deterministic(self, content):
        return None

    def get_prompt_instructions(self):
        return self.row.get("prompt_instructions", "")


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


class Rebrickable(SiteAdapter):
    """LEGO parts: the local copy of Rebrickable's daily dump first; a part missing from it goes to the live API
    (needs REBRICKABLE_API_KEY). Plain bricks, plates and tiles become cards by code."""
    domain = "rebrickable.com"

    def part_number(self, target):
        m = re.search(r"rebrickable\.com/parts/([^/]+)", target)
        return m.group(1) if m else re.sub(r"^lego-", "", target)

    def fetch_data(self, target):
        from .lego import RebrickableDump
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
        from .. import catalogue as cat
        from . import schema
        if not content or not cat.brick_dims(content["name"]):
            return None
        e = cat.lego_entry(content["part_num"], content["name"])
        return schema.from_engine(e, "lego", {"platform": "rebrickable", "url": content["url"],
                                              "external_id": content["part_num"], "made_by": "code"})


class LDrawOMR(SiteAdapter):
    """3D models of official sets (Path A): local copy first, else the LDraw Official Model Repository."""
    domain = "ldraw.org"

    def fetch_data(self, set_num):
        local = ROOT / "research" / "raw" / "lego" / f"{set_num}.mpd"
        if local.exists():
            return {"title": set_num, "url": str(local), "jsonld": None, "text": local.read_text(errors="replace")}
        raw = fetch(f"https://library.ldraw.org/library/omr/{set_num}.mpd")
        return raw and raw.lstrip().startswith("0") and {"title": set_num, "url": "ldraw omr", "jsonld": None, "text": raw}


GUIDES = ROOT / "research" / "raw" / "lego_text"


def _html_text(fragment):
    """HTML -> plain text with one line per paragraph, heading or list item."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", fragment, flags=re.S | re.I)
    t = re.sub(r"<(br|/p|/h\d|/li|/div|/tr)[^>]*>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\u00a0]+", " ", t)).strip()


class TextGuide(SiteAdapter):
    """Text building instructions written for blind builders (step by step: piece, size, colour, studs, place).
    fetch_data(set number, e.g. '60452-1') -> {title, url, jsonld, text} or None; kept in research/raw/lego_text.
    The site's set index is read once per process (index())."""
    site = ""
    _index = None

    def index(self):
        return {}

    def text_of(self, url):
        return None

    def fetch_data(self, set_num):
        local = GUIDES / f"{set_num}-{self.name}.txt"
        if local.exists():
            text = local.read_text(errors="replace")
            return {"title": set_num, "url": text.split("\n", 1)[0][len("SOURCE "):], "jsonld": None,
                    "text": text.split("\n", 1)[1]}
        if type(self)._index is None:
            try:
                type(self)._index = self.index()
            except Exception:
                type(self)._index = {}
        url = type(self)._index.get(set_num.split("-")[0])
        text = url and self.text_of(url)
        if not text or len(text) < 500:
            return None
        GUIDES.mkdir(parents=True, exist_ok=True)
        local.write_text(f"SOURCE {url}\n{text}")
        return {"title": set_num, "url": url, "jsonld": None, "text": text}


class LegoAudioBraille(TextGuide):
    """LEGO's own Audio & Braille instructions: one screen-reader page per set, /lego-<set>-<name>-readscr/."""
    domain = "legoaudioinstructions.com"

    def index(self):
        out = {}
        for page in range(1, 20):
            raw = fetch(f"https://legoaudioinstructions.com/wp-json/wp/v2/pages?per_page=100&page={page}&_fields=slug,link")
            rows = json.loads(raw) if raw and raw.lstrip().startswith("[") else []
            for r in rows:
                m = re.match(r"lego-(\d{4,6})-.*-readscr$", r["slug"])
                if m:
                    out.setdefault(m.group(1), r["link"])
            if len(rows) < 100:
                break
        return out

    def text_of(self, url):
        raw = fetch(url)
        main = raw and re.search(r"<main.*?</main>", raw, re.S | re.I)
        return _html_text(main.group(0) if main else raw or "")


class BricksForTheBlind(TextGuide):
    """Bricks for the Blind (volunteers, about 700 sets): each set's text as a .docx named '<set>-<name>.docx'."""
    domain = "bricksfortheblind.org"

    def index(self):
        out = {}
        for page in range(1, 30):
            raw = fetch(f"https://bricksfortheblind.org/wp-json/wp/v2/instructions?per_page=100&page={page}&_fields=slug,content")
            rows = json.loads(raw) if raw and raw.lstrip().startswith("[") else []
            for r in rows:
                for f in re.findall(r'(https?://[^"\s]+/uploads/[^"\s]+?\.docx)', r["content"]["rendered"]):
                    m = re.match(r"(\d{4,6})\b", f.rsplit("/", 1)[-1])
                    if m:
                        out.setdefault(m.group(1), f)
            if len(rows) < 100:
                break
        return out

    def text_of(self, url):
        import io
        import zipfile
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                doc = zipfile.ZipFile(io.BytesIO(r.read())).read("word/document.xml").decode("utf-8", "replace")
        except (OSError, zipfile.BadZipFile, KeyError):
            return None
        paras = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in re.findall(r"<w:p[ >].*?</w:p>", doc, re.S)]
        return "\n".join(html.unescape(p).strip() for p in paras if p.strip())


def text_guides(set_num):
    """Every text guide the registry's lego_text_guides sources have for a set (each site is checked), [] if none."""
    out = []
    for a in adapters("lego_text_guides"):
        got = a.fetch_data(set_num)
        if got:
            out.append({**got, "source": a.name})
    return out


ADAPTER_CLASSES = {c.__name__: c for c in (Adafruit, SparkFun, Pololu, Seeed, Mouser, DigiKey, Rebrickable, LDrawOMR,
                                           LegoAudioBraille, BricksForTheBlind)}


def adapters(domain):
    """Adapters for a registry section, in registry order, each carrying its registry row."""
    out = []
    for row in REGISTRY.get(domain, []):
        cls = ADAPTER_CLASSES.get(row["adapter"])
        if cls:
            a = cls()
            a.name, a.row = row["name"], row
            out.append(a)
    return out


def route(url):
    """Registry router: the adapter whose domain the URL belongs to, or None."""
    host = urllib.parse.urlparse(url).netloc.lower()
    for section in ("electronics", "lego", "lego_models", "lego_text_guides"):
        for a in adapters(section):
            if a.domain and host.endswith(a.domain):
                return a
    return None
