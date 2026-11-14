# -*- coding: utf-8 -*-
"""Narrowest cross-section of each power pour, graded against IPC-2152 (plan4 phase B, Task 6).

  python check_plane_width.py [board.kicad_pcb]

check_power_paths.py treats a zone as unbounded and grades the tracks and vias that feed it;
this file grades the zones themselves.  For every net in CURRENT, every pour of that net on
every layer is cut along each board row and each board column (STEP mm apart).  On each cut
line the copper is the pour's polygon minus, exactly on that line:

  * every other-net pad, via and track on the layer (a through-hole pad and a via pierce every
    layer), grown by CLEAR -- the fill knocks out round them;
  * every other-net zone on the layer, grown by CLEAR;
  * every rule area that forbids pour on the layer.

Runs shorter than the zone's min_thickness are dropped (they do not survive the fill).  The
copper on one cut line is then SUMMED over all the net's layers -- the layers carry the
current in parallel -- and the minimum over all cut lines that cross the net at all is the
answer.  That is deliberately pessimistic: the current may never cross the worst line.  A pour
that passes this passes for any path through it.

Plan3's version graded one net (/VBAT, 7 A, IPC-2221 at 10 K) on one layer.  Plan4 carries
6.4 A on feed B's rail and return and 1 A on feed A (spec 5.2); the rise allowance and the
chart are the ones check_power_paths.py uses (IPC-2152, 20 K, 1 oz on every layer).
Exit 1 on any failure.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from check_power_paths import load, ipc2152_width, RISE  # noqa: E402

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")
CURRENT = {   # net -> amps the pours must carry
    "FEED_B_P": 6.4, "VBAT_B": 6.4, "GND_B": 6.4,
    "POD_L_P": 3.2, "POD_R_P": 3.2,
    "VBAT": 1.0, "GND_IN": 1.0, "GND": 1.0,
}
STEP = 0.1     # mm between cut lines
CLEAR = 0.3    # zone clearance (gen_pcb.zones writes 0.3)
MIN_RUN = 0.2  # zone min_thickness


def poly_spans(poly, c, horiz):
    """Intervals of the line (y = c if horiz else x = c) inside the polygon (even-odd)."""
    xs = []
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if not horiz:
            ax, ay, bx, by = ay, ax, by, bx
        if (ay > c) != (by > c):
            xs.append(ax + (c - ay) * (bx - ax) / (by - ay))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def rect_span(r, c, horiz, grow):
    a0, a1, b0, b1 = (r[0], r[2], r[1], r[3]) if horiz else (r[1], r[3], r[0], r[2])
    if b0 - grow <= c <= b1 + grow:
        return (a0 - grow, a1 + grow)
    return None


def disc_span(x, y, rad, c, horiz):
    u, v = (x, y) if horiz else (y, x)
    d = abs(v - c)
    if d >= rad:
        return None
    h = math.sqrt(rad * rad - d * d)
    return (u - h, u + h)


def capsule_span(t, c, horiz, grow):
    _n, _l, x0, y0, x1, y1, w = t
    rad = w / 2 + grow
    if not horiz:
        x0, y0, x1, y1 = y0, x0, y1, x1
    if min(y0, y1) - rad > c or max(y0, y1) + rad < c:
        return None
    lo, hi = 1e9, -1e9
    for k in range(21):
        s = k / 20.0
        px, py = x0 + s * (x1 - x0), y0 + s * (y1 - y0)
        d = abs(py - c)
        if d < rad:
            h = math.sqrt(rad * rad - d * d)
            lo, hi = min(lo, px - h), max(hi, px + h)
    return (lo, hi) if lo < hi else None


def subtract(spans, cuts):
    out = spans
    for a, b in cuts:
        nxt = []
        for s0, s1 in out:
            if b <= s0 or a >= s1:
                nxt.append((s0, s1))
                continue
            if a > s0:
                nxt.append((s0, a))
            if b < s1:
                nxt.append((b, s1))
        out = nxt
    return out


def layer_obstacles(m, net, layer):
    """[(kind, geom)] of everything on `layer` that a pour of `net` must clear."""
    obs = []
    for _k, n, lays, r in m["pads"]:
        if n != net and layer in lays:
            obs.append(("rect", r))
    for n, x, y, s, _d in m["vias"]:
        if n != net:
            obs.append(("disc", (x, y, s / 2)))
    for t in m["tracks"]:
        if t[0] != net and t[1] == layer:
            obs.append(("track", t))
    for z in m["zones"]:
        if layer not in z[1] or not z[2]:
            continue
        if z[3] and z[4]:
            obs.append(("poly", (z[2], 0.0)))
        elif not z[3] and z[0] != net:
            obs.append(("poly", (z[2], CLEAR)))
    return obs


def line_copper(m, net, horiz, c, cache):
    total = 0.0
    for z in m["zones"]:
        if z[3] or z[0] != net or not z[2]:
            continue
        for layer in z[1]:
            spans = poly_spans(z[2], c, horiz)
            if not spans:
                continue
            if layer not in cache:
                cache[layer] = layer_obstacles(m, net, layer)
            cuts = []
            for kind, g in cache[layer]:
                if kind == "rect":
                    sp = rect_span(g, c, horiz, CLEAR)
                elif kind == "disc":
                    sp = disc_span(g[0], g[1], g[2] + CLEAR, c, horiz)
                elif kind == "track":
                    sp = capsule_span(g, c, horiz, CLEAR)
                else:
                    sp = None
                    for cc in (c - g[1], c, c + g[1]):
                        for a, b in poly_spans(g[0], cc, horiz):
                            cuts.append((a - g[1], b + g[1]))
                if sp:
                    cuts.append(sp)
            left = subtract(spans, cuts)
            total += sum(b - a for a, b in left if b - a >= MIN_RUN)
    return total


def grade(m, net):
    """(narrowest cut mm, where) over all rows and columns that cross the net's pours."""
    polys = [z[2] for z in m["zones"] if not z[3] and z[0] == net and z[2]]
    if not polys:
        return None, "no pour"
    best, where = 1e9, ""
    cache = {}
    for horiz in (True, False):
        k = 1 if horiz else 0
        lo = min(p[k] for poly in polys for p in poly)
        hi = max(p[k] for poly in polys for p in poly)
        c = lo + STEP / 2
        while c < hi:
            if any(poly_spans(poly, c, horiz) for poly in polys):
                w = line_copper(m, net, horiz, c, cache)
                if w < best:
                    best, where = w, ("row y = %.2f" if horiz else "column x = %.2f") % c
            c += STEP
    return best, where


def check(path=PCB):
    m = load(open(path, encoding="utf-8").read())
    f, log = [], []
    for net, amps in sorted(CURRENT.items()):
        need = ipc2152_width(amps)
        got, where = grade(m, net)
        if got is None:
            log.append("  %-9s %4.1f A  (no pour)" % (net, amps))
            continue
        log.append("  %-9s %4.1f A  need %5.2f mm  narrowest %6.2f mm at %s"
                   % (net, amps, need, got, where))
        if got < need:
            f.append("%s pour: narrowest cut %.2f mm at %s < %.2f mm for %.1f A (IPC-2152, %g K)"
                     % (net, got, where, need, amps, RISE))
    return f, log


def main():
    f, log = check()
    print("plane width (IPC-2152, %g K, 1 oz, summed over layers):" % RISE)
    for line in log:
        print(line)
    for line in f:
        print("FAIL " + line)
    print("plane_width: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
