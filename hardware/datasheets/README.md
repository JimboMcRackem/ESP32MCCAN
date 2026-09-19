# Datasheets

Source documents used for the verification in `../docs/part-selection.md`. Kept so that any PASS or
FAIL verdict there can be traced back to the document it was read from.

> **The PDFs and PNGs in this folder are gitignored by default.** They are third-party copyrighted
> documents and this repository is **public** — see "Publication" below. The index itself is tracked.

## Chosen parts

| File | Part | Role | Verification |
|---|---|---|---|
| `TJA1042_CAN_transceiver.pdf` | NXP TJA1042T/3 | CAN transceiver | Rows 5.1–5.4 **PASS**. Source of the go/no-go confirmation that standby signals bus wake-up by driving RXD low (Table 4 p.5, §7.1.2). **Rev. 8 (2015), via a Farnell mirror** — nxp.com blocks automated fetch. **Rev. 11 (2023) should be diffed before ordering.** |
| `ADG706_ADG707_analog_mux.pdf` | ADI ADG706BRU/BRUZ | 16:1 analog mux for the RGB sense chain | Rows 1c.1–1c.6 **PASS**. RON 6 Ω typ / 11–12 Ω max at 3 V, leakage ≤1.5 nA, pinout and truth table confirmed. **Rev. A is a 2002 document — confirm the current analog.com revision still matches.** |
| `infineon_bts7008_2epa_datasheet_en.pdf` | Infineon BTS7008-2EPA | Dual smart high-side switch for the Denali pair | **Rev. 1.21, 2024-07-29.** Added 2026-09-15, and it closed the Task 8 blocker. Source for: the pinout (Table 2 p.6 — VS is the **exposed pad**, each output is three pins), kILIS = 5400/5450 (Table 22 p.53) which sizes R81 at 2.2 kΩ, IIS(SAT) and the saturation voltage (Table 20 p.50) which is why R83 exists, the suggested external components (Table 24 p.54), and the thermal resistances (Table 6 p.11) that quantify row 2.6. |
| `tps1686.pdf` | TI TPS1686x | Candidate for F1, the board-mount eFuse | **SLVSHR6A, Nov 2025.** Adjustable 1-10 A limit at +-3%, adjustable transient blanking timer (the flash-to-pass discriminator), 92 V abs max, FLT pin plus a +-3% analog current monitor. **Fails the <=8 mOhm requirement at 15.7 mOhm typ / 26.5 mOhm max**, and the datasheet contradicts itself on which suffix auto-retries. See part-selection.md. |
| `LTC4380.pdf` | ADI LTC4380 | **Leading candidate for F1 - and for replacing Q1 with it.** Surge stopper with overcurrent protection | **Rev. C.** Drives *back-to-back* N-FETs, so it does reverse polarity AND overcurrent in one conduction path - which DELETES Q1's 0.78 W rather than adding to it. 4-72 V, AEC-Q100, 8 uA Iq, auto-retry on the -2/-4 suffixes (stated three times, consistently - unlike the TPS1686). Current limit is R_SNS with a fixed 50 mV (45-55 mV) threshold. **Gating open item: the FET runs LINEAR during clamping, so it needs an SOA curve, not an R_DS(on) number.** See part-selection.md. |
| `lm5069.pdf` | TI LM5069 | Candidate for F1, hot-swap controller + external FET | **SNVS452G, Jan 2020.** 9-80 V, 55 mV current-limit threshold, programmable fault timer and power limiting, latched and auto-restart versions. **Rejected on thermals: it does NOT block reverse polarity, so Q1 stays in the path - and with Q1's 0.78 W plus a 0.30 W sense resistor the route lands at ~66 C even with a zero-ohm FET.** Not automotive-qualified. See part-selection.md. |
| `NVMFD5877NL-D.PDF` | onsemi NVMFD5877NL | Candidate pass FET for the LTC4380 back-to-back pair | **Rev. 11, May 2025.** Dual N-ch, 60 V, Dual SO8FL, AEC-Q101, and it carries the **Forward Biased SOA curve (Figure 11)** the route needs. **REJECTED on R_DS(on): 31 mOhm typ / 39 mOhm max at VGS = 10 V, against a <=7.5 mOhm ceiling - back-to-back that is 62 mOhm and 3.04 W, putting the board at ~85 C.** Its free-air I_D (5-6 A) is also below the 7.0 A night load. Established one useful fact for the next candidate: the LTC4380 drives the gate 10-14 V above OUT, so the pass FETs do NOT need to be logic-level. See part-selection.md. |
| `cmf_automotive_signal_act45b_en.pdf` | TDK ACT45B-510-2P-TL003 | CAN common-mode choke (L6) | Source of the L6 land pattern (pads 1.35 x 0.90 mm at +-2.275/+-1.25, scale cross-checked at 16.125-16.129 u/mm on four dimensions) **and of the winding topology that exposed the L_Coupled pin-numbering defect** - windings are 1-4 and 2-3, not 1-2 and 3-4. |
| `esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf` | Espressif ESP32-WROOM-32E-N8 | The module | Supplied 2026-09-19. Carries the antenna keep-out specification needed for Task 8 placement. **Not yet read** - the EN reset RC (R22/C37) also remains UNVERIFIED pending Espressif's hardware-design guidelines, which is a different document. |
| `Littelfuse_1206L_PTC_series.pdf` | Littelfuse 1206L series | Resettable PTC, one per RGB string | Row 6.3 **FAILS — family-wide.** This PDF is the evidence: its own p.2 derating table (0.33 A @ 60 °C, 0.29 A @ 70 °C) puts the best 24 V-rated part, 1206L050/24, at only **0.31 A at 65 °C** against a 0.42 A sustained load. Needs a larger family — 1812L, Bourns MF-SMD or TE miniSMDC. |
| `PMV60ENEA_fig6_output_characteristics.png` | Nexperia PMV60ENEA | RGB low-side switching MOSFET (×12) | Row 1a.2 **PASS**. This figure *is* the evidence: the output-characteristic curve sits clearly above 0.5 A at Vgs ≤ 3.3 V. Read **qualitatively** — no precision is claimed from a graph. |
| ~~`SMBJ24A_TVS.pdf`~~, ~~`SMBJ_series_TVS.pdf`~~ | **NEITHER IS AN SMBJ24A DATASHEET** | — | **See "Correction" below.** `SMBJ24A_TVS.pdf` is a Diodes Inc. **wafer-fab process-change notice** with no electrical specifications; `SMBJ_series_TVS.pdf` is an unrelated **Powerex SCR/diode module** datasheet. **Row 6.2 is nonetheless CLOSED as of 2026-09-18** — by `smbj.pdf`, a genuine Bourns SMBJ series datasheet that was already in this folder, unindexed. See the section below. |

