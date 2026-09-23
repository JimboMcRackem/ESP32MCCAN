# -*- coding: utf-8 -*-
"""Hand the signal nets to KiCadRoutingTools, and leave everything else exactly as generated.

Why there is an external router at all
--------------------------------------
gen_pcb.py carries its own grid A* (the AR_* section).  It gets the board most of the way
there and it is the thing that knows about this design -- the GND_IN island, the thermal
vias, the ground drops, the true pad extents -- so it keeps the power stage, the fan-out
lanes and every hand route.  What it does badly is the last fifth of the signal bundle: on a
full pass it thrashes, ripping the same RGB return nets over and over, and settles at about
85 of 139 nets with the rest failing for want of a channel.  A dedicated router with rip-up
and reroute and real net ordering does that part better, so this file hands over exactly
that part and nothing else.

What this does NOT do
---------------------
It does not route, move or even look at the copper this repo decided by hand.  Every net in
the FEED and CAN classes is excluded by name, and so is GND.  POWER is NOT in that list --
this is no longer the set gen_pcb.AR_SKIP_CLASSES skips, because +24V, +5V and VLOGIC_IN
stopped being In4.Cu zones and became nets like any other, with nobody but this router left
to lay them.  So the boost stage, the feed and the CAN pair go through untouched, as
obstacles it has to work around, while the three rails go through as nets it routes.  The
exclusion list is built from layout_pcb.NETCLASSES rather than typed out here, so moving a
net into a class automatically keeps it out of the external router's hands.

The chain
---------
    0. check_courtyards.py over the placement, because a courtyard overlap is only caught by
       KiCad's DRC, which in this chain runs after the router does.
    1. gen_pcb.py with AR_SKIP=1 and PCB_OUT pointed at output/router/, so the input board is
       everything this repo generates MINUS the signal copper.  mccan.kicad_pcb is not
       touched, and neither is mccan.kicad_pro -- route.py writes DRC settings back into the
       sibling project, so it is given a copy.
    2. KiCadRoutingTools route.py over the signal nets only, on gen_pcb.SIGNAL_LAYERS --
       F.Cu, In2.Cu, In4.Cu and B.Cu.  In1.Cu is the ground plane and In3.Cu the VBAT
       plane; a track on either is a slot cut through a reference, so neither is offered.
    3. this repo's check_geometry, then the tool's own check_connected / check_drc /
       check_weird, then this repo's check_vias and check_grounds.

Why check_geometry runs first
----------------------------
Because the tool does not fail when it goes below the sizes it was given.  Its --fab-tier
flag is not the floor it reads as; --escalation is, and its default lets a failing net be
retried BELOW the board's own minimums.  The first full run came back nominally clean and
carried 2177 tracks at 0.0889 mm.  The flags below shut that off, and check_geometry is what
proves they did -- a board whose copper is under its own declared floors cannot be frozen,
however well it grades on connectivity.

Nothing here writes mccan.kicad_pcb.  Folding a good result back into the generated board is
a separate step -- see hardware/docs/routing-tool.md.

Usage
-----
    python scripts/route_external.py                 # regenerate input, route, check
    python scripts/route_external.py --no-regen      # reuse output/router/unrouted.kicad_pcb
    python scripts/route_external.py --preview       # route it, report, write no board
    python scripts/route_external.py -- --max-ripup 6 --heuristic-weight 1.9
                                                     # anything after -- goes to route.py

Environment:
    KRT_HOME    where KiCadRoutingTools lives   (default ~/KiCadRoutingTools)
    KRT_PYTHON  the interpreter that has numpy / scipy / shapely and the built Rust router
                (default: the .venv under KRT_HOME)
"""

import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_pcb as L  # noqa: E402
import gen_pcb as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
WORK = os.path.join(HW, "output", "router")

UNROUTED = os.path.join(WORK, "unrouted.kicad_pcb")
ROUTED = os.path.join(WORK, "routed.kicad_pcb")
SUMMARY = os.path.join(WORK, "routed-summary.json")

# The classes no router may touch.  FEED is hand-routed in Task 7 and CAN in Task 8, both
# because their geometry is the point: the feed is poured to a width, and the CAN pair has
# to stay a pair.  POWER used to be here too, back when +24V, +5V and VLOGIC_IN were zones
# on In4.Cu -- they are not, so somebody has to route them, and at 11, 7 and 6 pads on four
# signal layers that somebody is the external router.  This is deliberately NOT
# G.AR_SKIP_CLASSES any more: gen_pcb's own fallback router carries a two-layer occupancy
# grid and keeps its POWER skip.
HANDS_OFF = ("FEED", "CAN")


