# -*- coding: utf-8 -*-
"""Tests for check_netlist_prog.py against the generated programmer netlist (plan Task 2).

  python hardware/programmer/scripts/test_netlist_prog.py      exit 1 on any failure

Each test checks the real netlist passes, then breaks a copy and checks the gate catches it.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_netlist_prog as C  # noqa: E402

NL = None


def nl():
    global NL
    if NL is None:
        NL = C.load()
    return NL


def moved(n, ref, pin, net):
    """A copy of netlist n with ref.pin moved onto net."""
    m = copy.deepcopy(n)
    old = m.pin_net[(ref, pin)]
    m.nets[old].discard("%s.%s" % (ref, pin))
    m.nets.setdefault(net, set()).add("%s.%s" % (ref, pin))
    m.pin_net[(ref, pin)] = net
    m.part_pins[ref][pin] = net
    return m


def fails_with(m, word):
    f = C.check(m)
    assert any(word in x for x in f), (word, f)


def test_real_netlist_passes():
    assert C.check(nl()) == [], C.check(nl())


def test_j2_pinout():
    want = {"1": "+3V3_OUT", "2": "GND", "3": "UART_TX", "4": "UART_RX", "5": "DTR", "6": "RTS"}
    for p, net in want.items():
        assert nl().net_of("J2", p) == net, (p, nl().net_of("J2", p))
    fails_with(moved(nl(), "J2", "3", "UART_RX"), "J2")


def test_txrx_crossed():
    n = nl()
    rxd = C.pin_named(n, "U1", "RXD")
    txd = C.pin_named(n, "U1", "TXD")
    assert C.series(n, "UART_TX", n.net_of("U1", rxd)) == ["R3"]
    assert C.ohms(n.parts["R3"].value) == 4700
    assert C.series(n, "UART_RX", n.net_of("U1", txd)) == ["R4"]
    assert C.ohms(n.parts["R4"].value) == 470
    # swap U1's TXD and RXD: the crossover is gone
    m = moved(moved(n, "U1", rxd, "U_TXD"), "U1", txd, "U_RXD")
    fails_with(m, "TX/RX")


def test_dtr_rts_through_buffer():
    n = nl()
    for hdr, rref, upin in (("DTR", "R5", "~{DTR}"), ("RTS", "R6", "~{RTS}")):
        mid = [x for x in C.series_nets(n, hdr) if x != hdr]
        assert C.series(n, hdr, mid[0]) == [rref], (hdr, mid)
        assert C.ohms(n.parts[rref].value) == 270
        y = [p for p in C.members(n, mid[0]) if p.startswith("U5.")]
        assert len(y) == 1, (hdr, y)
        a = C.U5_INPUT_OF[y[0].split(".")[1]]
        assert n.net_of("U5", a) == n.net_of("U1", C.pin_named(n, "U1", upin)), (hdr, a)
    for p in ("3", "4", "5", "6"):
        assert not any(x.startswith("U1.") for x in C.members(n, n.net_of("J2", p))), p
    fails_with(moved(n, "R5", "1", n.net_of("U1", C.pin_named(n, "U1", "~{DTR}"))), "DTR")


def test_cc_pulldowns():
    n = nl()
    for cc, pin in (("CC1", "A5"), ("CC2", "B5")):
        assert n.net_of("J1", pin) == cc
        rs = C.series(n, cc, "GND")
        assert len(rs) == 1 and C.ohms(n.parts[rs[0]].value) == 5100, (cc, rs)
    fails_with(moved(n, "R2", "2", "VBUS"), "CC2")


def test_usb_pair():
    n = nl()
    for pins, net in ((("A6", "B6"), "USB_DP"), (("A7", "B7"), "USB_DN")):
        for p in pins:
            assert n.net_of("J1", p) == net, (p, n.net_of("J1", p))
    assert n.net_of("U1", C.pin_named(n, "U1", "UD+")) == "USB_DP"
    assert n.net_of("U1", C.pin_named(n, "U1", "UD-")) == "USB_DN"
    assert {n.net_of("U2", p) for p in ("1", "6")} == {"USB_DP"}
    assert {n.net_of("U2", p) for p in ("3", "4")} == {"USB_DN"}
    assert n.net_of("U2", "5") == "VBUS" and n.net_of("U2", "2") == "GND"
    fails_with(moved(n, "U2", "3", "USB_DP"), "USB")


def test_reverse_blocking_topology():
    n = nl()
    assert n.net_of("U3", C.pin_named(n, "U3", "VI")) == "VBUS"
    assert n.net_of("U3", C.pin_named(n, "U3", "VO")) == "+3V3_USB"
    assert n.net_of("U4", "1") == "+3V3_USB"    # VIN
    assert n.net_of("U4", "6") == "+3V3_OUT"    # VOUT
    assert n.net_of("U4", "3") == "GND"         # ~CE, active low
    got = {p.split(".")[0] for p in C.members(n, "+3V3_OUT")}
    assert got == {"J2", "U4", "C4", "C5"}, got
    fails_with(moved(n, "C7", "1", "+3V3_OUT"), "+3V3_OUT")


def test_u1_supplies():
    n = nl()
    assert n.net_of("U1", C.pin_named(n, "U1", "VDD5")) == "VBUS"
    assert n.net_of("U1", C.pin_named(n, "U1", "VBUS")) == "VBUS"
    assert n.net_of("U1", C.pin_named(n, "U1", "VIO")) == "+3V3_USB"
    assert n.net_of("U1", "2") == "GND" and n.net_of("U1", "17") == "GND"
    assert "+3V3_OUT" not in n.part_pins["U1"].values()
    assert n.net_of("U5", "8") == "+3V3_USB" and n.net_of("U5", "4") == "GND"
    assert n.net_of("U5", "1") == "GND" and n.net_of("U5", "7") == "GND"   # ~OE
    fails_with(moved(n, "U1", C.pin_named(n, "U1", "VIO"), "+3V3_OUT"), "U1")


def test_power_budget():
    b = C.budget(nl())
    assert b["v_at_mccan_min"] >= 3.0, b
    assert b["u3_tj_c"] <= 125.0, b


def test_misplug_currents():
    b = C.budget(nl())
    for ref in ("R3", "R4", "R5", "R6"):
        assert b["misplug_ma"][ref] <= 15.0, b["misplug_ma"]


def test_unpowered_backfeed_budget():
    b = C.budget(nl())
    assert b["rxd_backfeed_ma"] <= 1.0, b
    assert b["en_hold_v"] >= 2.5, b
    assert b["en_hold_v_without_buffer"] < 2.5, b   # why U5 exists


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
    print("test_netlist_prog: %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
