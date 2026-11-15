# -*- coding: utf-8 -*-
"""Single-sheet schematic writer for the programmer board (plan Task 2).

The block-extraction and `extends` resolution follow hardware/scripts/gen_mcu_can.py, copied
rather than imported because importing that module regenerates the MCCAN mcu_can sheet.

Style: every symbol sits at rotation 0 and every connected pin gets a 2.54 mm wire stub with
a net label at its free end, so the schematic is drawn from the pin table alone and no pin
coordinate is typed by hand: positions are read from the library symbol.  Unused pins get a
no-connect flag.  Symbols are spaced far enough apart that no two stubs can meet.
"""
import os
import re
import uuid

STOCK = "C:/Program Files/KiCad/10.0/share/kicad/symbols"
GRID = 1.27
STUB = 2.54
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def U(key):
    return str(uuid.uuid5(NS, "prog:" + key))


def fs(x):
    s = ("%.4f" % x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def ongrid(*vals):
    for v in vals:
        assert abs(v / GRID - round(v / GRID)) < 1e-6, "%s is off the 1.27 mm grid" % v
    return vals


def extract_block(text, header):
    i = text.index(header)
    i = text.index("(", i)
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while text[j] != '"' or text[j - 1] == "\\":
                j += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1


def reindent(blk, first, extra):
    lines = blk.split("\n")
    return "\n".join([("\t" * first) + lines[0]] +
                     [("\t" * extra) + ln if ln else ln for ln in lines[1:]])


def from_library(libid):
    """The symbol as KiCad caches it into a sheet: `extends` resolved, renamed to libid."""
    lib, name = libid.split(":")
    src = open(os.path.join(STOCK, lib + ".kicad_sym"), encoding="utf-8").read()
    blk = extract_block(src, '\t(symbol "%s"\n' % name)
    short = name
    ext = re.search(r'\(extends "([^"]+)"\)', blk)
    if ext:
        parent = extract_block(src, '\t(symbol "%s"\n' % ext.group(1))
        # the child's own property blocks (value, position, visibility) replace the parent's
        for m in re.finditer(r'\(property "([^"]+)" ', blk):
            child_prop = extract_block(blk[m.start():], "(property")
            hdr = '(property "%s" ' % m.group(1)
            if hdr in parent:
                parent = parent.replace(extract_block(parent[parent.index(hdr):], "(property"),
                                        child_prop, 1)
        blk = re.sub(r'\(symbol "[^"]+"\n', '(symbol "%s"\n' % libid, parent, count=1)
        blk = re.sub(r'\(symbol "%s_(\d+_\d+)"' % re.escape(ext.group(1)),
                     lambda mm: '(symbol "%s_%s"' % (short, mm.group(1)), blk)
    else:
        blk = blk.replace('(symbol "%s"\n' % name, '(symbol "%s"\n' % libid, 1)
    return reindent(blk, 2, 1)


PIN_RE = re.compile(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\).*?\(name "([^"]*)"'
                    r'.*?\(number "([^"]*)"', re.S)


def pins_by_unit(cached):
    """{unit: {number: (px, py, angle, name)}} from a from_library() block.
    Unit 0 pins (common to all units) are folded into every unit."""
    short = re.search(r'\(symbol "[^":]+:([^"]+)"', cached).group(1)
    units = {}
    for m in re.finditer(r'\(symbol "%s_(\d+)_(\d+)"' % re.escape(short), cached):
        sub = extract_block(cached[m.start() - 1:], "(symbol")
        u = int(m.group(1))
        for p in PIN_RE.finditer(sub):
            units.setdefault(u, {})[p.group(5)] = (float(p.group(1)), float(p.group(2)),
                                                   int(p.group(3)), p.group(4))
    common = units.pop(0, {})
    if not units:
        units[1] = {}
    for u in units:
        units[u].update(common)
    return units


# direction of the stub, away from the body, in sheet coordinates (y down), per pin angle
AWAY = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}
LABEL_ROT = {0: 180, 180: 0, 90: 270, 270: 90}


