# -*- coding: utf-8 -*-
"""Sheet notes for power_input.kicad_sch.

Recovered 2026-09-14 from the committed sheet, after the original scratchpad module was
lost to a filename collision with the rails notes module.  Fidelity was proved by
regenerating the sheet byte-for-byte against the committed copy before any change was made.

Rewritten 2026-09-20 for the eFuse (spec 4.2).  The sheet moved from A4 to A3 and the input
filter shifted 73.66 mm right, so every note box had to move as well: the old positions sat
on top of the new U10 block or the relocated filter.  Boxes are now STACKED AUTOMATICALLY
in two columns by _box() below -- add or edit text without recomputing any coordinates.

Deleted in that rewrite: the "P-CHANNEL MOSFET ORIENTATION (Q1)" box.  Q1 no longer exists.
"""
NOTE_FONT = 1.0

# ---------------------------------------------------------------- automatic stacking
# KiCad's text_box is a fixed rectangle and the text flows inside it, so the height only
# has to be big enough.  Measured against the boxes this file used to carry by hand,
# 1.75 mm per line plus the two 0.9525 mm margins is a comfortable fit at font 1.0.
GRID = 1.27
_LINE = 1.75
_PAD = 2.54

_COLS = {
    # name: (x, y_start, width)
    "right": (240.03, 11.43, 171.45),   # on grid: 189 and 135 pitches; 240.03 + 171.45 = 411.48 < 420
    "below": (20.32, 165.10, 209.55),   # on grid: 16, 130 and 165 pitches; the schematic ends at y = 157
}
_next_y = {k: v[1] for k, v in _COLS.items()}

TEXTBOXES = []


def _box(col, txt):
    x, _y0, w = _COLS[col]
    n = txt.count("\n") + 1
    h = n * _LINE + _PAD
    h = GRID * (int(h / GRID) + 1)
    y = _next_y[col]
    TEXTBOXES.append((txt, x, y, w, h))
    _next_y[col] = y + h + 2 * GRID


# ---------------------------------------------------------------- the eFuse
_box("right", """THE eFUSE (U10) -- WHAT REPLACED F1, Q1, D1 AND R1
This front end used to be a 10 A blade fuse, a P-channel reverse-polarity FET, a gate Zener and a 1M gate
pull-down.  Spec 4.2 replaced all four with ONE element: U10, an LTC4380-2 surge stopper driving a
back-to-back pair Q10/Q11.  It does three jobs the old arrangement did not do together --
  * REVERSE POLARITY, by the opposed body diodes of Q10/Q11 (see the common-drain note below).
  * OVERCURRENT, as an active current limit across R100 (5.6 mOhm), with a C62-timed fault trip and the
    -2 suffix's AUTO-RETRY at roughly 0.1-0.2% duty -- about one retry every 1.5-3 s.  Auto-retry is
    required, not preferred: the MCU is powered downstream of this stage and could never clear a latch.
  * OVERVOLTAGE, by holding VBAT_PROT near 29.5 V through a linear clamp.  That is what the internal
    31.5 V gate clamp gives with SEL tied to GND_IN.

The reference circuit is the datasheet's FIGURE 7 (12 V overcurrent-protected high-side switch), NOT
Figure 5.  Figure 7 is 12 V in, back-to-back FETs, an LTC4380-2, 80 VDC max against our 50.6 V worst
case.  Only R100 (R_SNS), R101 (R_DRN) and C62 (C_TMR) are rescaled -- Figure 7 is a 2 A design.

TWO DELIBERATE DEPARTURES FROM FIGURE 7, both checked:
  * R103/C64 are 33 Ohm / 47 nF, where Figure 7 draws 150 Ohm / 0.1 uF.  33 Ohm / 47 nF is the
    datasheet's own stated MINIMUM in PIN FUNCTIONS, and it is chosen because a larger C64 lengthens the
    output ramp: 0.1 uF pushes the fault timeout past 10 ms, off the end of the SOA curve that was
    checked.  Do not fit a larger C64 without re-checking the FETs' safe operating area.
  * ON is left open on its internal 1 MOhm pull-up and FLT is not routed to the MCU.  Both carry
    no-connect flags so ERC stays clean; both are available if a later revision wants them.

C65 IS NOT OPTIONAL.  PIN FUNCTIONS requires a minimum of 22 uF bypassing OUT "as close to the pin as
possible".  Nothing else on this sheet satisfies it -- C1 is 100 nF and sits behind the choke, C3 sits
behind L1 as well.  Layout must keep C65 next to U10 pin 5, not merely on the same net.

REFERENCE DESIGNATORS: spec 4.2 names these parts R88-R95, C49-C52 and D22-D24.  Those are taken --
R88-R99 and C49-C61 are the RGB output snubbers on the outputs sheet.  The mapping actually built is
R88->R100 .. R95->R107, C49->C62 .. C52->C65, and D22->D21 / D23->D22 / D24->D23.""")

