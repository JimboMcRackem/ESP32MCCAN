# -*- coding: utf-8 -*-
"""Grade a board's copper against what was ASKED for and what the board ALLOWS.

Why this exists
---------------
KiCadRoutingTools will quietly deliver copper finer than it was told to.  Its --fab-tier
flag is not the lever that stops it; --escalation is, and its default is "fab", which is
documented as "down to the fab tier floor, BELOW the board's own minimums".  The first real
run on this board came back with 2177 tracks at 0.0889 mm against a 0.25 mm request and a
0.20 mm board floor, 115 vias at 0.45/0.20 against a 0.6/0.3 request, and four stubs on the
plane layers.  Every one of those was reported in a warning buried in a 70 000 line log, and
none of them failed the run.

KiCad's own DRC would have caught the 0.0889 mm tracks and nothing else -- a via at the
board's declared floor is legal, and a two-micron stub on a plane layer is too small for a
clearance test to notice.  So the board-floor half of this is belt and braces, and the rest
of it is the part no other check does.

What it decides
---------------
FAIL, meaning the copper must not be frozen:

  * a track thinner than rules.min_track_width, a via smaller than rules.min_via_diameter,
    an annulus under rules.min_via_annular_width or a drill under
    rules.min_through_hole_diameter -- all read from the board's OWN project file, not
    typed here;
  * a track on a layer that is not a routing layer.  On the eight-layer board the planes are
    In1.Cu, In3.Cu and In6.Cu (GND) and In4.Cu (VBAT); a track on any of them is a slot cut
    through a reference plane, which is exactly the thing this stackup exists to avoid.  The
    routing layers are F.Cu, In2.Cu, In5.Cu and B.Cu.  The list is not typed here -- it is
    gen_pcb.SIGNAL_LAYERS, read at import, so it cannot drift from the board the way this
    sentence did: it said In4.Cu was a signal layer for the whole of the six-to-eight-layer
    move, during which In4.Cu became the solid VBAT plane;
  * a segment shorter than a tenth of the router grid.  Harmless on its own, but it is junk
    the diff would freeze into a generated board forever.

REPORTED and not failed: copper that is finer than gen_pcb's AR_* request but still legal.
Necking a track from 0.25 to 0.20 mm to get past a fine-pitch pad is ordinary layout, and a
router that never does it routes fewer nets.  The point is to see how much of it there is.

    python scripts/check_geometry.py                          # the generated board
    python scripts/check_geometry.py output/router/routed.kicad_pcb
"""

import io
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_routes import blocks, field, netmap  # noqa: E402
import gen_pcb as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)

# What the board was asked for.  The same constants gen_pcb's own router uses, so the two
# routers are graded by one ruler.
WANT_W = G.AR_W
WANT_VIA, WANT_DRILL = G.AR_VIA, G.AR_VIA_DRILL
# Every layer a track may legally sit on -- SIGNAL_LAYERS, not AR_LAYERS.  Those two used to
# be the same set and are not since the board went to six layers: AR_LAYERS is the two that
# gen_pcb's own two-layer router understands, and grading a four-layer result against it
# would fail every track the external router laid on In2.Cu or In5.Cu.
ROUTING_LAYERS = set(G.SIGNAL_LAYERS)
# A tenth of the routing grid.  Anything at or under this is a nub, not a track: the two the
# external router left behind were 10 um stubs hanging off the end of a real track and joining
# nothing to nothing, and KiCadRoutingTools' own check_weird did not see them because they are
# under its tolerance too.  The comparison below is <= rather than <, and deliberately: a
# segment of exactly MIN_LEN is exactly as useless as one a nanometre shorter, and leaving the
# boundary case to be settled by whether 100.600 - 100.590 rounds to 0.0099999 or 0.0100001 is
# not a gate, it is a coin toss.
MIN_LEN = G.AR_GRID / 10.0

