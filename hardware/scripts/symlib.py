# -*- coding: utf-8 -*-
"""Fix LM51571-Q1 pin electrical types and add the DML3017LDC smart load switch."""
import io, re

LIB = r"D:\Projects\ESP32MCCAN\hardware\symbols\mccan_parts.kicad_sym"
s = io.open(LIB, encoding="utf-8").read()

# ---------------------------------------------------------------- 1. pin types
# Datasheet SNVSBK8B Table 7-1 types, mapped to KiCad electrical types so that
# ERC stops inventing violations that do not exist in the circuit.
NEWTYPE = {
    "2":  "power_out",     # VCC is the OUTPUT of the internal LDO, not a supply input
    # BIAS is the supply input to that LDO, but R16 sits between it and VBAT, so as
    # far as ERC is concerned the pin lives on an isolated passive net.
    "3":  "passive",
    "4":  "open_collector",# PGOOD
    "5":  "passive",       # RT  - resistor to AGND
    "8":  "passive",       # COMP - compensation network
    "10": "passive",       # SS  - capacitor
    "11": "passive",       # MODE - resistor to AGND
    "12": "passive",       # SW x3 are one internal node; 'power_in' was wrong and
    "13": "passive",       # made ERC demand a driver for the converter's own
    "14": "passive",       # switch node
    "15": "no_connect",    # NC
    "17": "passive",       # EP thermal pad
}

def balanced_end(text, at):
    """Index just past the s-expression whose first '(' is at or after `at`."""
    depth, j = 0, text.index("(", at)
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
                return j + 1
        j += 1

# Bound the scan to the LM51571 symbol.  The DML3017LDC further down the file reuses
# the same pin numbers, so an unbounded scan retypes its pins as well.
start = s.index('(symbol "LM51571QRTERQ1_0_1"')
stop = balanced_end(s, s.index('\t(symbol "LM51571QRTERQ1"'))

def fix(m):
    body = m.group(0)
    num = re.search(r'\(number "(\d+)"', body)
    if num and num.group(1) in NEWTYPE:
        return re.sub(r'\(pin \w+ line', '(pin %s line' % NEWTYPE[num.group(1)], body, count=1)
    return body

PIN_RE = re.compile(r'\(pin \w+ line\n(?:\t+\(.*\n|\t+\).*\n|.*?\n)*?\t+\)\n(?=\t+\(pin |\t+\)\n)')
head, tail, rest = s[:start], s[start:stop], s[stop:]
n = [0]
def fix2(m):
    body = m.group(0)
    num = re.search(r'\(number "(\d+)"', body)
    if num and num.group(1) in NEWTYPE:
        n[0] += 1
        return re.sub(r'\(pin \w+ line', '(pin %s line' % NEWTYPE[num.group(1)], body, count=1)
    return body

# operate pin-block by pin-block using a simple scanner
out, i = [], 0
while True:
    k = tail.find("(pin ", i)
    if k < 0:
        out.append(tail[i:]); break
    out.append(tail[i:k])
    # find the matching close paren
    depth, j = 0, k
    while True:
        c = tail[j]
        if c == '"':
            j += 1
            while tail[j] != '"' or tail[j-1] == "\\":
                j += 1
        elif c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: break
        j += 1
    body = tail[k:j+1]
    num = re.search(r'\(number "(\d+)"', body)
    if num and num.group(1) in NEWTYPE:
        body = re.sub(r'\(pin \w+ line', '(pin %s line' % NEWTYPE[num.group(1)], body, count=1)
        n[0] += 1
    out.append(body)
    i = j + 1
s = head + "".join(out) + rest
print("LM51571 pin types changed:", n[0], "of", len(NEWTYPE))
assert n[0] == len(NEWTYPE)

# ---------------------------------------------------------------- 2. DML3017LDC
# Diodes DS46371 Rev. 1-2, October 2024.  Pin Description table, p.3:
#   1,13 VIN (pin 1 must connect to pin 13)   2 EN (active high, internal pulldown)
#   3 VCC (3.0-5.5 V)   4 GND   5 SR (slew rate)   6 PG (open drain)
#   7 BLEED (must tie to VOUT)   8-12 VOUT
PINS = [
    # num, name, type, x, y, angle
    ("1",  "VIN",   "power_in",       -12.7,  10.16,   0),
    ("13", "VIN",   "power_in",       -12.7,   7.62,   0),
    ("3",  "VCC",   "power_in",       -12.7,   2.54,   0),
    ("2",  "EN",    "input",          -12.7,  -2.54,   0),
    ("5",  "SR",    "passive",        -12.7,  -7.62,   0),
    ("12", "VOUT",  "passive",         12.7,  10.16, 180),
    ("11", "VOUT",  "passive",         12.7,   7.62, 180),
    ("10", "VOUT",  "passive",         12.7,   5.08, 180),
    ("9",  "VOUT",  "passive",         12.7,   2.54, 180),
    ("8",  "VOUT",  "passive",         12.7,   0.0,  180),
    ("7",  "BLEED", "passive",         12.7,  -5.08, 180),
    ("6",  "PG",    "passive",         12.7, -10.16, 180),
    ("4",  "GND",   "power_in",         0.0, -15.24,  90),
]

