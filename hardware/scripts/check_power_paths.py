# -*- coding: utf-8 -*-
"""Power paths, Kelvin sense, CAN pair and the U10 ON guard (plan4 phase B, Task 6; spec 5.2).

  python check_power_paths.py [board.kicad_pcb]

1. CAPACITY.  For each power path (source pads -> load pads, one net), the narrowest copper
   cross-section is the minimum cut of the net's copper graph, which by max-flow/min-cut is the
   maximum flow when every copper item is given its cross-section as a capacity.  So the
   "narrowest cut, summed across parallel layers" is computed exactly, as a max flow:
     track ......... its width (every layer is 1 oz);
     via ........... its barrel, pi * drill * 25 um, as an equivalent width of 1 oz (35 um) foil;
     pad, zone ..... unbounded -- a pad is a terminal, and a zone's own neck is graded by
                     check_plane_width.py (row/column cuts across the raster);
     pad -> zone ... unbounded when the zone connects pads solid, else 2 thermal spokes
                     (KiCad's min_resolved_spokes) of the zone's thermal_bridge_width.
   Each path must carry its current at <= RISE K by IPC-2152 (the generic chart fit below).
2. KELVIN.  U10 pin 4 (SNS) and pin 5 (VBAT_PROT) each reach R100's pad of the same net through
   a chain of tracks and vias that touches no other pad and no zone: the sense trace joins the
   current path only AT the resistor pad.
3. CAN PAIR.  CANH/CANL (and U6-CANH/U6-CANL): every pad of each net is connected by copper;
   along the signal path -- the shortest track chain from the connector pad to the choke pad
   (J8 -> L6 bus side; U6 -> L6 transceiver side) -- the two lengths differ by <= CAN_SKEW mm
   and >= CAN_COUPLED of each path runs within CAN_GAP mm (centre to centre) of the partner's.
   Test-point stubs hang off the pair and are not part of the path.  CAN_GAP is 3 mm because
   the pair has to fan out to L6's pins (2.5 mm apart) and J8's (4.6 mm).
4. U10 ON (pin 9, left open on its internal 1 Mohm pull-up -- README layout note, LTC4380 Rev. C
   Pin Functions: leakage to ground < 1 uA).  No copper of another net within ON_CLEAR mm of the
   pad on F.Cu or In1.Cu.  Excluded, because they cannot be moved: U10's own pads (0.5 mm pitch,
   0.16 mm gaps), and the first ON_CLEAR mm of a neighbouring U10 pin's fan-out track.  A zone on
   one of those layers passes only if a copperpour-not-allowed rule area covers the pad grown by
   ON_CLEAR there.
Exit 1 on any failure.
"""
import math
import os
import re
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from check_placement import footprints  # noqa: E402
from check_antenna import point_in_poly, layers_of, CU  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")
RISE = 20.0                 # K
OZ_MM = 0.035               # 1 oz foil
BARREL_MM = 0.025           # plated via wall
INF = 1e9

