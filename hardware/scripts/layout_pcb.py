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
# 200 x 140 mm (2026-09-23).  Was 140 x 100.
#
# The area doubles, and that is the whole point: the six-layer board reached 0 DRC errors
# at 76 % courtyard fill in the input block, with 12 designators demoted off the
# silkscreen for want of anywhere to print them.  Every one of that board's complaints was
# density.  See docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md.
#
# It also clears a defect logged in docs/enclosure.md section 2 item 5: seven cable glands
# need about 143 mm of wall and would not fit a 140 mm one.  200 mm fits them comfortably.
#
# Thermally it is free -- better than free.  The heat-spreader plate is the base and tracks
# the board footprint, so it goes from ~137 cm2 (61 C at 40 C ambient, against a 65 C
# target) to ~272 cm2, against the 150 cm2 enclosure.md section 1 asks for.  The plate stops
# being a design driver, which is why the thermal group no longer gets to veto placement.
X0, Y0 = 20.0, 20.0
X1, Y1 = 220.0, 160.0
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

# ------------------------------------------------------------------ regions and channels
# (x0, y0, x1, y1) in board coordinates.  Parts not named in PLACE are auto-flowed into
# their block's region on a courtyard-sized grid, largest first.
#
# The 200 x 140 map, laid out as four columns over a full-width wire-exit field, with a
# 6 mm CHANNEL between every pair of neighbours:
#
#     x:  23          70 76        117 123        181 187   217
#         +------------+ +---------+ +---------+ +-------+   y 23
#         |   input    | |  boost  | |         | |  mcu  |
#         |            | |         | |         | +-------+   y 60
#         +------------+ +---------+ |         |             y 70
#         ~~~~~~~~~~~~~~~~~~~~~~~~~~ | outputs |             y 70..76 channel
#         +------------+ +---------+ |         |             y 76
#         |   efuse    | |  rails  | |         |
#         |            | | profet  | |         |
#         +------------+ +---------+ +---------+             y 119
#         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   y 119..125 channel
#         | wire-exit field, full width                  |   y 125
#         +----------------------------------------------+   y 156
#
# The left band still runs the 7 A feed in ONE direction only -- J1 at the bottom, up
# through the eFuse, up through L2 and the pi filter, out of the top of "input".  Nothing
# doubles back.
#
# THE LEFT COLUMN IS THE WIDE ONE, and that is the correction this map exists to make.  The
# comments on the old board worried about the outputs block, but measured, outputs was at
# 37 % and `input` was at **75.8 %** -- the worst region on the board by a wide margin.  It
# holds L2 (a large through-hole choke), D2, L1, D3, R2/R3 and C1-C5 in 1131 mm2.  Scaling
# every region by the same factor would have left it the worst region still, so the left
# column gets 47 x 47 mm against outputs' 58 x 96, and input lands at 38.8 %.
#
# Outputs was never the problem, so it is not given the lion's share: 5568 mm2 takes its
# ~105 auto-flowed parts to 17 %, which is as much room as its escapes can use.
REGIONS = {
    "input":   (23.0,   23.0,  70.0,  70.0),
    "efuse":   (23.0,   76.0,  70.0, 119.0),
    "boost":   (76.0,   23.0, 117.0,  70.0),
    "rails":   (76.0,   76.0, 117.0, 119.0),
    "profet":  (76.0,  104.0, 117.0, 119.0),   # nested inside rails; U9 is hand-placed
    "outputs": (123.0,  23.0, 181.0, 119.0),
    "mcu":     (187.0,  23.0, 217.0,  60.0),   # U5's antenna points off the x = 217 edge
    "wire":    (23.0,  125.0, 217.0, 156.0),
}

# Part-free lanes.  The packer may not enter one; the router may, and that is the entire
# point -- on the old board the space between regions was whatever the packer happened not
# to fill, which is not a routing budget anyone can reason about.
#
# At 0.20 mm track on a 0.40 mm pitch a 6 mm channel carries about 15 tracks per layer,
# 60 across the four signal layers.  3456 mm2 in total, about 12 % of the board.
CHANNELS = [
    (70.0,   23.0,  76.0, 119.0),    # input/efuse  |  boost/rails
    (117.0,  23.0, 123.0, 119.0),    # boost/rails  |  outputs
    (181.0,  23.0, 187.0, 119.0),    # outputs      |  mcu
    (23.0,   70.0, 117.0,  76.0),    # input/boost  |  efuse/rails
    (23.0,  119.0, 217.0, 125.0),    # everything   |  the wire-exit field
]

