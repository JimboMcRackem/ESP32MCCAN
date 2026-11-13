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
import collections as _collections
import copy
import heapq as _heapq
import hashlib as _hashlib
import io
import json
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
# PCB_OUT redirects the write, so a throwaway board can be generated without standing on
# the real one -- that is what the external-router chain does when it wants an input board
# with the signal copper left off.  See docs/routing-tool.md.
BOARD = os.environ.get("PCB_OUT") or os.path.join(HW, "mccan.kicad_pcb")
# The external router's copper, frozen by scripts/freeze_routes.py.  When this file is
# present it REPLACES the autorouter below -- see docs/routing-tool.md.
FROZEN = os.path.join(HERE, "routes_signal.json")

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
        dn = find(c, "description")
        desc = unq(dn[1]) if dn is not None and len(dn) > 1 else ""
        dnp = any(unq(find(pr, "name")[1]) == "dnp" for pr in find_all(c, "property"))
        sp = find(c, "sheetpath")
        spath = unq(find(sp, "tstamps")[1]) if sp else "/"
        ts = unq(find(c, "tstamps")[1])
        comps.append(dict(ref=ref, value=val, fp=fp, sheetname=sheetname,
                          sheetfile=sheetfile, path=spath + ts, desc=desc, dnp=dnp))

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


SILK_REF_KEEP = ("J", "F", "TP", "U", "Q", "D", "L")
"""Reference designators that stay on the silkscreen.

Every one of the 398 silkscreen warnings was a Reference field -- over a pad, over a
neighbour's outline, or over another Reference.  None was between two real silk graphics.
That is what 233 parts on 140 x 100 mm costs: a 1 mm designator is about 2 mm wide and the
0402 field is on a 2 mm pitch, so the text cannot fit whatever it is moved to.

Value already lives on F.Fab, so moving the passives' references there too gives the
assembly drawing a fully labelled copy and leaves the silkscreen with outlines, pin-1 dots
and polarity marks -- which is what silkscreen is for at this density.  What a person has to
find on a finished board by eye stays: connectors, fuses, test points, and the semiconductors
worth probing.
"""


SILK_REF_GAP = 0.15
"""Clearance, mm, between a designator this moves and whatever it was moved off."""


def _font(prop):
    """(size_x, size_y, thickness) of a property's text, with KiCad's defaults."""
    eff = find(prop, "effects")
    fnt = find(eff, "font") if eff is not None else None
    sz = find(fnt, "size") if fnt is not None else None
    th = find(fnt, "thickness") if fnt is not None else None
    return (float(sz[1]) if sz is not None else 1.0,
            float(sz[2]) if sz is not None else 1.0,
            float(th[1]) if th is not None else 0.15)


def _text_wh(ref, prop):
    """How much board a designator covers, as (w, h) in mm at its own rotation.

    KiCad's stroke font runs a little under one em per glyph; 0.8 plus the stroke on each
    end is a slight over-estimate, which is the direction to err -- a box drawn too big only
    makes this pass fussier about where it puts the text.
    """
    sx, sy, tw = _font(prop)
    w, h = len(ref) * sx * 0.8 + tw, sy + tw
    at = find(prop, "at")
    ang = float(at[3]) if at is not None and len(at) > 3 else 0.0
    if int(round(ang / 90.0)) % 2:
        w, h = h, w
    return w, h


SILK_GFX = ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly")


def _gfx_box(g, fx, fy, rot):
    """Board-coordinate bbox of one footprint graphic, or None if it is not on front silk."""
    lay = find(g, "layer")
    if lay is None or unq(lay[1]) != "F.SilkS":
        return None
    st = find(g, "stroke")
    wd = find(st, "width") if st is not None else find(g, "width")
    hw = (float(wd[1]) / 2.0) if wd is not None and len(wd) > 1 else 0.05
    pts = []
    for h in ("start", "mid", "end", "center"):
        n = find(g, h)
        if n is not None and len(n) > 2:
            pts.append((float(n[1]), float(n[2])))
    p = find(g, "pts")
    if p is not None:
        pts += [(float(v[1]), float(v[2])) for v in find_all(p, "xy")]
    if g[0] == "fp_circle" and len(pts) == 2:
        # centre + a point on the rim: the square around the whole circle, not the chord.
        (cx, cy), (ex, ey) = pts
        r = math.hypot(ex - cx, ey - cy)
        pts = [(cx - r, cy - r), (cx + r, cy + r)]
    if not pts:
        return None
    xs, ys = [], []
    for lx, ly in pts:
        bx, by = rot_local(lx, ly, rot)
        xs.append(fx + bx)
        ys.append(fy + by)
    return (min(xs) - hw, min(ys) - hw, max(xs) + hw, max(ys) + hw)


def _hits(box, obstacles, skip):
    x0, y0, x1, y1 = box
    for owner, a0, b0, a1, b1 in obstacles:
        if owner == skip:
            continue
        if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
            return True
    return False


