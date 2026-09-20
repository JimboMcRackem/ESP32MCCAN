# -*- coding: utf-8 -*-
"""Generate hardware/mccan.kicad_pcb from output/netlist.net + fpmap.py + layout_pcb.py.

kicad-cli has no "create board from schematic" -- its `pcb` verbs are only
{drc, export, import, render, upgrade} -- so the board is authored as text, exactly like the
schematic sheets.  Re-run this after any schematic change:

    cd hardware
    "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist -o output/netlist.net mccan.kicad_sch
    python scripts/gen_pcb.py

Everything here is derived, nothing is remembered: footprint bodies are copied out of the
.kicad_mod libraries at generation time, nets come from the netlist, and placement comes from
layout_pcb.py.  **Never edit mccan.kicad_pcb in pcbnew** -- the next run will overwrite it.

Placement is grid-occupancy based: hand placements from layout_pcb.PLACE are stamped into a
0.5 mm occupancy grid first (plus KEEPCLEAR haloes), then every remaining part is flowed into
its region at the first free slot that fits its courtyard.  That guarantees no courtyard
overlap, which is the one placement error DRC will otherwise report 200 times.
"""

import array as _array
import copy
import heapq as _heapq
import io
import math
import os
import re
import sys
import time as _time
import uuid as _uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_pcb as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
NETLIST = os.path.join(HW, "output", "netlist.net")
BOARD = os.path.join(HW, "mccan.kicad_pcb")

NS = _uuid.UUID("6f1d5a7c-0b2e-4a91-9c33-mccanpcb0001".replace("mccanpcb0001", "8c33aa01b7d2"))


# --------------------------------------------------------------------------- s-expressions
def parse(s):
    """Parse one s-expression into nested lists.  Atoms keep their raw text, quotes included."""
    i = [0]
    n = len(s)

    def skip():
        while i[0] < n and s[i[0]] in " \t\r\n":
            i[0] += 1

    def node():
        i[0] += 1                      # consume '('
        out = []
        while True:
            skip()
            c = s[i[0]]
            if c == ")":
                i[0] += 1
                return out
            if c == "(":
                out.append(node())
                continue
            j = i[0]
            if c == '"':
                i[0] += 1
                while s[i[0]] != '"':
                    if s[i[0]] == "\\":
                        i[0] += 1
                    i[0] += 1
                i[0] += 1
            else:
                while s[i[0]] not in ' \t\r\n()':
                    i[0] += 1
            out.append(s[j:i[0]])

    skip()
    return node()


def dump(node, indent=1):
    """Serialise back.  All-atom nodes stay on one line, mixed nodes break like KiCad's own."""
    if isinstance(node, str):
        return node
    if all(isinstance(c, str) for c in node):
        return "(" + " ".join(node) + ")"
    pad = "\t" * indent
    head = []
    tail = []
    seen_list = False
    for c in node:
        if isinstance(c, str) and not seen_list:
            head.append(c)
        else:
            seen_list = True
            tail.append(c)
    out = "(" + " ".join(head) if head else "("
    for c in tail:
        out += "\n" + pad + dump(c, indent + 1)
    out += "\n" + "\t" * (indent - 1) + ")"
    return out


def find(node, head):
    for c in node:
        if isinstance(c, list) and c and c[0] == head:
            return c
    return None


def find_all(node, head):
    return [c for c in node if isinstance(c, list) and c and c[0] == head]


def unq(a):
    return a[1:-1] if len(a) > 1 and a[0] == '"' else a


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def num(v):
    t = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if t in ("", "-0") else t


# --------------------------------------------------------------------------- netlist
def read_netlist():
    t = io.open(NETLIST, encoding="utf-8").read()
    root = parse(t)

    comps = []
    comp_sec = find(root, "components")
    for c in find_all(comp_sec, "comp"):
        ref = unq(find(c, "ref")[1])
        val = unq(find(c, "value")[1])
        fp_n = find(c, "footprint")
        fp = unq(fp_n[1]) if fp_n and len(fp_n) > 1 else ""
        sheetname = sheetfile = ""
        for p in find_all(c, "property"):
            nm = unq(find(p, "name")[1])
            vn = find(p, "value")
            if nm == "Sheetname":
                sheetname = unq(vn[1]) if vn and len(vn) > 1 else ""
            elif nm == "Sheetfile":
                sheetfile = unq(vn[1]) if vn and len(vn) > 1 else ""
        sp = find(c, "sheetpath")
        spath = unq(find(sp, "tstamps")[1]) if sp else "/"
        ts = unq(find(c, "tstamps")[1])
        comps.append(dict(ref=ref, value=val, fp=fp, sheetname=sheetname,
                          sheetfile=sheetfile, path=spath + ts))

    nets = []            # (code, name)
    padnet = {}          # (ref, pin) -> code
    for net in find_all(find(root, "nets"), "net"):
        code = int(unq(find(net, "code")[1]))
        name = unq(find(net, "name")[1])
        nets.append((code, name))
        for nd in find_all(net, "node"):
            padnet[(unq(find(nd, "ref")[1]), unq(find(nd, "pin")[1]))] = code
    return comps, nets, padnet


# --------------------------------------------------------------------------- footprints
def fp_path(spec):
    lib, _, name = spec.partition(":")
    if lib == "mccan":
        return os.path.join(HW, "footprints", "mccan.pretty", name + ".kicad_mod")
    return os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod")


_FP_CACHE = {}


def load_fp(spec):
    if spec not in _FP_CACHE:
        p = fp_path(spec)
        if not os.path.exists(p):
            _FP_CACHE[spec] = None
        else:
            _FP_CACHE[spec] = parse(io.open(p, encoding="utf-8").read())
    return _FP_CACHE[spec]


def rot_local(x, y, deg):
    """Footprint-local (x, y) -> board-relative offset for a footprint rotated by `deg`."""
    t = math.radians(deg)
    c, s_ = math.cos(t), math.sin(t)
    return (x * c + y * s_, -x * s_ + y * c)


COURTYARDS = ("F.CrtYd", "B.CrtYd")


def extent(spec):
    """Courtyard bounding box as (w, h, ox, oy) in mm, falling back to the pad bbox + 0.5 mm.

    **(ox, oy) is the offset of the box centre from the footprint ORIGIN, and it is not always
    zero.** SolderWire, the Wurth choke and plenty of stock parts put their origin on pad 1,
    not on the centroid. Treating a placement coordinate as the centre of the box regardless
    silently shifts every occupancy test by half a part -- which is how J7 pad 3 ended up
    sitting on top of J8 pad 1 with DRC calling it a GND/CANH short."""
    fp = load_fp(spec)
    if fp is None:
        return (2.0, 2.0, 0.0, 0.0)
    pts = []
    pads = []
    for c in fp:
        if not isinstance(c, list) or not c:
            continue
        lay = find(c, "layer") or find(c, "layers")
        on_crtyd = lay is not None and any(unq(a) in COURTYARDS for a in lay[1:]
                                           if isinstance(a, str))
        if c[0] in ("fp_line", "fp_rect", "fp_circle", "fp_arc") and on_crtyd:
            for k in ("start", "end", "center", "mid"):
                s = find(c, k)
                if s:
                    pts.append((float(s[1]), float(s[2])))
        elif c[0] == "fp_poly" and on_crtyd:
            for xy in find_all(find(c, "pts"), "xy"):
                pts.append((float(xy[1]), float(xy[2])))
        elif c[0] == "pad":
            at = find(c, "at")
            sz = find(c, "size")
            if at and sz:
                x, y = float(at[1]), float(at[2])
                w, h = float(sz[1]), float(sz[2])
                pads += [(x - w / 2, y - h / 2), (x + w / 2, y + h / 2)]
    use = pts or pads
    if not use:
        return (2.0, 2.0, 0.0, 0.0)
    xs = [p[0] for p in use]
    ys = [p[1] for p in use]
    m = 0.0 if pts else 0.25
    x0, x1 = min(xs) - m, max(xs) + m
    y0, y1 = min(ys) - m, max(ys) + m
    return (x1 - x0, y1 - y0, (x0 + x1) / 2.0, (y0 + y1) / 2.0)


def box(spec, cx, cy, rot):
    """Board-coordinate bounding box of a footprint's courtyard, origin offset included."""
    w, h, ox, oy = extent(spec)
    ox, oy = rot_local(ox, oy, rot)
    if rot % 180:
        w, h = h, w
    return (cx + ox - w / 2, cy + oy - h / 2, cx + ox + w / 2, cy + oy + h / 2)


SKIP_CHILD = ("version", "generator", "generator_version", "layer", "at", "path",
              "sheetname", "sheetfile", "uuid", "tstamp", "embedded_fonts")


def reuuid(node, ref, ctr):
    if not isinstance(node, list):
        return
    if node and node[0] == "uuid" and len(node) > 1:
        ctr[0] += 1
        node[1] = q(str(_uuid.uuid5(NS, "%s#%d" % (ref, ctr[0]))))
    for c in node:
        reuuid(c, ref, ctr)


def addrot(at, rot):
    """Absolute-ise an (at x y [a]) node for a footprint rotated by `rot`."""
    a = float(at[3]) if len(at) > 3 else 0.0
    a = (a + rot) % 360.0
    if a == 0.0:
        del at[3:]
    else:
        at[3:] = [num(a)]


def build_footprint(c, x, y, rot, padnet):
    spec = c["fp"]
    lib = load_fp(spec)
    if lib is None:
        return None
    body = copy.deepcopy(lib)

    keep = []
    props = []
    for ch in body[2:] if isinstance(body[1], str) else body[1:]:
        if isinstance(ch, str):
            continue
        if ch[0] in SKIP_CHILD:
            continue
        if ch[0] == "property":
            props.append(ch)
        else:
            keep.append(ch)

    # Reference and Value carry the real designator, not REF** / the library name.
    for p in props:
        nm = unq(p[1])
        if nm == "Reference":
            p[2] = q(c["ref"])
        elif nm == "Value":
            p[2] = q(c["value"])
        elif nm == "Footprint":
            p[2] = q(spec)

    # Every (at) that belongs to something orientable becomes absolute.
    for ch in props + keep:
        if ch[0] in ("property", "fp_text", "fp_text_box", "pad", "model"):
            at = find(ch, "at")
            if at and ch[0] != "model":
                addrot(at, rot)

    # Nets onto the pads.
    for p in keep:
        if p[0] != "pad":
            continue
        pn = unq(p[1])
        code = padnet.get((c["ref"], pn))
        if code is None:
            continue
        name = NETNAME[code]
        layers = find(p, "layers")
        idx = p.index(layers) + 1 if layers is not None else len(p)
        p.insert(idx, ["net", str(code), q(name)])

    out = ["footprint", q(spec),
           ["layer", '"F.Cu"'],
           ["uuid", q(str(_uuid.uuid5(NS, c["ref"])))],
           ["at", num(x), num(y)] + ([num(rot)] if rot else [])]
    # descr / tags first, then properties, then path/sheet identity, then attr + geometry
    for h in ("descr", "tags"):
        n = [k for k in keep if k[0] == h]
        for k in n:
            out.append(k)
            keep.remove(k)
    out += props
    out.append(["path", q(c["path"])])
    out.append(["sheetname", q(c["sheetname"])])
    out.append(["sheetfile", q(c["sheetfile"])])
    out += keep

    ctr = [0]
    for ch in out:
        if isinstance(ch, list) and ch[0] != "uuid":
            reuuid(ch, c["ref"], ctr)
    return out


# --------------------------------------------------------------------------- placement
RES = 0.5          # occupancy grid pitch, mm
GUT = 0.4          # gutter between auto-flowed courtyards, mm


