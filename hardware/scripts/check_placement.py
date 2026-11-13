"""Placement gate (phase B, plan Task 4).

  python check_placement.py        (from hardware/ or hardware/scripts/)

Reads the GENERATED board (mccan.kicad_pcb) and the netlist, and asserts:
  * every netlist footprint is on the board, and on F.Cu (single-sided assembly, spec goal 4);
  * every pad is inside the outline, and every courtyard too unless the ref is in
    layout_pcb.OFFBOARD_OK (U5: its antenna clearance overhangs the edge on purpose);
  * the cable tails J1 J3 J4 J5 J8 J9 J10 J11 exit within 15 mm of layout_pcb.CABLE_EDGE.  A
    tail's exit is its strain-relief hole (the unnumbered NPTH the wire passes through); a
    tail without one is measured at its nearest pad;
  * every TP* is on F.Cu and no other part's courtyard comes within 1 mm of its pad;
  * every non-ground test point has a GND, GND_B or GND_IN test point within 25 mm (spec 8:
    "a GND pad within probe-clip reach of each group");
  * C67 and C68 have a pad within 10 mm of U14 pad 15 (feed-B bulk at the pod switch);
  * R100 has a pad within 8 mm of U10 pin 4 (the Kelvin sense resistor at its sense pin).
Exit 1 on any failure.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_pcb as G  # noqa: E402
import layout_pcb as L  # noqa: E402

BOARD = os.path.join(HW, "mccan.kicad_pcb")
TAILS = ("J1", "J3", "J4", "J5", "J8", "J9", "J10", "J11")
TAIL_REACH = 15.0
TP_HALO = 1.0
GND_TP_REACH = 25.0
GND_NETS = ("GND", "GND_B", "GND_IN")
NEAR = [  # (ref, (anchor ref, anchor pad), mm)
    ("C67", ("U14", "15"), 10.0),
    ("C68", ("U14", "15"), 10.0),
    ("R100", ("U10", "4"), 8.0),
]


def footprints(text):
    """ref -> dict(lib, layer, x, y, rot, pads=[(name, x, y, w, h, net)]) from the board.

    Pad positions are made absolute; (w, h) is the pad's axis-aligned extent on the board."""
    out = {}
    for blk in text.split("\n\t(footprint ")[1:]:
        lib = re.match(r'"([^"]*)"', blk).group(1)
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk)
        if not ref:
            continue
        layer = re.search(r'\n\t\t\(layer "([^"]*)"\)', blk).group(1)
        at = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk)
        fx, fy, fr = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
        pads = []
        for pm in re.finditer(r'\n\t\t\(pad "([^"]*)" (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+)'
                              r'(?: ([-\d.]+))?\)\s*\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)',
                              blk, re.S):
            lx, ly = float(pm.group(3)), float(pm.group(4))
            dx, dy = G.rot_local(lx, ly, fr)
            w, h = float(pm.group(6)), float(pm.group(7))
            prot = float(pm.group(5) or 0)
            t = math.radians(prot)
            c, s = abs(math.cos(t)), abs(math.sin(t))
            net = re.search(r'\(net \d+ "([^"]*)"\)', pm.group(8))
            pads.append((pm.group(1), fx + dx, fy + dy, w * c + h * s, w * s + h * c,
                         net.group(1).rsplit("/", 1)[-1] if net else "", pm.group(2)))
        out[ref.group(1)] = dict(lib=lib, layer=layer, x=fx, y=fy, rot=fr, pads=pads)
    return out


def edge_distance(x, y, edge):
    return {"bottom": L.Y1 - y, "top": y - L.Y0, "left": x - L.X0, "right": L.X1 - x}[edge]


def pad_dist(p, q):
    return math.hypot(p[1] - q[1], p[2] - q[2])


