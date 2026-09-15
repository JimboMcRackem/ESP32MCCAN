#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/sheets/outputs.kicad_sch (KiCad 10.0.2, format 20260306).

Task 6: PCA9685, 12 RGB switching channels with sense shunts, the 16:1 analog mux
and its sense-path protection, the dual PROFET, four PTCs and the panel connectors.
"""
import os, re, sys, uuid, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def U(key):
    return str(uuid.uuid5(NS, "outputs:" + key))

# ---------------------------------------------------------------- sheet identity
ROOT = open(os.path.join(HW, "mccan.kicad_sch"), encoding="utf-8").read()
ROOT_UUID = re.search(r'\(uuid "([0-9a-f-]+)"\)', ROOT).group(1)
m = re.search(r'\(uuid "([0-9a-f-]+)"\)(?:(?!\(sheet).)*?'
              r'\(property "Sheetfile" "sheets/outputs\.kicad_sch"', ROOT, re.S)
assert m, "could not find the outputs sheet instance in the root schematic"
INST_PATH = "/%s/%s" % (ROOT_UUID, m.group(1))
SHEET_UUID = str(uuid.uuid5(NS, "outputs-sheet"))

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

def from_schematic(sheet, libid):
    src = open(os.path.join(HW, "sheets", sheet), encoding="utf-8").read()
    return reindent(extract_block(src, '\t\t(symbol "%s"\n' % libid), 2, 0)

def from_library(path, name, libid):
    src = open(path, encoding="utf-8").read()
    blk = extract_block(src, '\t(symbol "%s"\n' % name)
    ext = re.search(r'\(extends "([^"]+)"\)', blk)
    if ext:
        parent = extract_block(src, '\t(symbol "%s"\n' % ext.group(1))
        val = re.search(r'\(property "Value" "([^"]*)"', blk)
        parent = re.sub(r'(\(property "Value" ")[^"]*(")',
                        lambda mm: mm.group(1) + (val.group(1) if val else name) + mm.group(2),
                        parent, count=1)
        blk = parent
        blk = re.sub(r'\(symbol "[^"]+"\n', '(symbol "%s"\n' % libid, blk, count=1)
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
for lid in ("Device:C", "Device:D_Schottky", "Device:R", "power:GND"):
    LIBS.append(from_schematic("power_input.kicad_sch", lid))
LIBS.append(from_library(os.path.join(STOCK, "Device.kicad_sym"), "Polyfuse", "Device:Polyfuse"))
LIBS.append(from_library(os.path.join(STOCK, "Driver_LED.kicad_sym"), "PCA9685PW",
                         "Driver_LED:PCA9685PW"))
LIBS.append(from_library(os.path.join(STOCK, "Connector.kicad_sym"), "Conn_01x02_Pin",
                         "Connector:Conn_01x02_Pin"))
LIBS.append(from_library(os.path.join(STOCK, "Connector.kicad_sym"), "Conn_01x03_Pin",
                         "Connector:Conn_01x03_Pin"))
LIBS.append(from_library(os.path.join(STOCK, "Connector.kicad_sym"), "Conn_01x04_Pin",
                         "Connector:Conn_01x04_Pin"))
for nm in ("ADG706", "NX5020UNBKS", "BTS7008_2EPA"):
    LIBS.append(from_library(os.path.join(HW, "symbols", "mccan_parts.kicad_sym"),
                             nm, "mccan_parts:" + nm))
LIBS.sort(key=lambda b: re.search(r'\(symbol "([^"]+)"', b).group(1))

# ---------------------------------------------------------------- geometry
def pin(x, y, rot, px, py):
    if rot == 0:    return (round(x + px, 4), round(y - py, 4))
    if rot == 90:   return (round(x - py, 4), round(y - px, 4))
    if rot == 180:  return (round(x - px, 4), round(y + py, 4))
    if rot == 270:  return (round(x + py, 4), round(y + px, 4))
    raise ValueError(rot)

TWOPIN = {"1": (0, 3.81), "2": (0, -3.81)}          # R, C, Polyfuse
DIODE  = {"1": (-3.81, 0), "2": (3.81, 0)}          # 1 = K, 2 = A
NFET   = {"1": (-5.08, 0), "2": (2.54, -5.08), "3": (2.54, 5.08)}   # G, S, D (unit map below)
PCA = {"1": (-17.78, -5.08), "2": (-17.78, -7.62), "3": (-17.78, -10.16),
       "4": (-17.78, -12.7), "5": (-17.78, -15.24), "6": (17.78, 17.78),
       "7": (17.78, 15.24), "8": (17.78, 12.7), "9": (17.78, 10.16),
       "10": (17.78, 7.62), "11": (17.78, 5.08), "12": (17.78, 2.54),
       "13": (17.78, 0), "14": (0, -27.94), "15": (17.78, -2.54),
       "16": (17.78, -5.08), "17": (17.78, -7.62), "18": (17.78, -10.16),
       "19": (17.78, -12.7), "20": (17.78, -15.24), "21": (17.78, -17.78),
       "22": (17.78, -20.32), "23": (-17.78, 10.16), "24": (-17.78, -17.78),
       "25": (-17.78, 12.7), "26": (-17.78, 17.78), "27": (-17.78, 15.24),
       "28": (0, 25.4)}
ADG = {}
_SN = {1: "19", 2: "20", 3: "21", 4: "22", 5: "23", 6: "24", 7: "25", 8: "26",
       9: "11", 10: "10", 11: "9", 12: "8", 13: "7", 14: "6", 15: "5", 16: "4"}
for _i in range(1, 17):
    ADG[_SN[_i]] = (-15.24, 17.78 - (_i - 1) * 2.54)
ADG.update({"28": (15.24, 17.78), "18": (15.24, 7.62), "17": (15.24, 2.54),
            "16": (15.24, 0), "15": (15.24, -2.54), "14": (15.24, -5.08),
            "2": (15.24, -12.7), "3": (15.24, -15.24), "13": (15.24, -17.78),
            "1": (0, 25.4), "12": (-5.08, -27.94), "27": (5.08, -27.94)})
BTS = {"1": (-12.7, 7.62), "2": (-12.7, 5.08), "3": (-12.7, 0), "4": (-12.7, -2.54),
       "5": (12.7, 7.62), "6": (12.7, 5.08), "7": (12.7, -5.08),
       "8": (0, 17.78), "9": (0, -17.78)}
CONN = {2: {"1": (5.08, 0), "2": (5.08, -2.54)},
        3: {"1": (5.08, 2.54), "2": (5.08, 0), "3": (5.08, -2.54)},
        4: {"1": (5.08, 2.54), "2": (5.08, 0), "3": (5.08, -2.54), "4": (5.08, -5.08)}}

SYMS, WIRES, JUNCS, LABELS, HLABELS, NOTES, NOCONN = [], [], [], [], [], [], []
PINMAP, GNDN = {}, [0]
GRID = 1.27

def ongrid(*vals):
    for v in vals:
        assert abs(v / GRID - round(v / GRID)) < 1e-6, "%s is off the 1.27 mm grid" % v
    return vals

def place(ref, libid, val, x, y, rot=0, pins=None, fields=None, desc="",
          dnp=False, unit=1, key=None):
    ongrid(x, y)
    SYMS.append(dict(ref=ref, libid=libid, val=val, x=x, y=y, rot=rot,
                     fields=fields or [], pinnums=list(pins.keys()) if pins else ["1"],
                     desc=desc, dnp=dnp, unit=unit, key=key or ref))
    if pins:
        PINMAP[key or ref] = {n: pin(x, y, rot, *p) for n, p in pins.items()}
    return PINMAP.get(key or ref)

def vpart(ref, libid, val, x, ytop, dnp=False):
    ongrid(x, ytop)
    cy = round(ytop + 3.81, 4)
    fields = [("Reference", ref, x + 1.651, cy - 1.27, 0),
              ("Value", val, x + 1.651, cy + 1.27, 0)]
    place(ref, libid, val, x, cy, 0, TWOPIN, fields, dnp=dnp)
    return (x, ytop), (x, round(ytop + 7.62, 4))

def hpart(ref, libid, val, xleft, y, dnp=False):
    ongrid(xleft, y)
    cx = round(xleft + 3.81, 4)
    fields = [("Reference", ref, cx, y - 2.921, 0),
              ("Value", val, cx, y + 2.921, 0)]
    place(ref, libid, val, cx, y, 90, TWOPIN, fields, dnp=dnp)
    return (xleft, y), (round(xleft + 7.62, 4), y)

def gnd(x, y):
    ongrid(x, y)
    GNDN[0] += 1
    ref = "#PWR3%02d" % GNDN[0]
    fields = [("Reference", ref, x, y + 6.35, 0, True),
              ("Value", "GND", x, y + 3.81, 0, True)]
    SYMS.append(dict(ref=ref, libid="power:GND", val="GND", x=x, y=y, rot=0,
                     fields=fields, pinnums=["1"], unit=1, key=ref,
                     desc='Power symbol creates a global label with name "GND" , ground',
                     power=True, dnp=False))
    return (x, y)

def w(a, b):
    assert a != b, a
    ongrid(*a); ongrid(*b)
    WIRES.append((a, b))

def j(p):
    ongrid(*p); JUNCS.append(p)

def nc(p):
    ongrid(*p); NOCONN.append(p)

def lab(name, x, y, rot=0):
    ongrid(x, y); LABELS.append((name, x, y, rot))

def hlab(name, shape, x, y, rot=0):
    ongrid(x, y); HLABELS.append((name, shape, x, y, rot))

# ---------------------------------------------------------------- channel table
# ChannelIndex order.  Firmware is already written and tested against this order;
# scrambling it produces a board whose colours and corners do not match the app.
CH = [(c, k) for c in ("FL", "FR", "RL", "RR") for k in ("R", "G", "B")]

# ================================================================ BLOCK A: PCA9685
U7 = place("U7", "Driver_LED:PCA9685PW", "PCA9685PW", 60.96, 63.5, 0, PCA,
           [("Reference", "U7", 60.96, 33.02, 0), ("Value", "PCA9685PW", 60.96, 96.52, 0)],
           desc="16-channel, 12-bit PWM Fm+ I2C-bus LED controller, TSSOP-28")
# VDD from the SWITCHED rail: the driver is unpowered in sleep, which is half of why
# the outputs cannot come on by accident.  See the ~OE note.
w(U7["28"], (U7["28"][0], 33.02)); w((U7["28"][0], 33.02), (25.4, 33.02))
hlab("+3V3_SW", "input", 25.4, 33.02, 180)
a, b = vpart("C41", "Device:C", "10uF", 53.34, 33.02); gnd(*b); j(a)
a, b = vpart("C42", "Device:C", "100nF", 45.72, 33.02); gnd(*b); j(a)
gnd(*U7["14"])
# I2C out as short stubs; the pull-ups live in block A2 and join by label
w(U7["27"], (33.02, U7["27"][1])); hlab("I2C_SDA", "bidirectional", 33.02, U7["27"][1], 180)
w(U7["26"], (33.02, U7["26"][1])); hlab("I2C_SCL", "bidirectional", 33.02, U7["26"][1], 180)
# EXTCLK tied to GND rather than left floating
w(U7["25"], (35.56, U7["25"][1])); gnd(35.56, U7["25"][1])
# ~OE pulled LOW = outputs enabled.  "Disabled by default" comes from the switched rail
# and the PCA9685's own power-on state, not from this pin -- see the note.
w(U7["23"], (40.64, U7["23"][1]))
a, b = vpart("R78", "Device:R", "10k", 40.64, U7["23"][1]); gnd(*b)
# A0-A5 to GND -> I2C address 0x40
for pnum in ("1", "2", "3", "4", "5", "24"):
    p = U7[pnum]
    w(p, (38.1, p[1])); j((38.1, p[1]))
w((38.1, U7["1"][1]), (38.1, U7["24"][1]))
w((38.1, U7["24"][1]), (38.1, 91.44)); gnd(38.1, 91.44)
# LED0-11 -> the 12 PWM nets, in ChannelIndex order.  LED12-15 unused.
for i, (corner, colour) in enumerate(CH):
    p = U7[str(6 + i)] if i < 8 else U7[str(15 + i - 8)]
    end = (round(p[0] + 7.62, 4), p[1])
    w(p, end); lab("PWM_%s_%s" % (corner, colour), end[0], end[1])
for pnum in ("19", "20", "21", "22"):
    nc(U7[pnum])

# ---------------------------------------------------------------- BLOCK A2: I2C pull-ups
for k, (net, rref) in enumerate((("I2C_SDA", "R76"), ("I2C_SCL", "R77"))):
    x = round(20.32 + k * 7.62, 4)
    w((x, 104.14), (x, 109.22)); lab(net, x, 104.14, 90)
    vpart(rref, "Device:R", "4.7k", x, 109.22)
    w((x, 116.84), (x, 121.92)); lab("+3V3_SW", x, 121.92, 90)

# ================================================================ BLOCK B: 12 channels
# Each channel: PWM -> gate (with pulldown); drain -> RET to the corner connector;
# source -> sense node -> 10 ohm shunt -> GND.
UNIT_PINS = {1: {"G": "2", "S": "1", "D": "6"}, 2: {"G": "5", "S": "4", "D": "3"}}
for i, (corner, colour) in enumerate(CH):
    y = round(30.48 + i * 25.4, 4)
    ref = "Q%d" % (4 + i // 2)
    unit = (i % 2) + 1
    pm = UNIT_PINS[unit]
    pins = {pm["G"]: NFET["1"], pm["S"]: NFET["2"], pm["D"]: NFET["3"]}
    key = "%s_%d" % (ref, unit)
    Q = place(ref, "mccan_parts:NX5020UNBKS", "NX5020UNBKS", 165.1, y, 0, pins,
              [("Reference", "%s%s" % (ref, "AB"[unit - 1]), 168.91, y - 1.27, 0),
               ("Value", "NX5020UNBKS", 168.91, y + 1.27, 0)],
              desc="50 V dual N-channel Trench MOSFET, Rds(on) specified at Vgs = 2.5 V, SOT363",
              unit=unit, key=key)
    G, S, D = Q[pm["G"]], Q[pm["S"]], Q[pm["D"]]
    # gate
    w((142.24, y), G); lab("PWM_%s_%s" % (corner, colour), 142.24, y)
    j((149.86, y)); w((149.86, y), (149.86, round(y + 5.08, 4)))
    vpart("R%d" % (40 + i), "Device:R", "10k", 149.86, round(y + 5.08, 4))
    gnd(149.86, round(y + 12.7, 4))
    # drain -> RET
    w(D, (D[0], round(y - 12.7, 4))); lab("RET_%s_%s" % (corner, colour), D[0], round(y - 12.7, 4), 90)
    # source -> sense node -> shunt -> GND
    w(S, (S[0], round(y + 7.62, 4)))
    vpart("R%d" % (52 + i), "Device:R", "10R", S[0], round(y + 7.62, 4))
    gnd(S[0], round(y + 15.24, 4))
    j((S[0], round(y + 7.62, 4)))
    w((S[0], round(y + 7.62, 4)), (182.88, round(y + 7.62, 4)))
    lab("SENSE_%s_%s" % (corner, colour), 182.88, round(y + 7.62, 4))

# ================================================================ BLOCK B2: sense protection
# 10 kOhm in series with every sense node, and a clamp to +3V3_SW.  The series resistor
# is what actually bounds a fault: at 24 V on a sense node it admits 2 mA, far inside the
# mux's input rating.  The clamp is redundancy, and a quad array may replace the
# discretes at layout to save area.
for i, (corner, colour) in enumerate(CH):
    y = round(30.48 + i * 19.05, 4)
    w((233.68, y), (241.3, y)); lab("SENSE_%s_%s" % (corner, colour), 233.68, y)
    a, b = hpart("R%d" % (64 + i), "Device:R", "10k", 241.3, y)
    w(b, (259.08, y))
    lab("MUXIN_%s_%s" % (corner, colour), 259.08, y)
    j((254.0, y))
    place("D%d" % (9 + i), "Device:D_Schottky", "BAT54", 254.0, round(y - 3.81, 4), 270, DIODE,
          [("Reference", "D%d" % (9 + i), 256.54, round(y - 5.08, 4), 0),
           ("Value", "BAT54", 256.54, round(y - 2.54, 4), 0)],
          desc="Schottky diode")
    w((254.0, round(y - 7.62, 4)), (254.0, round(y - 12.7, 4)))
    lab("+3V3_SW", 254.0, round(y - 12.7, 4), 90)

# ================================================================ BLOCK C: ADG706 mux
U8 = place("U8", "mccan_parts:ADG706", "ADG706", 355.6, 91.44, 0, ADG,
           [("Reference", "U8", 355.6, 60.96, 0), ("Value", "ADG706", 355.6, 124.46, 0)],
           desc="16-to-1 analog multiplexer, 1.8 V to 5.5 V single supply, TSSOP-28")
for i, (corner, colour) in enumerate(CH):
    p = U8[_SN[i + 1]]
    w((330.2, p[1]), p); lab("MUXIN_%s_%s" % (corner, colour), 330.2, p[1], 180)
# S13-S16 unused: tied to GND, per the datasheet's guidance for unused inputs
for i in range(13, 17):
    p = U8[_SN[i]]
    w((335.28, p[1]), p); j((335.28, p[1]))
w((335.28, U8[_SN[13]][1]), (335.28, U8[_SN[16]][1]))
w((335.28, U8[_SN[16]][1]), (335.28, 127.0)); gnd(335.28, 127.0)
# address lines
for pnum, net in (("17", "MUX_S0"), ("16", "MUX_S1"), ("15", "MUX_S2"), ("14", "MUX_S3")):
    p = U8[pnum]
    w(p, (388.62, p[1])); hlab(net, "input", 388.62, p[1], 0)
# EN tied enabled
w(U8["18"], (388.62, U8["18"][1])); lab("+3V3_SW", 388.62, U8["18"][1])
# supply
w(U8["1"], (U8["1"][0], 60.96)); w((U8["1"][0], 60.96), (335.28, 60.96))
lab("+3V3_SW", 335.28, 60.96, 180)
a, b = vpart("C43", "Device:C", "100nF", 342.9, 60.96); gnd(*b); j(a)
gnd(*U8["12"]); gnd(*U8["27"])
for pnum in ("2", "3", "13"):
    nc(U8[pnum])
# output -> RGB_ISNS, with the SAR sample-and-hold buffer cap
w(U8["28"], (401.32, U8["28"][1])); hlab("RGB_ISNS", "output", 401.32, U8["28"][1], 0)
j((396.24, U8["28"][1])); w((396.24, U8["28"][1]), (396.24, 114.3))
a, b = vpart("C45", "Device:C", "10nF", 396.24, 114.3); gnd(*b)

# ================================================================ BLOCK D: PROFET
U9 = place("U9", "mccan_parts:BTS7008_2EPA", "BTS7008-2EPA", 368.3, 190.5, 0, BTS,
           [("Reference", "U9", 368.3, 168.91, 0), ("Value", "BTS7008-2EPA", 368.3, 213.36, 0)],
           desc="Dual smart high-side switch, one multiplexed IS output with DSEL select, "
                "PG-TSDSO-14.  PIN NUMBERS ARE PLACEHOLDERS - verify before Task 8.")
w(U9["8"], (U9["8"][0], 163.83)); w((U9["8"][0], 163.83), (340.36, 163.83))
hlab("VBAT", "input", 340.36, 163.83, 180)
a, b = vpart("C46", "Device:C", "10uF", 355.6, 163.83); gnd(*b); j(a)
a, b = vpart("C47", "Device:C", "100nF", 347.98, 163.83); gnd(*b); j(a)
gnd(*U9["9"])
# inputs and control, all as stubs to hierarchical labels
for pnum, net in (("1", "PWM_DEN_A"), ("2", "PWM_DEN_B"),
                  ("3", "EN_DIAG"), ("4", "DEN_DSEL")):
    p = U9[pnum]
    w((325.12, p[1]), p); hlab(net, "input", 325.12, p[1], 180)
# the two PWM_DEN pulldowns, joined by label so they cross nothing
for k, (net, rref) in enumerate((("PWM_DEN_A", "R79"), ("PWM_DEN_B", "R80"))):
    x = round(340.36 + k * 10.16, 4)
    w((x, 215.9), (x, 220.98)); lab(net, x, 215.9, 90)
    vpart(rref, "Device:R", "10k", x, 220.98); gnd(x, 228.6)
# ONE multiplexed IS output -> scaling resistor -> ISNS_DEN, with a clamp
p = U9["7"]
w(p, (396.24, p[1]))
a, b = vpart("R81", "Device:R", "TBD-see-note", 396.24, p[1])
gnd(*b)
j((396.24, p[1])); w((396.24, p[1]), (414.02, p[1]))
hlab("ISNS_DEN", "output", 414.02, p[1], 0)
j((408.94, p[1]))
place("D21", "Device:D_Schottky", "BAT54", 408.94, round(p[1] - 3.81, 4), 270, DIODE,
      [("Reference", "D21", 411.48, round(p[1] - 5.08, 4), 0),
       ("Value", "BAT54", 411.48, round(p[1] - 2.54, 4), 0)],
      desc="Schottky diode")
w((408.94, round(p[1] - 7.62, 4)), (408.94, round(p[1] - 12.7, 4)))
hlab("+3V3_ALW", "input", 408.94, round(p[1] - 12.7, 4), 90)
# outputs
for pnum, net in (("5", "DEN_A_OUT"), ("6", "DEN_B_OUT")):
    p = U9[pnum]
    w(p, (396.24, p[1])); lab(net, 396.24, p[1])

# ================================================================ BLOCK E: PTCs
# Isolates a shorted string so one crushed cable cannot extinguish all four corners.
for i, corner in enumerate(("FL", "FR", "RL", "RR")):
    x = round(45.72 + i * 15.24, 4)
    w((x, 132.08), (x, 137.16)); lab("+24V", x, 132.08, 90)
    place("F%d" % (2 + i), "Device:Polyfuse", "1206L050/24", x, 140.97, 0, TWOPIN,
          [("Reference", "F%d" % (2 + i), x + 1.651, 139.7, 0),
           ("Value", "1206L050/24", x + 1.651, 142.24, 0)],
          desc="Resettable fuse, polymeric positive temperature coefficient")
    w((x, 144.78), (x, 149.86)); lab("+24V_%s" % corner, x, 149.86, 90)
w((96.52, 132.08), (106.68, 132.08)); lab("+24V", 96.52, 132.08)
hlab("+24V", "input", 106.68, 132.08, 0)

# ================================================================ BLOCK F: connectors
# Four corner connectors are IDENTICAL 4-way parts and CAN be mis-mated; each carries a
# distinct keying/colour code, recorded here because firmware cannot detect a swap.
KEYCODE = {"FL": "key A / black", "FR": "key B / grey",
           "RL": "key C / brown", "RR": "key D / natural"}
for i, corner in enumerate(("FL", "FR", "RL", "RR")):
    x, y = 60.96, round(179.07 + i * 33.02, 4)
    Jn = place("J%d" % (3 + i), "Connector:Conn_01x04_Pin", "%s  SS1.0 4w  %s" % (corner, KEYCODE[corner]),
               x, y, 0, CONN[4],
               [("Reference", "J%d" % (3 + i), x - 5.08, round(y - 11.43, 4), 0),
                ("Value", "%s  SS1.0 4w  %s" % (corner, KEYCODE[corner]), x - 5.08, round(y - 8.89, 4), 0)],
               desc="Generic connector, single row, 01x04")
    for k, net in enumerate(("+24V_%s" % corner, "RET_%s_R" % corner,
                             "RET_%s_G" % corner, "RET_%s_B" % corner)):
        p = Jn[str(k + 1)]
        w(p, (81.28, p[1])); lab(net, 81.28, p[1])
# Denali: two switched positives and a shared ground
J7 = place("J7", "Connector:Conn_01x03_Pin", "DENALI  SS1.5 3w", 60.96, 320.04, 0, CONN[3],
           [("Reference", "J7", 55.88, 308.61, 0), ("Value", "DENALI  SS1.5 3w", 55.88, 311.15, 0)],
           desc="Generic connector, single row, 01x03")
for k, net in enumerate(("DEN_A_OUT", "DEN_B_OUT")):
    p = J7[str(k + 1)]
    w(p, (81.28, p[1])); lab(net, 81.28, p[1])
gnd(*J7["3"])
# CAN
J8 = place("J8", "Connector:Conn_01x02_Pin", "CAN  SS1.0 2w", 60.96, 347.98, 0, CONN[2],
           [("Reference", "J8", 55.88, 337.82, 0), ("Value", "CAN  SS1.0 2w", 55.88, 340.36, 0)],
           desc="Generic connector, single row, 01x02")
for k, net in enumerate(("CANH", "CANL")):
    p = J8[str(k + 1)]
    w(p, (81.28, p[1])); hlab(net, "bidirectional", 81.28, p[1], 0)

# ================================================================ BLOCK G: DNP snubbers
# Series RC to GND on every RET net, all DNP, in case the long corner runs need taming
# during EMC work.  Fitting them is a stuff-option, not a board change.
for i, (corner, colour) in enumerate(CH):
    y = round(254.0 + i * 12.7, 4)
    w((233.68, y), (241.3, y)); lab("RET_%s_%s" % (corner, colour), 233.68, y)
    a, b = hpart("R%d" % (82 + i), "Device:R", "100R", 241.3, y, dnp=True)
    a2, b2 = hpart("C%d" % (48 + i), "Device:C", "10nF", 248.92, y, dnp=True)
    w(b2, (259.08, y)); w((259.08, y), (259.08, round(y + 5.08, 4)))
    gnd(259.08, round(y + 5.08, 4))

# ================================================================ NOTES
NOTEW = 135
def note(*parts):
    out = []
    for para in parts:
        if para.startswith("|"):
            out.extend(para[1:].split("\n"))
        else:
            out.extend(textwrap.wrap(para, NOTEW) or [""])
    NOTES.append("\n".join(out))

note("""|ACCEPTANCE (spec 5, 9.1, 9.2)
- PCA9685 on +3V3_SW, I2C, LED0-11 -> the 12 RGB switch inputs IN ChannelIndex ORDER:
  LED0,1,2 = FL R,G,B;  LED3,4,5 = FR R,G,B;  LED6,7,8 = RL R,G,B;  LED9,10,11 = RR R,G,B.
  LED12-15 UNUSED.
