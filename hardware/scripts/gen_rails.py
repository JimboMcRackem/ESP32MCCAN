#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/sheets/rails.kicad_sch (KiCad 10.0.2, format 20260306)."""
import os, re, uuid
import fpmap

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
SHEET_UUID = "41ca87d7-21c7-4e64-9af2-9cbb98c5af77"          # keep existing
INST_PATH = "/7410bb74-5653-4f1b-8c7c-ce17eb633f20/4a66277e-62b8-454b-8781-170494cf9f57"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def U(key):
    return str(uuid.uuid5(NS, "rails:" + key))

# ---------------------------------------------------------------- lib_symbols
def extract_block(text, header):
    """Return the full paren-balanced s-expression that `header` introduces,
    starting at its opening '(' (leading indentation stripped)."""
    i = text.index(header)
    i = text.index("(", i)
    depth = 0
    j = i
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
    """power_input.kicad_sch already stores these at 2-tab depth, verbatim from stock."""
    src = open(os.path.join(HW, "sheets", "power_input.kicad_sch"), encoding="utf-8").read()
    return reindent(extract_block(src, '\t\t(symbol "%s"\n' % libid), 2, 0)

def from_library(path, name, libid):
    src = open(path, encoding="utf-8").read()
    blk = extract_block(src, '\t(symbol "%s"\n' % name)
    assert blk.startswith('(symbol "%s"\n' % name)
    blk = blk.replace('(symbol "%s"\n' % name, '(symbol "%s"\n' % libid, 1)
    # library top level is 1 tab, schematic lib_symbols is 2 -> add one tab
    return reindent(blk, 2, 1)

LIBS = []
for lid in ("Device:C", "Device:L", "Device:R", "power:GND"):
    LIBS.append(from_schematic(lid))
LIBS.append(from_library(os.path.join(STOCK, "power.kicad_sym"),
                         "PWR_FLAG", "power:PWR_FLAG"))
LIBS.append(from_library(os.path.join(STOCK, "Regulator_Switching.kicad_sym"),
                         "LM5164DDA", "Regulator_Switching:LM5164DDA"))
LIBS.sort(key=lambda b: re.search(r'\(symbol "([^"]+)"', b).group(1))

# ---------------------------------------------------------------- geometry
def pin(x, y, rot, px, py):
    if rot == 0:    return (round(x + px, 4), round(y - py, 4))
    if rot == 90:   return (round(x - py, 4), round(y - px, 4))
    if rot == 180:  return (round(x - px, 4), round(y + py, 4))
    if rot == 270:  return (round(x + py, 4), round(y + px, 4))
    raise ValueError(rot)

LM5164 = {1: (-2.54, -12.7), 2: (-12.7, 7.62), 3: (-12.7, 2.54), 4: (-12.7, -5.08),
          5: (12.7, -2.54), 6: (12.7, -5.08), 7: (12.7, 7.62), 8: (12.7, 2.54),
          9: (2.54, -12.7)}
TWOPIN = {1: (0, 3.81), 2: (0, -3.81)}          # C, R, L

SYMS, WIRES, JUNCS, LABELS, HLABELS, NOTES, NOCONN = [], [], [], [], [], [], []
PINMAP = {}   # ref -> {num: (x, y)}
GNDN = [0]

def place(ref, libid, val, x, y, rot=0, pins=None, fields=None, npins=1, desc="",
          dnp=False):
    SYMS.append(dict(ref=ref, libid=libid, val=val, x=x, y=y, rot=rot,
                     fields=fields or [], npins=npins, desc=desc, dnp=dnp))
    if pins:
        PINMAP[ref] = {n: pin(x, y, rot, *p) for n, p in pins.items()}
    return PINMAP.get(ref)

def vpart(ref, libid, val, x, ytop, rot=0, dnp=False):
    """Vertical 2-pin part: pin1 at ytop, pin2 at ytop+7.62."""
    cy = round(ytop + 3.81, 4)
    fields = [("Reference", ref, x + 1.651, cy - 1.27, 0),
              ("Value", val, x + 1.651, cy + 1.27, 0)]
    place(ref, libid, val, x, cy, rot, TWOPIN, fields, npins=2, dnp=dnp)
    return (x, ytop), (x, round(ytop + 7.62, 4))