def check():
    f = []
    text = open(BOARD, encoding="utf-8").read()
    fps = footprints(text)
    comps, _nets, _padnet = G.read_netlist()
    refs = [c["ref"] for c in comps]

    for r in refs:
        if r not in fps:
            f.append("%s is not placed" % r)
    for r, d in fps.items():
        if r.startswith("H") and d["lib"].startswith("MountingHole:"):
            continue
        if d["layer"] != "F.Cu":
            f.append("%s is on %s, want F.Cu" % (r, d["layer"]))
        for p in d["pads"]:
            if (p[1] - p[3] / 2 < L.X0 or p[1] + p[3] / 2 > L.X1
                    or p[2] - p[4] / 2 < L.Y0 or p[2] + p[4] / 2 > L.Y1):
                f.append("%s pad %s at (%.2f, %.2f) is outside the outline" % (r, p[0], p[1], p[2]))
        if r not in L.OFFBOARD_OK:
            bx0, by0, bx1, by1 = G.box(d["lib"], d["x"], d["y"], d["rot"])
            if bx0 < L.X0 - 1e-6 or by0 < L.Y0 - 1e-6 or bx1 > L.X1 + 1e-6 or by1 > L.Y1 + 1e-6:
                f.append("%s courtyard %.2f..%.2f x %.2f..%.2f leaves the board"
                         % (r, bx0, bx1, by0, by1))

    for r in TAILS:
        d = fps.get(r)
        if d is None:
            continue
        relief = [p for p in d["pads"] if p[0] == "" and p[6] == "np_thru_hole"]
        pts = relief or d["pads"]
        worst = max(edge_distance(p[1], p[2], L.CABLE_EDGE) for p in pts) if relief else \
            min(edge_distance(p[1], p[2], L.CABLE_EDGE) for p in pts)
        if worst > TAIL_REACH:
            f.append("%s exits %.1f mm from the %s edge, want <= %.0f"
                     % (r, worst, L.CABLE_EDGE, TAIL_REACH))

    tps = dict((r, d) for r, d in fps.items() if r.startswith("TP"))
    gnd_tps = [d["pads"][0] for d in tps.values() if d["pads"] and d["pads"][0][5] in GND_NETS]
    boxes = dict((r, G.box(d["lib"], d["x"], d["y"], d["rot"])) for r, d in fps.items()
                 if not r.startswith("TP"))
    for r, d in sorted(tps.items(), key=lambda t: G.natkey(t[0])):
        if d["layer"] != "F.Cu":
            continue  # already reported
        p = d["pads"][0]
        hx0, hy0 = p[1] - p[3] / 2 - TP_HALO, p[2] - p[4] / 2 - TP_HALO
        hx1, hy1 = p[1] + p[3] / 2 + TP_HALO, p[2] + p[4] / 2 + TP_HALO
        for o, (bx0, by0, bx1, by1) in boxes.items():
            if bx0 < hx1 and hx0 < bx1 and by0 < hy1 and hy0 < by1:
                f.append("%s: %s's courtyard is within %.0f mm of the pad" % (r, o, TP_HALO))
        if p[5] not in GND_NETS:
            near = min([pad_dist(p, g) for g in gnd_tps] or [1e9])
            if near > GND_TP_REACH:
                f.append("%s (%s): nearest ground test point is %.1f mm away, want <= %.0f"
                         % (r, p[5], near, GND_TP_REACH))

    for r, (ar, apad), lim in NEAR:
        if r not in fps or ar not in fps:
            continue
        anchor = [p for p in fps[ar]["pads"] if p[0] == apad]
        if not anchor:
            f.append("%s has no pad %s" % (ar, apad))
            continue
        dmin = min(pad_dist(p, anchor[0]) for p in fps[r]["pads"])
        if dmin > lim:
            f.append("%s is %.1f mm from %s pad %s, want <= %.0f" % (r, dmin, ar, apad, lim))
    return f


def main():
    f = check()
    for line in f[:60]:
        print("FAIL " + line)
    if len(f) > 60:
        print("... %d more" % (len(f) - 60))
    print("placement: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
