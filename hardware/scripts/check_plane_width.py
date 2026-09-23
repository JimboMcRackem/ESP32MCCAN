# -*- coding: utf-8 -*-
"""Measure the narrowest cross-section of a power plane, and grade it against IPC-2221.

Why this exists
---------------
The stackup comment in gen_pcb.py has always carried a current-carrying claim about the VBAT
plane -- "IPC-2221 for an internal layer wants 11.5 mm of effective width at 1 oz for 7.0 A at
a 10 K rise, against 5.75 mm at 2 oz".  That claim decided the inner copper weight, and it was
never measured.  It did not need to be while the answer was 2 oz, because 5.75 mm on a
full-board plane is not a number anything could plausibly violate.  Going to six layers changes
that: PCBWay's inner-layer minimum spacing at 2 oz is 8 mil (0.203 mm), which is ABOVE this
board's 0.20 mm clearance, so the two new inner SIGNAL layers cannot be 2 oz -- and a fab's
inner copper weight is one selector for all inner layers unless you pay for a custom stackup.
1 oz inners move the requirement to 11.44 mm, which is a number a real via field can eat.

So this stops being an assumption and becomes a measurement.

What it measures
----------------
A plane is not a rectangle; it is a rectangle with several hundred holes in it.  Every via that
passes through punches an antipad, and so does every through-hole pad on another net.  This
rasterises the plane at the routing grid, subtracts those holes dilated by the clearance, and
then takes every straight cut across the board -- every column and every row -- and sums the
copper the cut actually crosses.  Runs narrower than the zone's own min_thickness are not
counted, because copper that thin does not survive the fill.

The minimum over all cuts is the answer.  It is a deliberately pessimistic one: it assumes the
current has to cross the single worst line on the board, when in reality it flows from the
input connector to the loads and may never see that line.  A plane that passes this passes for
any path; a plane that fails it needs the path argument made properly before the weight is
dropped.

    python scripts/check_plane_width.py                      # the generated board
    python scripts/check_plane_width.py board.kicad_pcb /VBAT
"""

import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pcb as G  # noqa: E402
import layout_pcb as L  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE),
                                                           "mccan.kicad_pcb")
NET = sys.argv[2] if len(sys.argv) > 2 else "/VBAT"

# The current the plane has to carry, and the rise we allow it.  7.0 A continuous is spec 6's
# feed figure; 10 K is the conventional IPC-2221 internal-layer allowance and the one the
# stackup comment has always quoted.
AMPS, RISE = 7.0, 10.0
GRID = G.AR_GRID

# Clearance from plane copper to a via or pad barrel of another net.  The POWER class asks 0.30
# and the zones ask the same of pads, so a hole is its own radius plus this.
CLEAR = 0.30


def ipc_width(amps, rise, oz):
    """IPC-2221 internal-layer conductor width, in mm, for `amps` at `rise` K and `oz` copper.

    A = (I / (k * dT**0.44)) ** (1/0.725) in square mils, k = 0.024 for an internal layer;
    width is that area over the foil thickness, and 1 oz is 1.378 mil.
    """
    area = (amps / (0.024 * rise ** 0.44)) ** (1.0 / 0.725)
    return area / (1.378 * oz) * 0.0254


def netmap(doc):
    out = {}
    for n in G.find_all(doc, "net"):
        out[int(n[1])] = G.unq(n[2])
    return out


def plane(doc, names):
    """The zone pouring NET, as (layer, [(x, y), ...], min_thickness)."""
    for z in G.find_all(doc, "zone"):
        nn = G.find(z, "net_name")
        if not nn or G.unq(nn[1]) != NET:
            continue
        lay = G.find(z, "layer") or G.find(z, "layers")
        name = lay[1] if lay else "?"
        poly = G.find(z, "polygon")
        pts = G.find(poly, "pts") if poly else None
        if not pts:
            continue
        xy = [(float(p[1]), float(p[2])) for p in G.find_all(pts, "xy")]
        mt = G.find(z, "min_thickness")
        return G.unq(name), xy, float(mt[1]) if mt else 0.0
    return None, None, None