def num(v):
    t = ("%.4f" % v).rstrip("0").rstrip(".")
    return t if t not in ("", "-0") else "0"

L = []
A = L.append
A('\t(symbol "DML3017LDC"')
A('\t\t(pin_names')
A('\t\t\t(offset 0.254)')
A('\t\t)')
A('\t\t(exclude_from_sim no)')
A('\t\t(in_bom yes)')
A('\t\t(on_board yes)')
A('\t\t(in_pos_files yes)')
A('\t\t(duplicate_pin_numbers_are_jumpers no)')
for name, val, hide in (("Reference", "U", False), ("Value", "DML3017LDC", False),
                        ("Footprint", "", True),
                        ("Datasheet", "https://www.diodes.com/assets/Datasheets/DML3017LDC.pdf", True),
                        ("Description", "Single-channel smart load switch, 0.5-20 V in, active-high EN with internal pulldown, soft-start, short-circuit and thermal protection, power-good, V-DFN3030-12", True)):
    A('\t\t(property "%s" "%s"' % (name, val))
    A('\t\t\t(at 0 %s 0)' % ("17.78" if name == "Reference" else "15.24" if name == "Value" else "0"))
    A('\t\t\t(show_name no)')
    A('\t\t\t(do_not_autoplace no)')
    if hide:
        A('\t\t\t(hide yes)')
    A('\t\t\t(effects')
    A('\t\t\t\t(font')
    A('\t\t\t\t\t(size 1.27 1.27)')
    if hide:
        A('\t\t\t\t\t(italic yes)')
    A('\t\t\t\t)')
    A('\t\t\t)')
    A('\t\t)')
A('\t\t(symbol "DML3017LDC_0_1"')
A('\t\t\t(rectangle')
A('\t\t\t\t(start -10.16 12.7)')
A('\t\t\t\t(end 10.16 -12.7)')
A('\t\t\t\t(stroke')
A('\t\t\t\t\t(width 0.254)')
A('\t\t\t\t\t(type default)')
A('\t\t\t\t)')
A('\t\t\t\t(fill')
A('\t\t\t\t\t(type background)')
A('\t\t\t\t)')
A('\t\t\t)')
for pnum, pname, ptype, x, y, ang in PINS:
    A('\t\t\t(pin %s line' % ptype)
    A('\t\t\t\t(at %s %s %d)' % (num(x), num(y), ang))
    A('\t\t\t\t(length 2.54)')
    A('\t\t\t\t(name "%s"' % pname)
    A('\t\t\t\t\t(effects')
    A('\t\t\t\t\t\t(font')
    A('\t\t\t\t\t\t\t(size 1.27 1.27)')
    A('\t\t\t\t\t\t)')
    A('\t\t\t\t\t)')
    A('\t\t\t\t)')
    A('\t\t\t\t(number "%s"' % pnum)
    A('\t\t\t\t\t(effects')
    A('\t\t\t\t\t\t(font')
    A('\t\t\t\t\t\t\t(size 1.27 1.27)')
    A('\t\t\t\t\t\t)')
    A('\t\t\t\t\t)')
    A('\t\t\t\t)')
    A('\t\t\t)')
A('\t\t)')
A('\t)')
NEW = "\n".join(L) + "\n"

if '(symbol "DML3017LDC"' in s:
    a = s.index('\t(symbol "DML3017LDC"')
    # find its balanced end
    depth, j = 0, s.index("(", a)
    while True:
        c = s[j]
        if c == '"':
            j += 1
            while s[j] != '"' or s[j-1] == "\\":
                j += 1
        elif c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: break
        j += 1
    s = s[:a] + NEW.rstrip("\n") + s[j+1:]
    print("DML3017LDC symbol replaced")
else:
    k = s.rstrip().rfind(")")
    s = s[:k] + NEW + ")\n"
    print("DML3017LDC symbol appended")

io.open(LIB, "w", encoding="utf-8", newline="\n").write(s)
print("written")

STOCKFET = r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Transistor_FET.kicad_sym"


def extract_graphics(path, symname):
    """Return the graphic children of <symname>_0_1, at 2-tab indentation."""
    src = io.open(path, encoding="utf-8").read()
    i = src.index('(symbol "%s_0_1"' % symname)
    end = balanced_end(src, i)
    blk = src[src.index("(", i):end]
    lines = blk.split("\n")[1:-1]          # drop the wrapper and its closing paren
    out = []
    for ln in lines:
        stripped = ln.lstrip("\t")
        depth = len(ln) - len(stripped)
        out.append("\t" * (depth - 2 + 2) + stripped)
    return "\n".join(out)



