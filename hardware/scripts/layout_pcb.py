"""Plan4 board layout data: outline, stack, rules, placement and routes (phase B).

Spec: docs/superpowers/specs/2026-11-13-board-layout-phase-b-design.md.  gen_pcb.py reads this
module; nothing here draws copper by itself.  The plan3 module this replaces (200 x 140 mm, RGB
stage) is kept for reference at hardware/archive/layout_pcb_plan3.py and is NOT a starting point.

FABRICATOR: JLCPCB, 8-layer FR-4, 1.6 mm.  Capability read from
https://jlcpcb.com/capabilities/pcb-capabilities on 2026-11-13 (multilayer column):
  trace / space, 1 oz ............ 0.09 / 0.09 mm (3.5 / 3.5 mil)
  trace / space, 2 oz ............ 0.15 / 0.15 mm
  via hole / via pad ............. 0.15 / 0.25 mm minimum; 0.2 mm hole preferred
  PTH annular ring, 1 oz ......... 0.15 mm absolute, 0.20 mm recommended
  hole-to-hole ................... via 0.2 mm, pad 0.45 mm (not split by net)
  via hole to track .............. 0.2 mm
  copper to routed edge .......... >= 0.2 mm
  copper, outer / inner .......... 1 or 2 oz / 0.5 (default), 1 or 2 oz
  silkscreen ..................... text height >= 1.0 mm, line >= 0.15 mm
  solder-mask bridge, 1 oz ....... 0.10 mm (green)
JLC_FLOOR holds those numbers; check_frame.py asserts every project rule is at or above them.
The project rules (RULES) are deliberately looser than the floor: nothing on this board needs
the fab's limit, and a margin costs nothing at JLCPCB's standard multilayer price.

STACKUP: 1.6 mm, outer 1 oz, inner 1 oz (JLCPCB's 1 oz inner option, not the 0.5 oz default:
the feed-B return and the pod outputs carry 6.4 A / 3.2 A and may need inner copper, spec 5.2).
No controlled impedance is ordered: CAN at 500 kbit/s does not need it.  The dielectric table
in gen_pcb.STACKUP_SEXPR is nominal; JLCPCB builds its standard 8-layer 1.6 mm press.
"""

# ---------------------------------------------------------------- outline
BOARD_W, BOARD_H = 140.0, 100.0
X0, Y0 = 20.0, 20.0
X1, Y1 = X0 + BOARD_W, Y0 + BOARD_H
EDGE_R = 1.0          # corner radius, drawn as four arcs
MOUNT_INSET = 5.0     # M3 mounting holes, centre inset from each corner
MOUNT_DRILL = 3.2
MOUNT_PAD = 6.0       # keep-clear diameter around each hole (M3 washer / standoff)

# Every cable leaves through one 140 mm edge (spec goal 5); the ESP32 antenna goes on the
# opposite edge (goal 6).  KiCad y grows downwards, so "bottom" is y = Y1.
CABLE_EDGE = "bottom"
ANTENNA_EDGE = "top"

# ---------------------------------------------------------------- stack
# (layer, role).  The GND_IN and GND_B regions are cut out of every GND plane under their
# own footprints (zones, Task 5); the separation rules are spec 5.2.
STACKUP = [
    ("F.Cu", "parts and signal"),
    ("In1.Cu", "GND plane"),
    ("In2.Cu", "signal"),
    ("In3.Cu", "power: VBAT / VBAT_B / +3V3_ALW / +5V areas"),
    ("In4.Cu", "GND plane"),
    ("In5.Cu", "signal"),
    ("In6.Cu", "GND plane"),
    ("B.Cu", "signal and pours (no parts)"),
]

# ---------------------------------------------------------------- rules
JLC_FLOOR = {
    "track": 0.09, "clearance": 0.09, "via_diameter": 0.25, "via_drill": 0.15,
    "annular_ring": 0.15, "hole_to_hole": 0.45, "hole_to_track": 0.2, "copper_to_edge": 0.2,
    "silk_text_height": 1.0, "silk_line_width": 0.15,
}

