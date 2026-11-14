# -*- coding: utf-8 -*-
"""Narrowest copper between a power path's terminals, by max-flow / min-cut.

  python check_plane_mincut.py [board.kicad_pcb]      exit 1 on any failure

check_plane_width.py cuts each pour along straight rows and columns; a straight cut is an upper
bound on the narrowest section, so a diagonal row of vias or a curved wall can neck a pour and
still pass it.  This gate measures the neck itself.  For every path in
check_power_paths.PATHS whose net has a pour, it:

  1. rasterises the net's copper on every copper layer on a STEP mm grid.  A cell is copper if
     its centre lies in the net's pour minus everything the fill must clear (other-net pads,
     vias, tracks and zones grown by the zone clearance, rule areas that forbid pour -- the same
     exact per-row geometry check_plane_width.py uses, runs under MIN_RUN dropped), or on one
     of the net's own pads or tracks;
  2. joins neighbouring cells, 8 ways, with Cauchy-Crofton capacities, so that the capacity of
     any cut is its LENGTH in mm.  Eight directions read a cut at 0.948 x its length square to
     the grid or at 45 degrees and 1.026 x at 22.5 degrees; capacities are scaled by 1/1.026,
     so a cut reads 0.92-1.0 x its true length at any angle -- never wide;
  3. joins the layers at the net's own vias and through-hole pads with unlimited capacity (the
     barrels are graded by check_power_paths.py), and ties the path's source pads to a source
     and its load pads to a sink;
  4. runs Dinic's max-flow.  The flow is the total copper width of the narrowest section
     between source and loads, summed over the layers that carry it in parallel, along ANY
     path -- and the residual graph locates it.

That width is graded against IPC-2152 for the path's current (20 K, 1 oz on every layer, as
check_power_paths.py).  Paths whose net has no pour are tracks, graded there.
"""
import collections
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from check_power_paths import load, ipc2152_width, RISE, PATHS  # noqa: E402
from check_plane_width import (poly_spans, rect_span, disc_span, capsule_span, subtract,  # noqa: E402
                               layer_obstacles, CLEAR, MIN_RUN)
from check_antenna import CU  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")
STEP = 0.1                       # mm grid
UNIT = 1e-5                      # mm of copper width per integer capacity unit
METRIC = (math.pi / 8) * (math.sin(math.radians(22.5)) * 2 + math.cos(math.radians(22.5)) * 2)
W_AXIS = STEP * math.pi / 8 / METRIC
W_DIAG = STEP * math.pi / (8 * math.sqrt(2)) / METRIC
INF = 1 << 60
CAP = 1.5     # flows stop at CAP x the IPC width: past that the exact width is not needed


# ------------------------------------------------------------------ copper raster
def row_spans(m, net, layer, c, cache):
    """Copper of `net` on `layer` along the row y = c: pour minus obstacles, plus own pads and
    tracks.  Sorted, merged (x0, x1) intervals."""
    spans = []
    for z in m["zones"]:
        if z[3] or z[0] != net or not z[2] or layer not in z[1]:
            continue
        sp = poly_spans(z[2], c, True)
        if not sp:
            continue
        if layer not in cache:
            cache[layer] = layer_obstacles(m, net, layer)
        cuts = []
        for kind, g in cache[layer]:
            if kind == "rect":
                s = rect_span(g, c, True, CLEAR)
            elif kind == "disc":
                s = disc_span(g[0], g[1], g[2] + CLEAR, c, True)
            elif kind == "track":
                s = capsule_span(g, c, True, CLEAR)
            else:
                s = None
                for cc in (c - g[1], c, c + g[1]):
                    for a, b in poly_spans(g[0], cc, True):
                        cuts.append((a - g[1], b + g[1]))
            if s:
                cuts.append(s)
        spans += [(a, b) for a, b in subtract(sp, cuts) if b - a >= MIN_RUN]
    for _k, n, lays, r in m["pads"]:
        if n == net and layer in lays:
            s = rect_span(r, c, True, 0.0)
            if s:
                spans.append(s)
    for t in m["tracks"]:
        if t[0] == net and t[1] == layer:
            s = capsule_span(t, c, True, 0.0)
            if s:
                spans.append(s)
    spans.sort()
    out = []
    for a, b in spans:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