def gnd(x, y):
    GNDN[0] += 1
    ref = "#PWR1%02d" % GNDN[0]
    fields = [("Reference", ref, x, y + 6.35, 0, True),
              ("Value", "GND", x, y + 3.81, 0, True)]
    SYMS.append(dict(ref=ref, libid="power:GND", val="GND", x=x, y=y, rot=0,
                     fields=fields, npins=1, desc='Power symbol creates a global label with name "GND" , ground',
                     power=True))
    return (x, y)

FLAGN = [0]
def pwrflag(x, y):
    """PWR_FLAG marks a net this board GENERATES, so ERC stops asking which
    output power pin drives it."""
    FLAGN[0] += 1
    ref = "#FLG1%02d" % FLAGN[0]
    fields = [("Reference", ref, x, y - 5.08, 0, True),
              ("Value", "PWR_FLAG", x, y - 2.54, 0, True)]
    SYMS.append(dict(ref=ref, libid="power:PWR_FLAG", val="PWR_FLAG", x=x, y=y, rot=0,
                     fields=fields, npins=1,
                     desc="Special symbol for telling ERC where power comes from",
                     power=True))
    return (x, y)

def nc(p):
    NOCONN.append(p)

def w(a, b):
    assert a != b, a
    WIRES.append((a, b))

def j(p):
    JUNCS.append(p)

def lab(name, x, y, rot=0):
    LABELS.append((name, x, y, rot))

def hlab(name, shape, x, y, rot=0):
    HLABELS.append((name, shape, x, y, rot))

# ================================================================ BLOCK 1
# U1 : 3.3 V always-on buck, VIN = VLOGIC_IN, EN tied to VIN
U1 = place("U1", "Regulator_Switching:LM5164DDA", "LM5164DDA", 76.2, 33.02, 0, LM5164,
           [("Reference", "U1", 66.04, 21.59, 0), ("Value", "LM5164DDA", 72.39, 21.59, 0)],
           npins=9, desc="1A synchronous buck converter with ultra-low IQ, 6V - 100V input, adjustable output voltage, HSOP-8")
hlab("VLOGIC_IN", "input", 35.56, 25.4, 180)
w((35.56, 25.4), (63.5, 25.4))                      # VIN rail
w((38.1, 25.4), (38.1, 17.78)); j((38.1, 25.4)); pwrflag(38.1, 17.78)
c1a, c1b = vpart("C6", "Device:C", "2.2uF", 43.18, 25.4); gnd(*c1b); j(c1a)
c2a, c2b = vpart("C7", "Device:C", "100nF", 50.8, 25.4); gnd(*c2b); j(c2a)
j((58.42, 25.4)); w((58.42, 25.4), (58.42, 30.48)); w((58.42, 30.48), (63.5, 30.48))  # EN = VIN
w((63.5, 38.1), (58.42, 38.1))                      # RON
r1a, r1b = vpart("R4", "Device:R", "20.5k", 58.42, 38.1); gnd(*r1b)
nc(U1[6])
w(U1[1], U1[9]); j((76.2, 45.72)); w((76.2, 45.72), (76.2, 48.26)); gnd(76.2, 48.26)
c3a, c3b = vpart("C8", "Device:C", "2.2nF", 96.52, 22.86)   # CBST 22.86 -> 30.48
w(U1[7], (93.98, 25.4)); w((93.98, 25.4), (93.98, 22.86)); w((93.98, 22.86), c3a)
w(U1[8], (96.52, 30.48)); j((96.52, 30.48)); w((96.52, 30.48), (104.14, 30.48))
lab("SW_3V3", 100.33, 30.48)
place("L4", "Device:L", "XAL7070-223ME", 107.95, 30.48, 90, TWOPIN,
      [("Reference", "L4", 109.22, 26.67, 90), ("Value", "XAL7070-223ME", 111.76, 34.29, 90)], npins=2)
