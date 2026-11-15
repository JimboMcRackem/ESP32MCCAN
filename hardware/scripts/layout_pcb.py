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
    "min_connection": 0.15,   # = min_track_width: a legal 0.15 mm track IS a 0.15 mm connection (Task 7)
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

# The three output quads (Task 7): centres in a row, 8 mm apart, rotated 90.
QUAD_X, QUAD_Y = (66.35, 74.35, 82.35), 75.7   # x.x5: puts the 0.5 mm-pitch pins on the 0.1 mm routing grid
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
    # star tie, rot 180: pad 2 GND_IN on the left inside R_IN, pad 1 GND_B on the right facing
    # the 1 mm R_IN / GND gap, where its vias drop to the 2 mm B.Cu tie to R_B (Task 6).
    "NT1": (58.5, 88.5, 180),
    # FEED B: J9 -> Q13 -> VBAT_B -> U14, bulk at U14's exposed pad (pad 15, VBAT_B).  Every
    # GND_B pad sits inside the GND_B region R_B (zones below); U14 itself does not -- its
    # ground pin is logic GND -- so it sits just outside R_B's top edge.
    "Q13": (117.0, 89.0, 0),
    # Q14 in parallel with Q13 (enclosure.md s.9: one FET alone runs > 125 C).  North of Q13,
    # same orientation: tab east on the FEED_B_P pours, source pins west on the VBAT_B pour.
    # Its thermal vias stay north of the POD_L In2 trunk at y 82.4.
    "Q14": (117.0, 77.5, 0),
    "U14": (128.0, 90.0, 0),
    "C67": (128.6, 94.4, 270),  # under U14: pad 1 VBAT_B up toward pad 15, pad 2 GND_B down
    "C68": (139.5, 89.0, 0),
    "C66": (149.5, 85.0, 0),
    "D25": (153.5, 91.0, 0),
    "C69": (106.0, 95.5, 0),
    "C70": (136.0, 96.2, 0),
    # Q13's gate network (Task 6: auto-flow had put R108 in feed A's corner and D24 in aux).
    # D24 (gate clamp) pad 1 sits in the VBAT_B source pour; R108 (gate pull-down) pad 2 GND_B
    # sits inside R_B, below the feed-B pours.
    "D24": (110.0, 91.6, 0),
    "R108": (113.0, 94.3, 270),
    # CAN protection at the connector (Task 6): J8 -> D6 (ESD, rot 90: CANH/CANL pins face J8,
    # GND up) -> R26 (termination) -> a coupled F.Cu pair up to L6's bus side.
    "D6": (95.7, 100.6, 90),
    "R26": (95.7, 97.4, 0),
    # Pinned where the Task 5 auto-flow put them, because Task 6's hand routes land on their
    # pads: the flow now steers round F.Cu routes (gen_pcb.place) and would otherwise move them.
    "C1": (46.58, 33.83, 0), "C2": (36.8, 34.08, 0), "C3": (36.25, 26.1, 0),
    "C4": (31.4, 34.25, 0), "D3": (24.1, 31.35, 0), "L1": (50.95, 26.0, 0),
    # Task 7: the quads turned 90 so their control pins (IN, SEL, DIAG, SNS, ILIM, GND) face
    # south to the resistor field and VS / OUT face north.  Side by side at rot 0, each chip's
    # control pins faced the next chip's OUT pins across a 2.15 mm gap that both sides needed
    # for escape vias, and the router left eleven of their nets open.  C41-C43 (VS decoupling)
    # sit north of each chip's VS pins, fed by the VS bar's drop (ROUTES).
    "C41": (QUAD_X[0], QUAD_Y - 5.1, 90), "C42": (QUAD_X[1], QUAD_Y - 5.1, 90),
    "C43": (QUAD_X[2], QUAD_Y - 5.1, 90),
    "U11": (QUAD_X[0], QUAD_Y, 90), "U12": (QUAD_X[1], QUAD_Y, 90), "U13": (QUAD_X[2], QUAD_Y, 90),
    "C65": (25.3, 75.25, 0), "D2": (55.75, 67.45, 0), "Q12": (22.53, 63.9, 0),
    "R101": (57.38, 72.33, 0), "R104": (22.08, 83.93, 0), "R105": (33.88, 72.83, 0),
    "U6": (90.3, 77.3, 0), "L6": (98.8, 76.55, 0),
    # outputs-sheet parts the flow otherwise spills into the GND_IN island (their GND pads
    # would land over GND_IN).  Task 7: moved from (105, 84.5/86.5), which sat inside the
    # GND_B region R_B -- they carry SNS_B / SNS_C, which must stay out of feed B -- into free
    # cells of the outputs sense grid beside R70.
    "R72": (93.08, 94.83, 0), "R73": (88.58, 97.83, 0),
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
    ["TP26", None, "TP6", "TP7", "TP12", "TP13"],
    ["TP14", "TP17", "TP18", "TP19", "TP20", "TP21"],
    ["TP22", "TP23", "TP24", "TP25", "TP16", "TP15"],   # CAN TPs nearest L6 (Task 6)
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
    "outputs": (63.0, 68.5, 98.5, 102.5),   # to the cable-tail courtyards (Task 6: routes took room)
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
    # U10 ON (pin 9).  Written when ON was open on its 1 Mohm pull-up (leakage < 1 uA).  ON is
    # now tied to VCC10 (2026-11-15), so this keep-out is belt-and-braces, not load-bearing:
    # no pour, track or via on In1 (the GND_IN plane directly beneath) within 0.6 mm of the pad.
    ("U10_ON", (59.25, 75.73, 61.95, 77.27), ["In1.Cu"]),
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
# reaches Q13's via array; the notch north of _B_CY reaches Q14's source vias
VBATB_POLY = [(107.0, 74.6), (116.0, 74.6), (116.0, _B_CY), (X1, _B_CY), (X1, 97.0), (107.0, 97.0)]
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
# Power pours connect their pads solid: two 0.4 mm thermal spokes per layer give J9.2 3.2 mm of
# copper across its four GND_B layers against the 6.1 mm 6.4 A needs (check_power_paths.py).
ZONES = [z + ("solid",) if z[0] in ("GND_B", "VBAT_B") else z for z in ZONES]
# FEED B (Task 6).  FEED_B_P: J9.1 -> Q13's drain tab on F.Cu and In5 (two layers in parallel,
# 6.5 mm wide at J9 where the pour squeezes between J10.4 and J9.2), plus B.Cu under Q13 for its
# thermal-via array (gen_pcb.thermal_vias: FEED_B_P is a planed net).  VBAT_B: Q13's source
# pins (1-3) and D24's anode on an F.Cu pour west of Q13, dropped by 12 vias to In3.
FEEDB_POLY = [(115.8, 74.6), (124.0, 74.6), (124.0, 93.3), (126.5, 93.3), (126.5, 102.4),
              (119.95, 102.4), (119.95, 96.5), (115.8, 92.2)]
