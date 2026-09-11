# Part Selection Verification Record

Every criterion below comes from the spec. A part may be chosen ONLY if every
row for it reads PASS. Candidate families are suggestions, not decisions.

## 1. RGB output stage (REVISED 2026-09-11) — discrete MOSFET + sense chain
Replaces the octal smart low-side switches, whose row 1.1 failed category-wide
(the full superseded verification record is preserved in the Appendix at the end
of this file — it is the evidence for why the design changed). Three part classes
are verified here: the FET, the sense resistor, the analog mux. 1 ohm x 0.14 A =
140 mV at full channel current, read at 0 dB ADC attenuation (0-1.1 V range).
Classification is open (~0 mV) / working (~140 mV) / shorted (saturated) — this is
**not** precision current metering.

### 1a. Logic-level N-MOSFET (12 required)
Candidate evaluated in full: **Nexperia PMV60ENEA** (40 V N-channel TrenchMOS,
SOT23 / TO-236AB, Product data sheet, 9 May 2019). Screened as alternatives:
Vishay SQS400EN (automotive 40 V, PowerPAK 1212-8, Rev. D 31-Oct-11) and ROHM
RSF015N06FRA ("4 V-drive" 60 V automotive) — see screening table below.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1a.1 | Vds >= 40 V (24 V rail plus transients) | Datasheet Section 4 "Quick reference data" Table 1 and Section 8 "Limiting values" Table 5: "VDS drain-source voltage — 40 V" (Tj = 25 degC). | **PASS** — meets the 40 V threshold exactly. Note: zero margin beyond the 40 V figure itself; the TVS clamp voltage (row 6.2, out of this section's scope) must settle below 40 V for this to hold in practice. |
| 1a.2 | **Fully enhanced at Vgs = 3.3 V** — Rds(on) specified AT or BELOW 3.3 V Vgs, not only at 4.5/10 V | Section 10 "Characteristics" Table 7 gives RDSon at exactly two gate drives: "VGS = 10 V; ID = 3 A; Tj = 25 degC — 60 / 75 mOhm" (typ/max) and "VGS = 4.5 V; ID = 2.6 A; Tj = 25 degC — 75 / 99 mOhm" (typ/max). No row exists at VGS <= 3.3 V. Fig. 8 ("RDSon vs ID") and Fig. 9 ("RDSon vs VGS") plot typical-only curves down to VGS = 2.4 V, but these are explicitly "typical values", not a guaranteed min/max specification — reading a number off them would not be a verified figure. Table 7 also gives VGSth (gate threshold) = 1 / 1.6 / 2.5 V (min/typ/max at Tj = 25 degC): a worst-case unit needs only 0.8 V of overdrive above threshold to reach 3.3 V Vgs, and the datasheet does not state what RDSon that corresponds to. | **FAIL** — RDSon is characterized at 4.5 V and 10 V only, exactly the gap the task brief warned about. Not verified for a 3.3 V PCA9685 gate drive. |
| 1a.3 | Id >= 1 A continuous | Table 1 / Table 5: "ID drain current VGS = 10 V; Tamb = 25 degC — 3 A"; "VGS = 10 V; Tamb = 100 degC — 2.1 A". | **PASS** — 3 A at 25 degC ambient, 2.1 A at 100 degC ambient, vs 1 A required (>=2x margin even hot). |
| 1a.4 | Rds(on) at 3.3 V Vgs gives <= 5 mW per channel at 0.14 A | Cannot be computed: no RDSon figure exists at VGS = 3.3 V (see 1a.2). Using the 4.5 V max figure (99 mOhm at ID = 2.6 A, Tj = 25 degC) as a stand-in gives 0.14^2 x 0.099 = 1.94 mW, which would pass — but RDSon at 3.3 V Vgs is known to be higher than at 4.5 V (Fig. 8/Fig. 9 show a step increase in RDSon as VGS drops below ~3.5 V), so the 4.5 V number is not a valid stand-in for 3.3 V operation. | **UNVERIFIED** — depends on the unresolved 1a.2 figure. Closing this needs either a bench RDSon measurement at VGS = 3.3 V, or a part with that figure in its datasheet. |
| 1a.5 | Gate charge low enough to switch cleanly at 400 Hz from a PCA9685 output (25 mA sink / 10 mA source) | Table 7 "Dynamic characteristics": "QG(tot) total gate charge — VGS = 10 V; VDS = 20 V; ID = 3 A; Tj = 25 degC — 3.6 / 5 nC" (typ/max). Charging to only 3.3 V requires less charge than this 10 V-referenced figure, so 5 nC max is a conservative (larger) upper bound. At the PCA9685's weaker drive current (10 mA source), charge time = 5 nC / 10 mA = 0.5 microseconds. | **PASS** — 0.5 us vs a 2.5 ms period at 400 Hz is 0.02% of the period; trivial margin regardless of the 3.3 V uncertainty in 1a.2/1a.4. |
| 1a.6 | In stock, multi-source | Digi-Key product page for PMV60ENEAR (fetched 2026-09-12): 0 units in stock, "3,000 expected in stock on 18-Jan-2027", unit price $0.54 (qty 1), lifecycle status "Active". TTI (via distributor search result, not independently opened): approx. 9,000 units in stock, price $0.074-$0.094 depending on quantity, ~10-week lead time for further stock. Single manufacturer part number (Nexperia); no second-source exact equivalent was checked. | **UNVERIFIED** — the part is Active and buildable in volume (TTI stock, quoted pricing), but the near-term single-unit-buy picture at Digi-Key is a backorder to Jan 2027. A human needs to check Mouser/Arrow/LCSC directly, confirm the TTI stock figure first-hand, and decide whether that lead time is acceptable or a second-source pin-compatible SOT23 N-channel MOSFET is needed. |

### Candidate screening for 1a

| Candidate | Outcome | Evidence |
|---|---|---|
| **Nexperia PMV60ENEA** | Best fit found; fails 1a.2/1a.4 (unverified at 3.3 V), rest PASS | Full datasheet verified — see table above. |
| **Vishay SQS400EN** | Same gap as PMV60ENEA | Datasheet Rev. D, 31-Oct-11, verified locally. Specifications table p.2: RDSon tabulated only at "VGS = 10 V; ID = 12 A" (13/18 mOhm typ/max) and "VGS = 4.5 V; ID = 9 A" (21/32 mOhm typ/max) — no VGS <= 3.3 V row. p.3 "On-Resistance vs. Gate-to-Source Voltage" is a typical-only graph reading down to ~2 V, not a guaranteed spec. VDS = 40 V, ID = 16 A — oversized for a 0.14 A load but does not close the 3.3 V gap. |
| **ROHM RSF015N06FRA** | Closer nominal drive voltage, still short of the criterion | Product-page search result: "4 V-drive type" N-channel, VDS = 60 V, ID = 1.5 A, RDSon typ 0.24-0.255 Ohm at VGS = 4-4.5 V, 0.21 Ohm at VGS = 10 V. Full PDF datasheet was not fetched (search-result data only). Even its "4 V-drive" spec sits above the 3.3 V PCA9685 output, and its RDSon is roughly 3x higher than PMV60ENEA's — not pursued further. |

No candidate found in this search satisfies 1a.2 as a *tabulated* spec. This
mirrors the task brief's warning: most 40 V-class logic-level/automotive
N-MOSFETs characterize RDSon at 4.5 V and 10 V, not at or below 3.3 V. Options for
a human to close this, in order of preference: (a) bench-characterize
PMV60ENEA's RDSon at VGS = 3.3 V directly — its 4.5 V number (75-99 mOhm) is
already far below the 5 mW/channel budget, so a real measurement may well still
pass; (b) add a small gate-drive level shifter so the FETs see 5 V instead of
3.3 V, which immediately satisfies 1a.2 against the existing 4.5 V spec; or
(c) continue the part search for a dedicated 2.5 V/1.8 V-gate-drive part rated
>= 40 V (only two families were checked here before the effort cap).

### 1b. Sense resistor (12 required)
| # | Required | Actual | Verdict |
|---|---|---|---|
| 1b.1 | 1 ohm, tolerance <= 1% (tolerance sets channel-to-channel reading spread) | | |
| 1b.2 | Power rating >= 50 mW with margin (dissipates 20 mW at 0.14 A) | | |
| 1b.3 | Temperature coefficient low enough that drift does not swamp open/working/short classification | | |

### 1c. 16-channel analog multiplexer (1 required)
Candidates: CD74HC4067, ADG706, MAX4617 family
| # | Required | Actual | Verdict |
|---|---|---|---|
| 1c.1 | 16 channels, single-ended, 4 binary select lines | | |
| 1c.2 | Operates from 3.3 V | | |
| 1c.3 | **On-resistance low enough not to corrupt a 140 mV reading** into the ESP32 ADC's input impedance | | |
| 1c.4 | Off-channel leakage small enough not to shift a 140 mV reading measurably | | |
| 1c.5 | Channel-to-channel on-resistance match (mismatch appears as per-channel offset) | | |
| 1c.6 | Settling time permits stepping 12 channels within a few ms sweep | | |

## 2. Dual smart high-side switch (1 required) — Denali
Candidate: Infineon BTS7008-2EPA or PROFET+2 12V family

| # | Required | Actual | Verdict |
|---|---|---|---|
| 2.1 | Continuous current per channel >= 3.3 A with margin | | |
| 2.2 | Current sense output resolves a 3.3 A load, ratio documented | | |
| 2.3 | 3.3 V logic compatible inputs (no level shifter needed) | | |
| 2.4 | PWM capable at 150 Hz | | |
| 2.5 | Integrated short-circuit, overcurrent, thermal shutdown | | |
| 2.6 | On-resistance gives <= 0.25 W for the pair at 3.3 A each | | |
| 2.7 | Standby current <= 20 uA | | |

## 3. Synchronous boost controller — 12 V to 24 V, 60 W
Candidate: TI LM5122-Q1

| # | Required | Actual | Verdict |
|---|---|---|---|
| 3.1 | Input rating 40-60 V (must exceed the 24 V TVS clamp voltage) | | |
| 3.2 | Synchronous (external FETs), efficiency >= 94% at 40 W out | | |
| 3.3 | Enable pin, 3.3 V logic compatible | | |
| 3.4 | Spread-spectrum or frequency dither available | | |
| 3.5 | Disabled-state current draw <= 10 uA, or gated externally | | |
| 3.6 | Dissipation at 40 W out <= 3 W including both FETs | | |

## 4. Low-quiescent buck — 12 V to 3.3 V, 1 A
Candidate: TI LM5164

| # | Required | Actual | Verdict |
|---|---|---|---|
| 4.1 | Quiescent current <= 30 uA (this is the dominant sleep contributor) | | |
| 4.2 | Output current >= 1 A (ESP32 WiFi TX peaks ~500 mA) | | |
| 4.3 | Input rating 40-60 V | | |
| 4.4 | Stable with no load (sleep condition) | | |

## 5. CAN transceiver
Candidate: NXP TJA1042T/3

Verified against **NXP TJA1042 Product data sheet Rev. 8, 15 January 2015**
(TJA1042T/3/1J, TJA1042T/1J, TJA1042TK/3/1J). nxp.com/docs blocks automated
fetch; the identical document was obtained from the Farnell mirror
(farnell.com/datasheets/1923816.pdf). Rev. 11 (16 January 2023) exists on
nxp.com and was not read — a human should diff the four parameters below
against Rev. 11 before the board order.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 5.1 | **GO/NO-GO:** standby mode signals bus wake-up by driving RXD LOW | **Yes.** Table 4 "Operating modes" p.5: Standby = pin STB HIGH, pin **RXD LOW = "wake-up request detected"**, RXD HIGH = "no wake-up request detected". §7.1.2 Standby mode p.5, verbatim: "only a low-power differential receiver monitors the bus lines for activity. The wake-up filter on the output of the low-power receiver does not latch bus dominant states, but ensures that only bus dominant and bus recessive states that persist longer than tfltr(wake)bus are reflected on pin RXD. … The low-power receiver is supplied by VIO, and is capable of detecting CAN bus activity even if VIO is the only supply voltage available. **When pin RXD goes LOW to signal a wake-up request**, a transition to Normal mode will not be triggered until STB is forced LOW." Timing, Table 8 p.12: tfltr(wake)bus (versions with VIO pin, Standby mode) **0.5 / 1.5 / 5 us**; td(stb-norm) standby-to-normal delay 7 / 25 / 47 us. | **PASS** — RXD is actively driven LOW on a filtered bus-dominant while in Standby, which is exactly the edge/level an ESP32 EXT0 wake needs, and it works on VIO alone (VCC may be off). **Two constraints to design to:** (a) §7.2.2 p.5 bus dominant time-out — "If the dominant state on the bus persists for longer than **tto(dom)bus**, the RXD pin is reset to HIGH", tto(dom)bus = 0.3 / 2 / 5 ms (Table 8 p.12), so the LOW is guaranteed for at least 0.3 ms but is **not latched** indefinitely; (b) RXD is not open-drain — IOL 2 / 5 / 12 mA, IOH −8 / −3 / −1 mA (Table 7 p.10) — so it must wake the ESP32 on level/edge, not be wire-ORed. |
| 5.2 | VIO pin for 3.3 V logic (the /3 suffix) | §7.3 p.8: "Pin 5 is either a SPLIT output pin or a VIO supply pin"; §7.3.2 p.8: "Pin VIO on the TJA1042T/3 and TJA1042TK/3 should be connected to the microcontroller supply voltage. This sets the signal levels of pins TXD, RXD and STB to the I/O levels of the microcontroller." §2 p.1: "VIO input on TJA1042T/3 and TJA1042TK/3 allows for direct interfacing with **3 V to 5 V** microcontrollers." Table 7 p.10: "VIO supply voltage on pin VIO **2.8 … 5.5 V**"; "Vuvd(VIO) undervoltage detection voltage on pin VIO 1.3 / 2.0 / **2.7 V**". Logic thresholds referenced to VIO: VIH 0.7xVIO min, VIL 0.3xVIO max (pins STB and TXD, Table 7 p.10). | **PASS** — 3.3 V sits inside the 2.8-5.5 V VIO window with 0.6 V above the 2.7 V max undervoltage-detect level; no level shifter needed on TXD/RXD/STB. |
| 5.3 | Standby current <= 20 uA | Table 7 p.10, Standby mode: "ICC supply current — Standby mode — **TJA1042T/3 or TJA1042TK/3: max 5 uA**" (the TJA1042T row, which "includes IIO", is typ 10 / max 15 uA). "IIO supply current on pin VIO — Standby mode; VTXD = VIO: **5 / – / 14 uA**" (column extraction reads min 5, typ –, max 14; the max of 14 uA is unambiguous). For the /3 part the two rails are separate, so worst-case standby = **5 + 14 = 19 uA max** over Tvj = −40 to +150 C. §7.2.3 p.5 condition: "Pins TXD and STB have internal pull-ups to VIO … **both pins should be held HIGH in Standby mode to minimize standby current**" — the datasheet's standby figures are specified at VTXD = VIO, so firmware must leave TXD and STB high through deep sleep. | **PASS, but with no margin** — 19 uA max vs the 20 uA criterion (95% of it). Against the whole-board target of <200 uA this is ~10% of budget. Note the figure is split across two rails: 5 uA from the 5 V VCC and 14 uA from the 3.3 V VIO. |
| 5.4 | TXD can be left pulled to VIO (recessive) with no fault latch | §7.2.3 p.5: "Pins TXD and STB have **internal pull-ups to VIO** to ensure a safe, defined state in case one or both of these pins are left floating." §7.2.1 p.5, TXD dominant time-out: "A 'TXD dominant time-out' timer is **started when pin TXD is set LOW** … The TXD dominant time-out timer is **reset when pin TXD is set to HIGH**." TXD HIGH is the recessive state, so the time-out never starts. Table 7 p.10: IIH at VTXD = VIO is −1 / – / +5 uA (vs IIL typ −150 / max −30 uA at VTXD = 0 V), i.e. holding TXD high also costs essentially nothing. There is no latched-fault or error-flag pin on this device at all (no ERR_N / EN pins — pin list §6 p.4 is TXD, GND, VCC, RXD, VIO or SPLIT, CANL, CANH, STB). | **PASS** — TXD at VIO is the intended idle state, it starts no timer and latches no fault, and it is also the condition under which the standby current of row 5.3 is specified. |

### Additional finding (not a listed criterion)

TJA1042 requires **VCC = 4.5 … 5.5 V** (Table 7 p.10), with Vuvd(VCC) 3.5 / – / 4.5 V
and §7.2.4 p.5: "Should VCC drop below the VCC undervoltage detection level,
Vuvd(VCC), the transceiver will switch to Standby mode." The design context lists
only a 3.3 V logic rail, so the board needs a 5 V rail (or a 5 V-capable CAN
transceiver) for the transceiver's VCC. Section 4 owns the rail decision; flagged
here because it is discovered by this section's datasheet read.

## 6. Discretes

| # | Required | Actual | Verdict |
|---|---|---|---|
| 6.1 | P-FET: Vds >= 40 V, Rds(on) <= 10 mOhm, Vgs rated for 24 V jump | | |
| 6.2 | TVS: standoff ~24 V, clamp < 40 V, rated for the feed current | | |
| 6.3 | PTC: 0.5 A hold at 24 V, trip < 1 A, 4 required | | |
| 6.4 | Schottky OR pair: 40 V, >= 0.5 A, low leakage | | |
| 6.5 | Boost inductor: shielded, saturation current >= 1.5x peak | | |

## Sleep budget roll-up (spec 8.2: target < 200 uA, ceiling 500 uA)

| Contributor | Datasheet value | Source |
|---|---|---|
| ESP32 deep sleep | | |
| EXT0 RTC_PERIPH domain | | |
| CAN transceiver standby | | |
| Buck quiescent | | |
| Low-side switches standby | | |
| PROFET standby | | |
| P-FET gate + divider leakage | | |
| **TOTAL** | | |

## Final BOM decision

| Function | Manufacturer part number | Package | Unit price | Stock |
|---|---|---|---|---|

## Appendix: superseded Section 1 — octal smart low-side switches (FAILED)

Preserved as the evidence record for why the RGB output stage was redesigned
(see Section 1 above). Row 1.1 (open-load detection at 0.14 A, ON-state) failed
for every candidate checked, which is the reason the design moved to discrete
MOSFETs + shunt + mux.

## 1. Octal smart low-side switch (2 required) — RGB channels
Candidates: ST VNI8200XP, Infineon TLE8110ED / TLE8108EM, NXP MC33996

Rows below are evaluated against **Infineon TLE8110ED** (Data Sheet Rev. 1.0,
2018-03-07 / Rev. 1.1, 2021-04-30 — same content for every parameter cited),
because it is the only candidate that provides a per-channel direct PWM input
pin (row 1.5). The other candidates were screened first — see
"Candidate screening" below the table.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1.1 | **GO/NO-GO:** open-load detection resolves a **0.14 A** load, and works in the ON state (not only OFF) | Open load is an **OFF-state-only** diagnosis. Diagnosis register field DRA/DRB, §12.3.2.1 p.64: `DRn[1]x/DRn[0]x = 01` is defined verbatim as "**Open Load in OFF-Mode**"; the ON-state code is `10` = "Over Load, Shorted Load, Over temperature **in ON-Mode**". §12.3.6 p.71 (DEVS.DCCx) confirms: "OFF-State Diagnosis (Detection of open load and short to GND) of CHx is switched OFF. **ON state diagnosis (over current and over temperature detection)** is still active." Mechanism is a VDS comparator, not a load-current comparator: Table 8 §8.2 p.29 — "Open load detection threshold voltage **VDSol 2.00 / 2.60 / 3.20 V**" (P_8.2.1) and "Output pull-down diagnosis current per channel **IDpd 50 / 90 / 150 mA** at VDS = 13.5 V" (P_8.2.2). No load-current detection threshold is specified anywhere in the datasheet, so "resolves a 0.14 A load" is **not a specified parameter** for this part. | **FAIL** — ON-state open-load detection does not exist; the 0.14 A resolution figure is unspecified (VDS-threshold method, OFF state only). See the go/no-go note below the table. |
| 1.2 | Output voltage rating >= 40 V | Abs Max Table 2 p.11: "Continuous Drain Source Voltage **VDSn −0.3 … 45 V**". Table 7 §7.3 p.21: "Output Clamping Voltage, Channel 1 to 10 **VDScl 45 / 55 / 60 V**" (P_7.3.10). Abs-max short-circuit entry p.11: "maximum Voltage for short circuit VDSn 24 V, one event on one channel". | **PASS** — 45 V continuous rating, 45 V min clamp, vs 40 V required (24 V rail + transient headroom). |
| 1.3 | Continuous current per channel >= 0.3 A | §7.1 p.19: "Channel 1 to 4 … nominal current requirement of **1.5 A**", "Channel 5 to 6 … nominal current requirement of **1.7 A**", "Channel 7 to 10 … nominal current requirement of **0.75 A**". RDSon specified at IDnom = 1.5 A / 1.7 A / 0.75 A respectively (Table 7 p.21). | **PASS** — lowest channel group is 0.75 A, vs 0.3 A required (5.4x margin over the 0.14 A load). |
| 1.4 | >= 6 channels per package (2 packages cover 12) | **10 channels** per package. Datasheet title: "Smart Multichannel Low Side Switch with Parallel Control and SPI Interface"; §2 p.6: "The TLE8110ED is equipped with 10 parallel input pins that are routed to each output channel." Pin list §3.2 pp.7-8 shows P_IN1…P_IN10 and OUT1…OUT10. Package PG-DSO-36. | **PASS** — 2 packages give 20 channels for the 12 needed, and allow the 12 to be placed on the low-RDSon groups (see 1.9). |
| 1.5 | Parallel/direct PWM input mode exists, usable at 400 Hz | Feature list p.1: "**Direct Parallel PWM Control of all Channels**". §2 p.6: 10 parallel input pins routed to each output channel (PWM does **not** go over SPI). Table 7 p.21 Timing: "Output Switching Frequency **fOUTx max 20 kHz**" (P_7.3.11); turn-on tdON 5/10 us (P_7.3.12), turn-off tdOFF 5/10 us (P_7.3.13). | **PASS** — 400 Hz is 1/50 of the 20 kHz max; 10 us edges are 0.4% of the 2.5 ms period. Caveat (not a spec violation): §8.1 p.28 Application Hint — "It is recommended to avoid OFF periods of the channel shorter than td(max) (**220 us**) in order to ensure the filter time is expired and the correct diagnosis information is stored", i.e. OFF-state diagnostics need duty <= ~91% at 400 Hz. |
| 1.6 | SPI diagnostics: open load, short to battery, short to GND, overtemperature | Only **four** diagnosis codes exist in total (§8.1 p.27 table, and §12.3.2.1 p.64): `00` Short to Ground (OFF-mode), `01` Open Load (OFF-mode), `10` "**Over Load, Shorted Load, Over temperature** in ON-Mode", `11` No Fault. All four required conditions are *detected*, but short-to-battery (which on a low-side switch appears as overload) and overtemperature are **merged into the single code `10`** and cannot be told apart over SPI. Short-to-GND threshold: Table 8 p.29 "VDSsg 1.00 / 1.50 / 2.00 V" (P_8.2.5), "IDsg −150 / −100 / −50 mA" (P_8.2.6). Note also §8.1 p.27: "No priority scheme is implemented for the diagnosis detection, any new diagnosis entry will override the previous one." | **FAIL** — all four conditions are detected, but the 2-bit register cannot distinguish short-to-battery from overtemperature. If the firmware only needs "a fault on this channel, ON-state class" this is adequate; as written, the criterion is not met. |
| 1.7 | Daisy-chainable on one CS, or 2 CS available in spare GPIO | §2 p.6: "The SPI interface provides **daisy-chain capability** in order to assemble multiple devices in one SPI chain." Protocol detail §12.2.3.4 p.47 "Daisy-Chain and 2x8-bit protocol". | **PASS** — two packages daisy-chain on one CS; no second CS GPIO needed. |
| 1.8 | Standby current <= 20 uA total for both packages | Table 5 §5.2 pp.14-15, standby (EN de-asserted) rows: "Analogue Supply Current during Reset **IDDstb** (VEN < VENI) **typ 1 / max 5 uA** at Tj = 85 C; **typ 2 / max 15 uA** at Tj = 150 C" (P_5.2.10). "Digital Supply Current during Reset **ICCstb** (VRST > VRSTI) **typ 2 / max 5 uA** at Tj = 85 C; **typ 5 / max 15 uA** at Tj = 150 C" (P_5.2.3). Per package at 85 C: typ 3 uA, max 10 uA. **Two packages: typ 6 uA, max 20 uA at 85 C; max 60 uA at 150 C.** Separately, Table 7 p.21 "Output Leakage Current in standby mode **IDoff**" (P_7.3.7-9) is specified max **3 uA** (Ch 1-4), **6 uA** (Ch 5-6), **2 uA** (Ch 7-10) per channel at Tj = 85 C and 8 / 12 / 5 uA at Tj = 150 C — all at **VDS = 13.5 V**, not at the 24 V rail this design uses. | **FAIL** — typical is comfortable (6 uA) but the guaranteed worst case is exactly 20 uA at 85 C with **zero margin**, 60 uA at 150 C, before adding IDoff, which for 12 channels adds up to ~36 uA at 85 C. Worst-case total exceeds the 20 uA criterion. Datasheet note 1) on Table 5: the standby rows are "Parameter not subject to production test. Specified by design." |
| 1.9 | On-resistance, and resulting dissipation at 0.14 A x 12 channels <= 0.2 W | Table 7 §7.3 p.21: RDSon Ch 1-4 "typ **0.3 Ohm** at IDnom = 1.5 A, Tj = 25 C / typ 0.45, **max 0.6 Ohm** at Tj = 150 C" (P_7.3.1); Ch 5-6 "typ **0.25 Ohm** at 25 C / typ 0.35, **max 0.5 Ohm** at 150 C" (P_7.3.2/3); Ch 7-10 "typ **0.6 Ohm** at 25 C / typ 0.85, **max 1.2 Ohm** at 150 C". Worst-case hot dissipation at 0.14 A, 100% duty, using 6 channels per package from groups 1-6 (8x Ch1-4 + 4x Ch5-6): 8 x 0.14^2 x 0.6 + 4 x 0.14^2 x 0.5 = 94 mW + 39 mW = **133 mW**. | **PASS** — 0.133 W vs 0.2 W limit, at max RDSon and Tj = 150 C. **Conditional on channel assignment:** if the 12 channels used include group 7-10 (max 1.2 Ohm), 12 x 0.14^2 x 1.2 = **282 mW** and the criterion FAILS. Layout must place all 12 RGB channels on OUT1-OUT6 of each package. |
| 1.10 | In stock, multi-source or >= 12 month lead visibility | Single-source (Infineon only; no second-source equivalent exists for the parallel-PWM + SPI-diagnostics combination). LCSC product page C540057 (fetched 2026-09-11) shows package DSO-36 and "**Not available now**" with no stock quantity, price or lead time published. Infineon's own part page did not render lifecycle status or distributor stock to an automated fetch. Digi-Key / Mouser / Arrow stock and lead time were not obtained. | **UNVERIFIED** — needs a human to check Digi-Key, Mouser and Arrow for TLE8110EDXUMA1 stock, price and quoted lead time, and to pull Infineon's PCN/lifecycle status (Active vs NRND) from the authenticated Infineon part page. The one data point obtained (LCSC: not available) is a negative signal. |

