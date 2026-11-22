# -*- coding: utf-8 -*-
"""Read the housing's inputs out of the board file.

  python hardware/enclosure/extract_board.py         writes hardware/enclosure/board.json

Read-only on hardware/mccan.kicad_pcb. Output is in BOARD coordinates: KiCad (x - 20, y - 20), the
board's top-left corner at (0, 0), +x right, +y toward the cable edge. Part heights come from the
KiCad 3D model (max z of its STEP points) where the model resolves, otherwise from FALLBACK_HEIGHT.
A part with neither is an error: a height of 0 would make the lid check pass falsely.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "mccan.kicad_pcb")
OUT = os.path.join(HERE, "board.json")
MODEL_DIRS = [
    r"C:\Program Files\KiCad\10.0\share\kicad\3dmodels",
    os.path.join(HERE, "..", "3dmodels"),
]
ORIGIN = (20.0, 20.0)  # KiCad position of the board's top-left corner (Edge.Cuts)
ANTENNA_COPPER = [70.75, 0, 119.25, 6.44]  # enclosure.md §2, board keep-out
ANTENNA_CLEAR = 15.0                       # Espressif: no metal within 15 mm

# Height above the board top (mm) for parts whose 3D model does not resolve here, or has none.
FALLBACK_HEIGHT = {
    "L2": 24.0,   # Würth 7448031002 on its 3 mm standoff, enclosure.md §1 (model path does not resolve)
    "U1": 1.75, "U2": 1.75,   # SOIC-8-EP, JEDEC MS-012 max
    "U14": 1.2,               # Infineon PG-TSDSO-14, datasheet max
    "Q13": 1.1, "Q14": 1.1,   # PowerPAK SO-8L
    "SW1": 3.8, "SW2": 3.8,   # XKB TS-1187A [TO CONFIRM] body + actuator
    "U11": 1.2, "U12": 1.2, "U13": 1.2,  # TI DGQ (HTSSOP-28) max
    "L6": 2.0,                # TDK ACT45B
    "NT1": 0.1,
    # Soldered wire tails: solder fillet plus the wire leaving the pad; the wires themselves are
    # routed by hand and checked as a lid clearance, not modelled.
    "J1": 3.0, "J3": 3.0, "J4": 3.0, "J5": 3.0, "J8": 3.0, "J9": 3.0, "J10": 3.0, "J11": 3.0,
}
# Datasheet floors: a resolved 3D model may not include everything above the board (L2's STEP reads
# 11.6 mm: it lacks the 3 mm standoff and its local frames). The datasheet figure wins when higher.
DATASHEET_MIN = {"L2": 24.0}  # enclosure.md §1: 24.0 mm max above the board
TEST_PAD_HEIGHT = 0.1


def part_height(ref, model_h):
    """(height, source) for a part, from its model height (or None) and the tables."""
    floor = DATASHEET_MIN.get(ref)
    if floor is not None and (model_h is None or model_h < floor):
        return floor, "datasheet"
    if model_h is not None:
        return model_h, "model"
    if ref in FALLBACK_HEIGHT:
        return FALLBACK_HEIGHT[ref], "table"
    if ref.startswith("TP"):
        return TEST_PAD_HEIGHT, "table"
    return None, None
TAILS = ("J1", "J3", "J4", "J5", "J8", "J9", "J10", "J11")


# ---------- s-expression ----------
def parse_sexp(text):
    tok = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')
    stack, cur = [], []
    for m in tok.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def kids(node, name):
    return [n for n in node if isinstance(n, list) and n and n[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


# ---------- geometry ----------
def to_board(fx, fy, rot, lx, ly):
    """Footprint-local point -> board coordinates (KiCad rotation, y down)."""
    a = math.radians(rot)
    x = lx * math.cos(a) + ly * math.sin(a)
    y = -lx * math.sin(a) + ly * math.cos(a)
    return round(fx + x - ORIGIN[0], 4), round(fy + y - ORIGIN[1], 4)


def shape_points(item):
    pts = []
    for key in ("start", "end", "center", "mid"):
        k = kid(item, key)
        if k:
            pts.append((float(k[1]), float(k[2])))
    pk = kid(item, "pts")
    if pk:
        for xy in kids(pk, "xy"):
            pts.append((float(xy[1]), float(xy[2])))
    if item[0] == "fp_circle" and kid(item, "center") and kid(item, "end"):
        (cx, cy), (ex, ey) = pts[0], pts[1]
        r = math.hypot(ex - cx, ey - cy)
        pts += [(cx - r, cy - r), (cx + r, cy + r)]
    return pts


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


# ---------- 3D model height ----------
_step_cache = {}


def resolve_model(path):
    p = path.replace("${KICAD10_3DMODEL_DIR}", MODEL_DIRS[0]).replace("${KIPRJMOD}", os.path.join(HERE, ".."))
    return p if os.path.isfile(p) else None


def model_height(model):
    """Max z (mm) of a placed model's STEP points, or None if the model does not resolve."""
    f = resolve_model(model[1])
    if not f:
        return None
    if f not in _step_cache:
        with open(f, encoding="latin-1") as fh:
            txt = fh.read()
        _step_cache[f] = [tuple(float(v) for v in m.groups())
                          for m in re.finditer(r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-\dEe.+]+)\s*,\s*([-\dEe.+]+)\s*,\s*([-\dEe.+]+)\s*\)", txt)]
    pts = _step_cache[f]
    if not pts:
        return None
    off = [float(v) for v in kid(kid(model, "offset"), "xyz")[1:4]] if kid(model, "offset") else [0, 0, 0]
    rx, ry, rz = ([math.radians(-float(v)) for v in kid(kid(model, "rotate"), "xyz")[1:4]]
                  if kid(model, "rotate") else [0, 0, 0])
    zmax = -1e9
    for x, y, z in pts:
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        zmax = max(zmax, z)
    return round(zmax + off[2], 3)


