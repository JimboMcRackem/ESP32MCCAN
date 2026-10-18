# Layout for power_input.kicad_sch.  A3 since 2026-09-20.
#
# Two blocks live on this sheet:
#
#   1. THE eFUSE (spec 4.2).  U10 LTC4380-2 driving a back-to-back pair Q10/Q11, with the
#      second FET's gate-steering network Q12/D22/D23/R105-R107.  This replaced F1 (a
#      blade fuse) and Q1 (a P-channel reverse-polarity FET); one part now does both jobs
#      and adds current limiting and a 29.5 V output clamp that neither did.
#   2. THE INPUT FILTER (spec 4.3), unchanged apart from being shifted 73.66 mm right to
#      make room.  D2 TVS -> L2 common-mode choke -> C1 -> L1 -> bulk -> D3 -> VLOGIC_IN.
#
#  y =  64.77 : Q10_G label stub
#  y =  69.85 : R2 (0R link across choke winding A)
#  y =  76.20 : main feed rail  FEED_P .. MID .. SNS .. VBAT_PROT | L2-A | VBAT_F .. VBAT
#  y =  81.28 : L2 winding B    (GND_IN on pin 2, board GND on pin 3)
#  y =  83.82 : bottom pins of C1..C5, D2 anode, C65
#  y =  86.36 : board GND symbols; VCC10 bus; U10_GATE tap
#  y =  87.63 : R3 (0R link across choke winding B)
#  y = 101.60 : downstream GND_IN rail
#  y = 110-157: the eFuse block -- U10, its gate network and its passives
#
# ---------------------------------------------------------------- THE PASS PAIR
# Q10 and Q11 are COMMON DRAIN: pin 3 (D) of both meets at MID, pin 2 (S) of Q10 goes to
# FEED_P and pin 2 (S) of Q11 goes to R100/SNS.  Their body diodes then oppose each other,
# which is the reverse-polarity block and holds with the part unpowered.
#
# Wiring them common SOURCE instead passes ERC, passes DRC, passes the pad count, and
# silently deletes the reverse-polarity protection.  An earlier draft of spec 4.2 said to
# do exactly that.  Do not "simplify" this, and re-read the netlist by hand after any
# change here -- gen_power_input.py prints the expected coordinates for every net.
#
# ---------------------------------------------------------------- REFERENCE DESIGNATORS
# CORRECTED 2026-09-20.  Spec 4.2 named these parts R88-R95 and C49-C52.  Those are ALREADY
# TAKEN: R88-R99 are the twelve RGB output snubber resistors and C49-C61 their partners, all
# on the outputs sheet.  Generating the sheet as specified would have put duplicate
# references in the netlist.  The mapping actually used, and now the canonical one:
#
#   R88->R100 (R_SNS)   R89->R101 (R_DRN)  R90->R102 (10R)    R91->R103 (33R)
#   R92->R104 (VCC 10k) R93->R105 (240k)   R94->R106 (10k)    R95->R107 (240k)
#   C49->C62 (C_TMR)    C50->C63 (VCC)     C51->C64 (47nF)    C52->C65 (22uF, NEW)
#   D22->D21 (22V Zener) D23->D22          D24->D23
#
# U10, Q10, Q11 and Q12 were free and keep their spec names.

# L1 and L2 ARE A COUPLED PAIR -- do not change one without re-checking the other.
# Review finding F4 caps the total series resistance of L1 plus BOTH windings of L2 at
# 22 mOhm, because they carry the entire 7.0 A night load and their loss lands on the
# 150 cm2 heat-spreader plate, which is sized for ~2.9 W total.
#   L1 = Vishay IHLP-4040DZ-01, 1.5 uH   ->  5.80 mOhm max
#   L2 = Wurth WE-CMBNC 7448031002       -> 6.3 mOhm max per winding = 12.6 mOhm
#   total 18.40 mOhm, 0.90 W at 7.0 A, 16.4% inside the ceiling.
# The eFuse pass pair and R100 add to that budget: 2 x 0.8 mOhm plus 5.6 mOhm = 7.2 mOhm,
# 0.35 W at 7.0 A.  Spec 4.2 accounts for it; do not re-spend it here.

SH = 73.66   # the input filter moved right by this much to make room for the eFuse

