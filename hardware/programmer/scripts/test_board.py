# -*- coding: utf-8 -*-
"""Tests for the generated programmer board (plan Task 3).

  python hardware/programmer/scripts/test_board.py      exit 1 on any failure
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_board as B  # noqa: E402
import parts  # noqa: E402

BD = None


def bd():
    global BD
    if BD is None:
        BD = B.read(B.PCB)
    return BD


def test_outline_size():
    x0, y0, x1, y1 = bd().edge
    assert x1 - x0 <= 22.0 and y1 - y0 <= 42.0, bd().edge


def test_all_top_side():
    bad = [f.ref for f in bd().fps if f.layer != "F.Cu"]
    assert not bad, bad


def test_every_part_placed():
    assert {f.ref for f in bd().fps} == set(parts.PARTS)


def test_j1_at_edge():
    # the receptacle's mouth (front of its courtyard) sits at the top edge, within 0.5 mm
    x0, y0, x1, y1 = bd().edge
    front = B.courtyard(bd(), "J1")[1]
    assert abs(front - y0) <= 0.5, (front, y0)


def test_j2_far_end():
    x0, y0, x1, y1 = bd().edge
    j2 = bd().fp("J2")
    assert y1 - j2.y <= 5.0, (j2.y, y1)


def test_header_silk():
    words = B.silk_words(bd())
    for w in ("3V3", "GND", "TX", "RX", "DTR", "RTS", "MCCAN PROG", "PWR"):
        assert any(w in t for t in words), (w, words)
    assert B.pin1_mark_near(bd(), "J2", B.PIN1_MARK_MM), "no pin-1 mark near J2 pin 1"


def test_usb_pair_routing():
    for net in ("USB_DP", "USB_DN"):
        assert B.via_count(bd(), net) <= 2, (net, B.via_count(bd(), net))
    a, b = B.track_length(bd(), "USB_DP"), B.track_length(bd(), "USB_DN")
    assert abs(a - b) <= B.USB_SKEW_MM and max(a, b) <= B.USB_MAX_MM, (a, b)


def test_regulator_heatsink_pour():
    assert B.zone_has_pad(bd(), "+3V3_USB", "F.Cu", "U3", "2"), "U3 tab not in an F.Cu +3V3_USB zone"
    area = B.zone_area(bd(), "+3V3_USB")
    assert area >= 200.0, area


def test_power_track_widths():
    bad = B.thin_power_tracks(bd(), ("VBUS", "+3V3_USB", "+3V3_OUT"))
    assert not bad, bad


def test_check_passes():
    f = B.check(B.PCB)
    assert not f, f


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
    print("test_board: %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