# The project's DRC minima (written into mccan.kicad_pro by gen_netclasses.py).
RULES = {
    "min_track_width": 0.15,
    "min_clearance": 0.15,
    "min_connection": 0.2,
    "min_via_diameter": 0.5,
    "min_through_hole_diameter": 0.2,
    "min_via_annular_width": 0.15,
    "min_hole_to_hole": 0.45,
    "min_hole_clearance": 0.25,
    "min_copper_edge_clearance": 0.5,
    "min_text_height": 1.0,
    "min_text_thickness": 0.15,
    "min_microvia_diameter": 0.2,
    "min_microvia_drill": 0.1,
    "min_silk_clearance": 0.0,
    "min_groove_width": 0.0,
    "min_resolved_spokes": 2,
}

NETCLASSES = [
    # name, track width, clearance, via size, via drill, nets
    # Widths are interactive defaults only; the power copper is laid as explicit routes and
    # pours (Task 6), sized by IPC-2152 there.
    ("FEED_B", 2.5, 0.3, 0.8, 0.4, ["FEED_B_P", "VBAT_B", "GND_B", "POD_L_P", "POD_R_P"]),
    ("FEED", 1.0, 0.3, 0.8, 0.4, ["FEED_P", "MID", "VBAT_F", "VBAT_PROT", "VBAT", "GND_IN"]),
    ("POWER", 0.5, 0.2, 0.6, 0.3, ["VLOGIC_IN", "+5V", "+3V3_ALW"]),
    ("CAN", 0.3, 0.2, 0.6, 0.3, ["CANH", "CANL", "Net-(U6-CANH)", "Net-(U6-CANL)"]),
]

# ---------------------------------------------------------------- placement (Task 4)
# Floorplan (KiCad y grows down; the cable edge is y = Y1 = 120, the antenna edge y = Y0 = 20):
#
#   y 20  | feed A (L2, Q10/Q11, ...) | rails       | U5 ESP32, antenna flush at top | service |
#         |                           |-------------|  module body                   | J2 SW   |
#   y 50  |                           | TP bank 1   |  MCU support                   |---------|
#         |                           | outputs     |                                | TP bk 2 |
#         |                           | U11-U13     |  CAN (U6 L6 D6)  |  feed B + aux (U14 ...) |
#   y 97  |  J1  |    J3    |   J4   |  J5  | J8 |   J10   | J9 |   J11   |  <- cable edge
#
# CABLE ROW.  One row fits: the eight tail courtyards total 122.2 mm against the 123.1 mm
# between the bottom mounting holes' courtyards (28.45 .. 151.55), so no stagger is needed.
# Every tail is at rot 0, which puts its strain-relief holes (local +y) at the cable edge:
# all relief holes sit on y = TAIL_RELIEF_Y, 3 mm in from the edge.  Order, left to right:
# feed A | front | rear 1, rear 2 (one 7-core cable, so adjacent: one gland) | CAN | pod L,
# feed B, pod R (feed B between its two loads keeps both 3.2 A paths short).
TAIL_RELIEF_Y = Y1 - 3.0
_R15, _R10, _R05 = 18.0, 16.2, 12.6       # relief-hole offset from pad 1, by wire gauge
CABLE_ROW = [  # ref, x of pad 1 (origin), relief offset
    ("J1", 30.75, _R15),
    ("J3", 40.90, _R05),
    ("J4", 63.00, _R05),
    ("J5", 80.50, _R05),
    ("J8", 93.40, _R05),
    ("J10", 102.00, _R10),
    ("J9", 122.65, _R15),
    ("J11", 133.10, _R10),
]

# U5: rot 0 puts the antenna (footprint -y) toward the top edge; the body edge at local
# y = -12.75 is placed ON y = Y0 (flush, Espressif's module-on-edge placement).  Its library
# courtyard includes the 15 mm antenna clearance beyond the body, which hangs off the board on
# purpose -- hence OFFBOARD_OK.
U5_X = 115.0
U5_Y = Y0 + 12.75

