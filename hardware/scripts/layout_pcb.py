# -*- coding: utf-8 -*-
"""Board outline, regions and placement for mccan.kicad_pcb (plan Task 8).

Same rule as the schematic sheets: **the board is generated, never hand-edited in pcbnew.**
Edit this module and re-run `python scripts/gen_pcb.py`.

--------------------------------------------------------------------------- THE BOARD SIZE
140 x 100 mm, decided here and not guessed. The parts' own courtyards, summed from the
footprint library, come to **68.3 cm2** across 231 placed parts. **20.1 cm2 of that is U5's
courtyard alone**, which is mostly the ESP32's antenna keep-out and hangs off the board edge,
so the real on-board demand is about **57 cm2**. Single-sided SMD assembly at a realistic 50%
packing therefore wants ~114 cm2, and the power polygons want width on top of that.

**140 x 100 = 140 cm2.** It also sits sensibly against the >= 150 cm2 heat-spreader plate
(spec 9.4) rather than fighting it, and `hardware/docs/enclosure.md` carries 100 x 80 mm as
**[PROVISIONAL] pending Task 8** -- this module is what that entry was waiting for.

**Assembly is SINGLE SIDED (F.Cu).** Nothing is placed on B.Cu. At this volume a second
assembly side costs more than the board area it saves, and B.Cu is wanted whole for routing.

------------------------------------------------------------------------- THE FOUR EDGES
Three spec constraints fix the orientation between them, and only one arrangement holds:

  * enclosure 1 -- the heat-spreader plate is the **BASE**, the face under the board, with the
    **antenna corner notched out**.  Decided 2026-09-20; it supersedes spec 9.1's "wall opposite
    the panel" and the earlier reading of enclosure 2.3 as "the wall opposite the antenna".
    The gap pad contacts **B.Cu**, so the plate has to be parallel to the board, not an edge
    wall -- which is also why the thermal group is not pushed against any one edge.
  * plan Task 8 Step 4 -- the module overhangs the board edge (Espressif's own first choice),
    and the plate is notched clear of the keep-out rather than routed around it in plan.
  * plan Task 8 Step 5 / enclosure 4 -- the wire-exit pads are on **one** edge.

        BASE (B.Cu) = the plate face. Thermal group anywhere over it, coupled by vias.
        LEFT edge  = free; historically called "the plate edge", which it no longer is.
        RIGHT edge = the antenna edge. U5 overhangs it; keep-out on all six layers,
                     and the base plate is NOTCHED so no metal enters it either.
        BOTTOM edge = the wire-exit edge. Power at the far left, CAN at the far right,
                      which is also plan Task 8's "CAN separated from the power feed".
        TOP edge   = free.

Note the connectors themselves are **panel mount**; what is on the board is
`Connector_Wire:SolderWire-*_Relief` solder pads. The board's "connector edge" is a wire-exit
field, not an abutting row of housings, which is why the widths below add up.

--------------------------------------------------------------------------- THE THERMAL GROUP
Amended 2026-09-20 after spec 4.2's rewrite. **L2, U9, L1, U3, L3** -- about 1.6 W of the
2.31 W night total. There are no external boost FETs (the LM51571-Q1 integrates its switch) and
there is no P-FET (4.2's pass pair dissipates 0.12 W between them).

**L2 is placed first and everything else gives way to it**: largest single term at 0.78 W,
tallest part at ~24 mm, through-hole on an otherwise-SMD board, and 23.0 x 17.0 mm in plane.

**R100 is deliberately NOT in the thermal group.** It dissipates 0.27 W but spec 4.2 requires
its own copper and a Kelvin tap -- the copper around it is part of the *measurement*, so it goes
in the eFuse island next to U10, and it gets no thermal vias down to the plate.
"""

# ------------------------------------------------------------------ board outline
X0, Y0 = 20.0, 20.0
X1, Y1 = 160.0, 120.0
EDGE_R = 3.0          # corner radius, drawn as four arcs
MOUNT_INSET = 5.0     # M3 mounting holes, centre inset from each corner
MOUNT_DRILL = 3.2
MOUNT_PAD = 6.0