### Go/no-go outcome for row 1.1

**Row 1.1 FAILS, and it fails for every candidate that was checked — this is not a
TLE8110ED-specific result.** Multichannel smart low-side switches in this class
implement open-load detection as an OFF-state VDS comparison against an internal
diagnostic pull-up/pull-down current source. ON-state open-load detection needs a
per-channel current sense, which none of the verified parts has. Per the task
rules no workaround is proposed here; the resolution (e.g. accepting OFF-phase
diagnostics inside the 400 Hz PWM cycle, or changing the diagnostics requirement)
is a design decision, not a part-selection one.

### Candidate screening

| Candidate | Outcome | Evidence |
|---|---|---|
| **Infineon TLE8110ED** | Best fit; fails 1.1, 1.6, 1.8 | Full datasheet verified — see table above. 10 ch, 45 V, per-channel parallel PWM inputs, SPI daisy-chain. Needs a **5 V analogue rail** (Table 5 p.15: "Analogue Supply Voltage VDD 4.5 … 5.5 V"); digital VCC may be 3.3 V ("Digital Supply Voltage VCC 3 … 5.5 V"). |
| **ST VNI8200XP** | **Not applicable** — wrong topology | ST datasheet title and product page: "Octal **high side** smart power solid state relay with serial/parallel selectable interface on chip". This is a high-side device and cannot serve as the low-side switch. (Also rated 10.5-36 V operating.) |
| **NXP MC33996** | Fails 1.1 and 1.5 | NXP product page (16-Output Switch with SPI Control) states diagnostics as "Output **ON short-to-VBAT** and **OFF short-to-ground/open** detection" — open load is OFF-state only (fails 1.1) — and PWM as "A Pulse-Width Modulation (PWM) control input may be used to pulse width modulate multiple outputs **at the same duty cycle**", i.e. one shared PWM pin, not 12 independent duty cycles (fails 1.5). Page also gives "Load supply voltage min. 0 V, max. 40 V", outputs "voltage clamped (50 V)", "Load current (IL) 0.35 A (Typ)", "current limited (0.9 A)", 16 channels. The full datasheet PDF could not be retrieved (nxp.com/docs blocks automated fetch; Digi-Key and Mouser mirrors returned HTTP 410), so its numeric open-load threshold was never read — recorded as unread, not estimated. |
| **Infineon TLE8108EM** | Not evaluated | Superseded by TLE8110ED in the same family; no datasheet was fetched, so nothing is asserted about it. |
| **Infineon TLE75008-ESD** | Checked as an alternative; fails 1.1 | Datasheet Rev. 1.10 2020-09-02 verified locally. Feature list p.1: "**Open Load detection at OFF state** using Output Status Monitor function"; §5 p.14: "Open Load at OFF state detection, a internal current source IOL can be activated via SPI"; Table §9.5 "Output diagnosis current IOL 70 / 85 / 100 uA at VDS = 3.3 V", "Open Load equivalent ROL 30 … 300 kOhm". Also a 12 V part ("SPIDER+ 12V") with only 2 direct input pins (IN0, IN1) — fails 1.5 as well. |