# ================================================================ generic builder
def emit(name, value, desc, datasheet, units, rect=None, graphics_from=None):
    """units: {unit_no: [(number, pinname, type, x, y, angle), ...]}"""
    L = []
    A = L.append
    A('\t(symbol "%s"' % name)
    A('\t\t(pin_names')
    A('\t\t\t(offset 0.254)')
    A('\t\t)')
    A('\t\t(exclude_from_sim no)')
    A('\t\t(in_bom yes)')
    A('\t\t(on_board yes)')
    A('\t\t(in_pos_files yes)')
    A('\t\t(duplicate_pin_numbers_are_jumpers no)')
    for pname, pval, hide in (("Reference", "U", False), ("Value", value, False),
                              ("Footprint", "", True), ("Datasheet", datasheet, True),
                              ("Description", desc, True)):
        A('\t\t(property "%s" "%s"' % (pname, pval))
        A('\t\t\t(at 0 %s 0)' % ("2.54" if pname == "Reference" else "0"))
        A('\t\t\t(show_name no)')
        A('\t\t\t(do_not_autoplace no)')
        if hide:
            A('\t\t\t(hide yes)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        if hide:
            A('\t\t\t\t\t(italic yes)')
        A('\t\t\t\t)')
        A('\t\t\t)')
        A('\t\t)')
    for unit, pinlist in sorted(units.items()):
        A('\t\t(symbol "%s_%d_1"' % (name.split(":")[-1], unit))
        if graphics_from:
            for ln in graphics_from.split("\n"):
                A("\t" + ln if ln.strip() else ln)
        elif rect:
            x0, y0, x1, y1 = rect
            A('\t\t\t(rectangle')
            A('\t\t\t\t(start %s %s)' % (x0, y0))
            A('\t\t\t\t(end %s %s)' % (x1, y1))
            A('\t\t\t\t(stroke')
            A('\t\t\t\t\t(width 0.254)')
            A('\t\t\t\t\t(type default)')
            A('\t\t\t\t)')
            A('\t\t\t\t(fill')
            A('\t\t\t\t\t(type background)')
            A('\t\t\t\t)')
            A('\t\t\t)')
        for pnum, pname, ptype, px, py, ang in pinlist:
            A('\t\t\t(pin %s line' % ptype)
            A('\t\t\t\t(at %s %s %d)' % (fs_(px), fs_(py), ang))
            A('\t\t\t\t(length 2.54)')
            A('\t\t\t\t(name "%s"' % pname)
            A('\t\t\t\t\t(effects')
            A('\t\t\t\t\t\t(font')
            A('\t\t\t\t\t\t\t(size 1.27 1.27)')
            A('\t\t\t\t\t\t)')
            A('\t\t\t\t\t)')
            A('\t\t\t\t)')
            A('\t\t\t\t(number "%s"' % pnum)
            A('\t\t\t\t\t(effects')
            A('\t\t\t\t\t\t(font')
            A('\t\t\t\t\t\t\t(size 1.27 1.27)')
            A('\t\t\t\t\t\t)')
            A('\t\t\t\t\t)')
            A('\t\t\t\t)')
            A('\t\t\t)')
        A('\t\t)')
    A('\t)')
    return "\n".join(L) + "\n"


def fs_(v):
    t = ("%.4f" % v).rstrip("0").rstrip(".")
    return t if t not in ("", "-0") else "0"


def install(lib_text, name, block):
    if '(symbol "%s"' % name in lib_text:
        a = lib_text.index('\t(symbol "%s"' % name)
        b = balanced_end(lib_text, a)
        return lib_text[:a] + block.rstrip("\n") + lib_text[b:], "replaced"
    k = lib_text.rstrip().rfind(")")
    return lib_text[:k] + block + ")\n", "appended"


# ---------------------------------------------------------------- ADG706
# ADG706_707.pdf, PIN CONFIGURATIONS (TSSOP-28):
#   1 VDD  2 NC  3 NC  4 S16  5 S15  6 S14  7 S13  8 S12  9 S11  10 S10  11 S9
#   12 GND  13 NC  14 A3  15 A2  16 A1  17 A0  18 EN  19 S1  20 S2  21 S3  22 S4
#   23 S5  24 S6  25 S7  26 S8  27 VSS  28 D
_S_NUM = {1: "19", 2: "20", 3: "21", 4: "22", 5: "23", 6: "24", 7: "25", 8: "26",
          9: "11", 10: "10", 11: "9", 12: "8", 13: "7", 14: "6", 15: "5", 16: "4"}
_adg = []
for _i in range(1, 17):
    _adg.append((_S_NUM[_i], "S%d" % _i, "passive", -15.24, 17.78 - (_i - 1) * 2.54, 0))
_adg += [
    ("28", "D",   "passive",    15.24,  17.78, 180),
    ("18", "EN",  "input",      15.24,   7.62, 180),
    ("17", "A0",  "input",      15.24,   2.54, 180),
    ("16", "A1",  "input",      15.24,   0.0,  180),
    ("15", "A2",  "input",      15.24,  -2.54, 180),
    ("14", "A3",  "input",      15.24,  -5.08, 180),
    ("2",  "NC",  "no_connect", 15.24, -12.7,  180),
    ("3",  "NC",  "no_connect", 15.24, -15.24, 180),
    ("13", "NC",  "no_connect", 15.24, -17.78, 180),
    ("1",  "VDD", "power_in",    0.0,   25.4,  270),
    ("12", "GND", "power_in",   -5.08, -27.94,  90),
    ("27", "VSS", "power_in",    5.08, -27.94,  90),
]
LIBTXT = io.open(LIB, encoding="utf-8").read()
blk = emit("ADG706", "ADG706",
           "16-to-1 analog multiplexer, 1.8 V to 5.5 V single supply, 2.5 ohm on-resistance, TSSOP-28",
           "https://www.analog.com/media/en/technical-documentation/data-sheets/ADG706_707.pdf",
           {1: _adg}, rect=(-12.7, 22.86, 12.7, -25.4))
LIBTXT, how = install(LIBTXT, "ADG706", blk)
print("ADG706", how)

# ---------------------------------------------------------------- NX5020UNBKS
# NX5020UNBKS.pdf Table 2: 1 S1, 2 G1, 3 D2, 4 S2, 5 G2, 6 D1.
# Two units so each RGB channel draws as one FET; 6 packages cover 12 channels.
_g = extract_graphics(STOCKFET, "Q_NMOS_GSD")
_u1 = [("2", "G1", "input", -5.08, 0.0, 0),
       ("1", "S1", "passive", 2.54, -5.08, 90),
       ("6", "D1", "passive", 2.54, 5.08, 270)]
_u2 = [("5", "G2", "input", -5.08, 0.0, 0),
       ("4", "S2", "passive", 2.54, -5.08, 90),
       ("3", "D2", "passive", 2.54, 5.08, 270)]
blk = emit("NX5020UNBKS", "NX5020UNBKS",
           "50 V dual N-channel Trench MOSFET, Rds(on) specified at Vgs = 2.5 V, SOT363",
           "https://assets.nexperia.com/documents/data-sheet/NX5020UNBKS.pdf",
           {1: _u1, 2: _u2}, graphics_from=_g)
LIBTXT, how = install(LIBTXT, "NX5020UNBKS", blk)
print("NX5020UNBKS", how)

# ---------------------------------------------------------------- BTS7008-2EPA
# !! PIN NUMBERS ARE PLACEHOLDERS !!  No Infineon datasheet is held locally.  The pin
# NAMES come from part-selection.md's verified notes (one multiplexed IS output plus a
# DSEL select line); the NUMBERS are invented and must be replaced from Infineon
# BTS7008-2EPA Rev. 1.21 before a footprint is assigned in Task 8.  The package is
# PG-TSDSO-14, so five further pins exist that are not modelled here.
_bts = [
    ("1", "IN0",  "input",    -12.7,   7.62, 0),
    ("2", "IN1",  "input",    -12.7,   5.08, 0),
    ("3", "DEN",  "input",    -12.7,   0.0,  0),
    ("4", "DSEL", "input",    -12.7,  -2.54, 0),
    ("5", "OUT0", "passive",   12.7,   7.62, 180),
    ("6", "OUT1", "passive",   12.7,   5.08, 180),
    ("7", "IS",   "passive",   12.7,  -5.08, 180),
    ("8", "VS",   "power_in",   0.0,  17.78, 270),
    ("9", "GND",  "power_in",   0.0, -17.78, 90),
]
blk = emit("BTS7008_2EPA", "BTS7008-2EPA",
           "Dual smart high-side switch, one multiplexed IS output with DSEL select, PG-TSDSO-14. "
           "PIN NUMBERS ARE PLACEHOLDERS - verify against Infineon Rev. 1.21 before Task 8.",
           "https://www.infineon.com/BTS7008-2EPA",
           {1: _bts}, rect=(-10.16, 15.24, 10.16, -15.24))
LIBTXT, how = install(LIBTXT, "BTS7008_2EPA", blk)
print("BTS7008_2EPA", how, "(PIN NUMBERS ARE PLACEHOLDERS)")

io.open(LIB, "w", encoding="utf-8", newline="\n").write(LIBTXT)
print("written")