# ------------------------------------------------------------------ antenna keep-out
# ESP32-WROOM-32E datasheet v1.8, Figure 12: the Antenna Area is 18.0 mm wide x 6.19 mm deep,
# measured from the module's end face and spanning the full module width. U5 is rotated so the
# antenna points right, overhanging X1 entirely -- so this rectangle is mostly off the board and
# is drawn as a keep-out for the part of it that is not.
ANT_W, ANT_D = 18.0, 6.19

# ------------------------------------------------------------------ regions
# (x0, y0, x1, y1) in board coordinates.  Parts not named in PLACE are auto-flowed into their
# block's region on a courtyard-sized grid, in reference order.
#
# The left band runs the 7 A feed in ONE direction only -- J1 at the bottom, up through the
# eFuse, up through L2 and the pi filter, out of the top right of "input".  Nothing doubles back.
REGIONS = {
    "input":   (23.0,  23.0,  62.0,  52.0),   # D2, L2, R2/R3, C1-C4, L1, D3, C5
    "efuse":   (23.0,  54.0,  62.0,  94.0),   # U10, Q10, Q11, R100, C65 and the gate network
    # The output block is by far the biggest -- 105 auto-flowed parts -- and at the original
    # 102..131 it packed them to 59 % courtyard fill, which is about twice what a two-layer
    # escape can be routed through: the autorouter left 60 nets unrouted and the occupancy
    # map showed 13..28 % free copper per 10 mm tile across the whole block, against 85..100 %
    # over the empty left half of the board.  So the block is given the 95..102 column as
    # well, and the rails block takes the southern half of its own column back from profet
    # (which holds no auto-flowed parts at all -- U9 is placed by hand) to pay for it.
    "boost":   (64.0,  23.0,  93.0,  48.0),   # U3, L3, D4, C61 and their passives
    "rails":   (64.0,  50.0,  93.0,  94.0),   # U1 buck, U2 5 V, U4, decoupling
    "profet":  (64.0,  82.0,  93.0,  94.0),   # U9 and its passives, inside the rails column
    "outputs": (95.0,  23.0, 131.0,  94.0),   # 12 RGB channels, U7, U8, F2-F5
    "mcu":     (133.0, 23.0, 158.0,  46.0),   # U6 and the CAN front end, above U5's courtyard
    "wire":    (23.0,  95.0, 158.0, 119.0),   # the wire-exit field
}

# Which region each sheet's leftovers flow into.  Parts whose block differs from their sheet
# are pinned by name in BLOCK below.
SHEET_REGION = {
    "power_input": "input",
    "rails":       "rails",
    "outputs":     "outputs",
    "mcu_can":     "mcu",
}

# Overrides: ref -> region, for parts whose sheet is not where they belong on the board.
BLOCK = {}
for _r in ("U10", "Q10", "Q11", "Q12", "R100", "R101", "R102", "R103", "R104", "R105",
           "R106", "R107", "C62", "C63", "C64", "C65", "D21", "D22", "D23",
           # D2 and R3 belong to the GND_IN side, not to the input filter their sheet puts
           # them on.  D2 is the TVS from VBAT_PROT to GND_IN and R3 is the single resistor
           # that ties GND_IN to GND; both reference the INPUT ground, so they have to sit in
           # the GND_IN column with U10 and J1.  Left in the input region they land above the
           # choke, on the far side of the very boundary they define, and the F.Cu GND_IN
           # island then cannot reach them without swallowing the post-choke filter.
           "D2", "R3"):
    BLOCK[_r] = "efuse"