PLACE = dict((ref, (x, TAIL_RELIEF_Y - off, 0)) for ref, x, off in CABLE_ROW)
PLACE.update({
    "U5": (U5_X, U5_Y, 0),
    # FEED A, bottom-up, all on the GND_IN side of L2 until L2 itself:
    #   J1.1 FEED_P -> Q10 (rot 0: source left, drain tab right) -> MID -> Q11 (rot 180: drain
    #   tab left, source right) -> SNS -> R100 (rot 90, SNS pad at the bottom) -> VBAT_PROT ->
    #   L2 pin 1.  L2 at rot 0 has its input row (1 VBAT_PROT, 2 GND_IN) at the bottom and its
    #   output row (4 VBAT_F, 3 GND) 10.7 mm above: the GND_IN / GND boundary (SPLIT_Y) runs
    #   between the two rows, so L2 and R3 (the DNP link across winding B) straddle it.
    "Q10": (31.5, 86.0, 0),
    "Q11": (46.5, 86.0, 180),
    "R100": (52.5, 76.5, 90),
    # Kelvin sense: U10 pin 4 (SNS) and pin 5 (VBAT_PROT) face R100 (check_placement: <= 8 mm).
    "U10": (58.5, 77.0, 0),
    "L2": (35.0, 66.0, 0),
    "R3": (53.5, 60.6, 90),     # pad 1 GND_IN below SPLIT_Y, pad 2 GND above
    "R2": (57.8, 60.6, 90),     # pad 1 VBAT_PROT below, pad 2 VBAT_F above
    "NT1": (58.5, 88.5, 0),     # star tie: pad 2 GND_IN here, pad 1 GND_B by a 2 mm track
    # FEED B: J9 -> Q13 -> VBAT_B -> U14, bulk at U14's exposed pad (pad 15, VBAT_B).  Every
    # GND_B pad sits inside the GND_B region R_B (zones below); U14 itself does not -- its
    # ground pin is logic GND -- so it sits just outside R_B's top edge.
    "Q13": (117.0, 89.0, 0),
    "U14": (128.0, 90.0, 0),
    "C67": (128.0, 94.8, 0),
    "C68": (139.5, 89.0, 0),
    "C66": (149.5, 85.0, 0),
    "D25": (153.5, 91.0, 0),
    "C69": (106.0, 95.5, 0),
    "C70": (136.0, 96.2, 0),
})

# Test points.  Each pad gets its NET NAME on the silkscreen to its right (spec 8; drawn in the
# silkscreen pass), so a bank column is TP_COL mm wide: 1.5 mm pad + the longest label
# ("VLOGIC_IN", ~8 mm at 1 mm text) + gaps.  Bank 1 is 4 columns x 6 rows around TP6 (GND);
# its farthest pad is ~17 mm from TP6 (spec 8: within probe-clip reach of a GND pad,
# check_placement: <= 25 mm).  Bank 2 is the feed-B group around TP3 (GND_B).  TP30 (GND_IN)
# sits in the feed-A corner so the ground split can be checked on the bench.
TP_COL, TP_ROW = 10.5, 3.0
_BANK1 = [  # columns, top to bottom
    ["TP1", "TP27", "TP4", "TP5", "TP28", "TP29"],
    ["TP15", "TP16", "TP6", "TP7", "TP12", "TP13"],
    ["TP14", "TP17", "TP18", "TP19", "TP20", "TP21"],
    ["TP22", "TP23", "TP24", "TP25", "TP26", None],
]
BANK1_X, BANK1_Y = 64.0, 52.0
for _i, _col in enumerate(_BANK1):
    for _j, _tp in enumerate(_col):
        if _tp:
            PLACE[_tp] = (BANK1_X + _i * TP_COL, BANK1_Y + _j * TP_ROW, 0)
_BANK2 = [["TP2", "TP3", "TP10"], ["TP11", "TP8", "TP9"]]
BANK2_X, BANK2_Y = 139.0, 61.0
for _i, _col in enumerate(_BANK2):
    for _j, _tp in enumerate(_col):
        PLACE[_tp] = (BANK2_X + _i * TP_COL, BANK2_Y + _j * TP_ROW, 0)
PLACE["TP30"] = (52.0, 94.0, 0)

