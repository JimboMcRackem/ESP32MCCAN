# Part Selection Verification Record

Every criterion below comes from the spec. A part may be chosen ONLY if every
row for it reads PASS. Candidate families are suggestions, not decisions.

## 1. Octal smart low-side switch (2 required) — RGB channels
Candidates: ST VNI8200XP, Infineon TLE8110ED / TLE8108EM, NXP MC33996

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1.1 | **GO/NO-GO:** open-load detection resolves a **0.14 A** load, and works in the ON state (not only OFF) | | |
| 1.2 | Output voltage rating >= 40 V | | |
| 1.3 | Continuous current per channel >= 0.3 A | | |
| 1.4 | >= 6 channels per package (2 packages cover 12) | | |
| 1.5 | Parallel/direct PWM input mode exists, usable at 400 Hz | | |
| 1.6 | SPI diagnostics: open load, short to battery, short to GND, overtemperature | | |
| 1.7 | Daisy-chainable on one CS, or 2 CS available in spare GPIO | | |
| 1.8 | Standby current <= 20 uA total for both packages | | |
| 1.9 | On-resistance, and resulting dissipation at 0.14 A x 12 channels <= 0.2 W | | |
| 1.10 | In stock, multi-source or >= 12 month lead visibility | | |

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
