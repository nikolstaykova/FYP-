"""Free-text search over part cards, modelled on MongoDB's `$text` search.

  index = TextIndex({"part_type_id": 10, "aliases": 8, "display_name": 5, "category": 2})
  index.add(doc_id, doc)
  index.search('arduino nano 33 iot')            -> [Hit(id, score, coverage)], best first
  index.search('"nano 33" -ble')                 quoted phrase must appear; -term excludes

As in MongoDB: a text index over several weighted fields; text split on spaces and punctuation, lowercased,
language stop words dropped, words stemmed; the query is an OR of its terms (a document matches if it has any),
"quoted phrases" are required, -terms exclude; documents are ranked by a text score summed over fields:
weight × term-frequency coefficient (repeats of a term count, with diminishing return, scaled by field length).
Added for our use: `coverage`, the share of the query's terms a hit contains, so a caller can say
"no card is this part" instead of taking any hit (MongoDB leaves that to the application).
"""
import collections
import math
import re
from dataclasses import dataclass

STOP = set("""a an and are as at be but by for from has have in into is it its of on or that the this to was were
will with x pcs pc piece pieces generic optional any other e.g eg etc board module kit""".split())


def stem(w):
    """A small English stemmer (Porter step 1 style): plurals and -ing/-ed. Numbers and model codes are kept."""
    if re.search(r"\d", w) or len(w) <= 3:
        return w
    for suf, rep in (("sses", "ss"), ("ies", "y"), ("ing", ""), ("ed", ""), ("es", "e"), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[: len(w) - len(suf)] + rep
    return w


def tokens(text):
    """Lowercase, split on anything not a letter/digit (hc-sr04 -> hc, sr04, hcsr04), drop stop words, stem."""
    out = []
    for raw in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower()):
        parts = raw.split("-")
        if len(parts) > 1 and any(re.search(r"\d", p) for p in parts):
            out.append("".join(parts))  # model codes are searched joined too: hc-sr04 -> hcsr04
        out += parts
    return [stem(t) for t in out if t not in STOP]


@dataclass
class Hit:
    id: str
    score: float
    coverage: float


class TextIndex:
    def __init__(self, weights):
        self.weights = weights
        self.docs = {}  # id -> {field: Counter(term)}
        self.text = {}  # id -> lowercased text of all fields, for phrase checks

    def add(self, doc_id, doc):
        fields = {}
        for f in self.weights:
            v = doc.get(f)
            v = " ".join(v) if isinstance(v, (list, tuple)) else (v or "")
            fields[f] = collections.Counter(tokens(v.replace("-", " ") + " " + v))
        self.docs[doc_id] = fields
        self.text[doc_id] = " ".join(" ".join(doc.get(f)) if isinstance(doc.get(f), list) else str(doc.get(f) or "")
                                     for f in self.weights).lower()

    @staticmethod
    def parse(query):
        phrases = [p.lower() for p in re.findall(r'"([^"]+)"', query)]
        rest = re.sub(r'"[^"]+"', " ", query)
        negs = {stem(t) for t in re.findall(r"(?:^|\s)-([a-z0-9]+)", rest.lower())}
        rest = re.sub(r"(?:^|\s)-[a-z0-9]+", " ", rest)
        terms = list(dict.fromkeys(tokens(rest + " " + " ".join(phrases))))
        return terms, phrases, negs

    def search(self, query, limit=5):
        terms, phrases, negs = self.parse(query)
        if not terms:
            return []
        total_w = sum(self.weights.values())
        hits = []
        for doc_id, fields in self.docs.items():
            if any(t in c for c in fields.values() for t in negs):
                continue
            if any(p not in self.text[doc_id] for p in phrases):
                continue
            score, found = 0.0, set()
            for f, counts in fields.items():
                n = sum(counts.values()) or 1
                for t in terms:
                    if counts[t]:
                        found.add(t)
                        # weight × frequency coefficient: more repeats help less, longer fields dilute
                        score += self.weights[f] * (1 + math.log(counts[t])) * (0.5 + 0.5 / math.sqrt(n))
            if found:
                cov = len(found) / len(terms)
                hits.append(Hit(doc_id, round(score / total_w, 4), round(cov, 3)))
        return sorted(hits, key=lambda h: (-h.score, -h.coverage))[:limit]