# The whole boost, not just its four big parts.  U3's support network was on the `rails`
# SHEET, so SHEET_REGION flowed all of it into the rails REGION -- and the region comment above
# said "U3, L3, D4, C61 and their passives" while BLOCK pinned only the four.  The result was a
# controller at y 30 with every one of its own components at y 62..71: COMP 35 mm from pin 8,
# SS 33 mm from pin 10, the FB divider 37 mm from pin 9, and the VCC and BIAS bypasses 40 mm
# from the pins they bypass.  COMP is the error amplifier's output and the highest-impedance
# node in the converter; a 35 mm trace to its compensation network runs beside the switch node
# and is how a boost oscillates.  C18/C19 are the INPUT capacitors and C20/C21/C22 the OUTPUT
# capacitors, and both pairs were ~35 mm from the parts they decouple, which makes a nonsense
# of "switch-node loop area minimised".
#
# This is placement, not routing, but it is the precondition for plan Task 9 Step 1: there is
# no good route for a 35 mm COMP trace, so the routing step cannot be done until the parts
# are where they belong.
for _r in ("U3", "L3", "D4", "C61",
           "C18", "C19",                      # VBAT input caps
           "C20", "C21", "C22",               # +24V output caps -- the commutation loop
           "C23", "C24", "R14",               # COMP network
           "C25",                             # soft start
           "C26", "R15",                      # VCC: 5.1R + 1uF, datasheet 9.3.2
           "C27", "R16",                      # BIAS: 0R from VBAT + 100nF
           "R10", "R11",                      # RT, MODE
           "R12", "R13",                      # FB divider
           "R20"):                            # EN pulldown
    BLOCK[_r] = "boost"
for _r in ("U9",):
    BLOCK[_r] = "profet"
for _r in ("J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8"):
    BLOCK[_r] = "wire"

