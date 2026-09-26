# -*- coding: utf-8 -*-
"""How much room ONE stranded pad actually has: its reachable pocket, measured.

Why this exists
---------------
show_room.py sweeps a rectangle and prints where a via or track of a net is allowed to sit.
That answers "is this spot free", which is the right question while you are placing copper by
hand.  It is the wrong question for a pad the router gave up on, because a spot can be free
and still be no use: the copper between it and the pad may be solid.  Two separate rounds of
this re-layout recorded "zero legal via sites" for a stranded pad while show_room, pointed at
a window drawn around the same pad, reported legal sites in it -- both true, and confusing
until you notice they are claims about different sets.  Q7.5 is the worked example: the window
170,48.5..176,54 holds 3 legal 0.50 mm via sites, all of them at x ~ 175.7, and every one is
on the far side of a wall from the pad.

So this floods outward from the pad instead of sweeping a box.  The pocket it returns is the
set of positions a track of this net can actually reach without crossing anything, and every
figure below is reported over that set, not over a window.  A number measured over a window is
not evidence about a stranded pad, and this file exists so that distinction is checkable
rather than asserted.

    python scripts/show_pocket.py NET REF.PAD  [options]
    python scripts/show_pocket.py NET x y      [options]

    --via MM      via diameter to test for a layer change (default 0.50)
    --drill MM    its drill, for the hole-to-hole floor (default 0.20)
    --track MM    track width the pocket is flooded with (default 0.20, the board floor)
    --layer L     layer to flood (default F.Cu; every component here is top-side)
    --step MM     grid pitch (default 0.05)
    --window MM   half-size of the first window (default 8, grown as needed)
    --pcb BOARD   read a different board

What it reports, and what each figure means
-------------------------------------------
* The pocket: reachable cells and area.  Cells are `--step` squares, so area is cells x
  step^2 -- a cell count is only comparable against another at the same step.
* Legal via sites INSIDE the pocket, copper-only, then how many of those also clear the
  0.30 mm hole-to-hole floor (gen_pcb.HOLE_TO_HOLE).  Copper and fab are separate gates and a
  site can pass one and fail the other, so they are counted separately: KiCad's DRC does not
  check hole-to-hole between same-net vias, which is exactly where a pad with its own frozen
  via in it lands.
* If there are none, the nearest miss: the pocket cell that comes closest to taking a via,
  how short it is, and the obstacle that is binding.  That obstacle is the thing to consider
  moving or dropping; nothing else in the pocket is.
* The widest disc of legal track centres in the pocket, with its centre.  This separates two
  reasons a pocket can hold no via.  A thin corridor is widened by moving one neighbour; a
  pocket that is wide for tracks and still refuses a 0.50 mm via is being blocked by copper on
  the OTHER layers, which a corridor-widening nudge does not touch.
* Own-net copper already inside the pocket: vias of this net the pocket already contains.  A
  via is a layer change the net already owns, so a pad with one in reach is not sealed to its
  layer however few new via sites there are -- the router leaves these behind as fanout stubs
  when it then fails the net.

Zero legal via sites in the pocket is the load-bearing result: a through via is the only way
this net leaves `--layer` at this pad, so zero sites and no own-net via in reach together mean
the pad cannot leave the layer at all, and the pocket is the whole of the net's freedom there.

The obstacle model
------------------
Every obstacle and every clearance comes from show_room.obstacles(), so this file and
show_room.py agree by construction rather than by two people getting the same arithmetic
right.  That means: clearance is per-netclass via gen_pcb.net_clearance / pad_clearance and
the wider of the two nets wins; copper of the net itself is not an obstacle, because the map
is of where THIS net may go; a via is a through via and is tested against copper on every
layer; a track is tested against its own layer plus every via and through-hole pad; all
components on this board are top-side, so SMD pads block F.Cu and nothing else.

The pocket is flooded 8-connected, so it counts a diagonal step between two cells that share
only a corner as passable.  That is the generous reading: it can only make a pocket look
bigger or better connected than a 4-connected flood would, never smaller.

Pads come from the netlist and the placer, so they are right even when mccan.kicad_pcb is
stale.  Tracks and vias come from the generated board, so they are only as current as the last
run of gen_pcb.py -- re-run it before trusting a number.  Under a freeze
(scripts/routes_signal.json present) the router's copper is emitted verbatim and is a real
obstacle, so mccan.kicad_pcb, this file's default, is the board to measure against; see the
--pcb note in show_room.py for when it is not.

The window is grown until the pocket stops touching its edge, and the result says so.  This is
not a convenience: a window that clips the pocket reports a pocket that is too small and can
turn a pad that has somewhere to go into one that looks sealed.  Truncation can only
understate reachability, never overstate it, so a BOUNDED result is trustworthy and a clipped
one is not.  A pocket that does not close inside --max-window is reported as unbounded, which
is itself the answer: that pad is not the sealed one.
"""

