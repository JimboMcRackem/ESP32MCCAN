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

SILK_REF_MIN_H = 0.8
SILK_REF_MIN_T = 0.08
"""The smallest a designator is allowed to get, mm.

These are the board's OWN minimums -- mccan.kicad_pro carries min_text_height 0.8 and
min_text_thickness 0.08 -- so shrinking to exactly them is the most room this can buy without
trading a silkscreen warning for a text_height one, which is not a trade."""


def _font_set(prop, sx, sy, tw):
    """Set a property's font size and stroke, in place."""
    eff = find(prop, "effects")
    fnt = find(eff, "font") if eff is not None else None
    if fnt is None:
        return
    sz = find(fnt, "size")
    if sz is not None:
        sz[1], sz[2] = num(sx), num(sy)
    th = find(fnt, "thickness")
    if th is not None:
        th[1] = num(tw)


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
    the library put it, then at the four sides of its own body at increasing distance, and
    only demoted to F.Fab if the part is boxed in on every side.

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

    moved = kept = shrunk = 0
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
        for push in (0.0, 0.3, 0.6, 0.9, 1.4):
            d = SILK_REF_GAP + push
            cands += [(mx, b0[1] - d - h / 2.0), (mx, b0[3] + d + h / 2.0),
                      (b0[0] - d - w / 2.0, my), (b0[2] + d + w / 2.0, my)]

        put, small = None, False
        for cx, cy in cands:
            if not _hits(box_at(cx, cy), obstacles, ref):
                put = (cx, cy)
                break
        if put is None:
            # Nothing fits at the library's text size.  Shrinking the designator is a smaller
            # loss than not printing it: SILK_REF_SHRINK still clears the 0.15 mm silkscreen
            # minimum most fabs quote, and a part whose label is small is more use than a part
            # with no label at all.
            sx, sy, tw = _font(prop)
            if sy > SILK_REF_MIN_H:
                k = SILK_REF_MIN_H / sy
                _font_set(prop, sx * k, SILK_REF_MIN_H, max(SILK_REF_MIN_T, tw * k))
                w, h = _text_wh(ref, prop)
                for cx, cy in cands:
                    if not _hits(box_at(cx, cy), obstacles, ref):
                        put, small = (cx, cy), True
                        break
                if put is None:
                    _font_set(prop, sx, sy, tw)
        if put is None:
            # Boxed in on every side even shrunk.  Value already lives on F.Fab, so the
            # assembly drawing still names the part; what is lost is reading it off the
            # bare board.
            lay[1] = q(unq(lay[1])[:2] + "Fab")
            gone.append(ref)
            continue
        if small:
            shrunk += 1
        obstacles.append((ref,) + box_at(put[0], put[1]))
        if abs(put[0] - (fx + bx)) < 1e-6 and abs(put[1] - (fy + by)) < 1e-6:
            kept += 1
            continue
        lx, ly = rot_local(put[0] - fx, put[1] - fy, -rot)
        at[1], at[2] = num(lx), num(ly)
        moved += 1
    print("silk references: %d left alone, %d moved, %d shrunk, %d demoted to F.Fab"
          % (kept, moved, shrunk, len(gone)))
    if gone:
        print("  no silkscreen room for: %s" % ", ".join(gone))


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


