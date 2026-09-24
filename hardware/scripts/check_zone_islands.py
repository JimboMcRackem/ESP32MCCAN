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
different fault (a routing miss), already visible in the unconnected-pad count, not a split
fill.  Gating on "a zone appears in an unconnected item" would fire on that pad case too;
gating on "a zone is paired with itself" does not.  This board currently has no zone-vs-pad
case at all -- `grep -c "Zone " output/drc.rpt` is 0 today -- so the exclusion is here to keep
the signature specific if one ever appears, not because one has been observed.

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

# Each block is exactly four lines: the header, a severity line, and two anchors.  Both anchors
# are captured whole and classified afterward -- a pad anchor and a zone anchor share no useful
# structure, so there is nothing to gain from parsing them with one pattern.
#
# The severity line is deliberately NOT pinned to the literal "Local override; error" text.
# Every block in both reports this gate has ever been run against carries exactly that string --
# confirmed on the current report and on 9f6d3a6's -- but that is a fact about the two boards
# examined, not a guarantee about what KiCad can emit.  Pinning to it would mean a block at a
# different severity fails to match, drops silently out of `blocks`, and the gate prints OK
# having never looked at it -- the exact "checks ran and returned 0" failure this file exists to
# prevent.  The header-count guard below is what makes that loosening safe: a block whose shape
# still doesn't match this pattern is no longer silent, it fails the whole run.
BLOCK_RE = re.compile(
    r'\[unconnected_items\]:[^\n]*\n'
    r'[ \t]*[^\n]+\n'
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
    # and returned 0 without any of them looking at current copper.  This comparison can in
    # principle misfire -- a checkout or git operation that restores mccan.kicad_pcb after
    # output/drc.rpt would make a genuinely fresh report look stale by a few seconds -- but the
    # trade is the right one either direction.  A false exit 2 costs the seconds it takes to
    # re-run DRC and look at why; trusting an mtime that lies costs a silent pass on a board that
    # was never actually checked, which is the failure this whole file exists to close off.
    if os.path.getmtime(REPORT) < os.path.getmtime(PCB):
        print("FAIL: %s is older than %s -- refill and re-run DRC before trusting this report"
              % (REPORT, PCB))
        return 2

    text = io.open(REPORT, encoding="utf-8").read()
    blocks = BLOCK_RE.findall(text)

    # A header this gate could not turn into a full block is a shape it does not recognise --
    # possibly the same "different severity line" case the loosened match above exists for,
    # taken further than this pattern accounts for.  Parsing FEWER blocks than there are
    # headers can hide a split fill and report clean, so it is fatal.
    #
    # It is a one-directional check, deliberately.  A block carrying a THIRD anchor line would
    # still parse from its first two, the counts would still agree, and the extra line would be
    # dropped without a word -- verified by injecting one.  That is tolerable where a short
    # block is not: the worst it can do is under-report, naming one split zone where the report
    # named two, and the gate still exits non-zero.  A short block makes the gate say OK.
    n_headers = text.count("[unconnected_items]:")
    if n_headers != len(blocks):
        print("FAIL: %d '[unconnected_items]' header(s) in %s but only %d parsed as full "
              "blocks -- this report has a shape this gate does not recognise and cannot be "
              "trusted" % (n_headers, REPORT, len(blocks)))
        return 2

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
