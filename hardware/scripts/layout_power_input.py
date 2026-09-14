# Layout block for power_input.kicad_sch -- spliced into gen.py at __LAYOUT_BLOCK__
#
#  y = 69.85 : R2 (0R link across choke winding A)
#  y = 76.20 : main feed rail  FEED_P .. FEED_FUSED .. VBAT_PROT | L2-A | VBAT_F .. VBAT .. VLOGIC_IN
#  y = 81.28 : L2 winding B    (GND_IN on pin 3, board GND on pin 4)
#  y = 83.82 : bottom pins of C1..C5, D2 anode
#  y = 86.36 : board GND symbols
#  y = 87.63 : R3 (0R link across choke winding B)
#  y = 88.90 : Q1_G rail
#  y = 101.60: GND_IN rail   (connector-side return -- LOCAL label, never a power symbol)

COMPS = [
    ("J1", "Connector:Conn_01x03_Pin",  26.67, 76.20,   0, "PWR (SS1.5 3-way)", ""),
    ("F1", "Device:Fuse",               40.64, 76.20,  90, "10A", ""),
    ("Q1", "Transistor_FET:Q_PMOS_GSD", 54.61, 78.74,  90, "SQJ415EP", ""),
    ("D1", "Device:D_Zener",            62.23, 85.09, 270, "12V", ""),
    ("R1", "Device:R",                  54.61, 92.71,   0, "1M", ""),
    ("D2", "Device:D_TVS",              66.04, 80.01, 270, "SMBJ24A", ""),
    ("L2", "Device:L_Coupled",          81.28, 78.74,   0, "CM choke", ""),
    ("R2", "Device:R",                  81.28, 69.85,  90, "0R (link)", ""),
    ("R3", "Device:R",                  81.28, 87.63,  90, "0R (link)", ""),
    ("C1", "Device:C",                  93.98, 80.01,   0, "100nF", ""),
    ("L1", "Device:L",                 104.14, 76.20,  90, "10uH", ""),
    ("C2", "Device:C",                 115.57, 80.01,   0, "100nF", ""),
    ("C3", "Device:C_Polarized",       123.19, 80.01,   0, "220uF", ""),
    ("C4", "Device:C",                 130.81, 80.01,   0, "1uF", ""),
    ("D3", "Device:D_Schottky",        140.97, 76.20, 180, "Schottky 40V", ""),
    ("C5", "Device:C",                 151.13, 80.01,   0, "100nF", ""),
]
HORIZONTAL = {"F1", "L1", "D3", "R2", "R3"}

# board GND only -- GND_IN deliberately has NO power symbol (see the split-ground note)
GNDS = [
    ("#PWR01",  86.36,  90.17),   # L2 winding B pin 4 / R3 pin 2 -- board side of the choke
    ("#PWR02",  93.98,  86.36),   # C1
    ("#PWR03", 115.57,  86.36),   # C2
    ("#PWR04", 123.19,  86.36),   # C3
    ("#PWR05", 130.81,  86.36),   # C4
    ("#PWR06", 151.13,  86.36),   # C5
]

WIRES = [
    ((31.75, 73.66), (31.75, 66.04)),   # J1.1 IGN_IN out to the label
    # FEED_P : J1.1 -> F1.1
    ((31.75, 76.20), (36.83, 76.20)),
    # FEED_FUSED : F1.2 -> Q1.3 (DRAIN)
    ((44.45, 76.20), (49.53, 76.20)),
    # VBAT_PROT : Q1.2 (SOURCE) -> D1 tap -> D2.1 -> L2.1 (winding A in)
    ((59.69, 76.20), (62.23, 76.20)),
    ((62.23, 76.20), (66.04, 76.20)),
    ((66.04, 76.20), (76.20, 76.20)),
    ((62.23, 76.20), (62.23, 81.28)),          # down to D1 cathode
    ((76.20, 76.20), (76.20, 69.85)),          # up to R2 link
    ((76.20, 69.85), (77.47, 69.85)),
    # VBAT_F : L2.2 (winding A out) -> R2 link -> C1.1 -> L1.1
    ((85.09, 69.85), (86.36, 69.85)),
    ((86.36, 69.85), (86.36, 76.20)),
    ((86.36, 76.20), (93.98, 76.20)),
    ((93.98, 76.20), (100.33, 76.20)),
    # Q1_G : Q1.1 (GATE) -> R1.1 -> D1.2 (anode)
    ((54.61, 83.82), (54.61, 88.90)),
    ((54.61, 88.90), (62.23, 88.90)),
    # VBAT : L1.2 -> C2 -> C3 -> C4 -> label stub -> D3.2 (anode)
    ((107.95, 76.20), (115.57, 76.20)),
    ((115.57, 76.20), (123.19, 76.20)),
    ((123.19, 76.20), (130.81, 76.20)),
    ((130.81, 76.20), (135.89, 76.20)),
    ((135.89, 76.20), (137.16, 76.20)),
    ((135.89, 76.20), (135.89, 68.58)),
    # VLOGIC_IN : D3.1 (cathode) -> C5.1 -> label
    ((144.78, 76.20), (151.13, 76.20)),
    ((151.13, 76.20), (157.48, 76.20)),
    # GND_IN : J1.2 + D2.2 + R1.2 + L2.3 + R3.1, all on the connector-side return
    ((31.75, 78.74), (31.75, 101.60)),         # J1 pin 2 down
    ((54.61, 96.52), (54.61, 101.60)),         # R1 pin 2 down
    ((66.04, 83.82), (66.04, 101.60)),         # D2 anode down
    ((76.20, 81.28), (76.20, 87.63)),          # L2 winding B pin 3 down
    ((76.20, 87.63), (77.47, 87.63)),          # across to R3 pin 1
    ((76.20, 87.63), (76.20, 101.60)),         # on down to the GND_IN rail
    ((31.75, 101.60), (54.61, 101.60)),
    ((54.61, 101.60), (66.04, 101.60)),
    ((66.04, 101.60), (76.20, 101.60)),
    # board GND, downstream side of the choke only
    ((85.09, 87.63), (86.36, 87.63)),          # R3 pin 2 across
    ((86.36, 87.63), (86.36, 81.28)),          # up to L2 winding B pin 4
    ((86.36, 87.63), (86.36, 90.17)),          # down to the GND symbol
    ((93.98, 83.82), (93.98, 86.36)),          # C1
    ((115.57, 83.82), (115.57, 86.36)),        # C2
    ((123.19, 83.82), (123.19, 86.36)),        # C3
    ((130.81, 83.82), (130.81, 86.36)),        # C4
    ((151.13, 83.82), (151.13, 86.36)),        # C5
]

