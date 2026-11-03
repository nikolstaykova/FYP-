"""The vocabulary of a part's metadata: every field that is a code, and the codes it may take (DATA_STRUCTURE.md
§3.4). One place for all of it, so a new part is drafted in these codes (part_metadata's schema is built from here),
stored in them (part_metadata.normalize), and checked against them (validate_store).

Free text is only where words are the point: a part's `description`, its `learner_tips`, the reasons (`why`), and
the original phrase kept beside a code (`material_text`, `mates_text`).
"""

DOMAINS = ("lego", "arduino")

# the port kinds a card may give its ports (what the joins connect)
PORT_KINDS = ("stud", "anti-stud", "pin", "pin-hole", "axle", "axle-hole", "bar", "clip", "hinge", "ball", "socket",
              "lead", "header-pin", "header-socket", "wire-end", "breadboard-hole", "screw", "lug", "pad", "hole", "edge",
              "sleeve")
# what a join's other side may be: a port kind, or a connector a part is sold with
CONNECTORS = ("usb", "usb-micro", "usb-c", "barrel-jack", "battery-connector", "grove", "qwiic", "rf-connector", "rj45",
              "rca", "microsd", "mains", "fpc", "plug", "connector", "minifig-neck", "bare-wire")
MATES = PORT_KINDS + CONNECTORS + ("other",)

JOIN_METHODS = ("insert", "push-on", "screw", "snap", "clip", "slide", "rest", "solder", "twist", "clutch", "clamp")
HOLDS_BY = ("friction", "form", "force", "material", "gravity", "spring")
REVERSIBLE = ("hand", "tool", "damaging", "permanent")

REVERSE_POWER = ("damage", "no-harm", "protected", "n/a")
MATERIALS = ("abs", "polycarbonate", "rubber", "silicone", "pcb", "ceramic", "glass", "copper", "steel", "aluminium",
             "carbon", "metal", "semiconductor", "epoxy", "plastic", "fabric", "paper", "wood", "magnet", "other")
BASIS = ("card", "image", "maker-page", "general-knowledge")
INTERFACES = ("digital", "analog", "pwm", "i2c", "spi", "uart", "1-wire", "usb", "single-wire")
WIRELESS = ("wifi", "bluetooth", "lora", "nfc", "ir", "rf", "cellular")

SWAP_KINDS = ("not-polarized", "card-symmetric", "same-pin", "joined-inside", "strip", "rail")
CONNECT_WAYS = ("breadboard", "header-socket", "female-jumper", "onto-header-pin", "screw-terminal", "solder")
TAKES = ("lead", "pin", "header-pin", "wire-end", "lug")
TOOLS = ("screwdriver", "soldering iron")
STATUS = ("drafted", "verified")
VIA = ("llm", "vlm")
SUBSTITUTE_FREE = ("colour", "length", "value")

# the metadata fields a part may have: what Claude drafts, what code works out, and where the part came from
DRAFTED = ("description", "material", "material_text", "size_studs", "dimensions_mm", "polarized", "reverse_power",
           "specs", "basis", "joins", "learner_tips", "card_issues", "confidence", "overridden")
COMPUTED = ("fits", "connect_by", "takes", "interchangeable", "substitutes", "schema_version", "status", "drafted_by",
            "via", "lesson", "checks_failed")
PROVENANCE = ("domain", "source_catalogue", "card_made_by")
FIELDS = DRAFTED + COMPUTED + PROVENANCE
TEXT = ("description", "learner_tips", "material_text")  # the only free text, with the reasons (`why`)

# field -> its codes, for checking a stored value (lists: every item must be one)
CODES = {"domain": DOMAINS, "reverse_power": REVERSE_POWER, "material": MATERIALS, "status": STATUS, "via": VIA}