# ------------------------------------------------------------------ hand placement
# ref -> (x, y, rotation).  Everything here is placed for a reason; everything else is flowed.
PLACE = {
    # -- the wire-exit field, left to right, laid end to end from the real courtyards.
    #    These footprints put their ORIGIN ON PAD 1, not on the centroid, so the numbers below
    #    are not the boxes: the box each one occupies is in the trailing comment.  J1 and J2
    #    sit at opposite ends, which is plan Task 8's "high-current separated from CAN"
    #    expressed as a distance.  J3-J6 stay adjacent, as enclosure.md section 4 requires.
    #    The wire-exit row is pitched to fit BETWEEN the two lower mounting holes.  H3 and H4
    #    are at x 25 and 155 with a 6 mm pad, so their courtyards own x 21.75..28.25 and
    #    151.75..158.25 at connector height -- leaving 123.0 mm of usable row.  The eight
    #    courtyards total 114.34 mm, so the gaps are 1.2 mm, not the 2.0 mm used elsewhere.
    #    These are courtyards, which already carry their own clearance, and nothing is routed
    #    between them: the row is pads and wire, so 1.2 mm is a real gap, not a shaved one.
    "J1":  (30.85, 97.91, 0),    # box x  28.60.. 45.10  y 95.84..118.16
    "J7":  (48.55, 97.91, 0),    # box x  46.30.. 62.80  y 95.84..118.16
    "J8":  (65.80, 100.59, 0),   # box x  64.00.. 72.20  y 99.01..114.99
    "J3":  (75.20, 100.59, 0),   # box x  73.40.. 90.80  y 99.01..114.99
    "J4":  (93.80, 100.59, 0),   # box x  92.00..109.40  y 99.01..114.99
    "J5":  (112.40, 100.59, 0),  # box x 110.60..128.00  y 99.01..114.99
    "J6":  (131.00, 100.59, 0),  # box x 129.20..146.60  y 99.01..114.99
    "J2":  (149.57, 100.65, 0),  # box x 147.80..151.34  y 98.88..115.12

    # -- the input filter.  Current arrives from the eFuse below and leaves at the top right.
    #    L2's origin is on pad 1 and sits +3.75, -5.03 off its box centre, so (37.25, 38.0)
    #    puts the box at x 28.50..53.50, y 23.15..42.80 -- clear of H1's pad at x 25, y 25.
    "L2":  (37.25, 38.0, 0),     # CM choke: placed FIRST. 25.0 x 19.65 mm, ~24 mm tall, THT
    "L1":  (31.0, 50.0, 0),      # pi-filter inductor, 0.28 W
    "C3":  (46.0, 50.0, 0),      # 220 uF bulk, at L1's output

    # -- the eFuse island.  Bottom row is nearest J1, so the 7 A path runs strictly upward:
    #    J1 -> Q10 -> Q11 -> R100 -> up to U10 and C65 -> out of the top into L2.
    "Q10": (31.0, 87.0, 0),
    "Q11": (46.0, 87.0, 0),
    "R100": (57.0, 87.0, 90),    # own copper, Kelvin tap -- see KEEPCLEAR
    "U10": (39.0, 74.0, 0),
    "C65": (54.0, 76.0, 0),      # at U10 pin 5, not merely on the net

    # -- the boost.  Laid out around U3's pinout rather than as a row, because the pinout is
    #    what decides where each network can go: SW on the RIGHT and TOP edges (pins 12, 13,
    #    14), VCC/BIAS on the LEFT (2, 3), RT/EN/COMP on the BOTTOM (5, 6, 8), FB/SS/MODE on
    #    the RIGHT (9, 10, 11).  So the power parts go above and right, the bias network left,
    #    the control network below and right, and nothing has to cross the switch node.
    #
    #    The commutation loop -- C20/21/22 -> D4 -> SW -> U3's internal FET -> GND -- is the
    #    one with the high di/dt, and it is the one this arrangement minimises: the output
    #    caps sit against D4's cathode tab, D4's anode is 2.3 mm from U3 pin 14, and the
    #    return is the In1.Cu ground plane one dielectric away rather than a trace.
    #
    #    VBAT does NOT need to reach L3 as a track.  In2.Cu is a VBAT plane end to end now, so
    #    L3 pad 1 and C18/C19 reach it with a via each, which is why L3 can sit on the far side
    #    of U3 from the input without a 20 mm run to get there.
    "U3":  (74.0, 32.0, 0),      # LM51571-Q1
    "D4":  (75.3, 25.6, 180),    # catch diode, tab up, anode down at U3's SW pins 13/14
    "L3":  (81.0, 28.6, 180),    # boost inductor, SW pad facing U3
    "C20": (69.9, 23.6, 180),    # +24V output caps, a 1206 column against D4's cathode tab:
    "C21": (69.9, 26.0, 180),    # +24V pad inboard at the tab, GND pad outboard where the
    "C22": (69.9, 28.4, 180),    # drop vias reach the plane.  This is the commutation loop.
    "C18": (86.2, 28.6, 0),      # VBAT input caps at L3 pad 1; VBAT arrives from the In2.Cu
    "C19": (86.2, 32.2, 0),      # plane underneath, by via, not by a track across the board
    # right of U3: FB (pin 9), the highest-impedance node after COMP, as a short vertical rail
    "R12": (79.0, 32.2, 180),    # FB divider top, 576k -- FB pad faces U3
    "C61": (79.0, 34.0, 180),    # feedforward across R12 (DNP)
    "R13": (79.0, 35.8, 0),      # FB divider bottom, 24.9k -- GND pad outboard
    # below U3: COMP (pin 8), RT (5), EN (6) all live on the bottom edge
    "R14": (74.0, 35.4, 180),    # COMP series 2.61k, straight down from pin 8
    "C23": (74.0, 37.2, 0),      # COMP series 10nF, straight down from R14
    "C24": (76.55, 35.8, 270),   # COMP parallel 100pF
    "R10": (70.6, 36.4, 180),    # RT 9.09k
    "R20": (70.6, 38.2, 180),    # EN pulldown 100k
    # left of U3: VCC (pin 2) and BIAS (pin 3) and their bypasses, off the switch node entirely
    "R15": (70.0, 30.6, 180),    # VCC 5.1R
    "C26": (66.6, 30.6, 180),    # VCC 1uF
    "R16": (70.0, 32.4, 0),      # BIAS 0R from VBAT -- VBAT pad outboard, to the plane
    "C27": (70.0, 34.2, 180),    # BIAS 100nF
    "R11": (74.0, 39.0, 180),    # MODE 37.4k -- a static level, so it takes the long stub
    "C25": (77.3, 39.0, 0),    # soft start 22nF -- a slow ramp, likewise
    "U9":  (76.0, 88.0, 0),      # PROFET, the shortest run to J7's Denali pads

    # -- the antenna edge.  Rotated 270 so the antenna points +X (verified against the
    #    footprint: its keep-out sits at local -Y, and 270 maps -Y to +X).
    #    The module END FACE is flush with X1 = 160: not cantilevered off the edge, but with
    #    the whole of the footprint's own all-layer keep-out zone left bare.
    #
    #    U5 sits LOW, not centred on the right edge, and that costs real estate on purpose.
    #    The stock footprint's courtyard is 48.5 x 41.5 mm because it carries Espressif's
    #    15 mm antenna clearance, and its embedded keep-out zone bans copper, vias and
    #    footprints over 48 x 21.2 mm of it.  Honouring that is not optional -- DRC enforces
    #    the keep-out, and the clearance is the whole reason the module is on this edge.
    #    Dropped to y = 72 the courtyard spans y 47.8..96.2, which clears the wire-exit field
    #    below and leaves the top right (y 23..46) usable for the MCU block.
    "U5":  (147.0, 72.0, 270),
}