def stitch_vias(netidx, grid):
    """GND vias tying In1.Cu, B.Cu and the F.Cu pours together (Step 6).

    Every one of these punches a hole in the In3.Cu power plane it passes through, which is why
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
		(6 "In2.Cu" signal)
		(8 "In3.Cu" power "PWR")
		(10 "In4.Cu" signal)
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

# The layers a track may legally sit on, and the layers where one is a slot cut through a
# reference plane.  Kept here rather than in the autorouter section because they are a fact
# about the STACKUP, not about any one router: check_geometry.py grades against them and
# route_external.py hands them to KiCadRoutingTools, and both would otherwise have to repeat
# the list and drift from it.
#
# AR_LAYERS, further down, is a SUBSET of this and deliberately so.  gen_pcb's own router
# carries a two-layer occupancy grid -- core, halo and vhalo are pairs, and a via is modelled
# as crossing "both" layers -- so widening it to six is a rewrite of the grid rather than a
# change to a constant.  It is the fallback path now that routes_signal.json exists, so it
# keeps the two layers it understands and the external router gets all four.
SIGNAL_LAYERS = ("F.Cu", "In2.Cu", "In4.Cu", "B.Cu")
PLANE_LAYERS = ("In1.Cu", "In3.Cu")

# 6-layer, 1.6 mm, 1 oz throughout.
#
#   F.Cu   signal
#   In1.Cu GND, solid and unbroken -- the reference plane spec 10 asks for
#   In2.Cu signal
#   In3.Cu VBAT, the 7.0 A feed
#   In4.Cu signal
#   B.Cu   signal
#
# Why six and not the five that was asked for (2026-09-22): a five-layer board is laminated
# out of a six-layer stack with one copper layer left unused, so it costs the same money, and
# an odd stack is asymmetric, so it warps more in reflow.  Six buys two routing layers instead
# of one for that money and puts a reference plane next to every signal layer.
#
# Why six at all: F.Cu and B.Cu alone did not close the board.  The external router settled at
# about 100 of 139 signal nets with the rest failing for want of a channel, and the failures
# were not clustered -- they were one pad here and one pad there across forty nets, which is
# what running out of layer looks like rather than what a bad net order looks like.
#
# Why 1 oz on the INNER layers, where this board used to carry 2 oz:
#
#   1. In2.Cu and In4.Cu now carry tracks, and at 2 oz PCBWay cannot etch them to this
#      board's rules.  Their inner-layer minimum is 4/4 mil at 1 oz but 6/8 mil at 2 oz, and
#      8 mil is 0.203 mm -- ABOVE the 0.20 mm clearance every net class here declares.  A
#      fab's inner copper weight is one selector for all inner layers unless you pay for a
#      custom stackup, so the signal layers decide it for the planes too.
#
#   2. The 2 oz was bought for the VBAT plane, on the argument that IPC-2221 wants 11.44 mm
#      of internal width for 7.0 A at a 10 K rise at 1 oz against 5.72 mm at 2 oz.  That
#      argument was never measured, and it is wrong by a wide margin: scripts/check_plane_width.py
#      rasterises the pour, punches all 1190 via and through-hole antipads out of it, and cuts
#      it in both directions.  The worst cut carries 71 mm of copper.  That is 6.1x what 1 oz
#      needs, so the weight was never what made the feed work -- having a whole layer was.
#
# The OUTER copper stays 1 oz for the reason it always did: 2 oz etching cannot hold the
# 0.15 mm pad-to-pad U10's land pattern needs, nor reliably the 0.20 mm the QFN/VSON parts
# need, and every land pattern lives on an outer layer.
#
# The dielectrics are a foil lamination -- two cores (In1/In2 and In3/In4) bonded by three
# prepregs, with F.Cu and B.Cu as foil on the outside.  It is symmetric about the middle
# prepreg, which is what keeps the panel flat.  The sub-thicknesses are nominal; the fab
# adjusts them to hit 1.6 mm.
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
			(layer "dielectric 3" (type "prepreg") (thickness 0.7608) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 4" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 5" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
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
    In2.Cu  -- nothing.  It is a signal layer and the router owns it; see SIGNAL_LAYERS.
    In3.Cu  -- VBAT, end to end.  It used to be split down x = 105 with +24V on the right, and
               that split was wrong in both directions: seven of the eleven +24V pads are LEFT
               of it (D4, C61, C20, C21, C22, R12) and two of the fifteen VBAT pads are RIGHT
               of it (C45, C46).  The two nets interleave across the whole board, so no
               straight line separates them -- the vertical split was not a lobe short of D4,
               it was the wrong model.

               The way out is not a cleverer split but the current figures.  VBAT is the 7.0 A
               feed and wants every millimetre of plane it can get; +24V is the boost output at
               0.5 A (spec 6), against 3.94 A of capability on a 2.0 mm POWER track at 1 oz.
               Giving half the power plane to the rail that needs it least starved the one that
               needs it most.  So In3.Cu is VBAT alone, and +24V is routed as POWER tracks --
               which is exactly what its net class was already sized for.

               It carried 2 oz until the board went to six layers.  It does not need to:
               scripts/check_plane_width.py measures the worst cut across this pour, with
               every antipad punched out of it, at 71 mm against the 11.44 mm IPC-2221 asks
               of 1 oz.  What carries the feed is having a layer, not having thick copper.
    In4.Cu  -- nothing, for the same reason as In2.Cu.
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

    # Pad connection is `thru_hole_only`: thermal reliefs for through-hole pads, solid copper
    # for SMD.  With reliefs on everything, three SMD pads came back as starved_thermal -- one
    # spoke where the zone asks for two -- because a routed track had crossed the line a second
    # spoke would have taken.  Chasing spokes around the autorouter is the wrong fix: this
    # board is reflow-assembled, where a relief on an SMD pad buys nothing and costs ground
    # impedance, and on the GND_IN island and the VBAT plane that impedance is the point.  The
    # connectors and other through-hole parts, which someone may well touch with an iron, keep
    # their reliefs.
    def zone(net, layers, pts, tag, prio=0):
        code = netidx[net]
        lay = ("(layers " + " ".join(q(x) for x in layers) + ")") if len(layers) > 1 \
              else ("(layer " + q(layers[0]) + ")")
        return ("\t(zone (net %d) (net_name %s) %s (uuid %s)\n"
                "\t\t(name %s) (hatch edge 0.5) (priority %d)\n"
                "\t\t(connect_pads thru_hole_only (clearance 0.3))\n"
                "\t\t(min_thickness 0.3) (filled_areas_thickness no)\n"
                "\t\t(fill yes (thermal_gap 0.4) (thermal_bridge_width 0.5))\n"
                "%s\n\t)" % (code, q(net), lay, U("zone_" + tag), q(tag), prio, poly(pts)))

    full = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    out.append(zone("GND", ["In1.Cu"], full, "GND_INNER"))
    out.append(zone("GND", ["B.Cu"], full, "GND_BOT"))
    out.append(zone("/VBAT", ["In3.Cu"], full, "VBAT_IN3"))
    # D4's tab needs somewhere for its thermal array to land now that +24V has no plane.
    # Priority 2 so it wins against the B.Cu ground pour, which notches around it.
    out.append(zone("/+24V", ["B.Cu"], L.D4_24V_ISLAND, "24V_D4", prio=2))
    # The GND_IN island.  Its shape is dictated by where the input ground actually is, and it
    # is checked against the pads by scripts/check_grounds.py -- every GND_IN pad must sit in
    # it and no GND pad may.  Three features are deliberate:
    #
    #   * the body, x 22..62 y 53.5..94, covers the whole eFuse column -- U10, Q10/Q11, R100,
    #     the sense path and D2/R3.  The east edge was 66 until 2026-09-21, which put it 1.2 mm
    #     INSIDE the rails block (x 64..93) and wrapped input ground around the west pad column
    #     of U4, C14, C31, R8 and L4 -- two of U4's pads are GND, so check_grounds.py failed the
    #     moment U4 got a footprint, and L4 pad 1 is the 3V3 switch node, which wants input
    #     ground nowhere near it.  62 keeps 3 mm past the easternmost GND_IN pad (D2 at x 59)
    #     and clears the rails column by 2.8 mm;
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
# on the board, between chip pads, and every one of them punches a hole in the In3.Cu power
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
                # the offset is in the pad's own frame, so it turns with the pad, not the part
                c_, s_ = math.cos(math.radians(pa)), math.sin(math.radians(pa))
                ax += ox * c_ + oy * s_
                ay += -ox * s_ + oy * c_
            dx, dy = rot_local(ax, ay, rot)
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
AR_VIA_COST = 35               # in tenth-mm steps: a layer change is worth 3.5 mm of detour
AR_DIAG_OK = True
# Each layer has a grain: F.Cu runs east-west, B.Cu north-south.  Going across the grain is
# allowed but costs AR_CROSS a step instead of 10, so a route that needs both axes would
# rather pay for a via than cut a long diagonal swathe across the open field -- which is what
# partitions the board and strands every net that comes after.
AR_CROSS = 22
AR_DIAG_COST = 22
# mm the search box grows by, tried in order, each with the pop budget it is worth: a box
# four times the area needs four times the budget or it just runs out with the frontier still
# growing, which is what "pop" in the failure list means.
AR_MARGIN = ((6.0, 1), (14.0, 2), (30.0, 5))
AR_MAX_POP = 600000
AR_RETRY_POP = 0            # give up on one attempt rather than hang the generator
# Rip-up.  A net that cannot get through asks which nets are in the way and has them taken off
# the board, then they queue up again behind it.  The caps are what stop two nets trading the
# same channel for ever; every rip-up also costs a map rebuild, so they are not free.
AR_SOFT_COST = 3000         # what crossing another net costs the question "who is in my way?"
AR_MAX_RIPS = 120           # rip-ups in the whole run
AR_RIP_TRIES = 6            # times one net may ask
AR_RIP_LIMIT = 5            # times one net may be torn up
# Every rip-up makes the contested corridor dearer for everyone except the net that just won
# it.  Without this two nets swap the same channel back and forth until the budget runs out,
# which is exactly what the first run did.  100 is 10 mm of detour: enough to send the loser
# round the outside rather than back through the door it was just shown out of.
AR_HIST_BUMP = 100

# Fan-out.  A pad in a dense package can only leave its package one way, and a track laid
# along the outside of the pad row seals every pin behind it -- which is how seven ESP32 GPIOs
# ended up with 160 reachable cells each.  So every pin of a multi-pad part is given a short
# lane straight out of the package before general routing starts, and that lane is never
# ripped up.  Two-pin parts need this as much as the packages do: an 0402 in a row of 0402s
# is walled in by its neighbours' clearance halos on three sides, and the map showed pads
# whose every surrounding cell was contested -- unreachable by any route, for ever.
AR_FAN_PADS = 2             # parts with at least this many pads get fan-out
AR_FAN_GAP = 0.8            # mm clear of the package outline the lane has to reach
AR_FAN_MAX = 3.0            # mm the lane may be, at most
AR_FAN_MIN = 0.35           # mm past the pad edge, below which the lane is not worth having

# The nets the router is not allowed to touch, by class name.  GND is named directly.
AR_SKIP_CLASSES = ("FEED", "POWER", "CAN")
# Why the last _ar_search gave up: "pop" means it ran out of budget with the frontier still
# growing (raise AR_MAX_POP or shrink the box), "blocked" means it exhausted every reachable
# cell (real congestion, or a box too small to go round the obstacle).
_AR_WHY = [""]
# The search that just failed, kept so the rip-up pass can ask the same question softly.
_AR_STUCK = []


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
        self.hist = [_array.array('i', [0]) * n, _array.array('i', [0]) * n]
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

    def zero(self):
        if not hasattr(self, "_zero"):
            z = _array.array('i', [0]) * (self.w * self.h)
            self._zero = [z, z]
        return self._zero

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
    # A via is wider than a track, so it needs a wider border than one: measuring the via
    # keep-out with the track's half-width let U10_DRN drop two vias 0.7 mm from the outline,
    # 0.1 mm inside the 0.8 mm an 0.6 mm annulus actually needs.
    nb = int((AR_EDGE + hw) / AR_GRID) + 1
    nbv = int((AR_EDGE + AR_VIA / 2.0) / AR_GRID) + 1
    for j in range(g.h):
        base = j * g.w
        edge = j < nb or j >= g.h - nb
        span = range(g.w) if edge else list(range(0, nb)) + list(range(g.w - nb, g.w))
        for i in span:
            g.halo[0][base + i] = -1
            g.halo[1][base + i] = -1
        edge = j < nbv or j >= g.h - nbv
        span = range(g.w) if edge else list(range(0, nbv)) + list(range(g.w - nbv, g.w))
        for i in span:
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
                if not ((x - cx) * sx > 0 and (y - cy) * sy > 0):
                    continue
                d = math.hypot(x - cx, y - cy)
                if d > r - AR_EDGE - hw:
                    g.halo[0][base + i] = -1
                    g.halo[1][base + i] = -1
                if d > r - AR_EDGE - AR_VIA / 2.0:
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


def _ar_search(g, net, srcs, dsts, dst_pts, box, maxpop=None, soft=0, hist=True):
    """A* from a set of (cell, layer) to a set of (cell, layer).  Returns the path, or None.

    Costs are in tenths of a millimetre so they stay integers: 10 for an orthogonal step, 14
    for a diagonal one, AR_VIA_COST for a layer change.  The heuristic is the octile distance
    to the nearest destination pad centre, which is admissible because no step is cheaper per
    millimetre than a straight orthogonal run.
    """
    i0, j0, i1, j1 = box
    core, halo, vhalo, w = g.core, g.halo, g.vhalo, g.w
    # The net that has just had a channel cleared for it routes without the history penalty;
    # everyone else pays it, which is what stops the pair of them swapping the channel.
    hcost = g.hist if hist else g.zero()

    def inbox(c):
        i = c % w
        return i0 <= i <= i1 and j0 <= (c // w) <= j1

    def extra(c, ly):
        """What this cell adds to the cost: 0 if free to this net, None if it may not be used.

        With `soft` set, a cell held by exactly one other net costs that much instead of being
        refused, so the search still finds a way through a full board and the path it returns
        names the nets standing in the way.  Contested cells (-1) stay hard: those are the
        board edge, the keep-outs and the places where two nets already meet.
        """
        v = halo[ly][c]
        if v == 0 or v == net or core[ly][c] == net:
            return hcost[ly][c]
        if soft and v > 0:
            return soft + hcost[ly][c]
        return None

    def pass_(c, ly):
        return extra(c, ly) is not None

    def hh(c):
        # Manhattan, not octile: with the grain costs below no step is cheaper than 10 per
        # tenth of a millimetre of Manhattan distance -- a diagonal covers two units for 22,
        # dearer than the 20 two orthogonal steps cost -- so this is admissible, and it is
        # tighter than octile, which is what keeps the search from sprawling.
        i, j = c % w, c // w
        best = 1 << 30
        for pi, pj in dst_pts:
            v = 10 * (abs(i - pi) + abs(j - pj))
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
    ew, ns = 10, AR_CROSS                       # F.Cu: east-west is with the grain
    by_layer = (((1, 0, ew), (-1, 0, ew), (0, 1, ns), (0, -1, ns)),
                ((1, 0, ns), (-1, 0, ns), (0, 1, ew), (0, -1, ew)))
    diags = ((1, 1, AR_DIAG_COST), (1, -1, AR_DIAG_COST),
             (-1, 1, AR_DIAG_COST), (-1, -1, AR_DIAG_COST))
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
        if pops > (maxpop or AR_MAX_POP):
            _AR_WHY[0] = "pop"
            return None
        i, j = c % w, c // w
        for dx, dy, cost in by_layer[ly]:
            ni, nj = i + dx, j + dy
            if not (i0 <= ni <= i1 and j0 <= nj <= j1):
                continue
            nc = nj * w + ni
            e = extra(nc, ly)
            if e is None:
                continue
            nd = d + cost + e
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
                e = extra(nc, ly)
                if e is None or not (pass_(j * w + ni, ly) and pass_(nj * w + i, ly)):
                    continue
                nd = d + cost + e
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
    _AR_WHY[0] = "blocked, %d cell(s) reached" % len(dist)
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


def _ar_emit(g, net, path, geo, placed):
    """Turn a cell path into board geometry, stamp it into the map, and file it under `net`.

    The geometry is kept in millimetres rather than as s-expressions because the rip-up pass
    has to be able to throw a net's routing away and lay the rest down again on a fresh map.
    """
    hw = AR_W / 2.0

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

    world = []
    for r in runs:
        if r[0] == "via":
            vx, vy = g.xy(r[1])
            world.append(("via", vx, vy))
        elif r[0] == "lead":
            world.append(("seg",) + tuple(r[1:5]) + (r[5],))
        else:
            x0, y0 = g.xy(r[1])
            x1, y1 = g.xy(r[2])
            world.append(("seg", x0, y0, x1, y1, r[3]))
    geo.setdefault(net, []).extend(world)
    _ar_stamp(g, net, world, placed)
    return (len([r for r in world if r[0] == "seg"]),
            len([r for r in world if r[0] == "via"]))


def _ar_stamp(g, net, world, placed):
    """Write one net's routing into the map, and its vias into `placed`."""
    hw = AR_W / 2.0
    _cn, cl = _ar_class(net)
    grow = hw + hw + max(AR_CLEAR, cl)
    idx = g.net_cells(net)
    for r in world:
        if r[0] == "via":
            _t, vx, vy = r
            placed.append((vx, vy, AR_VIA, AR_VIA_DRILL, net))
            for l2 in (0, 1):
                g.capsule(g.core[l2], vx, vy, vx, vy, AR_VIA / 2.0, net, idx[l2])
                g.capsule(g.halo[l2], vx, vy, vx, vy, AR_VIA / 2.0 + grow - hw, net)
            g.capsule(g.vhalo, vx, vy, vx, vy, AR_VIA + max(AR_CLEAR, cl), net)
        else:
            _t, x0, y0, x1, y1, ly = r
            g.capsule(g.core[ly], x0, y0, x1, y1, hw, net, idx[ly])
            g.capsule(g.halo[ly], x0, y0, x1, y1, grow, net)
            g.capsule(g.vhalo, x0, y0, x1, y1, hw + AR_VIA / 2.0 + max(AR_CLEAR, cl), net)


