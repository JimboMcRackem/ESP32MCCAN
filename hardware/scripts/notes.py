# -*- coding: utf-8 -*-
"""Sheet notes for rails.kicad_sch.  build(NOTES) appends wrapped note strings."""
import textwrap

NOTEW = 135          # characters per line at font size 0.8 in a 103.19 mm box


def build(NOTES):
    def note(*parts):
        """Each part is a paragraph (wrapped) unless it starts with '|' (verbatim)."""
        out = []
        for para in parts:
            if para.startswith("|"):
                out.extend(para[1:].split("\n"))
            else:
                out.extend(textwrap.wrap(para, NOTEW) or [""])
        NOTES.append("\n".join(out))

    note("""|SLEEP-BUDGET CRITICAL VALUES -- DO NOT "TIDY"
Both feedback dividers are >= 500 kohm on purpose. The LM5164's quoted quiescent
current does NOT include the external FB divider; a conventional 275 kohm divider
would add ~12 uA per rail, unbudgeted. At 348k/200k and 634k/200k each draws
6.0 uA. A high-impedance FB node needs the feedforward cap for stability -- that
is the trade being made deliberately.
EN_UVLO_SYNC has NO divider. A line-UVLO divider there would draw ~14 uA
continuously whether the boost is enabled or not. Driving it straight from the
GPIO keeps "floating = boost off" via the EN_BOOST pulldown.""")

    note("|U3 PIN 6 (EN_UVLO_SYNC) IS DRIVEN DIRECTLY BY EN_BOOST.  THERE IS NO DIVIDER.  DO NOT ADD ONE.",
         "The LM51571-Q1 typical application puts RUVLOT/RUVLOB from VSUPPLY to this pin to set a line UVLO. That divider sits across "
         "the battery rail and conducts whenever the battery is present, enabled or not -- about 14 uA, a large fraction of this "
         "board's whole deep-sleep budget. It was removed on purpose: the MCU brown-out and the LM51571's own VCC UVLO (2.8 V typ, "
         "sourced from BIAS) already cover the low-battery case, so an external line UVLO buys nothing.",
         "Consequences. (a) Pin 6 is high impedance with a ~5 uA hysteresis current source flowing OUT of it once above VUVLO. "
         "NOTHING on this sheet holds it low, so the EN_BOOST pulldown on mcu_can MUST exist -- 'floating = boost off' is only true "
         "if it is fitted. (b) ABSOLUTE MAXIMUM on pin 6 is 3.8 V to AGND (datasheet 8.1). A 3.3 V GPIO leaves 0.5 V of margin, so "
         "EN_BOOST must never see a 5 V pull-up. VUVLO(rising) is 1.5 V typ / 1.575 V max, so 3.3 V drives it hard enough. (c) Pin 6 "
         "is also the SYNC input; driving it DC means no external clock sync, which is intended.")

    note("|2.2 MHz ON THE BOOST IS DELIBERATE: THE AM BROADCAST BAND IS 530 kHz - 1.7 MHz",
         "This is a motorcycle. The boost is the loudest switcher on the board and it runs straight off the battery harness, which is "
         "the antenna. Its switching fundamental has to sit ABOVE the AM band, so U3 is set to 2.2 MHz -- the top of the "
         "LM51571-Q1's range and the frequency its electrical table is characterised at (RT = 9.09k; equation 5: "
         "RT = 2.21e10 / fRT - 955). R11 = 37.4k also enables Dual Random Spread Spectrum, whose low-frequency triangular profile "
         "targets exactly this band.",
         "The two BUCKS CANNOT do the same thing: the LM5164's maximum switching frequency is 1 MHz, which is INSIDE the AM band. "
         "They are therefore placed BELOW it -- R4 = 20.5k gives 402 kHz on the 3.3 V rail, R7 = 31.6k gives 396 kHz on the 5 V rail "
         "(FSW[kHz] = VOUT[V] x 2500 / RRON[kohm]). Their fundamentals are clear of the band; harmonics 2 and 3 are not, and no "
         "LM5164 setting can fix that. Mitigate in layout and filtering, not by raising the frequency: keep both buck power loops "
         "tiny, and remember the common-mode choke on power_input is there for this noise.")

    note("|THE LM5164 IS A CONSTANT-ON-TIME REGULATOR -- IT NEEDS IN-PHASE RIPPLE AT FB TO BE STABLE",
         "COT has no error amplifier. Datasheet 6.3.1 / table 6-1 require at least 20 mV of ripple at FB that is IN PHASE with the "
         "inductor current. Ceramic output caps alone give capacitive ripple, 90 degrees out of phase; the classic failure is bursts "
         "of on-pulses followed by a long off-time. C9 / C15 are the type-2 feedforward caps the brief calls for -- they AC-couple "
         "output ripple to FB, but they do not by themselves make that ripple resistive. Finish it one of two ways before ordering "
         "boards.",
         "(a) TYPE 2, as drawn: add a small series resistance in the output-cap leg. Equation 4 gives RESR >= 20 mV / dIL, i.e. "
         "~67 mohm (3.3 V rail, dIL 0.30 A) and ~54 mohm (5 V rail, dIL 0.37 A) at the 22 uH / 400 kHz operating point. Only ripple "
         "current flows in it (<1 mW) so it is nearly free, but it must be a real part -- do not rely on the cap's own ESR. "
         "(b) TYPE 3: the RA / CA / CB injection network of figure 7-1 (453k / 3.3nF / 56pF in TI's 12 V design). That is what the "
         "EVM ships and it needs no series resistance at all.",
         "C9 / C15 = 100 pF is well above the equation-6 minimum (3.1 pF, 2.7 pF) and puts the coupling zero near 4.5 kHz, two "
         "decades below FSW, so the full output ripple reaches FB.")

    note("|WHERE EVERY VALUE CAME FROM",
         "U1 / U2 LM5164DDA, VREF = 1.200 V, RFB2 = 1.2 / (VOUT - 1.2) x RFB1 (eq 10): 348k/200k -> 3.288 V, 634k/200k -> 5.004 V, "
         "6.0 uA each. TI recommends RFB1 in 100k..1M, so both sit inside the datasheet's own range. RRON: R4 20.5k -> 402 kHz, "
         "R7 31.6k -> 396 kHz; minimum on-time at the worst case (VIN clamped to ~39 V by the input TVS) is 205 ns, well above the "
         "50 ns floor. NOTE the LM5164 minimum VIN is 6 V, so a deep crank dip drops both bucks out -- correct, but know it. "
         "C8 / C14 = 2.2 nF is MANDATORY and exact: the datasheet says a larger bootstrap cap stresses the internal VCC regulator and "
         "damages the device. L4 / L5 = 22 uH gives 0.30 A (3.3 V) and 0.37 A (5 V) ripple at 13.8 V in, 30-37% of the 1 A rating; "
         "pick a shielded part whose saturation current clears the LM5164's 1.5 A peak current limit, not merely 1 A.",
         "U3 LM51571-Q1, VREF = 1.000 V, VLOAD = VREF x (RFBT/RFBB + 1) (eq 9): 115k/4.99k -> 24.05 V (+0.2%), 200 uA, drawn only "
         "while the boost is enabled. RT 9.09k -> 2.2 MHz. MODE 37.4k -> hiccup overload protection ON and spread spectrum ON "
         "(9.4.3). SS 22 nF, COMP 2.61k + 10 nF, CHF 100 pF, VCC 5.1R + 1 uF, BIAS 0R + 100 nF are the datasheet's "
         "list-of-materials values for its 6-to-12 V / 1.6 A / 2.1 MHz boost example (table 10-2); the VCC 5.1R + 1 uF pair is a "
         "hard requirement of section 9.3.2, not a suggestion. THE COMPENSATION IS A STARTING POINT, NOT A RESULT -- re-run "
         "R14 / C23 / C24 through the LM5157x Boost Quick Start Calculator for 24 V and this board's real load before a board spin.",
         "BIAS is fed from VBAT, not from +24V. Either is legal (BIAS operates 2.9 V to 45 V and the input TVS holds VBAT under "
         "that), but VBAT is unconditional whereas +24V only exists after the output pre-charges through L3 and D4. Shutdown current "
         "from BIAS is 2.6 uA typ / 5 uA max and would be drawn through L3 + D4 from VBAT anyway, so moving it saves nothing. Count "
         "that 2.6 uA in the sleep budget.")

    note("|PGOOD IS LEFT OPEN ON ALL THREE REGULATORS -- NOT AN OVERSIGHT",
         "PGOOD is open-drain and pulls LOW whenever its rail is down, which is precisely deep sleep. A 10k pull-up (the LM51571's "
         "recommended minimum) would sink 330 uA; even 100k sinks 33 uA continuously while asleep. No pull-up is fitted and no net "
         "is attached, so ERC reports these pins unconnected. No no-connect flags were added, on purpose: the ERC report is the "
         "reminder. If a rail-fault input is ever wanted, gate the pull-up -- do not just add one. U3 pin 15 (NC) is also left open.",
         "GND ON THIS SHEET IS BOARD GROUND. There is no GND_IN here; this sheet is downstream of the common-mode choke on "
         "power_input, so every ground symbol is the board-side return. AGND (7), both PGND (1, 16) and the exposed pad (17) tie to "
         "that one net, so R10's 'resistor to AGND' lands on GND -- the same node. Star them properly in layout.",
         "VBAT appears as THREE hierarchical labels (U2 input, L3 input, U3 BIAS feed) rather than one dragged wire. Same name, same "
         "sheet, same net -- confirmed in the exported netlist.")

    note("|BEFORE THIS SHEET IS TURNED INTO A BOARD",
         "1. No footprints are assigned to anything here; the Footprint field is empty on all 42 parts. 2. The 'rails' sheet symbol "
         "in mccan.kicad_sch has NO sheet pins, so all seven hierarchical labels below raise hier_label_mismatch in ERC -- add pins "
         "VLOGIC_IN (in), VBAT (in), EN_3V3SW (in), EN_BOOST (in), +3V3_ALW (out), +5V (out), +24V (out). 3. There is still no "
         "PWR_FLAG in the project, so GND reports power_pin_not_driven. 4. Decide type-2 vs type-3 ripple injection for the two "
         "bucks and fit the parts. 5. Re-run U3's compensation for 24 V. 6. Confirm the EN_BOOST pulldown exists on mcu_can and "
         "that nothing pulls EN_BOOST above 3.3 V. 7. L3 is 6.8 uH XAL4030-682ME -- check its saturation rating against the "
         "LM51571's 4.33 A switch current limit at the real 24 V load, not the nominal one. 8. D4 SS5PH102 sees VOUT plus "
         "switch-node overshoot; verify its rating against the real layout's ringing and keep the D4 / C20-C22 / PGND loop as small "
         "as physically possible -- at 2.2 MHz that loop is the whole EMI story.")
