# -*- coding: utf-8 -*-
"""Generate hardware/programmer/prog.kicad_pcb, prog.kicad_dru and the board half of
prog.kicad_pro from output/netlist.net (plan Task 3).

  python hardware/programmer/scripts/gen_pcb.py

Never edit prog.kicad_pcb in pcbnew: the next run overwrites it.

Layout (20 x 40 mm, 2 layers, all parts top):
  y 100-109  J1 USB-C, mouth at the top edge
  centre     the USB pair, hand-routed (HAND_USB): J1's interleaved A/B rows are joined by two
             short B.Cu bridges, then the pair runs through U2 (ESD) and turns into U1's
             left face.  Its geometry is fixed here, not left to the router.
  left       power: U3 (AMS1117) with its tab on a +3V3_USB pour on both layers, U4 (ideal
             diode) and C4/C5 next to J2 pin 1
  right      U1 (CH343P), its decoupling, R1/R3/R4, the LEDs, U5 (DTR/RTS buffer), R5/R6
  y 136-139  J2, the 1x6 header with the MCCAN J2's pin order
Everything else is routed by route.Router in the fixed order of ROUTE_ORDER, and graded by
DRC and check_board.py.
"""
import json
import math
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(PROG, "..", "scripts"))
import check_netlist  # noqa: E402
import parts  # noqa: E402
import pcblib as P  # noqa: E402
import route  # noqa: E402

PCB = os.path.join(PROG, "prog.kicad_pcb")
DRU = os.path.join(PROG, "prog.kicad_dru")
PRO = os.path.join(PROG, "prog.kicad_pro")
NETLIST = os.path.join(PROG, "output", "netlist.net")

X0, Y0, W, H = 100.0, 100.0, 20.0, 40.0
X1, Y1 = X0 + W, Y0 + H

# ref -> (x, y, rotation)
PLACE = {
    "J1": (110.0, 103.7, 180),
    "U2": (110.0, 115.0, 270),
    "U1": (115.2, 121.0, 270),
    "U3": (103.9, 118.6, 90),
    "U4": (104.3, 129.6, 0),
    "U5": (116.0, 126.5, 0),
    "J2": (103.65, 137.5, 90),
    "C2": (104.5, 110.4, 180),
    "R2": (107.3, 112.5, 270),
    "C1": (106.0, 125.8, 90),
    "C3": (102.6, 125.8, 90),
    "C4": (101.6, 132.6, 90),
    "C5": (107.0, 132.6, 90),
    "R1": (112.65, 111.0, 270),
    "R3": (112.65, 114.0, 270),
    "C8": (112.65, 117.0, 270),
    "R9": (114.35, 111.0, 270),
    "R10": (110.5, 124.6, 0),         # +3V3_USB bleeder, between U3 and U1
    "R4": (114.35, 114.0, 270),
    "C6": (114.95, 117.0, 90),
    "R7": (116.25, 111.0, 270),
    "R8": (116.25, 114.0, 270),
    "C7": (116.55, 117.0, 90),
    "D1": (118.05, 111.0, 270),
    "D2": (118.05, 114.0, 270),
    "D3": (118.05, 117.0, 270),
    "C9": (117.5, 124.0, 0),
    "R5": (113.8, 132.0, 270),
    "R6": (116.4, 132.0, 270),
}

TRACK = 0.2
POWER_W, NECK_W, NECK_R = 0.5, 0.3, 1.4
POWER = ("VBUS", "+3V3_USB", "+3V3_OUT")
USB_W, USB_VIA = 0.2, 0.5