# R100's surrounding copper is part of the current MEASUREMENT, not just cooling (spec 4.2).
# Nothing is auto-flowed within this radius of it.
KEEPCLEAR = {"R100": 4.0}

# Parts whose courtyard is allowed to leave the board outline.  U5's courtyard carries
# Espressif's 15 mm antenna clearance, and the whole point of putting the module on this edge
# is that most of that clearance is off the board.
OFFBOARD_OK = {"U5"}

# ------------------------------------------------------------------ board text
NOTES = [
    # (text, x, y, layer, size)
    ("LAYOUT CONSTRAINTS (spec 9.3, 9.4, 10 / plan Task 8)\n"
     "6 layers: F.Cu sig, In1.Cu GND solid and unbroken, In2.Cu sig, In3.Cu VBAT,\n"
     "In4.Cu sig, B.Cu sig. COPPER: 1 oz (35 um) on ALL SIX. 1 oz outer is what holds\n"
     "U10's 0.15 mm land pattern; 1 oz inner is what lets In2/In4 be etched to the\n"
     "0.20 mm clearance this board declares -- a 2 oz inner layer cannot hold it.\n"
     "Assembly is SINGLE SIDED -- nothing on B.Cu.\n"
     "FEED path (7.0 A cont, 7.8 A transient): the In3.Cu polygon, measured at 71 mm on\n"
     "its worst cut against the 11.44 mm IPC-2221 asks (10 C rise, internal, 1 oz) --\n"
     "see scripts/check_plane_width.py. On F.Cu the FEED class floor is\n"
     "3.5 mm = a 20 C rise; POUR to >= 4.5 mm for 10 C on any real run. No TRACK carries it.\n"
     "HEAT LEAVES THROUGH THE BASE, NOT AN EDGE: the plate is the face UNDER the board and\n"
     "couples through B.Cu. Thermal group L2 (0.78 W), U9 (0.35 W), L1 (0.28 W), U3, L3 --\n"
     "~1.6 W of the 2.31 W night total. L2 has no paddle; its heat goes to board copper.\n"
     "There are NO external boost FETs and NO P-FET. Night governs, not daytime.\n"
     "eFuse island near J1, and NOT via-coupled to the plate: U10, Q10, Q11, R100, C65.\n"
     "R100 needs its own copper and a Kelvin tap. C65 must sit AT U10 pin 5.\n"
     "Antenna edge is RIGHT: no copper, plating or parts on ANY layer in the U5 keep-out.\n"
     "Wire-exit field is BOTTOM: J1 power at the far left, J2 CAN at the far right.\n"
     "Boost switch-node loop area minimised; gate loops short and tight.\n"
     "GND_IN and GND are SEPARATE and meet at TWO places only: L2 winding B, and R3.\n"
     "The plane must not bridge them anywhere else -- see scripts/check_grounds.py.",
     23.0, 124.0, "Cmts.User", 1.5),
    ("THERMAL / FAB\n"
     "VIA IN PAD: U1.9, U2.9, U3.17, U9.15 and D4.3 are filled with 0.5 / 0.25 mm vias.\n"
     "These MUST be plugged and capped (IPC-4761 type IV or VI) -- unplugged vias in a\n"
     "solderable paddle wick paste out of the joint and void the thermal path they exist for.\n"
     "Heat leaves through B.Cu: assembly is single sided and the bottom is bare on purpose.\n"
     "Gap pad contacts the two dashed Cmts.User patches, ~1360 mm2 total. Do not tent the\n"
     "stitching vias inside them on B.Cu any more than the rest of the bottom side.\n"
     "U10 is MSOP-10 with NO exposed pad; its dissipation leaves through the lead frame.",
     102.0, 124.0, "Cmts.User", 1.2),
    ("ANTENNA KEEP-OUT -- no copper / plating / parts, ALL LAYERS.\n"
     "18.0 x 6.19 mm from the module end face (datasheet v1.8 Fig. 12).\n"
     "Enclosure must also give >= 15 mm clear in ALL directions (enclosure.md).",
     121.0, 16.0, "Cmts.User", 1.2),
]