## Added later — indexed 2026-09-18

**These thirteen files were in the folder but not in this index.** That gap had a real cost: row 6.2
of `../docs/part-selection.md` sat **UNVERIFIED across two sessions and nine failed fetch attempts**,
with a note that "a human must obtain a genuine PDF by a non-automated channel" — while
**`smbj.pdf`, a genuine primary datasheet, was already here.** *List the directory before concluding
a document is unobtainable.*

| File | Part | Role | Status |
|---|---|---|---|
| `smbj.pdf` | **Bourns SMBJ TVS series** (600 W, standoff 5–495 V) | Front-end clamp D2 = SMBJ24A | **CLOSES ROW 6.2 — 2026-09-18.** V<sub>RWM</sub> 24.0 V, V<sub>BR</sub> 26.7–29.5 V, **V<sub>C</sub> 38.9 V @ 15.5 A (10/1000 µs)**, **V<sub>C</sub> 50.6 V @ 77.5 A (8/20 µs)**. The 8/20 figure appears in **no distributor summary** and changes C3 to 63 V — see "Correction 2" in part-selection.md. **Read with care: `pdftotext -layout` staggers the three column blocks against each other**; the alignment was pinned from the document itself (V<sub>C</sub>/V<sub>BR(max)</sub> ≈ 1.31 across the series, +2-line offset), not assumed |
| `sqj461ep.pdf` | Vishay **SQJ461EP** | Reverse-polarity P-FET Q1 | The **60 V** replacement for the 40 V SQJ415EP. Task 7 finding **F1** — the schematic still carried the old number five days after the swap |
| `lm5164.pdf` | TI **LM5164** | 3.3 V and 5 V bucks U1/U2 | Selected. 100 V input rating clears the TVS clamp with large margin |
| `lm51571-q1.pdf` | TI **LM51571-Q1** | 24 V boost U3 | Selected, **non-synchronous**. Source of the 37.4k MODE value and the 2.6 µA typ / 5 µA max shutdown bias. **Its "transient protection up to 50 V" is at/just past the SMBJ24A's 50.6 V 8/20 clamp** — re-examine at EMI pre-scan |
| `DML3017LDC.pdf` | Diodes **DML3017LDC** | `+3V3_SW` load switch U4 | Selected. **Pin-1 orientation of V-DFN3030-12 is still ambiguous between the two figures in DS46371** — resolve from the package outline in Task 8, do not infer |
| `NX5020UNBKS.pdf` | Nexperia **NX5020UNBKS** | RGB low-side FETs, 6 dual packages = 12 channels | Selected. Built as a 2-unit symbol. 50 V, characterised at Vgs 2.5 V |
| `NX3020NAKW-Q.pdf` | Nexperia NX3020NAKW-Q | Considered for the same role | Not selected |
| `ss5ph102.pdf` | Vishay **SS5PH102** | Boost rectifier D4 | Selected — VRRM 100 V, IF(AV) 5 A, VF 0.70 V at 5 A, SMPC (TO-277A) |
| `xal7070.pdf` | Coilcraft **XAL7070** series | **Buck inductors L4/L5** | **Candidate found: XAL7070-223ME**, 22 µH, DCR 34.51 typ / 39.69 max mΩ, Isat 6.3 A, AEC-Q200 shielded. Comfortably clears the Isat ≥ 1.5 A requirement. Also holds a 2.2 µH part (11.2 mΩ, Isat 19.6 A) which **misses** L1's 8 mΩ budget |
| `xal4000.pdf` | Coilcraft XAL40xx series | Smaller siblings | Tops out around 2.2 µH; too small for the 7 A input path |
| `Panasonic_Inductor Hi Performance (ETQP_M__Y__ Series)  020626.pdf` | Panasonic **PCC-M / ETQP** automotive power chokes | **Input inductor L1** | **Candidate found: PCC-M1050M series**, low-value parts at **3.8–5.9 mΩ**, Isat ~18–21 A, 10.0 × 10.7 × 5.4 mm — inside the ≤ 8 mΩ budget at the ~2.2–2.5 µH the review recommends over 10 µH |
| `xcl105.pdf` | Torex XCL104/XCL105 | Inductor-integrated step-up converter | Considered for the 24 V boost and **not selected** — 1.4 A class, far too small |
| `xp202a0003mr.pdf` | Torex XP202A0003MR | P-channel 4 V MOSFET, SOT-23 | Considered and not selected for Q1 — nowhere near the 7 A / 60 V requirement |
| `DIOD-S-A0006646639-1.pdf` | Diodes **DMHT3006LFJ** 30 V N-channel H-bridge | — | Not used by this design |

