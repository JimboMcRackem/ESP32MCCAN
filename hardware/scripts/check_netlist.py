"""Netlist assertions: the test suite for the phase-A board schematic.

Encodes the electrical intent of decisions D1-D6 (plan 2026-10-18-board-schematic-phase-a) as
checks over the exported KiCad netlist.  Sheets are regenerated until every group passes.

    python check_netlist.py [--only GROUP ...] [NETLIST]

NETLIST defaults to ../output/netlist.net.  Prints "PASS <group>" or each failure; exit 0 only
when every selected check passes.

Conventions
  * Net names are stripped of their sheet/root prefix (/mcu_can/CAN_RXD -> CAN_RXD).  Two
    netlist nets that collapse to one bare name are reported (group `deleted`), not hidden.
  * A "resistor from NET to X" is a non-DNP part whose ref starts with R, with one pin on NET
    and the other on X.  A DNP resistor is not a pull-down.
  * Diode pins are told apart by pinfunction (K_1 / A_2); FET pins by G / S / D.
  * Chip pad numbers and application values come from quadpins; nothing is re-typed here.
"""
import argparse
import os
import re
import sys
from collections import defaultdict, namedtuple

import quadpins
from quadpins import PINS

Part = namedtuple("Part", "value footprint dnp")

SUPPLIES = ("+3V3_ALW", "+5V", "VBAT", "VBAT_B")


class Netlist:
    def __init__(self):
        self.nets = {}                    # bare name -> {"U5.7", ...}
        self.parts = {}                   # ref -> Part
        self.pin_net = {}                 # (ref, pin) -> bare net name
        self.pinfunc = {}                 # (ref, pin) -> pinfunction string ("" if none)
        self.collisions = []              # (bare, [raw names])
        self.part_pins = defaultdict(dict)  # ref -> {pin: bare net name}

    def net_of(self, ref, pin):
        return self.pin_net.get((ref, pin))

    def pins_of(self, ref, func_prefix):
        """Pin numbers of `ref` whose pinfunction (before the trailing _<pad>) starts with prefix."""
        out = []
        for (r, p), f in self.pinfunc.items():
            if r == ref and _func_name(f).startswith(func_prefix):
                out.append(p)
        return sorted(out, key=lambda x: (len(x), x))


def _func_name(f):
    return re.sub(r"_[^_]*$", "", f) if "_" in f else f


def bare(name):
    return name.rsplit("/", 1)[-1] if name.startswith("/") else name


def load(path):
    text = open(path, encoding="utf-8").read()
    nl = Netlist()
    c0, c1 = text.index("(components"), text.index("(libparts")
    for block in re.split(r"\n\t\t\(comp\b", text[c0:c1])[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', block).group(1)
        value = re.search(r'\(value "([^"]*)"\)', block)
        fp = re.search(r'\(footprint "([^"]*)"\)', block)
        dnp = re.search(r'\(property\s*\(name "dnp"\)', block) is not None
        nl.parts[ref] = Part(value.group(1) if value else "", fp.group(1) if fp else "", dnp)
    raw = defaultdict(list)
    n0 = text.index("\n\t(nets")
    for block in re.split(r"\n\t\t\(net\b", text[n0:])[1:]:
        rawname = re.search(r'\(name "([^"]*)"\)', block).group(1)
        b = bare(rawname)
        raw[b].append(rawname)
        members = nl.nets.setdefault(b, set())
        for m in re.finditer(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)(?:\s*\(pinfunction "([^"]*)"\))?',
                             block):
            ref, pin, func = m.group(1), m.group(2), m.group(3) or ""
            members.add("%s.%s" % (ref, pin))
            nl.pin_net[(ref, pin)] = b
            nl.pinfunc[(ref, pin)] = func
            nl.part_pins[ref][pin] = b
    nl.collisions = sorted((b, r) for b, r in raw.items() if len(r) > 1)
    return nl


# ------------------------------------------------------------------ helpers
def norm(v):
    return re.sub(r"[\s_]", "", v).lower()


def _tokens(v):
    """Whitespace tokens, lower-cased; a capacitance token loses its trailing F (100nF == 100n)."""
    out = []
    for t in v.lower().split():
        if re.fullmatch(r"\d+(\.\d+)?[pnumµ]f", t):
            t = t[:-1]
        out.append(t)
    return out


