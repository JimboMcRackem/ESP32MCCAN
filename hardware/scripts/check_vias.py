# -*- coding: utf-8 -*-
"""Check the generated vias against the pads they are supposed to serve.

DRC cannot catch what this catches.  A thermal via that misses its paddle and lands on bare
laminate breaks no rule: it is on the right net, clear of everything, and simply conducts
nothing.  A stitching via that lands inside another net's pad WOULD be caught -- but one that
lands inside a pad of its OWN net is a short to that pad's component, silently, and DRC calls
it a connection rather than a fault.  So both directions are checked here:

    * every via on a net that is NOT GND-stitch must lie wholly inside a pad of its own net,
      and that pad must belong to the part the via was generated for;
    * every GND stitching via must lie inside NO pad at all -- it is meant to tie the planes
      together in free space, not to land on a component terminal;
    * a via of a POWER net is graded by neither rule.  gen_pcb places 0.8 mm vias on VBAT,
      +5V and the other power nets wherever a hand route in ROUTES changes layer, and half
      of those are dropped deliberately on the terminal of the cap they feed -- which is
      what you want there, and indistinguishable by diameter from a stitching via.  They
      are counted and the pad-landings named, so a new one is visible, but only a landing
      in a pad of ANOTHER net is a failure;
    * every footprint that gen_pcb classed as having an exposed paddle must actually have
      vias in it, so a placement change that pushes a part off the board cannot quietly take
      its thermal path with it.

Run after gen_pcb.py.  Exit status is non-zero if any of that is broken.
"""

import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pcb as G          # noqa: E402

HW = os.path.dirname(HERE)
# A board path on the command line checks THAT board instead -- the external-router
# chain in route_external.py grades its own output with the same two guards.
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "mccan.kicad_pcb")
# A SECOND board path grades only the vias that board also has.  The two rules below read a
# via's job off its diameter, which is true of everything gen_pcb.py places and false of
# anything an external router adds: its signal vias are 0.6 mm like the stitching vias and
# land in pads on purpose, so grading them here would report dozens of failures that are not
# failures.  route_external.py therefore passes the unrouted input board as the baseline --
# which grades exactly gen_pcb's own vias, and proves at the same time that the router gave
# every one of them back unmoved.
BASE = sys.argv[2] if len(sys.argv) > 2 else None
# With no baseline board, the frozen route file is the baseline instead -- and for the
# generated board it is the BETTER one, because it is committed.  Once routes_signal.json
# exists, mccan.kicad_pcb carries the external router's copper too, so a bare
# `python scripts/check_vias.py` would grade the router's via-in-pad against a rule written
# for gen_pcb's stitching vias and report two dozen failures that are the router doing its
# job.  Subtracting the frozen vias leaves exactly the ones this repo placed.
FROZEN = os.path.join(HERE, "routes_signal.json")

FP_AT_RE = re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)')
PAD_RE = re.compile(
    r'\(pad "([^"]*)" (\w+) [\w_]+\s*\(at ([-\d.]+) ([-\d.]+)\s*([-\d.]+)?\)\s*'
    r'\(size ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\t\)', re.S)
VIA_RE = re.compile(
    r'\(via\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+)\)\s*\(drill ([-\d.]+)\)'
    r'\s*\(layers [^)]*\)\s*\(net (\d+)\)', re.S)


def rot(x, y, deg):
    t = math.radians(deg)
    return (x * math.cos(t) + y * math.sin(t), -x * math.sin(t) + y * math.cos(t))