# (label, net, [source pads], [load pads], amps)
PATHS = [
    # Q13 || Q14 (enclosure.md s.9): 6.4 A into the pair, and each FET's own leg at its 3.2 A share
    ("feed B in", "FEED_B_P", ["J9.1"], ["Q13.5", "Q14.5"], 6.4),
    ("feed B in Q14", "FEED_B_P", ["J9.1"], ["Q14.5"], 3.2),
    ("feed B rail", "VBAT_B", ["Q13.1", "Q13.2", "Q13.3", "Q14.1", "Q14.2", "Q14.3"], ["U14.15"], 6.4),
    ("feed B rail Q14", "VBAT_B", ["Q14.1", "Q14.2", "Q14.3"], ["U14.15"], 3.2),
    ("feed B return", "GND_B", ["J10.2", "J11.2"], ["J9.2"], 6.4),
    ("pod L", "POD_L_P", ["U14.12", "U14.13", "U14.14"], ["J10.1"], 3.2),
    ("pod R", "POD_R_P", ["U14.8", "U14.9", "U14.10"], ["J11.1"], 3.2),
    ("feed A in", "FEED_P", ["J1.1"], ["Q10.2"], 1.0),
    ("feed A mid", "MID", ["Q10.3"], ["Q11.3"], 1.0),
    ("feed A sense", "SNS", ["Q11.2"], ["R100.1"], 1.0),
    ("feed A prot", "VBAT_PROT", ["R100.2"], ["L2.1"], 1.0),
    ("feed A filt", "VBAT_F", ["L2.4"], ["L1.1"], 1.0),
    ("feed A rail", "VBAT", ["L1.2"], ["U11.20", "U11.21", "U11.22", "U11.23",
                                       "U12.20", "U12.21", "U12.22", "U12.23",
                                       "U13.20", "U13.21", "U13.22", "U13.23"], 1.0),
    ("feed A return", "GND_IN", ["J1.2"], ["L2.2"], 1.0),
]
KELVIN = [("U10.4", "R100.1"), ("U10.5", "R100.2")]
CAN_PAIRS = [(("CANH", "J8.1", "L6.4"), ("CANL", "J8.2", "L6.3")),
             (("Net-(U6-CANH)", "U6.7", "L6.1"), ("Net-(U6-CANL)", "U6.6", "L6.2"))]
CAN_SKEW, CAN_GAP, CAN_COUPLED = 2.0, 3.0, 0.8
ON_PAD, ON_CLEAR, ON_LAYERS = "U10.9", 0.5, ("F.Cu", "In1.Cu")


def ipc2152_width(amps, rise=RISE):
    """IPC-2152 conductor width (mm, 1 oz) -- the widely used fit to the generic chart:
    A [mil^2] = (117.555 * dT^-0.913 + 1.15) * I^(0.84 * dT^-0.018 + 1.159)."""
    area = (117.555 * rise ** -0.913 + 1.15) * amps ** (0.84 * rise ** -0.018 + 1.159)
    return area / (OZ_MM / 0.0254) * 0.0254   # mil^2 / foil mil -> width mil -> mm


def via_width(drill):
    return math.pi * drill * BARREL_MM / OZ_MM


def short(n):
    return n.rsplit("/", 1)[-1]


# ------------------------------------------------------------------ board model
def load(text):
    names = dict((int(c), short(n)) for c, n in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', text))
    fps = footprints(text)
    pads = []   # (key "REF.N", net, layers, rect)
    for ref, d in fps.items():
        for name, x, y, w, h, net, typ in d["pads"]:
            if typ == "np_thru_hole" or not net:
                continue
            lays = list(CU) if typ == "thru_hole" else [d["layer"]]
            pads.append(("%s.%s" % (ref, name), net, lays,
                         (x - w / 2, y - h / 2, x + w / 2, y + h / 2)))
    tracks = []  # (net, layer, x0, y0, x1, y1, w)
    for blk in text.split("\n\t(segment")[1:]:
        g = lambda p: re.search(p, blk)  # noqa: E731
        s, e = g(r"\(start ([-\d.]+) ([-\d.]+)\)"), g(r"\(end ([-\d.]+) ([-\d.]+)\)")
        w, l, n = g(r"\(width ([-\d.]+)\)"), g(r'\(layer "([^"]+)"\)'), g(r"\(net (\d+)")
        tracks.append((names.get(int(n.group(1)), ""), l.group(1), float(s.group(1)),
                       float(s.group(2)), float(e.group(1)), float(e.group(2)), float(w.group(1))))
    vias = []    # (net, x, y, size, drill)
    for blk in text.split("\n\t(via")[1:]:
        g = lambda p: re.search(p, blk)  # noqa: E731
        at, sz, dr, n = (g(r"\(at ([-\d.]+) ([-\d.]+)\)"), g(r"\(size ([-\d.]+)\)"),
                         g(r"\(drill ([-\d.]+)\)"), g(r"\(net (\d+)"))
        vias.append((names.get(int(n.group(1)), ""), float(at.group(1)), float(at.group(2)),
                     float(sz.group(1)), float(dr.group(1))))
    zones = []   # (net, layers, poly, rule, nopour, solid, bridge, name)
    for blk in text.split("\n\t(zone")[1:]:
        net = re.search(r'\(net_name "([^"]*)"\)', blk)
        lay = re.search(r'\n\t\t\(layers? ([^)]*)\)', blk)
        name = re.search(r'\n\t\t\(name "([^"]*)"\)', blk)
        pts = re.search(r"\(polygon\s*\(pts(.*?)\n\s*\)", blk, re.S)
        poly = [(float(a), float(b)) for a, b in
                re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", pts.group(1))] if pts else []
        br = re.search(r"\(thermal_bridge_width ([-\d.]+)\)", blk)
        zones.append((short(net.group(1)) if net else "", layers_of(lay.group(1)) if lay else [],
                      poly, "(keepout" in blk, "(copperpour not_allowed)" in blk,
                      bool(re.search(r"\(connect_pads\s+yes", blk)),
                      float(br.group(1)) if br else 0.5, name.group(1) if name else "?"))
    return dict(pads=pads, tracks=tracks, vias=vias, zones=zones)


# ------------------------------------------------------------------ geometry
def seg_dist(p, q, r):
    (x0, y0), (x1, y1) = p, q
    dx, dy = x1 - x0, y1 - y0
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((r[0] - x0) * dx + (r[1] - y0) * dy) / n))
    return math.hypot(x0 + t * dx - r[0], y0 + t * dy - r[1])