# ------------------------------------------------------------------ net classes -> mccan.kicad_pro
# Written into the PROJECT file, not the board: KiCad has kept net classes there since v7.
# FEED is the 7.0 A input chain and POWER is everything else, and the split exists because
# the stackup went to 1 oz OUTER copper on 2026-09-20 (see gen_pcb.STACKUP for why).
#
# Halving the outer copper halves what an outer-layer track carries.  By IPC-2221 a 2.0 mm
# F.Cu track is good for 6.51 A at 2 oz and only 3.94 A at 1 oz, both at a 10 K rise -- so the
# single POWER class at 2.0 mm, which was adequate before, is no longer adequate for the nets
# that carry the whole feed.  Those need 4.42 mm at 10 K, or 2.91 mm if a 20 K rise is allowed.
#
# FEED is therefore 3.5 mm, which is a 20 K-rise width (8.01 A) rather than a 10 K one, and
# that is deliberate: it is a FLOOR for the short hops between the input parts, which sit in
# one tight island by J1.  Anything running further than a few millimetres on F.Cu must be
# POURED to >= 4.5 mm, and the through-path itself belongs on the In2.Cu polygon at 5.75 mm.
# The board note says so, because a netclass minimum cannot express "and pour it".
#
# POWER stays at 2.0 mm.  It now covers only +24V, +5V and VLOGIC_IN, whose largest load is
# the boost output at 0.5 A (spec 6) -- 3.94 A of capability is ample.
NETCLASSES = [
    # name, track width, clearance, via size, via drill, nets
    ("FEED", 3.5, 0.3, 0.8, 0.4,
     ["VBAT", "VBAT_PROT", "VBAT_F", "FEED_P", "MID", "SNS", "GND_IN"]),
    ("POWER", 2.0, 0.3, 0.8, 0.4, ["VLOGIC_IN", "+24V", "+5V"]),
    ("CAN", 0.3, 0.2, 0.6, 0.3, ["CANH", "CANL"]),
]


# --------------------------------------------------------------------------- pours
# The F.Cu GND_IN island, in board coordinates.  It lives here rather than inside gen_pcb's
# zones() because two other things need the same polygon: the stitching-via generator, which
# must not drop a GND via inside it, and scripts/check_grounds.py, which reads it back off the
# board.  Shape reasoning is in zones().
GND_IN_ISLAND = [
    (42.0, 36.0), (48.0, 36.0), (48.0, 53.5), (62.0, 53.5), (62.0, 94.0),
    (46.0, 94.0), (46.0, Y1 - 0.5), (22.0, Y1 - 0.5), (22.0, 53.5), (42.0, 53.5),
]


def in_gnd_in_island(x, y, halo=0.0):
    """Is (x, y) -- grown by `halo` -- inside or touching the GND_IN island?

    Tested as a point-in-polygon on the four corners of the halo box plus the centre.  The
    island is an axis-aligned staircase, so that is exact for anything smaller than its
    narrowest 6 mm limb, which every via is.
    """
    pts = [(x, y)] if halo <= 0 else [
        (x, y), (x - halo, y - halo), (x + halo, y - halo),
        (x - halo, y + halo), (x + halo, y + halo)]
    for px, py in pts:
        hit = False
        n = len(GND_IN_ISLAND)
        for i in range(n):
            x0, y0 = GND_IN_ISLAND[i]
            x1, y1 = GND_IN_ISLAND[(i + 1) % n]
            if (y0 > py) != (y1 > py):
                if px < x0 + (py - y0) * (x1 - x0) / (y1 - y0):
                    hit = not hit
        if hit:
            return True
    return False