COMPS = [
    ("J1",  "Connector:Conn_01x02_Pin",   26.67,  76.20,   0, "PWR feed A -> SS1.5 2w", ""),

    # ---- eFuse: the pass pair, the sense resistor and the output bypass
    ("Q10", "Transistor_FET:Q_NMOS_GSD",  76.20,  73.66, 270, "IPT008N06NM5LF", ""),
    ("Q11", "Transistor_FET:Q_NMOS_GSD", 104.14,  78.74,  90, "IPT008N06NM5LF", ""),
    ("R100", "Device:R",                 116.84,  76.20,  90, "5m6 1% 1W", ""),
    # C65: the datasheet's PIN FUNCTIONS entry for OUT requires a minimum of 22 uF bypass
    # "as close to the pin as possible".  Nothing else on this sheet satisfies it -- C1 is
    # 100 nF and sits behind the common-mode choke, C3 sits behind L1 as well.
    ("C65", "Device:C_Polarized",        127.00,  80.01,   0, "22uF 63V", ""),

    # ---- eFuse: the controller
    ("U10", "mccan_parts:LTC4380",       101.60, 130.81,   0, "LTC4380HMS-2", ""),
    ("R101", "Device:R",                  90.17,  83.82,   0, "30k", ""),
    ("R102", "Device:R",                 104.14,  90.17,   0, "10R", ""),
    ("R103", "Device:R",                  82.55,  90.17,   0, "33R", ""),
    ("C64", "Device:C",                   82.55, 100.33,   0, "47nF", ""),
    ("C62", "Device:C",                  101.60, 148.59,   0, "680nF", ""),

    # ---- eFuse: the VCC feed
    ("R104", "Device:R",                  38.10,  82.55,   0, "10k", ""),
    ("C63", "Device:C",                   45.72,  90.17,   0, "220nF", ""),
    ("D21", "Device:D_Zener",             53.34,  90.17, 270, "22V", ""),

    # ---- eFuse: Q10's gate-steering network (datasheet Figure 7 Q3/D3/D2/R6/R5/R4)
    ("Q12", "Transistor_BJT:Q_NPN_BEC",   57.15, 121.92,   0, "MMBT3904", ""),
    ("D22", "Device:D",                   73.66, 116.84,   0, "1N4148", ""),
    ("D23", "Device:D",                   52.07, 137.16, 270, "1N4148", ""),
    ("R105", "Device:R",                  52.07, 118.11,   0, "240k", ""),
    ("R106", "Device:R",                  52.07, 128.27,   0, "10k", ""),
    ("R107", "Device:R",                  85.09, 116.84,  90, "240k", ""),

    # ---- input filter, shifted right by SH
    ("D2", "Device:D_TVS",                66.04 + SH,  80.01, 270, "SMBJ24A", ""),
    ("L2", "mccan_parts:CM_CHOKE_4T",     81.28 + SH,  78.74,   0, "7448031002", ""),
    ("R2", "Device:R",                    81.28 + SH,  69.85,  90, "0R (link)", ""),
    ("R3", "Device:R",                    81.28 + SH,  87.63,  90, "0R (link)", ""),
    ("C1", "Device:C",                    93.98 + SH,  80.01,   0, "100nF", ""),
    ("L1", "Device:L",                   104.14 + SH,  76.20,  90, "1.5uH", ""),
    ("C2", "Device:C",                   115.57 + SH,  80.01,   0, "100nF", ""),
    ("C3", "Device:C_Polarized",         123.19 + SH,  80.01,   0, "220uF 63V", ""),
    ("C4", "Device:C",                   130.81 + SH,  80.01,   0, "1uF", ""),
    ("D3", "Device:D_Schottky",          140.97 + SH,  76.20, 180, "Schottky 40V", ""),
    ("C5", "Device:C",                   151.13 + SH,  80.01,   0, "100nF", ""),

    # ---- feed B (D6): reverse-polarity P-FET + 24 V TVS for the AUX_R pod switch
    ("J9",  "Connector:Conn_01x02_Pin",  147.32, 124.46,   0, "SS1.5 2w feed B", ""),
    ("Q13", "Transistor_FET:Si7141DP",   172.72, 127.00,  90, "SQJ461EP", ""),
    ("R108", "Device:R",                 172.72, 139.70,   0, "100k", ""),
    ("D24", "Device:D_Zener",            185.42, 128.27, 270, "MMSZ5245B", ""),
    ("C66", "Device:C",                  203.20, 128.27,   0, "100nF 100V", ""),
    ("D25", "Device:D_Zener",             210.82, 128.27, 270, "SMBJ24A", ""),
    ("NT1", "Device:NetTie_2",           218.44, 147.32,   0, "NetTie_2", ""),
]
HORIZONTAL = {"L1", "D3", "R2", "R3", "R100", "R107"}