JUNCTIONS = [
    (62.23, 76.20), (66.04, 76.20), (76.20, 76.20), (86.36, 76.20), (93.98, 76.20),
    (115.57, 76.20), (123.19, 76.20), (130.81, 76.20), (135.89, 76.20), (151.13, 76.20),
    (54.61, 88.90), (76.20, 87.63), (86.36, 87.63),
    (54.61, 101.60), (66.04, 101.60),
]

LABELS = [
    ("FEED_P",     34.29,  76.20, 0),
    ("FEED_FUSED", 46.99,  76.20, 0),
    ("VBAT_PROT",  68.58,  76.20, 0),
    ("VBAT_F",     88.90,  76.20, 0),
    ("Q1_G",       57.15,  88.90, 0),
    ("GND_IN",     40.64, 101.60, 0),
]

HLABELS = [
    ("IGN_IN",    31.75, 66.04, 90, "output"),   # J1 cavity 1, topology B (spec 8.1a)
    ("VBAT",      135.89, 68.58, 90, "output"),
    ("VLOGIC_IN", 157.48, 76.20,  0, "output"),
]


# ---------------------------------------------------------------- field placement
# KiCad adds the SYMBOL's rotation to a field's own stored angle, then flips the
# justification rather than drawing text upside down.  Measured on this sheet:
#   symbol   0 + field  0 -> horizontal, grows RIGHT
#   symbol  90 + field 90 -> horizontal, grows LEFT
#   symbol 180 + field  0 -> horizontal, grows LEFT
#   symbol 270 + field 90 -> horizontal, grows RIGHT
# So a field angle of 90 is required on symbols rotated 90 or 270, or the text
# renders vertically and runs across the wiring.
def field_angle(rot):
    return 90 if rot in (90, 270) else 0


def grows_right(rot):
    return rot in (0, 270)


# explicit anchors, chosen so no field text crosses a wire, a symbol or another field
_ANCHORS = {
    "J1": ((21.59, 68.58), (21.59, 71.12)),
    "F1": ((44.45, 71.12), (44.45, 82.55)),
    "Q1": ((44.45, 86.36), (44.45, 88.90)),
    "D1": ((59.69, 91.44), (59.69, 94.00)),
    "R1": ((46.99, 91.44), (46.99, 94.61)),
    "D2": ((67.31, 85.09), (67.31, 87.63)),
    "L2": ((88.90, 67.31), (88.90, 69.85)),
    "R2": ((74.93, 65.41), (74.93, 67.95)),
    "R3": ((92.71, 92.71), (92.71, 95.25)),
    # caps: references in a row above the feed rail, values in a row below the grounds,
    # because a 7.62 mm pitch leaves no room for a value string between two bodies
    "C1": ((95.25, 72.39), (95.25, 90.17)),
    "L1": ((107.95, 71.12), (107.95, 82.55)),
    "C2": ((116.84, 72.39), (116.84, 90.17)),
    "C3": ((124.46, 72.39), (124.46, 90.17)),
    "C4": ((132.08, 72.39), (132.08, 90.17)),
    "D3": ((147.32, 71.12), (147.32, 82.55)),
    "C5": ((152.40, 72.39), (152.40, 90.17)),
}


def field_anchors(ref, x, y, rot):
    ra, va = _ANCHORS[ref]
    return ra, va, grows_right(rot)
