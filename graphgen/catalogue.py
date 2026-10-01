"""The part catalogue (GRAPH_SPEC §6): one entry per part TYPE, shared by every copy.

Entries have a `status`:
  verified    hand-checked (Arduino cards from CircuitQuest's library)
  imported    created automatically from a trusted source (LEGO parts from LDraw)
  unverified  drafted by the model the first time a manual used the part

"Store on demand": `Catalogue.add_drafts` adds model-drafted entries only for
types the catalogue did not have; `lego_entries` imports only the LDraw parts
a model actually uses.
"""
import copy
import glob
import json
import pathlib
import re

CQ = pathlib.Path.home() / "Desktop" / "CirquitQuest"

UNO_PORTS = [str(n) for n in range(14)] + [f"A{n}" for n in range(6)] + [
    "GND.1", "GND.2", "GND.3", "5V", "3.3V", "VIN", "AREF", "IOREF", "RESET"]


def _entry(type_, name, category, ports, *, conducts=(), through=(), symmetric=(), polarized=False,
           connector=False, alias=None, status="verified", mirror_of=None, rotation="none", **extra):
    return {"type": type_, "name": name, "category": category,
            "ports": [{"name": p, "kind": k} for p, k in ports],
            "conducts": [list(g) for g in conducts], "through": [list(g) for g in through],
            "symmetric": [list(g) for g in symmetric], "polarized": polarized, "connector": connector,
            "alias": alias, "mirror_of": mirror_of, "rotation_symmetry": rotation, "status": status, **extra}


def arduino_seed():
    """Verified Arduino entries converted from CircuitQuest's library cards."""
    entries = {}
    for path in sorted(glob.glob(str(CQ / "library" / "parts" / "*.json"))):
        card = json.loads(pathlib.Path(path).read_text())
        cid, sub = card["id"], card.get("subtype", "")
        if cid.startswith("resistor-"):
            cid = "resistor"  # one type; the value is an instance property (R21)
            if cid in entries:
                continue
        pins = list((card.get("pins") or {}).keys())
        kind = {"wire-lead": "lead", "pin": "header-pin", "short-leg": "lead", "lug": "lug"}.get(card.get("leads"), "pin")
        through = [pins[:2]] if len(pins) == 2 and not card.get("connector_only") else []
        if len(pins) == 3 and sub == "potentiometer":
            through = [["GND", "SIG"], ["SIG", "VCC"]]
        entries[cid] = _entry(
            cid, card.get("display_name", cid), sub or card.get("type", "part"), [(p, kind) for p in pins],
            through=through, symmetric=card.get("symmetric_pins", []), polarized=bool(card.get("polarized")),
            connector=bool(card.get("connector_only")), alias=card.get("pin_aliases"))
    # Cards without explicit pins that the experiment needs.
    entries["arduino-uno"] = _entry("arduino-uno", "Arduino Uno R3", "board",
                                    [(p, "header-socket") for p in UNO_PORTS],
                                    alias={"mode": "prefix", "prefixes": ["GND"]})
    entries["breadboard"] = _entry(
        "breadboard", "Solderless breadboard", "breadboard", [("<column><bank>.<row>", "breadboard-hole")],
        connector=True, alias={"mode": "strip"},
        port_rule="Holes are named '<column><bank>.<row>': column 1-30, bank 't' (top half, rows a-e) or 'b' "
                  "(bottom half, rows f-j), e.g. '12t.c', '7b.h'. The 5 holes of one column-bank are one strip. "
                  "Power rails: 'tp.<n>', 'tn.<n>', 'bp.<n>', 'bn.<n>' (each rail is one strip).")
    entries["jumper-wire"] = _entry("jumper-wire", "Jumper wire", "wire", [("a", "wire-end"), ("b", "wire-end")],
                                    conducts=[["a", "b"]], connector=True)
    entries["led"] = _entry("led", "LED", "led", [("A", "lead"), ("C", "lead")], through=[["A", "C"]], polarized=True)
    entries["pushbutton"] = _entry("pushbutton", "Pushbutton", "button",
                                   [("1.l", "lead"), ("1.r", "lead"), ("2.l", "lead"), ("2.r", "lead")],
                                   through=[["1", "2"]], symmetric=[["1", "2"]],
                                   alias={"mode": "prefix", "prefixes": ["1", "2"]})
    return entries


# --- LEGO: imported on demand from the LDraw parts library ----------------------
DIMS = re.compile(r"^(Brick|Plate|Tile)\s+(\d+)\s*x\s*(\d+)\s*$", re.I)


def brick_dims(description):
    """(kind, w, l) for plain bricks/plates/tiles, else None."""
    m = DIMS.match(re.sub(r"\s+", " ", description).strip())
    return (m.group(1).lower(), int(m.group(2)), int(m.group(3))) if m else None


def lego_entry(part_file, description):
    """A catalogue entry imported from the LDraw library (no model involved)."""
    num = part_file[:-4] if part_file.endswith(".dat") else part_file
    dims = brick_dims(description)
    ports = []
    if dims:
        kind, w, l = dims
        if kind != "tile":
            ports += [(f"stud.{i}.{j}", "stud") for i in range(1, w + 1) for j in range(1, l + 1)]
        ports += [(f"anti.{i}.{j}", "anti-stud") for i in range(1, w + 1) for j in range(1, l + 1)]
    rotation = "none"
    if dims:
        rotation = "90" if dims[1] == dims[2] else "180"
    mirror = None
    if re.search(r"\b(Left|Right)\b", description):
        mirror = "(LDraw: see the Left/Right twin)"
    return _entry(f"lego-{num}", description, dims[0] if dims else "lego-part", ports,
                  status="imported", rotation=rotation, mirror_of=mirror)


class Catalogue:
    def __init__(self, entries=None):
        self.entries = copy.deepcopy(entries or {})
        self.created = []  # types added on demand during this run

    def has(self, type_):
        return type_ in self.entries

    def get(self, type_):
        return self.entries.get(type_)

    def add_drafts(self, drafts):
        """Add model-drafted entries for types not already present (store on demand)."""
        added = []
        for d in drafts:
            d = dict(d)
            if d["type"] in self.entries:
                continue
            d.update(alias=None, status="unverified")
            self.entries[d["type"]] = d
            added.append(d["type"])
        self.created += added
        return added

    def prompt_text(self, types=None):
        """Compact one-line-per-type listing for the prompt."""
        lines = []
        for t in sorted(types or self.entries):
            e = self.entries[t]
            ports = e.get("port_rule") or ", ".join(p["name"] for p in e["ports"][:40])
            if len(e["ports"]) > 40:
                ports += f", … ({len(e['ports'])} ports)"
            flags = [f for f, on in (("polarized", e["polarized"]), ("connector", e["connector"])) if on]
            if e["symmetric"]:
                flags.append("symmetric " + "/".join("=".join(g) for g in e["symmetric"]))
            lines.append(f"- {t} | {e['name']} | ports: {ports}" + (f" | {', '.join(flags)}" if flags else ""))
        return "\n".join(lines)

    def to_json(self):
        return self.entries
