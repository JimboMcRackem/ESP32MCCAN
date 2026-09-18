# Schematic Review vs Spec

**Task 7, 2026-09-15.** Every spec requirement traced to the sheet and reference designator that
satisfies it, read back from the **exported netlist** rather than from the drawing.

Source of truth for the traces below: `hardware/output/netlist.net`, 166 nets, exported from
`mccan.kicad_sch` at commit-time. ERC gate after all fixes: **`--severity-all
--exit-code-violations` → exit=0, 0 errors, 0 warnings.**

**Result: 29 of 31 rows PASS. Three defects were found and fixed. One row is a spec-versus-design
divergence that needs a decision (F5), and one row passes on presence but carries an unbudgeted
thermal term (F4).**

---

## The checklist

| Spec | Requirement | Sheet / refdes | Verdict |
|---|---|---|---|
| 2.2 | Single populated feed; second feed is DNP footprints only, with no panel cutout | `power_input` J1/F1/Q1 — single feed correct. **No second-feed footprints exist.** | **See F5** |
| 4.1 | ONE panel fuse holder, 10 A, sized for the 7.8 A night case | `power_input` **F1**, 10 A, `FEED_P` → `FEED_FUSED` | **PASS** |
| 4.2 | P-FET reverse polarity, sized for 7.8 A (1.22 W at the 20 mΩ ceiling), Vgs clamped, gate network ≥ 1 MΩ | `power_input` **Q1 SQJ461EP** (was SQJ415EP — **F1**), **D1** 12 V Zener clamp, **R1 1 MΩ** to `GND_IN` | **PASS after F1** |
| 4.3 | 24 V TVS; all front-end parts ≥ 40 V | **D2 SMBJ24A**; Q1 now 60 V (**F1**). L1/L2/C1–C5 carry no part number or voltage rating — **O1, O5** | **PASS after F1** |
| 4.3 | π filter + CM choke on each feed | **L2** (CM choke) → **C1 / L1 / C2+C3+C4** (π). **R2/R3 were shorting both choke windings — F2.** | **PASS after F2** |
| 4.4 | Buck input from VLOGIC_IN; Schottky OR footprints present, second feed DNP | `VLOGIC_IN` ← **D3** ← `VBAT` → U1.2/U1.3 ✓. **Schottky OR is one diode, not a pair; no second feed.** | **See F5** |
| 5.1 | 12× discrete MOSFET, Vds ≥ 40 V, Id ≥ 0.5 A at Vgs ≤ 3.3 V from the output curve | **Q4–Q9**, NX5020UNBKS, 6 dual packages = 12 channels, 50 V, Rds(on) characterised **at Vgs 2.5 V** | **PASS** |
| 5.1 | ~~1 Ω~~ **10 Ω** shunt per channel; 12 `SENSE_*` into 16:1 mux in ChannelIndex order | **R52–R63 = 10 Ω**; `SENSE_*` → **R64–R75** → **U8** S1–S12 in order. *(Plan row says 1 Ω; spec §5.1 resized it to 10 Ω on 2026-09-13 — stale plan, see O6.)* | **PASS** |
| 5.1 | MUX_S0–S3 on GPIO 23/4/16/5 with pulldowns; RGB_ISNS on GPIO 32 (ADC1) | U5.37/26/27/29 = IO23/4/16/5 → U8.17/16/15/14; **R30–R33** pulldowns; `RGB_ISNS` U5.8 = **IO32** | **PASS** |
| 5.1 | NO SPI nets anywhere on the board | No MOSI / MISO / SCK / CS net exists in 166 nets | **PASS** |
| 6 | 5 V rail present, gated by EN_3V3SW (off in sleep), feeding ONLY TJA1042 VCC | **U2** LM5164 → `+5V`; `/+5V` reaches **U6.3 VCC and nothing else**; U2.3 EN on `EN_3V3SW` | **PASS** |
| 5.2 | 4× PTC on the per-string +24V feeds | **F2–F5** 1206L050/24 → `+24V_FL/FR/RL/RR`, one per corner | **PASS** |
| 5.3 | Dual PROFET from VBAT, ONE sense output to ISNS_DEN (GPIO 34) scaled for 3.3 A, DEN_DSEL on GPIO 33 | **U9.15 (EP) on `VBAT`**; IS → R82/R81/R83 → `ISNS_DEN` → U5.6 = **IO34**; `DEN_DSEL` U5.9 = **IO33** | **PASS** |
| 5.4 | Denali PWM from ESP32 LEDC on GPIO 18/19, NOT the PCA9685 | `PWM_DEN_A/B` ← **U5.30/31 = IO18/IO19**. U7 LED12–15 are no-connect flagged | **PASS** |
| 5.5 | PCA9685 LED0–11 in exact ChannelIndex order | LED0→`PWM_FL_R` … LED11→`PWM_RR_B`; FET *n* and mux address *n* match PWM channel *n* on all twelve | **PASS** |
| 6 | ~~Sync~~ **non-sync** boost VBAT → +24V, EN_BOOST with pulldown, ~~UVLO divider ≥ 1 MΩ~~ **direct GPIO enable** | **U3** LM51571-Q1 + **D4**; `VBAT`→L3→SW; **R20 100 kΩ** pulldown on `EN_BOOST`; U3.6 driven directly, **no divider** per spec §6. *(Plan row is stale — O6.)* | **PASS** |
| 6 | Low-Iq buck VLOGIC_IN → +3V3_ALW | **U1** LM5164 → `SW_3V3` → **L4** → `+3V3_ALW`; FB **R5 348 k / R6 200 k** = 548 kΩ (≥ 500 kΩ) | **PASS** |
| 3 | Load switch +3V3_ALW → +3V3_SW, EN_3V3SW with pulldown | **U4** DML3017LDC, VIN on `+3V3_ALW`, VOUT on `+3V3_SW`, EN on `EN_3V3SW`, **R19 100 kΩ** pulldown | **PASS** |
| 7.1 | ESP32-WROOM-32E-N8 (8 MB), onboard antenna variant | **U5**, value `ESP32-WROOM-32E-N8` | **PASS** |
| 7.2 | TXD 0 Ω link is DNP; TXD pulled recessive to VIO | **R23 0 Ω DNP** breaks `CAN_TXD` → U6.1; **R24 10 kΩ** from U6.1 to `+3V3_ALW` (= VIO) holds it recessive — **listen-only by construction** | **PASS** |
| 7.2 | 120 Ω terminator footprint present and UNPOPULATED | **R26 120 Ω DNP** across `CANH`/`CANL` | **PASS** |
| 7.2 | CAN CM choke + ESD protection | **L6** + **D6/D7** present as footprints. **Both are placeholder values — no part selected** (O5) | **PASS on presence** |
| 7.3 | Every GPIO matches the pin table exactly | All 19 checked pin-by-pin — table below | **PASS** |
| 7.3 | ISNS_DEN on GPIO 34 and RGB_ISNS on GPIO 32 (both ADC1); GPIO 39 spare; nothing analog on ADC2 | U5.6 = IO34, U5.8 = IO32; U5.5 = SENSOR_VN (**GPIO 39**) unconnected; ADC2 pins 0/2/4/12/13/14/15/25/26/27 carry **only digital nets** | **PASS** |
| 7.3 | CAN_STB on GPIO 14, pulled up to VIO | U5.13 = IO14 → U6.8 STB, **R25 10 kΩ** to `+3V3_ALW` (VIO) | **PASS** |
| 7.3 | All 14 PWM_* nets have pulldowns | 12 RGB: **R40–R51**. 2 Denali: **R86, R87** (added while resolving the PROFET). **14/14** | **PASS** |
| 7.4 | Prog header + DTR/RTS auto-reset + BOOT/EN buttons | **J2** 6-way; **Q2** (E=DTR, B←R28←RTS, C=`EN_MCU`) and **Q3** (E=RTS, B←R29←DTR, C=`BOOT_N`); **SW1** BOOT, **SW2** EN | **PASS** |
| 8.3 | Ignition-sense divider present, DNP | **R37 90.9 k / R38 33 k, both DNP**; **R39 100 kΩ POPULATED** (the §7.3 C2 requirement); **D8** clamp | **PASS** |
| 9.1 | **Seven** populated connectors + vent + one fuse holder = **nine** penetrations | J1 PWR (3-way), J3–J6 corners, J7 Denali, J8 CAN = **7**. J2 is internal. F1 + vent = **9**. | **PASS** |
| 9.2 | Corner connectors assigned distinct keying/colours | J3 key A/black, J4 key B/grey, J5 key C/brown, J6 key D/natural — carried in each Value field | **PASS** |
| 10 | DNP snubber footprints on the 12 outputs | **R88–R99 + C49–C60**, all DNP, one RC per `RET_*` | **PASS** |