# Set AR_PRUNE_DBG to a comma-separated net list to watch _ar_prune work on them.
_PRUNE_DBG = tuple(x for x in os.environ.get("AR_PRUNE_DBG", "").split(",") if x)


def _ar_prune(g, geo, fan):
    """Take off every track end that joins nothing -- what KiCad calls a dangling track.

    Two things leave stubs behind.  A fan-out lane is speculative by construction: it is laid
    before the net is routed, and if the net then fails, or the route arrives from a different
    side, the lane is a spur off a pad with a free far end.  And a net that failed part-way
    keeps the pieces it did manage, whose loose ends are the same thing.  354 lanes and 56
    failed nets between them put the dangling-track count over KiCad's 199 report cap.

    Three rules, and getting any of them wrong costs live copper:

    LAYER.  A pad holds an end only if the pad has copper on that layer -- every SMD pad here
    is F.Cu only, so a B.Cu end lying over one touches nothing.  Another run holds it only if
    that run is on the same layer.  A via holds it on either layer, because every via this
    router places spans both, and a via itself needs holding on BOTH layers, which is exactly
    what "connected on only one layer" means in KiCad's report.

    JUNCTION, not coverage.  A 0.1 mm step's far end sits 0.1414 mm from its own predecessor,
    inside that predecessor's 0.125 mm half-width -- so a plain "is this point covered by
    copper" test declares every chain end held by the segment behind it and prunes nothing.
    An end is held only where it MEETS something: another run's endpoint within half a grid
    step, or a T onto the interior of another run.

    TRIM, do not delete.  A fan-out lane is one long segment, and the route usually joins it
    part way along and leaves the rest hanging.  Deleting the lane takes the route's only
    path to the pad with it and unravels the whole net -- which is what happened to PWM_DEN_A.
    So a run held at one end only is walked in from the free end a grid step at a time and cut
    back to the last point that still meets something.  Only then, if nothing does, is it gone.

    Only free ends are ever removed, so nothing that was connected can stop being connected.
    """
    def dbg(net, msg):
        if NETNAME.get(net) in _PRUNE_DBG:
            print("    prune %s %s" % (NETNAME.get(net), msg))

    hw = AR_W / 2.0
    eps = 1e-6
    snap = AR_GRID / 2.0 + eps          # "the same point", at the grid the router works on
    cut = cutv = trim = 0
    for net in set(list(geo) + list(fan)):
        runs = [("geo", i) for i in range(len(geo.get(net, ())))]
        runs += [("fan", i) for i in range(len(fan.get(net, ())))]
        src = {"geo": geo, "fan": fan}
        live = set(runs)
        boxes = [b for b in g.pads.get(net, ())]

        def item(k):
            return src[k[0]][net][k[1]]

        def held(k, x, y, ly, rad, ox, oy):
            """Does the copper of radius `rad` at (x, y) meet its own net on layer `ly`?

            (ox, oy) is the OTHER end of the same run, and it is what makes this test honest.
            Copper overlaps when the shapes overlap -- that is the rule KiCad's connectivity
            uses, and it is why a route that stops one cell beside a fan-out lane is joined to
            it.  But a run's own chain neighbour, the one sitting on (ox, oy), has a 0.125 mm
            end cap that reaches straight past a 0.1 mm step and covers this end too.  That is
            not a connection, it is the same wire; count it and nothing ever prunes.  So the
            neighbour at the far end may hold this end only by a real T onto its interior.
            """
            for x0, y0, x1, y1, _px, _py, lys in boxes:
                if ly not in lys:
                    continue
                cx = min(max(x, x0), x1)
                cy = min(max(y, y0), y1)
                if math.hypot(x - cx, y - cy) <= eps:
                    return True
            for o in live:
                if o == k:
                    continue
                r = item(o)
                if r[0] == "via":
                    if math.hypot(r[1] - ox, r[2] - oy) <= snap:
                        continue               # the via this run climbs at its other end
                    if math.hypot(x - r[1], y - r[2]) <= max(AR_VIA / 2.0, rad) + eps:
                        return True
                    continue
                if r[5] != ly:
                    continue
                ax, ay, bx, by = r[1], r[2], r[3], r[4]
                if math.hypot(x - ax, y - ay) <= snap or math.hypot(x - bx, y - by) <= snap:
                    return True                # end to end: a junction, whatever else is true
                dx, dy = bx - ax, by - ay
                dd = dx * dx + dy * dy
                if dd <= 1e-12:
                    continue
                s = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / dd))
                if math.hypot(x - (ax + s * dx), y - (ay + s * dy)) > hw + rad + eps:
                    continue
                if (math.hypot(ax - ox, ay - oy) <= snap or math.hypot(bx - ox, by - oy) <= snap):
                    ln = math.sqrt(dd)         # chain neighbour: only a real T counts
                    if s * ln <= snap or (1.0 - s) * ln <= snap:
                        continue
                return True
            return False

        # Tracks and vias have to come off together, not one pass then the other.  Cutting a
        # track can orphan the via it climbed, and cutting that via can orphan the track on
        # the far layer that was hanging off it, so the two rules chase each other until
        # neither fires.  Every step shortens the copper, so this terminates.  A via on a net
        # that owns a pour is exempt: the plane connects it, and none of this geometry sees it.
        planed = NETNAME.get(net) in PLANED_NETS
        again = True
        while again:
            again = False
            for k in sorted(live):
                if k not in live:               # already gone earlier in this same pass
                    continue
                r = item(k)
                if r[0] == "via":
                    if planed or (held(k, r[1], r[2], 0, AR_VIA / 2.0, r[1], r[2])
                                  and held(k, r[1], r[2], 1, AR_VIA / 2.0, r[1], r[2])):
                        continue
                    dbg(net, "cuts %s %s" % (k, r))
                    live.discard(k)
                    cut += 1
                    cutv += 1
                    again = True
                    continue
                ly = r[5]
                one = held(k, r[1], r[2], ly, hw, r[3], r[4])
                two = held(k, r[3], r[4], ly, hw, r[1], r[2])
                if one and two:
                    continue
                if one or two:
                    ax, ay = (r[1], r[2]) if one else (r[3], r[4])
                    bx, by = (r[3], r[4]) if one else (r[1], r[2])
                    ln = math.hypot(bx - ax, by - ay)
                    n = max(1, int(round(ln / AR_GRID)))
                    for i in range(n - 1, 0, -1):
                        f = float(i) / n
                        px, py = ax + (bx - ax) * f, ay + (by - ay) * f
                        if held(k, px, py, ly, hw, ax, ay):
                            src[k[0]][net][k[1]] = ("seg", ax, ay, px, py, ly)
                            trim += 1
                            dbg(net, "trims %s to (%.2f, %.2f)" % (k, px, py))
                            again = True
                            break
                    else:
                        dbg(net, "cuts %s %s" % (k, r))
                        live.discard(k)
                        cut += 1
                        again = True
                    continue
                dbg(net, "cuts %s %s" % (k, r))
                live.discard(k)
                cut += 1
                again = True

        for tag, d in (("geo", geo), ("fan", fan)):
            if net in d:
                keep = [r for i, r in enumerate(d[net]) if (tag, i) in live]
                if keep:
                    d[net] = keep
                else:
                    del d[net]
    print("autorouter: %d dangling run(s) cut (%d track, %d via), %d trimmed back"
          % (cut, cut - cutv, cutv, trim))