def seg_seg(a0, a1, b0, b1):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = orient(b0, b1, a0), orient(b0, b1, a1)
    d3, d4 = orient(a0, a1, b0), orient(a0, a1, b1)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4:
        return 0.0
    return min(seg_dist(a0, a1, b0), seg_dist(a0, a1, b1), seg_dist(b0, b1, a0), seg_dist(b0, b1, a1))


def rect_pt(r, p):
    dx = max(r[0] - p[0], 0.0, p[0] - r[2])
    dy = max(r[1] - p[1], 0.0, p[1] - r[3])
    return math.hypot(dx, dy)


def seg_rect(p, q, r):
    if r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]:
        return 0.0
    edges = [((r[0], r[1]), (r[2], r[1])), ((r[2], r[1]), (r[2], r[3])),
             ((r[2], r[3]), (r[0], r[3])), ((r[0], r[3]), (r[0], r[1]))]
    return min(seg_seg(p, q, a, b) for a, b in edges)


def rect_in_poly(r, poly):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    return point_in_poly(cx, cy, poly)


EPS = 1e-3


# ------------------------------------------------------------------ net graph
class Graph(object):
    """Copper items of one net as nodes with capacities; node-split for max flow."""

    def __init__(self, m, net):
        self.items = []   # (kind, key, layers, geom, cap)
        for k, n, lays, r in m["pads"]:
            if n == net:
                self.items.append(("pad", k, lays, r, INF))
        for n, l, x0, y0, x1, y1, w in m["tracks"]:
            if n == net:
                self.items.append(("track", "%s(%.2f,%.2f)-(%.2f,%.2f)" % (l, x0, y0, x1, y1),
                                   [l], ((x0, y0), (x1, y1), w), w))
        for n, x, y, s, d in m["vias"]:
            if n == net:
                self.items.append(("via", "via(%.2f,%.2f)" % (x, y), list(CU), (x, y, s), via_width(d)))
        for z in m["zones"]:
            if z[0] == net and not z[3] and z[2]:
                self.items.append(("zone", z[7], z[1], z, INF))
        self.adj = [dict() for _ in self.items]   # i -> {j: edge cap}
        for i in range(len(self.items)):
            for j in range(i + 1, len(self.items)):
                c = self.touch(self.items[i], self.items[j])
                if c:
                    self.adj[i][j] = c
                    self.adj[j][i] = c

    @staticmethod
    def touch(a, b):
        """Edge capacity between two items (0 = not connected)."""
        if not set(a[2]) & set(b[2]):
            return 0
        if a[0] > b[0]:
            a, b = b, a
        ka, kb = a[0], b[0]
        ga, gb = a[3], b[3]
        if ka == "pad" and kb == "pad":
            return INF if (ga[0] < gb[2] and gb[0] < ga[2] and ga[1] < gb[3] and gb[1] < ga[3]) else 0
        if ka == "pad" and kb == "track":
            return INF if seg_rect(gb[0], gb[1], ga) <= gb[2] / 2 + EPS else 0
        if ka == "pad" and kb == "via":
            return INF if rect_pt(ga, gb[:2]) <= gb[2] / 2 + EPS else 0
        if ka == "pad" and kb == "zone":
            if not rect_in_poly(ga, gb[2]):
                return 0
            return INF if gb[5] else 2 * gb[6]
        if ka == "track" and kb == "track":
            return INF if seg_seg(ga[0], ga[1], gb[0], gb[1]) <= (ga[2] + gb[2]) / 2 + EPS else 0
        if ka == "track" and kb == "via":
            return INF if seg_dist(ga[0], ga[1], gb[:2]) <= (ga[2] + gb[2]) / 2 + EPS else 0
        if ka == "track" and kb == "zone":
            poly = gb[2]
            return INF if (point_in_poly(ga[0][0], ga[0][1], poly)
                           or point_in_poly(ga[1][0], ga[1][1], poly)) else 0
        if ka == "via" and kb == "via":
            return INF if math.hypot(ga[0] - gb[0], ga[1] - gb[1]) <= (ga[2] + gb[2]) / 2 + EPS else 0
        if ka == "via" and kb == "zone":
            return INF if point_in_poly(ga[0], ga[1], gb[2]) else 0
        if ka == "zone" and kb == "zone":
            return INF if any(point_in_poly(x, y, gb[2]) for x, y in ga[2]) else 0
        return 0

    def index(self, key):
        return [i for i, it in enumerate(self.items) if it[0] == "pad" and it[1] == key]

    def maxflow(self, srcs, sinks):
        """Node-capacitated max flow from any of srcs to any of sinks."""
        n = len(self.items)
        S, T = 2 * n, 2 * n + 1
        cap = {}

        def add(u, v, c):
            cap[(u, v)] = cap.get((u, v), 0.0) + c
            cap.setdefault((v, u), 0.0)
        for i, it in enumerate(self.items):
            add(2 * i, 2 * i + 1, it[4])                 # in -> out
            for j, c in self.adj[i].items():
                add(2 * i + 1, 2 * j, c)
        for i in srcs:
            add(S, 2 * i, INF)
        for i in sinks:
            add(2 * i + 1, T, INF)
        nbr = {}
        for (u, v) in cap:
            nbr.setdefault(u, []).append(v)
        flow = 0.0
        while True:
            prev = {S: None}
            dq = deque([S])
            while dq and T not in prev:
                u = dq.popleft()
                for v in nbr.get(u, ()):
                    if v not in prev and cap[(u, v)] > 1e-9:
                        prev[v] = u
                        dq.append(v)
            if T not in prev:
                return flow
            f, v = INF, T
            while prev[v] is not None:
                f = min(f, cap[(prev[v], v)])
                v = prev[v]
            if f >= INF / 2:
                return INF
            v = T
            while prev[v] is not None:
                cap[(prev[v], v)] -= f
                cap[(v, prev[v])] += f
                v = prev[v]
            flow += f

    def component(self, start, blocked=()):
        seen, dq = {start}, deque([start])
        while dq:
            u = dq.popleft()
            if u in blocked:
                continue
            for v in self.adj[u]:
                if v not in seen:
                    seen.add(v)
                    dq.append(v)
        return seen


