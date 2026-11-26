"""An Arduino's pins from numbers, not pictures (the learner's idea, 26 Nov 2026): every Uno-shaped board (Uno, Leonardo,
Duemilanove, Zero, Uno R4, the Due's and Mega's first part, and their clones) follows Arduino's shield standard, so its
header openings sit at fixed places from the board's edges. A board is stored as its form and its header rows
(FORMS, BOARDS; in the database under its part, graph/parts/arduino/board_geometry.py); in a photo, code finds the
blue board's outline and which way round it is (the USB and power-jack end), and maps the numbers onto it.

The reference photos (uno_overlay) stay for the boards that have one: the print overlay is more exact. This is for every
other board of the same form, with nothing to photograph or click first.

Positions in mils (thousandths of an inch, the shield drawings' unit), the board seen from above with its USB and
power jack on the left: x along the long edge from that end, y up from the power header's edge.

    pins(photo, board_id) -> {"pins": {name: (x, y) in the photo}, "rows": [...], "pitch": px} or None
"""
import cv2
import numpy as np

from validator import board as _board

MIL = 0.0254  # mm
# the Arduino Uno shield standard (Arduino's Uno Rev3 drawing); a 0.1" grid
UNO = {
    "size": (2700, 2100),
    "rows": {
        # the digital header along the top edge, y = 2.0": SCL..8 (10 openings), 0.16" gap, 7..0 (8)
        "uno-r3": {"y": 2000, "x": dict(zip(["SCL", "SDA", "AREF", "GND", "13", "12", "11", "10", "9", "8"],
                                            range(840, 1741, 100))) | dict(zip(["7", "6", "5", "4", "3", "2", "1", "0"],
                                                                              range(1900, 2601, 100)))},
        # older boards (Duemilanove, Diecimila): the same openings without SCL and SDA
        "duemilanove": {"y": 2000, "x": dict(zip(["AREF", "GND", "13", "12", "11", "10", "9", "8"], range(1040, 1741, 100)))
                        | dict(zip(["7", "6", "5", "4", "3", "2", "1", "0"], range(1900, 2601, 100)))},
        # the power + analog header along the bottom edge, y = 0.1": NC IOREF RESET 3V3 5V GND GND VIN, 0.2" gap, A0..A5
        "power-analog-8": {"y": 100, "x": dict(zip(["NC", "IOREF", "RESET", "3V3", "5V", "GND.", "GND..", "VIN"],
                                                   range(1000, 1701, 100))) | dict(zip([f"A{i}" for i in range(6)],
                                                                                      range(1900, 2401, 100)))},
        "power-analog-boot": {"y": 100, "x": dict(zip(["BOOT", "IOREF", "RESET", "3V3", "5V", "GND.", "GND..", "VIN"],
                                                      range(1000, 1701, 100))) | dict(zip([f"A{i}" for i in range(6)],
                                                                                         range(1900, 2401, 100)))},
        "power-analog-6": {"y": 100, "x": dict(zip(["RESET", "3V3", "5V", "GND.", "GND..", "VIN"], range(1200, 1701, 100)))
                           | dict(zip([f"A{i}" for i in range(6)], range(1900, 2401, 100)))},
    },
}
FORMS = {"uno": UNO}
# each board: its form and its rows (what is printed on it); a board not here but Uno-shaped: "uno", uno-r3 rows
BOARDS = {
    "arduino-uno": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-uno-r4-minima": ("uno", ["uno-r3", "power-analog-boot"]),
    "arduino-uno-r4-wifi": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-uno-wifi-rev2": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-leonardo": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-zero": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-yun": ("uno", ["uno-r3", "power-analog-8"]),
    "arduino-duemilanove": ("uno", ["duemilanove", "power-analog-6"]),
}


def form_of(board_id, uno_layout=False):
    """(form, rows) for a board, or None (not Uno-shaped)."""
    if board_id in BOARDS:
        return BOARDS[board_id]
    return ("uno", ["uno-r3", "power-analog-8"]) if uno_layout else None


