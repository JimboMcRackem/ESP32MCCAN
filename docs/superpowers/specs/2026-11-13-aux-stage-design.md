# Aux stage: pod switch, yellow PWM buffer, pod tails

**Date:** 2026-11-13. **Status:** drawn on `plan4-emarked-modules`. ERC is clean and every
`check_netlist.py` group passes.
**Approved by the user:** 2026-11-13.
**Builds on:** the redesign spec `2026-10-17-emarked-module-redesign-design.md`, using main's
copy, which holds the 2026-11-12 pod measurements in §2.2.1 and the feed arrangement in §4.1.1.
It also builds on the night-mode spec `2026-11-01-aux-night-mode-design.md`, §6.1 Branch A.

## 1. What the pods need

The bench measurements from 2026-11-12 are in redesign §2.2.1. The pod plug has four wires:

| Wire | Carries |
|---|---|
| Red | Supply. It also lights the DRL LEDs. |
| Black | Return |
| Yellow | A 5 V PWM signal at about 100 Hz. It sets main-LED brightness. |
| Blue | Role unknown |

- At worst case, each pod draws **3.2 A**: 12 V at full beam. The supply current comes in
  pulses at the PWM rate.
- Both pods run from feed B, which goes to the bike's 15 A aux 3 through a 10 A harness fuse.
  The circuit ratings are still to be confirmed on the bike.

## 2. Decisions

| # | Decision | Reason |
|---|---|---|
| A1 | **U14 Infineon BTS7008-2EPA**: one dual switch for both pods. OUT0 drives pod L and OUT1 drives pod R. VS (the exposed pad) is on `VBAT_B`. | Each channel handles 7.5 A nominal. The part is rated for capacitive loads. Its overload trip `IL(OVL0)` is **77–99 A** (Rev. 1.21, p.33), so the pods' input-capacitor inrush cannot trip it. Its inputs switch at 2.0 V maximum, so a 3.3 V GPIO drives them. The project already had this part's symbol, verified on 2026-09-15. |
| A2 | Inputs: `OUT_AUX_x` → 4.7 k series (R76/R77) → `IN_AUX_x`, with a 47 k pull-down (R74/R75). | This is the same pattern as the signal quads. A driven input sits at 3.0 V, and the input is low at reset. |
| A3 | DEN and DSEL are pulled down (R78/R79). IS has only RSENSE R80 (1.2 k). | No GPIO is free for pod diagnosis. **Changed from what was proposed:** the proposal had a DNP link from IS to `SNS_C`. It was dropped because DEN has no control line, and borrowing `DIAG_EN_Q` would put IS and U13's CS on `SNS_C` at the same time. Pod lamp-out needs a pin first. |
| A4 | **U15 TI SN74AHCT2G126**, powered from `+5V`. `AUX_PWM` (GPIO 13) drives both A inputs and has a 47 k pull-down (R81). Each **active-high enable** is that pod's `OUT_AUX_x`. | The PWM goes through one shared LEDC channel, as the firmware already does. The pod's own power-on signal gates its yellow line, so yellow is never driven into an unpowered pod. This closes the earlier back-feed concern with no extra GPIO. The TTL inputs accept 3.3 V. |
| A5 | Yellow chain: Y → 100 Ω (R82/R83) → clamp node → 220 Ω 1206 (R84/R85) → wire. The clamp node has a BZT52C5V6 to GND (D26/D27) and a 100 k pull-down (R86/R87). | If yellow shorts to 12 V, the Zener takes 29 mA and the 1206 takes 0.19 W. The 100 Ω keeps current into the buffer's output clamp small. Yellow idles low. **The series values are provisional** until the yellow input current is measured. |
| A6 | Supply parts on `VBAT_B`: C67 is 100 nF 100 V; C68 is 220 µF 63 V aluminium (10×10.5). Each output has a 10 nF 100 V capacitor (C69/C70). All of them return to `GND_B`. | These carry the 100 Hz pulse current. They are 63 V or more because the SMBJ24A clamps at 50.6 V. |
| A7 | Pod tails **J10/J11**: soldered 4-core tails (`SolderWire-1sqmm_1x04_P5.4mm`, relief). Pin 1 is red (`POD_x_P`), 2 is black (`GND_B`), 3 is yellow (`YEL_x`), 4 is blue (**not connected**). | This follows the D5 tail convention. 1.0 mm² copes with 3.2 A. Blue waits until its role is measured. |
| A8 | `GND_B` leaves the power_input sheet as the pods' return. U14's own GND pin goes to `GND`. | Pod current stays on feed B's return, while the logic levels are referenced to the MCU's ground. |
| A9 | GPIO 13 (module pad 16) changes from `LED_STAT` to `AUX_PWM`. D5 and R27 are deleted. | The user approved this on 2026-11-12. There is no status LED any more. |
| A10 | **R100 changes from 5.6 mΩ to 33 mΩ**, which sets feed A's limit at 1.36–1.67 A. | No pod is on feed A any more. The limit sits above feed A's ≈0.87 A worst case and below its ≈2 A fuse. Re-check it against the start-up current measured at bring-up (§9.1 item 2a). |
| A11 | Q13 (SQJ461EP, 16 mΩ) stays as feed B's reverse-polarity FET. | At 6.4 A it dissipates about 0.66 W. The layout must give it copper. |
| A12 | U13's CH3 is released from `AUX_MODE` and is now spare. | `AUX_MODE` was superseded on 2026-11-12. |

## 3. Still open

These come from the bench measurements (redesign §9.1):
- **Yellow input threshold and current:** they confirm or resize the R82–R85 series values.
- **Blue's role:** it decides what J10.4 and J11.4 connect to.
- **Pod inrush** (`docs/bench/2026-11-13-pod-inrush-procedure.md`): this confirms A1. It also
  sizes how much C68 has to carry.
- **SN74AHCT2G126 datasheet:** the pinout used is the standard 2G126 one, identical to KiCad's
  74LVC2G126. Check it against TI's sheet (see `hardware/datasheets/NEEDED.md`).

## 4. Verification

- **Generators:** `symlib.py`, `gen_power_input.py`, `gen_mcu_can.py`, `gen_outputs.py` and
  `gen_root.py` were run. A second run of each produces byte-identical output.
- **ERC** (`kicad-cli` 10.0.2): 0 violations.
- **`check_netlist.py`:** all seven groups pass. The `outputs` group now checks the whole aux
  stage: enables, series and pull-down resistors, the U14 pins, the yellow clamp chain, and that
  `AUX_PWM` has a pull-down. The `harness` group checks J10/J11 and that blue is open.
- **Mutation check:** swapping U15's two enables fails the `outputs` group with 4 findings.
- **Netlist read by hand:** `AUX_PWM`, `OUT_AUX_x`, `IN_AUX_x`, `POD_x_P`, `YEL_x`, the clamp
  nodes, `VBAT_B` and `GND_B` all hold exactly the intended pins.