# ------------------------------------------------------------------ checks
def check_paths(m, f, log):
    for label, net, src, dst, amps in PATHS:
        g = Graph(m, net)
        si = [i for k in src for i in g.index(k)]
        ti = [i for k in dst for i in g.index(k)]
        found = set(g.items[i][1] for i in si + ti)
        if found != set(src) | set(dst):
            f.append("%s: pads %s missing on net %s"
                     % (label, ", ".join(sorted(set(src) | set(dst) - found)), net))
            continue
        need = ipc2152_width(amps)
        got = g.maxflow(si, ti)
        txt = "inf" if got >= INF / 2 else "%.2f" % got
        log.append("  %-14s %-10s %4.1f A  need %5.2f mm  have %s mm" % (label, net, amps, need, txt))
        if got < need:
            f.append("%s (%s): narrowest cut %s mm of 1 oz < %.2f mm for %.1f A at %g K (IPC-2152)"
                     % (label, net, txt, need, amps, RISE))


def check_kelvin(m, f):
    for upin, rpad in KELVIN:
        net = [n for k, n, _l, _r in m["pads"] if k == upin]
        if not net:
            f.append("Kelvin: %s missing" % upin)
            continue
        g = Graph(m, net[0])
        u, r = g.index(upin), g.index(rpad)
        if not u or not r:
            f.append("Kelvin: %s or %s not on net %s" % (upin, rpad, net[0]))
            continue
        comp = g.component(u[0], blocked=set(r))
        if r[0] not in comp:
            f.append("Kelvin: %s does not reach %s through its own trace" % (upin, rpad))
            continue
        bad = [g.items[i][1] for i in comp
               if i not in (u[0], r[0]) and g.items[i][0] in ("pad", "zone")]
        if bad:
            f.append("Kelvin: %s -> %s sense trace also touches %s (it must join the current "
                     "path only at the resistor pad)" % (upin, rpad, ", ".join(sorted(bad))))
        # the sense chain itself must not be the current path: a track of it touching the
        # resistor pad must not also touch the power path's other copper (checked above via
        # 'bad'); and the power path must not use the sense chain -- i.e. the chain is a
        # dead end except at the two pads, which 'bad' already proves.


