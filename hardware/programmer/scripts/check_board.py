# -*- coding: utf-8 -*-
"""Geometry gate for the programmer board (plan Task 3) -- what DRC does not check.

  python hardware/programmer/scripts/check_board.py      exit 1 on any failure

Outline size, every part on top, J1 mouth at the edge and J2 at the far end, silk labels and
the pin-1 mark, USB pair vias and length match, the regulator's heatsink copper, and power
track widths (>= 0.5 mm, or a short neck into a pad narrower than that).
"""
import math
import os
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcblib as P  # noqa: E402
import parts  # noqa: E402

PCB = os.path.join(PROG, "prog.kicad_pcb")
POWER = ("VBUS", "+3V3_USB", "+3V3_OUT")
POWER_W = 0.5
# a power track may neck to 0.3 mm within 1.5 mm of a fine-pitch pad it feeds (QFN, SC-70,
# SSOP, SOT-23 pins are 0.3-0.6 mm wide at 0.5-0.95 mm pitch); gen_pcb.NECK_R is 1.4
NECK_W, NECK_REACH = 0.3, 1.5
HEATSINK_MM2 = 200.0
# the pin-1 arrow sits just outside the header's silk outline (1.27 mm from pin 1 at best)
PIN1_MARK_MM = 2.6
# CH343P is a full-speed (12 Mb/s) device: edges of 4 ns or slower, so 5 mm of skew is
# ~30 ps, under 1 % of an edge; 30 mm of trace is electrically short at those edges
USB_SKEW_MM, USB_MAX_MM = 5.0, 30.0

FP = namedtuple("FP", "ref spec x y rot layer pads")
Pad = namedtuple("Pad", "num x y w h net")


class Board:
    def __init__(self):
        self.fps, self.tracks, self.vias, self.zones = [], [], [], []
        self.texts, self.polys, self.edge_pts = [], [], []

    def fp(self, ref):
        return next(f for f in self.fps if f.ref == ref)

    @property
    def edge(self):
        xs = [p[0] for p in self.edge_pts]
        ys = [p[1] for p in self.edge_pts]
        return (min(xs), min(ys), max(xs), max(ys))


def read(path=PCB):
    root = P.parse(open(path, encoding="utf-8").read())
    # bare names (the schematic's root-sheet nets read "/VBUS" on the board)
    names = {n[1]: P.unq(n[2]).lstrip("/") for n in P.find_all(root, "net")}
    bd = Board()
    for f in P.find_all(root, "footprint"):
        at = P.find(f, "at")
        x, y = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(P.unq(p[2]) for p in P.find_all(f, "property") if P.unq(p[1]) == "Reference")
        pads = []
        for p in P.find_all(f, "pad"):
            pa, sz, nt = P.find(p, "at"), P.find(p, "size"), P.find(p, "net")
            dx, dy = P.rot_local(float(pa[1]), float(pa[2]), rot)
            w, h = float(sz[1]), float(sz[2])
            if (float(pa[3]) if len(pa) > 3 else 0.0) % 180:
                w, h = h, w
            pads.append(Pad(P.unq(p[1]), x + dx, y + dy, w, h,
                            P.unq(nt[2]).lstrip("/") if nt else None))
        bd.fps.append(FP(ref, P.unq(f[1]), x, y, rot, P.unq(P.find(f, "layer")[1]), pads))
    for s in P.find_all(root, "segment"):
        st, en = P.find(s, "start"), P.find(s, "end")
        bd.tracks.append((names[P.find(s, "net")[1]], P.unq(P.find(s, "layer")[1]),
                          (float(st[1]), float(st[2])), (float(en[1]), float(en[2])),
                          float(P.find(s, "width")[1])))
    for v in P.find_all(root, "via"):
        at = P.find(v, "at")
        bd.vias.append((names[P.find(v, "net")[1]], float(at[1]), float(at[2]),
                        float(P.find(v, "size")[1])))
    for z in P.find_all(root, "zone"):
        pts = [(float(p[1]), float(p[2])) for p in P.find_all(P.find(P.find(z, "polygon"), "pts"), "xy")]
        bd.zones.append((P.unq(P.find(z, "net_name")[1]).lstrip("/"),
                         P.unq(P.find(z, "layer")[1]), pts))
    for g in P.find_all(root, "gr_line") + P.find_all(root, "gr_arc"):
        if P.unq(P.find(g, "layer")[1]) == "Edge.Cuts":
            for k in ("start", "end", "mid"):
                c = P.find(g, k)
                if c:
                    bd.edge_pts.append((float(c[1]), float(c[2])))
    for t in P.find_all(root, "gr_text"):
        at = P.find(t, "at")
        bd.texts.append((P.unq(t[1]), P.unq(P.find(t, "layer")[1]), float(at[1]), float(at[2])))
    for g in P.find_all(root, "gr_poly"):
        pts = [(float(p[1]), float(p[2])) for p in P.find_all(P.find(g, "pts"), "xy")]
        bd.polys.append((P.unq(P.find(g, "layer")[1]), pts))
    return bd