w((111.76, 30.48), (160.02, 30.48))                 # +3V3_ALW rail
hlab("+3V3_ALW", "output", 160.02, 30.48, 0)
w((147.32, 30.48), (147.32, 22.86)); j((147.32, 30.48)); pwrflag(147.32, 22.86)
r2a, r2b = vpart("R5", "Device:R", "348k", 116.84, 30.48); j(r2a)
r3a, r3b = vpart("R6", "Device:R", "200k", 116.84, 38.1); gnd(*r3b); j(r3a)
c4a, c4b = vpart("C10", "Device:C", "22uF", 132.08, 30.48); gnd(*c4b); j(c4a)
c5a, c5b = vpart("C11", "Device:C", "22uF", 139.7, 30.48); gnd(*c5b); j(c5a)
w((116.84, 38.1), (91.44, 38.1)); w((91.44, 38.1), (91.44, 35.56)); w((91.44, 35.56), U1[5])
lab("FB_3V3", 105.41, 38.1)

# ================================================================ BLOCK 2
# U2 : 5 V buck gated by EN_5V, VIN = VBAT
U2 = place("U2", "Regulator_Switching:LM5164DDA", "LM5164DDA", 76.2, 78.74, 0, LM5164,
           [("Reference", "U2", 66.04, 67.31, 0), ("Value", "LM5164DDA", 72.39, 67.31, 0)],
           npins=9, desc="1A synchronous buck converter with ultra-low IQ, 6V - 100V input, adjustable output voltage, HSOP-8")
hlab("VBAT", "input", 63.5, 60.96, 90)
w((63.5, 60.96), (63.5, 71.12)); j((63.5, 63.5)); w((63.5, 63.5), (40.64, 63.5))
w((45.72, 63.5), (45.72, 55.88)); j((45.72, 63.5)); pwrflag(45.72, 55.88)
c7a, c7b = vpart("C12", "Device:C", "2.2uF", 48.26, 63.5); gnd(*c7b); j(c7a)
c8a, c8b = vpart("C13", "Device:C", "100nF", 40.64, 63.5); gnd(*c8b)
hlab("EN_5V", "input", 45.72, 76.2, 180)
w((45.72, 76.2), (63.5, 76.2))                      # EN
# Mandatory passive default (plan Global Constraints): floating = rail OFF.
j((53.34, 76.2)); w((53.34, 76.2), (53.34, 81.28))
r19a, r19b = vpart("R19", "Device:R", "100k", 53.34, 81.28); gnd(*r19b)
w((63.5, 83.82), (58.42, 83.82))
r4a, r4b = vpart("R7", "Device:R", "31.6k", 58.42, 83.82); gnd(*r4b)
nc(U2[6])
w(U2[1], U2[9]); j((76.2, 91.44)); w((76.2, 91.44), (76.2, 93.98)); gnd(76.2, 93.98)
c9a, c9b = vpart("C14", "Device:C", "2.2nF", 96.52, 68.58)
w(U2[7], (93.98, 71.12)); w((93.98, 71.12), (93.98, 68.58)); w((93.98, 68.58), c9a)
w(U2[8], (96.52, 76.2)); j((96.52, 76.2)); w((96.52, 76.2), (104.14, 76.2))
lab("SW_5V", 100.33, 76.2)
place("L5", "Device:L", "XAL7070-223ME", 107.95, 76.2, 90, TWOPIN,
      [("Reference", "L5", 109.22, 72.39, 90), ("Value", "XAL7070-223ME", 111.76, 80.01, 90)], npins=2)
w((111.76, 76.2), (160.02, 76.2))
hlab("+5V", "output", 160.02, 76.2, 0)
w((147.32, 76.2), (147.32, 68.58)); j((147.32, 76.2)); pwrflag(147.32, 68.58)
r5a, r5b = vpart("R8", "Device:R", "634k", 116.84, 76.2); j(r5a)
r6a, r6b = vpart("R9", "Device:R", "200k", 116.84, 83.82); gnd(*r6b); j(r6a)
c10a, c10b = vpart("C16", "Device:C", "22uF", 132.08, 76.2); gnd(*c10b); j(c10a)
c11a, c11b = vpart("C17", "Device:C", "100nF", 139.7, 76.2); gnd(*c11b); j(c11a)
w((116.84, 83.82), (91.44, 83.82)); w((91.44, 83.82), (91.44, 81.28)); w((91.44, 81.28), U2[5])
lab("FB_5V", 105.41, 83.82)