def value_is(nl, ref, want):
    """Exact match of the leading value token, and of any further tokens `want` names.

    "47k" does not match "147k"; want "100nF" matches "100nF 100V" (extra voltage token allowed
    when want omits it); want "100nF 100V" requires that voltage token exactly.
    """
    if ref not in nl.parts:
        return False
    have, need = _tokens(nl.parts[ref].value), _tokens(want)
    return bool(need) and have[:len(need)] == need


def resistors_between(nl, net, other, value=None):
    """Refs of live resistors with one pin on `net` and the other on `other`."""
    out = []
    for ref, pins in nl.part_pins.items():
        if not re.fullmatch(r"R\d+", ref) or nl.parts[ref].dnp or len(pins) != 2:
            continue
        a, b = pins.values()
        if {a, b} == {net, other} and a != b:
            if value is None or value_is(nl, ref, value):
                out.append(ref)
    return sorted(out)


def resistors_on(nl, net):
    """[(ref, other-net)] for live resistors with exactly one pin on `net`."""
    out = []
    for ref, pins in nl.part_pins.items():
        if not re.fullmatch(r"R\d+", ref) or nl.parts[ref].dnp or len(pins) != 2:
            continue
        a, b = pins.values()
        if a == net and b != net:
            out.append((ref, b))
        elif b == net and a != net:
            out.append((ref, a))
    return sorted(out)


def members(nl, net):
    return nl.nets.get(net, set())


def is_open(nl, ref, pin):
    n = nl.net_of(ref, pin)
    return n is None or n.startswith("unconnected-")


def has_part(nl, ref):
    return ref in nl.parts


def expect_pin(nl, ref, pin, net, label=""):
    """Failure list for 'ref.pin must be on net'."""
    if not has_part(nl, ref):
        return ["%s.%s should be on %s%s: part %s is not in the netlist" % (ref, pin, net, label, ref)]
    got = nl.net_of(ref, pin)
    if got != net:
        return ["%s.%s should be on %s%s, found %s" % (ref, pin, net, label, got)]
    return []


# ------------------------------------------------------------------ data from the plan
CHIPS = {  # D1
    "U11": ("A", ["FL_DRL", "FL_IND", "RL_DRL", "RL_IND"]),
    "U12": ("B", ["FR_DRL", "FR_IND", "RR_DRL", "RR_IND"]),
    "U13": ("C", ["RL_BRK", "RR_BRK", None, None]),
}

MCU_PADS = {  # D2: bare net -> U5 pad
    "OUT_FL_DRL": "10", "OUT_FL_IND": "11", "OUT_FR_DRL": "8", "OUT_FR_IND": "9",
    "OUT_RL_DRL": "12", "OUT_RL_IND": "27", "OUT_RL_BRK": "28", "OUT_RR_DRL": "30",
    "OUT_RR_IND": "31", "OUT_RR_BRK": "33", "OUT_AUX_L": "36", "OUT_AUX_R": "37",
    "EN_5V": "26", "LED_STAT": "16", "CAN_STB": "13", "CAN_RXD": "7",
    "DIAG_EN": "24", "DIAG_SEL0": "29", "DIAG_SEL1": "23",
    "SNS_A": "6", "SNS_B": "4", "SNS_C": "5", "IO12_STRAP": "14",
    "BOOT_N": "25", "EN_MCU": "3", "UART_RX": "34", "UART_TX": "35",
}

FEED_B = {  # D6: ref -> (value token, {role: net})
    "R108": ("100k", {"1|2": ("GATE_B", "GND_B")}),
    "C66": ("100nF", {"1|2": ("VBAT_B", "GND_B")}),
}

HARNESS = {  # D5: ref -> (footprint, [net per pin 1..n])
    "J1": ("SolderWire-1.5sqmm_1x02_P6mm_D1.7mm_OD3mm_Relief", ["FEED_P", "GND_IN"]),
    "J9": ("SolderWire-1.5sqmm_1x02_P6mm_D1.7mm_OD3mm_Relief", ["FEED_B_P", "GND_B"]),
    "J3": ("SolderWire-0.5sqmm_1x05_P4.6mm_D0.9mm_OD2.1mm_Relief",
           ["FL_DRL", "FL_IND", "FR_DRL", "FR_IND", "GND"]),
    "J4": ("SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief",
           ["RL_DRL", "RL_IND", "RL_BRK", "GND"]),
    "J5": ("SolderWire-0.5sqmm_1x03_P4.6mm_D0.9mm_OD2.1mm_Relief",
           ["RR_DRL", "RR_IND", "RR_BRK"]),
}