def rivals(doc, layer):
    """Zones of another net sharing the plane's layer, as [(net_name, zone_name), ...].

    This raster measures the plane's OUTLINE polygon minus barrels.  It does not do polygon
    arithmetic against other zones, so a second zone on the same layer -- which KiCad will
    carve out of this one if it has the higher priority -- is copper this check still counts.
    That blindness is the whole reason for this guard: a split power layer would read as a
    solid one and the number printed below would be a fiction.  Refuse to measure instead.
    """
    out = []
    for z in G.find_all(doc, "zone"):
        lay = G.find(z, "layer") or G.find(z, "layers")
        if not lay or G.unq(lay[1]) != layer:
            continue
        nn = G.find(z, "net_name")
        nm = G.unq(nn[1]) if nn else ""
        if nm == NET:
            continue
        zn = G.find(z, "name")
        out.append((nm or "<none>", G.unq(zn[1]) if zn else "?"))
    return out


def holes(doc, names):
    """Every barrel that punches this plane, as (x, y, radius) before clearance.

    A via's hole is its OUTER copper, not its drill: the plane is pulled back from the pad.
    A through-hole pad on another net is the same thing wearing a different name.  Barrels on
    the plane's own net are not holes at all -- they are where it connects, and subtracting
    them would be measuring the opposite of what is being asked.
    """
    out = []
    for v in G.find_all(doc, "via"):
        at, sz, nt = G.find(v, "at"), G.find(v, "size"), G.find(v, "net")
        if not (at and sz and nt) or names.get(int(nt[1])) == NET:
            continue
        out.append((float(at[1]), float(at[2]), float(sz[1]) / 2.0))
    for fp in G.find_all(doc, "footprint"):
        fat = G.find(fp, "at")
        fx, fy = float(fat[1]), float(fat[2])
        frot = float(fat[3]) if len(fat) > 3 else 0.0
        for pad in G.find_all(fp, "pad"):
            if len(pad) < 3 or pad[2] not in ("thru_hole", "np_thru_hole"):
                continue
            nt = G.find(pad, "net")
            if nt and names.get(int(nt[1])) == NET:
                continue
            at, sz = G.find(pad, "at"), G.find(pad, "size")
            if not (at and sz):
                continue
            lx, ly = G.rot_local(float(at[1]), float(at[2]), frot)
            out.append((fx + lx, fy + ly,
                        max(float(sz[1]), float(sz[2])) / 2.0))
    return out


def raster(pts, bores):
    """The plane as a grid of 1s at GRID pitch, holes already punched."""
    w = int(round((L.X1 - L.X0) / GRID)) + 1
    h = int(round((L.Y1 - L.Y0) / GRID)) + 1
    m = bytearray(w * h)
    n = len(pts)
    for j in range(h):
        y = L.Y0 + j * GRID
        xs = []
        for k in range(n):
            ax, ay = pts[k]
            bx, by = pts[(k + 1) % n]
            if (ay > y) != (by > y):
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
        xs.sort()
        row = j * w
        for k in range(0, len(xs) - 1, 2):
            i0 = max(0, int(math.ceil((xs[k] - L.X0) / GRID)))
            i1 = min(w - 1, int(math.floor((xs[k + 1] - L.X0) / GRID)))
            for i in range(i0, i1 + 1):
                m[row + i] = 1
    for bx, by, br in bores:
        r = br + CLEAR
        i0 = max(0, int(math.floor((bx - r - L.X0) / GRID)))
        i1 = min(w - 1, int(math.ceil((bx + r - L.X0) / GRID)))
        j0 = max(0, int(math.floor((by - r - L.Y0) / GRID)))
        j1 = min(h - 1, int(math.ceil((by + r - L.Y0) / GRID)))
        rr = r * r
        for j in range(j0, j1 + 1):
            dy = L.Y0 + j * GRID - by
            row = j * w
            for i in range(i0, i1 + 1):
                dx = L.X0 + i * GRID - bx
                if dx * dx + dy * dy <= rr:
                    m[row + i] = 0
    return m, w, h