class Sheet:
    def __init__(self, project, title, rev, date, paper="A4"):
        self.project, self.title, self.rev, self.date, self.paper = project, title, rev, date, paper
        self.uuid = U("root")
        self.libs, self.pins = {}, {}
        self.syms, self.wires, self.labels, self.noconn = [], [], [], []
        self.ends = {}      # stub end -> net, to catch two stubs meeting

    def lib(self, libid):
        if libid not in self.libs:
            self.libs[libid] = from_library(libid)
            self.pins[libid] = pins_by_unit(self.libs[libid])
        return self.pins[libid]

    def place(self, ref, libid, value, x, y, nets, unit=1, fields=()):
        """Place one unit of a symbol at (x, y), rotation 0.  nets: {pin number: net or None};
        every pin of the unit must be listed (None = no-connect).  fields: extra
        (name, value) properties, hidden."""
        ongrid(x, y)
        upins = self.lib(libid)[unit]
        missing = set(upins) - set(nets)
        extra = set(nets) - set(upins)
        assert not missing and not extra, (ref, unit, sorted(missing), sorted(extra))
        at = {}
        for num, (px, py, ang, _name) in upins.items():
            pt = (round(x + px, 4), round(y - py, 4))
            ongrid(*pt)
            net = nets[num]
            if pt in at:
                assert at[pt] == net, "%s: stacked pins on %s disagree (%s, %s)" % (
                    ref, pt, at[pt], net)
                continue
            at[pt] = net
            if net is None:
                self.noconn.append(pt)
                continue
            dx, dy = AWAY[ang]
            end = (round(pt[0] + dx * STUB, 4), round(pt[1] + dy * STUB, 4))
            assert end not in self.ends, "%s: stub end %s already used by %s" % (
                ref, end, self.ends[end])
            self.ends[end] = net
            self.wires.append((pt, end))
            self.labels.append((net, end[0], end[1], LABEL_ROT[ang]))
        self.syms.append(dict(ref=ref, libid=libid, val=value, x=x, y=y, unit=unit,
                              pins=sorted(upins), fields=list(fields)))

    # ------------------------------------------------------------------ output
    def text(self):
        out = []
        A = out.append
        A("(kicad_sch")
        A("\t(version 20260306)")
        A('\t(generator "eeschema")')
        A('\t(generator_version "10.0")')
        A('\t(uuid "%s")' % self.uuid)
        A('\t(paper "%s")' % self.paper)
        A("\t(title_block")
        A('\t\t(title "%s")' % self.title)
        A('\t\t(date "%s")' % self.date)
        A('\t\t(rev "%s")' % self.rev)
        A('\t\t(comment 1 "Generated by hardware/programmer/scripts/gen_sch.py - do not edit")')
        A("\t)")
        A("\t(lib_symbols")
        for libid in sorted(self.libs):
            A(self.libs[libid])
        A("\t)")
        for p in sorted(set(self.noconn)):
            A("\t(no_connect")
            A("\t\t(at %s %s)" % (fs(p[0]), fs(p[1])))
            A('\t\t(uuid "%s")' % U("nc%s,%s" % p))
            A("\t)")
        for a, b in self.wires:
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
        for name, x, y, rot in self.labels:
            A('\t(label "%s"' % name)
            A("\t\t(at %s %s %d)" % (fs(x), fs(y), rot))
            A("\t\t(effects")
            A("\t\t\t(font")
            A("\t\t\t\t(size 1.27 1.27)")
            A("\t\t\t)")
            A("\t\t\t(justify %s bottom)" % ("right" if rot in (180, 270) else "left"))
            A("\t\t)")
            A('\t\t(uuid "%s")' % U("l%s%s%s" % (name, x, y)))
            A("\t)")
        for s in self.syms:
            power = s["libid"].startswith("power:")
            A("\t(symbol")
            A('\t\t(lib_id "%s")' % s["libid"])
            A("\t\t(at %s %s 0)" % (fs(s["x"]), fs(s["y"])))
            A("\t\t(unit %d)" % s["unit"])
            A("\t\t(body_style 1)")
            A("\t\t(exclude_from_sim no)")
            A("\t\t(in_bom %s)" % ("no" if power else "yes"))
            A("\t\t(on_board %s)" % ("no" if power else "yes"))
            A("\t\t(in_pos_files %s)" % ("no" if power else "yes"))
            A("\t\t(dnp no)")
            A('\t\t(uuid "%s")' % U("s%s.%d" % (s["ref"], s["unit"])))
            props = [("Reference", s["ref"], s["x"] + 2.54, s["y"] - 5.08, power),
                     ("Value", s["val"], s["x"] + 2.54, s["y"] + 5.08, power)]
            props += [(n, v, s["x"], s["y"], True) for n, v in s["fields"]]
            for nm, val, px, py, hide in props:
                A('\t\t(property "%s" "%s"' % (nm, val.replace("\\", "\\\\").replace('"', '\\"')))
                A("\t\t\t(at %s %s 0)" % (fs(px), fs(py)))
                if hide:
                    A("\t\t\t(hide yes)")
                A("\t\t\t(show_name no)")
                A("\t\t\t(do_not_autoplace no)")
                A("\t\t\t(effects")
                A("\t\t\t\t(font")
                A("\t\t\t\t\t(size 1.27 1.27)")
                A("\t\t\t\t)")
                if nm in ("Reference", "Value"):
                    A("\t\t\t\t(justify left)")
                A("\t\t\t)")
                A("\t\t)")
            for n in s["pins"]:
                A('\t\t(pin "%s"' % n)
                A('\t\t\t(uuid "%s")' % U("p%s.%s" % (s["ref"], n)))
                A("\t\t)")
            A("\t\t(instances")
            A('\t\t\t(project "%s"' % self.project)
            A('\t\t\t\t(path "/%s"' % self.uuid)
            A('\t\t\t\t\t(reference "%s")' % s["ref"])
            A("\t\t\t\t\t(unit %d)" % s["unit"])
            A("\t\t\t\t)")
            A("\t\t\t)")
            A("\t\t)")
            A("\t)")
        A("\t(sheet_instances")
        A('\t\t(path "/"')
        A('\t\t\t(page "1")')
        A("\t\t)")
        A("\t)")
        A("\t(embedded_fonts no)")
        A(")")
        return "\n".join(out) + "\n"
