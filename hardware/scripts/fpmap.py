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
# R52-R63: the twelve RGB sense shunts, 10 ohm.  Normal dissipation is 7 mW at 26.7 mA,
# which a 0402 would carry.  1206 is here for the FAULT case: a channel shorted to +24 V
# puts ~2.5 W into one shunt.  1206 does not survive that either -- the package is sized
# on the understanding that FIRMWARE LATCHES A SHORTED CHANNEL OFF, which is recorded as a
# cross-domain dependency in part-selection.md and belongs in the section 12 firmware plan.
# If that latch is ever dropped, these must become 2512 1 W parts.
for _i in range(52, 64):
    R_OVERRIDE["R%d" % _i] = R_1206
# R88-R99: output snubber resistors, DNP footprints only.  1206 because a snubber that is
# ever actually fitted is dissipating real power at the switching frequency, and because
# the matching snubber capacitors C49-C60 are 1206 -- a snubber RC wants to be one
# compact pair, not a 0603 next to a 1206.
for _i in range(88, 100):
    R_OVERRIDE["R%d" % _i] = R_1206

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
for _r in ("C2", "C5", "C7", "C13", "C46"):       # 100 nF -- 0805 covers 100 nF at 100 V
    C_OVERRIDE[_r] = C_0805
for _r in ("C4", "C6", "C12"):                     # 1-2.2 uF at 63 V does not fit 0805
    C_OVERRIDE[_r] = C_1206
for _r in ("C18", "C19", "C45"):                   # 10 uF at 63 V needs 1210
    C_OVERRIDE[_r] = C_1210
# C20-C22: 4.7 uF on the +24 V rail.  Not a clamp-voltage case -- this is DC BIAS.  A
# 25 V X7R at 24 V keeps 40-60% of nameplate (review observation O1), so the boost's
# output capacitance is only what the package can actually hold.  1206 in a 50 V part.
for _r in ("C20", "C21", "C22"):
    C_OVERRIDE[_r] = C_1206
# C49-C60: output snubber capacitors, DNP.  Pairs with R88-R99; see that note.
for _i in range(49, 61):
    C_OVERRIDE["C%d" % _i] = C_1206

# ---------------------------------------------------------------- everything else
EXPLICIT = {
    # --- diodes
    "D1":  "Diode_SMD:D_SOD-123",              # 12 V Zener, P-FET gate clamp
    "D2":  "Diode_SMD:D_SMB",                  # SMBJ24A -- DO-214AA (SMB) per smbj.pdf
    "D3":  "Diode_SMD:D_SMA",                  # 40 V Schottky, logic-rail OR
    "D4":  "Package_TO_SOT_SMD:TO-277A",       # SS5PH102 -- SMPC/TO-277A per its datasheet
    "D5":  "LED_SMD:LED_0603_1608Metric",      # status LED
    "D6":  "Package_TO_SOT_SMD:SOT-23",        # PESD2CANFD24U-T, 3 terminals (Table 3)
    # --- transistors
    "Q1":  "Package_SO:PowerPAK_SO-8L_Single", # SQJ461EP
    "Q2":  "Package_TO_SOT_SMD:SOT-23",        # MMBT3904
    "Q3":  "Package_TO_SOT_SMD:SOT-23",
    # --- integrated circuits
    # LM5164 DDA = 8-pin SO PowerPAD.  The datasheet's mechanical drawing gives the
    # thermal pad as 3.4 x 2.8 mm; KiCad has no exact match, and EP2.62x3.51 is the
    # closest by area (9.20 mm2 against 9.52).  FLAGGED: draw an exact DDA land pattern
    # before fabrication -- this is a thermally critical part and the EP is its heatsink.
    "U1":  "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm",
    "U2":  "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm",
    # LM51571-Q1 RTE = WQFN-16 3x3 P0.5, exposed pad 1.66 +/-0.1 mm square (Figure 7-1
    # and the package drawing).  KiCad's EP1.675x1.675 is within tolerance.
    "U3":  "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.675x1.675mm",
    "U5":  "RF_Module:ESP32-WROOM-32E",        # ships with KiCad; 18.0 x 25.5 mm
    "U6":  "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",   # TJA1042T/3
    "U7":  "Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm", # PCA9685PW/Q900, SOT361-1
    "U8":  "Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm", # ADG706BRU
    "U9":  "Package_SO:Infineon_PG-TSDSO-14-22",    # BTS7008-2EPA, pad 15 = the EP (VS)
    # --- magnetics
    "L1":  "Inductor_SMD:L_Vishay_IHLP-4040",       # IHLP-4040DZ-01, 1.5 uH
    "L2":  "mccan:Wurth_WE-CMBNC_7448031002",       # vendor footprint, pads verified
    "L3":  "Inductor_SMD:L_Coilcraft_XAL4030-XXX",  # XAL4030-682ME, 6.8 uH boost
    "L4":  "Inductor_SMD:L_Coilcraft_XAL7070-XXX",  # XAL7070-223ME, 22 uH
    "L5":  "Inductor_SMD:L_Coilcraft_XAL7070-XXX",
    # --- protection
    "F2":  "Fuse:Fuse_1206_3216Metric",        # 1206L050/24 PTC, one per RGB string
    "F3":  "Fuse:Fuse_1206_3216Metric",
    "F4":  "Fuse:Fuse_1206_3216Metric",
    "F5":  "Fuse:Fuse_1206_3216Metric",
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
    # (J1 and J7 both mix 16 and 18/22 AWG) still seat.
    "J1":  "Connector_Wire:SolderWire-1.5sqmm_1x03_P6mm_D1.7mm_OD3mm_Relief",     # PWR, 16 AWG
    "J3":  "Connector_Wire:SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief", # FL, 22 AWG
    "J4":  "Connector_Wire:SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief", # FR
    "J5":  "Connector_Wire:SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief", # RL
    "J6":  "Connector_Wire:SolderWire-0.5sqmm_1x04_P4.6mm_D0.9mm_OD2.1mm_Relief", # RR
    "J7":  "Connector_Wire:SolderWire-1.5sqmm_1x03_P6mm_D1.7mm_OD3mm_Relief",     # Denali, 16 AWG gnd
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
}
# Q4-Q9: NX5020UNBKS, "a very small SOT363 (SC-88)" per its datasheet section 1.
for _i in range(4, 10):
    EXPLICIT["Q%d" % _i] = "Package_TO_SOT_SMD:SOT-363_SC-70-6"