> **The two inductor candidates are identified, not selected.** `pdftotext -layout` staggers the
> column blocks in both files, so the part-number ↔ value alignment must be confirmed before
> ordering. Task 8 pins them.

**Still genuinely missing** — see `NEEDED.md`: the **input CM choke L2** (7 A), the **CAN CM choke
L6**, the **CAN ESD D6/D7**, the **PCA9685**, the **Espressif hardware-design guidelines** (for the
unverified EN reset RC) and the **ESP32-WROOM-32E-N8 module datasheet** (for the antenna keep-out).

## Supplied 2026-09-18 — six files, five usable

Full read-out in `../docs/part-selection.md`, "Parts selected 2026-09-18".

| File | Part | Role | Verification |
|---|---|---|---|
| `ihlp-4040dz-01.pdf` | Vishay **IHLP-4040DZ-01** | **Input pi-filter inductor L1** | **SELECTED — 1.5 uH recommended**: DCR 5.30 typ / **5.80 max mOhm**, Isat 27.5 A, 0.28 W at 7.0 A, inside F4's 8 mOhm budget. The 2.2 uH part is 9.00 mOhm max and **misses it by 12.5%**. 10.16 x 10.16 x 4.0 mm; KiCad ships `Inductor_SMD:L_Vishay_IHLP-4040`. **Caveat: this is the COMMERCIAL series — AEC-Q200 appears nowhere in it.** Order the automotive IHLP variant for a vehicle |
| `cmf_automotive_signal_act45b_en.pdf` | TDK **ACT45B-510-2P-TL003** | **CAN common-mode choke L6** | **SELECTED.** 51 uH — matches L6's placeholder exactly. AEC-Q200, -40 to +150 C, CAN-BUS named as the application. DCR 1.0 Ohm max, rated 0.2 A (the node is listen-only, so it never transmits). Body 4.5 x 3.2 x 2.8 mm. **Note the value code: -510 is 51 uH; -101 is 100 uH.** **No KiCad footprint exists** — `L_CommonModeChoke_Coilank_ACM4532` is the right size class but its land pattern must be checked against the drawing |
| `PESD2CANFD24U-T.pdf` | Nexperia **PESD2CANFD24U-T** | **CAN ESD D6/D7** | **SELECTED — and it replaces BOTH placeholders with one part.** Single dual-line protector, SOT23, pins K1/K2/CC. VRWM 24 V, VCL 33 V typ / 43 V max at 1 A (8/20 us), 15 kV IEC 61000-4-2, Cd 3.5 pF, **AEC-Q101**, Tj 175 C. KiCad ships `Package_TO_SOT_SMD:SOT-23`. **This is a schematic change for `gen_mcu_can.py`, not just a BOM entry** |
| `PCA9685.pdf` | NXP **PCA9685** (order **PCA9685PW/Q900**) | RGB PWM controller U7 | **ALL FOUR OPEN QUESTIONS ANSWERED, NO DEFECT FOUND.** EXTCLK to GND is correct — pin-table footnote [2] says it "must be grounded when this feature is not used". `~OE` LOW is correct — 7.4 says LOW enables the outputs, so the Task 6 deviation was right. A0-A5 to GND gives 0x40. Outputs are **totem-pole by default** with LEDn **LOW at power-on reset**. **New firmware contract (Table 12 fn [3], Fig 13): for an external N-type driver the optimum is INVRT = 0, OUTDRV = 1 — both reset defaults, so leave MODE2 alone; INVRT = 1 would invert all twelve channels.** `/Q900` is **the only AEC-Q100 variant**. TSSOP28 SOT361-1 -> `Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm` |
| `esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf` | Espressif **ESP32-WROOM-32E-N8** | MCU module U5 | **CLOSES TWO OPEN ITEMS.** (1) **The EN reset RC is VERIFIED** — Figure 8's notes recommend "R = 10 kOhm and C = 1 uF", exactly the fitted R22/C37, which had been UNVERIFIED since Task 5. (2) **The pin table cross-checks completely** — all 19 assignments match Figure 3. Variant confirmed: 8 MB Quad SPI, no PSRAM, **18.0 x 25.5 x 3.1 mm**, -40 to +85 C (the 105 C parts are the H suffixes). KiCad ships `RF_Module:ESP32-WROOM-32E`. **The antenna keep-out DIMENSIONS are not in this document** — it defers to the Hardware Design Guidelines, still needed for Task 9 |
| `Accu-L-Automotive.pdf` | Vishay **Accu-L** thin-film RF inductors, L0402/L0805 | **none — not usable** | **NOT APPLICABLE TO THIS BOARD.** A high-Q RF/microwave matching inductor series for GPS, radar and telematics: values in **nanohenries** (from 0.56 nH), current ratings in **milliamps** (500-750 mA). AEC-Q200 and genuinely an inductor, which is presumably why it was picked up, but three orders of magnitude away from the 7 A power choke L2 needs |