# Maximum courtyard fill per region, enforced by scripts/check_density.py.  A region absent
# here is unconstrained -- "wire" is, because every part in it is hand-placed against the
# gland row and a budget would only restate the placement.
#
# These are NOT set to whatever the first passing run produced: a budget that exactly matches
# reality fails the moment anyone adds a part.  Each is the measured figure with headroom.
#
#             measured  budget
#   input       38.8 %    45 %   <- the tight one, and the reason the left column got wider
#   efuse       28.3 %    35 %
#   boost       10.5 %    30 %
#   rails       23.7 %    30 %
#   outputs     17.1 %    25 %
#   mcu         27.8 %    35 %
BUDGET = {
    "input":   0.45,
    "efuse":   0.35,
    "boost":   0.30,
    "rails":   0.30,
    "outputs": 0.25,
    "mcu":     0.35,
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
    #    H3 and H4 are still at x 25 and x 215 (X0/MOUNT_INSET did not move), so the row still
    #    starts clear of H3 at the same x it always did.  What changed is the room past it:
    #    194 mm now, against 123 mm before, so the row is re-pitched at the 2.0 mm gap used
    #    everywhere else on the board instead of the 1.2 mm the old row was squeezed to.
    #    These are courtyards, which already carry their own clearance, and nothing is routed
    #    between them: the row is pads and wire, so the gap is a real one, not a shaved one.
    #    Translated +30 in y with the wire region (95 -> 125); the eight courtyards still
    #    total 114.34 mm, so with seven 2.0 mm gaps the row now spans 128.34 mm, well inside
    #    the 194 mm on offer.
    "J1":  (30.85, 127.91, 0),   # box x  28.60.. 45.10  y 125.84..148.16
    "J7":  (49.35, 127.91, 0),   # box x  47.10.. 63.60  y 125.84..148.16
    "J8":  (67.40, 130.59, 0),   # box x  65.60.. 73.80  y 129.01..144.99
    "J3":  (77.60, 130.59, 0),   # box x  75.80.. 93.20  y 129.01..144.99
    "J4":  (97.00, 130.59, 0),   # box x  95.20..112.60  y 129.01..144.99
    "J5":  (116.40, 130.59, 0),  # box x 114.60..132.00  y 129.01..144.99
    "J6":  (135.80, 130.59, 0),  # box x 134.00..151.40  y 129.01..144.99
    "J2":  (155.17, 130.65, 0),  # box x 153.40..156.94  y 128.88..145.12

    # -- the input filter.  Current arrives from the eFuse below and leaves at the top right.
    #    The input region's origin (23, 23) did not move, so this cluster is untouched.
    #    L2's origin is on pad 1 and sits +3.75, -5.03 off its box centre, so (37.25, 38.0)
    #    puts the box at x 28.50..53.50, y 23.15..42.80 -- clear of H1's pad at x 25, y 25.
    "L2":  (37.25, 38.0, 0),     # CM choke: placed FIRST. 25.0 x 19.65 mm, ~24 mm tall, THT
    "L1":  (31.0, 50.0, 0),      # pi-filter inductor, 0.28 W
    "C3":  (46.0, 50.0, 0),      # 220 uF bulk, at L1's output

    # -- the eFuse island.  Translated +22 in y with the efuse region's origin (54 -> 76); x
    #    is unchanged.  Bottom row is nearest J1, so the 7 A path runs strictly upward:
    #    J1 -> Q10 -> Q11 -> R100 -> up to U10 and C65 -> out of the top into L2.
    #    Q11 is mirrored so the back-to-back pair meets drain-to-drain.  At a common 0
    #    rotation Q10's drain tab faces Q11's SOURCE, and both MID and SNS have to climb
    #    over a pad of the wrong net: 21.3 mm and 21.1 mm of detour measured against the
    #    bare board, versus 7.4 mm and 3.8 mm mirrored.  That is ~31 mm of 7 A copper,
    #    ~0.2 W, and it also frees the y 93.7 and y 80.5 corridors for the router.
    "Q10": (31.0, 109.0, 0),
    "Q11": (46.0, 109.0, 180),
    "R100": (57.0, 109.0, 90),   # own copper, Kelvin tap -- see KEEPCLEAR
    "U10": (39.0, 96.0, 0),
    "C65": (54.0, 98.0, 0),      # at U10 pin 5, not merely on the net

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
    #
    #    Translated +12 in x with the boost region's origin (64 -> 76); y is unchanged.  Every
    #    part here keeps its exact relative geometry, D4 across U3 pins 13/14 included -- see
    #    plan Task 9 Step 1.
    "U3":  (86.0, 32.0, 0),      # LM51571-Q1
    "D4":  (87.3, 25.6, 180),    # catch diode, tab up, anode down at U3's SW pins 13/14
    "L3":  (93.0, 28.6, 180),    # boost inductor, SW pad facing U3
    "C20": (81.9, 23.6, 180),    # +24V output caps, a 1206 column against D4's cathode tab:
    "C21": (81.9, 26.0, 180),    # +24V pad inboard at the tab, GND pad outboard where the
    "C22": (81.9, 28.4, 180),    # drop vias reach the plane.  This is the commutation loop.
    "C18": (98.2, 28.6, 0),      # VBAT input caps at L3 pad 1; VBAT arrives from the In2.Cu
    "C19": (98.2, 32.2, 0),      # plane underneath, by via, not by a track across the board
    # right of U3: FB (pin 9), the highest-impedance node after COMP, as a short vertical rail
    "R12": (91.0, 32.2, 180),    # FB divider top, 576k -- FB pad faces U3
    "C61": (91.0, 34.0, 180),    # feedforward across R12 (DNP)
    "R13": (91.0, 35.8, 0),      # FB divider bottom, 24.9k -- GND pad outboard
    # below U3: COMP (pin 8), RT (5), EN (6) all live on the bottom edge
    "R14": (86.0, 35.4, 180),    # COMP series 2.61k, straight down from pin 8
    "C23": (86.0, 37.2, 0),      # COMP series 10nF, straight down from R14
    "C24": (88.55, 35.8, 270),   # COMP parallel 100pF
    "R10": (82.6, 36.4, 180),    # RT 9.09k
    "R20": (82.6, 38.2, 180),    # EN pulldown 100k
    # left of U3: VCC (pin 2) and BIAS (pin 3) and their bypasses, off the switch node entirely
    "R15": (82.0, 30.6, 180),    # VCC 5.1R
    "C26": (78.6, 30.6, 180),    # VCC 1uF
    "R16": (82.0, 32.4, 0),      # BIAS 0R from VBAT -- VBAT pad outboard, to the plane
    "C27": (82.0, 34.2, 180),    # BIAS 100nF
    "R11": (86.0, 39.0, 180),    # MODE 37.4k -- a static level, so it takes the long stub
    "C25": (89.3, 39.0, 0),    # soft start 22nF -- a slow ramp, likewise
    # U9: translated with the profet region's origin, +12 in x (64 -> 76), +22 in y (82 -> 104).
    "U9":  (88.0, 110.0, 0),     # PROFET, the shortest run to J7's Denali pads

    # -- the antenna edge.  Rotated 270 so the antenna points +X (verified against the
    #    footprint: its keep-out sits at local -Y, and 270 maps -Y to +X).
    #    The module END FACE is flush with X1 = 220.0: not cantilevered off the edge, but with
    #    the whole of the footprint's own all-layer keep-out zone left bare.  Translated +60
    #    in x with the board edge (X1 160 -> 220); y is unchanged, since U5 is placed against
    #    the board edge, not against a region -- it is not a member of any REGIONS box (see
    #    OFFBOARD_OK and check_density.py's "outside every region" list).
    #
    #    U5 sits LOW, not centred on the right edge, and that costs real estate on purpose.
    #    The stock footprint's courtyard is 48.5 x 41.5 mm because it carries Espressif's
    #    15 mm antenna clearance, and its embedded keep-out zone bans copper, vias and
    #    footprints over 48 x 21.2 mm of it.  Honouring that is not optional -- DRC enforces
    #    the keep-out, and the clearance is the whole reason the module is on this edge.
    #    At y = 72 the courtyard spans y 47.8..96.2, which clears the wire-exit field below
    #    (now starting at y 125) and leaves the top right (y 23..60) usable for the MCU block.
    "U5":  (207.0, 72.0, 270),
}

# R100's surrounding copper is part of the current MEASUREMENT, not just cooling (spec 4.2).
# Nothing is auto-flowed within this radius of it.
KEEPCLEAR = {"R100": 4.0}

# A nudge is an offset applied to an AUTO-placed part after the packer has run.  It moves
# that one part and nothing else -- unlike a PLACE entry, which takes the part out of the
# flow order and lets everything packed after it slide into the hole.
#
# EMPTIED 2026-09-23 for the 200 x 140 re-layout.  Every offset here was measured against
# the 95 x 36 mm "outputs" region -- specific pixels of a specific packing (Q7 ends at
# x 130.300, the last resistor row lands at y 71.6, and so on) that no longer exists.  The
# region this task hands "outputs" is 58 x 96 mm, more than double the area, and the auto-flow
# is a first-fit packer that repacks from scratch: reapplying the old deltas blind would nudge
# parts by amounts sized for a room that is not the one they are in now, which is exactly how
# a stale nudge creates the overlap it was meant to prevent.
#
# What the nudges were FOR -- a 0.8 mm channel between two driver pins being one pad-width
# too narrow for two tracks, a 0.05 mm gap between resistor rows being no lane at all -- was a
# ROUTABILITY problem, not a courtyard-overlap one: the packer's own grid-occupancy search
# already guarantees no two courtyards overlap (see the module docstring), nudge or no nudge.
# check_courtyards.py confirms that still holds with NUDGE empty. Routability at the new,
# much lower "outputs" fill (target 17 %, against the 59 % that produced these nudges in the
# first place) is Task 9's question to re-ask once there is real copper to measure it against;
# an empty NUDGE is not a lost fix, it is a stale one taken out rather than miscopied.
NUDGE = {}

# Parts whose courtyard is allowed to leave the board outline.  U5's courtyard carries
# Espressif's 15 mm antenna clearance, and the whole point of putting the module on this edge
# is that most of that clearance is off the board.
OFFBOARD_OK = {"U5"}

