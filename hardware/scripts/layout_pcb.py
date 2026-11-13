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
PLACE = {}            # ref -> (x, y, rot), hand placements
REGIONS = {}          # name -> (x0, y0, x1, y1), auto-flow regions
SHEET_REGION = {}     # sheet name -> region
BLOCK = {}            # ref -> region, overriding its sheet's
KEEPCLEAR = {}        # ref -> halo (mm) kept free around a hand placement
NUDGE = {}            # ref -> (dx, dy) applied after the auto-flow
OFFBOARD_OK = set()   # refs whose courtyard may cross the outline (none yet)

# ---------------------------------------------------------------- copper (Tasks 5-7)
ZONES = []            # filled in Task 5
ROUTES = []           # hand routes, Task 6
ROUTE_VIAS = []       # hand vias, Task 6

# ---------------------------------------------------------------- drawing notes
NOTES = [
    # (text, x, y, layer, size)
    ("MCCAN plan4 board, 140 x 100 mm, 8 layers, 1.6 mm, 1 oz all layers.\n"
     "GENERATED by hardware/scripts/gen_pcb.py from layout_pcb.py -- do not edit in pcbnew.\n"
     "Cable edge: bottom.  Antenna edge: top.  Single-sided assembly (F.Cu).",
     X0, Y1 + 6.0, "Cmts.User", 1.5),
]
