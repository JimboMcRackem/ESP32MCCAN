# -*- coding: utf-8 -*-
"""Where a track or a via of one net is ALLOWED to sit, printed as a map of the window.

Why this exists
---------------
show_inner.py answers "what is in the way".  By the end of routing that stopped being the
useful question: the obstacle list around a stranded pin is twenty items long, half of them
on layers you were not thinking about, and the clearance each one wants depends on its
netclass.  Working that arithmetic by hand is slow, and slow in a way that hides the answer
-- more than one dead end on this board was found only after a route had been designed
against a wall that was never there, and one via position was rejected twice before the
thing rejecting it turned out to be a track on In2.Cu.

So this asks the question the other way round.  Give it a net and a window and it sweeps a
grid, tests every point against every obstacle at the clearance the rules actually apply,
and prints where the answer is yes.  A corridor you can see is a corridor you can route.

    python scripts/show_room.py NET x0 y0 x1 y1 --via [SIZE]
    python scripts/show_room.py NET x0 y0 x1 y1 --track LAYER [WIDTH]
    ...                                         [--step MM] [--pcb BOARD]

    '#' legal   '.' short by < 0.1 mm   ':' short by < 0.3 mm   ' ' worse

A via is a through via, so it is tested against copper on EVERY layer -- that is usually the
surprise.  A track is tested against its own layer plus every via and through-hole pad.  All
components on this board are top-side, so SMD pads block F.Cu and nothing else.

Copper of the net itself is not an obstacle: the map shows where this net may go, which
includes straight into its own pads.  The window is in board millimetres; obstacles up to
4 mm outside it are still counted.

The pads come from the netlist and the placer, so they are right even when mccan.kicad_pcb
is stale.  The tracks and vias come from the generated board, so they are only as current as
the last run of gen_pcb.py -- re-run it before trusting a map.

--pcb reads a different board.  Which board a ROUTES entry should be planned against depends
on whether the router's copper is frozen, and it is not the same answer it used to be.

While there is no scripts/routes_signal.json, gen_pcb lays ROUTES BEFORE it autoroutes, so
autorouted copper is not an obstacle to a new hand route -- it is copper that will be re-laid
around it.  Planning against mccan.kicad_pcb then rejects lanes that are actually free, and
output/router/unrouted.kicad_pcb (the same board with the signal copper left out) is what to
point --pcb at.

Once routes_signal.json exists that reasoning is void.  Frozen copper is emitted verbatim and
re-routes for nothing, so it is a real obstacle and mccan.kicad_pcb -- this file's default --
is the board to plan against.  Sweeping the unrouted board under a freeze returns corridors
that are already full, and gen_pcb.py then refuses the route.
"""

import io
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pcb as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(os.path.dirname(HERE), "mccan.kicad_pcb")   # --pcb overrides
MARGIN = 4.0    # mm outside the window an obstacle can still reach into it


def pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / d2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def obstacles(code, win, layer):
    """(clearance, pads, segments, vias) that a `code` object in `win` could foul.

    `layer` None means a through via: copper on every layer counts, SMD pads included.
    Otherwise only that layer's tracks count, plus the vias and through-hole pads, which
    are on all of them.  Each obstacle carries the distance its own centre line or edge
    has to keep from ours, so the sweep below only adds our half-width.
    """
    x0, y0, x1, y1 = win
    comps, _nets, padnet = G.read_netlist()
    comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
    pos = G.place(comps)[0]
    text = io.open(PCB, encoding="utf-8").read()
    G.NETNAME = dict((int(a), b) for a, b in
                     re.findall(r'\(net (\d+) "([^"]*)"\)', text))

    def near(a, b, c, d):
        return not (c < x0 - MARGIN or a > x1 + MARGIN or
                    d < y0 - MARGIN or b > y1 + MARGIN)

    mine = G.net_clearance(code)
    pads = []
    for p in G.pads_board(comps, pos, padnet):
        ref, pn, pnet, cx, cy, w, h, smd, _id = p
        if pnet == code or (smd and layer not in (None, "F.Cu")):
            continue
        if not near(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2):
            continue
        pads.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                     G.pad_clearance(p, code),
                     "%s.%s %s" % (ref, pn, G.NETNAME.get(pnet, "?"))))

    segs = []
    for m in re.finditer(r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*'
                         r'\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([-\d.]+)\)\s*'
                         r'\(layer "([^"]+)"\)\s*\(net (\d+)\)', text):
        n = int(m.group(7))
        if n == code or (layer is not None and m.group(6) != layer):
            continue
        ax, ay, bx, by, w = [float(m.group(i)) for i in (1, 2, 3, 4, 5)]
        if not near(min(ax, bx) - w, min(ay, by) - w, max(ax, bx) + w, max(ay, by) + w):
            continue
        segs.append((ax, ay, bx, by, w / 2 + max(mine, G.net_clearance(n)),
                     "%s %s" % (m.group(6), G.NETNAME.get(n, "?"))))

    vias = []
    for m in re.finditer(r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)\s*'
                         r'\(drill ([-\d.]+)\)\s*\(layers[^)]*\)\s*\(net (\d+)\)', text):
        n = int(m.group(5))
        if n == code:
            continue
        ax, ay, sz = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if not near(ax - sz, ay - sz, ax + sz, ay + sz):
            continue
        vias.append((ax, ay, sz / 2 + max(mine, G.net_clearance(n)),
                     "via " + G.NETNAME.get(n, "?")))
    return mine, pads, segs, vias