# DO NOT POPULATE.  R2 and R3 are 0R links that SHORT OUT both windings of the
# common-mode choke; they are the alternative build to L2, never a companion to it.
# Spec 4.3 requires the choke, so the choke is the populated option and these two are
# DNP.  Leaving them stuffed silently defeats the entire common-mode filter -- the board
# works perfectly and filters nothing, and no ERC or DRC check will say so.
#
# R103/C64 are NOT on this list.  They were going to be DNP compensation footprints; spec
# 4.2 populates them, and C62 (680 nF) is sized on the assumption that they are fitted.
DNP = {"R2", "R3"}

# board GND only -- GND_IN deliberately has NO power symbol (see the split-ground note)
GNDS = [
    ("#PWR01",  86.36 + SH,  90.17),   # L2 winding B pin 3 / R3 pin 2 -- board side
    ("#PWR02",  93.98 + SH,  86.36),   # C1
    ("#PWR03", 115.57 + SH,  86.36),   # C2
    ("#PWR04", 123.19 + SH,  86.36),   # C3
    ("#PWR05", 130.81 + SH,  86.36),   # C4
    ("#PWR06", 151.13 + SH,  86.36),   # C5
]

# ON is left open on its internal 1 MOhm pull-up, exactly as the datasheet's Figure 7 does;
# FLT is an open-drain fault flag we do not route to the MCU (spec 4.2).  Both need a
# no-connect flag or ERC reports them.
NOCONN = [
    (86.36, 135.89),    # U10 pin 9, ON
    (116.84, 125.73),   # U10 pin 7, FLT
]

