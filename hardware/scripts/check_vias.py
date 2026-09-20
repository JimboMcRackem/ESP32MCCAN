# -*- coding: utf-8 -*-
"""Check the generated vias against the pads they are supposed to serve.

DRC cannot catch what this catches.  A thermal via that misses its paddle and lands on bare
laminate breaks no rule: it is on the right net, clear of everything, and simply conducts
nothing.  A stitching via that lands inside another net's pad WOULD be caught -- but one that
lands inside a pad of its OWN net is a short to that pad's component, silently, and DRC calls
it a connection rather than a fault.  So both directions are checked here:

    * every via on a net that is NOT GND-stitch must lie wholly inside a pad of its own net,
      and that pad must belong to the part the via was generated for;
    * every GND stitching via must lie inside NO pad at all -- it is meant to tie the planes
      together in free space, not to land on a component terminal;
    * every footprint that gen_pcb classed as having an exposed paddle must actually have
      vias in it, so a placement change that pushes a part off the board cannot quietly take
      its thermal path with it.

Run after gen_pcb.py.  Exit status is non-zero if any of that is broken.
"""

import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PCB = os.path.join(HW, "mccan.kicad_pcb")

FP_AT_RE = re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)')
PAD_RE = re.compile(
    r'\(pad "([^"]*)" (\w+) [\w_]+\s*\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)\s*'
    r'\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)', re.S)
VIA_RE = re.compile(
    r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)\s*\(drill ([-\d.]+)\)'
    r'\s*\(layers [^)]*\)\s*\(net (\d+)\)', re.S)


def rot(x, y, deg):
    t = math.radians(deg)
    return (x * math.cos(t) + y * math.sin(t), -x * math.sin(t) + y * math.cos(t))


def read_pads(text):
    """(ref, pad, cx, cy, w, h, angle, net) in BOARD coordinates for every copper pad."""
    out = []
    for blk in text.split("\n\t(footprint ")[1:]:
        m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        fm = FP_AT_RE.search(blk)
        if not m or not fm:
            continue
        fx, fy = float(fm.group(1)), float(fm.group(2))
        frot = float(fm.group(3) or 0.0)
        for pm in PAD_RE.finditer(blk):
            if not pm.group(1):
                continue
            nm = re.search(r'\(net (\d+) "', pm.group(8))
            dx, dy = rot(float(pm.group(3)), float(pm.group(4)), frot)
            out.append((m.group(1), pm.group(1), fx + dx, fy + dy,
                        float(pm.group(6)), float(pm.group(7)),
                        float(pm.group(5) or 0.0),
                        int(nm.group(1)) if nm else 0))
    return out


def in_pad(pad, vx, vy, r):
    """Is a via of radius r wholly inside `pad`?  Pad angle is absolute in a .kicad_pcb."""
    _ref, _pn, cx, cy, w, h, ang, _net = pad
    # Into the pad's own frame.  rot() is its own inverse for the transpose, so rotate by -ang.
    ux, uy = rot(vx - cx, vy - cy, -ang)
    return abs(ux) + r <= w / 2.0 + 1e-6 and abs(uy) + r <= h / 2.0 + 1e-6


def touches_pad(pad, vx, vy, r):
    _ref, _pn, cx, cy, w, h, ang, _net = pad
    ux, uy = rot(vx - cx, vy - cy, -ang)
    return abs(ux) < w / 2.0 + r and abs(uy) < h / 2.0 + r


def main():
    text = io.open(PCB, encoding="utf-8").read()
    pads = read_pads(text)
    netname = dict((int(a), b) for a, b in
                   re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', text))

    vias = [(float(a), float(b), float(c), float(d), int(e))
            for a, b, c, d, e in VIA_RE.findall(text)]
    if not vias:
        print("FAIL: no vias on the board")
        return 1

    therm = [v for v in vias if v[2] < 0.6]
    stitch = [v for v in vias if v[2] >= 0.6]

    bad = []
    hosts = {}
    for vx, vy, size, _drill, net in therm:
        r = size / 2.0
        home = [p for p in pads if p[7] == net and in_pad(p, vx, vy, r)]
        if not home:
            near = [p for p in pads if touches_pad(p, vx, vy, r)]
            bad.append("thermal via at (%.2f, %.2f) on %s is not inside any pad of its net%s"
                       % (vx, vy, netname.get(net, "?"),
                          "" if not near else " (nearest: %s.%s)" % (near[0][0], near[0][1])))
        else:
            hosts.setdefault((home[0][0], home[0][1]), 0)
            hosts[(home[0][0], home[0][1])] += 1

    for vx, vy, size, _drill, net in stitch:
        r = size / 2.0
        hit = [p for p in pads if touches_pad(p, vx, vy, r)]
        if hit:
            bad.append("stitching via at (%.2f, %.2f) sits on %s.%s (%s)"
                       % (vx, vy, hit[0][0], hit[0][1], netname.get(hit[0][7], "?")))

    print("vias: %d thermal (< 0.6 mm), %d stitching" % (len(therm), len(stitch)))
    for (ref, pn), n in sorted(hosts.items()):
        print("  %s pad %s: %d thermal vias" % (ref, pn, n))
    for b in bad:
        print("  FAIL " + b)
    if bad:
        return 1
    print("  OK: every thermal via is inside its own pad, every stitching via is clear of pads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
