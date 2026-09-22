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
    #    Q11 is mirrored so the back-to-back pair meets drain-to-drain.  At a common 0
    #    rotation Q10's drain tab faces Q11's SOURCE, and both MID and SNS have to climb
    #    over a pad of the wrong net: 21.3 mm and 21.1 mm of detour measured against the
    #    bare board, versus 7.4 mm and 3.8 mm mirrored.  That is ~31 mm of 7 A copper,
    #    ~0.2 W, and it also frees the y 93.7 and y 80.5 corridors for the router.
    "Q10": (31.0, 87.0, 0),
    "Q11": (46.0, 87.0, 180),
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
     "Boost switch-node loop area minimised. NO gate loops: U3 switches internally, so the\n"
     "only fast edge is SW -> D4 -> C61 -> PGND. Keep that loop tight; nothing else here is.\n"
     "GND_IN and GND are SEPARATE and meet at TWO places only: L2 winding B, and R3.\n"
     "The plane must not bridge them anywhere else -- see scripts/check_grounds.py.",
     23.0, 124.0, "Cmts.User", 1.5),
    ("THERMAL / FAB / DFM\n"
     "VIA IN PAD: U1.9, U2.9, U3.17, U9.15 and D4.3 are filled with 0.55 / 0.25 mm vias.\n"
     "These MUST be plugged and capped (IPC-4761 type IV or VI) -- unplugged vias in a\n"
     "solderable paddle wick paste out of the joint and void the thermal path they exist for.\n"
     "Heat leaves through B.Cu: assembly is single sided and the bottom is bare on purpose.\n"
     "Gap pad contacts the two dashed Cmts.User patches, ~1360 mm2 total. Do not tent the\n"
     "stitching vias inside them on B.Cu any more than the rest of the bottom side.\n"
     "U10 is MSOP-10 with NO exposed pad; its dissipation leaves through the lead frame.\n"
     "B.Cu under D4 is +24 V, not ground. The gap pad is the ONLY thing between it and the\n"
     "plate -- it must be an insulator rated for the rail, not a conductive filler.\n"
     "\n"
     "ORDER NOTES -- these are not defaults, they have to be asked for:\n"
     "1. VIA IN PAD PLUGGED AND CAPPED on the five paddles above. The default finish is\n"
     "   TENTED, which is a mask skin over an open barrel and is not the same thing.\n"
     "2. NO SOLDER MASK DAM at U10. Its leads leave a 0.15 mm gap, and a dam that thin does\n"
     "   not survive the mask process -- a half-formed sliver is worse than none. Run the\n"
     "   opening across the leads and let the paste stencil define the joints.\n"
     "3. STENCIL 0.12 mm laser cut, trapezoidal walls. U1/U2 land patterns are at 0.200 mm\n"
     "   and U10 at 0.150 mm; all three are legal here by written exception\n"
     "   (mccan.kicad_dru), not by accident. Reduce paddle apertures to ~70% area.\n"
     "4. ASK BEFORE FAB: the quoted hole-to-hole minimum is written against 'vias <= 0.45\n"
     "   mm'. Every via here is 0.5 / 0.55 / 0.6 / 0.8 mm, so it is not clear whether the\n"
     "   0.3 mm rule this board is built to applies, or a wider one does.\n"
     "\n"
     "Full fabrication and assembly notes, with the text to paste into the order:\n"
     "docs/fabrication.md",
     23.0, 165.0, "Cmts.User", 1.2),
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
# POURED to >= 4.5 mm, and the through-path itself belongs on the In3.Cu polygon, which
# scripts/check_plane_width.py measures at 71 mm against the 11.44 mm 1 oz asks.
# The board note says so, because a netclass minimum cannot express "and pour it".
#
# POWER stays at 2.0 mm.  It now covers only +24V, +5V and VLOGIC_IN, whose largest load is
# the boost output at 0.5 A (spec 6) -- 3.94 A of capability is ample.
NETCLASSES = [
    # name, track width, clearance, via size, via drill, nets
    #
    # FEED's width is the 7 A chain's 3.5 mm, and that is a deliberate choice rather
    # than the obvious one.
    #
    # The chain -- J1 -> Q10 -> Q11 -> R100 -> L2 -> L1 -> the In3.Cu plane -- is hand-laid
    # in ROUTES at an explicit 3.5 mm, segment by segment, because it is the only part of
    # these nets that ever sees 7 A.  Everything else on them is a tap: gate-drive bias to
    # R104/R105/Q12, the MID sense divider, the Kelvin pair to U10 pins 4 and 5, D2's clamp,
    # decoupling.  Those land on 0603 pads inside the eFuse control band, and the widest
    # slot in that band is 0.95 mm.  A 3.5 mm class width does not make a tap wide -- it
    # makes it unroutable, and that is what 51 of the 72 unconnected items were.
    #
    # A netclass cannot say "3.5 mm on the trunk, 0.5 mm on the branches", and nothing here
    # routes automatically anyway: FEED, POWER and CAN are all in gen_pcb.AR_SKIP_CLASSES,
    # so neither the internal router nor KiCadRoutingTools will lay a millimetre of these
    # nets.  Every one of them is hand-authored in ROUTES with its own explicit width.
    #
    # That makes this number a default for interactive routing in KiCad and nothing more,
    # so it stays at the trunk's 3.5 mm: someone who pulls a tap at 3.5 mm sees the problem
    # in the first second, and someone who pulls the trunk at 0.5 mm might not.
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

    # VBAT into the boost.  L3 pad 1 and C18/C19 sit over the In3.Cu VBAT plane, so the feed
    # comes UP out of the plane rather than along the board: two 0.8/0.4 vias, ~0.5 A each.
    # This is the whole reason the stackup carries a dedicated VBAT plane (ae9319e).
    ("VBAT", "F.Cu", 1.20, [(82.19, 28.60), (84.73, 28.60)]),
    ("VBAT", "F.Cu", 1.20, [(84.73, 28.60), (84.73, 32.20)]),

    # -- Task 9 Step 2: the 7 A feed chain ----------------------------------------------
    #
    # J1.2 -> Q10 -> Q11 -> R100 -> L2 -> L1 -> the In3.Cu VBAT plane.  Every segment on
    # this chain is 3.5 mm, the FEED class width.  7.0 A continuous on 1 oz outer copper
    # is 2.89 mm at a 20 K rise by IPC-2221, so 3.5 mm is roughly a 13 K design point and
    # the 7.8 A transient lands near 17 K.  Nothing on this chain necks: where the board
    # is tight the route goes the long way round instead.
    #
    # The lanes were measured, not eyeballed.  A 0.1 mm occupancy grid of every foreign
    # pad grown by its own class clearance, a distance transform for the widest lane that
    # exists, and a turn-penalised Dijkstra for the path with the fewest corners -- run
    # against the board with the signal copper stripped, because these routes are authored
    # before the router runs and the router works around them.  That is what establishes
    # that the direct crossing of the eFuse control band is impossible at 3.5 mm.

    # FEED_P: J1 pin 2 into Q10's source bar.  The only way out of J1 is north, into the
    # 4.7 mm channel between J1's pad row (top edge y 96.33) and the FET row (bottom edge
    # y 91.35); a 3.5 mm track centred on y 94.0 clears them by 0.58 and 0.65 mm.  Q10's
    # source is a 0.8 mm bar with seven fingers running west off it, and the track lands
    # on the bar and runs its length so the current enters the fingers along the whole bar
    # rather than piling into the near end.
    # The only way west is the channel between the two drain tabs (they stop at y 92.05)
    # and the J1 pad row (it starts at y 96.33): 4.28 mm for a 3.5 mm track that wants
    # 0.30 either side.  That leaves 0.78 mm of slack, and a centreline at y 94.19 splits
    # it evenly -- 0.39 mm to the tabs, 0.39 mm to J1.  There is no wider lane and no
    # second one; moving one of the two rows is what it would take to loosen this.
    ("FEED_P", "F.Cu", 3.5, [(36.85, 97.91), (36.85, 94.19),
                             (25.75, 94.19), (25.75, 90.00)]),

    # MID: Q10's drain tab to Q11's, across the 1.70 mm between them -- Q10's copper ends
    # at x 37.65 and Q11's, mirrored by the 180 rotation, starts at 39.35.  This is the one
    # joint on the 7 A chain with a FET either side of it, so it is the one place a neck
    # would cost the most, and it is also the one place there is room not to have one:
    # both tabs are 10.1 mm tall and nothing else is within 2 mm.
    #
    # So the bridge is 8.0 mm, not the 3.5 mm FEED minimum -- the class width is a floor,
    # and here the copper is free.  Centred at y 87.00 it spans y 83.00..91.00, inside the
    # 8.7 mm anchor band of both pads, and the round track ends reach x 32.8 and 44.2,
    # well inside both tabs.  At 8 mm the rise over ambient across this joint is a rounding
    # error, and the two drains share a heat path instead of meeting through a strip.
    ("MID", "F.Cu", 8.0, [(36.80, 87.00), (40.20, 87.00)]),

    # SNS: Q11's source bar to the high side of the sense resistor.  R100 sits with its
    # pads stacked in y -- SNS at y 89.96, VBAT_PROT at 84.04 -- so this has to reach over
    # the VBAT_PROT pad without touching it and stop short of Q11's gate at y 90.80.
    # y 88.00 is the middle of that: 1.60 mm clear of R100 pin 2 below, 1.05 mm clear of
    # the gate above.  The Kelvin taps to U10 pins 4 and 5 come off R100's own pads and
    # are deliberately not this track.
    ("SNS", "F.Cu", 3.5, [(51.25, 88.00), (57.00, 88.00), (57.00, 89.96)]),

    # VBAT_PROT: the sense resistor's low side up to the common-mode choke.  The one long
    # haul on the board, and it cannot go straight.  The eFuse control band -- R3, Q12,
    # D21-D23, R101-R107, C62-C64 -- fills y 55..62 from x 23 across to x 60, and the
    # widest gap anywhere inside it is 0.87 mm.  Only two crossings exist at this width:
    # the west margin beside R3 (3.16 mm) and the east margin between D2's ground pad and
    # L4 (3.03 mm).  East is the side to be on, because R100 is already at x 57.
    #
    # Out of R100 on a diagonal to the east margin, north up x 61.7 just outside the
    # GND_IN island's east edge at x 62 -- which trims the pour's margin rather than
    # slotting it -- through the band at x 62.4, then one long 45 degree run back west.
    #
    # The last three segments are the part that is not obvious.  The island sends a 6 mm
    # stub south down x 42..48 to reach L2 pin 2, the GND_IN side of the choke.  Cutting
    # across that stub would sever L2 pin 2 from J1 pin 3, so the route drops south clear
    # of the stub's bottom edge at y 36 and comes at L2 pin 1 from underneath instead.
    # 78 mm of 3.5 mm copper is 11 mohm and 0.54 W at 7 A; the detour costs about 0.15 W
    # against a straight line that does not exist.
    ("VBAT_PROT", "F.Cu", 3.5, [(57.00, 83.80), (61.70, 79.10), (61.70, 59.30),
                                (62.40, 58.60), (62.40, 53.10), (50.10, 40.80),
                                (50.10, 33.90), (41.00, 33.90), (37.20, 37.70),
                                (37.20, 38.00)]),

    # VBAT_F: the choke's second winding out to the pi-filter inductor.  One 45 degree leg
    # and one straight; this corner is empty because L2 is 25 x 19.65 mm and was placed
    # first, which left the space.
    ("VBAT_F", "F.Cu", 3.5, [(37.25, 27.30), (26.49, 38.06), (26.49, 50.00)]),

    # VBAT: L1's output across to C3, and from there down onto the In3.Cu plane.  Both
    # pads are SMD, so the plane is not reached through either footprint and needs its own
    # via field.  The 2.5 mm gap between the two pads is the only clear copper for it --
    # see ROUTE_VIAS.  The link track overhangs C3's pad by 0.5 mm top and bottom, which is
    # its own net and has nothing else within 3 mm.
    ("VBAT", "F.Cu", 3.5, [(35.51, 50.00), (41.80, 50.00)]),

    # ------------------------------------------------------------------ U10's sense pair
    #
    # U10 is an MSOP-10: 0.34 mm pads on 0.50 mm pitch, so 0.16 mm of bare laminate between
    # one pin and the next.  FEED's 0.30 mm clearance cannot be held on both sides of an
    # interior pin -- the legal band either side of pin 4 is 0.06 mm wide, which is to say
    # there isn't one.  What makes the escape legal is the land-pattern rule gen_netclasses
    # writes into mccan.kicad_dru: KiCad tests a clearance condition with the two items in
    # both orders, so A.memberOfFootprint('U10') relaxes a TRACK against a U10 pad to
    # 0.12 mm exactly as it relaxes two U10 pads against each other.  gen_pcb.dru_floor()
    # reads that file back so the generator's own checker applies the same number.
    #
    # The escapes below sit at 0.18-0.20 mm from the neighbouring pin, which is ordinary
    # for a 0.5 mm-pitch part and well inside PCBWay's 0.1 mm minimum.  Everything past the
    # footprint returns to the full 0.30 mm.  Nothing else on this board leans on that
    # exemption, and no track-to-track pair anywhere does: the two escapes are held 0.50 mm
    # apart leaving the part, which is a genuine 0.30 mm gap at 0.5/0.3 mm widths.
    #
    # Both nets are also the current-limit sense pair -- U10 measures the drop across R100
    # between pin 4 (SNS) and pin 5 (OUT) -- so both end on R100's own copper rather than
    # on Q11's source tab.  They run as a pair, 0.90 mm between centrelines over the whole
    # 18 mm traverse, which keeps the differential loop area small without asking for a
    # clearance neither net can afford.

    # SNS: pin 4 is an interior pin with pins 3 and 5 either side, so west is the only way
    # out and 0.3 mm is the only width that fits -- 0.18 mm to each neighbour.  It widens
    # to 0.5 mm the moment it is clear of the land pattern.
    ("SNS", "F.Cu", 0.3, [(36.50, 74.50), (35.50, 74.50)]),
    ("SNS", "F.Cu", 0.5, [(35.50, 74.50), (35.50, 80.30),
                          (53.60, 80.30), (53.60, 87.00)]),

    # OUT (VBAT_PROT): pin 5 is the corner pin, so this one escapes south into open space
    # and only pin 4 is close.  It goes to C65 FIRST and reaches R100 second: C65 is the
    # part's mandatory output bypass and notes_power_input.py requires it AT pin 5, not
    # merely on the net, so the bypass must not hang off a spur taken after the sense run.
    #
    # C65's east side is walled in by its own GND_IN pad (x 54.95..58.45), so the leg on to
    # R100 leaves C65 southward and crosses beneath it at y 78.50, 1.45 mm clear.
    ("VBAT_PROT", "F.Cu", 0.5, [(37.40, 75.10), (37.40, 77.50),
                                (51.30, 77.50), (51.30, 76.30)]),
    ("VBAT_PROT", "F.Cu", 0.5, [(52.00, 76.30), (52.00, 78.50),
                                (56.00, 78.50), (56.00, 84.04)]),

    # ------------------------------------------------------- the eFuse gate-drive network
    #
    # Everything below carries microamps: R104/R105/R107 are 240k-class bias resistors and
    # R101 is the MID sense divider, so these are 0.5 mm tracks by choice, not by squeeze.
    # What is tight is where they can go.  The control band -- y 56..63, x 23..51 -- is two
    # rows of 0603s and SOT-23s with 0.6 to 1.5 mm between neighbouring pads, so none of
    # these nets crosses it.  They all use the empty channel at y 63, between the top of
    # that band (y 61.41, R103/R104) and the top of U10 (y 72.83), and drop into the band
    # from above through whichever inter-pad slot lines up.
    #
    # Their LONG legs, though, are on inner layers, and that is the part worth explaining.
    # F.Cu here is not empty copper: the GND_IN island is poured over this whole quadrant,
    # and it is the return path for the 7 A feed -- J1 pin 3 up to U10's ground pins.  A
    # 0.5 mm track is a 1.1 mm slot in that pour once clearance is counted, so a bias tap
    # drawn the short way across the block cuts the return it shares the layer with.  The
    # first attempt did exactly that: FEED_P ran down x 22.70 for 22 mm and east along
    # y 63 for 19 mm, MID down x 42.90 for 19 mm, and between them they cut the island
    # into three -- U10's two ground pins in one piece, J1's pin in another, everything
    # else in a third, which is what KiCad reported and what the ASCII map of the fill
    # showed.  The west lane was the worst of them: x 22..24 is the ONLY corridor the pour
    # has past Q10's pads, so a track laid in it severs J1 from the whole eFuse.
    #
    # So the hauls go on In2.Cu (FEED_P) and In4.Cu (MID) -- different layers so the two
    # cannot foul each other -- and F.Cu keeps only the stubs that reach into the band,
    # 2 to 5 mm each, which the pour flows round.  The cost is four vias on a microamp net,
    # which is nothing; the alternative was to spend the island.

    # FEED_P: Q10's source out to R104, Q12 and R105.  It never touches F.Cu between the
    # two, because F.Cu in this column belongs to the GND_IN return (see above).  The drop
    # is taken at (25.75, 92.60), which is INSIDE the 3.5 mm trunk that already runs from
    # J1 to Q10's source pad -- a via there lands on copper the pour has already given up,
    # so it costs the island nothing, whereas a via beside Q10's pad would sit in the one
    # corridor the island has left.  Then 30 mm north and 21 mm east on In2.Cu, surfacing
    # at each tap.
    ("FEED_P", "In2.Cu", 0.5, [(25.75, 92.60), (25.75, 63.00), (46.80, 63.00)]),
    # R105 is entered through the 1.50 mm slot between D22's two pads, 0.50 mm clear of
    # each, then diagonally into the pad.  Coming straight down x 47.50 -- the middle of
    # R105's own pad -- would have run 0.05 mm into D22 pin 2.
    ("FEED_P", "F.Cu", 0.5, [(46.80, 63.00), (46.80, 58.80), (47.50, 57.30)]),
    # R104 is reached from above: its own row is R103 p1 | R103 p2 | R104 p1 | R104 p2 on a
    # 1.65 mm pitch, so there is no way in from either side.
    ("FEED_P", "F.Cu", 0.5, [(27.36, 63.00), (27.36, 61.00)]),
    # Q12 pin 2 from the north-west, down the 1.35 mm between R3 pin 2 and R102 pin 1.
    # Coming at it from the east instead would mean the 0.86 mm slot between R102's own
    # pads, which is a 0.2 mm track at 0.33 mm clearance -- this way is 0.5 at 0.42.
    ("FEED_P", "F.Cu", 0.5, [(31.28, 63.00), (31.28, 58.35), (32.50, 58.35)]),

    # MID: Q11's drain tab up to the sense divider.  The one slot through this band is
    # between C64's two pads, 0.90 mm wide, which takes a 0.25 mm track at 0.325 mm
    # clearance either side.  It is a divider tap into a 240k-class leg, so the width costs
    # nothing; the alternatives were between R101's own pads (blocked by C64 pin 2) or west
    # of R101 (blocked by U10's right-hand pin column).
    # It also has to cross the SNS/OUT sense pair, which runs east-west at y 80.30 and
    # y 77.50 across this whole quadrant, and it must not wall U10's two ground pins off
    # from the rest of the island -- x 42.90 is 1.05 mm east of U10's right-hand pin
    # column, and a track there leaves the pour a 0.33 mm neck to reach those pins by,
    # which min_thickness eats.  Both problems have the same answer: stay off F.Cu.  The
    # drop is at y 81.60, on Q11's own tab, where the via may sit on the pad edge because
    # the tab is MID too; it surfaces again at y 62.00, just clear of C64, and threads the
    # 0.90 mm slot between C64's pads from there.  In4.Cu rather than In2.Cu only so that
    # it cannot collide with FEED_P's haul, which crosses this line at y 63.
    ("MID", "F.Cu", 0.25, [(42.90, 83.00), (42.90, 81.60)]),
    ("MID", "In4.Cu", 0.25, [(42.90, 81.60), (42.90, 62.00)]),
    ("MID", "F.Cu", 0.25, [(42.90, 62.00), (42.90, 57.80)]),

    # VBAT_PROT: D2, the SMBJ24A clamp, down to R2 pin 1 -- which is already on the trunk,
    # the diagonal passes straight through that pad.  East is walled off by D2's own GND_IN
    # pad (x 57.75..60.25) and north by C62 and R106, whose slots are 0.64 and 0.86 mm.
    # South is open the whole way, so the clamp gets 11.5 mm of 2.0 mm copper rather than
    # 6 mm of 0.3 mm through two necks; for a surge path the inductance of the neck would
    # cost more than the extra length does.
    ("VBAT_PROT", "F.Cu", 2.0, [(54.50, 57.00), (54.50, 45.50)]),

    # VBAT_F: C1 and R2 pin 2 back to the choke.  The VBAT_PROT trunk is a 3.5 mm wall
    # across this whole quadrant -- down x 50.10, west along y 33.90, then diagonally up to
    # L2 -- and its lowest edge is y 32.15, so the way through is underneath it at y 30.50,
    # in the empty band between the trunk and L2's own pad row.  Getting there from C1
    # means first going south of C5's drop, then west at y 33.60 -- which is set by
    # C5's ground drop, not by C5 itself: the stub and its via reach to y 32.66 --
    # and down around the trunk's corner cap at (50.10, 33.90), which reaches x 51.85.
    #
    # 1.0 mm rather than the 0.5 mm the current needs: C1 is a bypass on this rail and the
    # placement leaves it 22 mm from the nearest other VBAT_F copper, so the inductance of
    # the run is what limits it, not the resistance.
    ("VBAT_F", "F.Cu", 1.0, [(58.90, 31.00), (58.90, 33.60), (52.80, 33.60),
                             (52.80, 30.50), (37.25, 30.50), (37.25, 28.20)]),
    ("VBAT_F", "F.Cu", 1.0, [(58.90, 33.60), (58.90, 42.50),
                             (59.90, 43.50), (59.90, 45.00)]),

    # ------------------------------------------------------- VBAT down onto its own plane
    #
    # In3.Cu is VBAT end to end (see gen_pcb.zones), so every remaining VBAT pad on the
    # board is one via away from the rail and none of them needs a track across the board
    # to reach it.  That is the whole argument for spending a layer on the plane, and it
    # is why what follows is nine stubs rather than nine routes: the ratsnest listed nine
    # unconnected VBAT items and they are nine pads that were not yet on In3.Cu, not nine
    # journeys.  L1 pin 2 is already there through the six-via field above; everything else
    # gets its own drop.
    #
    # All nine stubs are 0.5 mm, which is 2.1 A on 1 oz outer copper at a 20 K rise.  Only
    # two of these pads carry more than milliamps and both are well inside that; the width
    # is set by what will sit under a 0.6 mm pad edge without necking, not by heat.  Each
    # via position was searched against the generated board -- every pad, all 142 ground
    # drops, the stitching and thermal fields, and every track already laid -- rather than
    # eyeballed off the placement.
    #
    # C12 gets TWO vias.  It is the input capacitor of the LM5164 and the placement leaves
    # 8 mm between it and U2's VIN pin, which looks like a bad input loop and is not: the
    # current goes down to In3.Cu and comes back on In1.Cu, 0.96 mm away, so the loop is
    # 8 mm long and 0.96 mm tall -- under 8 mm^2, which is about what a cap placed right at
    # the pin would give on the same stackup.  The pair halves the via inductance at the
    # end where the ripple current actually is.
    #
    # U2 pin 2 keeps ONE.  There is room for a second only 0.53 mm west of L5's pad, which
    # routes() measures at 0.214 mm because it treats a via as a square, and the second
    # hole is not worth arguing with the checker over: against 8 mm of plane run the
    # difference is a fraction of a nanohenry.  A local high-frequency cap AT pin 2 would
    # be worth more than either and wants a placement change, which is not this task's to
    # make -- it is written down in the routing notes instead.
    ("VBAT", "F.Cu", 0.5, [(23.95, 30.18), (23.95, 31.30)]),       # C2  100n
    ("VBAT", "F.Cu", 0.5, [(55.02, 28.35), (55.02, 27.05)]),       # C4  1u
    ("VBAT", "F.Cu", 0.5, [(59.70, 24.95), (61.40, 24.95)]),       # D3  Schottky, ~0.3 A
    ("VBAT", "F.Cu", 0.5, [(69.17, 32.40), (68.31, 32.40)]),       # R16 0R to U2 BIAS
    ("VBAT", "F.Cu", 0.5, [(75.53, 60.35), (76.88, 60.35)]),       # C12 2u2, U2 input
    ("VBAT", "F.Cu", 0.5, [(76.88, 59.70), (76.88, 61.00)]),       #     ... its second via
    ("VBAT", "F.Cu", 0.5, [(73.95, 63.18), (73.95, 62.00)]),       # C13 100n
    ("VBAT", "F.Cu", 0.5, [(83.42, 58.27), (82.09, 58.27)]),       # U2  VIN
    ("VBAT", "F.Cu", 0.5, [(113.03, 24.80), (113.03, 26.45)]),     # C45 10u
    ("VBAT", "F.Cu", 0.5, [(127.95, 42.18), (127.95, 43.30)]),     # C46 100n

    # -------------------------------------------------------------- VLOGIC_IN, D3 to U1
    #
    # VLOGIC_IN is six pads and one job: carry VBAT past D3's drop to U1, the always-on
    # 3.3 V buck, with C5 holding the rail up at the source end and C6/C7 at the load.  It
    # has no plane of its own, so unlike VBAT every one of these is a real track.
    #
    # Current: U1 is a 1 A part, so at 3.3 V out and 85 % it draws 3.3/(0.85*VIN) amps in.
    # That is 0.32 A at a 12 V VBAT and 0.65 A if the bike is cranking and VBAT sags to 6.
    # The trunk is 0.8 mm, which on an INNER layer at 1 oz is 1.38 A for a 20 K rise -- the
    # outer-layer number does not apply to most of this run -- so a little over twice the
    # worst case.  The last two stubs are 0.5 mm because a 0.8 mm track entering U1 pin 2,
    # which is 0.59 mm tall, would neck at the pad anyway.
    #
    # Nearly all of it is on In2.Cu, for two separate reasons at the two ends.
    #
    # At the D3 end it is because VBAT_F is already here and it encloses C5.  That route
    # leaves C1, runs south past C5's ground drop to y 33.60, west to x 52.80 and north to
    # y 30.50 before heading off to the choke -- three sides of a box round C5's pad, and
    # the fourth side is C4 sitting directly above it.  What is left between VBAT_F's edge
    # at x 53.30 and C5's at x 54.45 is 1.15 mm, and a 0.8 mm track needs 1.40.  So D3 does
    # not reach C5 on F.Cu at all: it drops through at (56.30, 26.55), in the clear space
    # south-east of its own pad, and C5 hangs off the haul underneath it by a 1.2 mm stub
    # to a via at (54.95, 32.35) -- 0.35 mm north of the VBAT_F run it cannot cross.
    #
    # At the U1 end it is because there is no lane.  L4, L5, U1 and U2 fill the row from
    # y 51.2 to 61.1 end to end, with their thermal via fields packed between them.  What
    # the row does leave, though, is the layer underneath: x 53..82 between y 52 and y 57
    # has not one via in it, because the SMD pads that crowd F.Cu there reach no further
    # than F.Cu.  The trunk runs straight down the middle of that at y 54.50.
    #
    # In2.Cu rather than In4.Cu on purpose.  The stackup puts In1.Cu (GND) 0.2 mm above
    # In2.Cu and 0.96 mm above In4.Cu, and the return for this rail is ground: on In2 the
    # supply loop is 40 mm long and 0.2 mm tall, about 8 mm^2, which is as good as this
    # rail gets without a plane of its own.
    ("VLOGIC_IN", "F.Cu",   0.8, [(56.30, 24.95), (56.30, 26.55)]),
    ("VLOGIC_IN", "In2.Cu", 0.8, [(56.30, 26.55), (56.30, 29.60), (54.95, 29.60),
                                  (54.95, 54.50), (81.55, 54.50)]),
    ("VLOGIC_IN", "F.Cu",   0.8, [(54.95, 31.18), (54.95, 32.35)]),          # C5
    #
    # C6 is picked up on the way past.  Its via surfaces at y 58.60, in the 1.75 mm band
    # between L4's pads and U4's, which is the only F.Cu the capacitor can be reached from:
    # west of it U4 leaves 1.23 mm, and a 0.8 mm via wants 1.40.  C7 is 1.2 mm further on.
    ("VLOGIC_IN", "In2.Cu", 0.8, [(70.03, 54.50), (70.03, 58.60)]),
    ("VLOGIC_IN", "F.Cu",   0.8, [(70.03, 58.60), (70.03, 60.35)]),
    ("VLOGIC_IN", "F.Cu",   0.8, [(70.03, 60.35), (70.03, 63.18)]),
    #
    # U1 is entered from the west, because its own exposed pad is on the east side of the
    # pin and pins 1 and 4 are directly above and below.  The via sits between L5's pad and
    # pin 1's ground drop, 0.48 mm off the one and 0.58 mm off the other.
    ("VLOGIC_IN", "In2.Cu", 0.8, [(81.55, 54.50), (81.55, 52.27)]),
    ("VLOGIC_IN", "F.Cu",   0.5, [(81.55, 52.27), (83.42, 52.27)]),
    # Pins 2 and 3 are VIN and EN, tied together on the part -- 0.67 mm apart in the same
    # column, so the link is a stub and not a route.
    ("VLOGIC_IN", "F.Cu",   0.5, [(83.42, 52.27), (83.42, 53.53)]),

    # ------------------------------------------------- +5V, the buck out to the CAN chip
    #
    # Worth saying plainly, because it sets every width below: the whole load on this rail
    # is U6, one TJA1042 transceiver, and its 70 mA worst case.  The other five pads are
    # L5 (the buck's inductor), C16 and C17 (its output capacitors), R8 (the top of the
    # feedback divider) and C29 (the feedforward cap) -- a converter and its own plumbing.
    # So the only current that is not microamps is the inductor's, and that only reaches
    # as far as the two output caps: 0.8 mm from L5 to C16 to C17, 0.5 mm everywhere after.
    #
    # The cap field here is on a 1.05 mm grid -- C8|C9|C10|C11 above, C15|C16|C17|C28 in
    # the middle, C32|C33|C34|R4|R5 below -- and 1.05 mm is exactly the gap a 0.5 mm track
    # at 0.30 mm clearance cannot pass through.  Nothing on F.Cu gets from L5's pad to C16,
    # nor from C16 to C17, nor from C29 to R8.  Every leg of this net is therefore a via
    # down and a via up, and the interesting part is only where the vias will fit.
    #
    # They fit where a search says they fit.  The five drops below were each found by
    # sweeping 72 angles out to 4 mm against the generated board -- every pad, all 142
    # ground drops, the stitching and thermal fields -- with the via modelled as the SQUARE
    # box that routes() measures, not as a disc.  That distinction matters here: half of
    # the candidates a disc accepts are corner clashes a box rejects.
    ("+5V", "F.Cu",   0.8, [(80.00, 56.50), (80.00, 58.60)]),               # L5 pin 2
    ("+5V", "In2.Cu", 0.8, [(80.00, 58.60), (80.00, 64.40), (84.15, 64.40)]),
    ("+5V", "F.Cu",   0.5, [(81.41, 64.93), (80.65, 64.40)]),               # C16
    ("+5V", "F.Cu",   0.5, [(84.91, 64.93), (84.15, 64.40)]),               # C17
    #
    # West to the divider.  The lane back is y 63.20, not the y 64.40 the caps are on: the
    # ground drops under C30 and C32 sit at (71.85, 64.25) and (75.85, 64.25) and close
    # y 64.40 off west of x 76.  y 63.20 threads between those and C13's VBAT drop at
    # (73.95, 62.00) with 0.50 mm on one side and 0.55 on the other.  R8 and C29 carry the
    # feedback divider's current and the feedforward cap's, which is to say nothing, so
    # their drops are 0.6/0.3 -- the smaller via is what fits, and it is honest about what
    # the net is.
    ("+5V", "In2.Cu", 0.5, [(80.00, 63.20), (70.30, 63.20), (70.30, 64.68)]),
    ("+5V", "F.Cu",   0.5, [(69.96, 65.43), (70.30, 64.68)]),               # C29
    ("+5V", "In2.Cu", 0.5, [(70.30, 64.68), (70.30, 66.00), (65.20, 66.00),
                            (65.20, 67.68)]),
    ("+5V", "F.Cu",   0.5, [(64.86, 68.43), (65.20, 67.68)]),               # R8
    #
    # And 55 mm east to U6.  This leg is on In4.Cu rather than In2.Cu for the same reason
    # FEED_P and MID are on different layers: VLOGIC_IN's haul already owns In2 in this
    # quadrant, and two power hauls that cannot share a layer cannot foul each other.  The
    # coupling it gives up does not matter at 70 mA of DC.
    #
    # The path is two clear lanes found by scanning the board for them.  x 93.00 is the gap
    # between the perimeter stitching column at x 91 and the next copper east, clear from
    # y 30 to y 70; y 34.50 runs from there to U6 with three vias anywhere near it, the
    # closest 1.43 mm off.  The dogleg at y 64.76 is to clear the ground drops at
    # (86.45, 63.76) and (89.95, 63.76), which leave a 1.39 mm window between them and the
    # drop at (86.45, 65.75); the track sits in the middle of it, 0.44 mm off each.
    ("+5V", "In4.Cu", 0.5, [(84.15, 64.40), (84.15, 64.76), (93.00, 64.76),
                            (93.00, 34.50), (131.00, 34.50), (131.00, 32.53)]),
    #
    # U6 pin 3 is entered from the west along its own centreline, 0.71 mm clear of pin 2's
    # ground drop above and 0.73 mm clear of pin 4 below.  C38 is its decoupling cap and it
    # is fed THROUGH the pin rather than before it -- the arrival is from the west and C38
    # sits south-east -- which at 70 mA over 3.4 mm of track is worth about 200 uV.  What
    # matters for a decoupler is its loop back to the pin, and that is the placement's to
    # answer, not the routing's.
    ("+5V", "F.Cu",   0.5, [(131.00, 32.53), (134.43, 32.53)]),
    ("+5V", "F.Cu",   0.5, [(134.43, 32.53), (136.90, 32.53), (136.90, 35.93),
                            (137.41, 35.93)]),                              # C38

    # ------------------------------------------- +24V, the boost output out to the fuses
    #
    # 320 mA.  That is the whole rail: 16 W/m of LED tape over 12 cm is 80 mA a corner and
    # there are four corners, which is also why F2-F5 are 0.5 A PTCs and why the boost is
    # an 8 W part rather than the 60 W one this design started with.  0.5 mm on an inner
    # layer is 0.98 A by IPC-2221, so the haul runs at three times its load.
    #
    # The high-current part of this net is not the haul at all -- it is the 30 mm between
    # D4's cathode and C20/C21/C22, where the boost's diode current is a 0.8 A triangle at
    # 400 kHz.  That loop was laid out first (see the block above): a 1.0 mm column up the
    # caps and a 1.5 mm rung into the tab.  What is left here is the diode's second
    # cathode pad.  D4 is a DPAK whose pad 1 and tab are the same node, 0.81 mm apart, and
    # 1.2 mm of copper across that gap costs nothing and halves the pad's share of the
    # current.
    ("+24V", "F.Cu", 1.20, [(76.34, 26.50), (76.34, 28.36)]),
    #
    # Then 47 mm east to the fuses, and none of it on F.Cu.  It cannot be: L3 and its two
    # pads fill x 79.3..82.7 from y 26.9 to 30.3, the SW_BOOST run to U3 fills y 29.3..30.1
    # from x 74.5 to 80.2, and U3 itself with its paddle and eleven passives own everything
    # from there down to y 40.  The one lane east on the top layer is between L3's own two
    # terminals, and threading the quiet output rail through the gap of a switching
    # inductor to save a via is not a trade worth making.
    #
    # In2.Cu is.  The tab already reaches it: the 5x5 thermal field under D4 is 25 vias on
    # this net going all the way through, so the haul starts by simply running along the
    # bottom row of them.  And In1.Cu -- solid ground, 0.1 mm under the top layer -- sits
    # between this track and every noisy thing it passes beneath, so running under L3 and
    # under the switch node costs nothing.  That shield is the real reason the inner layer
    # is the right answer here and not merely the available one.
    #
    # The lane picks its way north of the VBAT drop at (83.40, 28.60) and south of the
    # stitching row at y 26.00, turns south at x 92.60 in the 3.4 mm channel between the
    # perimeter stitching column at x 91.00 and U7's ground drops at x 95.10, and runs east
    # again at y 44.00 under the four fuses.  Between x 105 and x 127 that lane has exactly
    # two vias anywhere near it, 1.01 mm and 1.85 mm off.
    ("+24V", "In2.Cu", 0.50, [(76.29, 26.50), (77.28, 26.50), (77.28, 27.50),
                              (92.60, 27.50), (92.60, 44.00), (123.50, 44.00)]),
    #
    # The feedback divider taps the rail at a via east of R12, because the 0.84 mm between
    # R12 and C61 will not take one and x 80.2..84.2 between them is empty.  0.4 mm and a
    # 0.6/0.3 via: R12 is 1 MOhm-class and this branch carries microamps.
    ("+24V", "In2.Cu", 0.40, [(81.20, 27.50), (81.20, 33.10)]),
    ("+24V", "F.Cu",   0.40, [(81.20, 33.10), (79.83, 32.20)]),          # R12
    ("+24V", "F.Cu",   0.40, [(81.20, 33.10), (79.78, 34.00)]),          # C61
    #
    # Each fuse is fed from below.  Every one of them has a 1.25 mm strip under its input
    # pad between the two SENSE resistors that sit there, and a 0.6/0.3 via lands in the
    # middle of it with ~0.6 mm either side.  F3 and F4 sit on the lane itself; F2 and F5
    # are a millimetre off it and get a stub.
    ("+24V", "In2.Cu", 0.50, [(107.50, 44.00), (107.50, 43.00)]),
    ("+24V", "F.Cu",   0.50, [(107.50, 43.00), (107.08, 41.60)]),        # F2
    ("+24V", "In2.Cu", 0.50, [(112.50, 44.00), (112.50, 45.00)]),
    ("+24V", "F.Cu",   0.50, [(112.50, 45.00), (112.08, 43.60)]),        # F5
    ("+24V", "F.Cu",   0.50, [(118.50, 44.00), (118.08, 42.60)]),        # F3
    ("+24V", "F.Cu",   0.50, [(123.50, 44.00), (123.08, 42.60)]),        # F4
    #
    # ------------------------------------------- CANH/CANL, the pair out to the connector
    #
    # This is the one net on the board that leaves the box on a long unshielded harness, so
    # it is routed for immunity rather than for speed.  At 500 kbit/s the 110 mm from the
    # transceiver to J8 is about 0.7 ns of flight against a 50 ns edge: nothing here is a
    # transmission line, the stub lengths do not matter, and a few millimetres of skew
    # between the two tracks is 20 ps.  What does matter is that the pair stays together,
    # stays over solid ground, and never runs beside anything that switches.
    #
    # In2.Cu gives all three.  It sits 0.2 mm under In1.Cu, which is a solid ground plane
    # with no splits anywhere the pair crosses, so the return current runs directly beneath
    # each track for the whole 110 mm and the loop area is the track width times 0.2 mm.
    # F.Cu could not do that -- the pair would have to cross the LED output field, the fuse
    # bank and the RGB drivers, all of it switching -- and B.Cu is the bottom pour.  The
    # cost is that at 0.2 mm from the plane the pair is plane-referenced rather than edge
    # coupled: differential impedance lands near 70 ohm, not 120.  Widening the gap does
    # not fix that (the plane dominates), and at this bit rate it does not need fixing.
    # The 120 ohm termination at R26 is what the bus sees; the track is short enough to be
    # invisible to it.
    #
    # Topology: the transceiver's side of the choke is U6 -> L6 pins 1/2 (the router's, not
    # ours).  Everything from L6 pins 3/4 out is here: the choke to the ESD array, then a
    # drop to In2.Cu and 110 mm south-west to J8, with R26 tapped off along the way.
    #
    # -- the cluster, on F.Cu.  L6 to D6 is a 1.10 mm straight gap on CANH and a clear
    #    diagonal on CANL; nothing sits between them.
    ("CANH", "F.Cu", 0.30, [(146.68, 29.95), (149.19, 29.95)]),
    ("CANL", "F.Cu", 0.30, [(146.68, 32.40), (149.19, 31.85)]),
    #
    # -- and out of D6 to the drop vias.  East of D6 the only copper is its own ground pad
    #    and Q2, so both vias sit in the 3.0 mm pocket between them: CANH above D6's ground
    #    pad, CANL below it.  1.40 mm clear of it either way.
    ("CANH", "F.Cu", 0.30, [(149.19, 29.95), (150.60, 29.20)]),
    ("CANL", "F.Cu", 0.30, [(149.19, 31.85), (151.60, 32.90)]),
    #
    # -- the haul, on In2.Cu.  0.3 mm tracks on a 1.0 mm pitch, four corners each, and the
    #    two tracks take the same four corners in the same order: CANH is the inside of
    #    both right-hand turns and the outside of both left-hand ones, so the corner
    #    lengths cancel and the pair arrives matched without a serpentine anywhere.
    #
    #    The corridor is chosen, not found by a router.  Inner layers carry no zones and no
    #    SMD pads, so the only obstacles are vias and through-holes, and south of y 72 there
    #    are almost none: the band y 72..81 is empty across the entire board width.  The
    #    descent at x 140/141 threads between U5's ground field (1.89 mm east) and nothing
    #    at all to the west; the run west at y 75/76 has no obstacle within 4 mm; the drop
    #    to J8 at x 67.6/68.6 clears the nearest ground via by 3.09 mm.  The tightest point
    #    on the whole 110 mm is 0.30 mm, where CANH passes a ground via at (142.5, 43.3).
    #
    #    The pair also stays clear of U5's antenna keep-out (x 153.6..174.8, y 48..96) by
    #    turning west at y 44/45, well north of it.
    ("CANH", "In2.Cu", 0.30, [(150.60, 29.20), (150.60, 44.00), (140.00, 44.00),
                              (140.00, 75.00), (67.60, 75.00), (67.60, 96.00),
                              (65.80, 98.50), (65.80, 100.59)]),
    ("CANL", "In2.Cu", 0.30, [(151.60, 32.90), (151.60, 45.00), (141.00, 45.00),
                              (141.00, 76.00), (68.60, 76.00), (68.60, 96.00),
                              (70.40, 98.50), (70.40, 100.59)]),
    #
    # -- R26, the 120 ohm terminator.  It sits in a field of 0402s on a 1.05 mm pitch, and
    #    1.05 mm is too narrow for a via (which needs 1.20) but wide enough for a 0.3 mm
    #    track at 0.375 mm clearance.  Both of its pads therefore escape SOUTH on F.Cu --
    #    the only direction that is open, since north of R26 the channels are closed by a
    #    ground via at (143.5, 35.3) on one side and another at (147.0, 35.3) on the other
    #    -- and drop to the pair below the field, where F.Cu is empty from y 43.6 down.
    #
    #    The two stubs cross the opposite track of the pair, but they cross it on F.Cu
    #    while the pair is on In2.Cu, so there is nothing to avoid.  Each drop via sits on
    #    its own track and clears the other by 0.55 mm.
    ("CANH", "F.Cu", 0.30, [(143.43, 44.00), (143.43, 38.43), (144.36, 38.43)]),
    ("CANL", "F.Cu", 0.30, [(146.935, 45.00), (146.935, 38.43), (146.00, 38.43)]),
]