def _ar_sexpr(geo, tag="ar"):
    """The board text for everything the router laid down."""
    out = []
    for net in sorted(geo):
        for n, r in enumerate(geo[net]):
            if r[0] == "via":
                out.append(via(r[1], r[2], net, AR_VIA, AR_VIA_DRILL,
                               "%s%d.%d" % (tag, net, n)))
            else:
                out.append(seg(r[1], r[2], r[3], r[4], AR_W, AR_LAYERS[r[5]], net,
                               "%s%d.%d" % (tag, net, n)))
    return out


def _ar_fanout(g, comps, pos, padnet, wanted, fan, placed):
    """Give every pin of a dense package a short lane straight out of the package.

    Pads inside a package cannot be reached sideways: two neighbouring pads' clearance halos
    meet in the gap between them, so the only way to a pin is from outside, along the one line
    that leaves the package.  The first track that runs past the pad row takes that line away
    from every pin behind it.  Laying the lanes first reserves them; they are stamped like any
    other copper and are never ripped up, so the general router meets them as obstacles and
    starts each net from the far end of its own lane, out in the open.
    """
    byref = {}
    for ref, _pn, net, px, py, pw, ph, smd, _pid in pads_board(comps, pos, padnet):
        byref.setdefault(ref, []).append((net, px, py, pw, ph, smd))
    hw = AR_W / 2.0
    n = 0
    # Densest first: a 38-pin module has less choice about where its lanes go than an 8-pin
    # part, and whatever it does not take is still there for the others.
    for ref in sorted(byref, key=lambda r: -len(byref[r])):
        ps = byref[ref]
        if len(ps) < AR_FAN_PADS:
            continue
        bx0 = min(p[1] - p[3] / 2.0 for p in ps)
        bx1 = max(p[1] + p[3] / 2.0 for p in ps)
        by0 = min(p[2] - p[4] / 2.0 for p in ps)
        by1 = max(p[2] + p[4] / 2.0 for p in ps)
        for net, px, py, pw, ph, smd in ps:
            if net not in wanted:
                continue
            # Out of the package the short way: whichever edge this pad is nearest.
            d = ((px - bx0, (-1, 0)), (bx1 - px, (1, 0)), (py - by0, (0, -1)), (by1 - py, (0, 1)))
            _dist, (ux, uy) = min(d)
            # How far out the lane has to run: clear of the package, but no further than a pad
            # pitch or two -- a long lane is just a track laid blind.
            if ux:
                want = ((bx1 + AR_FAN_GAP) - px) if ux > 0 else (px - (bx0 - AR_FAN_GAP))
                edge = pw / 2.0
            else:
                want = ((by1 + AR_FAN_GAP) - py) if uy > 0 else (py - (by0 - AR_FAN_GAP))
                edge = ph / 2.0
            want = min(max(want, edge + AR_FAN_MIN), AR_FAN_MAX)
            ly = 0
            steps = int(want / AR_GRID)
            ok = 0
            for k in range(1, steps + 1):
                x, y = px + ux * k * AR_GRID, py + uy * k * AR_GRID
                i, j = g.ij(x, y)
                if not (0 <= i < g.w and 0 <= j < g.h):
                    break
                c = j * g.w + i
                v = g.halo[ly][c]
                if not (v == 0 or v == net or g.core[ly][c] == net):
                    break
                ok = k
            if ok * AR_GRID < edge + AR_FAN_MIN:
                continue
            ex, ey = px + ux * ok * AR_GRID, py + uy * ok * AR_GRID
            run = [("seg", px, py, ex, ey, ly)]
            fan.setdefault(net, []).extend(run)
            _ar_stamp(g, net, run, placed)
            n += 1
    print("autorouter: %d fan-out lane(s)" % n)