# ------------------------------------------------------------------ group: deleted
def chk_net_name_collisions(nl):
    return ["net name collision: %s is the bare name of %s" % (b, ", ".join(r)) for b, r in nl.collisions]


def chk_deleted_parts(nl):
    gone = ["LM51571-Q1", "DML3017LDC", "PCA9685PW/Q900", "ADG706", "NX5020UNBKS",
            "BTS7008-2EPA", "1206L050/24"]
    return ["deleted part still present: %s value %s" % (ref, p.value)
            for ref, p in sorted(nl.parts.items()) if p.value in gone]


def chk_deleted_nets(nl):
    gone = ["+24V", "+3V3_SW", "EN_BOOST", "EN_3V3SW", "EN_DIAG", "IGN_IN", "IGN_SENSE",
            "I2C_SDA", "I2C_SCL", "MUX_S0", "MUX_S1", "MUX_S2", "MUX_S3", "RGB_ISNS",
            "ISNS_DEN", "PWM_DEN_A", "PWM_DEN_B", "DEN_DSEL"]
    return ["deleted net still present: %s" % n for n in gone if n in nl.nets]


def chk_deleted_refs(nl):
    return ["deleted ref still present: %s (value %s)" % (r, nl.parts[r].value)
            for r in ("R23", "J6", "J7") if r in nl.parts]


# ------------------------------------------------------------------ group: feed_b
def chk_feed_b_nets(nl):
    f = []
    for n in ("VBAT", "VBAT_B", "FEED_B_P", "GATE_B", "GND_B"):
        if n not in nl.nets:
            f.append("net %s does not exist" % n)
    return f


def chk_feed_b_no_bridge(nl):
    f = []
    for ref, pins in sorted(nl.part_pins.items()):
        nets = set(pins.values())
        if "VBAT" in nets and "VBAT_B" in nets:
            f.append("%s has pins on both VBAT and VBAT_B (re-merges the two feeds)" % ref)
    return f


def chk_q13(nl):
    f = []
    if not has_part(nl, "Q13"):
        return ["Q13 (SQJ461EP) is not in the netlist"]
    if not value_is(nl, "Q13", "SQJ461EP"):
        f.append("Q13 value is %r, want SQJ461EP" % nl.parts["Q13"].value)
    for role, net in (("D", "FEED_B_P"), ("S", "VBAT_B"), ("G", "GATE_B")):
        pins = nl.pins_of("Q13", role)
        if not pins:
            f.append("Q13 has no %s pin (pinfunction)" % role)
        for p in pins:
            if nl.net_of("Q13", p) != net:
                f.append("Q13.%s (%s) should be on %s, found %s" % (p, role, net, nl.net_of("Q13", p)))
    return f


def _diode(nl, ref, token, k_net, a_net):
    if not has_part(nl, ref):
        return ["%s (%s) is not in the netlist" % (ref, token)]
    f = []
    if not value_is(nl, ref, token):
        f.append("%s value is %r, want %s" % (ref, nl.parts[ref].value, token))
    for role, net in (("K", k_net), ("A", a_net)):
        pins = nl.pins_of(ref, role)
        if not pins:
            f.append("%s has no %s pin (pinfunction)" % (ref, role))
        for p in pins:
            if nl.net_of(ref, p) != net:
                f.append("%s.%s (%s) should be on %s, found %s"
                         % (ref, p, role, net, nl.net_of(ref, p)))
    return f


def chk_gate_network(nl):
    f = []
    if not has_part(nl, "R108"):
        f.append("R108 (100k GATE_B-GND_B) is not in the netlist")
    else:
        if not value_is(nl, "R108", "100k"):
            f.append("R108 value is %r, want 100k" % nl.parts["R108"].value)
        if not resistors_between(nl, "GATE_B", "GND_B"):
            f.append("no resistor between GATE_B and GND_B")
        elif "R108" not in resistors_between(nl, "GATE_B", "GND_B"):
            f.append("R108 is not between GATE_B and GND_B")
    return f + _diode(nl, "D24", "MMSZ5245B", "VBAT_B", "GATE_B")


def chk_tvs(nl):
    return _diode(nl, "D25", "SMBJ24A", "VBAT_B", "GND_B")