## Supplied 2026-09-18 (later the same day) — the last blocking part

| File | Part | Role | Verification |
|---|---|---|---|
| `bourns_pm3700_cm_choke.pdf` | Bourns **PM3700-10-RC** | **Input common-mode choke L2** | **SELECTED — this closes review finding F4 and the blocking list.** 0.2 mH min, **DCR 0.008 Ohm (8 mOhm) max per winding**, **Irms 7.0 A**, leakage 1.6 uH typ, 20 dB over 5-55 MHz. **The only part in the series rated for the 7.0 A night load** — the next one down is 6.0 A. With L1 at 1.5 uH the pair is **21.80 mOhm against F4's 22 mOhm ceiling** and ~1.07 W, giving a ~2.87 W night total against the plate's ~2.9 W. **0.9% margin.** -55 to +125 C, 500 Vrms between windings, **no AEC-Q200 statement**. **21.6 x 17.78 x 11.5 mm — the part that drives the board outline and enclosure height; NO KiCad footprint exists.** Read with care: `pdftotext -layout` interleaves the dimension drawing with the parametric table and staggers the columns by two rows; the alignment was pinned from the **EIA part-marking code, which matches the inductance column 8 for 8** (201 = 200 uH ... 203 = 20 mH), and corroborated by the Features line "Current rating up to 7 A" |