# Hand-routed USB pair (see the module docstring).  J1 rotated 180: pad row at y 107.745;
# B6 D+ 109.25, A7 D- 109.75, A6 D+ 110.25, B7 D- 110.75.  Trunk: A7 (D-) and A6 (D+).
JY = 107.745
HAND_USB = {
    "USB_DN": {"F.Cu": [[(109.75, JY), (109.75, 110.9), (109.05, 111.6), (109.05, 113.8625)],
                        [(110.75, JY), (110.75, 110.2)],
                        [(109.05, 113.8625), (109.05, 121.75), (113.7125, 121.75)]],
               "B.Cu": [[(110.75, 110.2), (109.75, 110.2)]],
               "vias": [(110.75, 110.2), (109.75, 110.2)]},
    "USB_DP": {"F.Cu": [[(110.25, JY), (110.25, 110.9), (110.95, 111.6), (110.95, 113.8625)],
                        [(109.25, JY), (109.25, 109.4)],
                        [(110.95, 113.8625), (110.95, 121.25), (113.7125, 121.25)]],
               "B.Cu": [[(109.25, 109.4), (110.25, 109.4)]],
               "vias": [(109.25, 109.4), (110.25, 109.4)]},
}
# U2's GND (top middle) and VBUS (bottom middle) pins sit between the pair: one via each
HAND_POWER = [("GND", [(110.0, 113.8625), (110.0, 112.55)], (110.0, 112.55)),
              # (VBUS carries the whole load: full power width between the pair)
              ("VBUS", [(110.0, 116.1375), (110.0, 117.45)], (110.0, 117.45), 0.5),
              # U1 pin 2 (GND, top face) into the exposed pad
              ("GND", [(115.45, 119.5125), (115.45, 120.5)], None),
              # U1 VDD5 (top face) straight up to its decoupler C6: the TXD escape beside it
              # leaves no room for the router's wider clearance; narrow only within the
              # neck reach of the QFN pin, power width into C6
              ("VBUS", [(114.95, 119.5125), (114.95, 118.25)], None),
              ("VBUS", [(114.95, 118.25), (114.95, 117.775)], None, 0.5),
              # U5 pin 7 (GND) sits between B_DTR and +3V3_USB: straight out to a via
              ("GND", [(117.7, 126.175), (119.2, 126.175)], (119.2, 126.175))]
# U1's exposed pad: four GND vias in the pad, laid before anything can be routed under it
EP_VIAS = [(115.2 + dx, 121.0 + dy) for dx in (-0.45, 0.45) for dy in (-0.45, 0.45)]

# U3 heatsink: +3V3_USB pours on both layers, tied by thermal vias under the body
HEAT_F = [(100.35, 111.9), (107.0, 111.9), (107.0, 128.2), (100.35, 128.2)]
HEAT_B = [(100.35, 111.9), (106.6, 111.9), (106.6, 127.4), (100.35, 127.4)]
THERMAL_VIAS = [(x, y) for y in (117.6, 119.1) for x in (102.1, 103.6, 105.1)]

# U1's own pins first (they are the hardest to reach once power has gone round them), then
# power, then the GND escapes, then everything else
FIRST = ["V3_U1", "U_RXD", "U_TXD", "U_DTR", "U_RTS", "CC1", "CC2"]
ROUTE_ORDER = FIRST + ["VBUS", "+3V3_USB", "+3V3_OUT",
                       "B_DTR", "B_RTS", "DTR", "RTS", "UART_TX", "UART_RX",
                       "LED_PWR", "LED_TX", "LED_RX"]
N_BEFORE_GND = len(FIRST) + 3
STITCH = [(101.0, 102.0), (119.0, 102.0), (101.0, 108.5), (119.0, 108.5), (119.2, 120.5),
          (110.5, 130.0), (101.0, 139.0), (119.0, 139.0), (110.0, 134.5), (108.5, 127.0)]

# silk: J2 pin labels as seen at the MCCAN board (spec 6.1/6.7)
J2_LABELS = ("3V3", "GND", "TX", "RX", "DTR", "RTS")
LED_LABELS = {"D1": "PWR", "D2": "TX", "D3": "RX"}
TITLE = "MCCAN PROG A"


