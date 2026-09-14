#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/sheets/mcu_can.kicad_sch (KiCad 10.0.2, format 20260306).

Task 5: ESP32-WROOM-32E-N8, TJA1042T/3 with hardware-enforced listen-only,
programming header with auto-reset, status LED, ignition-sense divider.
"""
import os, re, uuid

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def U(key):
    return str(uuid.uuid5(NS, "mcu_can:" + key))

# ---------------------------------------------------------------- sheet identity
ROOT = open(os.path.join(HW, "mccan.kicad_sch"), encoding="utf-8").read()
m = re.search(r'\(uuid "([0-9a-f-]+)"\)(?:(?!\(sheet).)*?'
              r'\(property "Sheetfile" "sheets/mcu_can\.kicad_sch"', ROOT, re.S)
assert m, "could not find the mcu_can sheet instance in the root schematic"
SHEET_INSTANCE_UUID = m.group(1)
ROOT_UUID = re.search(r'\(uuid "([0-9a-f-]+)"\)', ROOT).group(1)
INST_PATH = "/%s/%s" % (ROOT_UUID, SHEET_INSTANCE_UUID)
SHEET_UUID = str(uuid.uuid5(NS, "mcu_can-sheet"))

# ---------------------------------------------------------------- lib_symbols
def extract_block(text, header):
    i = text.index(header)
    i = text.index("(", i)
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while text[j] != '"' or text[j - 1] == "\\":
                j += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1

def reindent(blk, first, extra):
    lines = blk.split("\n")
    return "\n".join([("\t" * first) + lines[0]] +
                     [("\t" * extra) + ln if ln else ln for ln in lines[1:]])

def from_schematic(libid):
    src = open(os.path.join(HW, "sheets", "power_input.kicad_sch"), encoding="utf-8").read()
    return reindent(extract_block(src, '\t\t(symbol "%s"\n' % libid), 2, 0)

def from_library(path, name, libid):
    """Resolve `extends` the way KiCad does when it caches a symbol into a sheet:
    inherit the parent's graphics and pins, keep the child's own properties."""
    src = open(path, encoding="utf-8").read()
    blk = extract_block(src, '\t(symbol "%s"\n' % name)
    ext = re.search(r'\(extends "([^"]+)"\)', blk)
    if ext:
        parent = extract_block(src, '\t(symbol "%s"\n' % ext.group(1))
        # child's Value property wins; everything else comes from the parent
        val = re.search(r'\(property "Value" "([^"]*)"', blk)
        parent = re.sub(r'(\(property "Value" ")[^"]*(")',
                        lambda mm: mm.group(1) + (val.group(1) if val else name) + mm.group(2),
                        parent, count=1)
        # carry over the child's own Footprint / Datasheet / Description if present
        for prop in ("Footprint", "Datasheet", "Description", "ki_keywords", "ki_description"):
            cm = re.search(r'\(property "%s" "([^"]*)"' % prop, blk)
            if cm:
                parent = re.sub(r'(\(property "%s" ")[^"]*(")' % prop,
                                lambda mm: mm.group(1) + cm.group(1) + mm.group(2),
                                parent, count=1)
        blk = parent
        blk = re.sub(r'\(symbol "[^"]+"\n', '(symbol "%s"\n' % libid, blk, count=1)
        # sub-symbol names must match the outer name or KiCad drops the graphics
        short = libid.split(":")[-1]
        blk = re.sub(r'\(symbol "%s_(\d+_\d+)"' % re.escape(ext.group(1)),
                     lambda mm: '(symbol "%s_%s"' % (short, mm.group(1)), blk)
    else:
        blk = blk.replace('(symbol "%s"\n' % name, '(symbol "%s"\n' % libid, 1)
        short = libid.split(":")[-1]
        blk = re.sub(r'\(symbol "%s_(\d+_\d+)"' % re.escape(name),
                     lambda mm: '(symbol "%s_%s"' % (short, mm.group(1)), blk)
    return reindent(blk, 2, 1)

LIBS = []
for lid in ("Device:C", "Device:D_Schottky", "Device:D_TVS", "Device:L_Coupled",
            "Device:R", "power:GND"):
    LIBS.append(from_schematic(lid))
LIBS.append(from_library(os.path.join(STOCK, "Device.kicad_sym"), "LED", "Device:LED"))
LIBS.append(from_library(os.path.join(STOCK, "RF_Module.kicad_sym"),
                         "ESP32-WROOM-32E", "RF_Module:ESP32-WROOM-32E"))
LIBS.append(from_library(os.path.join(STOCK, "Interface_CAN_LIN.kicad_sym"),
                         "TJA1042T-3", "Interface_CAN_LIN:TJA1042T-3"))
LIBS.append(from_library(os.path.join(STOCK, "Transistor_BJT.kicad_sym"),
                         "Q_NPN_BEC", "Transistor_BJT:Q_NPN_BEC"))
LIBS.append(from_library(os.path.join(STOCK, "Switch.kicad_sym"), "SW_Push", "Switch:SW_Push"))
LIBS.append(from_library(os.path.join(STOCK, "Connector_Generic.kicad_sym"),
                         "Conn_01x06", "Connector_Generic:Conn_01x06"))
LIBS.sort(key=lambda b: re.search(r'\(symbol "([^"]+)"', b).group(1))

# ---------------------------------------------------------------- geometry
def pin(x, y, rot, px, py):
    if rot == 0:    return (round(x + px, 4), round(y - py, 4))
    if rot == 90:   return (round(x - py, 4), round(y - px, 4))
    if rot == 180:  return (round(x - px, 4), round(y + py, 4))
    if rot == 270:  return (round(x + py, 4), round(y + px, 4))
    raise ValueError(rot)

ESP32 = {"[1,15,38,39]": (0, -35.56), "2": (0, 35.56), "3": (-15.24, 30.48),
         "4": (-15.24, 25.4), "5": (-15.24, 22.86), "6": (15.24, -25.4),
         "7": (15.24, -27.94), "8": (15.24, -20.32), "9": (15.24, -22.86),
         "10": (15.24, -12.7), "11": (15.24, -15.24), "12": (15.24, -17.78),
         "13": (15.24, 10.16), "14": (15.24, 15.24), "16": (15.24, 12.7),
         "17": (-12.7, -5.08), "18": (-12.7, -7.62), "19": (-12.7, -12.7),
         "20": (-12.7, -10.16), "21": (-12.7, 0), "22": (-12.7, -2.54),
         "23": (15.24, 7.62), "24": (15.24, 25.4), "25": (15.24, 30.48),
         "26": (15.24, 20.32), "27": (15.24, 5.08), "28": (15.24, 2.54),
         "29": (15.24, 17.78), "30": (15.24, 0), "31": (15.24, -2.54),
         "32": (-12.7, -27.94), "33": (15.24, -5.08), "34": (15.24, 22.86),
         "35": (15.24, 27.94), "36": (15.24, -7.62), "37": (15.24, -10.16)}
TJA = {"1": (-12.7, 5.08), "2": (0, -10.16), "3": (0, 10.16), "4": (-12.7, 2.54),
       "5": (-12.7, -2.54), "6": (12.7, -2.54), "7": (12.7, 2.54), "8": (-12.7, -5.08)}
COUPLED = {"1": (-5.08, 2.54), "2": (5.08, 2.54), "3": (-5.08, -2.54), "4": (5.08, -2.54)}
TWOPIN = {"1": (0, 3.81), "2": (0, -3.81)}
DIODE = {"1": (-3.81, 0), "2": (3.81, 0)}          # 1 = K/A1, 2 = A/A2
NPN = {"1": (-5.08, 0), "2": (2.54, -5.08), "3": (2.54, 5.08)}
SWP = {"1": (-5.08, 0), "2": (5.08, 0)}
CONN6 = {"1": (-5.08, 5.08), "2": (-5.08, 2.54), "3": (-5.08, 0),
         "4": (-5.08, -2.54), "5": (-5.08, -5.08), "6": (-5.08, -7.62)}

SYMS, WIRES, JUNCS, LABELS, HLABELS, NOTES, NOCONN = [], [], [], [], [], [], []
PINMAP = {}
GNDN = [0]

GRID = 1.27

def ongrid(*vals):
    for v in vals:
        assert abs(v / GRID - round(v / GRID)) < 1e-6, "%s is off the 1.27 mm grid" % v
    return vals

def place(ref, libid, val, x, y, rot=0, pins=None, fields=None, desc="", dnp=False):
    ongrid(x, y)
    SYMS.append(dict(ref=ref, libid=libid, val=val, x=x, y=y, rot=rot,
                     fields=fields or [], pinnums=list(pins.keys()) if pins else ["1"],
                     desc=desc, dnp=dnp))
    if pins:
        PINMAP[ref] = {n: pin(x, y, rot, *p) for n, p in pins.items()}
    return PINMAP.get(ref)

def vpart(ref, libid, val, x, ytop, dnp=False):
    """Vertical 2-pin part: pin1 at ytop, pin2 at ytop + 7.62."""
    ongrid(x, ytop)
    cy = round(ytop + 3.81, 4)
    fields = [("Reference", ref, x + 1.651, cy - 1.27, 0),
              ("Value", val, x + 1.651, cy + 1.27, 0)]
    place(ref, libid, val, x, cy, 0, TWOPIN, fields, dnp=dnp)
    return (x, ytop), (x, round(ytop + 7.62, 4))

def hpart(ref, libid, val, xleft, y, dnp=False):
    """Horizontal 2-pin part: pin1 at xleft, pin2 at xleft + 7.62."""
    ongrid(xleft, y)
    cx = round(xleft + 3.81, 4)
    fields = [("Reference", ref, cx, y - 2.921, 0),
              ("Value", val, cx, y + 2.921, 0)]
    place(ref, libid, val, cx, y, 90, TWOPIN, fields, dnp=dnp)
    return (xleft, y), (round(xleft + 7.62, 4), y)

def gnd(x, y):
    ongrid(x, y)
    GNDN[0] += 1
    ref = "#PWR2%02d" % GNDN[0]
    fields = [("Reference", ref, x, y + 6.35, 0, True),
              ("Value", "GND", x, y + 3.81, 0, True)]
    SYMS.append(dict(ref=ref, libid="power:GND", val="GND", x=x, y=y, rot=0,
                     fields=fields, pinnums=["1"],
                     desc='Power symbol creates a global label with name "GND" , ground',
                     power=True, dnp=False))
    return (x, y)

def w(a, b):
    assert a != b, a
    ongrid(*a); ongrid(*b)
    WIRES.append((a, b))

def j(p):
    ongrid(*p)
    JUNCS.append(p)

def nc(p):
    ongrid(*p)
    NOCONN.append(p)

def lab(name, x, y, rot=0):
    ongrid(x, y)
    LABELS.append((name, x, y, rot))

def hlab(name, shape, x, y, rot=0):
    ongrid(x, y)
    HLABELS.append((name, shape, x, y, rot))

# ================================================================ BLOCK A: ESP32
U5 = place("U5", "RF_Module:ESP32-WROOM-32E", "ESP32-WROOM-32E-N8", 149.86, 120.65, 0, ESP32,
           [("Reference", "U5", 149.86, 81.28, 0),
            ("Value", "ESP32-WROOM-32E-N8", 149.86, 158.75, 0)],
           desc="RF Module, ESP32-D0WD-V3 SoC, 8 MB SPI flash, Wi-Fi 802.11b/g/n, BT 4.2, PCB antenna, SMD")
VDD_Y, EN_Y = 76.2, U5["3"][1]

# --- VDD rail
w(U5["2"], (U5["2"][0], VDD_Y)); w((U5["2"][0], VDD_Y), (104.14, VDD_Y))
hlab("+3V3_ALW", "input", 104.14, VDD_Y, 180)
a, b = vpart("C35", "Device:C", "10uF", 109.22, VDD_Y); gnd(*b); j(a)
a, b = vpart("C36", "Device:C", "100nF", 116.84, VDD_Y); gnd(*b); j(a)
gnd(*U5["[1,15,38,39]"])

# --- EN reset network.  R22 holds EN high; C37 gives a clean power-on reset and
#     de-glitches the auto-reset transistor.
w(U5["3"], (124.46, EN_Y))
a, b = vpart("R22", "Device:R", "10k", 124.46, VDD_Y); j(a)
w(b, (124.46, EN_Y)); j((124.46, EN_Y))
a, b = vpart("C37", "Device:C", "1uF", 114.3, EN_Y); gnd(*b)
w((124.46, EN_Y), a)
lab("EN_MCU", 128.27, EN_Y)

# --- IGN_SENSE in on GPIO 36; GPIO 39 left spare
w(U5["4"], (127.0, U5["4"][1])); lab("IGN_SENSE", 127.0, U5["4"][1])
nc(U5["5"])

# --- right-hand fan-out.  Every net name is from the plan's Global Constraints
#     table; nothing is invented.  (pin, net, hier shape or None for a local label)
FANOUT = [
    ("25", "BOOT_N",     None),
    ("35", "UART_TX",    None),
    ("24", None,         None),      # GPIO 2  spare
    ("34", "UART_RX",    None),
    ("26", "MUX_S1",     "output"),
    ("29", "MUX_S3",     "output"),
    ("14", "IO12_STRAP", None),
    ("16", "LED_STAT",   None),
    ("13", "CAN_STB",    None),
    ("23", None,         None),      # GPIO 15 spare
    ("27", "MUX_S2",     "output"),
    ("28", "CAN_TXD",    None),
    ("30", "PWM_DEN_A",  "output"),
    ("31", "PWM_DEN_B",  "output"),
    ("33", "I2C_SDA",    "bidirectional"),
    ("36", "I2C_SCL",    "bidirectional"),
    ("37", "MUX_S0",     "output"),
    ("10", "EN_BOOST",   "output"),
    ("11", "EN_3V3SW",   "output"),
    ("12", "EN_DIAG",    "output"),
    ("8",  "RGB_ISNS",   "input"),
    ("9",  "DEN_DSEL",   "output"),
    ("6",  "ISNS_DEN",   "input"),
    ("7",  "CAN_RXD",    None),
]
for pnum, net, shape in FANOUT:
    p = U5[pnum]
    if net is None:
        nc(p)
        continue
    end = (round(p[0] + 7.62, 4), p[1])
    w(p, end)
    if shape:
        hlab(net, shape, end[0], end[1], 0)
    else:
        lab(net, end[0], end[1])

# ================================================================ BLOCK B: CAN
U6 = place("U6", "Interface_CAN_LIN:TJA1042T-3", "TJA1042T/3", 261.62, 95.25, 0, TJA,
           [("Reference", "U6", 261.62, 82.55, 0), ("Value", "TJA1042T/3", 261.62, 107.95, 0)],
           desc="High-speed CAN transceiver with standby mode and separate VIO supply, SO-8")
TXD_Y, RXD_Y, VIO_Y, STB_Y = U6["1"][1], U6["4"][1], U6["5"][1], U6["8"][1]
CANH_Y, CANL_Y = U6["7"][1], U6["6"][1]

# --- VCC from the SWITCHED 5 V rail: the transmit side powers down in sleep.
#     Routed right so the area above TXD stays free for the pull-up.
w(U6["3"], (U6["3"][0], 77.47)); w((U6["3"][0], 77.47), (292.1, 77.47))
hlab("+5V", "input", 292.1, 77.47, 0)
a, b = vpart("C38", "Device:C", "100nF", 283.21, 77.47); gnd(*b); j(a)
gnd(*U6["2"])

# --- VIO from the ALWAYS-ON 3.3 V rail: this is what keeps the receiver alive so
#     bus activity can wake the board (spec 8.3).
w(U6["5"], (231.14, VIO_Y)); w((231.14, VIO_Y), (231.14, 67.31))
hlab("+3V3_ALW", "input", 231.14, 67.31, 90)
a, b = vpart("C39", "Device:C", "100nF", 240.03, VIO_Y); gnd(*b); j(a)

# --- STB with its mandatory pull-up: floating = standby = receive only.
w(U6["8"], (U6["8"][0], 111.76)); w((U6["8"][0], 111.76), (236.22, 111.76))
a, b = vpart("R25", "Device:R", "10k", 236.22, 104.14)
w(a, (236.22, VIO_Y)); j((236.22, VIO_Y))
lab("CAN_STB", 241.3, 111.76)

# --- TXD path: DNP 0 ohm link + pull-up to VIO.  See the listen-only note.
a, b = hpart("R23", "Device:R", "0R", 236.22, TXD_Y, dnp=True)
w(b, U6["1"])
w(a, (224.79, TXD_Y)); lab("CAN_TXD", 224.79, TXD_Y, 180)
j((246.38, TXD_Y)); w((246.38, TXD_Y), (246.38, 82.55))
c, d = vpart("R24", "Device:R", "10k", 246.38, 74.93)   # pin2 lands on the wire above
w(c, (246.38, 69.85)); lab("+3V3_ALW", 246.38, 69.85, 90)

# --- RXD
w(U6["4"], (224.79, RXD_Y)); lab("CAN_RXD", 224.79, RXD_Y, 180)

# --- common-mode choke, then ESD clamps, then out to the connector on `outputs`
L6 = place("L6", "Device:L_Coupled", "51uH CM choke", 284.48, 95.25, 0, COUPLED,
           [("Reference", "L6", 284.48, 88.9, 0), ("Value", "51uH CM choke", 284.48, 101.6, 0)],
           desc="Coupled inductor, common-mode choke")
w(U6["7"], L6["1"])
w(U6["6"], L6["3"])
w(L6["2"], (299.72, CANH_Y)); hlab("CANH", "bidirectional", 299.72, CANH_Y, 0)
w(L6["4"], (299.72, CANL_Y)); hlab("CANL", "bidirectional", 299.72, CANL_Y, 0)

# D6 clamps CANH upward and D7 clamps CANL downward, so neither part sits across
# the other line.
place("D6", "Device:D_TVS", "24V bidir", 294.64, 88.9, 90, DIODE,
      [("Reference", "D6", 297.18, 87.63, 0), ("Value", "24V bidir", 297.18, 90.17, 0)],
      desc="Bidirectional transient-voltage-suppression diode")
j((294.64, CANH_Y)); w((294.64, 85.09), (294.64, 80.01)); gnd(294.64, 80.01)
place("D7", "Device:D_TVS", "24V bidir", 294.64, 101.6, 270, DIODE,
      [("Reference", "D7", 297.18, 100.33, 0), ("Value", "24V bidir", 297.18, 102.87, 0)],
      desc="Bidirectional transient-voltage-suppression diode")
j((294.64, CANL_Y)); w((294.64, 105.41), (294.64, 111.76)); gnd(294.64, 111.76)

# --- 120 ohm terminator, DNP: the vehicle bus is already terminated at both ends.
w((284.48, 109.22), (284.48, 114.3)); lab("CANH", 284.48, 109.22, 90)
a, b = vpart("R26", "Device:R", "120R", 284.48, 114.3, dnp=True)
w(b, (284.48, 127.0)); lab("CANL", 284.48, 127.0, 90)

# ================================================================ BLOCK C: programming
J2 = place("J2", "Connector_Generic:Conn_01x06", "Prog/UART", 60.96, 175.26, 0, CONN6,
           [("Reference", "J2", 60.96, 163.83, 0), ("Value", "Prog/UART", 60.96, 187.96, 0)],
           desc="Generic connector, single row, 01x06")
w(J2["1"], (36.83, J2["1"][1])); lab("+3V3_ALW", 36.83, J2["1"][1])
w(J2["2"], (30.48, J2["2"][1])); gnd(30.48, J2["2"][1])
w(J2["3"], (36.83, J2["3"][1])); lab("UART_TX", 36.83, J2["3"][1])
w(J2["4"], (36.83, J2["4"][1])); lab("UART_RX", 36.83, J2["4"][1])
w(J2["5"], (39.37, J2["5"][1])); lab("DTR", 39.37, J2["5"][1])
w(J2["6"], (43.18, J2["6"][1])); lab("RTS", 43.18, J2["6"][1])

# --- the standard cross-coupled auto-reset pair.  Each transistor's emitter sits on
#     the OTHER control line, so the pair only acts when DTR and RTS differ.
Q2 = place("Q2", "Transistor_BJT:Q_NPN_BEC", "MMBT3904", 85.09, 170.18, 0, NPN,
           [("Reference", "Q2", 90.17, 168.91, 0), ("Value", "MMBT3904", 90.17, 171.45, 0)],
           desc="0.2A Ic, 40V Vce, Small Signal NPN Transistor, SOT-23")
a, b = hpart("R28", "Device:R", "10k", 68.58, Q2["1"][1])
w(b, Q2["1"]); w(a, (62.23, Q2["1"][1])); lab("RTS", 62.23, Q2["1"][1])
w(Q2["2"], (93.98, Q2["2"][1])); lab("DTR", 93.98, Q2["2"][1])
w(Q2["3"], (Q2["3"][0], 158.75)); lab("EN_MCU", Q2["3"][0], 158.75, 90)

Q3 = place("Q3", "Transistor_BJT:Q_NPN_BEC", "MMBT3904", 85.09, 189.23, 0, NPN,
           [("Reference", "Q3", 90.17, 187.96, 0), ("Value", "MMBT3904", 90.17, 190.5, 0)],
           desc="0.2A Ic, 40V Vce, Small Signal NPN Transistor, SOT-23")
a, b = hpart("R29", "Device:R", "10k", 68.58, Q3["1"][1])
w(b, Q3["1"]); w(a, (62.23, Q3["1"][1])); lab("DTR", 62.23, Q3["1"][1])
w(Q3["2"], (93.98, Q3["2"][1])); lab("RTS", 93.98, Q3["2"][1])
w(Q3["3"], (97.79, Q3["3"][1])); lab("BOOT_N", 97.79, Q3["3"][1])

SW1 = place("SW1", "Switch:SW_Push", "BOOT", 110.49, 204.47, 0, SWP,
            [("Reference", "SW1", 110.49, 198.12, 0), ("Value", "BOOT", 110.49, 210.82, 0)],
            desc="Push button switch, generic, two pins")
w(SW1["1"], (100.33, 204.47)); lab("BOOT_N", 100.33, 204.47)
w(SW1["2"], (120.65, 204.47)); gnd(120.65, 204.47)

SW2 = place("SW2", "Switch:SW_Push", "EN/RESET", 110.49, 158.75, 0, SWP,
            [("Reference", "SW2", 110.49, 152.4, 0), ("Value", "EN/RESET", 110.49, 165.1, 0)],
            desc="Push button switch, generic, two pins")
w(SW2["1"], (100.33, 158.75)); lab("EN_MCU", 100.33, 158.75)
w(SW2["2"], (120.65, 158.75)); gnd(120.65, 158.75)

# ================================================================ BLOCK D: status LED
D5 = place("D5", "Device:LED", "green", 209.55, 160.02, 0, DIODE,
           [("Reference", "D5", 209.55, 154.94, 0), ("Value", "green", 209.55, 164.46, 0)],
           desc="Light emitting diode")
a, b = hpart("R27", "Device:R", "1k", 217.17, 160.02)
w(D5["2"], a)
w(b, (231.14, 160.02)); lab("LED_STAT", 231.14, 160.02)
w(D5["1"], (199.39, 160.02)); gnd(199.39, 160.02)

# ================================================================ BLOCK E: ignition sense
# Fallback wake path if the Experia CAN bus never idles (spec 8.3).  The divider is
# DNP; the pulldown is NOT.  GPIO 36 has no internal pull and EXT1 ANY_HIGH is armed
# on it, so a floating pin wakes the board on noise (review finding C2).
IGN_Y = 111.76
hlab("IGN_IN", "input", 39.37, 104.14, 180)
w((39.37, 104.14), (60.96, 104.14))
a, b = vpart("R37", "Device:R", "90.9k", 60.96, 104.14, dnp=True)
c, d = vpart("R38", "Device:R", "33k", 60.96, IGN_Y, dnp=True); gnd(*d)
j((60.96, IGN_Y)); lab("IGN_SENSE", 62.23, IGN_Y)
w((60.96, IGN_Y), (72.39, IGN_Y))
e, f = vpart("R39", "Device:R", "100k", 72.39, IGN_Y); gnd(*f)
j((72.39, IGN_Y))
# C40 forms an RC with R37: Rthev = 90.9k || 24.8k = 19.5k, so tau ~ 2 ms.  IGN_IN is
# an unshielded 12 V wire entering a sealed box onto a high-impedance node; ignition
# state changes over seconds, so the filter costs nothing in wake latency.
a2, b2 = vpart("C40", "Device:C", "100nF", 78.74, IGN_Y); gnd(*b2)
j((78.74, IGN_Y))
w((72.39, IGN_Y), (78.74, IGN_Y))
w((78.74, IGN_Y), (83.82, IGN_Y))
place("D8", "Device:D_Schottky", "BAT54", 83.82, 107.95, 270, DIODE,
      [("Reference", "D8", 86.36, 106.68, 0), ("Value", "BAT54", 86.36, 109.22, 0)],
      desc="Schottky diode")
w((83.82, 104.14), (83.82, 99.06)); lab("+3V3_ALW", 83.82, 99.06, 90)

# ================================================================ BLOCK F: passive defaults
# Every net the plan's biasing table requires to have a defined floating state, in one
# place so an omission is visible rather than buried in the fan-out.  These cost nothing
# in sleep: the GPIO is driven low, so there is no potential across them.
DEFAULTS = [
    ("R30", "MUX_S0",     "10k"),
    ("R31", "MUX_S1",     "10k"),
    ("R32", "MUX_S2",     "10k"),
    ("R33", "MUX_S3",     "10k"),   # GPIO 5 is a strapping pin - boot requirement
    ("R34", "DEN_DSEL",   "10k"),
    ("R35", "EN_DIAG",    "10k"),
    ("R36", "IO12_STRAP", "10k"),   # GPIO 12 selects flash voltage at boot
]
for i, (ref, net, val) in enumerate(DEFAULTS):
    x = round(40.64 + i * 15.24, 4)
    w((x, 215.9), (x, 220.98)); lab(net, x, 215.9, 90)
    a, b = vpart(ref, "Device:R", val, x, 220.98); gnd(*b)

# ================================================================ NOTES
NOTEW = 135
import textwrap
def note(*parts):
    out = []
    for para in parts:
        if para.startswith("|"):
            out.extend(para[1:].split("\n"))
        else:
            out.extend(textwrap.wrap(para, NOTEW) or [""])
    NOTES.append("\n".join(out))

note("""|ACCEPTANCE (spec 7, 8.1)
- ESP32-WROOM-32E-N8 (8 MB).  NOT the 4 MB variant, NOT the -32UE (U.FL) variant.
- Module powered from +3V3_ALW so it stays up in sleep.
- Pin assignment EXACTLY per the plan's Global Constraints table.
- CAN_RXD on GPIO 35 (RTC-capable, EXT0 wake); IGN_SENSE on GPIO 36 (EXT1 ANY_HIGH).
- ISNS_DEN on GPIO 34 (ADC1 ONLY); DEN_DSEL on GPIO 33 - the PROFET has ONE
  multiplexed IS output, not two.  GPIO 39 is spare.