def chk_c66(nl):
    if not has_part(nl, "C66"):
        return ["C66 (100 nF VBAT_B-GND_B) is not in the netlist"]
    f = []
    if not value_is(nl, "C66", "100nF"):
        f.append("C66 value is %r, want 100nF" % nl.parts["C66"].value)
    got = set(nl.part_pins["C66"].values())
    if got != {"VBAT_B", "GND_B"}:
        f.append("C66 should sit between VBAT_B and GND_B, found %s" % sorted(got))
    return f


def chk_nt1(nl):
    if not has_part(nl, "NT1"):
        return ["NT1 (NetTie GND_B-GND) is not in the netlist"]
    got = set(nl.part_pins["NT1"].values())
    f = []
    if got != {"GND_B", "GND"}:
        f.append("NT1 should tie GND_B to GND, found nets %s" % sorted(got))
    if "NetTie" not in nl.parts["NT1"].footprint:
        f.append("NT1 footprint is %r, want a NetTie footprint" % nl.parts["NT1"].footprint)
    return f


def chk_gnd_b_members(nl):
    want = {"J9", "R108", "D25", "C66", "NT1"}
    if "GND_B" not in nl.nets:
        return ["net GND_B does not exist"]
    got = {m.split(".")[0] for m in nl.nets["GND_B"]}
    f = []
    if got != want:
        f.append("GND_B should hold only %s, found %s" % (sorted(want), sorted(nl.nets["GND_B"])))
    if "J9.2" not in nl.nets["GND_B"]:
        f.append("J9.2 is not on GND_B")
    return f


# ------------------------------------------------------------------ group: rails
def chk_en_5v(nl):
    if "EN_5V" not in nl.nets:
        return ["net EN_5V does not exist (U5.26 + buck EN/UVLO + pull-down to GND)"]
    f = []
    m = nl.nets["EN_5V"]
    if "U5.26" not in m:
        f.append("EN_5V does not contain U5.26")
    en = [x for x in m
          if _func_name(nl.pinfunc.get(tuple(x.split(".", 1)), "")).startswith("EN/UVLO")]
    if not en:
        f.append("EN_5V does not reach a buck EN/UVLO pin")
    if not resistors_between(nl, "EN_5V", "GND"):
        f.append("EN_5V has no resistor to GND (enable nets carry an external pull-down)")
    return f


def chk_5v_reaches_u6(nl):
    pins = nl.pins_of("U6", "VCC") if has_part(nl, "U6") else []
    if not pins:
        return ["U6 has no VCC pin"]
    return [] if all(nl.net_of("U6", p) == "+5V" for p in pins) else \
        ["U6 VCC is on %s, want +5V" % [nl.net_of("U6", p) for p in pins]]


# ------------------------------------------------------------------ group: mcu
def chk_mcu_rows(nl):
    f = []
    for net, pad in sorted(MCU_PADS.items()):
        if net not in nl.nets:
            f.append("net %s does not exist (want U5.%s)" % (net, pad))
        elif "U5.%s" % pad not in nl.nets[net]:
            others = sorted(x for x in nl.nets[net] if x.startswith("U5."))
            f.append("U5.%s is not on %s (net holds U5 pins %s; U5.%s is on %s)"
                     % (pad, net, others, pad, nl.net_of("U5", pad)))
    return f


def chk_io12_strap(nl):
    if not resistors_between(nl, "IO12_STRAP", "GND"):
        return ["IO12_STRAP has no resistor to GND"]
    return []


def chk_txd_listen_only(nl):
    f = []
    n = nl.net_of("U6", "1") if has_part(nl, "U6") else None
    if n is None:
        return ["U6.1 (TXD) is unconnected or U6 missing"]
    u5 = sorted(x for x in members(nl, n) if x.startswith("U5."))
    if u5:
        f.append("U6.1 (TXD) net %s reaches U5 pins %s (listen-only must be hardware-enforced)"
                 % (n, u5))
    if not resistors_between(nl, n, "+3V3_ALW"):
        f.append("U6.1 (TXD) net %s has no resistor to +3V3_ALW (R24)" % n)
    return f


def chk_can_stb_pullup(nl):
    if not resistors_between(nl, "CAN_STB", "+3V3_ALW"):
        return ["CAN_STB has no resistor to +3V3_ALW (R25, standby by default)"]
    return []


# ------------------------------------------------------------------ group: outputs
def _chip_cells():
    for ref, (sns, fns) in CHIPS.items():
        for i, fn in enumerate(fns, 1):
            yield ref, sns, i, fn


