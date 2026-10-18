#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/sheets/outputs.kicad_sch (KiCad 10.0.2, format 20260306).

Plan4 phase A, Task 7: ten signal outputs on three TI TPS4H160B-Q1 quad smart high-side
switches (U11-U13, channel allocation D1), their input, sense and control networks, the two
kit-gated aux placeholders, and the harness tails J3/J4/J5 (D5) plus the CAN tail J8.
Pads and application values come from quadpins.py; nothing is re-typed here.
"""
import os, re, sys, uuid, textwrap
import fpmap
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


import quadpins
from quadpins import PINS

def pins_of(blk):
    """{pad number: (x, y)} from an embedded lib_symbols block (library coords, y up)."""
    out = {}
    for mm in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) \d+\).*?\(number "([^"]+)"',
                          blk, re.S):
        out[mm.group(3)] = (float(mm.group(1)), float(mm.group(2)))
    return out

LIBS = []
for lid in ("Device:C", "Device:D_Schottky", "Device:R", "power:GND"):
    LIBS.append(from_schematic("power_input.kicad_sch", lid))
CONN = {}
for n in (2, 3, 4, 5):
    blk = from_library(os.path.join(STOCK, "Connector.kicad_sym"), "Conn_01x%02d_Pin" % n,
                       "Connector:Conn_01x%02d_Pin" % n)
    LIBS.append(blk)
    CONN[n] = pins_of(blk)
_qblk = from_library(os.path.join(HW, "symbols", "mccan_parts.kicad_sym"),
                     quadpins.LIB_ID.split(":")[1], quadpins.LIB_ID)
LIBS.append(_qblk)
LIBS.sort(key=lambda b: re.search(r'\(symbol "([^"]+)"', b).group(1))

# The quad's pin offsets, read from the symbol itself, and cross-checked against quadpins so
# a pad that moved in one place and not the other stops the build.
QUAD = pins_of(_qblk)
assert sorted(QUAD, key=int) == sorted((p for v in PINS.values() for p in v), key=int), \
    "symbol pads %s do not match quadpins.PINS" % sorted(QUAD, key=int)

# ---------------------------------------------------------------- geometry
def pin(x, y, rot, px, py):
    if rot == 0:    return (round(x + px, 4), round(y - py, 4))
    if rot == 90:   return (round(x - py, 4), round(y - px, 4))
    if rot == 180:  return (round(x - px, 4), round(y + py, 4))
    if rot == 270:  return (round(x + py, 4), round(y + px, 4))
    raise ValueError(rot)

TWOPIN = {"1": (0, 3.81), "2": (0, -3.81)}          # R, C
DIODE  = {"1": (-3.81, 0), "2": (3.81, 0)}          # 1 = K, 2 = A

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

# A net that crosses to another sheet gets ONE hierarchical label (so the root grows one sheet
# pin for it, Task 8); every further appearance on this sheet is a local label of the same name,
# which KiCad joins to it.  Shapes follow the other generators: supplies and nets driven from
# mcu_can are inputs here, the sense lines this sheet drives are outputs.
SHAPE = {"VBAT": "input", "+3V3_ALW": "input", "+5V": "input",
         "DIAG_EN_Q": "input", "DIAG_SEL0_Q": "input", "DIAG_SEL1_Q": "input",
         "SNS_A": "output", "SNS_B": "output", "SNS_C": "output"}
_SEEN = set()
def xlab(name, x, y, rot=0):
    if name in _SEEN:
        lab(name, x, y, rot)
    else:
        _SEEN.add(name)
        hlab(name, SHAPE[name], x, y, rot)

# ================================================================ channel table (D1)
# Chip -> (ref, sense line, [function per channel 1..4]).  None = spare.  One dead chip never
# takes out both sides' indicators, and brake survives a side chip failing.
CHIPS = [("U11", "A", ["FL_DRL", "FL_IND", "RL_DRL", "RL_IND"]),
         ("U12", "B", ["FR_DRL", "FR_IND", "RR_DRL", "RR_IND"]),
         ("U13", "C", ["RL_BRK", "RR_BRK", None, None])]

# Reference allocation (all on this sheet; R40-R75, C41-C46, D8-D10 were freed by deleting
# the plan3 RGB stage):
#   R40-R49  IN series (R_IN_SERIES), used channels in CHIPS order
#   R50-R61  IN pull-downs (R_IN_PULLDOWN), all twelve channels in CHIPS order
#   R62-R64  R_CL, R65-R67 R_THER, R68-R70 R_SNS, R71-R73 sense series 4.7k  (U11, U12, U13)
#   R74/R75  OUT_AUX_L / OUT_AUX_R pull-downs
#   C41-C43  C_VS, C44-C46 sense filter 10 nF, D8-D10 BAT54 clamps            (U11, U12, U13)
SER = iter("R%d" % i for i in range(40, 50))
PD = iter("R%d" % i for i in range(50, 62))

# Sense path: series resistor between the chip's CS node and the ADC line.  At the 6.5 V
# worst-case fault level it holds the clamp current to (6.5 - 3.3 - 0.3) / 4.7k = 0.6 mA.
R_SNS_SERIES = "4.7k"
C_SNS_FILTER = "10nF"
CLAMP = "BAT54"

assert quadpins.C_OUT is None, \
    "quadpins.C_OUT is set: add the output capacitors (>= 63 V, 0805+) before regenerating"

def in_net(fn, ref, ch):
    return ("IN_" + fn) if fn else ("IN_%s_CH%d_SPARE" % (ref, ch))

# ================================================================ BLOCK A: input chains
# OUT_<fn> (the ESP32 pad, from mcu_can) -> R_IN_SERIES -> IN_<fn> (the chip pin) with
# R_IN_PULLDOWN to GND on the chip side: every IN net is low while the ESP32 is in reset, and
# no IN net has a path to a supply (Review Focus 1).  Spares get the pull-down only.
ROW0, PITCH = 30.48, 15.24
row = 0
for ref, _s, fns in CHIPS:
    for ch, fn in enumerate(fns, 1):
        y = round(ROW0 + row * PITCH, 4)
        row += 1
        net = in_net(fn, ref, ch)
        rpd = next(PD)
        if fn:
            hlab("OUT_" + fn, "input", 25.4, y, 180)
            w((25.4, y), (33.02, y))
            hpart(next(SER), "Device:R", quadpins.R_IN_SERIES, 33.02, y)
            w((40.64, y), (45.72, y)); w((45.72, y), (50.8, y)); j((45.72, y))
        else:
            w((45.72, y), (50.8, y))
        vpart(rpd, "Device:R", quadpins.R_IN_PULLDOWN, 45.72, y); gnd(45.72, round(y + 7.62, 4))
        lab(net, 50.8, y)

# ================================================================ BLOCK B: aux placeholders
# OUT_AUX_L / OUT_AUX_R: the switch stage is kit-gated (spec 9.1).  Until then each GPIO ends in
# one pull-down and nothing else, so the pin is defined and the net exists for the kit plan.
for net, rref in (("OUT_AUX_L", "R74"), ("OUT_AUX_R", "R75")):
    y = round(ROW0 + row * PITCH, 4)
    row += 1
    hlab(net, "input", 25.4, y, 180)
    w((25.4, y), (45.72, y))
    vpart(rref, "Device:R", quadpins.R_IN_PULLDOWN, 45.72, y); gnd(45.72, round(y + 7.62, 4))

# ================================================================ BLOCK C: the three quads
X0, Y0, DY = 152.4, 63.5, 101.6
for k, (ref, sx, fns) in enumerate(CHIPS):
    X, Y = X0, round(Y0 + k * DY, 4)
    Q = place(ref, quadpins.LIB_ID, quadpins.PART, X, Y, 0, QUAD,
              [("Reference", ref, X + 2.54, Y + 29.21, 0),
               ("Value", quadpins.PART, X + 2.54, Y + 31.75, 0)],
              desc="TI TPS4H160-Q1 Version B: quad 160 mOhm smart high-side switch, adjustable "
                   "current limit, multiplexed current-sense output, HTSSOP-28 + EP")
    P = lambda name, i=0: Q[PINS[name][i]]

    # VS: all four pads on one bus, C_VS at its right end, VBAT at its left end
    yb = round(Y - 30.48, 4)
    xs = sorted(P("VS", i)[0] for i in range(len(PINS["VS"])))
    for p in PINS["VS"]:
        w(Q[p], (Q[p][0], yb)); j((Q[p][0], yb))
    pts = [round(X - 17.78, 4)] + xs + [round(X + 17.78, 4)]
    for a, b in zip(pts, pts[1:]):
        w((a, yb), (b, yb))
    xlab("VBAT", pts[0], yb, 180)
    _, cb = vpart("C%d" % (41 + k), "Device:C", quadpins.C_VS, pts[-1], yb); gnd(*cb)

    # GND pads and the exposed pad straight to GND (no TI GND network: feed A's LTC4380
    # already blocks reverse polarity)
    for p in PINS["GND"] + PINS["EP"]:
        gnd(*Q[p])

    # left side: every control pin out to a label
    xl = round(X - 20.32, 4)
    for ch, fn in enumerate(fns, 1):
        p = P("IN%d" % ch); w(p, (xl, p[1])); lab(in_net(fn, ref, ch), xl, p[1], 180)
    for name, net in (("DIAG_EN", "DIAG_EN_Q"), ("SEL0", "DIAG_SEL0_Q"), ("SEL1", "DIAG_SEL1_Q")):
        p = P(name); w(p, (xl, p[1])); xlab(net, xl, p[1], 180)
    for name in ("THER", "CL"):
        p = P(name); w(p, (xl, p[1])); lab("%s_%s" % (name, sx), xl, p[1], 180)

    # right side: both OUT pads of a used channel to its function net; spares no-connect
    xr = round(X + 20.32, 4)
    for ch, fn in enumerate(fns, 1):
        for p in PINS["OUT%d" % ch]:
            if fn:
                w(Q[p], (xr, Q[p][1])); lab(fn, xr, Q[p][1])
            else:
                nc(Q[p])
    nc(P("FAULT"))                                       # R6: no GPIO left; CS reports faults
    for p in PINS["OTHER"]:
        nc(Q[p])                                         # R6: NC pads

    # sense: CS_x -> R_SNS to GND; -> 4.7k -> SNS_x; on SNS_x only, the BAT54 clamp (anode
    # SNS_x, cathode +3V3_ALW) and the 10 nF ADC charge reservoir
    p = P("SNS"); ys = p[1]
    w(p, (xr, ys)); lab("CS_" + sx, xr, ys)
    xa = round(X + 27.94, 4)
    w((xr, ys), (xa, ys)); j((xa, ys))
    _, b = vpart("R%d" % (68 + k), "Device:R", quadpins.R_SNS, xa, ys); gnd(*b)
    w((xa, ys), (round(X + 33.02, 4), ys))
    hpart("R%d" % (71 + k), "Device:R", R_SNS_SERIES, round(X + 33.02, 4), ys)
    xd, xc, xh = round(X + 45.72, 4), round(X + 53.34, 4), round(X + 60.96, 4)
    w((round(X + 40.64, 4), ys), (xd, ys)); w((xd, ys), (xc, ys)); w((xc, ys), (xh, ys))
    j((xd, ys)); j((xc, ys))
    dref = "D%d" % (8 + k)
    place(dref, "Device:D_Schottky", CLAMP, xd, round(ys - 3.81, 4), 270, DIODE,
          [("Reference", dref, xd + 2.54, round(ys - 5.08, 4), 0),
           ("Value", CLAMP, xd + 2.54, round(ys - 2.54, 4), 0)],
          desc="Schottky diode")
    w((xd, round(ys - 7.62, 4)), (xd, round(ys - 12.7, 4)))
    xlab("+3V3_ALW", xd, round(ys - 12.7, 4), 90)
    _, b = vpart("C%d" % (44 + k), "Device:C", C_SNS_FILTER, xc, ys); gnd(*b)
    xlab("SNS_" + sx, xh, ys, 0)

    # CL -> R_CL -> GND;  +5V -> R_THER -> THER (latch mode while awake)
    xcl, xth, yt = round(X + 76.2, 4), round(X + 86.36, 4), round(Y - 12.7, 4)
    w((xcl, yt), (xcl, round(yt + 5.08, 4))); lab("CL_" + sx, xcl, yt, 90)
    _, b = vpart("R%d" % (62 + k), "Device:R", quadpins.R_CL, xcl, round(yt + 5.08, 4)); gnd(*b)
    w((xth, yt), (xth, round(yt + 5.08, 4))); xlab("+5V", xth, yt, 90)
    _, b = vpart("R%d" % (65 + k), "Device:R", quadpins.R_THER, xth, round(yt + 5.08, 4))
    w(b, (xth, round(b[1] + 5.08, 4))); lab("THER_" + sx, xth, round(b[1] + 5.08, 4), 270)

# ================================================================ BLOCK D: harness tails (D5)
# Soldered wire tails, not connectors: the Superseal joints are out on the harness.
TAILS = [("J3", ["FL_DRL", "FL_IND", "FR_DRL", "FR_IND", "GND"], "FRONT tail",
          "Soldered wire tail, front run: FL/FR DRL and indicator, shared return"),
         ("J4", ["RL_DRL", "RL_IND", "RL_BRK", "GND"], "REAR tail 1 (7-core)",
          "Soldered wire tail, rear 7-core run part 1: RL DRL/indicator/brake, shared return"),
         ("J5", ["RR_DRL", "RR_IND", "RR_BRK"], "REAR tail 2 (7-core)",
          "Soldered wire tail, rear 7-core run part 2: RR DRL/indicator/brake"),
         ("J8", ["CANH", "CANL"], "CAN pigtail -> SS1.0 2w",
          "Soldered wire tail, 22 AWG twisted pair -- keep the twist to the pads")]
TX, ty = 279.4, 63.5
for jref, nets, val, desc in TAILS:
    n = len(nets)
    top = min(-py for _, py in CONN[n].values())
    Jn = place(jref, "Connector:Conn_01x%02d_Pin" % n, val, TX, ty, 0, CONN[n],
               [("Reference", jref, TX - 5.08, round(ty + top - 6.35, 4), 0),
                ("Value", val, TX - 5.08, round(ty + top - 3.81, 4), 0)],
               desc=desc)
    for i, net in enumerate(nets, 1):
        p = Jn[str(i)]
        if net == "GND":
            gnd(*p)
        elif net in ("CANH", "CANL"):
            w(p, (round(TX + 20.32, 4), p[1])); hlab(net, "bidirectional", round(TX + 20.32, 4), p[1], 0)
        else:
            w(p, (round(TX + 20.32, 4), p[1])); lab(net, round(TX + 20.32, 4), p[1])
    ty = round(ty + 38.1, 4)

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

note("""|SIGNAL OUTPUTS (spec 4.4, plan4 decision D1) -- three TI TPS4H160B-Q1 quads, ten channels, two spare
         CH1        CH2        CH3        CH4        sense
  U11    FL_DRL     FL_IND     RL_DRL     RL_IND     SNS_A   (left)
  U12    FR_DRL     FR_IND     RR_DRL     RR_IND     SNS_B   (right)
  U13    RL_BRK     RR_BRK     spare      spare      SNS_C   (brake)""",
"""One dead chip never takes out both sides' indicators, and brake survives a side chip failing.
Both OUT pads of each channel are tied to the channel's net.  No output capacitor: TI's typical
application (Fig. 8-1) shows none.  VS is VBAT (feed A, behind the LTC4380) with one 100 nF
100 V 0805 per chip (C41-C43) -- the SMBJ24A clamps at 50.6 V, so nothing on VBAT is under 63 V.""")

note("""|U13 CH3 -- RESERVED FOR AUX_MODE (spec 3), WIRED IN THE KIT PLAN.  U13 CH4 -- SPARE.
Both spare inputs are pulled down (R60, R61) and both spare outputs are no-connect.  Do not
re-use U13 ch3 for anything else: the kit plan needs it.""")

note("""|INPUTS -- WHY EVERY IN NET IS LOW AT RESET
Each OUT_* GPIO reaches its IN pin through R_IN_SERIES (4.7 kOhm, TI 7.3.7.5) and the IN net
carries R_IN_PULLDOWN (47 kOhm) to GND, so no channel can light while the ESP32 is in reset, in
download mode or asleep.  Driven high: 3.3 V x 32.0 k / (32.0 k + 4.7 k) = 2.88 V against
VIH = 2.0 V (47 k in parallel with the 100 k minimum internal pull-down).  Series R40-R49,
pull-downs R50-R61.""",
"""DIAG_EN_Q, DIAG_SEL0_Q and DIAG_SEL1_Q are shared by all three chips.  Their 4.7 kOhm series
resistors and the 47 kOhm DIAG_EN_Q pull-down live on mcu_can; SEL0/SEL1 have no external pull
(their level is irrelevant while DIAG_EN is low).""")

note("""|CURRENT LIMIT, THERMAL MODE, FAULT, GROUND
CL: R62-R64 = 4.02 kOhm -> 0.8 V x 2500 / 4.02 k = 0.50 A per channel (Eq. 4).
THER: R65-R67 = 10 kOhm to the GATED +5V -> latch-off while awake, so the firmware owns retry with
backoff (spec 6.3); with +5V off in sleep the pin's internal pull-down draws nothing.
FAULT: not connected -- no GPIO left; the per-chip sense line reports faults (4.5-6.5 V level).
GND pads and the exposed pad go straight to GND: feed A's LTC4380 already blocks reverse
polarity, so TI's GND resistor/diode network is not fitted.""")

