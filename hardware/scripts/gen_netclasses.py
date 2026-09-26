# -*- coding: utf-8 -*-
"""Write layout_pcb.NETCLASSES and the DRC constraints into hardware/mccan.kicad_pro.

Net classes have lived in the PROJECT file, not the board, since KiCad v7 -- so they cannot
be emitted by gen_pcb.py along with everything else.  This keeps them generated all the same:
run it after gen_pcb.py and the two stay in step.

It also writes hardware/mccan.kicad_dru, the custom-rule file, from a scan of the board --
see write_dru() for why that exists.

The constraints are set for **1 oz (35 um) copper on all six layers**, decided 2026-09-22.
Spec 10 originally asked for 2 oz outer; it could not survive contact with the land patterns,
because 2 oz etching cannot hold the 0.15 mm pad-to-pad U10 needs or reliably the 0.20 mm the
QFN/VSON parts need, and outer copper is where every land pattern lives.  The inner layers
then ran at 2 oz until the board went to six: In2.Cu and In5.Cu carry tracks now (the two
inner entries of gen_pcb.SIGNAL_LAYERS; In4.Cu is the solid /VBAT plane, not a track layer --
fault 7, fix round 2), and PCBWay
etches inner layers to 4/4 mil at 1 oz but only 6/8 mil at 2 oz -- and 8 mil is 0.203 mm,
above the 0.20 mm clearance declared below.  The 7.0 A feed is unaffected either way; see
the measurement in scripts/check_plane_width.py.

    min track / clearance   0.20 mm   (standard 1 oz capability; at 2 oz this had to be 0.25)
    min via                 0.45 / 0.2 mm -- set by the 0.5 / 0.25 mm thermal vias that fill the
                            exposed paddles, not by routing, which uses 0.6 / 0.3 and 0.8 / 0.4
    min hole-to-hole        0.3 mm
    copper-to-edge          0.5 mm

Dropping the global minimum to 0.20 mm does more than buy routing room: it takes the whole
0.20 mm QFN/VSON population OUT of the land-pattern exception list below, because their
land patterns no longer violate anything.  Only genuinely tighter parts need a rule now.

Net class widths come from the current-carrying requirement, not from taste, and they changed
with the copper.  By IPC-2221 a 2.0 mm outer track carries 6.51 A at 2 oz but only 3.94 A at
1 oz (10 K rise), so the single POWER class no longer covered the feed:
    FEED   3.5 mm track  -- the 7.0 A input chain.  3.5 mm is a 20 K-rise floor for the short
                            hops between the input parts; POUR to >= 4.5 mm for 10 K on any
                            real run.  The through-path is the In3.Cu polygon, measured at
                            71 mm on its worst cut against the 11.44 mm 1 oz asks.
    POWER  2.0 mm track  -- what is left: VLOGIC_IN, +24V, +5V.  Largest load is the boost
                            output at 0.5 A (spec 6), against 3.94 A of capability.
    CAN    0.3 mm, tight pair, matched -- CANH/CANL are a differential pair.
"""

import io
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_pcb as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PRO = os.path.join(HW, "mccan.kicad_pro")
PCB = os.path.join(HW, "mccan.kicad_pcb")
DRU = os.path.join(HW, "mccan.kicad_dru")
NETLIST = os.path.join(HW, "output", "netlist.net")