def net_tracks(m, net):
    return [t for t in m["tracks"] if t[0] == net]


def signal_path(m, net, src, dst):
    """Tracks on the shortest track/via chain from pad src to pad dst (Dijkstra on length)."""
    import heapq
    g = Graph(m, net)
    a, b = g.index(src), g.index(dst)
    if not a or not b:
        return None

    def ln(i):
        it = g.items[i]
        if it[0] != "track":
            return 0.0
        (x0, y0), (x1, y1), _w = it[3]
        return math.hypot(x1 - x0, y1 - y0)
    dist, prev = {a[0]: 0.0}, {}
    pq = [(0.0, a[0])]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b[0]:
            break
        if d > dist.get(u, 1e18) or (g.items[u][0] == "pad" and u != a[0]):
            continue
        for v in g.adj[u]:
            nd = d + ln(v)
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    if b[0] not in dist:
        return None
    out, u = [], b[0]
    while u in prev:
        u = prev[u]
        if g.items[u][0] == "track":
            (x0, y0), (x1, y1), _w = g.items[u][3]
            out.append((net, g.items[u][2][0], x0, y0, x1, y1, _w))
    return out


def check_can(m, f, log):
    for pa, pb in CAN_PAIRS:
        for net in (pa[0], pb[0]):
            g = Graph(m, net)
            pads = [i for i, it in enumerate(g.items) if it[0] == "pad"]
            comp = g.component(pads[0]) if pads else set()
            loose = [g.items[i][1] for i in pads if i not in comp]
            if loose:
                f.append("CAN: %s pads not connected by copper: %s" % (net, ", ".join(loose)))
        ta, tb = signal_path(m, *pa), signal_path(m, *pb)
        if ta is None or tb is None:
            f.append("CAN: no track path %s -> %s or %s -> %s" % (pa[1], pa[2], pb[1], pb[2]))
            continue
        la = sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in ta)
        lb = sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in tb)
        log.append("  CAN %s/%s path: %.2f / %.2f mm" % (pa[0], pb[0], la, lb))
        if abs(la - lb) > CAN_SKEW:
            f.append("CAN: %s %.2f mm vs %s %.2f mm, mismatch %.2f > %.1f mm"
                     % (pa[0], la, pb[0], lb, abs(la - lb), CAN_SKEW))
        for mine, other, name in ((ta, tb, pa[0]), (tb, ta, pb[0])):
            tot = near = 0.0
            for t in mine:
                ln = math.hypot(t[4] - t[2], t[5] - t[3])
                k = max(1, int(ln / 0.25))
                for s_ in range(k):
                    u = (s_ + 0.5) / k
                    p = (t[2] + u * (t[4] - t[2]), t[3] + u * (t[5] - t[3]))
                    tot += ln / k
                    if any(seg_dist((o[2], o[3]), (o[4], o[5]), p) <= CAN_GAP for o in other):
                        near += ln / k
            if tot and near / tot < CAN_COUPLED:
                f.append("CAN: only %.0f %% of %s runs within %.1f mm of its partner (want >= %.0f %%)"
                         % (100 * near / tot, name, CAN_GAP, 100 * CAN_COUPLED))