class Grid(object):
    def __init__(self):
        self.w = int((L.X1 - L.X0) / RES) + 1
        self.h = int((L.Y1 - L.Y0) / RES) + 1
        self.g = bytearray(self.w * self.h)

    def _idx(self, cx, cy):
        return cy * self.w + cx

    def cells(self, x0, y0, x1, y1):
        a = max(0, int((x0 - L.X0) / RES))
        b = max(0, int((y0 - L.Y0) / RES))
        cx = min(self.w - 1, int((x1 - L.X0) / RES))
        cy = min(self.h - 1, int((y1 - L.Y0) / RES))
        return a, b, cx, cy

    def mark(self, x0, y0, x1, y1):
        a, b, cx, cy = self.cells(x0, y0, x1, y1)
        for j in range(b, cy + 1):
            base = j * self.w
            for i in range(a, cx + 1):
                self.g[base + i] = 1

    def free(self, x0, y0, x1, y1):
        if x0 < L.X0 or y0 < L.Y0 or x1 > L.X1 or y1 > L.Y1:
            return False
        a, b, cx, cy = self.cells(x0, y0, x1, y1)
        for j in range(b, cy + 1):
            base = j * self.w
            for i in range(a, cx + 1):
                if self.g[base + i]:
                    return False
        return True


def fp_keepouts(spec, cx, cy, rot):
    """Bounding boxes of any keep-out zones embedded in the footprint, in board coordinates.

    The stock ESP32-WROOM-32E footprint carries its own all-layer antenna keep-out.  It is the
    datasheet-correct one, so it is used as-is rather than re-drawn -- but the placer has to
    know about it, or parts get flowed into the one rectangle DRC will not allow them in."""
    fp = load_fp(spec)
    if fp is None:
        return []
    out = []
    for c in fp:
        if not isinstance(c, list) or not c or c[0] != "zone":
            continue
        if find(c, "keepout") is None:
            continue
        poly = find(c, "polygon")
        if poly is None:
            continue
        pts = [rot_local(float(xy[1]), float(xy[2]), rot)
               for xy in find_all(find(poly, "pts"), "xy")]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        out.append((cx + min(xs), cy + min(ys), cx + max(xs), cy + max(ys)))
    return out


def natkey(ref):
    m = re.match(r"([A-Za-z_]+)(\d*)", ref)
    return (m.group(1), int(m.group(2) or 0))


def place(comps):
    grid = Grid()
    pos = {}

    by_ref = dict((c["ref"], c) for c in comps)

    # Board furniture is an obstacle too, and it is seeded into `hand` rather than merely
    # stamped on the grid: the grid only steers the auto-flow, so a mounting hole that a HAND
    # placement sits on top of would otherwise reach DRC unannounced.  H1 under the CM choke
    # and H3 under J1 both did exactly that.
    hand = {}
    for i, (mx, my) in enumerate(mount_holes()):
        w, h, ox, oy = extent(MOUNT_FP)
        hand["H%d" % (i + 1)] = (mx + ox - w / 2, my + oy - h / 2,
                                 mx + ox + w / 2, my + oy + h / 2)
        grid.mark(mx - 3.5, my - 3.5, mx + 3.5, my + 3.5)

    for ref, (x, y, rot) in L.PLACE.items():
        c = by_ref.get(ref)
        if c is None:
            print("  WARN: PLACE has %s, which is not in the netlist" % ref)
            continue
        bx0, by0, bx1, by1 = box(c["fp"], x, y, rot)
        halo = L.KEEPCLEAR.get(ref, 0.0)
        for other, ob in hand.items():
            if bx0 < ob[2] and ob[0] < bx1 and by0 < ob[3] and ob[1] < by1:
                print("  ERROR: hand placements %s and %s overlap" % (ref, other))
        if ref not in L.OFFBOARD_OK and (
                bx0 < L.X0 or by0 < L.Y0 or bx1 > L.X1 or by1 > L.Y1):
            print("  ERROR: %s courtyard %.2f..%.2f x %.2f..%.2f leaves the board"
                  % (ref, bx0, bx1, by0, by1))
        hand[ref] = (bx0, by0, bx1, by1)
        pos[ref] = (x, y, rot)
        grid.mark(bx0 - halo, by0 - halo, bx1 + halo, by1 + halo)
        for kx0, ky0, kx1, ky1 in fp_keepouts(c["fp"], x, y, rot):
            grid.mark(kx0, ky0, kx1, ky1)

    leftovers = []
    for c in sorted(comps, key=lambda c: natkey(c["ref"])):
        if c["ref"] in pos:
            continue
        region = L.BLOCK.get(c["ref"]) or L.SHEET_REGION.get(c["sheetname"])
        leftovers.append((region, c))
    # Largest first.  A row-major bottom-left packer strands the big parts if they arrive after
    # the small ones have already fragmented the space -- which is how a SOIC-8 ended up being
    # exiled from the MCU block into the input filter.
    def area(c):
        w, h, _ox, _oy = extent(c["fp"])
        return -(w + GUT) * (h + GUT)
    leftovers.sort(key=lambda rc: (rc[0] or "", area(rc[1]), natkey(rc[1]["ref"])))

    unplaced = []
    for region, c in leftovers:
        w, h, ox, oy = extent(c["fp"])
        w += GUT
        h += GUT
        got = None
        others = sorted((r for r in L.REGIONS if r != region), key=lambda r: near(region, r))
        for rgn in ([region] if region else []) + others:
            x0, y0, x1, y1 = L.REGIONS[rgn]
            y = y0
            while y + h <= y1 and got is None:
                x = x0
                while x + w <= x1:
                    if grid.free(x, y, x + w, y + h):
                        got = (rgn, x + w / 2 - ox, y + h / 2 - oy, w, h)
                        break
                    x += RES
                y += RES
            if got:
                break
        if got is None:
            unplaced.append(c["ref"])
            continue
        rgn, cx, cy, w, h = got
        pos[c["ref"]] = (cx, cy, 0)
        grid.mark(cx + ox - w / 2, cy + oy - h / 2, cx + ox + w / 2, cy + oy + h / 2)
        if rgn != region:
            print("  NOTE: %s spilled out of '%s' into '%s'" % (c["ref"], region, rgn))
    return pos, unplaced, grid


MOUNT_FP = "MountingHole:MountingHole_3.2mm_M3"

# --------------------------------------------------------------------------- vias
#
# Thermal vias are 0.5 / 0.25 mm, not the 0.8 / 0.4 used for stitching.  A small via is the
# right one here: the array has to fit INSIDE a pad that may be only 1.675 mm square (U3's
# QFN paddle), and thermal resistance falls with via COUNT far faster than with via diameter
# -- the barrel is a 25 um copper tube either way, so a 0.5 mm via has about 60 % of the
# copper cross-section of a 0.8 mm one but four of them fit where one did.
THERM_VIA, THERM_DRILL = 0.5, 0.25
THERM_PITCH = 0.8
THERM_MARGIN = 0.15     # mm of pad copper left outside the via annulus

# What counts as an exposed thermal pad.  This is deliberately strict, because a via in a pad
# is a MANUFACTURING decision, not just a copper one: an unplugged via in a solderable pad
# wicks paste out of the joint during reflow.  On a QFN/VSON paddle or a diode tab that is a
# solved problem -- the fab plugs and caps them and every app note assumes it -- but in the
# terminal pad of a 1210 capacitor it is a tombstoning defect waiting to happen.  So a pad
# qualifies only if it looks like a paddle: big in BOTH directions, and far bigger than any
# other pad on the same part.  That keeps C3, L1 and D3 out, whose two pads are the same size
# as each other; their plane connections are stitched beside the pad when Task 9 routes them.
THERM_MIN_AREA = 2.5    # mm^2
THERM_MIN_SIDE = 1.5    # mm on the SHORT side -- a 1.15 mm chip pad is not a paddle
THERM_DOMINANCE = 2.0   # times the next-largest pad on the same footprint

STITCH_VIA, STITCH_DRILL = 0.8, 0.4
STITCH_PITCH = 5.0      # perimeter ring
BOOST_PITCH = 3.0       # denser around the switch node, per Step 6

# A via only conducts heat or current somewhere if the net it lands on HAS copper on the other
# layers.  These are the nets that own a pour (see zones()); a via on anything else is a stub
# into a plane that gets notched around it, which costs plane area and buys nothing.  GND_IN
# is deliberately absent: its island is F.Cu only, so a via from a GND_IN pad would arrive at
# the In1.Cu GND plane -- the one net it must not touch.
PLANED_NETS = ("GND", "/VBAT", "/+24V")


def pads_local(c):
    """(num, px, py, pa, w, h) in FOOTPRINT-LOCAL coordinates for every copper pad.

    Local, not board: the via grid is laid out along the PAD's own axes and then rotated into
    place, because a pad rotated 90 degrees inside a footprint rotated 270 degrees has an
    array that runs neither along the board axes nor along the footprint's.
    """
    fp = load_fp(c["fp"])
    if fp is None:
        return []
    out = []
    for p in find_all(fp, "pad"):
        at, sz, lay = find(p, "at"), find(p, "size"), find(p, "layers")
        if at is None or sz is None or lay is None:
            continue
        if unq(p[2]) != "smd":
            continue    # a through-hole pad already reaches every layer
        names = [unq(a) for a in lay[1:] if isinstance(a, str)]
        if "F.Cu" not in names:
            continue
        pn = unq(p[1])
        if not pn:
            continue    # unnumbered paste apertures sit ON the pad they belong to
        out.append((pn, float(at[1]), float(at[2]),
                    float(at[3]) if len(at) > 3 else 0.0,
                    float(sz[1]), float(sz[2])))
    return out


# Every via emitted, as (x, y, size, drill, net).  gnd_drops() needs to know where the
# thermal and stitching vias went -- and the thermal ones are NOT all ground: there are
# /VBAT and /+24V arrays, so a ground drop that touched one would short a plane.
VIA_LOG = []


def via(x, y, net, size, drill, tag):
    VIA_LOG.append((x, y, size, drill, net))
    return ('\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n'
            '\t\t(layers "F.Cu" "B.Cu")\n\t\t(net %d)\n\t\t(uuid %s)\n\t)'
            % (num(x), num(y), num(size), num(drill), net, U(tag)))


def thermal_vias(comps, pos, padnet, netidx):
    """Via arrays inside every pad big enough to be a heat path onto a net that has a plane.

    Step 3 asks for "enough vias that the pad-to-L3 resistance does not dominate".  For a
    1.6 mm board with 25 um plated barrels, one 0.25 mm-drill via is roughly 60 K/W on its
    own; a 3 x 4 array is about 5 K/W, which is well under the 8-15 K/W a gap pad to the
    enclosure contributes, so the array stops being the bottleneck.  That is the criterion --
    not a via count copied from an app note.

    The array is inset THERM_MARGIN inside the pad edge.  The clearance that actually binds is
    NOT via-to-its-own-pad (same net, no clearance applies) but via-to-the-NEIGHBOURING pad,
    which on a QFN/VSON sits 0.20 mm beyond the paddle edge: 0.15 + 0.20 = 0.35 mm, clear of
    the 0.30 mm the POWER class asks for.  The land-pattern exception in mccan.kicad_dru does
    NOT cover this -- memberOfFootprint() matches pads, not vias -- so the margin has to be
    real, and DRC is what proves it.
    """
    want = set(netidx[n] for n in PLANED_NETS if n in netidx)
    out, log = [], []
    for c in sorted(comps, key=lambda c: natkey(c["ref"])):
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        pads = pads_local(c)
        areas = sorted((p[4] * p[5] for p in pads), reverse=True)
        runner_up = areas[1] if len(areas) > 1 else 0.0
        for pn, px, py, pa, w, h in pads:
            code = padnet.get((c["ref"], pn))
            if code is None or code not in want:
                continue
            if w * h < THERM_MIN_AREA or min(w, h) < THERM_MIN_SIDE:
                continue
            if w * h < THERM_DOMINANCE * runner_up:
                continue
            inset = THERM_VIA / 2.0 + THERM_MARGIN
            uw, uh = w - 2 * inset, h - 2 * inset
            if uw < 0 or uh < 0:
                continue
            nx = int(uw / THERM_PITCH) + 1
            ny = int(uh / THERM_PITCH) + 1
            sx = uw / (nx - 1) if nx > 1 else 0.0
            sy = uh / (ny - 1) if ny > 1 else 0.0
            for i in range(nx):
                for j in range(ny):
                    # pad frame -> footprint frame -> board frame
                    du, dv = rot_local(-uw / 2.0 + i * sx, -uh / 2.0 + j * sy, pa)
                    dx, dy = rot_local(px + du, py + dv, rot)
                    out.append(via(x + dx, y + dy, code, THERM_VIA, THERM_DRILL,
                                   "tv%s.%s.%d.%d" % (c["ref"], pn, i, j)))
            log.append("%s.%s %.2fx%.2f -> %dx%d on %s"
                       % (c["ref"], pn, w, h, nx, ny, NETNAME[code]))
    print("thermal vias: %d in %d pad(s)" % (len(out), len(log)))
    for s in log:
        print("    " + s)
    return out