# F.Cu only: a notch beside U14's west pins (2-6: IN_AUX_L, DEN, IS, DSEL, IN_AUX_R).  Those
# pads end at x 124.5, half a millimetre from the pour, and every one of them has to reach the
# ESP32 west across feed B.  Through the F.Cu pour is a slot in a 6.4 A path; so the pour steps
# back 1.4 mm here, the control lines drop to In2 (no pour under feed B there) in the notch, and
# FEED_B_P keeps 6.4 mm or more of F.Cu, with the full-width In5 pour beside it.
FEEDB_NOTCH_X, FEEDB_NOTCH_Y0, FEEDB_NOTCH_Y1 = 122.6, 87.4, 92.6
FEEDB_F_POLY = [(115.8, 74.6), (124.0, 74.6), (124.0, FEEDB_NOTCH_Y0),
                (FEEDB_NOTCH_X, FEEDB_NOTCH_Y0), (FEEDB_NOTCH_X, FEEDB_NOTCH_Y1),
                (124.0, FEEDB_NOTCH_Y1), (124.0, 93.3), (126.5, 93.3), (126.5, 102.4),
                (119.95, 102.4), (119.95, 96.5), (115.8, 92.2)]
FEEDB_BOT = [(115.5, 74.6), (124.0, 74.6), (124.0, 92.4), (115.5, 92.4)]
VBATB_SRC = [(107.6, 74.6), (114.64, 74.6), (114.64, 90.25), (109.4, 90.25), (109.4, 92.6),
             (107.6, 92.6)]
ZONES += [("FEED_B_P", ["F.Cu"], FEEDB_F_POLY, "FEEDB_F", 0, "solid"),
          ("FEED_B_P", ["In5.Cu"], FEEDB_POLY, "FEEDB_In5", 0, "solid"),
          ("FEED_B_P", ["B.Cu"], FEEDB_BOT, "FEEDB_B", 0, "solid"),
          ("VBAT_B", ["F.Cu"], VBATB_SRC, "VBATB_F", 0, "solid")]
RESERVED += [(115.5, 74.6, 126.5, 102.4), (107.0, 74.6, 116.0, 92.6)]
# Task 7: a strip south of each quad, kept from the auto-flow, for its silk designator (vertical
# at rot 90, ~3 mm tall; C4x takes the north side and the neighbouring chips are ~1 mm away
# east and west) and as the first few millimetres of the control pins' escape fan.
RESERVED += [(_qx - 1.5, QUAD_Y + 2.95, _qx + 1.5, QUAD_Y + 6.6) for _qx in QUAD_X]

