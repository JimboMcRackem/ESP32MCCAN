# -*- coding: utf-8 -*-
"""No two courtyards on this board may overlap.

Why this exists
---------------
KiCad's DRC checks this and nothing in this repo did, which is a bad place for a check to
live when the loop is "edit layout_pcb.py, regenerate, run the guards, route for twenty
minutes, THEN run DRC".  U4's nudge was taken at 0.9 mm on copper arithmetic -- the pads
cleared C6 by 0.925 mm -- and it regenerated clean, passed all four guards and routed before
DRC reported two courtyards_overlap ERRORS.  U4's courtyard reaches 0.275 mm past its pads
and C6's reaches 0.250 mm past its own, so courtyard to courtyard the gap was 0.700 mm, and
the move had to be redone at 0.65 mm.  Twenty minutes of routing to learn something that is
two rectangles and a subtraction.

So this is the cheap half of that DRC run, runnable in a second before the expensive half.
It reads the netlist and the placer -- not the board -- so it answers BEFORE a regenerate,
and the number it prints is the real budget for the next nudge.

    python scripts/check_courtyards.py [--near MM]

--near also lists pairs that do not overlap but come within MM of doing so, which is what
you want when you are about to move something: 0.05 mm of gap is a pass and a warning at
the same time.

Courtyards are compared as the bounding BOXES gen_pcb.extent() returns, which is what the
placer packs with.  KiCad compares the real outlines, so a box overlap between two parts
whose courtyards are not rectangular can be a false alarm -- rare on this board, where
nearly every courtyard is a rectangle.  A box overlap this reports is therefore a thing to
look at; a clean run means KiCad will agree.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pcb as G  # noqa: E402


def boxes():
    """(ref, x0, y0, x1, y1) courtyard box for every placed footprint."""
    comps, _nets, _padnet = G.read_netlist()
    comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
    pos = G.place(comps)[0]
    out = []
    for c in comps:
        ref = c["ref"]
        if ref not in pos:
            continue
        x, y, rot = pos[ref]
        w, h, ox, oy = G.extent(c["fp"])
        if rot % 180:
            w, h = h, w
        dx, dy = G.rot_local(ox, oy, rot)
        cx, cy = x + dx, y + dy
        out.append((ref, cx - w / 2., cy - h / 2., cx + w / 2., cy + h / 2.))
    return out


def main(argv):
    near = 0.0
    if "--near" in argv:
        near = float(argv[argv.index("--near") + 1])

    bx = boxes()
    bx.sort(key=lambda b: b[1])
    bad, close = [], []
    for i, a in enumerate(bx):
        for b in bx[i + 1:]:
            if b[1] > a[3] + max(near, 0.0):
                break                      # sorted by x0: nothing further right can reach
            gx = max(b[1] - a[3], a[1] - b[3])
            gy = max(b[2] - a[4], a[2] - b[4])
            gap = max(gx, gy)              # boxes overlap when BOTH axes overlap
            if gap < 0:
                bad.append((gap, a[0], b[0]))
            elif gap <= near:
                close.append((gap, a[0], b[0]))

    for gap, a, b in sorted(close):
        print("  note: %s and %s clear by %.3f mm" % (a, b, gap))
    if bad:
        for gap, a, b in sorted(bad):
            print("  %s and %s OVERLAP by %.3f mm" % (a, b, -gap))
        print("FAIL: %d courtyard pair(s) overlap." % len(bad))
        return 1
    print("courtyards: %d footprint(s), no overlaps%s."
          % (len(bx), (", %d pair(s) within %.2f mm" % (len(close), near)) if near else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
