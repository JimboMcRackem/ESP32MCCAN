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
    # Measured 2026-09-22, because this is the rule that will decide whether Task 9 step 6's
    # "zero warnings" gate is reachable.  It fires 12 times on the routed board and the 12
    # are two different things:
    #
    #   2 are REAL -- a router via landing off the corner of Q10 and Q11's gate pads rather
    #     than into them, so the two coppers overlap by 0.08 mm.  That is exactly what this
    #     rule is for and it wants fixing in the routing, not here.
    #   10 are necks inside the GND_BOT and VBAT_IN3 POURS, 0.01 to 0.19 mm, where the fill
    #     squeezes between two antipads.
    #
    # The obvious lever for the second group is the zones' own min_thickness, and it is not
    # the lever: raising it 0.3 -> 0.5 on a scratch copy took the count 12 -> 10, removing
    # both VBAT_IN3 necks and none of GND_BOT's eight.  KiCad's filler and KiCad's
    # connection_width check are not measuring the same thing.
    #
    # What makes the pour necks benign is not their width, it is that the pour is not the
    # path.  Return current runs on In1.Cu, which is solid and unbroken, and every SMD GND
    # pad has its own drop via into it -- B.Cu's GND is a shield and a thermal pour, not a
    # conductor of anything.  The same argument holds for VBAT_IN3, whose feed
    # scripts/check_plane_width.py measures at 71 mm.  And KiCad agrees the necks strand
    # nothing: it reports no isolated-copper violation and no unconnected GND item.
    # So the resolution is a scoped exception in mccan.kicad_dru for those two pours only,
    # written once the routing is final -- not a global relaxation, which would also stop
    # this rule catching the Q10/Q11 kind.
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