RULES = {
    "min_clearance": 0.20,      # 1 oz outer copper -- see the module docstring
    "min_track_width": 0.20,
    # 0.50 and 0.15 are one decision, not two: PCBWay's published floor is a 0.15 mm annular
    # ring, and they state it for exactly this board's case -- "for pads with vias in the
    # middle", which is what all 73 thermal vias are.  With min_through_hole_diameter at 0.2
    # a 0.15 mm ring makes 0.50 mm the smallest via that can exist, so the two numbers have to
    # move together.  This is also the floor the EXTERNAL router escalates down to: it is run
    # with --escalation board, which permits anything the board declares, and while this said
    # 0.1 it was entitled to hand back 123 vias at 0.45/0.20 -- a 0.125 mm ring, under PCBWay
    # and quietly so, because it was legal by this file's own word.  See docs/routing-tool.md.
    "min_via_diameter": 0.50,   # thermal vias are 0.55/0.25 -- see gen_pcb.thermal_vias()
    "min_via_annular_width": 0.15,
    "min_through_hole_diameter": 0.2,   # U5 thermal-pad vias are 0.2 mm in the stock footprint
    "min_hole_to_hole": 0.3,
    "min_hole_clearance": 0.25,
    "min_copper_edge_clearance": 0.5,
    # Tied to min_track_width, and it has to be: min_connection is the narrowest copper that
    # may carry a connection, so setting it ABOVE the thinnest track the board permits makes
    # every legitimately necked track a violation of a rule the same file grants.  It read
    # 0.25 here against a 0.20 track floor while the project file on disk said 0.15, which is
    # how the inconsistency stayed invisible: nothing had regenerated the file since.
    "min_connection": 0.20,
    # Re-measured 2026-09-26 on the EIGHT-layer board with the router's copper frozen in
    # place, because the figures that used to stand here were the six-layer board's and named
    # zones (GND_BOT, VBAT_IN3) that either no longer carry a neck or no longer exist.  The
    # rule fires 15 times, and the 15 are two different things:
    #
    #   3 are REAL, all on F.Cu, all where a router track meets a pad or a via at 45 degrees
    #     across the pad's rounded corner and leaves a hairline isthmus:
    #       0.0589 mm  R101.2 /power_input/U10_DRN  (56.8425, 78.2300)
    #       0.0790 mm  Q10.1  /power_input/Q10_G    (26.2000, 104.1000)
    #       0.1346 mm  Q12.1  Net-(Q12-B)           (42.6000, 77.8000)
    #     Same defect class the six-layer note described ("a router via landing off the corner
    #     of Q10 and Q11's gate pads rather than into them"), and the same verdict: it wants
    #     fixing in the routing, not here.  Fixed there -- see layout_pcb.ROUTES' "necks at
    #     three router-to-pad junctions" section, which lays 0.5 mm hand copper over the first
    #     leg of each frozen run and takes all three junctions to >= 0.700 mm.
    #   12 are necks in the GND_IN1 / GND_IN3 / GND_IN6 plane pours, 0.1558 to 0.1845 mm:
    #     FOUR necks with identical geometry, repeated on three layers, because those three
    #     zones are plane-only (0 track segments between them, verified on the board -- every
    #     one of its 5119 segments is on F.Cu, B.Cu, In2.Cu or In5.Cu) and every one of the
    #     board's 1401 vias is a full F.Cu-B.Cu barrel, so all three planes see exactly the
    #     same antipad field.
    #
    # The obvious lever for the second group is the zones' own min_thickness, and it is not
    # the lever: raising it 0.3 -> 0.5 on a scratch copy of the six-layer board took the count
    # 12 -> 10 and removed none of the GND necks.  KiCad's filler and KiCad's connection_width
    # check are not measuring the same thing.
    #
    # Why the plane necks are accepted, re-argued for THIS board rather than carried over.  Two
    # earlier arguments are both unavailable and neither is repeated here:
    #
    #   * "the pour is not the return path" -- true of the six-layer board, where the necks were
    #     in B.Cu's shield pour.  Not true here: In1.Cu is a neck layer and it IS the reference
    #     plane for F.Cu.
    #   * "a neck between two antipads is not a series path, because the plane is a sheet and
    #     current spreads around the constriction through the parallel copper beside it."  This
    #     board refutes the premise that argument needs, namely that the check reports pinches.
    #     Measured directly against In1.Cu's antipad field -- every foreign full-barrel via,
    #     reach = radius + max(zone 0.3, netclass clearance), counting only pairs on DIFFERENT
    #     nets whose antipads do not already overlap into one void -- 74 gaps are NARROWER than
    #     0.1558 mm, the narrowest neck KiCad reports, and seven of those 74 are at exactly
    #     0.0000 mm, i.e. two antipads touching.  KiCad reports none of the 74.  It reports four
    #     widths, once per plane.
    #
    # connection_width is therefore not reporting every narrowing in these pours, and the rule
    # by which it picks four out of at least seventy-eight is NOT KNOWN HERE: KiCad's
    # implementation was not read, and nothing below infers it from the 4-against-74 ratio.  Do
    # not write down a story about which necks matter -- there is no evidence in this repo for
    # any such story, in either direction.
    #
    # What does carry the exception is measured.  First, stranding, three ways on this board:
    #
    #   * KiCad's isolated_copper: 0 violations, and gen_netclasses now writes it at `error`
    #     rather than `warning`, so it cannot fail quietly.
    #   * scripts/check_zone_islands.py: "no zone is unconnected to itself".
    #   * the unconnected-item count: exactly one GND item, U4.4, the pad gen_pcb warns about
    #     on every build for having no room for a drop at all.
    #
    # Second, and this is the part that makes a neck in ONE plane not a constriction of the NET:
    # inter-layer stitching.  GND carries 434 of the board's 1401 vias and every one of the 1401
    # is a full F.Cu-B.Cu barrel, so each of the four GND pours is tied to the other three at
    # 434 points.  A reported neck constricts one of four parallel sheets that are shorted
    # together 434 times over; it does not constrict GND.  That is a claim about the net, and it
    # is the only claim made here.  It says nothing about local return-current density under an
    # F.Cu trace that crosses such a neck, which is a loop-area question none of these checks
    # was asked -- which is the other reason the number below is not set at the vendor floor.
    #
    # What is left to ask of a plane neck is whether it ETCHES.  The vendor floor is PCBWay's
    # inner-layer minimum at 1 oz, 4 mil = 0.1016 mm (see the module docstring, which picked
    # 1 oz inners on that figure) -- but the scoped exception in mccan.kicad_dru is deliberately
    # NOT set there.  It is set at 0.15 mm: 1.47x the floor, and only 0.0058 mm under today's
    # narrowest neck, so the rule stays a TRIPWIRE.  Any tightening of the via field brings it
    # straight back and someone has to look.  At the 0.10 mm it used to hold, a 0.11 mm sole
    # in-plane tie could appear in F.Cu's reference plane with both DRC severities green: 0.056
    # mm of silent headroom, which is not what a scoped exception is for.
    #
    # Measured margin, so a future reader can see what the exception spends.  Sweeping the
    # scoped minimum on this board: 0.15 and 0.16 mm pass all twelve, 0.17 mm fails three,
    # 0.20 mm fails all twelve, 0.24 mm fails eighteen.  The 0.0058 mm at 0.15 is not eaten by
    # zone-refill jitter: two consecutive `--refill-zones` DRC runs report the same four widths,
    # 0.1558 / 0.1652 / 0.1671 / 0.1845 mm, identical at the report's 0.0001 mm resolution.
    #
    # Scoped by zone NAME and by A.Type == 'Zone', which is what keeps it from masking the F.Cu
    # kind above: those are Pad+Track and Track+Via findings and this rule is not eligible to
    # grade them.  Note what the scope does NOT do: because KiCad reports every zone neck as a
    # single Zone item with no partner, the rule cannot tell a neck in open pour from a neck
    # that is the sole copper tying some via or pad into the plane.  No such case exists below
    # 0.20 mm today.
    "min_silk_clearance": 0.0,
}