- 12x discrete logic-level N-MOSFET, gate direct from PCA9685, sense shunt in each source leg
- 12 SENSE_* nodes -> 16:1 analog mux (MUX_S0-S3) -> RGB_ISNS -> GPIO 32 (ADC1_CH4)
- NO SPI anywhere on this board
- Dual PROFET from VBAT, inputs PWM_DEN_A/B from ESP32 LEDC on GPIO 18/19, NOT the PCA9685
- PROFET: ONE sense output -> ISNS_DEN (GPIO 34) with scaling resistor; DEN_DSEL selects
  which channel IS reports
- 4x PTC, one per string, on the +24V feeds
- All 14 PWM_* nets have a pulldown to GND
- 4 corner connectors, keyed/colour-coded differently from each other
- Denali connector: 2 switched positives + 1 shared ground
- Output snubber footprints present but DNP""")

note("""|SENSE CHAIN (spec 5.1) -- VALUES REVISED, THE PLAN TEXT IS STALE
10 ohm x 26.7 mA = 267 mV at full channel current (133 mV if the 6 cm strip length is used).
ADC1 at 0 dB attenuation (0-1.1 V range).  Classification is open (~0 mV) / working (~267 mV) /
shorted (saturated) -- NOT precision current metering.""",
"""Task 6 of the plan still says "1 ohm" and "140 mV", and asks for 2512 >= 1 W shunts.  Those
figures predate the RGB load being corrected downward by about 4x (spec 2.2); part-selection.md
rows 1b.1-1b.3 carry the current values and explicitly WITHDRAW the 2512 requirement.""",
"""Sampling is on-demand: firmware drives one channel to 100%, steps the mux, reads, advances.
The same sweep serves as the installation self-test.""")

note("""|SHUNT RATING DEPENDS ON A FIRMWARE BEHAVIOUR -- READ THIS BEFORE CHANGING EITHER
Normal dissipation in a 10 ohm shunt is 26.7 mA^2 x 10 = 7 mW, so an 0805 or 1206 is ample.""",
"""A SHORTED channel is different.  The boost then current-limits at roughly 0.5 A, which puts
about 2.5 W into that one shunt -- ten times a 1206's rating.  It survives only because the
diagnostic sweep is brief and because firmware LATCHES A SHORTED CHANNEL OFF once it classifies
one.  That makes the shunt package rating conditional on firmware behaviour, which is exactly
the kind of cross-domain dependency that gets lost between disciplines.""",
"""It is written down in three places on purpose: here, in part-selection.md, and it belongs in
the firmware spec (spec section 12) when that is written.  If firmware does NOT latch off, move
the shunts to 2512 1 W.""")

note("""|WHY ~OE IS PULLED LOW (R78) RATHER THAN HIGH
The plan says "OE tied so outputs are disabled by default".  Taken literally that means pulling
~OE HIGH -- but no GPIO is allocated to release it, so the board would be permanently dark.""",
""""Disabled by default" is already delivered twice over without this pin: the PCA9685 sits on
+3V3_SW so it is unpowered in sleep, and it powers up with MODE1 SLEEP set and every LEDn
register cleared, i.e. outputs off.  R78 holds ~OE low so the part is usable; the safe state
comes from the rail and the power-on register defaults.""")

note("""|SENSE-PATH PROTECTION (I15)
Each sense node reaches its mux input through 10 kOhm (R64-R75) with a clamp to +3V3_SW.
The SERIES RESISTOR is what actually bounds a fault: at 24 V on a sense node it admits 2 mA,
far inside the ADG706's input rating.  The clamps (D9-D20) are redundancy.""",
"""C45, 10 nF at the mux output, supplies the ADC's sample-and-hold charge locally, which is what
makes 10 kOhm series resistors harmless.  tau = 100 us, so firmware must wait >= 500 us after
each mux step before reading.  100 nF would stretch that to 1 ms.""",
"""A quad diode array may replace D9-D20 at layout to save area.""")

