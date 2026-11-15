# -*- coding: utf-8 -*-
"""Tests for parts.py (programmer board, plan Task 1).

  python hardware/programmer/scripts/test_parts.py      exit 1 on any failure
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parts  # noqa: E402

KICAD = "C:/Program Files/KiCad/10.0/share/kicad"


def test_every_ref_has_symbol_footprint_lcsc():
    for ref, e in parts.PARTS.items():
        for k in ("value", "symbol", "footprint", "lcsc", "mpn"):
            assert e.get(k), (ref, k)
        assert re.match(r"^C\d+$", e["lcsc"]), (ref, e["lcsc"])


def test_footprints_exist_in_kicad():
    for ref, e in parts.PARTS.items():
        lib, name = e["footprint"].split(":")
        p = "%s/footprints/%s.pretty/%s.kicad_mod" % (KICAD, lib, name)
        assert os.path.exists(p), (ref, p)


def test_symbols_exist_in_kicad():
    cache = {}
    for ref, e in parts.PARTS.items():
        lib, name = e["symbol"].split(":")
        if lib not in cache:
            cache[lib] = open("%s/symbols/%s.kicad_sym" % (KICAD, lib), encoding="utf-8").read()
        assert '(symbol "%s"' % name in cache[lib], (ref, e["symbol"])


def test_refs_match_plan():
    want = {"J1", "J2", "U1", "U2", "U3", "U4", "U5"}
    want |= {"R%d" % i for i in range(1, 11)}      # R10: back-feed bleeder (final review I1)
    want |= {"D1", "D2", "D3"}
    want |= {"C%d" % i for i in range(1, 10)}
    assert set(parts.PARTS) == want, sorted(set(parts.PARTS) ^ want)


def test_bom_lines_group_shared_parts():
    groups = [refs for _key, refs in parts.bom_lines()]
    assert ["R7", "R8", "R9", "R10"] in groups, groups
    assert ["C3", "C4", "C5"] in groups, groups
    allrefs = sorted(r for g in groups for r in g)
    assert allrefs == sorted(parts.PARTS), allrefs


def test_stock_grading_combined_need():
    import check_stock_prog as S
    lines = [("1k|R", ["R7", "R8", "R9"]), ("1k-alt|R", ["R1"])]
    table = {"R7": {"lcsc": "C1", "fallback": None}, "R1": {"lcsc": "C1", "fallback": None}}
    # need: 3x5 + max(5, 2) = 20 and 1x5 + 5 = 10 -> combined 30 on one C-number
    rows, bad = S.grade(lines, lambda ref: table[ref], lambda code: 29, boards=5)
    assert bad == 2 and all(r.startswith("SHORT") and "need=30" in r for r in rows), rows
    rows, bad = S.grade(lines, lambda ref: table[ref], lambda code: 30, boards=5)
    assert bad == 0 and all(r.startswith("OK") for r in rows), rows
    rows, bad = S.grade(lines, lambda ref: table[ref], lambda code: None, boards=5)
    assert bad == 2 and rows[0].startswith("MISSING"), rows


def main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:   # noqa: BLE001 -- report every test
                fails += 1
                print("FAIL", name, repr(e))
    print("test_parts: %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