_box("right", """THE PASS PAIR IS COMMON DRAIN.  DO NOT "SIMPLIFY" IT.
Q10 pin 3 (DRAIN) and Q11 pin 3 (DRAIN) meet at MID.  Q10 pin 2 (SOURCE) goes to FEED_P; Q11 pin 2
(SOURCE) goes to R100 and on to VBAT_PROT.  Sources OUTWARD, drains tied in the middle.

That is what makes the body diodes OPPOSE each other, and it is the entire reverse-polarity block --
forward current reaches the load through Q11's channel, reverse current is stopped by Q10's diode facing
the wrong way, and that holds with the part unpowered.

Wired common SOURCE instead, the board works normally, passes ERC, passes DRC, passes the pad count,
and has no reverse-polarity protection at all.  An earlier draft of spec 4.2 instructed exactly that.
The tell that it is wrong is the gate network: under common source both gates would sit on one node and
Q12/D22/D23/R105-R107 would have nothing to do.  They exist because Q10's gate must be referenced to
FEED_P while U10's GATE pin is referenced to OUT.

HOW Q10'S GATE IS DRIVEN.  U10's GATE sits at about OUT + 11.5 V.  R107 (240k) and D22 carry that across
to Q10's gate, landing it near FEED_P + 10.8 V -- enough to enhance a FET whose source is at the input.
R105 (240k from FEED_P) biases Q12's base through R106/D23; under reverse polarity GND_IN rises above the
feed, D23 conducts, Q12 turns on and clamps Q10's gate to its own source, holding Q10 hard off.
D23 stands off up to 50.6 V in normal operation, which is why it is a 75 V part and not a Schottky.

AFTER ANY CHANGE HERE, READ THE NETLIST BY HAND.  gen_power_input.py prints the expected coordinate for
every pin of every net; spec 4.2 makes that check a formal acceptance criterion.  This is the error class
that has got through every automated check on this board three times now -- the CM choke's pin numbering
in Task 7, the RGB FET clamp path in review finding F6, and the first draft of this very paragraph.""")