def krt_home():
    return (os.environ.get("KRT_HOME")
            or os.path.join(os.path.expanduser("~"), "KiCadRoutingTools"))


def krt_python(home):
    env = os.environ.get("KRT_PYTHON")
    if env:
        return env
    for parts in (("Scripts", "python.exe"), ("bin", "python")):
        cand = os.path.join(home, ".venv", parts[0], parts[1])
        if os.path.exists(cand):
            return cand
    return sys.executable


def excluded_nets():
    """Every net the external router must not touch, as route.py --nets exclusion patterns.

    NETCLASSES names nets by their SHORT name; the board names them hierarchically, so
    VBAT_PROT has to be matched as "*/VBAT_PROT".  Every net on this board starts with "/",
    so that one pattern covers both "/VBAT" and "/power_input/VBAT_PROT" -- and, deliberately,
    does NOT cover "/outputs/+24V_FL", which is a Default-class corner feed and is the
    external router's to lay.  GND is in no class at all, being the plane, so it goes in by
    hand.
    """
    out = ["!GND"]
    for cname, _tw, _cl, _vs, _vd, nets in L.NETCLASSES:
        if cname not in HANDS_OFF:
            continue
        for n in nets:
            out.append("!*/" + n)
    return out


def run(argv, title):
    print("")
    print("=== " + title)
    rc = subprocess.call(argv)
    print("    exit %d" % rc)
    return rc


def regenerate():
    """Write output/router/unrouted.kicad_pcb: this repo's board, minus the signal copper."""
    if not os.path.isdir(WORK):
        os.makedirs(WORK)
    env = dict(os.environ)
    env["AR_SKIP"] = "1"
    env["PCB_OUT"] = UNROUTED
    env["PYTHONIOENCODING"] = "utf-8"
    # Courtyards first, because this is the one failure that costs a whole run.  KiCad's DRC
    # is the only thing that checks courtyard overlap and it runs at the END of this chain --
    # after twenty minutes of routing.  U4's nudge was taken on copper arithmetic, regenerated
    # clean, passed every guard, routed, and only then came back with two courtyards_overlap
    # ERRORS.  The check costs a second and reads the placer, not the board, so it can run
    # before anything is generated at all.
    print("=== checking the placement")
    rc = subprocess.call([sys.executable, "-u", os.path.join(HERE, "check_courtyards.py")],
                         env=env)
    if rc:
        return rc

    print("=== generating the unrouted input board")
    rc = subprocess.call([sys.executable, "-u", os.path.join(HERE, "gen_pcb.py")], env=env)
    if rc:
        return rc
    # route.py reads the sibling project for net classes and DRC constraints and writes its
    # own adjustments back into it.  Give it a copy, so a router run can never edit the real
    # mccan.kicad_pro.
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(HW, "mccan" + ext)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(WORK, "unrouted" + ext))
    return protect()


def protect():
    """Tell route.py which nets it may not RIP, as distinct from may not ROUTE.

    --nets exclusions only keep a net out of the routing queue.  They say nothing about the
    rip-up ladder, and route.py's later salvage stages build their own rip-eligibility list
    from the board: run 6 printed "5 pre-existing net(s) eligible for rip-up: /+5V, /CANH,
    /CANL, /VLOGIC_IN, /outputs/PWM_RR_R" -- every one of them a net this script had just
    excluded.  It then ripped /+5V to clear a tap route for /+3V3_SW, could not put it back
    ("original corridor taken"), and shipped the board with the whole hand-routed +5V
    distribution gone: 21 segments and 4 vias, from the U2 output all the way to U6.  The
    improvement gate weighed one lost net against thirty gained and kept the result, which is
    the right call for a net the router owns and the wrong one for a net it does not.
    freeze_routes.py caught it, because that chain is additive by contract, but only after the
    run.

    route.py has a mechanism for exactly this: a protection map in the sibling .kicad_pro
    (issue #521, "routed invariants that later chain steps must not rip").  Every rip channel
    consults it -- the pre-run --rip-existing-nets expansion, all six in-run rip ladders
    through filter_rippable_blockers, and the octolinear smoothing pass.  Protection lifts
    only for a net named EXACTLY, with no glob, in --nets or --rip-existing-nets; "!*/+5V"
    carries a "*" and "!GND" is not the string "GND", so nothing this script passes can lift
    it by accident.

    The list is derived from excluded_nets() rather than restated, so the two cannot drift:
    same patterns, matched against the board's own net names the way route.py matches them.
    """
    text = io.open(UNROUTED, encoding="utf-8").read()
    names = [m.group(1) for m in re.finditer(r'\(net \d+ "([^"]+)"\)', text)]
    pats = [p.lstrip("!") for p in excluded_nets()]
    keep = sorted(set(n for n in names if any(fnmatch.fnmatch(n, p) for p in pats)))

    pro = os.path.join(WORK, "unrouted.kicad_pro")
    if not os.path.exists(pro):
        sys.stderr.write("no unrouted.kicad_pro to write protection into\n")
        return 1
    proj = json.load(io.open(pro, encoding="utf-8"))
    ns = proj.setdefault("kicad_routing_tools", {})
    ns["protected_nets"] = dict((n, "hand-routed") for n in keep)
    with io.open(pro, "w", encoding="utf-8") as f:
        f.write(json.dumps(proj, indent=2))
    print("    %d net(s) marked unrippable in unrouted.kicad_pro" % len(keep))
    return 0