def stitch_vias(netidx, grid):
    """GND vias tying In1.Cu, B.Cu and the F.Cu pours together (Step 6).

    Every one of these punches a hole in the In2.Cu power plane it passes through, which is why
    the ring is at 5 mm pitch and not something denser: a 0.8 mm via with 0.3 mm clearance
    takes 1.4 mm out of the plane, leaving a 3.6 mm web between holes.  The boost block gets
    2.5 mm because Step 6 asks for stitching there specifically; the denser ring costs the VBAT
    plane more copper, but it sits over the boost corner rather than across the run from the
    input to U9, which is where the 7 A actually flows.

    Candidates are tested against the placer's own occupancy grid, so a via can never land in a
    courtyard, in the ESP32 antenna keep-out or on a mounting hole -- those are already marked.
    The GND_IN island is excluded separately: it is a pour, not a part, so the grid knows
    nothing about it, and a GND via inside it would force the island to notch around a net it
    is specifically there to stay away from.
    """
    gnd = netidx.get("GND")
    if gnd is None:
        return []

    def ok(vx, vy):
        r = STITCH_VIA / 2.0 + 0.3
        if not grid.free(vx - r, vy - r, vx + r, vy + r):
            return False
        return not L.in_gnd_in_island(vx, vy, r)

    spots = []
    m = 2.0
    rx0, ry0, rx1, ry1 = L.X0 + m, L.Y0 + m, L.X1 - m, L.Y1 - m
    n = int(round((rx1 - rx0) / STITCH_PITCH))
    for i in range(n + 1):
        vx = rx0 + i * (rx1 - rx0) / n
        spots += [(vx, ry0), (vx, ry1)]
    n = int(round((ry1 - ry0) / STITCH_PITCH))
    for j in range(1, n):
        vy = ry0 + j * (ry1 - ry0) / n
        spots += [(rx0, vy), (rx1, vy)]
    ring = len(spots)

    bx0, by0, bx1, by1 = L.REGIONS["boost"]
    y = by0
    while y <= by1:
        x = bx0
        while x <= bx1:
            spots.append((x, y))
            x += BOOST_PITCH
        y += BOOST_PITCH

    out = []
    kept_ring = 0
    for k, (vx, vy) in enumerate(spots):
        if ok(vx, vy):
            out.append(via(vx, vy, gnd, STITCH_VIA, STITCH_DRILL, "sv%d" % k))
            kept_ring += 1 if k < ring else 0
    print("stitching vias: %d of %d candidates (%d of %d on the perimeter ring, "
          "%d of %d in the boost block)"
          % (len(out), len(spots), kept_ring, ring,
             len(out) - kept_ring, len(spots) - ring))
    return out


def near(a, b):
    """Distance between two region centres, for choosing where a part spills to."""
    if a is None or a not in L.REGIONS:
        return 0.0
    ax = (L.REGIONS[a][0] + L.REGIONS[a][2]) / 2
    ay = (L.REGIONS[a][1] + L.REGIONS[a][3]) / 2
    bx = (L.REGIONS[b][0] + L.REGIONS[b][2]) / 2
    by = (L.REGIONS[b][1] + L.REGIONS[b][3]) / 2
    return math.hypot(ax - bx, ay - by)


def mount_holes():
    i = L.MOUNT_INSET
    return [(L.X0 + i, L.Y0 + i), (L.X1 - i, L.Y0 + i),
            (L.X0 + i, L.Y1 - i), (L.X1 - i, L.Y1 - i)]


# --------------------------------------------------------------------------- board scaffold
def U(tag):
    return q(str(_uuid.uuid5(NS, "board:" + tag)))


LAYERS = """	(layers
		(0 "F.Cu" signal)
		(4 "In1.Cu" power "GND")
		(6 "In2.Cu" power "PWR")
		(2 "B.Cu" signal)
		(9 "F.Adhes" user "F.Adhesive")
		(11 "B.Adhes" user "B.Adhesive")
		(13 "F.Paste" user)
		(15 "B.Paste" user)
		(5 "F.SilkS" user "F.Silkscreen")
		(7 "B.SilkS" user "B.Silkscreen")
		(1 "F.Mask" user)
		(3 "B.Mask" user)
		(17 "Dwgs.User" user "User.Drawings")
		(19 "Cmts.User" user "User.Comments")
		(21 "Eco1.User" user "User.Eco1")
		(23 "Eco2.User" user "User.Eco2")
		(25 "Edge.Cuts" user)
		(27 "Margin" user)
		(31 "F.CrtYd" user "F.Courtyard")
		(29 "B.CrtYd" user "B.Courtyard")
		(35 "F.Fab" user)
		(33 "B.Fab" user)
	)"""

# 4-layer, 1.6 mm, 1 oz OUTER / 2 oz INNER copper.  Prepreg/core split so the
# GND plane (In1.Cu) is close to F.Cu: that is what makes the reference plane worth having.
#
# The weights are INVERTED relative to the usual arrangement, and relative to what spec 10
# originally asked for (2 oz outer).  Two reasons, decided 2026-09-20:
#
#   1. 2 oz etching cannot hold the 0.15 mm pad-to-pad U10's land pattern needs, nor
#      reliably the 0.20 mm the QFN/VSON parts need.  1 oz can.  Outer copper is where
#      every land pattern lives, so the fine-feature requirement lands entirely on it.
#
#   2. The 7.0 A feed does not run on an outer layer.  It runs on the In2.Cu polygon --
#      and at 1 oz that polygon was UNDER-SPECIFIED: IPC-2221 for an internal layer wants
#      11.5 mm of effective width at 1 oz for 7.0 A at a 10 K rise, against 5.75 mm at 2 oz.
#      Spec 10's '5-6 mm' figure is exactly the 2 oz number and was never reachable at 1 oz.
#      So putting the 2 oz on the inner layers does not trade the current path away; it is
#      what finally satisfies it, and it settles the plan's 4-5 vs 5-6 mm conflict at 5-6.
#
# Total copper is 0.21 mm either way, so 1.6 mm overall still closes.  The dielectric
# sub-thicknesses below are nominal -- the fab adjusts them to hit 1.6 mm with 2 oz inners.
STACKUP = """	(setup
		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.07))
			(layer "dielectric 2" (type "core") (thickness 0.94) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.07))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
		(pad_to_mask_clearance 0)
		(allow_soldermask_bridges_in_footprints no)
		(tenting front back)
		(pcbplotparams
			(layerselection 0x00000000_00000000_55555555_5755f5ff)
			(plot_on_all_layers_selection 0x00000000_00000000_00000000_00000000)
			(disableapertmacros no)
			(usegerberextensions no)
			(usegerberattributes yes)
			(usegerberadvancedattributes yes)
			(creategerberjobfile yes)
			(dashed_line_dash_ratio 12.000000)
			(dashed_line_gap_ratio 3.000000)
			(svgprecision 4)
			(plotframeref no)
			(mode 1)
			(useauxorigin no)
			(dxfpolygonmode yes)
			(dxfimperialunits yes)
			(dxfusepcbnewfont yes)
			(psnegative no)
			(psa4output no)
			(plot_black_and_white yes)
			(plotinvisibletext no)
			(sketchpadsonfab no)
			(plotpadnumbers no)
			(hidednponfab no)
			(sketchdnponfab yes)
			(crossoutdnponfab yes)
			(subtractmaskfromsilk no)
			(outputformat 1)
			(mirror no)
			(drillshape 1)
			(scaleselection 1)
			(outputdirectory "output/gerbers/")
		)
	)"""


def edge_cuts():
    """Rounded rectangle: four straight runs plus four 90 deg corner arcs."""
    r = L.EDGE_R
    x0, y0, x1, y1 = L.X0, L.Y0, L.X1, L.Y1
    out = []
    S = '(stroke (width 0.1) (type default)) (layer "Edge.Cuts")'

    def line(ax, ay, bx, by, tag):
        out.append('\t(gr_line (start %s %s) (end %s %s) %s (uuid %s))'
                   % (num(ax), num(ay), num(bx), num(by), S, U("edge_" + tag)))

    def arc(ax, ay, mx, my, bx, by, tag):
        out.append('\t(gr_arc (start %s %s) (mid %s %s) (end %s %s) %s (uuid %s))'
                   % (num(ax), num(ay), num(mx), num(my), num(bx), num(by), S,
                      U("edge_" + tag)))

    k = r * (1 - 0.70710678)
    line(x0 + r, y0, x1 - r, y0, "top")
    line(x1, y0 + r, x1, y1 - r, "right")
    line(x1 - r, y1, x0 + r, y1, "bottom")
    line(x0, y1 - r, x0, y0 + r, "left")
    arc(x1 - r, y0, x1 - k, y0 + k, x1, y0 + r, "tr")
    arc(x1, y1 - r, x1 - k, y1 - k, x1 - r, y1, "br")
    arc(x0 + r, y1, x0 + k, y1 - k, x0, y1 - r, "bl")
    arc(x0, y0 + r, x0 + k, y0 + k, x0 + r, y0, "tl")
    return out


def notes():
    out = []
    for i, (txt, x, y, layer, size) in enumerate(L.NOTES):
        lines = txt.split("\n")
        for j, ln in enumerate(lines):
            out.append('\t(gr_text %s (at %s %s) (layer %s) (uuid %s)\n'
                       '\t\t(effects (font (size %s %s) (thickness %s)) (justify left))\n'
                       '\t)'
                       % (q(ln), num(x), num(y + j * size * 1.4), q(layer),
                          U("note%d_%d" % (i, j)), num(size), num(size), num(size * 0.15)))
    return out


def tim_areas():
    """The gap-pad contact patches, on Cmts.User.  See layout_pcb.TIM_PADS for what they are."""
    out = []
    S = '(stroke (width 0.2) (type dash)) (fill no) (layer "Cmts.User")'
    for tag, x0, y0, x1, y1 in L.TIM_PADS:
        out.append('\t(gr_rect (start %s %s) (end %s %s) %s (uuid %s))'
                   % (num(x0), num(y0), num(x1), num(y1), S, U("tim_" + tag)))
        out.append('\t(gr_text %s (at %s %s) (layer "Cmts.User") (uuid %s)\n'
                   '\t\t(effects (font (size 1.2 1.2) (thickness 0.18)) (justify left))\n'
                   '\t)'
                   % (q("%s gap pad %.0f x %.0f mm = %.0f mm2 (B.Cu side)"
                        % (tag, x1 - x0, y1 - y0, (x1 - x0) * (y1 - y0))),
                      num(x0 + 0.5), num(y0 + 1.5), U("timtxt_" + tag)))
    return out