REGIONS = {
    "feedA_out": (X0, Y0, 62.0, 60.1),     # GND side of L2
    "feedA_in": (X0, 61.6, 62.0, 96.0),    # GND_IN side of L2
    "rails": (62.0, Y0, 90.5, 50.0),
    "tpbank": (62.0, 50.0, 104.5, 68.5),   # bank 1 only; nothing auto-flows here
    "mcu": (104.5, 46.5, 139.5, 74.0),
    "service": (139.5, 29.0, X1, 59.5),
    "outputs": (62.0, 68.5, 98.5, 96.0),
    "can": (86.0, 74.0, 112.0, 92.0),
    "aux": (106.0, 66.0, X1, 81.5),         # logic-GND parts of the aux stage, above R_B
}
SHEET_REGION = {
    "power_input": "feedA_out",
    "rails": "rails",
    "mcu_can": "mcu",
    "outputs": "outputs",
}
BLOCK = {}
for _r in ("D24", "R78", "R79", "R80",
           "U15", "U16", "C71", "C72", "R74", "R75", "R76", "R77",
           "R81", "R82", "R83", "R84", "R85", "R86", "R87", "D26", "D27"):
    BLOCK[_r] = "aux"
for _r in ("C62", "C63", "C64", "C65", "D2", "D21", "D22", "D23", "Q12",
           "R101", "R102", "R103", "R104", "R105", "R106", "R107"):
    BLOCK[_r] = "feedA_in"
for _r in ("U6", "L6", "D6", "R26", "R24", "R25"):
    BLOCK[_r] = "can"
for _r in ("J2", "SW1", "SW2", "Q2", "Q3", "R28", "R29", "R22", "C37"):
    BLOCK[_r] = "service"

# A test pad keeps 1 mm clear around it (check_placement), plus its label's room to the right,
# which the auto-flow must not take: the banks' columns are reserved as one block each.
KEEPCLEAR = dict((tp, 1.0) for tp in PLACE if tp.startswith("TP"))
RESERVED = [  # (x0, y0, x1, y1) marked occupied for the auto-flow (test-pad banks + labels)
    (BANK1_X - 2.0, BANK1_Y - 2.0, BANK1_X + 3 * TP_COL + 9.5, BANK1_Y + 5 * TP_ROW + 2.0),
    (BANK2_X - 2.0, BANK2_Y - 2.0, BANK2_X + TP_COL + 9.5, BANK2_Y + 2 * TP_ROW + 2.0),
    (PLACE["TP30"][0] - 2.0, PLACE["TP30"][1] - 2.0, PLACE["TP30"][0] + 9.5, PLACE["TP30"][1] + 2.0),
]
NUDGE = {}            # ref -> (dx, dy) applied after the auto-flow
OFFBOARD_OK = {"U5"}  # antenna clearance courtyard overhangs the top edge by design

# Rule areas (KiCad keep-outs): name, (x0, y0, x1, y1), layers.  The antenna keep-out is the
# rectangle check_antenna.py tests: module body +/- 15.25 mm wide, from the body edge to 6.44 mm
# in (datasheet Fig. 12 antenna area 6.19 mm + 0.25), on every copper layer.
KEEPOUTS = [
    ("ANTENNA", (U5_X - 24.25, Y0, U5_X + 24.25, U5_Y - 6.31), ["*.Cu"]),
]

# ---------------------------------------------------------------- copper (Tasks 5-7)
# Three grounds (spec 5.2; check_grounds.py proves the split):
#   R_IN  GND_IN island, feed A connector side: J1, Q10/Q11, R100, U10 and its parts, NT1.2,
#         L2's input row.  Bounded above by SPLIT_Y, between L2's two pad rows.
#   R_B   GND_B region, feed B: J10/J9/J11 pin 2s, C66-C70, D25.  Its top edge clears U14.
#   GND   everything else, on the three plane layers, cut back SPLIT_GAP from both regions.
SPLIT_Y = 61.1
SPLIT_GAP = 1.0
_IN_X, _IN_TAIL_X = 62.0, 39.05      # R_IN right edge; right edge of its J1 strip
_B_X, _B_Y, _B_CX, _B_CY = 99.8, 93.0, 132.5, 82.0   # R_B: strip left edge / top, C68 block
R_IN = [(X0, SPLIT_Y), (_IN_X, SPLIT_Y), (_IN_X, 97.0), (_IN_TAIL_X, 97.0), (_IN_TAIL_X, Y1),
        (X0, Y1)]
