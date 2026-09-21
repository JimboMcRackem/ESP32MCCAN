# -*- coding: utf-8 -*-
"""Check the F.Cu GND_IN island against the pads it is supposed to serve.

GND_IN and GND are different nets that meet at exactly two places: L2 winding B, and R3.
Nothing in DRC enforces that, because a pour never shorts to a foreign net -- KiCad simply
notches around it.  So a GND_IN island that misses half its own pads, or that blankets a
post-choke ground pad, passes DRC in silence.  That is the failure this file exists to catch:

    * every GND_IN pad on F.Cu must lie inside the island, or it has no local return and
      Task 9 has to route what should have been a plane;
    * no GND pad on F.Cu may lie inside it, or input-side copper is wrapped around
      post-choke ground -- coupling across the very component that separates them.

Run after gen_pcb.py.  Exit status is non-zero if either condition is broken.
"""

import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
# A board path on the command line checks THAT board instead -- the external-router
# chain in route_external.py grades its own output with the same two guards.
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")

ISLAND_NET = "/power_input/GND_IN"
PLANE_NET = "GND"

FP_AT_RE = re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)')
PAD_RE = re.compile(
    r'\(pad "([^"]*)" \w+ [\w_]+\s*\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)\s*'
    r'\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)', re.S)


def zone_polys(text, net, layer):
    """Every polygon of the zones on `net` / `layer`, as lists of (x, y)."""
    out = []
    for blk in text.split("\n\t(zone")[1:]:
        nm = re.search(r'\(net_name "([^"]*)"\)', blk)
        ly = re.search(r'\(layers? ([^)]*)\)', blk)
        if not nm or nm.group(1) != net:
            continue
        if not ly or layer not in ly.group(1):
            continue
        out.append([(float(a), float(b))
                    for a, b in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', blk)])
    return out


def inside(poly, x, y):
    """Ray-cast point-in-polygon.  The island is a plain simple polygon, so this is enough."""
    hit = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xc:
                hit = not hit
    return hit


def on_layer(tail, layer):
    """Is a pad on `layer`?  A through-hole pad says "*.Cu", not "F.Cu"."""
    m = re.search(r'\(layers ([^)]*)\)', tail)
    if not m:
        return False
    names = re.findall(r'"([^"]*)"', m.group(1))
    return layer in names or "*.Cu" in names


def pads_on(text, layer):
    """(ref, pad, x, y, net) for every pad present on `layer`, in BOARD coordinates."""
    out = []
    for blk in text.split("\n\t(footprint ")[1:]:
        m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        fm = FP_AT_RE.search(blk)
        if not m or not fm:
            continue
        fx, fy = float(fm.group(1)), float(fm.group(2))
        th = math.radians(float(fm.group(3) or 0.0))
        for pm in PAD_RE.finditer(blk):
            nm = re.search(r'\(net \d+ "([^"]*)"\)', pm.group(7))
            if not pm.group(1) or nm is None or not on_layer(pm.group(7), layer):
                continue
            x, y = float(pm.group(2)), float(pm.group(3))
            out.append((m.group(1), pm.group(1),
                        fx + x * math.cos(th) + y * math.sin(th),
                        fy - x * math.sin(th) + y * math.cos(th),
                        nm.group(1)))
    return out


def main():
    text = io.open(PCB, encoding="utf-8").read()
    polys = zone_polys(text, ISLAND_NET, "F.Cu")
    if not polys:
        print("FAIL: no F.Cu zone on %s" % ISLAND_NET)
        return 1

    def in_island(x, y):
        return any(inside(p, x, y) for p in polys)

    pads = pads_on(text, "F.Cu")

    # A part that carries BOTH nets is the boundary itself -- R3, the tie resistor, and L2,
    # whose winding B joins them.  Its GND pad sitting in the island is not a leak; it is the
    # one place the two grounds are meant to meet, and it has to be reachable from both sides.
    bridges = set(p[0] for p in pads if p[4] == ISLAND_NET) & \
        set(p[0] for p in pads if p[4] == PLANE_NET)

    missing = [p for p in pads if p[4] == ISLAND_NET and not in_island(p[2], p[3])]
    intruding = [p for p in pads if p[4] == PLANE_NET and p[0] not in bridges
                 and in_island(p[2], p[3])]
    total = len([p for p in pads if p[4] == ISLAND_NET])

    print("F.Cu %s island: %d polygon(s), %d vertices"
          % (ISLAND_NET, len(polys), sum(len(p) for p in polys)))
    print("  %s pads on F.Cu: %d, inside: %d" % (ISLAND_NET, total, total - len(missing)))
    for r, p, x, y, _ in sorted(missing):
        print("    FAIL %s pad %s (%.2f, %.2f) is outside the island" % (r, p, x, y))
    print("  %s pads inside the island: %d" % (PLANE_NET, len(intruding)))
    for r, p, x, y, _ in sorted(intruding):
        print("    FAIL %s pad %s (%.2f, %.2f) is post-choke ground inside the island"
              % (r, p, x, y))

    if missing or intruding:
        return 1
    print("  OK: the two grounds are separated on F.Cu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