# ---------------------------------------------------------------- symbols and values
_box("right", """SYMBOL AND PIN-NUMBER NOTES (this sheet was authored as text, not drawn in the GUI)
Q10 and Q11 use Transistor_FET:Q_NMOS_GSD, which numbers the pins 1 = G, 2 = S, 3 = D.  Device:Q_NMOS
also exists but numbers its pins with the LETTERS D / G / S, which map to no stock footprint.  The
Infineon HSOF-8 footprint numbers only three pads, 1/2/3, which is what lets the three-pin symbol map
onto an eight-lead package.
Q12 uses Transistor_BJT:Q_NPN_BEC -- 1 = B, 2 = E, 3 = C -- matching a SOT-23 MMBT3904 pinout.
U10 uses mccan_parts:LTC4380, built by symlib.py from the datasheet's PIN CONFIGURATION: 1 DRN, 2 VCC,
3 GATE, 4 SNS, 5 OUT, 6 SEL, 7 FLT, 8 GND, 9 ON, 10 TMR.  That is the MS (MSOP-10) package, which has NO
exposed pad.  The DD package does, numbered 11; ordering DD would leave the pad unlanded.
Most of U10's pins are typed PASSIVE on purpose.  The part sits on GND_IN, which by design carries no
power symbol, so a power_in GND or VCC pin would make ERC demand a driver that must never exist.
L2 uses mccan_parts:CM_CHOKE_4T, not Device:L_Coupled.  Winding A is pins 1-4 and carries the FEED
(VBAT_PROT -> VBAT_F); winding B is pins 2-3 and carries the RETURN (GND_IN -> GND).  L_Coupled numbers
the same part 1-2 / 3-4, and using it here shorted VBAT_PROT to GND through a winding.
In the KiCad 10 Device library a diode's pin 1 is the CATHODE (K) and pin 2 is the ANODE (A), and the
unrotated symbol draws the cathode on the LEFT.  D3, D21 and D23 are rotated here so their cathodes face
the nodes named in the net table; check polarity by the K / A pin names, not by pin-number habits
carried over from KiCad 9 or earlier.
D2 is Device:D_TVS, whose pins are A1 / A2 -- that is the BIDIRECTIONAL TVS symbol, while the SMBJ24A is
a UNIdirectional part.  Pin 1 is wired to VBAT_PROT so that pad 1 (the cathode band on an SMB body)
lands on the rail.  Either swap in a unidirectional symbol, or change the part number to SMBJ24CA if a
bidirectional clamp is what is actually wanted.""")

_box("right", """VALUE NOTES
R100 = 5.6 mOhm, the current-limit sense.  It carries the whole 7.0 A night load: 0.27 W, so 2512 at a
minimum and a 4-terminal (Kelvin) part if one can be had.  Task 8 must give it its own copper -- that
0.27 W couples into the board, not into the heat-spreader plate.
R101 = 30 kOhm sets the SOA multiplier from the voltage across the pair.  It is taken to MID, not to
FEED_P: it senses Q11's Vds.  Sized from the DRN pin's 1 mA limit at the SMBJ24A's 50.6 V 8/20 us clamp
-- (50.6 - 27) / 1 mA = 23.6 k, rounded up to the next standard value, giving 0.787 mA at 50.6 V.
C62 = 680 nF sets the fault timeout.  Worst-case inrush ramp with C64 fitted is 95 ms at 2.4 uA, and the
datasheet's guideline is to hold TMR's rise to 0.4 V during it.  Fault timeouts land at 9.2 ms into a
12 V dead short and 8.6 ms in the 23.6 V clamp case, both inside Diagram 3 derated to a 65 C case.
R104 / C63 / D21 = 10k / 220 nF / 22 V is U10's VCC feed, hold-up and clamp.  It appears in all three of
the datasheet's application circuits including the 20 V one, so it is not a high-voltage artefact.
R102 = 10 Ohm damps Q11's gate.  R103 / C64 = 33 Ohm / 47 nF compensate the current-limit amplifier --
POPULATED, not DNP; see the eFuse note for why the value is the datasheet minimum rather than Figure 7's.
R105 / R106 / R107 = 240k / 10k / 240k with Q12, D22 and D23 steer Q10's gate.  Jellybeans, but R105 and
R107 stand off the full 50.6 V clamp so they are 1206 rather than 0603.
R2 and R3 = 0R links.  Fit EITHER L2 OR R2+R3, never both -- see the split-ground note.
D2 = SMBJ24A load-dump clamp.  D3 = 40 V Schottky feeding the logic rail.
C3 = 220 uF electrolytic bulk; C1 / C2 / C4 / C5 ceramic; C65 = 22 uF, U10's mandatory output bypass.
L1 = 1.5 uH, the series element of the pi filter; L2 = the common-mode choke.

STILL OPEN: no orderable is named for Q12, D21, D22, D23 or C65, and the HSOF-8 variant for Q10/Q11
(-1 versus -2 versus -3) has not been confirmed against the Infineon package drawing.""")

