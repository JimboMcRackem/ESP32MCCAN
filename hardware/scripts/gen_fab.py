# -*- coding: utf-8 -*-
"""JLCPCB fabrication + assembly package for the plan4 board (phase B, Task 8).

    python scripts/gen_fab.py           write hardware/output/jlcpcb/
    python scripts/gen_fab.py --check   assert the package is complete and consistent

Writes, from mccan.kicad_pcb and output/netlist.net:
  gerbers.zip    every copper/mask/paste/silk layer + Edge.Cuts + Excellon drill (PTH, NPTH)
  bom.csv        Comment,Designator,Footprint,LCSC  -- one line per lcsc.bom_lines() group
  cpl.csv        Designator,Mid X,Mid Y,Layer,Rotation  -- KiCad's placement + ROT_FIX
  assembly.pdf   F.Fab (values + designators) and the outline, for whoever hand-solders
  stock.txt      scripts/check_stock.py's report for 5 boards, as run when this was written
  rotation-review.txt  every polarised part's JLCPCB rotation and how far it is trusted

Nothing here is hand-edited; re-run after any board change.
"""

import csv
import glob
import hashlib
import io
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import check_netlist  # noqa: E402
import fpmap  # noqa: E402
import layout_pcb as L  # noqa: E402
import lcsc  # noqa: E402