| `sm_pl_filter.pdf` | Coilcraft **CG3885-AL** (Document 1194P) | **Alternative for L2** | **Supplied as a headroom check, and it answers that question NO.** Fifteen power-line CM chokes; **only CG3885-AL meets 7.0 A** and it is also the lowest-DCR part in the book: 0.47 mH nom / **0.30 mH min per winding**, **Irms 10.0 A**, **DCR 8.0 mOhm max per winding** (footnote 4 is explicit), isolation 1000 Vrms, -40 to +85 C at Irms. **Its DCR is IDENTICAL to the PM3700's**, so the F4 sum stays 21.80 mOhm and the loss stays 1.07 W -- **the tight margin does not improve.** What it buys is current margin (10 A vs 7 A, so the night load sits at 70% of rating instead of 100%, ~15 K cooler), 50% more CM inductance and 2x isolation. What it costs is **2.1x the board area** -- 31.0 x 26.0 x 12.7 mm against 21.6 x 17.78 x 11.5 mm -- plus 15.3 g of mass. Dimensions tied to the part via the **page-number ordinal** (its detail page is 1194P-16), since the summary table's columns are staggered |

**Every electrical part is now selected.** What remains is documentary: the **Espressif Hardware
Design Guidelines** for the antenna keep-out dimensions (Task 9). See `NEEDED.md`.

| `wurth_we-cmbnc_7448031002.pdf` | Wurth **WE-CMBNC 7448031002** | **Input CM choke L2 -- RECOMMENDED** | **The best of the three and the only AEC-Q200 part.** Nanocrystalline: **2 mH** (vs 0.2 mH ferrite), **rated 10 A**, **DCR 6.3 mOhm max**, insulation 2100 V AC, **AEC-Q200 Grade 1**, -55 to +125 C, rise < 55 K at rated current. Nanocrystalline permeability is ~10x ferrite, so far fewer turns give more inductance at less resistance -- a different technology, not a better ferrite. **F4 improves for the first time: 18.40 mOhm total against the 22 mOhm ceiling (16.4% margin, vs 0.9% for both ferrite parts), 0.90 W, night total ~2.70 W.** It also un-couples the L1 choice -- even the 2.2 uH IHLP passes with it. **Costs: it is THROUGH-HOLE** (hole pattern 7.5 x 10.7 mm, 1.3 mm holes) on an otherwise-SMD board, and the **tallest candidate at ~17 mm**. Two items to confirm before ordering: whether 6.3 mOhm is per winding (assumed, conservative) or total, and the derating curve at the 65 C internal ambient |

**L2 candidates, side by side.** All three clear F4; only one clears it comfortably.

| | Bourns PM3700-10-RC | Coilcraft CG3885-AL | **Wurth 7448031002** |
|---|---|---|---|
| DCR per winding | 8.0 mOhm | 8.0 mOhm | **6.3 mOhm** |
| F4 total with L1 | 21.80 mOhm | 21.80 mOhm | **18.40 mOhm** |
| Margin on 22 mOhm | 0.9% | 0.9% | **16.4%** |
| Loss at 7.0 A | 1.07 W | 1.07 W | **0.90 W** |
| Rated current | 7.0 A | 10.0 A | **10 A** |
| Lcm | 0.2 mH | 0.30 mH | **2 mH** |
| Isolation | 500 Vrms | 1000 Vrms | **2100 V AC** |
| AEC-Q200 | no | no | **Grade 1** |
| Mounting | SMD | SMD | **through-hole** |
| Size (mm) | **21.6 x 17.8 x 11.5** | 31.0 x 26.0 x 12.7 | 25.0 x 24.0 x ~17.0 |

**Recommendation: the Wurth.** It is the only automotive-qualified option, and the only one that
gives the thermal budget real margin. The price is a through-hole part on an SMD board and ~4.3 mm
of extra height -- both enclosure/assembly questions rather than electrical ones.

## Considered and rejected — kept as evidence