# ------------------------------------------------------------------ board text
NOTES = [
    # (text, x, y, layer, size)
    ("LAYOUT CONSTRAINTS (spec 9.3, 9.4, 10 / plan Task 8), 200 x 140 mm, 8 layers\n"
     "Was 140 x 100 mm / 6 layers until 2026-09-23 (see board outline block, layout_pcb.py).\n"
     "STACKUP (1.6 mm, 1 oz throughout, see gen_pcb.STACKUP for the full dielectric table):\n"
     "F.Cu sig / In1.Cu GND / In2.Cu sig (CAN pair) / In3.Cu GND / In4.Cu POWER (VBAT) /\n"
     "In5.Cu sig / In6.Cu GND / B.Cu sig. Every signal layer has a solid GND plane on at\n"
     "least one face, and In2.Cu (CAN) has one on both -- a buried stripline by construction.\n"
     "Assembly is SINGLE SIDED -- nothing on B.Cu.\n"
     "FEED path (7.0 A cont, 7.8 A transient): the In4.Cu polygon is a solid /VBAT plane,\n"
     "priority 0, nothing else on the layer -- +24V, +5V and VLOGIC_IN are routed like any\n"
     "other net (see route_external.HANDS_OFF), not carved out as zones. Measured at\n"
     "106.50 mm on its worst cut against the 11.44 mm IPC-2221 asks (10 C rise, internal,\n"
     "1 oz) -- see scripts/check_plane_width.py. On F.Cu the FEED class floor is\n"
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
    # nets.  Every one of them is hand-authored in ROUTES with its own explicit width -- CAN's
    # net list below covers all four CAN nets, not just /CANH and /CANL (fault 1, fix round 2:
    # Net-(U6-CANH)/Net-(U6-CANL) used to fall through to Default and were skipped by neither
    # router only because they happened to be hand-routed anyway, not because AR_SKIP_CLASSES
    # named their class).
    #
    # That makes this number a default for interactive routing in KiCad and nothing more,
    # so it stays at the trunk's 3.5 mm: someone who pulls a tap at 3.5 mm sees the problem
    # in the first second, and someone who pulls the trunk at 0.5 mm might not.
    ("FEED", 3.5, 0.3, 0.8, 0.4,
     ["VBAT", "VBAT_PROT", "VBAT_F", "FEED_P", "MID", "SNS", "GND_IN"]),
    ("POWER", 2.0, 0.3, 0.8, 0.4, ["VLOGIC_IN", "+24V", "+5V"]),
    # CANH/CANL are the J8-D6-R26-L6 side; Net-(U6-CANH)/Net-(U6-CANL) are L6's transceiver-
    # side halves of the same electrical nets, named literally (no "/" hierarchy) because they
    # sit on the far side of the L6 choke split.  Fault 1 (fix round 2): without these two,
    # gen_netclasses.resolve()'s `n == short` arm never fires for them, they fall through to
    # Default (0.2 mm track/clearance, no diff-pair rules), and the 0.3 mm hand copper on that
    # half is legal-but-unenforced -- DRC would not object if a later change necked it down.
    ("CAN", 0.3, 0.2, 0.6, 0.3,
     ["CANH", "CANL", "Net-(U6-CANH)", "Net-(U6-CANL)"]),
]


# --------------------------------------------------------------------------- pours
# The F.Cu GND_IN island, in board coordinates.  It lives here rather than inside gen_pcb's
# zones() because two other things need the same polygon: the stitching-via generator, which
# must not drop a GND via inside it, and scripts/check_grounds.py, which reads it back off the
# board.  Shape reasoning is in zones().
#
# Rescaled for the 200 x 140 outline by moving each of the three features (see zones()) by
# the translation of the cluster it tracks, not by a single board-wide delta:
#   * the spur's top corners (36) sit on L2, which is in the "input" cluster and did not
#     move (dx = dy = 0) -- unchanged.
#   * the body (was y 53.5..94) tracks the "efuse" cluster, dy = +22, dx = 0 -- 75.5..116.
#     The spur's left edge (x 42) now runs the full 36..75.5 to reach it, crossing the
#     70..76 y-channel between the input/boost row and the efuse/rails row; that is exactly
#     what a channel is for -- it excludes parts, not copper.
#   * the strip's bottom corners (was Y1 - 0.5 = 119.5, which only equalled "just past J1"
#     because the old board's connector row sat hard against the old Y1) now track the wire
#     field instead, dy = +30 -- 149.5, which is J1's new box bottom (148.16) plus the same
#     1.34 mm the old board left below J1 (119.5 - 118.16).  Written as a literal because the
#     coincidence with the board edge that let it be `Y1 - 0.5` no longer holds: the wire
#     field stops 4 mm short of Y1.
#   * every x value is unchanged: none of the three clusters this polygon tracks (input,
#     efuse, wire) moved in x.
#
# The body's east edge does NOT carry over unchanged: D2 is auto-flowed, not hand-placed,
# and the efuse region is 8 mm wider than before (62 -> 70), so its packed position is not
# a translation of the old one. Regenerating and reading the actual pads back off the board
# (scripts/check_grounds.py, then a direct pad dump) showed the real easternmost GND_IN pad
# in this region is C64.2 at x 67.35 -- not D2, which repacked to the far west (x 29) -- so
# the east edge is 71.0: 3.65 mm past C64, and still 5.0 mm clear of the rails region at
# x 76 (more than the old edge's 2.8 mm, because rails moved right by 12 mm while this edge
# only moved out by 9). It sits 1.0 mm into the 70..76 channel, which is fine -- a channel
# keeps parts out, not copper.
GND_IN_ISLAND = [
    (42.0, 36.0), (48.0, 36.0), (48.0, 75.5), (71.0, 75.5), (71.0, 116.0),
    (46.0, 116.0), (46.0, 149.5), (22.0, 149.5), (22.0, 75.5), (42.0, 75.5),
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
# D4 moved with the rest of the boost cluster, dx = +12, dy = 0 (boost's new origin is
# (76, 23) against the old (64, 23); see PLACE).  The island is not centred on D4's own
# origin -- it is sized to the physical tab -- so it translates by the same delta, not by
# recomputing from D4's coordinate.
D4_24V_ISLAND = [(84.4, 21.7), (90.2, 21.7), (90.2, 27.4), (84.4, 27.4)]

# TIM-A spans the boost/rails column, both of which share dx = +12 (boost's origin moved
# 64 -> 76, rails' moved 64 -> 76 too), so the x edges translate by +12: 64->76, 98->110 --
# and that carries over unchanged, since it already covered D4's tab, U3's paddle (pin 17,
# at 86.0, 32.0) and L3.
#
# The y edges do NOT carry over: the old bottom (58) was sized against the auto-flowed
# U1.9/U2.9 paddles wherever the OLD, much smaller rails region (y 50..94) put them, and
# U1/U2 are not hand-placed, so that number is not a translation of anything. Reading the
# regenerated board (Step 5) back, U1.9 and U2.9 are both 2.62 x 3.51 mm pads centred at
# (98.40, 79.40) and (106.40, 79.40) -- box y 77.65..81.16, well inside the new x 76..110 --
# so the bottom edge is 82.0, half a millimetre past that, and the top stays at boost's own
# y0 (dy = 0: 23 -> 23).
#
# TIM-B tracks U9, which moved dx = +12, dy = +22 with the rest of the profet region (old
# origin (64, 82) -> new (76, 104)).
TIM_PADS = [
    ("TIM-A", 76.0, 23.0, 110.0, 82.0),
    ("TIM-B", 81.0, 104.0, 95.0, 116.0),
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

# Hand routes: (net, layer, width_mm, [(x, y), ...]).
#
# EMPTIED 2026-09-23 for the 200 x 140 re-layout.  Every entry named absolute board
# coordinates against a placement that no longer exists, so none of it could survive the
# move -- this is not a decision to hand-route less, it is the old copper being invalid.
#
# The six-layer board's routes are at tag `board/v2-6layer`, and they are worth reading
# before writing the new ones: the reasoning in their comments (why SW is 0.75 mm across
# two adjacent QFN pins, why the track stops at y 30.55 to clear U3's paddle, why the
# return half of the commutation loop is deliberately not routed) is about the circuit,
# not about the coordinates, and carries over unchanged.
#
# Refilled by Tasks 7-9: the feed chain, the CAN pair, the boost switch node.  Everything
# else on this board is the external router's -- see docs/routing-tool.md.
#
# Task 7 -- the 7 A feed chain, one direction only: J1 (bottom of the wire field) up
# through the eFuse (Q10/Q11 + U10), up through L2 and the pi filter (C65/L2/C3/L1),
# out the top of `input`.  Nothing doubles back.
#
# "Poured, never tracked": FEED's netclass width (3.5 mm) is a 20 C-rise floor sized for
# a hop of a few mm, not for a real run.  Every segment that actually carries the 7.0 A /
# 7.8 A trunk current is either >= 4.5 mm on F.Cu, or is a short stub into a FEED-class
# via (0.8/0.4 mm) that drops onto the solid In4.Cu VBAT plane -- the plane is what
# carries the bulk of the current, not the copper width of any one hand-drawn track.
# Bias/sense/gate-drive taps that do not carry trunk current (SNS, U10's gate, the
# VBAT_PROT/VBAT_F branches into R2/C1/D2) stay narrow -- 0.3-0.5 mm -- because widening
# them buys nothing and only adds clearance risk in the crowded U10 column.
#
# All geometry below was walked with show_room.py against the real DRU (FEED clearance
# 0.3 mm, FEED via 0.8/0.4) before being written here; the slack numbers quoted in each
# comment are show_room's own "tightest neighbour" figures, not eyeballed.

ROUTES = [
    # --- FEED_P trunk: J1.2 (+12V IGN-switched feed) down to Q10.2 (eFuse source) ---
    # J1's three pads sit on a 6 mm pitch at y=127.91; the only way out of the middle
    # pad (FEED_P) without touching IGN_IN (pad 1, west) or GND_IN (pad 3, east) is
    # straight down.  show_room at 4.5 mm confirms the column at x=36.85 stays legal
    # (>=2.6 mm slack to J1.1/J1.3) all the way to y=123, where the row opens up fully
    # across the whole 22-40 mm window -- that is where the trunk turns west to line up
    # with Q10's column at x=25.75.  25.75/109.6-123 was swept solid at 4.5 mm too.
    ("FEED_P", "F.Cu", 4.5, [(36.85, 127.91), (36.85, 123.0),
                              (25.75, 123.0), (25.75, 109.6)]),

    # --- MID bridge: Q10.3 (eFuse drain / half-bridge midpoint) to Q11.3 (same net) ---
    # Both pads are the same 8x10.1 mm DPAK-class tab, 1.7 mm apart edge to edge at
    # y=109.  A short, wide bridge at the netclass floor's *3.3x* (8 mm) rather than a
    # thin track: this is the highest-current single hop in the eFuse (all 7 A crosses
    # here), and there is nothing else nearby to clear -- copper is free when there is
    # nothing to avoid.  Endpoints sit 0.85 mm inside each pad's facing edge so the
    # track fully overlaps both pads' copper, not just their centrelines.
    ("MID", "F.Cu", 8.0, [(36.80, 109.0), (40.20, 109.0)]),

    # --- SNS trunk: Q11.2 (current-sense Kelvin tap) to R100.1 (sense resistor) ---
    # Low-current Kelvin line, stays at the netclass default.  y=109.5 was the first
    # try (north of Q11.1's gate pad) but gen_pcb's crossing check caught it: the
    # VBAT_PROT trunk is 4.5 mm wide and centred at y=106.0375, so its own copper
    # already reaches down to y=108.29 before any clearance is added, and 3.5 mm SNS
    # at 109.5 doesn't clear that by the required 0.3 mm once both half-widths are
    # counted.  y=110.7 puts SNS's near edge at 108.95 -- clear of the trunk by 0.66 mm.
    ("SNS", "F.Cu", 3.5, [(51.25, 108.4), (51.25, 110.7),
                           (57.0, 110.7), (57.0, 111.9625)]),

    # --- VBAT_PROT trunk: R100.2 (post-sense rail) to L2.1 (pi-filter input winding) ---
    # The one long haul on the board, and it cannot go straight: a single y for the
    # whole horizontal leg is impossible.  Crossing the GND_IN island's spur (x 42-48,
    # which starts at y=36) needs y <= 33.75; clearing D3.pad1/C1.pad1 over x 54-68
    # needs y >= ~34.6.  First attempt used one y=33.0 leg across the full x range and
    # show_room caught it colliding with both D3 and C1 -- so the leg is split in two:
    # y=33.0 while crossing the spur's x-range (37.25-48.5), y=35.5 once east of it,
    # where a fine sweep (0.25 mm step, x 48-74) came back 100% legal at 4.5 mm.
    ("VBAT_PROT", "F.Cu", 4.5, [(57.0, 106.0375), (73.0, 106.0375), (73.0, 35.5),
                                 (48.5, 35.5), (48.5, 33.0),
                                 (37.25, 33.0), (37.25, 38.0)]),

    # --- VBAT_F trunk: L2.4 (pi-filter output winding) to L1.1 (second-stage choke) ---
    # This carries the full 7.0 A continuous / 7.8 A transient the whole way -- VBAT_F
    # never drops to In4.Cu (that plane is /VBAT, a different net), so unlike every
    # other hop on this trunk there is no plane behind it.  It stays >= 4.5 mm for its
    # entire length; the fix below moves the ROUTE, not the width.
    #
    # The x=31.0 column (first tried) swept clear for the full y 27.3-50.0 span against
    # every *pad*, but gen_pcb's crossing check caught a track-vs-track conflict a pad
    # sweep can't see: L1's two pads are only 9 mm apart (26.4915 and 35.5085), the VBAT
    # link below is also 4.5 mm wide, and a 4.5 mm VBAT_F track turning at x=31.0 has a
    # rounded end-cap reaching to x=31.0+2.25=33.25 -- only 0.0085 mm short of the link's
    # own end-cap at x=35.5085-2.25=33.2585, well inside the 0.3 mm clearance floor
    # (reported: 0.008 < 0.300 mm).  Narrowing the copper there is what a first attempt
    # did, but that "short hop" turned out to be 7.5 mm of full-current trunk at 3.5 mm
    # -- a real run, not the brief's few-mm exception.
    #
    # Fixed instead by moving the turn 0.5 mm further from the link: at x=30.5 the same
    # 4.5 mm track's end-cap reaches only to 30.5+2.25=32.75, clearing the link's cap
    # edge (33.2585) by 0.5085 mm -- 0.2085 mm of margin past the 0.3 mm floor, the same
    # margin the narrowed version had, but now with full 4.5 mm copper end to end.  The
    # x=30.5 column was checked against every pad in the x 20-35 / y 25-52 window (L1.1
    # and C5 are the only two there): C5.2, the nearest, sits 4.25 mm away in x -- clear
    # by a wide margin, so the sweep result for x=31.0 still holds one column over.
    ("VBAT_F", "F.Cu", 4.5, [(37.25, 27.3), (30.5, 27.3), (30.5, 50.0), (26.4915, 50.0)]),

    # --- VBAT link: L1.2 to C3.1, then onto the In4.Cu plane via the array below ---
    # Last F.Cu hop before the feed goes onto the plane for good.  Short (6.3 mm), no
    # obstacles between the two pads at y=50.
    ("VBAT", "F.Cu", 4.5, [(35.5085, 50.0), (41.8, 50.0)]),

    # ===================== U10 Kelvin pair (SNS pin 4, VBAT_PROT pin 5) =====================
    # U10 is a 10-pad, 0.5 mm pitch part -- gen_pcb's dru_floor() relaxes clearance
    # between a hand track and a U10 *pad* to 0.18-0.2 mm for exactly this reason, but it
    # does NOT relax clearance between two hand tracks that both happen to be near U10.
    # The old 6-layer board's fix (board/v2-6layer) was to send the two pins out in
    # different directions so their escapes never run parallel: pin 5 is the south
    # corner of the column and escapes straight into open space below the part; pin 4
    # is the interior pin between pins 3 and 5, and only has a way out to the west,
    # inside the exemption band, before turning.  Both must reach C65.1 (the mandatory
    # output-bypass cap) before continuing on to the trunk -- notes_power_input.py is
    # explicit that neither line may hang a spur off the sense run instead.

    # SNS / pin 4: 0.3 mm reached only 0.075 mm clear of U10.1-3's pads once the
    # exemption's own floor (0.12 mm) is applied, and even inside the exemption the
    # round end-cap of pin 5's escape (0.5 mm pitch away) came out only 0.1 mm clear
    # of THIS track -- track-vs-track is never exempted.  The board's own track-width
    # floor is 0.2 mm, so that -- not 0.15 mm -- is as narrow as this hop can go:
    # at 0.2 mm the two pads' end-caps are exactly 0.5 - 0.2 = 0.3 mm apart, clearing
    # each other with nothing to spare, which is why this hop is kept as short as
    # possible (35.5-36.9) before widening.
    ("SNS", "F.Cu", 0.2, [(36.9, 96.5), (35.5, 96.5)]),
    # Widen to 0.5 mm only once the U10.1-3 column (west edge x=36.15) is behind by
    # >=0.3 mm even accounting for the wider cap -- the transition sits at x=35.5 so
    # the cap's east reach (35.5+0.25=35.75) still clears x=36.15 by 0.4 mm.
    # Route east at y=93 -- north of Q10.3/Q11.3/the MID bridge (all top out at
    # y=103.95-105) -- to x=48.3, which clears Q11.3's east edge (47.35) by 0.7 mm and
    # C65's west edge (49.55) by over 1 mm.  x=59.5 and x=54 (the two other gaps
    # available further east) were tried first and both failed: x=59.5 sits inside the
    # VBAT_PROT trunk's own 4.5 mm copper (x=57-73), and x=54 sits inside VBAT_PROT's
    # C65-to-trunk jog (x=51.3-57 at y=103.5).
    ("SNS", "F.Cu", 0.5, [(35.5, 96.5), (35.5, 93.0), (48.3, 93.0), (48.3, 98.5)]),
    # x=48.3 also crosses VBAT_PROT's OTHER jog -- pin 5's run from its own escape to
    # C65 sits at y=99.5, spanning x=36.9-51.3, which x=48.3 is inside.  SNS carries no
    # real current, so a two-via hop to duck under it on In5.Cu (clear here -- the
    # FEED_P taps' In5.Cu columns are at x=24/41/59.5, none of them 48.3) is cheaper
    # than hunting for a third F.Cu gap.
    ("SNS", "In5.Cu", 0.5, [(48.3, 98.5), (48.3, 100.5)]),
    ("SNS", "F.Cu", 0.5, [(48.3, 100.5), (48.3, 109.0), (57.0, 109.0), (57.0, 111.9625)]),

    # VBAT_PROT / pin 5: straight south into open space below the part.  The corner
    # pin has no U10 neighbour on that side, but pin 4's escape (above) starts only
    # 0.5 mm away at the shared column x=36.9 -- same fix, 0.2 mm (the board's track-
    # width floor) for the first hop so the two tracks' end-caps clear each other by
    # exactly 0.3 mm instead of colliding.
    ("VBAT_PROT", "F.Cu", 0.2, [(36.9, 97.0), (36.9, 97.6)]),
    # This short riser used to stay on F.Cu (widening to 0.5 mm at y=97.6, straight down
    # to y=99.5).  Measured with pcbnew's own zone filler (KiCad's bundled python,
    # ZONE_FILLER on the refilled board) that this is exactly what split GNDIN_F: with
    # this riser plus the y=99.5 jog below plus SNS's y=93 crossbar (ROUTES entries
    # 7/11/12) all present, the filler reported a second, orphaned island at bbox
    # x=[37.450,47.749] y=[93.550,98.950] -- 2700 vs 188 points, i.e. a real disconnected
    # pocket, not a rounding artefact.  Every one of those four bbox edges lands exactly
    # on a hand-track clearance offset (track edge + 0.3 mm): 93.55 = SNS's y=93 line +
    # 0.55, 47.75 = SNS's x=48.3 line - 0.55, 37.45 = this riser's x=36.9 line + 0.55,
    # 98.95 = the y=99.5 jog below - 0.55.  U10's own pads close the pocket's fourth
    # (west) side between SNS's escape (y=96.5) and this riser's start (y=97.6) -- U10
    # is fixed, not ours to move -- so SNS's crossbar (top+right) and this riser plus the
    # jog below (bottom+left) are the only two hand-routed sides of a closed ring around
    # that pocket, which is why removing any *one* of ROUTES 7/11/12 alone reopened it in
    # ablation but sliding any of the three sideways within the same F.Cu did not: the
    # ring just moved, it didn't open.  (Confirmed both directions per the review's
    # instruction: deleting all three or moving VBAT_PROT's own trunk joint at line ~696
    # left the split in place until this riser specifically was touched; restoring the
    # riser to F.Cu brought the second island straight back.)
    #
    # Fix: take this riser off F.Cu instead, so it can no longer form one wall of the
    # ring.  Two vias (0.8/0.4 mm, matching every other F.Cu<->In5.Cu hop on this net)
    # drop it to In5.Cu for the same x/y run -- clear there: FEED_P's In5.Cu columns are
    # at x=24/41/59.5, MID's B.Cu jog is at x=43.35, SNS's own In5.Cu duck-under is at
    # x=48.3, none of them x=36.9.  Re-verified with the same pcbnew filler: 1 island,
    # bbox x=[22,71] y=[36,149.5] -- the whole zone, GNDIN_F whole again.
    #
    # This also answers the review's Important-3 concern (SNS pin 4's 0.2 mm escape vs
    # this pin's own 0.2 mm hop above, stacking both the width and clearance floors at
    # once): moving pin 5 to an inner-layer via sooner, as the review suggested, was
    # tried and measured worse, not better.  The two 0.2 mm hops' own end-caps (fixed by
    # U10's 0.5 mm pin pitch, at 36.9/96.5 and 36.9/97.0-97.6) are unreachable by any
    # layer choice downstream -- both leave F.Cu straight off their pads before a via is
    # legal, and stadium-distance between them is exactly 0.500 mm centre-to-centre,
    # 0.300 mm edge-to-edge against a 0.300 mm floor: zero slack either way.  Pulling
    # *this* via closer to pin 5 (shrinking the 0.2 mm hop above instead of this 0.5 mm
    # one) does not help either -- a 0.8/0.4 mm via's radius (0.4 mm) needs more clearance
    # from SNS's crossbar than the 0.2 mm track it replaces (0.1 mm half-width) would, so
    # the via fight starts *before* the track fight does: y=97.2 fails gen_pcb's own
    # clearance check outright (0.200 < 0.300, SNS ROUTES[6] vs this via), y=97.4 and
    # above pass.  y=97.6 (here) already clears that floor by 0.2 mm; there is nothing
    # left to recover by moving the via closer, so the 0.2 mm escape stays as authored.
    ("VBAT_PROT", "In5.Cu", 0.5, [(36.9, 97.6), (36.9, 99.5)]),
    # East to C65.1 -- this is the mandatory bypass stop, reached before the trunk.
    ("VBAT_PROT", "F.Cu", 0.5, [(36.9, 99.5), (51.3, 99.5), (51.3, 98.0)]),
    # From C65.1 on to the trunk start (R100.2 / VBAT_PROT trunk's own origin point).
    ("VBAT_PROT", "F.Cu", 0.5, [(51.3, 98.0), (51.3, 103.5),
                                 (57.0, 103.5), (57.0, 106.0375)]),

    # ===================== Gate-drive / bias taps off the FEED_P trunk =====================
    # Same technique for all three: a short F.Cu stub to clear the part's own
    # neighbours, a FEED via down to In5.Cu (the spare signal layer not claimed by
    # In4.Cu's VBAT pour or In2.Cu's Task-8 CAN pair), a haul at a dedicated y-lane so
    # the three taps can't foul each other, and a second via landing back on the F.Cu
    # trunk.  Each tap lands on its own y (114/116/118 mm) at the trunk's x=25.75
    # column, 2 mm apart -- same net, so no via-via clearance is even required, but
    # keeping them apart avoids three vias trying to share one drill spot.

    # R104.1 (FEED_P into the VCC10 bias divider): stub clear of R106 (the other pad
    # on this footprint's row, 4.5 mm away) then to the via.
    ("FEED_P", "F.Cu", 0.5, [(24.255, 83.83), (24.0, 83.83), (24.0, 86.0)]),
    ("FEED_P", "In5.Cu", 0.5, [(24.0, 86.0), (24.0, 114.0), (25.75, 114.0)]),

    # Q12.2 (FEED_P into the gate-drive PNP emitter): stub south from the pad, clear of
    # Q12's own pad 3 (Q10_G) 1.9 mm to the east.
    ("FEED_P", "F.Cu", 0.5, [(42.5925, 79.75), (42.5925, 81.0), (41.0, 81.0)]),
    ("FEED_P", "In5.Cu", 0.5, [(41.0, 81.0), (41.0, 116.0), (25.75, 116.0)]),

    # R105.1 (FEED_P into the second bias divider): stub clear of D22 (Net-D22-A,
    # 1.05 mm south-east) before dropping.
    ("FEED_P", "F.Cu", 0.5, [(59.9175, 78.23), (59.5, 79.0), (59.5, 80.0)]),
    ("FEED_P", "In5.Cu", 0.5, [(59.5, 80.0), (59.5, 118.0), (25.75, 118.0)]),

    # R101.1 (MID sense-divider tap): on B.Cu, not In5.Cu -- a separate layer from the
    # three FEED_P taps above means this haul never needs checking against them for
    # crossings.  Via sits directly on Q11.3's own MID pad (no F.Cu stub needed there);
    # the far via lands directly on R101.1's pad.
    ("MID", "B.Cu", 0.5, [(43.35, 109.0), (43.35, 90.5), (53.9175, 90.5), (53.9175, 78.23)]),

    # D2.1 (VBAT_PROT into the input clamp diode): In5.Cu again, but routed south to
    # y=121 -- below all three FEED_P taps' lowest lane (118) -- before crossing east,
    # so it can never touch them even though it shares their layer and is a foreign net
    # there.  Final vertical at x=65 lands on the VBAT_PROT trunk's y=106.0375 leg.
    ("VBAT_PROT", "F.Cu", 0.5, [(25.1, 79.35), (22.5, 79.35)]),
    ("VBAT_PROT", "In5.Cu", 0.5, [(22.5, 79.35), (22.5, 121.0),
                                   (65.0, 121.0), (65.0, 106.0375)]),

    # ===================== VBAT_F / VBAT_PROT bias taps near L2/L1 =====================
    # R2 bridges VBAT_PROT to VBAT_F (bias divider across the eFuse's pi-filter choke);
    # C1 filters VBAT_F.

    # R2.1 (VBAT_PROT): the direct In5.Cu hop straight to the trunk's y=35.5 leg would
    # cross R2.2/C1.1's own In5.Cu haul below at x=55.4675 (both nets share that x on
    # the same layer) -- gen_pcb's crossing check caught it.  B.Cu is otherwise unused
    # in this x/y region (the only other B.Cu run, R101's MID tap, stays south of
    # y=78), so R2.1 moves there instead of adding a detour.
    ("VBAT_PROT", "B.Cu", 0.5, [(55.4675, 25.53), (55.4675, 35.5)]),

    # R2.2 and C1.1 (both VBAT_F): the first attempt hauled each straight north to
    # y=27.3 and west to the trunk -- but L2.3 (GND, a foreign net) sits at
    # (44.75, 27.3), directly in that path, and C1.1's own straight run north also
    # grazed the VBAT (/VBAT) via dropped for C2.1 four columns over.  Merged instead:
    # C1.1 jogs 1.5 mm west (clearing D3.2's via by >=0.7 mm) before turning north,
    # landing directly on R2.2's own pad (same net) rather than routing them in
    # parallel.  From R2.2, a single haul at y=29.3 clears D3.2 (its near edge is
    # 29.95, giving 0.4 mm) and L2.3 (0.775 mm) on the way to x=34.0, which lands on
    # the VBAT_F trunk's own y=27.3 leg (inside its x 31.0-37.25 span).
    ("VBAT_F", "In5.Cu", 0.5, [(63.805, 31.83), (62.3, 31.83),
                                (62.3, 25.53), (61.3925, 25.53)]),
    ("VBAT_F", "In5.Cu", 0.5, [(61.3925, 25.53), (61.0, 25.53), (61.0, 29.3),
                                (34.0, 29.3), (34.0, 27.3)]),

    # ===================== Task 8: CAN pair, buried stripline on In2.Cu =====================
    # Four nets -- the choke L6 splits each side in half.  Not routed as a literal chain: the
    # long haul below lands J8 directly on L6 (CANH on L6.4, CANL on L6.3), and D6 (the ESD
    # protection) and R26 are reached by short hops and a stub off that same copper, not by
    # passing through them in series -- see the "D6 -> R26 -> L6 cluster" comment further down
    # for why, and gen_mcu_can.py around lines 341-351 for why: R26 is a DNP 120-ohm shunt
    # straight across the CANH/CANL labels, not a series split termination.  All twelve pad
    # coordinates are the brief's measured figures, used verbatim.
    #
    # In2.Cu is empty apart from via barrels, so there is no F.Cu-style footprint/silk field to
    # dodge, but it is not obstacle-free either: 141 ground-drop vias land on it (gnd_drops(),
    # placed without knowledge of hand-route geometry), and clearing them is most of what shapes
    # the paths below -- see the long-haul corridor and the CANH_stub reroute in particular.
    # Every pad here (D6/R26/L6/U6) is SMD F.Cu-only -- J8 is the sole through-hole pad, so it
    # is the only one that reaches In2.Cu without a via, per ROUTE_VIAS below.
    #
    # J8 -> L6 ("/CANH", "/CANL"): the long haul. Landing on L6.4/L6.3 instead of D6.1/D6.2 is
    # the fix-round-1 finding: all four pads on each of CANH/CANL are the same net (J8, D6, R26,
    # L6 for CANH; same set for CANL), so which of them the haul lands on is a free choice, and
    # D6 stays reached through the CANH_main/CANL_main hop below either way. Landing on L6
    # instead of D6 keeps the 160 mm haul away from the D6/Q2/R26 cluster entirely, which is
    # where fix round 1 found the haul crossing CANL_main (a -0.300 mm overlap) and clipping
    # L6.3's own via (0.000 mm).
    #
    # A single straight J8->L6 segment clears that cluster but grazes several ground-drop vias
    # that a straight line happens to pass near mid-board (this board has 141 of them, placed
    # without knowledge of hand-route geometry). For CANH: one near 111.9,96.4, a denser run of
    # them spanning roughly 148,64 to 163,53 (a stitching field, not a single obstacle -- see
    # below), one near 175.8,46.1, and L6.2's own via right at the L6 approach -- and the L6.2
    # via sits on the *other* side of the baseline from the rest, so no single global offset
    # clears everything (shifting toward the others worsens L6.2). CANL grazes one, near
    # 167.4,55.5. Verified by `AR_SKIP=1 python scripts/gen_pcb.py` exiting 0: it checks the
    # CANH/CANL long haul against every pad and via on the board with exact rectangle
    # geometry and refuses to write the board if any of these grazes is actually short.
    #
    # The 148,64 - 163,53 stretch is not one via to bow around but a field of ground-drop vias
    # spaced 1.5-4 mm apart (the generator's own placement, not something this file controls),
    # so a single symmetric bump kept re-clipping whichever via ended up nearest its new
    # position -- each retry moved the offending via too, since gnd_drops() places every via at
    # the closest still-legal spot to its own pad given whatever the current hand route excludes,
    # so nudging the track just re-hugs the same ~0.1 mm short. Solved by treating it as a
    # corridor problem instead of a tuning problem: a script in the task's scratchpad dumped the
    # real via list gen_pcb.py places against this file's current track (importing gen_pcb.py
    # and calling its own pipeline up through gnd_drops(), the same functions the real gate
    # uses), then searched that obstacle field for a legal path with a Dijkstra search over a
    # fine grid along the corridor, and simplified the result to the fewest straight segments
    # that stay clear. The three-segment result below threads between the via rows with 0.36 mm
    # of clearance at its tightest point against the 0.20 mm the CAN netclass needs -- comfortably
    # past the ~0.1 mm the circle-vs-box placement/validation mismatch above can cost.
    #
    # The J8 breakout no longer converges the pair between J8's own pads either (fix round 1's
    # second finding, the 0.047/0.000 mm clashes against J8.2): heading for L6 from J8.1 leaves
    # J8.2 clear immediately (the line's slope carries it well north of J8.2 by the time it
    # reaches J8.2's own x), and the same holds in reverse for CANL against J8.1.
    ("CANH", "In2.Cu", 0.3, [(67.400, 130.590),
                              (108.4799, 97.2453), (113.5269, 93.2737),
                              (149.4137, 66.0515),
                              (154.3646, 62.1555),
                              (162.5813, 54.1626),
                              (167.0782, 52.1509),
                              (172.4254, 46.9251), (177.4724, 42.9535),
                              (187.5212, 37.0818), (192.5682, 33.1102),
                              (193.575, 31.300)]),
    ("CANL", "In2.Cu", 0.3, [(72.000, 130.590),
                              (164.0568, 56.2779), (168.9198, 52.4063),
                              (193.575, 33.800)]),

    # D6 -> R26 -> L6 cluster ("/CANH", "/CANL"): NOT routed as a literal D6->R26->L6 chain.
    # A first attempt at that (each hop a straight offset-parallel pair, as the J8->D6 haul
    # above is built) fails geometrically, not from a tuning mistake: D6's and L6's pad pairs
    # are north/south of each other (D6.1/L6.4 north, D6.2/L6.3 south) while R26's pad pair is
    # west/east of each other (R26.1 west, R26.2 east) -- a 90-degree mismatch in pair
    # orientation.  An exhaustive grid search over every candidate single-bend point for a
    # D6->R26 hop (scratchpad can_route6.py) found none that keep CANH and CANL from crossing
    # once the R26->L6 hop is added back in -- the chain reading of the brief's pad table
    # is geometrically unroutable on one layer as a plain 3-node chain.
    #
    # gen_mcu_can.py resolves this: R26 is a DNP 120-ohm bus terminator wired as a shunt
    # directly across the CANH and CANL labels (`w((284.48,109.22),(284.48,114.3)); lab("CANH",..)`
    # ... `vpart("R26",...,dnp=True)` ... `w(b,(284.48,127.0)); lab("CANL",..)`), not an inline
    # series element in either leg. Electrically the only copper that has to be continuous is
    # D6.1-L6.4 (CANH) and D6.2-L6.3 (CANL); R26's pads are branch stubs off that copper, not
    # waypoints on it. So each net is routed as a short direct D6->L6 main line plus a stub off
    # D6's pad down to R26 -- this does not move or re-place anything (Ruling 2's "route it as
    # placed" is about footprints, none of which move here), it only changes which pad-to-pad
    # copper path realises the same three pads.
    #
    # CANH_main (D6.1 -> L6.4) and CANL_main (D6.2 -> L6.3): the direct hop, unaffected by R26.
    ("CANH", "In2.Cu", 0.3, [(197.093, 31.350), (193.575, 31.300)]),
    ("CANL", "In2.Cu", 0.3, [(197.093, 33.250), (193.575, 33.800)]),

    # CANH_stub (D6.1 -> R26.1): fix round 1 found the predecessor's direct-ish two-bend detour
    # clashing four ways -- both of CANL_stub's own duck-under vias (0.165, 0.134) and two
    # pre-existing GND vias (0.136, 0.081) -- because it was checked against CANL_stub's and
    # CANH_main's segments but never against vias. Re-routed as a wide loop instead of a tight
    # weave: any path threading directly between D6/Q2 and R26 has to cross either CANL_stub's
    # D6.2->via_in leg or CANL_main (D6.2->L6.3) -- both start at D6.2 and fan out south/west,
    # boxing in the direct gap -- so this stub goes the other way: north over the D6/Q2 row,
    # east past R26.2, then south and back west underneath the whole R26 row to reach R26.1 from
    # the south. The first attempt at the north leg (y=29.5) ran into the L6->U6 hop's own
    # Net-(U6-CANH) lane below, which also passes over this row at y=29.55 -- moved to y=30.3,
    # the gap between that lane and Q2's own pads. Verified clear of D6.2/D6.3, all three Q2
    # pads, R26.2, CANL_stub's two vias and In2.Cu segments, CANL_main, both Net-(U6-...) lanes,
    # and the two GND vias named in the fix-round-1 report, by `AR_SKIP=1 python
    # scripts/gen_pcb.py` exiting 0 against this shape -- the same exact-rectangle clearance
    # gate that would refuse to write the board over any of those.
    ("CANH", "In2.Cu", 0.3, [(197.093, 31.350), (197.093, 30.300),
                              (209.800, 30.300), (209.800, 45.900),
                              (206.755, 45.900), (206.755, 43.330)]),

    # CANL_stub (D6.2 -> R26.2): a direct In2.Cu line from D6.2 to R26.2 threads the same narrow
    # D6/Q2/GND-via gap that CANH_stub's original (pre-fix-round-1) shape ran through, so this
    # stub ducks under that gap on In5.Cu for its middle third instead -- the same one-net
    # layer-hop pattern already used for SNS elsewhere in this file. In5.Cu is empty in this
    # region (confirmed directly from the board and with show_room.py). CANH_stub itself was
    # rerouted around the outside of this cluster in fix round 1 and no longer runs near here at
    # all, so this duck-under is no longer load-bearing against CANH_stub specifically, but it is
    # still what gets D6.2 -> R26.2 past D6.3, Q2 and the GND via, so it stays. A straight
    # via_in->via_out run on In5.Cu still clipped that GND via by 0.083 mm (its position on this
    # layer is the same barrel as on In2.Cu, since these are through vias) -- bowed 0.5 mm off
    # the straight line for the two waypoints nearest the via to clear it. Verified clear of
    # D6.3, Q2.1-3, the GND via, CANH_main and the rerouted CANH_stub by `AR_SKIP=1 python
    # scripts/gen_pcb.py` exiting 0: it checks this bow against every pad and via on the
    # board and refuses to write the board if any of the four is actually short.
    ("CANL", "In2.Cu", 0.3, [(197.093, 33.250), (201.7965, 37.4413)]),
    ("CANL", "In5.Cu", 0.3, [(201.7965, 37.4413),
                              (203.5759, 39.0268), (204.6297, 39.2962),
                              (205.0183, 40.3122), (206.6046, 41.7257)]),
    ("CANL", "In2.Cu", 0.3, [(206.6046, 41.7257), (208.405, 43.330)]),

    # L6 -> U6 ("Net-(U6-CANH)", "Net-(U6-CANL)"): the transceiver side, L6 pins 1/2 to U6's
    # CANH/CANL pins. L6.1/L6.2 sit at very nearly the same y as D6.1/D6.2 (the CANH_main/
    # CANL_main hop above), so a path that runs alongside that hop east would thread directly
    # through D6's own pads (including D6.3) and Q2 -- the same cluster the D6/R26/L6 stubs
    # above already have to route around. Instead this hop goes north of the whole D6/Q2/R26
    # cluster and the SW1/SW2 button footprints (whose pads run up to y=28.2), then drops down
    # into U6.7/U6.6 from the east side of the U6 footprint, which is clear. Net-(U6-CANH) and
    # Net-(U6-CANL) bend together (both turn at the lane transitions) but are not a fixed
    # distance apart: measured off these coordinates, they run 0.650 mm centre-to-centre for
    # 26.875 mm of the horizontal leg, then 0.700 mm apart for the 2.115 mm vertical leg into
    # U6, out of Net-(U6-CANH)'s 33.365 mm total. Both figures clear the CAN class's own
    # 0.3 mm track / 0.2 mm clearance, whose minimum centre-to-centre is 0.5 mm (0.6 mm is the
    # class's via diameter, not a pair-spacing figure), with margin to also clear L6.1's own pad
    # on the way up. Fix round 1 found the CANL lane (originally x=217.300) only 0.15 mm clear of
    # a GND via at (218.00, 32.07) -- 0.7 mm off a via that needs 0.2 mm clearance plus its own
    # and the track's half-widths. Both lanes are shifted 0.7 mm west (216.600 -> 215.900 for
    # CANH, 217.300 -> 216.600 for CANL) so the pair spacing is unchanged and the CANL lane clears
    # that via by a further 1.4 mm.
    ("Net-(U6-CANH)", "In2.Cu", 0.3, [(189.025, 31.300), (189.025, 29.550),
                                       (215.900, 29.550), (215.900, 31.665),
                                       (213.275, 31.665)]),
    ("Net-(U6-CANL)", "In2.Cu", 0.3, [(189.025, 33.800), (187.700, 33.800),
                                       (187.700, 28.900), (216.600, 28.900),
                                       (216.600, 32.935), (213.275, 32.935)]),
]

# Hand vias: (net, x, y, diameter_mm, drill_mm).  Emptied with ROUTES -- see above.
#
# FEED class via = 0.8 mm / 0.4 mm throughout (netclass default).  Rule of thumb from
# the brief: one 0.8/0.4 via is good for roughly 1-2 A, so anywhere the full 7 A
# transitions between F.Cu and the In4.Cu plane gets 6 vias in parallel (comfortably
# covers 7.8 A transient even assuming the low end of that per-via figure); taps that
# carry only a fraction of the trunk current (bias/gate-drive/sense) get a single via.
ROUTE_VIAS = [
    # VBAT link array: 6 vias in parallel for the full 7 A F.Cu-to-plane transition,
    # in the open pocket between L1.2 (east edge x=37.10) and C3.1 (west edge x=39.60).
    # Two x-columns (37.9, 38.85) each clear their neighbour's pad by >=0.35 mm; three
    # y-rows (48.7/50.0/51.3) straddling the link track's own y=50 -- all same net, so
    # no via-via clearance applies, the spacing is only to avoid drilling on top of
    # each other.
    ("VBAT", 37.9, 48.7, 0.8, 0.4), ("VBAT", 38.85, 48.7, 0.8, 0.4),
    ("VBAT", 37.9, 50.0, 0.8, 0.4), ("VBAT", 38.85, 50.0, 0.8, 0.4),
    ("VBAT", 37.9, 51.3, 0.8, 0.4), ("VBAT", 38.85, 51.3, 0.8, 0.4),

    # SNS's local In5.Cu duck under VBAT_PROT's pin-5-to-C65 jog at x=48.3/y=99.5 (see
    # ROUTES above) -- netclass default via since this is a sense line, not a trunk
    # current path.
    ("SNS", 48.3, 98.5, 0.8, 0.4), ("SNS", 48.3, 100.5, 0.8, 0.4),

    # VBAT_PROT pin 5's own short riser (x=36.9, y=97.6-99.5) taken to In5.Cu -- see the
    # comment on that ROUTES entry above for why (it closed one side of the ring that
    # split the GNDIN_F zone fill). Netclass default via, same size as SNS's pair above.
    ("VBAT_PROT", 36.9, 97.6, 0.8, 0.4), ("VBAT_PROT", 36.9, 99.5, 0.8, 0.4),

    # Gate-drive / bias taps: single via each, F.Cu <-> In5.Cu.
    ("FEED_P", 24.0, 86.0, 0.8, 0.4), ("FEED_P", 25.75, 114.0, 0.8, 0.4),
    ("FEED_P", 41.0, 81.0, 0.8, 0.4), ("FEED_P", 25.75, 116.0, 0.8, 0.4),
    ("FEED_P", 59.5, 80.0, 0.8, 0.4), ("FEED_P", 25.75, 118.0, 0.8, 0.4),
    ("MID", 43.35, 109.0, 0.8, 0.4), ("MID", 53.9175, 78.23, 0.8, 0.4),
    ("VBAT_PROT", 22.5, 79.35, 0.8, 0.4), ("VBAT_PROT", 65.0, 106.0375, 0.8, 0.4),
    ("VBAT_PROT", 55.4675, 25.53, 0.8, 0.4), ("VBAT_PROT", 55.4675, 35.5, 0.8, 0.4),
    ("VBAT_F", 63.805, 31.83, 0.8, 0.4), ("VBAT_F", 34.0, 27.3, 0.8, 0.4),
    ("VBAT_F", 61.3925, 25.53, 0.8, 0.4),

    # VBAT decoupling caps scattered across the board: each just needs its own
    # single via, dropped exactly at the pad's own centre so there is no F.Cu stub at
    # all (via-on-own-pad has no clearance issue with that pad).  Checked against each
    # part's own neighbour pad by margin arithmetic -- all clear.
    ("VBAT", 60.1, 30.85, 0.8, 0.4),     # D3.2
    ("VBAT", 64.35, 28.58, 0.8, 0.4),    # C2.1
    ("VBAT", 64.425, 24.75, 0.8, 0.4),   # C4.1
    ("VBAT", 81.175, 32.4, 0.8, 0.4),    # R16.1
    ("VBAT", 82.85, 88.08, 0.8, 0.4),    # C13.1
    ("VBAT", 106.32, 79.165, 0.8, 0.4),  # U2.2
    ("VBAT", 94.185, 28.6, 0.8, 0.4),    # L3.1
    ("VBAT", 96.725, 28.6, 0.8, 0.4),    # C18.1
    ("VBAT", 96.725, 32.2, 0.8, 0.4),    # C19.1
    ("VBAT", 108.925, 85.25, 0.8, 0.4),  # C12.1
    ("VBAT", 142.85, 50.58, 0.8, 0.4),   # C46.1
    ("VBAT", 160.925, 25.2, 0.8, 0.4),   # C45.1

    # Task 8: CAN pair F.Cu -> In2.Cu transitions.  Every SMD pad on the chain (D6, R26, L6,
    # U6 -- J8 is through-hole and needs none) gets one via dropped exactly at the pad's own
    # centre, the same "no F.Cu stub" technique as the VBAT decoupling caps above: via-on-own-
    # pad has no clearance issue with that pad, and it is what "drop to In2.Cu as soon as it
    # leaves its pad" means when the pad is the top of the via.  0.8/0.4 mm throughout, per the
    # signal-via size used for the feed's own risers -- the CAN netclass's own default via
    # (0.6/0.3) is left as the interactive-routing default only, same as every hand via on this
    # board.  The tightest neighbour on any of these footprints is U6.6/U6.7 against U6's own
    # pins 5/8: 1.27 mm pad-centre pitch against a 0.4 mm via radius and a 0.3 mm pad
    # half-height. Verified clear of every same-footprint neighbour (D6.3, R26's own opposite
    # pad, L6's other three pads, U6's pins 5/8) by `AR_SKIP=1 python scripts/gen_pcb.py`
    # exiting 0: it checks every hand via against every pad and via with exact rectangle
    # geometry and refuses to write the board if any of these six is actually short.
    ("CANH", 197.093, 31.350, 0.8, 0.4),               # D6.1
    ("CANL", 197.093, 33.250, 0.8, 0.4),               # D6.2
    ("CANH", 206.755, 43.330, 0.8, 0.4),               # R26.1
    ("CANL", 208.405, 43.330, 0.8, 0.4),               # R26.2
    ("CANH", 193.575, 31.300, 0.8, 0.4),               # L6.4
    ("CANL", 193.575, 33.800, 0.8, 0.4),               # L6.3
    ("Net-(U6-CANH)", 189.025, 31.300, 0.8, 0.4),      # L6.1
    ("Net-(U6-CANL)", 189.025, 33.800, 0.8, 0.4),      # L6.2
    ("Net-(U6-CANH)", 213.275, 31.665, 0.8, 0.4),      # U6.7
    ("Net-(U6-CANL)", 213.275, 32.935, 0.8, 0.4),      # U6.6

    # CANL_stub's In5.Cu duck-under (see the ROUTES comment above the D6/R26/L6 cluster): the
    # two layer-transition vias that bracket the stretch of CANL_stub where a direct D6.2->R26.2
    # line would clip D6.3, Q2 or the GND via.  Also 0.8/0.4 mm, same as every other hand via here.
    ("CANL", 201.7965, 37.4413, 0.8, 0.4),             # CANL_stub via_in  (In2.Cu -> In5.Cu)
    ("CANL", 206.6046, 41.7257, 0.8, 0.4),             # CANL_stub via_out (In5.Cu -> In2.Cu)
]


# Nets whose frozen router copper is thrown away, so that ROUTES above is their only source.
#
# scripts/routes_signal.json is generated by scripts/freeze_routes.py from the external
# router's output and is never hand-edited.  When the router fails a net it can still leave a
# stub behind -- a fanout via dropped inside a pad with no track ever laid on it -- and that
# stub is a dangling-via DRC item that no amount of hand routing elsewhere will clear.  Naming
# a net here makes gen_pcb.py skip every frozen segment and via on it, so what this file says
# about that net is what the board has.
#
# EMPTIED 2026-09-23 with ROUTES -- see above.  routes_signal.json itself is deleted, so there
# is no frozen copper left for this to act on.
FROZEN_DROP = ()
