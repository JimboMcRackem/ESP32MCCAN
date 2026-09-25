# -*- coding: utf-8 -*-
"""The nearest via a stranded pad can legally reach, printed as ROUTES/ROUTE_VIAS lines.

Why this exists
---------------
By the end of routing the recurring problem stopped being "no lane exists" and became "no
lane is LEFT": the autorouter takes nets in its own order, and the last arrivals find the
one thoroughfare across a crowded corner already full.  The summary calls both cases
boxed_in_static, but they want opposite fixes -- the first wants the parts moved, the second
wants the net to go first, and a placement change aimed at the second makes things worse.

The fix for the second is a ROUTES stub from the pad to a via.  gen_pcb lays ROUTES before it
autoroutes, so that stub is simply a net that is not competing; and In2.Cu and In5.Cu -- the
two inner layers of gen_pcb.SIGNAL_LAYERS -- carry no zones and no SMD pads, so once a pin is
on one of them it has left the contested band entirely.  In4.Cu is not one of them: it is the
solid /VBAT plane, not a routing layer (fault 7, fix round 2).  The stub does not need to be
long.  It needs to be LEGAL, which is the part that is tedious by hand and the part this does.

    python scripts/find_escape.py Q4.2 Q4.5 Q8.5
    python scripts/find_escape.py U8.10 --dir W --max 2.0
    ...                                 [--via SIZE] [--track W] [--step MM] [--pcb BOARD]

For each pad it sweeps outward and prints the nearest point where a through via clears every
layer AND the straight stub from the pad centre to it clears F.Cu -- then the two lines to
paste into layout_pcb.ROUTES and layout_pcb.ROUTE_VIAS.  Pads named in one invocation are
also kept clear of each other, so a row of escapes can be planned in one go.

--dir constrains the search to a compass direction (N S E W, comma-separated for several).
Worth using: the middle pin of a two-column package can only leave sideways, and letting the
sweep pick freely there just finds a closer point that is no use.

Why this does not use show_room's arithmetic
--------------------------------------------
This file models an obstacle the way gen_pcb.routes() models it, because a lane it clears has
to be a lane routes() will admit.  It therefore calls gen_pcb's own helpers directly --
_rect_gap and _seg_rect_gap for PADS, which routes() still models by their bounding box, and
_disc_disc_gap and _seg_disc_gap for VIAS, which it no longer does.  If routes() ever changes
how it measures either of them, this changes with it, which is the whole point.  (The
track-vs-track test at the bottom is this file's own grown-box approximation and always was;
it is the cautious direction for a search, and routes() does not have that test at all.)

It used to model a via as a square here too, matching what routes() then did.  Task 10's
ruling (task-10-step6-ruling.md) found that square the defect and not the caution: a via is
round, so its bounding box over-reports an off-axis intrusion by (sqrt(2)-1)*s/2 = 0.124 mm
on a 0.6 mm via.  A via 0.40 mm from its own pad's diagonal neighbour passed as a disc and
failed as a box by 0.025 mm, and the cure the box named was to move it in x, which is not the
axis the error was really about.  Both models now agree with show_room.py, which had the
honest picture of copper all along.

The board it reads matters, and which board is right changed when the router's copper was
frozen.  Before the freeze the answer was output/router/unrouted.kicad_pcb: gen_pcb laid
ROUTES first and then autorouted AROUND them, so autorouted copper was not an obstacle to a
new ROUTES entry, it was copper that would be re-laid, and sweeping against a routed board
rejected lanes the generator would have laid this copper into.

Once scripts/routes_signal.json exists that is no longer true.  Frozen copper is data: it is
emitted verbatim and it does not move for anything, so every one of its 4692 segments and 857
vias is an obstacle a new ROUTES entry genuinely has to miss.  Sweeping against the unrouted
board there is actively wrong -- it hands back lanes that are already full, and gen_pcb.py
rejects the route afterwards.

So the default follows the freeze: mccan.kicad_pcb while routes_signal.json exists, and
output/router/unrouted.kicad_pcb when it does not.  --pcb overrides either way; the one case
for forcing the unrouted board while a freeze is in place is planning a route you intend to
re-run the router after, which discards the freeze.
"""