import io
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pcb as G          # noqa: E402
import show_room as SR       # noqa: E402

BUCKET = 1.0        # mm; obstacle index cell, so a point only tests its own neighbourhood
MAX_WINDOW = 32.0   # mm half-size the window will grow to before giving up


def bucket_index(pads, segs, vias, half):
    """Obstacles keyed by the BUCKET cell they can reach, with `half` already added.

    A point then only has to test the obstacles in its own cell, which is what makes a
    100k-cell flood finish in seconds without numpy.  Everything is stored as
    (kind, geometry..., reach, label) with `reach` the distance our centre must keep.
    """
    idx = {}

    def add(lo_x, hi_x, lo_y, hi_y, item):
        for bi in range(int(math.floor(lo_x / BUCKET)), int(math.floor(hi_x / BUCKET)) + 1):
            for bj in range(int(math.floor(lo_y / BUCKET)), int(math.floor(hi_y / BUCKET)) + 1):
                idx.setdefault((bi, bj), []).append(item)

    for a, b, c, d, cl, lab in pads:
        r = half + cl
        add(a - r, c + r, b - r, d + r, ("pad", a, b, c, d, r, lab))
    for ax, ay, bx, by, need, lab in segs:
        r = half + need
        add(min(ax, bx) - r, max(ax, bx) + r, min(ay, by) - r, max(ay, by) + r,
            ("seg", ax, ay, bx, by, r, lab))
    for ax, ay, need, lab in vias:
        r = half + need
        add(ax - r, ax + r, ay - r, ay + r, ("via", ax, ay, r, lab))
    return idx


def slack_at(idx, px, py):
    """(slack, obstacle) for a centre at (px, py): >= 0 means legal, and by how much.

    Slack is the distance from our outline to the nearest obstacle's clearance boundary, so
    it doubles as the radius of the largest all-legal disc centred here.
    """
    best, who = 9e9, ""
    for o in idx.get((int(math.floor(px / BUCKET)), int(math.floor(py / BUCKET))), ()):
        if o[0] == "pad":
            _k, a, b, c, d, r, lab = o
            s = math.hypot(max(a - px, 0.0, px - c), max(b - py, 0.0, py - d)) - r
        elif o[0] == "seg":
            _k, ax, ay, bx, by, r, lab = o
            s = SR.pt_seg(px, py, ax, ay, bx, by) - r
        else:
            _k, ax, ay, r, lab = o
            s = math.hypot(px - ax, py - ay) - r
        if s < best:
            best, who = s, lab
    return best, who


def exact_slack(pads, segs, vias, half, px, py):
    """slack_at without the bucket index: the minimum over EVERY obstacle.

    slack_at only tests the obstacles whose clearance reaches into the point's own bucket,
    which is exact for deciding legality and exact for a negative slack -- anything that can
    push a slack below zero has that point inside its own reach, so it is always in the
    bucket.  It is NOT exact for a large positive slack, where the nearest obstacle may be
    further away than the bucket it was filed under.  The widest-disc figure is a large
    positive slack, so it is computed here instead.
    """
    best, who = 9e9, ""
    for a, b, c, d, cl, lab in pads:
        s = math.hypot(max(a - px, 0.0, px - c), max(b - py, 0.0, py - d)) - half - cl
        if s < best:
            best, who = s, lab
    for ax, ay, bx, by, need, lab in segs:
        s = SR.pt_seg(px, py, ax, ay, bx, by) - half - need
        if s < best:
            best, who = s, lab
    for ax, ay, need, lab in vias:
        s = math.hypot(px - ax, py - ay) - half - need
        if s < best:
            best, who = s, lab
    return best, who


def widest_disc(pocket, pads, segs, vias, half):
    """The pocket cell with the largest true slack, and that slack.

    Bucketed slack is an upper bound on the true slack, so working down the cells in bucketed
    order and stopping once the bound drops to the best exact value found is exact, and only
    touches a handful of cells.
    """
    best, out = -9e9, None
    for _bound, px, py in sorted(((v[2], v[0], v[1]) for v in pocket.values()), reverse=True):
        if _bound <= best:
            break
        s, who = exact_slack(pads, segs, vias, half, px, py)
        if s > best:
            best, out = s, (s, px, py, who)
    return out