# Stitching vias, 0.6 / 0.3 through: (net, region polygon, pitch mm).  Laid on a grid inside the
# region, at least STITCH_INSET from its edge and clear of every courtyard, keep-out, reserved
# test-pad block and mounting hole (gen_pcb.stitch_vias).  GND_B is densest: it carries 6.4 A
# across four layers and the vias are what share it between them.
STITCH_INSET = 1.0
STITCH = [("GND", GND_POLY, 8.0), ("GND_IN", R_IN, 5.0), ("GND_B", R_B, 4.0)]
# ---------------------------------------------------------------- hand routes (Task 6)
# ROUTES: (net, layer, width, [(x, y), ...], tag); ROUTE_VIAS: (net, x, y, size, drill, tag).
# Everything here is frozen copper the autorouter (Task 7) must leave alone: FEED_P, MID, SNS,
# VBAT_PROT, VBAT_F, VBAT, FEED_B_P, VBAT_B, POD_L_P, POD_R_P, GND_B off the pours, the buck
# switch nodes and CANH/CANL.  Widths are IPC-2152 at a 20 K rise, 1 oz (check_power_paths.py):
# 6.4 A needs 6.1 mm, 3.2 A 1.57 mm, 1 A 0.16 mm; a 0.8 / 0.4 via barrel counts as 0.9 mm.
ROUTES = []
ROUTE_VIAS = []


def _t(net, layer, w, pts, tag):
    ROUTES.append((net, layer, w, pts, tag))


def _v(net, x, y, tag, size=0.8, drill=0.4):
    ROUTE_VIAS.append((net, x, y, size, drill, tag))


def _drop(net, pad, via_xy, tag, w=0.8, size=0.8, drill=0.4):
    """An SMD pad's stub to a via beside it (pads are F.Cu; the pours are inner)."""
    _t(net, "F.Cu", w, [pad, via_xy], tag)
    _v(net, via_xy[0], via_xy[1], tag, size, drill)


# VBAT drop at L1 (Task 5): where feed A's VBAT is born; three vias to the In3 VBAT area.
_L1V_X = 58.6   # clear of U1's bulk-cap GND via (Task 6)
_t("VBAT", "F.Cu", 2.5, [(55.46, 26.0), (_L1V_X, 26.0)], "vbat_drop")
_t("VBAT", "F.Cu", 1.2, [(_L1V_X, 24.6), (_L1V_X, 27.4)], "vbat_drop_bar")
for _i in range(3):
    _v("VBAT", _L1V_X, 24.6 + 1.4 * _i, "vbat_drop%d" % _i)

# ---- BUCKS.  LM5164 (SNVSAU4D) Section 7.4.2, Figure 7-19 "LM5164 Single-Sided PCB Layout
# Example": ceramic input cap close to VIN and GND; BST cap close to BST and SW; FB resistors
# very close to FB and GND; RON resistor close to the RON pin; thermal vias under the PAD
# (gen_pcb.thermal_vias, GND).  Here, per buck at IC centre (ux, 31.8):
#   input caps west of pins 1-2 (small 0805 hard against the pins, 1210 bulk beside it), both
#   with GND vias, so the hot loop VIN -> cap -> GND -> pin 1 is ~3 mm;
#   inductor north (rot 180: SW pad over pin 8, OUT pad over the input side); SW is one 0.8 mm
#   track pin 8 -> L, the shortest copper on the node;
#   BST cap east between pins 7 and 8; output caps west of the L OUT pad with their own GND via;
#   RON resistor below pin 4; FB divider, feed-forward and ripple-injection (Type 3) parts in a
#   column below pin 5, the injection resistor fed from SW by a 0.3 mm track down the east side,
#   away from FB.
def _buck(tag, ux, refs, vin, sw, extra=None):
    (u, lr, cs, cb, cbst, co1, co2, rron, rfbb, rfbt, cff, rinj, cinj) = refs
    yc = 31.8
    PLACE.update({u: (ux, yc, 0), lr: (ux + 0.3, 24.15, 180), cbst: (ux + 4.65, 30.52, 90),
                  cs: (ux - 4.7, 30.53, 90), cb: (ux - 7.4, 30.53, 90),
                  co1: (ux - 5.45, 22.9, 180), co2: (ux - 5.45, 25.4, 180),
                  rron: (ux - 4.6, 35.4, 180), rfbb: (ux + 4.6, 35.4, 0),
                  rfbt: (ux + 4.6, 37.0, 180), cff: (ux + 4.6, 38.6, 0),
                  rinj: (ux + 4.6, 40.2, 180), cinj: (ux + 4.6, 41.8, 0)})
    pl, pr = ux - 2.48, ux + 2.48
    p1, p2, p3, p4 = 29.89, 31.16, 32.44, 33.70
    # switch node
    _t(sw, "F.Cu", 0.8, [(pr, p1), (ux + 3.15, 29.2), (ux + 3.15, 25.0)], tag + "_sw_l")
    _t(sw, "F.Cu", 0.4, [(pr, p1), (ux + 4.65, 29.74)], tag + "_sw_bst")
    _t(sw, "F.Cu", 0.3, [(ux + 4.65, 29.74), (ux + 6.4, 29.74), (ux + 6.4, 39.4),
                         (ux + 5.43, 40.2)], tag + "_sw_inj")
    _t("Net-(%s-BST)" % u, "F.Cu", 0.3, [(pr, p2), (ux + 4.65, 31.30)], tag + "_bst")
    # input loop
    _t(vin, "F.Cu", 0.6, [(pl, p2), (ux - 4.7, 31.48)], tag + "_vin")
    _t(vin, "F.Cu", 0.8, [(ux - 4.7, 31.48), (ux - 7.4, 32.0)], tag + "_vin_b")
    _t("GND", "F.Cu", 0.6, [(pl, p1), (ux - 4.7, 29.58)], tag + "_gnd")
    _t("GND", "F.Cu", 0.8, [(ux - 4.7, 29.58), (ux - 7.4, 29.06)], tag + "_gnd_b")
    _drop("GND", (ux - 4.7, 29.58), (ux - 4.7, 28.3), tag + "_gv1", w=0.6)
    _drop("GND", (ux - 7.4, 29.06), (ux - 7.4, 27.8), tag + "_gv2", w=0.6)
    # output
    _t(vout_of[u], "F.Cu", 1.0, [(ux - 2.55, 24.15), (ux - 4.67, 24.15)], tag + "_out")
    _t(vout_of[u], "F.Cu", 0.6, [(ux - 4.67, 22.9), (ux - 4.67, 25.4)], tag + "_out_bar")
    _t("GND", "F.Cu", 0.6, [(ux - 6.23, 22.9), (ux - 6.23, 25.4)], tag + "_og_bar")
    _v("GND", ux - 6.23, 24.15, tag + "_ogv", 0.6, 0.3)
    # RON
    _t("Net-(%s-RON)" % u, "F.Cu", 0.25, [(pl, p4), (ux - 3.2, 34.6), (ux - 3.77, 35.4)],
       tag + "_ron")
    if extra:
        extra(ux, pl, p2, p3)