- CAN_STB on GPIO 14, PULLED UP to VIO (floating = standby).
- TJA1042T/3 TXD through an UNPOPULATED 0 ohm link, TXD pulled to VIO.
- NO 120 ohm terminator populated; unpopulated footprint present.
- CAN common-mode choke + ESD protection on CANH/CANL.
- Programming header with DTR/RTS auto-reset pair, BOOT and EN buttons.
- IGN_SENSE divider footprint present but UNPOPULATED.""")

note("""|HARDWARE-ENFORCED LISTEN-ONLY
R23 (0 ohm) is DNP.  With it unpopulated the transceiver TXD is held recessive by R24
and the board is PHYSICALLY INCAPABLE of transmitting on the vehicle bus.  Populate R23
only for deliberate bench TX.""",
"""This is not a firmware setting that can be got wrong, and not a fuse that can be blown by
accident.  The link is the only conductive path from GPIO 17 to the transceiver, so a
board built to the BOM cannot assert a dominant bit on a moving motorcycle's bus no matter
what the firmware does.""")

note("""|TWO SUPPLIES, ON PURPOSE - DO NOT TIE THEM TOGETHER
VIO (pin 5) -> +3V3_ALW, always on.  VCC (pin 3) -> +5V, gated off in sleep.""",
"""The split is what makes CAN wake work.  In sleep the +5V rail is down, so the transmit
side and the bus drivers are unpowered, but VIO keeps the receiver and the RXD output
alive.  Bus traffic therefore still pulls RXD low, which is the EXT0 wake event on
GPIO 35.  Powering both from one rail loses either the wake path or the sleep budget.""",
"""TJA1042T/3 VCC is 4.5-5.5 V.  The "/3" suffix refers to VIO only.  Running VCC from 3.3 V
is out of spec - this was a genuine error in an early draft of the spec.""")

note("""|ANTENNA KEEP-OUT - carries into layout (Task 8)
No copper, no plating, no components and no ground pour may sit under the module's antenna
area, on ANY layer.  Overhang the module past the board edge, or cut the board back to it.
The finned/metal wall of the enclosure must not be the antenna wall either.""")

note("""|WHY THE AUTO-RESET PAIR IS CROSS-COUPLED
Each transistor's emitter sits on the OTHER control line, so the pair only acts when DTR
and RTS differ.  Both high or both low = run mode.  That is what stops a plain serial
monitor - which asserts one line on open - from dropping the board into the bootloader.""",
"""esptool drives DTR=0/RTS=1 to assert reset, then DTR=1/RTS=0 to hold IO0 low while EN
releases.  Q2 pulls EN low in the first state; Q3 pulls IO0 low in the second.""")

note("""|PASSIVE DEFAULTS (block F) - MANDATORY, NOT OPTIONAL
Every resistor in block F is required by the plan's biasing table.  Two are boot
requirements rather than merely safe defaults:""",
"""R33 on MUX_S3: GPIO 5 is a STRAPPING pin.  It is sampled at reset and must be defined.""",
"""R36 on IO12_STRAP: GPIO 12 (MTDI) selects the flash voltage at boot.  Sampled high it
selects 1.8 V, which will not run the module's 3.3 V flash.  Most WROOM-32E parts ship
with the eFuse already burned so the strap is ignored, but that is not guaranteed across
date codes and it is not worth a 10k resistor to find out.  ADDED 2026-09-14 - this one
is not in the plan; drop it if you would rather follow the plan exactly.""",
"""These draw ZERO current in sleep: the GPIO is driven low, so there is no potential
across them.""")

note("""|IGNITION SENSE (block E) - divider DNP, pulldown POPULATED
R37 and R38 are DNP.  R39 is NOT.  GPIO 36 has no internal pull-up or pull-down and EXT1
ANY_HIGH wake is armed on it, so a floating pin wakes the board on noise and flattens the
battery.  R39 defines it low whether or not the divider is fitted.""",
"""If the divider is ever populated: 90.9k over (33k || 100k = 24.8k) gives 2.57 V at
12.0 V in and 2.96 V at 13.8 V, both above the 2.48 V input-high threshold, with D8
clamping anything above the rail.  Current draw is 104 uA, but only while the ignition
line is live, so it does not touch the parked budget.""")

note("""|NET NAMED IGN_IN IS AN ADDITION TO THE CONTRACT
The plan says the divider is fed from "a VBAT-side input" but names no net.  IGN_IN is the
ignition-switched 12 V sense wire from the harness; it must land on a connector pin on the
outputs sheet.  Rename or remove it if the contract should stay closed.""")

note("""|EN_BOOST AND EN_3V3SW PULLDOWNS ARE ON THE RAILS SHEET, NOT HERE
The plan's Task 5 Step 4 asks for them here.  They are already fitted as R19 and R20 next
to the converters they gate, which is where they do the most good - the enable stays
defined even if the inter-sheet net is open.  One resistor per net; do not add a second.""")

# ================================================================ emit
def fs(x):
    s = ("%.4f" % x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"

out = []
A = out.append
A("(kicad_sch")
A("\t(version 20260306)")
A('\t(generator "eeschema")')
A('\t(generator_version "10.0")')
A('\t(uuid "%s")' % SHEET_UUID)
A('\t(paper "A3")')
A("\t(title_block")
A('\t\t(title "mcu_can")')
A("\t)")
A("\t(lib_symbols")
for b in LIBS:
    A(b)
A("\t)")

for i, txt in enumerate(NOTES):
    for ln in txt.split("\n"):
        assert len(ln) <= NOTEW, (len(ln), ln)
    NOTES[i] = (txt, round(len(txt.split("\n")) * 1.48 + 2.0, 2))

ny = 13.0
for txt, h in NOTES:
    esc = txt.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    A('\t(text_box "%s"' % esc)
    A("\t\t(exclude_from_sim no)")
    A("\t\t(at 310.0 %s 0)" % fs(ny))
    A("\t\t(size 103.19 %s)" % fs(h))
    A("\t\t(margins 0.9525 0.9525 0.9525 0.9525)")
    A("\t\t(stroke")
    A("\t\t\t(width 0)")
    A("\t\t\t(type default)")
    A("\t\t)")
    A("\t\t(fill")
    A("\t\t\t(type none)")
    A("\t\t)")
    A("\t\t(effects")
    A("\t\t\t(font")
    A("\t\t\t\t(size 0.8 0.8)")
    A("\t\t\t)")
    A("\t\t\t(justify left top)")
    A("\t\t)")
    A('\t\t(uuid "%s")' % U("note%.2f" % ny))
    A("\t)")
    ny = round(ny + h + 1.5, 2)
assert ny < 280.0, "notes overflow: %s" % ny

for p in sorted(set(NOCONN)):
    A("\t(no_connect")
    A("\t\t(at %s %s)" % (fs(p[0]), fs(p[1])))
    A('\t\t(uuid "%s")' % U("nc%s,%s" % p))
    A("\t)")

for p in sorted(set(JUNCS)):
    A("\t(junction")
    A("\t\t(at %s %s)" % (fs(p[0]), fs(p[1])))
    A("\t\t(diameter 0)")
    A("\t\t(color 0 0 0 0)")
    A('\t\t(uuid "%s")' % U("j%s,%s" % p))
    A("\t)")

for a, b in WIRES:
    A("\t(wire")
    A("\t\t(pts")
    A("\t\t\t(xy %s %s) (xy %s %s)" % (fs(a[0]), fs(a[1]), fs(b[0]), fs(b[1])))
    A("\t\t)")
    A("\t\t(stroke")
    A("\t\t\t(width 0)")
    A("\t\t\t(type default)")
    A("\t\t)")
    A('\t\t(uuid "%s")' % U("w%s,%s-%s,%s" % (a[0], a[1], b[0], b[1])))
    A("\t)")

for name, x, y, rot in LABELS:
    A('\t(label "%s"' % name)
    A("\t\t(at %s %s %d)" % (fs(x), fs(y), rot))
    A("\t\t(effects")
    A("\t\t\t(font")
    A("\t\t\t\t(size 1.27 1.27)")
    A("\t\t\t)")
    A("\t\t\t(justify left bottom)")
    A("\t\t)")
    A('\t\t(uuid "%s")' % U("l%s%s%s" % (name, x, y)))
    A("\t)")

for name, shape, x, y, rot in HLABELS:
    A('\t(hierarchical_label "%s"' % name)
    A("\t\t(shape %s)" % shape)
    A("\t\t(at %s %s %d)" % (fs(x), fs(y), rot))
    A("\t\t(effects")
    A("\t\t\t(font")
    A("\t\t\t\t(size 1.27 1.27)")
    A("\t\t\t)")
    A("\t\t\t(justify %s)" % ("right" if rot == 180 else "left"))
    A("\t\t)")
    A('\t\t(uuid "%s")' % U("h%s%s%s" % (name, x, y)))
    A("\t)")

for s in SYMS:
    A("\t(symbol")
    A('\t\t(lib_id "%s")' % s["libid"])
    A("\t\t(at %s %s %d)" % (fs(s["x"]), fs(s["y"]), s["rot"]))
    A("\t\t(unit 1)")
    A("\t\t(body_style 1)")
    A("\t\t(exclude_from_sim no)")
    A("\t\t(in_bom yes)")
    A("\t\t(on_board yes)")
    A("\t\t(in_pos_files yes)")
    A("\t\t(dnp %s)" % ("yes" if s["dnp"] else "no"))
    A('\t\t(uuid "%s")' % U("s" + s["ref"]))
    props = list(s["fields"])
    have = {p[0] for p in props}
    if "Reference" not in have:
        props.insert(0, ("Reference", s["ref"], s["x"], s["y"] - 2.54, 0))
    if "Value" not in have:
        props.insert(1, ("Value", s["val"], s["x"], s["y"] + 2.54, 0))
    for extra in ("Footprint", "Datasheet", "Description"):
        props.append((extra, "" if extra != "Description" else s["desc"],
                      s["x"], s["y"], 0, True))
    for p in props:
        nm, val, px, py, pa = p[:5]
        hide = len(p) > 5 and p[5]
        if nm in ("Footprint", "Datasheet", "Description"):
            hide = True
        A('\t\t(property "%s" "%s"' % (nm, val.replace("\\", "\\\\").replace('"', '\\"')))
        A("\t\t\t(at %s %s %d)" % (fs(px), fs(py), pa))
        if hide:
            A("\t\t\t(hide yes)")
        A("\t\t\t(show_name no)")
        A("\t\t\t(do_not_autoplace no)")
        A("\t\t\t(effects")
        A("\t\t\t\t(font")
        A("\t\t\t\t\t(size 1.27 1.27)")
        A("\t\t\t\t)")
        if nm in ("Reference", "Value"):
            A("\t\t\t\t(justify left)")
        A("\t\t\t)")
        A("\t\t)")
    for n in s["pinnums"]:
        A('\t\t(pin "%s"' % n)
        A('\t\t\t(uuid "%s")' % U("p%s.%s" % (s["ref"], n)))
        A("\t\t)")
    A("\t\t(instances")
    A('\t\t\t(project "mccan"')
    A('\t\t\t\t(path "%s"' % INST_PATH)
    A('\t\t\t\t\t(reference "%s")' % s["ref"])
    A("\t\t\t\t\t(unit 1)")
    A("\t\t\t\t)")
    A("\t\t\t)")
    A("\t\t)")
    A("\t)")

A(")")
open(os.path.join(HW, "sheets", "mcu_can.kicad_sch"), "w",
     encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
print("symbols:", len(SYMS), " wires:", len(WIRES), " junctions:", len(set(JUNCS)),
      " no-connects:", len(set(NOCONN)), " labels:", len(LABELS),
      " hlabels:", len(HLABELS), " notes end y:", ny)