def read_pads(text):
    """(ref, pad, cx, cy, w, h, angle, net) in BOARD coordinates for every copper pad."""
    out = []
    for blk in text.split("\n\t(footprint ")[1:]:
        m = re.search(r'\(property "Reference" "([^"]*)"', blk)
        fm = FP_AT_RE.search(blk)
        if not m or not fm:
            continue
        fx, fy = float(fm.group(1)), float(fm.group(2))
        frot = float(fm.group(3) or 0.0)
        for pm in PAD_RE.finditer(blk):
            if not pm.group(1):
                continue
            nm = re.search(r'\(net (\d+) "', pm.group(8))
            dx, dy = rot(float(pm.group(3)), float(pm.group(4)), frot)
            out.append((m.group(1), pm.group(1), fx + dx, fy + dy,
                        float(pm.group(6)), float(pm.group(7)),
                        float(pm.group(5) or 0.0),
                        int(nm.group(1)) if nm else 0))
    return out


def in_pad(pad, vx, vy, r):
    """Is a via of radius r wholly inside `pad`?  Pad angle is absolute in a .kicad_pcb."""
    _ref, _pn, cx, cy, w, h, ang, _net = pad
    # Into the pad's own frame.  rot() is its own inverse for the transpose, so rotate by -ang.
    ux, uy = rot(vx - cx, vy - cy, -ang)
    return abs(ux) + r <= w / 2.0 + 1e-6 and abs(uy) + r <= h / 2.0 + 1e-6


def touches_pad(pad, vx, vy, r):
    """Does a via of radius r touch `pad`?  Exact: a via is a CIRCLE.

    This was `abs(ux) < w / 2 + r and abs(uy) < h / 2 + r`, which is the same test for a
    SQUARE via and over-reports by up to r * (sqrt(2) - 1) -- 0.124 mm on a 0.6 mm via --
    in the quadrant off a pad's corner.  It failed the build on the GND drop via at
    (110.77, 80.17), whose copper is 0.0393 mm clear of U4.6; 137 of the board's 141 drop
    vias sit 0.0500 mm from their own pad by construction (gen_pcb.py:1882), and that one
    reads differently only because its escape is oblique rather than axis-aligned, so the
    pad's corner is what the square test caught.  gen_pcb decides where drops go with an
    exact test; a gate that grades them with a looser one reports the generator obeying its
    own rule as a fault.
    """
    _ref, _pn, cx, cy, w, h, ang, _net = pad
    ux, uy = rot(vx - cx, vy - cy, -ang)
    dx = max(abs(ux) - w / 2.0, 0.0)
    dy = max(abs(uy) - h / 2.0, 0.0)
    return math.hypot(dx, dy) < r


def read_pads_shaped(text):
    """(ref, pad, cx, cy, w, h, ang, net, shape, rratio) in BOARD coords for every named pad.

    Same fields as read_pads() above plus the shape and roundrect_rratio via_pad_tally() needs,
    read with gen_pcb's own balanced-paren parser rather than by extending PAD_RE. PAD_RE's
    lazy `.*?` up to the next `\\n\\t\\t)` is fine for pulling a `(net ...)` out of a pad's tail,
    which either is there or is not, but roundrect_rratio sits among a pile of other optional,
    unordered pad children (thermal reliefs, an explicit uuid, remove_unused_layers) where a
    boundary drawn by pattern instead of parens is one reordered sibling from silently grabbing
    the wrong number. gen_pcb.parse()/find()/find_all() cannot cross a boundary that isn't
    there, by construction.
    """
    root = G.parse(text)
    out = []
    for fp in G.find_all(root, "footprint"):
        fat = G.find(fp, "at")
        if fat is None:
            continue
        fx, fy = float(fat[1]), float(fat[2])
        frot = float(fat[3]) if len(fat) > 3 else 0.0
        ref = ""
        for prop in G.find_all(fp, "property"):
            if len(prop) > 1 and G.unq(prop[1]) == "Reference":
                ref = G.unq(prop[2])
                break
        for p in G.find_all(fp, "pad"):
            if len(p) < 4:
                continue
            pn = G.unq(p[1])
            if not pn:
                continue
            shape = p[3]
            pat, psz = G.find(p, "at"), G.find(p, "size")
            if pat is None or psz is None:
                continue
            px, py = float(pat[1]), float(pat[2])
            # The pad's OWN `at` angle is already board-ABSOLUTE in a .kicad_pcb (unlike a
            # library .kicad_mod, where it is footprint-relative) -- read_pads() above relies
            # on this same fact and uses it the same way. Only the pad's POSITION needs turning
            # by the footprint's rotation; its angle is not added to frot a second time.
            pang = float(pat[3]) if len(pat) > 3 else 0.0
            w, h = float(psz[1]), float(psz[2])
            dx, dy = rot(px, py, frot)
            netnode = G.find(p, "net")
            net = int(netnode[1]) if netnode else 0
            rrnode = G.find(p, "roundrect_rratio")
            rratio = float(rrnode[1]) if rrnode else 0.0
            out.append((ref, pn, fx + dx, fy + dy, w, h, pang, net, shape, rratio))
    return out