def check_on(m, f):
    on = [p for p in m["pads"] if p[0] == ON_PAD]
    if not on:
        f.append("ON: %s missing" % ON_PAD)
        return
    _k, onnet, _l, r = on[0]
    ref = ON_PAD.split(".")[0]
    own = [p for p in m["pads"] if p[0].split(".")[0] == ref]
    grown = (r[0] - ON_CLEAR, r[1] - ON_CLEAR, r[2] + ON_CLEAR, r[3] + ON_CLEAR)
    for layer in ON_LAYERS:
        for k, n, lays, pr in m["pads"]:
            if n != onnet and layer in lays and k.split(".")[0] != ref:
                d = max(pr[0] - r[2], r[0] - pr[2], 0.0), max(pr[1] - r[3], r[1] - pr[3], 0.0)
                if math.hypot(*d) < ON_CLEAR:
                    f.append("ON: pad %s on %s is %.2f mm from %s" % (k, layer, math.hypot(*d), ON_PAD))
        for n, l, x0, y0, x1, y1, w in m["tracks"]:
            if n == onnet or l != layer:
                continue
            ln = math.hypot(x1 - x0, y1 - y0)
            k = max(1, int(ln / 0.02))
            for s in range(k + 1):
                p = (x0 + (x1 - x0) * s / k, y0 + (y1 - y0) * s / k)
                # a neighbouring U10 pin's own fan-out, within ON_CLEAR of that pin, is exempt
                if any(q[1] == n and rect_pt(q[3], p) <= ON_CLEAR for q in own):
                    continue
                d = rect_pt(r, p) - w / 2
                if d < ON_CLEAR:
                    f.append("ON: %s track on %s at (%.2f, %.2f) is %.2f mm from %s"
                             % (n, layer, p[0], p[1], d, ON_PAD))
                    break
        for n, x, y, s, _d in m["vias"]:
            if n != onnet and rect_pt(r, (x, y)) - s / 2 < ON_CLEAR:
                f.append("ON: %s via at (%.2f, %.2f) is within %.1f mm of %s" % (n, x, y, ON_CLEAR, ON_PAD))
        covered = any(z[3] and z[4] and layer in z[1] and all(
            point_in_poly(x, y, z[2]) for x, y in ((grown[0], grown[1]), (grown[2], grown[1]),
                                                    (grown[2], grown[3]), (grown[0], grown[3])))
            for z in m["zones"])
        for z in m["zones"]:
            if z[3] or z[0] == onnet or layer not in z[1] or not z[2]:
                continue
            poly = z[2]
            hit = any(point_in_poly(x, y, poly) for x, y in
                      ((grown[0], grown[1]), (grown[2], grown[1]), (grown[2], grown[3]),
                       (grown[0], grown[3]), ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)))
            if hit and not covered:
                f.append("ON: zone %s (%s) on %s reaches within %.1f mm of %s with no pour keep-out"
                         % (z[7], z[0], layer, ON_CLEAR, ON_PAD))


def check(path=PCB):
    m = load(open(path, encoding="utf-8").read())
    f, log = [], []
    check_paths(m, f, log)
    check_kelvin(m, f)
    check_can(m, f, log)
    check_on(m, f)
    return f, log


def main():
    f, log = check()
    print("power paths (IPC-2152, %g K, 1 oz):" % RISE)
    for line in log:
        print(line)
    for line in f[:60]:
        print("FAIL " + line)
    if len(f) > 60:
        print("... %d more" % (len(f) - 60))
    print("power_paths: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