# The floors, for when even the repo's own project file cannot be read.  KiCad's built-in
# defaults are looser than anything this board declares, so falling back to those silently
# would turn a FAIL into a pass.  These are gen_netclasses.RULES, and a missing project file
# is reported rather than papered over.
FALLBACK = {
    "min_track_width": 0.2,
    "min_via_diameter": 0.5,
    "min_via_annular_width": 0.15,
    "min_through_hole_diameter": 0.2,
}

# The repo's project file, and the ONLY authority for what this board declares.
REPO_PRO = os.path.join(os.path.dirname(HERE), "mccan.kicad_pro")


def rules(board):
    """The board's declared minimums -- from the REPO's project file, never the board's own.

    This does not read the .kicad_pro beside the board being graded, and that is the whole
    point.  KiCadRoutingTools' route.py writes DRC settings back into its output project, and
    what it writes is LOOSER than what it was given: handed a project declaring a 0.50 mm via
    and a 0.15 mm annular ring, it wrote back 0.45 and 0.10.  (It does the same to
    min_connection, 0.25 -> 0.15, which is how the committed mccan.kicad_pro came to disagree
    with the generator that writes it.)  Grading a router's output against floors the router
    itself just rewrote is not a gate; it is the tool marking its own homework, and it would
    have passed exactly the 123 sub-floor vias this check exists to catch.

    gen_netclasses.py writes mccan.kicad_pro from RULES, so that file is what this repo has
    decided.  A sibling that disagrees is reported, because the disagreement is information.
    """
    out = dict(FALLBACK)
    if os.path.exists(REPO_PRO):
        got = (json.loads(io.open(REPO_PRO, encoding="utf-8").read())
               .get("board", {}).get("design_settings", {}).get("rules", {}))
        for k in FALLBACK:
            if k in got:
                out[k] = float(got[k])
    else:
        print("NOTE: %s is missing -- grading against gen_netclasses' own RULES"
              % os.path.basename(REPO_PRO))

    pro = os.path.splitext(board)[0] + ".kicad_pro"
    if os.path.exists(pro) and os.path.abspath(pro) != os.path.abspath(REPO_PRO):
        side = (json.loads(io.open(pro, encoding="utf-8").read())
                .get("board", {}).get("design_settings", {}).get("rules", {}))
        loose = ["%s %g (repo says %g)" % (k, float(side[k]), out[k])
                 for k in sorted(FALLBACK)
                 if k in side and float(side[k]) < out[k] - 1e-9]
        if loose:
            print("NOTE: %s declares looser floors than the repo, and is being IGNORED:"
                  % os.path.basename(pro))
            for line in loose:
                print("        " + line)
    return out


