# -*- coding: utf-8 -*-
"""Give the rails sheet symbol its pins and wire power_input across to it.

Every hierarchical label inside a child sheet needs a matching pin on the parent's
sheet symbol, otherwise KiCad reports hier_label_mismatch and the nets never join.
"""
import io, re, uuid

ROOT = r"D:\Projects\ESP32MCCAN\hardware\mccan.kicad_sch"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
def U(key):
    return str(uuid.uuid5(NS, "root:" + key))

s = io.open(ROOT, encoding="utf-8").read()

def fs(v):
    t = ("%.4f" % v).rstrip("0").rstrip(".")
    return t if t not in ("", "-0") else "0"

def sheetpin(name, kind, x, y, ang):
    just = "right" if ang == 0 else "left"
    return ("\t\t(pin \"%s\" %s\n"
            "\t\t\t(at %s %s %d)\n"
            "\t\t\t(uuid \"%s\")\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "\t\t\t\t(justify %s)\n"
            "\t\t\t)\n"
            "\t\t)\n") % (name, kind, fs(x), fs(y), ang, U("p" + name), just)

# ---------------------------------------------------------------- rails sheet box
# 25.4 mm square cannot carry eight pins on a 2.54 mm pitch; 44.45 square can, and
# still clears the outputs sheet which starts at y = 101.6.
RX, RY, RW, RH = 101.6, 50.8, 44.45, 44.45
s = s.replace('\t\t(at 101.6 50.8)\n\t\t(size 25.4 25.4)',
              '\t\t(at %s %s)\n\t\t(size %s %s)' % (fs(RX), fs(RY), fs(RW), fs(RH)), 1)

RAILS_PINS = [
    ("VBAT",       "input",  RX,      60.96, 180),
    ("VLOGIC_IN",  "input",  RX,      66.04, 180),
    ("EN_3V3SW",   "input",  RX,      71.12, 180),
    ("EN_BOOST",   "input",  RX,      76.2,  180),
    ("+3V3_ALW",   "output", RX + RW, 60.96, 0),
    ("+3V3_SW",    "output", RX + RW, 66.04, 0),
    ("+5V",        "output", RX + RW, 71.12, 0),
    ("+24V",       "output", RX + RW, 76.2,  0),
]

# insert the pins just before the rails sheet's closing paren
i = s.index('(property "Sheetfile" "sheets/rails.kicad_sch"')
j = s.index("\n\t)\n", i)
s = s[:j + 1] + "".join(sheetpin(*p) for p in RAILS_PINS) + s[j + 1:]
print("rails sheet pins added:", len(RAILS_PINS))

# ---------------------------------------------------------------- power_input pins
# Move them from the auto-placed top-left corner to the right edge, facing rails.
PI_X = 50.8 + 25.4
block = s[s.index('(property "Sheetfile" "sheets/power_input.kicad_sch"'):]
for name, y in (("VLOGIC_IN", 66.04), ("VBAT", 60.96)):
    pat = re.compile(r'(\(pin "%s" output\n\t\t\t\(at )[-\d.]+ [-\d.]+ \d+(\))' % re.escape(name))
    new, n = pat.subn(lambda m: m.group(1) + "%s %s 0" % (fs(PI_X), fs(y)) + m.group(2), s)
    assert n == 1, (name, n)
    s = new
    # and flip the justification to match a right-edge pin
print("power_input pins repositioned")
s = s.replace('\t\t\t\t(justify right)\n', '\t\t\t\t(justify left)\n')

# ---------------------------------------------------------------- wires
WIRES = [((PI_X, 60.96), (RX, 60.96)),      # VBAT
         ((PI_X, 66.04), (RX, 66.04))]      # VLOGIC_IN
out = []
for a, b in WIRES:
    out.append("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
               "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
               "\t\t(uuid \"%s\")\n\t)\n"
               % (fs(a[0]), fs(a[1]), fs(b[0]), fs(b[1]),
                  U("w%s,%s-%s,%s" % (a[0], a[1], b[0], b[1]))))
k = s.index("\t(sheet\n")
s = s[:k] + "".join(out) + s[k:]
print("wires added:", len(WIRES))

io.open(ROOT, "w", encoding="utf-8", newline="\n").write(s)
print("written")