def silk_refs(built, comps, pos, padnet):
    """Put every kept designator somewhere it does not land on silk or on copper.

    All 68 of the board's silkscreen warnings were one thing: a reference field over a
    neighbour's outline (35) or over a pad (33).  None was between two real silk graphics,
    and none involved a track -- so this is a text-placement problem, and it is decidable
    here, before anything is routed.

    SILK_REF_KEEP already took this from 398 to 68 by moving every other prefix to F.Fab.
    Moving the rest there too would leave a board whose semiconductors cannot be identified
    by eye, which is the opposite of what silkscreen is for.  So each survivor is tried where
    the library put it, then at the four sides of its own body at increasing distance.  A
    designator that fits nowhere fails the build -- placement is the placer's job, not
    silkscreen's.

    Boxes are axis-aligned and deliberately a little generous: over-reporting costs a nudge,
    under-reporting costs a DRC warning.  A designator is tested against every OTHER
    footprint's silk and against EVERY pad including its own, which is the pair of rules KiCad
    itself applies -- it does not flag a footprint's text against its own outline.
    """
    obstacles, own = [], {}
    for ref, fx, fy, rot, fp in built:
        for g in fp:
            if not isinstance(g, list) or g[0] not in SILK_GFX:
                continue
            box = _gfx_box(g, fx, fy, rot)
            if box:
                obstacles.append((ref,) + box)
                own.setdefault(ref, []).append(box)
    for pd in pads_board(comps, pos, padnet):
        ref, _pn, _net, cx, cy, w, h = pd[0], pd[1], pd[2], pd[3], pd[4], pd[5], pd[6]
        box = (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
        obstacles.append((ref,) + box)
        own.setdefault(ref, []).append(box)

    moved = kept = 0
    gone = []
    for ref, fx, fy, rot, fp in sorted(built, key=lambda b: natkey(b[0])):
        if ref.rstrip("0123456789") not in SILK_REF_KEEP:
            continue
        prop = None
        for p in fp:
            if isinstance(p, list) and p[0] == "property" and unq(p[1]) == "Reference":
                prop = p
        if prop is None:
            continue
        lay = find(prop, "layer")
        if lay is None or not unq(lay[1]).endswith(".SilkS"):
            continue
        at = find(prop, "at")
        w, h = _text_wh(ref, prop)

        def box_at(cx, cy):
            return (cx - w / 2.0 - SILK_REF_GAP, cy - h / 2.0 - SILK_REF_GAP,
                    cx + w / 2.0 + SILK_REF_GAP, cy + h / 2.0 + SILK_REF_GAP)

        bx, by = rot_local(float(at[1]), float(at[2]), rot)
        cands = [(fx + bx, fy + by)]
        mine = own.get(ref) or [(fx - 0.5, fy - 0.5, fx + 0.5, fy + 0.5)]
        b0 = (min(m[0] for m in mine), min(m[1] for m in mine),
              max(m[2] for m in mine), max(m[3] for m in mine))
        mx, my = (b0[0] + b0[2]) / 2.0, (b0[1] + b0[3]) / 2.0
        # The ladder used to stop at 1.4 mm, which was enough only because anything it could
        # not place got shrunk and then demoted.  With those gone it has to reach: U3 is
        # placed rather than auto-flowed and the boost commutation loop around it is tight on
        # purpose -- D4, R14, R15/R16 and R12 all sit inside 1.4 mm of an edge -- so its
        # designator lands on the left at d = 2.95, and nothing shorter works.  Measured: at
        # 2.0 the build fails on U3 and on U3 alone.
        for push in (0.0, 0.3, 0.6, 0.9, 1.4, 2.0, 2.8):
            d = SILK_REF_GAP + push
            cands += [(mx, b0[1] - d - h / 2.0), (mx, b0[3] + d + h / 2.0),
                      (b0[0] - d - w / 2.0, my), (b0[2] + d + w / 2.0, my)]

        put = None
        for cx, cy in cands:
            if not _hits(box_at(cx, cy), obstacles, ref):
                put = (cx, cy)
                break
        if put is None:
            gone.append(ref)
            continue
        obstacles.append((ref,) + box_at(put[0], put[1]))
        if abs(put[0] - (fx + bx)) < 1e-6 and abs(put[1] - (fy + by)) < 1e-6:
            kept += 1
            continue
        lx, ly = rot_local(put[0] - fx, put[1] - fy, -rot)
        at[1], at[2] = num(lx), num(ly)
        moved += 1
    print("silk references: %d left alone, %d moved" % (kept, moved))
    if gone:
        raise SystemExit(
            "FAIL: %d reference designator(s) have nowhere legible to print:\n"
            "  %s\n"
            "This is a PLACEMENT failure, not a silkscreen one.  The old board answered it\n"
            "by shrinking the text and then demoting it to F.Fab, which left twelve parts\n"
            "unidentifiable on the bare board -- the opposite of what silkscreen is for.\n"
            "Give the part more room in scripts/layout_pcb.py, or nudge its neighbours."
            % (len(gone), ", ".join(gone)))


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
    ref = c["ref"]
    pre = ref.rstrip("0123456789")
    got_desc = [False]
    for p in props:
        nm = unq(p[1])
        if nm == "Reference":
            p[2] = q(ref)
            lay = find(p, "layer")
            if lay is not None and unq(lay[1]).endswith(".SilkS") and pre not in SILK_REF_KEEP:
                lay[1] = q(unq(lay[1])[:2] + "Fab")
        elif nm == "Value":
            p[2] = q(c["value"])
        elif nm == "Footprint":
            p[2] = q(spec)
        elif nm == "Description":
            p[2] = q(c.get("desc", ""))
            got_desc[0] = True

    # The symbol's Description and its Do-Not-Populate flag are part of what board parity
    # compares, and a footprint that carries neither reports as a mismatch for every part
    # that has one: 46 "Field 'Description' differs" plus 31 "'Do not populate' settings
    # differ".  The schematic is the source of truth for both, so both are copied across.
    if c.get("desc") and not got_desc[0]:
        props.append(["property", q("Description"), q(c["desc"]),
                      ["at", "0", "0", "0"],
                      ["unlocked", "yes"], ["layer", q("F.Fab")], ["hide", "yes"],
                      ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]])
    if c.get("dnp"):
        at = [k for k in keep if k[0] == "attr"]
        if at:
            if "dnp" not in at[0]:
                at[0].append("dnp")
        else:
            keep.insert(0, ["attr", "dnp"])

    # Every (at) that belongs to something orientable becomes absolute.
    for ch in props + keep:
        if ch[0] in ("property", "fp_text", "fp_text_box", "pad", "model"):
            at = find(ch, "at")
            if at and ch[0] != "model":
                addrot(at, rot)

    # A zone inside a footprint is the one child KiCad keeps in BOARD coordinates rather than
    # in the footprint's own frame.  Copied across verbatim, the ESP32 module's antenna
    # keep-out landed at the board origin instead of over the antenna: that is why U5 was the
    # only part DRC reported as differing from its library copy, and it meant DRC was policing
    # an empty rectangle off the edge of the board while the antenna itself was unguarded.
    # The placer and the router were never fooled -- fp_keepouts() does this same transform.
    for z in keep:
        if z[0] != "zone":
            continue
        for poly in find_all(z, "polygon"):
            for xy in find_all(find(poly, "pts"), "xy"):
                zx, zy = rot_local(float(xy[1]), float(xy[2]), rot)
                xy[1], xy[2] = num(x + zx), num(y + zy)

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
GUT = 1.2          # gutter between auto-flowed courtyards, mm


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

    # Accumulate rather than print-and-continue, for the reason routes() now accumulates:
    # an "ERROR:" that still writes a board is not a gate.  Demonstrated, on a throwaway copy
    # of PLACE with J5 moved onto J6 and J7 moved 1.25 mm off the left edge -- a synthetic
    # injection, never a state this board shipped in: all three checks below printed their
    # ERROR, main() ran on, the board was written and the process exited 0.  The three most
    # consequential placement faults the generator knows how to find were advisory text.
    # They now refuse, below.  The current board triggers none of the three -- established by
    # arming this gate and regenerating: the board reproduces byte-for-byte and no ERROR
    # appears in stdout.
    overlaps = []
    offboard = []

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
                overlaps.append((ref, other))
        if ref not in L.OFFBOARD_OK and (
                bx0 < L.X0 or by0 < L.Y0 or bx1 > L.X1 or by1 > L.Y1):
            print("  ERROR: %s courtyard %.2f..%.2f x %.2f..%.2f leaves the board"
                  % (ref, bx0, bx1, by0, by1))
            offboard.append(ref)
        hand[ref] = (bx0, by0, bx1, by1)
        pos[ref] = (x, y, rot)
        grid.mark(bx0 - halo, by0 - halo, bx1 + halo, by1 + halo)
        for kx0, ky0, kx1, ky1 in fp_keepouts(c["fp"], x, y, rot):
            grid.mark(kx0, ky0, kx1, ky1)

    # Refuse here, not in main(), and before the auto-flow runs: the same placement of the
    # raise that routes() uses.  main() accumulates the whole file in `out` and does not open
    # BOARD for writing until its last two lines, so nothing has been written yet and the
    # previous board survives intact.  There is no opt-out list because the current board
    # prints none of these three; if one is ever deliberate it needs an explicit named
    # exemption here (L.OFFBOARD_OK is the existing precedent), not a downgraded check.
    if overlaps or offboard:
        raise SystemExit("gen_pcb: hand placements refused -- %d overlapping pair(s), "
                         "%d courtyard(s) off the board.  %s not written."
                         % (len(overlaps), len(offboard), os.path.basename(BOARD)))

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

    # A NUDGE moves an AUTO-placed part after the packer has finished, without changing
    # where the packer put anything else.  Pinning the part in PLACE instead would lift it
    # out of the flow order, and every part that packs after it slides into the hole --
    # which silently invalidates every hand route in ROUTES that names a coordinate.  A
    # nudge is the smaller hammer.  The grid never learns about it, so nothing here proves
    # the result is legal: check_geometry is what does that, and it runs on every build.
    for ref, (dx, dy) in L.NUDGE.items():
        if ref not in pos:
            print("  WARN: NUDGE has %s, which is not auto-placed" % ref)
            continue
        if ref in L.PLACE:
            print("  WARN: NUDGE and PLACE both name %s; edit PLACE instead" % ref)
            continue
        x, y, rot = pos[ref]
        pos[ref] = (x + dx, y + dy, rot)
    return pos, unplaced, grid