def mils(board_id, uno_layout=False):
    """The board's openings in mils: {row: {pin: (x, y)}} (what goes into the database), or None."""
    f = form_of(board_id, uno_layout)
    if not f:
        return None
    form = FORMS[f[0]]
    return {r: {p: (x, form["rows"][r]["y"]) for p, x in form["rows"][r]["x"].items()} for r in f[1]}


def _usb_end(img, quad):
    """Which short edge of the board's outline has the USB socket and the power jack: silver metal and a black block
    standing out past the blue board. Returns the index i of that edge (quad[i] -> quad[i+1])."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    q = np.asarray(quad, float)
    sides = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    short = [0, 2] if sides[0] < sides[1] else [1, 3]
    mid = q.mean(0)
    best, score = short[0], -1.0
    for i in short:
        a, b = q[i], q[(i + 1) % 4]
        out = (a + b) / 2 - mid
        out /= np.linalg.norm(out)
        # a band from a little inside the edge to well past it, along the whole edge
        poly = np.float32([a - out * sides[(i + 1) % 4] * 0.12, b - out * sides[(i + 1) % 4] * 0.12,
                           b + out * sides[(i + 1) % 4] * 0.14, a + out * sides[(i + 1) % 4] * 0.14])
        m = np.zeros(img.shape[:2], np.uint8)
        cv2.fillConvexPoly(m, poly.astype(np.int32), 255)
        sel = m > 0
        if not sel.any():
            continue
        h, s, v = hsv[..., 0][sel], hsv[..., 1][sel].astype(float), hsv[..., 2][sel].astype(float)
        silver = ((s < 45) & (v > 120)).mean()  # the USB socket's metal
        black = (v < 45).mean()  # the power jack
        blue = ((h >= 84) & (h <= 128) & (s > 45)).mean()
        sc = silver + 0.5 * black - 0.3 * blue
        if sc > score:
            best, score = i, sc
    return best


def pins(photo, board_id, uno_layout=False, img=None):
    """Every opening's place in the photo for a board of a known form: {"pins": {row: {pin: (x, y)}}, "pitch",
    "quad"} or None (no blue board found, or not Uno-shaped)."""
    rows = mils(board_id, uno_layout)
    if not rows:
        return None
    img = _board.load(str(photo)) if img is None else img
    H, W = img.shape[:2]
    f = 1200 / max(H, W)
    small = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    a = _board.arduino_box(small)
    if not a or a.get("cut"):
        return None
    quad = np.array([[x * W, y * H] for x, y in a["quad"]], float)
    i = _usb_end(img, quad)
    # the board's corners: (0,0) and (0,2100) on the USB edge, so that x runs away from it and y turns from x the
    # way it does seen from above (counter-clockwise on the screen, where y points down)
    p, q2 = quad[i], quad[(i + 1) % 4]
    far = [quad[(i + 2) % 4], quad[(i + 3) % 4]]
    vx = (far[0] + far[1]) / 2 - (p + q2) / 2
    def cz(u, v):
        return u[0] * v[1] - u[1] * v[0]
    o, top = (p, q2) if cz(vx, q2 - p) < 0 else (q2, p)
    x_end = min(far, key=lambda c: np.linalg.norm(c - o))
    xy_end = max(far, key=lambda c: np.linalg.norm(c - o))
    w, h = FORMS["uno"]["size"]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]),
                                    np.float32([o, x_end, xy_end, top]))
    out = {}
    for r, pts in rows.items():
        names = list(pts)
        xy = cv2.perspectiveTransform(np.float32([[pts[n] for n in names]]), M)[0]
        out[r] = {n: (float(x), float(y)) for n, (x, y) in zip(names, xy)}
    d = cv2.perspectiveTransform(np.float32([[[0, 0], [100, 0]]]), M)[0]
    return {"pins": out, "pitch": float(np.linalg.norm(d[1] - d[0])), "quad": [o.tolist(), x_end.tolist(),
                                                                              xy_end.tolist(), top.tolist()]}
