# -*- coding: utf-8 -*-
"""Stock check for the programmer board's JLCPCB assembly order (plan Task 1).

  python hardware/programmer/scripts/check_stock_prog.py [--boards N] [--offline]

Same output and rules as hardware/scripts/check_stock.py (whose fetch_stock and need it reuses):
  OK|SHORT|MISSING <value|footprint> <lcsc> stock=<n> need=<n> fallback=<c>
Exit 1 on any SHORT or MISSING.  Lines sharing a C-number are graded on their combined need.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "..", "scripts"))
import parts  # noqa: E402
from check_stock import fetch_stock, need  # noqa: E402


def grade(lines, entry_of, stock_of, boards):
    """lines: [(key, refs)]; entry_of(first ref) -> {"lcsc","fallback"}; stock_of(code) -> int|None.
    Returns (printed rows, number of SHORT/MISSING lines)."""
    total, cache, rows, bad = {}, {}, [], 0
    for key, refs in lines:
        code = entry_of(refs[0])["lcsc"]
        total[code] = total.get(code, 0) + need(refs, boards)
    for key, refs in lines:
        e = entry_of(refs[0])
        code, fb = e["lcsc"], e["fallback"] or "-"
        if code not in cache:
            cache[code] = stock_of(code)
        s, q = cache[code], total[code]
        if s is None:
            st, s = "MISSING", 0
        else:
            st = "OK" if s >= q else "SHORT"
        bad += st != "OK"
        rows.append("%s %s %s stock=%d need=%d fallback=%s" % (st, key, code, s, q, fb))
    return rows, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=5)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    lines = parts.bom_lines()
    if a.offline:
        for key, refs in lines:
            e = parts.PARTS[refs[0]]
            print("OK %s %s stock=? need=%d fallback=%s"
                  % (key, e["lcsc"], need(refs, a.boards), e["fallback"] or "-"))
        return 0
    rows, bad = grade(lines, lambda r: parts.PARTS[r], fetch_stock, a.boards)
    for r in rows:
        print(r)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
