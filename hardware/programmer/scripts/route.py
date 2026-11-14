# -*- coding: utf-8 -*-
"""Deterministic grid maze router for the programmer board's low-speed nets (plan Task 3).

The USB pair is hand-routed in gen_pcb.py; everything else that is not left to a pour is
routed here, in a fixed order, on a 0.05 mm grid, two layers, 8-way moves, vias costed.
Output is graded by KiCad DRC and check_board.py like any other copper -- the router is not
trusted to have honoured the rules (pcb-layout-routing: "grade its output").

Obstacles are kept as shapes: pads (axis-aligned rectangles, per layer), tracks (capsules),
vias and holes (discs).  A cell is free for a net of width w when every foreign shape is at
least CLEAR + w/2 away from the cell centre; a via cell additionally needs CLEAR + VIA/2 on
both layers.
"""
import heapq
import math

G = 0.05            # grid pitch, mm
CLEAR = 0.17        # router clearance (board rule 0.13; margin for grid and smoothing)
EDGE = 0.35         # copper to board edge
VIA, VIA_DRILL = 0.6, 0.3
VIA_COST = 40.0
# B.Cu is the ground plane: a step there costs double, so the router uses it to cross, not
# to travel, and the plane stays in one piece
LAYER_COST = {"F.Cu": 1.0, "B.Cu": 2.0}
LAYERS = ("F.Cu", "B.Cu")


class Shape:
    __slots__ = ("net", "layers", "kind", "a", "b", "r", "box")

    def __init__(self, net, layers, kind, a, b=None, r=0.0):
        # kind "rect": a = (x0, y0, x1, y1); "cap": a, b = ends, r = half width; "disc": a, r
        self.net, self.layers, self.kind, self.a, self.b, self.r = net, layers, kind, a, b, r
        if kind == "rect":
            self.box = a
        elif kind == "cap":
            self.box = (min(a[0], b[0]) - r, min(a[1], b[1]) - r,
                        max(a[0], b[0]) + r, max(a[1], b[1]) + r)
        else:
            self.box = (a[0] - r, a[1] - r, a[0] + r, a[1] + r)

    def dist(self, x, y):
        if self.kind == "rect":
            x0, y0, x1, y1 = self.a
            dx = max(x0 - x, 0.0, x - x1)
            dy = max(y0 - y, 0.0, y - y1)
            return math.hypot(dx, dy)
        if self.kind == "disc":
            return math.hypot(x - self.a[0], y - self.a[1]) - self.r
        (ax, ay), (bx, by) = self.a, self.b
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / L2))
        return math.hypot(x - ax - t * vx, y - ay - t * vy) - self.r


