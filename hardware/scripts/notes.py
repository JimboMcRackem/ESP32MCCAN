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

    note("|RAIL DOMAINS",
         "Three power domains plus one backup feed. +3V3_ALW is the always-on logic rail (U1, from VLOGIC_IN). +5V is the gated "
         "rail (U2, from VBAT) and is enabled only by EN_5V; with EN_5V floating, R19 holds the buck off. VBAT is the protected "
         "battery rail out of the input eFuse. VBAT_B is the second protected feed (spec 4.3) and is not generated on this sheet. "
         "There is no boost converter and no switched 3V3 rail on this board.")

    note("""|SLEEP-BUDGET CRITICAL VALUES -- DO NOT "TIDY"
Both feedback dividers are >= 500 kohm on purpose. The LM5164's quoted quiescent
current does NOT include the external FB divider; a conventional 275 kohm divider
would add ~12 uA per rail, unbudgeted. At 348k/200k and 634k/200k each draws
6.0 uA. A high-impedance FB node needs the feedforward cap for stability -- that
is the trade being made deliberately.""")

    note("|THE BUCKS RUN BELOW THE AM BAND ON PURPOSE: THE AM BROADCAST BAND IS 530 kHz - 1.7 MHz",
         "This is a motorcycle and the battery harness is the antenna. The LM5164's maximum switching frequency is 1 MHz, which is "
         "INSIDE the AM band, so both bucks are placed BELOW it -- R4 = 20.5k gives 402 kHz on the 3.3 V rail, R7 = 31.6k gives "
         "396 kHz on the 5 V rail (FSW[kHz] = VOUT[V] x 2500 / RRON[kohm]). Their fundamentals are clear of the band; harmonics 2 "
         "and 3 are not, and no LM5164 setting can fix that. Mitigate in layout and filtering, not by raising the frequency: keep "
         "both buck power loops tiny, and remember the common-mode choke on power_input is there for this noise.")

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
         "pick a shielded part whose saturation current clears the LM5164's 1.5 A peak current limit, not merely 1 A.")

    note("|PGOOD IS LEFT OPEN ON BOTH REGULATORS -- NOT AN OVERSIGHT",
         "PGOOD is open-drain and pulls LOW whenever its rail is down, which is precisely deep sleep. A pull-up would sink real "
         "current continuously while asleep (even 100k is 33 uA). No pull-up is fitted and no net is attached, so ERC reports "
         "these pins unconnected. No no-connect flags were added, on purpose: the ERC report is the reminder. If a rail-fault "
         "input is ever wanted, gate the pull-up -- do not just add one.",
         "GND ON THIS SHEET IS BOARD GROUND. There is no GND_IN here; this sheet is downstream of the common-mode choke on "
         "power_input, so every ground symbol is the board-side return. Star the converter grounds properly in layout.")
