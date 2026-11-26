"""A new board's geometry reference from the web: an openly licensed, straight-down photo on Wikimedia Commons, made
into a reference by code and put into the database under its part (26 Nov 2026, the learner's idea).

When the parts check sees an Uno-shaped board (female headers along both long edges) that has no reference, this runs in
the background:
1. search Commons for photos of the board (only free licences: CC0, CC BY, CC BY-SA, public domain; not the angled,
   back, side or enclosure ones by their names);
2. for each candidate, Opus looks at it with a pixel grid: is it this board, straight from above, and where are the
   first and last openings of each header row (and the labels printed by them, which say the row's layout);
3. code fits each row's openings exactly (the comb, only a third of an opening either way of Opus's ends);
4. it is kept only when all of these agree: the openings stand out clearly (contrast at least 32: a row under it is
   dropped, and the digital row must be there), the rows give the same spacing, Opus confirms the drawn names on
   close-ups of every row end, and no board already known is now mistaken for it (or it for them). Measured on the 5
   Commons photos made into references by hand: every pin kept within 0.22 of an opening (Opus's check alone let a
   row 0.85 off through: the contrast is what stops it);
5. saved in the repo's references (openly licensed: in git, with its credit) and in the database (status "auto",
   with the photo's address, author and licence), until a person looks at it.
If nothing on Commons will do, the board keeps its layout as numbers only.

    find(board_id, name) -> {"ok", "why", "photo", "rows", "tried", "cost_usd"}
    python -m validator.board_ref_web arduino-zero "Arduino Zero"
"""
import json
import pathlib
import re
import sys
import threading
import urllib.parse
import urllib.request

import cv2
import numpy as np

from validator import board as _board, uno_overlay as U

MODEL = "claude-opus-5-5"
API = "https://commons.wikimedia.org/w/api.php"
UA = "pinpoint-parts/1.0 (final year project; board reference photos)"
FREE = re.compile(r"^(cc0|cc[- ]by(-sa)?( \d\.\d)?|public domain|pd.*)$", re.I)
SKIP = re.compile(r"perspective|diagonal|back|bottom|side|enclosure|case|angle|schematic|pinout|logo|\.pdf$|\.svg$", re.I)
DOWNLOADS = U.LOCAL_REFS.parent / "commons"
LOG = U.LOCAL_REFS.parent / "web_refs.json"  # what was tried for each board, and why (not searched again)
MIN_CONTRAST = 32  # a row's openings against the plastic between them (see from_photo)
UNO_SHAPED = {"arduino-uno", "arduino-uno-r4-minima", "arduino-uno-r4-wifi", "arduino-uno-wifi-rev2",
              "arduino-leonardo", "arduino-duemilanove", "arduino-zero", "arduino-due", "arduino-due-r3",
              "arduino-mega", "arduino-yun", "arduino-yun-headers"}

LOOK = """Photo 1 is a photo found on the web for the board "{name}", with a pixel grid: a thin line every 50 pixels,
numbered along the top and the left edge.
First: is it that board (or the same board under another name), its component side, seen straight from above (its
edges square to the photo, not at an angle)?
Then find its two rows of female header sockets (black plastic strips with square openings) along the long edges:
- "digital": pins 0..13, with AREF and GND (and on newer boards SDA, SCL) at one end;
- "power": the power and analog row (IOREF, RESET, 3V3, 5V, GND, VIN, then A0..A5, maybe more).
For each row give the pixel centre of its FIRST and LAST opening (read x and y off the grid as exactly as you can),
the label printed on the board next to each of those two openings ("" if none is printed), and how many openings
the row has in all (count them).
Answer ONLY with JSON: {{"same_board": true, "straight": true, "digital": {{"first": [x, y], "first_label": "",
"last": [x, y], "last_label": "", "openings": 0}}, "power": {{...the same...}}}}  (a row you cannot see: null)"""

VERIFY = """The photos are close-ups of the two ends of each header row of an Arduino-style board seen from above (black
plastic strips with square openings). Code has drawn a short yellow line, with a yellow name, at the opening it thinks
is each end one. IGNORE the labels printed on the board (they can sit beside the openings). Look only at the black
header: does each yellow line point at the middle of the very LAST opening at that end of the strip (not the one
before it, not past the end, not between two openings)?
Answer ONLY with JSON: {"ok": true or false, "ends": [{"photo": 1, "right": true, "off": "a few words"}], "why": ""}"""