class Router:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.nx = int(round((x1 - x0) / G)) + 1
        self.ny = int(round((y1 - y0) / G)) + 1
        self.edge = (x0, y0, x1, y1)
        self.shapes = []
        self.tracks = []      # (net, layer, a, b, w)
        self.vias = []        # (net, (x, y))

    def xy(self, i, j):
        return (round(self.x0 + i * G, 4), round(self.y0 + j * G, 4))

    def ij(self, x, y):
        return (int(round((x - self.x0) / G)), int(round((y - self.y0) / G)))

    def add(self, shape):
        self.shapes.append(shape)

    def add_track(self, net, layer, a, b, w):
        self.tracks.append((net, layer, a, b, w))
        self.add(Shape(net, (layer,), "cap", a, b, w / 2.0))

    def add_via(self, net, p, size=VIA):
        self.vias.append((net, p, size))
        self.add(Shape(net, LAYERS, "disc", p, r=size / 2.0))

    # ---------------------------------------------------------------- free maps
    def blocked(self, net, half, layer):
        """Set of (i, j) a centreline of half-width `half` may not occupy on `layer`."""
        out = set()
        ex0, ey0, ex1, ey1 = self.edge
        m = EDGE + half
        for i in range(self.nx):
            x = self.x0 + i * G
            for j in range(self.ny):
                y = self.y0 + j * G
                if x < ex0 + m or x > ex1 - m or y < ey0 + m or y > ey1 - m:
                    out.add((i, j))
        for s in self.shapes:
            if s.net == net or layer not in s.layers:
                continue
            reach = CLEAR + half
            bx0, by0, bx1, by1 = s.box
            i0, j0 = self.ij(bx0 - reach, by0 - reach)
            i1, j1 = self.ij(bx1 + reach, by1 + reach)
            for i in range(max(i0 - 1, 0), min(i1 + 2, self.nx)):
                x = self.x0 + i * G
                for j in range(max(j0 - 1, 0), min(j1 + 2, self.ny)):
                    if (i, j) in out:
                        continue
                    if s.dist(x, self.y0 + j * G) < reach:
                        out.add((i, j))
        return out

    # ---------------------------------------------------------------- search
    def route(self, net, sources, targets, w, neck=None):
        """Connect any cell of `sources` to any cell of `targets` ({(i, j, layer)}).
        neck = (w_neck, cells): inside `cells` the narrower w_neck may be used.
        Returns the list of (i, j, layer) along the path, or None."""
        half = w / 2.0
        blk = {L: self.blocked(net, half, L) for L in LAYERS}
        vblk = self.blocked(net, VIA / 2.0, "F.Cu") | self.blocked(net, VIA / 2.0, "B.Cu")
        nb = None
        if neck:
            nb = {L: self.blocked(net, neck[0] / 2.0, L) for L in LAYERS}
            ncells = neck[1]
        self._maps = (blk, nb)

        def free(i, j, L):
            if (i, j) not in blk[L]:
                return True
            return bool(neck) and (i, j) in ncells and (i, j) not in nb[L]

        tcells = {(i, j) for i, j, _L in targets}
        tx = sum(i for i, _j in tcells) / len(tcells)
        ty = sum(j for _i, j in tcells) / len(tcells)

        def h(i, j):
            dx, dy = abs(i - tx), abs(j - ty)
            return max(dx, dy) + 0.414 * min(dx, dy) - 3.0

        openq, came, cost = [], {}, {}
        for s in sources:
            cost[s] = 0.0
            heapq.heappush(openq, (h(s[0], s[1]), 0.0, s))
            came[s] = None
        steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while openq:
            _f, c, node = heapq.heappop(openq)
            if c > cost.get(node, 1e18):
                continue
            if node in targets:
                path = []
                while node is not None:
                    path.append(node)
                    node = came[node]
                return path[::-1]
            i, j, L = node
            nbrs = []
            for di, dj, k in steps:
                n = (i + di, j + dj, L)
                if 0 <= n[0] < self.nx and 0 <= n[1] < self.ny and (free(n[0], n[1], L) or n in targets):
                    # a diagonal step must not cut a blocked corner
                    if di and dj and not (free(i + di, j, L) and free(i, j + dj, L)):
                        continue
                    nbrs.append((n, k))
            if (i, j) not in vblk:
                o = (i, j, "B.Cu" if L == "F.Cu" else "F.Cu")
                if free(i, j, o[2]) or o in targets:
                    nbrs.append((o, VIA_COST))
            for n, k in nbrs:
                nc = c + (k * LAYER_COST[n[2]] if n[2] == L else k)
                if nc < cost.get(n, 1e18):
                    cost[n] = nc
                    came[n] = node
                    heapq.heappush(openq, (nc + h(n[0], n[1]), nc, n))
        return None

    def _seg_free(self, a, b, blocked):
        """Every sample along a->b (cell coordinates) lands on a free cell."""
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2 + 1
        for k in range(n + 1):
            t = k / float(n)
            c = (int(round(a[0] + (b[0] - a[0]) * t)), int(round(a[1] + (b[1] - a[1]) * t)))
            if c in blocked:
                return False
        return True

    def _smooth(self, run, blocked):
        """Greedy line of sight over a cell run: keep the farthest visible point each time."""
        pts, i = [run[0]], 0
        while i < len(run) - 1:
            j = len(run) - 1
            while j > i + 1 and not self._seg_free(run[i], run[j], blocked):
                j -= 1
            pts.append(run[j])
            i = j
        return pts

    def commit(self, net, path, w, neck=None):
        """Turn a cell path from the last route() call into tracks and vias.  Within a layer
        the path is split where it enters or leaves the neck region, and each piece is
        smoothed by line of sight at the width it will be drawn with."""
        if not path:
            return []
        blk, nb = getattr(self, "_maps", (None, None))
        runs, cur = [], [path[0]]
        for a, b in zip(path, path[1:]):
            if a[2] != b[2]:
                runs.append(cur)
                self.add_via(net, self.xy(a[0], a[1]))
                cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        made = []
        for run in runs:
            if len(run) < 2:
                continue
            L = run[0][2]
            # pieces of equal neck membership; the one-step transition always belongs to the
            # narrow side (its cells are free at the narrow width, not necessarily the wide)
            m = [bool(neck) and (c[0], c[1]) in neck[1] for c in run]
            pieces, start, mem = [], 0, m[0]
            for k in range(1, len(run)):
                if m[k] == m[k - 1]:
                    continue
                if m[k - 1]:                       # narrow -> wide
                    pieces.append((run[start:k + 1], True))
                    start, mem = k, False
                else:                              # wide -> narrow
                    pieces.append((run[start:k], False))
                    start, mem = k - 1, True
            pieces.append((run[start:], mem))
            for piece, narrow in pieces:
                if len(piece) < 2:
                    continue
                ww = neck[0] if narrow else w
                blocked = (nb if narrow else blk)[L] if blk else set()
                cells = [(c[0], c[1]) for c in piece]
                pts = self._smooth(cells, blocked) if blk else cells
                for a, b in zip(pts, pts[1:]):
                    pa, pb = self.xy(a[0], a[1]), self.xy(b[0], b[1])
                    self.add_track(net, L, pa, pb, ww)
                    made.append((net, L, pa, pb, ww))
        return made