def cut(cells, count, step, mt):
    """Copper crossed by one straight cut, in mm, ignoring runs thinner than `mt`.

    Summing the runs rather than taking the widest is the right model for current: two 6 mm
    lobes either side of a via field carry what one 12 mm lobe carries.  Dropping the thin
    ones is not pedantry -- min_thickness is the width below which the fill deletes the
    copper outright, so a 0.2 mm sliver is not narrow, it is absent.
    """
    total, run = 0.0, 0
    for k in range(count):
        if cells[k]:
            run += 1
        else:
            if run * step >= mt - 1e-9:
                total += run * step
            run = 0
    if run * step >= mt - 1e-9:
        total += run * step
    return total


def main():
    if not os.path.exists(BOARD):
        print("FAIL: %s is missing" % BOARD)
        return 2
    doc = G.parse(io.open(BOARD, encoding="utf-8").read())
    names = netmap(doc)
    layer, pts, mt = plane(doc, names)
    if not pts:
        print("FAIL: no zone pours %s on %s" % (NET, os.path.basename(BOARD)))
        return 2
    share = rivals(doc, layer)
    if share:
        print("FAIL: %s is not alone on %s -- %d other zone(s) share the layer:"
              % (NET, layer, len(share)))
        for nm, zn in share:
            print("    %-24s %s" % (nm, zn))
        print("This check rasterises the plane's outline and subtracts barrels; it does no")
        print("polygon arithmetic against other zones.  A higher-priority neighbour eats")
        print("copper this raster would still count, so any width it printed would be a")
        print("fiction.  Give the plane its layer, or teach this check to subtract zones.")
        return 2

    bores = holes(doc, names)
    m, w, h = raster(pts, bores)

    cols = [(cut(m[i::w], h, GRID, mt), L.X0 + i * GRID) for i in range(w)]
    rows = [(cut(m[j * w:(j + 1) * w], w, GRID, mt), L.Y0 + j * GRID) for j in range(h)]
    # The edges of the board are not a cut through the plane, they are outside it.  Only cuts
    # that actually carry copper are cuts; a line past the end of the pour measures nothing.
    cols = [c for c in cols if c[0] > 0]
    rows = [r for r in rows if r[0] > 0]
    if not cols or not rows:
        print("FAIL: %s pours no copper at all on %s" % (NET, layer))
        return 1

    wx, xat = min(cols)
    wy, yat = min(rows)
    worst = min(wx, wy)

    print("%s on %s, %d hole(s) punched through it" % (NET, layer, len(bores)))
    print("  narrowest vertical cut:   %6.2f mm at x = %.1f" % (wx, xat))
    print("  narrowest horizontal cut: %6.2f mm at y = %.1f" % (wy, yat))
    print("  runs under min_thickness %g mm are not counted" % mt)
    print("")
    print("IPC-2221 internal, %.1f A at %.0f K rise:" % (AMPS, RISE))
    rc = 0
    for oz in (1.0, 2.0):
        need = ipc_width(AMPS, RISE, oz)
        ok = worst >= need
        print("  %g oz needs %5.2f mm -- %s (%.1fx margin)"
              % (oz, need, "OK" if ok else "SHORT", worst / need))
    need1 = ipc_width(AMPS, RISE, 1.0)
    if worst < need1:
        print("")
        print("FAIL: at 1 oz this plane is %.2f mm short of IPC-2221 on its worst cut."
              % (need1 - worst))
        print("      Either the inner copper goes to 2 oz, or the worst cut has to be shown")
        print("      to be off the current path -- which is an argument, not a default.")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