# --- rule severities, because a rule at `warning` is a rule the gate cannot report
#
# The DRC gate this repo runs is
#
#   kicad-cli pcb drc --severity-error --schematic-parity --exit-code-violations --refill-zones
#
# and `--severity-error` discards every finding whose rule is set to `warning`.  KiCad's stock
# project file sets 29 of its 62 rules to warning or ignore, and nothing here had ever touched
# them -- so on the committed board that gate reported `Found 0 violations` while
# `--severity-all` reported **28**: 15 connection_width and 13 via_dangling.  Every "DRC: 0
# errors" recorded on this branch was measured through that filter.
#
# Promoted here, with the reason each one is an error on THIS board and not a style note:
#
#   connection_width   the narrowest copper that may carry a connection, min_connection above.
#                      A 0.059 mm neck where a router track meets a gate or drain pad does not
#                      survive etching; that is an open gate on the eFuse, not a cosmetic
#                      finding.  15 of these were hidden.
#   hole_to_hole       min_hole_to_hole above, i.e. whether the fab can drill the board.  See
#                      the note in gen_pcb.check_via_holes for why this one was believed not to
#                      cover same-net pairs and does.
#   holes_co_located   two drills at the same point is a drill file the fab has to query.
#   via_dangling       a via connected on one layer or none.  Legal copper, but every one is
#                      counted in the via-in-pad population docs/fabrication.md tells the fab
#                      to plug and cap, so each buys a chargeable process step for nothing.
#                      13 were hidden.
#   track_dangling     a track that reaches nothing is either a missing connection or copper
#                      nobody meant to lay.
#   isolated_copper    the other half of the pour argument below: the whole case for leaving a
#                      zone neck alone is that it strands nothing, and this is the rule that
#                      would say otherwise.  It cannot be allowed to say it at warning.
#   copper_sliver      an etch-resolution defect, i.e. a fabrication question and not taste.
#
# Five of the seven report ZERO on this board, so promoting them costs nothing today and is
# purely about what the next change cannot do quietly.  What is deliberately left at `warning`
# is the silk/text/library-metadata group (silk_overlap, text_height, lib_footprint_issues,
# missing_footprint and the like): those are drawing-office findings, none of them decides
# whether the board works or can be built, and several fire on every clone because the
# footprint library is not registered in the runner's KiCad configuration.  `padstack` is left
# alone as well -- it reports 0 here, and every via on the board is graded for diameter, drill
# and annular ring by scripts/check_geometry.py, which gates rather than warns.
#
# None of this makes `--severity-error` sufficient on its own.  Run BOTH severities: the
# promoted rules are the ones that can fail a board, and the residue is still worth reading.
SEVERITIES = {
    "connection_width": "error",
    "copper_sliver": "error",
    "hole_to_hole": "error",
    "holes_co_located": "error",
    "isolated_copper": "error",
    "track_dangling": "error",
    "via_dangling": "error",
}