# --------------------------------------------------------------------------- thermal interface
# Gap-pad contact patches, drawn on Cmts.User for the assembly drawing.  Heat leaves this board
# through its BOTTOM: assembly is single sided, so B.Cu is bare and free to be pressed against
# the enclosure through a gap pad.  That is the whole reason the exposed paddles are filled with
# vias -- the via array is the series element between a part's paddle on F.Cu and the B.Cu
# copper the gap pad actually touches, and a patch over copper with no vias under it cools
# nothing but the laminate.
#
# So the patches are drawn around where the THERMAL VIAS are, not around every part that
# dissipates.  L1 and L2 are deliberately outside them: their loss is in the windings and in
# the copper at their own pads, and neither has a paddle a via array could serve.
#
#   TIM-A  the boost and rail block -- D4's tab, U3's paddle, U1 and U2's paddles, L3 alongside
#   TIM-B  U9, the PROFET, which sits on its own at the bottom of the profet region
#
# Total contact area is ~1.36e3 mm2.  hardware/docs/enclosure.md still assumes ~1000 mm2 at
# 3.8 W; both numbers need revisiting together now that night at ~2.31 W is the governing case.
# D4's +24V heat-spreader island on B.Cu.
#
# D4 is the boost catch diode; its tab is the cathode, so the tab IS the +24V node, and it sits
# inside TIM-A -- the gap pad is where its heat is meant to go.  gen_pcb.thermal_vias() fills
# the tab with a 5 x 6 array on that basis.  But +24V has no plane any more (see gen_pcb.zones):
# In2.Cu is VBAT end to end, because VBAT carries 7.0 A and +24V carries 0.5 A.  Without this
# island the array lands on B.Cu GND, gets notched away from it, and connects to nothing --
# thirty dangling vias, and the diode's heat path and its lowest-impedance current path both
# severed.  KiCad reported that as via_dangling warnings; DRC could not report it as an error,
# because a via that reaches no copper breaks no clearance rule.
#
# It is sized to D4's tab plus half a millimetre all round, and it MUST be resized whenever D4
# moves: a via that reaches no copper breaks no clearance rule, so KiCad can only report the
# severed array as via_dangling warnings, which an error-level gate will not catch.  Moving D4
# into the hand-placed boost cluster did exactly that, and the 30 dangling vias came straight
# back -- which is the only reason this comment says so.
#
# It stops at y 27.4, clearing D4 pad 2 (SW_BOOST, down to y 27.74) by 0.34 mm, over the 0.30 mm
# the POWER class asks for.  It does not reach D4 pad 1: that pad is SMD on F.Cu and is the same
# net anyway, so copper under it would connect nothing and only narrow the gap to the switch
# node.  On the right it stops 0.72 mm short of L3 pad 2, the other end of that switch node.
#
# It costs a 5.8 x 5.7 mm hole in the B.Cu ground pour, in the boost corner.  That is affordable
# because B.Cu is not the reference plane -- In1.Cu is, and In1.Cu stays unbroken.  Against the
# enclosure it is +24 V separated from the plate by the gap pad alone, which is an insulator
# rated in kilovolts; note it on the fab drawing all the same.
D4_24V_ISLAND = [(72.4, 21.7), (78.2, 21.7), (78.2, 27.4), (72.4, 27.4)]

TIM_PADS = [
    ("TIM-A", 64.0, 23.0, 98.0, 58.0),
    ("TIM-B", 69.0, 82.0, 83.0, 94.0),
]


# --------------------------------------------------------------------------- routes
#
# Hand routing, as data.  Each entry is (net, layer, width_mm, [(x, y), ...]) and becomes one
# track segment per adjacent pair of points; ROUTE_VIAS entries are (net, x, y, size, drill).
#
# `net` is matched against the netlist by its LAST path component, so "SW_BOOST" finds
# "/rails/SW_BOOST" without this file having to know which sheet a net was declared on.
#
# gen_pcb.routes() checks two things that are easy to get wrong by hand and invisible
# afterwards:
#
#   * every polyline END lands on copper of its own net -- a pad, a via, or another segment of
#     the same net.  The test is COPPER OVERLAP, not centreline-in-pad, because that is what
#     KiCad's connectivity actually uses: a 0.75 mm track whose centreline runs between two
#     0.25 mm QFN pads still connects to both, and demanding the centreline hit a pad would
#     rule out the only geometry that works on a 0.5 mm pitch part.
#   * no segment or via is closer to a FOREIGN pad than that pad's net class allows.
#
# Neither check replaces DRC.  They exist because a typo in a coordinate here produces a board
# that looks routed, and DRC reports only "unconnected item" somewhere in a list of hundreds.

