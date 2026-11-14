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
       F.Cu, In2.Cu, In5.Cu and B.Cu.  In1.Cu, In3.Cu and In6.Cu are the three GND planes
       and In4.Cu the solid VBAT plane (gen_pcb.PLANE_LAYERS); a track on any of them is a
       slot cut through a reference, so none of the four is offered.
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
SNS_IN = os.path.join(WORK, "sns_in.kicad_pcb")        # pass 1 input: + the SNS keep-outs
SNS_OUT = os.path.join(WORK, "sns_routed.kicad_pcb")   # pass 1 output = pass 2 input
ROUTED = os.path.join(WORK, "routed.kicad_pcb")
SUMMARY = os.path.join(WORK, "routed-summary.json")

# The classes no router may touch.  FEED is hand-routed in Task 7 and CAN in Task 8, both
# because their geometry is the point: the feed is poured to a width, and the CAN pair has
# to stay a pair.  POWER used to be here too, back when +24V, +5V and VLOGIC_IN were zones
# on In4.Cu -- they are not, so somebody has to route them, and at 11, 7 and 6 pads on four
# signal layers that somebody is the external router.  This is deliberately NOT
# G.AR_SKIP_CLASSES any more: gen_pcb's own fallback router carries a two-layer occupancy
# grid and keeps its POWER skip.
HANDS_OFF = ("FEED_B", "FEED", "CAN")

# Plan4 (Task 7).  The ground nets are PLANE nets the router welds into their pours: every SMD
# pad on GND or GND_IN gets its drop via from the route step (KiCadRoutingTools #562 -- the
# pour does no tapping).  GND_IN sits in the FEED class but has no hand copper of its own, so
# it is lifted out of HANDS_OFF here; GND_B is fully connected by its pours and stays out.
PLANE_NETS = [("GND", 0.4), ("/power_input/GND_IN", 0.4)]
# The logic rails are POWER class: routed here, at the class width.
POWER_NETS = [("*/+3V3_ALW", 0.5), ("*/+5V", 0.5), ("*/VLOGIC_IN", 0.5)]
ROUTABLE_FROM_HANDS_OFF = ("GND_IN",)