# The tightest land pattern on the board is U10's at 0.15 mm; the VSON/QFN/HSOF parts are at
# 0.20 mm.  0.12 keeps a margin under the worst of them, so a part fractionally tighter than
# its neighbours does not need a hand-written exception -- and, more importantly, so that the
# rule cannot pass by exactly equalling the gap it is meant to permit.
#
# Note the exception list SHRANK when the board went to 1 oz outer copper and the global
# minimum fell from 0.25 to 0.20 mm: a 0.20 mm land pattern is now legal on its own terms.
# What survives is the parts whose paddle sits on a FEED or POWER net, because those classes
# still ask for 0.30 mm -- the exception is now about netclass clearance, not fabrication.
DRU_MIN = 0.12

# The plane-pour connection_width exception.  The whole argument is in the min_connection note
# above; this is only the number and its scope.
#
# 0.15 mm, and NOT the vendor floor.  PCBWay's published inner-layer minimum at 1 oz is 4 mil =
# 0.1016 mm -- the figure the module docstring used to choose 1 oz inners -- and this value sits
# 1.47x above it deliberately.  Setting a waiver at the fabrication floor turns it into a
# blanket: the narrowest neck on this board is 0.1558 mm, so 0.10 mm would have admitted, with
# both DRC severities green, anything down to a 0.11 mm sole in-plane tie in F.Cu's reference
# plane.  0.15 mm leaves 0.0058 mm instead of 0.056 mm, so the rule still fires the moment the
# via field tightens at all.
#
# The sweep that shows it is live rather than disabled, re-run on this board: 0.15 and 0.16 mm
# pass all twelve, 0.17 mm fails three, 0.20 mm fails all twelve, 0.24 mm fails eighteen.  The
# 0.0058 mm is real margin and not measurement noise -- two consecutive `--refill-zones` DRC
# runs report the same four widths to the report's last digit.
#
# Scoped by zone NAME and by A.Type == 'Zone', so it can only GRADE a zone item.  That is what
# keeps it from masking the Q10/Q11 kind the min_connection note describes: those are
# pad-and-track findings on F.Cu, and this rule is not eligible to see them.  Verified rather
# than assumed -- with this rule in place the three F.Cu necks were still reported, at 0.0589,
# 0.0790 and 0.1346 mm, until they were fixed in layout_pcb.ROUTES.
PLANE_ZONES = ("GND_IN1", "GND_IN3", "GND_IN6")
PLANE_MIN = 0.15

