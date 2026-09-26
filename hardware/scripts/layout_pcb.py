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
    # placed without knowledge of hand-route geometry). Fix round 2's long haul threaded between
    # them one dodge at a time (CANH picking up 10 interior bends against CANL's 2, spacing
    # ranging 1.027-4.600 mm centre-to-centre) -- work fix round 3 undoes, because gnd_drops()
    # runs *after* the hand routes and refuses to place any drop that clashes with hand copper
    # (via_ok()): those vias were never fixed obstacles, so dodging them just chased a target
    # that would have moved out of the way on its own.
    #
    # J8 -> L6 ("/CANH", "/CANL"): the long haul, now routed as a true matched pair. Landing on
    # L6.4/L6.3 instead of D6.1/D6.2 is the fix-round-1 finding: all four pads on each of
    # CANH/CANL are the same net (J8, D6, R26, L6 for CANH; same set for CANL), so which of them
    # the haul lands on is a free choice, and D6 stays reached through the CANH_main/CANL_main
    # hop below either way. Landing on L6 instead of D6 keeps the 160 mm haul away from the
    # D6/Q2/R26 cluster entirely.
    #
    # The pair's shared centreline is the straight line J8.1 (67.400, 130.590) ->
    # L6.4 (193.575, 31.300), 160.557 mm at a bearing of 38.2 deg. When this pair was laid, the
    # only obstacles along that line that could not move were twelve 0.55 mm /VBAT thermal vias
    # -- a 3-wide by 4-deep grid at x 87.1/88.0/88.9, y 108.425/109.475/110.525/111.575, landing
    # 27.2-30.6 mm along the run and offset 1.647..5.236 mm from the centreline. A pair at
    # 0.650 mm centre-to-centre needs the centreline to stay 0.950 mm clear of a via that size
    # (0.325 pair half + 0.150 track half + 0.200 CAN clearance + 0.275 via half), so even the
    # closest of the twelve clears with 0.697 mm to spare and no deviation at all: measured
    # copper-to-copper, CANH passes it at 0.897 mm and CANL at 1.547 mm. Every ground-drop via
    # near the straight line moves for the pair anyway (via_ok()).
    #
    # THAT IS NO LONGER THE BINDING CLEARANCE. Task 10 froze an external router's copper into
    # scripts/routes_signal.json, and it put 857 vias on the board -- after these two tracks
    # were placed, and around them, because it treated them as fixed obstacles. Those vias
    # cannot move either: they are frozen data, not a search. Re-measured against all 857 plus
    # every generator via -- 13790 track-vs-via measurements for CANH and 13770 for CANL, disc
    # model, gen_pcb._seg_disc_gap:
    #
    #   CANH worst 0.2003 mm -- /+3V3_SW via d=0.60 at (158.100, 57.975), 0.200 mm required
    #   CANH next  0.2123 mm -- /outputs/MUXIN_FR_R via d=0.60 at (178.000, 42.300)
    #   CANL worst 0.2036 mm -- Net-(U9-IN1) via d=0.60 at (90.700, 113.500), 0.200 mm required
    #   CANL next  0.2037 / 0.2047 / 0.2187 mm -- /I2C_SDA (157.225, 61.150),
    #              /outputs/MUXIN_FL_R (161.325, 57.925), /outputs/MUXIN_FL_G d=0.50
    #              (163.300, 56.325)
    #
    # Nothing is short, and KiCad's DRC agrees (0 violations). But CANH is at the floor with
    # 0.00032 mm of margin -- 0.32 um on a 0.200 mm class limit -- and five more clearances sit
    # within 0.019 mm of it. There is nothing left to give anywhere along this pair. Do not tighten
    # the CAN clearance, do not widen these tracks, and do not nudge either polyline: any of
    # those makes the board fail, and the failure will name a via you cannot move.
    #
    # The ruling (task-10-step6-ruling.md) was to accept 0.2003 mm rather than re-route: the
    # router placed those vias to the netclass rule, KiCad agrees they are legal, and CAN here
    # is a terminated differential bus at motorcycle bit rates where a 0.6 mm via at 0.2 mm is
    # electrically irrelevant. Moving the pair means re-running the router and discarding 4692
    # frozen segments to buy nothing.
    #
    # The VBAT-grid and L6.2 figures below were re-measured under the same disc model and are
    # unchanged to the digit; they are simply no longer the tightest thing on the run.
    #
    # Each track is offset +-0.325 mm from that centreline (perpendicular to its 38.2 deg
    # bearing), so CANH and CANL hold an exact constant 0.650 mm centre-to-centre and never
    # move independently -- there is nothing to "turn together" because there is nothing to
    # turn, for as much of the run as the centreline model holds. At the J8 end it holds all
    # the way in: the fan-in bend sits 2 mm off the pads (J8.2's keepout constrains CANH's fan
    # to x <= 70.50 while y is in its 129.5-132.0 band -- this fan point lands at x = 68.77,
    # comfortably inside it -- CANL leaves from J8.2 itself so its own pad constrains it not at
    # all).
    #
    # At the L6 end the centreline model runs into a real fixed obstacle the brief's corridor
    # scan did not name: L6.2's own via (Net-(U6-CANL), (189.025, 33.800), part of the
    # untouched L6->U6 transceiver leg below, so it cannot move). It sits 0.849 mm off the
    # centreline, 155.4 mm along the run. That is OUTSIDE CANH's +-0.325 mm offset, so the pure
    # offset line does not overlap it -- but it does not clear it either: CANH's copper would
    # span 0.175..0.475 mm off the centreline and the via's spans 0.549..1.149, leaving a
    # 0.074 mm gap where the CAN netclass requires 0.200. Short by 0.126 mm, which
    # `AR_SKIP=1 python scripts/gen_pcb.py` refuses to write. CANL's own offset line passes the
    # via on the far side at 1.112 mm of copper gap and is untouched.
    #
    # So CANH's matched-pair section ends at 154.000 mm along the centreline (bend point H2) and
    # the last 6.600 mm to L6.4 threads south of the via and back north through one extra
    # waypoint (H3): H2->H3 is 1.494 mm and H3->L6.4 is 5.106 mm. Those two legs clear L6.2's
    # via by 0.399 mm and 0.428 mm respectively, against the 0.200 mm the CAN class requires --
    # a legitimate L6-approach deviation, not a ground-drop dodge. Shortening the matched
    # section costs nothing mid-run: the VBAT grid above is passed at 28-31 mm, far inside the
    # section that still holds, so its 0.897 mm clearance is unaffected. CANL keeps a plain
    # single-bend fan (L2, which projects to the same 154.000 mm point at the same 0.325 mm
    # offset, then straight to L6.3, 5.273 mm) since nothing blocks its side. Bend counts:
    # CANH 3 (H1, H2, H3), CANL 2 (L1, L2) -- the extra bend is confined to the last 6.6 mm at
    # the L6 end, and it is forced: without H3 the straight H2->L6.4 leg leaves only 0.145 mm to
    # that same via.
    ("CANH", "In2.Cu", 0.3, [(67.400, 130.590),
                              (68.7707, 129.0978),
                              (188.2209, 35.0997),
                              (189.5800, 34.4800),
                              (193.575, 31.300)]),
    ("CANL", "In2.Cu", 0.3, [(72.000, 130.590),
                              (69.1727, 129.6086),
                              (188.6229, 35.6105),
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

    # --- Task 9: boost switch node (D4 non-synchronous, so it is inside the loop) ---
    # Geometry below is the controller's own measured table (mccan.kicad_pcb at f1fcd93)
    # plus every pad this task's own coordinate dump re-derived and cross-checked
    # against that table (U3's 17 pads, D4, L3, C20/C21/C22, R12/C61/R13, C24, R14, C25).
    # Every clearance figure quoted in these comments is a true copper-to-copper gap
    # computed directly from the coordinates written here against the actual foreign
    # pad/via box: the distance from the track centreline to that box, minus half the
    # track width.  That is the measure gen_pcb.py's own route-clearance gate applies,
    # so a figure here and a figure from the gate are the same number.  A bounding-box
    # gap is NOT the same measure and understates any diagonal segment badly -- the
    # COMP jog below measures 0.125 mm that way against 0.350 mm of actual copper --
    # so nothing in this block is quoted that way.  Clearances use whichever netclass
    # genuinely applies to the pair.  SW_BOOST, Net-(U3-COMP), FB_24V and Net-(U3-SS)
    # match no NETCLASSES entry and sit on the 0.20 mm board default.  +24V does NOT --
    # it is in POWER (see NETCLASSES above), so it and every +24V pad, D4.1 included,
    # carry 0.30 mm.  Where a 0.20 mm net runs beside +24V copper the larger of the two
    # applies, which is 0.30 mm, not 0.20.

    # SW column: 0.75 mm centred at x=86.5 (outer edges of U3 pins 13/14 together),
    # straight into D4.2 with no bend (D4.2 spans x 85.560-86.960, fully containing the
    # column) and stopping at y=30.55 so the end cap (0.375 mm) lands at y=30.925,
    # 0.238 mm clear of U3's GND paddle (top edge y=31.163) while still covering 0.80 mm
    # of pins 13/14's 0.837 mm pad length. Both figures are the brief's own derived
    # numbers, used verbatim. Independently re-verified here by rectangle gap: clears
    # D4.1 (+24V, foreign, POWER class 0.30 mm floor) by 0.765 mm; clears pin 15 (NC)
    # by 0.25 mm (0.05 mm over the 0.20 mm floor); clears the GND paddle by 0.2375 mm
    # (0.0375 mm over the 0.20 mm floor -- thin, but it is what the paddle's position
    # and the pin-13/14 coverage requirement together allow).
    ("SW_BOOST", "F.Cu", 0.75, [(86.5, 28.365), (86.5, 30.55)]),

    # L3 rung: 0.75 mm at y=29.70 (spans 29.325-30.075), from L3.2's pad centre in to
    # the SW column. Clears D4.1 (+24V, foreign, POWER 0.30 mm floor) by 0.325 mm --
    # 0.025 mm of margin, the brief's own number, used verbatim -- and stays north of
    # U3's top-edge pads (pins 13/14 are this same net so no clearance applies there;
    # pins 15/16 sit west of x=86.5 and never enter this rung's x-range at all).
    ("SW_BOOST", "F.Cu", 0.75, [(91.815, 29.70), (86.5, 29.70)]),

    # Pin-12 tie: 0.30 mm, not a share of the SW current (its neighbour is MODE, not
    # another SW pin). Starts at pin 12's own centre, clears MODE (pin 11, foreign,
    # top edge y=31.625) by 0.225 mm at that start point -- the brief's own number,
    # used verbatim -- then bends to land on the L3 rung's own copper (T-junction) at
    # (88.2, 29.70), which is inside the rung's box (x 86.5-91.815, y 29.325-30.075).
    # The descending leg clears D4.1 by 0.550 mm -- its copper spans y 29.55-30.45 and
    # D4.1 ends at y 29.000, so they do not overlap in y at all -- against the 0.30 mm
    # POWER floor that D4.1's own netclass imposes.
    ("SW_BOOST", "F.Cu", 0.30, [(87.4562, 31.250), (88.2, 30.3), (88.2, 29.70)]),

    # +24V column: C20.1/C21.1/C22.1 are collinear at x=83.375 (no vias of their own --
    # this column and its rung are their only connection to anything, per the brief).
    # 1.0 mm, nothing foreign anywhere near this corridor (nearest is the VBAT riser at
    # (81.175, 32.4), out of this column's y-range entirely and >1.3 mm off in x even
    # if it weren't).
    ("+24V", "F.Cu", 1.0, [(83.375, 22.700), (83.375, 29.300)]),

    # +24V rung: 1.5 mm at y=24.5, from the column across into D4.3's tab (the same
    # net as the tab and its 25-via thermal grid, so no clearance applies there -- it
    # is meant to land on and feed that grid, which is how +24V actually leaves the
    # boost, per the controller's ruling: downward into the B.Cu pour under D4.3, not
    # along F.Cu). Overlaps C21.1's own pad in passing (same net, harmless).
    ("+24V", "F.Cu", 1.5, [(83.375, 24.5), (86.5, 24.5)]),

    # Net-(U3-COMP): the highest-impedance node in the converter, kept short and away
    # from SW per the brief. Pin 8 -> R14.1 -> C24.1 (C24's COMP terminal). Leaves pin 8
    # centre, jogs east to x=87.0 before running south; entering near x=87.0 is what
    # R14.1's own pad width (86.425-87.225) allows.
    #
    # THE OBSTACLE THIS JOG AVOIDS IS NOT WHAT THIS COMMENT USED TO SAY. It named "the
    # GND via at (86.25, 34.225)", quoted the brief's warning that a straight run down
    # pin 8's own centre (x=86.75) "clears that via by only 0.10 mm and fails", and then
    # claimed to have re-verified 0.350 mm and 0.325 mm against it. There is no via at
    # (86.250, 34.225). The nearest via of any net to that point is a GND thermal via at
    # (86.412, 32.413), 1.820 mm away, and gen_pcb prints "sharing a neighbour's via:
    # U3.7" -- pin 7 never got a drop of its own. All four figures were about copper the
    # board does not have.
    #
    # What is actually there, and what binds, re-measured against the generated board
    # with gen_pcb's own _seg_rect_gap / _seg_seg_dist:
    #   jog out of pad   0.248 mm to pin 7's ground stub (86.250,33.456)-(86.412,31.587),
    #                    0.250 mm to pin 7's pad itself
    #   run south        0.500 mm to pin 7's pad, 0.539 mm to that stub
    #   into R14.1       0.551 mm to the GND via at (86.775, 36.375)
    #   final leg        0.849 mm to C24.2 (GND, same footprint, foreign net)
    # The straight-down-x=86.75 alternative does NOT fail: measured, it clears 0.248 mm,
    # the same pinch the jog takes leaving the pad. What the jog buys is the long leg --
    # 0.500 mm instead of 0.248 mm for the whole run south -- so the 0.248 mm pinch is
    # confined to 0.35 mm of diagonal next to the pad instead of running 1.9 mm alongside
    # pin 7. That is a real reason for the jog; the via was not.
    # Worst slack +0.048 mm on a 0.200 mm limit.
    ("Net-(U3-COMP)", "F.Cu", 0.25, [(86.750, 33.4562), (87.0, 33.7), (87.0, 34.6),
                                       (86.825, 35.400), (88.550, 35.025)]),

    # FB_24V: the only F.Cu run this net needs is pin 9 out to a trunk that ties
    # R12.2/C61.2/R13.1 together, which is the far end of the output-cap divider,
    # satisfying the controller's "tap the far end".
    #
    # The divider's OTHER end, R12.1/C61.1, used to be described here as reading "through
    # the +24V pour (R12.1/C61.1 drop straight to it below, see ROUTE_VIAS)". Both halves
    # of that are now wrong: there is no +24V pour anywhere near those pads -- /+24V's one
    # zone is 24V_D4 on B.Cu, 5 mm away -- and the two ROUTE_VIAS entries were removed for
    # exactly that reason. What actually feeds R12.1/C61.1 is the frozen router's F.Cu
    # copper, (91.800,34.000)-(91.800,32.200) between the two pads and
    # (91.800,32.200)-(90.300,30.700) up to the +24V via there. The ruling's substance --
    # no long F.Cu haul round from the output caps, no run beside SW -- is unaffected.
    #
    # Hop clears pin 10 (SS, foreign) by 0.250 mm and pin 8 (COMP, foreign) by 0.523 mm.
    # Trunk's tightest is now 0.899 mm to that frozen /+24V track, then 1.025 mm to C24.1
    # and to C61.1's pad -- all comfortable; this net has no tight neighbour once past
    # pin 10. Worst slack +0.050 mm on a 0.200 mm limit.
    ("FB_24V", "F.Cu", 0.25, [(87.4562, 32.750), (90.175, 32.750)]),
    ("FB_24V", "F.Cu", 0.25, [(90.175, 32.200), (90.175, 35.800)]),

    # Net-(U3-SS): boxed in at pin 10 -- MODE (pin 11) north, the GND paddle west, the
    # FB_24V hop directly south at y=32.75 (same corridor SS has to cross to reach C25).
    # Runs east along pin 10's own row into the open pocket east of U3's pins and west of
    # the FB_24V trunk, then ducks to In5.Cu to pass underneath the FB_24V hop entirely on
    # a different layer -- SMD pads have no copper off F.Cu, so this also clears C24 and
    # R14 without needing to thread the narrow corridor between them. Comes back to F.Cu
    # south of C24 and runs straight down into C25.1.
    #
    # The duck-under via sat at x=88.500 until Step 6.1 and now sits at 88.600. It was the
    # single obstacle that sealed pin 11 (MODE) into a pocket with no exit: pin 11 can only
    # leave its pad eastward, and the gate between pin 12's pad corner (87.875, 31.375) and
    # that via measured 0.884 mm where a 0.20 mm centreline needs 0.900 (0.300 to the pad,
    # 0.600 to the 0.60 mm via disc). 0.100 mm east makes the gate 0.957 mm and MODE routes;
    # see Net-(U3-MODE) below. Re-measured against the GENERATED board in Step 6.3, which
    # is what moved these numbers: the figures here were first written before MODE existed,
    # and MODE now runs alongside SS for its whole length, so MODE is the tightest neighbour
    # of three of SS's five features. Tightest neighbour per leg, all on a 0.200 mm limit:
    #   pin-10 row       0.250 mm to pin 11, to pin 9 and to the FB_24V hop
    #   jog south        0.250 mm to the FB_24V hop
    #   In5.Cu run       0.400 mm to MODE's via at (88.400, 31.200), then 0.491 mm to the
    #                    GND drop via at (87.625, 36.575)
    #   run into C25.1   0.650 mm to C24.2 (GND)
    #   via_in  0.60 mm  0.225 mm to MODE's via, 0.236 and 0.252 mm to MODE's two F.Cu
    #                    legs, 0.253 mm to MODE's In2.Cu run south  <- binding
    #   via_out 0.60 mm  0.254 mm to MODE's In2.Cu run into R11, 0.475 mm to C24.2 (GND)
    # Worst slack over the whole net is +0.025 mm on a 0.200 mm class limit.
    ("Net-(U3-SS)", "F.Cu", 0.25, [(87.4562, 32.250), (88.600, 32.250), (88.600, 32.000)]),
    ("Net-(U3-SS)", "In5.Cu", 0.25, [(88.600, 32.000), (88.525, 37.8)]),
    ("Net-(U3-SS)", "F.Cu", 0.25, [(88.525, 37.8), (88.525, 39.000)]),

    # ---------------------------------------------------------------------------------
    # Step 6.1: the nets the external router left open. Each one was planned on a 0.05 mm
    # clearance grid over the frozen router copper, then measured against that copper with
    # gen_pcb's own gap functions -- pads as bounding boxes, vias as discs, tracks as
    # capsules -- and the tightest neighbour of every leg is quoted below. "Slack" is the
    # measured gap less the binding netclass clearance, so +0.000 would be exactly at the
    # limit; nothing here is.
    # ---------------------------------------------------------------------------------

    # Net-(U3-MODE): U3 pin 11 out to R11.1. Pin 11's only escape is east, through the
    # 0.957 mm gate between pin 12's pad and the relocated SS via (see above) -- with the
    # via at its old 88.500 this net had no route at all, on any layer, and no legal via
    # site anywhere in the pocket. East out of the pad, diagonally past pin 12's corner,
    # then down to In2.Cu and south past U3 to R11 at y=39. Tightest per leg:
    #
    # There is no via at the R11 end. The external router had already dropped a 0.60/0.30
    # via-in-pad on this net at R11.1 (86.825, 39.000) and left the rest of the net open,
    # so the In2.Cu run simply ends on that via. A hand via of our own at (86.800, 39.000)
    # -- which is what this file had until Step 6.3 -- put two 0.30 mm drills 0.025 mm
    # apart, 0.275 mm INSIDE the 0.300 mm hole-to-hole floor. gen_pcb's check_via_holes is
    # what found it, and now gates it. This comment used to add "KiCad's DRC never said a
    # word because it skips hole-to-hole between two vias on the same net". That is false:
    # KiCad checks same-net pairs and reports them (verified -- see the note in
    # gen_pcb.check_via_holes). It said nothing because hole_to_hole was set to `warning` in
    # mccan.kicad_pro and the gate ran --severity-error, which discards warnings.
    #
    # Tightest neighbour per leg, measured against the generated board:
    #   east out of pad  0.250 mm to the SW_BOOST hop, 0.275 mm to pin 10's and pin 12's pads
    #   diagonal         0.218 mm to pin 12's pad (the binding measurement on this net)
    #   jog to the via   0.252 mm to the SS duck-under via at (88.600, 32.000)
    #   In2.Cu south     0.253 mm to that same SS via on the long leg -- the tightest of the
    #                    seven In2.Cu legs -- then 0.254 mm to the SS via at (88.525,
    #                    37.800), 0.277-0.280 mm alongside SS, and 0.342 mm to the GND drop
    #                    via at (87.625, 36.575)
    #   via down 0.60    0.225 mm to pin 12's pad and 0.225 mm to the SS via at (88.600,
    #                    32.000), 0.262 mm to the SW_BOOST hop
    # Worst slack +0.018 mm on a 0.200 mm limit.
    ("Net-(U3-MODE)", "F.Cu", 0.20, [(87.456, 31.750), (87.950, 31.750), (88.250, 31.450),
                                     (88.400, 31.200)]),
    ("Net-(U3-MODE)", "In2.Cu", 0.20, [(88.400, 31.200), (88.050, 31.600), (87.950, 31.750),
                                       (87.900, 35.800), (88.250, 36.150), (88.400, 36.400),
                                       (88.400, 37.000), (87.900, 37.500), (86.825, 39.000)]),

    # Net-(U3-VCC): U3 pin 2 out to R15.1, west along the pin row and then down. Pin 2 was
    # also sealed until Step 6.1, by pin 1's ground drop sitting at (83.775, 31.250); that
    # drop is placed by gen_pcb.gnd_drops AFTER routes(), and its own via_ok refuses any
    # site a hand route already occupies, so drawing this route is what moves it. Tightest:
    #   west out of pad  0.275 mm to pin 1 (GND) and to pin 3 (BIAS), both foreign
    #   diagonal to R15  0.287 mm to pin 1, 0.300 mm to the BIAS run at y=32.250
    # Worst slack +0.075 mm on a 0.200 mm limit. No via: the whole net is one F.Cu run.
    ("Net-(U3-VCC)", "F.Cu", 0.20, [(84.544, 31.750), (83.950, 31.750), (82.825, 30.600)]),

    # GND at U4 pin 6 -- a ground drop placed here rather than by gen_pcb.gnd_drops, and
    # deliberately dog-legged AWAY from the site the placer would pick.
    #
    # U4's two ground pins, 4 and 6, sit either side of pin 5 (Net-(U4-SR)) on a 0.5 mm
    # pitch, and the only copper any of the three can escape into is a pocket about 1 mm
    # across, south-west of the part. Measured with gen_pcb's own gap functions, sweeping
    # every 0.05 mm site within 2.5 mm of each pad:
    #   pin 4   0 legal drop sites, with or without SR drawn (Step 6's gap 14, pre-existing)
    #   pin 6   67 legal drop sites, every one of them inside the box
    #           x 96.05..96.45, y 87.35..88.00 -- which is the pocket
    # and flooding pin 5's own F.Cu pocket gives 9044 cells with pin 6's drop absent but
    # 350 cells and ZERO legal via sites with it present, at every via size down to the
    # board minimum 0.50/0.20. Pin 5's escape leaves the pad westward, runs south down a
    # channel at x 95.25..96.05 and turns back east through a doorway 0.10 mm tall at
    # y 87.65..87.75; any 0.60 mm via in the box shuts that doorway. So a straight drop for
    # pin 6 and a route for pin 5 cannot both exist, and since pin 4 has no site either,
    # letting the placer have the pocket would leave U4 with no ground connection at all.
    #
    # A drop stub is a single straight segment, so gnd_drops has no way out of the pocket.
    # A route does: this one leaves the pad east-south-east, squeezes between pin 6's own
    # pad and the /+3V3_ALW paddle (pin 13), and vias down 1.38 mm away at (97.750, 88.050),
    # clear of the box entirely. Re-flooding pin 5's pocket with it in place gives 8526
    # cells and 306 legal via sites, so both pins get served. Tightest per leg, all against
    # the 0.200 mm Default clearance:
    #   (96.700,87.150)-(96.900,87.350)   0.226 to pin 13's paddle, 0.250 to pin 5's pad
    #   (96.900,87.350)-(96.900,87.450)   0.226 to pin 13's paddle
    #   (96.900,87.450)-(96.950,87.500)   0.223 to pin 13's paddle
    #   (96.950,87.500)-(97.000,87.550)   0.215 to pin 13's paddle  <- binding
    #   (97.000,87.550)-(97.050,87.600)   0.215 to pin 13's paddle
    #   (97.050,87.600)-(97.100,87.650)   0.222 to pin 13's paddle
    #   (97.100,87.650)-(97.750,88.050)   0.244 to pin 13's paddle
    #   via 0.60/0.30                     0.225 to the +24V_FL run on In5.Cu,
    #                                     0.226 to the two /EN_3V3SW runs on In2.Cu
    # Worst slack +0.015 mm. The width is 0.20, not the 0.25 the other hand routes use:
    # 0.25 puts three of those legs 0.010 mm inside the paddle's clearance, and a ground
    # drop carries no current that needs the extra copper.
    ("GND", "F.Cu", 0.20, [(96.700, 87.150), (96.900, 87.350), (96.900, 87.450),
                           (96.950, 87.500), (97.000, 87.550), (97.050, 87.600),
                           (97.100, 87.650), (97.750, 88.050)]),

    # Net-(U4-SR): U4 pin 5 out to C32.1, a 17 mm haul, planned against the dogleg above.
    # West out of the pad between pins 4 and 6, south down the channel and back east through
    # the doorway to a via at (96.400, 87.850) -- inside the box pin 6's drop used to own --
    # then north-east on In2.Cu between the FB_5V vias to the south-west of C32, and up to
    # In5.Cu for the last 2 mm because F.Cu there is full of the RET_FL_G return. Tightest
    # per leg, all against 0.200 mm:
    #   F.Cu escape      0.236 to pin 6's pad, 0.240 to it again on the south leg, 0.250 to
    #                    pin 4's pad; 0.300 mm is the closest any of the four F.Cu legs gets
    #                    to the dogleg's own GND copper
    #   In2.Cu haul      0.254 to the FB_5V via at (105.600, 93.000) is the tightest of the
    #                    ten legs; the whole haul sits in 0.254..0.280, set by those FB_5V
    #                    vias -- (99.100,88.800), (100.500,90.200), (104.000,91.400),
    #                    (105.600,93.000) -- and, on the first three legs, by the GND drop
    #                    via at (97.750, 88.050)
    #   In5.Cu hop       1.181 to the GND via at (107.355, 92.655)
    #   via (96.400,87.850)   0.240 to the dogleg's F.Cu legs, 0.250 to pin 6's pad
    #   via (108.750,93.400)  0.225 to the RET_FL_G run on F.Cu  <- binding
    # Worst slack +0.025 mm.
    #
    # As with Net-(U3-MODE), there is no via at the C32 end: the router's own 0.60/0.30
    # via-in-pad at C32.1 (110.305, 91.830) is where the In5.Cu hop lands. The hand via this
    # file used to place at (110.300, 91.850) sat 0.021 mm from it -- 0.279 mm inside the
    # 0.300 mm hole-to-hole floor, and silent in DRC because hole_to_hole was a `warning` and
    # the gate ran --severity-error. NOT because the two are the same net, which is what this
    # comment used to say: KiCad checks same-net hole-to-hole and reports it. See the note in
    # gen_pcb.check_via_holes for the verification.
    ("Net-(U4-SR)", "F.Cu", 0.20, [(96.700, 86.650), (96.250, 86.650), (96.000, 86.900),
                                   (96.050, 87.500), (96.400, 87.850)]),
    ("Net-(U4-SR)", "In2.Cu", 0.20, [(96.400, 87.850), (97.350, 88.600), (97.500, 88.700),
                                     (98.100, 88.750), (100.100, 90.750), (100.250, 90.850),
                                     (102.550, 90.900), (105.200, 93.550), (105.350, 93.650),
                                     (108.450, 93.700), (108.750, 93.400)]),
    ("Net-(U4-SR)", "In5.Cu", 0.20, [(108.750, 93.400), (110.305, 91.830)]),

    # /EN_BOOST: U3 pin 6 down to R20.1. This is the tightest net in this batch and the
    # only one planned to the class limit itself rather than with the 0.005 mm planning
    # margin the others carry: pin 6's sole escape is the channel between pin 5's pad
    # corner (85.375, 33.875) and pin 7 on the other side, and that channel leaves
    # 0.202 mm to pin 5 at its narrowest -- 2 um over the 0.200 mm floor.
    #
    # "Pin 7 on the other side" is the correction. This comment used to say the channel's
    # far wall was "pin 7's ground drop via at (86.250, 34.225)" and quoted three
    # clearances against it. No via exists there: nearest of any net is a GND thermal via
    # at (86.412, 32.413), 1.820 mm off, and gen_pcb prints "sharing a neighbour's via:
    # U3.7", so pin 7 has no drop via of its own -- it has its PAD, and a ground stub from
    # the pad centre (86.250, 33.456) running south to the neighbour's via at
    # (86.412, 31.587). Re-measured against the generated board, per leg:
    #   south out of pad 0.202 mm to pin 5 (RT, foreign) at the pinch; on the other side
    #                    0.275 mm to pin 7's pad and 0.275 mm to that ground stub
    #   In2.Cu run       1.422 mm to the GND via at (81.775, 39.025) -- this leg is not
    #                    tight at all, and the 0.419 mm here before was not measuring it
    #   via down 0.60    0.225 mm to R14.2's pad, 0.230 mm to pin 5's pad
    #   via up   0.60    0.925 mm to R20.2 (GND)
    # Worst slack +0.002 mm on a 0.200 mm limit -- unchanged, because the binding number
    # was always the 0.202 mm to pin 5 and that one was right. There is nothing left to
    # give here: any future change near U3 pins 5-7 has to re-plan this net, not nudge it.
    # Widening the channel would mean moving pin 7's ground stub, which buys nothing the
    # rule does not already allow.
    ("/EN_BOOST", "F.Cu", 0.20, [(85.750, 33.456), (85.700, 33.850), (85.700, 33.950),
                                 (85.650, 34.000), (85.650, 34.100), (85.550, 34.200),
                                 (85.450, 34.400)]),
    ("/EN_BOOST", "In2.Cu", 0.20, [(85.450, 34.400), (83.400, 38.200)]),
    ("/EN_BOOST", "F.Cu", 0.20, [(83.400, 38.200), (83.425, 38.200)]),

    # Step 6.1b. The route below was planned by grid search against the FROZEN board
    # (mccan.kicad_pcb, which under the freeze is what the copper really is), stepping 0.05 mm
    # on all four signal layers, and every number quoted was then re-measured with gen_pcb's
    # own gap functions -- _seg_rect_gap for pads, _seg_seg_dist for tracks, _seg_disc_gap for
    # vias, plus a via sweep against copper on EVERY layer, which routes() itself never does.
    # Width is 0.20 mm, the board floor, not the router's 0.25: in this corridor 0.25 loses
    # the lane outright, and a load-switch gate carries no current worth the copper.

    # /power_input/U10_GATE: U10 pin 3 down to the router's own via at (38.300, 83.600),
    # 14.5 mm, F.Cu -> In5.Cu. The easy one in this batch: this is the input-protection
    # cluster, not the output field, and the channel south at x = 39.20..39.45 was still open.
    #
    # The router had already routed the R103 end of this net -- R103.1 through a 0.60/0.30
    # via at (38.300, 83.600) and on east to Q10 -- and left the U10 end open. So the haul
    # ends ON that via, on In5.Cu, which is one of the layers it reaches; no hand via and no
    # F.Cu landing leg are needed. Until Step 6.3 this route did place its own via, at
    # (38.000, 83.850), which is 0.091 mm hole-to-hole from the router's -- inside the
    # 0.300 mm fab floor, and invisible to the DRC gate because hole_to_hole was a `warning`
    # and the gate ran --severity-error. Not, as this comment used to claim, because the two
    # vias are the same net: KiCad checks same-net pairs and reports them (see the note in
    # gen_pcb.check_via_holes). gen_pcb.check_via_holes gates it at generate time now, and
    # gen_netclasses.py writes hole_to_hole at `error` so KiCad gates it too. Ending on the
    # router's via also lengthens the
    # last In5.Cu leg's tightest gap from 0.933 mm to 1.111 mm.
    #
    # The polyline starts at (37.200, 96.000) -- 0.300 mm east of pin 3's pad centre but well
    # inside the pad, which spans x 36.15..37.65 -- because a leg drawn from the centre itself
    # meets the end cap of the /power_input/SNS run that turns at (36.900, 96.500) at exactly
    # 0.200 mm. Zero slack, measured, not guessed. Starting east of that cap costs no copper
    # and buys 0.057 mm. Tightest per run, against the 0.200 mm Default clearance except
    # where noted:
    #   F.Cu escape   0.257 then 0.268 to the /power_input/VCC10 run along y = 95.5; also
    #                 0.201 to U10 pin 2, whose own pads mccan.kicad_dru relaxes to 0.120
    #   In5.Cu haul   0.246 and 0.241 to the VCC10 via at (38.800, 94.700)  <- binding
    #                 0.249 to the /power_input/Q10_G via at (38.700, 91.400)
    #                 1.111 on the last leg, to the VCC10 via at (36.850, 83.175)
    #   via (38.900, 95.550)  0.256 to that same VCC10 via at (38.800, 94.700)
    # Worst slack +0.041 mm on a 0.200 mm limit.
    ("U10_GATE", "F.Cu", 0.20, [(37.200, 96.000), (38.150, 95.950), (38.900, 95.550)]),
    ("U10_GATE", "In5.Cu", 0.20, [(38.900, 95.550), (39.400, 95.000), (39.450, 94.700),
                                  (39.200, 86.500), (38.300, 83.600)]),

    # Step 6.3. Three more of U7's PCA9685 outputs, all three planned together against the
    # frozen board and then re-measured against the GENERATED board -- the one this file
    # produces, with these three routes and every ground drop in it -- so the figures below
    # are the artifact's, not the plan's. Same measurement model as Step 6.1b above.
    #
    # The committed /outputs/PWM_FL_R route that used to sit here has been REMOVED, and this
    # batch re-routes that net from scratch. It was not wrong; it was first. U7 pins 6 and 7
    # are 0.650 mm apart and both escape eastward through the same pocket, and the route that
    # took the pocket sealed it: flooding pin 7's escape with the old PWM_FL_R in place gave
    # 221 reachable cells and ZERO legal via sites at the board-minimum 0.50/0.20 via, and the
    # only wall the search could name was that route's own F.Cu escape. Routing pin 7 first and
    # pin 6 around it gets both out. The old comment also closed by saying the blind spot in
    # gnd_drops "is reported in the Step 6.1b report, not patched here" -- c6bb73f patched it,
    # so that sentence went with the route.
    #
    # Vias are 0.50/0.20 on the two PWM_FL_* nets and the netclass 0.60/0.30 on PWM_FR_R.
    # 0.50 is the board minimum via diameter and 0.20 the drill it forces: min_via_annular_
    # width is 0.15 mm, so a 0.50 barrel cannot take the 0.25 mm drill that dia/2 would give.
    # The small barrel is necessary, not tidy -- PWM_FL_G's via at (138.600, 48.550) clears a
    # MUXIN_RL_G via by 0.207 mm and PWM_FL_R's at (145.500, 29.700) clears PWM_FL_G's own
    # F.Cu escape by 0.202 mm, so 0.60 would put both 0.043 and 0.048 mm inside the floor.
    # PWM_FR_R's tightest via has 0.208 mm at 0.60, so it keeps the default.
    #
    # Two ground drops moved out of the way of this copper, and only two: the drop at
    # (142.000, 32.925) to (141.900, 32.925), and the one at (144.405, 57.655) to
    # (144.619, 57.627). gnd_drops() re-picked both sites itself, the board still carries 139
    # drop vias serving 140 of the 141 SMD ground pads (U3.7 shares a neighbour's), and the
    # only pad without one is still U4.4 -- the same tally as before this batch.
    #
    # All three nets END ON A VIA THE ROUTER ALREADY PLACED, at (159.600, 52.000),
    # (148.500, 54.000) and (170.200, 54.300), rather than dropping a landing via of their
    # own next to it. Each of them first had its own, and each of those three sat 0.019 mm,
    # 0.000 mm and -0.229 mm hole-to-hole from the router's -- two of them literally inside
    # the other barrel. The DRC gate passed all three, and the reason was the SEVERITY, not
    # the net: hole_to_hole was set to `warning` in mccan.kicad_pro and the gate ran
    # --severity-error, which discards warnings. This comment used to say KiCad "does not
    # check hole-to-hole between two vias on the same net"; it does, and reports it -- see the
    # note in gen_pcb.check_via_holes for the verification. Either way this would have shipped
    # to the fab as three pairs of 0.30 mm drills a few microns apart, because nobody ran the
    # one --severity-all pass that would have shown it. gen_pcb.check_via_holes gates it now,
    # gen_netclasses.py writes hole_to_hole at `error`, and it
    # also caught three older hand vias the same way (Net-(U3-MODE), Net-(U4-SR) and
    # /power_input/U10_GATE above, all three fixed the same way).

    # /outputs/PWM_FL_G: U7 pin 7 east then the long way round to R41.1 at (161.255, 54.330) --
    # 9 runs, 7 vias, F.Cu/B.Cu/In2.Cu. Pin 7 is the harder of the pair: its escape pocket is
    # the 0.650 mm-pitch gap between pins 6 and 8, everything east of it is the router's output
    # field, and the route drops to B.Cu almost at once, runs west under the mux block, turns
    # south on In2.Cu down the x = 136.2 channel, and only comes back east across the bottom
    # of the output field where In2.Cu is clear. Tightest per run, all against the 0.200 mm
    # Default clearance:
    #   F.Cu escape     0.202 to PWM_FL_R's via at (145.500, 29.700)  <- binding
    #   B.Cu west       0.229 to the ground drop at (141.900, 32.925)
    #   In2.Cu south    0.236 to the ISNS_DEN via at (137.700, 45.200)
    #   B.Cu south      0.270 to the PWM_FL_B run on B.Cu
    #   In2.Cu east     0.251 to the PWM_RR_G via at (143.000, 56.800)
    #   F.Cu hop        0.272 to the MUXIN_RR_G via at (144.800, 59.400)
    #   In2.Cu east     0.210 to the PWM_DEN_B via at (155.900, 59.100)
    #   B.Cu north      0.270 to the MUXIN_FL_R run on B.Cu at x = 156.850
    #   F.Cu landing    0.276 to the RET_FL_B via at (160.000, 53.500)
    #   via (145.000,30.350)  0.226 to the MUXIN_RR_R run on In2.Cu
    #   via (137.800,32.800)  0.225 to the +3V3_SW run on F.Cu
    #   via (138.600,48.550)  0.207 to the MUXIN_RL_G via at (138.500, 47.800)
    #   via (141.600,56.000)  0.225 to the RET_FR_G run on In5.Cu
    #   via (143.650,57.850)  0.300 to the PWM_RR_G run on B.Cu
    #   via (145.700,59.350)  0.225 to the Net-(C47-Pad1) run on F.Cu
    #   via (156.600,57.400)  0.225 to the SENSE_RR_B run on F.Cu
    # The B.Cu north run carries a waypoint at (158.700, 52.325) that buys nothing but
    # clearance: with the run going straight from (158.000, 52.350) to the router's via at
    # (159.600, 52.000) it passed a /outputs/PWM_RR_B via at (158.500, 51.700) at 0.178 mm,
    # 0.022 inside the floor. A 0.05 mm sweep of single waypoints over the window found a
    # plateau there; the leg's binding gap is now 0.270 mm elsewhere.
    # Worst slack +0.002 mm, and it is the pin 6/pin 7 pinch: this route's F.Cu escape and
    # PWM_FL_R's first via are the same 0.202 mm pair seen from either side. Like /EN_BOOST
    # above, that is the class floor met exactly rather than a margin over it, and anything
    # that changes either net near U7 pins 6-7 has to re-plan both of them together.

    ("PWM_FL_G", "F.Cu", 0.20, [(143.087, 28.375), (143.950, 28.450), (144.200, 28.700), (144.600, 29.150), (144.950, 29.750), (145.000, 30.350)]),
    ("PWM_FL_G", "B.Cu", 0.20, [(145.000, 30.350), (145.000, 31.250), (144.000, 32.250), (141.700, 32.300), (137.800, 32.800)]),
    ("PWM_FL_G", "In2.Cu", 0.20, [(137.800, 32.800), (136.650, 32.850), (136.500, 32.950), (136.350, 33.100), (136.250, 33.250), (136.200, 39.550), (136.300, 39.700), (137.550, 40.950), (137.600, 42.650), (137.950, 44.550), (139.200, 45.800), (139.200, 48.050), (138.900, 48.350), (138.600, 48.550)]),
    ("PWM_FL_G", "B.Cu", 0.20, [(138.600, 48.550), (139.800, 52.700), (139.950, 52.950), (141.800, 54.800), (141.800, 55.800), (141.600, 56.000)]),
    ("PWM_FL_G", "In2.Cu", 0.20, [(141.600, 56.000), (142.450, 57.100), (142.700, 57.350), (143.650, 57.850)]),
    ("PWM_FL_G", "F.Cu", 0.20, [(143.650, 57.850), (143.800, 58.350), (144.300, 58.350), (144.700, 58.350), (145.700, 59.350)]),
    ("PWM_FL_G", "In2.Cu", 0.20, [(145.700, 59.350), (150.150, 60.700), (153.650, 60.650), (154.450, 60.450), (156.150, 59.700), (156.250, 59.600), (156.300, 59.600), (156.550, 59.350), (156.600, 57.400)]),
    ("PWM_FL_G", "B.Cu", 0.20, [(156.600, 57.400), (155.675, 56.025), (155.750, 54.550), (157.850, 52.450), (158.000, 52.350), (158.700, 52.325), (159.600, 52.000)]),
    ("PWM_FL_G", "F.Cu", 0.20, [(159.600, 52.000), (160.550, 53.100), (161.255, 54.330)]),

    # /outputs/PWM_FL_R: U7 pin 6 out to R40.1 at (150.255, 53.830) -- 6 runs, 4 vias,
    # F.Cu/B.Cu/In2.Cu. Pin 6 goes second and takes the long way west and south round the
    # outside of everything: to B.Cu at (145.500, 29.700), west along y = 33..36 threading the
    # MUXIN fanout, down the left edge of the mux block to In2.Cu and back, then a long B.Cu
    # diagonal south-east under the output field to In2.Cu for the last 3 mm into R40. The
    # detour is what the pair costs: pin 7 owns the pocket, so pin 6 cannot use it, and the
    # stretch (143.950,32.950)-(141.250,33.600) is the one place on all three routes where the
    # copper is legal against a ground drop but inside the enclosing SQUARE that gnd_drops uses
    # -- 0.130 mm to the box round the drop that was at (142.000, 32.925), which is why that
    # drop moved 0.100 mm west. No single-vertex nudge and no one- or two-vertex detour clears
    # the box there (a 0.05 mm grid sweep over the whole 2.75 x 2.75 mm window found 410 points
    # reachable from the east end and none that reach the west end), so the drop moves instead.
    # Tightest per run, all against the 0.200 mm Default clearance:
    #   F.Cu escape     0.254 to pin 7's own pad (U7.7, PWM_FL_G)
    #   B.Cu west       0.228 to the ground drop at (133.875, 37.000)
    #   In2.Cu jog      0.300 to the SENSE_FR_B via at (131.700, 43.600)
    #   B.Cu diagonal   0.251 to the PWM_RR_G via at (143.000, 56.800)
    #   In2.Cu landing  0.269 to the MUXIN_RR_B via at (145.875, 55.175)
    #   F.Cu stub       0.487 to the MUXIN_FR_B via at (148.175, 54.825)
    #   via (145.500,29.700)  0.202 to PWM_FL_G's F.Cu escape  <- binding, the pin 6/7 pinch
    #   via (132.200,41.950)  0.225 to the Net-(C60-Pad1) run on F.Cu
    #   via (132.200,45.300)  0.225 to the SENSE_FR_R run on In5.Cu
    #   via (145.150,54.950)  0.209 to the MUXIN_RR_B via at (145.875, 55.175)
    # Worst slack +0.002 mm, the same pinch quoted under PWM_FL_G.
    ("PWM_FL_R", "F.Cu", 0.20, [(143.087, 27.725), (143.950, 27.800), (144.700, 28.550), (145.000, 28.900), (145.500, 29.700)]),
    ("PWM_FL_R", "B.Cu", 0.20, [(145.500, 29.700), (145.650, 30.150), (145.650, 31.250), (143.950, 32.950), (142.800, 33.000), (142.550, 33.250), (142.550, 33.300), (142.250, 33.600), (141.250, 33.600), (140.900, 33.250), (140.650, 33.100), (140.200, 33.150), (133.250, 36.400), (133.250, 36.700), (133.200, 40.950), (132.200, 41.950)]),
    ("PWM_FL_R", "In2.Cu", 0.20, [(132.200, 41.950), (132.400, 42.150), (132.400, 45.100), (132.200, 45.300)]),
    ("PWM_FL_R", "B.Cu", 0.20, [(132.200, 45.300), (132.950, 47.250), (135.050, 51.200), (136.100, 52.250), (136.150, 54.750), (136.850, 55.800), (137.000, 55.950), (137.150, 56.050), (140.800, 56.100), (141.300, 56.600), (142.300, 56.650), (142.700, 56.250), (145.150, 54.950)]),
    ("PWM_FL_R", "In2.Cu", 0.20, [(145.150, 54.950), (145.450, 54.650), (145.700, 54.500), (147.675, 53.650), (148.500, 54.000)]),
    ("PWM_FL_R", "F.Cu", 0.20, [(148.500, 54.000), (150.255, 53.830)]),

    # /outputs/PWM_FR_R: U7 pin 9 out to R43.1 at (170.255, 54.330) -- 8 runs, 7 vias,
    # F.Cu/B.Cu/In5.Cu, and the only one of the three that keeps the netclass 0.60/0.30 via.
    # Pin 9 escapes WEST, away from its destination, because east of it is the same output
    # field the other two had to go round; it drops to B.Cu at (138.000, 29.400) and then runs
    # right along the top of the board above the mux row, down the east edge at x = 175..180,
    # and back west past R66 to R43. The long B.Cu legs are in the margin the router left
    # above and outside the output field, which is why this one has the most slack of the three.
    # Tightest per run, all against the 0.200 mm Default clearance:
    #   F.Cu escape     0.236 to pin 8's pad (U7.8, PWM_FL_B)
    #   B.Cu north      0.245 to the MUXIN_FL_B via at (141.875, 28.050)
    #   In5.Cu hop      0.436 to the PWM_RL_R run on In5.Cu
    #   B.Cu east edge  0.255 to the SENSE_FR_G via at (178.000, 58.200)
    #   In5.Cu west     0.260 to the Net-(U9-IN1) via at (175.905, 60.330)
    #   B.Cu west       0.275 to the PWM_DEN_A via at (170.700, 61.400)
    #   F.Cu north      0.252 to the RET_RR_R via at (168.100, 59.000)
    #   B.Cu west       0.267 to the SENSE_FR_B via at (168.500, 55.100)
    #   via (138.000,29.400)  0.208 to the MUXIN_FR_R run on F.Cu  <- binding
    #   via (171.600,25.400)  0.211 to the Net-(U7-~{OE}) run on B.Cu
    #   via (173.800,29.300)  0.236 to the PWM_RL_R run on In5.Cu
    #   via (178.050,59.750)  0.225 to the SENSE_FL_B run on In5.Cu
    #   via (172.200,61.900)  0.211 to the RET_RL_G run on F.Cu
    #   via (168.050,61.150)  0.211 to the PWM_DEN_A run on F.Cu
    #   via (167.400,58.250)  0.212 to R66.1 (SENSE_FL_B)
    # Worst slack +0.008 mm.
    ("PWM_FR_R", "F.Cu", 0.20, [(143.087, 29.675), (142.350, 29.700), (142.000, 29.350), (141.850, 29.250), (141.350, 29.250), (141.150, 29.400), (138.000, 29.400)]),
    ("PWM_FR_R", "B.Cu", 0.20, [(138.000, 29.400), (141.150, 29.400), (141.350, 29.250), (141.650, 29.200), (142.500, 28.350), (142.550, 27.650), (144.500, 25.700), (147.250, 24.600), (157.850, 23.500), (165.850, 23.250), (170.250, 24.100), (170.350, 24.150), (171.600, 25.400)]),
    ("PWM_FR_R", "In5.Cu", 0.20, [(171.600, 25.400), (171.600, 27.100), (173.800, 29.300)]),
    ("PWM_FR_R", "B.Cu", 0.20, [(173.800, 29.300), (174.350, 29.900), (174.450, 30.150), (175.200, 39.450), (176.700, 41.275), (176.500, 42.500), (179.500, 45.500), (179.600, 45.650), (180.000, 52.450), (179.250, 55.550), (179.150, 55.700), (178.700, 56.150), (178.650, 58.450), (178.050, 59.750)]),
    ("PWM_FR_R", "In5.Cu", 0.20, [(178.050, 59.750), (175.400, 59.650), (173.500, 61.550), (173.350, 61.650), (172.200, 61.900)]),
    ("PWM_FR_R", "B.Cu", 0.20, [(172.200, 61.900), (170.650, 62.100), (168.050, 61.150)]),
    ("PWM_FR_R", "F.Cu", 0.20, [(168.050, 61.150), (167.550, 59.350), (167.450, 59.250), (167.400, 58.250)]),
    ("PWM_FR_R", "B.Cu", 0.20, [(167.400, 58.250), (167.400, 57.200), (170.200, 54.300)]),

    # ============== necks at three router-to-pad junctions on F.Cu ==============
    #
    # Not new connections.  Each of these three lays 0.5 mm of hand copper directly on top of
    # the first leg of a frozen router run, to widen a junction that KiCad's connection_width
    # check reports as a hairline isthmus.  Found only after gen_netclasses.py stopped writing
    # connection_width at `warning`, which the --severity-error gate had been discarding:
    #
    #   0.0589 mm  R101.2 /power_input/U10_DRN  (56.8425, 78.2300)
    #   0.0790 mm  Q10.1  /power_input/Q10_G    (26.2000, 104.1000)
    #   0.1346 mm  Q12.1  Net-(Q12-B)           (42.6000, 77.8000)
    #
    # all against the board's own 0.2000 mm min_connection.  The geometry is the same in all
    # three: the router leaves the pad on a 45 degree diagonal at 0.25 mm and crosses the pad
    # outline near its ROUNDED CORNER, so the copper common to track and pad tapers to a sliver
    # instead of meeting across a full 0.25 mm.  0.059 mm of copper is not a fabrication margin,
    # it is a coin toss at the etch tank -- and U10_DRN is the protection FET's drain node,
    # Q10_G is Q10's gate and Net-(Q12-B) is the gate driver's base.  A neck that does not
    # survive etching on those is an open gate on the eFuse, not a cosmetic finding.
    #
    # Why hand copper over the junction and not a re-route: this is the router's copper, frozen
    # in scripts/routes_signal.json, and the freeze is not regenerated (plan Task 10 ruling).
    # FROZEN_DROP would take the WHOLE net's router copper -- 14, 22 and 14 segments -- to fix a
    # 1 mm junction.  Adding copper on the same net can only widen the union, never narrow it,
    # so it is the minimal change that fixes the actual defect rather than the report of it.
    # Each segment is collinear with, and shorter than, the frozen leg it overlays, so it adds
    # no new geometry: U10_DRN's frozen leg runs (56.8, 78.2)-(56.0, 79.0) and this covers the
    # first 0.990 mm of it; the other two cover their frozen legs exactly end to end.
    #
    # 0.5 mm is measured, not chosen for looks.  Sweeping the width against KiCad's own check
    # (every value below run as a full DRC at --severity-all):
    #     0.30 mm  fixes U10_DRN only          -- Q10_G still 0.0790, Q12-B still 0.1100
    #     0.35 mm  fixes U10_DRN only          -- Q10_G still 0.0790, Q12-B still 0.0856
    #     0.40 mm  fixes U10_DRN and Q10_G     -- Q12-B still 0.0601 (its pad is only 0.6 mm
    #                                             tall, so a 45 degree crossing has very little
    #                                             pad edge to meet)
    #     0.50 mm  fixes all three
    # Achieved connection width after the fix, read by raising min_connection on a scratch copy
    # of the generated board until each junction reappears: none of the three is reported at a
    # 0.70 mm threshold, so all three are >= 0.700 mm -- 3.5x the 0.2000 mm floor, and the
    # figure a 0.5 mm track presents across a 45 degree crossing (0.5 * sqrt(2) = 0.7071 mm),
    # which is the cross-check that the sweep is measuring the junction and not something else.
    #
    # Clearance cost of the extra 0.125 mm of half-width, measured against every other piece of
    # copper on F.Cu plus every via and pad on the board (gen_pcb's own gap helpers and its own
    # net_clearance), tightest neighbour each:
    #   U10_DRN     1.370 mm to pad R101.1 (/power_input/MID), need 0.300 -- slack +1.070
    #   Q10_G       0.850 mm to pad Q10.2 (/power_input/FEED_P), need 0.300 -- slack +0.550
    #   Net-(Q12-B) 0.800 mm to pad Q12.2 (/power_input/FEED_P), need 0.300 -- slack +0.500
    # This is the eFuse block, not the output field; there is room here and these are the
    # loosest hand routes on the board.
    ("U10_DRN", "F.Cu", 0.50, [(56.800, 78.200), (56.100, 78.900)]),
    ("Q10_G", "F.Cu", 0.50, [(26.200, 104.100), (25.800, 104.500)]),
    ("Net-(Q12-B)", "F.Cu", 0.50, [(42.600, 77.800), (42.000, 78.400)]),

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
    # leaves its pad" means when the pad is the top of the via.  0.6/0.3 mm throughout, per the
    # CAN netclass's own via figures (NETCLASSES: ("CAN", 0.3, 0.2, 0.6, 0.3, ...)) -- fix
    # round 3: gen_pcb.py takes sz/dr straight from this tuple and never consults the netclass
    # for a hand via, so the class's own via size was inert here until these twelve were changed
    # by hand to match it. Smaller than the FEED-class 0.8/0.4 used elsewhere on this board, and
    # it buys clearance room too: a 0.6 mm via needs 0.10 mm less clearance on each side than a
    # 0.8 mm one. The tightest neighbour on any of these footprints is U6.6/U6.7 against U6's own
    # pins 5/8: 1.27 mm pad-centre pitch against a 0.3 mm via radius and a 0.3 mm pad
    # half-height. Verified clear of every same-footprint neighbour (D6.3, R26's own opposite
    # pad, L6's other three pads, U6's pins 5/8) by `AR_SKIP=1 python scripts/gen_pcb.py`
    # exiting 0: it checks every hand via against every pad and via with exact rectangle
    # geometry and refuses to write the board if any of these six is actually short.
    ("CANH", 197.093, 31.350, 0.6, 0.3),               # D6.1
    ("CANL", 197.093, 33.250, 0.6, 0.3),               # D6.2
    ("CANH", 206.755, 43.330, 0.6, 0.3),               # R26.1
    ("CANL", 208.405, 43.330, 0.6, 0.3),               # R26.2
    ("CANH", 193.575, 31.300, 0.6, 0.3),               # L6.4
    ("CANL", 193.575, 33.800, 0.6, 0.3),               # L6.3
    ("Net-(U6-CANH)", 189.025, 31.300, 0.6, 0.3),      # L6.1
    ("Net-(U6-CANL)", 189.025, 33.800, 0.6, 0.3),      # L6.2
    ("Net-(U6-CANH)", 213.275, 31.665, 0.6, 0.3),      # U6.7
    ("Net-(U6-CANL)", 213.275, 32.935, 0.6, 0.3),      # U6.6

    # CANL_stub's In5.Cu duck-under (see the ROUTES comment above the D6/R26/L6 cluster): the
    # two layer-transition vias that bracket the stretch of CANL_stub where a direct D6.2->R26.2
    # line would clip D6.3, Q2 or the GND via.  Also 0.6/0.3 mm now, per the CAN netclass, same
    # as every other hand via on this net.
    ("CANL", 201.7965, 37.4413, 0.6, 0.3),             # CANL_stub via_in  (In2.Cu -> In5.Cu)
    ("CANL", 206.6046, 41.7257, 0.6, 0.3),             # CANL_stub via_out (In5.Cu -> In2.Cu)

    # Task 9: boost switch node.  THE TWO VIAS THAT USED TO BE HERE ARE GONE -- do not put
    # them back without re-reading this.
    #
    # They were ("+24V", 91.825, 32.200) at R12.1 and ("+24V", 91.775, 34.000) at C61.1,
    # via-on-own-pad drops whose comment said they "drop straight to the +24V pour" so that
    # FB_24V's divider could read the pour instead of being hauled round on F.Cu.  On this
    # board there is no such pour to drop to.  /+24V owns exactly one zone -- 24V_D4, on
    # B.Cu, x 84.400..90.200, y 21.700..27.400 -- and In4.Cu, the inner plane the six-layer
    # stackup would have given +24V a piece of, is solid /VBAT here (Task 5 reversed the
    # split).  The nearest island corner is (90.200, 27.400), which is 5.07 mm from R12.1
    # and 6.79 mm from C61.1, so both vias landed on bare B.Cu and KiCad reported both as
    # [via_dangling] once Step 2 took that rule off warning.
    #
    # Nothing is lost by deleting them because the frozen router already ties both pads to
    # the rail on F.Cu: (91.800,34.000)-(91.800,32.200) joins the two pads, (91.800,32.200)-
    # (90.300,30.700) runs up to the +24V via at (90.300,30.700), and (91.800,34.000)-
    # (97.500,39.700) carries on east.  R12.1 and C61.1 are not among the 11 unconnected
    # pads before this change or after it -- the vias were contributing no connection, only
    # two holes and two annular rings in the middle of the boost node.
    # Net-(U3-SS)'s F.Cu <-> In5.Cu duck-under, bracketing the FB_24V hop and the
    # C24/R14 pair -- see the ROUTES comment above. Netclass default via size, same
    # as the sense/bias taps elsewhere in this file (this is a soft-start line, no
    # meaningful current).
    ("Net-(U3-SS)", 88.600, 32.0, 0.6, 0.3),   # via_in  (F.Cu -> In5.Cu), moved east 0.100
    ("Net-(U3-SS)", 88.525, 37.8, 0.6, 0.3),   # via_out (In5.Cu -> F.Cu)

    # Step 6.1 vias. Sizes are the netclass default 0.6/0.3 -- every one of these is a
    # signal line with no current worth a bigger barrel, and on this board a 0.6 mm via is
    # already the widest obstacle most of these corridors can absorb. Clearances for each
    # are quoted in that net's ROUTES comment above.
    ("Net-(U3-MODE)", 88.400, 31.200, 0.6, 0.3),   # F.Cu -> In2.Cu, east of pin 12
    ("GND", 97.750, 88.050, 0.6, 0.3),             # U4 pin 6's ground drop, see ROUTES
    ("Net-(U4-SR)", 96.400, 87.850, 0.6, 0.3),     # F.Cu -> In2.Cu, the pocket's own site
    ("Net-(U4-SR)", 108.750, 93.400, 0.6, 0.3),    # In2.Cu -> In5.Cu, clear of RET_FL_G
    ("/EN_BOOST", 85.450, 34.400, 0.6, 0.3),       # F.Cu -> In2.Cu below U3 pin 6
    ("/EN_BOOST", 83.400, 38.200, 0.6, 0.3),       # In2.Cu -> F.Cu at R20.1

    # Step 6.1b vias. Same 0.6/0.3 netclass default, same reasoning, and each one was swept
    # against copper on every layer (routes() does not do that for a hand via) -- clearances
    # are quoted in the ROUTES comment for the net.
    ("U10_GATE", 38.900, 95.550, 0.6, 0.3),        # F.Cu -> In5.Cu, east of the VCC10 via
    # Step 6.3 vias. 0.50/0.20 on the two PWM_FL_* nets -- the board's minimum via diameter
    # and the largest drill 0.15 mm min_via_annular_width leaves it -- because at the netclass
    # 0.60 the (138.600,48.550) and (145.500,29.700) barrels land 0.043 and 0.048 mm inside the
    # clearance floor. 0.60/0.30 on PWM_FR_R, whose tightest barrel still has 0.208 mm. Each
    # was swept against copper on every layer; clearances are in each net's ROUTES comment.
    ("PWM_FL_G", 145.000, 30.350, 0.50, 0.20),
    ("PWM_FL_G", 137.800, 32.800, 0.50, 0.20),
    ("PWM_FL_G", 138.600, 48.550, 0.50, 0.20),
    ("PWM_FL_G", 141.600, 56.000, 0.50, 0.20),
    ("PWM_FL_G", 143.650, 57.850, 0.50, 0.20),
    ("PWM_FL_G", 145.700, 59.350, 0.50, 0.20),
    ("PWM_FL_G", 156.600, 57.400, 0.50, 0.20),
    ("PWM_FL_R", 145.500, 29.700, 0.50, 0.20),
    ("PWM_FL_R", 132.200, 41.950, 0.50, 0.20),
    ("PWM_FL_R", 132.200, 45.300, 0.50, 0.20),
    ("PWM_FL_R", 145.150, 54.950, 0.50, 0.20),
    ("PWM_FR_R", 138.000, 29.400, 0.60, 0.30),
    ("PWM_FR_R", 171.600, 25.400, 0.60, 0.30),
    ("PWM_FR_R", 173.800, 29.300, 0.60, 0.30),
    ("PWM_FR_R", 178.050, 59.750, 0.60, 0.30),
    ("PWM_FR_R", 172.200, 61.900, 0.60, 0.30),
    ("PWM_FR_R", 168.050, 61.150, 0.60, 0.30),
    ("PWM_FR_R", 167.400, 58.250, 0.60, 0.30),
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
# Two entries, and only two.  scripts/routes_signal.json exists and is the board's main source
# of copper (4692 segments, 857 vias, 136 nets), so this tuple DOES have frozen copper to act
# on -- naming a net here would throw that net's router copper away.  An earlier comment here
# claimed routes_signal.json had been deleted; it had not.
#
# Net-(U3-VCC) is the first of the two nets where that costs nothing.  Its whole frozen entry is
#   "Net-(U3-VCC)": {"segments": [], "vias": [[82.825, 30.6, 0.6, 0.3]]}
# -- zero segments and a single fanout via the router dropped into R15.1's pad and then never
# laid a track on.  That is the textbook case this tuple was built for, and KiCad reported it
# as [via_dangling] @(82.825, 30.600) once Step 2 took that rule off warning.  The net itself
# is closed by hand, by the single F.Cu run in ROUTES above ("No via: the whole net is one
# F.Cu run"), whose far end is that same (82.825, 30.600); dropping the via therefore removes
# a hole and an annular ring and severs nothing.  Net-(U3-VCC) is not among the 11 unconnected
# pads before this entry or after it.
#
# Net-(U9-IS) is the second, and it is the same shape with a little more debris:
#   "Net-(U9-IS)": {"segments": [[86.1, 110.0, 85.15, 110.0, 0.25, "F.Cu"],
#                                [86.1, 110.0, 85.81, 110.0, 0.25, "F.Cu"]],
#                   "vias": [[86.1, 110.0, 0.5, 0.2]]}
# -- a fanout via in U9.4 and two overlapping westward stubs, 0.95 mm and 0.29 mm, that both
# start on that pad and end in open space.  The net's other pad is R82.1 at (133.755, 62.330),
# 50 mm away, and the router never went there: the net is open with this copper and open
# without it, and KiCad already reports the 0.29 mm stub as its own [unconnected_items] item.
# Nothing is foreclosed by dropping it, and that is measured rather than assumed --
# `python scripts/show_pocket.py "Net-(U9-IS)" U9.4` reports U9.4's F.Cu pocket as UNBOUNDED
# (420.86 mm2 inside a +/-32 mm window) with 122152 via sites that clear both the copper rule
# and the 0.30 mm hole-to-hole floor.  Whoever closes this net can put a via wherever the route
# wants one.
#
# Contrast /outputs/PWM_RR_B, whose frozen entry has the same shape -- zero segments, one via,
# at (158.500, 51.700) in Q9.5 -- and which is NOT named here.  Step 6.4 measured that pad's
# pocket as sealed: 7 copper-legal via sites, all 7 failing the hole-to-hole floor against that
# same frozen drill.  Its via is the only layer change Q9.5 has, so dropping it would trade a
# dangling-via item for the loss of the net's only escape from F.Cu.  It stays, and stays
# reported.
#
# This does not reopen the Step 6.4 question below.  That question was whether to drop a net
# that SEALS another net's via pocket, where the copper thrown away is 20-96 mm of real route
# and the cost is re-authoring it here by hand.  Here there is no route to throw away at all.
#
# Step 6.4 measured what naming a net here would buy on the two widest sealed pockets.  Each
# pocket IS sealed by one identifiable net's frozen copper rather than by geometry, but in every
# case that net is one the board currently has closed, so neither is named above.  Every figure
# below is from scripts/show_pocket.py, which is committed for exactly this reason -- reproduce
# any of them with `python scripts/show_pocket.py NET REF.PAD` (prefix MSYS_NO_PATHCONV=1 in
# Git Bash or the leading slash in the net name is read as a path):
#
#   /outputs/PWM_RL_G, pad Q7.5 (172.888, 51.200).  Its reachable F.Cu pocket is 2745 cells of
#   0.05 mm (6.86 mm2, and 6.92 mm2 at a quarter of that pitch) and holds no legal 0.50/0.20 via
#   site anywhere, so the net cannot leave F.Cu at this pad; the nearest miss is (170.000,
#   52.300), short by 0.029 mm against a /outputs/PWM_FR_B via.  The pocket is not a thin
#   corridor -- the widest all-legal disc of F.Cu track centres inside it has radius 0.598 mm,
#   at (172.050, 49.450) -- so what denies the via is copper on the other three signal layers,
#   not the width of this one.  Dropping any one of /outputs/PWM_RL_B (50 segments, 13 vias,
#   85.36 mm), /outputs/SENSE_RL_B (33, 9, 80.87 mm) or /outputs/SENSE_RL_G (59, 10, 95.99 mm)
#   opens the pocket and puts the rest of PWM_RL_G's own frozen copper in reach, but only at
#   R47.1: the hand run needed is 48.5 mm straight-line, and the dropped net's 81-96 mm has to
#   be re-authored here in full.
#
#   /outputs/PWM_RR_B, pad Q9.5 (158.388, 51.700).  Q9.5 is NOT sealed.  The router left this
#   net a via-in-pad at (158.500, 51.700) and no track at all, so Q9.5 already reaches all four
#   signal layers.  Its F.Cu pocket does hold 7 copper-legal via sites, and all 7 fail the
#   0.30 mm hole-to-hole floor against that same frozen drill (best -0.200 mm, at (158.800,
#   51.700) against the 0.20 mm drill at (158.500, 51.700)), which is why an
#   earlier count of "0 legal sites" here was both wrong and harmless: the net does not need a
#   new via at this pad.  The seals are the other two pads.  R51.1 (147.255, 56.830) has the
#   widest pocket measured on this board, 4438 cells (11.10 mm2), with no legal via site at all,
#   and /outputs/PWM_FL_G (22 segments, 2 vias, 20.24 mm) is the only single drop that both
#   frees it and connects it to Q9.5.  U7.18 (148.812, 30.975) has a 156-cell pocket (0.39 mm2)
#   whose best via position is 0.450 mm short, bound by /outputs/MUXIN_RL_B on In2.Cu -- the one
#   net that frees it (31 segments, 9 vias, 57.71 mm).  Closing PWM_RR_B needs both drops, not
#   one, plus 38 mm of new hand run, because it has no frozen copper of its own to join.
#
# And the cheap-looking drops are the expensive ones.  /outputs/PWM_FL_G and /outputs/PWM_FL_R
# are the only two nets whose ROUTES run above changes layer on a via this file does not place:
# PWM_FL_G at (159.600, 52.000) and PWM_FL_R at (148.500, 54.000), each its own net's frozen
# via, which is what check_via_holes' docstring in gen_pcb.py recommends doing where the router
# already has a via to hand.  Dropping either net's frozen copper therefore severs that net's
# own hand route as well as orphaning the pad the router reached through it -- Q4.5 and Q4.2
# respectively -- so the 20.24 mm above is the cost of the copper, not of the change.
#
# The authority for all of the above is scripts/show_pocket.py, which is committed and rerunnable;
# the narrative version, with the candidate tables and the recommendation that the remaining
# shortfall is placement in the U7/U8/Q7/Q9 output bank rather than routing, is in
# .superpowers/sdd/2026-09-23-pcb-relayout-8layer/task-10-step6.4-report.md -- which .gitignore
# excludes, so it is in the working tree and not in a clone.
FROZEN_DROP = (
    "Net-(U3-VCC)",     # a lone fanout via in R15.1, no track; the net is hand-routed above
    "Net-(U9-IS)",      # a fanout via in U9.4 and two stubs to nowhere; the net is open either way
)