PCB = os.path.join(HW, "mccan.kicad_pcb")
NETLIST = os.path.join(HW, "output", "netlist.net")
OUT = os.path.join(HW, "output", "jlcpcb")
KICAD = os.environ.get("KICAD_CLI", r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe")

BOM, CPL, ZIP, PDF = (os.path.join(OUT, n) for n in ("bom.csv", "cpl.csv", "gerbers.zip",
                                                     "assembly.pdf"))
STOCK, ROTREV, DRC = (os.path.join(OUT, n) for n in ("stock.txt", "rotation-review.txt",
                                                     "drc.rpt"))
# sha256 of the board the package was cut from; --check refuses a package from another board.
STAMP = os.path.join(OUT, "board.sha256")


def board_hash():
    """sha256 of mccan.kicad_pcb, line endings normalised (git may check it out CRLF)."""
    with io.open(PCB, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()

GERBER_LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu",
                 "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "Edge.Cuts"]
PROTEL = dict([("F.Cu", ".gtl"), ("B.Cu", ".gbl"), ("F.Paste", ".gtp"), ("B.Paste", ".gbp"),
               ("F.SilkS", ".gto"), ("B.SilkS", ".gbo"), ("F.Mask", ".gts"), ("B.Mask", ".gbs"),
               ("Edge.Cuts", ".gm1")] + [("In%d.Cu" % i, ".g%d" % i) for i in range(1, 7)])

# JLCPCB's placement rotation = KiCad's + this offset, per footprint (KiCad Package column).
# JLCPCB's part library draws some packages turned relative to the IPC/KiCad zero orientation.
# NO offset here has been checked against JLCPCB; check() refuses any other label:
#   "recalled"    the offset as recalled from the community tables (JLCKicadTools rotations.cf,
#                 jlcpcb-tools), not re-fetched -- likely right, not known right;
#   "unverified"  the package is in no table; the value is the nearest family's, or 0.
# So EVERY polarised part is checked in JLCPCB's placement preview before the order is paid
# (rotation-review.txt).  A row confirmed there may be relabelled "confirmed" -- and check()'s
# allowed set widened with it -- only by whoever confirmed it.
# Every footprint a polarised part uses has an entry; check() enforces that.  Non-polarised
# two-terminal parts (R, C, non-polar connectors) need none: 0 and 180 place the same.
ROT_FIX = {
    "SOT-23": (180, "recalled"),
    "SOT-23-5": (180, "recalled"),
    "SOIC-8_3.9x4.9mm_P1.27mm": (270, "recalled"),
    "SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm": (270, "recalled"),
    "MSOP-10_3x3mm_P0.5mm": (270, "recalled"),
    "PowerPAK_SO-8L_Single": (270, "unverified"),  # table has PowerPAK_SO-8_Single, not -8L
    "CP_Elec_10x10.5": (180, "recalled"),
    "CP_Elec_6.3x7.7": (180, "recalled"),
    "TI_DGQ0028C": (270, "unverified"),            # HVSSOP-28: the table's HTSSOP family
    "Infineon_PG-TSDSO-14-22": (270, "unverified"),  # TSSOP-like: the table's TSSOP family
    "Infineon_PG-HSOF-8-1": (0, "unverified"),     # TOLL: in no table
    "ESP32-WROOM-32E": (0, "unverified"),          # module: in no table
    "D_SOD-123": (0, "unverified"),
    "D_SOD-323": (0, "unverified"),
    "D_SMA": (0, "unverified"),
    "D_SMB": (0, "unverified"),
    # Not polarised by a mark, but wrong if turned 90 degrees (rotation-review.txt):
    "SW_Push_1P1T_XKB_TS-1187A": (0, "unverified"),   # pins joined in pairs: 90 = always pressed
    "TDK_ACT45B": (0, "unverified"),                  # 90 cross-connects CANH and CANL
    "PinHeader_1x06_P2.54mm_Vertical": (0, "unverified"),
    "Wurth_WE-CMBNC_7448031002": (0, "unverified"),   # 90 cross-connects the two windings
}

# Parts whose placement must be checked: the electrolytics, the switches (pins joined in pairs),
# the two-winding chokes, and the header; plus every D*, Q*, U*.
POLARISED_EXTRA = ("C3", "C65", "C68", "SW1", "SW2", "L2", "L6", "J2")

# KiCad's origin for these through-hole footprints is pin 1, not the body centre, which is what
# JLCPCB's CPL "Mid X/Y" means.  Their CPL position is the centre of their pads.
CENTROID_FROM_PADS = ("J2", "L2")


def polarised(ref):
    return ref in POLARISED_EXTRA or ref.rstrip("0123456789") in ("D", "Q", "U")


def pad_centre(ref, text):
    """(dx, dy) board-frame offset from `ref`'s origin to the centre of its pads' positions."""
    i = text.index('(property "Reference" "%s"' % ref)
    s = text.rfind("\t(footprint ", 0, i)
    e = text.find("\n\t(footprint ", i)
    blk = text[s:e if e > 0 else len(text)]
    at = re.search(r"^\t\t\(at [-\d.]+ [-\d.]+(?: ([-\d.]+))?\)", blk, re.M)
    rot = math.radians(float(at.group(1) or 0))
    pts = [(float(x), float(y)) for x, y in
           re.findall(r'\(pad "[^"]*" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', blk)]
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    # KiCad: board y down, angle counter-clockwise as seen from the top.
    return (cx * math.cos(rot) + cy * math.sin(rot), -cx * math.sin(rot) + cy * math.cos(rot))


def cpl_xy(ref, k, text):
    """CPL Mid X/Y: KiCad's position-file origin, moved to the pad centre where it is pin 1.
    The position file is y-up, so a board-frame dy goes in negated."""
    if ref not in CENTROID_FROM_PADS:
        return k["x"], k["y"]
    dx, dy = pad_centre(ref, text)
    return k["x"] + dx, k["y"] - dy


def fp_name(fp):
    return fp.split(":", 1)[-1]


def bom_parts():
    """{ref: (value, footprint, lcsc)} for every part JLCPCB is to place."""
    out = {}
    for key, refs in lcsc.bom_lines(NETLIST):
        entry = lcsc.LCSC.get(key)
        val, fp = key.split("|", 1)
        for r in refs:
            out[r] = (val, fp, entry["lcsc"] if entry else "")
    return out


def not_purchased(ref, nl):
    """Test pads, wire tails, the net tie, mounting holes: copper, not parts."""
    return ref.startswith("H") and ref not in nl.parts or (
        ref in nl.parts and not fpmap.in_bom(ref))


def read_csv(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def mm(s):
    return float(s[:-2] if s.endswith("mm") else s)


# --------------------------------------------------------------------------- check

def check():
    fails = []

    def fail(msg):
        fails.append(msg)

    for p in (ZIP, BOM, CPL, PDF, STOCK, ROTREV, STAMP):
        if not os.path.exists(p):
            fail("missing output %s" % os.path.relpath(p, HW))
    if fails:
        return fails
    if io.open(STAMP, encoding="utf-8").read().strip() != board_hash():
        fail("the package was cut from a different mccan.kicad_pcb -- re-run gen_fab.py")
        return fails

    nl = check_netlist.load(NETLIST)
    want = bom_parts()

    # gerbers.zip: every layer and the drill
    names = zipfile.ZipFile(ZIP).namelist()
    # By Protel extension: KiCad names the files after the USER layer names (GND_1, PWR_3,
    # F_Silkscreen), so the canonical name is not in them.
    for ly in GERBER_LAYERS:
        if not any(n.endswith(PROTEL[ly]) for n in names):
            fail("gerbers.zip has no %s layer (*%s)" % (ly, PROTEL[ly]))
    if not any(n.endswith(".drl") for n in names):
        fail("gerbers.zip has no Excellon drill file")

    # bom.csv: header, one appearance per placed part, a C-number on every line
    rows = read_csv(BOM)
    if rows[0] != ["Comment", "Designator", "Footprint", "LCSC"]:
        fail("bom.csv header is %r" % rows[0])
    seen = {}
    for r in rows[1:]:
        if not re.match(r"^C\d+$", r[3]):
            fail("bom.csv line %r has no C-number" % r[1])
        for ref in [x.strip() for x in r[1].split(",")]:
            seen[ref] = seen.get(ref, 0) + 1
            if not_purchased(ref, nl):
                fail("bom.csv lists %s, which is not a purchased part" % ref)
            elif ref in want and want[ref][2] != r[3]:
                fail("bom.csv gives %s %s, lcsc.py says %s" % (ref, r[3], want[ref][2]))
    for ref in sorted(want, key=lambda r: (r.rstrip("0123456789"), len(r), r)):
        if seen.get(ref, 0) != 1:
            fail("%s appears %d times in bom.csv (want 1)" % (ref, seen.get(ref, 0)))
    for ref in seen:
        if ref not in want and not not_purchased(ref, nl):
            fail("bom.csv lists %s, which is DNP or unknown" % ref)

    # cpl.csv: the same set of parts, rotations = KiCad's + ROT_FIX
    text = io.open(PCB, encoding="utf-8").read()
    kicad = kicad_pos()
    rows = read_csv(CPL)
    if rows[0] != ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]:
        fail("cpl.csv header is %r" % rows[0])
    placed = {}
    for r in rows[1:]:
        ref = r[0]
        if ref in placed:
            fail("cpl.csv lists %s twice" % ref)
        placed[ref] = r
        if not_purchased(ref, nl) or ref.startswith("TP"):
            fail("cpl.csv lists %s, which is not a purchased part" % ref)
            continue
        if ref not in kicad:
            fail("cpl.csv lists %s, which KiCad did not place" % ref)
            continue
        k = kicad[ref]
        fix = ROT_FIX.get(k["pkg"], (0, None))[0]
        ex, ey = cpl_xy(ref, k, text)
        if abs(mm(r[1]) - ex) > 1e-3 or abs(mm(r[2]) - ey) > 1e-3:
            fail("cpl.csv %s at (%s, %s), want the part's centre (%g, %g)"
                 % (ref, r[1], r[2], ex, ey))
        if abs((float(r[4]) - (k["rot"] + fix)) % 360.0) > 1e-3 and \
                abs((float(r[4]) - (k["rot"] + fix)) % 360.0 - 360.0) > 1e-3:
            fail("cpl.csv %s rotation %s, want KiCad %g + ROT_FIX %d" % (ref, r[4], k["rot"], fix))
        if r[3] != "Top":
            fail("cpl.csv %s on %s; this board is single-sided" % (ref, r[3]))
        if polarised(ref) and k["pkg"] not in ROT_FIX:
            fail("polarised %s (%s) has no ROT_FIX entry" % (ref, k["pkg"]))
    for ref in want:
        if ref not in placed:
            fail("%s is in the BOM but not in cpl.csv" % ref)

    # rotation-review.txt: every polarised part listed, none presented as settled
    rev = io.open(ROTREV, encoding="utf-8").read()
    listed = set(re.findall(r"^(\w+)\s", rev.split("\n\n", 1)[-1], re.M))
    for ref in sorted(r for r in want if polarised(r)):
        if ref not in listed:
            fail("rotation-review.txt does not list polarised %s" % ref)
    if "EVERY row" not in rev:
        fail("rotation-review.txt does not ask for every row to be checked")
    for how in sorted(set(h for _f, h in ROT_FIX.values()) - set(("recalled", "unverified"))):
        fail("ROT_FIX trust %r: no offset here has been checked against JLCPCB" % how)

    # silkscreen: every TP labelled with its net on F.SilkS; KiCad's own DRC grades placement
    # (silk_over_copper = on a pad, silk_edge_clearance = clipped, silk_overlap = on silk)
    silk = set(re.findall(r'\(gr_text "([^"]*)" \(at ([-\d.]+) ([-\d.]+)\) \(layer "F\.SilkS"\)',
                          text))
    labelled = dict(((float(x), float(y)), t) for t, x, y in silk)
    for ref, (x, y, _r) in sorted(L.PLACE.items()):
        if not ref.startswith("TP"):
            continue
        net = nl.pin_net.get((ref, "1"), "")
        hit = [t for (lx, ly), t in labelled.items() if abs(ly - y) < 1e-6 and 0 < lx - x < 1.5]
        if hit != [net]:
            fail("%s (%s) is labelled %r on F.SilkS" % (ref, net, hit))
    for ref in sorted(want):
        if ref.rstrip("0123456789") in ("J", "F", "U", "Q", "D", "L"):
            m = re.search(r'\(property "Reference" "%s"[^\n]*\n\t*\(at [^)]*\)\n\t*\(layer "([^"]*)"'
                          % re.escape(ref), text)
            if m and m.group(1) != "F.SilkS":
                fail("%s designator is on %s, not F.SilkS" % (ref, m.group(1)))
    rpt = io.open(DRC, encoding="utf-8").read() if os.path.exists(DRC) else ""
    if "** Found 0 DRC violations **" not in rpt:
        bad = sorted(set(re.findall(r"^\[(\w+)\]", rpt, re.M)))
        fail("DRC (all severities) is not clean: %s" % (", ".join(bad) or "no report"))
    if "** Found 0 unconnected pads **" not in rpt:
        fail("DRC reports unconnected pads")
    return fails


POS = os.path.join(OUT, "kicad-pos.csv")


def cli(*args):
    r = subprocess.run([KICAD] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode not in (0, 5):   # 5: drc --exit-code-violations found some; graded later
        raise SystemExit("kicad-cli %s failed (%d):\n%s%s"
                         % (" ".join(args[:3]), r.returncode, r.stdout, r.stderr))
    return r


def kicad_pos():
    """{ref: {x, y, rot, pkg, side}} straight from KiCad's placement export (kicad-pos.csv).

    KiCad's position file is y-up (board y negated), which is the frame JLCPCB's CPL reader
    expects from a KiCad export; it is passed through unchanged.
    """
    out = {}
    for r in read_csv(POS)[1:]:
        out[r[0]] = dict(x=float(r[3]), y=float(r[4]), rot=float(r[5]) % 360.0, pkg=r[2],
                         side=r[6])
    return out


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    gdir = os.path.join(OUT, "gerbers")
    os.makedirs(gdir)

    cli("pcb", "export", "gerbers", "--layers", ",".join(GERBER_LAYERS), "--subtract-soldermask",
        "--check-zones", "-o", gdir + os.sep, PCB)
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--excellon-units", "mm", "--generate-map", "--map-format", "pdf", "-o", gdir + os.sep, PCB)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(glob.glob(os.path.join(gdir, "*"))):
            if not p.endswith(".pdf"):
                z.write(p, os.path.basename(p))

    cli("pcb", "export", "pos", "--side", "both", "--format", "csv", "--units", "mm",
        "--exclude-dnp", "-o", POS, PCB)
    kicad = kicad_pos()

    nl = check_netlist.load(NETLIST)
    want = bom_parts()
    missing = sorted(r for r in want if not want[r][2])
    if missing:
        raise SystemExit("gen_fab: no LCSC entry for %s -- add it to lcsc.py" % ", ".join(missing))

    with io.open(BOM, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for key, refs in lcsc.bom_lines(NETLIST):
            val, fp = key.split("|", 1)
            w.writerow([val, ",".join(refs), fp_name(fp), lcsc.LCSC[key]["lcsc"]])

    text = io.open(PCB, encoding="utf-8").read()
    review = []
    with io.open(CPL, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref in sorted(want, key=lambda r: (r.rstrip("0123456789"),
                                               int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))):
            k = kicad.get(ref)
            if k is None:
                raise SystemExit("gen_fab: %s is in the BOM but KiCad did not place it" % ref)
            fix, how = ROT_FIX.get(k["pkg"], (0, None))
            rot = (k["rot"] + fix) % 360.0
            x, y = cpl_xy(ref, k, text)
            w.writerow([ref, "%.4fmm" % x, "%.4fmm" % y,
                        "Top" if k["side"] == "top" else "Bottom", "%g" % rot])
            if polarised(ref):
                review.append("%-5s %-44s KiCad %5g + %3d = %5g  %s"
                              % (ref, k["pkg"], k["rot"], fix, rot, how or "NO ENTRY"))

    with io.open(ROTREV, "w", encoding="utf-8", newline="\n") as f:
        f.write("Parts whose orientation matters: JLCPCB rotation = KiCad + ROT_FIX\n"
                "(scripts/gen_fab.py).  No offset has been checked against JLCPCB: 'recalled'\n"
                "is from memory of the community tables, 'unverified' is in no table.\n"
                "Check EVERY row in JLCPCB's placement preview before the order is paid:\n"
                "pin 1 / cathode / + marking against the board's silk; SW1/SW2, L2 and L6\n"
                "against their pads (wrong by 90 degrees shorts or cross-connects them);\n"
                "J2 and L2 are placed at their pad centre, not KiCad's pin-1 origin.\n\n")
        f.write("\n".join(review) + "\n")

    cli("pcb", "export", "pdf", "--mode-single", "--layers", "F.Fab,Edge.Cuts",
        "--include-border-title", "--black-and-white", "--scale", "0", "-o", PDF, PCB)

    # 3D views, for reading before an order: parts the right way round, TP labels, antenna.
    for name, extra in (("top", ["--side", "top"]), ("bottom", ["--side", "bottom"])):
        cli("pcb", "render", *extra, "-w", "2800", "-h", "2000", "--background", "opaque",
            "-o", os.path.join(OUT, "render-%s.png" % name), PCB)

    # The DRC the package was cut from, all severities, zones refilled (see routing-tool.md).
    cli("pcb", "drc", "--severity-all", "--schematic-parity", "--refill-zones", "-o", DRC, PCB)
    with io.open(STAMP, "w", encoding="utf-8", newline="\n") as f:
        f.write(board_hash() + "\n")

    # Stock, as of now: a report, not a gate here -- check_stock's own exit code is the gate.
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_stock.py"), "--boards", "5"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    with io.open(STOCK, "w", encoding="utf-8", newline="\n") as f:
        f.write(r.stdout + r.stderr)
        f.write("\n(check_stock.py exit %d)\n" % r.returncode)

    print("wrote %s: gerbers.zip (%d files), bom.csv (%d lines, %d parts), cpl.csv (%d), "
          "assembly.pdf, stock.txt (exit %d), rotation-review.txt (%d polarised, %d unverified)"
          % (os.path.relpath(OUT, HW), len(zipfile.ZipFile(ZIP).namelist()),
             len(lcsc.bom_lines(NETLIST)), len(want), len(want), r.returncode, len(review),
             sum("unverified" in x for x in review)))
    _ = nl
    return 0


def main(argv):
    if "--check" in argv:
        fails = check()
        for f in fails:
            print("FAIL: %s" % f)
        print("gen_fab --check: %s" % ("FAIL (%d)" % len(fails) if fails else "PASS"))
        return 1 if fails else 0
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