def _ar_rebuild(base, geo):
    """A fresh map with everything in `geo` laid back down.  What is not in `geo` is gone.

    Un-stamping one net in place is not possible: a halo cell holding -1 records that two nets
    met there and cannot say which, so the only honest way to take a net off the board is to
    build the map again without it.  That costs a few seconds, which is why rip-ups are
    counted and capped.
    """
    comps, pos, padnet, netidx, placed0, keepouts, fan, hist = base
    placed = list(placed0)
    g = _ar_build(comps, pos, padnet, netidx, placed, keepouts)
    g.hist = hist
    for net in sorted(fan):
        _ar_stamp(g, net, fan[net], placed)
    for net in sorted(geo):
        _ar_stamp(g, net, geo[net], placed)
    return g, placed


def _ar_route_net(g, net, geo, placed, tally, margins, maxpop, t0, hist=True):
    """Join `net`'s pieces one at a time until it is whole.  Returns why it stopped, or "".

    Each round takes the largest piece as the source and the nearest other piece as the
    destination, so the net grows outward from its own centre of gravity rather than chaining
    end to end.  The search box starts tight and is widened only if that fails: a tight box is
    both faster and straighter, and a net that needs the wide one is usually going round
    something.
    """
    comps_ = _ar_components(g, net)
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
        for margin, budget in margins:
            allx = [p[0] for p in sx] + [p[0] for p in dxy]
            ally = [p[1] for p in sx] + [p[1] for p in dxy]
            box = (max(0, g.ij(min(allx) - margin, 0)[0]),
                   max(0, g.ij(0, min(ally) - margin)[1]),
                   min(g.w - 1, g.ij(max(allx) + margin, 0)[0]),
                   min(g.h - 1, g.ij(0, max(ally) + margin)[1]))
            path = _ar_search(g, net, src, set(dst), pts, box, maxpop * budget, hist=hist)
            if path:
                break
        if not path:
            _AR_STUCK[:] = [src, set(dst), pts, box]
            return "%d piece(s) left, %s" % (len(comps_), _AR_WHY[0])
        s, v = _ar_emit(g, net, path, geo, placed)
        tally[0] += 1
        tally[1] += s
        tally[2] += v
        comps_ = _ar_components(g, net)
    return ""