R_B = [(_B_X, _B_Y), (_B_CX, _B_Y), (_B_CX, _B_CY), (X1, _B_CY), (X1, Y1), (_B_X, Y1)]
_g = SPLIT_GAP
# The planes are also cut back from the antenna keep-out (0.5 mm beyond it), so no copper is
# drawn there at all -- the rule area is the second line of defence, not the first.
_AX0, _AX1, _AY1 = U5_X - 24.25 - 0.5, U5_X + 24.25 + 0.5, U5_Y - 6.31 + 0.5
GND_POLY = [(X0, Y0), (_AX0, Y0), (_AX0, _AY1), (_AX1, _AY1), (_AX1, Y0), (X1, Y0), (X1, _B_CY - _g), (_B_CX - _g, _B_CY - _g),
            (_B_CX - _g, _B_Y - _g), (_B_X - _g, _B_Y - _g), (_B_X - _g, Y1),
            (_IN_TAIL_X + _g, Y1), (_IN_TAIL_X + _g, 97.0 + _g), (_IN_X + _g, 97.0 + _g),
            (_IN_X + _g, SPLIT_Y - _g), (X0, SPLIT_Y - _g)]
# In3 power areas.  VBAT: L1/C3 (feed A output) across the rails and the quads, stopping short
# of the antenna keep-out and of R_IN.  VBAT_B: Q13 -> U14 VS -> C66-C68 / D25.
VBAT_POLY = [(X0, Y0), (89.5, Y0), (89.5, 60.0), (98.5, 60.0), (98.5, 97.0), (_IN_X + _g, 97.0),
             (_IN_X + _g, SPLIT_Y - _g), (X0, SPLIT_Y - _g)]
VBATB_POLY = [(112.0, _B_CY), (X1, _B_CY), (X1, 97.0), (112.0, 97.0)]
PLANES = ["In1.Cu", "In4.Cu", "In6.Cu"]
ZONES = []    # (net, [layers], poly, name, priority)
for _l in PLANES:
    _n = _l.split(".")[0]
    ZONES += [("GND", [_l], GND_POLY, "GND_" + _n, 0),
              ("GND_IN", [_l], R_IN, "GNDIN_" + _n, 0),
              ("GND_B", [_l], R_B, "GNDB_" + _n, 0)]
ZONES += [("GND_B", ["B.Cu"], R_B, "GNDB_B", 0),
          ("VBAT", ["In3.Cu"], VBAT_POLY, "VBAT_In3", 0),
          ("VBAT_B", ["In3.Cu"], VBATB_POLY, "VBATB_In3", 0)]

# Stitching vias, 0.6 / 0.3 through: (net, region polygon, pitch mm).  Laid on a grid inside the
# region, at least STITCH_INSET from its edge and clear of every courtyard, keep-out, reserved
# test-pad block and mounting hole (gen_pcb.stitch_vias).  GND_B is densest: it carries 6.4 A
# across four layers and the vias are what share it between them.
STITCH_INSET = 1.0
STITCH = [("GND", GND_POLY, 8.0), ("GND_IN", R_IN, 5.0), ("GND_B", R_B, 4.0)]
# (net, layer, width, [(x, y), ...], tag) / (net, x, y, size, drill, tag)
# VBAT drop (Task 5): L1 pad 2 is where feed A's VBAT is born, and every VBAT pad on the board is
# SMD on F.Cu -- without vias the In3 VBAT area is an island tied to nothing.  A 2.5 mm stub east
# to three 0.8 / 0.4 vias (0.9 A for feed A today; three barrels are ~3 A).
_L1V_X = 59.5
ROUTES = [
    ("VBAT", "F.Cu", 2.5, [(55.46, 26.0), (_L1V_X, 26.0)], "vbat_drop"),
    ("VBAT", "F.Cu", 1.2, [(_L1V_X, 24.6), (_L1V_X, 27.4)], "vbat_drop_bar"),
]
ROUTE_VIAS = [("VBAT", _L1V_X, 24.6 + 1.4 * i, 0.8, 0.4, "vbat_drop%d" % i) for i in range(3)]

# ---------------------------------------------------------------- drawing notes
NOTES = [
    # (text, x, y, layer, size)
    ("MCCAN plan4 board, 140 x 100 mm, 8 layers, 1.6 mm, 1 oz all layers.\n"
     "GENERATED by hardware/scripts/gen_pcb.py from layout_pcb.py -- do not edit in pcbnew.\n"
     "Cable edge: bottom.  Antenna edge: top.  Single-sided assembly (F.Cu).",
     X0, Y1 + 6.0, "Cmts.User", 1.5),
]