class Graph(object):
    """Dinic's max-flow on flat arrays (pure Python: no numpy on this machine)."""

    def __init__(self):
        self.head, self.to, self.cap, self.nxt = [], [], [], []

    def node(self):
        self.head.append(-1)
        return len(self.head) - 1

    def arc(self, u, v, c, back=0):
        for a, b, cc in ((u, v, c), (v, u, back)):
            self.to.append(b)
            self.cap.append(cc)
            self.nxt.append(self.head[a])
            self.head[a] = len(self.to) - 1

    def maxflow(self, s, t):
        head, to, cap, nxt = self.head, self.to, self.cap, self.nxt
        n = len(head)
        flow = 0
        while True:
            level = [-1] * n
            level[s] = 0
            q = collections.deque([s])
            while q:
                u = q.popleft()
                if level[t] >= 0 and level[u] >= level[t]:
                    break          # nothing beyond the sink's level is on a shortest path
                e = head[u]
                while e != -1:
                    if cap[e] > 0 and level[to[e]] < 0:
                        level[to[e]] = level[u] + 1
                        q.append(to[e])
                    e = nxt[e]
            if level[t] < 0:
                return flow
            it = list(head)
            while True:
                # one augmenting path in the level graph, iteratively
                path = []
                u = s
                while u != t:
                    e = it[u]
                    while e != -1 and not (cap[e] > 0 and level[to[e]] == level[u] + 1):
                        e = nxt[e]
                    it[u] = e
                    if e == -1:
                        if not path:
                            break
                        level[u] = -1          # dead end: prune, step back
                        e = path.pop()
                        u = to[e ^ 1]
                        it[u] = nxt[it[u]]
                        continue
                    path.append(e)
                    u = to[e]
                if u != t:
                    break
                f = min(cap[e] for e in path)
                for e in path:
                    cap[e] -= f
                    cap[e ^ 1] += f
                flow += f

    def reachable(self, s):
        seen = [False] * len(self.head)
        seen[s] = True
        q = collections.deque([s])
        while q:
            u = q.popleft()
            e = self.head[u]
            while e != -1:
                if self.cap[e] > 0 and not seen[self.to[e]]:
                    seen[self.to[e]] = True
                    q.append(self.to[e])
                e = self.nxt[e]
        return seen


def pad_of(m, key):
    hits = [p for p in m["pads"] if p[0] == key]
    if not hits:
        raise KeyError("no pad %s on the board" % key)
    return hits


