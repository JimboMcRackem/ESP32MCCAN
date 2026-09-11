# Part Selection Verification Record

Every criterion below comes from the spec. A part may be chosen ONLY if every
row for it reads PASS. Candidate families are suggestions, not decisions.

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

| # | Required | Actual | Verdict |
|---|---|---|---|
| 5.1 | **GO/NO-GO:** standby mode signals bus wake-up by driving RXD LOW | | |
| 5.2 | VIO pin for 3.3 V logic (the /3 suffix) | | |
| 5.3 | Standby current <= 20 uA | | |
| 5.4 | TXD can be left pulled to VIO (recessive) with no fault latch | | |

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
