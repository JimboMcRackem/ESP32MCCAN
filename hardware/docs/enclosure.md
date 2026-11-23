# Enclosure

**Board:** the plan4 board, 140 × 100 mm (README "Board status"). **Rewritten 2026-11-15.** The
earlier version described the retired plan3 board (200 × 140 mm, aluminium heat-spreader plate, gap
pad, Denali pods, 5 × M12 + 2 × M16 glands). It is in git history; none of it applies here.

**Authority:** board layout spec `../../docs/superpowers/specs/2026-11-13-board-layout-phase-b-design.md`
(§1, §5.1, §6), `fabrication.md` §7, `harness.md` §2. Coordinates are read from
`scripts/layout_pcb.py` and `mccan.kicad_pcb`.

Items marked **[TO CONFIRM]** need a catalogue lookup or a measurement. No part numbers are
invented here: a guessed part number in a document that drives an order is worse than an admitted gap.

---

## 1. What has to fit

The box goes under the Experia's fairing, next to the bike's main charge board (layout spec §1).
It is chosen to fit the board, not the other way round. There is no heat-spreader plate; the
thermal record is §9 (kept at §9 because the generator scripts cite it there).

| Item | Value |
|---|---|
| Board outline | **140 × 100 mm**, 1.6 mm thick, 1 mm corner radius |
| Mounting | **4 × M3**, 3.2 mm non-plated holes, **5 mm in from each corner**; keep 6 mm diameter clear for a washer or standoff |
| Hole centres, from the top-left corner (antenna edge at the top) | (5, 5), (135, 5), (5, 95), (135, 95) mm |
| Tallest part, top side | **L2, 25.0 mm max** above the board (Würth 7448031002 choke, THT, seated on its own moulded base; no separate standoff). Its body is 24.0 × 17.0 mm max. The KiCad 3D model stands only 21.3 mm, so size the enclosure from the datasheet, not the STEP. Next are C3 and C68, about 10.5 mm |
| Bottom side | No parts. The THT leads of J2 and L2 and the soldered wire tails protrude: use standoffs of **at least 5 mm** |
| Cable edge | The **bottom** 140 mm edge. All eight wire tails in one row (J1, J3, J4, J5, J8, J10, J9, J11), spanning about 122 mm |
| Antenna edge | The **top** edge, opposite the cables (§2) |
| Internal depth | Standoff + 1.6 mm + 25 mm + clearance: **at least ~36 mm**. The layout spec assumed about 50 mm, which fits |
| Service loop | Enough slack on every tail to lift the board out with the glands slackened. Nothing unplugs |
| Lid-off access | J2 (programming), SW1 (BOOT) and SW2 (EN) beside it, and the 30 test pads. Normal updates are over WiFi, so the lid stays on in service |

## 2. Antenna clearance