vout_of = {"U1": "+3V3_ALW", "U2": "+5V"}


def _u1_extra(ux, pl, p2, p3):
    _t("VLOGIC_IN", "F.Cu", 0.4, [(pl, p2), (pl, p3)], "b3_vin23")   # pins 2 and 3 are both VIN


def _u2_extra(ux, pl, p2, p3):
    PLACE["R19"] = (ux - 4.6, 37.0, 180)
    _drop("VBAT", (ux - 7.4, 32.0), (ux - 7.4, 33.7), "b5_vbat")


_buck("b3", 68.0, ("U1", "L4", "C7", "C6", "C8", "C10", "C11", "R4", "R6", "R5", "C9", "R17",
                   "C28"), "VLOGIC_IN", "SW_3V3", _u1_extra)
_buck("b5", 83.3, ("U2", "L5", "C13", "C12", "C14", "C16", "C17", "R7", "R9", "R8", "C15", "R18",
                   "C29"), "VBAT", "SW_5V", _u2_extra)

# ---- FEED A (1 A; 0.16 mm needed, routed 0.8-3 mm).  J1.1 -> Q10 -> MID -> Q11 -> SNS -> R100
# -> VBAT_PROT -> L2.1 ... L2.4 VBAT_F -> L1 -> VBAT.
_t("FEED_P", "F.Cu", 1.0, [(30.75, 98.0), (30.75, 96.5), (27.25, 93.0), (27.25, 90.0)], "feedp")
_t("FEED_P", "F.Cu", 0.4, [(21.25, 83.93), (21.25, 85.5), (26.9, 85.5)], "feedp_r104")
# Q12 / R105 (Q10 gate drive) take FEED_P off J1.1 on In2: Q10's gate pad sits on top of its
# source leads, so F.Cu has no way out of Q10.2 northward.
_t("FEED_P", "In2.Cu", 0.4, [(30.75, 99.0), (24.0, 92.25), (24.0, 74.5), (30.8, 72.83)], "feedp_in2")
_t("FEED_P", "In2.Cu", 0.4, [(24.0, 74.5), (21.59, 70.0), (21.59, 66.4)], "feedp_in2_q12")
_drop("FEED_P", (32.42, 72.83), (30.8, 72.83), "feedp_r105", w=0.4, size=0.6, drill=0.3)
_drop("FEED_P", (21.59, 64.85), (21.59, 66.4), "feedp_q12", w=0.4, size=0.6, drill=0.3)
_t("MID", "F.Cu", 3.0, [(36.5, 86.0), (41.5, 86.0)], "mid")
_drop("MID", (43.5, 82.0), (43.5, 80.9), "mid_v1", w=0.6, size=0.6, drill=0.3)
_t("MID", "In2.Cu", 0.6, [(43.5, 80.9), (48.5, 75.9), (48.5, 70.8), (55.92, 70.8)], "mid_in2")
_drop("MID", (55.92, 71.6), (55.92, 70.8), "mid_v2", w=0.6, size=0.6, drill=0.3)
_t("SNS", "F.Cu", 0.8, [(50.75, 82.2), (51.3, 79.6)], "sns")
# Kelvin sense (LTC4380 SNS / VCC sense, R100 = 33 mOhm): each trace joins R100 at its pad and
# nowhere else.  SNS leaves U10.4 west and lands on R100.1's U10-side corner; VBAT_PROT leaves
# U10.5 and crosses under it on In2 to R100.2 -- the two cannot both stay on F.Cu.
_t("SNS", "F.Cu", 0.2, [(56.4, 77.5), (55.2, 77.5), (53.9, 78.95)], "kelvin_sns")
# U10 ON (pin 9) tied to VCC10 (2026-11-15 robustness review): west from pad 9 between the pad
# rows, dropping to y 76.8 before x 58.7 to pass the TMR via at (57.8, 76.0) by 0.425 mm, and
# landing on VCC10's existing via under the body at (57.675, 76.8).  Clears the TMR track
# (y 76.0) and the GND_IN track to pad 8 (y 77.0) by 0.325 mm, pads 8 and 10 by 0.25 mm.
_t("VCC10", "F.Cu", 0.15, [(60.6, 76.5), (59.0, 76.5), (58.7, 76.8), (57.675, 76.8)], "u10_on")
_t("VBAT_PROT", "F.Cu", 0.2, [(56.4, 78.0), (55.5, 78.0), (55.0, 78.5), (55.0, 78.9)], "kelvin_vp1")
_v("VBAT_PROT", 55.0, 78.9, "kelvin_vp1", 0.6, 0.3)
_t("VBAT_PROT", "In2.Cu", 0.2, [(55.0, 78.9), (54.9, 74.4)], "kelvin_vp2")
_v("VBAT_PROT", 54.9, 74.4, "kelvin_vp3", 0.6, 0.3)
_t("VBAT_PROT", "F.Cu", 0.2, [(54.9, 74.4), (53.9, 73.9)], "kelvin_vp3")
_t("VBAT_PROT", "F.Cu", 1.0, [(51.3, 73.5), (49.5, 71.7), (49.5, 69.8), (36.6, 69.8), (35.0, 67.0)],
   "vprot")