# ---------------------------------------------------------------- filter order
_box("right", """INPUT FILTER ORDER: eFuse -> TVS -> CM choke -> pi filter -> bulk
The TVS (D2) must come BEFORE the choke.  Surge clamping degrades with series inductance between the
entry point and the clamp, so any inductance ahead of D2 lets the clamped voltage overshoot.
The choke (L2) must come BEFORE the pi filter.  The common-mode noise being blocked originates INSIDE
the board -- it is the boost converter on the rails sheet -- so the choke has to sit between the
switcher and the harness, not out at the connector.
D2 sits DOWNSTREAM of the eFuse, on VBAT_PROT.  That is deliberate and it is an assumption spec 4.2's
SOA arithmetic depends on: the 23.6 V-at-7 A clamp case is computed with the TVS not clamping the input.
Moving D2 to FEED_P would protect Q10/Q11 from the surge directly and is arguably better -- it is logged
as an open question for spec 4.3, and it invalidates the SOA numbers if it is done without redoing them.""")

_box("right", """FEED B (J9 -> Q13) -- SERVES AUX_R ONLY.  NEVER DIODE-OR IT WITH VBAT.
Feed B is a second, independent 12 V pigtail for the AUX_R pod switch.  It has no eFuse, no buck and no
filter (spec 4.1.1): reverse polarity and a 24 V load-dump clamp, nothing else.
  * Q13 (SQJ461EP, P-channel) is the reverse-polarity block: DRAIN to FEED_B_P (J9), SOURCE to VBAT_B.
    R108 (100k) pulls GATE_B to GND_B; D24 (15 V Zener, cathode VBAT_B, anode GATE_B) holds VGS inside the
    +/-20 V rating at the 50.6 V clamp.
  * D25 (SMBJ24A) sits on the PROTECTED side, VBAT_B to GND_B.  C66 = 100 nF.  D25 is drawn with
    Device:D_Zener (K / A), not Device:D_TVS: the SMBJ24A is unidirectional and D_TVS is the bidirectional symbol.
  * NT1 joins GND_B to GND at one deliberate point (the star point for the layout phase).  GND_B is local
    to this sheet and must not touch GND_IN or the plane anywhere else.
  * NEVER diode-OR VBAT_B with VBAT.  The feeds stay separate so a fault on one cannot take out the other.
  * The 3 A fuse for feed B is HARNESS-SIDE, below the bike's 5 A circuit fuse.  There is no fuse here.
Q13 uses the Si7141DP symbol (S = pins 1-3, G = 4, D = 5) because it matches the SQJ461EP PowerPAK SO-8L
footprint's five pads; its Value field is SQJ461EP.  Worst case 2.48 A at 10.5 V is 0.10 W in Q13.""")

# ---------------------------------------------------------------- split ground
_box("below", '''COMMON-MODE CHOKE AND THE SPLIT GROUND -- DO NOT "TIDY" THIS

GND_IN (connector side) and GND (board side) are SEPARATE NETS, joined only through choke winding B.
Nothing else may bridge them -- no wire, no capacitor, and on the PCB no ground-plane copper.

The usual way this gets broken is CAPACITIVE, not a wire: a decoupling cap from VBAT_PROT (upstream) to
GND (downstream) bridges winding A's input to winding B's output, giving HF a path straight around the
choke.  The circuit then works perfectly and filters nothing, and no ERC or DRC check will complain.

That is why C1 sits on VBAT_F (downstream) and the TVS anode sits on GND_IN (upstream).

THE ENTIRE eFUSE SITS ON GND_IN.  U10's GND and SEL, C62, C63, C64, C65 and D21/D23's anodes all return
to the connector side, because U10 measures the feed and must reference the return the battery is
actually connected to.  Do not move any of them to board GND to "shorten the return path".

BUILD OPTION: fit EITHER L2 (the choke) OR R2+R3 (0R links that short the windings).  Links give the
simple tied-ground case for the first prototype; the footprint is present either way so fitting a real
choke later needs no board revision.

LAYOUT (Task 8): the ground plane must not bridge the choke.

GND_IN is a LOCAL label, never a power symbol.  A second power symbol named GND would merge the two
returns globally and silently defeat the whole arrangement.''')
