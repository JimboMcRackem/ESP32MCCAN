# -*- coding: utf-8 -*-
"""Programmer board part table (plan 2026-11-14-programmer-board, Task 1).

PARTS[ref] = {"value", "symbol", "footprint", "lcsc", "mpn", "fallback", "note"}
  symbol / footprint: KiCad 10 stock library ids.
  lcsc: JLCPCB C-number, checked against JLCPCB's own stock by check_stock_prog.py.
  fallback: a pre-chosen alternative C-number, "GLOBAL" (JLCPCB global sourcing) or None.
Stock checked 2026-11-14.  Why each part was chosen: hardware/programmer/README.md.
"""
from collections import OrderedDict
import re

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"


def _p(value, symbol, footprint, lcsc, mpn, fallback=None, note=""):
    return {"value": value, "symbol": symbol, "footprint": footprint, "lcsc": lcsc,
            "mpn": mpn, "fallback": fallback, "note": note}


def _r(value, lcsc, mpn, note=""):
    return _p(value, "Device:R", R0603, lcsc, mpn, None, note)


PARTS = OrderedDict([
    ("J1", _p("USB-C", "Connector:USB_C_Receptacle_USB2.0_16P",
              "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "C165948", "TYPE-C-31-M-12",
              None, "USB 2.0 device receptacle")),
    ("J2", _p("Prog 1x6", "Connector_Generic:Conn_01x06",
              "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", "C492405",
              "PZ254V-11-06P", None, "THT; JLCPCB THT service; same part as the MCCAN J2")),
    ("U1", _p("CH343P", "Interface_USB:CH343P",
              "Package_DFN_QFN:WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm", "C2846043", "CH343P",
              "C2858418", "USB CDC-ACM serial; fallback CH9102F (spec 6.5)")),
    ("U2", _p("USBLC6-2SC6", "Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
              "C7519", "USBLC6-2SC6", "C2827654", "ESD on D+/D-")),
    ("U3", _p("AMS1117-3.3", "Regulator_Linear:AMS1117-3.3",
              "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "C6186", "AMS1117-3.3", None,
              "basic; 1 A, current limit + thermal shutdown")),
    ("U4", _p("LM66100", "Power_Management:LM66100DCK", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
              "C2869734", "LM66100DCKR", None, "ideal diode, reverse blocking")),
    ("U5", _p("74LVC2G125", "74xGxx:74LVC2G125", "Package_SO:SSOP-8_2.95x2.8mm_P0.65mm",
              "C206035", "SN74LVC2G125DCTR", None,
              "DTR/RTS buffer; Ioff keeps outputs Hi-Z when unpowered")),
    ("R1", _r("5.1k", "C23186", "0603WAF5101T5E", "CC1")),
    ("R2", _r("5.1k", "C23186", "0603WAF5101T5E", "CC2")),
    ("R3", _r("4.7k", "C23162", "0603WAF4701T5E", "ESP TX -> U1 RXD, back-feed limit")),
    ("R4", _r("470", "C23179", "0603WAF4700T5E", "U1 TXD -> ESP RX")),
    ("R5", _r("270", "C22966", "0603WAF2700T5E", "DTR; 3.34 V / 270 = 12 mA if misplugged")),
    ("R6", _r("270", "C22966", "0603WAF2700T5E", "RTS")),
    ("R7", _r("1k", "C21190", "0603WAF1001T5E", "PWR LED")),
    ("R8", _r("1k", "C21190", "0603WAF1001T5E", "TX LED")),
    ("R9", _r("1k", "C21190", "0603WAF1001T5E", "RX LED")),
    ("D1", _p("PWR yellow-green", "Device:LED", LED0603, "C2289", "KT-0603YG", None,
              "Vf ~2.1 V; pure green (Vf 3.1 V) is too high for a 3.3 V rail")),
    ("D2", _p("TX red", "Device:LED", LED0603, "C2286", "KT-0603R", None, "")),
    ("D3", _p("RX yellow", "Device:LED", LED0603, "C2287", "KT-0603Y", None, "")),
    ("C1", _p("10uF", "Device:C", C0805, "C15850", "CL21A106KAYNNNE", None, "VBUS bulk, U3 in")),
    ("C2", _p("100nF", "Device:C", C0603, "C14663", "CC0603KRX7R9BB104", None, "VBUS at J1")),
    ("C3", _p("22uF", "Device:C", C0805, "C45783", "CL21A226MAQNNNE", None, "U3 out")),
    ("C4", _p("22uF", "Device:C", C0805, "C45783", "CL21A226MAQNNNE", None, "+3V3_OUT bulk")),
    ("C5", _p("22uF", "Device:C", C0805, "C45783", "CL21A226MAQNNNE", None, "+3V3_OUT bulk")),
    ("C6", _p("100nF", "Device:C", C0603, "C14663", "CC0603KRX7R9BB104", None, "U1 VDD5")),
    ("C7", _p("100nF", "Device:C", C0603, "C14663", "CC0603KRX7R9BB104", None, "U1 VIO")),
    ("C8", _p("1uF", "Device:C", C0603, "C15849", "CL10A105KB8NNNC", None, "U1 V3_OUT")),
    ("C9", _p("100nF", "Device:C", C0603, "C14663", "CC0603KRX7R9BB104", None, "U5 VCC")),
])


def _natural(ref):
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2)))


def bom_lines():
    """[(value|footprint, [refs])] with refs in natural order, lines in first-ref order."""
    groups = OrderedDict()
    for ref in sorted(PARTS, key=_natural):
        e = PARTS[ref]
        groups.setdefault("%s|%s" % (e["value"], e["footprint"]), []).append(ref)
    return list(groups.items())