_t("VBAT_PROT", "F.Cu", 1.0, [(52.6, 73.2), (53.6, 68.3)], "vprot_d2")
_t("VBAT_PROT", "F.Cu", 1.0, [(53.6, 67.45), (55.0, 65.5), (57.8, 64.0)], "vprot_r2")
_t("VBAT_PROT", "F.Cu", 0.8, [(34.5, 66.8), (30.0, 70.5), (24.0, 70.5), (22.6, 74.5)], "vprot_c65")
_t("VBAT_F", "F.Cu", 1.0, [(35.0, 55.3), (35.0, 50.0), (45.8, 39.2), (45.8, 28.0)], "vbatf")
_t("VBAT_F", "F.Cu", 1.0, [(35.0, 50.0), (56.0, 50.0), (57.8, 56.9)], "vbatf_r2")
# VBAT drops to In3 (every VBAT pad is SMD on F.Cu)
_drop("VBAT", (31.0, 27.0), (31.0, 28.4), "vbat_c3a")
_drop("VBAT", (33.1, 27.0), (33.1, 28.4), "vbat_c3b")
_drop("VBAT", (26.1, 30.6), (26.1, 29.3), "vbat_d3")
_drop("VBAT", (29.92, 34.9), (29.92, 36.3), "vbat_c4")
_drop("VBAT", (35.85, 34.6), (35.85, 36.0), "vbat_c2")
_drop("VBAT", (64.0, 52.0), (62.4, 52.0), "vbat_tp1", w=0.5, size=0.6, drill=0.3)
# Each quad (rot 90): pins 20-23 (VS) in a row 2.2 mm north of the chip centre, barred; the
# bar's centre drops north to an In3 via and on to C4x's VBAT pad (pad 1, 0.95 mm south of the
# cap's centre).  The drop runs up the 3 mm channel between OUT2 and OUT3, where only NC pins
# 19 and 24 sit beside VS.
for _qx, _q in zip(QUAD_X, ("u11", "u12", "u13")):
    _t("VBAT", "F.Cu", 0.3, [(_qx - 0.75, QUAD_Y - 2.2), (_qx + 0.75, QUAD_Y - 2.2)],
       "vbat_" + _q + "_bar")
    _drop("VBAT", (_qx, QUAD_Y - 2.2), (_qx, QUAD_Y - 3.6), "vbat_" + _q,
          w=0.5, size=0.6, drill=0.3)
    _t("VBAT", "F.Cu", 0.5, [(_qx, QUAD_Y - 3.6), (_qx, QUAD_Y - 4.15)], "vbat_" + _q + "_c")
    # GND pin 13 to the chip's own exposed pad (GND, with its thermal-via array): straight up
    # from the pad's inner end, clear of pins 12 and 14 by 0.225 mm, then onto the EP's corner.
    # The router could not weld it once ILIM (pin 12) had escaped beside it (U12, Task 7).
    _t("GND", "F.Cu", 0.25, [(_qx + 2.75, QUAD_Y + 1.7), (_qx + 2.75, QUAD_Y + 1.0),
                             (_qx + 2.2, QUAD_Y + 0.6)], "gnd13_" + _q)

