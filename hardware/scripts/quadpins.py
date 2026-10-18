"""The signal-output quad switch: one place for its pads and application values.

symlib.py builds the symbol from PINS, gen_outputs.py wires it from PINS and the values below,
and check_netlist.py asserts against the same names -- so a pad number is written once.

Source: TI TPS4H160-Q1 datasheet SLVSCV8E (Dec 2015, rev. June 2025), held locally as
hardware/datasheets/tps4h160-q1.pdf.  Version B (current-sense analog output) is the variant
used: it has the CS pin and the SEL/SEH channel select; Version A has four open-drain status
pins instead and no analog sense.  Selection reasoning: hardware/docs/part-selection.md,
"Signal-output quad switch, 2026-10-18".
"""

PART = "TPS4H160BQPWPRQ1"               # orderable, Version B, PWP (HTSSOP-28), p.34 addendum
LIB_ID = "mccan_parts:TPS4H160B_Q1"
# PWP0028V land pattern: exposed pad 2.24-2.94 x 4.92-5.62 mm (p.38 package outline).  The
# closest stock footprint is EP2.85x5.4; re-check it against the p.39 example board layout in
# the layout phase, before any copper is drawn around it.
FOOTPRINT = "Package_SO:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.85x5.4mm"

# Table 5-1 "Pin Functions", pp.4-5, Version B column; Figure 5-2 p.4.
# Our names -> datasheet names: SEL0 = SEL (CS channel-select LOW bit, pin 8), SEL1 = SEH
# (HIGH bit, pin 7), SNS = CS (current-sense output, pin 10).
PINS = {
    "IN1": ["3"],
    "IN2": ["4"],
    "IN3": ["5"],
    "IN4": ["6"],
    "OUT1": ["27", "28"],
    "OUT2": ["25", "26"],
    "OUT3": ["17", "18"],
    "OUT4": ["15", "16"],
    "VS": ["20", "21", "22", "23"],
    "GND": ["1", "12"],
    "DIAG_EN": ["14"],                   # internal pull-down
    "SEL0": ["8"],                       # SEL, internal pull-down
    "SEL1": ["7"],                       # SEH, internal pull-down
    "SNS": ["10"],                       # CS
    "CL": ["11"],                        # adjustable current limit; R(CL) to GND
    "THER": ["13"],                      # low = auto-retry, high = latch off (s.7.3, p.24)
    "FAULT": ["9"],                      # global open-drain fault; left unconnected here
    "EP": ["29"],                        # thermal pad: "connect to device GND or leave floating"
    "OTHER": ["2", "19", "24"],          # NC, no internal connection
}

# ---------------------------------------------------------------- application values
# Logic input.  VIH = 2 V, VIL = 0.8 V; internal pull-down R(logic,pd) 100 k min / 175 k typ / 250 k max
# (s.6.5 p.8).  TI s.7.3.7.5 (p.26) recommends 4.7 k in series with every MCU line at 3.3 V.
#   Rpd || Rint(min) = 47 k || 100 k = 32.0 k
#   VIN(high) = 3.3 x 32.0 / (32.0 + 4.7) = 2.88 V  >=  VIH + 0.5 = 2.5 V
R_IN_SERIES = "4.7k"
R_IN_PULLDOWN = "47k"

# Current limit, one per chip (shared by its four channels).  Eq.4 p.18:
#   R(CL) = VCL(th) x K(CL) / I_CL = 0.8 V x 2500 / 0.5 A = 4.0 k  ->  4.02 k (E96) = 0.498 A
# 0.5 A is 6x the 80 mA steady load and above the indicator's 0.08 A steady current (its inrush
# is unmeasured, spec 9.2), and accuracy is +/-15 % in the 0.5-7 A band.
R_CL = "4.02k"

# Current sense.  K(CS) = 300 (s.6.5 p.8).  Linear full scale at the current limit:
#   R(CS) = VCS x K(CS) / I = 3.0 V x 300 / 0.5 A = 1.8 k
#   80 mA -> 0.48 V;  20 mA (rear *_DRL) -> 0.12 V.
# Eq.3 p.17: R(CS) >= VCS(H,min) / ICS(H,min) = 4.5 V / 15 mA = 300 R  ->  1.8 k passes.
# The FAULT level VCS(H) is 4.5-6.5 V regardless of R(CS); the Schottky clamp to +3V3_ALW in
# gen_outputs.py handles that, not this resistor.  A reading above ~3.0 V therefore means fault.
R_SNS = "1.8k"

# THER pulled to the GATED +5V: latch mode while the board is awake, so the firmware owns retry
# with backoff (spec 6.3); with +5V off in sleep the pin's internal pull-down draws nothing.
R_THER = "10k"

# The typical application (Fig. 8-1, p.28) shows no output capacitor.  VS decoupling is this
# project's rule for VBAT: >= 63 V because of the SMBJ24A's 50.6 V clamp.
C_OUT = None
C_VS = "100nF 100V"