ROUTE_VIAS = [
    # FEED_P's haul on In2.Cu, and the three taps it surfaces for -- see the routes above.
    ("FEED_P", 25.75, 92.60, 0.8, 0.4),
    ("FEED_P", 27.36, 63.00, 0.8, 0.4),
    ("FEED_P", 31.28, 63.00, 0.8, 0.4),
    ("FEED_P", 46.80, 63.00, 0.8, 0.4),

    # MID's haul on In4.Cu -- see the MID routes above.
    ("MID", 42.90, 81.60, 0.8, 0.4),
    ("MID", 42.90, 62.00, 0.8, 0.4),

    ("VBAT", 83.40, 28.60, 0.8, 0.4),
    ("VBAT", 84.73, 30.40, 0.8, 0.4),

    # The nine plane drops -- see the stubs at the end of ROUTES for the reasoning.  0.8/0.4
    # is the FEED class via; at these currents one apiece is generous and the pair on C12
    # is about inductance, not amps.
    ("VBAT", 23.95, 31.30, 0.8, 0.4),       # C2
    ("VBAT", 55.02, 27.05, 0.8, 0.4),       # C4
    ("VBAT", 61.40, 24.95, 0.8, 0.4),       # D3
    ("VBAT", 68.31, 32.40, 0.8, 0.4),       # R16
    ("VBAT", 76.88, 59.70, 0.8, 0.4),       # C12
    ("VBAT", 76.88, 61.00, 0.8, 0.4),       # C12
    ("VBAT", 73.95, 62.00, 0.8, 0.4),       # C13
    ("VBAT", 82.09, 58.27, 0.8, 0.4),       # U2
    ("VBAT", 113.03, 26.45, 0.8, 0.4),      # C45
    ("VBAT", 127.95, 43.30, 0.8, 0.4),      # C46

    # VLOGIC_IN's In2.Cu haul -- see the routes above.  0.8/0.4 at 0.65 A worst case.
    ("VLOGIC_IN", 56.30, 26.55, 0.8, 0.4),  # D3, the source end
    ("VLOGIC_IN", 54.95, 32.35, 0.8, 0.4),  # C5
    ("VLOGIC_IN", 70.03, 58.60, 0.8, 0.4),  # C6/C7
    ("VLOGIC_IN", 81.55, 52.27, 0.8, 0.4),  # U1 pin 2

    # +5V -- see the routes above.  0.8/0.4 on the converter's own path, 0.6/0.3 on the
    # two feedback taps, where the smaller hole is both sufficient and the only one that
    # fits between C30's ground drop and C7.
    ("+5V", 80.00, 58.60, 0.8, 0.4),        # L5 pin 2
    ("+5V", 80.65, 64.40, 0.8, 0.4),        # C16
    ("+5V", 84.15, 64.40, 0.8, 0.4),        # C17, and the east haul starts here
    ("+5V", 70.30, 64.68, 0.6, 0.3),        # C29
    ("+5V", 65.20, 67.68, 0.6, 0.3),        # R8
    ("+5V", 131.00, 32.53, 0.8, 0.4),       # U6 pin 3

    # +24V -- 320 mA, so 0.6/0.3 throughout; the current lives in the D4-to-C20 loop on
    # F.Cu, not out here.  The tab's own thermal field is what gets this net onto In2.Cu.
    ("+24V", 81.20, 33.10, 0.6, 0.3),       # R12 / C61, the feedback tap
    ("+24V", 107.50, 43.00, 0.6, 0.3),      # F2
    ("+24V", 112.50, 45.00, 0.6, 0.3),      # F5
    ("+24V", 118.50, 44.00, 0.6, 0.3),      # F3
    ("+24V", 123.50, 44.00, 0.6, 0.3),      # F4

    # CAN -- 0.6/0.3 throughout, which is the CAN class's own via and the smallest the
    # board uses.  Two drop the pair from the ESD array onto In2.Cu; two surface it again
    # under R26.  Nothing here carries current worth the name.
    ("CANH", 150.60, 29.20, 0.6, 0.3),      # D6 pin 1, the ESD array
    ("CANL", 151.60, 32.90, 0.6, 0.3),      # D6 pin 2
    ("CANH", 143.43, 44.00, 0.6, 0.3),      # R26 pin 1, the terminator's stub
    ("CANL", 146.935, 45.00, 0.6, 0.3),     # R26 pin 2

    # VBAT down onto the In3.Cu plane, in the gap between L1 pin 2 and C3 pin 1.  Six
    # 0.8/0.4 vias on a 1.2 mm column and 1.15 mm row pitch: 1.17 A each at 7 A, about
    # 0.88 mohm apiece, and spaced so their antipads stay separate holes in the plane
    # instead of merging into one slot across it.  All six sit entirely on the 3.5 mm
    # link track above.
    ("VBAT", 37.75, 48.85, 0.8, 0.4),
    ("VBAT", 38.95, 48.85, 0.8, 0.4),
    ("VBAT", 37.75, 50.00, 0.8, 0.4),
    ("VBAT", 38.95, 50.00, 0.8, 0.4),
    ("VBAT", 37.75, 51.15, 0.8, 0.4),
    ("VBAT", 38.95, 51.15, 0.8, 0.4),
]