# ---- Commons ---------------------------------------------------------------------------------------------------------
def _get(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def search(name, limit=12):
    """Commons photos for a board: [{"title", "url", "licence", "author", "page", "width"}], free licences only,
    straight-looking titles first, bigger first."""
    hits = _get({"action": "query", "list": "search", "srnamespace": 6, "srlimit": limit, "srsearch": name})
    titles = [h["title"] for h in hits.get("query", {}).get("search", [])]
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in ("arduino", "board")]
    titles = [t for t in titles if not SKIP.search(t) and all(w in t.lower().replace("ú", "u") for w in words)]
    if not titles:
        return []
    info = _get({"action": "query", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
                 "titles": "|".join(titles[:10])})
    out = []
    for p in info.get("query", {}).get("pages", {}).values():
        i = (p.get("imageinfo") or [{}])[0]
        m = i.get("extmetadata") or {}
        lic = (m.get("LicenseShortName") or {}).get("value", "")
        if not FREE.match(lic.strip()):
            continue
        author = re.sub(r"<[^>]+>", "", (m.get("Artist") or {}).get("value", "")).strip()
        out.append({"title": p["title"], "url": i.get("thumburl") or i.get("url"), "licence": lic, "author": author,
                    "page": i.get("descriptionurl") or "", "width": i.get("width") or 0})
    return sorted(out, key=lambda c: -c["width"])


def download(c):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", c["title"].split(":", 1)[-1])
    path = DOWNLOADS / name
    if not path.exists():
        req = urllib.request.Request(c["url"], headers={"User-Agent": UA})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    img = cv2.imread(str(path))
    if img is None:
        return None
    jpg = path.with_suffix(".jpg")
    if path.suffix.lower() != ".jpg":
        cv2.imwrite(str(jpg), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return jpg


# ---- one photo -> rows -------------------------------------------------------------------------------------------
def _grid(img, step=50):
    g = img.copy()
    h, w = g.shape[:2]
    for x in range(0, w, step):
        cv2.line(g, (x, 0), (x, h), (0, 255, 255) if x % 250 else (0, 160, 255), 1)
        if x % 100 == 0:
            for col, th in (((0, 0, 0), 3), ((0, 255, 255), 1)):
                cv2.putText(g, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, th)
    for y in range(0, h, step):
        cv2.line(g, (0, y), (w, y), (0, 255, 255) if y % 250 else (0, 160, 255), 1)
        if y % 100 == 0:
            for col, th in (((0, 0, 0), 3), ((0, 255, 255), 1)):
                cv2.putText(g, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, th)
    return g


def _jpeg(img, q=88):
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()


def _json(text):
    i, j = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[i:j + 1])
    except ValueError:
        return {}


def layout_of(kind, r, board_id=""):
    """A row's layout from its two end labels and its count, and whether its ends must be swapped (the layout starts
    at SCL / AREF, or at NC / IOREF / RESET / BOOT): (layout, swap) or (None, False)."""
    a, b = str(r.get("first_label") or "").upper().strip(), str(r.get("last_label") or "").upper().strip()
    n = int(r.get("openings") or 0)
    if kind == "digital":
        swap = b in {"SCL", "SDA", "AREF"} or (a in {"0", "D0", "RX", "RX0", "RX<0", "RX←0"} and b not in {"0", "D0"})
        first = b if swap else a
        if n >= 24:
            return "mega", swap
        if first in {"SCL", "SDA"} or n in (17, 18, 19):
            return "uno-r3", swap
        if first == "AREF" or n in (15, 16):
            return "duemilanove", swap
        return None, False
    swap = (a.startswith("A") and a[1:].isdigit()) or a in {"CANTX", "DAC1"}
    first, last = (b, a) if swap else (a, b)
    if last in {"CANTX", "CANRX"}:
        return "power-analog-due", swap
    if n >= 22:
        return "power-analog-mega", swap
    if n >= 13:
        return ("power-analog-boot" if first == "BOOT" else "power-analog-8"), swap
    if n >= 11:
        return "power-analog-6", swap
    return None, False


def _row(ref, name, first, last):
    """The row's openings near the ends given (the comb only nudges, a third of an opening): the row or None."""
    order, idx = U.layout(name)
    a, b = np.array(first, float), np.array(last, float)
    if np.linalg.norm(b - a) < 100:
        return None
    u = (b - a) / np.linalg.norm(b - a)
    nrm = np.array([-u[1], u[0]])
    if (a - np.array([ref.shape[1] / 2, ref.shape[0] / 2])) @ nrm < 0:
        nrm = -nrm
    pitch = np.linalg.norm(b - a) / idx[order[-1]]
    got = U.openings(ref, a, u, nrm, pitch, order, idx, across_range=(-0.4, 0.4), spread=0.05, along_range=0.33)
    if got is None:
        return None
    pins, fit = got
    return {"layout": name, "from": "openings", "fit": fit,
            "pins": {p: [round(float(v), 1) for v in pins[p]] for p in order}}