### GPIO table, read back pin by pin

| Spec function | Spec GPIO | Netlist | |
|---|---|---|---|
| CAN RX | 35 | U5.7 `IO35` ← `CAN_RXD` | ✓ |
| Ignition sense | 36 | U5.4 `SENSOR_VP` ← `IGN_SENSE` | ✓ |
| CAN TX | 17 | U5.28 `IO17` → `CAN_TXD` | ✓ |
| I²C SDA / SCL | 21 / 22 | U5.33 `IO21`, U5.36 `IO22` | ✓ |
| Denali A / B PWM | 18 / 19 | U5.30 `IO18`, U5.31 `IO19` | ✓ |
| Denali sense | 34 | U5.6 `IO34` | ✓ |
| `DEN_DSEL` | 33 | U5.9 `IO33` | ✓ |
| RGB sense | 32 | U5.8 `IO32` | ✓ |
| Mux S0–S3 | 23 / 4 / 16 / 5 | U5.37, U5.26, U5.27, U5.29 | ✓ |
| Boost enable | 25 | U5.10 `IO25` | ✓ |
| `EN_3V3SW` | 26 | U5.11 `IO26` | ✓ |
| PROFET diag enable | 27 | U5.12 `IO27` | ✓ |
| Status LED | 13 | U5.16 `IO13` | ✓ |
| CAN STB | 14 | U5.13 `IO14` | ✓ |
| Programming | 0, 1, 3, EN | U5.25, U5.35, U5.34, U5.3 | ✓ |
| Spare | 2, 12, 15, 39 | U5.24 NC, U5.14 (pulldown only), U5.23 NC, U5.5 NC | ✓ |