DRU_HEAD = """(version 1)

# GENERATED by scripts/gen_netclasses.py -- do not edit.
#
# Vendor land patterns.  A clearance constraint governs what the LAYOUT may do; it has no
# business policing the gap between a part's own pads, which is fixed by the manufacturer's
# recommended footprint and is identical on every board that uses the part.  The exposed
# thermal pad of a VSON/QFN/HSOF sits 0.20 mm from its neighbouring signal pads, and U10's
# land pattern is tighter still at 0.15 mm -- both under this board's 0.25 mm global minimum
# and under the POWER class's 0.30 mm.  No edit to this board can change that; the only real
# choices are to use the part or not to use it.
#
# Suppressing the check is therefore correct, but it is NOT free: it moves the requirement out
# of DRC and into the fab notes.  Each ref below is listed with the gap it actually needs --
# down to 0.15 mm -- and the board is no easier to build than its tightest entry.  The
# assembler likewise needs a stencil and reflow profile that will not bridge an exposed
# thermal pad to the pin 0.15-0.20 mm away.  Say so on the fab drawing.
#
# The list comes from scanning the generated board for intra-footprint pad pairs on DIFFERENT
# nets closer than the clearance being applied, so it cannot drift out of step with the
# schematic.  A rule keyed on a ref that no longer exists would be silently dead; a part that
# newly needs one appears here on the next run.
#
# The condition has to name each ref.  A.memberOfFootprint('U1') works; the tempting
# A.memberOfFootprint(B) parses, never matches, and fails open with no error at all.
"""

PLANE_RULE = """# Ground-plane pour necks, %s only.
#
# min_connection is 0.2000 mm and these pours hold four necks -- 0.1558, 0.1652, 0.1671 and
# 0.1845 mm -- reported identically on all three layers because those zones are plane-only (no
# track segment on any of them; all 5119 segments are on F.Cu, B.Cu, In2.Cu or In5.Cu) and all
# 1401 vias are full F.Cu-B.Cu barrels, so the three planes see exactly the same antipad field.
#
# Read scripts/gen_netclasses.py's min_connection note before changing this.  Two things it says
# matter here, and the second is the one earlier versions of this comment got wrong:
#
#   1. This rule is NOT justified by any claim about which necks are series paths.  KiCad's
#      connection_width reports FOUR necks in these pours, while an independent scan of In1.Cu's
#      antipad field finds 74 foreign-net gaps NARROWER than the 0.1558 mm it reports -- seven of
#      them at exactly 0.0000 mm, two antipads touching -- and reports none of those 74.  So the
#      check does not report every pinch, and the rule by which it selects four out of at least
#      seventy-eight is unknown: KiCad's implementation was not read.  Any comment here that
#      explains which necks matter is guessing.
#   2. What justifies it is stranding and stitching, both measured.  Stranding: 0
#      isolated_copper (promoted to `error`, not `warning`), scripts/check_zone_islands.py
#      reports no zone unconnected to itself, and the only unconnected GND item on the board is
#      U4.4 -- the one pad gen_pcb warns has no room for a drop at all.  Stitching: GND carries
#      434 of the 1401 vias and every one is a full F.Cu-B.Cu barrel, so each of the four GND
#      pours is tied to the other three at 434 points.  A neck narrows one of four sheets that
#      are shorted together 434 times; it does not narrow the net.
#
# What remains to ask of a plane neck is whether it ETCHES -- and this is set ABOVE the vendor
# floor, not at it.  PCBWay's inner-layer minimum at 1 oz is 4 mil = 0.1016 mm (the figure that
# chose 1 oz inners in scripts/gen_netclasses.py's module docstring); %.2f mm is 1.47x that and
# 0.0058 mm below the narrowest neck here, so the rule remains a tripwire that any tightening of
# the via field trips, rather than a blanket admitting anything the fab can etch.  The sweep:
# 0.15 and 0.16 mm pass all twelve, 0.17 mm fails three, 0.20 mm fails all twelve, 0.24 mm fails
# eighteen.  Two consecutive `--refill-zones` runs report the same four widths to 0.0001 mm, so
# that 0.0058 mm is margin and not refill noise.
#
# Scoped to these zones by name and to A.Type == 'Zone', deliberately: a global relaxation
# would also stop this rule catching a router track meeting a pad across its rounded corner,
# which is what it caught on F.Cu at U10_DRN, Q10_G and Net-(Q12-B).  The scope bounds what the
# rule GRADES, not what it can excuse -- KiCad reports every zone neck as a lone Zone item, so
# this rule cannot distinguish open-pour copper from copper that is some via's only tie into the
# plane.  Nothing on this board is in the latter shape below 0.20 mm.
(rule "ground plane pour necks"
\t(constraint connection_width (min %smm))
\t(condition "A.Type == 'Zone' && (%s)"))
"""


