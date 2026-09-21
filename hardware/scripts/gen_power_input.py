#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate hardware/sheets/power_input.kicad_sch.

Repaired 2026-09-15.  This generator had drifted out of step with the committed
sheet, which had been saved from the KiCad GUI: it was missing four cosmetic
fields and did not match the GUI's element ordering.  Fixed, it now reproduces
the pre-J1 committed sheet BYTE FOR BYTE, which is what proves it faithful.
See kicanon.py for the ordering rules.
"""
import os, sys, uuid, math
import fpmap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = HERE
OUT = os.path.join(HERE, "..", "sheets", "power_input.kicad_sch")

SHEET_UUID = "998d692e-4a37-4d1c-95bc-f35ab32eee34"
ROOT_UUID = "7410bb74-5653-4f1b-8c7c-ce17eb633f20"
SHEET_INST_UUID = "bb7f7a86-b153-4a57-9167-66f1a7c26371"
INST_PATH = "/%s/%s" % (ROOT_UUID, SHEET_INST_UUID)
PROJECT = "mccan"

# deterministic uuids so re-runs produce stable files
_ns = uuid.UUID("11111111-2222-3333-4444-555555555555")
def U(tag):
    return str(uuid.uuid5(_ns, tag))

libsyms = open(os.path.join(HERE, "power_input_libsyms.txt"), encoding="utf-8").read()

# ---------------------------------------------------------------- pin geometry
# library pin coordinates (lib frame, Y-up), keyed by lib_id -> {number: (x, y)}
PINS = {
    "Connector:Conn_01x03_Pin": {"1": (5.08, 2.54), "2": (5.08, 0.0),
                             "3": (5.08, -2.54)},
    "Device:Fuse":              {"1": (0.0, 3.81), "2": (0.0, -3.81)},
    # Transistor_FET:Q_PMOS_GSD -- 1 = G, 2 = S, 3 = D (numeric, maps to real footprints)
    "Transistor_FET:Q_PMOS_GSD": {"1": (-5.08, 0.0), "2": (2.54, -5.08), "3": (2.54, 5.08)},
    "Device:R":                 {"1": (0.0, 3.81), "2": (0.0, -3.81)},
    # Transistor_FET:Q_NMOS_GSD -- 1 = G, 2 = S, 3 = D.  The eFuse pass pair Q10/Q11 is
    # COMMON DRAIN: pin 3 of both meets at MID, pin 2 of Q10 goes to FEED_P and pin 2 of
    # Q11 goes to R88.  Get this backwards and the reverse-polarity block disappears while
    # ERC, DRC and the pad count all still pass.  See spec section 4.2.
    "Transistor_FET:Q_NMOS_GSD": {"1": (-5.08, 0.0), "2": (2.54, -5.08), "3": (2.54, 5.08)},
    # Transistor_BJT:Q_NPN_BEC -- 1 = B, 2 = E, 3 = C
    "Transistor_BJT:Q_NPN_BEC": {"1": (-5.08, 0.0), "2": (2.54, -5.08), "3": (2.54, 5.08)},
    # Device:D and the three diode variants below: pin 1 = CATHODE, pin 2 = ANODE.
    "Device:D":                 {"1": (-3.81, 0.0), "2": (3.81, 0.0)},
    "Device:L":                 {"1": (0.0, 3.81), "2": (0.0, -3.81)},
    "Device:C":                 {"1": (0.0, 3.81), "2": (0.0, -3.81)},
    "Device:C_Polarized":       {"1": (0.0, 3.81), "2": (0.0, -3.81)},
    "Device:D_Zener":           {"1": (-3.81, 0.0), "2": (3.81, 0.0)},
    "Device:D_TVS":             {"1": (-3.81, 0.0), "2": (3.81, 0.0)},
    "Device:D_Schottky":        {"1": (-3.81, 0.0), "2": (3.81, 0.0)},
    # mccan_parts:CM_CHOKE_4T -- winding A = 1(left)-4(right), winding B = 2(left)-3(right),
    # matching the Wurth 7448031002 datasheet.  Device:L_Coupled numbers these 1-2/3-4 and
    # using it here shorted VBAT_PROT to GND through a winding.  See symlib.py.
    "mccan_parts:CM_CHOKE_4T":  {"1": (-5.08, 2.54), "4": (5.08, 2.54),
                                 "2": (-5.08, -2.54), "3": (5.08, -2.54)},
    # mccan_parts:LTC4380 -- MSOP-10, see symlib.py for the verified pin numbering.
    "mccan_parts:LTC4380":      {"1": (-7.62, 12.7),  "3": (-2.54, 12.7),
                                 "4": (2.54, 12.7),   "5": (7.62, 12.7),
                                 "2": (-15.24, 5.08), "9": (-15.24, -5.08),
                                 "7": (15.24, 5.08),  "8": (-7.62, -12.7),
                                 "10": (0.0, -12.7),  "6": (7.62, -12.7)},
    "power:GND":                {"1": (0.0, 0.0)},
}

def place(px, py, rot, lx, ly):
    """library coord -> sheet coord for a symbol placed at (px,py) with rotation rot."""
    if rot == 0:
        return (px + lx, py - ly)
    if rot == 90:
        return (px - ly, py - lx)
    if rot == 180:
        return (px - lx, py + ly)
    if rot == 270:
        return (px + ly, py + lx)
    raise ValueError(rot)

# ---------------------------------------------------------------- components
# (ref, lib_id, x, y, rot, value, footprint, value_offset)
import importlib.util as _ilu2
_sp2 = _ilu2.spec_from_file_location("layout", os.path.join(HERE, "layout_power_input.py"))
layout = _ilu2.module_from_spec(_sp2)
_sp2.loader.exec_module(layout)
COMPS = layout.COMPS
HORIZONTAL = layout.HORIZONTAL
GNDS = layout.GNDS
WIRES = layout.WIRES
JUNCTIONS = layout.JUNCTIONS
LABELS = layout.LABELS
HLABELS = layout.HLABELS
NOCONN = getattr(layout, "NOCONN", ())

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("notes", os.path.join(HERE, "notes_power_input.py"))
notes = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(notes)
TEXTBOXES = notes.TEXTBOXES
NOTE_FONT = notes.NOTE_FONT

# ---------------------------------------------------------------- emit
def f(v):
    s = "%.4f" % v
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"

L = []
def w(indent, s):
    L.append("\t" * indent + s)

w(0, "(kicad_sch")
w(1, "(version 20260306)")
w(1, '(generator "eeschema")')
w(1, '(generator_version "10.0")')
w(1, '(uuid "%s")' % SHEET_UUID)
# A3 since 2026-09-20: the LTC4380 eFuse block (section 4.2) needs the room below the
# rail that A4 does not have.  Mixed paper sizes are already normal on this project --
# outputs is A2, mcu_can and rails are A3.
w(1, '(paper "A3")')
w(1, "(title_block")
w(2, '(title "power_input")')
w(1, ")")
w(1, "(lib_symbols")
_blocks = []
for block in libsyms.split("\n(symbol "):
    block = block.strip("\n")
    if not block:
        continue
    if not block.startswith("(symbol "):
        block = "(symbol " + block
    _blocks.append(block)
# KiCad writes lib_symbols in name order
_blocks.sort(key=lambda b: b.split('"')[1])
for block in _blocks:
    block = block.strip("\n")
    if not block:
        continue
    if not block.startswith("(symbol "):
        block = "(symbol " + block
    # re-indent: first line at two tabs, keep inner relative indentation
    blines = block.split("\n")
    L.append("\t\t" + blines[0].strip())
    for bl in blines[1:]:
        L.append("\t" + bl)
w(1, ")")

# ---- text boxes
for (txt, x, y, sx, sy) in TEXTBOXES:
    esc = txt.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    w(1, '(text_box "%s"' % esc)
    w(2, "(exclude_from_sim no)")
    w(2, "(at %s %s 0)" % (f(x), f(y)))
    w(2, "(size %s %s)" % (f(sx), f(sy)))
    w(2, "(margins 0.9525 0.9525 0.9525 0.9525)")
    w(2, "(stroke")
    w(3, "(width 0)")
    w(3, "(type default)")
    w(2, ")")
    w(2, "(fill")
    w(3, "(type none)")
    w(2, ")")
    w(2, "(effects")
    w(3, "(font")
    w(4, "(size %s %s)" % (f(NOTE_FONT), f(NOTE_FONT)))
    w(3, ")")
    w(3, "(justify left top)")
    w(2, ")")
    w(2, '(uuid "%s")' % U("tb" + txt[:40]))
    w(1, ")")

# ---- no-connect flags
# These are not decoration: without them ERC reports every deliberately unused pin.
for (x, y) in NOCONN:
    w(1, "(no_connect")
    w(2, "(at %s %s)" % (f(x), f(y)))
    w(2, '(uuid "%s")' % U("nc%s%s" % (x, y)))
    w(1, ")")

# ---- junctions
for (x, y) in JUNCTIONS:
    w(1, "(junction")
    w(2, "(at %s %s)" % (f(x), f(y)))
    w(2, "(diameter 0)")
    w(2, "(color 0 0 0 0)")
    w(2, '(uuid "%s")' % U("junc%s%s" % (x, y)))
    w(1, ")")

# ---- wires
for (a, b) in WIRES:
    w(1, "(wire")
    w(2, "(pts")
    w(3, "(xy %s %s) (xy %s %s)" % (f(a[0]), f(a[1]), f(b[0]), f(b[1])))
    w(2, ")")
    w(2, "(stroke")
    w(3, "(width 0)")
    w(3, "(type default)")
    w(2, ")")
    w(2, '(uuid "%s")' % U("wire%s%s" % (a, b)))
    w(1, ")")

# ---- local labels
for (name, x, y, rot) in LABELS:
    w(1, '(label "%s"' % name)
    w(2, "(at %s %s %d)" % (f(x), f(y), rot))
    w(2, "(effects")
    w(3, "(font")
    w(4, "(size 1.27 1.27)")
    w(3, ")")
    w(3, "(justify left bottom)")
    w(2, ")")
    w(2, '(uuid "%s")' % U("lbl%s@%s,%s" % (name, x, y)))
    w(1, ")")

# ---- hierarchical labels
for (name, x, y, rot, shape) in HLABELS:
    w(1, '(hierarchical_label "%s"' % name)
    w(2, "(shape %s)" % shape)
    w(2, "(at %s %s %d)" % (f(x), f(y), rot))
    w(2, "(effects")
    w(3, "(font")
    w(4, "(size 1.27 1.27)")
    w(3, ")")
    w(3, "(justify left)")
    w(2, ")")
    w(2, '(uuid "%s")' % U("hlbl" + name))
    w(1, ")")

# ---- symbols
def emit_symbol(ref, lib_id, x, y, rot, value, footprint, desc, hide_ref=False,
                val_at=None, ref_at=None, fld_ang=0):
    def prop(name, val, px, py, ang, hide=False, justify=False):
        w(2, '(property "%s" "%s"' % (name, val))
        w(3, "(at %s %s %d)" % (f(px), f(py), ang))
        if hide:
            w(3, "(hide yes)")
        w(3, "(show_name no)")
        w(3, "(do_not_autoplace no)")
        w(3, "(effects")
        w(4, "(font")
        w(5, "(size 1.27 1.27)")
        w(4, ")")
        if justify:
            w(4, "(justify left)")
        w(3, ")")
        w(2, ")")

    w(1, "(symbol")
    w(2, '(lib_id "%s")' % lib_id)
    w(2, "(at %s %s %d)" % (f(x), f(y), rot))
    w(2, "(unit 1)")
    w(2, "(body_style 1)")
    w(2, "(exclude_from_sim no)")
    w(2, "(in_bom %s)" % ("yes" if fpmap.in_bom(ref) else "no"))
    w(2, "(on_board yes)")
    w(2, "(in_pos_files yes)")
    w(2, "(dnp %s)" % ("yes" if ref in getattr(layout, "DNP", ()) else "no"))
    w(2, '(uuid "%s")' % U("sym" + ref))
    rx, ry = ref_at if ref_at else (x, y)
    vx, vy = val_at if val_at else (x, y)
    prop("Reference", ref, rx, ry, fld_ang, hide=hide_ref, justify=True)
    prop("Value", value, vx, vy, fld_ang, justify=True)
    prop("Footprint", footprint or fpmap.fp(ref), x, y, 0, hide=True)
    prop("Datasheet", "", x, y, 0, hide=True)
    prop("Description", desc, x, y, 0, hide=True)
    for num in sorted(PINS[lib_id].keys()):
        w(2, '(pin "%s"' % num)
        w(3, '(uuid "%s")' % U("pin%s%s" % (ref, num)))
        w(2, ")")
    w(2, "(instances")
    w(3, '(project "%s"' % PROJECT)
    w(4, '(path "%s"' % INST_PATH)
    w(5, '(reference "%s")' % ref)
    w(5, "(unit 1)")
    w(4, ")")
    w(3, ")")
    w(2, ")")
    w(1, ")")

for (ref, lib_id, x, y, rot, value, fp) in COMPS:
    ra, va, _gr = layout.field_anchors(ref, x, y, rot)
    emit_symbol(ref, lib_id, x, y, rot, value, fp, "", val_at=va, ref_at=ra,
                fld_ang=layout.field_angle(rot))

for (ref, x, y) in GNDS:
    emit_symbol(ref, "power:GND", x, y, 0, "GND", "",
                "Power symbol creates a global label with name \\\"GND\\\" , ground",
                hide_ref=True, val_at=(x, y + 3.81), ref_at=(x, y + 6.35))

w(0, ")")

import kicanon
_text = kicanon.canonicalise("\n".join(L) + "\n")
open(OUT, "w", encoding="utf-8", newline="\n").write(_text)
print("wrote", OUT, len(L), "lines")

# -------- report expected connectivity from the geometry
# The roster below is the netlist this sheet is SUPPOSED to produce, written from the
# schematic intent rather than read back from the geometry -- so when the printed
# coordinates for a net do not all agree, the geometry is wrong, not this list.
#
# Q10 / Q11 are the place to look first.  Pin 3 (D) of BOTH lands on MID; pin 2 (S) of Q10
# lands on FEED_P and pin 2 (S) of Q11 on the R88 side.  That is COMMON DRAIN and it is
# what blocks reverse current.  Common source passes ERC, DRC and the pad count and is
# wrong.  Spec section 4.2 requires this to be read by hand after every regeneration.
nets = {
    "IGN_IN":     [("J1", "1")],
    "FEED_P":     [("J1", "2"), ("R104", "1"), ("Q10", "2"), ("R105", "1"), ("Q12", "2")],
    "VCC10":      [("R104", "2"), ("C63", "1"), ("D21", "1"), ("U10", "2")],
    "MID":        [("Q10", "3"), ("Q11", "3"), ("R101", "1")],
    "U10_DRN":    [("R101", "2"), ("U10", "1")],
    "U10_GATE":   [("U10", "3"), ("R102", "2"), ("R103", "1"), ("R107", "2")],
    "Q10_G":      [("Q10", "1"), ("Q12", "3"), ("D22", "1")],
    "Q11_G":      [("Q11", "1"), ("R102", "1")],
    "Q12_B":      [("Q12", "1"), ("R105", "2"), ("R106", "1")],
    "SNS":        [("Q11", "2"), ("R100", "1"), ("U10", "4")],
    "VBAT_PROT":  [("R100", "2"), ("C65", "1"), ("U10", "5"),
                   ("D2", "1"), ("L2", "1"), ("R2", "1")],
    "VBAT_F":     [("L2", "4"), ("R2", "2"), ("C1", "1"), ("L1", "1")],
    "VBAT":       [("L1", "2"), ("C2", "1"), ("C3", "1"), ("C4", "1"), ("D3", "2")],
    "VLOGIC_IN":  [("D3", "1"), ("C5", "1")],
    # GND_IN is the connector-side return.  It carries no power symbol by design -- see the
    # split-ground note on the sheet -- so every member reaches it through a local label.
    "GND_IN":     [("J1", "3"), ("D2", "2"), ("L2", "2"), ("R3", "1"),
                   ("C63", "2"), ("D21", "2"), ("C64", "2"), ("C65", "2"),
                   ("C62", "2"), ("D23", "2"), ("U10", "8"), ("U10", "6")],
    "GND(board)": [("L2", "3"), ("R3", "2"), ("C1", "2"), ("C2", "2"), ("C3", "2"),
                   ("C4", "2"), ("C5", "2")],
    # the last three are two-member nets with no label of their own
    "D22_A":      [("D22", "2"), ("R107", "1")],
    "R106_D23":   [("R106", "2"), ("D23", "1")],
    "R103_C64":   [("R103", "2"), ("C64", "1")],
    "U10_TMR":    [("U10", "10"), ("C62", "1")],
}
lookup = {r: (lid, x, y, rot) for (r, lid, x, y, rot, v, fp) in COMPS}
print("\nexpected pin coordinates:")
for net, members in nets.items():
    pts = []
    for (r, p) in members:
        lid, x, y, rot = lookup[r]
        lx, ly = PINS[lid][p]
        pts.append("%s.%s=(%s,%s)" % (r, p, f(place(x, y, rot, lx, ly)[0]),
                                      f(place(x, y, rot, lx, ly)[1])))
    print(" ", net, " ".join(pts))
