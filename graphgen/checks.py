"""Checks run on Claude's graph before accepting it. Each problem is written so it can be sent
back to Claude for repair ("issue" text says what is wrong and where).

Electronics (circuit laws, on the logical view):
  E1 supply shorted   a net holds both a supply (5V, 3.3V, VIN) and GND
  E2 pin shorted      a board signal pin sits directly on a supply or GND net
  E3 part shorted     both legs of a two-legged part are on the same net
  E4 leg unconnected  a leg of a two-legged part touches nothing
  E5 floating input   a pin's only other connection is a switch contact, with no pull-up/pull-down
                      resistor (skipped when the code uses INPUT_PULLUP)
LEGO:
  L1 parts page       piece counts differ from the booklet's own parts page (when it has one)
  L2 unknown part     `lego-<number>` is not a real LEGO part number
  L3 separate pieces  the build falls apart into several unconnected groups
Both: the spec rules from validate.py (V2 unused part, V3 incompatible ports, V4 missing/over-used port).
"""
import collections
import re

from . import logical, validate
from .score import family, role

SUPPLY = {"5V", "3V3", "VIN"}
TWO_LEGGED = {"led", "resistor", "button", "buzzer"}


def _board_role(key, types):
    part, port = key.split(":", 1)
    return role("board", port) if family(types.get(part)) == "board" else None


def electronics(flat, catalogue, manual_text=""):
    issues = []
    types = {n["id"]: n["type"] for n in flat["nodes"]}
    nets = logical.nets(flat, catalogue)
    net_of = {k: i for i, n in enumerate(nets) for k in n}
    pullup = "INPUT_PULLUP" in manual_text or "pull_up=True" in manual_text
    for net in nets:
        roles = {_board_role(k, types) for k in net} - {None}
        if "GND" in roles and roles & SUPPLY:
            issues.append(("E1", f"supply shorted to ground: {sorted(net)}"))
        signal = [k for k in net if _board_role(k, types) not in (None, "GND", *SUPPLY)]
        if signal and roles & ({"GND"} | SUPPLY):
            issues.append(("E2", f"board pin {signal} is wired straight to {sorted(roles & ({'GND'} | SUPPLY))} with nothing in between: {sorted(net)}"))
        others = [k for k in net if _board_role(k, types) is None]
        if signal and not pullup and others and all(family(types.get(k.split(':')[0])) == "button" for k in others):
            issues.append(("E5", f"pin {signal} connects only to a button contact {others}: it floats when the button is open "
                                 "(the pull-down/pull-up resistor must join this same pin net)"))
    for n in flat["nodes"]:
        fam = family(n["type"])
        if fam not in TWO_LEGGED:
            continue
        entry = catalogue.get(n["type"]) or {}
        legs = sorted({logical.canonical_port(entry, p["name"]) for p in entry.get("ports", [])})
        if len(legs) != 2:
            continue
        keys = [f"{n['id']}:{leg}" for leg in legs]
        if all(k in net_of for k in keys) and net_of[keys[0]] == net_of[keys[1]]:
            issues.append(("E3", f"{n['id']} ({n['type']}) has both legs on one net, so it is shorted out"))
        for k in keys:
            if k not in net_of:
                issues.append(("E4", f"leg {k} is not connected to anything"))
    return issues


def _components(flat):
    adj = collections.defaultdict(set)
    for e in flat["edges"]:
        if e["type"] in ("joined", "contact") and e["u"] != e["v"]:
            adj[e["u"]].add(e["v"])
            adj[e["v"]].add(e["u"])
    seen, groups = set(), 0
    for n in flat["nodes"]:
        if n["id"] in seen:
            continue
        groups += 1
        stack = [n["id"]]
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(adj[x] - seen)
    return groups


def booklet_inventory(pdf_bytes):
    """Element ID -> count from a booklet's own parts page(s), if it has any (text like '4x' then '300401')."""
    if not pdf_bytes:
        return {}
    import pymupdf
    inv = collections.Counter()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        tokens = page.get_text().split()
        if sum(1 for t in tokens if re.fullmatch(r"\d{6,7}", t)) < 5:
            continue  # not an inventory page
        for a, b in zip(tokens, tokens[1:]):
            m = re.fullmatch(r"(\d{1,3})x", a)
            if m and re.fullmatch(r"\d{6,7}", b):
                inv[b] += int(m.group(1))
    return dict(inv)


def lego(flat, part_nums, booklet_inv=None):
    issues = []
    if booklet_inv:
        built = collections.Counter()
        for n in flat["nodes"]:
            m = re.search(r"(\d{6,7})", f"{n['type']} {n.get('label') or ''}")
            if m:
                built[m.group(1)] += 1
        wrong = [(el, want, built.get(el, 0)) for el, want in booklet_inv.items() if built.get(el, 0) != want]
        extra = [el for el in built if el not in booklet_inv]
        if wrong or extra:
            issues.append(("L1", "piece counts differ from the booklet's parts page: "
                           + ", ".join(f"element {el}: page says {w}, graph has {b}" for el, w, b in wrong[:15])
                           + (f"; elements not on the page: {extra[:10]}" if extra else "")))
    for n in flat["nodes"]:
        m = re.match(r"^lego-([0-9a-z]+)$", n["type"].lower())
        if m and not re.fullmatch(r"\d{6,7}", m.group(1)) and m.group(1) not in part_nums:
            issues.append(("L2", f"{n['id']}: '{n['type']}' is not a real LEGO part number"))
    groups = _components(flat)
    if groups > 1:
        issues.append(("L3", f"the build is {groups} separate groups of pieces; connect them unless the booklet really builds separate models"))
    return issues


def run(flat, catalogue, domain, manual_text="", part_nums=frozenset(), booklet_inv=None):
    spec = [(r, m) for r, m in validate.validate(flat, catalogue)]
    if domain == "arduino":
        return spec + electronics(flat, catalogue, manual_text)
    return spec + lego(flat, part_nums, booklet_inv)


def repair_message(issues, limit=40):
    lines = [f"- [{rule}] {msg}" for rule, msg in issues[:limit]]
    more = f"\n- … and {len(issues) - limit} more" if len(issues) > limit else ""
    return ("Checking your graph found these problems:\n" + "\n".join(lines) + more +
            "\n\nReturn the COMPLETE corrected graph (same format). Fix every real problem; if one is not a real "
            "problem for this manual (e.g. the booklet truly builds separate models), keep that part and say why in notes.")