def load_netlist():
    nl = check_netlist.load(NETLIST)
    text = open(NETLIST, encoding="utf-8").read()
    # the router works in bare names (VBUS); the board carries the schematic's (/VBUS)
    raw = {check_netlist.bare(n): n
           for n in re.findall(r'\(code "\d+"\)\s*\(name "([^"]*)"', text)}
    return nl, P.netlist_tstamps(text), raw


def pad_rects(ref):
    """[(num, (x0, y0, x1, y1), layers, kind)] for a placed footprint."""
    spec = parts.PARTS[ref]["footprint"]
    x, y, rot = PLACE[ref]
    out = []
    for n, px, py, w, h, kind in P.pads_of(spec):
        dx, dy = P.rot_local(px, py, rot)
        if rot % 180:
            w, h = h, w
        cx, cy = x + dx, y + dy
        layers = ("F.Cu", "B.Cu") if kind in ("thru_hole", "np_thru_hole") else ("F.Cu",)
        out.append((n, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), layers, kind))
    return out


def courtyard(ref):
    spec = parts.PARTS[ref]["footprint"]
    x, y, rot = PLACE[ref]
    pts = []
    for g in P.load_fp(spec):
        if isinstance(g, list) and g and g[0] in ("fp_line", "fp_rect") and \
                P.unq(P.find(g, "layer")[1]) == "F.CrtYd":
            for k in ("start", "end"):
                c = P.find(g, k)
                dx, dy = P.rot_local(float(c[1]), float(c[2]), rot)
                pts.append((x + dx, y + dy))
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def check_placement():
    refs = sorted(PLACE)
    assert set(refs) == set(parts.PARTS), sorted(set(refs) ^ set(parts.PARTS))
    bad = []
    for i, a in enumerate(refs):
        ca = courtyard(a)
        for b in refs[i + 1:]:
            cb = courtyard(b)
            if ca[0] < cb[2] and cb[0] < ca[2] and ca[1] < cb[3] and cb[1] < ca[3]:
                bad.append((a, b))
    assert not bad, "courtyard overlaps: %s" % bad