import io
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pcb as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# The freeze picks the board -- see the docstring.  G.FROZEN is the same routes_signal.json
# gen_pcb tests for, so this default and gen_pcb's own branch cannot drift apart.
PCB = (os.path.join(os.path.dirname(HERE), "mccan.kicad_pcb") if os.path.exists(G.FROZEN)
       else os.path.join(os.path.dirname(HERE), "output", "router", "unrouted.kicad_pcb"))
MARGIN = 6.0                       # mm outside a box an obstacle can still reach into it
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def board(path):
    """(net codes by name, vias as (x, y, size, net), segments) read off a generated board."""
    text = io.open(path, encoding="utf-8").read()
    codes = dict((b, int(a)) for a, b in re.findall(r'\(net (\d+) "([^"]*)"\)', text))
    vias = []
    for m in re.finditer(r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)\s*'
                         r'\(drill ([-\d.]+)\)\s*\(layers[^)]*\)\s*\(net (\d+)\)', text):
        x, y, sz = float(m.group(1)), float(m.group(2)), float(m.group(3))
        vias.append((x, y, sz, int(m.group(5))))
    segs = []
    for m in re.finditer(r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*'
                         r'\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([-\d.]+)\)\s*'
                         r'\(layer "([^"]+)"\)\s*\(net (\d+)\)', text):
        segs.append((float(m.group(1)), float(m.group(2)),
                     float(m.group(3)), float(m.group(4)),
                     float(m.group(5)), m.group(6), int(m.group(7))))
    return codes, vias, segs


def clear(box, code, pads, vias, segs, layer=None, seg=None):
    """Is `box` (or `seg` inside it) clear of every foreign pad, via and track?

    This mirrors gen_pcb.routes() check 2 exactly, including its treatment of `layer`:
    None means "every layer", which for a through via is the truth, and is NOT the same
    as an inner layer -- an inner layer skips the SMD pads and a via must not.
    """
    for p in pads:
        if p[2] == code or (layer is not None and not G._pad_on(p, layer)):
            continue
        b = G._pad_box(p)
        if (b[2] < box[0] - MARGIN or b[0] > box[2] + MARGIN
                or b[3] < box[1] - MARGIN or b[1] > box[3] + MARGIN):
            continue
        g = (G._seg_rect_gap(seg[0], seg[1], seg[2], b) if seg else G._rect_gap(box, b))
        if g < G.pad_clearance(p, code):
            return False
    for vx, vy, vsz, vnet in vias:
        if vnet == code:
            continue
        # Box arithmetic stays the prefilter -- it is cheap and never misses a candidate --
        # but the disc decides, the way routes() decides.
        r = vsz / 2
        if (vx + r < box[0] - MARGIN or vx - r > box[2] + MARGIN
                or vy + r < box[1] - MARGIN or vy - r > box[3] + MARGIN):
            continue
        need = max(G.net_clearance(vnet), G.net_clearance(code))
        if seg:
            g = G._seg_disc_gap(seg[0], seg[1], seg[2], vx, vy, vsz)
        else:
            # No seg means `box` is a candidate VIA's own box, square by construction at
            # both call sites, so its centre and diameter come straight back out of it.
            g = G._disc_disc_gap((box[0] + box[2]) / 2, (box[1] + box[3]) / 2,
                                 box[2] - box[0], vx, vy, vsz)
        if g < need:
            return False
    for ax, ay, bx, by, w, lay, n in segs:
        if n == code or (layer is not None and lay != layer):
            continue
        if (max(ax, bx) < box[0] - MARGIN or min(ax, bx) > box[2] + MARGIN
                or max(ay, by) < box[1] - MARGIN or min(ay, by) > box[3] + MARGIN):
            continue
        # Grow the box by what the far track wants, then ask whether it reaches in.
        need = max(G.net_clearance(n), G.net_clearance(code)) + w / 2
        grown = (box[0] - need, box[1] - need, box[2] + need, box[3] + need)
        if G._seg_rect_gap((ax, ay), (bx, by), seg[2] if seg else 0.0, grown) <= 0.0:
            return False
    return True


