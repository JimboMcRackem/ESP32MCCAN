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