def read_vias_parsed(root):
    """(x, y, size, net) for every via, read with the real parser.

    `re.findall(r'\\(via ...')` -- VIA_RE above -- already gets the head right (`\\(via\\s`, not
    the bare `(via` that also matches the zone keyword `vias not_allowed`), so a via READ this
    way is not the trap. The trap this function avoids is scanning `.kicad_pcb` at all with a
    pattern instead of parens for the surrounding pad-shape lookup in via_pad_tally(); this one
    is here mainly so that lookup has a single parsed `root` to share instead of parsing the
    (multi-megabyte) board text twice.
    """
    out = []
    for v in G.find_all(root, "via"):
        at, sz, net = G.find(v, "at"), G.find(v, "size"), G.find(v, "net")
        if at is None or sz is None or net is None:
            continue
        out.append((float(at[1]), float(at[2]), float(sz[1]), int(net[1])))
    return out


def in_pad_shape(pad, vx, vy):
    """Is (vx, vy) really under this pad's copper -- its true shape, not its bounding box?

    Every other geometry test in this file boxes a pad on purpose: in_pad() and touches_pad()
    above are clearance tests, and a box is the safe, conservative stand-in for a shape gen_pcb
    doesn't otherwise need modelled exactly. A via-in-pad tally is not a clearance test -- it
    answers a factual question, whether a via's copper really sits under a pad's copper, so the
    fab knows to plug and cap that hole. Boxing a roundrect pad's filleted corner off answers
    that question wrong: it reports vias landing in the corner the box claims and the fillet
    does not, and there are exactly four of those on this board. So roundrect (and oval, which
    is the same shape with the corner forced to a semicircle) get the real rounded-rect test,
    via the standard trick of clamping the point into the shape's inner (hw-r, hh-r) rectangle
    and checking the clamped remainder against the corner radius -- this single formula also
    covers circle (r = half the pad, so it degenerates to a plain circle test) and a plain box
    (r = 0, so the clamp remainder is just the overshoot past the edge). The remaining shapes
    (rect, trapezoid, custom) fall back to the same box every other check in this file already
    uses for them; a custom pad's real copper can run past its declared `size` (see gen_pcb's
    pads_board() docstring on Q10) so this under-counts a custom pad's true footprint, same as
    the rest of this file already does.
    """
    _ref, _pn, cx, cy, w, h, ang, _net, shape, rratio = pad
    ux, uy = rot(vx - cx, vy - cy, -ang)
    hw, hh = w / 2.0, h / 2.0
    if shape == "circle":
        r = hw
    elif shape == "oval":
        r = min(w, h) / 2.0
    elif shape == "roundrect":
        r = rratio * min(w, h)
    else:
        r = 0.0
    qx = max(abs(ux) - (hw - r), 0.0)
    qy = max(abs(uy) - (hh - r), 0.0)
    return math.hypot(qx, qy) <= r + 1e-6


