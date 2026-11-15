# -*- coding: utf-8 -*-
"""Netlist gate for the programmer board (plan Task 2).

  python hardware/programmer/scripts/check_netlist_prog.py      exit 1 on any failure

Asserts the J2 pinout and the TX/RX crossover (spec 6.1-6.2), the USB-C device wiring, the
reverse-blocking power path (spec 6.3), the DTR/RTS buffer that keeps an unpowered programmer
from holding the ESP32 in reset, and prints the power / misplug / back-feed budget.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(PROG, "..", "scripts"))
import check_netlist  # noqa: E402

NETLIST = os.path.join(PROG, "output", "netlist.net")
MCCAN_NETLIST = os.path.join(PROG, "..", "output", "netlist.net")

J2_PINOUT = {"1": "+3V3_OUT", "2": "GND", "3": "UART_TX", "4": "UART_RX", "5": "DTR", "6": "RTS"}
U5_INPUT_OF = {"6": "2", "3": "5"}     # 74LVC2G125: output Y pin -> its A input pin
# Header DTR/RTS are fed from U1's ~RTS/~DTR: CROSSED.  The MCCAN board's EN transistor (Q2)
# has its emitter on DTR and its base fed from RTS (R28) -- the reverse of Espressif's
# circuit -- so esptool's "pin DTR high, pin RTS low" reset only reaches EN if the programmer
# swaps the two.  test_esptool_auto_reset traces it through both netlists.
HEADER_FROM_U1 = {"DTR": "~{RTS}", "RTS": "~{DTR}"}

# ---- budget inputs (sources in hardware/programmer/README.md)
V_REG_MIN = 3.234       # AMS1117-3.3: 3.3 V -2 % over line, load and temperature
VBUS_MAX = 5.25         # USB 2.0 VBUS maximum
VBUS_MIN = 4.75         # USB 2.0 VBUS minimum at a host port (a bus-powered hub may give 4.4)
R_USB_CABLE = 0.4       # 1 m USB cable, VBUS out and GND back
U3_DROPOUT = 1.3        # AMS1117 dropout, max at 800 mA (datasheet; 1.1 V typ)
I_LOAD = 0.6            # spec 6.3: 600 mA continuous
I_OWN = 0.01            # U1 3 mA + LEDs ~3.5 mA + U5, rounded up
R_U4 = 0.095            # LM66100 on-resistance (JLCPCB listing; datasheet typ 79 mOhm)
R_CABLE = 0.2           # 20 cm Dupont, out and back, with four crimp contacts
THETA_U3 = 70.0         # SOT-223 on >= 150 mm2 of tab copper (Task 3 asserts the area)
T_BENCH = 25.0
V_MCCAN_MAX = 3.34      # MCCAN U1 set point, top of tolerance (spec 6.3)
V_ESD = 0.5             # forward drop of a CMOS input's ESD diode at < 1 mA
R22_EN_PULLUP = 10e3    # MCCAN EN_MCU pull-up (hardware/output/netlist.net R22)
I_OFF = 10e-6           # SN74LVC2G125 Ioff max, VCC = 0


def load(path=NETLIST):
    return check_netlist.load(path)


def members(nl, net):
    return sorted(nl.nets.get(net, ()))


def pin_named(nl, ref, name):
    """The pin number of ref whose pin function is `name` (KiCad may append _<n>)."""
    hits = [p for (r, p), f in nl.pinfunc.items()
            if r == ref and (f == name or re.fullmatch(re.escape(name) + r"_\d+", f))]
    assert len(hits) == 1, (ref, name, hits)
    return hits[0]


def ohms(v):
    m = re.fullmatch(r"([\d.]+)\s*([kKmM]?)", v.strip().replace("R", ""))
    assert m, v
    return float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e-3, "M": 1e6}[m.group(2)]


def series(nl, a, b):
    """Resistors with one pin on net a and the other on net b."""
    out = []
    for ref, pins in nl.part_pins.items():
        if ref.startswith("R") and sorted(pins.values()) == sorted([a, b]) and a != b:
            out.append(ref)
    return sorted(out)


def series_nets(nl, net):
    """Nets reached from `net` through one resistor."""
    out = set()
    for ref, pins in nl.part_pins.items():
        if ref.startswith("R") and net in pins.values():
            out |= set(pins.values())
    return sorted(out)


def budget(nl):
    r = {k: ohms(nl.parts[k].value) for k in ("R3", "R4", "R5", "R6")}
    p_u3 = (VBUS_MAX - V_REG_MIN) * (I_LOAD + I_OWN)
    # U3 is regulating, or in dropout from the lowest VBUS a host port gives through a cable
    v_u3 = min(V_REG_MIN, VBUS_MIN - (I_LOAD + I_OWN) * R_USB_CABLE - U3_DROPOUT)
    i_rxd = (V_MCCAN_MAX - V_ESD) / r["R3"]
    # USB unplugged, MCCAN powered: the ESP's TX injects i_rxd into +3V3_USB through U1's RXD
    # ESD diode; the bleeder alone (worst case, nothing else loading the rail) sets the rail
    bleed = [ohms(nl.parts[k].value) for k in series(nl, "+3V3_USB", "GND")]
    v_rail = i_rxd * min(bleed) if bleed else float("inf")
    return {
        "v_u3_out_min": round(v_u3, 3),
        "v_at_mccan_min": round(v_u3 - I_LOAD * (R_U4 + R_CABLE), 3),
        "u3_watts": round(p_u3, 3),
        "u3_tj_c": round(T_BENCH + p_u3 * THETA_U3, 1),
        "misplug_ma": {k: round(V_MCCAN_MAX / v * 1e3, 2) for k, v in r.items()},
        "rxd_backfeed_ma": round(i_rxd * 1e3, 3),
        "usb_rail_backfed_v": round(v_rail, 3),
        "en_hold_v": round(V_MCCAN_MAX - R22_EN_PULLUP * I_OFF, 3),
    }


def auto_reset_states(nl, mccan):
    """Which of the MCCAN board's EN_MCU / BOOT_N each esptool step pulls low.

    Programmer: U1 pin level -> U5 (non-inverting) -> one series resistor -> header pin.
    MCCAN: header pin -> J2 net; an NPN with its collector on EN_MCU or BOOT_N conducts when
    the net feeding its base resistor is high and its emitter net is low.
    Returns {"reset": {...}, "boot": {...}}, each {collector net: pulled low?}."""
    def header_pin(u1_name):
        u = nl.net_of("U1", pin_named(nl, "U1", u1_name))
        ys = [y for y, a in U5_INPUT_OF.items() if nl.net_of("U5", a) == u]
        assert len(ys) == 1, (u1_name, ys)
        out = nl.net_of("U5", ys[0])
        hdr = [x for x in series_nets(nl, out) if x != out]
        assert len(hdr) == 1, (u1_name, hdr)
        pins = [p for p, n in nl.part_pins["J2"].items() if n == hdr[0]]
        assert len(pins) == 1, (u1_name, pins)
        return pins[0]

    def fn(ref, letter):
        return next(p for (r, p), f in mccan.pinfunc.items()
                    if r == ref and f.split("_")[0] == letter)

    route = {u: mccan.net_of("J2", header_pin(u)) for u in ("~{DTR}", "~{RTS}")}
    out = {}
    for step, lv in (("reset", {"~{DTR}": 1, "~{RTS}": 0}), ("boot", {"~{DTR}": 0, "~{RTS}": 1})):
        level = {route[u]: v for u, v in lv.items()}
        got = {}
        for q in sorted(r for r in mccan.part_pins if r.startswith("Q")):
            try:
                c = mccan.net_of(q, fn(q, "C"))
            except StopIteration:
                continue
            if c not in ("EN_MCU", "BOOT_N"):
                continue
            e = mccan.net_of(q, fn(q, "E"))
            b = mccan.net_of(q, fn(q, "B"))
            src = [x for x in series_nets(mccan, b) if x != b]
            on = len(src) == 1 and level.get(src[0]) == 1 and level.get(e) == 0
            got[c] = got.get(c, False) or on
        out[step] = got
    return out


# ------------------------------------------------------------------ checks
def chk_j2(nl):
    return ["J2.%s is on %s, want %s" % (p, nl.net_of("J2", p), net)
            for p, net in J2_PINOUT.items() if nl.net_of("J2", p) != net]


def _through(nl, hdr_net, u1_name, want_r):
    try:
        u1 = nl.net_of("U1", pin_named(nl, "U1", u1_name))
    except AssertionError:
        return False
    return series(nl, hdr_net, u1) == [want_r]


def chk_txrx(nl):
    f = []
    if not _through(nl, "UART_TX", "RXD", "R3"):
        f.append("TX/RX: header pin 3 (ESP TX) must reach U1 RXD through R3 only")
    if not _through(nl, "UART_RX", "TXD", "R4"):
        f.append("TX/RX: header pin 4 (ESP RX) must reach U1 TXD through R4 only")
    return f


def chk_dtr_rts(nl):
    f = []
    for hdr, rref in (("DTR", "R5"), ("RTS", "R6")):
        upin = HEADER_FROM_U1[hdr]
        mids = [x for x in series_nets(nl, hdr) if x != hdr]
        ok = len(mids) == 1 and series(nl, hdr, mids[0]) == [rref]
        if ok:
            ys = [p.split(".")[1] for p in members(nl, mids[0]) if p.startswith("U5.")]
            ok = (len(ys) == 1 and ys[0] in U5_INPUT_OF and
                  nl.net_of("U5", U5_INPUT_OF[ys[0]]) ==
                  nl.net_of("U1", pin_named(nl, "U1", upin)))
        if not ok:
            f.append("%s: header must reach U1 %s via %s and a U5 buffer" % (hdr, upin, rref))
    for p in ("3", "4", "5", "6"):           # signal pins; 1 and 2 are supply and GND
        if any(x.startswith("U1.") for x in members(nl, nl.net_of("J2", p))):
            f.append("J2.%s: touches U1 directly (no series resistor / buffer)" % p)
    return f


def chk_cc(nl):
    f = []
    for cc, pin in (("CC1", "A5"), ("CC2", "B5")):
        rs = series(nl, cc, "GND")
        if nl.net_of("J1", pin) != cc or len(rs) != 1 or ohms(nl.parts[rs[0]].value) != 5100:
            f.append("%s: J1.%s needs exactly one 5.1k to GND" % (cc, pin))
    return f


def chk_usb(nl):
    want = [("J1", "A6", "USB_DP"), ("J1", "B6", "USB_DP"), ("J1", "A7", "USB_DN"),
            ("J1", "B7", "USB_DN"), ("U2", "1", "USB_DP"), ("U2", "6", "USB_DP"),
            ("U2", "3", "USB_DN"), ("U2", "4", "USB_DN"), ("U2", "5", "VBUS"),
            ("U2", "2", "GND")]
    f = ["USB: %s.%s is on %s, want %s" % (r, p, nl.net_of(r, p), n)
         for r, p, n in want if nl.net_of(r, p) != n]
    for name, net in (("UD+", "USB_DP"), ("UD-", "USB_DN")):
        if nl.net_of("U1", pin_named(nl, "U1", name)) != net:
            f.append("USB: U1 %s not on %s" % (name, net))
    return f


def chk_power(nl):
    f = []
    want = [("U3", pin_named(nl, "U3", "VI"), "VBUS"), ("U3", pin_named(nl, "U3", "VO"), "+3V3_USB"),
            ("U4", "1", "+3V3_USB"), ("U4", "6", "+3V3_OUT"), ("U4", "3", "GND")]
    f += ["power: %s.%s is on %s, want %s" % (r, p, nl.net_of(r, p), n)
          for r, p, n in want if nl.net_of(r, p) != n]
    out = {p.split(".")[0] for p in members(nl, "+3V3_OUT")}
    if out != {"J2", "U4", "C4", "C5"}:
        f.append("+3V3_OUT: members %s, want only J2, U4, C4, C5" % sorted(out))
    return f


def chk_u1_u5_supplies(nl):
    want = [("U1", pin_named(nl, "U1", "VDD5"), "VBUS"), ("U1", pin_named(nl, "U1", "VBUS"), "VBUS"),
            ("U1", pin_named(nl, "U1", "VIO"), "+3V3_USB"), ("U1", "2", "GND"), ("U1", "17", "GND"),
            ("U5", "8", "+3V3_USB"), ("U5", "4", "GND"), ("U5", "1", "GND"), ("U5", "7", "GND")]
    f = ["supply: %s.%s is on %s, want %s" % (r, p, nl.net_of(r, p), n)
         for r, p, n in want if nl.net_of(r, p) != n]
    if "+3V3_OUT" in nl.part_pins["U1"].values():
        f.append("supply: U1 must not touch +3V3_OUT")
    return f


def chk_budget(nl):
    b, f = budget(nl), []
    if b["v_at_mccan_min"] < 3.0:
        f.append("budget: %.3f V at the MCCAN board < 3.0 V" % b["v_at_mccan_min"])
    if b["u3_tj_c"] > 125.0:
        f.append("budget: U3 junction %.1f C > 125 C" % b["u3_tj_c"])
    f += ["budget: misplug %s %.1f mA > 15 mA" % (k, v) for k, v in b["misplug_ma"].items()
          if v > 15.0]
    if b["rxd_backfeed_ma"] > 1.0 or b["en_hold_v"] < 2.5 or b["usb_rail_backfed_v"] >= 1.0:
        f.append("budget: unpowered back-feed %s" % b)
    return f


def chk_auto_reset(nl):
    want = {"reset": {"EN_MCU": True, "BOOT_N": False}, "boot": {"EN_MCU": False, "BOOT_N": True}}
    try:
        got = auto_reset_states(nl, load(MCCAN_NETLIST))
    except (AssertionError, KeyError, StopIteration) as e:
        return ["auto-reset: cannot trace DTR/RTS to the MCCAN board (%r)" % (e,)]
    return [] if got == want else ["auto-reset: esptool's steps pull %s, want %s" % (got, want)]


CHECKS = (chk_j2, chk_txrx, chk_dtr_rts, chk_cc, chk_usb, chk_power, chk_u1_u5_supplies,
          chk_budget, chk_auto_reset)


def check(nl):
    f = []
    for c in CHECKS:
        try:
            f += c(nl)
        except AssertionError as e:      # a pin missing or doubled is itself a failure
            f.append("%s: %r" % (c.__name__, e))
    return f


def main():
    nl = load()
    for k, v in budget(nl).items():
        print("budget %s = %s" % (k, v))
    f = check(nl)
    for x in f:
        print("FAIL", x)
    print("check_netlist_prog: %s" % ("PASS" if not f else "FAIL (%d)" % len(f)))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