These justify the single largest design decision in the project: that the RGB output stage could not
use multichannel smart low-side switches.

| File | Part | Why it is here |
|---|---|---|
| `REJECTED_TLE8110ED_octal_low_side_switch.pdf` | Infineon TLE8110ED | **The evidence for the row 1.1 category failure.** Diagnosis code `01` is defined verbatim as "Open Load in **OFF-Mode**"; ON-mode codes cover only overload/short/overtemperature. Detection is a VDS comparator (VDSol 2.00/2.60/3.20 V, 50/90/150 mA injected pull-down) — there is **no load-current threshold at all**, so 0.14 A is unspecified rather than out of range. Also failed rows 1.6 and 1.8. |
| `REJECTED_TLE75008_octal_low_side_switch.pdf` | Infineon TLE75008 | Same category, same limitation. Confirms the failure is a property of the part class, not one vendor. |
| `REJECTED_IRLZ44N_fig1_output_characteristics.png` | Infineon IRLZ44N | Briefly selected, then **rejected by the controller**: a 55 V / 47 A **TO-220 through-hole power brick** for a 0.14 A load. Twelve would dominate the board and force through-hole assembly. Its 25 µA leakage × 12 was also what appeared to blow the sleep budget — a symptom of the wrong package, not a real problem. |
| `ALTERNATE_ADG726_ADG732_dual_mux.pdf` | ADI ADG726/ADG732 | Dual 16:1 / single 32:1. Considered, then dropped for ADG706 — the single 16:1 is the right shape. |
| `PMV30ENEA_fig6_output_characteristics.png` | Nexperia PMV30ENEA | Qualifies **technically** as a second source (its curve confirms Id >= 0.5 A at Vgs <= 3.3 V), but **does NOT relieve the sourcing problem** — also backordered at Digi-Key and unavailable at Mouser, apparently the same fab constraint as the PMV60ENEA. |

## Correction — the "easy win" was not real

An earlier version of this file claimed `SMBJ24A_TVS.pdf` was a genuine 268 KB SMBJ24A datasheet and
that opening it would close row 6.2. **That claim was wrong, and it was made from the file size and a
valid PDF header without reading the contents.** On actually opening them:

- `SMBJ24A_TVS.pdf` is a **Diodes Inc. wafer-fabrication process-change notice** — no electrical
  characteristics at all
- `SMBJ_series_TVS.pdf` is a **Powerex SCR/diode module** datasheet, an unrelated part

Row 6.2 was therefore left open, and nine fetch attempts across two sessions failed (403 / timeout
from Mouser, Bourns, ST and Littelfuse), with the conclusion that "closing it needs a human to
download a genuine SMBJ24A datasheet in a browser."

> **That conclusion was wrong, and in a second way (2026-09-18).** A human *had* already supplied
> one: **`smbj.pdf`** — a genuine Bourns SMBJ-series datasheet — was sitting in this directory the
> whole time, absent from this index and uncited by row 6.2. The first correction was calling a file
> a datasheet without reading it; **the second was calling a datasheet absent without listing the
> directory.** Row 6.2 is now **CLOSED**.

Distributor summary figures (standoff 24 V, VBR min 26.7 V, clamping max 38.9 V, 600 W) would pass the
criteria on their face, but a distributor summary is not a primary source, which is this record own
standard.

## Not copied here

- **Failed downloads.** Several scratchpad files were saved with a `.pdf` extension but are ~13.9 KB
  error or block pages, not datasheets. Excluded deliberately.
- **A duplicate.** `t.pdf` was a second copy of the TLE8110ED datasheet.
- **Text extractions.** The verifying agents saved `.txt` dumps of several PDFs. Redundant where the
  PDF itself is present.
- **MC33996.** No primary datasheet was ever retrievable (NXP blocks automated fetch; distributor
  mirrors returned HTTP 410). Its rows in `part-selection.md` are labelled as product-page data.

## Publication

These are **third-party copyrighted documents** and this repository is **public**. Redistributing
vendor datasheets is common practice in hardware repositories, but some manufacturers' terms prohibit
it, so they are **gitignored by default** rather than published on your behalf.

To publish them anyway, remove the `datasheets/*.pdf` and `datasheets/*.png` lines from
`hardware/.gitignore`. To keep them private but backed up, copy the folder somewhere outside the repo.

Either way, nothing is lost locally — the files are on disk in this folder.