note("""|PROFET PIN NUMBERS ARE PLACEHOLDERS -- BLOCKER FOR TASK 8
No Infineon datasheet for the BTS7008-2EPA is held locally.  The pin NAMES on U9 are from
verified notes in part-selection.md; the pin NUMBERS are invented, and the package is
PG-TSDSO-14, so five further pins exist that are not modelled at all.""",
"""R81, the IS scaling resistor, is likewise unsized: it needs the part's kILIS current-sense
ratio.  Its value reads TBD-see-note deliberately so it cannot pass a BOM review unnoticed.""",
"""Nothing here can reach fabrication without passing through footprint assignment in Task 8,
which is where this must be resolved.  Get the datasheet first.""")

note("""|CORNER CONNECTORS CAN BE MIS-MATED -- THIS IS A SAFETY ITEM (spec 9.2)
All four are identical Superseal 1.0 4-way parts.  Swapping front for rear reverses the
indicators, and the firmware cannot detect it.  Each connector carries a distinct keying or
colour code in its Value field: FL key A / black, FR key B / grey, RL key C / brown,
RR key D / natural.  Carry these into the harness build and the install instructions.""")

note("""|PTCs (F2-F5), one per string
Isolates a shorted string so one crushed cable cannot extinguish all four corners (spec 5.2).
Littelfuse 1206L050/24: Ihold 0.50 A at 23 C, 0.31 A at 65 C, against an 80 mA per-string load.
That is a 3.9x margin at the hot internal temperature, which is the case that matters.""")

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
A('\t(paper "A2")')
A("\t(title_block")
A('\t\t(title "outputs")')
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
    A("\t\t(at 460.0 %s 0)" % fs(ny))
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
assert ny < 400.0, "notes overflow: %s" % ny

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
    A("\t\t(unit %d)" % s["unit"])
    A("\t\t(body_style 1)")
    A("\t\t(exclude_from_sim no)")
    A("\t\t(in_bom yes)")
    A("\t\t(on_board yes)")
    A("\t\t(in_pos_files yes)")
    A("\t\t(dnp %s)" % ("yes" if s["dnp"] else "no"))
    A('\t\t(uuid "%s")' % U("s" + s["key"]))
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
        A('\t\t\t(uuid "%s")' % U("p%s.%s" % (s["key"], n)))
        A("\t\t)")
    A("\t\t(instances")
    A('\t\t\t(project "mccan"')
    A('\t\t\t\t(path "%s"' % INST_PATH)
    A('\t\t\t\t\t(reference "%s")' % s["ref"])
    A("\t\t\t\t\t(unit %d)" % s["unit"])
    A("\t\t\t\t)")
    A("\t\t\t)")
    A("\t\t)")
    A("\t)")

A(")")

import kicanon
_text = kicanon.canonicalise("\n".join(out) + "\n")
open(os.path.join(HW, "sheets", "outputs.kicad_sch"), "w",
     encoding="utf-8", newline="\n").write(_text)
print("symbols:", len(SYMS), " wires:", len(WIRES), " junctions:", len(set(JUNCS)),
      " no-connects:", len(set(NOCONN)), " labels:", len(LABELS),
      " hlabels:", len(HLABELS), " notes end y:", ny)