def _pulldown(nl, net, what):
    if not resistors_between(nl, net, "GND", quadpins.R_IN_PULLDOWN):
        return ["%s: net %s has no %s resistor to GND" % (what, net, quadpins.R_IN_PULLDOWN)]
    return []


def chk_chips_present(nl):
    return ["%s (TPS4H160 quad) is not in the netlist" % r for r in CHIPS if not has_part(nl, r)]


def chk_signal_channels(nl):
    f = []
    for ref, sns, ch, fn in _chip_cells():
        if not has_part(nl, ref):
            continue
        in_pin = PINS["IN%d" % ch][0]
        in_net = nl.net_of(ref, in_pin)
        tag = "%s IN%d (pad %s)" % (ref, ch, in_pin)
        if fn is None:                                   # spare channel
            if in_net is None or in_net.startswith("unconnected-"):
                f.append("%s: spare input is floating, needs a %s pull-down" % (tag, quadpins.R_IN_PULLDOWN))
            else:
                f += _pulldown(nl, in_net, tag + " (spare)")
            for p in PINS["OUT%d" % ch]:
                if not is_open(nl, ref, p):
                    f.append("%s.%s (OUT%d, spare) should be unconnected, found %s"
                             % (ref, p, ch, nl.net_of(ref, p)))
            continue
        out = "OUT_" + fn
        pad = MCU_PADS[out]
        m = members(nl, out)
        if not m:
            f.append("%s: net %s does not exist" % (tag, out))
        else:
            rs = [x for x in m if re.fullmatch(r"R\d+", x.split(".")[0])]
            others = sorted(x for x in m if x != "U5." + pad and x not in rs)
            if "U5." + pad not in m:
                f.append("%s should hold U5.%s" % (out, pad))
            if len(rs) != 1:
                f.append("%s should hold exactly one series resistor, found %s" % (out, sorted(rs)))
            if others:
                f.append("%s holds %s besides U5.%s and the series resistor" % (out, others, pad))
            for x in rs:
                r = x.split(".")[0]
                if not value_is(nl, r, quadpins.R_IN_SERIES):
                    f.append("%s series resistor %s is %r, want %s"
                             % (out, r, nl.parts[r].value, quadpins.R_IN_SERIES))
            far = {o for r, o in resistors_on(nl, out)}
            if in_net is None:
                f.append("%s is unconnected, want a net with the %s series resistor" % (tag, out))
            elif in_net not in far:
                f.append("%s is on %s, which is not the far side of the %s series resistor (%s)"
                         % (tag, in_net, out, sorted(far)))
            else:
                f += _pulldown(nl, in_net, tag)
        outs = PINS["OUT%d" % ch]
        for p in outs:
            if nl.net_of(ref, p) != fn:
                f.append("%s.%s (OUT%d) should be on %s, found %s" % (ref, p, ch, fn, nl.net_of(ref, p)))
    return f


def chk_aux_outputs(nl):
    f = []
    for net in ("OUT_AUX_L", "OUT_AUX_R"):
        pad = MCU_PADS[net]
        m = members(nl, net)
        if not m:
            f.append("net %s does not exist" % net)
            continue
        rs = sorted(x for x in m if re.fullmatch(r"R\d+", x.split(".")[0]))
        others = sorted(x for x in m if x != "U5." + pad and x not in rs)
        if "U5." + pad not in m:
            f.append("%s should hold U5.%s" % (net, pad))
        if others:
            f.append("%s holds %s besides U5.%s and its pull-down" % (net, others, pad))
        if len(rs) != 1:
            f.append("%s should hold exactly one resistor (the pull-down), found %s" % (net, rs))
        elif nl.parts[rs[0].split(".")[0]].dnp or not resistors_between(nl, net, "GND"):
            f.append("%s: resistor %s is not a live pull-down to GND" % (net, rs[0]))
    return f


