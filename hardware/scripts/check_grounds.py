# -*- coding: utf-8 -*-
"""The three-ground split (plan4 phase B, Task 5; spec 5.2).

  python check_grounds.py [board.kicad_pcb]

GND (logic, board side of L2), GND_IN (feed A connector side of L2) and GND_B (feed B / pod
return) are three nets that may meet only at named parts:

    GND    -- GND_IN   only through L2 (winding B) and R3 (the DNP 0R link across it)
    GND_B  -- GND_IN   only at NT1, the 2 mm star tie
    GND    -- GND_B    nowhere

KiCad never shorts two nets -- a pour simply notches around foreign copper -- so DRC passes a
board whose GND plane has been drawn straight over the GND_IN island.  This file checks the
INTENT instead, geometrically, against the authored zone outlines and copper:

  1. star:   the netlist has exactly the bridging parts above, and no others;
  2. zones:  no zone of one ground net overlaps a zone of another on the same layer;
  3. copper: no via, track or through-hole pad of one ground net lies inside another ground
             net's zone (a via or THT pad pierces every layer, so it is tested on all of them);
  4. reach:  every GND_B zone, track and via is connected to J9.2 through GND_B copper (and by
             2-3, none of that copper sits in GND);
  5. pods:   J10.2, J11.2 and the GND_B pads of C67-C70 lie over GND_B zone copper, and over no
             GND or GND_IN zone on any layer.
Exit 1 on any failure.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from check_antenna import point_in_poly, layers_of  # noqa: E402
from check_placement import footprints  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")
GROUNDS = ("GND", "GND_IN", "GND_B")
ALLOWED = {  # frozenset of nets -> the refs allowed to carry both
    frozenset(("GND", "GND_IN")): {"L2", "R3"},
    frozenset(("GND_B", "GND_IN")): {"NT1"},
    frozenset(("GND", "GND_B")): set(),
}
POD_PADS = [("J10", "2"), ("J11", "2"), ("C67", "2"), ("C68", "2"), ("C69", "2"), ("C70", "2")]


def short(n):
    return n.rsplit("/", 1)[-1]


def netnames(text):
    return dict((int(c), short(n)) for c, n in re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', text))


def zones(text):
    """[(net, layer, poly, name)] for every copper zone (rule areas excluded)."""
    out = []
    for blk in text.split("\n\t(zone")[1:]:
        if "(keepout" in blk:
            continue
        net = re.search(r'\(net_name "([^"]*)"\)', blk)
        lay = re.search(r'\n\t\t\(layers? ([^)]*)\)', blk)
        name = re.search(r'\n\t\t\(name "([^"]*)"\)', blk)
        # The group must end at the closing line: ending it at "\)\s*\)" eats the last
        # vertex's own ")" and findall then drops that vertex.
        pts = re.search(r"\(polygon\s*\(pts(.*?)\n\s*\)", blk, re.S)
        if not (net and lay and pts):
            continue
        poly = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", pts.group(1))]
        for l in layers_of(lay.group(1)):
            out.append((short(net.group(1)), l, poly, name.group(1) if name else "?"))
    return out


def tracks(text, names):
    """[(net, layer, x0, y0, x1, y1, width)] for every straight segment."""
    out = []
    for blk in text.split("\n\t(segment")[1:]:
        s = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", blk)
        e = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", blk)
        w = re.search(r"\(width ([-\d.]+)\)", blk)
        l = re.search(r'\(layer "([^"]+)"\)', blk)
        n = re.search(r"\(net (\d+)", blk)
        if s and e and w and l and n:
            out.append((names.get(int(n.group(1)), ""), l.group(1), float(s.group(1)),
                        float(s.group(2)), float(e.group(1)), float(e.group(2)), float(w.group(1))))
    return out


def vias(text, names):
    """[(net, x, y, size)] for every via."""
    out = []
    for blk in text.split("\n\t(via")[1:]:
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", blk)
        net = re.search(r"\(net (\d+)", blk)
        size = re.search(r"\(size ([-\d.]+)\)", blk)
        if at and net:
            out.append((names.get(int(net.group(1)), ""), float(at.group(1)), float(at.group(2)),
                        float(size.group(1)) if size else 0.6))
    return out


def segs_cross(p, q, r, s):
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    def on(a, b, c):
        return (min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
                and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9)
    o1, o2, o3, o4 = orient(p, q, r), orient(p, q, s), orient(r, s, p), orient(r, s, q)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and on(p, q, r)) or (o2 == 0 and on(p, q, s))
            or (o3 == 0 and on(r, s, p)) or (o4 == 0 and on(r, s, q)))


def polys_intersect(a, b):
    for i in range(len(a)):
        p, q = a[i], a[(i + 1) % len(a)]
        for j in range(len(b)):
            if segs_cross(p, q, b[j], b[(j + 1) % len(b)]):
                return True
    return point_in_poly(a[0][0], a[0][1], b) or point_in_poly(b[0][0], b[0][1], a)


def seg_point_dist(x0, y0, x1, y1, px, py):
    dx, dy = x1 - x0, y1 - y0
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / n))
    return math.hypot(x0 + t * dx - px, y0 + t * dy - py)


def seg_in_poly(x0, y0, x1, y1, w, poly):
    """Does a track (fattened by half its width) touch the polygon's area?"""
    if point_in_poly(x0, y0, poly) or point_in_poly(x1, y1, poly):
        return True
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if segs_cross((x0, y0), (x1, y1), a, b):
            return True
        if seg_point_dist(x0, y0, x1, y1, a[0], a[1]) < w / 2:
            return True
    return False