MOUNT_FP = "MountingHole:MountingHole_3.2mm_M3"

# --------------------------------------------------------------------------- vias
#
# Thermal vias are 0.5 / 0.25 mm, not the 0.8 / 0.4 used for stitching.  A small via is the
# right one here: the array has to fit INSIDE a pad that may be only 1.675 mm square (U3's
# QFN paddle), and thermal resistance falls with via COUNT far faster than with via diameter
# -- the barrel is a 25 um copper tube either way, so a 0.5 mm via has about 60 % of the
# copper cross-section of a 0.8 mm one but four of them fit where one did.
# 0.55 rather than 0.50 buys the annular ring, not the copper: 0.55/0.25 is a 0.15 mm ring,
# which is PCBWay's published minimum and is stated for exactly this case -- "for pads with
# vias in the middle".  At 0.50/0.25 the ring was 0.125 mm and under it.  The cost is eight
# vias, because the bigger via insets the array further: D4 goes 6x5 -> 5x5 and U9 3x5 -> 3x4,
# while U1, U2 and U3 are unchanged.  That is affordable on the argument this file already
# makes above -- the array stops being the bottleneck once it is well under the 8-15 K/W of
# the gap pad, and 25 vias under D4 still is.
THERM_VIA, THERM_DRILL = 0.55, 0.25
THERM_PITCH = 0.8
# mm of pad copper left outside the via annulus.  Held at 0.15 deliberately when THERM_VIA
# grew: the clearance that binds is via-to-NEIGHBOURING-pad (see thermal_vias below), 0.15 +
# 0.20 = 0.35 mm against the 0.30 mm the POWER class asks.  Dropping it to 0.125 would have
# kept D4 at 6x5, and left 0.025 mm of margin instead of 0.05 mm to do it.  Not a trade worth
# making for five vias.
THERM_MARGIN = 0.15

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
# Nets that own a plane or pour a thermal-via array can land in (plan4: Task 5 zones).
PLANED_NETS = ("GND", "/VBAT", "/VBAT_B", "/GND_B", "/power_input/GND_IN")


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
            # The epsilon is not decoration.  uw is a difference of floats, so a pad whose
            # usable width is an exact multiple of the pitch lands on either side of the
            # integer by luck: 4.80 - 2*(0.275 + 0.125) is 3.9999999999999996, and int() of
            # that over 0.8 gives 4 where the arithmetic says 5, silently costing a column.
            # Whether a via array gets one more column should not be decided by rounding.
            nx = int(uw / THERM_PITCH + 1e-9) + 1
            ny = int(uh / THERM_PITCH + 1e-9) + 1
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