def zones(netidx):
    """Copper pours.

    In1.Cu  -- solid GND, the unbroken reference plane spec 10 asks for.
    In2.Cu  -- VBAT, end to end.  It used to be split down x = 105 with +24V on the right, and
               that split was wrong in both directions: seven of the eleven +24V pads are LEFT
               of it (D4, C61, C20, C21, C22, R12) and two of the fifteen VBAT pads are RIGHT
               of it (C45, C46).  The two nets interleave across the whole board, so no
               straight line separates them -- the vertical split was not a lobe short of D4,
               it was the wrong model.

               The way out is not a cleverer split but the current figures.  VBAT is the 7.0 A
               feed and wants every millimetre of plane it can get; +24V is the boost output at
               0.5 A (spec 6), against 3.94 A of capability on a 2.0 mm POWER track at 1 oz.
               Giving half the power plane to the rail that needs it least starved the one that
               needs it most.  So In2.Cu is VBAT alone, and +24V is routed as POWER tracks --
               which is exactly what its net class was already sized for.
    B.Cu    -- GND, plus one small +24V island under D4's tab; see L.D4_24V_ISLAND.
    F.Cu    -- a local GND_IN island over the eFuse and the wire-exit corner.  GND_IN is a
               SEPARATE net from GND and meets it only through L2 winding B; giving it its own
               island is how that separation survives a pour instead of being an ideal on paper.
    """
    out = []
    ins = 0.5
    x0, y0, x1, y1 = L.X0 + ins, L.Y0 + ins, L.X1 - ins, L.Y1 - ins

    def poly(pts):
        s = "\t\t(polygon\n\t\t\t(pts\n"
        for px, py in pts:
            s += "\t\t\t\t(xy %s %s)\n" % (num(px), num(py))
        return s + "\t\t\t)\n\t\t)"

    def zone(net, layers, pts, tag, prio=0):
        code = netidx[net]
        lay = ("(layers " + " ".join(q(x) for x in layers) + ")") if len(layers) > 1 \
              else ("(layer " + q(layers[0]) + ")")
        return ("\t(zone (net %d) (net_name %s) %s (uuid %s)\n"
                "\t\t(name %s) (hatch edge 0.5) (priority %d)\n"
                "\t\t(connect_pads (clearance 0.3))\n"
                "\t\t(min_thickness 0.3) (filled_areas_thickness no)\n"
                "\t\t(fill yes (thermal_gap 0.4) (thermal_bridge_width 0.5))\n"
                "%s\n\t)" % (code, q(net), lay, U("zone_" + tag), q(tag), prio, poly(pts)))

    full = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    out.append(zone("GND", ["In1.Cu"], full, "GND_INNER"))
    out.append(zone("GND", ["B.Cu"], full, "GND_BOT"))
    out.append(zone("/VBAT", ["In2.Cu"], full, "VBAT_IN2"))
    # D4's tab needs somewhere for its thermal array to land now that +24V has no plane.
    # Priority 2 so it wins against the B.Cu ground pour, which notches around it.
    out.append(zone("/+24V", ["B.Cu"], L.D4_24V_ISLAND, "24V_D4", prio=2))
    # The GND_IN island.  Its shape is dictated by where the input ground actually is, and it
    # is checked against the pads by scripts/check_grounds.py -- every GND_IN pad must sit in
    # it and no GND pad may.  Three features are deliberate:
    #
    #   * the body, x 22..66 y 53.5..94, covers the whole eFuse column -- U10, Q10/Q11, R100,
    #     the sense path and D2/R3;
    #   * a narrow SPUR, x 42..48 up to y 36, reaches L2 pad 2 (GND_IN, at 44.75, 38) and
    #     nothing else.  L2's OUTPUT pads are at y 27.3, so the spur stops well short of them
    #     and the post-choke pi filter (C1, C2, C3, L1) stays outside the pour entirely.  A
    #     rectangle up to the choke would have wrapped GND_IN copper around post-choke ground
    #     pads, coupling across the very component that separates them;
    #   * below y 94 the island narrows to x 22..46, which takes in J1 (GND_IN at x 42.85)
    #     and stops short of J7's GND pad at x 60.55.
    out.append(zone("/power_input/GND_IN", ["F.Cu"], L.GND_IN_ISLAND, "GNDIN_F", prio=1))

    return out


# --------------------------------------------------------------------------- ground drops
#
# Every SMD ground pad needs a via, and nothing else on the board provides one.
#
# GND is poured on In1.Cu and B.Cu; it is NOT poured on F.Cu, because F.Cu is the signal layer
# and the one F.Cu pour that does exist is the GND_IN island, a DIFFERENT net.  So a ground pad
# sits on a layer where its own net has no copper at all.  The 15 through-hole ground pads are
# fine -- a plated barrel already crosses every layer -- and three exposed paddles are filled by
# thermal_vias().  The other 140 have no path to the plane whatever, which is why they are a
# quarter of the ratsnest.  This is not routing work and should not wait for it.
#
# The via goes BESIDE the pad, not in it.  thermal_vias() puts vias in pads, but only in ones
# that look like a paddle, for the reason set out there: an unplugged via inside the terminal
# pad of a chip part wicks paste out of the joint during reflow.  A 0402 ground pad gets a via
# next to it and a stub to reach it -- which is also what the comment in thermal_vias promised
# would happen "when Task 9 routes them".
#
# The via is 0.6 / 0.3, not the 0.8 / 0.4 used for stitching: these land in the tightest company
# on the board, between chip pads, and every one of them punches a hole in the In2.Cu power
# plane on its way past.  0.6 mm keeps that hole to 1.2 mm with clearance.
#
# Placement is a search, not a formula.  Candidates run outward from the pad, starting in the
# direction away from the part's own centre -- which is where the free copper usually is -- and
# fanning to either side.  Each candidate is tested against real geometry rather than against
# the placer's occupancy grid: the grid marks whole courtyards as occupied, so every candidate
# beside a pad would fail, including the correct ones.  What actually has to be checked is:
#
#   * foreign pads, at DROP_CLEAR -- the widest netclass clearance on the board, so the test
#     does not depend on which net the neighbour happens to be on;
#   * its OWN pad and other ground pads, at zero gap but no overlap, because via-in-pad is a
#     fab decision this generator is specifically not taking;
#   * every via already placed, including the thermal arrays, which are NOT all ground -- there
#     are /VBAT and /+24V arrays, and a ground via touching one would short a plane to ground;
#   * the antenna keep-out, read from U5's own footprint, where no plating is allowed at all;
#   * the GND_IN island, for the reason stitch_vias() gives: a GND via inside it forces the
#     island to notch around the one net it exists to stay away from;
#   * the board edge and the mounting holes.
#
# The stub is checked the same way, as a swept rectangle.  A via that is reachable only by a
# stub that clips a neighbouring pad is not a usable via, so the two are accepted together.

DROP_VIA, DROP_DRILL = 0.6, 0.3
DROP_CLEAR = 0.30       # the WIDEST netclass clearance -- used only where the neighbour is
                        # not a pad on a known net: the board edge, a keep-out, a mounting
                        # hole.  Pad-to-pad uses net_clearance() below, because assuming the
                        # worst case everywhere is not conservative, it is wrong: 0.30 mm is
                        # what FEED and POWER ask for, while GND and the signals are Default
                        # class at 0.20 mm.  On a 0.65 mm pitch part the gap between pins is
                        # 0.25 mm, so the difference decides whether a ground pin can have a
                        # via at all.  Demanding 0.30 there does not make the board safer; it
                        # makes it unroutable and leaves the pin unconnected, which is worse.
DROP_DEFAULT_CLEAR = 0.20


def net_clearance(code):
    """The clearance the netclass rules actually apply to a net, by net code."""
    name = NETNAME.get(code) or ""
    short = name.rsplit("/", 1)[-1]
    for cname, tw, cl, vd, vdr, nets in L.NETCLASSES:
        if name in nets or short in nets:
            return cl
    return DROP_DEFAULT_CLEAR
DROP_MAX_R = 3.0        # mm from pad centre; beyond this the stub is no longer a drop
DROP_STUB_MAX = 0.5     # stub width ceiling; narrower if the pad is narrower


# Every track segment emitted, as (x0, y0, x1, y1, width, layer, net).  The autorouter needs
# to know where the ground drops and the hand routes went, and seg() is the single constructor
# they all pass through, so logging here catches every one of them without anybody remembering to.
TRACK_LOG = []


def seg(x0, y0, x1, y1, w, layer, net, tag):
    TRACK_LOG.append((x0, y0, x1, y1, w, layer, net))
    return ('\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n'
            '\t\t(layer %s)\n\t\t(net %d)\n\t\t(uuid %s)\n\t)'
            % (num(x0), num(y0), num(x1), num(y1), num(w), q(layer), net, U(tag)))


def pads_board(comps, pos, padnet):
    """Every copper pad as (ref, pad, net, cx, cy, w, h, smd, id) with an AXIS-ALIGNED bbox.

    `id` is a unique index per pad INSTANCE, and it is not decoration.  A pad NUMBER does not
    identify a pad: the ESP32 module's ground pad is a dozen separate pads all numbered 39, and
    keying "the pad we are placing a via for" on (ref, number) excused every one of them from
    the clearance test at once.  Six ground drops landed inside a neighbouring 39 before this
    had an index to tell them apart.

    Both the position and the SIZE are rotated by the footprint's rotation.  The pad angle in
    a library footprint is footprint-RELATIVE -- build_footprint() absolute-ises it through
    addrot() on the way out -- so reading it here without adding `rot` orients every non-square
    pad of every rotated part along the wrong axis.  That is what this function did until now,
    and it is why U5's 0.90 x 1.50 castellated pads came back as 1.50 x 0.90 boxes overlapping
    each other on a 1.27 mm pitch.  Nothing caught it, because a too-wide box is pessimistic --
    it only refuses ground drops that would have been legal -- while the too-SHORT other axis
    is optimistic, and an optimistic clearance test fails silently by definition.

    Taking the axis-aligned bounding box of the rotated pad is exact for the rectangular pads
    this matters for and pessimistic -- safe -- for ovals and circles.
    """
    out = []
    for c in comps:
        if c["ref"] not in pos:
            continue
        fp = load_fp(c["fp"])
        if fp is None:
            continue
        x, y, rot = pos[c["ref"]]
        for p in find_all(fp, "pad"):
            at, sz, lay = find(p, "at"), find(p, "size"), find(p, "layers")
            if at is None or sz is None or lay is None:
                continue
            pn = unq(p[1])
            if not pn:
                continue
            names = [unq(a) for a in lay[1:] if isinstance(a, str)]
            if not any(n in ("F.Cu", "*.Cu") for n in names):
                continue
            pa = (float(at[3]) if len(at) > 3 else 0.0) + rot
            w, h = float(sz[1]), float(sz[2])
            th = math.radians(pa)
            cth, sth = abs(math.cos(th)), abs(math.sin(th))
            bw, bh = w * cth + h * sth, w * sth + h * cth
            dx, dy = rot_local(float(at[1]), float(at[2]), rot)
            out.append((c["ref"], pn, padnet.get((c["ref"], pn)),
                        x + dx, y + dy, bw, bh, unq(p[2]) == "smd", len(out)))
    return out


class Hash(object):
    """A 4 mm bucket grid over the pads, so a candidate test is local rather than board-wide."""

    CELL = 4.0

    def __init__(self, items):
        self.b = {}
        for it in items:
            cx, cy, w, h = it[3], it[4], it[5], it[6]
            for i in range(int((cx - w / 2) / self.CELL), int((cx + w / 2) / self.CELL) + 1):
                for j in range(int((cy - h / 2) / self.CELL), int((cy + h / 2) / self.CELL) + 1):
                    self.b.setdefault((i, j), []).append(it)

    def near(self, x0, y0, x1, y1):
        out = []
        for i in range(int(x0 / self.CELL), int(x1 / self.CELL) + 1):
            for j in range(int(y0 / self.CELL), int(y1 / self.CELL) + 1):
                out += self.b.get((i, j), [])
        return out


def _pt_rect(px, py, rx0, ry0, rx1, ry1):
    """Euclidean distance from a point to an axis-aligned rectangle; 0 if inside."""
    dx = max(rx0 - px, 0.0, px - rx1)
    dy = max(ry0 - py, 0.0, py - ry1)
    return math.hypot(dx, dy)


def _seg_seg(ax, ay, bx, by, cx, cy, dx_, dy_):
    """Distance between two line segments."""
    def pt_seg(px, py, x0, y0, x1, y1):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
        return math.hypot(px - (x0 + t * vx), py - (y0 + t * vy))

    rx, ry = bx - ax, by - ay
    sx, sy = dx_ - cx, dy_ - cy
    den = rx * sy - ry * sx
    if abs(den) > 1e-12:
        t = ((cx - ax) * sy - (cy - ay) * sx) / den
        u = ((cx - ax) * ry - (cy - ay) * rx) / den
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0          # they cross
    return min(pt_seg(ax, ay, cx, cy, dx_, dy_), pt_seg(bx, by, cx, cy, dx_, dy_),
               pt_seg(cx, cy, ax, ay, bx, by), pt_seg(dx_, dy_, ax, ay, bx, by))


