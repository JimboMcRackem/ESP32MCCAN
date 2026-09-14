#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/mccan.kicad_sch, the root sheet.

Every hierarchical label inside a child sheet needs a matching pin on the parent's
sheet symbol, or KiCad reports hier_label_mismatch and the nets never join.

Sheet pins are connected by a stub and a root-level LABEL rather than by wires drawn
between the boxes.  With ~40 inter-sheet nets, wiring the boxes directly produces a
rat's nest that is unreadable and unmaintainable; labels at the root sheet scope join
by name exactly the same way.

The four sheet UUIDs are FIXED here: every symbol instance inside a child sheet
carries the parent path, so changing one orphans every reference designator on that
sheet.
"""
import os, uuid

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
def U(key):
    return str(uuid.uuid5(NS, "root:" + key))

ROOT_UUID = "7410bb74-5653-4f1b-8c7c-ce17eb633f20"
UUIDS = {
    "outputs":     "4008c412-efce-41fb-837c-ba7220a4d335",
    "rails":       "4a66277e-62b8-454b-8781-170494cf9f57",
    "mcu_can":     "5a511665-9b85-4ced-b6e3-f23e247294e2",
    "power_input": "bb7f7a86-b153-4a57-9167-66f1a7c26371",
}

# name -> (x, y, w, h)
BOX = {
    "power_input": (40.64,  40.64,  60.96, 45.72),
    "rails":       (165.1, 40.64,  60.96, 66.04),
    "mcu_can":     (40.64, 132.08, 60.96, 68.58),
    "outputs":     (165.1, 132.08, 60.96, 78.74),
}

# name -> list of (pin, kind, edge)   edge in {"L", "R"}
PINS = {
    "power_input": [
        ("VBAT",      "output", "R"),
        ("VLOGIC_IN", "output", "R"),
    ],
    "rails": [
        ("VBAT",      "input",  "L"),
        ("VLOGIC_IN", "input",  "L"),
        ("EN_3V3SW",  "input",  "L"),
        ("EN_BOOST",  "input",  "L"),
        ("+3V3_ALW",  "output", "R"),
        ("+3V3_SW",   "output", "R"),
        ("+5V",       "output", "R"),
        ("+24V",      "output", "R"),
    ],
    "mcu_can": [
        ("+3V3_ALW",  "input",         "L"),
        ("+5V",       "input",         "L"),
        ("RGB_ISNS",  "input",         "L"),
        ("ISNS_DEN",  "input",         "L"),
        ("IGN_IN",    "input",         "L"),
        ("EN_BOOST",  "output",        "L"),
        ("EN_3V3SW",  "output",        "L"),
        ("I2C_SDA",   "bidirectional", "R"),
        ("I2C_SCL",   "bidirectional", "R"),
        ("MUX_S0",    "output",        "R"),
        ("MUX_S1",    "output",        "R"),
        ("MUX_S2",    "output",        "R"),
        ("MUX_S3",    "output",        "R"),
        ("PWM_DEN_A", "output",        "R"),
        ("PWM_DEN_B", "output",        "R"),
        ("DEN_DSEL",  "output",        "R"),
        ("EN_DIAG",   "output",        "R"),
        ("CANH",      "bidirectional", "R"),
        ("CANL",      "bidirectional", "R"),
    ],
    "outputs": [],          # Task 6
}

GRID = 1.27
STUB = 8.89

def ongrid(v):
    assert abs(v / GRID - round(v / GRID)) < 1e-6, "%s is off the 1.27 mm grid" % v
    return v
WIRES, LABELS = [], []

def fs(v):
    t = ("%.4f" % v).rstrip("0").rstrip(".")
    return t if t not in ("", "-0") else "0"

def sheet(name):
    x, y, wd, ht = (ongrid(v) for v in BOX[name])
    rows = PINS[name]
    left = [p for p in rows if p[2] == "L"]
    right = [p for p in rows if p[2] == "R"]
    out = []
    A = out.append
    A("\t(sheet")
    A("\t\t(at %s %s)" % (fs(x), fs(y)))
    A("\t\t(size %s %s)" % (fs(wd), fs(ht)))
    A("\t\t(exclude_from_sim no)")
    A("\t\t(in_bom yes)")
    A("\t\t(on_board yes)")
    A("\t\t(dnp no)")
    A("\t\t(stroke")
    A("\t\t\t(width 0.1524)")
    A("\t\t\t(type solid)")
    A("\t\t)")
    A("\t\t(fill")
    A("\t\t\t(color 0 0 0 0)")
    A("\t\t)")
    A('\t\t(uuid "%s")' % UUIDS[name])
    for prop, val, dy, just in (("Sheetname", name, -0.7968, "bottom"),
                                ("Sheetfile", "sheets/%s.kicad_sch" % name, ht + 0.981, "top")):
        A('\t\t(property "%s" "%s"' % (prop, val))
        A("\t\t\t(at %s %s 0)" % (fs(x), fs(y + dy)))
        A("\t\t\t(show_name no)")
        A("\t\t\t(do_not_autoplace no)")
        A("\t\t\t(effects")
        A("\t\t\t\t(font")
        A("\t\t\t\t\t(size 1.27 1.27)")
        A("\t\t\t\t)")
        A("\t\t\t\t(justify left %s)" % just)
        A("\t\t\t)")
        A("\t\t)")
    for side, rows2 in (("L", left), ("R", right)):
        px = x if side == "L" else x + wd
        ang = 180 if side == "L" else 0
        for i, (pn, kind, _) in enumerate(rows2):
            py = ongrid(round(y + 7.62 + i * 3.81, 4))
            assert py < y + ht, "%s: pin %s falls outside the box" % (name, pn)
            A('\t\t(pin "%s" %s' % (pn, kind))
            A("\t\t\t(at %s %s %d)" % (fs(px), fs(py), ang))
            A('\t\t\t(uuid "%s")' % U("%s/%s" % (name, pn)))
            A("\t\t\t(effects")
            A("\t\t\t\t(font")
            A("\t\t\t\t\t(size 1.27 1.27)")
            A("\t\t\t\t)")
            A("\t\t\t\t(justify %s)" % ("right" if side == "L" else "left"))
            A("\t\t\t)")
            A("\t\t)")
            ex = round(px - STUB, 4) if side == "L" else round(px + STUB, 4)
            WIRES.append(((px, py), (ex, py)))
            LABELS.append((pn, ex, py, 180 if side == "L" else 0))
    A("\t)")
    return "\n".join(out)

out = []
A = out.append
A("(kicad_sch")
A("\t(version 20260306)")
A('\t(generator "eeschema")')
A('\t(generator_version "10.0")')
A('\t(uuid "%s")' % ROOT_UUID)
A('\t(paper "A3")')
A("\t(title_block")
A('\t\t(title "MCCAN Root")')
A('\t\t(comment 1 "Net naming contract: see hardware/README.md")')
A('\t\t(comment 2 "Sheet pins are joined by root-level labels, not by wires between boxes")')
A("\t)")
A("\t(lib_symbols)")

blocks = [sheet(n) for n in ("power_input", "rails", "mcu_can", "outputs")]

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

for nm, x, y, rot in LABELS:
    A('\t(label "%s"' % nm)
    A("\t\t(at %s %s %d)" % (fs(x), fs(y), rot))
    A("\t\t(effects")
    A("\t\t\t(font")
    A("\t\t\t\t(size 1.27 1.27)")
    A("\t\t\t)")
    A("\t\t\t(justify %s bottom)" % ("right" if rot == 180 else "left"))
    A("\t\t)")
    A('\t\t(uuid "%s")' % U("l%s%s%s" % (nm, x, y)))
    A("\t)")

for b in blocks:
    A(b)

A("\t(sheet_instances")
A('\t\t(path "/"')
A('\t\t\t(page "1")')
A("\t\t)")
A("\t)")
A("\t(embedded_fonts no)")
A(")")

open(os.path.join(HW, "mccan.kicad_sch"), "w", encoding="utf-8", newline="\n").write(
    "\n".join(out) + "\n")
print("sheets: 4  pins:", sum(len(v) for v in PINS.values()),
      " wires:", len(WIRES), " labels:", len(LABELS))
