"""Stock check for the JLCPCB assembly order (phase B, plan Task 2).

  python check_stock.py [--boards N] [--offline]

One line per BOM line:
  OK|SHORT|MISSING|GLOBAL <key> <lcsc> stock=<n> need=<n> fallback=<c>
Exit 1 on any SHORT or MISSING.  GLOBAL means JLCPCB's own stock is short but the owner has
approved JLCPCB global sourcing of that exact part (lcsc.py fallback "GLOBAL" plus an OWNER
note) -- still machine-placed, but it adds lead time: read those lines before ordering.

--offline checks only that every BOM line has an LCSC entry.
need = qty_per_board * N + attrition (max(5, 10 %) for passives, 2 for the rest).  Lines that
share a C-number draw on one stock, so each is graded, and shown, with their combined need.

Stock source: JLCPCB's own assembly-parts API (the stock the assembler places from),
  POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList
  {"keyword": "<C-number>", "currentPage": 1, "pageSize": 5}  ->  data.componentPageInfo.list[].stockCount
LCSC's own endpoint (https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=<C>) reports the
distributor warehouse, which is not what the assembler draws on.  Endpoints as of 2026-11-13.
"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lcsc  # noqa: E402

NETLIST = os.path.join(HERE, "..", "output", "netlist.net")
API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def need(refs, boards):
    n = len(refs) * boards
    passive = refs[0][0] in "RCLD"
    return n + (max(5, (n + 9) // 10) if passive else 2)


def fetch_stock(code):
    """JLCPCB assembly stock for one C-number; None if the part is not listed."""
    req = urllib.request.Request(
        API, data=json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for c in ((d.get("data") or {}).get("componentPageInfo") or {}).get("list") or []:
        if c.get("componentCode") == code:
            return int(c.get("stockCount") or 0)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=5)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    bad = 0
    lines = lcsc.bom_lines(NETLIST)
    # Lines that share a C-number (SW1 and SW2 differ only in value) draw on one stock: grade
    # each against the combined need, and fetch each C-number once.
    total, stock = {}, {}
    for key, refs in lines:
        e = lcsc.LCSC.get(key)
        if e:
            total[e["lcsc"]] = total.get(e["lcsc"], 0) + need(refs, a.boards)
    for key, refs in lines:
        e = lcsc.LCSC.get(key)
        q = need(refs, a.boards)
        if not e:
            print("MISSING %s - stock=? need=%d fallback=- (%s)" % (key, q, ",".join(refs)))
            bad += 1
            continue
        fb = e["fallback"] or "-"
        if a.offline:
            print("OK %s %s stock=? need=%d fallback=%s" % (key, e["lcsc"], q, fb))
            continue
        if e["lcsc"] not in stock:
            stock[e["lcsc"]] = fetch_stock(e["lcsc"])
        s = stock[e["lcsc"]]
        if total[e["lcsc"]] > q:
            q = total[e["lcsc"]]   # shown as need=<combined>
        if s is None:
            st, s = "MISSING", 0
        elif s >= q:
            st = "OK"
        elif fb == "GLOBAL" and "OWNER" in e["note"]:
            st = "GLOBAL"
        else:
            st = "SHORT"
        bad += st in ("SHORT", "MISSING")
        print("%s %s %s stock=%d need=%d fallback=%s" % (st, key, e["lcsc"], s, q, fb))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