---

## F1 — Q1 carried the superseded part number *(FIXED)*

`layout_power_input.py` set Q1's value to **SQJ415EP**. That part was **replaced by the SQJ461EP on
2026-09-13** and the replacement is recorded in `part-selection.md` ("Two selections that fixed
specific defects"), in the final selections table, and in spec §9.4's thermal row — but never
reached the schematic.

This is not cosmetic. The SQJ415EP is a **40 V** part, and it was replaced *because* the SMBJ24A's
measured clamp is **38.9 V**, leaving **1.1 V (2.8%)** of margin on the one device that sees every
transient the vehicle produces. The SQJ461EP's 60 V gives **21.1 V (54%)**.

Anyone reading the schematic — or building a BOM from it — would have ordered the wrong FET, and
the board would have worked perfectly until the first real transient.

**Fixed:** Q1 → `SQJ461EP`. Same PowerPAK SO-8L footprint, so nothing else changes.

### And the open question about its gate drive is now closed

`part-selection.md` left this open: *"16 mΩ is the −10 V column; the −4.5 V column is 21 mΩ, slightly
above the ≤ 20 mΩ ceiling. Confirm at schematic review rather than assuming it."*

Traced: D1 (12 V Zener) has its cathode on `VBAT_PROT` and its anode on `Q1_G`; R1 (1 MΩ) runs from
`Q1_G` to `GND_IN`. At a 12.6 V rail the gate sits between 0 V and ~1.6 V, so **Vgs is −11 to
−12.6 V**. That is comfortably past −10 V, so **the 16 mΩ column applies** and the 0.78 W night
figure in §9.4 stands. At a 14.4 V rail Vgs reaches about −13 V, still inside the ±20 V rating.

---

## F2 — the common-mode choke was shorted out in the BOM *(FIXED)*

`power_input` carries **R2 and R3, two 0 Ω links that short winding A and winding B of L2**. They
are the deliberate *alternative* build — links give the simple tied-ground case for a first
prototype — and the sheet note says so explicitly: *"Fit EITHER L2 OR R2+R3, never both."*

**Neither was marked DNP.** A BOM generated from this schematic would have stuffed the choke and
both links, and the links win: L2 becomes a decorative part with a wire across each winding.

The consequence is the exact failure §4.3 warns about at length — **the board works perfectly and
filters nothing**, the split between `GND_IN` and `GND` collapses, and **no ERC or DRC check says
a word**. It would have surfaced, if at all, as an unexplained EMC failure late in the programme.

**Fixed:** `DNP = {"R2", "R3"}` in `layout_power_input.py`, and `gen_power_input.py` taught to emit
`(dnp yes)`. The choke is the populated option, as §4.3 requires. The links keep their footprints,
so the tied-ground fallback is still a stuff option.

---

## F3 — the 24 V feedback divider was drawing more in sleep than everything else combined *(FIXED)*

**R12 (115 kΩ) + R13 (4.99 kΩ) = 120 kΩ from `+24V` to GND, and it conducts in deep sleep.**

With the boost disabled, `+24V` does not fall to zero. A boost converter's inductor and rectifier
form a DC path from the input: `VBAT` → **L3** → **D4** → `+24V`. The node therefore sits at about
**12.35 V** whenever the battery is connected, and the divider draws

> (12.6 − 0.25) / 120 kΩ = **103 µA**

**That row does not exist in the spec §8.2 budget.** It is larger than every other contributor put
together, and it is the same class of omission that correction C3 already caught once on this
project — an external divider on a rail that stays powered, invisible to the controller's own
quoted I<sub>Q</sub>.

| | typ | max |
|---|---|---|
| §8.2 as written | ~85 µA | ~100 µA |
| **What would actually have been built** | **~176 µA** | **~193 µA** |
| Target | < 200 µA | < 200 µA |

It would have **passed** — by 3.5% — while the documented budget was wrong by a factor of two. A
board drawing 193 µA against a predicted 100 µA is exactly the kind of thing that gets chased for
days at bring-up.

**Fixed:** **R12 → 576 kΩ, R13 → 24.9 kΩ.** Same ratio (24.13 V against 24.05 V, a 0.3% shift,
immaterial to an LED strip), five times the impedance:

> (12.6 − 0.25) / 601 kΩ = **20.5 µA**

**Revised sleep budget (topology B):**

| Contributor | typ | max |
|---|---|---|
| ESP32 deep sleep + EXT0 | 10 | 10 |
| CAN transceiver standby | 19 | 19 |
| 3.3 V buck I<sub>Q</sub> (one instance) | 10.5 | 25 |
| PROFET standby | 0.6 | 0.6 |
| RGB FET leakage, 12 × | 12 | 12 |
| P-FET gate network (R1 = 1 MΩ) | 12.6 | 12.6 |
| Boost BIAS shutdown | 2.6 | **5** (was budgeted at typ — **O2**) |
| 3.3 V buck FB divider (548 kΩ) | 6.0 | 6.0 |
| **24 V boost FB divider (601 kΩ)** | **20.5** | **20.5** |
| **Total** | **~94 µA** | **~111 µA** |

Comfortably inside the 200 µA target again, with the largest contributor now named.

**One consequence, mitigated.** A higher divider means a higher FB node impedance —
576 k ∥ 24.9 k = **23.9 kΩ** — so stray capacitance forms a pole nearer the loop crossover than
before. It should still sit far above it (≈ 666 kHz against a crossover well under 150 kHz, bounded
by the 439 kHz right-half-plane zero), but if bring-up says otherwise the remedy is a feedforward
capacitor across R12. **C61, 10 pF, DNP** is now fitted as a footprint — the difference between a
stuff option and a respin.

---

## F4 — the input filter's series elements have no thermal budget and no DCR ceiling *(OPEN — constraint now specified)*

Row 4.3 passes on presence: the π filter and CM choke are both there. But **L1 and L2 sit in the
main feed path and carry the entire load current**, and neither §9.4's thermal table nor
`part-selection.md` has a row for them. Both are also **unselected parts** — L1 is "10uH" and L2 is
"CM choke", with no manufacturer, no DCR and no current rating.

At the governing night load of **7.0 A**, plausible DCRs are not a rounding error:

| Element | DCR assumed | Loss at 7.0 A |
|---|---|---|
| L1, 10 µH rated ≥ 8 A | 10–20 mΩ | 0.49–0.98 W |
| L2, both windings (out and back) | 2 × 5–10 mΩ | 0.49–0.98 W |
| **Together** | | **1.0–2.0 W** |

Against a night total of **~1.8 W**, that is a doubling. The ≥ 150 cm² flat plate in §9.4 was sized
at 1.9 W for a 16 K rise; at ~3.5 W it would run ~30 K and miss the 65 °C internal target.

**This is a part-selection constraint, not a wiring defect, so the schematic is unchanged.** What
the review can fix is that the constraint was nowhere stated. It now is:

> **Requirement (new): the total series resistance of L1 plus both windings of L2 must not exceed
> 22 mΩ.** That holds the pair to ~1.1 W at 7.0 A, which keeps the night total near 2.9 W — the most
> a 150 cm² flat plate absorbs while still meeting the 65 °C internal target at 40 °C ambient.
> Budget it as **L1 ≤ 8 mΩ** and **L2 ≤ 7 mΩ per winding**.

**Recommendation: reconsider L1 = 10 µH.** 10 µH at 8 A is a physically large, lossy part. The
filter's job is to attenuate the 400 kHz bucks and the 2.2 MHz boost, and with C3 = 220 µF the LC
corner is already at 3.4 kHz — about **83 dB** of attenuation at 400 kHz. Dropping L1 to **2.2 µH**
moves the corner to 7.2 kHz and still gives **~70 dB**, while shrinking the part and its DCR
several-fold. Flag this at the EMI pre-scan (spec §10) rather than treating 10 µH as settled.

---

## F5 — the second feed's DNP footprints do not exist *(OPEN — needs a decision)*

Spec **§4.4 is explicit**: *"The second feed's board footprints are retained and left unpopulated —
connector position, P-FET stage and the Schottky OR — so the domain split below can be restored by
populating parts, not by respinning the board."* §2.2 repeats it, and the plan's Task 3 Steps 3–5
called for it.

**None of it is in the schematic.** There is one feed, one fuse, one P-FET stage, one π filter, and
**D3 is a single Schottky, not an OR pair**. `VBAT_B` exists nowhere in the 166 nets.

This is a divergence between spec and design, and it has two legitimate resolutions — the choice is
yours, not mine:

**(a) Build it.** Roughly 15 DNP parts on `power_input`: a second connector footprint, fuse, P-FET,
Zener, gate resistor, TVS, choke, π filter and the second OR diode. Preserves the §4.4 upgrade path
exactly as written. Costs board area on a design that has to fit an enclosure with a flat
heat-spreader plate, and adds a second high-current footprint that will never be populated on the
reference bike.

**(b) Amend §4.4 to drop it — my recommendation.** The load analysis that retired the dual feed is
solid and has held through two reversals: night draws 7.0 A of a 10 A feed, and §2.4's operating
modes are owner-confirmed rather than assumed. More to the point, **the design has moved on**: J1 is
now a **3-way** connector carrying `IGN_IN` for the topology-B battery-feed case (§8.1a), which is a
different and better answer to "what if the supply arrangement changes". Carrying unpopulated
copper for a superseded contingency, on a board whose area is thermally constrained, buys less than
it costs.

Either way the spec and the schematic must be made to agree before Task 8 commits to an outline.

---

## Observations — not failures, but they should not stay unwritten

**O1 — no capacitor carries a voltage rating or dielectric.** Every `C*` value on the board is bare
capacitance. Two places where that is load-bearing rather than tidy-up:

- **C3, 220 µF electrolytic on `VBAT`** must be ≥ 50 V to survive the 38.9 V TVS clamp. A 25 V part
  fits the same footprint and fails on the first transient.
- **C20–C22, 4.7 µF on `+24V`.** If these are X7R, **DC-bias derating at 24 V typically leaves
  40–60% of the nameplate** — so the boost's output capacitance may be ~6–8 µF, not 14.1 µF. That
  needs checking against the LM51571's ripple and loop requirements before the BOM freezes.

**O2 — boost shutdown current was budgeted at typical.** Table 8.5 of the LM51571 datasheet gives
I<sub>SHUTDOWN(BIAS)</sub> = 2.6 µA **typ / 5 µA max**; §8.2 carries "≤ 2.6 µA" in both columns.
Corrected in the F3 table above. 2.4 µA — immaterial, but the max column should be a max.

**O3 — the two ADC channels run at different attenuations, and firmware needs to know.** This is a
firmware-visible contract that appears in no single place:

| Net | GPIO | Full-scale signal | Attenuation | Settling |
|---|---|---|---|---|
| `RGB_ISNS` | 32 | 267 mV (10 Ω × 26.7 mA) | **0 dB** (0–1.1 V), per §5.1 | ≥ 500 µs after a mux step (C44, τ = 100 µs) |
| `ISNS_DEN` | 34 | 1.34 V (2.2 kΩ × 611 µA) | **11 dB** (0.15–2.45 V) | ≥ 250 µs after a DSEL change (C48, τ = 47 µs) |

Setting one attenuation for both would put the RGB chain at 11% of scale or saturate the PROFET
chain. Carry this into the firmware plan for §12.

**O4 — §2.3 and the built design disagree on per-channel current.** The spec says **~33 mA**, the
schematic and `part-selection.md` are built to **26.7 mA** (267 mV across 10 Ω). Both derive from an
*assumed* strip figure, and §2.2 already flags it as "assumed, not measured". Harmless — it only
scales the sense reading, and the open/working/shorted classification is unaffected — but the two
documents should be reconciled once the strips are measured.

**O5 — parts with no manufacturer part number.** See the table in the next section.

**O6 — several plan checklist rows are stale against the current spec.** Recorded here so nobody
"fixes" the schematic to match them: **1 Ω shunt** (spec §5.1 resized it to 10 Ω on 2026-09-13);
**synchronous boost** (the LM51571-Q1 is non-synchronous by selection); **UVLO divider ≥ 1 MΩ**
(§6 removed the divider entirely — the pin is driven straight from the GPIO); **PWR connector 2-way**
(now 3-way, carrying `IGN_IN` per §8.1a). The schematic is right and the plan text is behind.

---

## What is still needed from outside the project

### Datasheets

| Priority | Part | Why it is needed |
|---|---|---|
| **Blocking Task 8** | **CAN common-mode choke** (L6) — *no part selected* | Value is a placeholder "51 µH". Needs a CAN-rated part with a real footprint and a current rating. Typical candidates: TDK ACT45B-101-2P, Würth 744232101, Murata DLW43SH101XK2 |
| **Blocking Task 8** | **CAN bus ESD/TVS** (D6, D7) — *no part selected* | Placeholder "24 V bidir". A single dual-line CAN protector is preferable to two discretes — e.g. NXP PESD2CAN, Nexperia PESD1CAN, ON NUP2105L |
| **Blocking Task 8** | **Input π-filter inductor L1** and **input CM choke L2** — *no parts selected* | Both carry the **full 7.0 A**. Needed to close **F4** — the 22 mΩ total DCR ceiling cannot be verified without real parts |
| **Blocking Task 8** | **Buck inductors L4 / L5** ("22 µH") — *no parts selected* | Need shielded, AEC-Q200, Isat ≥ 1.5 A, with a footprint |
| High | **NXP PCA9685** (U7) | **Not held locally at all**, despite being a fitted part. Needed to confirm EXTCLK handling when unused (it is currently tied to GND), the A0–A5 address strapping, `~OE` behaviour and the output ratings |
| High | **Espressif ESP32 Hardware Design Guidelines** | The EN reset RC (**R22 10 kΩ / C37 1 µF**) is recorded as **UNVERIFIED** in `part-selection.md`. Espressif specifies this network; it should not be guessed |
| High | **ESP32-WROOM-32E-N8 module datasheet** | For the module footprint, the antenna keep-out zone (a layout constraint, not just a part fact) and a final pin-table cross-check |
| Medium | **BAT54** (D8–D21, fourteen of them) | Needed to confirm V<sub>F</sub> at the clamp point and, more importantly, **reverse leakage at 3.3 V over temperature** — twelve of these sit across the RGB sense nodes, where leakage biases the reading |
| Medium | **D1 12 V Zener**, **D3 40 V Schottky**, **C3 220 µF**, **F1 blade fuse holder** | No part numbers; needed for the BOM and for footprints |
| Low | **MMBT3904** (Q2, Q3) | Generic, jellybean; any vendor's datasheet will do |

### 3D models

Nothing in the project has a footprint yet, so no 3D model is *needed* until Task 8 assigns them —
KiCad's own libraries ship STEP models for every standard passive, SOIC, WQFN, TSSOP and SOT
package here, including `Package_SO:Infineon_PG-TSDSO-14-22`. The models worth sourcing yourself are
the ones KiCad cannot have, and they matter because the enclosure and panel layout (§9) depend on
real geometry:

| Model | Why it matters |
|---|---|
| **ESP32-WROOM-32E module** | Tall, and its antenna end dictates a keep-out plus board-edge placement. Espressif publish a STEP model |
| **TE Superseal 1.0 connectors** — 4-way (J3–J6) and 2-way (J8) | Panel penetration positions and mating clearance (§9.1). TE publish STEP models per part number |
| **TE Superseal 1.5 connectors** — 3-way (J1 PWR, J7 Denali) | Same |
| **Panel-mount ATO/ATC fuse holder** (F1) | One of the nine penetrations; needs a real body and cap-clearance envelope |
| **Enclosure and the ≥ 150 cm² heat-spreader plate** | Not a component model, but the plate's fit and the gap-pad stack-up to Q1, U3 and U9 need real geometry before Task 8 places those parts |
| **L1, L2, L4, L5, L6** | Once chosen (see above) — L1 and L2 in particular may be large enough to drive the board outline |

---

## Verification after the fixes

```
kicad-cli sch erc --severity-all --exit-code-violations -o output/erc.rpt mccan.kicad_sch
exit=0     ERC messages: 0   Errors 0   Warnings 0
```

**166 nets**, unchanged by the three fixes — C61 joined `+24V` and `FB_24V` rather than creating a
net, and the DNP flags are BOM attributes, not connectivity.

DNP set, read back from the netlist — **31 parts**: R2, R3 (choke links, **new**), R23 (TXD link),
R26 (terminator), R37, R38 (ignition divider), R88–R99 + C49–C60 (output snubbers), C61 (boost Cff,
**new**).

Designators remain gapless: **R1–R99, C1–C61, D1–D21, Q1–Q9, U1–U9, J1–J8, F1–F5, L1–L6, SW1–SW2.**

All six generators re-run and idempotent.

---

## Sign-off

**Rows 1–31: 29 PASS, 2 carried forward (F4 constraint recorded, F5 awaiting a decision).**

Task 8 must not start on the outline until **F5** is resolved, since it determines the board area
`power_input` needs, and should not freeze the BOM until **F4**'s two inductors are chosen against
the 22 mΩ ceiling.
