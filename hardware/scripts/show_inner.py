# -*- coding: utf-8 -*-
"""What is actually in the way on an inner layer, in a window of the board.

Why this exists
---------------
Hand-routing on this board moved to the inner signal layers (In2.Cu and In5.Cu, the two inner
entries of gen_pcb.SIGNAL_LAYERS) once it went to six layers, and the reason it works there is
worth stating: those two layers carry no zones and no SMD pads.  An SMD pad exists on F.Cu
only; a zone exists where gen_pcb puts one, and neither In2 nor In5 gets one -- In4.Cu does
(the solid /VBAT plane), which is exactly why it is not one of these two (fault 7, fix
round 2).  So the ONLY things a track on an inner layer can hit are vias and through-hole
pads -- typically twenty of them where F.Cu has three hundred.

That is a completely different picture from the one you get by looking at the board, and it
is the picture you need before choosing a lane.  This prints it.

    python scripts/show_inner.py x0 y0 x1 y1            # obstacles in the window
    python scripts/show_inner.py x0 y0 x1 y1 --tracks   # and the inner copper already laid

Everything is in board millimetres, and every box is printed as the extent the clearance
check will actually measure against: pads at their true size, vias as the SQUARE box
gen_pcb.routes() models them with.  The square matters.  routes() measures box-to-box, so a
via that clears a disc of the same diameter can still foul a corner, and half the candidate
positions a mental picture accepts are rejected on that alone.

The obstacle list comes from the netlist and the placer, so it is right even when
mccan.kicad_pcb is stale; --tracks reads the generated board, so it is only as current as
the last run of gen_pcb.py.
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pcb as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(os.path.dirname(HERE), "mccan.kicad_pcb")


def short(name):
    return (name or "").rsplit("/", 1)[-1]


def obstacles():
    """(x0, y0, x1, y1, net, ref, pad) for every via and through-hole pad on the board."""
    comps, nets, padnet = G.read_netlist()
    G.NETNAME[0] = ""
    for code, name in nets:
        G.NETNAME[code] = name
    missing = [c["ref"] for c in comps if not c["fp"] or G.load_fp(c["fp"]) is None]
    comps = [c for c in comps if c["ref"] not in missing]
    pos = G.place(comps)[0]

    out = []
    for ref, pn, net, cx, cy, w, h, smd, _id in G.pads_board(comps, pos, padnet):
        if smd:
            continue                      # F.Cu only; invisible to an inner layer
        out.append((cx - w / 2., cy - h / 2., cx + w / 2., cy + h / 2.,
                    short(G.NETNAME.get(net, "")), ref, str(pn)))

    t = io.open(PCB, encoding="utf-8").read()
    names = dict((int(c), n) for c, n in
                 re.findall(r'\(net (\d+) "([^"]*)"\)', t.split("\n\t(footprint ")[0]))
    for m in re.finditer(r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)'
                         r'.*?\(net (\d+)\)', t, re.S):
        x, y, sz = float(m.group(1)), float(m.group(2)), float(m.group(3))
        out.append((x - sz / 2, y - sz / 2, x + sz / 2, y + sz / 2,
                    short(names.get(int(m.group(4)), "")), "via", ""))
    return out


def tracks():
    """(layer, net, width, x0, y0, x1, y1) for every segment on an inner layer."""
    t = io.open(PCB, encoding="utf-8").read()
    names = dict((int(c), n) for c, n in
                 re.findall(r'\(net (\d+) "([^"]*)"\)', t.split("\n\t(footprint ")[0]))
    pat = re.compile(r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
                     r'\s*\(width ([-\d.]+)\)\s*\(layer "([^"]+)"\)\s*\(net (\d+)\)', re.S)
    out = []
    for m in pat.finditer(t):
        layer = m.group(6)
        if not layer.startswith("In"):
            continue
        out.append((layer, short(names.get(int(m.group(7)), "")), float(m.group(5)),
                    float(m.group(1)), float(m.group(2)),
                    float(m.group(3)), float(m.group(4))))
    return out


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 4:
        sys.stderr.write(__doc__)
        return 2
    x0, y0, x1, y1 = [float(v) for v in args]
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0

    rows = [r for r in obstacles()
            if not (r[2] < x0 or r[0] > x1 or r[3] < y0 or r[1] > y1)]
    rows.sort(key=lambda r: (r[1], r[0]))
    for a, b, c, d, net, ref, pad in rows:
        print("%-6s %-4s %-16s x %7.2f..%7.2f  y %7.2f..%7.2f"
              % (ref, pad, net, a, c, b, d))
    print("# %d obstacle(s) in x %.2f..%.2f  y %.2f..%.2f" % (len(rows), x0, x1, y0, y1))

    if "--tracks" not in argv:
        return 0
    segs = [s for s in tracks()
            if not (max(s[3], s[5]) < x0 or min(s[3], s[5]) > x1
                    or max(s[4], s[6]) < y0 or min(s[4], s[6]) > y1)]
    segs.sort(key=lambda s: (s[0], s[1], s[4], s[3]))
    print("")
    for layer, net, w, ax, ay, bx, by in segs:
        print("%-7s %-12s w%.2f  (%7.2f,%7.2f) -> (%7.2f,%7.2f)"
              % (layer, net, w, ax, ay, bx, by))
    print("# %d inner segment(s)" % len(segs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