# The quads' shared diagnostic bus, by hand (Task 7).  SEL1/SEL0/DIAG_EN are pins 6/7/8 -- the
# middle of the 0.5 mm control row -- and each net joins all three chips, so it has to cross
# every other quad's IN/CS/ILIM escapes heading south.  Left to the router, that box failed
# CS_B and DIAG_SEL0_Q on a near-empty board (pass 1b, route10).  Here each of the three pins
# drops to its own via in the room under NC pins 9 and 10, staggered 0.8 mm in y, and the
# three nets run east-west as parallel In2 buses (no pour on In2).  The router then sees only
# straight-south escapes for pins 2-5, 11 and 12, plus one via-to-driver link per bus.
#   pin 8 (EN, +0.25)   -> 45 deg east under pin 9 -> via (+1.0,  pad end + 0.725)
#   pin 7 (SEL0, -0.25) -> south, then 45 deg      -> via (+0.15, pad end + 1.525)
#   pin 6 (SEL1, -0.75) -> south, then 45 deg      -> via (-0.35, pad end + 2.325)
# Clearances (0.2 mm track, 0.6 mm via): via-to-via >= 0.94; the vias sit >= 0.75 off the
# pin-5 and pin-11 centre lines; the pin-8 diagonal clears pad 9 by 0.24 and the pin-7 track
# by 0.3; the In2 buses are 0.8 mm apart and clear each other's vias by 0.4.
_QPAD_END = QUAD_Y + 2.2 + 0.725                     # control pads' outer (south) end
DIAG_BUS = (("DIAG_EN_Q", 0.25, [(0.25, 0.125), (0.85, 0.725), (1.0, 0.725)]),
            ("DIAG_SEL0_Q", -0.25, [(-0.25, 1.125), (0.15, 1.525)]),
            ("DIAG_SEL1_Q", -0.75, [(-0.75, 1.925), (-0.35, 2.325)]))
for _qx, _q in zip(QUAD_X, ("u11", "u12", "u13")):
    for _net, _px, _path in DIAG_BUS:
        _pts = [(_qx + _px, _QPAD_END - 0.3)] + [(_qx + dx, _QPAD_END + dy) for dx, dy in _path]
        _t(_net, "F.Cu", 0.2, _pts, "diag_%s_%s" % (_net.lower(), _q))
        _v(_net, _pts[-1][0], _pts[-1][1], "diag_%s_%s" % (_net.lower(), _q), 0.6, 0.3)
# U14's control pins (2-6, 0.65 mm pitch, pads x 124.5-125.8) into the FEED_B_P notch, by hand
# for the same reason: route12 left IN_AUX_L boxed in there after the others took the room.
# Each pin runs west to a via in one of two columns -- x 124.0 (0.2 mm off the pads' ends) and
# 123.25 (0.35 mm off the notch edge, so the FEED_B pour's 0.3 mm clearance just meets the
# outline) -- alternating, so a track from the inner column passes the outer column's vias at
# 0.25 mm.  The router picks each via up on In2, under the pour.
U14_FAN = (("IN_AUX_L", 88.7, 124.0), ("Net-(U14-DEN)", 89.35, 123.25),
           ("Net-(U14-IS)", 90.0, 124.0), ("Net-(U14-DSEL)", 90.65, 123.25),
           ("IN_AUX_R", 91.3, 124.0))
for _net, _y, _vx in U14_FAN:
    _drop(_net, (125.15, _y), (_vx, _y), "u14_fan_%.2f" % _y, w=0.2, size=0.6, drill=0.3)
for _net, _px, _path in DIAG_BUS:
    _vx, _vy = _path[-1]
    _t(_net, "In2.Cu", 0.2, [(QUAD_X[0] + _vx, _QPAD_END + _vy),
                             (QUAD_X[-1] + _vx, _QPAD_END + _vy)], "diag_%s_bus" % _net.lower())