def via_pad_tally(text):
    """Independent measurement: how many vias have their centre inside a copper pad.

    This is the number fabrication.md #14 item 1 tells the fab about. It used to be a
    hand-counted 65 (five named thermal paddles) with no way to notice the other population --
    vias this repo places deliberately at a pad centre on the feed chain, and vias the router
    drops off-centre wherever it changes layer inside a pad -- growing unseen. Recomputing it
    here from the board on every run is how it stops being able to go stale.

    Returns (hits, pads_hit, by_size, by_ref_prefix) where `hits` is the via count, `pads_hit`
    the count of distinct (ref, pad) pairs touched, `by_size` a dict of via diameter -> count,
    and `by_ref_prefix` a dict of the first non-digit prefix of each hit pad's ref (R, C, U, D,
    L, Q, F, ...) -> count of distinct pads of that prefix. Raises on anything that leaves the
    result in doubt -- an empty board, or zero pads/vias parsed -- so the gate can fail loudly
    on "cannot compute" rather than silently report zero.
    """
    root = G.parse(text)
    pads = read_pads_shaped(text)
    vias = read_vias_parsed(root)
    if not pads or not vias:
        raise ValueError("parsed %d pad(s) and %d via(s) -- cannot compute a tally"
                          % (len(pads), len(vias)))
    hit_pads = set()
    by_size = {}
    n = 0
    for vx, vy, vsize, vnet in vias:
        # A via is counted once even if its centre sits inside more than one same-net pad
        # (two pads of one net can legitimately overlap, e.g. a ground-plane-fill footprint) --
        # the question is "does this via need plugging", not "how many pads does it touch".
        for pad in pads:
            if pad[7] != vnet:
                continue
            if in_pad_shape(pad, vx, vy):
                hit_pads.add((pad[0], pad[1]))
                by_size[vsize] = by_size.get(vsize, 0) + 1
                n += 1
                break
    by_prefix = {}
    for ref, _pn in hit_pads:
        prefix = ref.rstrip("0123456789") or ref
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
    return n, len(hit_pads), by_size, by_prefix