# ---------- main ----------
def load(pcb_path=PCB):
    with open(pcb_path, encoding="utf8") as fh:
        root = parse_sexp(fh.read())

    # Board outline from Edge.Cuts
    edge = []
    for g in root:
        if isinstance(g, list) and g[0] in ("gr_line", "gr_arc", "gr_rect") and kid(g, "layer") and kid(g, "layer")[1] == "Edge.Cuts":
            edge += shape_points(g)
    ex0, ey0, ex1, ey1 = bbox(edge)
    assert (round(ex0, 3), round(ey0, 3)) == ORIGIN, f"board origin moved: {(ex0, ey0)}"
    thick = float(kid(kid(root, "general"), "thickness")[1])

    holes, parts, tails = [], [], []
    access = {"TP": []}
    for fp in kids(root, "footprint"):
        at = kid(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in kids(fp, "property") if p[1] == "Reference")
        crt, padpts, pads = [], [], []
        for item in fp:
            if isinstance(item, list) and item[0].startswith("fp_") and kid(item, "layer") and kid(item, "layer")[1] == "F.CrtYd":
                crt += [to_board(fx, fy, rot, *p) for p in shape_points(item)]
        for pad in kids(fp, "pad"):
            pa = kid(pad, "at")
            px, py = to_board(fx, fy, rot, float(pa[1]), float(pa[2]))
            sz = kid(pad, "size")
            w, h = float(sz[1]), float(sz[2])
            padpts += [(px - w / 2, py - h / 2), (px + w / 2, py + h / 2)]
            dr = kid(pad, "drill")
            d = float(dr[1]) if dr and len(dr) > 1 and dr[1] not in ("oval",) else 0.0
            pads.append([px, py, d])
        box = [round(v, 3) for v in bbox(crt or padpts)]

        if ref.startswith("H") and fp[1].startswith("MountingHole"):
            holes.append({"ref": ref, "x": round(fx - ORIGIN[0], 3), "y": round(fy - ORIGIN[1], 3),
                          "d": max(p[2] for p in pads) if pads else 3.2})
            continue

        mh = None
        for m in kids(fp, "model"):
            mh = model_height(m)
            if mh is not None:
                break
        h, src = part_height(ref, mh)
        if h is None or h <= 0:
            raise ValueError(f"{ref}: no 3D model height and no FALLBACK_HEIGHT entry")
        parts.append({"ref": ref, "x": round(fx - ORIGIN[0], 3), "y": round(fy - ORIGIN[1], 3), "rot": rot,
                      "bbox": box, "height": h, "height_src": src})
        if ref in TAILS:
            tails.append({"ref": ref, "pads": pads})
        if ref in ("J2", "SW1", "SW2"):
            access[ref] = box
        if ref.startswith("TP"):
            access["TP"].append([round(fx - ORIGIN[0], 3), round(fy - ORIGIN[1], 3)])

    c = ANTENNA_COPPER
    return {
        "source": "hardware/mccan.kicad_pcb",
        "outline": {"w": round(ex1 - ex0, 3), "h": round(ey1 - ey0, 3), "r": 1.0, "t": thick},
        "holes": sorted(holes, key=lambda h: h["ref"]),
        "parts": sorted(parts, key=lambda p: p["ref"]),
        "tails": tails,
        "access": access,
        "antenna": {"copper": c,
                    "zone": [c[0] - ANTENNA_CLEAR, -ANTENNA_CLEAR, c[2] + ANTENNA_CLEAR, round(c[3] + ANTENNA_CLEAR, 2)]},
    }


if __name__ == "__main__":
    b = load(PCB)
    with open(OUT, "w", encoding="utf8") as fh:
        json.dump(b, fh, indent=1)
    tall = sorted(b["parts"], key=lambda p: -p["height"])[:5]
    print("wrote", OUT, "-", len(b["parts"]), "parts; tallest:",
          ", ".join(f"{p['ref']} {p['height']} ({p['height_src']})" for p in tall))
    sys.exit(0)