def _draw(ref, rows):
    out = ref.copy()
    mid = np.array([ref.shape[1] / 2, ref.shape[0] / 2])
    for row in rows:
        order, idx = U.layout(row["layout"])
        pins = {p: np.array(v, float) for p, v in row["pins"].items()}
        a, b = pins[order[0]], pins[order[-1]]
        u = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-u[1], u[0]])
        if (a - mid) @ nrm < 0:
            nrm = -nrm
        pitch = np.linalg.norm(b - a) / idx[order[-1]]
        for p, xy in pins.items():
            name = p.rstrip(".")
            cv2.line(out, tuple(int(v) for v in xy + nrm * pitch * 0.6), tuple(int(v) for v in xy + nrm * pitch * 1.3),
                     (0, 230, 255), 2)
            lab = xy + nrm * pitch * 1.9
            (tw, th), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            x, y = int(lab[0] - tw / 2), int(lab[1] + th / 2)
            cv2.rectangle(out, (x - 3, y - th - 3), (x + tw + 3, y + 4), (0, 230, 255), -1)
            cv2.putText(out, name, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    return out


def _ends(drawn, rows, k=3.0):
    out = []
    for row in rows:
        order, idx = U.layout(row["layout"])
        a, b = np.array(row["pins"][order[0]]), np.array(row["pins"][order[-1]])
        pitch = np.linalg.norm(b - a) / idx[order[-1]]
        for p in (a, b):
            r = int(pitch * 3.2)
            c = drawn[int(max(0, p[1] - r)):int(p[1] + r), int(max(0, p[0] - r)):int(p[0] + r)]
            if c.size:
                out.append(cv2.resize(c, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC))
    return out


def _confused(board_id, ref):
    """With this reference added, is any known board's own photo now taken for another, or this photo for one of
    them? [what went wrong]."""
    known = [r for r in U._load_refs() if r["board"] != board_id]
    k, d = U._features(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY))
    me = {"board": board_id, "image": ref, "kp": k, "des": d, "rows": []}
    saved, U._refs = U._refs, known + [me]
    try:
        bad = []
        for r in known + [me]:
            got = U.overlay(r["image"])
            if not got or got[0]["board"] != r["board"]:
                bad.append(f"{r['board']} read as {got[0]['board'] if got else 'nothing'}")
        return bad
    finally:
        U._refs = saved


def from_photo(board_id, name, photo, ask):
    """Rows for a board from one photo, and every check: {"ok", "why", "rows", "ref", "cost"}."""
    cost = 0.0
    img = _board.load(str(photo))
    ref, _, _ = U.crop(img)
    if max(ref.shape[:2]) < 1000:
        return {"ok": False, "why": "too small", "cost": cost}
    out, st, _ = ask(MODEL, [(_jpeg(_grid(ref)), "image/jpeg")], LOOK.format(name=name), max_tokens=4000, effort="medium")
    cost += st.get("cost_usd") or 0
    f = _json(out)
    if f.get("same_board") is not True or f.get("straight") is not True:
        return {"ok": False, "why": "not this board, or not straight from above", "cost": cost}
    rows = []
    for kind in ("digital", "power"):
        r = f.get(kind)
        if not isinstance(r, dict) or not r.get("first") or not r.get("last"):
            continue
        lay, swap = layout_of(kind, r, board_id)
        if not lay:
            continue
        a, b = (r["last"], r["first"]) if swap else (r["first"], r["last"])
        # both ways round: the gap between blocks (8 | 7, VIN | A0) sits off-centre, so the wrong way puts it on an
        # opening and scores lower; the labels Opus reads say the way only where the board prints them (26 Nov: the
        # Yún prints none by its headers, and one run read its digital row the wrong way round)
        both = [x for x in (_row(ref, lay, a, b), _row(ref, lay, b, a)) if x]
        if both:
            rows.append(max(both, key=lambda x: x["fit"]["contrast"]))
    # a row whose openings do not stand out is dropped (26 Nov, 5 Commons photos against references made by hand: rows
    # at contrast 37-121 within 0.22 of an opening, the Due's power row at 26 was 0.85 off and Opus's check passed
    # it); the digital row, where most wires go, must be there
    weak = [r["layout"] for r in rows if r["fit"]["contrast"] < MIN_CONTRAST]
    rows = [r for r in rows if r["fit"]["contrast"] >= MIN_CONTRAST]
    kinds = [r["layout"] for r in rows]
    if not any(k in ("uno-r3", "duemilanove", "mega") for k in kinds):
        return {"ok": False, "why": f"the digital header was not found clearly ({kinds}; weak: {weak})", "cost": cost,
                "rows": rows}
    # the rows run the same way: pin 0 and A5 (each row's last) are both at the end away from the USB socket
    dirs = []
    for r in rows:
        order, _ = U.layout(r["layout"])
        d = np.array(r["pins"][order[-1]]) - np.array(r["pins"][order[0]])
        dirs.append(d / np.linalg.norm(d))
    if any(float(dirs[0] @ d) < 0.9 for d in dirs[1:]):
        return {"ok": False, "why": "the header rows run opposite ways", "cost": cost, "rows": rows}
    sp = [r["fit"]["spacing"] for r in rows]
    if max(sp) > 1.03 * min(sp):
        return {"ok": False, "why": f"the rows disagree on the spacing ({sp})", "cost": cost, "rows": rows}
    out2, st2, _ = ask(MODEL, [(_jpeg(e), "image/jpeg") for e in _ends(_draw(ref, rows), rows)], VERIFY,
                       max_tokens=2000, effort="medium")
    cost += st2.get("cost_usd") or 0
    v = _json(out2)
    if v.get("ok") is not True or any(e.get("right") is False for e in v.get("ends") or []):
        return {"ok": False, "why": f"the ends were not on the last openings: {v.get('why') or out2[:100]}",
                "cost": cost, "rows": rows}
    bad = _confused(board_id, ref)
    if bad:
        return {"ok": False, "why": f"boards mixed up: {bad}", "cost": cost, "rows": rows}
    return {"ok": True, "why": v.get("why") or "", "rows": rows, "ref": ref, "cost": cost}