def _ar_key(comps, pos, padnet, placed, keepouts):
    """A fingerprint of everything the search actually depends on.

    Which pads exist, where each one sits, what net it is on, what is already laid down and
    where the keep-outs are -- plus the router's own constants.  Nothing else reaches the
    search, so if this matches, last run's answer is still this run's answer.
    """
    h = _hashlib.sha1()
    for t in sorted(repr(x) for x in pads_board(comps, pos, padnet)):
        h.update(t.encode())
    for t in sorted(repr(x) for x in placed):
        h.update(t.encode())
    for t in sorted(repr(x) for x in keepouts):
        h.update(t.encode())
    h.update(repr([(n, v) for n, v in sorted(globals().items())
                   if n.startswith("AR_") and n != "AR_DUMP"]).encode())
    return h.hexdigest()


def _ar_cache(path, key, result=None):
    """Read the cached routing for `key`, or write `result` under it.  None on a miss.

    Routing is half an hour of search, and the board gets regenerated for things that have
    nothing to do with routing: a silkscreen policy, a description field, a keep-out that was
    in the wrong coordinate frame.  This lets those regenerate in seconds, and because the key
    covers every input the search reads, a move of so much as one pad misses it.
    """
    import pickle
    if result is None:
        try:
            with open(path, "rb") as fh:
                k, geo, fan, failed = pickle.load(fh)
        except (IOError, OSError, EOFError, ValueError, pickle.UnpicklingError):
            return None
        return (geo, fan, failed) if k == key else None
    with open(path, "wb") as fh:
        pickle.dump((key,) + result, fh, 2)
    return result


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
    out, nseg, nvia, missing = [], 0, 0, []
    for name in sorted(nets):
        net = netidx.get(name)
        if net is None:
            missing.append(name)
            continue
        d = nets[name]
        for i, r in enumerate(d.get("segments", ())):
            out.append(seg(r[0], r[1], r[2], r[3], r[4], r[5], net, "fz%d.s%d" % (net, i)))
            nseg += 1
        for i, v in enumerate(d.get("vias", ())):
            out.append(via(v[0], v[1], net, v[2], v[3], "fz%d.v%d" % (net, i)))
            nvia += 1
    print("frozen routes: %d segment(s), %d via(s) over %d net(s) from %s"
          % (nseg, nvia, len(nets) - len(missing), os.path.basename(FROZEN)))
    if missing:
        # A net in the frozen file that the board no longer has means the schematic moved
        # under the freeze.  Carrying on would drop that net's copper without saying so.
        print("FAIL: %d frozen net(s) are not on this board: %s"
              % (len(missing), ", ".join(missing[:8])))
        print("      Re-run scripts/route_external.py and scripts/freeze_routes.py,")
        print("      or delete %s to fall back to the built-in router." % FROZEN)
        raise SystemExit(1)
    return out