WIRES = [
    # ---------------------------------------------------------------- the feed rail
    ((31.75, 76.20), (38.10, 76.20)),        # FEED_P : J1.1 -> R104 tap
    ((38.10, 76.20), (38.10, 78.74)),        #          down to R104.1
    ((38.10, 76.20), (71.12, 76.20)),        #          on to Q10 pin 2 (SOURCE)
    ((81.28, 76.20), (90.17, 76.20)),        # MID : Q10 pin 3 (DRAIN) -> R101 tap
    ((90.17, 76.20), (90.17, 80.01)),        #       down to R101.1
    ((90.17, 76.20), (99.06, 76.20)),        #       on to Q11 pin 3 (DRAIN)
    ((109.22, 76.20), (113.03, 76.20)),      # SNS : Q11 pin 2 (SOURCE) -> R100.1
    ((113.03, 76.20), (113.03, 83.82)),      #       stub down to the SNS label
    ((120.65, 76.20), (127.00, 76.20)),      # VBAT_PROT : R100.2 -> C65
    ((127.00, 76.20), (139.70, 76.20)),      #             on to D2 cathode
    ((139.70, 76.20), (149.86, 76.20)),      #             on to L2 winding A in
    ((127.00, 83.82), (127.00, 88.90)),      # C65 return to GND_IN
    ((76.20, 68.58), (76.20, 64.77)),        # Q10 pin 1 (GATE) up to its label

    # ---------------------------------------------------------------- VCC10
    ((38.10, 86.36), (45.72, 86.36)),        # R104.2 -> C63.1
    ((45.72, 86.36), (53.34, 86.36)),        #        -> D21 cathode
    ((53.34, 86.36), (60.96, 86.36)),        #        -> the VCC10 label
    ((45.72, 93.98), (53.34, 93.98)),        # C63.2 -> D21 anode
    ((53.34, 93.98), (60.96, 93.98)),        #       -> the GND_IN label
    ((31.75, 78.74), (31.75, 88.90)),        # J1.2 down to its GND_IN label

    # ---------------------------------------------------------------- U10 sense taps
    ((90.17, 87.63), (90.17, 91.44)),        # R101.2 down to the U10_DRN label
    ((76.20, 86.36), (82.55, 86.36)),        # R103.1 across to the U10_GATE label
    ((82.55, 93.98), (82.55, 96.52)),        # R103.2 -> C64.1
    ((82.55, 104.14), (82.55, 106.68)),      # C64.2 -> GND_IN
    ((104.14, 83.82), (104.14, 86.36)),      # Q11 pin 1 (GATE) -> R102.1
    ((104.14, 93.98), (104.14, 97.79)),      # R102.2 -> the U10_GATE label

    # ---------------------------------------------------------------- U10 itself
    ((93.98, 118.11), (93.98, 114.30)),      # pin 1  DRN
    ((99.06, 118.11), (99.06, 114.30)),      # pin 3  GATE
    ((104.14, 118.11), (104.14, 114.30)),    # pin 4  SNS
    ((109.22, 118.11), (109.22, 114.30)),    # pin 5  OUT
    ((86.36, 125.73), (80.01, 125.73)),      # pin 2  VCC
    ((93.98, 143.51), (93.98, 147.32)),      # pin 8  GND
    ((93.98, 147.32), (87.63, 147.32)),
    ((101.60, 143.51), (101.60, 144.78)),    # pin 10 TMR -> C62
    ((101.60, 152.40), (101.60, 156.21)),    # C62 -> GND_IN
    ((109.22, 143.51), (109.22, 147.32)),    # pin 6  SEL -> GND_IN
    ((109.22, 147.32), (115.57, 147.32)),

    # ---------------------------------------------------------------- Q10's gate network
    ((59.69, 127.00), (66.04, 127.00)),      # Q12 pin 2 (EMITTER) -> FEED_P
    ((59.69, 116.84), (63.50, 116.84)),      # Q12 pin 3 (COLLECTOR) -> the Q10_G tee
    ((63.50, 116.84), (69.85, 116.84)),      #      -> D22 cathode
    ((63.50, 116.84), (63.50, 113.03)),      #      -> the Q10_G label
    ((77.47, 116.84), (81.28, 116.84)),      # D22 anode -> R107.1
    ((88.90, 116.84), (88.90, 111.76)),      # R107.2 -> the U10_GATE label
    ((52.07, 114.30), (52.07, 110.49)),      # R105.1 -> FEED_P
    ((52.07, 124.46), (52.07, 121.92)),      # R106.1 -> Q12 pin 1 (BASE)
    ((52.07, 132.08), (52.07, 133.35)),      # R106.2 -> D23 cathode
    ((52.07, 140.97), (52.07, 144.78)),      # D23 anode -> GND_IN

    # ---------------------------------------------------------------- input filter
    ((139.70, 83.82), (139.70, 101.60)),     # D2 anode down to the GND_IN rail
    ((133.35, 101.60), (139.70, 101.60)),    # the rail, out to its label
    ((139.70, 101.60), (149.86, 101.60)),
    ((149.86, 87.63), (149.86, 101.60)),
    ((149.86, 76.20), (149.86, 69.85)),      # VBAT_PROT up to the R2 link
    ((149.86, 69.85), (151.13, 69.85)),
    ((158.75, 69.85), (160.02, 69.85)),      # R2 link back down to VBAT_F
    ((160.02, 69.85), (160.02, 76.20)),
    ((149.86, 81.28), (149.86, 87.63)),      # L2 winding B pin 2 -> GND_IN side
    ((149.86, 87.63), (151.13, 87.63)),      #      across to the R3 link
    ((158.75, 87.63), (160.02, 87.63)),      # R3 link -> board GND side
    ((160.02, 87.63), (160.02, 81.28)),      #      up to L2 winding B pin 3
    ((160.02, 87.63), (160.02, 90.17)),      #      down to the GND symbol
    ((160.02, 76.20), (167.64, 76.20)),      # VBAT_F : L2 winding A out -> C1
    ((167.64, 76.20), (173.99, 76.20)),      #      -> L1.1
    ((167.64, 83.82), (167.64, 86.36)),      # C1 return
    ((181.61, 76.20), (189.23, 76.20)),      # VBAT : L1.2 -> C2
    ((189.23, 76.20), (196.85, 76.20)),      #      -> C3
    ((196.85, 76.20), (204.47, 76.20)),      #      -> C4
    ((204.47, 76.20), (209.55, 76.20)),      #      -> the VBAT tee
    ((209.55, 76.20), (210.82, 76.20)),      #      -> D3 anode
    ((209.55, 76.20), (209.55, 68.58)),      #      -> the VBAT hierarchical label
    ((189.23, 83.82), (189.23, 86.36)),      # C2 return
    ((196.85, 83.82), (196.85, 86.36)),      # C3 return
    ((204.47, 83.82), (204.47, 86.36)),      # C4 return
    ((218.44, 76.20), (224.79, 76.20)),      # VLOGIC_IN : D3 cathode -> C5
    ((224.79, 76.20), (231.14, 76.20)),      #      -> the hierarchical label
    ((224.79, 83.82), (224.79, 86.36)),      # C5 return

    # ---------------------------------------------------------------- feed B (D6)
    # FEED_B_P : J9.1 -> Q13 pin 5 (DRAIN).  Q13 is rotated 90 so D is left, S is right, G is down.
    ((152.40, 124.46), (154.94, 124.46)),
    ((154.94, 124.46), (167.64, 124.46)),
    # VBAT_B : Q13 pin 1-3 (SOURCE) -> D24 cathode -> C66 -> D25 cathode -> the hierarchical label
    ((177.80, 124.46), (185.42, 124.46)),
    ((185.42, 124.46), (203.20, 124.46)),
    ((203.20, 124.46), (210.82, 124.46)),
    ((210.82, 124.46), (223.52, 124.46)),
    # GATE_B : Q13 pin 4 (GATE) -> D24 anode, and down to R108
    ((172.72, 132.08), (175.26, 132.08)),
    ((175.26, 132.08), (185.42, 132.08)),
    ((172.72, 132.08), (172.72, 135.89)),
    # GND_B : J9.2, R108.2, C66.2, D25.2 and NT1 pin 1 on one rail
    ((152.40, 127.00), (152.40, 147.32)),
    ((152.40, 147.32), (160.02, 147.32)),
    ((160.02, 147.32), (172.72, 147.32)),
    ((172.72, 143.51), (172.72, 147.32)),
    ((172.72, 147.32), (203.20, 147.32)),
    ((203.20, 132.08), (203.20, 147.32)),
    ((203.20, 147.32), (210.82, 147.32)),
    ((210.82, 132.08), (210.82, 147.32)),
    ((210.82, 147.32), (215.90, 147.32)),
    # NT1 pin 2 -> GND_IN (connector side of L2), through a local label like the other GND_IN members
    ((220.98, 147.32), (226.06, 147.32)),
]