def reach(text):
    """Failures for GND_B copper not connected to J9.2.

    Task 6: connectivity is check_power_paths.Graph's -- a track joins a pad anywhere it
    overlaps the pad (SMD or THT), and a track joins a track anywhere they touch.  The Task 5
    version linked a track to a pad only at the pad centre and to another track only at a
    shared endpoint, which reported the feed-B decoupling stubs as islands."""
    from check_power_paths import load, Graph
    g = Graph(load(text), "GND_B")
    start = g.index("J9.2")
    if not start:
        return ["reach: J9 pad 2 not found"]
    seen = g.component(start[0])
    f = []
    for i, it in enumerate(g.items):
        if i in seen or it[0] == "pad":
            continue
        f.append("reach: GND_B %s %s is not connected to J9.2" % (it[0], it[1]))
    for i, it in enumerate(g.items):
        if it[0] == "pad" and i not in seen:
            f.append("reach: GND_B pad %s is not connected to J9.2" % it[1])
    return f


def check():
    f = []
    text = open(PCB, encoding="utf-8").read()
    names = netnames(text)
    fps = footprints(text)
    zs = [z for z in zones(text) if z[0] in GROUNDS]
    trs = [t for t in tracks(text, names) if t[0] in GROUNDS]
    vs = [v for v in vias(text, names) if v[0] in GROUNDS]

    # 1. star
    carriers = {}
    for ref, d in fps.items():
        nets = set(p[5] for p in d["pads"]) & set(GROUNDS)
        for pair in ALLOWED:
            if pair <= nets:
                carriers.setdefault(pair, set()).add(ref)
    for pair, allowed in ALLOWED.items():
        got = carriers.get(pair, set())
        if got != allowed:
            f.append("star: parts carrying both %s are %s, want exactly %s"
                     % (" and ".join(sorted(pair)), sorted(got) or "none", sorted(allowed) or "none"))

    # 2. zones of different grounds on one layer
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            a, b = zs[i], zs[j]
            if a[0] != b[0] and a[1] == b[1] and polys_intersect(a[2], b[2]):
                f.append("bridge: zone %s [%s] overlaps zone %s [%s] on %s"
                         % (a[3], a[0], b[3], b[0], a[1]))

    # 3. ground copper inside another ground's zone
    tht = [(r, p) for r, d in fps.items() for p in d["pads"]
           if p[5] in GROUNDS and p[6] == "thru_hole"]
    for net, layer, poly, zname in zs:
        for vn, x, y, _s in vs:
            if vn != net and point_in_poly(x, y, poly):
                f.append("bridge: %s via at (%.2f, %.2f) is inside zone %s [%s] on %s"
                         % (vn, x, y, zname, net, layer))
        for r, p in tht:
            if p[5] != net and point_in_poly(p[1], p[2], poly):
                f.append("bridge: %s pad %s.%s is inside zone %s [%s] on %s"
                         % (p[5], r, p[0], zname, net, layer))
        for tn, tl, x0, y0, x1, y1, w in trs:
            if tn != net and tl == layer and seg_in_poly(x0, y0, x1, y1, w, poly):
                f.append("bridge: %s track (%.2f, %.2f)-(%.2f, %.2f) on %s enters zone %s [%s]"
                         % (tn, x0, y0, x1, y1, tl, zname, net))

    # 4. GND_B reachability from J9.2
    f += reach(text)

    # 5. pod returns over GND_B copper only
    for ref, pad in POD_PADS:
        ps = [p for p in fps.get(ref, {"pads": []})["pads"] if p[0] == pad]
        if not ps:
            f.append("pods: %s pad %s not found" % (ref, pad))
            continue
        p = ps[0]
        if p[5] != "GND_B":
            f.append("pods: %s.%s is on %s, want GND_B" % (ref, pad, p[5]))
        if not any(z[0] == "GND_B" and point_in_poly(p[1], p[2], z[2]) for z in zs):
            f.append("pods: %s.%s at (%.2f, %.2f) is not over any GND_B zone" % (ref, pad, p[1], p[2]))
        for z in zs:
            if z[0] != "GND_B" and point_in_poly(p[1], p[2], z[2]):
                f.append("pods: %s.%s lies over zone %s [%s] on %s" % (ref, pad, z[3], z[0], z[1]))
    return f


def main():
    f = check()
    for line in f[:60]:
        print("FAIL " + line)
    if len(f) > 60:
        print("... %d more" % (len(f) - 60))
    print("grounds: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