def drills(text):
    """Every via drill on the board, for the hole-to-hole floor.

    Vias only.  Through-hole pad drills are not in here, so a site this reports as clearing
    the floor is cleared against vias and not against the connectors' own holes -- true for
    every pad this tool has been pointed at, all of which are in SMD fanout, but not a general
    guarantee.  The regex head is `[(]via\\b`: a via serialises with a newline after `(via`,
    so the literal "(via " matches nothing, and a bare "(via" also matches "(vias
    not_allowed)" in the zone keepouts.
    """
    return [(float(m.group(1)), float(m.group(2)), float(m.group(4)))
            for m in re.finditer(r'[(]via\b\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)'
                                 r'\s*\(drill ([-\d.]+)\)', text)]


def own_vias(text, code):
    """This net's own vias: layer changes it already has, which are not obstacles to it."""
    return [(float(m.group(1)), float(m.group(2)), float(m.group(3)))
            for m in re.finditer(r'[(]via\b\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)'
                                 r'\s*\(drill [-\d.]+\)\s*\(layers[^)]*\)\s*\(net (\d+)\)', text)
            if int(m.group(4)) == code]


def flood(code, start_cells, win, layer, track, step):
    """Reachable cells from `start_cells`, plus the track-slack of each, inside `win`.

    Returns (pocket, touched_edge, obstacles); pocket maps (i, j) -> (x, y, slack, obstacle),
    and the slack in it is the bucketed upper bound (see exact_slack).
    """
    x0, y0, x1, y1 = win
    nx = int(round((x1 - x0) / step)) + 1
    ny = int(round((y1 - y0) / step)) + 1
    mine, pads, segs, vias = SR.obstacles(code, win, layer)
    idx = bucket_index(pads, segs, vias, track / 2.0)
    pocket, edge, stack = {}, False, []

    def visit(i, j):
        if (i, j) in pocket or not (0 <= i < nx and 0 <= j < ny):
            return
        px, py = x0 + i * step, y0 + j * step
        s, who = slack_at(idx, px, py)
        if s < 0:
            return
        pocket[(i, j)] = (px, py, s, who)
        stack.append((i, j))

    for i, j in start_cells:
        visit(i, j)
    while stack:
        i, j = stack.pop()
        if i in (0, nx - 1) or j in (0, ny - 1):
            edge = True
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di or dj:
                    visit(i + di, j + dj)
    return pocket, edge, (mine, pads, segs, vias)


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    net = argv[1]
    rest = list(argv[2:])
    opt = {"--via": 0.50, "--drill": 0.20, "--track": 0.20, "--step": 0.05, "--window": 8.0}
    layer = "F.Cu"
    for k in list(opt):
        if k in rest:
            i = rest.index(k)
            opt[k] = float(rest[i + 1])
            rest = rest[:i] + rest[i + 2:]
    if "--layer" in rest:
        i = rest.index("--layer")
        layer = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    if "--pcb" in rest:
        i = rest.index("--pcb")
        SR.PCB = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    step, track, via, drill = opt["--step"], opt["--track"], opt["--via"], opt["--drill"]

    text = io.open(SR.PCB, encoding="utf-8").read()
    code = None
    for a, b in re.findall(r'\(net (\d+) "([^"]*)"\)', text):
        if b == net:
            code = int(a)
    if code is None:
        sys.exit("no net named %s on the board (a leading-slash name needs "
                 "MSYS_NO_PATHCONV=1 in Git Bash)" % net)

    # Where to flood from: a pad's whole footprint, or one point.
    if len(rest) == 1:
        comps, _n, padnet = G.read_netlist()
        comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
        pos = G.place(comps)[0]
        box = None
        for p in G.pads_board(comps, pos, padnet):
            if "%s.%s" % (p[0], p[1]) == rest[0]:
                box = (p[3] - p[5] / 2, p[4] - p[6] / 2, p[3] + p[5] / 2, p[4] + p[6] / 2)
                if p[2] != code:
                    sys.exit("%s is on %s, not %s"
                             % (rest[0], G.NETNAME.get(p[2], "?"), net))
        if box is None:
            sys.exit("no pad named %s" % rest[0])
        where, cx, cy = rest[0], (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    elif len(rest) == 2:
        cx, cy = float(rest[0]), float(rest[1])
        box = (cx, cy, cx, cy)
        where = "(%.3f, %.3f)" % (cx, cy)
    else:
        sys.exit(__doc__)

    print("pocket of %s at %s, flooded with a %.3f mm track on %s, step %g"
          % (net, where, track, layer, step))

    half = opt["--window"]
    while True:
        # The lattice is anchored to absolute board coordinates, not to the pad: cells sit on
        # exact multiples of --step wherever the window happens to start.  Anchoring to the pad
        # instead makes the cell count depend on the window size, which is how the same pocket
        # came out as 2771, 2762 and 2759 cells in three different measurements of it.
        x0 = step * math.floor((cx - half) / step + 1e-9)
        y0 = step * math.floor((cy - half) / step + 1e-9)
        win = (x0, y0, x0 + 2 * half, y0 + 2 * half)
        starts = []
        i0 = int(math.ceil((box[0] - x0) / step))
        i1 = int(math.floor((box[2] - x0) / step))
        j0 = int(math.ceil((box[1] - y0) / step))
        j1 = int(math.floor((box[3] - y0) / step))
        for i in range(i0, max(i0, i1) + 1):
            for j in range(j0, max(j0, j1) + 1):
                starts.append((i, j))
        pocket, edge, obs = flood(code, starts, win, layer, track, step)
        if not pocket:
            sys.exit("  no legal starting cell: a %.3f mm track does not fit at %s at all"
                     % (track, where))
        if not edge or half >= MAX_WINDOW:
            break
        half *= 2

    area = len(pocket) * step * step
    print("  lattice  cells on exact multiples of %g mm, origin (%.3f, %.3f)"
          % (step, x0, y0))
    print("  window   +/-%.1f mm, %s" % (half, "BOUNDED -- the pocket closes inside it"
                                         if not edge else
                                         "UNBOUNDED at +/-%.0f mm: the pocket runs off the "
                                         "window, so this pad is not sealed and the figures "
                                         "below are a floor, not a measurement" % MAX_WINDOW))
    print("  pocket   %d cell(s), %.2f mm2" % (len(pocket), area))

    xs = [v[0] for v in pocket.values()]
    ys = [v[1] for v in pocket.values()]
    print("  extent   %.3f..%.3f x %.3f..%.3f mm" % (min(xs), max(xs), min(ys), max(ys)))

    ws, wx, wy, who = widest_disc(pocket, obs[1], obs[2], obs[3], track / 2.0)
    print("  widest   disc of legal track centres has radius %.3f mm at (%.3f, %.3f); "
          "%s is what closes it" % (ws, wx, wy, who))

    # Via sites inside the pocket: copper first, then the fab's hole-to-hole floor.
    _mine, pads, segs, vias = SR.obstacles(code, (min(xs) - 1, min(ys) - 1,
                                                  max(xs) + 1, max(ys) + 1), None)
    vidx = bucket_index(pads, segs, vias, via / 2.0)
    legal, misses = [], []
    for (px, py, _s, _w) in pocket.values():
        s, who = slack_at(vidx, px, py)
        (legal if s >= 0 else misses).append((s, px, py, who))
    print("  via      %.2f/%.2f mm needs a clear %.2f mm circle on every layer: "
          "%d legal site(s) in the pocket" % (via, drill, via + 2 * _mine, len(legal)))

    if legal:
        h2h = []
        for s, px, py, who in legal:
            worst, wat = 9e9, ""
            for ax, ay, dd in drills(text):
                g = math.hypot(px - ax, py - ay) - (drill + dd) / 2.0
                if g < worst:
                    worst, wat = g, "a %.2f mm drill at (%.3f, %.3f)" % (dd, ax, ay)
            h2h.append((worst, px, py, s, wat))
        ok = [h for h in h2h if h[0] >= G.HOLE_TO_HOLE]
        h2h.sort(reverse=True)
        print("           of those, %d also clear the %.2f mm hole-to-hole floor"
              % (len(ok), G.HOLE_TO_HOLE))
        for worst, px, py, s, wat in h2h[:4]:
            print("             (%.3f, %.3f) copper slack %+.3f, hole-to-hole %+.3f vs %s"
                  % (px, py, s, worst - G.HOLE_TO_HOLE, wat))
    else:
        misses.sort(reverse=True)
        print("           nearest miss inside the pocket:")
        for s, px, py, who in misses[:4]:
            print("             (%.3f, %.3f) short by %.4f mm, bound by %s" % (px, py, -s, who))

    own = [(x, y, sz) for x, y, sz in own_vias(text, code)
           if (int(round((x - win[0]) / step)), int(round((y - win[1]) / step))) in pocket]
    if own:
        print("  own      %d via(s) of this net already inside the pocket -- it already "
              "changes layer here, so it is NOT sealed to %s:" % (len(own), layer))
        for x, y, sz in own:
            print("             %.2f mm via at (%.3f, %.3f)" % (sz, x, y))
    else:
        print("  own      no via of this net inside the pocket%s"
              % (", so with no legal site it cannot leave %s at this pad" % layer
                 if not legal else ""))


if __name__ == "__main__":
    main(sys.argv)