# ------------------------------------------------------------------ measures
def courtyard(bd, ref):
    f = bd.fp(ref)
    pts = []
    for g in P.load_fp(f.spec):
        if isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect"):
            if P.unq(P.find(g, "layer")[1]) == "F.CrtYd":
                for k in ("start", "end"):
                    c = P.find(g, k)
                    dx, dy = P.rot_local(float(c[1]), float(c[2]), f.rot)
                    pts.append((f.x + dx, f.y + dy))
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def silk_words(bd):
    return [t for t, lay, _x, _y in bd.texts if lay == "F.SilkS"]


def pin1_mark_near(bd, ref, d):
    p1 = next(p for p in bd.fp(ref).pads if p.num == "1")
    for lay, pts in bd.polys:
        if lay == "F.SilkS":
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            if math.hypot(cx - p1.x, cy - p1.y) <= d:
                return True
    return False


def via_count(bd, net):
    return sum(1 for v in bd.vias if v[0] == net)


def track_length(bd, net):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for n, _l, a, b, _w in bd.tracks if n == net)


def _inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[i - 1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def zone_has_pad(bd, net, layer, ref, num):
    pads = [p for p in bd.fp(ref).pads if p.num == num]
    return any(n == net and l == layer and all(_inside((p.x, p.y), pts) for p in pads)
               for n, l, pts in bd.zones)


def _area(pts):
    return abs(sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1]
                   for i in range(len(pts)))) / 2.0


def zone_area(bd, net):
    return sum(_area(pts) for n, _l, pts in bd.zones if n == net)


def thin_power_tracks(bd, nets=POWER):
    narrow = [p for f in bd.fps for p in f.pads if min(p.w, p.h) < POWER_W]
    bad = []
    for n, lay, a, b, w in bd.tracks:
        if n not in nets or w >= POWER_W - 1e-6:
            continue
        # a neck: both ends within NECK_REACH of the centre of one narrow pad on the same net
        near = any(p.net == n and all(math.hypot(e[0] - p.x, e[1] - p.y) <= NECK_REACH + 1e-6
                                      for e in (a, b)) for p in narrow)
        if not (w >= NECK_W - 1e-6 and near):
            bad.append((n, lay, a, b, w))
    return bad


def check(path=PCB):
    bd = read(path)
    f = []
    x0, y0, x1, y1 = bd.edge
    if x1 - x0 > 22.0 or y1 - y0 > 42.0:
        f.append("outline %.1f x %.1f mm > 22 x 42" % (x1 - x0, y1 - y0))
    f += ["%s not on F.Cu" % p.ref for p in bd.fps if p.layer != "F.Cu"]
    if {p.ref for p in bd.fps} != set(parts.PARTS):
        f.append("placed parts differ from parts.PARTS")
    if abs(courtyard(bd, "J1")[1] - y0) > 0.5:
        f.append("J1 mouth not at the top edge")
    if y1 - bd.fp("J2").y > 5.0:
        f.append("J2 not at the far end")
    words = silk_words(bd)
    f += ["silk: no '%s'" % w for w in ("3V3", "GND", "TX", "RX", "DTR", "RTS", "MCCAN PROG",
                                        "PWR") if not any(w in t for t in words)]
    if not pin1_mark_near(bd, "J2", PIN1_MARK_MM):
        f.append("silk: no pin-1 mark at J2")
    for net in ("USB_DP", "USB_DN"):
        if via_count(bd, net) > 2:
            f.append("%s has %d vias (> 2)" % (net, via_count(bd, net)))
    a, b = track_length(bd, "USB_DP"), track_length(bd, "USB_DN")
    if abs(a - b) > USB_SKEW_MM or max(a, b) > USB_MAX_MM:
        f.append("USB pair lengths %.2f / %.2f mm" % (a, b))
    if not zone_has_pad(bd, "+3V3_USB", "F.Cu", "U3", "2"):
        f.append("U3 tab outside an F.Cu +3V3_USB zone")
    if zone_area(bd, "+3V3_USB") < HEATSINK_MM2:
        f.append("+3V3_USB heatsink copper %.0f mm2 < %.0f" % (zone_area(bd, "+3V3_USB"),
                                                               HEATSINK_MM2))
    f += ["thin power track %s" % (t,) for t in thin_power_tracks(bd)]
    return f


def main():
    f = check()
    for x in f:
        print("FAIL", x)
    print("check_board: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