ROUTES = [
    # -- Task 9 Step 1: the boost power stage -------------------------------------------
    #
    # The commutation loop is C20/C21/C22 -> D4 -> U3's SW pins -> U3's internal FET -> GND,
    # and it is the loop with the high di/dt, so it is the one laid out first and tightest.
    # The return half of it is not routed at all: In1.Cu is solid GND one 0.2 mm dielectric
    # below F.Cu, so the return current mirrors the outbound path directly beneath it, which
    # is a smaller loop than any trace could be.
    #
    # SW is carried on U3 pins 12, 13 and 14.  Pins 13 and 14 are the two rightmost of the top
    # edge, 0.5 mm apart, and a 0.75 mm track centred between them at x 74.5 overlaps both and
    # still clears pin 15 (NC, right edge at x 73.875) by 0.25 mm.  That is why D4 was moved to
    # x 75.3: it puts D4's anode pad at x 73.56..74.96, so the same 0.75 mm track runs straight
    # up into it without a bend, and keeps 0.765 mm from D4's cathode pad on the way.  You
    # cannot bring 0.75 mm of copper into a single pin of a 0.5 mm pitch QFN; you can bring it
    # into two adjacent pins of the same net, and the switch node is the one place worth
    # arranging the placement around to get it.
    # It stops at y 30.55, not lower: U3's exposed GND paddle (pad 17) reaches up to
    # y 31.16, and a 0.75 mm track's end cap reaches 0.375 mm past its endpoint.  At
    # 30.55 the copper stops at 30.925 and clears the paddle by 0.235 mm, while still
    # covering pins 13 and 14 over 0.835 mm of their 0.84 mm length.
    ("SW_BOOST", "F.Cu", 0.75, [(74.5, 30.55), (74.5, 28.37)]),

    # L3 joins the node from the east along y 29.70.  It has to pass under D4's cathode pad
    # (bottom edge y 29.00) and over U3's top-edge pads (top edge y 30.12): at 0.75 mm wide the
    # track spans 29.325..30.075, which clears the cathode -- a FOREIGN net, +24V, POWER class,
    # 0.30 mm -- by 0.325 mm, and touches U3's pins, which is the connection.
    ("SW_BOOST", "F.Cu", 0.75, [(79.81, 29.70), (74.5, 29.70)]),

    # Pin 12 is the third SW pin, on the right edge, and it gets a 0.3 mm tie rather than a
    # share of the current: its neighbour is pin 11 (MODE) 0.5 mm below, and 0.3 mm is the
    # widest track that still clears MODE by 0.225 mm.  The current is on pins 13 and 14.
    ("SW_BOOST", "F.Cu", 0.30, [(75.46, 31.25), (76.40, 30.31), (76.40, 29.70)]),

    # +24V: the output caps to D4's cathode tab.  A 1.0 mm column at x 71.37 picks up all three
    # +24V pads -- the caps are oriented with that pad inboard for exactly this -- and a 1.5 mm
    # rung at mid-tab height carries it into the tab.  0.5 A on 1.0 mm of 1 oz outer copper is
    # 2.3 A of capability; the width here is about loop area and inductance, not about heat.
    ("+24V", "F.Cu", 1.00, [(71.37, 28.40), (71.37, 23.60)]),
    ("+24V", "F.Cu", 1.50, [(71.37, 25.00), (73.60, 25.00)]),

    # VBAT into the boost.  L3 pad 1 and C18/C19 sit over the In2.Cu VBAT plane, so the feed
    # comes UP out of the plane rather than along the board: two 0.8/0.4 vias, ~0.5 A each.
    # This is the whole reason In2.Cu became one VBAT plane in ae9319e.
    ("VBAT", "F.Cu", 1.20, [(82.19, 28.60), (84.73, 28.60)]),
    ("VBAT", "F.Cu", 1.20, [(84.73, 28.60), (84.73, 32.20)]),
]

ROUTE_VIAS = [
    ("VBAT", 83.40, 28.60, 0.8, 0.4),
    ("VBAT", 84.73, 30.40, 0.8, 0.4),
]
