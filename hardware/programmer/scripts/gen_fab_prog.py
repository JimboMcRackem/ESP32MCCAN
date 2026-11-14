# -*- coding: utf-8 -*-
"""JLCPCB fabrication + assembly package for the programmer board (plan Task 4).

    python hardware/programmer/scripts/gen_fab_prog.py           write output/jlcpcb/
    python hardware/programmer/scripts/gen_fab_prog.py --check   grade the package

Writes, from prog.kicad_pcb and parts.py, into hardware/programmer/output/jlcpcb/:
  drc.rpt              the DRC the package was cut from (all severities, zones refilled,
                       schematic parity); build() stops unless it is clean
  gerbers.zip          F/B copper, mask, paste, silk, Edge.Cuts, PTH and NPTH Excellon drill
  bom.csv              Comment,Designator,Footprint,LCSC -- one line per parts.bom_lines() group
  cpl.csv              Designator,Mid X,Mid Y,Layer,Rotation -- KiCad's placement + ROT_FIX
  assembly.pdf         F.Fab (designators, values) and the outline
  stock.txt            check_stock_prog.py's report for 5 boards, as run when this was written
  rotation-review.txt  every polarised part's JLCPCB rotation and how far it is trusted
  board.sha256         sha256 of the board the package was cut from (written last)

The rotation table, the pad-centre CPL for parts whose KiCad origin is not their body centre,
and the stamp follow hardware/scripts/gen_fab.py; they are copied, not imported, because that
module imports the main board's layout.  Nothing here is hand-edited.
"""
import csv
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import check_board  # noqa: E402
import parts  # noqa: E402