def chk_sense(nl):
    f = []
    for ref, (sns, _) in CHIPS.items():
        if not has_part(nl, ref):
            continue
        pad = PINS["SNS"][0]
        n = nl.net_of(ref, pad)
        tag = "%s SNS (pad %s)" % (ref, pad)
        if n is None or n.startswith("unconnected-"):
            f.append("%s is unconnected" % tag)
            continue
        if not resistors_between(nl, n, "GND", quadpins.R_SNS):
            f.append("%s net %s has no %s resistor to GND" % (tag, n, quadpins.R_SNS))
        series = [r for r, o in resistors_on(nl, n) if o == "SNS_" + sns]
        if not series:
            f.append("%s net %s has no series resistor to SNS_%s" % (tag, n, sns))
        # Schottky clamp on SNS_x only: anode on SNS_x (ADC side of the series resistor, which
        # limits the clamp current from the 4.5-6.5 V fault level), cathode on +3V3_ALW.
        if not _clamp(nl, "SNS_" + sns):
            f.append("%s: no Schottky (anode SNS_%s, cathode +3V3_ALW) on SNS_%s" % (tag, sns, sns))
    return f


def _clamp(nl, net):
    for ref, pins in nl.part_pins.items():
        if not ref.startswith("D"):
            continue
        k = [p for p in pins if _func_name(nl.pinfunc[(ref, p)]) == "K"]
        a = [p for p in pins if _func_name(nl.pinfunc[(ref, p)]) == "A"]
        if k and a and all(pins[p] == "+3V3_ALW" for p in k) and all(pins[p] == net for p in a):
            return True
    return False


def chk_chip_pins(nl):
    f = []
    for ref in CHIPS:
        if not has_part(nl, ref):
            continue
        n = nl.net_of(ref, PINS["CL"][0])
        if n is None or not resistors_between(nl, n, "GND", quadpins.R_CL):
            f.append("%s CL (pad %s) net %s has no %s resistor to GND"
                     % (ref, PINS["CL"][0], n, quadpins.R_CL))
        n = nl.net_of(ref, PINS["THER"][0])
        if n is None or not resistors_between(nl, n, "+5V", quadpins.R_THER):
            f.append("%s THER (pad %s) net %s has no %s resistor to +5V"
                     % (ref, PINS["THER"][0], n, quadpins.R_THER))
        if not is_open(nl, ref, PINS["FAULT"][0]):
            f.append("%s FAULT (pad %s) should be unconnected, found %s"
                     % (ref, PINS["FAULT"][0], nl.net_of(ref, PINS["FAULT"][0])))
        f += expect_pin(nl, ref, PINS["EP"][0], "GND", " (EP)")
        for p in PINS["VS"]:
            f += expect_pin(nl, ref, p, "VBAT", " (VS)")
        for p in PINS["GND"]:
            f += expect_pin(nl, ref, p, "GND", " (GND)")
    return f


def chk_diag(nl):
    """R1: MCU-side DIAG_* = U5 pad + 4.7k series; chip-side DIAG_*_Q reaches all three chips."""
    f = []
    for mcu, chip_pin in (("DIAG_EN", "DIAG_EN"), ("DIAG_SEL0", "SEL0"), ("DIAG_SEL1", "SEL1")):
        q = mcu + "_Q"
        pad = MCU_PADS[mcu]
        m = members(nl, mcu)
        if not m:
            f.append("net %s does not exist" % mcu)
        else:
            rs = [x for x in m if re.fullmatch(r"R\d+", x.split(".")[0])]
            others = sorted(x for x in m if x != "U5." + pad and x not in rs)
            if others:
                f.append("%s holds %s besides U5.%s and its series resistor" % (mcu, others, pad))
            if len(rs) != 1:
                f.append("%s should hold exactly one series resistor, found %s" % (mcu, sorted(rs)))
            far = {o for r, o in resistors_on(nl, mcu)}
            if q not in far:
                f.append("%s series resistor does not lead to %s (leads to %s)" % (mcu, q, sorted(far)))
            for x in rs:
                r = x.split(".")[0]
                if not value_is(nl, r, quadpins.R_IN_SERIES):
                    f.append("%s series resistor %s is %r, want %s"
                             % (mcu, r, nl.parts[r].value, quadpins.R_IN_SERIES))
        qm = members(nl, q)
        if not qm:
            f.append("net %s does not exist" % q)
            continue
        for ref in CHIPS:
            if "%s.%s" % (ref, PINS[chip_pin][0]) not in qm:
                f.append("%s does not reach %s.%s" % (q, ref, PINS[chip_pin][0]))
        u5 = sorted(x for x in qm if x.startswith("U5."))
        if u5:
            f.append("%s reaches U5 directly (%s); only through the series resistor" % (q, u5))
        pulls = [(r, o) for r, o in resistors_on(nl, q) if o != mcu]
        if q == "DIAG_EN_Q":
            if not resistors_between(nl, q, "GND", "10k"):
                f.append("DIAG_EN_Q has no 10k pull-down to GND")
        elif pulls:
            f.append("%s should have no pull resistor, found %s" % (q, pulls))
    return f