def _seg_rect(x0, y0, x1, y1, rx0, ry0, rx1, ry1):
    """Distance from a segment to an axis-aligned rectangle; 0 if it touches or enters."""
    if (rx0 <= x0 <= rx1 and ry0 <= y0 <= ry1) or (rx0 <= x1 <= rx1 and ry0 <= y1 <= ry1):
        return 0.0
    return min(_seg_seg(x0, y0, x1, y1, rx0, ry0, rx1, ry0),
               _seg_seg(x0, y0, x1, y1, rx1, ry0, rx1, ry1),
               _seg_seg(x0, y0, x1, y1, rx1, ry1, rx0, ry1),
               _seg_seg(x0, y0, x1, y1, rx0, ry1, rx0, ry0))


# Both tests below are EXACT rather than bounding-box, and that is not fussiness.  A via is a
# circle and a track is a capsule -- KiCad's segments have round caps -- so exact is the same
# amount of code as an approximation and answers the question the DRC will actually ask.  The
# axis-aligned bbox this replaced merged the far end's x-extent with the near end's y-extent,
# so a diagonal stub leaving a fine-pitch pin read as clipping the neighbour it was moving
# AWAY from, and four ground pins on U3 and U8 were reported unreachable when they were not.

def _via_clear(vx, vy, r, pads, gnd, skip):
    """Is a via at (vx, vy) clear of every pad it could touch?

    Same-net pads are held to a zero gap rather than ignored: a ground via landing inside a
    ground pad is legal copper but a fab decision (paste wicks down an unplugged via in a
    solderable pad), and one this generator deliberately does not take -- thermal_vias() is
    where via-in-pad is decided, and only for pads that look like a paddle.
    """
    for ref, pn, net, px, py, pw, ph, smd, pid in pads:
        if pid in skip:
            continue
        need = 0.0 if net == gnd else max(net_clearance(net), DROP_DEFAULT_CLEAR)
        if _pt_rect(vx, vy, px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2) < r + need:
            return False
    return True


def _stub_clear(x0, y0, x1, y1, w, pads, gnd, skip):
    """Is the stub, as a capsule of width `w`, clear of every pad it could touch?

    Same-net pads are not obstacles at all here.  A ground track crossing a ground pad is not
    a fault; it is the connection.
    """
    for ref, pn, net, px, py, pw, ph, smd, pid in pads:
        if pid in skip or net == gnd:
            continue
        need = max(net_clearance(net), DROP_DEFAULT_CLEAR)
        if _seg_rect(x0, y0, x1, y1,
                     px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2) < w / 2 + need:
            return False
    return True


def gnd_drops(comps, pos, padnet, netidx, placed, keepouts):
    """A via beside every SMD ground pad, with a stub to reach it.

    `placed` is (x, y, size, drill, net) for every via already on the board; `keepouts` is the
    all-layer keep-out boxes.  Returns (vias, segments) and appends the new vias to `placed`,
    so the drops cannot collide with each other either.
    """
    gnd = netidx.get("GND")
    if gnd is None:
        return [], []

    allpads = pads_board(comps, pos, padnet)
    hash_ = Hash(allpads)
    r = DROP_VIA / 2.0
    holes = [(mx, my, L.MOUNT_PAD) for mx, my in mount_holes()]

    def via_ok(vx, vy, skip, island=True):
        if not (L.X0 + 0.5 + r <= vx <= L.X1 - 0.5 - r
                and L.Y0 + 0.5 + r <= vy <= L.Y1 - 0.5 - r):
            return False
        for kx0, ky0, kx1, ky1 in keepouts:
            if kx0 - r < vx < kx1 + r and ky0 - r < vy < ky1 + r:
                return False
        if island and L.in_gnd_in_island(vx, vy, r + DROP_CLEAR):
            return False
        for mx, my, md in holes:
            if math.hypot(vx - mx, vy - my) < md / 2.0 + r + DROP_CLEAR:
                return False
        for px, py, ps, pd, pnet in placed:
            d = math.hypot(vx - px, vy - py)
            if d < max((DROP_DRILL + pd) / 2.0 + 0.3,
                       (DROP_VIA + ps) / 2.0 + (0.0 if pnet == gnd else DROP_CLEAR)):
                return False
        near = hash_.near(vx - r - DROP_CLEAR, vy - r - DROP_CLEAR,
                          vx + r + DROP_CLEAR, vy + r + DROP_CLEAR)
        return _via_clear(vx, vy, r, near, gnd, skip)

    def stub_ok(x0, y0, x1, y1, w, skip, pad=None):
        """The stub, as a swept box -- but only the part of it OUTSIDE its own pad.

        The run starts at the pad centre, so its first stretch lies within the pad's own
        outline.  That stretch is not copper the stub adds; it is the pad.  Checking it
        anyway fails every fine-pitch IC pin on the board: a 0.65 mm pitch leaves 0.25 mm
        between pads, so a box drawn along a pin from its centre is inside its neighbour's
        clearance before it has gone anywhere.  Clip to where the stub actually leaves the
        pad and the test asks the right question.  The emitted segment is unchanged -- it
        still starts at the centre, which is what anchors it to the pad.

        """
        if pad is not None:
            pw, ph = pad
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy)
            if n > 1e-9:
                # How far along the run the pad's own outline reaches.
                tx = (pw / 2.0) / abs(dx) if abs(dx) > 1e-9 else 1e9
                ty = (ph / 2.0) / abs(dy) if abs(dy) > 1e-9 else 1e9
                t = min(min(tx, ty), 1.0)
                x0, y0 = x0 + dx * t, y0 + dy * t
        bx0, bx1 = min(x0, x1) - w / 2, max(x0, x1) + w / 2
        by0, by1 = min(y0, y1) - w / 2, max(y0, y1) + w / 2
        near = hash_.near(bx0 - DROP_CLEAR, by0 - DROP_CLEAR,
                          bx1 + DROP_CLEAR, by1 + DROP_CLEAR)
        if not _stub_clear(x0, y0, x1, y1, w, near, gnd, skip):
            return False
        # Foreign vias -- the thermal arrays are not all ground.
        for px, py, ps, pd, pnet in placed:
            if pnet == gnd:
                continue
            need = max(net_clearance(pnet), DROP_DEFAULT_CLEAR)
            if _seg_rect(x0, y0, x1, y1, px - ps / 2, py - ps / 2,
                         px + ps / 2, py + ps / 2) < w / 2 + need:
                return False
        return True

    # Ground pads that still need one: SMD, and with no via already inside them.
    todo = []
    for ref, pn, net, px, py, pw, ph, smd, pid in allpads:
        if net != gnd or not smd:
            continue
        if any(abs(vx - px) <= pw / 2 and abs(vy - py) <= ph / 2
               for vx, vy, _s, _d, _n in placed):
            continue
        todo.append((ref, pn, px, py, pw, ph, pid))

    centre = {}
    for ref, pn, net, px, py, pw, ph, smd, pid in allpads:
        cx, cy, n = centre.get(ref, (0.0, 0.0, 0))
        centre[ref] = (cx + px, cy + py, n + 1)

    vias, segs, failed, shared = [], [], [], []
    for ref, pn, px, py, pw, ph, pid in sorted(
            todo, key=lambda t: (natkey(t[0]), t[1], t[6])):
        cx, cy, n = centre[ref]
        ox, oy = px - cx / n, py - cy / n
        base = math.atan2(oy, ox) if math.hypot(ox, oy) > 1e-6 else 0.0
        w = min(DROP_STUB_MAX, pw, ph)
        skip = set([pid])
        # R3 is the ONE resistor that ties GND_IN to GND, so its ground pad sits in
        # the middle of the GND_IN island by design.  Excluding the island here would
        # deny a via to the only pad on the board that cannot do without one.  The
        # island notches around the pad already; one more notch for its via changes
        # nothing.  check_grounds.py still proves the two nets stay apart.
        island = (ref != "R3")
        # Directions to try, in order of preference.
        #
        # The pad's own LONG AXIS comes first, because that is how a pin escapes: straight out
        # of the end, staying centred between its neighbours for as long as it can.  It is not
        # a rounding of the fan below -- it is the one direction the fan cannot express.  The
        # fan steps 15 degrees off the line to the part centre, which on a pad whose centre is
        # offset from that line never lands square; U8 pin 27 missed a legal escape by three
        # degrees and 0.03 mm, and was reported unreachable with clear copper straight ahead.
        axis = 0.0 if pw >= ph else math.pi / 2.0
        angles = sorted((axis, axis + math.pi), key=lambda a: -math.cos(a - base))
        for step in range(0, 13):
            for sgn in ((1,) if step == 0 else (1, -1)):
                angles.append(base + sgn * step * math.radians(15))

        got = None
        for th in angles:
            d = max(pw, ph) / 2.0 + r + 0.05
            while d <= DROP_MAX_R:
                vx, vy = px + d * math.cos(th), py + d * math.sin(th)
                if (via_ok(vx, vy, skip, island)
                        and stub_ok(px, py, vx, vy, w, skip, (pw, ph))):
                    got = (vx, vy)
                    break
                d += 0.05
            if got:
                break
        if not got:
            # Fallback: SHARE a via that is already there.  On a multi-pad IC the ground pins
            # come in runs -- U7 and U8 have eight apiece -- and once the first few have taken
            # the free copper there is no room left for one via per pad.  Tying the pad to a
            # neighbour's via is not a compromise; it is what a person would draw, and the
            # stub is shorter than the one a private via 3 mm away would have needed.  The
            # stub is checked exactly as before, so a share that would clip a pad is refused.
            best = None
            for vx, vy, vs, vd, vnet in placed:
                if vnet != gnd:
                    continue
                d = math.hypot(vx - px, vy - py)
                if d > DROP_MAX_R or (best is not None and d >= best[0]):
                    continue
                if stub_ok(px, py, vx, vy, w, skip, (pw, ph)):
                    best = (d, vx, vy)
            if best is not None:
                shared.append("%s.%s" % (ref, pn))
                segs.append(seg(px, py, best[1], best[2], w, "F.Cu", gnd,
                                "gs%s.%s.%d" % (ref, pn, pid)))
                continue
            failed.append("%s.%s" % (ref, pn))
            continue
        vx, vy = got
        vias.append(via(vx, vy, gnd, DROP_VIA, DROP_DRILL, "gd%s.%s.%d" % (ref, pn, pid)))
        segs.append(seg(px, py, vx, vy, w, "F.Cu", gnd, "gs%s.%s.%d" % (ref, pn, pid)))
        placed.append((vx, vy, DROP_VIA, DROP_DRILL, gnd))

    print("ground drops: %d own via(s), %d shared, for %d SMD GND pad(s)"
          % (len(vias), len(shared), len(todo)))
    if shared:
        print("    sharing a neighbour's via: %s" % ", ".join(shared))
    if failed:
        print("  WARN: no room for a drop at %d pad(s): %s"
              % (len(failed), ", ".join(failed)))
    return vias, segs


# --------------------------------------------------------------------------- routes
#
# layout_pcb.ROUTES / ROUTE_VIAS turned into track segments and vias, with the two checks the
# comment there describes.  Both work on COPPER OVERLAP rather than on centrelines -- see that
# comment for why -- and both are advisory: they print and carry on, because the authority on a
# routed board is DRC, and a check here that refused to emit would only hide the geometry from
# the tool that can actually judge it.
#
# Boxes are axis-aligned bounds: exact for the orthogonal runs, which is nearly all of them,
# and pessimistic for diagonals.  Pessimistic is the safe direction for a clearance test and
# the unsafe one for an anchorage test, so a diagonal that only just reaches its pad will be
# reported as anchored when it is not.  DRC still catches that as an unconnected item; what
# this catches is the coordinate typo that DRC can only describe as "unconnected", somewhere,
# in a list of hundreds.