def autoroute(comps, pos, padnet, netidx, placed, keepouts):
    """Route every signal net that is not already whole.  Returns the segments and vias."""
    gnd = netidx.get("GND")
    t0 = _time.time()
    fan, hist = {}, None
    base = [comps, pos, padnet, netidx, list(placed), keepouts, fan, None]
    g = _ar_build(comps, pos, padnet, netidx, placed, keepouts)
    base[7] = hist = g.hist
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
        # Most pieces first, then shortest span.  A rail with a dozen stops has the least
        # freedom about where it goes and has to be laid while the field is still open; the
        # two-pad nets can thread whatever is left.
        todo.append((-len(comps_), max(xs) - min(xs) + max(ys) - min(ys), net))
    todo.sort()
    print("autorouter: %d net(s) to route, %.1f s to here"
          % (len(todo), _time.time() - t0))

    _ar_fanout(g, comps, pos, padnet, set(net for _p, _s, net in todo), fan, placed)
    # The lanes are copper too, so what was several pieces may now be fewer.
    todo = [(-len(_ar_components(g, net)), sp, net) for _p, sp, net in todo]
    todo = [t for t in todo if t[0] < -1]
    todo.sort()
    print("autorouter: %d net(s) still in pieces, %.1f s to here"
          % (len(todo), _time.time() - t0))

    geo = {}
    tally = [0, 0, 0]                       # connections, segments, vias
    failed = {}
    cpath = os.environ.get("AR_CACHE")
    key = _ar_key(comps, pos, padnet, placed, keepouts) if cpath else None
    hit = _ar_cache(cpath, key) if cpath else None
    if hit:
        geo, cfan, failed = hit
        fan.clear()
        fan.update(cfan)
        g, placed = _ar_rebuild(base, geo)
        queue = _collections.deque()
        print("autorouter: %d routed net(s) reused from %s" % (len(geo), cpath))
    else:
        queue = _collections.deque(net for _p, _s, net in todo)
    rips = _collections.Counter()           # how often each net has been torn up
    tries = _collections.Counter()          # how often each net has asked for a rip-up
    winner = set()                          # nets that have just had a channel cleared
    nrip = 0
    while queue:
        net = queue.popleft()
        why = _ar_route_net(g, net, geo, placed, tally, AR_MARGIN, AR_MAX_POP, t0,
                            hist=(net not in winner))
        winner.discard(net)
        if not why:
            failed.pop(net, None)
            continue
        failed[net] = why
        if nrip >= AR_MAX_RIPS or tries[net] >= AR_RIP_TRIES or not _AR_STUCK:
            continue
        # Ask the same question again, this time allowed through other nets at a price.  The
        # path that comes back is the one the board would permit if those nets moved, so the
        # nets it crosses are exactly the ones worth tearing up.
        src, dst, pts, box = _AR_STUCK
        soft = _ar_search(g, net, src, dst, pts, box, AR_MAX_POP * AR_MARGIN[-1][1],
                          soft=AR_SOFT_COST)
        blockers = []
        if soft:
            for c, ly in soft:
                v = g.halo[ly][c]
                if (v > 0 and v != net and v in geo and v not in blockers
                        and rips[v] < AR_RIP_LIMIT):
                    blockers.append(v)
        if not blockers:
            continue
        tries[net] += 1
        nrip += 1
        # Make the corridor dearer for everyone who is about to be sent round it.
        for c, ly in soft:
            v = g.halo[ly][c]
            if v > 0 and v != net:
                hist[ly][c] += AR_HIST_BUMP
        winner.add(net)
        for b in blockers:
            rips[b] += 1
            del geo[b]
        geo.pop(net, None)                  # this net starts again too, from bare pads
        print("    rip %d: %s takes out %s" % (nrip, NETNAME.get(net, "?"),
                                               ", ".join(NETNAME.get(b, "?") for b in blockers)))
        g, placed = _ar_rebuild(base, geo)
        queue.appendleft(net)
        for b in blockers:
            queue.append(b)

    if cpath and not hit:
        _ar_cache(cpath, key, (geo, fan, failed))
        print("autorouter: result cached in %s" % cpath)

    _ar_prune(g, geo, fan)
    done = len([n for n in geo if n not in failed])
    nseg = (sum(1 for n in geo for r in geo[n] if r[0] == "seg")
            + sum(len(v) for v in fan.values()))
    nvia = sum(1 for n in geo for r in geo[n] if r[0] == "via")
    out = _ar_sexpr(geo) + _ar_sexpr(fan, "fan")
    print("autorouter: %d net(s) routed, %d rip-up(s), %d segment(s), %d via(s)"
          % (done, nrip, nseg, nvia))
    if os.environ.get("AR_DUMP"):
        import pickle
        with open(os.environ["AR_DUMP"], "wb") as fh:
            pickle.dump((g.w, g.h, g.core, g.halo, g.vhalo, g.cells, g.pads,
                         dict(failed), NETNAME, AR_GRID, L.X0, L.Y0, fan, geo), fh, 2)
        print("autorouter: map dumped to %s" % os.environ["AR_DUMP"])
    if failed:
        print("  WARN: no path for %d net(s):" % len(failed))
        for net, why in sorted(failed.items(), key=lambda kv: NETNAME.get(kv[0], "")):
            print("      %-26s %s" % (NETNAME.get(net, "?"), why))
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

    pos, unplaced, grid = place(comps)
    if unplaced:
        print("  ERROR: %d part(s) would not fit: %s" % (len(unplaced), ", ".join(unplaced)))

    # Footprints stay STRUCTURED until every one of them exists, because silk_refs()
    # has to see the whole board's silkscreen and copper at once to know where a
    # designator can go without landing on either.
    built = []
    for c in sorted(comps, key=lambda c: natkey(c["ref"])):
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        fp = build_footprint(c, x, y, rot, padnet)
        if fp:
            built.append((c["ref"], x, y, rot, fp))
    silk_refs(built, comps, pos, padnet)
    body = ["\t" + dump(fp, 2) for _r, _x, _y, _rt, fp in built]

    # Mounting holes: plain, NON-plated.  Tying signal GND to a metal enclosure at four points
    # is a grounding decision, not a layout default -- it stays out until someone decides it.
    mh = []
    for i, (mx, my) in enumerate(mount_holes()):
        c = dict(ref="H%d" % (i + 1), value="MountingHole", sheetname="", sheetfile="",
                 path="/" + str(_uuid.uuid5(NS, "mh%d" % i)),
                 fp=MOUNT_FP)
        fp = build_footprint(c, mx, my, 0, {})
        if fp:
            # `board_only` is what exempts a footprint from the schematic-parity check,
            # which is the honest description of a plain hole: it is not a part, it has no
            # symbol, and it belongs in neither the BOM nor the pick-and-place file.
            # Without it the four holes came back as four "Extra footprint" warnings.
            fp.insert(2 if isinstance(fp[1], str) else 1,
                      ["attr", "board_only", "exclude_from_bom",
                       "exclude_from_pos_files"])
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
               '\t\t(comment 2 "Board 140 x 100 mm, 6 layer, 1 oz copper on all layers")\n'
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
    # AR_SKIP leaves the signal nets unrouted on purpose.  The hand routes, the thermal and
    # stitching vias and the ground drops above are all still here, so what comes out is a
    # board an external router can be pointed at: everything this repo decided by hand is
    # already copper, and the only thing missing is the part being handed over.
    if os.environ.get("AR_SKIP"):
        print("autorouter: skipped (AR_SKIP) -- signal nets left unrouted")
    elif os.path.exists(FROZEN) and not os.environ.get("AR_ROUTE"):
        out += frozen_routes(netidx)
    else:
        out += autoroute(comps, pos, padnet, netidx, placed, kos)
    out += zones(netidx)
    out.append('\t(embedded_fonts no)')
    out.append(")")

    io.open(BOARD, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("wrote %s (%.1f kB)" % (BOARD, os.path.getsize(BOARD) / 1024.0))


if __name__ == "__main__":
    main()
