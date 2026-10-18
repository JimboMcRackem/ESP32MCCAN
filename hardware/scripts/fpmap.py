"""Footprint assignment for every symbol in the project.  Task 8, step 0.

The generators call `fp(ref)` when emitting each symbol's Footprint property, so the
assignment lives here in one auditable place rather than being scattered across four
sheet generators.  Nothing else in the project chooses a footprint.

Three rules govern the choices below:

1. **Signal passives are 0603.**  Small enough to be dense, large enough to hand-rework,
   and the standard for the rest of the board.
2. **A passive gets a larger package for a REASON, and the reason is written next to it.**
   Either it carries current, or it stands off a voltage that forces a bigger part, or a
   fault condition puts power into it.  A package chosen "to be safe" with no stated
   reason is just wasted area.
3. **Nothing gets a footprint that has not been checked to exist.**  `verify_fpmap.py`
   resolves every string here against the KiCad libraries and the project library, and
   checks that the pad count matches the symbol's pin count.

The voltage rule for the front end is worth restating because it is not obvious from the
schematic: **the SMBJ24A's 8/20 us clamping voltage is 50.6 V** (`smbj.pdf`, see
part-selection.md "Correction 2").  Every part on the raw feed -- FEED_P, FEED_FUSED,
VBAT_F, VBAT_PROT, VBAT, VLOGIC_IN -- must survive that, not the 38.9 V figure the
distributor summaries quote.  That is why the bulk ceramics there are 1206/1210 rather
than 0805: a 63 V part in 0805 either does not exist at these values or derates so hard
under DC bias that it is not the capacitance the design assumes.
"""

import quadpins

# ---------------------------------------------------------------- stock libraries
R_0603 = "Resistor_SMD:R_0603_1608Metric"
R_1206 = "Resistor_SMD:R_1206_3216Metric"
R_2512 = "Resistor_SMD:R_2512_6332Metric"
C_0603 = "Capacitor_SMD:C_0603_1608Metric"
C_0805 = "Capacitor_SMD:C_0805_2012Metric"
C_1206 = "Capacitor_SMD:C_1206_3216Metric"
C_1210 = "Capacitor_SMD:C_1210_3225Metric"

# ---------------------------------------------------------------- resistors
# Default 0603.  Overrides, each with its reason:
R_OVERRIDE = {
    # R2/R3 are the 0 ohm links that bypass the two windings of the input common-mode
    # choke L2.  They are DNP -- the choke is the populated option (review finding F2) --
    # but if anyone ever fits them for the tied-ground prototype build they carry the
    # ENTIRE 7.0 A night load.  A 0603 link is rated around 1 A.  2512 or nothing.
    "R2": R_2512,
    "R3": R_2512,
}
# R100-R107: the eFuse (spec 4.2).  Two reasons break the 0603 default here.
#   R100 is the 5.6 mOhm current-sense shunt and carries the whole 7.0 A night load:
#   0.27 W steady, and the datasheet's current-limit loop reads across it, so it wants its
#   own copper and a 4-terminal part if one can be had.  2512 is the floor.
#   R101/R105/R107 stand off the raw feed.  A 0603's working-voltage rating is 50 V and
#   the SMBJ24A's 8/20 us clamp is 50.6 V -- that is not margin, it is a coin toss.  1206
#   is rated 200 V.  R102/R103/R104/R106 all sit on clamped or low-voltage nodes and stay
#   at the 0603 default.
R_OVERRIDE["R100"] = R_2512
for _r in ("R101", "R105", "R107"):
    R_OVERRIDE[_r] = R_1206

# ---------------------------------------------------------------- capacitors
# Default 0603.  Overrides:
C_OVERRIDE = {
    # C3: 220 uF bulk on VBAT.  Must be a 63 V part -- see the module docstring.  An
    # aluminium electrolytic V-chip can; 10 x 10.5 mm is the smallest that holds
    # 220 uF at 63 V.
    "C3": "Capacitor_SMD:CP_Elec_10x10.5",
}
# Ceramics on the raw feed.  These see the TVS clamp, so they are 63 V+ parts and sized
# by what that actually costs in package:
for _r in ("C2", "C5", "C7", "C13"):              # 100 nF -- 0805 covers 100 nF at 100 V
    C_OVERRIDE[_r] = C_0805