def min_cut(m, net, srcs, dsts, step=STEP, cap=None):
    """(narrowest copper width mm between the source and load pads, where it is).

    With `cap` (mm), the flow stops at that width: a result equal to `cap` means "at least
    cap" -- enough to grade a path without finding the whole of a wide plane's cut."""
    layers = sorted(set(l for z in m["zones"] if not z[3] and z[0] == net for l in z[1]) |
                    set(l for p in m["pads"] if p[1] == net for l in p[2]) |
                    set(t[1] for t in m["tracks"] if t[0] == net), key=CU.index)
    xs, ys = [], []
    for z in m["zones"]:
        if not z[3] and z[0] == net:
            xs += [p[0] for p in z[2]]
            ys += [p[1] for p in z[2]]
    for _k, n, _l, r in m["pads"]:
        if n == net:
            xs += [r[0], r[2]]
            ys += [r[1], r[3]]
    for t in m["tracks"]:
        if t[0] == net:
            xs += [t[2] - t[6], t[4] + t[6], t[2] + t[6], t[4] - t[6]]
            ys += [t[3] - t[6], t[5] + t[6], t[3] + t[6], t[5] - t[6]]
    x0 = math.floor(min(xs) / step) * step - step
    y0 = math.floor(min(ys) / step) * step - step
    nx = int(math.ceil((max(xs) - x0) / step)) + 2
    ny = int(math.ceil((max(ys) - y0) / step)) + 2

    g = Graph()
    cell = {}                                    # layer -> {(i, j): node}
    cache = {}
    for layer in layers:
        cl = cell[layer] = {}
        for j in range(ny):
            c = y0 + (j + 0.5) * step
            for a, b in row_spans(m, net, layer, c, cache):
                for i in range(max(0, int(math.ceil((a - x0) / step - 0.5))),
                               min(nx, int(math.floor((b - x0) / step - 0.5)) + 1)):
                    cl[(i, j)] = g.node()
        wa, wd = int(round(W_AXIS / UNIT)), int(round(W_DIAG / UNIT))
        for (i, j), u in cl.items():
            for di, dj, w in ((1, 0, wa), (0, 1, wa), (1, 1, wd), (-1, 1, wd)):
                v = cl.get((i + di, j + dj))
                if v is not None:
                    g.arc(u, v, w, w)

    def cells_in(layer, r):
        """Copper cells of `layer` whose centre is in the box r; else the cell at its centre."""
        cl = cell.get(layer, {})
        i0 = int(math.ceil((r[0] - x0) / step - 0.5))
        i1 = int(math.floor((r[2] - x0) / step - 0.5))
        j0 = int(math.ceil((r[1] - y0) / step - 0.5))
        j1 = int(math.floor((r[3] - y0) / step - 0.5))
        out = [cl[(i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) if (i, j) in cl]
        if not out:
            ci = int(math.floor(((r[0] + r[2]) / 2 - x0) / step))
            cj = int(math.floor(((r[1] + r[3]) / 2 - y0) / step))
            if (ci, cj) in cl:
                out = [cl[(ci, cj)]]
        return out

    # the net's own vias and through-hole pads join every layer they touch
    for n, x, y, size, _d in m["vias"]:
        if n != net:
            continue
        hub = g.node()
        h = size / 2
        for layer in layers:
            for u in cells_in(layer, (x - h, y - h, x + h, y + h)):
                g.arc(hub, u, INF, INF)
    for key, n, lays, r in m["pads"]:
        if n == net and len(lays) > 1:
            hub = g.node()
            for layer in lays:
                if layer in cell:
                    for u in cells_in(layer, r):
                        g.arc(hub, u, INF, INF)

    s, t = g.node(), g.node()
    s_in = None
    if cap is not None:
        s_in, s = s, g.node()
        g.arc(s_in, s, int(round(cap / UNIT)))
    for keys, end in ((srcs, s), (dsts, t)):
        for key in keys:
            for _k, _n, lays, r in pad_of(m, key):
                for layer in lays:
                    if layer in cell:
                        for u in cells_in(layer, r):
                            if end == s:
                                g.arc(s, u, INF)
                            else:
                                g.arc(u, t, INF)
    flow = g.maxflow(s_in if s_in is not None else s, t)
    if flow >= INF:
        return float("inf"), "source and load share copper with no cut between them"
    if cap is not None and flow >= int(round(cap / UNIT)):
        return cap, "(capped: at least this wide)"

    if flow == 0:
        return 0.0, "no copper joins source and load"

    seen = g.reachable(s)
    where = collections.defaultdict(list)
    for layer, cl in cell.items():
        for (i, j), u in cl.items():
            if not seen[u]:
                continue
            for di, dj in ((1, 0), (0, 1), (1, 1), (-1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1)):
                v = cl.get((i + di, j + dj))
                if v is not None and not seen[v]:
                    where[layer].append((x0 + (i + 0.5) * step, y0 + (j + 0.5) * step))
    desc = "; ".join("%s x %.1f..%.1f y %.1f..%.1f" % (
        l, min(p[0] for p in pts), max(p[0] for p in pts),
        min(p[1] for p in pts), max(p[1] for p in pts))
        for l, pts in sorted(where.items(), key=lambda kv: CU.index(kv[0])))
    return flow * UNIT, desc or "no copper cut"


def check_model(m, paths):
    f, log = [], []
    for label, net, src, dst, amps in paths:
        if not any(not z[3] and z[0] == net and z[2] for z in m["zones"]):
            continue
        need = ipc2152_width(amps)
        got, where = min_cut(m, net, src, dst, cap=CAP * need)
        if where.startswith("(capped"):
            log.append("  %-16s %-9s %4.1f A  need %5.2f mm  min cut >= %5.2f mm (%g x need)"
                       % (label, net, amps, need, got, CAP))
        else:
            log.append("  %-16s %-9s %4.1f A  need %5.2f mm  min cut   %5.2f mm  at %s"
                       % (label, net, amps, need, got, where))
        if got < need:
            f.append("%s (%s): min cut %.2f mm < %.2f mm for %.1f A (IPC-2152, %g K) at %s"
                     % (label, net, got, need, amps, RISE, where))
    return f, log


def check(path=PCB):
    return check_model(load(open(path, encoding="utf-8").read()), PATHS)


def main():
    f, log = check()
    print("plane min-cut (IPC-2152, %g K, 1 oz, summed over parallel layers):" % RISE)
    for line in log:
        print(line)
    for line in f:
        print("FAIL " + line)
    print("plane_mincut: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
