"""BOM line -> JLCPCB/LCSC part mapping (phase B, plan Task 2).

Key: "<value>|<footprint>" exactly as the netlist holds them.  Each entry:
  {"lcsc": "C1234", "mpn": "...", "fallback": "C5678" or None, "note": "..."}
A fallback is pre-chosen for every line whose LCSC stock was under 200 when chosen.
"""
from collections import defaultdict
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_netlist  # noqa: E402
from fpmap import in_bom  # noqa: E402

LCSC = {
}


def bom_lines(netlist_path):
    """Non-DNP, in_bom() parts grouped by value + footprint, sorted by key."""
    nl = check_netlist.load(netlist_path)
    groups = defaultdict(list)
    for ref, p in nl.parts.items():
        if p.dnp or not in_bom(ref):
            continue
        groups["%s|%s" % (p.value, p.footprint)].append(ref)
    return sorted((k, sorted(v, key=lambda r: (r.rstrip("0123456789"), int("0" + r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ_")))))
                  for k, v in groups.items())