for _r in ("C4", "C6", "C12"):                     # 1-2.2 uF at 63 V does not fit 0805
    C_OVERRIDE[_r] = C_1206
# C41-C43: C_VS, one 100 nF per signal quad (U11-U13) on VBAT -- the raw feed behind the
# LTC4380, so it sees the SMBJ24A's 50.6 V clamp: a 100 V part (quadpins.C_VS), and 0805 is
# where 100 nF at 100 V fits, same reasoning as C2/C5/C7.  C44-C46 (10 nF on the 3.3 V SNS_x
# lines) and every other passive on the outputs sheet are 0603 signal parts: no entry.
for _r in ("C41", "C42", "C43"):
    C_OVERRIDE[_r] = C_0805
# C62-C65: the eFuse.  C62 (C_TMR) and C63 (VCC, clamped to 22 V by D21) are ordinary
# 0603 parts.  C64 hangs off the GATE node, which rides at OUT + 11.5 V and therefore up
# to ~40 V against GND_IN -- 0805 for a 63 V part, same reasoning as C2/C5/C7.
C_OVERRIDE["C64"] = C_0805
# C65: 22 uF minimum at the LTC4380's OUT pin, on the raw feed, so a 63 V part.  22 uF at
# 63 V does not exist in any ceramic package that would survive the DC bias -- a 1210 63 V
# X7R holds a few uF at 24 V.  An aluminium V-chip can, like C3.  FLAGGED: no orderable
# picked yet; 6.3 x 7.7 mm is the smallest body that holds 22 uF at 63 V, and the
# footprint must be re-checked against whatever part is actually chosen.
C_OVERRIDE["C65"] = "Capacitor_SMD:CP_Elec_6.3x7.7"
# C66: 100 nF on VBAT_B, behind Q13 and ahead of the SMBJ24A's 50.6 V clamp -- same reasoning
# as C2/C5/C7: a 100 V part, and 0805 is where 100 nF at 100 V fits.
C_OVERRIDE["C66"] = C_0805
# R108 (100 k, GATE_B pull-down) is a signal passive on a gate node: 0603 default, no entry.

