# -*- coding: utf-8 -*-
"""How full each placement region is, against the budget it declares.

Why this exists
---------------
A comment in layout_pcb.py records the outputs block at 59 % courtyard fill.  It was
written by hand, after the fact, about a region that was widened in the same commit --
so it was true of something for about a minute.  Measured, the block is at 37 %, and the
congested one is `input` at 76 %.  That is the whole argument for a gate: the number was
not wrong when it was written, it just stopped being about anything.  Density is the root cause behind most of
that board's problems (silk with nowhere to go, a router that could not find a
channel, hand-routing doing the router's job), so it is worth a gate rather than a
comment.

Fill is courtyard area over region area.  It is a blunt measure -- it does not know
that a tall part needs more room than a flat one, or that an escape needs room on one
particular side -- but the failure it catches is blunt too, and a blunt measure that
runs on every build beats a precise one that runs once.

    python scripts/check_density.py [--report]

--report prints the table and always exits 0, which is what you want while you are
still choosing the budgets.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_pcb as G          # noqa: E402
import layout_pcb as L       # noqa: E402


def main():
    report = "--report" in sys.argv

    comps, nets, padnet = G.read_netlist()
    comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
    pos, unplaced, _grid = G.place(comps)

    # Courtyard area per region.  A part counts against the region its courtyard CENTRE
    # falls in, so a part that straddles a boundary is charged to one region rather than
    # to neither.  Parts outside every region (the wire field's hand placements sit in
    # 'wire', but U5 hangs off the board edge) are charged to nothing and listed.
    area = dict((r, 0.0) for r in L.REGIONS)
    homeless = []
    for c in comps:
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        x0, y0, x1, y1 = G.box(c["fp"], x, y, rot)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        a = (x1 - x0) * (y1 - y0)
        for r, (rx0, ry0, rx1, ry1) in L.REGIONS.items():
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                area[r] += a
                break
        else:
            homeless.append(c["ref"])

    budget = getattr(L, "BUDGET", {})

    # A BUDGET key that names no REGIONS entry is silently ignored by the loop below --
    # no row, no warning, no effect on the exit code -- which is exactly the kind of
    # stale, no-longer-about-anything number this gate exists to catch. Task 4 rewrites
    # both REGIONS and BUDGET, so a budget naming a region that no longer exists is a
    # budget nobody is enforcing, and that has to fail loudly rather than vanish.
    stray = set(budget) - set(L.REGIONS)
    if stray:
        print("ERROR: BUDGET names region(s) not in REGIONS: %s"
              % ", ".join(sorted(stray)))
        return 1

    bad = []
    print("%-10s %9s %9s %7s %7s" % ("region", "rgn mm2", "used mm2", "fill", "budget"))
    for r in sorted(L.REGIONS):
        rx0, ry0, rx1, ry1 = L.REGIONS[r]
        ra = (rx1 - rx0) * (ry1 - ry0)
        fill = area[r] / ra if ra else 0.0
        lim = budget.get(r)
        flag = ""
        if lim is not None and fill > lim:
            flag = "  OVER"
            bad.append((r, fill, lim))
        print("%-10s %8.0f %9.0f %6.1f%% %6s%s"
              % (r, ra, area[r], fill * 100.0,
                 ("%.0f%%" % (lim * 100.0)) if lim is not None else "-", flag))

    if homeless:
        print("outside every region: %s" % ", ".join(sorted(homeless)))
    if unplaced:
        print("UNPLACED: %s" % ", ".join(sorted(unplaced)))

    if report:
        return 0
    for r, fill, lim in bad:
        print("FAIL: region '%s' is %.1f%% full against a %.0f%% budget"
              % (r, fill * 100.0, lim * 100.0))
    if unplaced:
        print("FAIL: %d part(s) would not fit" % len(unplaced))
    return 1 if (bad or unplaced) else 0


if __name__ == "__main__":
    sys.exit(main())