# D7-D20: BAT54 clamps.
for _i in range(7, 21):
    EXPLICIT["D%d" % _i] = "Diode_SMD:D_SOD-123"

# ---------------------------------------------------------------- BLOCKED
# These have NO footprint yet and cannot get one from a library or from a datasheet the
# project holds.  `fp()` returns "" for them so the gap is visible in the netlist rather
# than papered over with a plausible-looking wrong package.  See datasheets/NEEDED.md.
BLOCKED = {
    # No part selected at all, and it is a panel penetration so the body matters.
    # F1 changed 2026-09-19 from a panel-mount blade holder to a BOARD-MOUNTED eFUSE.
    # Requirements are in docs/part-selection.md "F1 -- eFuse requirements"; the two that
    # constrain the search hardest are a limit setpoint of 9-10 A (BELOW 7.8 A and the
    # flash-to-pass transient is chopped, because an eFuse has none of the thermal inertia
    # the blade fuse relied on; ABOVE 10 A and it exceeds the connector rating) and
    # AUTO-RETRY rather than latch-off (the MCU is powered downstream of F1, so it cannot
    # clear a latch).
    "F1": "board-mount eFuse, >=8 A at 65 C, limit 9-10 A, auto-retry -- no part selected",
    # Datasheet IS held, but the land pattern must be drawn:
    #   L6  -- ACT45B, 4.5 x 3.2 mm 4-pin.  KiCad's Coilank ACM4532 is the right size
    #          class but its pads (+-1.825/+-1.125, 1.15x1.55) do not map onto the
    #          ACT45B's extracted land figures (1.6/3.4/3.2) without guessing.
    #   U4  -- DML3017LDC, V-DFN3030-12.  The pin-1 orientation is AMBIGUOUS between the
    #          two figures in DS46371 and must be resolved from the package outline, not
    #          inferred.  Drawing it with pin 1 wrong mirrors the whole part.
    "U4": "DML3017LDC V-DFN3030-12 -- pin-1 orientation ambiguous in DS46371",
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


def all_assigned():
    """Every ref this module knows about, for the verifier."""
    out = dict(EXPLICIT)
    out.update(R_OVERRIDE)
    out.update(C_OVERRIDE)
    return out