def histogram(counts, fmt="%g mm"):
    """`counts` printed commonest first, as "value xN"."""
    return ", ".join((fmt % v) + " x%d" % n
                     for v, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def via_histogram(counts):
    return ", ".join("%g/%g mm x%d" % (s, d, n)
                     for (s, d), n in sorted(counts.items(), key=lambda kv: -kv[1]))


def segments(text, names, lim, fails, widths, layers, necked):
    n = 0
    for blk in blocks(text, "segment"):
        st, en, w = field(blk, "start", 2), field(blk, "end", 2), field(blk, "width")
        ly = re.search(r'\(layer "([^"]*)"\)', blk)
        nt = re.search(r"\(net (\d+)\)", blk)
        if not (st and en and w and ly):
            continue
        n += 1
        name = names.get(int(nt.group(1)), "") if nt else ""
        wd, lay = round(w[0], 4), ly.group(1)
        widths[wd] = widths.get(wd, 0) + 1
        layers[lay] = layers.get(lay, 0) + 1
        where = "%s on %s @ (%.3f, %.3f)" % (name or "(no net)", lay, st[0], st[1])
        if wd < lim["min_track_width"] - 1e-6:
            fails.append("track under the board's %.3f mm floor: %.4f mm, %s"
                         % (lim["min_track_width"], wd, where))
        elif wd < WANT_W - 1e-6:
            necked[wd] = necked.get(wd, 0) + 1
        if lay not in ROUTING_LAYERS:
            fails.append("track on a plane layer, which is a slot cut through it: %s" % where)
        if math.hypot(st[0] - en[0], st[1] - en[1]) <= MIN_LEN + 1e-9:
            fails.append("zero-length segment: %s" % where)
    return n


def vias(text, names, lim, fails, sizes, necked):
    n = 0
    for blk in blocks(text, "via"):
        at, sz, dr = field(blk, "at", 2), field(blk, "size"), field(blk, "drill")
        nt = re.search(r"\(net (\d+)\)", blk)
        if not (at and sz and dr):
            continue
        n += 1
        name = names.get(int(nt.group(1)), "") if nt else ""
        s, d = round(sz[0], 4), round(dr[0], 4)
        sizes[(s, d)] = sizes.get((s, d), 0) + 1
        where = "%g/%g mm, %s @ (%.3f, %.3f)" % (s, d, name or "(no net)", at[0], at[1])
        ann = (s - d) / 2.0
        if s < lim["min_via_diameter"] - 1e-6:
            fails.append("via under the board's %.3f mm floor: %s"
                         % (lim["min_via_diameter"], where))
        elif s < WANT_VIA - 1e-6 or d < WANT_DRILL - 1e-6:
            necked[(s, d)] = necked.get((s, d), 0) + 1
        if ann < lim["min_via_annular_width"] - 1e-6:
            fails.append("annulus under the board's %.3f mm floor: %s"
                         % (lim["min_via_annular_width"], where))
        if d < lim["min_through_hole_diameter"] - 1e-6:
            fails.append("drill under the board's %.3f mm floor: %s"
                         % (lim["min_through_hole_diameter"], where))
    return n


def main(argv):
    board = argv[0] if argv else os.path.join(HW, "mccan.kicad_pcb")
    if not os.path.exists(board):
        print("FAIL: %s is missing" % board)
        return 2
    text = io.open(board, encoding="utf-8").read()
    names = netmap(text)
    lim = rules(board)

    fails = []
    widths, layers, sizes = {}, {}, {}
    necked_w, necked_v = {}, {}
    nseg = segments(text, names, lim, fails, widths, layers, necked_w)
    nvia = vias(text, names, lim, fails, sizes, necked_v)

    print("%s: %d segment(s), %d via(s)" % (os.path.basename(board), nseg, nvia))
    print("  widths: %s" % histogram(widths))
    print("  layers: %s" % histogram(layers, "%s"))
    print("  vias:   %s" % via_histogram(sizes))
    print("  asked for: track %g mm, via %g/%g mm, routing layers %s"
          % (WANT_W, WANT_VIA, WANT_DRILL, " ".join(sorted(ROUTING_LAYERS))))
    print("  board floors: %s" % ", ".join("%s %g" % (k[4:], v) for k, v in sorted(lim.items())))
    if necked_w:
        print("  necked tracks, legal but under the %g mm request: %s"
              % (WANT_W, histogram(necked_w)))
    if necked_v:
        print("  necked vias, legal but under the %g/%g request: %s"
              % (WANT_VIA, WANT_DRILL, via_histogram(necked_v)))

    if not fails:
        print("OK: all copper is at or above the board's own declared floors, and no track")
        print("    sits on a plane layer.")
        return 0

    # The same complaint two thousand times over is one problem, not two thousand of them.
    heads = {}
    for f in fails:
        heads.setdefault(f.split(":")[0], []).append(f)
    print("")
    print("FAIL: %d piece(s) of copper this board must not be frozen with." % len(fails))
    for head in sorted(heads, key=lambda h: -len(heads[h])):
        group = heads[head]
        print("  %s (x%d)" % (head, len(group)))
        for f in group[:4]:
            print("      %s" % f.split(": ", 1)[-1])
        if len(group) > 4:
            print("      ... and %d more" % (len(group) - 4))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