JUNCTIONS = [
    (38.10, 76.20), (90.17, 76.20), (113.03, 76.20), (127.00, 76.20),
    (139.70, 76.20), (149.86, 76.20), (160.02, 76.20), (167.64, 76.20),
    (189.23, 76.20), (196.85, 76.20), (204.47, 76.20), (209.55, 76.20),
    (224.79, 76.20),
    (45.72, 86.36), (53.34, 86.36), (53.34, 93.98),
    (149.86, 87.63), (160.02, 87.63), (139.70, 101.60),
    (52.07, 121.92), (63.50, 116.84),
    # feed B
    (172.72, 132.08), (185.42, 124.46), (203.20, 124.46), (210.82, 124.46),
    (172.72, 147.32), (203.20, 147.32), (210.82, 147.32),
]

LABELS = [
    # the feed rail
    ("FEED_P",    34.29,  76.20, 0),
    ("MID",       85.09,  76.20, 0),
    ("VBAT_PROT", 132.08, 76.20, 0),
    ("VBAT_F",    162.56, 76.20, 0),
    ("SNS",       113.03, 83.82, 0),
    ("Q10_G",     76.20,  64.77, 90),
    # VCC10 and the connector-side return in the eFuse block
    ("VCC10",     60.96,  86.36, 0),
    ("VCC10",     80.01, 125.73, 0),
    ("GND_IN",    31.75,  88.90, 0),
    ("GND_IN",    60.96,  93.98, 0),
    ("GND_IN",    127.00, 88.90, 0),
    ("GND_IN",    82.55, 106.68, 0),
    ("GND_IN",    52.07, 144.78, 0),
    ("GND_IN",    87.63, 147.32, 0),
    ("GND_IN",    115.57, 147.32, 0),
    ("GND_IN",    101.60, 156.21, 0),
    ("GND_IN",    133.35, 101.60, 0),
    # U10's own nets
    ("U10_DRN",   90.17,  91.44, 0),
    ("U10_DRN",   93.98, 114.30, 90),
    ("U10_GATE",  76.20,  86.36, 0),
    ("U10_GATE",  104.14, 97.79, 0),
    ("U10_GATE",  99.06, 114.30, 90),
    ("U10_GATE",  88.90, 111.76, 90),
    ("SNS",       104.14, 114.30, 90),
    ("VBAT_PROT", 109.22, 114.30, 90),
    # the gate-steering network
    ("FEED_P",    66.04, 127.00, 0),
    ("FEED_P",    52.07, 110.49, 90),
    ("Q10_G",     63.50, 113.03, 90),
    # feed B
    ("FEED_B_P",  154.94, 124.46, 0),
    ("GATE_B",    175.26, 132.08, 0),
    ("GND_B",     160.02, 147.32, 0),
    ("GND_IN",    226.06, 147.32, 0),     # NT1 pin 2
]