def archive():
    """Keep every routed board, filed under the score it got.

    Each run overwrites routed.kicad_pcb, and the runs are not monotonic -- they are a
    sequence of experiments whose results wander.  Run 4 of this board scored 276 connected
    pad pairs, run 5 scored 274, and run 4's copper was gone before anyone knew that, which
    means the best result the board had produced could not be frozen, compared against, or
    even looked at.  Copying costs 1.7 MB and a moment; output/router/ is gitignored, so it
    costs the repository nothing at all.
    """
    try:
        s = json.load(io.open(SUMMARY, encoding="utf-8"))
        tag = "%03d-of-%03d" % (s.get("pad_pairs_connected", 0), s.get("pad_pairs_total", 0))
    except Exception:
        tag = "unknown"
    keep = os.path.join(WORK, "runs")
    if not os.path.isdir(keep):
        os.makedirs(keep)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for src, ext in ((ROUTED, ".kicad_pcb"), (SUMMARY, ".json")):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(keep, "%s-%s%s" % (stamp, tag, ext)))
    print("    kept as output/router/runs/%s-%s.*" % (stamp, tag))


def main(argv):
    regen = "--no-regen" not in argv
    preview = "--preview" in argv
    extra = argv[argv.index("--") + 1:] if "--" in argv else []

    home = krt_home()
    py = krt_python(home)
    route = os.path.join(home, "py_router", "route.py")
    if not os.path.exists(route):
        print("FAIL: no py_router/route.py under %s -- set KRT_HOME" % home)
        return 2
    built = any(os.path.exists(os.path.join(home, "rust_router", "grid_router" + x))
                for x in (".pyd", ".so", ".abi3.so"))
    if not built:
        print("WARN: the Rust router is not built under %s, so this will be ~10x slower." % home)
        print("      cd %s && python build_router.py" % home)

    if regen:
        rc = regenerate()
        if rc:
            return rc
    if not os.path.exists(UNROUTED):
        print("FAIL: %s is missing; run without --no-regen" % UNROUTED)
        return 2

    # Geometry: the same numbers gen_pcb's own router uses, so the two results are comparable
    # and so this one lands on the same 0.1 mm grid as the fan-out lanes it has to join.
    cmd = [py, "-u", route, UNROUTED, ROUTED]
    cmd += ["--nets", "*"] + excluded_nets()
    cmd += ["--layers"] + list(G.SIGNAL_LAYERS)
    cmd += ["--track-width", str(G.AR_W)]
    cmd += ["--clearance", str(G.AR_CLEAR)]
    cmd += ["--via-size", str(G.AR_VIA), "--via-drill", str(G.AR_VIA_DRILL)]
    cmd += ["--grid-step", str(G.AR_GRID)]
    cmd += ["--board-edge-clearance", str(G.AR_EDGE)]
    # 10, not gen_pcb's AR_VIA_COST of 35.  That 35 was chosen for a TWO layer board, where a
    # via really does cost you the other side; this board has four signal layers.  Measured
    # back to back with everything else identical, 35 scored 274 connected pad pairs and 10
    # scored 276, so it is worth keeping -- but not for the reason it was tried.  The theory
    # was that a high via cost makes the router hoard F.Cu, which is the one layer carrying
    # every SMD pad on the board.  It does not: the layer split barely moved (F.Cu 34.5% of
    # track length at 35, 35.3% at 10), because the distribution is pinned by the fact that
    # every net starts and ends on F.Cu whatever it does in between.  What the lower cost
    # actually buys is permission to hop more often -- 629 vias became 937 -- which is worth
    # about two pad pairs at the margin and nothing at all to the layer balance.
    #
    # VIA_COST in the environment overrides it, which is how those two runs were compared.
    cmd += ["--via-cost", os.environ.get("VIA_COST", "10")]
    # A hard fab floor.  Left to itself the router escalates to the "advanced" tier when a net
    # will not otherwise close -- a preview run took U8 pad 21's plane tap down to a 0.25/0.15
    # via -- and says so in a warning that is easy to lose in 70 000 lines of log.  This board
    # is quoted at the standard tier and its own minimums are 0.20 mm, so a net that needs
    # finer geometry than that is a net we want reported as failed, not quietly laid.
    cmd += ["--fab-tier", "standard"]
    # --fab-tier alone does not hold that floor.  The lever is --escalation, whose DEFAULT is
    # "fab" -- documented as "down to the fab tier floor, BELOW the board's own minimums" --
    # and the first full run took it, handing back 2177 tracks at 0.0889 mm against this
    # 0.25 mm request.  "board" is the setting the comment above was reaching for: a net may
    # neck down to what this board declares and KiCad's DRC accepts (0.20 mm track, 0.45 mm
    # via) and no further; below that it fails and is named.
    cmd += ["--escalation", "board"]
    # There is not a BGA on this board -- no BGA, no LGA, no CSP, nothing on a ball grid at
    # all.  The detector is really a fine-pitch-grid detector and it fires on TSSOP and QFN:
    # it read U7, a 0.65 mm TSSOP-28, as "14 rows x 2 columns" and ran an under-pad shrink
    # rescue at 0.0762 mm track / 0.25 mm via / 0.09 mm clearance.  That rescue path is where
    # the sub-floor copper came from, and it is not a path this board ever needs.
    cmd += ["--no-bga-zones"]
    # freeze_routes.py is a DIFF, so it is only correct while the output is a SUPERSET of the
    # input.  Left alone, the post-route cleanup sweeps input copper it judges dead: the last
    # run stripped 7 input segments and left 5 nets ripped, which freeze_routes.py would have
    # refused -- rightly, and after an hour of routing.  This makes the input read-only.
    cmd += ["--keep-input-copper"]
    # The run's own tally, as a file.  route.py prints two JSON_SUMMARY blocks to stdout when
    # its end-of-run reconciliation fires, and scraping either one alone is wrong; this is the
    # merged one, and it is the only place the escalation counts are reported as data.
    cmd += ["--json-out", SUMMARY]
    if preview:
        cmd.append("--preview")
    cmd += extra

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    print("")
    print("=== routing the signal nets with KiCadRoutingTools")
    print("    " + " ".join(cmd))
    rc = subprocess.call(cmd, env=env)
    print("    exit %d" % rc)
    if rc or preview:
        return rc
    archive()

    # Geometry first, because it is the one that decides whether the rest is worth reading.
    # A board with copper under its own floors cannot be frozen however well it grades on
    # connectivity, and this is the check that catches the router quietly going below what it
    # was told -- see the --escalation comment above, and scripts/check_geometry.py.
    run([sys.executable, "-u", os.path.join(HERE, "check_geometry.py"), ROUTED],
        "track and via geometry against the board's own floors (this repo)")
    run([py, "-u", os.path.join(home, "py_router", "check_connected.py"), ROUTED],
        "connectivity (KiCadRoutingTools)")
    run([py, "-u", os.path.join(home, "py_router", "check_drc.py"), ROUTED],
        "clearances (KiCadRoutingTools)")
    run([py, "-u", os.path.join(home, "py_router", "check_weird.py"), ROUTED],
        "copper hygiene, dangling stubs included (KiCadRoutingTools)")
    # With the input board as a baseline this grades gen_pcb's OWN vias and skips the
    # router's, which is the only way the thermal/stitching split means anything here -- and
    # it fails if the router handed back fewer than it was given.  See check_vias.py's BASE.
    run([sys.executable, "-u", os.path.join(HERE, "check_vias.py"), ROUTED, UNROUTED],
        "via placement, gen_pcb's own vias only (this repo)")
    run([sys.executable, "-u", os.path.join(HERE, "check_grounds.py"), ROUTED],
        "GND / GND_IN separation (this repo)")
    # Last, because it is the only check whose answer the ROUTER can make worse: every via
    # it placed punches another antipad through the VBAT plane, so the plane is narrower
    # after a run than the input board it was measured on.
    run([sys.executable, "-u", os.path.join(HERE, "check_plane_width.py"), ROUTED],
        "VBAT plane cross-section against IPC-2221 (this repo)")

    print("")
    print("The routed board is %s." % ROUTED)
    print("It is NOT mccan.kicad_pcb, and it is not meant to be committed as one --")
    print("hardware/docs/routing-tool.md has how a good result gets folded back in.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
