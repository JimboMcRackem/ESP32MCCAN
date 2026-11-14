# -*- coding: utf-8 -*-
"""Generate hardware/programmer/prog.kicad_sch (and a minimal prog.kicad_pro if absent).

  python hardware/programmer/scripts/gen_sch.py

The whole circuit is the CONNECT table below: ref -> {pin number: net, None = no-connect}.
Header-side nets carry the MCCAN board's own names (UART_TX, UART_RX, DTR, RTS) so the cable
reads straight across.  Why each part and value: hardware/programmer/README.md.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(PROG, "..", "scripts"))
import kicanon  # noqa: E402
import parts  # noqa: E402
from schlib import Sheet  # noqa: E402

SCH = os.path.join(PROG, "prog.kicad_sch")
PRO = os.path.join(PROG, "prog.kicad_pro")

V, G, U, O = "VBUS", "GND", "+3V3_USB", "+3V3_OUT"

CONNECT = {
    # USB-C receptacle: USB 2.0 device, both orientations
    "J1": {"A1": G, "A12": G, "B1": G, "B12": G, "SH": G,
           "A4": V, "A9": V, "B4": V, "B9": V,
           "A5": "CC1", "B5": "CC2",
           "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN",
           "A8": None, "B8": None},
    # programmer header: the MCCAN J2's pin order, so the cable is straight-through
    "J2": {"1": O, "2": G, "3": "UART_TX", "4": "UART_RX", "5": "DTR", "6": "RTS"},
    # CH343P: VDD5/VBUS from USB, I/O at 3.3 V; modem inputs have internal pull-ups
    "U1": {"1": U, "2": G, "17": G, "3": V, "9": V, "6": "V3_U1",
           "4": "U_TXD", "5": "U_RXD", "7": "USB_DP", "8": "USB_DN",
           "12": "U_DTR", "13": "U_RTS",
           "10": None, "11": None, "14": None, "15": None, "16": None},
    "U2": {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "2": G, "5": V},
    "U3": {"1": G, "2": U, "3": V},                    # AMS1117: GND, VO, VI
    "U4": {"1": U, "2": G, "3": G, "4": None, "5": None, "6": O},   # LM66100, ~CE low = on
    "R1": {"1": "CC1", "2": G},
    "R2": {"1": "CC2", "2": G},
    "R3": {"1": "UART_TX", "2": "U_RXD"},
    "R4": {"1": "U_TXD", "2": "UART_RX"},
    "R5": {"1": "B_DTR", "2": "DTR"},
    "R6": {"1": "B_RTS", "2": "RTS"},
    "R7": {"1": U, "2": "LED_PWR"},
    "R8": {"1": U, "2": "LED_TX"},
    "R9": {"1": U, "2": "LED_RX"},
    "D1": {"2": "LED_PWR", "1": G},                    # Device:LED: 1 = K, 2 = A
    "D2": {"2": "LED_TX", "1": "U_TXD"},
    "D3": {"2": "LED_RX", "1": "UART_TX"},
    "C1": {"1": V, "2": G}, "C2": {"1": V, "2": G}, "C6": {"1": V, "2": G},
    "C3": {"1": U, "2": G}, "C7": {"1": U, "2": G}, "C9": {"1": U, "2": G},
    "C4": {"1": O, "2": G}, "C5": {"1": O, "2": G},
    "C8": {"1": "V3_U1", "2": G},
}
# 74LVC2G125, one entry per unit: 1 = DTR buffer, 2 = RTS buffer, 3 = supply
U5_UNITS = {1: {"1": G, "2": "U_DTR", "6": "B_DTR"},
            2: {"7": G, "5": "U_RTS", "3": "B_RTS"},
            3: {"4": G, "8": U}}

# sheet positions (A3, mm, on the 2.54 grid); two-pin parts are laid out in rows below
POS = {"J1": (50.8, 76.2), "U2": (119.38, 63.5), "U1": (190.5, 76.2),
       "U3": (50.8, 152.4), "U4": (119.38, 152.4), "J2": (190.5, 152.4)}
U5_POS = {1: (279.4, 50.8), 2: (279.4, 101.6), 3: (337.82, 76.2)}
ROW_RC = (25.4, 215.9, 15.24)      # x0, y, step
ROW_LED = (63.5, 254.0, 38.1)
FLAGS = (("#FLG01", V, (264.16, 152.4)), ("#FLG02", G, (289.56, 152.4)))


def fields(ref):
    e = parts.PARTS[ref]
    return [("Footprint", e["footprint"]), ("LCSC", e["lcsc"]), ("MPN", e["mpn"])]


def build():
    sh = Sheet("prog", "MCCAN programmer", "A", "2026-11-14", paper="A3")
    for ref, (x, y) in POS.items():
        e = parts.PARTS[ref]
        sh.place(ref, e["symbol"], e["value"], x, y, CONNECT[ref], fields=fields(ref))
    e = parts.PARTS["U5"]
    for unit, (x, y) in U5_POS.items():
        sh.place("U5", e["symbol"], e["value"], x, y, U5_UNITS[unit], unit=unit,
                 fields=fields("U5"))
    twopin = [r for r in parts.PARTS if r[0] in "RC"]
    x0, y, step = ROW_RC
    for i, ref in enumerate(sorted(twopin, key=lambda r: (r[0], int(r[1:])))):
        e = parts.PARTS[ref]
        sh.place(ref, e["symbol"], e["value"], round(x0 + i * step, 4), y, CONNECT[ref],
                 fields=fields(ref))
    x0, y, step = ROW_LED
    for i, ref in enumerate(("D1", "D2", "D3")):
        e = parts.PARTS[ref]
        sh.place(ref, e["symbol"], e["value"], round(x0 + i * step, 4), y, CONNECT[ref],
                 fields=fields(ref))
    for ref, net, (x, y) in FLAGS:
        sh.place(ref, "power:PWR_FLAG", "PWR_FLAG", x, y, {"1": net})
    placed = {s["ref"] for s in sh.syms}
    assert placed >= set(parts.PARTS), sorted(set(parts.PARTS) - placed)
    text = kicanon.canonicalise(sh.text())
    with open(SCH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if not os.path.exists(PRO):
        with open(PRO, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"meta": {"filename": "prog.kicad_pro", "version": 3}}, f, indent=2)
            f.write("\n")
    return text


if __name__ == "__main__":
    t = build()
    print("wrote %s (%d lines)" % (SCH, t.count("\n")))