def build():
    check_placement()
    nl, tstamps, raw = load_netlist()
    names = sorted(nl.nets)
    code = {n: k + 1 for k, n in enumerate(names)}
    R = route.Router(X0, Y0, X1, Y1)
    padcells = {}       # net -> {(i, j, layer)}

    def cells_in(box, layers):
        # the pad's inscribed square, so a round or oval pad's corners are not counted
        s = 0.15 * min(box[2] - box[0], box[3] - box[1])
        box = (box[0] + s, box[1] + s, box[2] - s, box[3] - s)
        i0, j0 = R.ij(box[0], box[1])
        i1, j1 = R.ij(box[2], box[3])
        out = set()
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                x, y = R.xy(i, j)
                if box[0] + 1e-6 < x < box[2] - 1e-6 and box[1] + 1e-6 < y < box[3] - 1e-6:
                    out |= {(i, j, L) for L in layers}
        return out

    pad_groups = {}     # net -> [(ref, num, cells, min side)]
    for ref in PLACE:
        for n, box, layers, kind in pad_rects(ref):
            if kind == "np_thru_hole":
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                # hole clearance (0.25) exceeds copper clearance: widen the keep-out
                R.add(route.Shape(None, route.LAYERS, "disc", (cx, cy),
                                  r=(box[2] - box[0]) / 2 + 0.1))
                continue
            net = nl.net_of(ref, n)
            R.add(route.Shape(net, layers, "rect", box))
            if net:
                cs = cells_in(box, layers)
                pad_groups.setdefault(net, []).append((ref, n, cs, min(box[2] - box[0],
                                                                         box[3] - box[1]),
                                                       ((box[0] + box[2]) / 2,
                                                        (box[1] + box[3]) / 2)))

    # ---- fixed copper: USB pair, U2's power vias, U3 thermal vias
    for net, d in HAND_USB.items():
        for L in ("F.Cu", "B.Cu"):
            for poly in d[L]:
                for a, b in zip(poly, poly[1:]):
                    R.add_track(net, L, a, b, USB_W)
        for v in d["vias"]:
            R.add_via(net, v, USB_VIA)
    for net, poly, v, *wd in HAND_POWER:
        for a, b in zip(poly, poly[1:]):
            R.add_track(net, "F.Cu", a, b, wd[0] if wd else NECK_W)
        if v:
            R.add_via(net, v)
    for v in THERMAL_VIAS:
        R.add_via("+3V3_USB", v)
    for v in EP_VIAS:
        R.add_via("GND", v, USB_VIA)

    # ---- routed nets: grow a tree from the first pad to each next-nearest pad
    failed = []

    def cells_of(tracks, vias):
        out = set()
        for L, a, b in tracks:
            ia, ja = R.ij(*a)
            ib, jb = R.ij(*b)
            steps = max(abs(ib - ia), abs(jb - ja), 1)
            for k in range(steps + 1):
                out.add((ia + round((ib - ia) * k / steps), ja + round((jb - ja) * k / steps), L))
        for p in vias:
            i, j = R.ij(*p)
            out |= {(i, j, "F.Cu"), (i, j, "B.Cu")}
        return out

    def own_cells(net):
        return cells_of([(L, a, b) for n2, L, a, b, _w in R.tracks if n2 == net],
                        [p for n2, p, _s in R.vias if n2 == net])

    def route_nets(nets):
        for net in nets:
            groups = sorted(pad_groups[net], key=lambda g: (g[0], g[1]))
            power = net in POWER
            w = POWER_W if power else TRACK
            neck = None
            if power:
                nc = set()
                for _r, _n, _cs, side, (cx, cy) in groups:
                    if side < POWER_W:
                        i0, j0 = R.ij(cx - NECK_R, cy - NECK_R)
                        i1, j1 = R.ij(cx + NECK_R, cy + NECK_R)
                        for i in range(i0, i1 + 1):
                            for j in range(j0, j1 + 1):
                                x, y = R.xy(i, j)
                                if math.hypot(x - cx, y - cy) <= NECK_R:
                                    nc.add((i, j))
                neck = (NECK_W, nc)
            # each piece of fixed copper is a target in its own right: two hand stubs of one
            # net are not connected to each other until a route joins them.  Items that
            # already touch are merged first.
            items = [set(g[2]) for g in groups]
            for pn, poly, v, *_w in HAND_POWER:
                if pn == net:
                    items.append(cells_of([("F.Cu", a, b) for a, b in zip(poly, poly[1:])],
                                          [v] if v else []))
            clusters = []
            for it in items:
                hit = [c for c in clusters if c & it]
                for c in hit:
                    clusters.remove(c)
                    it |= c
                clusters.append(it)
            first = next(c for c in clusters if c & groups[0][2])
            tree = set(first)
            centre0 = groups[0][4]

            def centre(cs):
                return (sum(R.xy(i, j)[0] for i, j, _L in cs) / len(cs),
                        sum(R.xy(i, j)[1] for i, j, _L in cs) / len(cs))
            todo = [(None, None, c, None, centre(c)) for c in clusters if c is not first]
            while todo:
                # nearest remaining pad to the tree's first pad
                g = min(todo, key=lambda g: abs(g[4][0] - centre0[0]) + abs(g[4][1] - centre0[1]))
                todo.remove(g)
                if g[2] & tree:
                    continue
                path = R.route(net, tree, g[2], w, neck)
                if path is None:
                    failed.append("%s: near (%.2f, %.2f)" % (net, g[4][0], g[4][1]))
                    continue
                nv = len(R.vias)
                made = R.commit(net, path, w, neck)
                # the committed (smoothed) copper, not the raw cell path
                tree |= g[2] | cells_of([(L, a, b) for _n, L, a, b, _w in made],
                                        [p for _n, p, _s in R.vias[nv:]])


    route_nets(ROUTE_ORDER[:N_BEFORE_GND])

    # ---- GND: every SMD GND pad gets a short escape to a via (both pours then join them)
    def in_poly(p, poly):
        x, y = p
        c = False
        for k in range(len(poly)):
            (xa, ya), (xb, yb) = poly[k], poly[k - 1]
            if (ya > y) != (yb > y) and x < (xb - xa) * (y - ya) / (yb - ya) + xa:
                c = not c
        return c

    for ref, n, cs, _side, centre in sorted(pad_groups["GND"], key=lambda g: (g[0], g[1])):
        if any(L == "B.Cu" for _i, _j, L in cs):
            continue            # through-hole: already on both layers
        if cs & own_cells("GND"):
            continue            # already tied to a GND via by the fixed copper (U1 pin 2, EP)
        vblk = R.blocked("GND", route.VIA / 2.0, "F.Cu") | R.blocked("GND", route.VIA / 2.0, "B.Cu")
        blk = R.blocked("GND", NECK_W / 2.0, "F.Cu")
        # breadth-first from the pad to the nearest legal via spot: off the pad itself (no
        # via-in-pad) and outside HEAT_B, where B.Cu is +3V3_USB rather than GND
        start = {(i, j) for i, j, _L in cs}
        pi0 = min(i for i, _j in start) - int(0.35 / route.G)
        pi1 = max(i for i, _j in start) + int(0.35 / route.G)
        pj0 = min(j for _i, j in start) - int(0.35 / route.G)
        pj1 = max(j for _i, j in start) + int(0.35 / route.G)
        gvias = [R.ij(*p) for n2, p, _s in R.vias if n2 == "GND"]
        seen = {s: None for s in start}
        frontier = sorted(start)
        hit, reuse = None, False
        while frontier and hit is None:
            nxt = []
            for c in frontier:
                on_pad = pi0 <= c[0] <= pi1 and pj0 <= c[1] <= pj1
                near = [v for v in gvias if abs(v[0] - c[0]) + abs(v[1] - c[1]) <= 2]
                if near and not in_poly(R.xy(*c), HEAT_B):
                    hit, reuse = c, True      # an existing GND via: join it
                    break
                spaced = all(math.hypot(v[0] - c[0], v[1] - c[1]) * route.G >= 0.9
                             for v in gvias)
                if not on_pad and spaced and c not in vblk and not in_poly(R.xy(*c), HEAT_B):
                    hit = c
                    break
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        m = (c[0] + di, c[1] + dj)
                        if m not in seen and (m not in blk or m in start):
                            seen[m] = c
                            nxt.append(m)
            frontier = nxt
        if hit is None:
            failed.append("GND: %s.%s (no via spot)" % (ref, n))
            continue
        path = []
        c = hit
        while c is not None:
            path.append((c[0], c[1], "F.Cu"))
            c = seen[c]
        path = path[::-1]
        R._maps = ({"F.Cu": blk, "B.Cu": blk}, None)
        R.commit("GND", path, NECK_W)
        if not reuse:
            R.add_via("GND", R.xy(*hit))

    route_nets(ROUTE_ORDER[N_BEFORE_GND:])

    # ---- stitching vias where they fit
    vfree = R.blocked("GND", route.VIA / 2.0, "F.Cu") | R.blocked("GND", route.VIA / 2.0, "B.Cu")
    for p in STITCH:
        if R.ij(*p) not in vfree and not in_poly(p, HEAT_B):
            R.add_via("GND", p)

    write(nl, tstamps, names, code, R, raw)
    return failed