PCB = os.path.join(PROG, "prog.kicad_pcb")
OUT = os.path.join(PROG, "output", "jlcpcb")
KICAD = os.environ.get("KICAD_CLI", r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe")
FILES = ("gerbers.zip", "bom.csv", "cpl.csv", "assembly.pdf", "stock.txt",
         "rotation-review.txt", "drc.rpt", "board.sha256")
BOARDS = 5

GERBER_LAYERS = ["F.Cu", "B.Cu", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask",
                 "Edge.Cuts"]
PROTEL = {"F.Cu": ".gtl", "B.Cu": ".gbl", "F.Paste": ".gtp", "B.Paste": ".gbp",
          "F.SilkS": ".gto", "B.SilkS": ".gbo", "F.Mask": ".gts", "B.Mask": ".gbs",
          "Edge.Cuts": ".gm1"}

# JLCPCB's placement rotation = KiCad's + this offset, per footprint (KiCad Package column).
# NO offset here has been checked against JLCPCB (see hardware/scripts/gen_fab.py):
#   "recalled"    the main board's ROT_FIX holds a recalled value for the same family;
#   "unverified"  the nearest family's value from memory of the community tables, or 0.
# EVERY row of rotation-review.txt is checked in JLCPCB's placement preview before paying.
ROT_FIX = {
    "SOT-23-6": (180, "recalled"),                       # main: SOT-23 / SOT-23-5 recalled 180
    "SOT-223-3_TabPin2": (180, "unverified"),
    "SOT-363_SC-70-6": (180, "unverified"),
    "SSOP-8_2.95x2.8mm_P0.65mm": (270, "unverified"),    # main: SOIC-8 recalled 270
    "WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm": (270, "unverified"),
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": (0, "unverified"),
    "PinHeader_1x06_P2.54mm_Vertical": (0, "unverified"),  # main: unverified 0
    "LED_0603_1608Metric": (0, "unverified"),
}

# KiCad's origin for these is not the body centre that JLCPCB's Mid X/Y means (the header's is
# pin 1, the receptacle's sits behind its mouth): their CPL position is the centre of their pads.
CENTROID_FROM_PADS = ("J1", "J2")


def polarised(ref):
    return ref.rstrip("0123456789") in ("U", "D", "J")


def board_hash(pcb=PCB):
    """sha256 of the board, line endings normalised (git may check it out CRLF)."""
    with io.open(pcb, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def pad_centre_board(ref, pcb=PCB):
    """Board-frame (x, y) of the centre of `ref`'s pad positions (bounding box of centres)."""
    pads = check_board.read(pcb).fp(ref).pads
    return ((min(p.x for p in pads) + max(p.x for p in pads)) / 2,
            (min(p.y for p in pads) + max(p.y for p in pads)) / 2)


def fp_name(fp):
    return fp.split(":", 1)[-1]


def read_csv(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def kicad_pos(path):
    """{ref: {x, y, rot, pkg, side}} from KiCad's position export (y-up, as JLCPCB reads it)."""
    return {r[0]: dict(x=float(r[3]), y=float(r[4]), rot=float(r[5]) % 360.0, pkg=r[2],
                       side=r[6]) for r in read_csv(path)[1:]}


def cpl_xy(ref, k, pcb):
    if ref not in CENTROID_FROM_PADS:
        return k["x"], k["y"]
    cx, cy = pad_centre_board(ref, pcb)
    return cx, -cy


def mm(s):
    return float(s[:-2] if s.endswith("mm") else s)


# --------------------------------------------------------------------------- check
def check(out=OUT, pcb=PCB):
    fails = []
    for n in FILES:
        if not os.path.exists(os.path.join(out, n)):
            fails.append("missing output %s" % n)
    if fails:
        return fails
    P = lambda n: os.path.join(out, n)  # noqa: E731
    if io.open(P("board.sha256"), encoding="utf-8").read().strip() != board_hash(pcb):
        return ["board.sha256: the package was cut from a different board -- re-run "
                "gen_fab_prog.py"]

    rpt = io.open(P("drc.rpt"), encoding="utf-8").read()
    for what in ("DRC violations", "unconnected pads", "Footprint errors"):
        if "** Found 0 %s **" % what not in rpt:
            fails.append("drc.rpt: not 0 %s" % what)

    names = zipfile.ZipFile(P("gerbers.zip")).namelist()
    for ly in GERBER_LAYERS:
        if not any(n.endswith(PROTEL[ly]) for n in names):
            fails.append("gerbers.zip has no %s layer (*%s)" % (ly, PROTEL[ly]))
    for d in ("PTH", "NPTH"):
        if not any(n.endswith("-%s.drl" % d) for n in names):
            fails.append("gerbers.zip has no %s drill file" % d)

    rows = read_csv(P("bom.csv"))
    if rows[0] != ["Comment", "Designator", "Footprint", "LCSC"]:
        fails.append("bom.csv header is %r" % rows[0])
    seen = {}
    for r in rows[1:]:
        for ref in [x.strip() for x in r[1].split(",")]:
            seen[ref] = seen.get(ref, 0) + 1
            if ref not in parts.PARTS:
                fails.append("bom.csv lists %s, which is not in parts.py" % ref)
            elif parts.PARTS[ref]["lcsc"] != r[3]:
                fails.append("bom.csv gives %s %s, parts.py says %s"
                             % (ref, r[3], parts.PARTS[ref]["lcsc"]))
    for ref in parts.PARTS:
        if seen.get(ref, 0) != 1:
            fails.append("%s appears %d times in bom.csv (want 1)" % (ref, seen.get(ref, 0)))

    kicad = kicad_pos(P("kicad-pos.csv"))
    rows = read_csv(P("cpl.csv"))
    if rows[0] != ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]:
        fails.append("cpl.csv header is %r" % rows[0])
    placed = set()
    for r in rows[1:]:
        ref = r[0]
        if ref in placed or ref not in kicad or ref not in parts.PARTS:
            fails.append("cpl.csv: %s listed twice, or not a placed part" % ref)
            continue
        placed.add(ref)
        k = kicad[ref]
        ex, ey = cpl_xy(ref, k, pcb)
        if abs(mm(r[1]) - ex) > 1e-3 or abs(mm(r[2]) - ey) > 1e-3:
            fails.append("cpl.csv %s at (%s, %s), want (%.4f, %.4f)" % (ref, r[1], r[2], ex, ey))
        fix = ROT_FIX.get(k["pkg"], (0, None))[0]
        d = (float(r[4]) - (k["rot"] + fix)) % 360.0
        if min(d, 360.0 - d) > 1e-3:
            fails.append("cpl.csv %s rotation %s, want KiCad %g + ROT_FIX %d"
                         % (ref, r[4], k["rot"], fix))
        if r[3] != "Top":
            fails.append("cpl.csv %s on %s; every part is on top" % (ref, r[3]))
        if polarised(ref) and k["pkg"] not in ROT_FIX:
            fails.append("polarised %s (%s) has no ROT_FIX entry" % (ref, k["pkg"]))
    for ref in parts.PARTS:
        if ref not in placed:
            fails.append("%s is in parts.py but not in cpl.csv" % ref)

    rev = io.open(P("rotation-review.txt"), encoding="utf-8").read()
    if "EVERY row" not in rev:
        fails.append("rotation-review.txt does not ask for every row to be checked")
    body = rev.split("\n\n", 1)[-1]
    for ref in [r for r in parts.PARTS if polarised(r)]:
        m = re.search(r"^%s\s.*\s(\w+)\s*$" % ref, body, re.M)
        if not m or m.group(1) not in ("recalled", "unverified"):
            fails.append("rotation-review.txt does not list polarised %s with a trust label" % ref)
    for how in sorted(set(h for _f, h in ROT_FIX.values()) - {"recalled", "unverified"}):
        fails.append("ROT_FIX trust %r: no offset here has been checked against JLCPCB" % how)
    return fails


# --------------------------------------------------------------------------- build
def cli(*args):
    r = subprocess.run([KICAD] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode not in (0, 5):
        raise SystemExit("kicad-cli %s failed (%d):\n%s%s"
                         % (" ".join(args[:3]), r.returncode, r.stdout, r.stderr))
    return r


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    gdir = os.path.join(OUT, "gerbers")
    os.makedirs(gdir)
    P = lambda n: os.path.join(OUT, n)  # noqa: E731

    # the DRC first: no package is cut from a board that is not clean
    cli("pcb", "drc", "--severity-all", "--schematic-parity", "--refill-zones",
        "-o", P("drc.rpt"), PCB)
    rpt = io.open(P("drc.rpt"), encoding="utf-8").read()
    # the report file words schematic parity as "Footprint errors"
    for what in ("DRC violations", "unconnected pads", "Footprint errors"):
        if "** Found 0 %s **" % what not in rpt:
            raise SystemExit("gen_fab_prog: DRC is not clean (%s) -- see %s" % (what, P("drc.rpt")))

    cli("pcb", "export", "gerbers", "--layers", ",".join(GERBER_LAYERS), "--subtract-soldermask",
        "--check-zones", "-o", gdir + os.sep, PCB)
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--excellon-units", "mm", "-o", gdir + os.sep, PCB)
    with zipfile.ZipFile(P("gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(glob.glob(os.path.join(gdir, "*"))):
            z.write(p, os.path.basename(p))
    shutil.rmtree(gdir)

    with io.open(P("bom.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for key, refs in parts.bom_lines():
            val, fp = key.split("|", 1)
            w.writerow([val, ",".join(refs), fp_name(fp), parts.PARTS[refs[0]]["lcsc"]])

    cli("pcb", "export", "pos", "--side", "both", "--format", "csv", "--units", "mm",
        "-o", P("kicad-pos.csv"), PCB)
    kicad = kicad_pos(P("kicad-pos.csv"))
    review = []
    with io.open(P("cpl.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref in parts.PARTS:
            k = kicad.get(ref)
            if k is None:
                raise SystemExit("gen_fab_prog: %s is in parts.py but KiCad did not place it" % ref)
            fix, how = ROT_FIX.get(k["pkg"], (0, None))
            rot = (k["rot"] + fix) % 360.0
            x, y = cpl_xy(ref, k, PCB)
            w.writerow([ref, "%.4fmm" % x, "%.4fmm" % y,
                        "Top" if k["side"] == "top" else "Bottom", "%g" % rot])
            if polarised(ref):
                review.append("%-3s %-42s KiCad %5g + %3d = %5g  %s"
                              % (ref, k["pkg"], k["rot"], fix, rot, how or "NO-ENTRY"))

    with io.open(P("rotation-review.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("Programmer board: parts whose orientation matters.  JLCPCB rotation = KiCad +\n"
                "ROT_FIX (scripts/gen_fab_prog.py).  No offset has been checked against JLCPCB:\n"
                "'recalled' follows the main board's recalled value for the same family,\n"
                "'unverified' is from memory or 0.\n"
                "Check EVERY row in JLCPCB's placement preview before the order is paid:\n"
                "U1-U5 pin-1 dot on KiCad's pin 1; D1-D3 cathode (pin 1) towards J1, the USB\n"
                "end of the board; J1 and J2 sit on their pads (both are placed at their pad\n"
                "centre, not KiCad's origin).\n\n")
        f.write("\n".join(review) + "\n")

    cli("pcb", "export", "pdf", "--mode-single", "--layers", "F.Fab,Edge.Cuts",
        "--include-border-title", "--black-and-white", "--scale", "0", "-o", P("assembly.pdf"),
        PCB)

    # stock, as of now: a report, not a gate here (check_stock_prog's own exit code is)
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_stock_prog.py"),
                        "--boards", str(BOARDS)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    with io.open(P("stock.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(r.stdout + r.stderr)
        f.write("\n(check_stock_prog.py --boards %d exit %d)\n" % (BOARDS, r.returncode))

    with io.open(P("board.sha256"), "w", encoding="utf-8", newline="\n") as f:
        f.write(board_hash() + "\n")
    print("wrote %s: gerbers.zip (%d files), bom.csv (%d lines), cpl.csv (%d), assembly.pdf, "
          "stock.txt (exit %d), rotation-review.txt (%d rows)"
          % (os.path.relpath(OUT, PROG), len(zipfile.ZipFile(P("gerbers.zip")).namelist()),
             len(parts.bom_lines()), len(parts.PARTS), r.returncode, len(review)))
    return 0


def main(argv):
    if "--check" in argv:
        fails = check()
        for f in fails:
            print("FAIL: %s" % f)
        print("check: %s" % ("FAIL (%d)" % len(fails) if fails else "PASS"))
        return 1 if fails else 0
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