U5 (ESP32-WROOM-32E) sits on the **top** edge, centred **95 mm from the left edge**, its body edge
flush with the board edge (Espressif's module-on-edge placement).

- **Board keep-out** (no copper on any layer, no parts): from the left edge **70.75–119.25 mm**,
  from the top edge **0–6.44 mm**. It is in the Gerbers and checked by `check_antenna.py`.
- **In the box:** Espressif recommends **15 mm clear in all directions** around the antenna. Keep
  **no metal, cable, gland body, bracket boss or screw** within 15 mm of the top edge across that
  48.5 mm span, or above and below it.
- **A plastic wall inside that zone is acceptable; metal is not.** That is why the box must be
  plastic. **[TO CONFIRM]** that the chosen box leaves the zone free of metal fittings.

## 3. Glands and the cable wall

**Seven glands on the bottom wall**, one per sheathed cable: feed A, front, rear (J4 + J5 are one
7-core cable), CAN, pod L, feed B, pod R. The pad row, cable sizes, sheathing rule and strain
relief are in `harness.md` §2. That is the authority; this section only adds the box's side.

- The tails span about 122 mm of a 140 mm edge, about 17 mm per gland on average. Glands that do
  not fit one row can go in two rows on the same wall: the tails are soldered wires, not panel
  connectors, so they fan out inside the box.
- Keep the CAN gland away from the two feed glands where the row allows.
- **[TO CONFIRM]** Gland sizes and cutout spacing, against the cables actually bought. The old
  M12/M16 figures belonged to the retired RGB, Denali and power runs.

## 4. Box selection

**[TO CONFIRM]** A polycarbonate or ABS box, IP67, with a gasketed lid and lid screws reachable
once installed. Criteria, in priority order:

1. Internal space for §1: 140 × 100 mm plus the service loop, and at least ~35 mm internal depth.
2. Plastic throughout, with no metal inserts in the antenna zone (§2).
3. A bottom wall that takes seven glands (§3).
4. Mounting bosses or a flat floor for four standoffs at the §1 hole pattern.
5. Fits the space under the fairing next to the charge board. **[TO CONFIRM]** by trial fit.

The Hammond 1554/1555 and Fibox MNX ranges reach this size class. **The exact part number and
internal dimensions still need a catalogue lookup.**

## 5. Pressure-equalisation vent

**[TO CONFIRM]** A breathable membrane vent (Gore type or equivalent), panel-mounted.

**It is not optional.** A sealed box that heats and cools pumps air past its seals and eventually
draws moisture *through* them. The vent equalises pressure while blocking liquid water, and is
what makes an IP67 rating hold for years rather than months.

Mount it on a sheltered face, **pointing downward or sideways**, never upward where standing water
collects on the membrane.

## 6. Mounting

- Box to frame: **rubber isolators** for vibration. With no plate, there is no thermal path to
  protect, so the isolators can go wherever is convenient.
- Bracket: steel or aluminium, stiff enough not to resonate, with no large unsupported spans, and
  kept clear of the antenna zone (§2).
- Orientation: glands and vent **downward or sideways**, never upward.
- Board to box: four M3 standoffs at the §1 hole pattern, at least 5 mm tall.

## 7. Conformal coating

**[TO CONFIRM]** Acrylic or silicone. Acrylic is easier to rework; silicone tolerates temperature
better and is kinder over thermal cycles.

**Mask before coating, every one of these:**

| Must be masked | Why |
|---|---|
| The wire-tail pads J1, J3, J4, J5, J8, J9, J10, J11 | Coating insulates; the wires are soldered after coating or need rework access |
| J2, the programming header | Needed for flashing |
| SW1 and SW2 | Coating inside a tactile switch stops it working |
| Test pads TP1–TP30 | Needed for bring-up and fault-finding |
| The antenna keep-out (§2) | Coating over the antenna detunes it |
| The vent | Coating would seal the membrane |

**J2 is wired for the MCCAN programmer, not an FTDI cable.** Pins 5 and 6 are `DTR` and `RTS`,
named for the auto-reset transistor pair Q2/Q3, and Q2's emitter is on `DTR`, the reverse of
Espressif's circuit. Any adapter other than the programmer board needs its DTR and RTS crossed
(adapter DTR → J2.6, adapter RTS → J2.5). See `bring-up.md` Stage 3.

## 8. Open items

| Item | Needed to close |
|---|---|
| Box part number and internal dimensions | Catalogue lookup against §1 and §4 |
| Gland sizes and cutout spacing | Gland datasheets, against the cables bought (`harness.md` §2) |
| Vent part number | Catalogue lookup |
| Coating material | Owner's choice (§7) |
| Standoff and bracket hardware | Follows the box choice |
| Real box temperature | Measured on the bike (`bring-up.md` Stage 8), against the 85 °C design ambient |

---

## 9. Thermal: no plate

**Decided in the layout spec (§6): no heat-spreader plate; copper alone carries the heat, at an
85 °C design ambient inside the box.** The box is an ordinary sealed plastic box. The tally that
confirms the decision (2026-11-14):

| Part | Loss | θJA used | Tj at 85 °C | Verdict |
|---|---|---|---|---|
| Q13, Q14 SQJ461EP (feed B reverse-polarity P-FETs, in parallel), each | 3.2² × 25.6 mΩ (16 mΩ × 1.6, hot) = **0.26 W** | 65 °C/W, datasheet PCB-mounted, not scaled down | **≈ 102 °C** | PASS |
| U14 BTS7008-2EPA (pod switch) | 2 × 3.2² × 16 mΩ (max, 150 °C) = 0.33 W | 30.9 K/W (JEDEC 2s2p); EP on the solid `VBAT_B` pours | ≈ 95 °C | PASS |
| U11–U13 TPS4HC120A | 4 × 0.08² × 250 mΩ (150 °C) = 6 mW per chip, plus quiescent (bounded at 10 mA × 14.4 V = 0.14 W, not read from the datasheet) | 32.1 °C/W | ≤ 90 °C | PASS |
| U1 LM5164 (3V3) | 1.65 W out at an assumed 80 % → 0.41 W (bound) | 43.4 °C/W | ≈ 103 °C | PASS |
| U2 LM5164 (5 V) | 0.5 W out at an assumed 75 % → 0.17 W | 43.4 °C/W | ≈ 92 °C | PASS |
| R100 33 mΩ | 0.87² × 33 mΩ = 25 mW of 1 W | — | — | PASS |
| Q10/Q11 IPT007N06N | 0.87² × 0.7 mΩ ≈ 0.5 mW each | — | — | PASS |
| D2 SMBJ24A, D25 SMBJ18A, D24 Zener | 0 in steady state (standoff above 14.4 V) | — | — | PASS |
| **Board total** | **≈ 1.4–1.6 W** | | | |

Loads behind the tally: pods 3.2 A each (6.4 A on feed B), signal channels ≤ 0.08 A, feed A
≤ 0.87 A, 3V3 ≤ 0.5 A (WiFi transmit peak taken as continuous), 5 V ≤ 0.1 A.

**Why two P-FETs.** One SQJ461EP carrying all 6.4 A loses 0.85–1.05 W once hot and reaches
128–153 °C: over the 125 °C line. Two in parallel share current well (R<sub>DS(on)</sub> rises
with temperature, so the hotter FET sheds current to the cooler one), and each sits near 102 °C.
The options not taken were an N-FET ideal diode, reinstating a plate, and lowering the design
ambient (65 °C still leaves one FET at about 125 °C).

**Check it on the bike** (`bring-up.md` Stage 7 and Stage 8): the bench rise of Q13/Q14 and the
real box temperature after a long ride on a warm day. If the box runs well below 85 °C, the
margin is larger than the tally shows.