def main(argv):
    names = [a for a in argv if not a.startswith("--") and "." in a and a[0].isalpha()]
    if not names:
        sys.stderr.write(__doc__)
        return 2

    def opt(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default

    global PCB
    PCB = opt("--pcb", PCB)
    via_sz = float(opt("--via", "0.6"))
    via_dr = float(opt("--drill", "%.3f" % (via_sz / 2)))
    trk = float(opt("--track", "0.25"))
    step = float(opt("--step", "0.05"))
    far = float(opt("--max", "3.5"))
    dirs = [DIRS[d.strip().upper()] for d in opt("--dir", "").split(",") if d.strip()]

    codes, bvias, segs = board(PCB)
    G.NETNAME = dict((v, k) for k, v in codes.items())
    comps, _nets, padnet = G.read_netlist()
    comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
    pos = G.place(comps)[0]
    pads = list(G.pads_board(comps, pos, padnet))

    routes, vias, taken, bad = [], [], [], 0
    for name in names:
        ref, pn = name.split(".", 1)
        hit = [p for p in pads if p[0] == ref and str(p[1]) == pn]
        if not hit:
            print("# %-10s no such pad" % name)
            bad += 1
            continue
        pad = hit[0]
        code, px, py = pad[2], pad[3], pad[4]
        net = G.NETNAME.get(code, "?")

        # Sweep outward in rings so the FIRST hit is the nearest one.
        best = None
        for k in range(int(round(0.4 / step)), int(round(far / step)) + 1):
            d = round(k * step, 3)
            cand = ([(px + ux * d, py + uy * d) for ux, uy in dirs] if dirs else
                    [(px + d * math.cos(a * math.pi / 60),
                      py + d * math.sin(a * math.pi / 60)) for a in range(120)])
            for vx, vy in cand:
                vx, vy = round(vx, 3), round(vy, 3)
                vb = (vx - via_sz / 2, vy - via_sz / 2, vx + via_sz / 2, vy + via_sz / 2)
                if not clear(vb, code, pads, bvias, segs):
                    continue
                # Candidate-vs-candidate is via-vs-via, so both are discs here too.
                if any(G._disc_disc_gap(vx, vy, via_sz,
                                        (t[0] + t[2]) / 2, (t[1] + t[3]) / 2,
                                        t[2] - t[0]) < G.net_clearance(code)
                       for t in taken):
                    continue
                sb = (min(px, vx) - trk / 2, min(py, vy) - trk / 2,
                      max(px, vx) + trk / 2, max(py, vy) + trk / 2)
                if not clear(sb, code, pads, bvias, segs, "F.Cu", ((px, py), (vx, vy), trk)):
                    continue
                best = (d, vx, vy, vb)
                break
            if best:
                break
        if not best:
            print("# %-10s %-22s NO legal via within %.2f mm" % (name, net, far))
            bad += 1
            continue
        taken.append(best[3])
        routes.append('    ("%s", "F.Cu", %.2f, [(%.3f, %.3f), (%.3f, %.3f)]),   # %s'
                      % (net, trk, px, py, best[1], best[2], name))
        vias.append('    ("%s", %.3f, %.3f, %.2f, %.2f),   # %s  %.3f mm out'
                    % (net, best[1], best[2], via_sz, via_dr, name, best[0]))

    if routes:
        print("# ROUTES")
        print("\n".join(routes))
        print("\n# ROUTE_VIAS")
        print("\n".join(vias))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