# ---- NT1 star tie (README: a 2.0 mm tie that outlasts the harness fuse).  NT1.1 (GND_B) ->
# 2 mm F.Cu -> four vias in the 1 mm gap between R_IN and the GND planes (in neither pour) ->
# 2 mm B.Cu east into R_B's B.Cu GND_B pour.
_t("GND_B", "F.Cu", 2.0, [(60.5, 88.5), (62.5, 88.5)], "nt1")
_t("GND_B", "F.Cu", 1.0, [(62.5, 86.6), (62.5, 90.2)], "nt1_bar")
_t("GND_B", "B.Cu", 1.0, [(62.5, 86.6), (62.5, 90.2)], "nt1_bbar")
for _i in range(4):
    _v("GND_B", 62.5, 86.6 + 1.2 * _i, "nt1_%d" % _i)
_t("GND_B", "B.Cu", 2.0, [(62.5, 88.5), (68.4, 94.4), (101.0, 94.4)], "nt1_tie")

# ---- FEED B (6.4 A).  FEED_B_P and Q13's source side are pours (ZONES above).  VBAT_B leaves
# the source pour through 12 vias (10.8 mm) to In3 and reaches U14's pad 15 through its 12
# thermal vias (6.7 mm); D24 / R108 are Q13's gate network.
for _i, _x in enumerate((108.4, 109.6, 110.8, 112.0)):
    for _j, _y in enumerate((86.4, 87.6, 88.8)):
        _v("VBAT_B", _x, _y, "q13src_%d_%d" % (_i, _j))
_t("GATE_B", "F.Cu", 0.3, [(114.28, 90.9), (112.6, 91.6), (111.65, 91.6)], "gateb")
_t("GATE_B", "F.Cu", 0.3, [(112.6, 91.6), (113.0, 92.6), (113.0, 93.47)], "gateb_r108")
# Q14 (parallel with Q13): its own 12 source vias to In3's notch, and its gate down the 1.16 mm
# gap between the source pins and the FEED_B_P pour to Q13's gate pin.
for _i, _x in enumerate((108.4, 109.6, 110.8, 112.0)):
    for _j, _y in enumerate((75.3, 76.5, 77.7)):
        _v("VBAT_B", _x, _y, "q14src_%d_%d" % (_i, _j))
_t("GATE_B", "F.Cu", 0.3, [(114.28, 79.405), (115.22, 79.9), (115.22, 90.4), (114.28, 90.9)],
   "gateb_q14")
_drop("GND_B", (113.0, 95.13), (113.0, 96.4), "r108", w=0.6)
_t("VBAT_B", "F.Cu", 1.0, [(128.6, 93.45), (128.3, 91.5)], "c67_vs")
_t("GND_B", "F.Cu", 1.0, [(128.6, 95.35), (128.65, 98.0)], "c67_gnd")
for _x in (134.3, 136.3):
    _drop("VBAT_B", (_x, 88.0), (_x, 86.9), "c68v%d" % int(_x))
for _x in (142.7, 144.7):
    _drop("GND_B", (_x, 89.5), (_x, 91.4), "c68g%d" % int(_x))
_drop("VBAT_B", (148.55, 84.3), (148.55, 83.3), "c66v", w=0.6)
_drop("GND_B", (150.45, 85.7), (150.45, 86.7), "c66g", w=0.6)
_drop("VBAT_B", (151.35, 92.0), (151.35, 93.4), "d25v")
_drop("GND_B", (155.65, 92.0), (155.65, 93.4), "d25g")
# POD outputs (3.2 A, 1.57 mm).  Each channel's three U14 pins are bridged by a 1.74 mm bar the
# height of the pin group (the pins themselves are the narrowest copper: 3 x 0.45 mm).
_t("POD_R_P", "F.Cu", 1.74, [(130.85, 91.3), (132.0, 91.3)], "podr_bar")
_t("POD_R_P", "F.Cu", 2.0, [(132.0, 91.3), (132.0, 100.8)], "podr")
_t("POD_R_P", "F.Cu", 1.0, [(132.0, 96.2), (135.05, 96.2)], "podr_c70")
_t("GND_B", "F.Cu", 1.0, [(136.95, 96.2), (138.5, 100.0)], "c70_gnd")
_v("POD_R_P", 132.0, 94.0, "podr_tp", 0.6, 0.3)
_t("POD_R_P", "In5.Cu", 0.3, [(132.0, 94.0), (146.0, 80.0), (151.2, 74.8), (151.2, 62.6)], "podr_tp")
_drop("POD_R_P", (149.5, 61.0), (151.2, 62.6), "podr_tp11", w=0.3, size=0.6, drill=0.3)
_t("POD_L_P", "F.Cu", 1.74, [(130.85, 88.7), (131.7, 88.7)], "podl_bar")
_t("POD_L_P", "F.Cu", 2.0, [(131.7, 88.3), (131.7, 82.6)], "podl")
for _i, _y in enumerate((85.4, 84.2, 83.0)):
    _v("POD_L_P", 131.7, _y, "podl_%d" % _i)