def write(nl, tstamps, names, code, R, raw):
    out = []
    A = out.append
    A("(kicad_pcb")
    A("\t(version 20241229)")
    A('\t(generator "prog-gen_pcb.py")')
    A('\t(generator_version "9.0")')
    A("\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)")
    A('\t(paper "A4")')
    A('\t(title_block\n\t\t(title "MCCAN programmer")\n\t\t(date "2026-11-14")\n\t\t(rev "A")\n'
      '\t\t(comment 1 "GENERATED by hardware/programmer/scripts/gen_pcb.py -- do not edit")\n\t)')
    A("\t(layers\n\t\t(0 \"F.Cu\" signal)\n\t\t(2 \"B.Cu\" signal)\n"
      "\t\t(9 \"F.Adhes\" user \"F.Adhesive\")\n\t\t(11 \"B.Adhes\" user \"B.Adhesive\")\n"
      "\t\t(13 \"F.Paste\" user)\n\t\t(15 \"B.Paste\" user)\n"
      "\t\t(5 \"F.SilkS\" user \"F.Silkscreen\")\n\t\t(7 \"B.SilkS\" user \"B.Silkscreen\")\n"
      "\t\t(1 \"F.Mask\" user)\n\t\t(3 \"B.Mask\" user)\n"
      "\t\t(17 \"Dwgs.User\" user \"User.Drawings\")\n\t\t(19 \"Cmts.User\" user \"User.Comments\")\n"
      "\t\t(25 \"Edge.Cuts\" user)\n\t\t(27 \"Margin\" user)\n"
      "\t\t(31 \"F.CrtYd\" user \"F.Courtyard\")\n\t\t(29 \"B.CrtYd\" user \"B.Courtyard\")\n"
      "\t\t(35 \"F.Fab\" user)\n\t\t(33 \"B.Fab\" user)\n\t)")
    A("\t(setup\n\t\t(stackup\n"
      '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))\n'
      '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))\n'
      '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))\n'
      '\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))\n'
      '\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") '
      '(epsilon_r 4.5) (loss_tangent 0.02))\n'
      '\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))\n'
      '\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))\n'
      '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))\n'
      '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))\n'
      '\t\t\t(copper_finish "HAL lead-free")\n\t\t\t(dielectric_constraints no)\n\t\t)\n'
      "\t\t(pad_to_mask_clearance 0)\n\t\t(allow_soldermask_bridges_in_footprints no)\n"
      "\t\t(tenting front back)\n\t)")
    A('\t(net 0 "")')
    for n in names:
        A('\t(net %d %s)' % (code[n], P.q(raw[n])))
    for ref in sorted(PLACE, key=lambda r: (r[0], int(r[1:]))):
        e = parts.PARTS[ref]
        x, y, rot = PLACE[ref]
        padnet = {pin: (code[net], raw[net]) for pin, net in nl.part_pins[ref].items()}
        fp = P.footprint(e["footprint"], ref, e["value"], x, y, rot, padnet,
                         "/" + tstamps[ref], "prog.kicad_sch",
                         fields=[("LCSC", e["lcsc"]), ("MPN", e["mpn"])])
        A("\t" + P.dump(fp, 2))
    for k, (net, L, a, b, w) in enumerate(R.tracks):
        A(P.segment(a, b, w, L, code[net], "seg%d" % k))
    for k, (net, p, size) in enumerate(R.vias):
        A(P.via(p, size, route.VIA_DRILL, code[net], "via%d" % k))
    # pours: GND on both layers; +3V3_USB heatsink above them
    edge = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    A(P.zone(code["GND"], raw["GND"], "F.Cu", edge, 0, "zgndF"))
    A(P.zone(code["GND"], raw["GND"], "B.Cu", edge, 0, "zgndB"))
    A(P.zone(code["+3V3_USB"], raw["+3V3_USB"], "F.Cu", HEAT_F, 1, "zheatF", solid=True))
    A(P.zone(code["+3V3_USB"], raw["+3V3_USB"], "B.Cu", HEAT_B, 1, "zheatB", solid=True))
    for it in P.rounded_rect(X0, Y0, X1, Y1, 1.0, "Edge.Cuts", 0.1, "edge"):
        A(it)
    # silk
    jx, jy, _r = PLACE["J2"]
    for k, lab in enumerate(J2_LABELS):
        A(P.gr_text(lab, (jx + 2.54 * k, jy - 2.2), "F.SilkS", 0.8, "j2lab%d" % k,
                    thick=0.15))
    # pin-1 arrow left of the header outline, pointing at pin 1
    A(P.gr_poly([(jx - 2.75, jy - 0.45), (jx - 2.75, jy + 0.45), (jx - 2.05, jy)], "F.SilkS",
                "pin1"))
    for ref, lab in LED_LABELS.items():
        x, y, _r = PLACE[ref]
        A(P.gr_text(lab, (119.4, y), "F.SilkS", 0.8, "led" + ref, rot=90, thick=0.15))
    A(P.gr_text(TITLE, (119.3, 131.5), "F.SilkS", 0.9, "title", rot=90, thick=0.15))
    A(")")
    with open(PCB, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    write_rules()


def write_rules():
    with open(DRU, "w", encoding="utf-8", newline="\n") as f:
        f.write("(version 1)\n\n"
                "# GENERATED by hardware/programmer/scripts/gen_pcb.py -- do not edit.\n"
                "# JLCPCB standard 2-layer limits (2026-11): 0.127 mm track/space, 0.3 mm via\n"
                "# drill.  The board's own rules (prog.kicad_pro) sit at or above them:\n"
                "# 0.13 mm clearance, 0.15 mm track, 0.5/0.3 mm via, 0.3 mm copper to edge.\n\n"
                "# USB-C receptacle: its two pad rows are fixed by the manufacturer at 0.2 mm\n"
                "(rule \"J1 land pattern\"\n"
                "\t(constraint clearance (min 0.12mm))\n"
                "\t(condition \"A.memberOfFootprint('J1') && B.memberOfFootprint('J1')\"))\n\n"
                "# USB-C mouth: the receptacle overhangs the edge by design (spec 6.1), so its\n"
                "# body outline is printed up to the edge and the fab clips it there\n"
                "(rule \"J1 silk at the mouth\"\n"
                "\t(constraint silk_clearance (min 0mm))\n"
                "\t(severity ignore)\n"
                "\t(condition \"A.memberOfFootprint('J1') && A.Layer == 'F.SilkS'\"))\n\n"
                "# a pad squeezed between fine-pitch neighbours may land on the pour with one\n"
                "# spoke; the pad's own GND escape via carries it\n"
                "(rule \"one spoke\"\n"
                "\t(constraint min_resolved_spokes 1))\n")
    pro = {
        "board": {"design_settings": {
            "defaults": {"silk_line_width": 0.15, "silk_text_size_h": 0.9,
                         "silk_text_size_v": 0.9, "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.13, "min_track_width": 0.15,
                      "min_via_diameter": 0.5, "min_via_annular_width": 0.1,
                      "min_through_hole_diameter": 0.3, "min_hole_clearance": 0.25,
                      "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3,
                      "min_silk_clearance": 0.0, "min_text_height": 0.8,
                      "min_text_thickness": 0.12, "solder_mask_to_copper_clearance": 0.0}}},
        "meta": {"filename": "prog.kicad_pro", "version": 3},
        "net_settings": {"classes": [{
            "name": "Default", "clearance": 0.13, "track_width": 0.2,
            "via_diameter": 0.6, "via_drill": 0.3, "microvia_diameter": 0.3,
            "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647}],
            "meta": {"version": 4}},
    }
    with open(PRO, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    import time
    t = time.time()
    failed = build()
    print("wrote %s in %.0f s" % (PCB, time.time() - t))
    for x in failed:
        print("UNROUTED", x)
    sys.exit(1 if failed else 0)