def main(argv):
    if len(argv) < 7:
        sys.exit(__doc__)
    net = argv[1]
    x0, y0, x1, y1 = [float(a) for a in argv[2:6]]
    rest = argv[6:]
    step = 0.05
    if "--pcb" in rest:
        global PCB
        i = rest.index("--pcb")
        PCB = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    if "--step" in rest:
        i = rest.index("--step")
        step = float(rest[i + 1])
        rest = rest[:i] + rest[i + 2:]
    if rest[0] == "--via":
        layer = None
        size = float(rest[1]) if len(rest) > 1 else 0.6
        what = "via %.2f mm" % size
    elif rest[0] == "--track":
        layer = rest[1]
        size = float(rest[2]) if len(rest) > 2 else 0.25
        what = "track %.3f mm on %s" % (size, layer)
    else:
        sys.exit(__doc__)
    half = size / 2

    code = None
    text = io.open(PCB, encoding="utf-8").read()
    for a, b in re.findall(r'\(net (\d+) "([^"]*)"\)', text):
        if b == net:
            code = int(a)
    if code is None:
        sys.exit("no net named %s on the board" % net)
    mine, pads, segs, vias = obstacles(code, (x0, y0, x1, y1), layer)

    def slack(px, py):
        best, who = 9e9, ""
        for a, b, c, d, cl, lab in pads:
            s = math.hypot(max(a - px, 0.0, px - c), max(b - py, 0.0, py - d)) - half - cl
            if s < best:
                best, who = s, lab
        for ax, ay, bx, by, need, lab in segs:
            s = pt_seg(px, py, ax, ay, bx, by) - half - need
            if s < best:
                best, who = s, lab
        for ax, ay, need, lab in vias:
            s = math.hypot(px - ax, py - ay) - half - need
            if s < best:
                best, who = s, lab
        return best, who

    nx = int(round((x1 - x0) / step)) + 1
    ny = int(round((y1 - y0) / step)) + 1
    print("%s of %s (clearance %.2f), window %.3f,%.3f..%.3f,%.3f step %.3f"
          % (what, net, mine, x0, y0, x1, y1, step))
    ruler = " " * 12 + "|"
    for i in range(nx):
        x = x0 + i * step
        ruler += "%d" % (int(round(x)) % 10) if abs(x - round(x)) < step / 2 else " "
    print(ruler + "|")
    seen = []
    for j in range(ny - 1, -1, -1):
        py = y0 + j * step
        line = ""
        for i in range(nx):
            px = x0 + i * step
            s, who = slack(px, py)
            line += "#" if s >= 0 else ("." if s > -0.1 else (":" if s > -0.3 else " "))
            seen.append((s, px, py, who))
        print("  y %8.3f |%s|" % (py, line))
    print(ruler + "|")
    seen.sort(reverse=True)
    good = [s for s in seen if s[0] >= 0]
    print("legal: %d of %d point(s)" % (len(good), nx * ny))
    print("roomiest, with the tightest neighbour named:" if good
          else "least bad, with the blocker named:")
    for s, px, py, who in seen[:8]:
        print("  (%8.3f,%8.3f)  %s %.3f   %s"
              % (px, py, "slack" if s >= 0 else "short", abs(s), who))


if __name__ == "__main__":
    main(sys.argv)
