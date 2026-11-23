# -*- coding: utf-8 -*-
"""Tests for extract_board.py, run on the real board file.

  python hardware/enclosure/test_extract_board.py      exit 1 on any failure
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_board as E  # noqa: E402

PCB = os.path.join(HERE, "..", "mccan.kicad_pcb")
B = E.load(PCB)
PARTS = {p["ref"]: p for p in B["parts"]}
FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def near(a, b, tol=0.01):
    return abs(a - b) <= tol


def test_outline():
    o = B["outline"]
    check("outline", near(o["w"], 140) and near(o["h"], 100) and near(o["r"], 1) and near(o["t"], 1.6), o)


def test_holes():
    want = {"H1": (5, 5), "H2": (135, 5), "H3": (5, 95), "H4": (135, 95)}
    got = {h["ref"]: h for h in B["holes"]}
    check("holes refs", set(got) == set(want), sorted(got))
    for r, (x, y) in want.items():
        h = got.get(r)
        check("hole " + r, h and near(h["x"], x) and near(h["y"], y) and near(h["d"], 3.2), h)


def test_every_part_has_height():
    for p in B["parts"]:
        if p["ref"].startswith("H"):
            continue
        check("height>0 " + p["ref"], p["height"] > 0, p)
    l2 = PARTS["L2"]
    check("L2 height", near(l2["height"], 25.0) and l2["height_src"] in ("table", "datasheet"), l2)


def test_datasheet_floor_beats_short_model():
    # L2: Würth 7448031002 is 25.0 mm max above the board (datasheet side view); its nominal STEP
    # reads lower once placed (21.3 mm), so the datasheet figure must win over any shorter model.
    check("L2 floor", E.part_height("L2", 21.3) == (25.0, "datasheet"), E.part_height("L2", 21.3))
    check("model above floor kept", E.part_height("L2", 26.0) == (26.0, "model"), E.part_height("L2", 26.0))
    check("other part model", E.part_height("C3", 10.5) == (10.5, "model"), E.part_height("C3", 10.5))
    check("no model -> table", E.part_height("U1", None) == (1.75, "table"), E.part_height("U1", None))


def test_tallest():
    tall = max((p for p in B["parts"]), key=lambda p: p["height"])
    check("tallest is L2", tall["ref"] == "L2", tall["ref"])
    for r in ("C3", "C68"):
        check(r + " height", near(PARTS[r]["height"], 10.5, 0.3), PARTS[r]["height"])


def test_rotated_courtyard():
    x0, y0, x1, y1 = PARTS["C6"]["bbox"]  # C_1206 at 90 deg: long axis along y
    check("C6 rotated", (y1 - y0) > (x1 - x0), PARTS["C6"]["bbox"])


def test_l2_bbox():
    x0, y0, x1, y1 = PARTS["L2"]["bbox"]  # courtyard, board coords
    check("L2 bbox", near(x0, 6.25) and near(x1, 31.25) and near(y0, 31.15) and near(y1, 50.8), PARTS["L2"]["bbox"])


def test_tails():
    refs = sorted(t["ref"] for t in B["tails"])
    check("tail refs", refs == sorted(["J1", "J3", "J4", "J5", "J8", "J9", "J10", "J11"]), refs)
    for t in B["tails"]:
        for x, y, d in t["pads"]:
            check("tail pad y " + t["ref"], y > 75, (x, y))


def test_access():
    a = B["access"]
    check("TP count", len(a["TP"]) == 30, len(a["TP"]))
    for k in ("J2", "SW1", "SW2"):
        check("access " + k, k in a and len(a[k]) == 4, a.get(k))


def test_antenna():
    check("antenna zone", B["antenna"]["zone"] == [55.75, -15, 134.25, 21.44], B["antenna"])
    check("antenna copper", B["antenna"]["copper"] == [70.75, 0, 119.25, 6.44], B["antenna"])


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
    for f in FAILS:
        print("FAIL", f)
    print(f"{'FAILED' if FAILS else 'OK'}: {len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)