_t("POD_L_P", "In2.Cu", 2.0, [(131.7, 85.4), (131.7, 82.4), (102.0, 82.4), (102.0, 100.8)], "podl_in2")
_t("POD_L_P", "F.Cu", 1.0, [(102.0, 100.8), (102.0, 97.0), (103.5, 95.5), (105.05, 95.5)], "podl_c69")
_t("GND_B", "F.Cu", 1.0, [(106.95, 95.5), (107.4, 99.6)], "c69_gnd")
_t("POD_L_P", "In2.Cu", 0.3, [(131.7, 83.0), (139.0, 75.7), (139.0, 68.6)], "podl_tp")
_drop("POD_L_P", (139.0, 67.0), (139.0, 68.6), "podl_tp10", w=0.3, size=0.6, drill=0.3)
# Bank-2 test pads: GND_B by F.Cu only (a GND_B via here would pierce the GND planes), VBAT_B
# by a via and In3.
_t("GND_B", "F.Cu", 0.5, [(139.0, 64.0), (141.0, 64.0), (141.0, 83.0), (142.2, 87.9)], "tp3")
_drop("VBAT_B", (139.0, 61.0), (137.4, 61.0), "tp2", w=0.3, size=0.6, drill=0.3)
_t("VBAT_B", "In3.Cu", 0.3, [(137.4, 61.0), (137.4, 82.6)], "tp2_in3")

# ---- CAN.  Inner pair U6 -> L6, then L6's bus pins -> a coupled F.Cu pair (0.8 mm pitch) down
# to R26 (termination) and D6 (ESD) at J8.  Coming from below with CANH on the west lane, the
# pair meets J8 (CANH west) and L6 (CANH on top, reached under the choke body) without
# crossing.  CANH's detour round L6 and to the farther J8 pin is matched by a meander on CANL.
_t("Net-(U6-CANH)", "F.Cu", 0.3, [(92.77, 76.66), (94.6, 76.66), (95.86, 75.4), (96.52, 75.3)], "can_ih")
_t("Net-(U6-CANL)", "F.Cu", 0.3, [(92.77, 77.94), (96.52, 77.8)], "can_il")
_t("CANH", "F.Cu", 0.3, [(93.4, 104.4), (94.75, 101.54), (94.87, 97.4), (97.6, 94.67), (97.6, 80.0),
                         (98.6, 79.0), (98.6, 75.3), (100.6, 75.3)], "canh")
CANL_MEANDER = [(98.4, 89.0), (99.6, 89.0), (99.6, 87.6), (98.4, 87.6), (98.4, 86.2), (99.6, 86.2),
                (99.6, 84.8), (98.4, 84.8)]
_t("CANL", "F.Cu", 0.3, [(98.0, 104.4), (96.65, 101.54), (96.53, 97.4), (98.4, 95.53)]
   + CANL_MEANDER + [(98.4, 80.6), (100.4, 78.6), (101.08, 77.8)], "canl")
_drop("GND", (95.7, 99.66), (95.7, 98.4), "d6_gnd", w=0.4, size=0.6, drill=0.3)
_t("CANH", "F.Cu", 0.3, [(95.5, 67.0), (100.8, 67.0), (100.8, 75.3)], "canh_tp15")
_t("CANL", "F.Cu", 0.3, [(95.5, 64.0), (102.6, 64.0), (102.6, 77.8), (101.08, 77.8)], "canl_tp16")

# ---------------------------------------------------------------- drawing notes
NOTES = [
    # (text, x, y, layer, size)
    ("MCCAN plan4 board, 140 x 100 mm, 8 layers, 1.6 mm, 1 oz all layers.\n"
     "GENERATED by hardware/scripts/gen_pcb.py from layout_pcb.py -- do not edit in pcbnew.\n"
     "Cable edge: bottom.  Antenna edge: top.  Single-sided assembly (F.Cu).",
     X0, Y1 + 6.0, "Cmts.User", 1.5),
]
# J2 pin names and a mis-plug warning on F.SilkS (2026-11-15 robustness review).  J2 is a plain
# 2.54 mm header in the pin order 3V3 GND TX RX DTR RTS; a generic FTDI cable (GND CTS VCC TX RX
# RTS) would put GND on +3V3_ALW and 5 V on TXD0.  J2 is auto-flowed, so these coordinates
# follow its current pads (x 141.87, pin 1 at y 31.37, 2.54 mm pitch); DRC's silk checks catch
# any overlap if it moves.
_J2X, _J2Y = 141.87, 31.37
for _i, _name in enumerate(("3V3", "GND", "TX", "RX", "DTR", "RTS")):
    NOTES.append((_name, _J2X - 5.27, _J2Y + 2.54 * _i, "F.SilkS", 1.0))
NOTES.append(("PROG ONLY\nNOT FTDI", _J2X - 15.37, _J2Y + 5.08, "F.SilkS", 1.0))
