# -*- coding: utf-8 -*-
"""Catch a zone that filled as two (or more) disconnected islands.

Task 7 pinched `GNDIN_F` in two.  It filled as a pair of disconnected copper islands and the
board shipped through every check this repo had:

    * KiCad DRC with `--refill-zones` reported 0 violations.  A split fill is an *unconnected
      item*, not a violation -- `--exit-code-violations` never sees it.
    * `check_grounds.py` passed.  It tests the zone's *authored polygon* with point-in-polygon
      against pad centres; the polygon was never wrong, the copper that filled inside it was.

What the DRC report shows that neither check does is the unconnected-item body itself.  A split
fill produces an `[unconnected_items]` block whose two anchors are BOTH the same zone, at the
same point -- KiCad reporting the zone as unconnected to itself:

    [unconnected_items]: Missing connection between items
        Local override; error
        @(42.0000 mm, 36.0000 mm): Zone 'GNDIN_F' [/power_input/GND_IN] on F.Cu, priority 1
        @(42.0000 mm, 36.0000 mm): Zone 'GNDIN_F' [/power_input/GND_IN] on F.Cu, priority 1

That is what this parses `output/drc.rpt` for.  It deliberately does NOT fire on a block where a
zone appears against a PAD -- a pad on the zone's net that failed to connect to it is a
different fault (a routing miss), already visible in the unconnected-pad count, and this board
carries one of those unrelated to any split fill: U4.4 has "no room for a drop" and shows up
paired with a pad, never with itself. Gating on "a zone appears in an unconnected item" would
also fire on that pad-only case; gating on "a zone is paired with itself" does not.

Run after `kicad-cli.exe pcb drc --refill-zones` has written `output/drc.rpt`.  Exit status is
non-zero if any zone shows the self-paired signature, or if the report cannot be trusted (it is
missing, or older than the board it is supposed to describe).

    python scripts/check_zone_islands.py                       # output/drc.rpt vs mccan.kicad_pcb
    python scripts/check_zone_islands.py other/drc.rpt other/board.kicad_pcb
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
REPORT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "output", "drc.rpt")
PCB = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HW, "mccan.kicad_pcb")

# Each block is exactly four lines: the header, "Local override; error", and two anchors.  Both
# anchors are captured whole and classified afterward -- a pad anchor and a zone anchor share no
# useful structure, so there is nothing to gain from parsing them with one pattern.
BLOCK_RE = re.compile(
    r'\[unconnected_items\]:[^\n]*\n'
    r'[ \t]*Local override; error\n'
    r'[ \t]*@\(([-\d.]+) mm, ([-\d.]+) mm\): ([^\n]+)\n'
    r'[ \t]*@\(([-\d.]+) mm, ([-\d.]+) mm\): ([^\n]+)')

ZONE_RE = re.compile(r"^Zone '([^']+)' \[([^\]]*)\] on ([^,\n]+)")


def main():
    if not os.path.exists(PCB):
        print("FAIL: %s is missing" % PCB)
        return 2
    if not os.path.exists(REPORT):
        print("FAIL: %s is missing -- run kicad-cli.exe pcb drc --refill-zones first" % REPORT)
        return 2
    # A stale report describes a board that no longer exists.  Silently trusting one is exactly
    # how the split fill this file exists to catch shipped in the first place: three checks ran
    # and returned 0 without any of them looking at current copper.
    if os.path.getmtime(REPORT) < os.path.getmtime(PCB):
        print("FAIL: %s is older than %s -- refill and re-run DRC before trusting this report"
              % (REPORT, PCB))
        return 2

    text = io.open(REPORT, encoding="utf-8").read()
    blocks = BLOCK_RE.findall(text)

    splits = []
    for x1, y1, d1, x2, y2, d2 in blocks:
        m1, m2 = ZONE_RE.match(d1), ZONE_RE.match(d2)
        if not m1 or not m2:
            continue
        if m1.group(1) != m2.group(1):
            continue
        splits.append((m1.group(1), m1.group(2), m1.group(3), float(x1), float(y1)))

    print("%s: %d unconnected-item block(s) parsed" % (os.path.basename(REPORT), len(blocks)))
    if splits:
        for name, net, layer, x, y in splits:
            print("  FAIL zone '%s' [%s] on %s is unconnected to itself at (%.4f mm, %.4f mm)"
                  % (name, net, layer, x, y))
        print("  -> the fill split into disconnected islands; refill and re-route the gap")
        return 1

    print("  OK: no zone is unconnected to itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
