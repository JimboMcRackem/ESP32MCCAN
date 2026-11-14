"""Board frame gate (phase B, plan Task 3).

  python check_frame.py        (from hardware/ or hardware/scripts/)

Asserts, against mccan.kicad_pcb and mccan.kicad_pro:
  * the Edge.Cuts bounding box is layout_pcb.BOARD_W x BOARD_H (140 x 100 mm, +/-0.01);
  * exactly 8 copper layers;
  * 4 mounting holes, 3.2 mm drill, 5 mm in from each corner;
  * every DRC minimum in the project is at or above JLCPCB's 8-layer capability
    (layout_pcb.JLC_FLOOR, sourced in layout_pcb's docstring).
Exit 1 on any failure.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import layout_pcb as L  # noqa: E402

BOARD = os.path.join(HW, "mccan.kicad_pcb")
PRO = os.path.join(HW, "mccan.kicad_pro")
TOL = 0.01

# kicad_pro rule key -> JLC_FLOOR key it must be >= to
RULE_FLOOR = {
    "min_track_width": "track",
    "min_clearance": "clearance",
    "min_via_diameter": "via_diameter",
    "min_through_hole_diameter": "via_drill",
    "min_via_annular_width": "annular_ring",
    "min_hole_to_hole": "hole_to_hole",
    "min_hole_clearance": "hole_to_track",
    "min_copper_edge_clearance": "copper_to_edge",
    "min_text_height": "silk_text_height",
    "min_text_thickness": "silk_line_width",
}


def edge_bbox(text):
    xs, ys = [], []
    for m in re.finditer(r"\(gr_(?:line|arc|rect)\s(.*?)\(layer \"Edge\.Cuts\"\)", text, re.S):
        for x, y in re.findall(r"\((?:start|end|mid) ([-\d.]+) ([-\d.]+)\)", m.group(1)):
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def copper_layers(text):
    i = text.index("\t(layers")
    block = text[i:text.index("\n\t)", i)]
    return re.findall(r'\(\d+ "([^"]+\.Cu)"', block)


def mount_holes(text):
    out = []
    for blk in re.split(r"\n\t\(footprint ", text)[1:]:
        if not blk.startswith('"MountingHole:'):
            continue
        at = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)", blk)
        drill = re.search(r"\(drill ([\d.]+)\)", blk)
        out.append((float(at.group(1)), float(at.group(2)), float(drill.group(1)) if drill else None))
    return out


def check():
    f = []
    text = open(BOARD, encoding="utf-8").read()
    bb = edge_bbox(text)
    if bb is None:
        f.append("no Edge.Cuts outline")
    else:
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if abs(w - L.BOARD_W) > TOL or abs(h - L.BOARD_H) > TOL:
            f.append("outline is %.2f x %.2f mm, want %.1f x %.1f" % (w, h, L.BOARD_W, L.BOARD_H))
    cu = copper_layers(text)
    if len(cu) != 8:
        f.append("%d copper layers (%s), want 8" % (len(cu), ", ".join(cu)))
    holes = mount_holes(text)
    if len(holes) != 4:
        f.append("%d mounting holes, want 4" % len(holes))
    elif bb is not None:
        x0, y0, x1, y1 = bb
        want = sorted([(x0 + 5, y0 + 5), (x1 - 5, y0 + 5), (x0 + 5, y1 - 5), (x1 - 5, y1 - 5)])
        got = sorted((x, y) for x, y, _d in holes)
        for (wx, wy), (gx, gy) in zip(want, got):
            if abs(wx - gx) > TOL or abs(wy - gy) > TOL:
                f.append("mounting hole at (%.2f, %.2f), want (%.2f, %.2f)" % (gx, gy, wx, wy))
        for x, y, d in holes:
            if d is None or abs(d - 3.2) > TOL:
                f.append("mounting hole at (%.2f, %.2f) has drill %s, want 3.2" % (x, y, d))
    rules = json.load(open(PRO, encoding="utf-8"))["board"]["design_settings"]["rules"]
    for key, floor in RULE_FLOOR.items():
        v, lim = rules.get(key), L.JLC_FLOOR[floor]
        if v is None or v + 1e-9 < lim:
            f.append("rule %s = %s is below JLCPCB's %s floor %.3f mm" % (key, v, floor, lim))
    return f


def main():
    f = check()
    for line in f:
        print("FAIL " + line)
    print("frame: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