# ---------------------------------------------------------------- everything else
EXPLICIT = {
    # --- diodes
    "D2":  "Diode_SMD:D_SMB",                  # SMBJ24A -- DO-214AA (SMB) per smbj.pdf
    "D3":  "Diode_SMD:D_SMA",                  # 40 V Schottky, logic-rail OR
    "D5":  "LED_SMD:LED_0603_1608Metric",      # status LED
    # --- eFuse, spec 4.2.  D1/Q1/F1 used to be the front end and are gone: one LTC4380
    # and its pass pair now do reverse polarity, overcurrent and overvoltage together.
    "D21": "Diode_SMD:D_SOD-123",              # 22 V Zener, U10 VCC clamp
    "D22": "Diode_SMD:D_SOD-323",              # 1N4148 class, Q10 gate feed
    "D23": "Diode_SMD:D_SOD-323",              # 1N4148 class, Q12 base steering
    "D6":  "Package_TO_SOT_SMD:SOT-23",        # PESD2CANFD24U-T, 3 terminals (Table 3)
    # --- transistors
    "Q2":  "Package_TO_SOT_SMD:SOT-23",        # MMBT3904
    "Q3":  "Package_TO_SOT_SMD:SOT-23",
    # Q10/Q11: IPT008N06NM5LF, Infineon HSOF-8 ("OptiMOS Source-Down").  The KiCad
    # footprint numbers only three pads -- 1, 2, 3 -- which is what lets a three-pin
    # Q_NMOS_GSD symbol map onto it.  FLAGGED: HSOF-8-1 versus -2 versus -3 has NOT been
    # confirmed against the datasheet's package drawing, and the variants differ in pad
    # geometry.  Resolve before fabrication (Task 8).
    "Q10": "Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1",
    "Q11": "Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1",
    "Q12": "Package_TO_SOT_SMD:SOT-23",        # MMBT3904 class, Q10 gate steering
    # --- integrated circuits
    # LM5164 DDA = 8-pin SO PowerPAD.  The datasheet's mechanical drawing gives the
    # thermal pad as 3.4 x 2.8 mm; KiCad has no exact match, and EP2.62x3.51 is the
    # closest by area (9.20 mm2 against 9.52).  FLAGGED: draw an exact DDA land pattern
    # before fabrication -- this is a thermally critical part and the EP is its heatsink.
    "U1":  "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm",
    "U2":  "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm",
    "U5":  "RF_Module:ESP32-WROOM-32E",        # ships with KiCad; 18.0 x 25.5 mm
    "U6":  "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",   # TJA1042T/3
    # LTC4380HMS-2: the MS package is MSOP-10 with NO exposed pad.  The DD (DFN) package
    # does have one and numbers it 11; the symbol has ten pins, so ordering DD would leave
    # the pad unlanded.  Order the MS part.
    "U10": "Package_SO:MSOP-10_3x3mm_P0.5mm",
    # --- magnetics
    "L1":  "Inductor_SMD:L_Vishay_IHLP-4040",       # IHLP-4040DZ-01, 1.5 uH
    "L2":  "mccan:Wurth_WE-CMBNC_7448031002",       # vendor footprint, pads verified
    "L4":  "Inductor_SMD:L_Coilcraft_XAL7070-XXX",  # XAL7070-223ME, 22 uH
    "L5":  "Inductor_SMD:L_Coilcraft_XAL7070-XXX",
    # --- connectors and switches
    "J2":  "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",  # internal prog

    # ---- Wire entries.  RESOLVED 2026-09-19: TE Superseal is a WIRE-TO-WIRE series and
    # has no panel-mount board-side housing, so the seven "panel connectors" these used to
    # be could never have been built.  The board side is now soldered wire tails; the
    # Superseal joints live out on the harness and the cables enter through cable glands.
    # That is also why these sat in BLOCKED for the whole of Task 8 step 0 -- the footprint
    # was unassignable because the part class was wrong, not because a datasheet was missing.
    #
    # _Relief variants: the footprint carries a second, unplated hole per conductor so the
    # wire can be threaded back through it.  That is the board-level strain relief, and it
    # is what keeps a pulled cable from lifting a pad.  It is not optional here -- nothing
    # else mechanically restrains these wires.
    #
    # Hole sizes are chosen by the LARGEST conductor in each cable, so mixed-gauge tails
    # still seat.
    # Phase A (plan4, D5): J1 is feed A, 2-pin since the ignition cavity went; J9 is feed B;
    # J3 is the front tail (4 lamps + GND); J4/J5 are the two parts of the rear 7-core run
    # (KiCad's Connector_Wire relief footprints stop at 1x06, so one cable is two tails).
    "J1":  "Connector_Wire:SolderWire-1.5sqmm_1x02_P6mm_D1.7mm_OD3mm_Relief",     # feed A: FEED_P, GND_IN
    "J9":  "Connector_Wire:SolderWire-1.5sqmm_1x02_P6mm_D1.7mm_OD3mm_Relief",     # feed B: FEED_B_P, GND_B
    "J3":  "Connector_Wire:SolderWire-0.5sqmm_1x05_P4.6mm_D0.9mm_OD2.1mm_Relief", # front: FL/FR DRL+IND, GND
    "J4":  "Connector_Wire:SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief", # rear 1: RL DRL/IND/BRK, GND
    "J5":  "Connector_Wire:SolderWire-0.5sqmm_1x03_P4.6mm_D0.9mm_OD2.1mm_Relief", # rear 2: RR DRL/IND/BRK
    "J8":  "Connector_Wire:SolderWire-0.5sqmm_1x02_P4.6mm_D0.9mm_OD2.1mm_Relief", # CAN twisted pair

    # L6: drawn 2026-09-19 from the RECOMMENDED LAND PATTERN figure of
    # cmf_automotive_signal_act45b_en.pdf, read as vector geometry rather than as a text
    # dump.  The four bare numerals in the text (1.6 / 3.4 / 3.2 / 5.9) carry no axis, so
    # they were tied back to the drawn pad rectangles: all four pads 21.77 x 14.51 pdf
    # units, and the scale comes out at 16.125-16.129 u/mm on all four dimensions
    # independently, which is what makes the reading safe rather than plausible.
    #   pads 1.35 x 0.90 mm, centres (+-2.275, +-1.25); column gap 3.2 / overall 5.9;
    #   row gap 1.6 / overall 3.4.  Pin 1 top-left, 4 top-right, 2 bottom-left, 3 bottom-right.
    "L6":  "mccan:TDK_ACT45B",
    "SW1": "Button_Switch_SMD:Panasonic_EVQPUJ_EVQPUA",   # BOOT
    "SW2": "Button_Switch_SMD:Panasonic_EVQPUJ_EVQPUA",   # EN/RESET

    # --- plan4 phase A.  The three signal-output quads (TPS4H160B-Q1, PWP HTSSOP-28): the
    # footprint and its EP caveat live next to the pad table in quadpins.py.
    "U11": quadpins.FOOTPRINT,                 # quad A (left)
    "U12": quadpins.FOOTPRINT,                 # quad B (right)
    "U13": quadpins.FOOTPRINT,                 # quad C (brake)
    # --- feed B reverse-polarity circuit (D6)
    "Q13": "Package_SO:PowerPAK_SO-8L_Single",     # SQJ461EP, same package plan3's Q1 used
    "D24": "Diode_SMD:D_SOD-123",              # MMSZ5245B 15 V zener, Q13 gate clamp
    "D25": "Diode_SMD:D_SMB",                  # SMBJ24A on VBAT_B -- DO-214AA, as D2
    "NT1": "NetTie:NetTie-2_SMD_Pad0.5mm",     # GND_B <-> GND star point
}
# D8-D10: BAT54 sense-line clamps, one per signal quad (SNS_A/B/C -> +3V3_ALW).
for _i in range(8, 11):
    EXPLICIT["D%d" % _i] = "Diode_SMD:D_SOD-123"

