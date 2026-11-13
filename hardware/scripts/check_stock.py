"""Stock check for the JLCPCB assembly order (phase B, plan Task 2).

  python check_stock.py [--boards N] [--offline]

One line per BOM line:  OK|SHORT|MISSING <key> <lcsc> stock=<n> need=<n> fallback=<c>
Exit 1 on any SHORT or MISSING.  --offline checks only that every BOM line has an LCSC entry.
need = qty_per_board * N + attrition (max(5, 10%) for passives, 2 for the rest).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lcsc  # noqa: E402

NETLIST = os.path.join(HERE, "..", "output", "netlist.net")


def need(refs, boards):
    n = len(refs) * boards
    passive = refs[0][0] in "RCLD" and not refs[0].startswith(("DIP",))
    return n + (max(5, (n + 9) // 10) if passive else 2)


def fetch_stock(code):
    raise NotImplementedError


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=5)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    bad = 0
    for key, refs in lcsc.bom_lines(NETLIST):
        e = lcsc.LCSC.get(key)
        q = need(refs, a.boards)
        if not e:
            print("MISSING %s - stock=? need=%d fallback=- (%s)" % (key, q, ",".join(refs)))
            bad += 1
            continue
        if a.offline:
            print("OK %s %s stock=? need=%d fallback=%s" % (key, e["lcsc"], q, e["fallback"] or "-"))
            continue
        s = fetch_stock(e["lcsc"])
        st = "OK" if s >= q else "SHORT"
        bad += st != "OK"
        print("%s %s %s stock=%d need=%d fallback=%s" % (st, key, e["lcsc"], s, q, e["fallback"] or "-"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
