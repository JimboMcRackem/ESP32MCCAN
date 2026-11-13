"""Antenna gate (phase B, plan Task 4; spec goal 6).

  python check_antenna.py        (from hardware/ or hardware/scripts/)

Asserts, against the generated mccan.kicad_pcb:
  * U5 (ESP32-WROOM-32E) is rotated so its antenna end faces layout_pcb.ANTENNA_EDGE, and the
    module's antenna-end edge is flush with that board edge or overhangs it (<= 0.5 mm inboard);
  * nothing copper -- pad, track, arc, via or copper zone, on any of the 8 layers -- lies in the
    keep-out rectangle KEEPOUT_LOCAL (module frame), clipped to the board.  A copper zone whose
    outline crosses the rectangle passes only if a rule area with `copperpour not_allowed` on
    that layer covers the whole rectangle (that is what stops the fill).

KEEPOUT_LOCAL, in the footprint's own frame (mm, y grows away from the antenna):
  y  -12.75 .. -6.31   the module's antenna end (body edge at -12.75) down to the bottom of the
                       antenna area: 6.19 mm from the body edge in the WROOM-32E datasheet v1.8,
                       Fig. 12 "Recommended PCB Land Pattern", plus the 0.25 mm the KiCad library
                       courtyard adds;
  x  -24.25 .. 24.25   the 18 mm body +/- 15.25 mm: Espressif's >= 15 mm clearance either side of
                       the antenna (ESP32 Hardware Design Guidelines, module-on-edge placement),
                       as encoded in the KiCad RF_Module:ESP32-WROOM-32E courtyard.
Exit 1 on any failure.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_pcb as G  # noqa: E402
import layout_pcb as L  # noqa: E402
from check_placement import footprints  # noqa: E402

BOARD = os.path.join(HW, "mccan.kicad_pcb")
MODULE = "U5"
BODY_EDGE = -12.75
KEEPOUT_LOCAL = (-24.25, -12.75, 24.25, -6.31)
FLUSH_TOL = 0.5
CU = ["F.Cu"] + ["In%d.Cu" % i for i in range(1, 7)] + ["B.Cu"]
# board direction the module's local -y points to, by rotation
FACING = {0: "top", 90: "left", 180: "bottom", 270: "right"}


def keepout_rect(d):
    """KEEPOUT_LOCAL in board coordinates, as an axis-aligned box, clipped to the outline."""
    x0, y0, x1, y1 = KEEPOUT_LOCAL
    pts = [G.rot_local(x, y, d["rot"]) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    xs = [d["x"] + p[0] for p in pts]
    ys = [d["y"] + p[1] for p in pts]
    return (max(min(xs), L.X0), max(min(ys), L.Y0), min(max(xs), L.X1), min(max(ys), L.Y1))


def seg_hits_rect(ax, ay, bx, by, r, grow):
    """Does the segment a-b, fattened by `grow`, touch the box r?  (Liang-Barsky clip.)"""
    x0, y0, x1, y1 = r[0] - grow, r[1] - grow, r[2] + grow, r[3] + grow
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def poly_hits_rect(poly, r):
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if seg_hits_rect(a[0], a[1], b[0], b[1], r, 0.0):
            return True
    return point_in_poly((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, poly)


def poly_covers_rect(poly, r):
    e = 0.01   # a rule area drawn exactly on the rectangle covers it; test just inside
    corners = ((r[0] + e, r[1] + e), (r[2] - e, r[1] + e), (r[0] + e, r[3] - e), (r[2] - e, r[3] - e))
    return all(point_in_poly(x, y, poly) for x, y in corners) and not any(
        r[0] < px < r[2] and r[1] < py < r[3] for px, py in poly)


def layers_of(spec):
    out = []
    for l in re.findall(r'"([^"]+)"', spec):
        if l == "*.Cu":
            out += CU
        elif l == "F&B.Cu":
            out += ["F.Cu", "B.Cu"]
        elif l.endswith(".Cu"):
            out.append(l)
    return out


def zones(text):
    """[(net_name, layers, poly, is_rule_area, copperpour_not_allowed)]"""
    out = []
    for blk in text.split("\n\t(zone")[1:]:
        net = re.search(r'\(net_name "([^"]*)"\)', blk)
        lay = re.search(r'\n\t\t\(layers? ([^)]*)\)', blk)
        # The group must end at the closing line: ending it at "\)\s*\)" eats the last
        # vertex's own ")" and findall then drops that vertex.
        pts = re.search(r"\(polygon\s*\(pts(.*?)\n\s*\)", blk, re.S)
        poly = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)",
                                                          pts.group(1))] if pts else []
        rule = "(keepout" in blk
        nopour = bool(re.search(r"\(copperpour not_allowed\)", blk))
        out.append((net.group(1) if net else "", layers_of(lay.group(1)) if lay else [], poly,
                    rule, nopour))
    return out


def check():
    f = []
    text = open(BOARD, encoding="utf-8").read()
    fps = footprints(text)
    d = fps.get(MODULE)
    if d is None:
        return ["%s is not placed" % MODULE]
    rot = int(round(d["rot"])) % 360
    facing = FACING.get(rot)
    if facing != L.ANTENNA_EDGE:
        f.append("%s antenna faces %s (rot %s), want %s" % (MODULE, facing, d["rot"], L.ANTENNA_EDGE))
    else:
        ex, ey = G.rot_local(0.0, BODY_EDGE, d["rot"])
        inboard = {"top": d["y"] + ey - L.Y0, "bottom": L.Y1 - (d["y"] + ey),
                   "left": d["x"] + ex - L.X0, "right": L.X1 - (d["x"] + ex)}[facing]
        if inboard > FLUSH_TOL:
            f.append("%s antenna end is %.2f mm inboard of the %s edge, want flush or overhang"
                     % (MODULE, inboard, facing))
    r = keepout_rect(d)
    if r[0] >= r[2] or r[1] >= r[3]:
        return f + ["keep-out rectangle is entirely off the board"]

    for ref, fd in fps.items():
        for p in fd["pads"]:
            if p[6] == "np_thru_hole":
                continue
            pr = (p[1] - p[3] / 2, p[2] - p[4] / 2, p[1] + p[3] / 2, p[2] + p[4] / 2)
            if pr[0] < r[2] and r[0] < pr[2] and pr[1] < r[3] and r[1] < pr[3]:
                f.append("pad %s.%s at (%.2f, %.2f) is in the antenna keep-out" % (ref, p[0], p[1], p[2]))
    for m in re.finditer(r'\n\t\((segment|arc)\s*\(start ([-\d.]+) ([-\d.]+)\)(?:\s*\(mid [-\d.]+ [-\d.]+\))?'
                         r'\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([-\d.]+)\)\s*\(layer "([^"]+)"\)',
                         text):
        if seg_hits_rect(float(m.group(2)), float(m.group(3)), float(m.group(4)),
                         float(m.group(5)), r, float(m.group(6)) / 2):
            f.append("%s on %s from (%s, %s) is in the antenna keep-out"
                     % (m.group(1), m.group(7), m.group(2), m.group(3)))
    for m in re.finditer(r'\n\t\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)', text):
        x, y, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if r[0] - s / 2 < x < r[2] + s / 2 and r[1] - s / 2 < y < r[3] + s / 2:
            f.append("via at (%.2f, %.2f) is in the antenna keep-out" % (x, y))

    zs = zones(text)
    covered = set()
    for _n, lays, poly, rule, nopour in zs:
        if rule and nopour and poly and poly_covers_rect(poly, r):
            covered.update(lays)
    for net, lays, poly, rule, _np in zs:
        if rule or not poly or not poly_hits_rect(poly, r):
            continue
        for l in lays:
            if l not in covered:
                f.append("copper zone %s on %s reaches into the antenna keep-out" % (net, l))
    return f


def main():
    f = check()
    for line in f[:40]:
        print("FAIL " + line)
    if len(f) > 40:
        print("... %d more" % (len(f) - 40))
    print("antenna: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