HLABELS = [
    ("VBAT",      209.55, 68.58, 90, "output"),
    ("VLOGIC_IN", 231.14, 76.20,  0, "output"),
    ("VBAT_B",    223.52, 124.46, 0, "output"),   # feed B, no consumer until Task 8 wires the root
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
    "J1":   ((21.59, 68.58), (21.59, 71.12)),
    # feed B
    "J9":   ((137.16, 119.38), (137.16, 121.92)),
    "Q13":  ((175.26, 116.84), (175.26, 119.38)),   # rot 90 -> grows left
    "R108": ((173.99, 138.43), (173.99, 140.97)),
    "D24":  ((187.96, 127.00), (187.96, 129.54)),
    "C66":  ((204.47, 118.11), (204.47, 120.65)),
    "D25":  ((213.36, 127.00), (213.36, 129.54)),
    "NT1":  ((215.90, 142.24), (215.90, 144.78)),
    # eFuse block
    "Q10":  ((60.96, 67.31), (60.96, 69.85)),     # grows right, into empty space above
    "Q11":  ((97.79, 86.36), (97.79, 88.90)),     # rot 90 -> grows left
    "R100": ((114.30, 67.31), (114.30, 69.85)),   # rot 90 -> grows left
    "C65":  ((128.27, 78.74), (128.27, 81.28)),
    "U10":  ((118.11, 133.35), (118.11, 135.89)),
    "R101": ((91.44, 82.55), (91.44, 85.09)),
    "R102": ((105.41, 88.90), (105.41, 91.44)),
    "R103": ((83.82, 88.90), (83.82, 91.44)),
    "C64":  ((83.82, 99.06), (83.82, 101.60)),
    "C62":  ((102.87, 147.32), (102.87, 149.86)),
    "R104": ((39.37, 81.28), (39.37, 83.82)),
    "C63":  ((46.99, 88.90), (46.99, 91.44)),
    "D21":  ((55.88, 88.90), (55.88, 91.44)),
    "Q12":  ((62.23, 130.81), (62.23, 133.35)),
    "D22":  ((71.12, 120.65), (71.12, 123.19)),
    "D23":  ((53.34, 135.89), (53.34, 138.43)),
    "R105": ((44.45, 116.84), (44.45, 119.38)),
    "R106": ((44.45, 127.00), (44.45, 129.54)),
    "R107": ((80.01, 132.08), (80.01, 134.62)),   # rot 90 -> grows left
    # input filter, all shifted by SH
    "D2":   ((67.31 + SH, 85.09), (67.31 + SH, 87.63)),
    "L2":   ((88.90 + SH, 67.31), (88.90 + SH, 69.85)),
    "R2":   ((74.93 + SH, 65.41), (74.93 + SH, 67.95)),
    "R3":   ((92.71 + SH, 92.71), (92.71 + SH, 95.25)),
    # caps: references in a row above the feed rail, values in a row below the grounds,
    # because a 7.62 mm pitch leaves no room for a value string between two bodies
    "C1":   ((95.25 + SH, 72.39), (95.25 + SH, 90.17)),
    "L1":   ((107.95 + SH, 71.12), (107.95 + SH, 82.55)),
    "C2":   ((116.84 + SH, 72.39), (116.84 + SH, 90.17)),
    "C3":   ((124.46 + SH, 72.39), (124.46 + SH, 90.17)),
    "C4":   ((132.08 + SH, 72.39), (132.08 + SH, 90.17)),
    "D3":   ((147.32 + SH, 71.12), (147.32 + SH, 82.55)),
    "C5":   ((152.40 + SH, 72.39), (152.40 + SH, 90.17)),
}


def field_anchors(ref, x, y, rot):
    ra, va = _ANCHORS[ref]
    return ra, va, grows_right(rot)