# The three GND planes carry DISTINCT user-facing names, and that is not cosmetic.
#
# KiCad names a gerber after the layer's USER name when it has one, and this board stores
# `(usegerberextensions no)` (see PCBPLOT below), which makes every plot file `.gbr`.  While
# all three planes were called "GND" a `--board-plot-params` export wrote mccan-GND.gbr three
# times: In1.Cu, In3.Cu and In6.Cu collapsed into one file and two ground planes vanished with
# no error, no warning and a job file that still listed fifteen paths.  A board that passes
# every gate becomes a four-layer order.  The extension-based names it happened to get away
# with before (.g1 / .g3 / .g6) were an accident of the export invocation, not a property of
# the board.
#
# Nothing in this repo keys off these strings: every script addresses layers by their canonical
# name (In1.Cu, In3.Cu, In6.Cu) -- grep confirmed, and the zones below are named separately
# (GND_IN1 / GND_IN3 / GND_IN6) and are unchanged.  In4.Cu keeps "PWR" because it is already
# unique; renaming it would move a gerber filename for no fab-facing gain.
LAYERS = """	(layers
		(0 "F.Cu" signal)
		(4 "In1.Cu" power "GND_In1")
		(6 "In2.Cu" signal)
		(8 "In3.Cu" power "GND_In3")
		(10 "In4.Cu" power "PWR")
		(12 "In5.Cu" signal)
		(14 "In6.Cu" power "GND_In6")
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


def _check_layer_names(layers):
    """Fail generation if two layers would plot to the same gerber filename.

    A layer plots under its user name when it has one and its canonical name otherwise, so
    those effective names must be unique -- case-insensitively, since the files land on a
    Windows filesystem.  This is the regression guard for the collapse described above: it
    happened once silently, and a hand-written LAYERS table can repeat a name again."""
    seen = {}
    for canon, user in re.findall(r'\(\d+ "([^"]+)" \w+(?: "([^"]+)")?\)', layers):
        name = user or canon
        prev = seen.setdefault(name.lower(), canon)
        assert prev == canon, (
            f"layers {prev} and {canon} both plot as {name!r}: their gerbers would overwrite "
            f"each other.  Give each a unique user name in LAYERS.")


_check_layer_names(LAYERS)

# The layers a track may legally sit on, and the layers where one is a slot cut through a
# reference plane.  Kept here rather than in the autorouter section because they are a fact
# about the STACKUP, not about any one router: check_geometry.py grades against them and
# route_external.py hands them to KiCadRoutingTools, and both would otherwise have to repeat
# the list and drift from it.
#
# AR_LAYERS, further down, is a SUBSET of SIGNAL_LAYERS and deliberately so.  gen_pcb's own
# router carries a two-layer occupancy grid, so widening it is a rewrite of the grid rather
# than a change to a constant.  It is the fallback now that routes_signal.json exists, so it
# keeps the two layers it understands and the external router gets all four.
SIGNAL_LAYERS = ("F.Cu", "In2.Cu", "In5.Cu", "B.Cu")
PLANE_LAYERS = ("In1.Cu", "In3.Cu", "In4.Cu", "In6.Cu")

# 8-layer, 1.6 mm, 1 oz throughout (2026-09-23).  Was six.
#
#   F.Cu   signal -- component escapes, short runs
#   In1.Cu GND, solid
#   In2.Cu signal -- the CAN pair lives here
#   In3.Cu GND, solid
#   In4.Cu POWER -- VBAT, solid
#   In5.Cu signal -- bulk routing
#   In6.Cu GND, solid
#   B.Cu   signal -- short runs, plate side
#
# Four routing layers, three ground planes, one power layer.
#
# WHAT THIS FIXES THAT SIX DID NOT.  The six-layer stack was
# F sig / GND / sig / VBAT / sig / B sig, in which B.Cu is a signal layer whose only
# neighbour is another signal layer.  Bottom-side traces had no adjacent reference plane and
# so no defined return path -- the B.Cu GND pour is on the SAME layer as those traces, which
# is not the same thing as a plane beneath them.  Here every signal layer has a solid GND
# plane on at least one face, and In2.Cu has one on both.
#
# WHY CAN GOES ON In2.Cu.  Between two solid planes it is a buried stripline, so "CAN
# segregated from the high-current and boost nets" is satisfied by construction rather than
# by a keep-away rule that nothing enforces -- the pair is physically enclosed in copper.  It
# is also off the two layers where the feed pours and the switch node live.
#
# WHY In4.Cu IS VBAT ALONE.  VLOGIC_IN, +24V and +5V were POWER-class 2.0 mm tracks; as
# pad-bounded island zones at priority 1 they would have cost no routing effort at all, and
# spec 3.2 took that trade.  Measured on this placement it does not hold: a rail's island is
# a bounding box over every one of its pads, and the rails interleave with VBAT and with each
# other across the whole board.  /+24V's eleven pads alone span x 83.38..174.58, an island
# that swallows five /VBAT pads -- the boost input caps and the boost inductor, the highest-
# current taps on the layer.  So the rails are routed instead (see route_external.HANDS_OFF)
# and In4.Cu carries VBAT and nothing else.  check_plane_width.py measured the old VBAT
# pour's worst cut at 71 mm against the 11.44 mm IPC-2221 asks for 7.0 A at a 10 K rise on
# 1 oz internal copper -- a 6.1x margin -- and it runs on every build and fails the board if
# that margin is gone.
#
# Return paths under the split are sound: In5.Cu is the only signal layer adjacent to In4.Cu
# and it has solid In6.Cu GND on its other face.
#
# AR_LAYERS, further down, is a SUBSET of SIGNAL_LAYERS and deliberately so.  gen_pcb's own
# router carries a two-layer occupancy grid, so widening it is a rewrite of the grid rather
# than a change to a constant.  It is the fallback now that routes_signal.json exists, so it
# keeps the two layers it understands and the external router gets all four.
#
# DIELECTRICS.  Foil lamination: three cores (In1/In2, In3/In4, In5/In6) bonded by four
# prepregs, with F.Cu and B.Cu as foil outside.  Symmetric about the middle core, which is
# what keeps the panel flat.  Copper 8 x 0.035 = 0.28; dielectric 1.2908; total 1.5708 mm,
# exactly as the six-layer stack summed to.  Sub-thicknesses are nominal -- the fab adjusts
# them to hit 1.6 mm.
#
#   F.Cu  --0.100 prepreg-- In1 --0.200 core-- In2 --0.2454 prepreg-- In3
#         --0.200 core-- In4 --0.2454 prepreg-- In5 --0.200 core-- In6
#         --0.100 prepreg-- B.Cu
#
# The 0.1 mm outer prepregs put F.Cu and B.Cu tight against their GND planes, which is what
# makes an outer-layer escape's return path short.
STACKUP = """	(setup
		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 2" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2454) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 4" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 5" (type "prepreg") (thickness 0.2454) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In5.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 6" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In6.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 7" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
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
# rules.min_hole_to_hole from scripts/gen_netclasses.py -- a fab floor, not a netclass one,
# so it applies between two drills on the same net as much as on different ones.
HOLE_TO_HOLE = 0.3

# The float-tie allowance, subtracted from every clearance and hole-to-hole comparison in this
# file so that an arithmetic tie is not decided by the last bit of a double.  It is ONE number
# with ONE name because eleven copies of a literal drift, and because every comment below says
# "the same float-tie allowance" -- which has to stay true.
#
# It was 1e-6 mm, and the comment justifying that said one nanometre is "three orders below
# anything a fab holds or KiCad writes".  Both halves of that were confused.  1e-6 mm is one
# MICROmetre, not one nanometre, and it is exactly one KiCad internal unit -- KiCad stores
# board geometry in integer nanometres, so 1e-6 mm is 1000 of the smallest distance KiCad can
# represent.  The blind spot was therefore not "three orders below anything": it was a full
# 1000 representable steps wide, and a gap genuinely 1 nm short of the rule passed here and was
# an error in KiCad's own DRC.  Nor was it three orders below this board's margins -- the
# tightest legitimate slack measured on it is +0.000317 mm, only 317x the old epsilon.
#
# 1e-9 mm is one nanometre: one KiCad internal unit, the smallest gap that can differ from a
# tie at all.  Float error on gaps built from ~200 mm coordinates is ~1e-15 mm here, six orders
# below this, so it still absorbs every tie.  Measured on this board, every comparison at every
# site (1.6 million of them):
#   drop via vs foreign track   691108 comparisons, one strictly negative -- the GND via at
#                               (163.875, 26.900) against /outputs/MUXIN_RL_R on B.Cu, at
#                               -0.000000000000002 -- plus three exact zeros; none below -1e-9
#   hand via vs frozen track    two exact ties at 0.300 mm, ROUTE_VIAS[36] (/VBAT) against
#                               /outputs/MUXIN_RR_B and Net-(U7-~{OE}); none below -1e-9
#   hand track vs track         391422 comparisons, none negative, tightest tie exactly 0.0
#   hand track vs via           399958 comparisons, none negative, tightest slack +0.000317
#   hand via hole-to-hole       106400 comparisons, tightest slack +0.2066 -- decorative here
# The +0.000317 is the tightest legitimate slack on the whole board, so a 1e-6 epsilon sat only
# 317x below the thing it was supposed to be invisible against; 1e-9 sits 317000x below it.
#
# Two independent checks that this is a behavioural no-op today: building with TIE = 1e-9 gives
# a board byte-identical to the one 1e-6 produced (md5 6c4f884ff624c5b9d3bc484f7bb2613e) and 0
# ERROR lines, and building with TIE = 0.0 refuses -- on the two 0.300 mm hand-via ties above --
# which is what makes the allowance load-bearing rather than decoration.
TIE = 1e-9


def net_clearance(code):
    """The clearance the netclass rules actually apply to a net, by net code."""
    name = NETNAME.get(code) or ""
    short = name.rsplit("/", 1)[-1]
    for cname, tw, cl, vd, vdr, nets in L.NETCLASSES:
        if name in nets or short in nets:
            return cl
    return DROP_DEFAULT_CLEAR


_DRU_FLOOR = None


def dru_floor():
    """Per-footprint clearance floors, read back out of the generated mccan.kicad_dru.

    gen_netclasses.py writes a rule for every footprint whose vendor land pattern is
    tighter than the clearance the netclasses would apply -- U1, U2 and U10 today.  Those
    rules are what let a 0.5 mm-pitch part exist on this board at all, and KiCad tests a
    clearance condition with the two items in BOTH orders, so `A.memberOfFootprint('U10')`
    relaxes a track against a U10 pad just as much as it relaxes two U10 pads against each
    other.  That is broader than the comment in the .dru describes, and it is also the only
    reason a track can escape U10's pins: at 0.30 mm the legal band between pin 4's
    neighbours is 0.06 mm wide, i.e. there isn't one.

    So the checker has to apply the same floor, or it reports violations on copper KiCad
    passes and we learn to ignore it.  Parsing the artifact rather than re-deriving the
    scan keeps the two from drifting: if a ref stops needing a rule, it stops getting the
    exemption here on the same run.

    Missing file -> empty map -> the netclass clearance stands, which is the safe way to
    be wrong.
    """
    global _DRU_FLOOR
    if _DRU_FLOOR is None:
        _DRU_FLOOR = {}
        try:
            txt = io.open(os.path.join(HW, "mccan.kicad_dru"),
                          encoding="utf-8").read()
        except IOError:
            txt = ""
        for blk in txt.split("(rule ")[1:]:
            m = re.search(r"\(min\s+([0-9.]+)mm\)", blk)
            for ref in re.findall(r"A\.memberOfFootprint\('([^']+)'\)", blk):
                if m:
                    _DRU_FLOOR[ref] = min(_DRU_FLOOR.get(ref, 9e9), float(m.group(1)))
    return _DRU_FLOOR


def pad_clearance(pad, code):
    """Clearance required between a foreign net `code` and pad `pad`."""
    need = max(net_clearance(pad[2]), net_clearance(code))
    floor = dru_floor().get(pad[0])
    return need if floor is None else min(need, floor)


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


def prim_bbox(pad):
    """Bounding box of a custom pad's `primitives`, in pad-local mm, or None.

    Only the vertex/centre geometry is read; a primitive's stroke `width` is added on all sides
    so an unfilled outline is not under-reported.
    """
    prims = find(pad, "primitives")
    if prims is None:
        return None
    xs, ys = [], []
    for g in prims[1:]:
        if not isinstance(g, list) or not g:
            continue
        wd = find(g, "width")
        hw = (float(wd[1]) / 2.0) if wd is not None and len(wd) > 1 else 0.0
        pts = find(g, "pts")
        got = []
        if pts is not None:
            got = [(float(q[1]), float(q[2])) for q in pts[1:]
                   if isinstance(q, list) and q and q[0] == "xy"]
        elif g[0] in ("gr_circle", "gr_arc"):
            ctr, end = find(g, "center"), find(g, "end")
            if ctr is not None and end is not None:
                cx, cy = float(ctr[1]), float(ctr[2])
                r = math.hypot(float(end[1]) - cx, float(end[2]) - cy)
                got = [(cx - r, cy - r), (cx + r, cy + r)]
        elif g[0] == "gr_line":
            st, end = find(g, "start"), find(g, "end")
            if st is not None and end is not None:
                got = [(float(st[1]), float(st[2])), (float(end[1]), float(end[2]))]
        for qx, qy in got:
            xs += [qx - hw, qx + hw]
            ys += [qy - hw, qy + hw]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


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
            ox = oy = 0.0
            if unq(p[3]) == "custom":
                # A custom pad's `size` is only its ANCHOR shape.  The copper that actually gets
                # etched is the union of the anchor with the `primitives`, and on a power package
                # that is very much bigger: Q10's pad 3 reads `size 2.9 x 8.7` but its two polys
                # span 8.0 x 10.1 and sit off to one side of the anchor.  Routing against the
                # anchor alone drove three Q10_G tracks straight across the MID drain.
                bb = prim_bbox(p)
                if bb is not None:
                    x0 = min(bb[0], -w / 2.0); y0 = min(bb[1], -h / 2.0)
                    x1 = max(bb[2], w / 2.0); y1 = max(bb[3], h / 2.0)
                    w, h = x1 - x0, y1 - y0
                    ox, oy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            th = math.radians(pa)
            cth, sth = abs(math.cos(th)), abs(math.sin(th))
            bw, bh = w * cth + h * sth, w * sth + h * cth
            ax, ay = float(at[1]), float(at[2])
            if ox or oy:
                # The offset is in the pad's own frame, so it turns by the pad's angle -- and
                # by the pad's angle ALONE.  `pa` is pad + part, and rot_local() below turns
                # the finished (ax, ay) by the part again, so using `pa` here counted the
                # part's rotation twice.  On Q11 (a 180 part whose drain tab sits 1.15 mm off
                # its anchor) that put the tab 2.30 mm west of its real copper, which is a
                # third of the tab's width; KiCad's own DRC found the SNS track 0.15 mm off a
                # pad this function had reported as 2.45 mm clear.  Wrong in the optimistic
                # direction, so nothing here caught it -- only the real DRC did.
                pl = float(at[3]) if len(at) > 3 else 0.0
                c_, s_ = math.cos(math.radians(pl)), math.sin(math.radians(pl))
                ax += ox * c_ + oy * s_
                ay += -ox * s_ + oy * c_
            dx, dy = rot_local(ax, ay, rot)
            out.append((c["ref"], pn, padnet.get((c["ref"], pn)),
                        x + dx, y + dy, bw, bh, unq(p[2]) == "smd", len(out)))
    return out


class BoxHash(object):
    """A 4 mm bucket grid over anything that can name its own bounding box.

    Takes (item, x0, y0, x1, y1).  This is what makes the frozen router's 4690 segments and
    855 vias usable as obstacles: a board-wide scan per candidate site is 141 pads x hundreds
    of candidates x thousands of obstacles, which does not finish.

    `near` lives here only.  It used to exist twice, verbatim, here and in Hash -- which is now
    a subclass that only knows how to turn a pad tuple into a box.
    """

    CELL = 4.0

    def __init__(self, items):
        self.b = {}
        for it, x0, y0, x1, y1 in items:
            for i in range(int(x0 / self.CELL), int(x1 / self.CELL) + 1):
                for j in range(int(y0 / self.CELL), int(y1 / self.CELL) + 1):
                    self.b.setdefault((i, j), []).append(it)

    def near(self, x0, y0, x1, y1):
        out = []
        for i in range(int(x0 / self.CELL), int(x1 / self.CELL) + 1):
            for j in range(int(y0 / self.CELL), int(y1 / self.CELL) + 1):
                out += self.b.get((i, j), [])
        return out


class Hash(BoxHash):
    """BoxHash over the pads, so a candidate test is local rather than board-wide.

    A pad tuple from pads_board() is (ref, pad, net, cx, cy, w, h, smd, id) with an
    axis-aligned bbox, so the box is just centre +- half-size.  The bucket ranges this
    produces are the same integers the hand-written version computed, so the index and every
    `near` result are unchanged.
    """

    def __init__(self, items):
        BoxHash.__init__(self, [(it, it[3] - it[5] / 2, it[4] - it[6] / 2,
                                 it[3] + it[5] / 2, it[4] + it[6] / 2) for it in items])


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


def _rect_gap(a, b):
    """Gap between two (x0, y0, x1, y1) rectangles; 0.0 if they touch or overlap."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


def _seg_box(x0, y0, x1, y1, w):
    return (min(x0, x1) - w / 2, min(y0, y1) - w / 2,
            max(x0, x1) + w / 2, max(y0, y1) + w / 2)


def _pt_seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 == 0.0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / d2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _seg_seg_dist(a0, a1, b0, b1):
    """Distance between two segments; 0.0 if they cross or touch."""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2 = side(a0, a1, b0), side(a0, a1, b1)
    d3, d4 = side(b0, b1, a0), side(b0, b1, a1)
    if ((d1 > 0.0) != (d2 > 0.0)) and ((d3 > 0.0) != (d4 > 0.0)):
        return 0.0
    # Collinear and touching cases fall through to the endpoint distances, which return
    # 0.0 for them anyway, so the strict test above does not need to handle them.
    return min(_pt_seg_dist(b0[0], b0[1], a0[0], a0[1], a1[0], a1[1]),
               _pt_seg_dist(b1[0], b1[1], a0[0], a0[1], a1[0], a1[1]),
               _pt_seg_dist(a0[0], a0[1], b0[0], b0[1], b1[0], b1[1]),
               _pt_seg_dist(a1[0], a1[1], b0[0], b0[1], b1[0], b1[1]))


def _seg_rect_gap(p0, p1, w, rect):
    """Gap between a w-wide track segment and an (x0, y0, x1, y1) rectangle.

    The track is a capsule -- the segment swept by a round w-wide brush -- and not the
    bounding box of its two endpoints.  For a diagonal run the two differ wildly: the
    bounding box of a 12 mm 45 degree segment is a 12 mm square, so testing the box
    reports a clearance violation against every pad inside that square, almost none of
    which the copper goes anywhere near.  Those false alarms are worse than useless:
    they bury the real violations in the same list.

    The rectangle stays a rectangle.  Pads are modelled by their bounding box everywhere
    else in this file -- a round pad included -- and that is the conservative side to err
    on, so it is left alone.

    Vias are the exception and do not come here: they are discs, and _seg_disc_gap below
    says why a box is the wrong shape rather than a cautious one.  gnd_drops' via_ok is the
    one place that still hands this function a via box, deliberately, and says so.
    """
    x0, y0, x1, y1 = rect
    for (px, py) in (p0, p1):
        if x0 <= px <= x1 and y0 <= py <= y1:
            return 0.0
    c = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    d = min(_seg_seg_dist(p0, p1, c[k], c[(k + 1) % 4]) for k in range(4))
    return max(0.0, d - w / 2)


# --- vias are round, and a bounding square is not a conservative approximation of a circle
#
# A pad is modelled by its bounding box everywhere in this file, and _seg_rect_gap's docstring
# argues that is the conservative side to err on.  That argument is about a pad: a pad has an
# orientation and a shape the box encloses, and erring outward describes copper that might be
# there.  A via has neither.  It is a disc, always, and its bounding square claims copper at
# the corners that does not exist -- over-reporting the intrusion by (sqrt(2)-1)*s/2, which is
# 0.124 mm for a 0.6 mm via and lands in full whenever a track approaches the barrel off-axis.
#
# That is not a safety margin, it is a different rule.  It cost this board a real ruling: the
# 12 findings check_track_crossings raised the first time it ran after the frozen router copper
# (Task 10 Step 6.0) were every one of them a square-corner artifact -- all 12 clear under the
# disc, KiCad's own DRC found 0 violations on the same copper, and the model had been 0.124 mm
# tighter than the rule KiCad enforces since Task 7.  The ruling is at
# .superpowers/sdd/2026-09-23-pcb-relayout-8layer/task-10-step6-ruling.md, which .gitignore
# excludes -- it is in the working tree and not in a clone, so the paragraph above is the
# clone's copy of the reasoning and not a pointer to it.
#
# So: pads keep the box, vias get these.  Do not "simplify" a via back onto _seg_rect_gap.

def _seg_disc_gap(p0, p1, w, cx, cy, dia):
    """Gap between a w-wide track segment and a via of diameter `dia` centred (cx, cy).

    Copper to copper: the track is the capsule swept by a round w-wide brush and the via is
    a disc, so the gap is the centreline-to-centre distance less both radii.  Clamped at 0.0
    when they overlap, like the rest of the gap helpers here.
    """
    return max(0.0, _pt_seg_dist(cx, cy, p0[0], p0[1], p1[0], p1[1]) - dia / 2.0 - w / 2.0)


def _disc_disc_gap(ax, ay, adia, bx, by, bdia):
    """Gap between two vias, both discs.  0.0 if they touch or overlap."""
    return max(0.0, math.hypot(ax - bx, ay - by) - adia / 2.0 - bdia / 2.0)


def _pad_on(p, layer):
    """Is this pad present on `layer`?

    pads_board() keeps only pads whose layer list names F.Cu or *.Cu, and no footprint on
    this board sits on B.Cu, so an SMD pad here is an F.Cu pad and everything else is
    through-hole and reaches every layer.  Without this a route on In2.Cu is measured
    against every SMD pad on the front -- wrong in both directions at once: it refuses
    inner-layer lanes that are wide open, and it lets an inner-layer end "anchor" on a
    front pad it cannot touch without a via.
    """
    return (not p[7]) or layer == "F.Cu"


def _pad_box(p):
    _ref, _pn, _net, px, py, pw, ph, _smd, _pid = p
    return (px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2)


def check_track_crossings(lo, hi):
    """Every hand route against every other piece of copper on its layer.

    routes() checks its segments against pads and against vias, which is what it had to do
    when the hand routes were the only tracks on the board.  They are not any more: there
    are 142 ground-drop stubs, and the hand routes now cross each other's paths in the
    eFuse block.  Both gaps were invisible here and both were found by KiCad instead -- a
    MID tap laid straight across the SNS and OUT sense pair, and a VBAT_F run 0.145 mm off
    a ground drop, because the width had been widened after the clearance was worked out by
    hand.  Anything the generator cannot see, it cannot stop me repeating.

    TRACK_LOG[lo:hi] is what routes() emitted; everything else in TRACK_LOG is a drop, a
    stub, or the autorouter's own work.  Each hand segment is compared against every track
    on the same layer belonging to another net -- hand routes included, so a pair of them
    crossing is caught too.  The autorouter's output is compared against but not among
    itself: it has its own model of the rules and re-litigating it here would only produce
    noise nobody would read.

    The caller has to run this AFTER the copper it is meant to compare against exists.  It
    used to be called between gnd_drops() and the router, which meant "every other piece of
    copper on its layer" was the drops and the other hand routes and nothing else -- the
    router's several thousand segments and vias were created afterwards and were invisible
    here, so a hand route could be laid straight through frozen router copper and this
    function would say nothing.  It is now called after the frozen/autoroute branch, which
    is still after gnd_drops, so both orderings hold.
    """
    close = []
    for i in range(lo, min(hi, len(TRACK_LOG))):
        ax0, ay0, ax1, ay1, aw, alay, anet = TRACK_LOG[i]
        for j, (bx0, by0, bx1, by1, bw, blay, bnet) in enumerate(TRACK_LOG):
            if j == i or blay != alay or bnet == anet:
                continue
            if j >= lo and j < hi and j < i:
                continue        # hand-vs-hand pair already done in the other order
            need = max(net_clearance(anet), net_clearance(bnet))
            gap = _seg_seg_dist((ax0, ay0), (ax1, ay1),
                                (bx0, by0), (bx1, by1)) - (aw + bw) / 2
            # `need - TIE`, not `need`: the same float-tie allowance that
            # check_drop_via_crossings explains below, applied here for the same reason.
            # The tightest hand-vs-hand pair on this board is an exact tie --
            # /power_input/SNS against /power_input/VBAT_PROT on F.Cu at (36.90, 96.50),
            # gap 0.300000 against a 0.300 need -- so under a strict `<` whether the build
            # passes is decided by the last bit of a double rather than by any real copper.
            # The allowance only ever lets a gap through, so it cannot fail a board that
            # passes today, and at one nanometre it is the narrowest allowance that can
            # absorb a tie at all -- KiCad's own geometry grid is one nanometre.
            if gap < need - TIE:
                close.append("%s (%.2f,%.2f)-(%.2f,%.2f) vs %s (%.2f,%.2f)-(%.2f,%.2f) "
                             "on %s: %.3f < %.3f"
                             % (NETNAME.get(anet, "?"), ax0, ay0, ax1, ay1,
                                NETNAME.get(bnet, "?"), bx0, by0, bx1, by1,
                                alay, gap, need))
        # Vias, for the same reason.  routes() tests against `placed`, which at that point
        # holds only the thermal and stitching fields -- every one of the 142 ground drops
        # is created afterwards and was invisible to it.
        for vx, vy, vs, _vd, vnet in VIA_LOG:
            if vnet == anet:
                continue
            need = max(net_clearance(anet), net_clearance(vnet))
            # _seg_disc_gap, not _seg_rect_gap: the via is round.  See the note above it.
            gap = _seg_disc_gap((ax0, ay0), (ax1, ay1), aw, vx, vy, vs)
            # `need - TIE`: the same float-tie allowance, for the same reason.
            if gap < need - TIE:
                close.append("%s (%.2f,%.2f)-(%.2f,%.2f) vs a %s via (%.2f,%.2f): "
                             "%.3f < %.3f"
                             % (NETNAME.get(anet, "?"), ax0, ay0, ax1, ay1,
                                NETNAME.get(vnet, "?"), vx, vy, gap, need))
    if close:
        raise SystemExit("hand routes clash with other copper:\n  "
                         + "\n  ".join(sorted(set(close))))


def check_via_holes(lo, hi):
    """Hole-to-hole between every hand via and every other via on the board.

    A hand route that changes layer where the router already changed layer lands on the
    router's own via, and the fab is handed two 0.30 mm drills 0.02 mm apart, which is a slot
    it did not ask for. Three of Step 6.1/6.1b's hand vias were exactly that, and the only
    reason they were ever noticed is that Step 6.3 hit the same thing and the numbers were
    looked at directly.

    This docstring used to say KiCad's DRC "skips pairs on the SAME net, so DRC says nothing".
    That is FALSE and it was asserted here and at four places in layout_pcb.py. KiCad 10.0
    checks same-net hole-to-hole and reports it -- verified by duplicating the /+24V via at
    (90.300, 30.700) 0.1414 mm away on its own net:

        [hole_to_hole]: Drilled hole too close to other hole
            (board setup constraints min 0.2995 mm; actual 0.0000 mm)
            Rule: board setup constraints; warning
            @(90.3000 mm, 30.7000 mm): Via [/+24V] on F.Cu - B.Cu
            @(90.4000 mm, 30.8000 mm): Via [/+24V] on F.Cu - B.Cu

    What silenced it was the SEVERITY, not the net: `hole_to_hole` was set to `warning` in
    mccan.kicad_pro and the gate runs `--severity-error`, which discards warnings entirely.
    One `--severity-all` run would have covered every pair on the board -- the router's and
    the drops' included, on the same net and on different nets -- for free, and that is the
    gate nobody reached for. scripts/gen_netclasses.py now writes `hole_to_hole` at `error`.

    This function is still worth having, for the reason the rest of this file exists: it
    refuses at generate time, before a board is written, so a bad hand via never reaches the
    artifact KiCad would be asked about. But it is a first line, not the only one, and the
    residual it used to claim ("router-vs-router and drop-vs-drop pairs on the same net are
    ungated, and KiCad will not look") was wrong twice over -- the ungated population included
    DIFFERENT-net router and drop pairs as well, and KiCad does look.

    Nothing else in the generator covers it: routes() checks a hand via against `placed`, which
    at that point is the thermal and stitching fields only, and gnd_drops() does its own
    hole-to-hole but only for drops. So this is the hand vias' turn, VIA_LOG[lo:hi], against
    every via on the board -- the router's included, and its own net included, because a drill
    does not care what net it is on. min_hole_to_hole is 0.3 mm (scripts/gen_netclasses.py);
    TIE is the same float-tie allowance as check_drop_via_crossings above.

    Where this fires, the fix is usually not to move the hand via but to delete it: if the
    router already has a via on this net within a hair of it, the hand run can simply end on
    the router's via and change layer there.
    """
    close = []
    for i in range(lo, min(hi, len(VIA_LOG))):
        ax, ay, _as, ad, anet = VIA_LOG[i]
        for j, (bx, by, _bs, bd, bnet) in enumerate(VIA_LOG):
            if j == i:
                continue
            gap = math.hypot(ax - bx, ay - by) - (ad + bd) / 2.0
            if gap < HOLE_TO_HOLE - TIE:
                close.append("a %s via (%.3f,%.3f) drill %.2f vs a %s via (%.3f,%.3f) "
                             "drill %.2f: hole-to-hole %.3f < %.3f"
                             % (NETNAME.get(anet, "?"), ax, ay, ad,
                                NETNAME.get(bnet, "?"), bx, by, bd, gap, HOLE_TO_HOLE))
    if close:
        raise SystemExit("hand vias are too close to another drill:\n  "
                         + "\n  ".join(sorted(set(close))))


def frozen_routes(netidx):
    """Emit the copper an external router laid, as frozen by scripts/freeze_routes.py.

    The board stays generated: this reads data, not a board.  A run on a machine with no
    router installed produces the same copper as the run that first laid it, which is the
    whole point -- see docs/routing-tool.md 4.

    Widths and layers come from the file rather than from AR_W / AR_LAYERS, because the
    external router is allowed to neck a track down or lay a power net wide, and re-stamping
    everything at one width would quietly undo that.
    """
    doc = json.load(io.open(FROZEN, encoding="utf-8"))
    nets = doc.get("nets", {})
    drop = set(getattr(L, "FROZEN_DROP", ()))
    out, nseg, nvia, missing, dropped = [], 0, 0, [], []
    for name in sorted(nets):
        net = netidx.get(name)
        if net is None:
            missing.append(name)
            continue
        if name in drop:
            # layout_pcb.FROZEN_DROP: this net is hand-authored in ROUTES, so the router's
            # copper for it -- usually an abandoned fanout via -- is not wanted.
            dropped.append(name)
            continue
        d = nets[name]
        for i, r in enumerate(d.get("segments", ())):
            out.append(seg(r[0], r[1], r[2], r[3], r[4], r[5], net, "fz%d.s%d" % (net, i)))
            nseg += 1
        for i, v in enumerate(d.get("vias", ())):
            out.append(via(v[0], v[1], net, v[2], v[3], "fz%d.v%d" % (net, i)))
            nvia += 1
    print("frozen routes: %d segment(s), %d via(s) over %d net(s) from %s"
          % (nseg, nvia, len(nets) - len(missing) - len(dropped), os.path.basename(FROZEN)))
    if dropped:
        print("  dropped %d net(s) named in layout_pcb.FROZEN_DROP: %s"
              % (len(dropped), ", ".join(dropped)))
    for name in sorted(drop - set(dropped)):
        # A stale entry would silently do nothing, and the next reader would believe it.
        print("  WARNING: FROZEN_DROP names %r, which the frozen file does not carry" % name)
    if missing:
        # A net in the frozen file that the board no longer has means the schematic moved
        # under the freeze.  Carrying on would drop that net's copper without saying so.
        print("FAIL: %d frozen net(s) are not on this board: %s"
              % (len(missing), ", ".join(missing[:8])))
        print("      Re-run scripts/route_external.py and scripts/freeze_routes.py,")
        print("      or delete %s to fall back to the built-in router." % FROZEN)
        raise SystemExit(1)
    return out


NETNAME = {}




# ---------------------------------------------------------------- copper from layout_pcb tables
def zones(netidx):
    """Pours from layout_pcb.ZONES: (net, [layers], [(x, y), ...], name, priority).

    Fill is left to `kicad-cli pcb drc --refill-zones` / the fab step; the file holds outlines
    only, so it stays byte-stable across regenerations.
    """
    out = []
    for net, layers, poly, name, prio in L.ZONES:
        code = netidx.get(net)
        if code is None:
            raise SystemExit("gen_pcb: zone %s names net %s, which is not in the netlist" % (name, net))
        pts = " ".join("(xy %s %s)" % (num(x), num(y)) for x, y in poly)
        out.append('\t(zone\n\t\t(net %d)\n\t\t(net_name %s)\n\t\t(layers %s)\n'
                   '\t\t(uuid %s)\n\t\t(name %s)\n\t\t(hatch edge 0.5)\n\t\t(priority %d)\n'
                   '\t\t(connect_pads\n\t\t\t(clearance 0.3)\n\t\t)\n'
                   '\t\t(min_thickness 0.2)\n\t\t(filled_areas_thickness no)\n'
                   '\t\t(fill\n\t\t\t(thermal_gap 0.3)\n\t\t\t(thermal_bridge_width 0.4)\n\t\t)\n'
                   '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n\t)'
                   % (code, q(net), " ".join(q(x) for x in layers), U("zone:" + name), q(name),
                      prio, pts))
    return out


def routes(netidx):
    """Hand copper from layout_pcb.ROUTES and ROUTE_VIAS.

    ROUTES:     (net, layer, width, [(x, y), ...], tag)  -- a polyline, one segment per pair.
    ROUTE_VIAS: (net, x, y, size, drill, tag)            -- through vias, F.Cu to B.Cu.
    """
    out = []
    for net, layer, width, pts, tag in L.ROUTES:
        code = netidx.get(net)
        if code is None:
            raise SystemExit("gen_pcb: route %s names net %s, which is not in the netlist" % (tag, net))
        for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
            out.append(seg(x0, y0, x1, y1, width, layer, code, "%s.%d" % (tag, i)))
    for net, x, y, size, drill, tag in L.ROUTE_VIAS:
        code = netidx.get(net)
        if code is None:
            raise SystemExit("gen_pcb: via %s names net %s, which is not in the netlist" % (tag, net))
        out.append(via(x, y, code, size, drill, "rv" + tag))
    return out


def main():
    comps, nets, padnet = read_netlist()
    NETNAME[0] = ""
    for code, name in nets:
        NETNAME[code] = name
    netidx = dict((name, code) for code, name in nets)
    # layout_pcb names nets without the hierarchy prefix; accept both spellings.
    for code, name in nets:
        netidx.setdefault(name.rsplit("/", 1)[-1], code)

    missing = [c["ref"] for c in comps if not c["fp"] or load_fp(c["fp"]) is None]
    if missing:
        raise SystemExit("gen_pcb: no footprint for %d part(s): %s" % (len(missing), ", ".join(missing)))
    print("nets %d, parts %d" % (len(nets), len(comps)))

    # FRAME ONLY until Task 4 fills PLACE / REGIONS: outline, holes, stack and rules, no parts.
    frame_only = not L.PLACE and not L.REGIONS
    if frame_only:
        print("frame only: layout_pcb has no placement yet -- no footprints written")
        pos, unplaced, grid = {}, [], None
    else:
        pos, unplaced, grid = place(comps)
    if unplaced:
        print("  ERROR: %d part(s) would not fit: %s" % (len(unplaced), ", ".join(unplaced)))
        raise SystemExit("gen_pcb: %d part(s) would not fit.  %s not written."
                         % (len(unplaced), os.path.basename(BOARD)))

    built = []
    for c in sorted(comps, key=lambda c: natkey(c["ref"])):
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        fp = build_footprint(c, x, y, rot, padnet)
        if fp:
            built.append((c["ref"], x, y, rot, fp))
    if built:
        silk_refs(built, comps, pos, padnet)
    body = ["\t" + dump(fp, 2) for _r, _x, _y, _rt, fp in built]

    # Mounting holes: plain, NON-plated (no enclosure ground bond decided).
    mh = []
    for i, (mx, my) in enumerate(mount_holes()):
        c = dict(ref="H%d" % (i + 1), value="MountingHole", sheetname="", sheetfile="",
                 path="/" + str(_uuid.uuid5(NS, "mh%d" % i)), fp=MOUNT_FP)
        fp = build_footprint(c, mx, my, 0, {})
        if fp:
            fp.insert(2 if isinstance(fp[1], str) else 1,
                      ["attr", "board_only", "exclude_from_bom", "exclude_from_pos_files"])
            mh.append("\t" + dump(fp, 2))

    out = []
    out.append("(kicad_pcb")
    out.append("\t(version 20241229)")
    out.append('\t(generator "mccan-gen_pcb.py")')
    out.append('\t(generator_version "9.0")')
    out.append("\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)")
    out.append('\t(paper "A4")')
    out.append('\t(title_block\n\t\t(title "MCCAN Lighting Controller (plan4)")\n'
               '\t\t(comment 1 "GENERATED by scripts/gen_pcb.py -- do not edit in pcbnew")\n'
               '\t\t(comment 2 "Board %g x %g mm, 8 layer, 1 oz copper on all layers, JLCPCB")\n'
               '\t)' % (L.BOARD_W, L.BOARD_H))
    out.append(LAYERS)
    out.append(STACKUP)
    for code, name in [(0, "")] + nets:
        out.append("\t(net %d %s)" % (code, q(name)))
    out += mh
    out += body
    out += edge_cuts()
    out += notes()
    if not frame_only:
        out += thermal_vias(comps, pos, padnet, netidx)
    _rt_lo, _rv_lo = len(TRACK_LOG), len(VIA_LOG)
    out += routes(netidx)
    if os.path.exists(FROZEN):
        out += frozen_routes(netidx)
    check_track_crossings(_rt_lo, len(TRACK_LOG))
    check_via_holes(_rv_lo, len(VIA_LOG))
    out += zones(netidx)
    out.append('\t(embedded_fonts no)')
    out.append(")")

    io.open(BOARD, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("wrote %s (%.1f kB)" % (BOARD, os.path.getsize(BOARD) / 1024.0))


if __name__ == "__main__":
    main()