# ================================================================ BLOCK 5
# Type-3 ripple injection for both LM5164 rails (datasheet 7.2.2.6).
# Connected entirely by label so it stays clear of the dense power blocks.
#   RA from SW, CA to VOUT, CB couples the ramp into FB.
#   CA    >= 10 / (fSW x RFB1||RFB2)
#   RA.CA >= tON(nom) x (VIN(nom) - VOUT) / 20 mV
def type3(x, tag, swnet, fbnet, outnet, ra, rr, ca, cc, cb, cbv):
    y0 = 195.58
    w((x, y0 - 5.08), (x, y0)); lab(swnet, x, y0 - 5.08)
    vpart(ra, "Device:R", rr, x, y0)
    node = (x, y0 + 7.62)
    vpart(ca, "Device:C", cc, x, node[1])
    w((x, node[1] + 7.62), (x + 15.24, node[1] + 7.62))
    lab(outnet, x + 15.24, node[1] + 7.62)
    j(node); w(node, (x + 15.24, node[1]))
    vpart(cb, "Device:C", cbv, x + 15.24, y0)
    w((x + 15.24, y0), (x + 15.24, y0 - 5.08)); lab(fbnet, x + 15.24, y0 - 5.08)

# 3.3 V: RFB1||RFB2 = 127 k, fSW = 402 kHz -> CA >= 196 pF, use 2.2 nF
#        tON = 714 ns at 11.5 V in -> RA >= 133 k.  CB = 75 us / (3 x RFB1) = 72 pF
type3(50.8, "3V3", "SW_3V3", "FB_3V3", "+3V3_ALW", "R17", "133k", "C28", "2.2nF", "C9", "68pF")
# 5 V:   RFB1||RFB2 = 152 k, fSW = 396 kHz -> CA >= 166 pF, use 2.2 nF
#        tON = 1010 ns at 12.5 V in -> RA >= 172 k.  CB = 75 us / (3 x RFB1) = 39 pF
type3(101.6, "5V", "SW_5V", "FB_5V", "+5V", "R18", "174k", "C29", "2.2nF", "C15", "39pF")

# GND is a global net whose only source is the connector return, so it needs a flag too.
w((30.48, 185.42), (30.48, 190.5)); pwrflag(30.48, 185.42); gnd(30.48, 190.5)

# ================================================================ NOTES
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes as _notes
_notes.build(NOTES)
NOTEW = _notes.NOTEW

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
A('\t\t(title "rails")')
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
    assert "\n" not in esc
    A('\t(text_box "%s"' % esc)
    A("\t\t(exclude_from_sim no)")
    A("\t\t(at 300.0 %s 0)" % fs(ny))
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
assert ny < 280.0, "notes overflow into the title block: %s" % ny

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
    A("		(in_bom %s)" % ("yes" if fpmap.in_bom(s["ref"]) else "no"))
    A("\t\t(on_board yes)")
    A("\t\t(in_pos_files yes)")
    A("\t\t(dnp %s)" % ("yes" if s.get("dnp") else "no"))
    A('\t\t(uuid "%s")' % U("s" + s["ref"]))
    props = list(s["fields"])
    have = {p[0] for p in props}
    if "Reference" not in have:
        props.insert(0, ("Reference", s["ref"], s["x"], s["y"] - 2.54, 0))
    if "Value" not in have:
        props.insert(1, ("Value", s["val"], s["x"], s["y"] + 2.54, 0))
    for extra in ("Footprint", "Datasheet", "Description"):
        _v = fpmap.fp(s["ref"]) if extra == "Footprint" else (
            s.get(extra.lower(), "") or ("" if extra != "Description" else s["desc"]))
        props.append((extra, _v, s["x"], s["y"], 0, True))
    for p in props:
        nm, val, px, py, pa = p[:5]
        hide = len(p) > 5 and p[5]
        if nm in ("Footprint", "Datasheet") or (nm == "Description"):
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
    for n in range(1, s["npins"] + 1):
        A('\t\t(pin "%d"' % n)
        A('\t\t\t(uuid "%s")' % U("p%s.%d" % (s["ref"], n)))
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
import kicanon
_text = kicanon.canonicalise("\n".join(out) + "\n")
open(os.path.join(HW, "sheets", "rails.kicad_sch"), "w",
     encoding="utf-8", newline="\n").write(_text)
print("symbols:", len(SYMS), " wires:", len(WIRES), " junctions:", len(set(JUNCS)),
      " labels:", len(LABELS), " hlabels:", len(HLABELS), " notes end y:", ny)
