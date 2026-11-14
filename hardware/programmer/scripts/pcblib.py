# -*- coding: utf-8 -*-
"""Board-text helpers for the programmer board (plan Task 3).

parse()/dump() and the footprint instancing follow hardware/scripts/gen_pcb.py, copied rather
than imported: that module imports layout_pcb and keeps the MCCAN board's net table and
uuid namespace in module globals, so it cannot instance a second board.
"""
import copy
import io
import math
import os
import re
import uuid

STOCK = "C:/Program Files/KiCad/10.0/share/kicad/footprints"
NS = uuid.UUID("3d0d5f0e-7c1b-4f7a-9e55-6b1c2a9e0b11")


def U(key):
    return str(uuid.uuid5(NS, key))


def q(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def unq(s):
    return s[1:-1] if len(s) >= 2 and s[0] == '"' else s


def num(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def parse(s):
    """Parse one s-expression into nested lists; atoms keep their raw text, quotes included."""
    i = [0]
    n = len(s)

    def skip():
        while i[0] < n and s[i[0]] in " \t\r\n":
            i[0] += 1

    def node():
        i[0] += 1
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
    if isinstance(node, str):
        return node
    if all(isinstance(c, str) for c in node):
        return "(" + " ".join(node) + ")"
    pad = "\t" * indent
    head, tail, seen = [], [], False
    for c in node:
        if isinstance(c, str) and not seen:
            head.append(c)
        else:
            seen = True
            tail.append(c)
    out = "(" + " ".join(head)
    for c in tail:
        out += "\n" + pad + dump(c, indent + 1)
    return out + "\n" + "\t" * (indent - 1) + ")"


def find(node, head):
    for c in node:
        if isinstance(c, list) and c and c[0] == head:
            return c
    return None


def find_all(node, head):
    return [c for c in node if isinstance(c, list) and c and c[0] == head]


_FP = {}


def load_fp(spec):
    if spec not in _FP:
        lib, name = spec.split(":")
        p = os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod")
        _FP[spec] = parse(io.open(p, encoding="utf-8").read())
    return _FP[spec]


def rot_local(x, y, deg):
    """Footprint-local (x, y) -> board offset for a footprint rotated by `deg` (KiCad CCW)."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return (x * c + y * s, -x * s + y * c)


def pads_of(spec):
    """[(number, x, y, w, h, kind)] in footprint-local coordinates, size already rotated by
    the pad's own angle."""
    out = []
    for p in find_all(load_fp(spec), "pad"):
        at, sz = find(p, "at"), find(p, "size")
        a = float(at[3]) if len(at) > 3 else 0.0
        w, h = float(sz[1]), float(sz[2])
        if a % 180:
            w, h = h, w
        out.append((unq(p[1]), float(at[1]), float(at[2]), w, h, p[2]))
    return out


def pad_xy(spec, x, y, rot, number):
    """Board coordinates of every pad `number` of a footprint placed at (x, y, rot)."""
    out = []
    for n, px, py, _w, _h, _k in pads_of(spec):
        if n == number:
            dx, dy = rot_local(px, py, rot)
            out.append((round(x + dx, 4), round(y + dy, 4)))
    return out


SKIP = ("version", "generator", "generator_version", "layer", "at", "uuid", "tstamp",
        "embedded_fonts")


def _addrot(at, rot):
    a = (float(at[3]) if len(at) > 3 else 0.0) + rot
    a %= 360.0
    if a == 0.0:
        del at[3:]
    else:
        at[3:] = [num(a)]


def _reuuid(node, ref, ctr):
    if not isinstance(node, list):
        return
    if node and node[0] == "uuid" and len(node) > 1:
        ctr[0] += 1
        node[1] = q(U("%s#%d" % (ref, ctr[0])))
    for c in node:
        _reuuid(c, ref, ctr)


def footprint(spec, ref, value, x, y, rot, padnet, path, sheetfile, fields=()):
    """A placed footprint node.  padnet: {pad number: (code, name)}.  The reference moves to
    F.Fab (the board's silk carries net and function labels instead, spec 6.7)."""
    body = copy.deepcopy(load_fp(spec))
    keep, props = [], []
    for ch in body[2:]:
        if isinstance(ch, str) or ch[0] in SKIP:
            continue
        (props if ch[0] == "property" else keep).append(ch)
    for p in props:
        nm = unq(p[1])
        if nm == "Reference":
            p[2] = q(ref)
            lay = find(p, "layer")
            if lay is not None and unq(lay[1]).endswith(".SilkS"):
                lay[1] = q("F.Fab")
        elif nm == "Value":
            p[2] = q(value)
        elif nm == "Footprint":
            p[2] = q(spec)
    for nm, val in fields:
        props.append(["property", q(nm), q(val), ["at", "0", "0", "0"], ["layer", q("F.Fab")],
                      ["hide", "yes"], ["effects", ["font", ["size", "1", "1"],
                                                    ["thickness", "0.15"]]]])
    for ch in props + keep:
        if ch[0] in ("property", "fp_text", "pad"):
            at = find(ch, "at")
            if at:
                _addrot(at, rot)
    for p in keep:
        if p[0] != "pad":
            continue
        code = padnet.get(unq(p[1]))
        if code is None:
            continue
        lay = find(p, "layers")
        p.insert(p.index(lay) + 1, ["net", str(code[0]), q(code[1])])
    out = ["footprint", q(spec), ["layer", q("F.Cu")], ["uuid", q(U("fp" + ref))],
           ["at", num(x), num(y)] + ([num(rot)] if rot else [])]
    for h in ("descr", "tags"):
        for k in [k for k in keep if k[0] == h]:
            out.append(k)
            keep.remove(k)
    out += props
    out += [["path", q(path)], ["sheetname", q("/")], ["sheetfile", q(sheetfile)]]
    out += keep
    ctr = [0]
    for ch in out:
        if isinstance(ch, list) and ch[0] != "uuid":
            _reuuid(ch, ref, ctr)
    return out


# ------------------------------------------------------------------ board items
def segment(a, b, w, layer, code, key):
    return ('\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n\t\t(layer "%s")\n'
            '\t\t(net %d)\n\t\t(uuid "%s")\n\t)' % (num(a[0]), num(a[1]), num(b[0]), num(b[1]),
                                                   num(w), layer, code, U(key)))


def via(p, size, drill, code, key):
    return ('\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n\t\t(layers "F.Cu" "B.Cu")\n'
            '\t\t(net %d)\n\t\t(uuid "%s")\n\t)' % (num(p[0]), num(p[1]), num(size), num(drill),
                                                   code, U(key)))


def zone(code, name, layer, pts, priority, key, clearance=0.25, thermal=0.3, spoke=0.4,
         solid=False):
    xy = " ".join("(xy %s %s)" % (num(x), num(y)) for x, y in pts)
    return ('\t(zone\n\t\t(net %d)\n\t\t(net_name "%s")\n\t\t(layer "%s")\n\t\t(uuid "%s")\n'
            '\t\t(hatch edge 0.5)\n\t\t(priority %d)\n\t\t(connect_pads%s\n\t\t\t(clearance %s)\n'
            '\t\t)\n\t\t(min_thickness 0.2)\n\t\t(filled_areas_thickness no)\n'
            '\t\t(fill yes\n\t\t\t(thermal_gap %s)\n\t\t\t(thermal_bridge_width %s)\n\t\t)\n'
            '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n\t)'
            % (code, name, layer, U(key), priority, " yes" if solid else "", num(clearance),
               num(thermal), num(spoke), xy))


def gr_line(a, b, layer, w, key):
    return ('\t(gr_line (start %s %s) (end %s %s) (stroke (width %s) (type default)) '
            '(layer "%s") (uuid "%s"))' % (num(a[0]), num(a[1]), num(b[0]), num(b[1]), num(w),
                                           layer, U(key)))


def gr_arc(s, m, e, layer, w, key):
    return ('\t(gr_arc (start %s %s) (mid %s %s) (end %s %s) (stroke (width %s) (type default)) '
            '(layer "%s") (uuid "%s"))' % (num(s[0]), num(s[1]), num(m[0]), num(m[1]),
                                           num(e[0]), num(e[1]), num(w), layer, U(key)))


def gr_poly(pts, layer, key, fill=True):
    xy = " ".join("(xy %s %s)" % (num(x), num(y)) for x, y in pts)
    return ('\t(gr_poly (pts %s) (stroke (width 0.1) (type solid)) (fill %s) (layer "%s") '
            '(uuid "%s"))' % (xy, "yes" if fill else "no", layer, U(key)))


def gr_text(text, at, layer, size, key, rot=0, justify=None, thick=None):
    j = " (justify %s)" % justify if justify else ""
    return ('\t(gr_text %s (at %s %s%s) (layer "%s") (uuid "%s")\n\t\t(effects (font (size %s %s)'
            ' (thickness %s))%s)\n\t)' % (q(text), num(at[0]), num(at[1]),
                                          (" %s" % num(rot)) if rot else "", layer, U(key),
                                          num(size), num(size), num(thick or size * 0.15), j))


def rounded_rect(x0, y0, x1, y1, r, layer, w, key):
    """Edge.Cuts outline with corner radius r, as four lines and four arcs."""
    c = r * (1 - math.sqrt(0.5))
    items = [gr_line((x0 + r, y0), (x1 - r, y0), layer, w, key + "t"),
             gr_line((x1, y0 + r), (x1, y1 - r), layer, w, key + "r"),
             gr_line((x1 - r, y1), (x0 + r, y1), layer, w, key + "b"),
             gr_line((x0, y1 - r), (x0, y0 + r), layer, w, key + "l"),
             gr_arc((x1 - r, y0), (x1 - c, y0 + c), (x1, y0 + r), layer, w, key + "a1"),
             gr_arc((x1, y1 - r), (x1 - c, y1 - c), (x1 - r, y1), layer, w, key + "a2"),
             gr_arc((x0 + r, y1), (x0 + c, y1 - c), (x0, y1 - r), layer, w, key + "a3"),
             gr_arc((x0, y0 + r), (x0 + c, y0 + c), (x0 + r, y0), layer, w, key + "a4")]
    return items


def netlist_tstamps(text):
    """{ref: first tstamp} from a kicadsexpr netlist (the footprint path is '/<tstamp>')."""
    out = {}
    for m in re.finditer(r'\(ref "([^"]+)"\)', text):
        blk = text[m.end():m.end() + 6000]
        t = re.search(r'\(tstamps "([0-9a-f-]+)"', blk)
        if t and m.group(1) not in out and "(comp" in text[max(0, m.start() - 40):m.start()]:
            out[m.group(1)] = t.group(1)
    return out