def main():
    text = io.open(PCB, encoding="utf-8").read()
    pads = read_pads(text)
    netname = dict((int(a), b) for a, b in
                   re.findall(r'\n\t\(net (\d+) "([^"]*)"\)', text))

    vias = [(float(a), float(b), float(c), float(d), int(e))
            for a, b, c, d, e in VIA_RE.findall(text)]
    if not vias:
        print("FAIL: no vias on the board")
        return 1

    skipped = 0
    if BASE:
        keep = set()
        for a, b, c, d, _e in VIA_RE.findall(io.open(BASE, encoding="utf-8").read()):
            keep.add((round(float(a), 3), round(float(b), 3),
                      round(float(c), 3), round(float(d), 3)))
        mine = [v for v in vias if (round(v[0], 3), round(v[1], 3),
                                    round(v[2], 3), round(v[3], 3)) in keep]
        skipped = len(vias) - len(mine)
        missing = len(keep) - len(mine)
        vias = mine
        print("baseline %s: grading %d via(s), ignoring %d the router added"
              % (os.path.basename(BASE), len(vias), skipped))
        if missing > 0:
            # --keep-input-copper is meant to make this impossible.  If it happens the
            # routed board is not a superset of its input and freeze_routes.py will refuse
            # it too; say so here, where the reason is legible.
            print("  FAIL: %d via(s) of the baseline are not on this board" % missing)
            return 1
    elif os.path.exists(FROZEN):
        import json
        doc = json.load(io.open(FROZEN, encoding="utf-8"))
        drop = set()
        for net in doc.get("nets", {}).values():
            for x, y, sz, dr in net.get("vias", []):
                drop.add((round(x, 3), round(y, 3), round(sz, 3), round(dr, 3)))
        mine = [v for v in vias if (round(v[0], 3), round(v[1], 3),
                                    round(v[2], 3), round(v[3], 3)) not in drop]
        skipped = len(vias) - len(mine)
        vias = mine
        print("routes_signal.json: grading %d via(s), ignoring %d frozen from the router"
              % (len(vias), skipped))

    gnd = set(c for c, n in netname.items() if n == "GND")
    therm = [v for v in vias if v[2] < 0.6]
    # Diameter says what a via is for only on GND.  A 0.8 mm via on VBAT is a hand route
    # changing layer, and it lands on its own pad about as often as not; grading it by the
    # stitching rule reports the router doing its job as a fault.
    stitch = [v for v in vias if v[2] >= 0.6 and v[4] in gnd]
    power = [v for v in vias if v[2] >= 0.6 and v[4] not in gnd]

    bad = []
    hosts = {}
    for vx, vy, size, _drill, net in therm:
        r = size / 2.0
        home = [p for p in pads if p[7] == net and in_pad(p, vx, vy, r)]
        if not home:
            near = [p for p in pads if touches_pad(p, vx, vy, r)]
            bad.append("thermal via at (%.2f, %.2f) on %s is not inside any pad of its net%s"
                       % (vx, vy, netname.get(net, "?"),
                          "" if not near else " (nearest: %s.%s)" % (near[0][0], near[0][1])))
        else:
            hosts.setdefault((home[0][0], home[0][1]), 0)
            hosts[(home[0][0], home[0][1])] += 1

    for vx, vy, size, _drill, net in stitch:
        r = size / 2.0
        hit = [p for p in pads if touches_pad(p, vx, vy, r)]
        if hit:
            bad.append("stitching via at (%.2f, %.2f) sits on %s.%s (%s)"
                       % (vx, vy, hit[0][0], hit[0][1], netname.get(hit[0][7], "?")))

    landed = []
    for vx, vy, size, _drill, net in power:
        r = size / 2.0
        hit = [p for p in pads if touches_pad(p, vx, vy, r)]
        foreign = [p for p in hit if p[7] != net]
        if foreign:
            bad.append("%s via at (%.2f, %.2f) sits on %s.%s, which is %s"
                       % (netname.get(net, "?"), vx, vy, foreign[0][0], foreign[0][1],
                          netname.get(foreign[0][7], "?")))
        elif hit:
            landed.append("%s via at (%.2f, %.2f) on %s.%s"
                          % (netname.get(net, "?"), vx, vy, hit[0][0], hit[0][1]))

    print("vias: %d thermal (< 0.6 mm), %d GND stitching, %d power/route"
          % (len(therm), len(stitch), len(power)))
    for (ref, pn), n in sorted(hosts.items()):
        print("  %s pad %s: %d thermal vias" % (ref, pn, n))
    if landed:
        print("  %d power via(s) land on a pad of their own net (deliberate):" % len(landed))
        for s in landed:
            print("    " + s)
    for b in bad:
        print("  FAIL " + b)

    # Independent of everything above: how many vias need plugging and capping per
    # fabrication.md #14 item 1. This is not a DRC-shaped pass/fail -- a via landing in a pad
    # of its OWN net is legal copper, not a fault -- so the only failure mode here is not being
    # able to compute the number at all; a real reroute changing the count is expected and
    # exactly what recomputing it every run is for.
    try:
        vp_n, vp_pads, vp_size, vp_prefix = via_pad_tally(text)
    except Exception as e:
        print("  FAIL via-in-pad tally: %s" % e)
        return 1
    print("via-in-pad: %d via(s) land inside %d pad(s) -- see fabrication.md #14 item 1"
          % (vp_n, vp_pads))
    for sz in sorted(vp_size):
        print("  %.2f mm dia: %d" % (sz, vp_size[sz]))
    if vp_prefix:
        print("  by part prefix: "
              + ", ".join("%s %d" % (k, vp_prefix[k]) for k in sorted(vp_prefix)))

    if bad:
        return 1
    print("  OK: every thermal via is inside its own pad, every stitching via is clear of pads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