def net_names():
    t = io.open(NETLIST, encoding="utf-8").read()
    return re.findall(r'\(name "([^"]*)"\)', t[t.index("(nets"):])


def resolve(short, names):
    """A short net name from layout_pcb -> the hierarchical name the netlist actually uses."""
    hits = [n for n in names if n == short or n.rsplit("/", 1)[-1] == short]
    return hits


def refkey(ref):
    return (re.sub(r"\d", "", ref), int(re.sub(r"\D", "", ref) or 0))


PAD_RE = re.compile(
    r'\(pad "([^"]*)" \w+ [\w_]+\s*\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)\s*'
    r'\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)', re.S)
FP_AT_RE = re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)')


def scan_tight_footprints(clearance):
    """Refs whose OWN pads sit closer together than the clearance that would be applied.

    `clearance(net)` gives the applicable clearance for a net; a pair is judged against the
    larger of its two.

    Pad positions in a .kicad_pcb are footprint-LOCAL, so every pad of one footprint shares a
    frame and the positions compare directly.  Pad ROTATION, though, is stored ABSOLUTE -- it
    already includes the footprint's own rotation -- so the angle that orients a pad's (size)
    within the local frame is (pad rotation - footprint rotation).  Ignoring that reads
    U5's 0.9 x 1.5 mm castellations as 1.5 x 0.9 and reports its 1.27 mm pitch as an overlap.

    Gaps are measured between axis-aligned bounding boxes: exact for the rectangular and
    roundrect pads this matters for, pessimistic -- i.e. safe -- for ovals and circles.
    """
    t = io.open(PCB, encoding="utf-8").read()
    out = {}
    for blk in t.split("\n\t(footprint ")[1:]:
        m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        if not m:
            continue
        fm = FP_AT_RE.search(blk)
        frot = float(fm.group(3) or 0.0) if fm else 0.0
        pads = []
        for pm in PAD_RE.finditer(blk):
            nm = re.search(r'\(net \d+ "([^"]*)"\)', pm.group(7))
            if not pm.group(1) or nm is None:
                continue   # unnumbered paste apertures sit ON the thermal pad; not a pair
            x, y = float(pm.group(2)), float(pm.group(3))
            w, h = float(pm.group(5)), float(pm.group(6))
            th = math.radians(float(pm.group(4) or 0.0) - frot)
            c, s = abs(math.cos(th)), abs(math.sin(th))
            pads.append((x, y, w * c + h * s, w * s + h * c, nm.group(1)))
        worst = None
        for i in range(len(pads)):
            for j in range(i + 1, len(pads)):
                a, b = pads[i], pads[j]
                if a[4] == b[4]:
                    continue
                dx = abs(a[0] - b[0]) - (a[2] + b[2]) / 2
                dy = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
                gap = math.hypot(max(dx, 0.0), max(dy, 0.0))
                need = max(clearance(a[4]), clearance(b[4]))
                if gap < need - 1e-6 and (worst is None or gap < worst):
                    worst = gap
        if worst is not None:
            out[m.group(1)] = worst
    return out