# ---------------------------------------------------------------- BLOCKED
# These have NO footprint yet and cannot get one from a library or from a datasheet the
# project holds.  `fp()` returns "" for them so the gap is visible in the netlist rather
# than papered over with a plausible-looking wrong package.  See datasheets/NEEDED.md.
BLOCKED = {
    # EMPTY, and it should stay that way.  `fp()` returns "" for anything listed here so an
    # unassignable part shows up as a hole in the netlist rather than being papered over
    # with a plausible-looking wrong package, and every part on this board now has a
    # footprint that was either shipped with KiCad or drawn from a held datasheet.
    #
    # The last one out was L6 (ACT45B, drawn 2026-09-19 from the recommended land pattern
    # read as vector geometry).
    #
    # F1 IS GONE, and is not a candidate to come back.  It was a blade fuse, then briefly a
    # board-mounted eFuse with no part selected; spec 4.2 resolved it by making U10
    # (LTC4380 + Q10/Q11) the fuse, the reverse-polarity block and the overvoltage clamp in
    # one element.  D1, Q1 and R1 went with it.  Do not re-add a separate fuse without
    # re-reading 4.2 -- a series fuse in front of the eFuse only adds resistance to the 7 A
    # path.
}


def fp(ref):
    """Footprint for a reference designator, or "" if none is assigned yet."""
    if ref in BLOCKED:
        return ""
    if ref in EXPLICIT:
        return EXPLICIT[ref]
    if ref.startswith("R"):
        return R_OVERRIDE.get(ref, R_0603)
    if ref.startswith("C"):
        return C_OVERRIDE.get(ref, C_0603)
    return ""


def in_bom(ref):
    """False for a footprint that is not a purchased part.

    KiCad's Connector_Wire:SolderWire-* footprints are BOM-excluded in the library, because
    there is no connector to buy: they are bare pads with a strain-relief slot, and the wire
    itself is a harness line, not a board line (see hardware/docs/harness.md).  The symbols
    said "in BOM" while the footprints said otherwise, which board parity reported as seven
    "'Exclude from bill of materials' settings differ" warnings.  The footprints are right.
    """
    return not fp(ref).startswith("Connector_Wire:SolderWire")


def all_assigned():
    """Every ref this module knows about, for the verifier."""
    out = dict(EXPLICIT)
    out.update(R_OVERRIDE)
    out.update(C_OVERRIDE)
    return out