# The ADC sense lines (brief Task 7 step 1): routed FIRST and alone, on In5.Cu (GND on In4 and
# In6, both faces) with F.Cu for the pad escapes priced 10x, and kept by router keep-outs out
# of the feed-B region (R_B and the Q13/Q14 pours) and the buck region.  The second pass
# routes everything else around them and cannot rip them (pre-existing copper is never ripped).
SNS_NETS = ["/SNS_A", "/SNS_B", "/SNS_C"]
SNS_LAYERS, SNS_COSTS = ["F.Cu", "In5.Cu"], ["10", "1"]
SNS_KEEPOUTS = {
    "feed_B": (L._B_X, 74.0, L.X1, L.Y1),                   # R_B, plus Q14's pours to y 74.6
    "bucks": L.REGIONS["rails"],
}
# Copper the router must never lay, in any pass, as (name, layers, polygon).
#  - The feed-B pours, on the layers they are poured on.  A signal track through FEED_B_P or
#    the F.Cu VBAT_B source pour is legal to DRC -- the pour just clears around it -- and it
#    carves a slot across a 6.4 A path (route9 ran DSEL and others through Q13's drain copper).
#  - U10's ON pin (pin 9, unconnected).  check_power_paths' ON guard wants foreign copper on
#    F.Cu more than 0.5 mm from that pad; route9 ran FL_DRL down x 61.8, 0.50 mm off its end.
#    The pad ends at x 61.35; the area runs to 61.7 and the router adds its clearance (0.2)
#    beyond it, so foreign copper stops at x >= 61.9.  Pins 8 and 10 escape west, inward.
_U10_ON = (L.PLACE["U10"][0] + 2.1 + 0.75, L.PLACE["U10"][1] - 0.5)    # pad 9's east end
# NT1, the GND_B/GND_IN star tie: its 4 x 2 mm copper bar is a graphic polygon with no net,
# so a via in it -- route12 put a GND_IN weld via in pad 2's edge -- is a KiCad hole_clearance
# error.  Vias only (a 4th field "vias"): tracks still have to reach both pads.
_NT1 = L.PLACE["NT1"]
RULE_KEEPOUTS = [
    ("ko_nt1", ["F.Cu"], [(_NT1[0] - 3.0, _NT1[1] - 1.0), (_NT1[0] + 3.0, _NT1[1] - 1.0),
                          (_NT1[0] + 3.0, _NT1[1] + 1.0), (_NT1[0] - 3.0, _NT1[1] + 1.0)], "vias"),
    # F.Cu and In5 both take the notched outline: the notch is where U14's control lines
    # drop to In2, and their vias pierce In5 there (the In5 pour clears round each one).
    ("ko_feedb", ["F.Cu", "In5.Cu"], L.FEEDB_F_POLY),
    ("ko_feedb_bot", ["B.Cu"], L.FEEDB_BOT),
    ("ko_vbatb_src", ["F.Cu"], L.VBATB_SRC),
    ("ko_u10_on", ["F.Cu"], [(_U10_ON[0] + 0.05, _U10_ON[1] - 0.5), (_U10_ON[0] + 0.35, _U10_ON[1] - 0.5),
                             (_U10_ON[0] + 0.35, _U10_ON[1] + 0.5), (_U10_ON[0] + 0.05, _U10_ON[1] + 0.5)]),
]


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

    NETCLASSES names nets by their SHORT name, and this has to match the board's actual net
    names the same two ways gen_netclasses.resolve() does: `n == short` for a net named
    literally, or `n.rsplit("/", 1)[-1] == short` for one named hierarchically.  So each short
    name gets BOTH an exact pattern and a "*/"-prefixed one, rather than picking one form and
    guessing which nets need it.

    Most nets on this board are hierarchical -- VBAT_PROT has to be matched as "*/VBAT_PROT",
    which covers both "/VBAT" and "/power_input/VBAT_PROT", and, deliberately, does NOT cover
    "/outputs/+24V_FL", a Default-class corner feed that is the external router's to lay.  But
    Net-(U6-CANH) and Net-(U6-CANL), the transceiver-side halves of the CAN pair, are named
    literally with no "/" in them at all (fault 2, fix round 2): "*/" + n requires a "/" to
    appear before the match, so that pattern alone silently excluded nothing for these two, and
    the external router was free to hand-route over Task 8's own copper.  Emitting the exact
    pattern too closes that gap without having to special-case which nets are which -- the
    pattern that does not apply to a given net (e.g. plain "!CANH", when the board only ever
    calls it "/CANH") simply never matches anything.

    GND is in no class at all, being the plane, so it goes in by hand.
    """
    out = []
    for cname, _tw, _cl, _vs, _vd, nets in L.NETCLASSES:
        if cname not in HANDS_OFF:
            continue
        for n in nets:
            if n in ROUTABLE_FROM_HANDS_OFF:
                continue
            out.append("!" + n)
            out.append("!*/" + n)
    return out


def run(argv, title):
    print("")
    print("=== " + title)
    rc = subprocess.call(argv)
    print("    exit %d" % rc)
    return rc


LAND_RULE = re.compile(r"\(constraint clearance \(min ([\d.]+)mm\)\)\s*"
                       r"\(condition \"A\.memberOfFootprint\('([^']+)'\)\"\)")


def land_pattern_floors(dru):
    """{ref: clearance} from the .kicad_dru 'land pattern' rules gen_pcb writes."""
    try:
        text = io.open(dru, encoding="utf-8").read()
    except IOError:
        return {}
    return dict((ref, float(mm)) for mm, ref in LAND_RULE.findall(text))


def drc_gate(argv, title, dru):
    """check_drc.py, graded for the one rule class it says it cannot see.

    check_drc skips the .kicad_dru land-pattern rules ("non-layer scope ... skipped, KiCad will
    still enforce it") and grades a pad inside U2/U10-U14 at its net class instead.  route11
    failed on 23 such pairs -- hand fan-outs and pin welds 0.2 mm off a 0.5 mm-pitch neighbour --
    every one of which KiCad's own DRC accepts.  A pad-to-copper item is accepted here only when
    its pad belongs to a part with such a rule AND the real gap meets that rule; anything else,
    a short included, still fails.  KiCad's DRC on the generated board is the final word.
    """
    out = os.path.join(WORK, "check_drc.json")
    rc = run(argv + ["--json", out], title)
    if not rc:
        return 0
    floors = land_pattern_floors(dru)
    try:
        items = json.load(io.open(out, encoding="utf-8"))["items"]
    except (IOError, ValueError, KeyError):
        return rc
    # The tool lists what it ACCEPTED in the same array (212 vias in paste openings, graded on
    # the fab drawing); those carry an "accepted" reason and are not violations.
    items = [it for it in items if not it.get("accepted")]
    bad = []
    for it in items:
        ref = (it.get("pad_ref") or "").split(".")[0]
        gap = it.get("required_mm", 0) - it.get("overlap_mm", 1)
        if (it.get("type") in ("pad-segment", "pad-via") and not it.get("short")
                and ref in floors and gap >= floors[ref] - 1e-6):
            continue
        bad.append(it)
    print("    %d item(s) inside a land-pattern rule KiCad enforces and this copper meets; "
          "%d other(s)" % (len(items) - len(bad), len(bad)))
    return 1 if bad else 0


WEIRD_OK = ("redundant-cycle", "removable-segment")


def weird_gate(argv, title):
    """check_weird.py, failing on everything but spare copper.

    redundant-cycle and removable-segment are copper a net does not need -- a loop, a second
    path -- and nothing KiCad's DRC or a fab objects to.  Dangling ends and vias, soft joints,
    stacked copper, orphan islands and narrow pad joints still fail.
    """
    print("")
    print("=== " + title)
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = p.communicate()[0].decode("utf-8", "replace")
    sys.stdout.write(text)
    print("    exit %d" % p.returncode)
    if not p.returncode:
        return 0
    counts = dict((k, int(n)) for k, n in re.findall(r"^\s+([a-z-]+): (\d+)\s*$", text, re.M))
    if not counts:
        return p.returncode
    bad = dict((k, n) for k, n in counts.items() if n and k not in WEIRD_OK)
    print("    spare copper only (%s) -- accepted" % ", ".join(WEIRD_OK) if not bad
          else "    FAIL: %s" % ", ".join("%s %d" % kv for kv in sorted(bad.items())))
    return 1 if bad else 0


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
    floor_clearance(os.path.join(WORK, "unrouted.kicad_pro"))
    return protect()


def floor_clearance(pro):
    """Raise the router copy's rules.min_clearance to the Default class's clearance.

    --escalation board lets a failing net descend to the board's declared floors, and this
    board declares 0.15 mm clearance (the hand-routed fine-pitch fan-outs need it).  route10's
    fine passes took that and shipped 0.15 mm gaps on Default-class nets -- which KiCad's own DRC
    grades against the class's 0.2 mm and fails.  Width may still neck to 0.15 (KiCad checks
    track width against the board minimum, not the class); clearance may not.  Only the
    router's scratch copy changes; mccan.kicad_pro keeps 0.15.
    """
    d = json.load(io.open(pro, encoding="utf-8"))
    d["board"]["design_settings"]["rules"]["min_clearance"] = G.AR_CLEAR
    io.open(pro, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")


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


SIG_OUT = os.path.join(WORK, "sig_routed.kicad_pcb")     # pass 2 output = pass 2b input
SIG_SUMMARY = os.path.join(WORK, "sig-summary.json")
FINE_OUT = os.path.join(WORK, "fine_routed.kicad_pcb")
FINE_SUMMARY = os.path.join(WORK, "fine-summary.json")
# Fine passes: 0.05 mm grid and the 0.15 mm track floor (layout_pcb.RULES), but the Default
# class clearance (0.2) -- KiCad and gen_pcb.check_track_crossings both enforce the class.
FINE_GRID, FINE_W = 0.05, 0.15
QUAD_OUT = os.path.join(WORK, "quad_routed.kicad_pcb")   # pass 1b output = pass 2 input
QUAD_SUMMARY = os.path.join(WORK, "quad-summary.json")
QUADS, QUAD_PINS = ("U11", "U12", "U13"), set(str(n) for n in range(2, 14))


def quad_control_nets(board):
    """The nets on the quads' control pins (2-13: IN, SEL, DIAG_EN, SNS, ILIM), less ground
    and no-connects -- and less the SNS lines, which pass 1 owns."""
    text = io.open(board, encoding="utf-8").read()
    out = set()
    for fp in text.split("\n\t(footprint ")[1:]:
        ref = re.search(r'\(property "Reference" "([^"]+)"', fp)
        if not ref or ref.group(1) not in QUADS:
            continue
        for m in re.finditer(r'\(pad "(\d+)"[^\n]*(?:\n[^\n]*?){0,12}?\(net (?:\d+ )?"([^"]+)"\)', fp):
            if m.group(1) in QUAD_PINS:
                out.add(m.group(2))
    return sorted(n for n in out
                  if n not in ("GND",) + tuple(SNS_NETS) and not n.startswith("unconnected-"))


def protect_more(pro, nets):
    """Add `nets` to the route.py protection map in project file `pro` (see protect())."""
    proj = json.load(io.open(pro, encoding="utf-8"))
    ns = proj.setdefault("kicad_routing_tools", {}).setdefault("protected_nets", {})
    for n in nets:
        ns[n] = "routed by an earlier pass"
    with io.open(pro, "w", encoding="utf-8") as f:
        f.write(json.dumps(proj, indent=2))


def open_nets(summary):
    """Every net a route.py --json-out summary reports as failed or left open."""
    try:
        s = json.load(io.open(summary, encoding="utf-8"))
    except (IOError, ValueError):
        return []
    out = set(s.get("failed_single", ())) | set(s.get("open_single", ()))
    out |= set(m["net_name"] for m in s.get("failed_multipoint", ()))
    return sorted(out)


def write_sns_input():
    """UNROUTED plus the pass-1 keep-out polygons on User.2 (route.py --keepout reads them)."""
    text = io.open(UNROUTED, encoding="utf-8").read().rstrip()
    assert text.endswith(")")
    polys = []
    for name, (x0, y0, x1, y1) in sorted(SNS_KEEPOUTS.items()):
        pts = " ".join("(xy %g %g)" % p for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
        polys.append('\t(gr_poly (pts %s) (stroke (width 0.1) (type solid)) (fill no) '
                     '(layer "User.2") (uuid "%s"))'
                     % (pts, "00000000-0000-4000-8000-%012d" % (len(polys) + 1)))
    # Rule-area keep-outs, which route.py honours in EVERY pass without a flag, per layer, and
    # which carry from this file through every later pass's input.  (These live only in the
    # router's scratch boards: gen_pcb.py never emits them.)
    for ko in RULE_KEEPOUTS:
        name, layers, pts = ko[:3]
        tracks = "allowed" if ko[3:] == ("vias",) else "not_allowed"
        polys.append('\t(zone (net 0) (net_name "") (layers %s) (uuid "%s") (name "%s") '
                     '(hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) '
                     '(keepout (tracks %s) (vias not_allowed) (pads allowed) '
                     '(copperpour allowed) (footprints allowed)) '
                     '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                     '(polygon (pts %s)))'
                     % (" ".join('"%s"' % l for l in layers),
                        "00000000-0000-4000-8000-%012d" % (len(polys) + 1), name, tracks,
                        " ".join("(xy %g %g)" % p for p in pts)))
    io.open(SNS_IN, "w", encoding="utf-8", newline="\n").write(
        text[:-1] + "\n".join(polys) + "\n)\n")
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(WORK, "unrouted" + ext)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(WORK, "sns_in" + ext))


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
    cmd = []
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
    if preview:
        cmd.append("--preview")
    cmd += extra

    widths = PLANE_NETS + POWER_NETS
    cmd += ["--power-nets"] + [n for n, _w in widths]
    cmd += ["--power-nets-widths"] + [str(w) for _n, w in widths]

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    # Pass 1: the sense lines alone, inside their keep-outs.
    write_sns_input()
    p1 = [py, "-u", route, SNS_IN, SNS_OUT, "--nets"] + SNS_NETS
    p1 += ["--layers"] + SNS_LAYERS + ["--layer-costs"] + SNS_COSTS + ["--keepout"]
    p1 += cmd
    print("")
    print("=== pass 1: SNS_A/B/C on In5.Cu, kept out of feed B and the bucks")
    print("    " + " ".join(p1))
    rc = subprocess.call(p1, env=env)
    print("    exit %d" % rc)
    if rc or preview:
        return rc
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(WORK, "unrouted" + ext)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(WORK, "sns_routed" + ext))
    # Pre-existing copper is NOT safe from a later pass: route.py's via-in-pad decline path
    # blamed /SNS_A for a boxed pad, ripped it, and could not put it back.  So the sense lines
    # join the hand-routed nets in the protection map for every later pass.
    protect_more(os.path.join(WORK, "sns_routed.kicad_pro"), SNS_NETS)

    # Pass 1b: the quads' control nets, before anything else crowds the field south of them.
    # Twelve used pins a chip on a 0.5 mm pitch: routed in the general pass they came last into
    # a field already full of other nets' vias, and route.py found them "boxed in by static
    # obstacles" -- ten were left open however they were ordered.  Fine grid, board floors.
    quad = quad_control_nets(SNS_OUT)
    p1b = [py, "-u", route, SNS_OUT, QUAD_OUT, "--nets"] + quad
    p1b += ["--layers"] + list(G.SIGNAL_LAYERS) + cmd
    p1b += ["--grid-step", str(FINE_GRID), "--clearance", str(G.AR_CLEAR),
            "--track-width", str(FINE_W), "--json-out", QUAD_SUMMARY]
    print("")
    print("=== pass 1b: the quads' %d control nets, on the fine grid" % len(quad))
    print("    " + " ".join(p1b))
    rc = subprocess.call(p1b, env=env)
    print("    exit %d" % rc)
    if rc:
        return rc
    shutil.copyfile(os.path.join(WORK, "sns_routed.kicad_pro"),
                    os.path.join(WORK, "quad_routed.kicad_pro"))
    if os.path.exists(os.path.join(WORK, "unrouted.kicad_dru")):
        shutil.copyfile(os.path.join(WORK, "unrouted.kicad_dru"),
                        os.path.join(WORK, "quad_routed.kicad_dru"))
    done = [n for n in quad if n not in open_nets(QUAD_SUMMARY)]
    protect_more(os.path.join(WORK, "quad_routed.kicad_pro"), done)
    early = SNS_NETS + done

    # Pass 2: every other signal net and the ground welds, around the sense lines -- but NOT
    # the logic rails.  Routed in one pass with the signals, +3V3_ALW went first and laid its
    # 0.5 mm track along U11's pin tips (x 62.2, y 61-81), walling in all fourteen of its
    # control pins; the quads' IN/ILIM/CS nets then had nowhere to escape.
    rails = [n for n, _w in POWER_NETS]
    p2 = [py, "-u", route, QUAD_OUT, SIG_OUT, "--nets", "*"] + excluded_nets()
    p2 += ["!" + n for n in rails]
    p2 += ["--layers"] + list(G.SIGNAL_LAYERS) + cmd + ["--json-out", SIG_SUMMARY]
    print("")
    print("=== pass 2: every other signal net and the ground welds")
    print("    " + " ".join(p2))
    rc = subprocess.call(p2, env=env)
    print("    exit %d" % rc)
    if rc:
        return rc
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(WORK, "unrouted" + ext)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(WORK, "sig_routed" + ext))
    protect_more(os.path.join(WORK, "sig_routed.kicad_pro"), early)

    # Pass 2b: the logic rails, around everything else.
    p2b = [py, "-u", route, SIG_OUT, ROUTED, "--nets"] + rails
    p2b += ["--layers"] + list(G.SIGNAL_LAYERS) + cmd + ["--json-out", SUMMARY]
    print("")
    print("=== pass 2b: the logic rails")
    print("    " + " ".join(p2b))
    rc = subprocess.call(p2b, env=env)
    print("    exit %d" % rc)
    if rc:
        return rc

    # Pass 3: whatever passes 2 and 2b left open, on a 0.05 mm grid at the board's 0.15 mm floors.
    # The quads (TPS4HC120 DGQ, 0.5 mm pitch) put their pad centres on x.x5, half a 0.1 mm
    # cell off grid, so at 0.2 / 0.2 their inner pins are boxed in by their own neighbours --
    # route.py says so ("boxed in by static obstacles ... not by congestion").  A board-global
    # 0.05 mm grid is ~6M cells a layer, so it is scoped to the failed nets only.
    # route.py writes its own relaxed floors back into its OUTPUT project ("FAB FLOOR RELAXED":
    # pass 2b left routed.kicad_pro at 0.15 mm clearance), and the next pass reads that as its
    # floor -- route11's pass 3 shipped 15 Default-class gaps of 0.15-0.198 mm that gen_pcb
    # refused.  So routed.kicad_pro is put back to sig_routed's (unrouted's floors plus the
    # protection map) before pass 3 reads it and again before the gates grade against it.
    def reset_routed_pro():
        for ext in (".kicad_pro", ".kicad_dru"):
            src = os.path.join(WORK, "sig_routed" + ext)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(WORK, "routed" + ext))
    reset_routed_pro()
    left = sorted(set(open_nets(SIG_SUMMARY)) | set(open_nets(SUMMARY)))
    if left:
        p3 = [py, "-u", route, ROUTED, FINE_OUT, "--nets"] + left
        p3 += ["--layers"] + list(G.SIGNAL_LAYERS) + cmd
        p3 += ["--grid-step", str(FINE_GRID), "--clearance", str(G.AR_CLEAR),
               "--track-width", str(FINE_W), "--json-out", FINE_SUMMARY]
        # The last pass may rip earlier router copper to close what is left: "*" covers every
        # unprotected net, and the quad nets are named exactly, which is what lifts their
        # pass-1b protection (route.py #521).  The SNS lines and every hand-routed net stay
        # protected -- they are never named.  route.py restores a ripped net it cannot re-route.
        p3 += ["--rip-existing-nets", "*"] + [n for n in early if n not in SNS_NETS]
        print("")
        print("=== pass 3: %d net(s) pass 2 left open, on the fine grid" % len(left))
        print("    " + " ".join(p3))
        rc = subprocess.call(p3, env=env)
        print("    exit %d" % rc)
        if rc:
            return rc
        shutil.copyfile(FINE_OUT, ROUTED)
        reset_routed_pro()
        print("    still open after pass 3: %s" % (", ".join(open_nets(FINE_SUMMARY)) or "none"))
    archive()

    # run() does subprocess.call and RETURNS rc -- it does not raise.  Until this block
    # accumulated, all seven results below were discarded and this function returned 0
    # unconditionally, so a router result that check_geometry graded as under the board's own
    # floors, or that check_grounds found had bridged GND to GND_IN, or that check_plane_width
    # found had pinched the 7 A plane below IPC-2221, was printed as a failure and then
    # reported as an overall success.  regenerate() tests `if rc:` at four sites; these seven
    # simply omitted it.  Collect, name, and fail.
    failed = []

    def gate(argv, title):
        if run(argv, title):
            failed.append(os.path.basename(argv[2]))

    # Geometry first, because it is the one that decides whether the rest is worth reading.
    # A board with copper under its own floors cannot be frozen however well it grades on
    # connectivity, and this is the check that catches the router quietly going below what it
    # was told -- see the --escalation comment above, and scripts/check_geometry.py.  All
    # seven still RUN even after one fails: the point of the chain is the whole report, and a
    # human folding a result back in wants every gate's answer, not just the first bad one.
    gate([sys.executable, "-u", os.path.join(HERE, "check_geometry.py"), ROUTED, "--freeze-drops"],
         "track and via geometry against the board's own floors (this repo)")
    # "?*" = every NAMED net: the no-net pads (mounting holes, the solder-wire footprints'
    # strain-relief pads) are "net 0", which is not a net and has nothing to connect.
    gate([py, "-u", os.path.join(home, "py_router", "check_connected.py"), ROUTED,
          "--nets", "?*"],
         "connectivity (KiCadRoutingTools)")
    if drc_gate([py, "-u", os.path.join(home, "py_router", "check_drc.py"), ROUTED],
                "clearances (KiCadRoutingTools)", os.path.join(WORK, "routed.kicad_dru")):
        failed.append("check_drc.py")
    if weird_gate([py, "-u", os.path.join(home, "py_router", "check_weird.py"), ROUTED],
                  "copper hygiene, dangling stubs included (KiCadRoutingTools)"):
        failed.append("check_weird.py")
    # With the input board as a baseline this grades gen_pcb's OWN vias and skips the
    # router's, which is the only way the thermal/stitching split means anything here -- and
    # it fails if the router handed back fewer than it was given.  See check_vias.py's BASE.
    gate([sys.executable, "-u", os.path.join(HERE, "check_vias.py"), ROUTED, UNROUTED],
         "via placement, gen_pcb's own vias only (this repo)")
    gate([sys.executable, "-u", os.path.join(HERE, "check_grounds.py"), ROUTED],
         "GND / GND_IN separation (this repo)")
    # Last, because it is the only check whose answer the ROUTER can make worse: every via
    # it placed punches another antipad through the VBAT plane, so the plane is narrower
    # after a run than the input board it was measured on.
    gate([sys.executable, "-u", os.path.join(HERE, "check_plane_width.py"), ROUTED],
         "power pour cross-sections against IPC-2152 (this repo)")
    gate([sys.executable, "-u", os.path.join(HERE, "check_power_paths.py"), ROUTED],
         "power paths, Kelvin sense, CAN pair (this repo)")

    print("")
    if failed:
        print("FAIL: %d of 8 post-route gate(s) failed: %s"
              % (len(failed), ", ".join(failed)))
        print("%s exists, but it is NOT a candidate to fold back into mccan.kicad_pcb." % ROUTED)
        return 1

    print("The routed board is %s." % ROUTED)
    print("It is NOT mccan.kicad_pcb, and it is not meant to be committed as one --")
    print("hardware/docs/routing-tool.md has how a good result gets folded back in.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