# ------------------------------------------------------------------ group: harness
def chk_harness(nl):
    f = []
    for ref, (fp, nets) in sorted(HARNESS.items()):
        if not has_part(nl, ref):
            f.append("%s is not in the netlist (want footprint %s)" % (ref, fp))
            continue
        if not nl.parts[ref].footprint.endswith(fp):
            f.append("%s footprint is %r, want ...%s" % (ref, nl.parts[ref].footprint, fp))
        npins = len(nl.part_pins[ref])
        if npins != len(nets):
            f.append("%s has %d pins, want %d" % (ref, npins, len(nets)))
        for i, net in enumerate(nets, 1):
            f += expect_pin(nl, ref, str(i), net)
    return f


# ------------------------------------------------------------------ group: boot_safety
def chk_in_nets(nl):
    f = []
    seen = 0
    for ref in CHIPS:
        if not has_part(nl, ref):
            f.append("%s is not in the netlist: its IN nets cannot be checked" % ref)
            continue
        for ch in range(1, 5):
            pin = PINS["IN%d" % ch][0]
            n = nl.net_of(ref, pin)
            tag = "%s IN%d (pad %s)" % (ref, ch, pin)
            seen += 1
            if n is None or n.startswith("unconnected-"):
                f.append("%s floats (no pull-down to GND)" % tag)
                continue
            if n in SUPPLIES:
                f.append("%s is directly on supply %s" % (tag, n))
            if not resistors_between(nl, n, "GND"):
                f.append("%s net %s has no resistor to GND" % (tag, n))
            for r, o in resistors_on(nl, n):
                if o in SUPPLIES:
                    f.append("%s net %s has pull-up %s to %s" % (tag, n, r, o))
    return f


def chk_out_strapping(nl):
    bad = {"13": "GPIO14", "14": "GPIO12", "23": "GPIO15", "24": "GPIO2", "25": "GPIO0", "29": "GPIO5"}
    f = []
    for n, m in sorted(nl.nets.items()):
        if n.startswith("OUT_"):
            for pad, gpio in sorted(bad.items()):
                if "U5." + pad in m:
                    f.append("%s is on U5.%s (%s, strapping/boot-toggling): no lamp output there"
                             % (n, pad, gpio))
    return f


GROUPS = {
    "deleted": [chk_deleted_parts, chk_deleted_nets, chk_deleted_refs],
    "feed_b": [chk_feed_b_nets, chk_feed_b_no_bridge, chk_q13, chk_gate_network, chk_tvs,
               chk_c66, chk_nt1, chk_gnd_b_members],
    "rails": [chk_en_5v, chk_5v_reaches_u6],
    "mcu": [chk_mcu_rows, chk_io12_strap, chk_txd_listen_only, chk_can_stb_pullup],
    "outputs": [chk_chips_present, chk_signal_channels, chk_aux_outputs, chk_sense,
                chk_chip_pins, chk_diag],
    "harness": [chk_harness],
    "boot_safety": [chk_in_nets, chk_out_strapping],
}


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="GROUP", help="run only these groups")
    ap.add_argument("netlist", nargs="?", default=os.path.join(here, "..", "output", "netlist.net"))
    args = ap.parse_args(argv)
    only = args.only or []
    path = args.netlist
    # `--only a b FILE` swallows FILE into --only; recover it.
    if only and only[-1] not in GROUPS and os.path.isfile(only[-1]):
        path = only.pop()
    unknown = [g for g in only if g not in GROUPS]
    if unknown:
        ap.error("unknown group(s) %s; choose from %s" % (unknown, list(GROUPS)))
    nl = load(path)
    failed = False
    coll = chk_net_name_collisions(nl)      # always checked, whatever --only selects
    if coll:
        failed = True
        print("FAIL net_names (%d)" % len(coll))
        for x in coll:
            print("  " + x)
    for group, checks in GROUPS.items():
        if only and group not in only:
            continue
        fails = [x for c in checks for x in c(nl)]
        if fails:
            failed = True
            print("FAIL %s (%d)" % (group, len(fails)))
            for x in fails:
                print("  " + x)
        else:
            print("PASS %s" % group)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