note("""|SENSE PATH -- CS -> R_SNS -> 4.7 k -> SNS_x, CLAMPED ON THE ADC SIDE ONLY (Review Focus 4)
R68-R70 = 1.8 kOhm set the scale: 3.0 V at the 0.5 A limit (K = 300), 0.48 V at 80 mA.
On a short or over-temperature the CS pin goes to its 4.5-6.5 V fault level.  R71-R73 (4.7 kOhm)
then carry (6.5 - 3.3 - 0.3) / 4.7 k = 0.6 mA into the BAT54 (D8-D10, anode SNS_x, cathode
+3V3_ALW), which holds the ADC pin at ~3.6 V.  The clamp sits on SNS_x deliberately: on the CS
node it would have no series resistor to limit its current.""",
"""C44-C46 (10 nF) at the ADC end supply the SAR sample-and-hold charge locally; tau with 4.7 k is
tau = (4.7 k + 1.8 k) x 10 nF = 65 us, so firmware waits >= 400 us after any DIAG_SEL or DIAG_EN change before reading.  A reading above
~3.0 V means fault, not current.""")

note("""|AUX OUTPUTS -- PLACEHOLDERS ONLY (spec 9.1, kit-gated)
OUT_AUX_L and OUT_AUX_R each end in one 47 kOhm pull-down (R74, R75) and nothing else.  The
switch stage, the pod tail and the R100 re-size are kit-gated (spec 9.1) and are added in the
kit plan, not here.""")

note("""|HARNESS TAILS (D5) -- SOLDERED WIRE, NOT CONNECTORS
J3 front: FL_DRL, FL_IND, FR_DRL, FR_IND, GND.  J4 rear part 1: RL_DRL, RL_IND, RL_BRK, GND.
J5 rear part 2: RR_DRL, RR_IND, RR_BRK.  J8: CAN twisted pair.""",
"""J4 and J5 are one 7-core cable through one gland, split across two tails only because KiCad's
Connector_Wire relief footprints stop at 1x06; the 7-core run has one return (spec 3.1), on J4.
The Superseal joints sit out on the harness.  The _Relief footprints' second, unplated hole per
conductor is the strain relief: nothing else mechanically restrains these wires.""")

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
    A("\t\t\t(justify %s bottom)" % ("right" if rot in (180, 270) else "left"))
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
    A("		(in_bom %s)" % ("yes" if fpmap.in_bom(s["ref"]) else "no"))
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
        _v = fpmap.fp(s["ref"]) if extra == "Footprint" else (
            "" if extra != "Description" else s["desc"])
        props.append((extra, _v, s["x"], s["y"], 0, True))
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