def _log(board_id, entry):
    import time
    entry = {**entry, "when": int(time.time())}
    try:
        log = json.loads(LOG.read_text())
    except (OSError, ValueError):
        log = {}
    log[board_id] = entry
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=1))


def _credit(board_id, c):
    p = U.REFS / "CREDITS.md"
    line = f"| {board_id} (found by code, not yet checked) | {c['page']} | {c['author']} | {c['licence']} |\n"
    text = p.read_text() if p.exists() else ""
    if c["page"] not in text:
        p.write_text(text.rstrip("\n") + "\n" + line)


def find(board_id, name, save=True, ask=None, candidates=None):
    """Look for a photo of board_id on Commons and make it a reference: the first candidate that passes every check
    is saved (repo + database, status "auto"). candidates: skip the search (tests, measuring)."""
    if ask is None:
        from gather.gather_vlm import ask
    tried, cost = [], 0.0
    try:
        cands = candidates if candidates is not None else search(name)
    except Exception as e:
        cands, tried = [], [{"photo": None, "why": f"search failed: {e}"}]
    for c in cands[:4]:
        try:
            photo = c.get("path") or download(c)
        except Exception as e:
            tried.append({"photo": c.get("title"), "why": f"download failed: {e}"})
            continue
        if photo is None:
            continue
        r = from_photo(board_id, name, photo, ask)
        cost += r["cost"]
        tried.append({"photo": c.get("title"), "why": r["why"] if not r["ok"] else "kept"})
        if not r["ok"]:
            continue
        result = {"ok": True, "why": r["why"], "photo": c.get("title"), "rows": r["rows"], "tried": tried,
                  "cost_usd": round(cost, 4)}
        if save:
            cv2.imwrite(str(U.REFS / f"{board_id}.jpg"), r["ref"], [cv2.IMWRITE_JPEG_QUALITY, 92])
            meta = {"photo": c.get("title", "").split(":", 1)[-1],
                    "source": f"{c.get('page')} ({c.get('author')}, {c.get('licence')})",
                    "made": "auto", "status": "auto", "rows": r["rows"]}
            (U.REFS / f"{board_id}.json").write_text(json.dumps(meta, indent=1))
            _credit(board_id, c)
            U._saved(board_id)
            _log(board_id, {k: v for k, v in result.items() if k != "rows"})
        return result
    result = {"ok": False, "why": "no photo on Commons would do", "tried": tried, "cost_usd": round(cost, 4)}
    if save:
        _log(board_id, result)
    return result


def wanted(board_id, uno_layout=False):
    """An Uno-shaped board with no reference (files or database) that was not looked for already."""
    if not (board_id in UNO_SHAPED or uno_layout):
        return False
    if any(r["board"] == board_id for r in U._load_refs()):
        return False
    import time
    try:
        e = json.loads(LOG.read_text()).get(board_id)
    except (OSError, ValueError):
        e = None
    # looked for and nothing would do: again after 30 days (photos are added to Commons over time)
    return e is None or (not e.get("ok") and time.time() - e.get("when", 0) > 30 * 86400)


def in_background(board_id, name, uno_layout=False):
    """find() on its own thread when the board wants one (never holds up the learner's check). True when started."""
    if not wanted(board_id, uno_layout):
        return False

    def go():
        try:
            r = find(board_id, name)
            print(f"board reference for {board_id}: {'made from ' + str(r.get('photo')) if r['ok'] else r['why']} "
                  f"(${r.get('cost_usd')})", file=sys.stderr)
        except Exception as e:
            print(f"board reference for {board_id}: failed ({e})", file=sys.stderr)
    threading.Thread(target=go, daemon=True).start()
    return True


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in find(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]).items()
                      if k != "rows"}, indent=1))