def write_dru(clearance):
    tight = scan_tight_footprints(clearance)
    parts = [DRU_HEAD.format(min=DRU_MIN)]
    parts.append(PLANE_RULE % (" / ".join(PLANE_ZONES), PLANE_MIN, "%.2f" % PLANE_MIN,
                               " || ".join("A.Name == '%s'" % z for z in PLANE_ZONES)))
    for ref in sorted(tight, key=refkey):
        parts.append(
            '# %s needs %.3f mm pad-to-pad\n'
            '(rule "land pattern %s"\n'
            '\t(constraint clearance (min %smm))\n'
            '\t(condition "A.memberOfFootprint(\'%s\')"))\n'
            % (ref, tight[ref], ref, DRU_MIN, ref))
    io.open(DRU, "w", encoding="utf-8", newline="\n").write("\n".join(parts))
    return tight


def main():
    pro = json.load(io.open(PRO, encoding="utf-8"))
    names = net_names()

    base = pro["net_settings"]["classes"][0]
    classes = [base]
    patterns = []
    unknown = []

    for name, tw, cl, vd, vdr, nets in L.NETCLASSES:
        c = dict(base)
        c.update({"name": name, "track_width": tw, "clearance": cl,
                  "via_diameter": vd, "via_drill": vdr, "priority": len(classes)})
        if name == "CAN":
            c.update({"diff_pair_width": 0.3, "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25})
        classes.append(c)
        for short in nets:
            hits = resolve(short, names)
            if not hits:
                unknown.append(short)
            for h in hits:
                patterns.append({"netclass": name, "pattern": h})

    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = patterns
    pro["board"]["design_settings"]["rules"].update(RULES)
    pro["board"]["design_settings"].setdefault("rule_severities", {}).update(SEVERITIES)
    pro["board"]["design_settings"]["track_widths"] = [0.0, 0.25, 0.4, 0.8, 2.0]
    pro["board"]["design_settings"]["via_dimensions"] = [
        {"diameter": 0.0, "drill": 0.0},
        {"diameter": 0.6, "drill": 0.3},
        {"diameter": 0.8, "drill": 0.4},
    ]

    io.open(PRO, "w", encoding="utf-8", newline="\n").write(
        json.dumps(pro, indent=2, ensure_ascii=False) + "\n")

    print("classes: %s" % ", ".join(c["name"] for c in classes))
    print("rule severities raised to error: %s" % ", ".join(sorted(SEVERITIES)))
    print("patterns: %d" % len(patterns))
    for p in patterns:
        print("    %-6s %s" % (p["netclass"], p["pattern"]))
    if unknown:
        print("  WARN: no net matches %s" % ", ".join(sorted(set(unknown))))

    # A pad pair is judged against the clearance KiCad would actually apply to it: the
    # netclass of each net, defaulting to the board minimum.
    by_net = {}
    for p in patterns:
        by_net[p["pattern"]] = next(
            c["clearance"] for c in classes if c["name"] == p["netclass"])

    def clearance(net):
        return by_net.get(net, RULES["min_clearance"])

    tight = write_dru(clearance)
    print("land-pattern rules (a part's own pads closer than its nets' clearance): %d"
          % len(tight))
    for ref in sorted(tight, key=refkey):
        print("    %-5s %.3f mm" % (ref, tight[ref]))


if __name__ == "__main__":
    main()