def _rect_gap(a, b):
    """Gap between two (x0, y0, x1, y1) rectangles; 0.0 if they touch or overlap."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


def _seg_box(x0, y0, x1, y1, w):
    return (min(x0, x1) - w / 2, min(y0, y1) - w / 2,
            max(x0, x1) + w / 2, max(y0, y1) + w / 2)


def _pad_box(p):
    _ref, _pn, _net, px, py, pw, ph, _smd, _pid = p
    return (px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2)


def routes(comps, pos, padnet, netidx, placed):
    """Emit ROUTES and ROUTE_VIAS, after checking anchorage and foreign clearance."""
    spec = list(getattr(L, "ROUTES", []))
    vspec = list(getattr(L, "ROUTE_VIAS", []))
    if not spec and not vspec:
        return []

    # Nets are named by their last path component, so "+24V" finds "/+24V" and "SW_BOOST"
    # finds "/rails/SW_BOOST" without this file knowing which sheet declared them.
    short = {}
    for name, code in netidx.items():
        short.setdefault(name.rsplit("/", 1)[-1], []).append(name)

    def resolve(n, what):
        if n in netidx:
            return netidx[n]
        hits = short.get(n, [])
        if len(hits) == 1:
            return netidx[hits[0]]
        if not hits:
            print("  ERROR: %s names net %r, which is not in the netlist" % (what, n))
        else:
            print("  ERROR: %s names net %r, which is ambiguous: %s"
                  % (what, n, ", ".join(sorted(hits))))
        return None

    allpads = pads_board(comps, pos, padnet)
    hash_ = Hash(allpads)

    # Flatten first, so the anchorage test can see pieces that come later in the table as well
    # as earlier ones -- the order entries are written in should not decide whether they pass.
    segs, vias = [], []
    for i, (n, layer, w, pts) in enumerate(spec):
        code = resolve(n, "ROUTES entry %d" % i)
        if code is None:
            continue
        for j in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[j], pts[j + 1]
            segs.append(dict(code=code, name=n, layer=layer, w=w, i=i, j=j,
                             p0=(x0, y0), p1=(x1, y1),
                             box=_seg_box(x0, y0, x1, y1, w)))
    for i, (n, x, y, sz, dr) in enumerate(vspec):
        code = resolve(n, "ROUTE_VIAS entry %d" % i)
        if code is None:
            continue
        vias.append(dict(code=code, name=n, x=x, y=y, sz=sz, dr=dr, i=i,
                         box=(x - sz / 2, y - sz / 2, x + sz / 2, y + sz / 2)))

    # --- check 1: does each polyline END land on copper of its own net?
    #
    # A via counts on any layer -- that is what a via is for -- so vias carry layer None and
    # match anything.  A segment counts only on its own layer.
    dangling = []
    for s in segs:
        for end, which in ((s["p0"], "start"), (s["p1"], "end")):
            w = s["w"]
            b = (end[0] - w / 2, end[1] - w / 2, end[0] + w / 2, end[1] + w / 2)
            ok = any(p[2] == s["code"] and _rect_gap(b, _pad_box(p)) <= 0.0
                     for p in hash_.near(*b))
            if not ok:
                ok = any(o is not s and o["code"] == s["code"]
                         and o["layer"] == s["layer"] and _rect_gap(b, o["box"]) <= 0.0
                         for o in segs)
            if not ok:
                ok = any(v["code"] == s["code"] and _rect_gap(b, v["box"]) <= 0.0
                         for v in vias)
            if not ok:
                dangling.append("%s ROUTES[%d] seg %d %s (%.2f, %.2f)"
                                % (s["name"], s["i"], s["j"], which, end[0], end[1]))

    # --- check 2: foreign clearance, against the wider of the two nets' class clearances
    close = []

    def check(box, code, what):
        for p in hash_.near(box[0] - 0.5, box[1] - 0.5, box[2] + 0.5, box[3] + 0.5):
            if p[2] == code:
                continue
            need = max(net_clearance(p[2]), net_clearance(code))
            g = _rect_gap(box, _pad_box(p))
            if g < need:
                close.append("%s vs %s.%s (%s): %.3f < %.3f"
                             % (what, p[0], p[1], NETNAME.get(p[2], "?"), g, need))

    for s in segs:
        check(s["box"], s["code"], "%s ROUTES[%d] seg %d" % (s["name"], s["i"], s["j"]))
    for v in vias:
        what = "%s ROUTE_VIAS[%d]" % (v["name"], v["i"])
        check(v["box"], v["code"], what)
        for vx, vy, vs, vd, vnet in placed:
            if vnet == v["code"]:
                continue
            need = max(net_clearance(vnet), net_clearance(v["code"]))
            g = _rect_gap(v["box"], (vx - vs / 2, vy - vs / 2, vx + vs / 2, vy + vs / 2))
            if g < need:
                close.append("%s vs a via on %s: %.3f < %.3f"
                             % (what, NETNAME.get(vnet, "?"), g, need))

    print("routes: %d segment(s) on %d net(s), %d via(s)"
          % (len(segs), len(set(s["code"] for s in segs)), len(vias)))
    if dangling:
        print("  ERROR: %d route end(s) land on no copper of their own net:" % len(dangling))
        for d in dangling:
            print("      %s" % d)
    if close:
        print("  ERROR: %d route clearance(s) short:" % len(close))
        for c in close:
            print("      %s" % c)

    out = []
    for s in segs:
        out.append(seg(s["p0"][0], s["p0"][1], s["p1"][0], s["p1"][1],
                       s["w"], s["layer"], s["code"], "rt%d.%d" % (s["i"], s["j"])))
    for v in vias:
        out.append(via(v["x"], v["y"], v["code"], v["sz"], v["dr"], "rv%d" % v["i"]))
        placed.append((v["x"], v["y"], v["sz"], v["dr"], v["code"]))
    return out


# --------------------------------------------------------------------------- autorouter
#
# A grid maze router for the signal nets.
#
# Why this exists.  After the ground drops there are still ~330 unconnected pads, and I tried
# to hand-author the boost's control nets into ROUTES first.  Four nets have to escape U3's
# right edge -- SW, MODE, SS and FB on 0.5 mm pitch -- and they have to nest in the order their
# pins come in, past a 100 pF cap that sits in the only channel.  Every arrangement I worked out
# by hand broke one of the four, and each attempt cost a full pass of measuring pad boxes.  That
# is a search problem, and this is the thing that does searches.
#
# ROUTES still comes first and still wins: anything in that table is already copper before the
# router starts, so the switch node, the commutation loop and anything else whose geometry is a
# design decision stays hand-authored.  The router is for the connections where any legal path
# will do, which is most of them.
#
# What it does NOT do:
#
#   * GND.  It is a plane on In1.Cu and B.Cu and every SMD pad already has a drop.
#   * the FEED and POWER classes.  Those are 2.0 and 3.5 mm wide and the clearance map here is
#     built for a 0.25 mm track; they are plan Task 9 Step 2 and they are hand work, because
#     their width is a thermal decision and their shape is a loop-area decision.
#   * differential pairs.  CAN is Step 3 and wants matched, coupled geometry, not two
#     independently searched paths.
#
# How the map works.  Two arrays per routable layer over a 0.1 mm grid:
#
#   core[layer]  the net code of the copper actually at that cell, or 0.
#   halo[layer]  the net code of the copper whose CLEARANCE covers that cell; -1 if two
#                different nets both claim it, 0 if nobody does.
#
# A cell is passable for net N if halo is 0 or N -- or if core is N, which lets a route sit
# inside its own pad, the one place where copper of its own net is already committed.  The halo
# radius is the obstacle's own extent grown by (0.125 + the obstacle net's clearance): a
# centreline outside that leaves a 0.25 mm track's EDGE at least that clearance away, which is
# what the rule actually asks.  Growing by the obstacle's class rather than by the widest class
# on the board is what makes a 0.5 mm pitch QFN escapable at all: straight out from a 0.25 mm
# pad, the neighbouring pad's edge is 0.375 mm away and the halo is 0.325 mm, so the cell on the
# pad's own centreline is free -- by 0.05 mm.  At the board-wide 0.30 mm it would not be.
#
# Rounded rectangles are stamped as square ones, and diagonal runs as true capsules.  Square is
# pessimistic at the corners, which is the safe direction for a clearance map.
#
# None of this replaces DRC.  It is a model of the rules, and the board is judged by the tool
# that owns them.

AR_GRID = 0.1                  # mm per cell
AR_W = 0.25                    # what the router emits; narrow, because escape geometry governs
AR_CLEAR = 0.20                # Default class; wider classes are read per obstacle net
AR_VIA, AR_VIA_DRILL = 0.6, 0.3
AR_LAYERS = ("F.Cu", "B.Cu")
AR_EDGE = 0.5                  # mm of copper-free border inside the board outline
AR_VIA_COST = 45               # in tenth-mm steps: a layer change is worth 4.5 mm of detour
AR_DIAG_OK = True
AR_MARGIN = (6.0, 14.0, 30.0)  # mm the search box grows by, tried in order
AR_MAX_POP = 600000            # give up on one attempt rather than hang the generator

# The nets the router is not allowed to touch, by class name.  GND is named directly.
AR_SKIP_CLASSES = ("FEED", "POWER", "CAN")


def _ar_class(code):
    name = NETNAME.get(code) or ""
    short = name.rsplit("/", 1)[-1]
    for cname, tw, cl, vd, vdr, nets in L.NETCLASSES:
        if name in nets or short in nets:
            return cname, cl
    return "Default", DROP_DEFAULT_CLEAR


class ARMap(object):
    """The occupancy and clearance model, on a 0.1 mm grid over the board."""

    def __init__(self):
        self.w = int(round((L.X1 - L.X0) / AR_GRID)) + 1
        self.h = int(round((L.Y1 - L.Y0) / AR_GRID)) + 1
        n = self.w * self.h
        z = _array.array('h', [0])
        self.core = [z * n, z * n]
        self.halo = [z * n, z * n]
        self.vhalo = z * n          # too close for a VIA; one map, since a via crosses both
        self.cells = {}             # net -> [set of cells on F, set of cells on B]
        self.pads = {}              # net -> [(x0, y0, x1, y1, cx, cy, layers)]

    # -- coordinates
    def ij(self, x, y):
        return (int(round((x - L.X0) / AR_GRID)), int(round((y - L.Y0) / AR_GRID)))

    def xy(self, c):
        return (L.X0 + (c % self.w) * AR_GRID, L.Y0 + (c // self.w) * AR_GRID)

    # -- stamping.  `mark` writes one cell of one map with the net-or-contested rule.
    def _mark(self, m, c, net):
        v = m[c]
        if v == 0:
            m[c] = net
        elif v != net:
            m[c] = -1

    def _box(self, x0, y0, x1, y1, grow):
        i0, j0 = self.ij(x0 - grow, y0 - grow)
        i1, j1 = self.ij(x1 + grow, y1 + grow)
        return (max(0, i0), max(0, j0), min(self.w - 1, i1), min(self.h - 1, j1))

    def rect(self, m, x0, y0, x1, y1, grow, net, index=None):
        i0, j0, i1, j1 = self._box(x0, y0, x1, y1, grow)
        for j in range(j0, j1 + 1):
            base = j * self.w
            for i in range(i0, i1 + 1):
                self._mark(m, base + i, net)
                if index is not None:
                    index.add(base + i)

    def capsule(self, m, x0, y0, x1, y1, r, net, index=None):
        """Everything within r of the segment.  Exact, because the ground-drop stubs run at
        every angle and their bounding boxes would block a great deal of innocent copper."""
        i0, j0, i1, j1 = self._box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), r)
        dx, dy = x1 - x0, y1 - y0
        dd = dx * dx + dy * dy
        rr = r * r
        for j in range(j0, j1 + 1):
            py = L.Y0 + j * AR_GRID
            base = j * self.w
            for i in range(i0, i1 + 1):
                px = L.X0 + i * AR_GRID
                if dd <= 1e-12:
                    t = 0.0
                else:
                    t = ((px - x0) * dx + (py - y0) * dy) / dd
                    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                ex, ey = px - (x0 + t * dx), py - (y0 + t * dy)
                if ex * ex + ey * ey <= rr:
                    self._mark(m, base + i, net)
                    if index is not None:
                        index.add(base + i)

    def net_cells(self, net):
        if net not in self.cells:
            self.cells[net] = [set(), set()]
        return self.cells[net]


def _ar_build(comps, pos, padnet, netidx, placed, keepouts):
    """The map, from the pads, the vias and every track already emitted."""
    g = ARMap()
    hw = AR_W / 2.0

    # -- board edge: a border of hard-blocked cells, as a net nobody owns.  The outline is a
    #    rounded rectangle, so the corner radius is taken off the corners too.
    bw = AR_EDGE + hw
    nb = int(bw / AR_GRID) + 1
    for j in range(g.h):
        base = j * g.w
        edge = j < nb or j >= g.h - nb
        span = range(g.w) if edge else list(range(0, nb)) + list(range(g.w - nb, g.w))
        for i in span:
            g.halo[0][base + i] = -1
            g.halo[1][base + i] = -1
            g.vhalo[base + i] = -1
    r = L.EDGE_R
    for cx, cy, sx, sy in ((L.X0 + r, L.Y0 + r, -1, -1), (L.X1 - r, L.Y0 + r, 1, -1),
                           (L.X0 + r, L.Y1 - r, -1, 1), (L.X1 - r, L.Y1 - r, 1, 1)):
        i0, j0, i1, j1 = g._box(min(cx, cx + sx * r), min(cy, cy + sy * r),
                                max(cx, cx + sx * r), max(cy, cy + sy * r), 0.0)
        for j in range(j0, j1 + 1):
            y = L.Y0 + j * AR_GRID
            base = j * g.w
            for i in range(i0, i1 + 1):
                x = L.X0 + i * AR_GRID
                if (x - cx) * sx > 0 and (y - cy) * sy > 0 \
                        and math.hypot(x - cx, y - cy) > r - AR_EDGE - hw:
                    g.halo[0][base + i] = -1
                    g.halo[1][base + i] = -1
                    g.vhalo[base + i] = -1

    # -- pads.  A through-hole pad is copper on both layers; an SMD pad only on F.Cu, which is
    #    the layer every SMD part on this board is on.
    for ref, pn, net, px, py, pw, ph, smd, _pid in pads_board(comps, pos, padnet):
        net = net or -1
        _cn, cl = _ar_class(net)
        grow = hw + max(AR_CLEAR, cl)
        x0, y0, x1, y1 = px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2
        lays = (0,) if smd else (0, 1)
        idx = g.net_cells(net) if net > 0 else None
        for ly in lays:
            g.rect(g.core[ly], x0, y0, x1, y1, 0.0, net, idx[ly] if idx else None)
            g.rect(g.halo[ly], x0, y0, x1, y1, grow, net)
        g.rect(g.vhalo, x0, y0, x1, y1, AR_VIA / 2.0 + max(AR_CLEAR, cl), net)
        # A via that half-overlaps a pad -- its OWN pad; a foreign one is already excluded by
        # the line above -- joins it through a crescent of copper narrower than either, which
        # is a connection-width violation even though nothing is shorted.  Keep the annulus
        # off the pad entirely and let a track make the join at full width.
        g.rect(g.vhalo, x0, y0, x1, y1, AR_VIA / 2.0, -1)
        if net > 0:
            g.pads.setdefault(net, []).append((x0, y0, x1, y1, px, py, lays))

    # -- tracks already emitted: the hand routes and the ground-drop stubs.
    for x0, y0, x1, y1, w, layer, net in TRACK_LOG:
        ly = AR_LAYERS.index(layer) if layer in AR_LAYERS else None
        if ly is None:
            continue
        net = net or -1
        _cn, cl = _ar_class(net)
        idx = g.net_cells(net) if net > 0 else None
        g.capsule(g.core[ly], x0, y0, x1, y1, w / 2.0, net, idx[ly] if idx else None)
        g.capsule(g.halo[ly], x0, y0, x1, y1, w / 2.0 + hw + max(AR_CLEAR, cl), net)
        g.capsule(g.vhalo, x0, y0, x1, y1, w / 2.0 + AR_VIA / 2.0 + max(AR_CLEAR, cl), net)

    # -- vias already placed: thermal arrays, stitching, ground drops.  These cross both layers.
    for vx, vy, vs, vd, vnet in placed:
        vnet = vnet or -1
        _cn, cl = _ar_class(vnet)
        idx = g.net_cells(vnet) if vnet > 0 else None
        for ly in (0, 1):
            g.capsule(g.core[ly], vx, vy, vx, vy, vs / 2.0, vnet, idx[ly] if idx else None)
            g.capsule(g.halo[ly], vx, vy, vx, vy, vs / 2.0 + hw + max(AR_CLEAR, cl), vnet)
        g.capsule(g.vhalo, vx, vy, vx, vy, vs / 2.0 + AR_VIA / 2.0 + max(AR_CLEAR, cl), vnet)

    # -- places nothing may go at all: the antenna keep-out, the mounting holes, and (for vias
    #    only) the GND_IN island, for the reason stitch_vias() gives -- a hole punched through
    #    the input island is copper taken out of the one net carrying the whole load current.
    for kx0, ky0, kx1, ky1 in keepouts:
        g.rect(g.halo[0], kx0, ky0, kx1, ky1, hw, -1)
        g.rect(g.halo[1], kx0, ky0, kx1, ky1, hw, -1)
        g.rect(g.vhalo, kx0, ky0, kx1, ky1, AR_VIA / 2.0, -1)
    for mx, my in mount_holes():
        rr = L.MOUNT_PAD / 2.0 + AR_CLEAR
        for ly in (0, 1):
            g.capsule(g.halo[ly], mx, my, mx, my, rr + hw, -1)
        g.capsule(g.vhalo, mx, my, mx, my, rr + AR_VIA / 2.0, -1)
    # The island is an axis-aligned staircase, so it is rasterised by scanline rather than by
    # asking in_gnd_in_island() about all 1.4 million cells -- which is a 10-edge polygon test
    # per cell and takes minutes.  Three scanlines per row, at y - halo, y and y + halo, with
    # the x spans grown by the halo, reproduce that function's five-point test as a superset.
    ih = AR_VIA / 2.0 + AR_CLEAR
    poly = L.GND_IN_ISLAND
    nvp = len(poly)
    for j in range(g.h):
        y = L.Y0 + j * AR_GRID
        base = j * g.w
        spans = []
        for dy in (-ih, 0.0, ih):
            py = y + dy
            xs = []
            for k in range(nvp):
                x0, y0 = poly[k]
                x1, y1 = poly[(k + 1) % nvp]
                if (y0 > py) != (y1 > py):
                    xs.append(x0 + (py - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            grow = 0.0 if dy == 0.0 else ih
            for k in range(0, len(xs) - 1, 2):
                spans.append((xs[k] - grow, xs[k + 1] + grow))
        for xa, xb in spans:
            i0 = max(0, int(math.ceil((xa - L.X0) / AR_GRID)))
            i1 = min(g.w - 1, int((xb - L.X0) / AR_GRID))
            for i in range(i0, i1 + 1):
                g.vhalo[base + i] = -1
    return g


def _ar_components(g, net):
    """The connected pieces of `net`'s existing copper, as lists of (cell, layer).

    Flood fill over the net's own core cells, 4-connected within a layer and joined between
    layers wherever the net has a via.  Two pads that DRC calls unconnected are two components
    here; when this returns one component the net is done.
    """
    idx = g.cells.get(net)
    if not idx:
        return []
    seen = set()
    comps = []
    for ly0 in (0, 1):
        for start in idx[ly0]:
            # A cell recorded at stamp time may since have been overwritten by another net's
            # copper, which makes it contested rather than ours.  Starting a flood there would
            # report one bogus single-cell component per such cell.
            if (start, ly0) in seen or g.core[ly0][start] != net:
                continue
            stack = [(start, ly0)]
            seen.add((start, ly0))
            comp = []
            while stack:
                c, ly = stack.pop()
                comp.append((c, ly))
                i = c % g.w
                nb = []
                if i > 0:
                    nb.append((c - 1, ly))
                if i < g.w - 1:
                    nb.append((c + 1, ly))
                if c >= g.w:
                    nb.append((c - g.w, ly))
                if c < g.w * (g.h - 1):
                    nb.append((c + g.w, ly))
                # a cell that is this net's copper on BOTH layers is a via of this net
                other = 1 - ly
                if g.core[other][c] == net:
                    nb.append((c, other))
                for cc, ll in nb:
                    if (cc, ll) not in seen and g.core[ll][cc] == net:
                        seen.add((cc, ll))
                        stack.append((cc, ll))
            comps.append(comp)
    return comps


def _ar_search(g, net, srcs, dsts, dst_pts, box):
    """A* from a set of (cell, layer) to a set of (cell, layer).  Returns the path, or None.

    Costs are in tenths of a millimetre so they stay integers: 10 for an orthogonal step, 14
    for a diagonal one, AR_VIA_COST for a layer change.  The heuristic is the octile distance
    to the nearest destination pad centre, which is admissible because no step is cheaper per
    millimetre than a straight orthogonal run.
    """
    i0, j0, i1, j1 = box
    core, halo, vhalo, w = g.core, g.halo, g.vhalo, g.w

    def inbox(c):
        i = c % w
        return i0 <= i <= i1 and j0 <= (c // w) <= j1

    def pass_(c, ly):
        v = halo[ly][c]
        return v == 0 or v == net or core[ly][c] == net

    def hh(c):
        i, j = c % w, c // w
        best = 1 << 30
        for pi, pj in dst_pts:
            dx, dy = abs(i - pi), abs(j - pj)
            v = 10 * (dx + dy) - 6 * min(dx, dy) if AR_DIAG_OK else 10 * (dx + dy)
            if v < best:
                best = v
        return best

    goal = set(dsts)
    dist = {}
    prev = {}
    heap = []
    for c, ly in srcs:
        if not inbox(c):
            continue
        k = (c, ly)
        if k not in dist:
            dist[k] = 0
            _heapq.heappush(heap, (hh(c), 0, c, ly))
    pops = 0
    steps = ((1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10))
    diags = ((1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14))
    while heap:
        f, d, c, ly = _heapq.heappop(heap)
        if d > dist.get((c, ly), 1 << 30):
            continue
        if (c, ly) in goal:
            path = [(c, ly)]
            while (c, ly) in prev:
                c, ly = prev[(c, ly)]
                path.append((c, ly))
            path.reverse()
            return path
        pops += 1
        if pops > AR_MAX_POP:
            return None
        i, j = c % w, c // w
        for dx, dy, cost in steps:
            ni, nj = i + dx, j + dy
            if not (i0 <= ni <= i1 and j0 <= nj <= j1):
                continue
            nc = nj * w + ni
            if not pass_(nc, ly):
                continue
            nd = d + cost
            if nd < dist.get((nc, ly), 1 << 30):
                dist[(nc, ly)] = nd
                prev[(nc, ly)] = (c, ly)
                _heapq.heappush(heap, (nd + hh(nc), nd, nc, ly))
        if AR_DIAG_OK:
            for dx, dy, cost in diags:
                ni, nj = i + dx, j + dy
                if not (i0 <= ni <= i1 and j0 <= nj <= j1):
                    continue
                nc = nj * w + ni
                # no squeezing between two blocked cells on the diagonal
                if not (pass_(nc, ly) and pass_(j * w + ni, ly) and pass_(nj * w + i, ly)):
                    continue
                nd = d + cost
                if nd < dist.get((nc, ly), 1 << 30):
                    dist[(nc, ly)] = nd
                    prev[(nc, ly)] = (c, ly)
                    _heapq.heappush(heap, (nd + hh(nc), nd, nc, ly))
        # layer change
        oly = 1 - ly
        if vhalo[c] in (0, net) and pass_(c, oly):
            nd = d + AR_VIA_COST
            if nd < dist.get((c, oly), 1 << 30):
                dist[(c, oly)] = nd
                prev[(c, oly)] = (c, ly)
                _heapq.heappush(heap, (nd + hh(c), nd, c, oly))
    return None


def _ar_pad_at(g, net, cell, ly):
    """The pad of `net` whose box contains this cell on this layer, or None.

    The box is widened by half a grid cell because ARMap.rect() rounds to the nearest cell
    when it stamps, so the pad's copper in the map reaches half a cell beyond the real edge
    and A* is entitled to finish there.  Testing against the un-widened box misses exactly
    those ends -- which are the ones furthest off centre, so the very ones that need a lead.
    """
    x, y = g.xy(cell)
    h = AR_GRID / 2.0 + 1e-9
    for x0, y0, x1, y1, cx, cy, lays in g.pads.get(net, ()):
        if ly in lays and x0 - h <= x <= x1 + h and y0 - h <= y <= y1 + h:
            return (x0 - h, y0 - h, x1 + h, y1 + h, cx, cy)
    return None


def _ar_trim(g, net, seq):
    """Replace the run of in-pad cells at the head of `seq` with one lead from the pad centre.

    A* finishes on whatever cell of the target pad it reached first and then wanders about
    inside it, so the segment that actually crosses the pad boundary usually leaves through a
    corner.  The overlap is then a sliver: KiCad measures the connection across the sliver
    rather than across the track, which is a connection-width violation, and on a rounded-rect
    pad -- where the box this router works from is bigger than the copper -- the corner may not
    be pad copper at all, which is a dangling track.  Running one straight lead from the pad
    centre out to the first cell beyond the box crosses the boundary at full track width, at
    whatever angle it leaves.  The lead stays inside the box, which is copper of this net
    already, so it needs no clearance check of its own.

    Returns (cells to drop from the head, the lead, or None if the head is not in a pad).
    """
    c0, ly0 = seq[0]
    pad = _ar_pad_at(g, net, c0, ly0)
    if pad is None:
        return 0, None
    x0, y0, x1, y1, cx, cy = pad
    k = 0
    while k + 1 < len(seq) and seq[k + 1][1] == ly0:
        px, py = g.xy(seq[k + 1][0])
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            k += 1              # the first cell outside the box: the lead ends here
            break
        k += 1
    tx, ty = g.xy(seq[k][0])
    if abs(tx - cx) < 1e-9 and abs(ty - cy) < 1e-9:
        return k, None
    return k, (cx, cy, tx, ty, ly0)


def _ar_emit(g, net, path, out, placed):
    """Turn a cell path into segments and vias, and stamp it back into the map."""
    hw = AR_W / 2.0
    _cn, cl = _ar_class(net)
    grow = hw + hw + max(AR_CLEAR, cl)
    idx = g.net_cells(net)

    kh, lead_h = _ar_trim(g, net, path)
    kt, lead_t = _ar_trim(g, net, path[::-1])
    if kh + kt < len(path):
        path = path[kh:len(path) - kt]

    runs = []
    if lead_h:
        runs.append(("lead",) + lead_h)
    i = 0
    while i < len(path) - 1:
        c, ly = path[i]
        c2, ly2 = path[i + 1]
        if ly2 != ly:
            runs.append(("via", c, ly))
            i += 1
            continue
        d = (c2 % g.w - c % g.w, c2 // g.w - c // g.w)
        j = i + 1
        while j < len(path) - 1:
            c3, ly3 = path[j + 1]
            cj, lyj = path[j]
            if ly3 != lyj:
                break
            if (c3 % g.w - cj % g.w, c3 // g.w - cj // g.w) != d:
                break
            j += 1
        runs.append(("seg", c, path[j][0], ly))
        i = j
    if lead_t:
        runs.append(("lead",) + lead_t)

    n = 0
    for r in runs:
        if r[0] == "lead":
            _t, x0, y0, x1, y1, ly = r
            out.append(seg(x0, y0, x1, y1, AR_W, AR_LAYERS[ly], net, "ar%d.%d" % (net, n)))
            g.capsule(g.core[ly], x0, y0, x1, y1, hw, net, idx[ly])
            g.capsule(g.halo[ly], x0, y0, x1, y1, grow, net)
            g.capsule(g.vhalo, x0, y0, x1, y1, hw + AR_VIA / 2.0 + max(AR_CLEAR, cl), net)
        elif r[0] == "via":
            _c, ly = r[1], r[2]
            vx, vy = g.xy(_c)
            out.append(via(vx, vy, net, AR_VIA, AR_VIA_DRILL, "ar%d.%d" % (net, n)))
            placed.append((vx, vy, AR_VIA, AR_VIA_DRILL, net))
            for l2 in (0, 1):
                g.capsule(g.core[l2], vx, vy, vx, vy, AR_VIA / 2.0, net, idx[l2])
                g.capsule(g.halo[l2], vx, vy, vx, vy, AR_VIA / 2.0 + grow - hw, net)
            g.capsule(g.vhalo, vx, vy, vx, vy, AR_VIA + max(AR_CLEAR, cl), net)
        else:
            _c, _c2, ly = r[1], r[2], r[3]
            x0, y0 = g.xy(_c)
            x1, y1 = g.xy(_c2)
            out.append(seg(x0, y0, x1, y1, AR_W, AR_LAYERS[ly], net, "ar%d.%d" % (net, n)))
            g.capsule(g.core[ly], x0, y0, x1, y1, hw, net, idx[ly])
            g.capsule(g.halo[ly], x0, y0, x1, y1, grow, net)
            g.capsule(g.vhalo, x0, y0, x1, y1, hw + AR_VIA / 2.0 + max(AR_CLEAR, cl), net)
        n += 1
    return (len([r for r in runs if r[0] in ("seg", "lead")]),
            len([r for r in runs if r[0] == "via"]))


def autoroute(comps, pos, padnet, netidx, placed, keepouts):
    """Route every signal net that is not already whole.  Returns the segments and vias."""
    gnd = netidx.get("GND")
    t0 = _time.time()
    g = _ar_build(comps, pos, padnet, netidx, placed, keepouts)
    print("autorouter: clearance map over %d x %d cells in %.1f s"
          % (g.w, g.h, _time.time() - t0))

    todo = []
    for net in sorted(g.cells):
        if net <= 0 or net == gnd:
            continue
        cname, _cl = _ar_class(net)
        if cname in AR_SKIP_CLASSES:
            continue
        comps_ = _ar_components(g, net)
        if len(comps_) < 2:
            continue
        # shortest first: the tight nets get the channels before the loose ones fill them
        xs = [g.xy(c)[0] for cm in comps_ for c, _l in cm]
        ys = [g.xy(c)[1] for cm in comps_ for c, _l in cm]
        todo.append((max(xs) - min(xs) + max(ys) - min(ys), len(comps_), net))
    todo.sort()
    print("autorouter: %d net(s) to route, %.1f s to here"
          % (len(todo), _time.time() - t0))

    out = []
    done = fail = nseg = nvia = 0
    failed = []
    for _span, _n, net in todo:
        comps_ = _ar_components(g, net)
        # grow one component until it has swallowed the rest, nearest first
        while len(comps_) > 1:
            comps_.sort(key=len, reverse=True)
            src = comps_[0]
            rest = comps_[1:]
            sx = [g.xy(c) for c, _l in src]
            scx = sum(p[0] for p in sx) / len(sx)
            scy = sum(p[1] for p in sx) / len(sx)
            rest.sort(key=lambda cm: min(math.hypot(g.xy(c)[0] - scx, g.xy(c)[1] - scy)
                                         for c, _l in cm))
            dst = rest[0]
            dxy = [g.xy(c) for c, _l in dst]
            pts = [(int(round((x - L.X0) / AR_GRID)), int(round((y - L.Y0) / AR_GRID)))
                   for x, y in dxy[::max(1, len(dxy) // 8)]]
            path = None
            print("    %-26s %d piece(s), %.1f s" % (NETNAME.get(net, "?"), len(comps_),
                                                     _time.time() - t0))
            for margin in AR_MARGIN:
                allx = [p[0] for p in sx] + [p[0] for p in dxy]
                ally = [p[1] for p in sx] + [p[1] for p in dxy]
                box = (max(0, g.ij(min(allx) - margin, 0)[0]),
                       max(0, g.ij(0, min(ally) - margin)[1]),
                       min(g.w - 1, g.ij(max(allx) + margin, 0)[0]),
                       min(g.h - 1, g.ij(0, max(ally) + margin)[1]))
                path = _ar_search(g, net, src, set(dst), pts, box)
                if path:
                    break
            if not path:
                failed.append("%s (%d piece(s) left)" % (NETNAME.get(net, "?"), len(comps_)))
                fail += 1
                break
            s, v = _ar_emit(g, net, path, out, placed)
            nseg += s
            nvia += v
            done += 1
            comps_ = _ar_components(g, net)

    print("autorouter: %d connection(s) routed, %d segment(s), %d via(s)"
          % (done, nseg, nvia))
    if failed:
        print("  WARN: no path for %d net(s):" % len(failed))
        for f in failed:
            print("      %s" % f)
    return out


# --------------------------------------------------------------------------- main
NETNAME = {}


def main():
    comps, nets, padnet = read_netlist()
    NETNAME[0] = ""
    for code, name in nets:
        NETNAME[code] = name
    netidx = dict((name, code) for code, name in nets)

    missing = [c["ref"] for c in comps if not c["fp"] or load_fp(c["fp"]) is None]
    if missing:
        print("  WARN: no footprint for %d part(s): %s" % (len(missing), ", ".join(missing)))
    comps = [c for c in comps if c["ref"] not in missing]

    print("nets %d, parts %d" % (len(nets), len(comps)))
    # Pads the footprint has but the symbol does not -- see layout_pcb.PAD_ALIAS.
    for (ref, pad), src in sorted(L.PAD_ALIAS.items()):
        if (ref, src) in padnet:
            padnet[(ref, pad)] = padnet[(ref, src)]
            print("  pad alias: %s pad %s follows pad %s -> %s"
                  % (ref, pad, src, NETNAME[padnet[(ref, pad)]]))
        else:
            print("  WARN: PAD_ALIAS source %s pad %s is not in the netlist" % (ref, src))

    pos, unplaced, grid = place(comps)
    if unplaced:
        print("  ERROR: %d part(s) would not fit: %s" % (len(unplaced), ", ".join(unplaced)))

    body = []
    for c in sorted(comps, key=lambda c: natkey(c["ref"])):
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        fp = build_footprint(c, x, y, rot, padnet)
        if fp:
            body.append("\t" + dump(fp, 2))

    # Mounting holes: plain, NON-plated.  Tying signal GND to a metal enclosure at four points
    # is a grounding decision, not a layout default -- it stays out until someone decides it.
    mh = []
    for i, (mx, my) in enumerate(mount_holes()):
        c = dict(ref="H%d" % (i + 1), value="MountingHole", sheetname="", sheetfile="",
                 path="/" + str(_uuid.uuid5(NS, "mh%d" % i)),
                 fp=MOUNT_FP)
        fp = build_footprint(c, mx, my, 0, {})
        if fp:
            mh.append("\t" + dump(fp, 2))

    out = []
    out.append("(kicad_pcb")
    out.append("\t(version 20241229)")
    out.append('\t(generator "mccan-gen_pcb.py")')
    out.append('\t(generator_version "9.0")')
    out.append("\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)")
    out.append('\t(paper "A3")')
    out.append('\t(title_block\n\t\t(title "MCCAN Lighting Controller")\n'
               '\t\t(comment 1 "GENERATED by scripts/gen_pcb.py -- do not edit in pcbnew")\n'
               '\t\t(comment 2 "Board 140 x 100 mm, 4 layer, 1 oz outer / 2 oz inner copper")\n'
               '\t)')
    out.append(LAYERS)
    out.append(STACKUP)
    for code, name in [(0, "")] + nets:
        out.append("\t(net %d %s)" % (code, q(name)))
    out += mh
    out += body
    out += edge_cuts()
    out += notes()
    out += tim_areas()
    out += thermal_vias(comps, pos, padnet, netidx)
    out += stitch_vias(netidx, grid)
    # Ground drops go LAST of the vias, so `placed` already holds the thermal and
    # stitching ones and a drop cannot be put on top of either.
    kos = []
    for c in comps:
        if c["ref"] in pos:
            x, y, rot = pos[c["ref"]]
            kos += fp_keepouts(c["fp"], x, y, rot)
    # Hand routes go BEFORE the ground drops, so a drop cannot be placed on top of a route
    # via: gnd_drops tests every candidate against `placed`, and `placed` has to already hold
    # them for that test to mean anything.
    placed = list(VIA_LOG)
    out += routes(comps, pos, padnet, netidx, placed)
    dv, ds = gnd_drops(comps, pos, padnet, netidx, placed, kos)
    out += dv
    out += ds
    # The autorouter goes LAST of the copper, so its map sees the hand routes, the thermal and
    # stitching vias, and every ground drop as obstacles it has to work around.  Running it any
    # earlier would let it take the space a drop has no alternative to.
    out += autoroute(comps, pos, padnet, netidx, placed, kos)
    out += zones(netidx)
    out.append('\t(embedded_fonts no)')
    out.append(")")

    io.open(BOARD, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("wrote %s (%.1f kB)" % (BOARD, os.path.getsize(BOARD) / 1024.0))


if __name__ == "__main__":
    main()
